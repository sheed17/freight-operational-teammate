"""THE dedup inbox (ADR-008 §2.6, M-24, M-26, `AC-ADPT-010`, `AC-EVT-004/005/006`).

    Every consumer MUST have a durable inbox keyed `(consumer_id, tenant_id, event_id)`, and MUST
    process the event and insert the inbox row **in one transaction**. — M-24

    *This is HOW "consumers must be idempotent" is achieved. Previously it was an instruction —
    and instructions are not mechanisms.*

An instruction to be idempotent is complied with by whoever remembers. A shared transaction with a
UNIQUE constraint is complied with by everyone, including the handler written in a hurry eighteen
months from now. That is the whole design: the handler is not asked to be careful.

THE SIX THINGS THAT HAPPEN TO AN ARRIVING EVENT, IN ORDER

1. **Malformed ⇒ REJECTED.** A missing or unparseable envelope field never reaches a handler.
   Validation lives in `EventEnvelope`; this module refuses what it will not construct.
2. **Cross-tenant ⇒ REJECTED, before anything else.** The tenant check runs before the transaction
   opens and before the handler is reachable, and it writes NOTHING — not even an inbox row,
   because writing a row keyed by the foreign tenant would itself be the cross-tenant write. [C-1]
   ### It runs BEFORE the contract check on purpose: whose event this is outranks what it says.
3. **Not a canonical fact ⇒ REJECTED** *(U5.3)*. The event is upcast to its contract's current
   version and checked against that contract — name, producer transition, aggregate, body, decision
   pins, actor authority. A handler is only ever handed a current, canonical representation. §6's
   mixed-version rule is honoured here: an additive field from a newer producer is IGNORED, not
   refused. ### A refusal writes NO inbox row, so a corrected redelivery of the same `event_id` can
   still apply — recording a rejection as a consumption would make the event permanently
   unconsumable, which is event loss wearing an idempotency guarantee.
4. **Already in the inbox ⇒ NO-OP.** Not an error. Not a second effect. `AC-RACE-007`,
   `AC-RACE-009`, `AC-ADPT-010` and §4 field 21 all land here.
5. **A reference that does not exist yet, or a version gap in a STRICT family ⇒ PARKED** in
   `pending_references`, with its arrival order and a TTL — neither dropped nor failed (M-26).
   Drained in arrival order the moment the referent appears; TTL expiry surfaces an owned problem.
6. **Otherwise ⇒ APPLIED**: the handler runs and the inbox row is inserted IN ONE COMMIT.

WHY THE HANDLER RUNS INSIDE THE TRANSACTION

Because `AC-RACE-008` and `AC-RACE-009` are the same mechanism read from two sides. A consumer
that crashes BEFORE the commit leaves no inbox row and no state change, so redelivery reprocesses
and reaches the same digest. A consumer that crashes AFTER the commit has both, so redelivery
finds the row and does nothing. There is no third outcome, and there is no window in which the
effect happened but the record of having consumed the event did not — which is the consumer-side
restatement of I10.

A handler that raises therefore rolls back its own writes AND its inbox row, and the event is
redelivered. That is deliberate: a handler failure must not be recorded as a successful
consumption, and "we logged the error and moved on" is how an event is lost.

WHAT THIS MODULE DOES NOT DECIDE

It does not know which aggregates exist — entities are P6. Existence is answered by a
`reference_resolver` the caller supplies; with none supplied, reference parking is OFF and the
module says so rather than pretending every reference resolves.

It does not mint an `ExceptionRaised` on TTL expiry. `expire_overdue` marks the row EXPIRED and
RETURNS the expired parks, each naming its accountable owner, for the caller to raise. M9 and the
`ExceptionRaised` contract are P6/U5.3; emitting a canonical event name from here would be this
unit writing another unit's contract.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from .event_contracts import UpcasterRegistry
from .event_contracts import read as read_canonical
from .event_envelope import (
    STRICT_ORDER_AGGREGATE_TYPES,
    EnvelopeError,
    EventEnvelope,
    format_instant,
)
from .tenant import require_tenant

# How long a dangling reference may stay parked before it becomes a human's problem. A day is long
# enough for an out-of-order producer, a slow migration or a retried batch, and short enough that
# nobody discovers it in a quarterly review. M-26 requires SOME finite TTL; it does not pick one.
DEFAULT_PARK_TTL = timedelta(hours=24)

# A bound on one drain cascade, so a pathological park graph cannot spin. Exceeding it is not
# silently tolerated — `drain_limit_reached` is reported on the result.
DEFAULT_DRAIN_LIMIT = 256


class ConsumeOutcome(str, Enum):
    """Every terminal answer the inbox can give. There is no `ERROR` and no `IGNORED`.

    A handler exception is not an outcome — it propagates, having rolled everything back, because
    swallowing it here would turn a failed consumption into a recorded one.
    """

    APPLIED = "APPLIED"
    DUPLICATE_NOOP = "DUPLICATE_NOOP"
    STALE_NOOP = "STALE_NOOP"
    PARKED_MISSING_AGGREGATE = "PARKED_MISSING_AGGREGATE"
    PARKED_VERSION_GAP = "PARKED_VERSION_GAP"
    ALREADY_PARKED = "ALREADY_PARKED"
    REJECTED_CROSS_TENANT = "REJECTED_CROSS_TENANT"
    REJECTED_MALFORMED = "REJECTED_MALFORMED"


@dataclass(frozen=True)
class ConsumeResult:
    """One consumption's outcome, with the drain cascade it triggered."""

    outcome: ConsumeOutcome
    event_id: str | None
    detail: str = ""
    drained: tuple[str, ...] = ()
    drain_limit_reached: bool = False

    @property
    def applied(self) -> bool:
        return self.outcome is ConsumeOutcome.APPLIED

    @property
    def is_noop(self) -> bool:
        """The three shapes of "this changed nothing", which acceptance treats as one answer."""
        return self.outcome in (
            ConsumeOutcome.DUPLICATE_NOOP, ConsumeOutcome.STALE_NOOP, ConsumeOutcome.ALREADY_PARKED,
        )


@dataclass(frozen=True)
class ParkedReference:
    """One event held back because something it names is not here yet."""

    tenant: str
    consumer_id: str
    event_id: str
    referenced_type: str
    referenced_id: str
    park_reason: str
    park_state: str
    arrival_sequence: int
    parked_at: str
    expires_at: str
    attempts: int
    accountable_owner_id: str | None
    envelope: EventEnvelope


@dataclass(frozen=True)
class ExpiredReference:
    """A park whose TTL ran out. It has an owner, and the caller must give it to them.

    M-26: *a permanently dangling reference is a real problem, and it gets a human — not a log
    line.* This object is that human's name plus the evidence, returned rather than logged.
    """

    park: ParkedReference
    expired_at: str

    @property
    def accountable_owner_id(self) -> str | None:
        return self.park.accountable_owner_id


class InboxError(RuntimeError):
    """The inbox cannot do what was asked."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# The type of the caller-supplied existence oracle: (aggregate_type, aggregate_id) -> bool.
ReferenceResolver = Callable[[str, str], bool]

# The type of a handler: it receives the envelope and does whatever ITS OWN guard says.
# The event does not instruct it (§9); the handler decides, and it decides inside our transaction.
Handler = Callable[[EventEnvelope], None]


class DedupInbox:
    """One consumer's durable inbox, on an existing connection.

    Bound to ONE `(tenant, consumer_id)` pair at construction. Not a convenience: an inbox that
    could be re-pointed at another tenant per call would put the tenant check in the caller's
    hands, and [C-1] is not a thing a caller should be able to get wrong.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        tenant: str,
        consumer_id: str,
        clock: Callable[[], datetime] | None = None,
        park_ttl: timedelta = DEFAULT_PARK_TTL,
        reference_resolver: ReferenceResolver | None = None,
        strict_aggregate_types: Iterable[str] = STRICT_ORDER_AGGREGATE_TYPES,
        observer: Callable[[dict[str, Any]], None] | None = None,
        upcasters: UpcasterRegistry | None = None,
    ) -> None:
        if getattr(conn, "row_factory", None) is not sqlite3.Row:
            raise InboxError(
                "DedupInbox reads columns by name and requires `row_factory = sqlite3.Row` "
                "(WorkflowStore sets it; PostgresConnection reports it)."
            )
        self._conn = conn
        self._tenant = require_tenant(tenant, context="DedupInbox")
        self._consumer_id = str(consumer_id or "").strip()
        if not self._consumer_id:
            raise InboxError(
                "a consumer must be identifiable: the dedup key is "
                "(tenant, consumer_id, event_id), and an anonymous consumer shares another "
                "consumer's dedup namespace."
            )
        self._clock = clock or _utc_now
        self._park_ttl = park_ttl
        if park_ttl <= timedelta(0):
            raise InboxError(
                "park_ttl must be positive: a park with no TTL is a place events go to be "
                "forgotten, which M-26 exists to forbid."
            )
        self._resolver = reference_resolver
        self._strict = frozenset(strict_aggregate_types)
        self._observer = observer or (lambda event: None)
        # The upcaster set this consumer reads history through. Defaulting to the process-wide
        # registry (`event_contracts.UPCASTERS`) is deliberate: a consumer that quietly used its own
        # empty registry would reject historical versions the rest of the system can read perfectly
        # well. Injectable so a test can exercise an evolution the canonical corpus has not had yet.
        self._upcasters = upcasters

    @property
    def tenant(self) -> str:
        return self._tenant

    @property
    def consumer_id(self) -> str:
        return self._consumer_id

    @property
    def reference_parking_enabled(self) -> bool:
        """False when no resolver was supplied — stated, never silently assumed to be True."""
        return self._resolver is not None

    def observe(self, event: dict[str, Any]) -> None:
        """Observability may describe control flow and may never alter it: exceptions swallowed."""
        try:
            self._observer(dict(event))
        except BaseException:
            pass

    # --- the entry point ------------------------------------------------------------------------

    def consume(
        self,
        envelope: EventEnvelope | Mapping[str, Any],
        handler: Handler,
        *,
        requires: Sequence[tuple[str, str]] = (),
        requires_existing: Sequence[tuple[str, str]] = (),
        accountable_owner_id: str | None = None,
    ) -> ConsumeResult:
        """Consume ONE event, exactly once, or say precisely why not.

        `requires` names references this event depends on beyond its own aggregate, as
        `(aggregate_type, aggregate_id)` pairs. When it is empty the pairs are derived from the
        envelope's `entity_versions` keys where they are written `type:id` — the SD-3 set is, by
        definition, "every entity referenced by a material fact, the target resource, and any
        gate-precondition entity" (§5), which is exactly the set whose absence should park.

        ### `requires_existing` SAYS THE ONE THING `requires` CANNOT, AND IT IS A SECOND PARAMETER
        ON PURPOSE. A `requires` pair equal to the event's own aggregate is SKIPPED — the creation
        event IS its aggregate arriving, and making it wait for itself would park every root event
        forever. But some events name their own aggregate as a genuine PREREQUISITE: M1's
        `HumanDecided` is a decision ABOUT a Work Item that must already exist, and it rides on
        `work_item:<id>` because that is its ordering key. Stated through `requires`, that demand
        was silently DROPPED — the handler then raised, the receipt rolled back with it, and the
        event redelivered forever. M-26's exact failure, reached by skipping M-26.

        So the caller states it here instead: these pairs are resolved WITHOUT the self-aggregate
        skip, and a missing one parks like any other (M-26). Overloading `requires` would have made
        every already-certified caller's meaning ambiguous — a pair equal to the own aggregate would
        have changed sense underneath callers who never asked. A caller that passes nothing here is
        unaffected, which is the whole reason this is a new name and not a new meaning.
        """
        if not callable(handler):
            raise InboxError("consume requires a handler callable")
        try:
            event = (envelope if isinstance(envelope, EventEnvelope)
                     else EventEnvelope.from_document(envelope))
        except EnvelopeError as exc:
            # Refused BEFORE any transaction and BEFORE the handler. A malformed envelope is not a
            # fact; there is nothing to be idempotent about.
            self.observe({
                "kind": "MalformedEventRejected", "consumer_id": self._consumer_id,
                "tenant": self._tenant, "reason": str(exc),
            })
            return ConsumeResult(
                outcome=ConsumeOutcome.REJECTED_MALFORMED, event_id=None, detail=str(exc),
            )

        # [C-1]. FIRST, and outside the transaction: a cross-tenant event must not cause a write of
        # any kind, and it must never reach a handler that might act on it.
        if event.tenant_id != self._tenant:
            self.observe({
                "kind": "CrossTenantAccessAttempted", "consumer_id": self._consumer_id,
                "inbox_tenant": self._tenant, "event_tenant": event.tenant_id,
                "event_id": event.event_id, "event_name": event.event_name,
            })
            return ConsumeResult(
                outcome=ConsumeOutcome.REJECTED_CROSS_TENANT, event_id=event.event_id,
                detail=(
                    f"event names tenant {event.tenant_id!r}; this inbox serves "
                    f"{self._tenant!r}. Rejected before the handler and before any write."
                ),
            )

        # THE CONTRACT GATE, and §6's "applied on read" (U5.3). AFTER the tenant check on purpose:
        # a foreign-tenant event must be refused before this consumer spends any judgement on what
        # it says, and [C-1] outranks every other question about it.
        #
        # `read_canonical` upcasts the event to its contract's current version and then validates in
        # CONSUMER mode — so a handler is only ever handed a current, canonical representation, and
        # an additive field from a newer producer is ignored rather than refused (§6's mixed-version
        # rule). Everything from here on uses the upcast event: parking, the inbox row and the
        # handler must all see the same representation, or a parked event would drain into a handler
        # in a form the pre-park checks never examined.
        try:
            event = read_canonical(event, upcasters=self._upcasters)
        except EnvelopeError as exc:
            # Refused before the transaction and before the handler, exactly like a malformed
            # envelope: an event that is not the fact its name promises is not a fact we consumed.
            self.observe({
                "kind": "NonCanonicalEventRejected", "consumer_id": self._consumer_id,
                "tenant": self._tenant, "event_id": event.event_id,
                "event_name": event.event_name, "reason": str(exc),
            })
            return ConsumeResult(
                outcome=ConsumeOutcome.REJECTED_MALFORMED, event_id=event.event_id, detail=str(exc),
            )

        result = self._consume_validated(
            event, handler, requires=tuple(requires),
            requires_existing=tuple(requires_existing),
            accountable_owner_id=accountable_owner_id,
        )
        if result.outcome is not ConsumeOutcome.APPLIED:
            return result
        drained, limited = self._drain_for(event, handler)
        return ConsumeResult(
            outcome=result.outcome, event_id=result.event_id, detail=result.detail,
            drained=drained, drain_limit_reached=limited,
        )

    # --- the one transaction --------------------------------------------------------------------

    def _consume_validated(
        self,
        event: EventEnvelope,
        handler: Handler,
        *,
        requires: tuple[tuple[str, str], ...],
        requires_existing: tuple[tuple[str, str], ...] = (),
        accountable_owner_id: str | None,
        draining: bool = False,
    ) -> ConsumeResult:
        now = self._clock()
        now_text = format_instant(now)
        conn = self._conn
        if conn.in_transaction:
            # The inbox OWNS this transaction, because M-24 requires the handler's writes and the
            # inbox row to share exactly one commit and only the owner of a transaction can
            # guarantee that. A caller (or a handler) that opened its own would decide the commit
            # boundary instead, and the guarantee would quietly become the caller's discipline.
            raise InboxError(
                "consume() was called with a transaction already open. The inbox opens and commits "
                "the transaction that carries BOTH the handler's writes and the inbox row (M-24); "
                "a handler must therefore do its writes on this connection and must not begin, "
                "commit or roll back."
            )
        # BEGIN IMMEDIATE takes the write lock before the first read, so the SELECT that decides
        # "have we seen this?" and the INSERT that records "we have now" cannot be interleaved by
        # another writer. Same idiom as `run_checkpoint`; same reason.
        conn.execute("BEGIN IMMEDIATE")
        try:
            seen = conn.execute(
                "SELECT outcome FROM event_inbox "
                " WHERE tenant = ? AND consumer_id = ? AND event_id = ?",
                (self._tenant, self._consumer_id, event.event_id),
            ).fetchone()
            if seen is not None:
                conn.rollback()
                self.observe({
                    "kind": "DuplicateDeliveryIgnored", "consumer_id": self._consumer_id,
                    "tenant": self._tenant, "event_id": event.event_id,
                    "prior_outcome": seen["outcome"],
                })
                return ConsumeResult(
                    outcome=ConsumeOutcome.DUPLICATE_NOOP, event_id=event.event_id,
                    detail=(
                        f"(tenant, consumer, event_id) is already recorded with outcome "
                        f"{seen['outcome']!r}. Redelivery is a no-op (M-24), not an error."
                    ),
                )
            parked = conn.execute(
                "SELECT park_state FROM pending_references "
                " WHERE tenant = ? AND consumer_id = ? AND event_id = ?",
                (self._tenant, self._consumer_id, event.event_id),
            ).fetchone()
            # A redelivery of an event we are already holding is counted and otherwise ignored —
            # unless this IS the drain replaying it, which is the one caller allowed past.
            if parked is not None and parked["park_state"] == "PARKED" and not draining:
                # ### UNLESS THE REDELIVERY *IS* THE DRAIN, WHICH FOR AN EXPLICIT PREREQUISITE IS
                # THE ONLY DRAIN THERE IS. `_drain_for` seeds itself from the aggregate of the
                # event it just APPLIED, so it can only ever release a cohort parked on somebody
                # ELSE's aggregate. An event held on a `requires_existing` pair is waiting for a
                # machine that no consumed event of this consumer applies — nothing would ever
                # seed a drain for it, and M-26's "drained the moment the referent appears" would
                # decay into "expired onto a human's desk a day later". So when the caller named
                # explicit prerequisites and every one of them now resolves, the park is closed
                # and the event goes on to be consumed, exactly once, in THIS transaction.
                # A caller that named none cannot reach this: the guard is false and the branch
                # below is the one it has always taken.
                released = bool(requires_existing) and self._first_unresolved_reference(
                    event, (), requires_existing,
                ) is None
                if not released:
                    conn.execute(
                        "UPDATE pending_references SET attempts = attempts + 1, "
                        "last_attempt_at = ? "
                        " WHERE tenant = ? AND consumer_id = ? AND event_id = ?",
                        (now_text, self._tenant, self._consumer_id, event.event_id),
                    )
                    conn.commit()
                    return ConsumeResult(
                        outcome=ConsumeOutcome.ALREADY_PARKED, event_id=event.event_id,
                        detail="already parked; the redelivery was counted, nothing else changed",
                    )
                self._resolve_park_locked(event.event_id, state="DRAINED", now=now_text)

            blocker = self._first_unresolved_reference(event, requires, requires_existing)
            if blocker is not None:
                self._park_locked(
                    event, referenced=blocker, reason="MISSING_AGGREGATE", now=now,
                    accountable_owner_id=accountable_owner_id,
                )
                conn.commit()
                self.observe({
                    "kind": "EventParked", "reason": "MISSING_AGGREGATE",
                    "consumer_id": self._consumer_id, "tenant": self._tenant,
                    "event_id": event.event_id, "referenced": list(blocker),
                })
                return ConsumeResult(
                    outcome=ConsumeOutcome.PARKED_MISSING_AGGREGATE, event_id=event.event_id,
                    detail=(
                        f"references {blocker[0]}:{blocker[1]}, which does not exist yet. Parked "
                        f"in arrival order with a TTL (M-26) — neither dropped nor failed."
                    ),
                )

            applied_version = self._cursor_locked(event.aggregate_type, event.aggregate_id)
            strict = event.aggregate_type in self._strict
            # ### THE TWO FAMILIES READ A LOW VERSION DIFFERENTLY, AND THE ASYMMETRY IS THE POINT.
            #
            # ORDER-TOLERANT (F5 Observation, F7, F9, F14): natural-key idempotent and explicitly
            # convergent, so a version below the high-water mark is a SUPERSEDED fact. Applying it
            # would let an older observation overwrite a newer one. Recorded as STALE_NOOP so it
            # is not reconsidered on every redelivery, and never handed to the handler.
            #
            # STRICT (F2, F3, F4, F11, F13): gap-parked below, so by the time the cursor reads N
            # every version up to N HAS been applied in order. A lower or equal version can
            # therefore only be a SIBLING co-emitted by a transition already applied - EF-2 emits
            # `GrantClaimed` AND `EffectAttempted` on one `effect_grant` at one version - and
            # dropping it would silently lose a fact from a version-monotonic history. Redelivery
            # of the SAME event is already handled above by `event_id`, so applying here cannot
            # double-apply anything.
            if not strict and event.aggregate_version < applied_version:
                self._record_inbox_locked(event, outcome="STALE_NOOP", now=now_text)
                conn.commit()
                return ConsumeResult(
                    outcome=ConsumeOutcome.STALE_NOOP, event_id=event.event_id,
                    detail=(
                        f"aggregate_version {event.aggregate_version} is below the applied "
                        f"high-water mark {applied_version} for "
                        f"{event.aggregate_type}:{event.aggregate_id}, and this family is "
                        f"order-tolerant and natural-key idempotent (events/registry.md §8)"
                    ),
                )
            if strict and event.aggregate_version > applied_version + 1:
                self._park_locked(
                    event, referenced=(event.aggregate_type, event.aggregate_id),
                    reason="VERSION_GAP", now=now, accountable_owner_id=accountable_owner_id,
                )
                conn.commit()
                self.observe({
                    "kind": "EventParked", "reason": "VERSION_GAP",
                    "consumer_id": self._consumer_id, "tenant": self._tenant,
                    "event_id": event.event_id, "expected_version": applied_version + 1,
                    "arrived_version": event.aggregate_version,
                })
                return ConsumeResult(
                    outcome=ConsumeOutcome.PARKED_VERSION_GAP, event_id=event.event_id,
                    detail=(
                        f"{event.aggregate_type} requires STRICT per-aggregate ordering "
                        f"(events/registry.md §8); expected version {applied_version + 1}, got "
                        f"{event.aggregate_version}. Parked until the gap fills."
                    ),
                )

            # THE ONE COMMIT: the inbox row, the handler's own writes, and the cursor.
            self._record_inbox_locked(event, outcome="APPLIED", now=now_text)
            handler(event)
            self._advance_cursor_locked(event, now=now_text)
            if draining:
                # The park is resolved in the SAME commit that applies it. Doing it afterwards
                # would leave a window in which the event is consumed but its park row still says
                # PARKED — and `expire_overdue` would then hand a human a problem that no longer
                # exists, which is worse than not reporting it.
                self._resolve_park_locked(event.event_id, state="DRAINED", now=now_text)
            conn.commit()
        except BaseException:
            # Includes a handler exception: its writes, the inbox row and the cursor all vanish
            # together, and the event will be redelivered. A failed consumption is never recorded
            # as a successful one.
            conn.rollback()
            raise
        self.observe({
            "kind": "EventApplied", "consumer_id": self._consumer_id, "tenant": self._tenant,
            "event_id": event.event_id, "event_name": event.event_name,
            "aggregate": f"{event.aggregate_type}:{event.aggregate_id}",
            "aggregate_version": event.aggregate_version,
        })
        return ConsumeResult(outcome=ConsumeOutcome.APPLIED, event_id=event.event_id)

    # --- parking and draining ---------------------------------------------------------------

    def _first_unresolved_reference(
        self,
        event: EventEnvelope,
        requires: tuple[tuple[str, str], ...],
        requires_existing: tuple[tuple[str, str], ...] = (),
    ) -> tuple[str, str] | None:
        if self._resolver is None:
            return None
        for aggregate_type, aggregate_id in requires_existing:
            # NO self-aggregate skip, and that is the entire point of the parameter: naming a pair
            # here IS the caller saying "this machine must already exist even though the event
            # rides on it". Checked first so the caller's own statement outranks any derivation.
            if not self._resolver(aggregate_type, aggregate_id):
                return (aggregate_type, aggregate_id)
        wanted = requires
        if not wanted and not requires_existing:
            # The `entity_versions` derivation is a DEFAULT for a caller who named nothing, not an
            # addition to what a caller did name. A caller that stated its prerequisites has stated
            # them, and inferring more would park events on references it deliberately did not ask
            # about.
            wanted = _references_from_entity_versions(event)
        for aggregate_type, aggregate_id in wanted:
            if (aggregate_type, aggregate_id) == (event.aggregate_type, event.aggregate_id):
                # An event never waits for its own aggregate: the creation event IS the aggregate
                # coming into existence, and requiring it to pre-exist would park every root event
                # forever. `requires_existing` is how a caller says otherwise for the events whose
                # own aggregate genuinely IS a prerequisite.
                continue
            if not self._resolver(aggregate_type, aggregate_id):
                return (aggregate_type, aggregate_id)
        return None

    def _park_locked(
        self,
        event: EventEnvelope,
        *,
        referenced: tuple[str, str],
        reason: str,
        now: datetime,
        accountable_owner_id: str | None,
    ) -> None:
        """Insert a park row. Caller holds the write lock and owns the commit."""
        arrival = int(self._conn.execute(
            "SELECT COALESCE(MAX(arrival_sequence), 0) + 1 FROM pending_references "
            " WHERE tenant = ? AND consumer_id = ?",
            (self._tenant, self._consumer_id),
        ).fetchone()[0])
        owner = accountable_owner_id or event.accountable_owner_id
        self._conn.execute(
            """
            INSERT INTO pending_references (
                tenant, consumer_id, event_id, referenced_type, referenced_id, park_reason,
                park_state, arrival_sequence, parked_at, expires_at, attempts, last_attempt_at,
                resolved_at, accountable_owner_id, envelope_json
            ) VALUES (?,?,?,?,?,?, 'PARKED', ?,?,?, 1, ?, NULL, ?, ?)
            ON CONFLICT (tenant, consumer_id, event_id) DO UPDATE SET
                attempts = attempts + 1,
                last_attempt_at = excluded.last_attempt_at
            """,
            (
                self._tenant, self._consumer_id, event.event_id, referenced[0], referenced[1],
                reason, arrival, format_instant(now), format_instant(now + self._park_ttl),
                format_instant(now), owner, event.to_json(),
            ),
        )

    def _drain_for(self, event: EventEnvelope, handler: Handler) -> tuple[tuple[str, ...], bool]:
        """After a successful apply, replay everything now unblocked — IN ARRIVAL ORDER (M-26).

        The worklist is a set of REFERENTS, not one: draining a parked event can itself bring an
        aggregate into existence, which unblocks a second cohort waiting on THAT one. Scanning only
        the originally-applied aggregate would drain the first link of such a chain and silently
        leave the rest parked until their TTLs expired.

        The scan restarts after every apply, because arrival order is re-evaluated each time, and
        the whole cascade is bounded by `DEFAULT_DRAIN_LIMIT` — reported on the result rather than
        swallowed, so a park graph that exhausts it is visible instead of merely slow.
        """
        drained: list[str] = []
        pending_referents: list[tuple[str, str]] = [(event.aggregate_type, event.aggregate_id)]
        seen_referents: set[tuple[str, str]] = set()
        steps = 0
        while pending_referents:
            referent = pending_referents.pop(0)
            if referent in seen_referents:
                continue
            seen_referents.add(referent)
            while True:
                steps += 1
                if steps > DEFAULT_DRAIN_LIMIT:
                    return tuple(drained), True
                progressed = False
                for park in self._parked_against(*referent):
                    if park.event_id in drained:
                        continue
                    outcome = self._consume_validated(
                        park.envelope, handler, requires=(),
                        accountable_owner_id=park.accountable_owner_id, draining=True,
                    )
                    if outcome.outcome in (
                        ConsumeOutcome.APPLIED, ConsumeOutcome.STALE_NOOP,
                        ConsumeOutcome.DUPLICATE_NOOP,
                    ):
                        # STALE and DUPLICATE resolve the park too: both mean "this event is
                        # finished with", and a park left behind for a finished event is exactly
                        # what would later expire onto somebody's desk for no reason.
                        if outcome.outcome is not ConsumeOutcome.APPLIED:
                            self._resolve_park(park.event_id, state="DRAINED")
                        drained.append(park.event_id)
                        unblocked = (park.envelope.aggregate_type, park.envelope.aggregate_id)
                        if unblocked not in seen_referents:
                            pending_referents.append(unblocked)
                        progressed = True
                        break
                if not progressed:
                    break
        return tuple(drained), False

    def _parked_against(self, referenced_type: str, referenced_id: str) -> list[ParkedReference]:
        rows = self._conn.execute(
            """
            SELECT * FROM pending_references
             WHERE tenant = ? AND consumer_id = ? AND park_state = 'PARKED'
               AND referenced_type = ? AND referenced_id = ?
          ORDER BY arrival_sequence
            """,
            (self._tenant, self._consumer_id, referenced_type, referenced_id),
        ).fetchall()
        return [_row_to_park(r) for r in rows]

    def _resolve_park_locked(self, event_id: str, *, state: str, now: str) -> None:
        """Caller holds the write lock and owns the commit."""
        self._conn.execute(
            "UPDATE pending_references SET park_state = ?, resolved_at = ? "
            " WHERE tenant = ? AND consumer_id = ? AND event_id = ? AND park_state = 'PARKED'",
            (state, now, self._tenant, self._consumer_id, event_id),
        )

    def _resolve_park(self, event_id: str, *, state: str) -> None:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._resolve_park_locked(event_id, state=state,
                                      now=format_instant(self._clock()))
            self._conn.commit()
        except BaseException:
            self._conn.rollback()
            raise

    # --- the cursor ---------------------------------------------------------------------------

    def _cursor_locked(self, aggregate_type: str, aggregate_id: str) -> int:
        row = self._conn.execute(
            "SELECT applied_version FROM inbox_aggregate_cursor "
            " WHERE tenant = ? AND consumer_id = ? AND aggregate_type = ? AND aggregate_id = ?",
            (self._tenant, self._consumer_id, aggregate_type, aggregate_id),
        ).fetchone()
        return int(row["applied_version"]) if row is not None else 0

    def _advance_cursor_locked(self, event: EventEnvelope, *, now: str) -> None:
        # ### THE TARGET COLUMN IS TABLE-QUALIFIED, AND THAT IS A PORTABILITY REQUIREMENT.
        # SQLite accepts a bare `applied_version` on the right of `DO UPDATE SET`; PostgreSQL
        # refuses it as ambiguous between the target row and `excluded`. Qualifying it is valid in
        # BOTH dialects, so the SQL is portable rather than translated — a rewrite rule for upsert
        # bodies would be a parser, and a parser is a thing that gets one case wrong later.
        # (`MAX(a, b)` is the scalar form; `persistence` renders it as PostgreSQL's `GREATEST`.)
        self._conn.execute(
            """
            INSERT INTO inbox_aggregate_cursor
                (tenant, consumer_id, aggregate_type, aggregate_id, applied_version, updated_at)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT (tenant, consumer_id, aggregate_type, aggregate_id) DO UPDATE SET
                applied_version = MAX(inbox_aggregate_cursor.applied_version,
                                      excluded.applied_version),
                updated_at = excluded.updated_at
            """,
            (self._tenant, self._consumer_id, event.aggregate_type, event.aggregate_id,
             event.aggregate_version, now),
        )

    def _record_inbox_locked(self, event: EventEnvelope, *, outcome: str, now: str) -> None:
        self._conn.execute(
            """
            INSERT INTO event_inbox (
                tenant, consumer_id, event_id, event_name, aggregate_type, aggregate_id,
                aggregate_version, envelope_digest, outcome, consumed_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (self._tenant, self._consumer_id, event.event_id, event.event_name,
             event.aggregate_type, event.aggregate_id, event.aggregate_version,
             event.digest(), outcome, now),
        )

    # --- read side and the TTL sweep ------------------------------------------------------------

    def parked(self) -> list[ParkedReference]:
        rows = self._conn.execute(
            "SELECT * FROM pending_references "
            " WHERE tenant = ? AND consumer_id = ? AND park_state = 'PARKED' "
            " ORDER BY arrival_sequence",
            (self._tenant, self._consumer_id),
        ).fetchall()
        return [_row_to_park(r) for r in rows]

    def seen(self, event_id: str) -> str | None:
        row = self._conn.execute(
            "SELECT outcome FROM event_inbox "
            " WHERE tenant = ? AND consumer_id = ? AND event_id = ?",
            (self._tenant, self._consumer_id, event_id),
        ).fetchone()
        return row["outcome"] if row is not None else None

    def expire_overdue(self) -> list[ExpiredReference]:
        """Mark every park past its TTL EXPIRED and RETURN them, each naming its owner.

        Returned, not logged, and not resolved here: M-26's failure mode is *an Exception with an
        accountable owner*, and this module cannot raise a canonical `ExceptionRaised` (that
        contract is U5.3's, and M9 is P6). The caller gets the owner and the evidence and is the
        one that can.
        """
        now = self._clock()
        now_text = format_instant(now)
        expired: list[ExpiredReference] = []
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            rows = self._conn.execute(
                "SELECT * FROM pending_references "
                " WHERE tenant = ? AND consumer_id = ? AND park_state = 'PARKED' "
                "   AND expires_at <= ? ORDER BY arrival_sequence",
                (self._tenant, self._consumer_id, now_text),
            ).fetchall()
            for row in rows:
                self._conn.execute(
                    "UPDATE pending_references SET park_state = 'EXPIRED', resolved_at = ? "
                    " WHERE tenant = ? AND consumer_id = ? AND event_id = ?",
                    (now_text, self._tenant, self._consumer_id, row["event_id"]),
                )
                expired.append(ExpiredReference(park=_row_to_park(row), expired_at=now_text))
            self._conn.commit()
        except BaseException:
            self._conn.rollback()
            raise
        for item in expired:
            self.observe({
                "kind": "PendingReferenceExpired", "consumer_id": self._consumer_id,
                "tenant": self._tenant, "event_id": item.park.event_id,
                "referenced": f"{item.park.referenced_type}:{item.park.referenced_id}",
                "accountable_owner_id": item.accountable_owner_id,
                "parked_at": item.park.parked_at, "expired_at": item.expired_at,
            })
        return expired


def _references_from_entity_versions(event: EventEnvelope) -> tuple[tuple[str, str], ...]:
    """The SD-3 pin set, read as references, where its keys are written `type:id`.

    A key that is not in `type:id` form is skipped rather than guessed at — inventing an aggregate
    type from a bare string would park events against aggregates that never existed.
    """
    if not event.entity_versions:
        return ()
    out: list[tuple[str, str]] = []
    for key in event.entity_versions:
        if not isinstance(key, str) or key.count(":") != 1:
            continue
        aggregate_type, aggregate_id = key.split(":", 1)
        if aggregate_type and aggregate_id:
            out.append((aggregate_type, aggregate_id))
    return tuple(out)


def _row_to_park(row: Any) -> ParkedReference:
    return ParkedReference(
        tenant=row["tenant"], consumer_id=row["consumer_id"], event_id=row["event_id"],
        referenced_type=row["referenced_type"], referenced_id=row["referenced_id"],
        park_reason=row["park_reason"], park_state=row["park_state"],
        arrival_sequence=int(row["arrival_sequence"]), parked_at=row["parked_at"],
        expires_at=row["expires_at"], attempts=int(row["attempts"]),
        accountable_owner_id=row["accountable_owner_id"],
        envelope=EventEnvelope.from_json(row["envelope_json"]),
    )
