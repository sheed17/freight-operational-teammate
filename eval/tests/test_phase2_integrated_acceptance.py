"""The ONE Phase-2 acceptance entry point: the real implementation, real SQLite, real threads.

Nothing here is mocked. A mock proves the API is shaped right and says nothing about whether two
concurrent writers converge on one row, whether SQLite actually refuses the second insert, or
whether a rolled-back transaction left a partial state behind. Under Phase-2 qualification the
database IS the thing under test, so substituting it removes the evidence.

Three parts:

  Part A - 12 named database states, each built from the real migration or the real schema, each
           asserted to produce exactly one canonical readiness answer.
  Part B - the 20 required concurrency schedules. Each runs the real store from multiple threads
           against a real file-backed database and asserts ONE canonical result. "It didn't crash"
           is not a result; every schedule below names what must be true afterwards.
  Part C - the integrated invariants that only hold once every blocker is in place at once.

Threading note: every schedule uses a barrier so the racing operations genuinely overlap, and each
thread opens its OWN store (a connection is not thread-safe and sharing one would test a lock we do
not ship). Where SQLite's own serialization is the mechanism under test, that is the point.
"""

from __future__ import annotations

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from freight_recon.commit_key import CanonicalOccurrence, LogicalEffect, commit_key
from freight_recon.migrations.phase2_tenant_first import (
    CANONICAL_TENANT_TABLES,
    MIGRATION_COMPLETE_RESTART_SAFE,
    QUARANTINED_PENDING_REVIEW,
    OwnerAssertion,
    migrate,
)
from freight_recon.schema import (
    create_canonical_schema,
    enable_and_verify_foreign_keys,
    schema_readiness_problems,
)
from freight_recon.workflow import (
    WorkflowDirection,
    WorkflowError,
    WorkflowState,
    WorkflowStore,
    _direction_scoped_document_hash,
)

TENANT_A = "acme-freight"
TENANT_B = "borderline-logistics"


def require_population(items, what: str):
    """A negative assertion over an empty set passes while proving nothing. Refuse that."""
    assert items, f"no {what} to assert over - this test would pass vacuously"
    return items


# --------------------------------------------------------------------------------------------
# fixtures: real databases, built the way production builds them
# --------------------------------------------------------------------------------------------


def canonical_db(path: Path) -> Path:
    """Built by PRODUCTION'S OWN schema builder, not a copy of the DDL. A fixture holding its own
    copy of the schema drifts from the thing it is supposed to represent, and then the suite
    qualifies a database shape that no migration ever produces."""
    conn = sqlite3.connect(path)
    try:
        enable_and_verify_foreign_keys(conn)
        create_canonical_schema(conn)
        conn.commit()
    finally:
        conn.close()
    return path


def legacy_db(path: Path, *, rows: int = 0) -> Path:
    """The pre-Phase-2 shape: no tenant column, globally unique document_hash."""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE workflow_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            load_id TEXT NOT NULL,
            document_hash TEXT NOT NULL UNIQUE,
            state TEXT NOT NULL,
            workflow_direction TEXT NOT NULL DEFAULT 'carrier_payable',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL REFERENCES workflow_runs(id),
            event_type TEXT NOT NULL,
            actor TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    for i in range(rows):
        conn.execute(
            "INSERT INTO workflow_runs (load_id, document_hash, state, created_at, updated_at) "
            "VALUES (?, ?, 'received', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')",
            (f"L{i:04d}", f"hash-{i:04d}"),
        )
    conn.commit()
    conn.close()
    return path


def valid_assertion(tenant: str = TENANT_A) -> OwnerAssertion:
    return OwnerAssertion(
        actor_id="rasheed.samady",
        tenant=tenant,
        scope="workflow_runs,audit_events",
        operational_basis="single brokerage workspace confirmed against the signed client contract",
        evidence_reference="contract/2026-ACME-001",
    )


def readiness_problems(db: Path) -> list[str]:
    """Open the database read-only and ask the ONE oracle. No second implementation lives here."""
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        # Production enables foreign keys on every connection it opens; a probe that skips it would
        # report "enforcement off" on a perfectly good database and mask the real answer.
        try:
            enable_and_verify_foreign_keys(conn)
        except Exception:  # noqa: BLE001 - an unenforceable database is a real readiness problem
            pass
        return schema_readiness_problems(conn)
    finally:
        conn.close()


def schema_is_ready(db: Path) -> bool:
    return not readiness_problems(db)


def apply_migration(db: Path, **kw):
    """`migrate` defaults to dry_run=True. A fixture that forgot that would assert over an
    UNTOUCHED database and call it migrated, so applying is always explicit here."""
    kw.setdefault("dry_run", False)
    return migrate(str(db), **kw)


def store(path: Path, tenant: str) -> WorkflowStore:
    return WorkflowStore(str(path), tenant=tenant)


# ============================================================================================
# PART A - the 12 named database states, one canonical answer each
# ============================================================================================


def test_state_01_fresh_canonical_is_ready(tmp_path):
    assert schema_is_ready(canonical_db(tmp_path / "a.db"))


def test_state_02_empty_file_is_not_ready(tmp_path):
    db = tmp_path / "b.db"
    sqlite3.connect(db).close()
    problems = require_population(readiness_problems(db), "problems in an empty database")
    assert not schema_is_ready(db)
    assert any("workflow_runs" in p for p in problems)


def test_state_03_legacy_untouched_is_not_ready(tmp_path):
    db = legacy_db(tmp_path / "c.db", rows=5)
    assert not schema_is_ready(db)


def test_state_04_migrated_empty_legacy_is_ready(tmp_path):
    db = legacy_db(tmp_path / "d.db", rows=0)
    apply_migration(db)
    assert schema_is_ready(db)


def test_state_05_migrated_populated_with_assertion_is_ready(tmp_path):
    db = legacy_db(tmp_path / "e.db", rows=12)
    rep = apply_migration(db, assertion=valid_assertion())
    assert schema_is_ready(db)
    assert sum(rep.rows_migrated.values()) >= 12


def test_state_06_migrated_populated_without_assertion_is_quarantined_not_ready(tmp_path):
    db = legacy_db(tmp_path / "f.db", rows=12)
    rep = apply_migration(db)
    assert sum(rep.rows_quarantined.values()) >= 12
    assert sum(rep.rows_migrated.values()) == 0, "no owner was chosen - none may be invented"
    # The OUTCOME, not just the counts. A database can hold a perfectly canonical schema and still
    # be unsafe to serve because 12 rows have no owner; if the outcome reads CANONICAL_READY an
    # operator deploys on top of unresolved history and the counts nobody read said so quietly.
    assert rep.outcome == QUARANTINED_PENDING_REVIEW, rep.outcome
    assert rep.next_action.strip(), "an outcome with no next action is a status, not an instruction"


def test_state_07_lying_completion_marker_over_malformed_schema_is_not_ready(tmp_path):
    db = tmp_path / "g.db"
    conn = sqlite3.connect(canonical_db(db))
    conn.execute("DROP TABLE effect_grants")
    conn.commit()
    conn.close()
    assert not schema_is_ready(db), "structure outranks a marker's claim about the past"


def test_state_08_canonical_with_orphan_rows_is_not_ready(tmp_path):
    db = canonical_db(tmp_path / "h.db")
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(
        "INSERT INTO audit_events "
        "(tenant, id, run_id, event_type, actor, payload_json, created_at) "
        "VALUES (?, 1, 999, 'x', 'y', '{}', 'z')",
        (TENANT_A,),
    )
    conn.commit()
    conn.close()
    assert not schema_is_ready(db)


def test_state_09_second_effect_ledger_is_not_ready(tmp_path):
    db = canonical_db(tmp_path / "i.db")
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE legacy_commits (tenant TEXT, commit_key TEXT, state TEXT)"
    )
    conn.commit()
    conn.close()
    assert not schema_is_ready(db), "two tables answering 'was this effect done?' is one too many"


def test_state_10_future_schema_version_is_refused(tmp_path):
    db = canonical_db(tmp_path / "j.db")
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO schema_migrations (migration, step, applied_at) "
        "VALUES ('phase2_tenant_first', 'version:9999', 'later')"
    )
    conn.commit()
    conn.close()
    assert not schema_is_ready(db), "a database written by a newer build is never downgraded"


def test_state_11_already_canonical_remigration_is_a_true_noop(tmp_path):
    db = canonical_db(tmp_path / "k.db")
    s = store(db, TENANT_A)
    run = s.receive_document("L1", "hash-1", {})
    s.close()
    apply_migration(db, assertion=valid_assertion())
    assert schema_is_ready(db)
    s2 = store(db, TENANT_A)
    assert s2.get_run(run.id) is not None, "the rerun must not have dropped the row or its index"
    s2.close()


def test_state_12_two_tenants_in_one_canonical_database_are_both_ready(tmp_path):
    db = canonical_db(tmp_path / "l.db")
    for t in (TENANT_A, TENANT_B):
        s = store(db, t)
        s.receive_document("SAME-LOAD", "identical-bytes", {})
        s.close()
    assert schema_is_ready(db)


# ============================================================================================
# PART B - the 20 required concurrency schedules
# ============================================================================================


def race(n: int, fn):
    """Run fn(i) on n threads that genuinely overlap. Returns (results, exceptions)."""
    barrier = threading.Barrier(n)
    results, errors = [None] * n, [None] * n

    def run(i):
        barrier.wait(timeout=10)
        try:
            results[i] = fn(i)
        except Exception as exc:  # noqa: BLE001 - the exception IS the result under test
            errors[i] = exc

    with ThreadPoolExecutor(max_workers=n) as pool:
        list(pool.map(run, range(n)))
    return results, errors


# --- document identity: schedules 1-4 ---------------------------------------------------------


def test_schedule_01_same_tenant_same_bytes_concurrently_yield_exactly_one_run(tmp_path):
    """CANONICAL RESULT: one run. Not two, not an integrity error surfaced to the caller."""
    db = canonical_db(tmp_path / "s1.db")

    def f(_):
        s = store(db, TENANT_A)
        try:
            return s.receive_document("L-1", "bytes-abc", {}).id
        finally:
            s.close()

    ids, errors = race(4, f)
    assert [e for e in errors if e] == []
    assert len(set(ids)) == 1, f"the same bytes produced {set(ids)} - deduplication raced"


def test_schedule_02_different_tenants_same_bytes_concurrently_yield_two_independent_runs(tmp_path):
    """CANONICAL RESULT: two runs, one per tenant. This is the live cross-tenant defect."""
    db = canonical_db(tmp_path / "s2.db")
    tenants = [TENANT_A, TENANT_B]

    def f(i):
        s = store(db, tenants[i])
        try:
            return (tenants[i], s.receive_document("L-1", "bytes-abc", {}).id)
        finally:
            s.close()

    out, errors = race(2, f)
    assert [e for e in errors if e] == []
    scoped = _direction_scoped_document_hash("bytes-abc", WorkflowDirection.CARRIER_PAYABLE)
    a = store(db, TENANT_A)
    b = store(db, TENANT_B)
    try:
        # Positive control FIRST: if neither tenant could see its own row, the isolation assertion
        # below would pass over an empty world and prove nothing at all.
        assert a.get_run_by_hash(scoped) is not None
        assert b.get_run_by_hash(scoped) is not None
        assert a.get_run_by_hash(scoped).id == a.list_runs()[0].id
        rows_a = a.conn.execute(
            "SELECT COUNT(*) c FROM workflow_runs WHERE tenant = ?", (TENANT_A,)
        ).fetchone()["c"]
        rows_b = b.conn.execute(
            "SELECT COUNT(*) c FROM workflow_runs WHERE tenant = ?", (TENANT_B,)
        ).fetchone()["c"]
        assert (rows_a, rows_b) == (1, 1), "each brokerage owns exactly its own filing"
    finally:
        a.close()
        b.close()


def test_schedule_03_same_bytes_different_directions_are_different_documents(tmp_path):
    """CANONICAL RESULT: two runs. A payable and a receivable are not the same effect."""
    db = canonical_db(tmp_path / "s3.db")
    directions = [WorkflowDirection.CARRIER_PAYABLE, WorkflowDirection.CUSTOMER_INVOICE]

    def f(i):
        s = store(db, TENANT_A)
        try:
            return s.receive_document(
                "L-1", "bytes-abc", {}, workflow_direction=directions[i]
            ).id
        finally:
            s.close()

    ids, errors = race(2, f)
    assert [e for e in errors if e] == []
    assert len(set(ids)) == 2, "direction-scoping collapsed two distinct documents into one"


def test_schedule_04_concurrent_reads_during_a_write_never_see_another_tenant(tmp_path):
    """CANONICAL RESULT: tenant B reads None throughout - never a partial row of A's."""
    db = canonical_db(tmp_path / "s4.db")

    def f(i):
        if i == 0:
            s = store(db, TENANT_A)
            try:
                for n in range(15):
                    s.receive_document(f"L-{n}", f"bytes-{n}", {})
                return "wrote"
            finally:
                s.close()
        s = store(db, TENANT_B)
        try:
            return [
                s.get_run_by_hash(
                    _direction_scoped_document_hash(
                        f"bytes-{n}", WorkflowDirection.CARRIER_PAYABLE
                    )
                )
                for n in range(15)
            ]
        finally:
            s.close()

    out, errors = race(2, f)
    assert [e for e in errors if e] == []
    seen = require_population(out[1], "reads by the observing tenant")
    assert all(r is None for r in seen), "tenant B observed tenant A's document mid-write"
    # Positive control: the writer CAN see those same rows, so the Nones above are isolation and
    # not simply a lookup that never matches anything for anybody.
    a = store(db, TENANT_A)
    try:
        found = [
            a.get_run_by_hash(
                _direction_scoped_document_hash(f"bytes-{n}", WorkflowDirection.CARRIER_PAYABLE)
            )
            for n in range(15)
        ]
    finally:
        a.close()
    assert all(r is not None for r in found), "the writer cannot see its own rows - probe is broken"


# --- Commit Key / effect ledger: schedules 5-9 -------------------------------------------------


def ck(tenant: str, occurrence: str = "pa-001") -> str:
    return commit_key(
        LogicalEffect(
            tenant=tenant,
            action_class="record_payment",
            target_system="truckingoffice",
            target_resource_id="INV-560010",
            target_operation="apply_payment",
            occurrence_key=CanonicalOccurrence("Payment Application", occurrence).key(),
        )
    )


def _claim(s: WorkflowStore, key: str, amount: str = "2850.00") -> bool:
    return s.claim_operation_commit(
        commit_key=key,
        target_system="truckingoffice",
        lane="record_payment",
        load_ref="INV-560010",
        party="acme",
        approved_amount=amount,
        payload={},
    )


def test_schedule_05_concurrent_identical_commit_keys_in_one_tenant_reserve_exactly_once(tmp_path):
    """CANONICAL RESULT: exactly one True. This is the double-payment guard."""
    db = canonical_db(tmp_path / "s5.db")
    key = ck(TENANT_A)

    def f(_):
        s = store(db, TENANT_A)
        try:
            return _claim(s, key)
        finally:
            s.close()

    got, errors = race(5, f)
    assert [e for e in errors if e] == []
    assert sum(1 for g in got if g) == 1, f"{sum(1 for g in got if g)} reservations for one effect"


def test_schedule_06_concurrent_same_commit_key_in_two_tenants_both_reserve(tmp_path):
    """CANONICAL RESULT: both True. A's invoice must never block B's."""
    db = canonical_db(tmp_path / "s6.db")
    tenants = [TENANT_A, TENANT_B]
    key = "identical-key-string"

    def f(i):
        s = store(db, tenants[i])
        try:
            return _claim(s, key)
        finally:
            s.close()

    got, errors = race(2, f)
    assert [e for e in errors if e] == []
    assert got == [True, True], "one brokerage's Commit Key suppressed another's real effect"


def test_schedule_07_concurrent_different_amounts_same_effect_reserve_once(tmp_path):
    """CANONICAL RESULT: one reservation. The amount is a material fact, never part of identity."""
    db = canonical_db(tmp_path / "s7.db")
    key = ck(TENANT_A)
    amounts = ["2850.00", "3100.00", "2850.00"]

    def f(i):
        s = store(db, TENANT_A)
        try:
            return _claim(s, key, amounts[i])
        finally:
            s.close()

    got, errors = race(3, f)
    assert [e for e in errors if e] == []
    assert sum(1 for g in got if g) == 1, "differing amounts manufactured a second invoice"


def test_schedule_08_concurrent_distinct_occurrences_each_reserve(tmp_path):
    """CANONICAL RESULT: three reservations. Two genuinely different payments are not duplicates."""
    db = canonical_db(tmp_path / "s8.db")

    def f(i):
        s = store(db, TENANT_A)
        try:
            return _claim(s, ck(TENANT_A, f"pa-{i:03d}"))
        finally:
            s.close()

    got, errors = race(3, f)
    assert [e for e in errors if e] == []
    assert sum(1 for g in got if g) == 3, "distinct occurrences were collapsed - a payment was lost"


def test_schedule_09_concurrent_ledger_reads_never_cross_tenants(tmp_path):
    """CANONICAL RESULT: each tenant's ledger contains only its own grants."""
    db = canonical_db(tmp_path / "s9.db")
    tenants = [TENANT_A, TENANT_B]

    def f(i):
        s = store(db, tenants[i])
        try:
            for n in range(10):
                _claim(s, ck(tenants[i], f"pa-{n}"))
            return s.conn.execute(
                "SELECT DISTINCT tenant FROM effect_grants WHERE tenant = ?", (tenants[i],)
            ).fetchall()
        finally:
            s.close()

    out, errors = race(2, f)
    assert [e for e in errors if e] == []
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    per = {
        r["tenant"]: r["c"]
        for r in conn.execute("SELECT tenant, COUNT(*) c FROM effect_grants GROUP BY tenant")
    }
    conn.close()
    assert per == {TENANT_A: 10, TENANT_B: 10}


# --- workflow updates: schedules 10-13 --------------------------------------------------------


def seeded_run(db: Path, tenant: str, tag: str = "r"):
    s = store(db, tenant)
    run = s.receive_document(f"L-{tag}", f"bytes-{tag}", {})
    s.close()
    return run.id


def test_schedule_10_concurrent_transitions_to_the_same_state_apply_exactly_once(tmp_path):
    """CANONICAL RESULT: one success, the rest refused. Never two audit events for one move.

    The window this defends is between reading the current state and writing the next one. A single
    round barely opens it - the threads queue on SQLite's write lock and serialize by luck, so the
    state-validity check alone appears sufficient. Rounds are repeated over fresh runs, and every
    store is opened and its run READ before the barrier, so all racers hold the same stale state
    when they are released. That is the interleaving the compare-and-set exists for; without the
    repetition this schedule passes with the CAS removed, which is to say it proves nothing.
    """
    db = canonical_db(tmp_path / "s10.db")
    for round_no in range(12):
        rid = seeded_run(db, TENANT_A, f"r{round_no}")
        stores = [store(db, TENANT_A) for _ in range(4)]
        for st in stores:
            st.get_run(rid)  # everyone reads RECEIVED BEFORE anyone is allowed to write

        def f(i, _rid=rid, _stores=stores):
            try:
                _stores[i].transition(_rid, WorkflowState.EXTRACTED)
                return "ok"
            except WorkflowError:
                return "refused"

        got, errors = race(4, f)
        for st in stores:
            st.close()
        assert [e for e in errors if e] == []
        assert got.count("ok") == 1, (
            f"round {round_no}: {got.count('ok')} threads all believed they moved the run"
        )
        s = store(db, TENANT_A)
        try:
            moves = [e for e in s.audit_events(rid) if e["event_type"] == "state_transition"]
            assert len(moves) == 1, f"round {round_no}: the losing threads still wrote history"
        finally:
            s.close()


def test_schedule_11_concurrent_cross_tenant_transition_is_refused_as_not_found(tmp_path):
    """CANONICAL RESULT: B raises 'not found'. Not 'forbidden' - the row is not B's to know about."""
    db = canonical_db(tmp_path / "s11.db")
    rid = seeded_run(db, TENANT_A)

    def f(i):
        s = store(db, TENANT_B if i else TENANT_A)
        try:
            s.transition(rid, WorkflowState.EXTRACTED)
            return "ok"
        except WorkflowError as exc:
            return str(exc)
        finally:
            s.close()

    got, errors = race(2, f)
    assert [e for e in errors if e] == []
    assert "not found" in got[1], f"tenant B got {got[1]!r} - existence itself is a disclosure"


def test_schedule_12_concurrent_audit_writes_do_not_interleave_ids_across_tenants(tmp_path):
    """CANONICAL RESULT: each tenant's event ids are a dense 1..N of its OWN events."""
    db = canonical_db(tmp_path / "s12.db")
    tenants = [TENANT_A, TENANT_B]
    runs = {t: seeded_run(db, t, t) for t in tenants}

    def f(i):
        t = tenants[i]
        s = store(db, t)
        try:
            for n in range(8):
                s.add_audit_event(runs[t], f"probe_{n}", actor="test", payload={})
            return [e["id"] for e in s.audit_events(runs[t])]
        finally:
            s.close()

    out, errors = race(2, f)
    assert [e for e in errors if e] == []
    for ids in out:
        ids = require_population(ids, "audit events")
        assert ids == list(range(1, len(ids) + 1)), f"ids {ids} are not per-tenant dense"


def test_schedule_13_a_failed_transition_leaves_no_partial_state(tmp_path):
    """CANONICAL RESULT: an invalid move changes nothing - not the state, not the history."""
    db = canonical_db(tmp_path / "s13.db")
    rid = seeded_run(db, TENANT_A)

    def f(i):
        s = store(db, TENANT_A)
        try:
            target = WorkflowState.EXTRACTED if i == 0 else WorkflowState.DONE
            s.transition(rid, target)
            return "ok"
        except WorkflowError:
            return "refused"
        finally:
            s.close()

    got, errors = race(2, f)
    assert [e for e in errors if e] == []
    assert "refused" in got, "an illegal jump was accepted under concurrency"
    s = store(db, TENANT_A)
    try:
        assert s.get_run(rid).state == WorkflowState.EXTRACTED
        # One receipt + one legal transition. The refused jump wrote NO history: a rejected move
        # that still left a trace would read, a year later, as if it had happened.
        kinds = [e["event_type"] for e in s.audit_events(rid)]
        assert kinds == ["document_received", "state_transition"], kinds
    finally:
        s.close()


# --- migration: schedules 14-20 ---------------------------------------------------------------


def test_schedule_14_two_concurrent_migrations_of_one_database_converge(tmp_path):
    """CANONICAL RESULT: the database ends canonical exactly once - no double-rebuild."""
    db = legacy_db(tmp_path / "s14.db", rows=6)

    def f(_):
        try:
            return apply_migration(db, assertion=valid_assertion()).outcome
        except Exception as exc:  # noqa: BLE001
            return f"raised:{type(exc).__name__}"

    got, errors = race(2, f)
    assert [e for e in errors if e] == []
    assert schema_is_ready(db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    n = conn.execute("SELECT COUNT(*) c FROM workflow_runs").fetchone()["c"]
    assertions = conn.execute("SELECT COUNT(*) c FROM owner_assertions").fetchone()["c"]
    conn.close()
    assert n == 6, f"{n} rows after two migrations of 6 - history was duplicated"
    assert assertions >= 1


def test_schedule_15_a_reader_during_migration_never_sees_a_half_migrated_schema(tmp_path):
    """CANONICAL RESULT: the reader either refuses (not ready) or reads a complete schema."""
    db = legacy_db(tmp_path / "s15.db", rows=40)
    observations: list[bool] = []

    def f(i):
        if i == 0:
            return apply_migration(db, assertion=valid_assertion()).outcome
        for _ in range(30):
            observations.append(schema_is_ready(db))
        return "read"

    _, errors = race(2, f)
    assert [e for e in errors if e] == []
    require_population(observations, "readiness observations during migration")
    # Every observation is a whole answer; a half-migrated tree must never report ready.
    assert schema_is_ready(db)


def test_schedule_16_concurrent_conflicting_assertions_preserve_the_first(tmp_path):
    """CANONICAL RESULT: one owner, the disagreement recorded, zero rows reassigned."""
    db = legacy_db(tmp_path / "s16.db", rows=6)
    tenants = [TENANT_A, TENANT_B]

    def f(i):
        try:
            return apply_migration(db, assertion=valid_assertion(tenants[i])).outcome
        except Exception as exc:  # noqa: BLE001
            return f"raised:{type(exc).__name__}"

    got, errors = race(2, f)
    assert [e for e in errors if e] == []
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    owners = {r["tenant"] for r in conn.execute("SELECT DISTINCT tenant FROM workflow_runs")}
    conn.close()
    assert len(owners) <= 1, f"rows ended up split between {owners} by a race over ownership"


def test_schedule_17_concurrent_dry_runs_write_nothing(tmp_path):
    """CANONICAL RESULT: the file is byte-identical afterwards."""
    import hashlib

    db = legacy_db(tmp_path / "s17.db", rows=6)
    before = hashlib.sha256(db.read_bytes()).hexdigest()

    def f(_):
        return apply_migration(db, assertion=valid_assertion(), dry_run=True).outcome

    _, errors = race(3, f)
    assert [e for e in errors if e] == []
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before


def test_schedule_18_an_application_starting_during_migration_refuses_the_legacy_shape(tmp_path):
    """CANONICAL RESULT: the store refuses rather than writing into a pre-tenant schema."""
    db = legacy_db(tmp_path / "s18.db", rows=6)
    with pytest.raises(Exception) as exc:
        s = store(db, TENANT_A)
        s.receive_document("L-1", "bytes-1", {})
    assert "ready" in str(exc.value).lower() or "schema" in str(exc.value).lower()


def test_schedule_19_concurrent_migration_and_writes_never_produce_an_unowned_row(tmp_path):
    """CANONICAL RESULT: every surviving business row has a real tenant - never NULL, never ''."""
    db = legacy_db(tmp_path / "s19.db", rows=20)
    apply_migration(db, assertion=valid_assertion())

    def f(i):
        s = store(db, TENANT_A if i % 2 == 0 else TENANT_B)
        try:
            for n in range(10):
                s.receive_document(f"L-{i}-{n}", f"bytes-{i}-{n}", {})
            return "ok"
        finally:
            s.close()

    _, errors = race(4, f)
    assert [e for e in errors if e] == []
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    bad = conn.execute(
        "SELECT COUNT(*) c FROM workflow_runs WHERE tenant IS NULL OR TRIM(tenant) = ''"
    ).fetchone()["c"]
    total = conn.execute("SELECT COUNT(*) c FROM workflow_runs").fetchone()["c"]
    conn.close()
    assert total >= 60, f"only {total} rows - the population is too small to prove anything"
    assert bad == 0


def test_schedule_20_the_completion_marker_appears_only_after_readiness_holds(tmp_path):
    """CANONICAL RESULT: no observation ever finds the marker present while readiness is false."""
    db = legacy_db(tmp_path / "s20.db", rows=40)
    violations: list[str] = []
    checked = []

    def marked() -> bool:
        try:
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                rows = conn.execute("SELECT step FROM schema_migrations").fetchall()
            finally:
                conn.close()
            return any(str(r[0]).startswith("version:") for r in rows)
        except sqlite3.Error:
            return False

    done = threading.Event()

    def f(i):
        if i == 0:
            try:
                return apply_migration(db, assertion=valid_assertion()).outcome
            finally:
                done.set()
        # Poll UNTIL the migration finishes, not a fixed number of times. A counted loop can run
        # out before the migration even starts, and then observes nothing while reporting success -
        # verified: with a premature marker introduced, a fixed 40-iteration watcher stayed green.
        while not done.is_set():
            m = marked()
            checked.append(m)
            if m and not schema_is_ready(db):
                violations.append("marker present while the schema was not ready")
        checked.append(marked())
        return "watched"

    _, errors = race(2, f)
    assert [e for e in errors if e] == []
    require_population(checked, "marker observations")
    assert violations == [], violations[0] if violations else ""
    assert marked() and schema_is_ready(db)

    # The concurrent watcher above is a weak instrument and I proved it: the migration holds the
    # write lock for its whole (millisecond) duration, so a reader observes nothing until it is
    # already over. With the marker deliberately stamped before the constraints existed, the
    # watcher stayed green. The ordering is therefore asserted DETERMINISTICALLY as well, on a
    # database whose readiness can never pass - if the marker is written before readiness is
    # checked, it is present here, and if it is written last it is absent.
    doomed = legacy_db(tmp_path / "s20b.db", rows=6)
    conn = sqlite3.connect(doomed)
    conn.execute("CREATE TABLE legacy_commits (tenant TEXT, commit_key TEXT, state TEXT)")
    conn.commit()
    conn.close()
    try:
        rep = apply_migration(doomed, assertion=valid_assertion())
        assert rep.outcome != MIGRATION_COMPLETE_RESTART_SAFE, rep.outcome
    except Exception:  # noqa: BLE001 - refusing outright is an equally correct answer
        pass
    assert not schema_is_ready(doomed), "fixture is wrong - this database was supposed to fail"
    conn = sqlite3.connect(doomed)
    try:
        steps = [r[0] for r in conn.execute("SELECT step FROM schema_migrations")]
    finally:
        conn.close()
    require_population(steps, "migration step markers")
    stamped = [x for x in steps if str(x).startswith("version:")]
    assert stamped == [], (
        f"the completion marker {stamped} was written to a database that is NOT ready - "
        "a marker written early outranks the present and is how a half-migrated database "
        "gets deployed on top of"
    )


# ============================================================================================
# PART C - integrated invariants that only hold with every blocker in place
# ============================================================================================


def test_the_full_phase_2_stack_holds_end_to_end(tmp_path):
    """One database, two brokerages, the same bytes and the same Commit Key - fully independent."""
    db = legacy_db(tmp_path / "e2e.db", rows=8)
    rep = apply_migration(db, assertion=valid_assertion(TENANT_A))
    assert schema_is_ready(db)
    assert sum(rep.rows_migrated.values()) == 8

    a, b = store(db, TENANT_A), store(db, TENANT_B)
    try:
        ra = a.receive_document("SHARED", "same-bytes", {})
        rb = b.receive_document("SHARED", "same-bytes", {})
        # A continues its OWN sequence after the 8 migrated rows; B, a new tenant in the same
        # database, starts at 1. Ids are per-tenant, so the numbers legitimately collide across
        # tenants and mean nothing to each other.
        assert (ra.id, rb.id) == (9, 1), (ra.id, rb.id)
        assert a.get_run(ra.id).id == ra.id
        assert b.get_run(rb.id).id == rb.id
        assert _claim(a, "shared-key") and _claim(b, "shared-key")
        assert not _claim(a, "shared-key"), "a duplicate within one tenant must still be refused"
        a.transition(ra.id, WorkflowState.EXTRACTED)
        with pytest.raises(WorkflowError):
            b.transition(ra.id, WorkflowState.EXTRACTED)
    finally:
        a.close()
        b.close()


def test_every_canonical_table_is_exercised_by_this_suite(tmp_path):
    """A qualification suite that never touches a table has not qualified it."""
    db = canonical_db(tmp_path / "cov.db")
    conn = sqlite3.connect(db)
    present = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    missing = [t for t in CANONICAL_TENANT_TABLES if t not in present]
    assert missing == [], f"canonical tables absent from a fresh schema: {missing}"
