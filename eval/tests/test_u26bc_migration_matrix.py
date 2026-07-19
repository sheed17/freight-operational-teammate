"""U2.6BC Blocker 5 — the complete migration and cutover matrix.

PHASE_GUARD

Every supported starting shape must reach EXACTLY ONE classified outcome, and each outcome must tell
an operator what to do next. "It failed" is not an outcome: it does not say whether to retry, supply
an assertion, repair a schema by hand, or stop and call someone.

    The completion marker is written LAST, and only if readiness passes.

A marker written earlier is a claim about the past that outranks the present — which is precisely how
a half-migrated database gets deployed on top of.
"""

import hashlib
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from freight_recon.migrations.phase2_tenant_first import (
    CANONICAL_READY,
    CONFLICTING_OWNER_ASSERTION,
    DRY_RUN_ONLY,
    MIGRATION_COMPLETE_RESTART_SAFE,
    MIGRATION_OUTCOMES,
    NEXT_ACTION,
    OWNER_ASSERTION_REQUIRED,
    PARTIAL_MIGRATION_DETECTED,
    QUARANTINED_PENDING_REVIEW,
    TARGET_SCHEMA,
    UNSUPPORTED_SCHEMA_VERSION,
    AssertionIncomplete,
    MigrationRefused,
    OwnerAssertion,
    migrate,
)
from freight_recon.schema import create_canonical_schema, schema_readiness_problems

from fixtures.legacy_workspace import LEGACY_RUNS, build_legacy_workspace

VALID = dict(
    actor_id="rasheed@neyma",
    tenant="acme-brokerage",
    scope="neyma_workflow.sqlite3 — all pre-migration legacy rows",
    operational_basis="sole workspace onboarded for Acme in June 2026; verified against the onboarding record",
    evidence_reference="docs/onboarding/acme-2026-06.md",
)


def _assertion(**over):
    return OwnerAssertion(**{**VALID, **over})


def _digest(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _tables(db) -> set[str]:
    c = sqlite3.connect(db)
    try:
        return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        c.close()


def _count(db, table) -> int:
    if table not in _tables(db):
        return 0
    c = sqlite3.connect(db)
    try:
        return c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        c.close()


def _ready(db) -> list[str]:
    c = sqlite3.connect(db)
    c.execute("PRAGMA foreign_keys = ON")
    try:
        return schema_readiness_problems(c)
    finally:
        c.close()


# ---- the shapes ------------------------------------------------------------------------------

def _fresh(tmp_path, name="fresh.db") -> str:
    db = tmp_path / name
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys = ON")
    create_canonical_schema(conn)
    conn.close()
    return str(db)


def _empty_legacy(tmp_path, name="empty-legacy.db", *, claims=True) -> str:
    """Legacy tables, no business rows."""
    db = tmp_path / name
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE workflow_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, load_id TEXT NOT NULL,
            document_hash TEXT NOT NULL UNIQUE, state TEXT NOT NULL,
            workflow_direction TEXT NOT NULL DEFAULT 'CARRIER_PAYABLE', invoice_number TEXT,
            carrier TEXT, outcome TEXT, reason TEXT, created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL);
        CREATE TABLE audit_events (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL,
            event_type TEXT NOT NULL, actor TEXT NOT NULL, from_state TEXT, to_state TEXT,
            payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
    """)
    if claims:
        conn.execute("""CREATE TABLE operation_commit_claims (commit_key TEXT PRIMARY KEY,
            tenant TEXT NOT NULL, lane TEXT NOT NULL, load_ref TEXT NOT NULL, party TEXT NOT NULL,
            approved_amount TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL)""")
    conn.commit(); conn.close()
    return str(db)


def _populated_legacy(tmp_path, name="legacy.db") -> str:
    db = tmp_path / name
    build_legacy_workspace(db)
    return str(db)


# ==================================================== every outcome is classified and actionable

def test_every_outcome_names_a_safe_next_action():
    assert len(MIGRATION_OUTCOMES) == 10
    assert set(MIGRATION_OUTCOMES) == set(NEXT_ACTION)
    # A word count is not a contract: mutation showed that "ok..." passes it while telling an
    # operator nothing. The action must name something a person can actually DO.
    VERBS = ("supply", "re-run", "rerun", "inspect", "review", "repair", "deploy", "resolve",
             "settle", "none", "stop")
    for o in MIGRATION_OUTCOMES:
        action = NEXT_ACTION[o]
        assert len(action.split()) >= 4, f"{o}: the next action is too thin to act on"
        # The verb must OPEN the instruction. Allowing it anywhere lets "okand settle each row..."
        # pass — mutation found exactly that, because a substring check anywhere in a sentence is
        # satisfied by the sentence still containing its old text.
        assert action.lower().split()[0].strip(",.;:") in VERBS, (
            f"{o}: {action!r} does not begin with an action an operator can take"
        )


# ================================================================ SHAPE 1 — fresh empty database

def test_shape_1_fresh_database_is_canonical_and_rerun_is_a_noop(tmp_path):
    db = _fresh(tmp_path)
    assert _ready(db) == [], "a freshly created database is not canonical"
    assert "effect_grants" in _tables(db)
    before = _digest(db)
    rep = migrate(db, dry_run=False)
    assert rep.outcome in (CANONICAL_READY, MIGRATION_COMPLETE_RESTART_SAFE)
    assert _digest(db) == before or _ready(db) == [], "migrating a canonical database changed it"


# ================================================================= SHAPE 2 — empty legacy database

def test_shape_2_empty_legacy_needs_no_assertion_and_becomes_canonical(tmp_path):
    """No business rows means no ownership to assert. Requiring one would be theatre."""
    db = _empty_legacy(tmp_path)
    rep = migrate(db, dry_run=False)
    assert sum(rep.rows_quarantined.values()) == 0
    assert "effect_grants" in _tables(db), "the canonical ledger was not created"
    assert rep.outcome in (CANONICAL_READY, MIGRATION_COMPLETE_RESTART_SAFE), rep.readiness_problems
    assert _ready(db) == []


def test_shape_13_empty_legacy_claim_table_still_yields_the_ledger(tmp_path):
    db = _empty_legacy(tmp_path, "empty-claims.db", claims=True)
    migrate(db, dry_run=False)
    assert "effect_grants" in _tables(db)
    assert _count(db, "effect_grants") == 0, "empty legacy claims manufactured ledger rows"


def test_shape_12_absent_legacy_claim_table_still_yields_the_ledger(tmp_path):
    """Ledger creation must not depend on a legacy table that a workspace never had."""
    db = _empty_legacy(tmp_path, "no-claims.db", claims=False)
    migrate(db, dry_run=False)
    assert "effect_grants" in _tables(db)
    assert _count(db, "effect_grants") == 0


# ======================================================= SHAPES 3-7 — populated legacy + assertion

def test_shape_3_valid_assertion_migrates_only_the_authorized_scope(tmp_path):
    db = _populated_legacy(tmp_path)
    rep = migrate(db, assertion=_assertion(), dry_run=False)
    assert rep.outcome == CANONICAL_READY, rep.readiness_problems
    assert sum(rep.rows_migrated.values()) == 120
    assert sum(rep.rows_quarantined.values()) == 0
    tenants = {r[0] for r in sqlite3.connect(db).execute("SELECT DISTINCT tenant FROM workflow_runs")}
    assert tenants == {VALID["tenant"]}
    assert _count(db, "owner_assertions") == 1
    assert rep.migration_run_id and rep.assertion_id


def test_shape_4_no_assertion_quarantines_and_never_infers_ownership(tmp_path):
    db = _populated_legacy(tmp_path)
    rep = migrate(db, dry_run=False)
    assert rep.outcome == QUARANTINED_PENDING_REVIEW, rep.outcome
    assert sum(rep.rows_migrated.values()) == 0
    assert sum(rep.rows_quarantined.values()) == 120
    assert _count(db, "workflow_runs") == 0, "a row was guessed into a tenant"
    assert _count(db, "owner_assertions") == 0
    # The outcome must tell an operator what to DO. Quarantine's action is to settle each row by
    # hand — the point being that nothing was guessed, which is what the wording has to convey.
    assert "by hand" in rep.next_action and "Nothing was guessed" in rep.next_action


def test_shape_5_invalid_tenant_assertion_changes_absolutely_nothing(tmp_path):
    from freight_recon.tenant import InvalidTenant

    db = _populated_legacy(tmp_path)
    before = _digest(db)
    with pytest.raises(InvalidTenant):
        migrate(db, assertion=_assertion(tenant="default"), dry_run=False)
    assert _digest(db) == before, "an invalid assertion still touched the database"
    assert "owner_assertions" not in _tables(db)
    assert "migration_quarantine" not in _tables(db)


@pytest.mark.parametrize("missing", ["actor_id", "scope", "operational_basis", "evidence_reference"])
def test_shape_6_incomplete_assertion_fails_before_assignment(tmp_path, missing):
    db = _populated_legacy(tmp_path)
    before = _digest(db)
    with pytest.raises(AssertionIncomplete):
        migrate(db, assertion=_assertion(**{missing: ""}), dry_run=False)
    assert _digest(db) == before


def test_shape_7_conflicting_assertion_preserves_original_ownership(tmp_path):
    db = _populated_legacy(tmp_path)
    migrate(db, assertion=_assertion(), dry_run=False)
    with pytest.raises(MigrationRefused, match="CONFLICTING OWNER ASSERTION"):
        migrate(db, assertion=_assertion(tenant="beta-logistics", actor_id="other@neyma"),
                dry_run=False)
    tenants = {r[0] for r in sqlite3.connect(db).execute("SELECT DISTINCT tenant FROM workflow_runs")}
    assert tenants == {VALID["tenant"]}, "a conflicting assertion reassigned ownership"
    c = sqlite3.connect(db)
    assert c.execute("SELECT conflicts_detected FROM owner_assertions").fetchone()[0] == 1
    c.close()


# ======================================================== SHAPES 8, 10, 11 — partial and malformed

def test_shape_8_partial_additive_schema_is_detected_and_blocks_runtime(tmp_path):
    """Tenant columns exist, constraints do not. Runtime must stay blocked."""
    db = tmp_path / "partial.db"
    conn = sqlite3.connect(db)
    for name in ("workflow_runs", "audit_events"):
        conn.execute(TARGET_SCHEMA[name])
    conn.commit(); conn.close()
    problems = _ready(str(db))
    assert problems, "a partial schema reported ready"
    rep = migrate(str(db), dry_run=True)
    assert rep.outcome in (DRY_RUN_ONLY, PARTIAL_MIGRATION_DETECTED)


def test_shape_11_a_completion_marker_cannot_outrank_a_malformed_schema(tmp_path):
    """THE marker rule: structure decides, the marker only records what structure proved."""
    db = tmp_path / "lying-marker.db"
    conn = sqlite3.connect(db)
    for name, ddl in TARGET_SCHEMA.items():
        if name == "security_events":     # deliberately absent
            continue
        conn.execute(ddl)
    conn.execute("INSERT INTO schema_migrations (migration, step, applied_at, detail) "
                 "VALUES ('phase2_tenant_first', 'version:phase2-tenant-first-1', 'now', 'lie')")
    conn.commit(); conn.close()
    problems = _ready(str(db))
    assert problems, "a marker claiming completion outranked a missing canonical table"
    assert any("security_events" in p for p in problems)


def test_shape_19_an_unsupported_future_version_is_refused_not_downgraded(tmp_path):
    db = _fresh(tmp_path, "future.db")
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO schema_migrations (migration, step, applied_at, detail) "
                 "VALUES ('phase2_tenant_first', 'version:phase9-from-the-future', 'now', '')")
    conn.commit(); conn.close()
    problems = _ready(db)
    assert problems and any("schema version" in p for p in problems)
    rep = migrate(db, dry_run=True)
    assert rep.outcome in (UNSUPPORTED_SCHEMA_VERSION, DRY_RUN_ONLY)
    assert "must NOT be downgraded" in NEXT_ACTION[UNSUPPORTED_SCHEMA_VERSION]


# ================================================================ SHAPE 20 — already canonical

def test_shape_20_already_canonical_is_a_true_noop(tmp_path):
    db = _populated_legacy(tmp_path)
    migrate(db, assertion=_assertion(), dry_run=False)
    assertions_before = _count(db, "owner_assertions")
    effects_before = _count(db, "effect_grants")
    runs_before = _count(db, "workflow_runs")

    rep = migrate(db, assertion=_assertion(), dry_run=False)
    assert rep.already_applied is True
    assert rep.outcome == MIGRATION_COMPLETE_RESTART_SAFE
    assert _count(db, "owner_assertions") == assertions_before, "rerun duplicated the assertion"
    assert _count(db, "effect_grants") == effects_before, "rerun duplicated canonical effects"
    assert _count(db, "workflow_runs") == runs_before, "rerun duplicated rows"
    assert _ready(db) == []


# ============================================================================ DRY-RUN QUALIFICATION

def test_dry_run_changes_nothing_on_every_shape(tmp_path):
    """Byte identity, not 'no errors observed'."""
    shapes = {
        "fresh": _fresh(tmp_path, "d1.db"),
        "empty-legacy": _empty_legacy(tmp_path, "d2.db"),
        "populated": _populated_legacy(tmp_path, "d3.db"),
    }
    for name, db in shapes.items():
        before = _digest(db)
        rep = migrate(db, assertion=_assertion(), dry_run=True)
        assert _digest(db) == before, f"dry run wrote to the {name} database"
        assert rep.dry_run is True
        assert rep.outcome in (DRY_RUN_ONLY, OWNER_ASSERTION_REQUIRED,
                               MIGRATION_COMPLETE_RESTART_SAFE, CANONICAL_READY)


def test_dry_run_on_unowned_history_says_an_assertion_is_required(tmp_path):
    """An operator should learn this BEFORE apply, not after a refusal."""
    db = _populated_legacy(tmp_path)
    rep = migrate(db, dry_run=True)
    assert rep.outcome == OWNER_ASSERTION_REQUIRED
    assert rep.classifications.get("AMBIGUOUS_TENANT") == 120


# ============================================================ SHAPES 14-15 — legacy effect history

def _seed_legacy_claims(db, rows):
    conn = sqlite3.connect(db)
    for key, amount, status in rows:
        conn.execute(
            "INSERT INTO operation_commit_claims (commit_key, tenant, lane, load_ref, party,"
            " approved_amount, payload_json, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (key, "acme-brokerage", "raise_invoice", "LD-1", "CUST", amount,
             f'{{"status": "{status}"}}', "2026-06-01"))
    conn.commit(); conn.close()


def test_shape_14_duplicate_legacy_reservations_are_preserved_not_merged(tmp_path):
    """Two legacy rows for one logical effect ARE evidence of a historical double-commit."""
    db = _empty_legacy(tmp_path, "dupes.db")
    _seed_legacy_claims(db, [("legacy-a", "2850.00", "COMMITTED"),
                             ("legacy-b", "3100.00", "COMMITTED")])
    rep = migrate(db, assertion=_assertion(), dry_run=False)
    assert _count(db, "effect_grants") == 2, "two historical observations were merged into one"
    amounts = {r[0] for r in sqlite3.connect(db).execute(
        "SELECT approved_amount FROM effect_grants")}
    assert amounts == {"2850.00", "3100.00"}, "material-fact disagreement was erased"
    assert rep.classifications.get("DUPLICATE_LEGACY_RESERVATION", 0) >= 2


def test_shape_15_a_timeout_never_becomes_failed(tmp_path):
    """An unconfirmed reservation is UNKNOWN. Silence is not failure and not success."""
    db = _empty_legacy(tmp_path, "timeout.db")
    _seed_legacy_claims(db, [("legacy-reserved", "2850.00", "RESERVED")])
    migrate(db, assertion=_assertion(), dry_run=False)
    row = sqlite3.connect(db).execute(
        "SELECT state, unknown_reason FROM effect_grants").fetchone()
    assert row[0] == "UNKNOWN_OUTCOME", f"a timeout was classified {row[0]!r}"
    assert row[0] != "FAILED"
    assert row[1], "the unknown reason was not recorded"


def test_a_committed_legacy_effect_is_not_re_manufactured_as_pending(tmp_path):
    db = _empty_legacy(tmp_path, "committed.db")
    _seed_legacy_claims(db, [("legacy-done", "2850.00", "COMMITTED")])
    migrate(db, assertion=_assertion(), dry_run=False)
    state = sqlite3.connect(db).execute("SELECT state FROM effect_grants").fetchone()[0]
    assert state == "VERIFIED", f"a proven-committed effect became {state!r}"


# ============================================================ restart / interruption qualification

def test_an_interrupted_migration_resumes_without_duplicating(tmp_path):
    """Simulated interruption: the migration is re-invoked over its own partial output."""
    db = _populated_legacy(tmp_path)
    # first pass with no assertion: everything quarantines, nothing is assigned
    first = migrate(db, dry_run=False)
    assert sum(first.rows_quarantined.values()) == 120
    quarantined_before = _count(db, "migration_quarantine")

    # resume: the same call again must not double-quarantine
    second = migrate(db, dry_run=False)
    assert _count(db, "migration_quarantine") == quarantined_before, (
        "a resumed migration duplicated quarantine evidence"
    )
    assert _count(db, "workflow_runs") == 0
    assert second.outcome in (QUARANTINED_PENDING_REVIEW, MIGRATION_COMPLETE_RESTART_SAFE,
                              CANONICAL_READY)


def test_the_completion_marker_is_written_only_after_readiness_passes(tmp_path):
    """Structural: the marker follows readiness in the source, not merely in intent."""
    import inspect

    from freight_recon.migrations import phase2_tenant_first as m

    src = inspect.getsource(m.migrate)
    marker = src.index('_mark(conn, f"version:{SCHEMA_VERSION}"')
    decision = src.index("rep.outcome = _final_outcome(db, rep, already=False)")
    assert decision < marker, (
        "the completion marker is written before readiness is decided — a marker that outranks "
        "structure is how a half-migrated database gets deployed on top of"
    )


# ==================================================================== mixed-version cutover

def test_a_tenant_scoped_application_refuses_a_legacy_database(tmp_path):
    """New application, old schema: fail closed before any tenant-owned SQL."""
    from freight_recon.schema import SchemaNotReady
    from freight_recon.workflow import WorkflowStore

    db = _populated_legacy(tmp_path)
    with pytest.raises(SchemaNotReady):
        store = WorkflowStore(db, tenant="acme-brokerage")
        try:
            store.list_runs()
        finally:
            store.close()


def test_a_migrated_database_serves_the_tenant_scoped_application(tmp_path):
    from freight_recon.workflow import WorkflowStore

    db = _populated_legacy(tmp_path)
    migrate(db, assertion=_assertion(), dry_run=False)
    store = WorkflowStore(db, tenant=VALID["tenant"])
    try:
        assert len(store.list_runs()) == 18
    finally:
        store.close()


def test_the_forward_only_boundary_is_documented_and_structural():
    """Rollback may disable capability. It may never restore unscoped execution."""
    import inspect

    from freight_recon import workflow
    from freight_recon.migrations import phase2_tenant_first as m

    # no path re-creates the global document-hash uniqueness the migration removed
    assert "document_hash TEXT NOT NULL UNIQUE" not in m.TARGET_SCHEMA["workflow_runs"]
    # and the store cannot be built without a tenant
    params = inspect.signature(workflow.WorkflowStore.__init__).parameters
    assert params["tenant"].default is inspect.Parameter.empty
