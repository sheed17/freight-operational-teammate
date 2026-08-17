"""AC-SEC-001 — the integrated Phase-2 tenant-isolation oracle.

PHASE_GUARD

Reconstructed from the FROZEN acceptance specification, not from the implementation:

    "tenant is STRUCTURALLY required on records, events, grants, witnesses, mappings, credentials,
     cache keys, leases, adapter calls — a schema+API sweep: every one of the nine carries
     `tenant_id` NOT NULL, first in its key"

Nine surfaces. **Phase 2 owns three of them** — records, grants, and the API that reaches them —
and **Phase 3 delivered two more**: witnesses (the checkpoint_witnesses table, tenant-first,
FK-bound within its tenant) and leases (grant TTL / claim semantics, tenant-scoped end to end).
Events (P5), mappings (P9), credentials/cache-keys and adapter calls (P4/P8) still do not exist,
and a green tick against a surface that does not exist is not evidence.

    So AC-SEC-001 is green FOR ITS PHASE-2 AND PHASE-3 SURFACES and explicitly incomplete for
    the rest. The registry says which, by name, so nobody can read this as "tenancy is done".

Every member below runs the REAL implementation. A member that is skipped, xfailed, substituted or
inferred rather than executed fails the registry.
"""

import ast
import re
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from freight_recon.migrations.phase2_tenant_first import (
    CANONICAL_TENANT_TABLES,
    GRANT_STATES,
    TENANT_EXEMPT_TABLES,
)
from freight_recon.schema import create_canonical_schema, schema_readiness_problems
from freight_recon.workflow import WorkflowStore
from phase0.evaluation import Evaluation

A, B = "tenant-alpha", "tenant-beta"

# ---------------------------------------------------------------------------------------------
# THE REGISTRY. Exact membership: omission, substitution and an empty registry all fail.
# ---------------------------------------------------------------------------------------------
PHASE2_SURFACES = {
    "records": "the seven tenant-owned tables and every store method reaching them",
    "grants": "the canonical effect_grants ledger and its Commit Key identity",
    "api": "WorkflowStore construction and the router/store tenant agreement",
}
# Delivered by P3: the two surfaces the Phase-2 registry deferred to the checkpoint unit.
PHASE3_SURFACES = {
    "witnesses": "checkpoint_witnesses — tenant-first PK, tenant-consistent FK to the grant",
    "leases": "grant TTL and the claim CAS — expiry, revocation and claims all tenant-scoped",
}
DEFERRED_SURFACES = {
    "events": "P5 — outbox/inbox do not exist",
    "mappings": "P9 — External Entity Mapping does not exist",
    "credentials": "P4 — adapter credential storage is not contained",
    "cache_keys": "P4 — no adapter cache exists to key",
    "adapter_calls": "P4 — adapter containment",
}

AC_SEC_001_MEMBERS = (
    # construction and tenant authority
    "store_requires_explicit_validated_tenant",
    "no_production_site_uses_a_sentinel_or_literal_tenant",
    "construction_sites_are_exactly_registered",
    # runtime reads
    "every_affected_read_is_tenant_scoped_in_sql",
    "cross_tenant_record_is_indistinguishable_from_missing",
    "document_hash_lookup_is_tenant_scoped",
    "commit_key_lookup_is_tenant_scoped",
    # runtime writes
    "every_affected_write_persists_the_bound_tenant",
    "ownership_cannot_be_supplied_by_caller",
    "cross_tenant_update_changes_nothing",
    "cross_tenant_child_cannot_reference_another_tenants_parent",
    # schema
    "exact_seven_tenant_owned_tables",
    "tenant_columns_not_null_without_sentinel_defaults",
    "tenant_scoped_document_hash_uniqueness",
    "tenant_scoped_commit_key_uniqueness",
    "composite_tenant_aware_foreign_keys_enforced",
    "one_canonical_effect_ledger_with_exact_states",
    # cross-tenant identity matrix
    "same_document_hash_across_tenants_is_independent",
    "same_commit_key_across_tenants_is_independent",
    "reused_internal_ids_across_tenants_connect_nothing",
    # same-tenant convergence
    "same_tenant_duplicate_document_converges",
    "same_tenant_duplicate_commit_key_is_refused",
    # effect identity
    "commit_key_excludes_the_amount_structurally",
    "router_and_store_tenants_must_agree",
    # P3 surfaces: witnesses and leases
    "witness_table_is_tenant_first_and_cross_tenant_witnesses_read_as_absent",
    "witness_cannot_vouch_for_another_tenants_grant",
    "grant_expiry_and_claims_are_tenant_scoped",
)


def _canonical_db(tmp_path, name="ac-sec-001.db") -> str:
    db = tmp_path / name
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys = ON")
    create_canonical_schema(conn)
    conn.close()
    return str(db)


def _store(tmp_path, tenant, name="ac-sec-001.db"):
    return WorkflowStore(tmp_path / name, tenant=tenant)


# ============================================================== the registry's own integrity

def test_ac_sec_001_registry_is_exact_and_non_empty():
    ev = Evaluation(name="ac_sec_001.registry", sources_inspected=[__file__],
                    accepted=list(AC_SEC_001_MEMBERS))
    ev.require_population(minimum=20)
    assert len(AC_SEC_001_MEMBERS) == len(set(AC_SEC_001_MEMBERS)), "duplicate registry member"
    here = Path(__file__).read_text(encoding="utf-8")
    missing = [m for m in AC_SEC_001_MEMBERS if f"def test_{m}(" not in here]
    assert not missing, (
        f"registered member(s) with no executing test: {missing} — a registry member that is "
        f"inferred rather than executed is not evidence"
    )


def test_no_ac_sec_001_member_is_skipped_or_xfailed():
    """Structural, by AST: a substring scan matches the words in THIS assertion and fires on itself.

    (It did, the first time it ran — the same fragment-vs-token error that has bitten three guards
    in this programme. Decorators are read from the syntax tree, so the check sees marks, not prose.)
    """
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    disabled = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for dec in node.decorator_list:
            src = ast.unparse(dec)
            if "mark.skip" in src or "mark.xfail" in src:
                disabled.append(node.name)
    assert not disabled, f"AC-SEC-001 member(s) disabled: {disabled} — silence is not a pass"


def test_ac_sec_001_states_exactly_which_surfaces_it_covers():
    """Green for what Phase 2 and Phase 3 own; explicitly incomplete for what does not exist."""
    assert set(PHASE2_SURFACES) | set(PHASE3_SURFACES) | set(DEFERRED_SURFACES) == {
        "records", "grants", "api", "events", "witnesses", "mappings",
        "credentials", "cache_keys", "leases", "adapter_calls",
    }, "the nine canonical surfaces (plus api) drifted from the frozen specification"
    assert not (set(PHASE3_SURFACES) & set(DEFERRED_SURFACES)), (
        "a surface cannot be simultaneously delivered and deferred")
    assert set(PHASE3_SURFACES) == {"witnesses", "leases"}, (
        "P3 owns exactly the two surfaces the Phase-2 registry deferred to it")
    for surface, why in DEFERRED_SURFACES.items():
        assert re.match(r"P\d", why), f"{surface}: no phase named for the deferral"


# ================================================== construction and tenant authority

def test_store_requires_explicit_validated_tenant(tmp_path):
    from freight_recon.tenant import InvalidTenant, MissingTenant

    db = _canonical_db(tmp_path)
    with pytest.raises(TypeError):
        WorkflowStore(db)                       # type: ignore[call-arg]
    for bad in (None, "", "  ", "default", "test"):
        with pytest.raises((MissingTenant, InvalidTenant)):
            WorkflowStore(db, tenant=bad)       # type: ignore[arg-type]


def test_no_production_site_uses_a_sentinel_or_literal_tenant():
    offenders = []
    for p in sorted((ROOT / "src").rglob("*.py")) + sorted((ROOT / "scripts").glob("*.py")):
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and \
                    n.func.id in ("WorkflowStore", "OperationRouter"):
                for k in n.keywords:
                    if k.arg == "tenant" and isinstance(k.value, ast.Constant):
                        offenders.append(f"{p.name}:{n.lineno} -> {k.value.value!r}")
    assert not offenders, f"production site(s) hardcode a tenant: {offenders}"


def test_construction_sites_are_exactly_registered():
    sites = []
    for p in sorted(ROOT.rglob("*.py")):
        if any(x in p.parts for x in (".venv", "__pycache__")):
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "WorkflowStore":
                sites.append((str(p.relative_to(ROOT)), any(k.arg == "tenant" for k in n.keywords)))
    ev = Evaluation(name="ac_sec_001.sites", sources_inspected=[str(ROOT)],
                    accepted=[s[0] for s in sites])
    ev.require_population(minimum=100)
    deliberate = ("test_u26a_tenant_construction", "test_ac_sec_001_registry")
    missing = [f for f, has in sites if not has and not any(d in f for d in deliberate)]
    assert not missing, f"construction site(s) without an explicit tenant: {sorted(set(missing))}"


# ================================================================== runtime reads

def test_every_affected_read_is_tenant_scoped_in_sql():
    src = (ROOT / "src" / "freight_recon" / "workflow.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "WorkflowStore")
    unscoped = []
    for m in [n for n in cls.body if isinstance(n, ast.FunctionDef)]:
        seg = ast.get_source_segment(src, m) or ""
        if not any(t in seg for t in CANONICAL_TENANT_TABLES) or m.name == "_migrate":
            continue
        if not (("self._tenant" in seg) and (re.search(r"tenant\s*=\s*\?", seg) or "tenant," in seg)):
            unscoped.append(m.name)
    assert not unscoped, f"unscoped affected method(s): {unscoped}"


def test_cross_tenant_record_is_indistinguishable_from_missing(tmp_path):
    a, b = _store(tmp_path, A), _store(tmp_path, B)
    try:
        run = a.receive_document(load_id="LD-1", document_hash="a-doc", payload={})
        assert b.get_run(run.id) is None
        assert b.get_run(999_999) is None       # absent and cross-tenant are the same answer
    finally:
        a.close(); b.close()


def test_document_hash_lookup_is_tenant_scoped(tmp_path):
    a, b = _store(tmp_path, A), _store(tmp_path, B)
    try:
        a.receive_document(load_id="LD-1", document_hash="shared-bytes", payload={})
        stored = a.conn.execute("SELECT document_hash FROM workflow_runs").fetchone()["document_hash"]
        assert a.get_run_by_hash(stored) is not None
        assert b.get_run_by_hash(stored) is None
    finally:
        a.close(); b.close()


def test_commit_key_lookup_is_tenant_scoped(tmp_path):
    a, b = _store(tmp_path, A), _store(tmp_path, B)
    try:
        a.claim_operation_commit(commit_key="ck", target_system="tms", lane="raise_invoice",
                                 load_ref="LD-1", party="ACME", approved_amount="100.00",
                                 payload={"status": "RESERVED"})
        assert a.operation_commit_claim(commit_key="ck") is not None
        assert b.operation_commit_claim(commit_key="ck") is None
    finally:
        a.close(); b.close()


# ================================================================== runtime writes

def test_every_affected_write_persists_the_bound_tenant(tmp_path):
    s = _store(tmp_path, A)
    try:
        run = s.receive_document(load_id="LD-1", document_hash="w", payload={})
        s.add_audit_event(run.id, "noted", actor="a", payload={})
        s.add_security_event("probe", actor="a", payload={})
        s.claim_operation_action("act-1", actor="a", payload={})
        s.claim_delivery_action("del-1", run_id=run.id, actor="a", payload={})
        s.record_operation_token_amount(token_fingerprint="fp", action_id="act-1",
                                        approved_amount="10.00", payload={})
        s.claim_operation_commit(commit_key="ck", target_system="tms", lane="raise_invoice",
                                 load_ref="LD-1", party="ACME", payload={"status": "RESERVED"})
        for table in CANONICAL_TENANT_TABLES:
            rows = s.conn.execute(f"SELECT COUNT(*) c FROM {table} WHERE tenant != ?",
                                  (A,)).fetchone()["c"]
            assert rows == 0, f"{table} holds a row not owned by the bound tenant"
    finally:
        s.close()


def test_ownership_cannot_be_supplied_by_caller():
    import inspect

    for name in ("claim_operation_commit", "receive_document", "add_audit_event",
                 "claim_operation_action", "record_operation_token_amount"):
        params = inspect.signature(getattr(WorkflowStore, name)).parameters
        assert "tenant" not in params, f"{name} accepts caller-supplied ownership"


def test_cross_tenant_update_changes_nothing(tmp_path):
    from freight_recon.workflow import WorkflowError

    a, b = _store(tmp_path, A), _store(tmp_path, B)
    try:
        run = a.receive_document(load_id="LD-1", document_hash="u", payload={})
        before = a.get_run(run.id).state
        with pytest.raises(WorkflowError):
            b.transition(run.id, "REVIEW", actor="attacker")
        assert a.get_run(run.id).state == before
    finally:
        a.close(); b.close()


def test_cross_tenant_child_cannot_reference_another_tenants_parent(tmp_path):
    a, b = _store(tmp_path, A), _store(tmp_path, B)
    try:
        run = a.receive_document(load_id="LD-1", document_hash="c", payload={})
        assert b.claim_delivery_action("x", run_id=run.id, actor="attacker", payload={}) is False
    finally:
        a.close(); b.close()


# ========================================================================= schema

def test_exact_seven_tenant_owned_tables():
    assert set(CANONICAL_TENANT_TABLES) == {
        "workflow_runs", "audit_events", "security_events", "operation_action_claims",
        "delivery_action_claims", "effect_grants", "operation_token_amounts"}


def test_tenant_columns_not_null_without_sentinel_defaults(tmp_path):
    db = _canonical_db(tmp_path, "schema.db")
    conn = sqlite3.connect(db)
    try:
        for table in CANONICAL_TENANT_TABLES:
            col = next(r for r in conn.execute(f"PRAGMA table_info({table})") if r[1] == "tenant")
            assert col[3], f"{table}.tenant is nullable"
            assert col[4] is None, f"{table}.tenant carries DEFAULT {col[4]!r}"
    finally:
        conn.close()


def test_tenant_scoped_document_hash_uniqueness(tmp_path):
    db = _canonical_db(tmp_path, "dh.db")
    conn = sqlite3.connect(db)
    try:
        for idx in conn.execute("PRAGMA index_list(workflow_runs)"):
            if idx[2]:
                cols = [r[2] for r in conn.execute(f"PRAGMA index_info({idx[1]})")]
                assert cols != ["document_hash"], "a GLOBAL document-hash unique index exists"
    finally:
        conn.close()


def test_tenant_scoped_commit_key_uniqueness(tmp_path):
    db = _canonical_db(tmp_path, "ck.db")
    conn = sqlite3.connect(db)
    try:
        found = False
        for idx in conn.execute("PRAGMA index_list(effect_grants)"):
            if idx[2]:
                cols = [r[2] for r in conn.execute(f"PRAGMA index_info({idx[1]})")]
                assert cols != ["commit_key"], "a GLOBAL Commit Key unique index exists"
                if cols[:2] == ["tenant", "commit_key"]:
                    found = True
        assert found, "no tenant-scoped Commit Key uniqueness"
    finally:
        conn.close()


def test_composite_tenant_aware_foreign_keys_enforced(tmp_path):
    db = _canonical_db(tmp_path, "fk.db")
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        fks = [(r[2], r[3], r[4]) for r in conn.execute("PRAGMA foreign_key_list(audit_events)")]
        assert ("workflow_runs", "tenant", "tenant") in fks, f"tenant is not part of the FK: {fks}"
        assert schema_readiness_problems(conn) == []
    finally:
        conn.close()


def test_one_canonical_effect_ledger_with_exact_states(tmp_path):
    db = _canonical_db(tmp_path, "ledger.db")
    conn = sqlite3.connect(db)
    try:
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='effect_grants'").fetchone()[0]
        constrained = set(re.findall(r"'([A-Z_]+)'", re.search(
            r"CHECK\s*\(\s*state\s+IN\s*\(([^)]*)\)", ddl, re.S | re.I).group(1)))
        assert constrained == set(GRANT_STATES)
        assert "REVOKED" in constrained and "EXPIRED_UNCLAIMED" in constrained
        others = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")
            if r[0] != "effect_grants" and r[0] not in TENANT_EXEMPT_TABLES]
        # ### THE WORD THAT DOES THE WORK IS `INDEPENDENTLY` (narrowed at P6 M2, matching
        # `schema._second_ledger_problems`). CLAUDE.md rule 17 forbids a second effect AUTHORITY —
        # a row that can, on its own, be presented as permission to touch the outside world. A
        # table that reserves a commit key while holding a FOREIGN KEY into `effect_grants` is
        # answerable to the one ledger by construction; `pipeline_instances` is required to carry
        # exactly that reservation by `02-pipeline-instance.machine.md` §14 PL-1 (Layer 1: one
        # attempt RUNNING at a time), while Layer 2 — the grant ledger — remains the only thing
        # that decides whether an effect may EXIST. A genuinely independent second ledger has no
        # such reference: that is what makes it independent, and it is what this still refuses.
        checked = 0
        for t in others:
            cols = {r[1] for r in conn.execute(f"PRAGMA table_info({t})")}
            if not ({"commit_key", "state"} <= cols):
                continue
            checked += 1
            referents = {r[2] for r in conn.execute(f"PRAGMA foreign_key_list({t})")}
            assert "effect_grants" in referents, (
                f"{t} reserves a commit key and declares NO foreign key into effect_grants: it is "
                f"a second effect ledger (CLAUDE.md rule 17)")
        assert checked, (
            "no table other than effect_grants carries commit_key + state, so the check above "
            "passed over an empty set and proved nothing about the rule it defends")
    finally:
        conn.close()


# ======================================================= cross-tenant identity matrix

def test_same_document_hash_across_tenants_is_independent(tmp_path):
    a, b = _store(tmp_path, A), _store(tmp_path, B)
    try:
        assert a.receive_document(load_id="LD-1", document_hash="same", payload={}) is not None
        assert b.receive_document(load_id="LD-1", document_hash="same", payload={}) is not None
        assert len(a.list_runs()) == 1 and len(b.list_runs()) == 1
    finally:
        a.close(); b.close()


def test_same_commit_key_across_tenants_is_independent(tmp_path):
    a, b = _store(tmp_path, A), _store(tmp_path, B)
    kw = dict(commit_key="shared-ck", target_system="tms", lane="raise_invoice",
              load_ref="LD-1", party="ACME", payload={"status": "RESERVED"})
    try:
        assert a.claim_operation_commit(**kw) is True
        assert b.claim_operation_commit(**kw) is True, "one tenant's key blocked another's effect"
    finally:
        a.close(); b.close()


def test_reused_internal_ids_across_tenants_connect_nothing(tmp_path):
    a, b = _store(tmp_path, A), _store(tmp_path, B)
    try:
        ra = a.receive_document(load_id="LD-1", document_hash="ida", payload={})
        rb = b.receive_document(load_id="LD-1", document_hash="idb", payload={})
        # Ids are PER TENANT: both runs are id=1. That is the point — a reused id must connect
        # nothing, so each tenant sees only its own events under the same numeric id.
        assert ra.id == rb.id, "the fixture no longer exercises a reused id"
        a.add_audit_event(ra.id, "a-note", actor="a", payload={})
        b.add_audit_event(rb.id, "b-note", actor="b", payload={})
        assert [e["event_type"] for e in a.audit_events(ra.id)] == ["document_received", "a-note"]
        assert [e["event_type"] for e in b.audit_events(rb.id)] == ["document_received", "b-note"]
    finally:
        a.close(); b.close()


# ========================================================= same-tenant convergence

def test_same_tenant_duplicate_document_converges(tmp_path):
    s = _store(tmp_path, A)
    try:
        first = s.receive_document(load_id="LD-1", document_hash="dup", payload={})
        second = s.receive_document(load_id="LD-1", document_hash="dup", payload={})
        assert first.id == second.id and len(s.list_runs()) == 1
    finally:
        s.close()


def test_same_tenant_duplicate_commit_key_is_refused(tmp_path):
    s = _store(tmp_path, A)
    kw = dict(commit_key="one-effect", target_system="tms", lane="raise_invoice",
              load_ref="LD-1", party="ACME", payload={"status": "RESERVED"})
    try:
        assert s.claim_operation_commit(**kw) is True
        assert s.claim_operation_commit(**kw) is False
    finally:
        s.close()


# ============================================================== effect identity

def test_commit_key_excludes_the_amount_structurally():
    import dataclasses

    from freight_recon.commit_key import LogicalEffect

    fields = [f.name for f in dataclasses.fields(LogicalEffect)]
    assert "approved_amount" not in fields and "amount" not in fields
    with pytest.raises(ImportError):
        from freight_recon.workflow import operation_commit_key  # noqa: F401


def test_router_and_store_tenants_must_agree(tmp_path):
    from freight_recon.operation_router import OperationRouter, freight_lanes

    store = _store(tmp_path, A)
    try:
        with pytest.raises(ValueError, match="does not match its commit_store tenant"):
            OperationRouter(lanes=freight_lanes(), build_agent=lambda **_: None,
                            tenant=B, commit_store=store)
    finally:
        store.close()


# ============================================================== P3 surfaces: witnesses, leases

def _p3_kernel(tmp_path, tenant, name):
    """A checkpoint kernel over a green scenario for one tenant, sharing one database file."""
    sys.path.insert(0, str(ROOT / "eval" / "tests"))
    from phase3_kit import (
        CheckpointInputs, CheckpointRequest, live_reader, make_approval, make_effect,
        make_facts, make_kernel,
    )
    from freight_recon.checkpoint import run_checkpoint

    store = WorkflowStore(tmp_path / name, tenant=tenant)
    kernel, clock = make_kernel(store)
    effect = make_effect(tenant=tenant, resource="load:shared-id")
    facts = make_facts(entity_ref="load:shared-id")
    versions = {"load:shared-id": 1}
    approval = make_approval(effect, facts, versions, clock)
    inputs = CheckpointInputs(
        material_facts_reader=live_reader(lambda: dict(facts)),
        projection_assertion={"status": "DELIVERED"},
        projected_state_reader=live_reader({"status": "DELIVERED"}),
        entity_version_reader=live_reader({"load:shared-id": 1}),
        approval=approval)
    request = CheckpointRequest(effect=effect, actor="pipeline",
                                accountable_owner="owner:rasheed",
                                target_entity_ref="load:shared-id")
    outcome = run_checkpoint(kernel, request, inputs)
    assert outcome.authorized, f"AC-SEC-001 fixture checkpoint refused: {outcome}"
    return store, kernel, clock, effect, outcome


def test_witness_table_is_tenant_first_and_cross_tenant_witnesses_read_as_absent(tmp_path):
    """The witness surface: tenant is FIRST in the primary key, and tenant B reading the same
    database sees NONE of tenant A's witnesses — absent, not forbidden."""
    store_a, kernel_a, clock, effect_a, outcome_a = _p3_kernel(tmp_path, A, "shared.db")
    try:
        pk = [r[1] for r in sorted(
            (r for r in store_a.conn.execute("PRAGMA table_info(checkpoint_witnesses)").fetchall()
             if r[5]), key=lambda r: r[5])]
        assert pk[0] == "tenant", f"checkpoint_witnesses PK is {pk}; tenant must be first (C-1)"
        store_b = WorkflowStore(tmp_path / "shared.db", tenant=B)
        visible_to_b = store_b.conn.execute(
            "SELECT COUNT(*) FROM checkpoint_witnesses WHERE tenant = ?", (B,)).fetchone()[0]
        assert visible_to_b == 0
        total = store_a.conn.execute("SELECT COUNT(*) FROM checkpoint_witnesses").fetchone()[0]
        assert total == 1, "the witness population collapsed — this test would pass vacuously"
        store_b.close()
    finally:
        store_a.close()


def test_witness_cannot_vouch_for_another_tenants_grant(tmp_path):
    """The tenant-consistent FK: a witness row spelled against another tenant's grant is refused
    by the database even when the grant_id matches byte-for-byte."""
    store_a, kernel_a, clock, effect_a, outcome_a = _p3_kernel(tmp_path, A, "shared.db")
    try:
        with pytest.raises(sqlite3.IntegrityError):
            store_a.conn.execute(
                """INSERT INTO checkpoint_witnesses (
                    tenant, checkpoint_id, grant_id, actor, accountable_owner, action_class,
                    target_system, target_resource_id, target_operation, commit_key,
                    material_facts_fingerprint, entity_versions_json, approval_id,
                    approval_fingerprint, policy_version, gate_decision, autonomy_state,
                    brake_version, projected_observations_json, native_claims_json,
                    created_at, expires_at)
                VALUES (?, 'cp-cross', ?, 'x', 'x', 'a', 't', 'r', 'o', 'ck-cross', 'fp', '{}',
                        'ap', 'apf', 'pv', 'HUMAN_APPROVAL_REQUIRED', 'H', 'bv', '[]', '[]',
                        '2026-01-01T00:00:00+00:00', '2026-01-01T00:01:00+00:00')""",
                (B, outcome_a.handle.grant_id))
        store_a.conn.rollback()
    finally:
        store_a.close()


def test_grant_expiry_and_claims_are_tenant_scoped(tmp_path):
    """The lease surface: tenant B's expiry sweep never transitions tenant A's grants, and
    tenant B cannot claim tenant A's live capability through the same database file."""
    from freight_recon.checkpoint import EffectGrantHandle, claim_grant_cas, expire_unclaimed
    from phase3_kit import make_kernel as mk, params_for

    store_a, kernel_a, clock_a, effect_a, outcome_a = _p3_kernel(tmp_path, A, "shared.db")
    try:
        store_b = WorkflowStore(tmp_path / "shared.db", tenant=B)
        kernel_b, clock_b = mk(store_b)
        clock_b.advance(seconds=3600)   # far past every TTL — but only B's partition is swept
        assert expire_unclaimed(kernel_b) == 0, "tenant B's sweep reached tenant A's grants"
        state = store_a.conn.execute(
            "SELECT state FROM effect_grants WHERE grant_id = ?",
            (outcome_a.handle.grant_id,)).fetchone()["state"]
        assert state == "GRANTED"
        cross = EffectGrantHandle(
            tenant=A, grant_id=outcome_a.handle.grant_id, token=outcome_a.handle.token,
            signature=kernel_b.sign(outcome_a.handle.token))
        refused = claim_grant_cas(kernel_b, cross, params_for(effect_a))
        assert refused.claimed is False and refused.cause == "NO_SUCH_GRANT"
        won = claim_grant_cas(kernel_a, outcome_a.handle, params_for(effect_a))
        assert won.claimed is True, "tenant A's own claim must still succeed after B's probes"
        store_b.close()
    finally:
        store_a.close()
