"""THE transactional outbox and its relay (ADR-008 §2.5, M-23, `AC-RACE-006/007`).

THE ONE SENTENCE THIS MODULE EXISTS FOR

    `UPDATE machine_state (version++)` **+** `INSERT INTO event_outbox` — ONE transaction.
    Both, or neither.

The failure it forecloses is the dual write: a state change lands, the process dies, and the event
that was supposed to record it never happens. The action was taken and it is unrecorded — I10's
exact prohibition, and F-06. No amount of "remember to emit the event" prevents it, because the
window is between two commits and nobody is awake in it.

So `TransactionalOutbox.emit` **refuses to run outside an open transaction.** There is no supported
way to write an outbox row in a commit of its own; the API does not have one. That is the whole
mechanism, and it is why `emit` looks anticlimactic.

WHY AT-LEAST-ONCE IS THE HONEST POSTURE, NOT A CONCESSION

The relay publishes and then marks the row published. Those cannot be one act — the publish leaves
the database. Whatever the order, a crash in between is possible:

    crash BEFORE publish  ⇒ the row is still PENDING ⇒ recovery re-sends the IDENTICAL row,
                            byte-for-byte, same `event_id`.                    (`AC-RACE-006`)
    crash AFTER publish   ⇒ the row is still PENDING ⇒ recovery sends it AGAIN, and the consumer
                            has already seen it.                               (`AC-RACE-007`)

Both criteria end in the same place — **inbox no-op** — because the outbox does not try to solve
the second case. It cannot. It makes the second case CHEAP instead, by guaranteeing the re-send is
identical, and the dedup inbox (`event_inbox.py`) makes it free. That division is why U5.7 and U5.8
are one unit: neither half satisfies either criterion alone.

WHY THE RELAY LEASES WHOLE AGGREGATES

Strict per-aggregate ordering is REQUIRED for F2, F3, F4, F11 and F13 (`events/registry.md` §8).
If two relays each grabbed a slice of the pending rows, version 7 could reach a consumer before
version 6 — legal for the transport but a real problem for a version-monotonic machine. So a relay
leases every pending row of an aggregate or none of it, and no other relay may touch that aggregate
until the lease lapses. Ordering is then preserved by construction on the send side, and the inbox
parks a gap on the receive side. Two independent mechanisms, because delivery ordering is exactly
the kind of guarantee that quietly stops holding.

WHAT IT REFUSES TO COMMIT (U5.3)

`emit` validates the envelope against its canonical contract before the INSERT, inside the caller's
open transaction. So a non-canonical fact does not merely fail to publish — the state change it was
travelling with is rolled back too, because the commit that would have made both real never happens.
An event that is not a fact cannot take a state change with it. PRODUCER mode: this IS the producer,
and an emitter of ours that invents a payload field is a defect to catch in the commit that writes
it. (A CONSUMER reading that same event ignores unknown fields, per `events/registry.md` §6 — the
asymmetry is the specification's, and it lives in `event_contracts.py`.)

WHAT THIS MODULE DOES NOT DO

It does not publish anywhere by itself. `OutboxRelay` requires a `publish` callable from its
caller; there is no default sink, no network client, no adapter import, and no configuration that
turns one on. The relay moves rows from PENDING to PUBLISHED through a function someone else
supplied. **Nothing here enables a production write or an external effect** — an event is a FACT,
it is not authority (CLAUDE.md rule 9), and the effect boundary remains ADR-004's, untouched.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from .event_contracts import ValidationMode, validate
from .persistence import integrity_errors
from .event_envelope import EventEnvelope, format_instant
from .migrations.phase5_event_transport import STRICT_ORDER_ABORT
from .tenant import require_tenant

# How long a relay may hold a claim before another relay may assume it died. Short enough that a
# crashed relay does not stall delivery for long; long enough that a slow publish is not stolen
# mid-flight and delivered twice for no reason. Duplicate delivery is HARMLESS, never desirable.
DEFAULT_LEASE = timedelta(seconds=30)


class OutboxError(RuntimeError):
    """The outbox cannot do what was asked. Never silently degraded into a best effort."""


class OutboxNotInTransaction(OutboxError):
    """`emit` was called outside an open transaction.

    This is THE refusal of M-23. An outbox row written in its own commit is a dual write with an
    extra table: the state change it was supposed to be atomic with can still be lost, and the
    resulting event would assert a transition that never happened. There is no lenient mode and no
    `allow_autocommit=True`, because a flag is exactly how the guarantee would be turned off on a
    Friday.
    """


class DuplicateEmission(OutboxError):
    """A second event claimed an identity that is already emitted for this tenant.

    Either the same `event_id`, or the same `idempotency_identity` — §4's transition-natural key.
    Both mean the producing transition is being recorded twice, and the correct response is to
    fail the transition rather than to record a fact twice or to invent a new id for it.
    """


class OutboxTenantMismatch(OutboxError):
    """An envelope was offered to an outbox bound to a different tenant. [C-1]"""


class StrictOrderViolation(OutboxError):
    """Two DIFFERENT transitions claimed one (tenant, aggregate, version) in a strict family.

    Distinct from `DuplicateEmission` on purpose. SQLite reports a trigger `RAISE(ABORT)` and a
    UNIQUE violation through the same exception type, and telling the reader "this event is
    already emitted" would send them hunting for a duplicate that does not exist. What actually
    happened is that a version-monotonic aggregate's counter did not move.
    """


@dataclass(frozen=True)
class OutboxRow:
    """One durable emission record, as the relay sees it."""

    tenant: str
    event_id: str
    event_name: str
    aggregate_type: str
    aggregate_id: str
    aggregate_version: int
    sequence: int
    delivery_state: str
    publish_attempts: int
    envelope_digest: str
    envelope: EventEnvelope

    @property
    def aggregate_key(self) -> tuple[str, str]:
        return (self.aggregate_type, self.aggregate_id)


@dataclass(frozen=True)
class RelayResult:
    """What one relay pass did. Every count is derived from rows, never from intentions."""

    claimed: tuple[str, ...] = ()
    published: tuple[str, ...] = ()
    failed: tuple[str, ...] = ()
    withheld_for_order: tuple[str, ...] = ()
    aggregates: tuple[tuple[str, str], ...] = ()

    @property
    def published_count(self) -> int:
        return len(self.published)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_row_factory(conn: sqlite3.Connection, *, where: str) -> None:
    """Rows are read by NAME here. A positional row factory would silently mis-map columns.

    Checked rather than assumed because the mis-mapping would not raise — it would return the
    wrong string for the right column name, which is the class of bug that survives a test suite.
    """
    # Both supported backends satisfy this: `WorkflowStore` sets `sqlite3.Row`, and
    # `PostgresConnection` reports the same, because on BOTH backends the runtime reads columns by
    # NAME. A positional row factory would not raise — it would return the wrong string for the
    # right column name, which is the class of bug that survives a test suite.
    if getattr(conn, "row_factory", None) is not sqlite3.Row:
        raise OutboxError(
            f"{where} requires a connection whose `row_factory` is `sqlite3.Row` (WorkflowStore "
            f"sets it; PostgresConnection reports it); got {getattr(conn, 'row_factory', None)!r}. "
            f"Columns are read by name."
        )


class TransactionalOutbox:
    """The producer half. Layered on an EXISTING connection so it shares the caller's transaction.

    It takes a `sqlite3.Connection`, never a path — the point is that the state change and the
    event travel in the same transaction on the same connection, and a store that opened its own
    connection could not do that no matter how carefully it was called.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        tenant: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        _require_row_factory(conn, where="TransactionalOutbox")
        self._conn = conn
        self._tenant = require_tenant(tenant, context="TransactionalOutbox")
        self._clock = clock or _utc_now

    @property
    def tenant(self) -> str:
        return self._tenant

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    def emit(self, envelope: EventEnvelope) -> OutboxRow:
        """Write ONE event into the caller's OPEN transaction. Commits nothing.

        The caller's `conn.commit()` is what makes both the state change and this row real, and
        the caller's `rollback()` is what makes neither of them real. That is M-23, and it is the
        only thing this method is for.
        """
        if not isinstance(envelope, EventEnvelope):
            raise OutboxError(
                f"emit takes an EventEnvelope, got {type(envelope).__name__}. A dict is not an "
                f"envelope: the validation is the point."
            )
        if not self._conn.in_transaction:
            raise OutboxNotInTransaction(
                "emit() was called with no transaction open. The event must be written in the SAME "
                "commit as the state change that produced it (M-23) — open one with "
                "`conn.execute('BEGIN IMMEDIATE')`, or use `transactional_emit(...)`, which does "
                "it for you. Writing the event in a commit of its own is the dual write this "
                "table exists to abolish."
            )
        if envelope.tenant_id != self._tenant:
            raise OutboxTenantMismatch(
                f"the envelope names tenant {envelope.tenant_id!r}; this outbox is bound to "
                f"{self._tenant!r}. An event never crosses a tenant [C-1]."
            )
        # THE CONTRACT GATE (U5.3). Checked HERE, inside the caller's open transaction and before
        # the INSERT, so a non-canonical fact cannot reach the durable log at all: the caller's
        # commit is what would make it real, and this raises before that commit can happen. PRODUCER
        # mode, because this IS the producer — an emitter of ours that invents a payload field is a
        # defect to catch in the commit that writes it, not a fact to publish and regret.
        #
        # Fail-closed by construction rather than by option: there is no `validate=False`, for the
        # same reason `emit` has no `allow_autocommit=True`. A flag is how a guarantee gets turned
        # off on a Friday.
        validate(envelope, mode=ValidationMode.PRODUCER)
        # MAX+1 under the caller's write lock — the same per-tenant allocation idiom
        # `WorkflowStore._next_id` uses, and safe for the same reason: BEGIN IMMEDIATE serializes
        # writers, so no second allocator can be between the read and the insert.
        sequence = int(self._conn.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 FROM event_outbox WHERE tenant = ?",
            (self._tenant,),
        ).fetchone()[0])
        try:
            self._conn.execute(
                """
                INSERT INTO event_outbox (
                    tenant, event_id, event_name, event_version, envelope_schema_version,
                    aggregate_type, aggregate_id, aggregate_version, producer_transition_id,
                    correlation_id, causation_id, idempotency_identity, occurred_at, recorded_at,
                    envelope_json, envelope_digest, sequence, delivery_state, published_at,
                    publish_attempts, leased_by, lease_expires_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'PENDING', NULL, 0, NULL, NULL)
                """,
                (
                    envelope.tenant_id, envelope.event_id, envelope.event_name,
                    envelope.event_version, envelope.schema_version, envelope.aggregate_type,
                    envelope.aggregate_id, envelope.aggregate_version,
                    envelope.producer_transition_id, envelope.correlation_id,
                    envelope.causation_id, envelope.idempotency_identity, envelope.occurred_at,
                    envelope.recorded_at, envelope.to_json(), envelope.digest(), sequence,
                ),
            )
        except integrity_errors() as exc:
            if STRICT_ORDER_ABORT in str(exc):
                raise StrictOrderViolation(
                    f"{exc}. Aggregate {envelope.aggregate_type}:{envelope.aggregate_id} already "
                    f"holds version {envelope.aggregate_version} for a different transition, and "
                    f"{envelope.producer_transition_id} is trying to take it. Two events at ONE "
                    f"version are legal when ONE transition emits them (EF-2 emits GrantClaimed "
                    f"and EffectAttempted); two TRANSITIONS at one version means the version "
                    f"counter did not advance."
                ) from exc
            raise DuplicateEmission(
                f"this event is already emitted for tenant {self._tenant!r}: {exc}. "
                f"event_id={envelope.event_id!r}, "
                f"idempotency_identity={envelope.idempotency_identity!r}. "
                f"A producing transition records its fact ONCE; a retry re-sends the row that is "
                f"already here (§4), it does not write a second one."
            ) from exc
        return OutboxRow(
            tenant=envelope.tenant_id, event_id=envelope.event_id, event_name=envelope.event_name,
            aggregate_type=envelope.aggregate_type, aggregate_id=envelope.aggregate_id,
            aggregate_version=envelope.aggregate_version, sequence=sequence,
            delivery_state="PENDING", publish_attempts=0, envelope_digest=envelope.digest(),
            envelope=envelope,
        )

    def emit_all(self, envelopes: Sequence[EventEnvelope]) -> list[OutboxRow]:
        """Several events in the caller's one transaction — §11.4's "the EVENTS it emits"."""
        return [self.emit(e) for e in envelopes]

    # --- read-side helpers (no transaction required; these do not mutate) --------------------

    def pending(self, limit: int | None = None) -> list[OutboxRow]:
        sql = ("SELECT * FROM event_outbox WHERE tenant = ? AND delivery_state = 'PENDING' "
               "ORDER BY sequence")
        params: tuple[Any, ...] = (self._tenant,)
        if limit is not None:
            sql += " LIMIT ?"
            params = (*params, int(limit))
        return [_row_to_outbox_row(r) for r in self._conn.execute(sql, params).fetchall()]

    def published(self) -> list[OutboxRow]:
        return [_row_to_outbox_row(r) for r in self._conn.execute(
            "SELECT * FROM event_outbox WHERE tenant = ? AND delivery_state = 'PUBLISHED' "
            "ORDER BY sequence", (self._tenant,)).fetchall()]

    def get(self, event_id: str) -> OutboxRow | None:
        row = self._conn.execute(
            "SELECT * FROM event_outbox WHERE tenant = ? AND event_id = ?",
            (self._tenant, event_id),
        ).fetchone()
        return _row_to_outbox_row(row) if row is not None else None

    def count_unpublished(self) -> int:
        return int(self._conn.execute(
            "SELECT COUNT(*) FROM event_outbox WHERE tenant = ? AND delivery_state = 'PENDING'",
            (self._tenant,),
        ).fetchone()[0])


@dataclass
class EmitSession:
    """The handle `transactional_emit` yields: the connection, and the outbox bound to it."""

    conn: sqlite3.Connection
    outbox: TransactionalOutbox
    emitted: list[OutboxRow] = field(default_factory=list)

    def emit(self, envelope: EventEnvelope) -> OutboxRow:
        row = self.outbox.emit(envelope)
        self.emitted.append(row)
        return row

    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        """The state change, on the SAME connection and therefore in the SAME transaction."""
        return self.conn.execute(sql, tuple(params))


@contextmanager
def transactional_emit(
    conn: sqlite3.Connection,
    *,
    tenant: str,
    clock: Callable[[], datetime] | None = None,
) -> Iterator[EmitSession]:
    """ONE transaction carrying a state change and the events it emits. M-23, as a call.

    `BEGIN IMMEDIATE` takes the write lock before the first read, exactly as `run_checkpoint` and
    `WorkflowStore._write_txn` do — the repository has one transaction idiom and this is it. Any
    exception rolls the whole thing back, so a failure between the state write and the event write
    leaves NEITHER, which is the outcome M-23 names.
    """
    outbox = TransactionalOutbox(conn, tenant=tenant, clock=clock)
    conn.execute("BEGIN IMMEDIATE")
    session = EmitSession(conn=conn, outbox=outbox)
    try:
        yield session
    except BaseException:
        conn.rollback()
        raise
    else:
        conn.commit()


class OutboxRelay:
    """The publisher half: claim, publish, mark published — three steps, on purpose.

    The three steps are separated so that a crash between any two of them is a case this class has
    an answer for, rather than a case it has never been in.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        tenant: str,
        publish: Callable[[EventEnvelope], None],
        relay_id: str,
        clock: Callable[[], datetime] | None = None,
        lease: timedelta = DEFAULT_LEASE,
    ) -> None:
        if not callable(publish):
            raise OutboxError(
                "OutboxRelay requires a `publish` callable. There is deliberately no default sink: "
                "a relay that knew how to reach the outside world on its own would be an "
                "unreviewed egress path."
            )
        _require_row_factory(conn, where="OutboxRelay")
        self._conn = conn
        self._tenant = require_tenant(tenant, context="OutboxRelay")
        self._publish = publish
        self._relay_id = str(relay_id or "").strip()
        if not self._relay_id:
            raise OutboxError("a relay must be identifiable: `relay_id` is required")
        self._clock = clock or _utc_now
        self._lease = lease

    @property
    def relay_id(self) -> str:
        return self._relay_id

    def run_once(self, *, max_aggregates: int = 16) -> RelayResult:
        """Claim up to `max_aggregates` aggregates' pending rows, publish them, mark them.

        Returns what actually happened. A publish that raises stops THAT aggregate at the failing
        row and leaves the remainder pending — sending version 9 after version 8 failed would be
        the out-of-order delivery the lease exists to prevent.
        """
        claimed = self._claim(max_aggregates=max_aggregates)
        if not claimed:
            return RelayResult()
        published: list[str] = []
        failed: list[str] = []
        withheld: list[str] = []
        by_aggregate: dict[tuple[str, str], list[OutboxRow]] = {}
        for row in claimed:
            by_aggregate.setdefault(row.aggregate_key, []).append(row)
        for rows in by_aggregate.values():
            rows.sort(key=lambda r: (r.aggregate_version, r.sequence))
            blocked = False
            for row in rows:
                if blocked:
                    withheld.append(row.event_id)
                    self._release(row.event_id)
                    continue
                try:
                    # THE PUBLISH. Outside any transaction on purpose: holding a database write
                    # lock across a call that leaves the process is how a slow sink becomes a
                    # stalled database.
                    self._publish(row.envelope)
                except BaseException:
                    # The row stays PENDING. Whether the sink actually received it is unknowable
                    # from here — which is precisely why redelivery must be harmless rather than
                    # rare. `AC-RACE-007` is this branch.
                    failed.append(row.event_id)
                    self._record_attempt(row.event_id)
                    blocked = True
                    continue
                self._mark_published(row.event_id)
                published.append(row.event_id)
        return RelayResult(
            claimed=tuple(r.event_id for r in claimed),
            published=tuple(published),
            failed=tuple(failed),
            withheld_for_order=tuple(withheld),
            aggregates=tuple(sorted(by_aggregate)),
        )

    def drain(self, *, max_passes: int = 32) -> RelayResult:
        """Run passes until nothing more publishes. Bounded, so a permanently failing sink stops."""
        published: list[str] = []
        failed: list[str] = []
        for _ in range(max_passes):
            result = self.run_once()
            published.extend(result.published)
            failed.extend(result.failed)
            if not result.published:
                break
        return RelayResult(published=tuple(published), failed=tuple(failed))

    # --- the three steps ----------------------------------------------------------------------

    def _claim(self, *, max_aggregates: int) -> list[OutboxRow]:
        """Lease WHOLE aggregates, under the write lock. Two relays cannot claim the same row."""
        now = self._clock()
        now_text = format_instant(now)
        until = format_instant(now + self._lease)
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            # An aggregate is available when it has a pending row and NO row of it is under a live
            # lease held by anyone. Whole-aggregate exclusivity is what preserves §8's order.
            aggregates = self._conn.execute(
                """
                SELECT aggregate_type, aggregate_id, MIN(sequence) AS head
                  FROM event_outbox
                 WHERE tenant = ? AND delivery_state = 'PENDING'
              GROUP BY aggregate_type, aggregate_id
                HAVING SUM(CASE WHEN leased_by IS NOT NULL AND lease_expires_at > ? THEN 1 ELSE 0 END) = 0
              ORDER BY head
                 LIMIT ?
                """,
                (self._tenant, now_text, int(max_aggregates)),
            ).fetchall()
            rows: list[OutboxRow] = []
            for aggregate_type, aggregate_id, _head in aggregates:
                cursor = self._conn.execute(
                    """
                    UPDATE event_outbox
                       SET leased_by = ?, lease_expires_at = ?
                     WHERE tenant = ? AND aggregate_type = ? AND aggregate_id = ?
                       AND delivery_state = 'PENDING'
                       AND (leased_by IS NULL OR lease_expires_at <= ?)
                    """,
                    (self._relay_id, until, self._tenant, aggregate_type, aggregate_id, now_text),
                )
                if cursor.rowcount <= 0:
                    continue
                rows.extend(
                    _row_to_outbox_row(r) for r in self._conn.execute(
                        """
                        SELECT * FROM event_outbox
                         WHERE tenant = ? AND aggregate_type = ? AND aggregate_id = ?
                           AND delivery_state = 'PENDING' AND leased_by = ?
                      ORDER BY aggregate_version, sequence
                        """,
                        (self._tenant, aggregate_type, aggregate_id, self._relay_id),
                    ).fetchall()
                )
            self._conn.commit()
        except BaseException:
            self._conn.rollback()
            raise
        return rows

    def _mark_published(self, event_id: str) -> None:
        """The second commit. A crash before it means the row is re-sent — identically."""
        now = format_instant(self._clock())
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                """
                UPDATE event_outbox
                   SET delivery_state = 'PUBLISHED', published_at = ?,
                       publish_attempts = publish_attempts + 1,
                       leased_by = NULL, lease_expires_at = NULL
                 WHERE tenant = ? AND event_id = ? AND delivery_state = 'PENDING'
                """,
                (now, self._tenant, event_id),
            )
            self._conn.commit()
        except BaseException:
            self._conn.rollback()
            raise

    def _record_attempt(self, event_id: str) -> None:
        """A failed publish: count it, drop the lease, leave the row PENDING."""
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                """
                UPDATE event_outbox
                   SET publish_attempts = publish_attempts + 1,
                       leased_by = NULL, lease_expires_at = NULL
                 WHERE tenant = ? AND event_id = ? AND delivery_state = 'PENDING'
                """,
                (self._tenant, event_id),
            )
            self._conn.commit()
        except BaseException:
            self._conn.rollback()
            raise

    def _release(self, event_id: str) -> None:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                "UPDATE event_outbox SET leased_by = NULL, lease_expires_at = NULL "
                " WHERE tenant = ? AND event_id = ? AND delivery_state = 'PENDING'",
                (self._tenant, event_id),
            )
            self._conn.commit()
        except BaseException:
            self._conn.rollback()
            raise


def _row_to_outbox_row(row: Any) -> OutboxRow:
    envelope = EventEnvelope.from_json(row["envelope_json"])
    stored = row["envelope_digest"]
    if envelope.digest() != stored:
        # The canonical bytes ARE what is stored, so this can only mean the row was edited around
        # the immutability triggers, or the serializer changed under a live corpus. Both are
        # refusals: an event whose bytes no longer hash to their recorded digest is not evidence.
        raise OutboxError(
            f"outbox row {row['event_id']!r} does not match its recorded digest "
            f"({envelope.digest()} != {stored}). The stored envelope has been altered, or ev_v1 "
            f"changed without a version bump. Either way this row is no longer the fact that was "
            f"committed."
        )
    return OutboxRow(
        tenant=row["tenant"], event_id=row["event_id"], event_name=row["event_name"],
        aggregate_type=row["aggregate_type"], aggregate_id=row["aggregate_id"],
        aggregate_version=int(row["aggregate_version"]), sequence=int(row["sequence"]),
        delivery_state=row["delivery_state"], publish_attempts=int(row["publish_attempts"]),
        envelope_digest=stored, envelope=envelope,
    )
