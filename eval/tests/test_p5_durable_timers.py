"""P5 durable timers — how Neyma notices that something did NOT happen (M-36, ADR-016 §2).

### WHAT THIS UNIT IS ACTUALLY FOR. Almost everything that goes wrong in freight is a SILENCE: the
POD never arrives, the carrier never checks in, the appointment window passes with no update,
detention accrues while nobody notices. A system that only reacts to inbound events cannot help
with any of it. A durable timer is how a MISSING event becomes an observable one — `ExpectationOverdue`
(EX-3), `ExceptionAgeing`/`ExceptionEscalated` (EC-4/EC-5), `WorkEscalated` (WI-10),
`ApprovalExpired` (AP-3) and `GrantExpired` (EF-2x, "nothing happened") are all driven by it.

THE PROPERTY THIS FILE DEFENDS

    ### M-36. A timeout MUST be a durable timer emitting `TimerFired` — never a background sweep,
    never a scan for "things that look old."

The load-bearing node is `test_no_component_scans_for_staleness`, which the specification names
outright. A sweep asks the business tables which rows LOOK old; every answer depends on a predicate
someone can edit, it silently misses what a slightly different `WHERE` would have caught, and
nothing fails when it does — the work simply never ages. A timer is the opposite: the deadline is
written once, by the transition that created the obligation, in the same commit.

DISCIPLINE, as everywhere in this suite: discover, never enumerate; exact sets, not counts; a
proven population before every negative assertion; and no node may pass by measuring nothing.
"""

from __future__ import annotations

import ast
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for entry in (str(ROOT / "src"), str(ROOT / "eval")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from phase5_kit import Clock, make_store  # noqa: E402

from freight_recon.event_timers import (  # noqa: E402
    DurableTimers,
    DuplicateTimer,
    TimerError,
    TimerFired,
    TimerNotInTransaction,
    TimerRelay,
)
from freight_recon.migrations.phase5_durable_timers import (  # noqa: E402
    TIMER_INDEXES,
    TIMER_STATES,
    TIMER_TRIGGERS,
    timer_readiness_problems,
)

TENANT = "brokerage-northwind"
OTHER = "brokerage-cascade"


def require_population(population, *, at_least: int, what: str):
    assert len(population) >= at_least, (
        f"{what}: expected at least {at_least}, found {len(population)}. A case that iterates an "
        f"empty population proves nothing while reporting success."
    )
    return population


def _timers(store, clock, tenant=TENANT):
    return DurableTimers(store.conn, tenant=tenant, clock=clock)


def _schedule(store, timers, **kwargs):
    """Schedule inside a transaction that also moves real state — the M-23 shape."""
    store.conn.execute("BEGIN IMMEDIATE")
    timer_id = timers.schedule(**kwargs)
    store.conn.execute("UPDATE platform_brake SET brake_version = brake_version + 1 WHERE id = 1")
    store.conn.commit()
    return timer_id


# ============================================================ 1. the schema is a real mechanism

def test_the_timer_schema_is_ready_on_every_canonical_database(tmp_path):
    store = make_store(tmp_path, tenant=TENANT)
    assert timer_readiness_problems(store.conn) == []
    stamped = [r[0] for r in store.conn.execute(
        "SELECT step FROM schema_migrations WHERE migration='phase5_durable_timers'").fetchall()]
    assert stamped == ["version:p5-timers-1"], stamped
    store.close()


def test_the_timer_table_is_tenant_first(tmp_path):
    """[C-1]. There is no tenant-exempt timer: "whose deadline is this" has no honest answer
    other than a tenant."""
    store = make_store(tmp_path, tenant=TENANT)
    primary = [r[1] for r in store.conn.execute("PRAGMA table_info(durable_timers)").fetchall()
               if r[5]]
    assert primary[0] == "tenant", primary
    store.close()


def test_a_deadline_cannot_be_moved_once_written(tmp_path):
    """### A DEADLINE THAT CAN BE EDITED CAN BE QUIETLY PUSHED OUT, which is how an obligation
    stops ageing without anyone deciding that it should. Enforced by the database, so it survives
    an admin with a connection."""
    store, clock = make_store(tmp_path, tenant=TENANT), Clock()
    timers = _timers(store, clock)
    _schedule(store, timers, timer_id="t1", aggregate_type="expectation", aggregate_id="ex-1",
              timer_kind="expectation_deadline", fire_at=clock() + timedelta(hours=2))
    for column, value in (("fire_at", "2099-01-01T00:00:00.000Z"),
                          ("aggregate_id", "ex-elsewhere"),
                          ("timer_kind", "something_else"),
                          ("tenant", OTHER)):
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            store.conn.execute(
                f"UPDATE durable_timers SET {column}=? WHERE timer_id='t1'", (value,))
        store.conn.rollback()
    store.close()


def test_a_terminal_timer_can_never_be_re_armed(tmp_path):
    """Re-arming a FIRED deadline fires it twice; re-arming a CANCELLED one resurrects an
    obligation somebody decided was over."""
    store, clock = make_store(tmp_path, tenant=TENANT), Clock()
    timers = _timers(store, clock)
    _schedule(store, timers, timer_id="t1", aggregate_type="work_item", aggregate_id="wi-1",
              timer_kind="age_threshold", fire_at=clock())
    TimerRelay(store.conn, tenant=TENANT, handler=lambda t: None, relay_id="r",
               clock=clock).run_once()
    assert timers.get("t1")["state"] == "FIRED"
    with pytest.raises(sqlite3.IntegrityError, match="never return to SCHEDULED"):
        store.conn.execute("UPDATE durable_timers SET state='SCHEDULED' WHERE timer_id='t1'")
    store.conn.rollback()
    store.close()


def test_a_timer_row_can_never_be_deleted(tmp_path):
    """S8: a timer records that a deadline EXISTED. Deleting it erases the evidence that an
    obligation was ever owed."""
    store, clock = make_store(tmp_path, tenant=TENANT), Clock()
    timers = _timers(store, clock)
    _schedule(store, timers, timer_id="t1", aggregate_type="expectation", aggregate_id="ex-1",
              timer_kind="expectation_deadline", fire_at=clock())
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        store.conn.execute("DELETE FROM durable_timers WHERE timer_id='t1'")
    store.conn.rollback()
    store.close()


# ================================================== 2. M-36 — a timer, not a sweep

# ### THE ONE SWEEP THAT EXISTS TODAY, NAMED RATHER THAN HIDDEN.
#
# `checkpoint.expire_unclaimed` (P3) scans `effect_grants` for GRANTED rows past their TTL and
# reports `GrantExpired` — EF-2x, "nothing happened". It IS a background sweep over business state,
# and its own docstring says so: *"durable timers arrive with P5."* P5 has now arrived and the
# sweep has not moved, because migrating it means transitioning the M3 machine, and the machines
# are P6.
#
# An earlier version of this guard could not see it — twice over: it inspected only literals
# containing both `select` and `where` (this is an UPDATE), and `expires_at` sits in the
# deadline-column carve-out. Three prose artifacts meanwhile asserted the no-sweep property was
# structural. ### A GUARD CARVED OUT AROUND ITS OWN COUNTEREXAMPLE IS NOT A GUARD, so the
# exemption is recorded HERE, with the obligation that discharges it, and the guard is widened to
# catch everything else.
KNOWN_SWEEP_EXEMPTIONS: dict[str, str] = {
    "checkpoint.py": (
        "expire_unclaimed (EF-2x): a P3 sweep over effect_grants that predates durable timers. "
        "Migrating it to a TimerFired-driven M3 transition is P6 work; P5 may not touch the "
        "checkpoint kernel (prohibited scope), and this increment leaves it byte-unchanged."
    ),
}


def test_no_component_scans_for_staleness():
    """### THE NODE THE SPECIFICATION NAMES BY NAME (M-36), AND WHAT IT HONESTLY COVERS.

    A sweep infers staleness from a RECORD-KEEPING timestamp — `created_at`, `occurred_at` — asking
    "which rows LOOK old?". A schedule reads a DEADLINE somebody wrote deliberately (`fire_at`,
    `expires_at`); `pending_references.expires_at` is M-26's prescribed mechanism, and flagging it
    would be the over-strictness pattern this phase keeps producing.

    That distinction is right but it is not sufficient on its own, so this node also:
      * normalises whitespace before matching (the repository writes SQL multi-line with aligned
        operators, so a raw-literal match missed its own house style);
      * inspects UPDATE and DELETE, not only SELECT — the sweep that actually exists is an UPDATE;
      * runs POSITIVE CONTROLS, so a detector that detects nothing cannot pass;
      * treats `KNOWN_SWEEP_EXEMPTIONS` as an exact set — an exemption that disappears fails too,
        so the obligation cannot be silently discharged by deleting the row.
    """
    import re as _re

    src = ROOT / "src" / "freight_recon"
    modules = require_population(sorted(src.rglob("*.py")), at_least=50,
                                 what="production modules inspected")

    BUSINESS_TABLES = {
        "workflow_runs", "audit_events", "security_events", "effect_grants",
        "checkpoint_witnesses", "operation_action_claims", "delivery_action_claims",
        "event_outbox", "event_inbox", "pending_references", "brakes",
        "owner_assertions", "platform_brake", "operation_token_amounts",
        "autonomous_run_counters", "migration_quarantine",
    }
    AGE_COLUMNS = {"created_at", "occurred_at", "recorded_at", "updated_at", "scheduled_at",
                   "parked_at", "as_of", "consumed_at", "published_at"}

    # ### THE DISTINCTION IS NOT "deadline column vs record-keeping column" — IT IS WHETHER A
    # MECHANISM OWNS THE DEADLINE.
    #
    # `durable_timers.fire_at` IS the schedule. `pending_references.expires_at` is M-26's
    # PRESCRIBED mechanism — a TTL written at park time and drained on expiry. Reading either is
    # the mechanism the specification mandates, and flagging them would be the over-strictness
    # pattern.
    #
    # `effect_grants.expires_at` is different in the way that matters: nobody scheduled it. It is a
    # TTL discovered by periodically asking the ledger which grants LOOK expired — a sweep wearing
    # a deadline column's name. An earlier version of this guard exempted every `expires_at`
    # everywhere and therefore could not see the one real sweep in the tree.
    # `lease_expires_at` is deliberately ABSENT: a relay lease is delivery bookkeeping for
    # at-least-once handoff, not an obligation deadline, and claiming rows whose lease lapsed is
    # not asking "which work looks old". Including it flagged both relays — caught by this guard's
    # own positive controls, via a SUBSTRING match of `expires_at` inside `lease_expires_at`, which
    # is why the comparison below is whole-token (CLAUDE.md §9: substring guards fire on their own
    # assertion text and on unrelated words).
    SCHEDULE_TABLES = {"durable_timers", "pending_references"}
    DEADLINE_COLUMNS = {"expires_at", "fire_at", "recheck_at"}

    def sweeps(sql: str) -> str | None:
        """The offending age predicate, or None. Whitespace-normalised, both operand orders."""
        flat = " ".join(sql.lower().split())
        if not any(verb in flat for verb in ("select", "update", "delete")):
            return None
        if "where" not in flat or not any(table in flat for table in BUSINESS_TABLES):
            return None
        # A statement touching ONLY schedule-bearing tables is reading a schedule, not sweeping.
        named = {table for table in BUSINESS_TABLES | SCHEDULE_TABLES if table in flat}
        columns = set(AGE_COLUMNS)
        if not named <= SCHEDULE_TABLES:
            columns |= DEADLINE_COLUMNS
        for column in columns:
            if _re.search(rf"\b{column}\b\s*(<=?|between)", flat) or \
               _re.search(rf"(>=?)\s*\b{column}\b", flat) or \
               _re.search(rf"julianday\s*\([^)]*\)\s*-\s*julianday\s*\(\s*\b{column}\b", flat):
                return f"{column} compared against a bound value"
        return None

    # ### POSITIVE CONTROLS FIRST. A negative assertion whose detector was never exercised is not
    # a guard, and the earlier version of this node had none — it passed nine of ten genuine sweep
    # spellings.
    for control in (
        "SELECT * FROM workflow_runs WHERE tenant = ? AND created_at <= ?",
        "SELECT * FROM audit_events WHERE ? > occurred_at",
        "SELECT * FROM event_inbox WHERE tenant = ?\n           AND consumed_at  <= ?",
        "UPDATE effect_grants SET state='X' WHERE recorded_at <= ?",
        "DELETE FROM security_events WHERE occurred_at BETWEEN ? AND ?",
    ):
        assert sweeps(control) is not None, f"the detector cannot see a genuine sweep: {control!r}"
    # ...and a negative control, so it is not simply flagging everything.
    assert sweeps("SELECT * FROM durable_timers WHERE tenant=? AND state='SCHEDULED' "
                  "AND fire_at <= ?") is None, "the detector flags the prescribed mechanism"

    offenders: dict[str, list[str]] = {}
    inspected = 0
    for path in modules:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            inspected += 1
            finding = sweeps(node.value)
            if finding:
                offenders.setdefault(path.name, []).append(finding)
    assert inspected, "the scan parsed no SQL at all — it cannot conclude anything"

    unexpected = {name: found for name, found in offenders.items()
                  if name not in KNOWN_SWEEP_EXEMPTIONS}
    assert not unexpected, (
        "a component scans business state for things that look old. M-36: a timeout MUST be a "
        f"durable timer, never a sweep: {unexpected}"
    )
    # ### THE EXEMPTION IS AN EXACT SET, IN BOTH DIRECTIONS. If the P3 sweep is ever migrated to a
    # timer, this node goes red and the exemption must be REMOVED deliberately — an obligation that
    # can be discharged by silence is not an obligation.
    assert set(offenders) == set(KNOWN_SWEEP_EXEMPTIONS), {
        "sweeping but unexempted": sorted(set(offenders) - set(KNOWN_SWEEP_EXEMPTIONS)),
        "exempted but no longer sweeping": sorted(set(KNOWN_SWEEP_EXEMPTIONS) - set(offenders)),
    }


def test_the_due_lookup_reads_only_the_schedule():
    """The positive half: the timer service's own query names `durable_timers` and nothing else.

    Note the narrower claim than an earlier docstring made. It is NOT true that "the only module
    that selects on a time-versus-now comparison is the timer service": `event_inbox` drains
    `pending_references` on `expires_at` (M-26's mechanism) and both relays compare
    `lease_expires_at`. What is true, and is what matters, is that the timer service reads the
    SCHEDULE and never business state.
    """
    import inspect

    from freight_recon import event_timers

    source = inspect.getsource(event_timers)
    for table in ("workflow_runs", "event_outbox", "event_inbox", "effect_grants",
                  "checkpoint_witnesses", "brakes"):
        assert table not in source, (
            f"the timer service reads {table}: a schedule must not interrogate business state"
        )
    assert "durable_timers" in source


def test_the_due_index_exists_so_firing_is_a_seek_not_a_scan(tmp_path):
    """Without the index the relay degrades into the table scan M-36 forbids in spirit."""
    store = make_store(tmp_path, tenant=TENANT)
    present = {r[0] for r in store.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'").fetchall()}
    assert set(TIMER_INDEXES) <= present, set(TIMER_INDEXES) - present
    plan = store.conn.execute(
        "EXPLAIN QUERY PLAN SELECT * FROM durable_timers "
        " WHERE tenant=? AND state='SCHEDULED' AND fire_at <= ?", (TENANT, "2026-01-01")
    ).fetchall()
    rendered = " ".join(str(r[3]) for r in plan).lower()
    assert "using index" in rendered or "search" in rendered, rendered
    store.close()


# ============================================================ 3. the deadline commits with the work

def test_scheduling_refuses_to_run_outside_a_transaction(tmp_path):
    """### THE REFUSAL, for the same reason `TransactionalOutbox.emit` has one. A deadline written
    in a commit of its own can be lost while the obligation survives — and an obligation whose
    timer was lost never ages, never escalates and is never reported. It sits there looking fine."""
    store, clock = make_store(tmp_path, tenant=TENANT), Clock()
    with pytest.raises(TimerNotInTransaction, match="SAME commit"):
        _timers(store, clock).schedule(
            timer_id="t1", aggregate_type="expectation", aggregate_id="ex-1",
            timer_kind="expectation_deadline", fire_at=clock())
    assert _timers(store, clock).scheduled_count() == 0
    store.close()


def test_a_rolled_back_obligation_leaves_no_deadline(tmp_path):
    """Both, or neither — M-23's shape applied to time."""
    store, clock = make_store(tmp_path, tenant=TENANT), Clock()
    timers = _timers(store, clock)
    baseline = store.conn.execute(
        "SELECT brake_version FROM platform_brake WHERE id=1").fetchone()[0]
    store.conn.execute("BEGIN IMMEDIATE")
    timers.schedule(timer_id="t1", aggregate_type="expectation", aggregate_id="ex-1",
                    timer_kind="expectation_deadline", fire_at=clock())
    store.conn.execute("UPDATE platform_brake SET brake_version = brake_version + 1 WHERE id=1")
    store.conn.rollback()
    assert timers.scheduled_count() == 0, "the obligation rolled back but its deadline survives"
    assert store.conn.execute(
        "SELECT brake_version FROM platform_brake WHERE id=1").fetchone()[0] == baseline
    store.close()


def test_cancelling_also_requires_the_transaction_that_ended_the_obligation(tmp_path):
    """### SYMMETRICAL TO SCHEDULING, AND FOR A SYMMETRICAL REASON. A cancellation committing
    separately leaves an obligation closed with a LIVE deadline — which later fires into a machine
    that has moved on — or a cancelled deadline with the obligation still OPEN, never ageing."""
    store, clock = make_store(tmp_path, tenant=TENANT), Clock()
    timers = _timers(store, clock)
    _schedule(store, timers, timer_id="t1", aggregate_type="expectation", aggregate_id="ex-1",
              timer_kind="expectation_deadline", fire_at=clock() + timedelta(hours=1))
    with pytest.raises(TimerNotInTransaction):
        timers.cancel("t1", reason="POD arrived early")
    assert timers.get("t1")["state"] == "SCHEDULED"
    store.close()


def test_a_timer_identity_is_claimed_once(tmp_path):
    store, clock = make_store(tmp_path, tenant=TENANT), Clock()
    timers = _timers(store, clock)
    _schedule(store, timers, timer_id="t1", aggregate_type="expectation", aggregate_id="ex-1",
              timer_kind="expectation_deadline", fire_at=clock())
    store.conn.execute("BEGIN IMMEDIATE")
    with pytest.raises(DuplicateTimer, match="already exists"):
        timers.schedule(timer_id="t1", aggregate_type="expectation", aggregate_id="ex-1",
                        timer_kind="expectation_deadline", fire_at=clock())
    store.conn.rollback()
    store.close()


def test_a_timer_without_a_kind_is_refused(tmp_path):
    """`timer_kind` tells the MACHINE which of its guards this arrival concerns. A timer with no
    kind fires into nothing."""
    store, clock = make_store(tmp_path, tenant=TENANT), Clock()
    store.conn.execute("BEGIN IMMEDIATE")
    with pytest.raises(TimerError, match="timer_kind"):
        _timers(store, clock).schedule(timer_id="t1", aggregate_type="expectation",
                                       aggregate_id="ex-1", timer_kind="  ", fire_at=clock())
    store.conn.rollback()
    store.close()


# ============================================================ 4. firing, restart, and redelivery

def test_a_timer_fires_only_once_its_time_has_come(tmp_path):
    store, clock = make_store(tmp_path, tenant=TENANT), Clock()
    timers = _timers(store, clock)
    _schedule(store, timers, timer_id="t1", aggregate_type="expectation", aggregate_id="ex-1",
              timer_kind="expectation_deadline", fire_at=clock() + timedelta(hours=2))
    fired: list[TimerFired] = []
    relay = TimerRelay(store.conn, tenant=TENANT, handler=fired.append, relay_id="r", clock=clock)
    assert relay.run_once().fired == (), "a timer fired before its deadline"
    clock.advance(hours=3)
    assert relay.run_once().fired == ("t1",)
    assert relay.run_once().fired == (), "a fired timer fired again"
    assert len(fired) == 1
    store.close()


def test_the_deadline_survives_a_restart(tmp_path):
    """### P5's NAMED HOSTILE CASE: "timer loss across restart". The store is closed and reopened —
    a genuine process restart — and the deadline is still armed and still fires."""
    clock = Clock()
    store = make_store(tmp_path, tenant=TENANT, name="timers.db")
    _schedule(store, _timers(store, clock), timer_id="t1", aggregate_type="expectation",
              aggregate_id="ex-1", timer_kind="expectation_deadline",
              fire_at=clock() + timedelta(hours=2))
    store.close()

    clock.advance(hours=3)
    reopened = make_store(tmp_path, tenant=TENANT, name="timers.db")
    timers = _timers(reopened, clock)
    assert timers.scheduled_count() == 1, "the deadline did not survive the restart"
    assert [r["timer_id"] for r in timers.due()] == ["t1"]
    fired: list[TimerFired] = []
    assert TimerRelay(reopened.conn, tenant=TENANT, handler=fired.append, relay_id="r",
                      clock=clock).run_once().fired == ("t1",)
    assert fired[0].timer_kind == "expectation_deadline"
    reopened.close()


def test_a_handler_that_raises_leaves_the_deadline_armed(tmp_path):
    """At-least-once: whether the machine acted is unknowable from here, so the deadline stays
    until a pass succeeds. A timer fires AT LEAST once; the machine's guard makes it act once."""
    store, clock = make_store(tmp_path, tenant=TENANT), Clock()
    timers = _timers(store, clock)
    _schedule(store, timers, timer_id="t1", aggregate_type="exception", aggregate_id="ec-1",
              timer_kind="age_threshold", fire_at=clock())

    def explode(trigger: TimerFired) -> None:
        raise RuntimeError("the machine was mid-transition")

    result = TimerRelay(store.conn, tenant=TENANT, handler=explode, relay_id="r",
                        clock=clock).run_once()
    assert result.failed == ("t1",) and result.fired == ()
    assert timers.get("t1")["state"] == "SCHEDULED", "a failed delivery consumed the deadline"
    assert timers.get("t1")["fire_attempts"] == 1

    fired: list[TimerFired] = []
    assert TimerRelay(store.conn, tenant=TENANT, handler=fired.append, relay_id="r",
                      clock=clock).run_once().fired == ("t1",)
    store.close()


def test_the_fired_trigger_carries_its_identity_so_a_redelivery_is_deduplicable(tmp_path):
    store, clock = make_store(tmp_path, tenant=TENANT), Clock()
    timers = _timers(store, clock)
    _schedule(store, timers, timer_id="t1", aggregate_type="expectation", aggregate_id="ex-1",
              timer_kind="expectation_deadline", fire_at=clock(),
              payload={"expectation_key": "pod_by", "deadline_utc": "2026-05-01T17:00:00.000Z"})
    fired: list[TimerFired] = []
    TimerRelay(store.conn, tenant=TENANT, handler=fired.append, relay_id="r",
               clock=clock).run_once()
    trigger = fired[0]
    assert trigger.identity == (TENANT, "t1")
    assert trigger.payload == {"expectation_key": "pod_by",
                               "deadline_utc": "2026-05-01T17:00:00.000Z"}
    store.close()


def test_two_relays_cannot_fire_one_deadline_twice(tmp_path):
    """### THE LEASE, ACTUALLY TESTED. An earlier version ran the two relays SEQUENTIALLY, so the
    second found nothing because the timer was already FIRED — it passed with the entire leasing
    mechanism deleted. The second relay now runs from INSIDE the first one's handler, while the
    lease is held and the state is still SCHEDULED, which is the only arrangement in which the
    lease is what decides."""
    store, clock = make_store(tmp_path, tenant=TENANT), Clock()
    timers = _timers(store, clock)
    _schedule(store, timers, timer_id="t1", aggregate_type="expectation", aggregate_id="ex-1",
              timer_kind="expectation_deadline", fire_at=clock())
    first: list[TimerFired] = []
    interloper: list[TimerFired] = []

    def deliver_then_let_a_second_relay_try(trigger: TimerFired) -> None:
        first.append(trigger)
        assert timers.get("t1")["state"] == "SCHEDULED", "the fixture no longer holds a lease"
        assert TimerRelay(store.conn, tenant=TENANT, handler=interloper.append,
                          relay_id="r2", clock=clock).run_once().fired == (), \
            "a second relay claimed a leased timer"

    assert TimerRelay(store.conn, tenant=TENANT, handler=deliver_then_let_a_second_relay_try,
                      relay_id="r1", clock=clock).run_once().fired == ("t1",)
    assert (len(first), len(interloper)) == (1, 0)
    store.close()


def test_a_lapsed_lease_is_reclaimable(tmp_path):
    """The other half: a relay that died mid-delivery must not strand the deadline forever."""
    store, clock = make_store(tmp_path, tenant=TENANT), Clock()
    timers = _timers(store, clock)
    _schedule(store, timers, timer_id="t1", aggregate_type="expectation", aggregate_id="ex-1",
              timer_kind="expectation_deadline", fire_at=clock())

    def die(trigger: TimerFired) -> None:
        raise RuntimeError("the relay process was killed mid-delivery")

    TimerRelay(store.conn, tenant=TENANT, handler=die, relay_id="dead", clock=clock).run_once()
    assert timers.get("t1")["state"] == "SCHEDULED"
    clock.advance(minutes=5)                       # past DEFAULT_TIMER_LEASE
    recovered: list[TimerFired] = []
    assert TimerRelay(store.conn, tenant=TENANT, handler=recovered.append, relay_id="fresh",
                      clock=clock).run_once().fired == ("t1",)
    store.close()


def test_a_timer_cancelled_mid_delivery_is_reported_superseded_not_fired(tmp_path):
    """### CANCELLED IS NOT FIRED, EVEN WHEN THE HANDLER ALREADY SAW IT. `cancel` matches
    SCHEDULED without considering the lease, so it can land underneath a relay. The mark then
    matches zero rows — and reporting the timer as fired anyway made history say CANCELLED while
    the relay said fired, so "did this ever go overdue?" answered NO for a machine already told it
    did. Counts are derived from ROWS."""
    store, clock = make_store(tmp_path, tenant=TENANT), Clock()
    timers = _timers(store, clock)
    _schedule(store, timers, timer_id="t1", aggregate_type="expectation", aggregate_id="ex-1",
              timer_kind="expectation_deadline", fire_at=clock())
    seen: list[TimerFired] = []

    def cancel_underneath(trigger: TimerFired) -> None:
        seen.append(trigger)
        store.conn.execute("BEGIN IMMEDIATE")
        assert timers.cancel("t1", reason="POD arrived while the relay was mid-delivery")
        store.conn.commit()

    result = TimerRelay(store.conn, tenant=TENANT, handler=cancel_underneath, relay_id="r",
                        clock=clock).run_once()
    assert result.fired == (), "a cancelled timer was reported as fired"
    assert result.superseded == ("t1",), result
    assert len(seen) == 1
    row = timers.get("t1")
    assert row["state"] == "CANCELLED" and row["fired_at"] is None
    store.close()


# ============================================================ 5. cancellation and tenant isolation

def test_a_cancelled_deadline_never_fires(tmp_path):
    """### CANCELLED IS NOT FIRED, AND THE DIFFERENCE IS RECORDED. An obligation that ended before
    its deadline did not come due; collapsing the two would make "did this ever go overdue?"
    unanswerable from history."""
    store, clock = make_store(tmp_path, tenant=TENANT), Clock()
    timers = _timers(store, clock)
    _schedule(store, timers, timer_id="t1", aggregate_type="expectation", aggregate_id="ex-1",
              timer_kind="expectation_deadline", fire_at=clock() + timedelta(hours=1))
    store.conn.execute("BEGIN IMMEDIATE")
    assert timers.cancel("t1", reason="POD arrived early") is True
    store.conn.commit()

    row = timers.get("t1")
    assert row["state"] == "CANCELLED" and row["cancel_reason"] == "POD arrived early"
    clock.advance(hours=5)
    assert timers.due() == []
    fired: list[TimerFired] = []
    assert TimerRelay(store.conn, tenant=TENANT, handler=fired.append, relay_id="r",
                      clock=clock).run_once().fired == ()
    store.close()


def test_cancelling_requires_a_reason(tmp_path):
    """History records WHY an obligation ended early."""
    store, clock = make_store(tmp_path, tenant=TENANT), Clock()
    timers = _timers(store, clock)
    _schedule(store, timers, timer_id="t1", aggregate_type="expectation", aggregate_id="ex-1",
              timer_kind="expectation_deadline", fire_at=clock())
    store.conn.execute("BEGIN IMMEDIATE")
    with pytest.raises(TimerError, match="reason"):
        timers.cancel("t1", reason="   ")
    store.conn.rollback()
    store.close()


def test_a_terminal_transition_cancels_every_deadline_on_its_aggregate(tmp_path):
    store, clock = make_store(tmp_path, tenant=TENANT), Clock()
    timers = _timers(store, clock)
    for index in range(3):
        _schedule(store, timers, timer_id=f"t{index}", aggregate_type="exception",
                  aggregate_id="ec-1", timer_kind=f"threshold-{index}",
                  fire_at=clock() + timedelta(hours=index + 1))
    _schedule(store, timers, timer_id="other", aggregate_type="exception", aggregate_id="ec-2",
              timer_kind="threshold-0", fire_at=clock() + timedelta(hours=1))
    store.conn.execute("BEGIN IMMEDIATE")
    assert timers.cancel_for_aggregate("exception", "ec-1", reason="resolved by a human") == 3
    store.conn.commit()
    assert timers.scheduled_count() == 1, "a sibling aggregate's deadline was cancelled too"
    store.close()


def test_one_tenants_deadlines_are_invisible_to_another(tmp_path):
    """[C-1]. Tenant is the first key, so a relay for one brokerage cannot fire another's."""
    store, clock = make_store(tmp_path, tenant=TENANT), Clock()
    _schedule(store, _timers(store, clock), timer_id="t1", aggregate_type="expectation",
              aggregate_id="ex-1", timer_kind="expectation_deadline", fire_at=clock())
    other = DurableTimers(store.conn, tenant=OTHER, clock=clock)
    assert other.due() == [] and other.scheduled_count() == 0
    fired: list[TimerFired] = []
    assert TimerRelay(store.conn, tenant=OTHER, handler=fired.append, relay_id="r",
                      clock=clock).run_once().fired == ()
    assert TimerRelay(store.conn, tenant=TENANT, handler=fired.append, relay_id="r",
                      clock=clock).run_once().fired == ("t1",)
    store.close()


def test_a_sentinel_tenant_cannot_hold_a_deadline(tmp_path):
    """`require_tenant` refuses every placeholder — a deadline whose tenant is "default" is a
    deadline that will eventually fire into the wrong brokerage."""
    store = make_store(tmp_path, tenant=TENANT)
    for sentinel in ("default", "test", "", "   "):
        with pytest.raises(ValueError):
            DurableTimers(store.conn, tenant=sentinel)
    store.close()


# ============================================================ 6. the boundary with P6

def test_the_timer_service_decides_nothing_about_what_a_fired_timer_MEANS():
    """### THE SAFETY BOUNDARY. `TimerFired` is a TRIGGER, not one of the 105 canonical contracts
    (the corpus errata excludes it explicitly). GR-6 forbids any timer transition from moving an
    `UNKNOWN_OUTCOME`; `NEEDS_VERIFICATION`, `COMPENSATION_FAILED` and an ACTIVE policy each name
    ANY `TimerFired` as an ILLEGAL transition; and rule 12 says a timeout alone never becomes
    `FAILED`. A timer service that decided outcomes could violate all of those. This one reports
    the arrival of a time — the refusals stay where the guards are, in P6's machines.
    """
    import inspect

    from freight_recon import event_timers

    from freight_recon.event_envelope import EventEnvelope

    # ### PARSED, NOT SUBSTRING-MATCHED. `f"import {name}"` does not match
    # `from .event_contracts import validate` — the exact spelling every module here uses — so the
    # check missed the import form it most needed to catch.
    tree = ast.parse(inspect.getsource(event_timers))
    reached: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                reached.add(node.module.split(".")[-1])
            reached.update(alias.name.split(".")[-1] for alias in node.names)
        elif isinstance(node, ast.Import):
            reached.update(alias.name.split(".")[-1] for alias in node.names)
    assert reached, "the import scan found nothing — it cannot conclude anything"
    forbidden = {"event_contracts", "event_outbox", "event_inbox", "EventEnvelope",
                 "TransactionalOutbox", "CONTRACTS", "validate"}
    assert not (reached & forbidden), (
        f"the timer service reaches {sorted(reached & forbidden)}: deciding what a fired timer "
        f"MEANS is the machine's job (P6), and a service that can mint an outcome can violate GR-6"
    )
    # And it must not NAME a canonical outcome event either.
    source = inspect.getsource(event_timers)
    import re as _re
    for outcome in ("ExpectationOverdue", "ExceptionAgeing", "ExceptionEscalated",
                    "ApprovalExpired", "GrantExpired", "WorkEscalated"):
        assert not _re.search(rf"\b{outcome}\s*\(", source), (
            f"the timer service constructs {outcome}"
        )

    # ### DIRECT, NOT VACUOUS. The old form was `issubclass(TimerFired, () or ())` — an empty
    # tuple, so it could never fail. It was vacuous BECAUSE the property held, and would have
    # stayed vacuous if someone later imported EventEnvelope under an alias.
    assert not issubclass(TimerFired, EventEnvelope), (
        "TimerFired became an EventEnvelope: a trigger dressed as one of the 105 looks like a fact "
        "about the world rather than a signal that a time arrived"
    )


def test_the_states_are_exactly_the_three_the_schema_allows(tmp_path):
    """Exact set, not a count: a same-count substitution must fail."""
    store = make_store(tmp_path, tenant=TENANT)
    ddl = store.conn.execute(
        "SELECT sql FROM sqlite_master WHERE name='durable_timers'").fetchone()[0]
    for state in TIMER_STATES:
        assert f"'{state}'" in ddl, f"{state} is not in the CHECK constraint"
    with pytest.raises(sqlite3.IntegrityError):
        store.conn.execute(
            "INSERT INTO durable_timers (tenant, timer_id, aggregate_type, aggregate_id, "
            "timer_kind, fire_at, state, scheduled_at) VALUES (?,?,?,?,?,?,?,?)",
            (TENANT, "bad", "expectation", "ex-1", "k", "2026-01-01T00:00:00.000Z",
             "PAUSED", "2026-01-01T00:00:00.000Z"))
    store.conn.rollback()
    assert set(TIMER_TRIGGERS) == {
        "trg_durable_timers_immutable", "trg_durable_timers_terminal",
        "trg_durable_timers_no_delete"}, set(TIMER_TRIGGERS)
    store.close()
