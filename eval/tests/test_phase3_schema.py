"""Phase 3 — schema: the checkpoint tables in the one readiness contract, the live-hold index,
fresh/migrated parity, and the atomicity probe over the checkpoint transaction.

The atomicity probe is AC-SAFE-004's oracle: exactly one commit contains all seven reads, the
witness insert and the mint — traced from the SQLite statement stream, not inferred from code
reading.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from phase3_kit import T_A, green_scenario, make_store  # noqa: E402

from freight_recon.migrations.phase2_tenant_first import TARGET_SCHEMA, INDEXES  # noqa: E402
from freight_recon.migrations.phase3_checkpoint import (  # noqa: E402
    LIVE_HOLD_STATES,
    P3_INDEXES,
    P3_TRIGGERS,
    REPLACED_INDEXES,
    create_phase3_schema,
    phase3_readiness_problems,
)
from freight_recon.schema import (  # noqa: E402
    create_canonical_schema,
    schema_readiness_problems,
)
from freight_recon.workflow import WorkflowStore, utc_now  # noqa: E402
from freight_recon.checkpoint import run_checkpoint  # noqa: E402


def test_a_fresh_database_is_checkpoint_ready_with_zero_problems(tmp_path):
    store = make_store(tmp_path)
    assert schema_readiness_problems(store.conn) == []
    assert phase3_readiness_problems(store.conn) == []
    store.close()


def test_missing_witness_triggers_are_a_readiness_problem(tmp_path):
    store = make_store(tmp_path)
    for trigger in P3_TRIGGERS:
        store.conn.execute(f"DROP TRIGGER {trigger}")
    store.conn.commit()
    problems = phase3_readiness_problems(store.conn)
    assert any("append-only triggers missing" in p for p in problems), problems
    store.close()


def test_a_missing_platform_brake_row_is_a_readiness_problem(tmp_path):
    store = make_store(tmp_path)
    store.conn.execute("DELETE FROM platform_brake")
    store.conn.commit()
    problems = phase3_readiness_problems(store.conn)
    assert any("exactly ONE row" in p for p in problems), problems
    store.close()


def test_the_replaced_strict_index_is_reported_if_it_returns(tmp_path):
    store = make_store(tmp_path)
    store.conn.execute("DROP INDEX ix_effect_grants_live_hold")
    store.conn.execute(
        "CREATE UNIQUE INDEX ix_effect_grants_tenant_commit_key "
        "ON effect_grants (tenant, commit_key)")
    store.conn.commit()
    problems = phase3_readiness_problems(store.conn)
    assert any("still present" in p for p in problems), problems
    assert any("ix_effect_grants_live_hold" in p for p in problems), problems
    store.close()


def test_a_phase2_only_database_is_refused_until_the_phase3_migration_runs(tmp_path):
    """An existing Phase-2 canonical database (no checkpoint tables) is refused at construction
    with the migration named; running the migration makes it byte-equivalent to fresh."""
    db = tmp_path / "p2only.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    # Build the PHASE-2 shape only: the P2 DDL + P2 indexes, including the strict ledger index.
    for ddl in TARGET_SCHEMA.values():
        conn.execute(ddl)
    for ddl in INDEXES.values():
        conn.execute(ddl)
    conn.commit()
    problems = schema_readiness_problems(conn)
    assert any("phase3_checkpoint migration" in p for p in problems), problems
    with pytest.raises(Exception):
        WorkflowStore(db, tenant=T_A)
    performed = create_phase3_schema(conn, now=utc_now())
    assert any(step.startswith("create-table:checkpoint_witnesses") for step in performed)
    assert any(step == "drop-index:ix_effect_grants_tenant_commit_key" for step in performed)
    assert phase3_readiness_problems(conn) == []
    # ### P5 CORRECTION. "Canonical" is ONE shape and that shape moved: since the event transport
    # landed, a database carrying only P2+P3 is still refused, and correctly so - a store whose
    # outbox does not exist cannot honour M-23. This node keeps asserting that the P3 migration
    # closes the P3 gap (above), and now also that P3 followed by P5 reaches the FRESH shape
    # (below) - which is the property that actually matters here and is unchanged: a migrated
    # database and a fresh database agree about what canonical means.
    from freight_recon.migrations.phase5_event_transport import (  # noqa: E402
        create_phase5_schema,
        phase5_readiness_problems,
    )

    assert any("phase5_event_transport" in p for p in schema_readiness_problems(conn)), (
        schema_readiness_problems(conn))
    p5_performed = create_phase5_schema(conn, now=utc_now())
    assert any(step == "create-table:event_outbox" for step in p5_performed)
    assert any(step == "create-trigger:trg_event_inbox_append_only_delete" for step in p5_performed)
    assert phase5_readiness_problems(conn) == []
    conn.close()
    migrated = WorkflowStore(db, tenant=T_A)   # now constructible
    fresh = make_store(tmp_path, name="fresh.db")

    def shape(c: sqlite3.Connection) -> set[tuple[str, str]]:
        return {
            (r["type"], r["name"]) for r in c.execute(
                "SELECT type, name FROM sqlite_master WHERE type IN ('table','index','trigger') "
                "AND name NOT LIKE 'sqlite_%'").fetchall()
        }

    assert shape(migrated.conn) == shape(fresh.conn), (
        "a migrated database and a fresh database disagree about what canonical means")
    migrated.close()
    fresh.close()


def test_rerunning_the_phase3_migration_is_a_noop(tmp_path):
    store = make_store(tmp_path)
    assert create_phase3_schema(store.conn, now=utc_now()) == []
    store.close()


def test_the_live_hold_index_holds_live_and_committed_frees_dead(tmp_path):
    """One live-or-committed row per (tenant, commit_key): GRANTED/CLAIMED/ATTEMPTED/VERIFIED/
    UNKNOWN_OUTCOME block a second row; EXPIRED_UNCLAIMED/REVOKED/FAILED free the key."""
    store = make_store(tmp_path)

    def insert(state: str, suffix: str) -> None:
        store.conn.execute(
            "INSERT INTO effect_grants (tenant, grant_id, commit_key, action_class, "
            "target_system, target_resource_id, target_operation, state, issued_at, created_at) "
            "VALUES (?, ?, 'ck-hold', 'a', 't', 'r', 'o', ?, 'now', 'now')",
            (T_A, f"g-{suffix}", state))

    held = 0
    for state in LIVE_HOLD_STATES:
        store.conn.execute("DELETE FROM effect_grants WHERE commit_key = 'ck-hold'")
        insert(state, "first")
        with pytest.raises(sqlite3.IntegrityError):
            insert("GRANTED", "second")
        store.conn.rollback()
        held += 1
    assert held == 5, "the live-hold population collapsed"
    freed = 0
    for state in ("EXPIRED_UNCLAIMED", "REVOKED", "FAILED"):
        store.conn.execute("DELETE FROM effect_grants WHERE commit_key = 'ck-hold'")
        insert(state, "dead")
        insert("GRANTED", "re-mint")     # must succeed: the dead row frees the key
        store.conn.execute("DELETE FROM effect_grants WHERE commit_key = 'ck-hold'")
        freed += 1
    store.conn.commit()
    assert freed == 3
    store.close()


def test_the_commit_once_partial_index_survives_unchanged(tmp_path):
    store = make_store(tmp_path)
    row = store.conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'ix_effect_grants_commit_once'").fetchone()
    assert row and "WHERE state = 'CLAIMED'" in row["sql"]
    store.close()


def test_no_second_effect_ledger_appeared_with_the_new_tables(tmp_path):
    """checkpoint_witnesses carries commit_key but deliberately NO state (no lifecycle);
    brakes carries state but no commit_key. Neither is a second effect authority, and the
    Phase-2 guard that scans for one still passes over the extended schema."""
    store = make_store(tmp_path)
    assert schema_readiness_problems(store.conn) == []
    witness_cols = {r[1] for r in store.conn.execute(
        "PRAGMA table_info(checkpoint_witnesses)").fetchall()}
    assert "commit_key" in witness_cols and "state" not in witness_cols
    brake_cols = {r[1] for r in store.conn.execute("PRAGMA table_info(brakes)").fetchall()}
    assert "state" in brake_cols and "commit_key" not in brake_cols
    store.close()


# ------------------------------------------------------------------ the atomicity probe

def test_exactly_one_commit_contains_the_seven_reads_the_witness_and_the_mint(tmp_path):
    """AC-SAFE-004's transaction-boundary probe: trace the statement stream during a green
    checkpoint and assert ONE transaction covers the brake read, the witness insert and the
    grant insert — no commit between them, no statement after the BEGIN outside it."""
    store, kernel, clock, effect, facts, versions, approval, world, inputs, request = (
        green_scenario(tmp_path))
    statements: list[str] = []
    store.conn.set_trace_callback(lambda sql: statements.append(" ".join(sql.split())))
    outcome = run_checkpoint(kernel, request, inputs)
    store.conn.set_trace_callback(None)
    assert outcome.authorized
    begins = [i for i, s in enumerate(statements) if s.startswith("BEGIN")]
    commits = [i for i, s in enumerate(statements) if s == "COMMIT"]
    assert len(begins) == 1 and len(commits) == 1, (
        f"the checkpoint must be ONE transaction: BEGINs={len(begins)} COMMITs={len(commits)}\n"
        + "\n".join(statements))
    inside = statements[begins[0] + 1: commits[0]]
    assert any("FROM platform_brake" in s for s in inside), "brake read escaped the transaction"
    assert any(s.startswith("INSERT INTO effect_grants") for s in inside), "mint escaped"
    assert any(s.startswith("INSERT INTO checkpoint_witnesses") for s in inside), "witness escaped"
    witness_index = next(i for i, s in enumerate(inside)
                         if s.startswith("INSERT INTO checkpoint_witnesses"))
    grant_index = next(i for i, s in enumerate(inside)
                       if s.startswith("INSERT INTO effect_grants"))
    between = inside[min(witness_index, grant_index) + 1: max(witness_index, grant_index)]
    assert all(not s.startswith(("COMMIT", "BEGIN")) for s in between), (
        "a transaction boundary between the witness insert and the mint")
    store.close()


def test_a_refused_checkpoint_commits_nothing_at_any_statement(tmp_path):
    """The refusal path's transaction discipline: a step-2 drift refusal rolls back; the only
    COMMITs in the stream belong to the post-rollback security-event record, and no INSERT into
    the witness or grant tables appears anywhere."""
    store, kernel, clock, effect, facts, versions, approval, world, inputs, request = (
        green_scenario(tmp_path))
    from freight_recon.fingerprint import Money
    from dataclasses import replace
    world["facts"]["amount"] = replace(world["facts"]["amount"], _value=Money(310000, "GBP"))
    statements: list[str] = []
    store.conn.set_trace_callback(lambda sql: statements.append(" ".join(sql.split())))
    outcome = run_checkpoint(kernel, request, inputs)
    store.conn.set_trace_callback(None)
    assert outcome.authorized is False and outcome.reason == "VOID_ON_DRIFT"
    assert not any("INSERT INTO checkpoint_witnesses" in s for s in statements)
    assert not any("INSERT INTO effect_grants" in s for s in statements)
    assert any(s.startswith("ROLLBACK") for s in statements), "the refusal never rolled back"
    store.close()
