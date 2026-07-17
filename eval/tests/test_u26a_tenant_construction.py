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


def _sites():
    """Every real WorkflowStore(...) call, by AST. Text matching would count comments and strings."""
    ev = Evaluation(name="u26a.construction_sites")
    out = []
    for p in python_files(ROOT / "src", ROOT / "scripts", ROOT / "eval"):
        # This file's own probes construct a store WITHOUT a tenant on purpose, to prove it is
        # refused. Counting them would make the guard report the very defect it verifies is absent.
        if p.name == "test_u26a_tenant_construction.py":
            continue
        ev.sources_inspected.append(rel(p))
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "WorkflowStore":
                kw = {k.arg: k.value for k in node.keywords}
                ev.candidates.append(f"{rel(p)}:{node.lineno}")
                ev.accepted.append((rel(p), node.lineno, kw.get("tenant")))
                out.append((rel(p), node.lineno, kw.get("tenant")))
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
    missing = [f"{f}:{ln}" for f, ln, t in sites if t is None]
    assert not missing, (
        f"{len(missing)} WorkflowStore construction site(s) supply no tenant:\n  "
        + "\n  ".join(missing[:12])
    )


def test_14_no_production_site_uses_a_fixture_tenant():
    """A fixture value in production is a test tenant owning real rows."""
    sites, ev = _sites()
    ev.require_population(minimum=100)
    leaked = [
        f"{f}:{ln}" for f, ln, t in sites
        if not f.startswith("eval/") and isinstance(t, ast.Constant)
        and isinstance(t.value, str) and "fixture" in t.value.lower()
    ]
    assert not leaked, f"production site(s) using a fixture tenant: {leaked}"


def test_15_no_construction_site_hardcodes_a_sentinel_tenant():
    sites, ev = _sites()
    ev.require_population(minimum=100)
    bad = [
        f"{f}:{ln} -> {t.value!r}" for f, ln, t in sites
        if isinstance(t, ast.Constant) and isinstance(t.value, str)
        and t.value.strip().lower() in FORBIDDEN_TENANTS
    ]
    assert not bad, f"sentinel tenant hardcoded at: {bad}"


def test_no_production_site_hardcodes_any_string_tenant():
    """A production tenant must come from config or an operator — never a literal in the source."""
    sites, ev = _sites()
    ev.require_population(minimum=100)
    literals = [
        f"{f}:{ln} -> {t.value!r}" for f, ln, t in sites
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

def test_u26a_does_not_claim_tenant_isolation():
    """The honest boundary, asserted so it cannot quietly drift into a false claim."""
    src = (ROOT / "src" / "freight_recon" / "workflow.py").read_text()
    assert "U2.6A SCOPE" in src
    assert "does NOT yet make the store" in src and "tenant-safe" in src
    # The 22 methods really are still unscoped. When U2.6B lands, this test SHOULD fail and be
    # replaced — it is a marker of an intermediate state, not a permanent truth.
    assert "self._tenant" in src


def test_22_ac_sec_001_remains_red():
    """The live schema is untouched: 7 of 8 tables are still not tenant-first."""
    from phase0 import manifest, schema_probe
    tables, ev = schema_probe.tables()
    ev.require_population(minimum=8)
    offenders = {t.name for t in tables if not t.canonical}
    assert offenders == manifest.tables_not_tenant_first()
    assert len(offenders) == 7, "the schema changed — U2.6A must not activate the migration"
