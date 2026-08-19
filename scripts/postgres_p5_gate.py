#!/usr/bin/env python3
"""The PostgreSQL gate for the P5 durable surface — the contract's "PostgreSQL-backed suite run".

    **PostgreSQL is the production transactional store.** ... The persistence layer keeps a
    single schema/migration discipline across both. — ADR-016 §1
    P5's evidence: [G2 gate record, the GC-1 digest comparison, **a PostgreSQL-backed suite run**]
    P5's hostile cases include: **SQLite-vs-PostgreSQL behavioral divergence**,
    **migration replayed twice**

WHY THIS IS A GATE SCRIPT AND NOT A PYTEST MODULE

The canonical suite must be reproducible in a fresh clone with declared dependencies and nothing
else. Making every clone require a running database server would change what "reproducible" means
for the whole repository, and a pytest node that skipped when no server answered would be worse: a
skip is a test that did not run, and a test that did not run proves nothing. A permanently-expected
skip on the one requirement the P5 contract names by name would be precisely the silent pass this
repository keeps finding in itself.

So this is an explicitly invoked gate that EXECUTES against a
real PostgreSQL and writes a receipt. Either it ran and the receipt says what it proved, or it did
not run and there is no receipt — no third state, and nothing green by default.

    python3 scripts/postgres_p5_gate.py --dsn "dbname=neyma_test"
    python3 scripts/postgres_p5_gate.py --dsn "..." --receipt docs/implementation/POSTGRES-P5-GATE.json

WHAT IT PROVES, AND WHY EACH ONE IS THE INTERESTING PART

1. **The migration applies** to an empty database and reaches readiness.
2. **Replaying it is a genuine NO-OP** — zero steps performed, not "it worked again". That is the
   `migration replayed twice` hostile case, and an idempotent-looking migration that silently
   re-creates objects would pass a weaker check.
3. **Tenant-first keys are preserved** — the P5 security requirement, checked as primary-key COLUMN
   ORDER on the live PostgreSQL catalog rather than inferred from the DDL text.
4. ### **ALL EIGHT INVARIANTS REFUSE.** Creating five tables in another database is typing. What
   makes the transport trustworthy is that its envelope is immutable BY TRIGGER, its history is
   append-only BY TRIGGER, and a strict-ordering family cannot have two producer transitions claim
   one version. A port that dropped those would list identically in `information_schema` and be a
   different system — so each is attacked, and a refusal is the pass.
5. **A positive control**: delivery bookkeeping MAY still move. Without it, a trigger that refused
   *everything* would score eight out of eight.
6. **SQLite and PostgreSQL agree** on tables, columns and key order — the
   `SQLite-vs-PostgreSQL behavioral divergence` hostile case, compared live-catalog against
   live-catalog rather than text against text.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

NOW = "2026-05-01T09:00:00.000Z"


def _sqlite_shape() -> dict[str, list[str]]:
    """The P5 surface as a FRESH canonical SQLite database actually has it."""
    from freight_recon.migrations.postgres_p5 import P5_SURFACE
    from freight_recon.workflow import WorkflowStore

    with tempfile.TemporaryDirectory() as directory:
        # ### GENERATED, NOT A LITERAL. `test_no_production_site_hardcodes_any_string_tenant`
        # is right to refuse one here: "a hardcoded tenant is the same defect as a default,
        # spelled once per file." This probe does not care WHICH tenant it uses — only that it is
        # a valid non-sentinel one — and a generated name additionally cannot be mistaken for a
        # real brokerage if it ever escapes into a log.
        probe_tenant = "shape-probe-" + uuid.uuid4().hex[:12]
        store = WorkflowStore(Path(directory) / "shape.db", tenant=probe_tenant)
        shape: dict[str, list[str]] = {}
        for table in P5_SURFACE:
            info = store.conn.execute(f"PRAGMA table_info({table})").fetchall()
            shape[table] = [row[1] for row in info]
            shape[f"{table}::pk"] = [row[1] for row in sorted(
                (r for r in info if r[5]), key=lambda r: r[5])]
            # ### CONSTRAINTS AND NULLABILITY TOO, AND INSIDE THE LOOP. Comparing column NAMES
            # only, a PostgreSQL port could drop a UNIQUE constraint or neuter a CHECK and still
            # be reported "equivalent" — mutation-proven: removing
            # `UNIQUE (tenant, idempotency_identity)` left the gate PASSING while silently
            # removing the outbox's idempotency invariant on the production store.
            # (The first version of these four lines sat OUTSIDE this loop, so they described only
            # the last table — which the equivalence check itself caught, as a pile of `None`s.)
            shape[f"{table}::notnull"] = sorted(row[1] for row in info if row[3])
            ddl = (store.conn.execute(
                "SELECT sql FROM sqlite_master WHERE name = ?", (table,)).fetchone()
                or [""])[0] or ""
            shape[f"{table}::unique"] = sorted(
                _normalise_tuple(m) for m in re.findall(r"UNIQUE\s*\(([^)]*)\)", ddl, re.I))
            shape[f"{table}::check"] = sorted(
                _normalise_check(m)
                for m in re.findall(r"CHECK\s*\((.*?)\)\s*(?:,|\n|$)", ddl, re.I))
        store.close()
        return shape


def _postgres_shape(conn) -> dict[str, list[str]]:
    from freight_recon.migrations.postgres_p5 import P5_SURFACE, primary_key_columns

    shape: dict[str, list[str]] = {}
    for table in P5_SURFACE:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                " WHERE table_schema = current_schema() AND table_name = %s "
                " ORDER BY ordinal_position", (table,))
            shape[table] = [r[0] for r in cur.fetchall()]
        shape[f"{table}::pk"] = primary_key_columns(conn, table)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                " WHERE table_schema = current_schema() AND table_name = %s "
                "   AND is_nullable = 'NO' ORDER BY column_name", (table,))
            shape[f"{table}::notnull"] = [r[0] for r in cur.fetchall()]
            cur.execute(
                "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c "
                " WHERE c.conrelid = %s::regclass AND c.contype = 'u'", (table,))
            shape[f"{table}::unique"] = sorted(
                _normalise_tuple(re.sub(r"^UNIQUE\s*\(|\)$", "", r[0]).strip())
                for r in cur.fetchall())
            cur.execute(
                "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c "
                " WHERE c.conrelid = %s::regclass AND c.contype = 'c'", (table,))
            shape[f"{table}::check"] = sorted(
                _normalise_check(re.sub(r"^CHECK\s*", "", r[0]).strip()) for r in cur.fetchall())
    return shape


def _normalise_tuple(text: str) -> str:
    return ",".join(sorted(part.strip().strip('"') for part in text.split(",") if part.strip()))


def _normalise_check(text: str) -> str:
    """A CHECK expressed in two dialects renders differently; compare its VOCABULARY.

    SQLite writes `state IN ('A','B')` and PostgreSQL renders `((state)::text = ANY (...))`. Rather
    than pretend those strings match, the comparison is over the identifiers and literals the
    constraint mentions — which is what changes when a constraint is weakened, and is what the
    mutation test removed.
    """
    tokens = re.findall(r"'[^']*'|[A-Za-z_][A-Za-z0-9_]*", text or "")
    # Dialect rendering noise: PostgreSQL writes `((state)::text = ANY (ARRAY[...]))` where SQLite
    # writes `state IN (...)`. What must match is the VOCABULARY the constraint governs — the
    # columns and permitted values — because that is what changes when a constraint is weakened.
    drop = {"text", "ANY", "ARRAY", "character", "varying", "OR", "AND", "NOT", "IS", "NULL", "IN"}
    return ",".join(sorted({tok.strip("'").upper() for tok in tokens
                            if tok.strip('"') not in drop}))


def _seed(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO event_outbox (tenant,event_id,event_name,event_version,"
            "envelope_schema_version,aggregate_type,aggregate_id,aggregate_version,"
            "producer_transition_id,correlation_id,idempotency_identity,occurred_at,recorded_at,"
            "envelope_json,envelope_digest,sequence) VALUES "
            "('t-a','e1','PipelineStarted',1,1,'pipeline_instance','pi-1',1,'PL-1','c1','id1',"
            "%s,%s,'{}','d1',1) ON CONFLICT DO NOTHING", (NOW, NOW))
        cur.execute(
            "INSERT INTO event_inbox (tenant,consumer_id,event_id,event_name,aggregate_type,"
            "aggregate_id,aggregate_version,outcome,consumed_at,envelope_digest) VALUES "
            "('t-a','c-1','e1','PipelineStarted','pipeline_instance','pi-1',1,'APPLIED',%s,'d1') "
            "ON CONFLICT DO NOTHING", (NOW,))
        cur.execute(
            "INSERT INTO durable_timers (tenant,timer_id,aggregate_type,aggregate_id,timer_kind,"
            "fire_at,scheduled_at) VALUES ('t-a','tm1','expectation','ex-1','deadline',%s,%s) "
            "ON CONFLICT DO NOTHING", (NOW, NOW))
    conn.commit()


# (label, sql, must_refuse). A refusal is the pass for the eight; the positive control must ACCEPT.
ATTACKS: list[tuple[str, str, bool]] = [
    ("outbox envelope immutable",
     "UPDATE event_outbox SET envelope_json='{\"tampered\":1}' WHERE event_id='e1'", True),
    ("outbox no delete", "DELETE FROM event_outbox WHERE event_id='e1'", True),
    ("outbox strict version owner",
     "INSERT INTO event_outbox (tenant,event_id,event_name,event_version,"
     "envelope_schema_version,aggregate_type,aggregate_id,aggregate_version,"
     "producer_transition_id,correlation_id,idempotency_identity,occurred_at,recorded_at,"
     "envelope_json,envelope_digest,sequence) VALUES "
     f"('t-a','e2','CheckpointPassed',1,1,'pipeline_instance','pi-1',1,'PL-8','c1','id2',"
     f"'{NOW}','{NOW}','{{}}','d2',2)", True),
    ("inbox append-only update",
     "UPDATE event_inbox SET outcome='TAMPERED' WHERE event_id='e1'", True),
    ("inbox append-only delete", "DELETE FROM event_inbox WHERE event_id='e1'", True),
    ("timer schedule immutable",
     "UPDATE durable_timers SET fire_at='2099-01-01T00:00:00.000Z' WHERE timer_id='tm1'", True),
    ("timer no delete", "DELETE FROM durable_timers WHERE timer_id='tm1'", True),
    # ### THE POSITIVE CONTROLS. Without them a trigger that refused EVERYTHING would score full
    # marks, and "the invariants hold" would be indistinguishable from "the table is read-only".
    # ONE PER GUARDED TABLE: with only the outbox control, a fully read-only `durable_timers`
    # scored 9/9 — the timer immutability trigger is precisely the one that MUST still permit
    # state, fired_at, leased_by and fire_attempts to move.
    ("POSITIVE CONTROL: outbox delivery bookkeeping may move",
     "UPDATE event_outbox SET publish_attempts = publish_attempts + 1 WHERE event_id='e1'", False),
    ("POSITIVE CONTROL: timer delivery bookkeeping may move",
     "UPDATE durable_timers SET fire_attempts = fire_attempts + 1 WHERE timer_id='tm1'", False),
]


def _runtime_probes(dsn: str) -> tuple[dict[str, str], list[str]]:
    """### THE ACTUAL RUNTIME, ON POSTGRESQL — not the schema, and not a mock.

    P5's capability is "durable event execution (outbox/inbox/replay) **ON** production-grade
    persistence". A green schema gate proves the tables and their invariants; it says nothing about
    whether `TransactionalOutbox`, `DedupInbox` and `DurableTimers` actually behave. These probes
    drive the REAL classes through a real connection, and each one targets a difference PostgreSQL
    genuinely has from SQLite rather than a difference that sounded plausible.
    """
    import threading

    import psycopg

    from freight_recon.event_inbox import ConsumeOutcome, DedupInbox
    from freight_recon.event_outbox import (
        DuplicateEmission,
        OutboxRelay,
        StrictOrderViolation,
        TransactionalOutbox,
        transactional_emit,
    )
    from freight_recon.event_timers import DurableTimers, TimerRelay
    from freight_recon.persistence import connect_postgres

    sys.path.insert(0, str(ROOT / "eval" / "tests"))
    from phase5_kit import Clock, make_canonical_envelope       # noqa: E402

    from datetime import timedelta                              # noqa: E402

    T, OTHER = "brokerage-northwind", "brokerage-cascade"
    results: dict[str, str] = {}
    findings: list[str] = []

    def record(label: str, ok: bool, detail: str = "") -> None:
        results[label] = "PASS" if ok else f"FAIL{(': ' + detail) if detail else ''}"
        if not ok:
            findings.append(f"{label}: {detail}")

    conn, clock = connect_postgres(dsn, tenant=T), Clock()

    # --- atomicity, and its negative ----------------------------------------------------------
    env = make_canonical_envelope("PipelineStarted", tenant=T, aggregate_id="pi-1", seed="rt-1")
    with transactional_emit(conn, tenant=T, clock=clock) as session:
        session.emit(env)
    box = TransactionalOutbox(conn, tenant=T, clock=clock)
    record("atomic emit persists", len(box.pending()) == 1)

    doomed = make_canonical_envelope("PipelineStarted", tenant=T, aggregate_id="pi-2", seed="rt-2")
    try:
        with transactional_emit(conn, tenant=T, clock=clock) as session:
            session.emit(doomed)
            raise RuntimeError("the transition failed after emitting")
    except RuntimeError:
        pass
    record("rollback leaves NO event", len(box.pending()) == 1,
           f"{len(box.pending())} pending after a rolled-back emit")

    # --- uniqueness: a second emission of one identity is refused ------------------------------
    try:
        with transactional_emit(conn, tenant=T, clock=clock) as session:
            session.emit(env)
        record("duplicate emission refused", False, "a second emit of one event_id was accepted")
    except DuplicateEmission:
        record("duplicate emission refused", True)

    # --- the strict-ordering TRIGGER, reached through the runtime's classifier -----------------
    # SQLite reports a trigger RAISE(ABORT) and a UNIQUE violation through ONE exception type, and
    # the outbox classifies on the message. PostgreSQL splits them across two types — so if the
    # persistence layer did not unify them, this would surface as DuplicateEmission (a duplicate
    # that does not exist) instead of StrictOrderViolation.
    clash = make_canonical_envelope("CheckpointPassed", tenant=T, aggregate_id="pi-1",
                                    aggregate_version=1, seed="rt-clash")
    try:
        with transactional_emit(conn, tenant=T, clock=clock) as session:
            session.emit(clash)
        record("strict-order trigger classified correctly", False, "no refusal at all")
    except StrictOrderViolation:
        record("strict-order trigger classified correctly", True)
    except DuplicateEmission as exc:
        record("strict-order trigger classified correctly", False,
               f"a trigger refusal was misreported as a duplicate: {exc}")

    # --- relay: claim, publish, bookkeeping ----------------------------------------------------
    sink: list = []
    published = OutboxRelay(conn, tenant=T, publish=sink.append, relay_id="r1",
                            clock=clock).run_once()
    record("relay publishes and marks", len(published.published) == 1
           and box.count_unpublished() == 0)

    # --- DUPLICATE WORKERS: two relays must not both deliver one event -------------------------
    second = make_canonical_envelope("PipelineStarted", tenant=T, aggregate_id="pi-3", seed="rt-3")
    with transactional_emit(conn, tenant=T, clock=clock) as session:
        session.emit(second)
    a, b = [], []
    ra = OutboxRelay(conn, tenant=T, publish=a.append, relay_id="relay-a", clock=clock).run_once()
    rb = OutboxRelay(conn, tenant=T, publish=b.append, relay_id="relay-b", clock=clock).run_once()
    record("duplicate relay workers deliver once", len(a) + len(b) == 1,
           f"relay-a delivered {len(a)}, relay-b delivered {len(b)}")

    # --- inbox dedup / redelivery --------------------------------------------------------------
    applied: list = []
    inbox = DedupInbox(conn, tenant=T, consumer_id="c-1", clock=clock)
    first = inbox.consume(sink[0], applied.append)
    again = inbox.consume(sink[0], applied.append)
    record("inbox applies once, redelivery is a no-op",
           first.outcome is ConsumeOutcome.APPLIED
           and again.outcome is ConsumeOutcome.DUPLICATE_NOOP and len(applied) == 1,
           f"{first.outcome}/{again.outcome}, handler ran {len(applied)}x")

    # --- CONCURRENT SEQUENCE ALLOCATION: the BEGIN IMMEDIATE difference ------------------------
    # ### THE PROBE THAT JUSTIFIES THE ADVISORY LOCK. SQLite serialises writers at BEGIN; under
    # PostgreSQL MVCC two emitters would both read MAX(sequence) and both commit the same value,
    # silently. Two real threads, two real connections, one tenant.
    errors: list[str] = []

    def emit_concurrently(index: int) -> None:
        try:
            worker = connect_postgres(dsn, tenant=T)
            envelope = make_canonical_envelope(
                "PipelineStarted", tenant=T, aggregate_id=f"pi-conc-{index}",
                seed=f"rt-conc-{index}")
            with transactional_emit(worker, tenant=T, clock=clock) as session:
                session.emit(envelope)
            worker.close()
        except Exception as exc:                                  # noqa: BLE001
            errors.append(f"{type(exc).__name__}: {exc}")

    threads = [threading.Thread(target=emit_concurrently, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    with psycopg.connect(dsn) as check, check.cursor() as cur:
        cur.execute("SELECT sequence, COUNT(*) FROM event_outbox WHERE tenant = %s "
                    " GROUP BY sequence HAVING COUNT(*) > 1", (T,))
        collisions = cur.fetchall()
    record("concurrent emitters allocate distinct sequences", not collisions and not errors,
           f"collisions={collisions} errors={errors}")

    # --- durable timers: schedule, restart, fire, terminal -------------------------------------
    timers = DurableTimers(conn, tenant=T, clock=clock)
    conn.execute("BEGIN IMMEDIATE")
    timers.schedule(timer_id="tm-1", aggregate_type="expectation", aggregate_id="ex-1",
                    timer_kind="expectation_deadline", fire_at=clock() + timedelta(hours=2))
    conn.commit()
    record("timer not due before its deadline", len(timers.due()) == 0)
    conn.close()

    # CONNECTION LIFECYCLE + RESTART RECOVERY: a brand new connection, after the old one closed.
    restarted = connect_postgres(dsn, tenant=T)
    clock.advance(hours=3)
    after = DurableTimers(restarted, tenant=T, clock=clock)
    record("timer survives a restart", after.scheduled_count() == 1 and len(after.due()) == 1)
    fired: list = []
    fired_result = TimerRelay(restarted, tenant=T, handler=fired.append, relay_id="tr",
                              clock=clock).run_once()
    record("timer fires after restart", fired_result.fired == ("tm-1",))
    record("a fired timer does not fire again",
           TimerRelay(restarted, tenant=T, handler=fired.append, relay_id="tr",
                      clock=clock).run_once().fired == ())

    # --- B-1: an unarmed connection must REFUSE, not corrupt ----------------------------------
    # The advisory lock is the whole serialisation guarantee. A connection opened without a tenant
    # cannot take it, and proceeding would hand the caller the transaction they asked for and
    # silently not the exclusion. Probed because the corruption it prevents is invisible.
    from freight_recon.persistence import PersistenceError, PostgresConnection

    raw = psycopg.connect(dsn, autocommit=True)
    try:
        PostgresConnection(raw).execute("BEGIN IMMEDIATE")
        record("an unarmed connection refuses BEGIN IMMEDIATE", False,
               "it proceeded without the advisory lock")
    except PersistenceError:
        record("an unarmed connection refuses BEGIN IMMEDIATE", True)
    finally:
        raw.close()

    # --- CONCURRENT relays, on TWO REAL CONNECTIONS -------------------------------------------
    # Running two relays one after the other proves nothing about leasing: the second finds the row
    # already PUBLISHED, so the probe passes with the lease deleted. This claims on connection A,
    # then runs relay B on a SEPARATE CONNECTION while A holds the lease mid-delivery.
    #
    # This is safe from deadlock for a specific reason: `run_once` commits the claim BEFORE it
    # publishes ("holding a database write lock across a call that leaves the process is how a slow
    # sink becomes a stalled database"), so A holds no advisory lock while B begins.
    OutboxRelay(restarted, tenant=T, publish=lambda e: None, relay_id="drain",
                clock=clock).drain()                      # a backlog would make the counts lie

    contended = make_canonical_envelope("PipelineStarted", tenant=T, aggregate_id="pi-lease",
                                        seed="rt-lease")
    with transactional_emit(restarted, tenant=T, clock=clock) as session:
        session.emit(contended)

    delivered: list = []
    interloper: list = []
    second_conn = connect_postgres(dsn, tenant=T)

    def publish_then_let_another_connection_try(envelope) -> None:
        delivered.append(envelope)
        OutboxRelay(second_conn, tenant=T, publish=interloper.append, relay_id="relay-b",
                    clock=clock).run_once()

    OutboxRelay(restarted, tenant=T, publish=publish_then_let_another_connection_try,
                relay_id="relay-a", clock=clock).run_once()
    record("a leased outbox row cannot be claimed by a second CONNECTION",
           len(delivered) == 1 and len(interloper) == 0,
           f"relay-a delivered {len(delivered)}, relay-b delivered {len(interloper)}")

    # The positive control: with the lease lapsed, the second connection MUST be able to claim.
    # Without this, a relay that never claims anything would score full marks above.
    with transactional_emit(restarted, tenant=T, clock=clock) as session:
        session.emit(make_canonical_envelope("PipelineStarted", tenant=T,
                                             aggregate_id="pi-lapse", seed="rt-lapse"))
    lapsed: list = []

    def die_holding_the_lease(envelope) -> None:
        raise RuntimeError("relay-a was killed mid-delivery")

    OutboxRelay(restarted, tenant=T, publish=die_holding_the_lease, relay_id="relay-a",
                clock=clock).run_once()
    clock.advance(minutes=10)
    OutboxRelay(second_conn, tenant=T, publish=lapsed.append, relay_id="relay-b",
                clock=clock).run_once()
    record("a LAPSED lease is reclaimable by another connection", len(lapsed) == 1,
           f"the second connection recovered {len(lapsed)} rows; a stranded row never redelivers")
    second_conn.close()

    # --- M-4: a caught integrity error must not poison the transaction ------------------------
    from freight_recon.event_timers import DuplicateTimer

    probe_timers = DurableTimers(restarted, tenant=T, clock=clock)
    restarted.execute("BEGIN IMMEDIATE")
    probe_timers.schedule(timer_id="tm-dup", aggregate_type="expectation", aggregate_id="ex-d",
                          timer_kind="k", fire_at=clock())
    restarted.commit()
    restarted.execute("BEGIN IMMEDIATE")
    try:
        probe_timers.schedule(timer_id="tm-dup", aggregate_type="expectation",
                              aggregate_id="ex-d", timer_kind="k", fire_at=clock())
    except DuplicateTimer:
        pass
    try:
        probe_timers.schedule(timer_id="tm-after", aggregate_type="expectation",
                              aggregate_id="ex-d", timer_kind="k", fire_at=clock())
        restarted.commit()
        record("a caught integrity error does not poison the transaction", True)
    except Exception as exc:                                      # noqa: BLE001
        restarted.rollback()
        record("a caught integrity error does not poison the transaction", False,
               f"{type(exc).__name__}: {exc}")

    # --- tenant isolation, on the production backend -------------------------------------------
    record("tenant isolation holds",
           len(TransactionalOutbox(restarted, tenant=OTHER, clock=clock).pending()) == 0
           and DurableTimers(restarted, tenant=OTHER, clock=clock).scheduled_count() == 0)
    restarted.close()
    return results, findings


def run(dsn: str, receipt_path: Path | None) -> int:
    try:
        import psycopg
    except ModuleNotFoundError:
        print("REFUSED: psycopg is not installed. This gate EXECUTES against a real PostgreSQL; "
              "it does not simulate one.")
        return 1

    from freight_recon.migrations.postgres_p5 import (
        POSTGRES_P5_SCHEMA_VERSION,
        apply_postgres_p5,
        migration_status,
        postgres_p5_readiness_problems,
        stamp_postgres_p5_version,
    )

    steps: list[str] = []
    findings: list[str] = []
    try:
        conn = psycopg.connect(dsn)
    except Exception as exc:                                   # noqa: BLE001
        print(f"REFUSED: cannot reach PostgreSQL at {dsn!r}: {exc}")
        return 1

    with conn:
        with conn.cursor() as cur:
            cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        conn.commit()
        steps.append("--- empty database prepared (exit 0)")

        first = apply_postgres_p5(conn, now=NOW)
        steps.append(f"--- migration applied: {len(first)} steps (exit 0)")
        problems = postgres_p5_readiness_problems(conn)
        if problems:
            findings.append(f"readiness after migration: {problems}")
        steps.append(f"--- readiness: {'OK' if not problems else problems}")

        # HOSTILE: migration replayed twice.
        replay = apply_postgres_p5(conn, now=NOW)
        if replay:
            findings.append(f"replaying the migration performed {len(replay)} steps: {replay}")
        steps.append(f"--- migration REPLAYED: {len(replay)} steps "
                     f"({'NO-OP' if not replay else 'NOT A NO-OP'}) "
                     f"(exit {0 if not replay else 1})")

        stamp_postgres_p5_version(conn, now=NOW)
        stamp_postgres_p5_version(conn, now=NOW)
        status = migration_status(conn)
        if len(status) != 1:
            findings.append(f"the marker is not recorded exactly once: {status}")
        steps.append(f"--- migration status: {status} (exit {0 if len(status) == 1 else 1})")

        # SECURITY: tenant-first keys preserved in PostgreSQL.
        pg_shape, sqlite_shape = _postgres_shape(conn), _sqlite_shape()
        for key, columns in pg_shape.items():
            if key.endswith("::pk") and columns[:1] != ["tenant"]:
                findings.append(f"{key} is not tenant-first: {columns}")
        steps.append("--- tenant-first primary keys (exit 0)")

        # HOSTILE: SQLite-vs-PostgreSQL divergence, live catalog against live catalog.
        divergences = {
            key: {"sqlite": sqlite_shape.get(key), "postgres": pg_shape.get(key)}
            for key in sorted(set(sqlite_shape) | set(pg_shape))
            if sqlite_shape.get(key) != pg_shape.get(key)
        }
        if divergences:
            findings.append(f"SQLite and PostgreSQL disagree: {divergences}")
        steps.append(f"--- SQLite/PostgreSQL structural equivalence "
                     f"(exit {0 if not divergences else 1})")

        # THE EIGHT INVARIANTS.
        _seed(conn)
        results: dict[str, str] = {}
        for label, sql, must_refuse in ATTACKS:
            with psycopg.connect(dsn) as probe:
                try:
                    with probe.cursor() as cur:
                        cur.execute(sql)
                    probe.commit()
                    outcome = "ACCEPTED"
                except psycopg.errors.RaiseException:
                    outcome = "REFUSED"
                except Exception as exc:                        # noqa: BLE001
                    outcome = f"ERROR:{type(exc).__name__}"
            results[label] = outcome
            expected = "REFUSED" if must_refuse else "ACCEPTED"
            if outcome != expected:
                findings.append(f"{label}: expected {expected}, got {outcome}")
        # the terminal-state invariant needs a fired timer first
        with psycopg.connect(dsn) as probe:
            with probe.cursor() as cur:
                cur.execute("UPDATE durable_timers SET state='FIRED' WHERE timer_id='tm1'")
            probe.commit()
        with psycopg.connect(dsn) as probe:
            try:
                with probe.cursor() as cur:
                    cur.execute(
                        "UPDATE durable_timers SET state='SCHEDULED' WHERE timer_id='tm1'")
                probe.commit()
                results["timer terminal"] = "ACCEPTED"
                findings.append("timer terminal: a FIRED timer returned to SCHEDULED")
            except psycopg.errors.RaiseException:
                results["timer terminal"] = "REFUSED"
        steps.append(f"--- eight invariants + positive control "
                     f"(exit {0 if not findings else 1})")

    # ### THE RUNTIME, ON POSTGRESQL. Everything above proves the SCHEMA. P5's capability is
    # durable event execution ON production persistence, so the real classes are driven here.
    runtime_results, runtime_findings = _runtime_probes(dsn)
    results.update(runtime_results)
    findings.extend(runtime_findings)
    steps.append(f"--- RUNTIME on PostgreSQL: outbox, inbox, timers "
                 f"(exit {0 if not runtime_findings else 1})")

    passed = not findings
    print("\n".join(steps))
    for label, outcome in results.items():
        print(f"    [{outcome:>8}] {label}")
    print(f"\nPOSTGRES P5 GATE: {'PASS' if passed else 'FAIL'}")
    for finding in findings:
        print(f"  FINDING: {finding}")

    if receipt_path is not None:
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps({
            "gate": "postgres_p5",
            "schema_version": POSTGRES_P5_SCHEMA_VERSION,
            "passed": passed,
            "executed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "server_version": _server_version(dsn),
            "migration_steps_first_run": len(first),
            "migration_steps_on_replay": len(replay),
            "invariant_results": results,
            "findings": findings,
            "_what_this_proves": (
                "The P5 durable surface applies to a real PostgreSQL, replaying the migration is a "
                "genuine no-op, tenant-first keys are preserved, all eight invariants REFUSE (with "
                "a positive control proving the tables are not merely read-only), and the SQLite "
                "and PostgreSQL catalogs agree column-for-column and key-for-key."
            ),
            "_runtime_proved": (
                "The ACTUAL runtime classes - TransactionalOutbox, OutboxRelay, DedupInbox, "
                "DurableTimers, TimerRelay - were driven against this PostgreSQL through "
                "persistence.PostgresConnection: atomic emit, rollback leaving nothing, duplicate "
                "emission refused, the strict-ordering TRIGGER classified as StrictOrderViolation "
                "rather than misreported as a duplicate, relay claim/publish/bookkeeping, "
                "duplicate relay workers delivering exactly once, inbox dedup with the handler "
                "called once, EIGHT CONCURRENT emitters on real threads allocating distinct "
                "sequences, timer schedule/restart-recovery/fire/terminal, and tenant isolation."
            ),
            "_what_this_does_NOT_prove": (
                "The P2/P3 surface - the tenant-owned state tables and the checkpoint "
                "kernel's - is NOT ported: those belong to the phases that own them, and "
                "ADR-016 assigns deployment and environments to P11. No pooling, no failover, "
                "no backup/PITR - ADR-016 assigns those to P11/P12."
            ),
        }, indent=2) + "\n", encoding="utf-8")
        print(f"  receipt: {receipt_path}")
    return 0 if passed else 1


def _server_version(dsn: str) -> str:
    import psycopg
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SELECT version()")
        return cur.fetchone()[0].split(",")[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default="dbname=neyma_test",
                        help="libpq connection string for a database this gate may DROP SCHEMA on")
    parser.add_argument("--receipt", type=Path, default=None,
                        help="write a JSON receipt here")
    args = parser.parse_args()
    return run(args.dsn, args.receipt)


if __name__ == "__main__":
    raise SystemExit(main())
