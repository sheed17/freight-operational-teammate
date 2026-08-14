"""Durable timers: how Neyma notices that something did NOT happen (P5, M-36, ADR-016 §2).

    ### M-36. A timeout MUST be a durable timer emitting `TimerFired` — never a background
    sweep, never a scan for "things that look old."

WHY THIS IS A FREIGHT CAPABILITY AND NOT PLUMBING

Almost everything that goes wrong in freight is a **silence**. The POD never arrives. The carrier
never checks in. The appointment window passes with no update. Detention accrues while nobody
notices. An operator's real job is largely watching for things that should have happened and did
not — and a system that only reacts to inbound events is structurally incapable of helping with it.

A durable timer is how a *missing* event becomes an observable one. `ExpectationOverdue` (EX-3),
`ExceptionAgeing` and `ExceptionEscalated` (EC-4/EC-5), `WorkEscalated` (WI-10), `ApprovalExpired`
(AP-3), `GrantExpired` (EF-2x, *"nothing happened"*) are all driven by a `TimerFired` trigger, and
none of them can exist without this.

THE ONE THING THIS MODULE REFUSES TO DO, AND WHY IT MATTERS MOST

### **IT DOES NOT DECIDE WHAT A FIRED TIMER MEANS.** `TimerFired` is a *trigger*, not a canonical
event — the corpus errata excludes it from the 105 explicitly. This module says only *"the time you
asked for has arrived, for this aggregate, under this kind"*. The MACHINE then transitions by its
own deterministic guard, and those machines are **P6**.

That boundary is a safety property, not tidiness. `GR-6` forbids any timer transition from moving
an `UNKNOWN_OUTCOME`; `NEEDS_VERIFICATION`, `COMPENSATION_FAILED` and an ACTIVE policy each name
**any** `TimerFired` as an ILLEGAL transition; and rule 12 says a timeout alone never becomes
`FAILED`. A timer service that decided outcomes could violate every one of those. One that only
reports the arrival of a time cannot — the refusals stay where the guards are.

WHY SCHEDULING REFUSES TO RUN OUTSIDE A TRANSACTION

The same reason `TransactionalOutbox.emit` does. A deadline created in its own commit is a dual
write: the obligation lands, the process dies, and the thing that would have made it observable
never exists. The obligation would then sit forever, un-aged, and **nothing would report it** —
which is precisely the failure a timer is for. So `schedule` requires the caller's open
transaction, and there is no lenient mode.

AT-LEAST-ONCE, LIKE EVERY OTHER DELIVERY HERE

The relay claims a due timer under a lease, hands it to a handler, then marks it FIRED. Those
cannot be one act, so a crash between them re-delivers — and re-delivery must therefore be
harmless. It is: the trigger carries the timer's own identity, so a consumer deduplicates it
exactly as it deduplicates a redelivered event. A timer fires **at least** once; a machine acts
**exactly** once, because the machine's guard is idempotent.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .event_envelope import format_instant
from .migrations.phase5_durable_timers import TIMER_IMMUTABLE_ABORT
from .persistence import integrity_errors
from .tenant import require_tenant

# How long a relay may hold a claim before another may assume it died. Same reasoning as the
# outbox's: short enough that a crashed relay does not stall a deadline for long, long enough that
# a slow handler is not stolen mid-flight and fired twice for no reason.
DEFAULT_TIMER_LEASE = timedelta(seconds=30)


class TimerError(RuntimeError):
    """The timer service cannot do what was asked. Never silently degraded."""


class TimerNotInTransaction(TimerError):
    """`schedule` was called outside an open transaction.

    THE refusal, for the same reason `OutboxNotInTransaction` exists. A deadline written in a
    commit of its own can be lost while the obligation it guards survives — and an obligation whose
    timer was lost never ages, never escalates, and is never reported. It simply sits there looking
    fine.
    """


class TimerScheduleImmutable(TimerError):
    """Something tried to move a deadline. A deadline that can be edited can be quietly pushed
    out, which is how an obligation stops ageing without anyone deciding that it should."""


class DuplicateTimer(TimerError):
    """`(tenant, timer_id)` already exists. A timer identity is claimed once."""


@dataclass(frozen=True)
class TimerFired:
    """The trigger a fired timer produces. ### IT CARRIES NO DECISION.

    Deliberately not an `EventEnvelope`: `TimerFired` is not one of the 105 canonical contracts,
    and dressing it as one would make it look like a fact about the world rather than a signal that
    a time arrived.
    """

    tenant: str
    timer_id: str
    aggregate_type: str
    aggregate_id: str
    timer_kind: str
    fire_at: str
    fired_at: str
    payload: dict[str, Any]
    correlation_id: str | None = None
    causation_id: str | None = None

    @property
    def identity(self) -> tuple[str, str]:
        """`(tenant, timer_id)` — what a consumer deduplicates a redelivery on."""
        return (self.tenant, self.timer_id)


@dataclass(frozen=True)
class TimerRelayResult:
    """What one relay pass did. Counts derived from rows, never from intentions."""

    fired: tuple[str, ...] = ()
    failed: tuple[str, ...] = ()
    # Delivered, then found no longer SCHEDULED — cancelled underneath the relay. Neither fired
    # nor failed, and reported rather than folded into either.
    superseded: tuple[str, ...] = ()
    claimed: tuple[str, ...] = ()

    @property
    def fired_count(self) -> int:
        return len(self.fired)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_row_factory(conn: sqlite3.Connection, *, where: str) -> None:
    if getattr(conn, "row_factory", None) is not sqlite3.Row:
        raise TimerError(
            f"{where} requires a connection whose `row_factory` is `sqlite3.Row` "
            f"(WorkflowStore sets it; PostgresConnection reports it); columns are read by name."
        )


class DurableTimers:
    """The scheduling half. Layered on an EXISTING connection so it shares the caller's transaction."""

    def __init__(self, conn: sqlite3.Connection, *, tenant: str,
                 clock: Callable[[], datetime] | None = None) -> None:
        _require_row_factory(conn, where="DurableTimers")
        self._conn = conn
        self._tenant = require_tenant(tenant, context="DurableTimers")
        self._clock = clock or _utc_now

    @property
    def tenant(self) -> str:
        return self._tenant

    def _require_transaction(self, what: str) -> None:
        """### CANCELLING IS A STATE CHANGE, SO IT COMMITS WITH THE TRANSITION THAT CAUSED IT.

        The same rule as `schedule`, and for a symmetrical reason. A cancellation that commits
        separately from the terminal transition leaves one of two wrecks: an obligation closed with
        a LIVE deadline still armed — which later fires into a machine that has moved on — or a
        cancelled deadline with the obligation still OPEN, which then never ages at all.

        (It also stops a bare `UPDATE` leaving an implicit transaction open on the connection,
        which is how the first version of this method deadlocked the relay's `BEGIN IMMEDIATE` —
        found by exercising cancel and fire in one session.)
        """
        if not self._conn.in_transaction:
            raise TimerNotInTransaction(
                f"{what}() was called with no transaction open. A deadline is cancelled by the "
                f"transition that ended the obligation, and the two must commit together (M-23)."
            )

    def schedule(
        self,
        *,
        timer_id: str,
        aggregate_type: str,
        aggregate_id: str,
        timer_kind: str,
        fire_at: datetime | str,
        payload: dict[str, Any] | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
    ) -> str:
        """Write ONE deadline into the caller's OPEN transaction. Commits nothing.

        The caller's commit is what makes both the obligation and its deadline real, and the
        caller's rollback is what makes neither real. That is the whole point of the refusal below.
        """
        if not self._conn.in_transaction:
            raise TimerNotInTransaction(
                "schedule() was called with no transaction open. A deadline must be written in the "
                "SAME commit as the obligation it guards — open one with "
                "`conn.execute('BEGIN IMMEDIATE')`. A timer written in a commit of its own can be "
                "lost while the obligation survives, and an obligation with no timer never ages, "
                "never escalates and is never reported."
            )
        identifier = str(timer_id or "").strip()
        if not identifier:
            raise TimerError("a timer must be identifiable: `timer_id` is required")
        kind = str(timer_kind or "").strip()
        if not kind:
            raise TimerError(
                "`timer_kind` is required: it is what tells the MACHINE which of its guards this "
                "arrival concerns. A timer with no kind fires into nothing."
            )
        when = fire_at if isinstance(fire_at, str) else format_instant(fire_at)
        try:
            self._conn.execute(
                """
                INSERT INTO durable_timers (
                    tenant, timer_id, aggregate_type, aggregate_id, timer_kind, fire_at,
                    state, scheduled_at, fired_at, cancelled_at, cancel_reason, fire_attempts,
                    leased_by, lease_expires_at, correlation_id, causation_id, payload_json
                ) VALUES (?,?,?,?,?,?, 'SCHEDULED', ?, NULL, NULL, NULL, 0, NULL, NULL, ?,?,?)
                """,
                (self._tenant, identifier, aggregate_type, aggregate_id, kind, when,
                 format_instant(self._clock()), correlation_id, causation_id,
                 _dump(payload or {})),
            )
        except integrity_errors() as exc:
            raise DuplicateTimer(
                f"timer {identifier!r} already exists for tenant {self._tenant!r}: {exc}. A timer "
                f"identity is claimed once; re-arming a deadline means cancelling and scheduling a "
                f"new one, so that history records both."
            ) from exc
        return identifier

    def cancel(self, timer_id: str, *, reason: str) -> bool:
        """Cancel a SCHEDULED timer. Returns False when there was nothing to cancel.

        ### CANCELLED IS NOT FIRED, AND THE DIFFERENCE IS RECORDED. An obligation that ended before
        its deadline did not come due; collapsing the two would make "did this ever go overdue?"
        unanswerable from history. A reason is required for the same purpose.
        """
        self._require_transaction("cancel")
        if not str(reason or "").strip():
            raise TimerError("cancelling a deadline requires a reason: history records why")
        cursor = self._conn.execute(
            "UPDATE durable_timers SET state='CANCELLED', cancelled_at=?, cancel_reason=?, "
            "       leased_by=NULL, lease_expires_at=NULL "
            " WHERE tenant=? AND timer_id=? AND state='SCHEDULED'",
            (format_instant(self._clock()), reason, self._tenant, timer_id),
        )
        return cursor.rowcount > 0

    def cancel_for_aggregate(self, aggregate_type: str, aggregate_id: str, *, reason: str) -> int:
        """Cancel every SCHEDULED timer on one aggregate — what a terminal transition does."""
        self._require_transaction("cancel_for_aggregate")
        if not str(reason or "").strip():
            raise TimerError("cancelling deadlines requires a reason: history records why")
        cursor = self._conn.execute(
            "UPDATE durable_timers SET state='CANCELLED', cancelled_at=?, cancel_reason=?, "
            "       leased_by=NULL, lease_expires_at=NULL "
            " WHERE tenant=? AND aggregate_type=? AND aggregate_id=? AND state='SCHEDULED'",
            (format_instant(self._clock()), reason, self._tenant, aggregate_type, aggregate_id),
        )
        return cursor.rowcount

    # --- read side (no transaction required; these do not mutate) ------------------------------

    def due(self, *, now: datetime | None = None, limit: int | None = None) -> list[sqlite3.Row]:
        """Timers whose time has come.

        ### THIS IS A LOOKUP ON AN EXPLICIT SCHEDULE, NOT A SEARCH FOR THINGS THAT LOOK OLD. It
        reads `durable_timers` only — never a business table, never an age predicate over
        operational state. That distinction is M-36's whole content, and
        `test_no_component_scans_for_staleness` asserts it structurally rather than trusting it.
        """
        moment = format_instant(now or self._clock())
        sql = ("SELECT * FROM durable_timers "
               " WHERE tenant=? AND state='SCHEDULED' AND fire_at <= ? ORDER BY fire_at, timer_id")
        params: tuple[Any, ...] = (self._tenant, moment)
        if limit is not None:
            sql += " LIMIT ?"
            params = (*params, int(limit))
        return self._conn.execute(sql, params).fetchall()

    def get(self, timer_id: str) -> sqlite3.Row | None:
        return self._conn.execute(
            "SELECT * FROM durable_timers WHERE tenant=? AND timer_id=?",
            (self._tenant, timer_id)).fetchone()

    def scheduled_count(self) -> int:
        return int(self._conn.execute(
            "SELECT COUNT(*) FROM durable_timers WHERE tenant=? AND state='SCHEDULED'",
            (self._tenant,)).fetchone()[0])


class TimerRelay:
    """The firing half: claim, deliver, mark fired — three steps, on purpose.

    Separated so that a crash between any two is a case this class has an answer for. A crash after
    delivery and before marking re-delivers, which is why the trigger carries its own identity.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        tenant: str,
        handler: Callable[[TimerFired], None],
        relay_id: str,
        clock: Callable[[], datetime] | None = None,
        lease: timedelta = DEFAULT_TIMER_LEASE,
    ) -> None:
        if not callable(handler):
            raise TimerError(
                "TimerRelay requires a `handler`. There is deliberately no default: a relay that "
                "knew what a fired timer MEANS would be deciding transitions, and those belong to "
                "the machines (P6)."
            )
        _require_row_factory(conn, where="TimerRelay")
        self._conn = conn
        self._tenant = require_tenant(tenant, context="TimerRelay")
        self._handler = handler
        self._relay_id = str(relay_id or "").strip()
        if not self._relay_id:
            raise TimerError("a relay must be identifiable: `relay_id` is required")
        self._clock = clock or _utc_now
        self._lease = lease

    def run_once(self, *, max_timers: int = 64) -> TimerRelayResult:
        """Fire every timer whose time has come. Returns what actually happened."""
        claimed = self._claim(max_timers=max_timers)
        if not claimed:
            return TimerRelayResult()
        fired: list[str] = []
        failed: list[str] = []
        superseded: list[str] = []
        for row in claimed:
            trigger = TimerFired(
                tenant=row["tenant"], timer_id=row["timer_id"],
                aggregate_type=row["aggregate_type"], aggregate_id=row["aggregate_id"],
                timer_kind=row["timer_kind"], fire_at=row["fire_at"],
                fired_at=format_instant(self._clock()), payload=_load(row["payload_json"]),
                correlation_id=row["correlation_id"], causation_id=row["causation_id"],
            )
            try:
                # THE DELIVERY. Outside any transaction on purpose: holding a write lock across a
                # handler that may itself write is how a slow machine becomes a stalled database.
                self._handler(trigger)
            except BaseException:
                # The row stays SCHEDULED. Whether the machine acted is unknowable from here, which
                # is why re-delivery must be harmless rather than rare.
                failed.append(row["timer_id"])
                self._record_attempt(row["timer_id"])
                continue
            if self._mark_fired(row["timer_id"]):
                fired.append(row["timer_id"])
            else:
                # The timer was cancelled (or otherwise left SCHEDULED) underneath this delivery.
                # Neither fired nor failed: the handler DID see it, and history says it never came
                # due. Reported so a caller can reconcile rather than silently counted as either.
                superseded.append(row["timer_id"])
        return TimerRelayResult(fired=tuple(fired), failed=tuple(failed),
                                superseded=tuple(superseded),
                                claimed=tuple(r["timer_id"] for r in claimed))

    def drain(self, *, max_passes: int = 32) -> TimerRelayResult:
        """Passes until nothing more fires. Bounded, so a permanently failing handler stops."""
        fired: list[str] = []
        failed: list[str] = []
        for _ in range(max_passes):
            result = self.run_once()
            fired.extend(result.fired)
            failed.extend(result.failed)
            if not result.fired:
                break
        return TimerRelayResult(fired=tuple(fired), failed=tuple(failed))

    # --- the three steps -----------------------------------------------------------------------

    def _claim(self, *, max_timers: int) -> list[sqlite3.Row]:
        now = self._clock()
        now_text = format_instant(now)
        until = format_instant(now + self._lease)
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            rows = self._conn.execute(
                """
                SELECT * FROM durable_timers
                 WHERE tenant=? AND state='SCHEDULED' AND fire_at <= ?
                   AND (leased_by IS NULL OR lease_expires_at <= ?)
              ORDER BY fire_at, timer_id LIMIT ?
                """,
                (self._tenant, now_text, now_text, int(max_timers)),
            ).fetchall()
            leased = []
            for row in rows:
                # ### THE LEASE PREDICATE GOES IN THE **UPDATE**, and the rowcount decides — the
                # shape `OutboxRelay._claim` already uses. Putting it only in the SELECT made this
                # correct by accident of the surrounding serialisation rather than by the lease,
                # so a second relay could re-claim a row between the two statements.
                cursor = self._conn.execute(
                    "UPDATE durable_timers SET leased_by=?, lease_expires_at=? "
                    " WHERE tenant=? AND timer_id=? AND state='SCHEDULED' "
                    "   AND (leased_by IS NULL OR lease_expires_at <= ?)",
                    (self._relay_id, until, self._tenant, row["timer_id"], now_text),
                )
                if cursor.rowcount > 0:
                    leased.append(row)
            rows = leased
            self._conn.commit()
        except BaseException:
            self._conn.rollback()
            raise
        return rows

    def _mark_fired(self, timer_id: str) -> bool:
        """True when this timer was genuinely marked FIRED. ### THE ROWCOUNT IS THE POINT.

        `cancel` matches `state='SCHEDULED'` without considering the lease, so a timer can be
        cancelled while a relay holds it mid-delivery. The mark then matches ZERO rows — and an
        earlier version ignored that and reported the timer as fired anyway, so history said
        CANCELLED while the relay said fired. "Did this expectation ever go overdue?" answered NO
        for a machine that had already been told it did. Counts are derived from ROWS, never from
        intentions, and this is what makes that sentence true.
        """
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            cursor = self._conn.execute(
                "UPDATE durable_timers SET state='FIRED', fired_at=?, "
                "       fire_attempts=fire_attempts+1, leased_by=NULL, lease_expires_at=NULL "
                " WHERE tenant=? AND timer_id=? AND state='SCHEDULED'",
                (format_instant(self._clock()), self._tenant, timer_id),
            )
            marked = cursor.rowcount > 0
            self._conn.commit()
            return marked
        except BaseException:
            self._conn.rollback()
            raise

    def _record_attempt(self, timer_id: str) -> None:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                "UPDATE durable_timers SET fire_attempts=fire_attempts+1, "
                "       leased_by=NULL, lease_expires_at=NULL "
                " WHERE tenant=? AND timer_id=? AND state='SCHEDULED'",
                (self._tenant, timer_id),
            )
            self._conn.commit()
        except BaseException:
            self._conn.rollback()
            raise


def _dump(payload: dict[str, Any]) -> str:
    import json
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def _load(text: str) -> dict[str, Any]:
    import json
    try:
        loaded = json.loads(text or "{}")
    except ValueError:
        return {}
    return loaded if isinstance(loaded, dict) else {}
