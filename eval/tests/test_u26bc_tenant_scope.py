"""U2.6BC Blocker 4 — exact tenant-scope qualification of the persistence boundary.

PHASE_GUARD

Blocker 3 proved the DATABASE enforces tenant-first structure. This proves the APPLICATION uses it:
every affected method carries the bound tenant into the SQL, and a cross-tenant access returns
nothing, changes nothing and discloses nothing.

    Counts are informational. The oracle is exact-set equality, and a same-count substitution fails.

The three merge-gating methods — `receive_document`, `get_run_by_hash`, `claim_operation_commit` —
are the ones where a gap is a cross-tenant money defect rather than a leak: identical document bytes,
identical load references and identical Commit Keys are all NORMAL across two brokerages.
"""

import ast
import pathlib
import re
import sys

import pytest

sys.path.insert(0, str(sys.path[0] or "."))
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from freight_recon.commit_key import LogicalEffect
from freight_recon.migrations.phase2_tenant_first import CANONICAL_TENANT_TABLES
from freight_recon.workflow import WorkflowStore
from phase0.evaluation import Evaluation

A, B = "tenant-alpha", "tenant-beta"
WORKFLOW_SRC = ROOT / "src" / "freight_recon" / "workflow.py"


def _store(tmp_path, tenant, name="w.sqlite3"):
    return WorkflowStore(tmp_path / name, tenant=tenant)


def _affected_methods() -> dict[str, dict]:
    """Every WorkflowStore method touching the exact seven tables, by AST. Zero => fail."""
    src = WORKFLOW_SRC.read_text(encoding="utf-8")
    tree = ast.parse(src)
    cls = next(n for n in ast.walk(tree)
               if isinstance(n, ast.ClassDef) and n.name == "WorkflowStore")
    out = {}
    for m in [n for n in cls.body if isinstance(n, ast.FunctionDef)]:
        seg = ast.get_source_segment(src, m) or ""
        tables = sorted({t for t in CANONICAL_TENANT_TABLES if t in seg})
        if not tables:
            continue
        ops = sorted({o for o in ("SELECT", "INSERT", "UPDATE", "DELETE")
                      if re.search(rf"\b{o}\b", seg)})
        out[m.name] = {
            "tables": tables,
            "ops": ops,
            "write": any(o in ops for o in ("INSERT", "UPDATE", "DELETE")),
            "bound_tenant": ("self._tenant" in seg or "self.tenant" in seg),
            "tenant_predicate": bool(re.search(r"tenant\s*=\s*\?", seg)) or "tenant," in seg,
            "readiness_gated": "_require_schema_ready" in seg,
            "source": seg,
        }
    return out


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


def _construction_sites() -> list[tuple[str, int, bool]]:
    sites = []
    for p in sorted(ROOT.rglob("*.py")):
        if any(x in p.parts for x in (".venv", "__pycache__", "node_modules")):
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        probes = _refusal_probe_lines(tree)
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "WorkflowStore":
                if n.lineno in probes:
                    continue
                sites.append((str(p.relative_to(ROOT)), n.lineno,
                              any(k.arg == "tenant" for k in n.keywords)))
    return sites


# ==================================================== exact sets — membership, never counts

def test_the_exact_seven_table_set():
    assert set(CANONICAL_TENANT_TABLES) == {
        "workflow_runs", "audit_events", "security_events", "operation_action_claims",
        "delivery_action_claims", "effect_grants", "operation_token_amounts",
    }, "the canonical table SET changed — a same-count substitution must fail here"


def test_the_exact_affected_method_set_is_fully_scoped():
    """22 methods: 13 write, 9 read. `_migrate` is the schema itself and carries no predicate."""
    ev = Evaluation(name="b4.methods", sources_inspected=[str(WORKFLOW_SRC)])
    methods = _affected_methods()
    for name in methods:
        ev.candidates.append(name)
        ev.accepted.append(name)
    ev.require_population(minimum=20)

    unscoped = [n for n, m in methods.items()
                if n != "_migrate" and not (m["bound_tenant"] and m["tenant_predicate"])]
    assert not unscoped, f"affected method(s) not tenant-scoped: {unscoped}"

    ungated = [n for n, m in methods.items() if n != "_migrate" and not m["readiness_gated"]]
    assert not ungated, (
        f"method(s) issue tenant-owned SQL without the readiness gate: {ungated} — "
        f"they would run against a legacy schema instead of failing closed"
    )

    writes = {n for n, m in methods.items() if m["write"]}
    reads = set(methods) - writes
    assert len(methods) == 22 and len(writes) == 13 and len(reads) == 9, (
        f"the affected-method set changed: {len(methods)} total, {len(writes)}W/{len(reads)}R"
    )


def test_no_affected_method_accepts_a_tenant_argument():
    """The store's tenant is the ONLY source. A per-method tenant could diverge from the binding."""
    offenders = []
    for name, m in _affected_methods().items():
        sig = re.search(rf"def {re.escape(name)}\((.*?)\)\s*->", m["source"], re.S)
        if sig and re.search(r"\btenant\b\s*:", sig.group(1)):
            offenders.append(name)
    assert not offenders, f"method(s) accept a tenant argument that could override the binding: {offenders}"


def test_no_affected_method_filters_tenant_in_python():
    """A global query filtered afterwards has already read another tenant's rows."""
    offenders = []
    for name, m in _affected_methods().items():
        body = m["source"]
        if re.search(r'row\[["\']tenant["\']\]\s*==|\.tenant\s*==\s*self\._tenant', body):
            offenders.append(name)
    assert not offenders, f"method(s) filter tenant in Python after querying: {offenders}"


def test_the_exact_construction_site_set():
    sites = _construction_sites()
    ev = Evaluation(name="b4.sites", sources_inspected=[str(WORKFLOW_SRC)],
                    accepted=[f"{f}:{l}" for f, l, _ in sites])
    ev.require_population(minimum=100)
    missing = [f"{f}:{l}" for f, l, has in sites if not has]
    assert not missing, f"construction site(s) without an explicit tenant: {missing}"
    production = [s for s in sites if s[0].startswith(("src/", "scripts/"))]
    assert all(has for _, _, has in production), "a production site omits its tenant"


# ============================================ merge-gating 1: receive_document (document hash)

def test_gating_receive_document_same_bytes_are_independent_across_tenants(tmp_path):
    """Two brokerages receiving the SAME document is normal. It was a silent collision."""
    a = _store(tmp_path, A, "shared.sqlite3")
    b = _store(tmp_path, B, "shared.sqlite3")
    try:
        ra = a.receive_document(load_id="LD-1", document_hash="identical-bytes", payload={})
        rb = b.receive_document(load_id="LD-1", document_hash="identical-bytes", payload={})
        assert ra is not None and rb is not None
        scoped = a.conn.execute("SELECT document_hash FROM workflow_runs").fetchone()["document_hash"]
        assert a.get_run_by_hash(scoped) is not None
        assert b.get_run_by_hash(scoped) is not None, (
            "tenant B could not see its OWN row for identical bytes")
        assert len(a.list_runs()) == 1 and len(b.list_runs()) == 1
    finally:
        a.close(); b.close()


def test_gating_receive_document_same_tenant_duplicate_is_still_absorbed(tmp_path):
    """Tenant scoping must not become tenant blindness: within ONE tenant, dedup still holds."""
    s = _store(tmp_path, A)
    try:
        first = s.receive_document(load_id="LD-1", document_hash="dup", payload={})
        second = s.receive_document(load_id="LD-1", document_hash="dup", payload={})
        assert first.id == second.id, "same-tenant duplicate detection regressed"
        assert len(s.list_runs()) == 1
    finally:
        s.close()


# ============================================== merge-gating 2: get_run_by_hash (no disclosure)

def test_gating_get_run_by_hash_never_returns_another_tenants_row(tmp_path):
    a = _store(tmp_path, A, "shared.sqlite3")
    b = _store(tmp_path, B, "shared.sqlite3")
    try:
        a.receive_document(load_id="LD-9", document_hash="only-in-a", payload={})
        scoped = a.conn.execute("SELECT document_hash FROM workflow_runs").fetchone()["document_hash"]
        assert a.get_run_by_hash(scoped) is not None
        assert b.get_run_by_hash(scoped) is None, "cross-tenant row was observable"
        # Absent and cross-tenant are indistinguishable: both are simply None.
        assert b.get_run_by_hash("never-existed-anywhere") is None
    finally:
        a.close(); b.close()


def test_gating_get_run_by_id_is_tenant_scoped(tmp_path):
    """Reused internal ids across tenants must not connect anything."""
    a = _store(tmp_path, A, "shared.sqlite3")
    b = _store(tmp_path, B, "shared.sqlite3")
    try:
        ra = a.receive_document(load_id="LD-1", document_hash="a-doc", payload={})
        assert a.get_run(ra.id) is not None
        assert b.get_run(ra.id) is None, "tenant B read tenant A's run by numeric id"
    finally:
        a.close(); b.close()


# ========================================== merge-gating 3: claim_operation_commit (Commit Key)

def _reservation(key="ck-shared"):
    """Note what is ABSENT: a tenant. `claim_operation_commit` has no tenant parameter, so a caller
    cannot supply one — ownership comes from the store binding or not at all. That is stronger than
    ignoring a caller's value, and it is why the override test below asserts the SIGNATURE."""
    return {"commit_key": key, "target_system": "tms", "lane": "raise_invoice",
            "load_ref": "LD-1", "party": "ACME", "approved_amount": "2850.00"}


def test_gating_same_commit_key_is_independent_across_tenants(tmp_path):
    """Identical Commit Keys in two brokerages are NORMAL. One blocking the other is the defect."""
    a = _store(tmp_path, A, "shared.sqlite3")
    b = _store(tmp_path, B, "shared.sqlite3")
    try:
        assert a.claim_operation_commit(**_reservation(), payload={"status": "RESERVED"}) is True
        assert b.claim_operation_commit(**_reservation(), payload={"status": "RESERVED"}) is True, (
            "tenant A's Commit Key blocked tenant B's legitimate effect"
        )
    finally:
        a.close(); b.close()


def test_gating_duplicate_commit_key_within_one_tenant_is_refused(tmp_path):
    s = _store(tmp_path, A)
    try:
        assert s.claim_operation_commit(**_reservation(), payload={"status": "RESERVED"}) is True
        assert s.claim_operation_commit(**_reservation(), payload={"status": "RESERVED"}) is False, (
            "commit-once regressed: one logical effect reserved twice in one tenant"
        )
    finally:
        s.close()


def test_gating_commit_reservation_is_not_readable_across_tenants(tmp_path):
    a = _store(tmp_path, A, "shared.sqlite3")
    b = _store(tmp_path, B, "shared.sqlite3")
    try:
        a.claim_operation_commit(**_reservation(), payload={"status": "RESERVED"})
        assert a.operation_commit_claim(commit_key="ck-shared") is not None
        assert b.operation_commit_claim(commit_key="ck-shared") is None, (
            "tenant B observed tenant A's effect reservation"
        )
    finally:
        a.close(); b.close()


def test_gating_payload_tenant_cannot_override_the_store_binding(tmp_path):
    """Ownership cannot be supplied by a caller — the parameter does not exist.

    Structural, not defensive: `claim_operation_commit` accepts no `tenant`, so there is nothing to
    ignore and nothing to get wrong. A method that accepted one and discarded it would still be one
    edit away from honouring it.
    """
    import inspect

    params = inspect.signature(WorkflowStore.claim_operation_commit).parameters
    assert "tenant" not in params, (
        "claim_operation_commit accepts a tenant argument: ownership could come from the caller "
        "instead of the store binding"
    )
    store = _store(tmp_path, A)
    try:
        store.claim_operation_commit(**_reservation(), payload={"status": "RESERVED"})
        row = store.conn.execute("SELECT tenant FROM effect_grants").fetchone()
        assert row["tenant"] == A, "the reservation was not owned by the bound tenant"
    finally:
        store.close()


# ================================================================ writes: cross-tenant negatives

def test_cross_tenant_update_changes_zero_rows(tmp_path):
    a = _store(tmp_path, A, "shared.sqlite3")
    b = _store(tmp_path, B, "shared.sqlite3")
    try:
        run = a.receive_document(load_id="LD-1", document_hash="a-doc", payload={})
        before = a.get_run(run.id).state
        # Stronger than a silent no-op: the row is simply NOT THERE for tenant B, so the store
        # raises "workflow run not found" rather than updating zero rows and reporting success.
        from freight_recon.workflow import WorkflowError
        with pytest.raises(WorkflowError, match="not found"):
            b.transition(run.id, "REVIEW", actor="attacker")
        assert a.get_run(run.id).state == before, "tenant B mutated tenant A's run"
    finally:
        a.close(); b.close()


def test_cross_tenant_child_cannot_attach_to_another_tenants_parent(tmp_path):
    a = _store(tmp_path, A, "shared.sqlite3")
    b = _store(tmp_path, B, "shared.sqlite3")
    try:
        run = a.receive_document(load_id="LD-1", document_hash="a-doc", payload={})
        claimed = b.claim_delivery_action("x-1", run_id=run.id, actor="attacker", payload={})
        assert claimed is False, "a child attached to another tenant's parent"
    finally:
        a.close(); b.close()


def test_audit_history_is_tenant_scoped(tmp_path):
    a = _store(tmp_path, A, "shared.sqlite3")
    b = _store(tmp_path, B, "shared.sqlite3")
    try:
        run = a.receive_document(load_id="LD-1", document_hash="a-doc", payload={})
        a.add_audit_event(run.id, "noted", actor="a", payload={})
        assert a.audit_events(run.id), "same-tenant history is unreadable"
        assert b.audit_events(run.id) == [], "tenant B read tenant A's audit history"
    finally:
        a.close(); b.close()


def test_token_amounts_are_tenant_scoped(tmp_path):
    """An APPROVED AMOUNT bound to a token must never be readable by another tenant."""
    a = _store(tmp_path, A, "shared.sqlite3")
    b = _store(tmp_path, B, "shared.sqlite3")
    try:
        a.record_operation_token_amount(token_fingerprint="fp-1", action_id="act-1",
                                        approved_amount="2850.00", payload={})
        assert a.operation_token_amount(token_fingerprint="fp-1") == "2850.00"
        assert b.operation_token_amount(token_fingerprint="fp-1") is None, "tenant B read tenant A's approved amount"
    finally:
        a.close(); b.close()


def test_action_claims_are_tenant_scoped(tmp_path):
    """A single-use action id in one tenant must not consume another tenant's claim."""
    a = _store(tmp_path, A, "shared.sqlite3")
    b = _store(tmp_path, B, "shared.sqlite3")
    try:
        assert a.claim_operation_action("act-1", actor="a", payload={}) is True
        assert b.claim_operation_action("act-1", actor="b", payload={}) is True, (
            "tenant A's action id consumed tenant B's single-use claim"
        )
        assert a.claim_operation_action("act-1", actor="a", payload={}) is False
    finally:
        a.close(); b.close()


# ============================================================ router / store tenant consistency

def test_router_and_store_tenants_must_match(tmp_path):
    """A Commit Key minted for one tenant and persisted under another is a cross-tenant defect."""
    from freight_recon.operation_router import OperationRouter, freight_lanes

    store = _store(tmp_path, A)
    try:
        with pytest.raises(ValueError, match="does not match its commit_store tenant"):
            OperationRouter(lanes=freight_lanes(), build_agent=lambda **_: None,
                            tenant=B, commit_store=store)
    finally:
        store.close()


def test_router_with_matching_tenant_is_accepted(tmp_path):
    from freight_recon.operation_router import OperationRouter, freight_lanes

    store = _store(tmp_path, A)
    try:
        r = OperationRouter(lanes=freight_lanes(), build_agent=lambda **_: None,
                            tenant=A, commit_store=store)
        assert r.tenant == store.tenant
    finally:
        store.close()


def test_no_production_effect_path_uses_a_sentinel_router_tenant():
    """`tenant="default"` on an effect-bearing router was the live defect the guard now blocks."""
    offenders = []
    for p in sorted((ROOT / "src").rglob("*.py")) + sorted((ROOT / "scripts").glob("*.py")):
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "OperationRouter":
                for k in n.keywords:
                    if k.arg == "tenant" and isinstance(k.value, ast.Constant):
                        offenders.append(f"{p.name}:{n.lineno} -> {k.value.value!r}")
    assert not offenders, f"production router(s) with a hardcoded tenant: {offenders}"


# ================================================================= schema readiness precedes SQL

def test_a_legacy_schema_fails_before_any_tenant_owned_sql(tmp_path):
    import shutil

    from freight_recon.schema import SchemaNotReady

    from fixtures.legacy_workspace import build_legacy_workspace
    db = tmp_path / "legacy.sqlite3"
    build_legacy_workspace(db)
    with pytest.raises(SchemaNotReady):
        # Construction may itself refuse, or the first tenant-owned call does. Either is fail-closed;
        # what must never happen is a query running against a schema that cannot honour tenancy.
        store = WorkflowStore(db, tenant=A)
        try:
            store.list_runs()
        finally:
            store.close()


# ------------------------------------------------------------------------------------------
# Added after mutation testing found two real gaps in this very suite.
# ------------------------------------------------------------------------------------------

def test_the_unfiltered_audit_list_read_is_tenant_scoped(tmp_path):
    """The `run_id=None` branch — the one a support tool reaches for.

    Mutation found this untested: making the unfiltered branch global left every test green while
    `audit_events()` returned EVERY tenant's history. The scoped branch was covered and the
    unscoped-by-default branch was not, which is the wrong way round: the convenience path is the
    one that leaks.
    """
    a = _store(tmp_path, A, "shared.sqlite3")
    b = _store(tmp_path, B, "shared.sqlite3")
    try:
        run = a.receive_document(load_id="LD-1", document_hash="a-doc", payload={})
        a.add_audit_event(run.id, "noted", actor="a", payload={})
        assert a.audit_events(), "same-tenant unfiltered history is unreadable"
        assert b.audit_events() == [], (
            "the unfiltered audit read returned another tenant's history"
        )
    finally:
        a.close(); b.close()


def test_the_exact_table_set_fails_on_a_dropped_member():
    """The set must be asserted against a literal, not against itself.

    Mutation found this: dropping `operation_token_amounts` from the canonical tuple left the
    equality test green, because both sides of the comparison moved together. A registry that
    validates itself validates nothing.
    """
    expected = {
        "workflow_runs", "audit_events", "security_events", "operation_action_claims",
        "delivery_action_claims", "effect_grants", "operation_token_amounts",
    }
    assert set(CANONICAL_TENANT_TABLES) == expected
    assert len(CANONICAL_TENANT_TABLES) == 7
    # Every canonical table must also be reachable by at least one affected method, or it is
    # tenant-first in the schema and untouched by the application.
    touched = {t for m in _affected_methods().values() for t in m["tables"]}
    assert touched == expected, f"table(s) never touched by any method: {sorted(expected - touched)}"
