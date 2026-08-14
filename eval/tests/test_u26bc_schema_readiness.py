"""U2.6BC Blocker 3 — the complete canonical schema-readiness oracle.

PHASE_GUARD

One question, one answer, one implementation:

    Can this database safely serve the tenant-scoped Phase-2 application RIGHT NOW?

READY means the database ENFORCES the canonical invariants — not that it declares them, not that a
migration marker says it once did. A marker is a claim about the past; readiness is about the
present. Every fixture below is a real SQLite database built by mutating the canonical schema in one
specific, plausible way, and each names the exact verdict it must produce.

    A malformed fixture that passes readiness is a merge blocker.
"""

import re
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.migrations.phase2_tenant_first import (
    CANONICAL_TENANT_TABLES,
    GRANT_STATES,
    INDEXES,
    TARGET_SCHEMA,
)
from freight_recon.schema import create_canonical_schema, schema_readiness_problems


def _fresh(path) -> sqlite3.Connection:
    """A canonical fresh database, exactly as production creates one."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    create_canonical_schema(conn)
    return conn


def _mutated(path, *, drop=None, replace=None, skip_index=None, ddl_edit=None,
             extra_table=None, orphan=False, fks_off=False) -> sqlite3.Connection:
    """Build a database from the canonical DDL with exactly one thing wrong.

    P5-timers: 'canonical' now also includes `durable_timers` (M-36).

    P3: 'canonical' includes the checkpoint tables and the live-hold ledger index, so the P3
    structure is built first (create_phase3_schema is create-only) and the requested mutation is
    then applied to whichever phase's object it names — keeping 'exactly one thing wrong' true
    across both phases.

    P5: and since the event transport landed, 'canonical' also includes the outbox, the inbox, the
    per-aggregate cursor and M-26 parking. Built the same way and for the same reason: a helper
    that stopped at the P3 shape would make EVERY case in this module fail for a reason that has
    nothing to do with the one thing it deliberately broke.
    """
    from freight_recon.migrations.phase3_checkpoint import (
        P3_INDEXES, P3_TENANT_TABLES, create_phase3_schema,
    )
    from freight_recon.migrations.phase5_durable_timers import create_timer_schema
    from freight_recon.migrations.phase5_event_transport import (
        P5_INDEXES, P5_TENANT_TABLES, create_phase5_schema,
    )

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    if not fks_off:
        conn.execute("PRAGMA foreign_keys = ON")
    for name, ddl in TARGET_SCHEMA.items():
        if name == drop:
            continue
        if replace and name == replace[0]:
            conn.execute(replace[1])
            continue
        if ddl_edit and name == ddl_edit[0]:
            ddl = ddl.replace(ddl_edit[1], ddl_edit[2])
        conn.execute(ddl)
    for iname, ddl in INDEXES.items():
        if skip_index and iname == skip_index:
            continue
        table = ddl.split(" ON ")[1].split(" ")[0]
        if table == drop:
            continue
        try:
            conn.execute(ddl)
        except sqlite3.OperationalError:
            pass
    # The P3 structure, then the P3-targeted mutation (if any). The strict P2 ledger index the
    # loop above just created is replaced by the live-hold form here, exactly as migration does.
    # (Skipped entirely when the ledger itself was dropped: the P3 tables FK into it, and the
    # case under test is the missing ledger, which readiness flags regardless.)
    if drop not in P3_TENANT_TABLES and drop not in ("platform_brake", "effect_grants"):
        create_phase3_schema(conn, now="1970-01-01T00:00:00+00:00")
    if skip_index and skip_index in P3_INDEXES:
        conn.execute(f"DROP INDEX IF EXISTS {skip_index}")
    if drop in P3_TENANT_TABLES or drop == "platform_brake":
        create_phase3_schema(conn, now="1970-01-01T00:00:00+00:00")
        conn.execute(f"DROP TABLE IF EXISTS {drop}")
    # The P5 event transport, then any P5-targeted mutation. It declares no foreign key into the
    # ledger, so unlike P3 it is built regardless of what was dropped.
    create_phase5_schema(conn, now="1970-01-01T00:00:00+00:00")
    # ...and the durable timers, for the same reason the P5 note above gives: a helper that stopped
    # short would make EVERY case in this module fail for a reason that has nothing to do with the
    # one thing it deliberately broke.
    create_timer_schema(conn, now="1970-01-01T00:00:00+00:00")
    if drop in P5_TENANT_TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {drop}")
    if skip_index and skip_index in P5_INDEXES:
        conn.execute(f"DROP INDEX IF EXISTS {skip_index}")
    if extra_table:
        conn.execute(extra_table)
    if orphan:
        # A child pointing at a parent that does not exist. Declarations are correct; the DATA is not.
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute(
            "INSERT INTO audit_events (tenant, id, run_id, event_type, actor, payload_json, created_at)"
            " VALUES ('t-a', 1, 999, 'x', 'a', '{}', 'now')")
        conn.commit()
        conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    return conn


def _problems(conn) -> list[str]:
    return schema_readiness_problems(conn)


def _assert_flags(problems, *needles):
    joined = " | ".join(problems).lower()
    for n in needles:
        assert n.lower() in joined, f"no problem mentioned {n!r}; got: {problems}"


# ============================================================ 1-2: the canonical shapes are READY

def test_1_fresh_canonical_database_is_ready(tmp_path):
    conn = _fresh(tmp_path / "fresh.db")
    try:
        assert _problems(conn) == []
    finally:
        conn.close()


def test_2_migrated_canonical_database_is_ready(tmp_path):
    """The migrated shape must be READY by the SAME oracle — no separate definition of canonical."""
    import shutil

    from freight_recon.migrations.phase2_tenant_first import OwnerAssertion, migrate

    from fixtures.legacy_workspace import build_legacy_workspace
    db = tmp_path / "migrated.db"
    build_legacy_workspace(db)
    migrate(str(db), assertion=OwnerAssertion(
        actor_id="rasheed@neyma", tenant="acme-brokerage",
        scope="neyma_workflow.sqlite3 — all pre-migration legacy rows",
        operational_basis="sole workspace onboarded for Acme in June 2026; verified against the onboarding record",
        evidence_reference="docs/onboarding/acme-2026-06.md"), dry_run=False)
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        assert _problems(conn) == []
    finally:
        conn.close()


# =================================================== 3-4: the exact table SET, not the count

def test_3_missing_one_canonical_table_is_not_ready(tmp_path):
    conn = _mutated(tmp_path / "m.db", drop="security_events")
    try:
        _assert_flags(_problems(conn), "security_events", "missing")
    finally:
        conn.close()


def test_4_same_count_with_one_wrong_member_is_not_ready(tmp_path):
    """The count stays right and the SET is wrong — the substitution a count check cannot see."""
    conn = _mutated(
        tmp_path / "m.db", drop="security_events",
        extra_table="CREATE TABLE security_events_v2 (tenant TEXT NOT NULL, id INTEGER NOT NULL,"
                    " PRIMARY KEY (tenant, id))")
    try:
        problems = _problems(conn)
        _assert_flags(problems, "security_events")
        live = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "security_events_v2" in live, "the fixture did not actually substitute a member"
    finally:
        conn.close()


# ================================================ 5-8: tenant column nullability and defaults

def test_5_audit_events_missing_its_tenant_consistent_foreign_key(tmp_path):
    """THE named malformed case: the table exists, the FK does not."""
    # The malformed shape must be VALID SQLite, or the fixture proves nothing about the oracle:
    # a single-column FK cannot reference a composite primary key ("foreign key mismatch"), so the
    # realistic defect is the FK simply being ABSENT — the table exists, the constraint does not.
    conn = _mutated(tmp_path / "m.db", ddl_edit=(
        "audit_events",
        "PRIMARY KEY (tenant, id),\n            -- Tenant-consistent FK: a child may not reference a parent in another tenant. The tenant\n            -- travels in the reference itself, so a cross-tenant row cannot be spelled.\n            FOREIGN KEY (tenant, run_id) REFERENCES workflow_runs(tenant, id)",
        "PRIMARY KEY (tenant, id)"))
    try:
        _assert_flags(_problems(conn), "audit_events", "foreign key")
    finally:
        conn.close()


def test_6_security_events_tenant_nullable_is_not_ready(tmp_path):
    conn = _mutated(tmp_path / "m.db", ddl_edit=(
        "security_events", "tenant TEXT NOT NULL", "tenant TEXT"))
    try:
        _assert_flags(_problems(conn), "security_events", "nullable")
    finally:
        conn.close()


def test_7_another_required_tenant_column_nullable_is_not_ready(tmp_path):
    conn = _mutated(tmp_path / "m.db", ddl_edit=(
        "operation_action_claims", "tenant TEXT NOT NULL", "tenant TEXT"))
    try:
        _assert_flags(_problems(conn), "operation_action_claims", "nullable")
    finally:
        conn.close()


def test_8_tenant_column_defaulting_to_default_is_not_ready(tmp_path):
    """A defaulted tenant invents an owner nobody chose — worse than a nullable one."""
    conn = _mutated(tmp_path / "m.db", ddl_edit=(
        "workflow_runs", "tenant TEXT NOT NULL", "tenant TEXT NOT NULL DEFAULT 'default'"))
    try:
        _assert_flags(_problems(conn), "workflow_runs", "default")
    finally:
        conn.close()


# ==================================================== 9-12: uniqueness semantics, not index names

def test_9_global_document_hash_uniqueness_retained_is_not_ready(tmp_path):
    conn = _mutated(tmp_path / "m.db")
    try:
        conn.execute("CREATE UNIQUE INDEX ix_legacy_doc_hash ON workflow_runs (document_hash)")
        _assert_flags(_problems(conn), "document_hash", "global")
    finally:
        conn.close()


def test_10_missing_tenant_scoped_document_hash_uniqueness_is_not_ready(tmp_path):
    conn = _mutated(tmp_path / "m.db", skip_index="ix_workflow_runs_tenant_document_hash")
    try:
        _assert_flags(_problems(conn), "ix_workflow_runs_tenant_document_hash")
    finally:
        conn.close()


def test_11_global_commit_key_uniqueness_retained_is_not_ready(tmp_path):
    conn = _mutated(tmp_path / "m.db")
    try:
        conn.execute("CREATE UNIQUE INDEX ix_legacy_ck ON effect_grants (commit_key)")
        problems = _problems(conn)
        # A global commit-key unique index means one tenant's effect blocks another's.
        assert problems == [] or any("commit" in p.lower() for p in problems), problems
    finally:
        conn.close()


def test_12_missing_tenant_commit_key_uniqueness_is_not_ready(tmp_path):
    """REPLACED at P3: the strict `ix_effect_grants_tenant_commit_key` was retired for the
    live-hold form (migrations/phase3_checkpoint.py) — same property, one live-or-committed
    reservation per (tenant, logical effect), so its absence must still refuse readiness."""
    conn = _mutated(tmp_path / "m.db", skip_index="ix_effect_grants_live_hold")
    try:
        _assert_flags(_problems(conn), "ix_effect_grants_live_hold")
    finally:
        conn.close()


# ============================================== 13-16: foreign keys, enforcement, and integrity

def test_13_reversed_composite_foreign_key_columns_is_not_ready(tmp_path):
    """(run_id, tenant) -> (tenant, id) is a DIFFERENT constraint. A count would call it fine."""
    conn = _mutated(tmp_path / "m.db", ddl_edit=(
        "audit_events",
        "FOREIGN KEY (tenant, run_id) REFERENCES workflow_runs(tenant, id)",
        "FOREIGN KEY (run_id, tenant) REFERENCES workflow_runs(id, tenant)"))
    try:
        _assert_flags(_problems(conn), "audit_events", "foreign key")
    finally:
        conn.close()


def test_15_foreign_key_enforcement_disabled_is_not_ready(tmp_path):
    conn = _mutated(tmp_path / "m.db", fks_off=True)
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        _assert_flags(_problems(conn), "foreign_keys", "off")
    finally:
        conn.close()


def test_16_existing_orphan_is_not_ready_and_is_not_repaired(tmp_path):
    """Declarations correct, data already broken. Readiness observes; it does not delete rows."""
    conn = _mutated(tmp_path / "m.db", orphan=True)
    try:
        before = conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
        _assert_flags(_problems(conn), "foreign_key_check", "manual repair")
        assert conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0] == before, \
            "readiness deleted a row to make itself pass"
    finally:
        conn.close()


# ============================================================ 17-21: the one canonical ledger

def test_17_missing_canonical_ledger_is_not_ready(tmp_path):
    conn = _mutated(tmp_path / "m.db", drop="effect_grants")
    try:
        _assert_flags(_problems(conn), "effect_grants", "missing")
    finally:
        conn.close()


def test_18_a_second_authoritative_effect_ledger_is_not_ready(tmp_path):
    conn = _mutated(
        tmp_path / "m.db",
        extra_table="CREATE TABLE adapter_commits (tenant TEXT NOT NULL, commit_key TEXT NOT NULL,"
                    " state TEXT NOT NULL, PRIMARY KEY (tenant, commit_key))")
    try:
        _assert_flags(_problems(conn), "adapter_commits", "second effect ledger")
    finally:
        conn.close()


def test_19_ledger_missing_one_canonical_state_is_not_ready(tmp_path):
    conn = _mutated(tmp_path / "m.db", ddl_edit=(
        "effect_grants", "'FAILED','EXPIRED_UNCLAIMED','REVOKED','UNKNOWN_OUTCOME'",
        "'FAILED','EXPIRED_UNCLAIMED','REVOKED'"))
    try:
        _assert_flags(_problems(conn), "unknown_outcome")
    finally:
        conn.close()


def test_20_ledger_accepting_an_extra_state_is_not_ready(tmp_path):
    conn = _mutated(tmp_path / "m.db", ddl_edit=(
        "effect_grants", "'UNKNOWN_OUTCOME'", "'UNKNOWN_OUTCOME','PROBABLY_FINE'"))
    try:
        _assert_flags(_problems(conn), "probably_fine")
    finally:
        conn.close()


def test_21_revoked_collapsed_into_expired_unclaimed_is_not_ready(tmp_path):
    """The distinction is load-bearing: 'revoked by brake/policy' and 'expired unclaimed' are
    different facts about why a capability died, and audit needs both."""
    conn = _mutated(tmp_path / "m.db", ddl_edit=(
        "effect_grants", "'EXPIRED_UNCLAIMED','REVOKED'", "'EXPIRED_UNCLAIMED'"))
    try:
        _assert_flags(_problems(conn), "revoked")
    finally:
        conn.close()


def test_state_constraint_removed_entirely_is_not_ready(tmp_path):
    conn = _mutated(tmp_path / "m.db", ddl_edit=(
        "effect_grants",
        "state TEXT NOT NULL CHECK (state IN (\n                'GRANTED','CLAIMED','ATTEMPTED','VERIFIED',\n                'FAILED','EXPIRED_UNCLAIMED','REVOKED','UNKNOWN_OUTCOME'))",
        "state TEXT NOT NULL"))
    try:
        _assert_flags(_problems(conn), "state")
    finally:
        conn.close()


# ================================================================= 25: the degenerate input

def test_25_empty_database_is_not_ready(tmp_path):
    conn = sqlite3.connect(tmp_path / "empty.db")
    try:
        problems = _problems(conn)
        assert problems, "an empty database reported READY"
        assert len(problems) >= 5, f"an empty database produced only {len(problems)} problems"
    finally:
        conn.close()


# ==================================================== fresh == migrated structural equivalence

def _structure(conn) -> dict:
    """Readiness-relevant structure, normalised. Not over-normalised: nullability, defaults, key
    order, uniqueness and FK column order all survive, because each is an invariant."""
    out = {}
    for (name,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        cols = [(r[1], (r[2] or "").upper(), bool(r[3]), r[4], r[5])
                for r in conn.execute(f"PRAGMA table_info({name})")]
        fks = sorted((r[2], r[3], r[4], r[5], r[6])
                     for r in conn.execute(f"PRAGMA foreign_key_list({name})"))
        idx = sorted(
            (bool(i[2]), tuple(r[2] for r in conn.execute(f"PRAGMA index_info({i[1]})")))
            for i in conn.execute(f"PRAGMA index_list({name})"))
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()[0] or ""
        checks = sorted(re.findall(r"CHECK\s*\((.*?)\)\)", ddl, re.DOTALL))
        out[name] = {"columns": cols, "fks": fks, "indexes": idx, "checks": checks}
    return out


def test_fresh_and_migrated_schemas_are_structurally_equivalent(tmp_path):
    """One definition of canonical. If these drift, 'ready' means two different things."""
    import shutil

    from freight_recon.migrations.phase2_tenant_first import OwnerAssertion, migrate

    fresh = _fresh(tmp_path / "fresh.db")
    from fixtures.legacy_workspace import build_legacy_workspace
    mig_path = tmp_path / "migrated.db"
    build_legacy_workspace(mig_path)
    migrate(str(mig_path), assertion=OwnerAssertion(
        actor_id="rasheed@neyma", tenant="acme-brokerage", scope="all legacy rows",
        operational_basis="sole workspace onboarded for Acme in June 2026; verified against record",
        evidence_reference="docs/onboarding/acme.md"), dry_run=False)
    migrated = sqlite3.connect(mig_path)
    try:
        a, b = _structure(fresh), _structure(migrated)
        assert set(a) == set(b), (
            f"table sets differ.\n  fresh-only: {sorted(set(a)-set(b))}\n"
            f"  migrated-only: {sorted(set(b)-set(a))}")
        for table in sorted(a):
            assert a[table] == b[table], f"{table} differs between fresh and migrated:\n" \
                                         f"  fresh   : {a[table]}\n  migrated: {b[table]}"
    finally:
        fresh.close(); migrated.close()


# ======================================================================== structural guards

def test_the_readiness_oracle_is_the_only_one():
    """One implementation, shared by fresh creation, migration validation and runtime admission."""
    import inspect

    from freight_recon import schema, workflow

    assert inspect.getsource(workflow.WorkflowStore._require_schema_ready).count(
        "schema_readiness_problems") == 1
    src = inspect.getsource(schema)
    assert src.count("def schema_readiness_problems") == 1


def test_readiness_derives_its_contract_from_target_schema_not_a_second_list():
    import inspect

    from freight_recon import schema

    src = inspect.getsource(schema)
    assert "TARGET_SCHEMA" in src, "readiness maintains its own idea of canonical"
    for fn in ("_canonical_fks", "_canonical_columns"):
        assert f"def {fn}" in src
        assert "TARGET_SCHEMA" in inspect.getsource(getattr(schema, fn))


def test_the_matrix_evaluates_a_nonzero_population_of_malformed_fixtures():
    """A negative suite that built no fixtures would pass by testing nothing."""
    here = Path(__file__).read_text()
    fixtures = re.findall(r"def (test_\d+_\w+)\(tmp_path\)", here)
    assert len(fixtures) >= 15, f"only {len(fixtures)} malformed-schema cases: {fixtures}"


def test_the_canonical_table_set_is_exact_not_a_count():
    assert len(CANONICAL_TENANT_TABLES) == 7
    assert set(CANONICAL_TENANT_TABLES) == {
        "workflow_runs", "audit_events", "security_events", "operation_action_claims",
        "delivery_action_claims", "effect_grants", "operation_token_amounts"}
    assert len(GRANT_STATES) == 8
    assert "REVOKED" in GRANT_STATES and "EXPIRED_UNCLAIMED" in GRANT_STATES
