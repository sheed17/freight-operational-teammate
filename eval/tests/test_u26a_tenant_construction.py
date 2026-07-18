"""U2.6A — explicit tenant identity at the WorkflowStore construction boundary.

READ THIS BEFORE TRUSTING ANY OF IT:

    U2.6A binds a tenant. It does NOT make persistence tenant-safe.

The 22 affected store methods still issue their original unscoped SQL, and the schema is still the
pre-migration one. A store that knows its tenant and does not use it is exactly that — and calling
this "tenant isolation" would be the most expensive lie in the phase. Query scoping is U2.6B (all 22
together, because a store where some methods are scoped and others are not READS as safe, which is
worse than one where none are). Schema activation is U2.6C.

What this file proves is narrower and real: no code path anywhere can obtain a WorkflowStore without
naming whose data it is about to touch.
"""

import ast
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freight_recon.tenant import FORBIDDEN_TENANTS, InvalidTenant, MissingTenant, require_tenant
from freight_recon.workflow import WorkflowStore
from phase0.evaluation import Evaluation
from phase0.sources import ROOT, python_files, rel

FIXTURE_A, FIXTURE_B = "tenant-fixture-a", "tenant-fixture-b"


def _refusal_probe_lines(tree: ast.AST) -> set[int]:
    """Lines inside a `with pytest.raises(...)` block.

    A WorkflowStore built there is a REFUSAL PROBE: the test asserts the construction fails, so
    counting it would make the guard report the very defect it exists to prove is absent. This is
    decided STRUCTURALLY rather than by exempting filenames - three separate guards in this program
    enumerated the files they knew about and silently stopped covering the ones added afterwards.
    """
    out: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.With, ast.AsyncWith)):
            continue
        raises = False
        for item in node.items:
            call = item.context_expr
            if isinstance(call, ast.Call):
                fn = call.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                if name == "raises":
                    raises = True
        if raises:
            for child in ast.walk(node):
                if hasattr(child, "lineno"):
                    out.add(child.lineno)
    return out


def _sites():
    """Every real WorkflowStore(...) call, by AST. Text matching would count comments and strings."""
    ev = Evaluation(name="u26a.construction_sites")
    out = []
    for p in python_files(ROOT / "src", ROOT / "scripts", ROOT / "eval"):
        # This file's refusal probes are excluded STRUCTURALLY by _refusal_probe_lines, not by
        # skipping the file. Skipping the file also hid its LEGITIMATE construction sites from the
        # guard, which is a hole exactly the size of one test module.
        ev.sources_inspected.append(rel(p))
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        probes = _refusal_probe_lines(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "WorkflowStore":
                kw = {k.arg: k.value for k in node.keywords}
                is_probe = node.lineno in probes
                # EVERY site enters the population, probe or not. Excluding probes from the count
                # as well as the check would let a widened exemption shrink the denominator
                # silently - and a guard that inspects fewer things while still reporting green is
                # the exact failure this floor exists to catch.
                ev.candidates.append(f"{rel(p)}:{node.lineno}")
                ev.accepted.append((rel(p), node.lineno, kw.get("tenant")))
                out.append((rel(p), node.lineno, kw.get("tenant"), is_probe))
    return out, ev


# ------------------------------------------------------------------ the constructor itself (1-6)

def test_1_workflowstore_cannot_be_constructed_without_tenant(tmp_path):
    with pytest.raises(TypeError):
        WorkflowStore(tmp_path / "w.sqlite3")          # type: ignore[call-arg]


def test_2_to_5_rejects_none_empty_blank_and_every_sentinel(tmp_path):
    for bad in (None, "", "   ", "\t\n"):
        with pytest.raises((MissingTenant, InvalidTenant)):
            WorkflowStore(tmp_path / "w.sqlite3", tenant=bad)   # type: ignore[arg-type]
    assert len(FORBIDDEN_TENANTS) >= 15, "the sentinel list has been thinned"
    for sentinel in FORBIDDEN_TENANTS:
        with pytest.raises(InvalidTenant):
            WorkflowStore(tmp_path / "w.sqlite3", tenant=sentinel)
        with pytest.raises(InvalidTenant):
            WorkflowStore(tmp_path / "w.sqlite3", tenant=sentinel.upper())   # casing is not a loophole


def test_6_tenant_is_immutable_for_the_store_lifetime(tmp_path):
    """Rebinding an open store would make every prior read and write ambiguous after the fact."""
    s = WorkflowStore(tmp_path / "w.sqlite3", tenant=FIXTURE_A)
    try:
        assert s.tenant == FIXTURE_A
        with pytest.raises(AttributeError):
            s.tenant = FIXTURE_B        # type: ignore[misc]
    finally:
        s.close()


def test_tenant_is_keyword_only_so_it_cannot_be_passed_positionally_by_accident():
    import inspect
    p = inspect.signature(WorkflowStore.__init__).parameters["tenant"]
    assert p.kind is inspect.Parameter.KEYWORD_ONLY
    assert p.default is inspect.Parameter.empty, "tenant acquired a default"


# ------------------------------------------------------------- CallbackAppConfig (7-8)

def test_7_and_8_callbackappconfig_requires_and_validates_tenant():
    from freight_recon.action_callback import CallbackAppConfig
    import dataclasses

    fields = [f.name for f in dataclasses.fields(CallbackAppConfig)]
    assert fields[0] == "tenant", "tenant must be first and required, not an optional afterthought"
    import inspect
    params = inspect.signature(CallbackAppConfig.__init__).parameters
    assert params["tenant"].default is inspect.Parameter.empty, "tenant acquired a default"
    required = [n for n, p in params.items()
                if n != "self" and p.default is inspect.Parameter.empty]
    for bad in ("", "default", "test", None):
        kwargs = {n: "x" for n in required}
        kwargs["tenant"] = bad
        with pytest.raises((MissingTenant, InvalidTenant)):
            CallbackAppConfig(**kwargs)   # type: ignore[arg-type]


# ------------------------------------------------------- every construction site (9-10, 14-18)

def test_9_and_10_every_construction_site_supplies_an_explicit_tenant():
    sites, ev = _sites()
    ev.require_population(minimum=100)
    missing = [f"{f}:{ln}" for f, ln, t, probe in sites if t is None and not probe]
    assert not missing, (
        f"{len(missing)} WorkflowStore construction site(s) supply no tenant:\n  "
        + "\n  ".join(missing[:12])
    )


def test_the_refusal_probe_exemption_stays_a_narrow_exception():
    """The exemption must stay small and must never touch production.

    Widening it is the cheap way to make this guard green: exempt enough and there is nothing left
    to check. Mutation proved that a blanket exemption slipped past the population floor alone.
    """
    sites, _ = _sites()
    assert sites, "no construction sites - this test would pass over an empty set"
    probes = [(f, ln) for f, ln, _t, probe in sites if probe]
    assert probes, "no refusal probes found - the exemption mechanism is not being exercised"
    assert len(probes) <= len(sites) // 10, (
        f"{len(probes)} of {len(sites)} construction sites are exempted as refusal probes - "
        "the exception has become the rule"
    )
    leaked = [f"{f}:{ln}" for f, ln in probes if not f.startswith("eval/")]
    assert not leaked, f"production code exempted as a refusal probe: {leaked}"


def test_14_no_production_site_uses_a_fixture_tenant():
    """A fixture value in production is a test tenant owning real rows."""
    sites, ev = _sites()
    ev.require_population(minimum=100)
    leaked = [
        f"{f}:{ln}" for f, ln, t, _probe in sites
        if not f.startswith("eval/") and isinstance(t, ast.Constant)
        and isinstance(t.value, str) and "fixture" in t.value.lower()
    ]
    assert not leaked, f"production site(s) using a fixture tenant: {leaked}"


def test_15_no_construction_site_hardcodes_a_sentinel_tenant():
    sites, ev = _sites()
    ev.require_population(minimum=100)
    bad = [
        f"{f}:{ln} -> {t.value!r}" for f, ln, t, _probe in sites
        if isinstance(t, ast.Constant) and isinstance(t.value, str)
        and t.value.strip().lower() in FORBIDDEN_TENANTS
    ]
    assert not bad, f"sentinel tenant hardcoded at: {bad}"


def test_no_production_site_hardcodes_any_string_tenant():
    """A production tenant must come from config or an operator — never a literal in the source."""
    sites, ev = _sites()
    ev.require_population(minimum=100)
    literals = [
        f"{f}:{ln} -> {t.value!r}" for f, ln, t, _probe in sites
        if not f.startswith("eval/") and isinstance(t, ast.Constant) and isinstance(t.value, str)
    ]
    assert not literals, (
        "production construction site(s) hardcode a tenant literal:\n  " + "\n  ".join(literals)
        + "\nA hardcoded tenant is the same defect as a default, spelled once per file."
    )


def test_18_a_zero_site_enumeration_fails_rather_than_passing_vacuously():
    """A negative over an empty population proves nothing — the M-9 family, guarded."""
    ev = Evaluation(name="u26a.empty", sources_inspected=["x.py"])
    from phase0.evaluation import EmptyPopulationError
    with pytest.raises(EmptyPopulationError):
        ev.require_population(minimum=1)


# --------------------------------------------------------------- tenant sources (11-13)

def test_11_the_migration_tool_requires_an_explicit_assertion():
    src = (ROOT / "scripts" / "report_legacy_commit_identities.py").read_text()
    assert '"--tenant", required=True' in src.replace("'", '"'), "the tool may pick its own tenant"
    assert "OPERATOR ASSERTION" in src


def test_12_a_missing_production_tenant_fails_before_any_persistence():
    from freight_recon.cli_tenant import resolve_cli_tenant
    with pytest.raises(MissingTenant):
        resolve_cli_tenant(context="a production entry point with no source")


def test_13_two_tenants_get_independent_store_instances(tmp_path):
    a = WorkflowStore(tmp_path / "a.sqlite3", tenant=FIXTURE_A)
    b = WorkflowStore(tmp_path / "b.sqlite3", tenant=FIXTURE_B)
    try:
        assert a.tenant != b.tenant
    finally:
        a.close(); b.close()


def test_the_canonical_source_is_the_client_configs_client_id():
    from freight_recon.cli_tenant import tenant_from_client_config
    got = tenant_from_client_config(ROOT / "configs" / "clients" / "rasheed_first_design_partner.yaml")
    assert got == "rasheed_first_design_partner"


def test_no_ambient_thread_local_or_process_wide_current_tenant():
    """Tenant travels with the call. An ambient current-tenant is a global with better manners."""
    ev = Evaluation(name="u26a.ambient_tenant")
    offenders = []
    for p in python_files(ROOT / "src"):
        ev.sources_inspected.append(rel(p))
        text = p.read_text(encoding="utf-8")
        ev.accepted.append(rel(p))
        for pattern in ("threading.local", "contextvars", "CURRENT_TENANT", "_current_tenant",
                        "set_current_tenant", "global tenant"):
            if pattern in text:
                offenders.append(f"{rel(p)}: {pattern}")
    ev.require_population(minimum=40)
    assert not offenders, f"ambient tenant machinery: {offenders}"


# ------------------------------------------------------------------- what this does NOT claim

def test_the_tenant_boundary_is_now_complete_not_merely_bound():
    """SUPERSEDED BY U2.6BC — and this is the assertion it was always waiting for.

    U2.6A deliberately shipped a test saying "a store that knows its tenant and does not use it is
    exactly that", so nobody could mistake a construction boundary for isolation. That intermediate
    state has ended: the methods are scoped (Blocker 4), the schema enforces it (Blocker 3), and the
    migration reaches it safely (Blocker 5). Deleting the old test would erase the record of a
    deliberate half-step; replacing it records that the half-step finished.
    """
    import ast

    from freight_recon.migrations.phase2_tenant_first import CANONICAL_TENANT_TABLES

    src = (ROOT / "src" / "freight_recon" / "workflow.py").read_text(encoding="utf-8")

    # 1. still tenant-BOUND (U2.6A's guarantee survives)
    assert "self._tenant" in src

    # 2. and now tenant-SCOPED: every affected method carries the tenant into the SQL.
    tree = ast.parse(src)
    cls = next(n for n in ast.walk(tree)
               if isinstance(n, ast.ClassDef) and n.name == "WorkflowStore")
    unscoped = []
    for m in [n for n in cls.body if isinstance(n, ast.FunctionDef)]:
        seg = ast.get_source_segment(src, m) or ""
        if not any(t in seg for t in CANONICAL_TENANT_TABLES) or m.name == "_migrate":
            continue
        scoped = ("self._tenant" in seg) and (
            re.search(r"tenant\s*=\s*\?", seg) or "tenant," in seg)
        if not scoped:
            unscoped.append(m.name)
    assert not unscoped, f"the boundary is incomplete again: {unscoped}"

    # 3. the U2.6A caveat is gone from the source, because it is no longer true.
    assert "U2.6A SCOPE" not in src, (
        "the interim 'bound but not scoped' caveat is still in the code after U2.6BC"
    )


def test_22_ac_sec_001_is_now_satisfied_at_the_schema_level():
    """SUPERSEDED BY U2.6BC. This asserted AC-SEC-001 was RED (7 of 8 tables non-tenant-first) so
    U2.6A could not drift into claiming it. All seven have since migrated, so the honest assertion
    is the opposite one - and it is still a guard: it fails the moment a business table regresses.
    """
    from freight_recon.migrations.phase2_tenant_first import TENANT_EXEMPT_TABLES
    from phase0 import schema_probe

    tables, ev = schema_probe.tables()
    ev.require_population(minimum=8)
    offending = [t.name for t in tables
                 if not t.canonical and t.name not in TENANT_EXEMPT_TABLES]
    assert offending == [], f"AC-SEC-001 regressed: {offending} are not tenant-first"

