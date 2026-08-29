"""Machine M8 — the Expectation: one `expectations` row per owed observation that tells "the thing
never came" apart from "we were not watching", and OWES something rather than authorizing anything.

    ### AN EXPECTATION IS A DURABLE COMMITMENT THAT SOMETHING SHOULD BE OBSERVED BY A DEADLINE.
    ### `OVERDUE` MEANS THE THING NEVER CAME AND WE CAN PROVE WE WERE WATCHING. `INDETERMINATE`
    ### MEANS THE DEADLINE PASSED AND WE WERE BLIND. THEY ARE DIFFERENT FACTS (I8).
    ### AN EXPECTATION OWES SOMETHING; IT DOES NOT AUTHORIZE ANYTHING (entity §4/§38/§40).

Almost everything that goes wrong in freight is a SILENCE — the POD never arrives, the carrier never
checks in, the appointment window passes with no update. A system that only reacts to inbound events
is structurally incapable of helping with any of it. The Expectation is the mechanism for time-driven
and non-event work, and it carries exactly one hard honesty rule, which is the whole reason this unit
is not a bare timer:

    ### WE DO NOT ACCUSE A COUNTERPARTY OF A FAILURE THAT WAS OURS.

An Expectation may become `OVERDUE` ONLY where the declared observation channel was demonstrably
HEALTHY across the required window, proved by a `coverage_ref`. If the channel was down, or the
coverage is unknown, or there is NO coverage record at all, the honest state is `INDETERMINATE` — it
fails toward blindness, the safe direction (M-32). ### THE ABSENCE OF A COVERAGE RECORD IS NOT HEALTH.

### WHAT THIS MACHINE OWNS, AND WHAT IT ONLY FEEDS.

It owns the six states and the EX-1…EX-7 transitions of `08-expectation.machine.md` §14, and it is the
canonical PRODUCER of the seven already-registered F8 `Expectation*` events on the `expectation`
aggregate. It rides P5's transactional outbox, dedup inbox and durable timers exactly as M3…M7 do. The
deadline is a DURABLE TIMER (machine §37, M-36) scheduled in the SAME commit as the raise — no
in-memory sleep, no background sweep, no second timer mechanism. The `TimerFired` arrival + the
coverage read + the resulting state + its event are ONE commit (entity §15, [C-2]).

### THE HONESTY SPLIT IS STRUCTURAL, NOT A PYTHON BRANCH. `coverage_health` is tied to the real
`observation_coverage` row by a composite FK, and a database CHECK requires it to be HEALTHY for
`OVERDUE`, so `OVERDUE` without a healthy `coverage_ref` is structurally impossible (entity §16/§37).
The machine reads coverage from the persisted record — never from a model, a counterparty or a
parameter content could set — and CONFIDENCE is never a guard input: it never turns `INDETERMINATE`
into `OVERDUE`, at any value including 1.0 (GR-8).

### IT OWES, IT DOES NOT AUTHORIZE (task §3.9). `native_projection()` projects an undischarged
Expectation into the checkpoint's EXISTING `ProvenancedFact(evidence_condition='unknown')` WITHOUT
importing the checkpoint — an owed obligation makes a field `unknown`, which step 4 treats as
not-`consistent`. `unknown` IS NOT `conflicting` (I8): an undischarged Expectation is MISSING
information, not contradictory information — mapping it to CONFLICTING would make M8 a Conflict
detector, and M7 already owns that. P3 stays the sole gate minter and M3 the single effect authority
(CLAUDE.md rule 17); M8 mints no gate decision.

### THE M9 EXCEPTION SEAM DOES NOT MINT M9's CONTRACT (### M8-AQ-1). F8 records M9 as the consumer of
`ExpectationOverdue`, `ExpectationIndeterminate` and `ExpectationExpired`. M9 is the next unbuilt
machine and its exception event is M9's contract. Like M5's landed UNPARSEABLE/UNBOUND seam, M8 emits
its OWN registered F8 event into the outbox, atomically with the transition, and leaves a DURABLE,
RETAINED row that NAMES AN ACCOUNTABLE HUMAN — nothing is silent. It mints no M9 event, builds no
`exceptions` table, and implements no `EC-*`. This module names the seam in PROSE, never by the M9
contract's registered identifier.

### THE F14 TRIPWIRE THAT IS MINE (task §3.10). `IllegalTransitionAttempted` (GR-1, mandatory) on
every illegal `(state, trigger)`, to audit AND security — cancelling an INDETERMINATE expectation,
expiring a RAISED one, forcing OVERDUE without healthy coverage, and evaluating a window in UTC are
the shapes machine §15 and the EX-6/EX-7 from-sets name by hand. NOT mine:
`ProvenanceStrengtheningAttempted` (P7's), `OwnerAssertedOverwriteAttempted` (M6's),
`CrossTenantAccessAttempted` (the inbox's).

### IT SHIPS DARK. Nothing under `src/freight_recon/` imports this module; the only script that may is
`scripts/probe_phase6_expectation.py`. It joins no importer, tracking service, SLA dashboard or live
channel, authorizes no effect, mints no gate decision, and the production `GateRegistry` stays EMPTY.
M8's product form is a live tracking / SLA / "what is late" product — so that product is precisely the
thing that does not arrive with it. It builds NO channel health probe, poller or coverage importer:
the coverage rows M8 is verified against are written by the probe and the tests.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .event_contracts import CONTRACTS
from .event_envelope import EventEnvelope, format_instant
from .event_inbox import ConsumeResult, DedupInbox
from .event_timers import DurableTimers, TimerFired
from .migrations.phase6_expectations import (
    COVERAGE_HEALTH,
    EXPECTATION_STATES,
    HEALTHY_COVERAGE,
    HUMAN_OWNED_EXPECTATION_STATES,
    SUBJECT_KINDS,
    TERMINAL_EXPECTATION_STATES,
)
from .tenant import require_tenant

# The aggregate this machine owns. `expectation` is NOT in `STRICT_ORDER_AGGREGATE_TYPES` (F8 is
# ORDER-TOLERANT, events/registry.md §8 — F8 appears in neither the strict nor the tolerant list, and
# event_contracts_data.json resolves all seven F8 contracts to strict_order:false). ### M8-AQ-5 is
# REPORTED: the family file calls discharge/expiry "STRICT"; §8's per-family lists do not name F8 at
# all. Every reading agrees the universal ordering key holds within one aggregate and a discharge
# arriving before its raise is PARKED — which is what this machine builds, and it declares NO
# previous_aggregate_version, exactly as M5 (the other order-tolerant P6 machine) does.
AGGREGATE_TYPE = "expectation"

# entity §5 — the Expectation Service raises and owns expectations.
PRODUCER_COMPONENT = "expectation_service"

# The one consumer identity M8 presents to the dedup inbox. Fixed, because the dedup key is
# `(tenant, consumer_id, event_id)` and a renamed consumer would re-arm every duplicate.
CONSUMER_ID = "m8-expectation"

# GR-1's producer id for `IllegalTransitionAttempted` — the RULE, not a transition. Identical to
# M1..M7's, for the same reason.
ILLEGAL_TRANSITION_PRODUCER = "GR-1"

# A refusal advances no version; two refusals against one expectation at one version would otherwise
# collide on one idempotency identity — the poison-loop defect M1 shipped. Applied here.
ILLEGAL_ATTEMPT_IDENTITY_PREFIX = "ita_v1"

# ### THE TWO DURABLE-TIMER KINDS, AND ONLY TWO (machine §37, M-36). The DEADLINE timer is armed at the
# raise and fires EX-3/EX-3i; the TERMINAL-AGE timer is armed when the expectation becomes
# OVERDUE/INDETERMINATE and fires EX-7. Neither is a sweep; both ride P5's existing substrate. No
# timer_kind reaches DISCHARGED or CANCELLED — those are event-driven, never timer-driven.
TIMER_KIND_DEADLINE = "expectation_deadline"
TIMER_KIND_TERMINAL_AGE = "expectation_terminal_age"

HUMAN = "HUMAN"


class M8Error(RuntimeError):
    """This machine will not do what was asked. Never degraded into a partial transition."""


class UnknownExpectation(M8Error):
    """No `expectations` row with this id exists FOR THIS TENANT. Indistinguishable from "belongs to
    another tenant" on purpose — [C-1] rejects a cross-tenant question rather than answering it."""


class GuardNotSatisfied(M8Error):
    """The (state, trigger) pair IS legal here and a precondition is false. No event is emitted."""


class IllegalTransition(M8Error):
    """GR-1 / [C-4]. The (state, trigger) pair is not enumerated (or §15 forbids the shape). Raised
    AFTER `IllegalTransitionAttempted` is recorded, which is the point of recording it."""


class StateConflict(M8Error):
    """A state-guarded UPDATE matched zero rows: the expectation moved under us (GR-3). Reload."""


class MalformedExpectation(M8Error):
    """The inputs to a raise are not a canonical expectation — an empty subject, a missing channel or
    deadline, an unknown facility timezone, a subject_kind off the closed set. Fail closed; nothing is
    persisted."""


# --------------------------------------------------------------------------------- the state set

# ### THESE ENUM CLASS NAMES ARE DELIBERATELY PREFIXED `Ex…`, NOT `Expectation…`. The permanent
# verification scenario flags any identifier beginning `Expectation` + a capital that is not one of the
# seven registered F8 event contracts — an internal type sharing that shape reads as an unregistered
# event name minted in the machine (registry.md §5: no machine may define a local synonym). So the six
# states carry a machine-local `Ex` prefix, and the only `Expectation`+capital identifiers in this file
# are the seven registered F8 event names.
class ExState(str, Enum):
    RAISED = "RAISED"
    DISCHARGED = "DISCHARGED"
    OVERDUE = "OVERDUE"
    INDETERMINATE = "INDETERMINATE"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class Trigger(str, Enum):
    """The closed set of driving facts, named from §14's triggers and §33's "Consumes", plus the
    illegal shapes §15 and the EX-6/EX-7 from-sets name by hand so GR-1 answers them uniformly.

    The values avoid any `Expectation[A-Z]` spelling for the same reason the state enum does — an
    internal token sharing that shape reads as an unregistered event minted here."""

    OBSERVATION_BOUND = "ObservationBound"          # EX-2 / EX-4
    TIMER_FIRED = "TimerFired"                        # EX-3 / EX-3i / EX-7
    DEADLINE_CHANGED = "DeadlineChanged"              # EX-5
    REASON_DISAPPEARED = "ReasonDisappeared"          # EX-6
    # ### THE ILLEGAL SHAPES (machine §15, EX-6/EX-7 from-sets). Cancelling an INDETERMINATE, expiring
    # a RAISED, forcing OVERDUE with no healthy coverage, and evaluating a window in the wrong timezone.
    CANCEL_INDETERMINATE = "CancelIndeterminate"
    EXPIRE_RAISED = "ExpireRaised"
    OVERDUE_WITHOUT_COVERAGE = "OverdueWithoutCoverage"
    UTC_WINDOW = "WindowEvaluatedInUtc"


TERMINAL_STATES: frozenset[ExState] = frozenset(
    ExState(s) for s in TERMINAL_EXPECTATION_STATES)
HUMAN_OWNED_STATES: frozenset[ExState] = frozenset(
    ExState(s) for s in HUMAN_OWNED_EXPECTATION_STATES)

# The seven F8 contracts this machine MINTS — exactly the registered set, no eighth `Expectation*`
# name. A TimedOut / Missed / Closed variant is what an invented eighth event would be called; none is
# here, and the source contains no `Expectation`+capital token outside these seven registered names —
# the permanent scenario's unregistered-name sweep reads exactly that.
PRODUCED_CONTRACTS: frozenset[str] = frozenset(
    ("ExpectationRaised", "ExpectationDischarged", "ExpectationOverdue", "ExpectationIndeterminate",
     "ExpectationReVersioned", "ExpectationCancelled", "ExpectationExpired"))

# ### THE M8-OWNED SEAM RECORD (### M8-AQ-1). F8 records M9 (Exception) as the consumer of three M8
# events; M9 is the next unbuilt machine and its exception event is M9's contract. M8 emits its OWN
# registered F8 event and leaves a durable, human-owned row — it mints no M9 event and builds no
# exceptions table. Named in PROSE, never by the M9 contract's registered identifier, exactly as M5's
# landed observation.py records the same shape.
M8_EXCEPTION_SEAM = (
    "An OVERDUE / INDETERMINATE / EXPIRED expectation is a durable, retained, human-owned row that a "
    "downstream exception machine consumes; that machine is the next unbuilt one, and its exception "
    "event is its own contract. M8 emits its registered F8 event into the outbox atomically with the "
    "transition and leaves the row naming an accountable human — nothing is silent, and M8 mints no "
    "foreign contract and builds no exceptions table. This is M5's landed UNPARSEABLE/UNBOUND seam."
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def facility_local_deadline(appointment_wall: datetime, facility_timezone: str) -> datetime:
    """### CONVERT A FACILITY-LOCAL WALL-CLOCK APPOINTMENT TO ITS UTC INSTANT, HONOURING DST (entity
    §42, machine §38, F-25).

    A 17:00 delivery appointment in Denver is localised in `America/Denver` — which is UTC-7 in winter
    and UTC-6 under daylight time — NOT read as 17:00 UTC. The wall time must be NAIVE (a facility
    clock reading); a tz-aware value is already committed to an offset and cannot be re-localised. An
    unknown zone fails closed. Evaluating the window in UTC instead of facility-local is ILLEGAL
    (machine §15) — this function does the correct thing, and the machine records the illegal attempt
    where a caller asks for the wrong one."""
    if appointment_wall.tzinfo is not None:
        raise MalformedExpectation(
            "a facility appointment window is a NAIVE wall-clock reading localised in the facility's "
            "timezone; a tz-aware value has already chosen an offset and cannot honour a DST boundary.")
    try:
        zone = ZoneInfo(facility_timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise MalformedExpectation(
            f"originating_timezone {facility_timezone!r} is not a known IANA facility zone ({exc}); a "
            f"deadline cannot be evaluated facility-local without one (F-25).") from exc
    return appointment_wall.replace(tzinfo=zone).astimezone(timezone.utc)


# ------------------------------------------------------------------------------------ the row

@dataclass(frozen=True)
class Coverage:
    """One `observation_coverage` row, as the machine reads it. A statement about a CHANNEL over a
    WINDOW — never about a fact. `health` is one of the closed vocabulary; the absence of any row is
    NOT a value here, it is modelled as no Coverage at all and read as INDETERMINATE (M-32)."""

    tenant: str
    coverage_id: str
    channel: str
    window_start: str
    window_end: str
    health: str
    probe_source: str


@dataclass(frozen=True)
class Expectation:
    """One `expectations` row, as the machine reads it."""

    tenant: str
    expectation_id: str
    subject_ref: str
    subject_kind: str
    expected_type: str
    expected_source: str
    expectation_key: str
    deadline_utc: str
    originating_timezone: str
    state: ExState
    version: int
    discharge_observation_id: str | None
    late: int | None
    coverage_ref: str | None
    coverage_health: str | None
    coverage_gap: str | None
    overdue_at: str | None
    owner_id: str | None
    deadline_history: str | None
    terminal_age_ms: int | None
    proposed_confidence: str | None
    created_at: str

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    @property
    def is_owed(self) -> bool:
        """### AN OWED-BUT-UNDISCHARGED EXPECTATION (RAISED / OVERDUE / INDETERMINATE). A DISCHARGED
        one is satisfied; a CANCELLED / EXPIRED one is no longer owed."""
        return self.state in (ExState.RAISED, ExState.OVERDUE, ExState.INDETERMINATE)

    @property
    def deadline_history_list(self) -> list[str]:
        try:
            loaded = json.loads(self.deadline_history or "[]")
        except ValueError:
            return []
        return [str(x) for x in loaded] if isinstance(loaded, list) else []

    def native_projection(self) -> "NativeExpectationProjection":
        """### THE SEAM WITH THE CHECKPOINT (task §3.9, entity §38). Project this expectation into the
        shape step 4 reads (`checkpoint.ProvenancedFact`) WITHOUT importing the checkpoint. An
        owed-but-undischarged expectation makes its field `unknown`, and step 4 refuses a fact whose
        evidence_condition is not `consistent`. ### `unknown` IS NOT `conflicting` (I8): this is
        MISSING information, not contradictory information — M8 FEEDS the one gate authority, it never
        duplicates it, and it is not a Conflict detector."""
        owed = self.is_owed
        return NativeExpectationProjection(
            field=self.expected_type, subject_ref=self.subject_ref,
            evidence_condition=("unknown" if owed else "consistent"), owed=owed)


@dataclass(frozen=True)
class NativeExpectationProjection:
    """The fields `checkpoint.ProvenancedFact` reads, projected from an M8 expectation without
    importing the checkpoint. The probe builds the real `ProvenancedFact` from these and shows step 4
    refuses an `unknown` — an INPUT to the gate, never a gate."""

    field: str
    subject_ref: str
    evidence_condition: str            # 'unknown' while owed, 'consistent' once discharged
    owed: bool


@dataclass(frozen=True)
class TransitionResult:
    transition_id: str                 # the machine row: EX-1..EX-7
    expectation: Expectation
    from_state: ExState | None
    to_state: ExState
    event_ids: tuple[str, ...] = ()
    event_names: tuple[str, ...] = ()
    event_producer: str | None = None
    coalesced: bool = False            # a raise that found an existing live expectation for the key
    late: bool = False                 # a discharge from OVERDUE/INDETERMINATE (EX-4)


@dataclass(frozen=True)
class ReconstructedExpectation:
    """A full-history fold of one expectation's event stream — sandboxed, zero authority (GR-11, K-3).

    ### THE HONESTY SPLIT IS REBUILT FROM THE RECORDED COVERAGE, NOT THE LIVE CHANNEL (entity §34). The
    OVERDUE-vs-INDETERMINATE verdict is read from WHICH event was recorded at the time, so a rebuild
    reaches the same verdict next Tuesday regardless of the channel's state now. Every count is of what
    the REBUILD created, which is always zero."""

    expectation_id: str
    state: ExState | None
    coverage_basis: str | None         # the coverage_ref / coverage_gap the recorded event carried
    new_authority: int = 0
    external_effects: int = 0
    coverage_rewritten: int = 0
    state_flips: int = 0


@dataclass(frozen=True)
class ConsumedTransition:
    consume: ConsumeResult
    transition: TransitionResult | None = None
    refusal: str | None = None

    @property
    def moved(self) -> bool:
        return self.transition is not None


# --------------------------------------------------------------------------------- the machine

class M8Machine:
    """M8, on an existing connection, bound to ONE tenant. Bound at construction so a caller cannot
    re-point it at another tenant and put [C-1] in its own hands."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        tenant: str,
        clock: Callable[[], datetime] | None = None,
        producer_component: str = PRODUCER_COMPONENT,
    ) -> None:
        if getattr(conn, "row_factory", None) is not sqlite3.Row:
            raise M8Error(
                "M8Machine reads columns by name and requires `row_factory = sqlite3.Row`.")
        self._conn = conn
        self._tenant = require_tenant(tenant, context="M8Machine")
        self._clock = clock or _utc_now
        self._component = producer_component

    @property
    def tenant(self) -> str:
        return self._tenant

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    # --- reads -----------------------------------------------------------------------------------

    def get(self, expectation_id: str) -> Expectation | None:
        row = self._conn.execute(
            "SELECT * FROM expectations WHERE tenant = ? AND expectation_id = ?",
            (self._tenant, expectation_id),
        ).fetchone()
        return _row_to_expectation(row) if row is not None else None

    def require(self, expectation_id: str) -> Expectation:
        found = self.get(expectation_id)
        if found is None:
            raise UnknownExpectation(
                f"no expectation {expectation_id!r} for tenant {self._tenant!r}. This machine does not "
                f"look outside its tenant to find out whether it exists elsewhere ([C-1]).")
        return found

    def live_expectation_for(self, subject_ref: str, expected_type: str) -> Expectation | None:
        """### THE DUPLICATE-PREVENTION READ (entity §17). At most one RAISED row can match — the
        partial unique index guarantees it."""
        key = _expectation_key(subject_ref, expected_type)
        row = self._conn.execute(
            "SELECT * FROM expectations WHERE tenant = ? AND expectation_key = ? AND state = 'RAISED'",
            (self._tenant, key),
        ).fetchone()
        return _row_to_expectation(row) if row is not None else None

    # --- EX-1: the raise (and its coalescing) -----------------------------------------------------

    def raise_expectation(
        self,
        *,
        subject_ref: str,
        expected_type: str,
        expected_source: str,
        owner_id: str,
        originating_timezone: str,
        deadline_utc: datetime | str | None = None,
        appointment_local: datetime | None = None,
        subject_kind: str = "entity",
        terminal_age_ms: int | None = None,
        proposed_confidence: float | str | None = None,
        expectation_id: str | None = None,
        actor_id: str = "expectation",
        actor_kind: str = "system",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
        schedule_timer: bool = True,
        evaluate_in_utc: bool = False,
    ) -> TransitionResult:
        """EX-1 — ### RAISE OVER A DECLARED CHANNEL, STORE THE DEADLINE IN UTC WITH THE FACILITY
        TIMEZONE RETAINED, AND SCHEDULE THE DURABLE DEADLINE TIMER IN ONE COMMIT (entity §15/§21,
        machine §35/§37).

        The `expectations` row (state RAISED) and the durable deadline timer are written in ONE
        transaction — a deadline written in a commit of its own can be lost while the obligation
        survives, and an obligation with no timer never ages. If a RAISED expectation already exists
        for `(tenant, subject_ref, expected_type)` the partial unique index refuses the insert and the
        raise COALESCES onto it — a second raise never creates a second live expectation (entity §17)."""
        subject = _require_text(subject_ref, "subject_ref")
        etype = _require_text(expected_type, "expected_type")
        source = _require_text(expected_source, "expected_source")
        tz = _require_text(originating_timezone, "originating_timezone")
        if subject_kind not in SUBJECT_KINDS:
            raise MalformedExpectation(
                f"subject_kind {subject_kind!r} is not one of {list(SUBJECT_KINDS)} (### M8-AQ-4): the "
                f"observation kind is FK-backed into observations (M5), the entity kind is a freight "
                f"projection (P9+). There is no third.")
        deadline_dt = self._resolve_deadline(
            deadline_utc=deadline_utc, appointment_local=appointment_local,
            originating_timezone=tz, evaluate_in_utc=evaluate_in_utc, subject=subject, etype=etype,
            actor_id=actor_id)
        owner = self._require_named_human(owner_id, "the expectation owner", actor_kind=actor_kind)

        key = _expectation_key(subject, etype)
        eid = expectation_id or f"exp-{uuid.uuid4().hex[:16]}"
        deadline_text = format_instant(deadline_dt)
        subject_obs = subject if subject_kind == "observation" else None
        confidence = None if proposed_confidence is None else str(proposed_confidence)
        now = format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            try:
                conn.execute(
                    """
                    INSERT INTO expectations (
                        tenant, expectation_id, subject_ref, subject_kind, subject_observation_ref,
                        expected_type, expected_source, expectation_key, deadline_utc,
                        originating_timezone, state, version, discharge_observation_id, late,
                        coverage_ref, coverage_health, coverage_gap, overdue_at, owner_id,
                        deadline_history, terminal_age_ms, proposed_confidence, created_at, updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?, 'RAISED', 1, NULL, NULL, NULL, NULL, NULL, NULL,
                              NULL, NULL, ?, ?, ?, ?)
                    """,
                    (self._tenant, eid, subject, subject_kind, subject_obs, etype, source, key,
                     deadline_text, tz, terminal_age_ms, confidence, now, now),
                )
            except sqlite3.IntegrityError:
                # ### AT MOST ONE LIVE RAISED EXPECTATION PER KEY. A RAISED expectation already exists —
                # coalesce onto it rather than raise a second (entity §17). A concurrent raiser loses no
                # obligation and never creates a duplicate live expectation.
                conn.rollback()
                existing = self.live_expectation_for(subject, etype)
                if existing is None:
                    raise
                return TransitionResult(
                    transition_id="EX-1", expectation=existing, from_state=None,
                    to_state=existing.state, coalesced=True)
            created = self.require(eid)
            if schedule_timer:
                # ### THE DEADLINE IS A DURABLE TIMER, IN THE SAME COMMIT AS THE RAISE (machine §37,
                # M-36, AP-3's shape). The owner and terminal age ride the payload so the fired deadline
                # knows who owns the resulting obligation and when it terminally ages.
                self._arm_deadline_timer(created, owner, terminal_age_ms, correlation_id)
            envelope = self._raise_envelope(
                created, actor_kind=actor_kind, actor_id=actor_id, correlation_id=correlation_id,
                causation_id=causation_id, trace_id=trace_id, event_id=event_id, now=now)
            self._outbox().emit(envelope)
            conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        return TransitionResult(
            transition_id="EX-1", expectation=created, from_state=None, to_state=ExState.RAISED,
            event_ids=(envelope.event_id,), event_names=("ExpectationRaised",), event_producer="EX-1")

    # --- EX-2 / EX-4: discharge -------------------------------------------------------------------

    def discharge(
        self,
        expectation_id: str,
        *,
        observation_id: str,
        expected: Expectation | None = None,
        actor_id: str = "ingestion",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """EX-2 (from RAISED) / EX-4 (from OVERDUE/INDETERMINATE) — ### A BOUND OBSERVATION DISCHARGES
        THE EXPECTATION, AND A LATE ARRIVAL IS ALWAYS ACCEPTED (entity §13/§26, machine §16).

        The discharging observation must be BOUND, of THIS tenant, and about the expectation's subject.
        An unbound one, one about another subject, and one belonging to another tenant each fail
        closed. From OVERDUE/INDETERMINATE the transition is EX-4 and the discharge is marked `late` —
        the POD that arrives in month four is still a POD, and it is never rejected because the deadline
        passed. Discharge BEATS overdue/indeterminate (§16): whichever raced, the arrival wins."""
        expectation = expected or self.require(expectation_id)
        obs = self._conn.execute(
            "SELECT observation_id, state, bound_entity_ref FROM observations "
            "WHERE tenant = ? AND observation_id = ?",
            (self._tenant, observation_id)).fetchone()
        if obs is None:
            raise GuardNotSatisfied(
                f"discharge requires a BOUND observation of THIS tenant; {observation_id!r} is not an "
                f"observation of {self._tenant!r}. A wrong-tenant or unknown observation fails closed "
                f"([C-1], entity §13) — the machine does not look across tenants to discharge.")
        if obs["state"] != "BOUND":
            raise GuardNotSatisfied(
                f"discharge requires a BOUND observation (entity §13, machine §31); {observation_id!r} "
                f"is {obs['state']!r}. An unbound observation is not yet a fact about a known subject "
                f"and cannot discharge — Neyma never guesses which expectation an unbound reading owes.")
        if not (obs["bound_entity_ref"] == expectation.subject_ref
                or obs["observation_id"] == expectation.subject_ref):
            raise GuardNotSatisfied(
                f"observation {observation_id!r} is about {obs['bound_entity_ref']!r}, not the "
                f"expectation's subject {expectation.subject_ref!r}: a POD bound to another load does "
                f"not discharge this one (entity §13).")

        if expectation.state is ExState.RAISED:
            producer, late = "EX-2", False
        elif expectation.state in (ExState.OVERDUE, ExState.INDETERMINATE):
            producer, late = "EX-4", True
        else:
            raise GuardNotSatisfied(
                f"discharge is from RAISED (EX-2) or OVERDUE/INDETERMINATE (EX-4); {expectation_id!r} "
                f"is {expectation.state.value} (terminal). A discharged/cancelled/expired expectation "
                f"is not re-discharged.")
        result = self._advance(
            expectation, producer, ExState.DISCHARGED, event_name="ExpectationDischarged",
            payload={"discharge_observation_id": observation_id, "late": late},
            event_producer=producer, actor_type="system", actor_id=actor_id,
            writes="discharge_observation_id = ?, late = ?", write_args=(observation_id, int(late)),
            correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
            event_id=event_id,
            after_write=self._cancel_timers_after(expectation.expectation_id, "discharged"))
        return TransitionResult(
            transition_id=result.transition_id, expectation=result.expectation,
            from_state=result.from_state, to_state=result.to_state, event_ids=result.event_ids,
            event_names=result.event_names, event_producer=result.event_producer, late=late)

    # --- EX-3 / EX-3i: the deadline evaluation (the honesty split) --------------------------------

    def evaluate_deadline(
        self,
        expectation_id: str,
        *,
        owner_id: str | None = None,
        terminal_age_ms: int | None = None,
        window_start: str | None = None,
        window_end: str | None = None,
        insist: str | None = None,
        expected: Expectation | None = None,
        actor_id: str = "timer",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult | None:
        """EX-3 (→ OVERDUE) / EX-3i (→ INDETERMINATE) — ### THE HONESTY SPLIT, READ FROM THE PERSISTED
        COVERAGE (entity §16/§36, M-32).

        Healthy coverage throughout the required window ⇒ OVERDUE (the thing never came, and we can
        prove we were watching). Down, unknown, partial or ABSENT coverage ⇒ INDETERMINATE (the
        deadline passed and we were blind). ### THE ABSENCE OF A COVERAGE RECORD IS NOT HEALTH. The
        verdict comes ONLY from the persisted `observation_coverage` record — never from a model, a
        counterparty or `proposed_confidence`. A named human owns the resulting obligation. A
        redelivered timer against a no-longer-RAISED expectation is a no-op (GR-4)."""
        expectation = expected or self.require(expectation_id)
        if expectation.state is not ExState.RAISED:
            # ### A REDELIVERED TIMER IS A NO-OP (GR-4). A discharge (or an earlier evaluation) already
            # moved this expectation; the deadline decides nothing a second time.
            return None
        owner = self._require_named_human(
            owner_id, "the overdue/indeterminate owner", actor_kind="human")
        req_start = window_start or expectation.created_at
        req_end = window_end or expectation.deadline_utc
        term = terminal_age_ms if terminal_age_ms is not None else expectation.terminal_age_ms
        health, coverage_id = self._coverage_verdict(expectation.expected_source, req_start, req_end)
        now = format_instant(self._clock())

        if health == HEALTHY_COVERAGE and coverage_id is not None:
            # EX-3 — a missed deadline over a demonstrably healthy window. The composite FK + the
            # OVERDUE CHECK make this the only path that may write OVERDUE.
            return self._advance(
                expectation, "EX-3", ExState.OVERDUE, event_name="ExpectationOverdue",
                payload={"coverage_ref": coverage_id}, event_producer="EX-3", actor_type="system",
                actor_id=actor_id,
                writes="coverage_ref = ?, coverage_health = ?, overdue_at = ?, owner_id = ?",
                write_args=(coverage_id, HEALTHY_COVERAGE, now, owner),
                correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                event_id=event_id, now=now,
                after_write=self._arm_terminal_age_after(expectation.expectation_id, term, now,
                                                         correlation_id))

        # ### DOWN / UNKNOWN / PARTIAL / ABSENT ⇒ INDETERMINATE. We were blind; we do not accuse the
        # counterparty of a failure that was ours. `insist='OVERDUE'` here is machine §15's ILLEGAL
        # shape, refused under GR-1.
        if insist == "OVERDUE":
            self._refuse_illegal(expectation.expectation_id, Trigger.OVERDUE_WITHOUT_COVERAGE,
                                 actor_id=actor_id)
            raise IllegalTransition(
                f"OVERDUE requires a coverage_ref proving the channel was HEALTHY throughout the window "
                f"(machine §15, M-32); the coverage here is {health!r}. Forcing OVERDUE would accuse a "
                f"counterparty of a failure that was ours — recorded to audit and security under GR-1, "
                f"and the honest state is INDETERMINATE.")
        gap = _coverage_gap(health, coverage_id)
        write_ref = coverage_id if coverage_id is not None else None
        write_health = health if coverage_id is not None else None
        return self._advance(
            expectation, "EX-3i", ExState.INDETERMINATE, event_name="ExpectationIndeterminate",
            payload={"coverage_gap": gap}, event_producer="EX-3i", actor_type="system",
            actor_id=actor_id,
            writes="coverage_ref = ?, coverage_health = ?, coverage_gap = ?, overdue_at = ?, "
                   "owner_id = ?",
            write_args=(write_ref, write_health, gap, now, owner),
            correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
            event_id=event_id, now=now,
            after_write=self._arm_terminal_age_after(expectation.expectation_id, term, now,
                                                     correlation_id))

    # --- EX-5: the deadline amendment (re-version, never supersession) ----------------------------

    def amend_deadline(
        self,
        expectation_id: str,
        *,
        new_deadline_utc: datetime | str | None = None,
        appointment_local: datetime | None = None,
        expected: Expectation | None = None,
        actor_id: str = "operator",
        actor_kind: str = "human",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """EX-5 — RAISED → RAISED (v++) on `DeadlineChanged`. ### A DEADLINE AMENDMENT RE-VERSIONS; IT
        IS NOT A SUPERSESSION (entity §19/§24). `deadline_history[]` retains the prior deadline; the
        subject and the expected type MAY NOT be mutated (entity §22, enforced by the identity trigger).
        The durable deadline timer is re-armed for the new instant in the same commit."""
        expectation = expected or self.require(expectation_id)
        if expectation.state is not ExState.RAISED:
            raise GuardNotSatisfied(
                f"EX-5 amends the deadline of a RAISED expectation; {expectation_id!r} is "
                f"{expectation.state.value}. A deadline is not amended after it has been judged.")
        new_dt = self._resolve_deadline(
            deadline_utc=new_deadline_utc, appointment_local=appointment_local,
            originating_timezone=expectation.originating_timezone, evaluate_in_utc=False,
            subject=expectation.subject_ref, etype=expectation.expected_type, actor_id=actor_id)
        new_text = format_instant(new_dt)
        history = expectation.deadline_history_list + [expectation.deadline_utc]
        now = format_instant(self._clock())
        return self._advance(
            expectation, "EX-5", ExState.RAISED, event_name="ExpectationReVersioned",
            payload={"deadline_history": history}, event_producer="EX-5",
            actor_type=("human" if str(actor_kind).upper() == HUMAN else "system"), actor_id=actor_id,
            writes="deadline_utc = ?, deadline_history = ?", write_args=(new_text, json.dumps(history)),
            correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
            event_id=event_id, now=now,
            after_write=self._rearm_deadline_after(expectation, new_dt, now, correlation_id))

    # --- EX-6: cancellation (the reason disappeared) ----------------------------------------------

    def cancel(
        self,
        expectation_id: str,
        *,
        reason: str,
        expected: Expectation | None = None,
        actor_id: str = "operator",
        actor_kind: str = "system",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """EX-6 — {RAISED, OVERDUE} → CANCELLED on `ReasonDisappeared` (e.g. the load cancelled). ###
        THE FROM-SET IS {RAISED, OVERDUE}; INDETERMINATE IS NOT IN IT. Cancelling an INDETERMINATE
        expectation is an ILLEGAL transition under GR-1 (there is no EX-6i). A wrong expectation is
        CANCELLED, never corrected (entity §23) and never superseded (§24); the row is retained ([C-9])."""
        expectation = expected or self.require(expectation_id)
        reason_text = _require_text(reason, "reason")
        if expectation.state is ExState.INDETERMINATE:
            self._refuse_illegal(expectation.expectation_id, Trigger.CANCEL_INDETERMINATE,
                                 actor_id=actor_id)
            raise IllegalTransition(
                f"EX-6 cancels a RAISED or OVERDUE expectation; {expectation_id!r} is INDETERMINATE, "
                f"which is NOT in the from-set (machine §14, GR-1). There is no EX-6i, and widening the "
                f"row would let a blind window be quietly closed. Recorded to audit and security.")
        if expectation.state not in (ExState.RAISED, ExState.OVERDUE):
            raise GuardNotSatisfied(
                f"EX-6 cancels a RAISED or OVERDUE expectation; {expectation_id!r} is "
                f"{expectation.state.value} (terminal). A discharged/expired/cancelled expectation is "
                f"retained, not re-cancelled.")
        return self._advance(
            expectation, "EX-6", ExState.CANCELLED, event_name="ExpectationCancelled",
            payload={"reason": reason_text},
            event_producer="EX-6",
            actor_type=("human" if str(actor_kind).upper() == HUMAN else "system"), actor_id=actor_id,
            writes="", write_args=(), correlation_id=correlation_id, causation_id=causation_id,
            trace_id=trace_id, event_id=event_id,
            after_write=self._cancel_timers_after(expectation.expectation_id, "cancelled"))

    # --- EX-7: expiry (terminal age, never silence) -----------------------------------------------

    def expire(
        self,
        expectation_id: str,
        *,
        expected: Expectation | None = None,
        actor_id: str = "timer",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """EX-7 — {OVERDUE, INDETERMINATE} → EXPIRED on the terminal-age timer. ### THE FROM-SET IS
        {OVERDUE, INDETERMINATE}; A RAISED EXPECTATION NEVER EXPIRES. Terminal age is an age PAST a
        human-owned state, not a second deadline. ### EXPIRY IS EXPLICIT AND NEVER SILENT (entity §26,
        machine §12/§23): it emits ExpectationExpired and RETAINS the row, still naming its human. No
        sweep, no reaper, no scan."""
        expectation = expected or self.require(expectation_id)
        if expectation.state is ExState.RAISED:
            self._refuse_illegal(expectation.expectation_id, Trigger.EXPIRE_RAISED, actor_id=actor_id)
            raise IllegalTransition(
                f"EX-7 expires an OVERDUE or INDETERMINATE expectation; {expectation_id!r} is RAISED, "
                f"which NEVER expires (machine §14, GR-1). Terminal age is an age past a human-owned "
                f"state, not a second deadline. Recorded to audit and security under GR-1.")
        if expectation.state not in (ExState.OVERDUE, ExState.INDETERMINATE):
            raise GuardNotSatisfied(
                f"EX-7 expires an OVERDUE or INDETERMINATE expectation; {expectation_id!r} is "
                f"{expectation.state.value} (terminal). A discharged/cancelled/expired expectation is "
                f"retained, not re-expired.")
        return self._advance(
            expectation, "EX-7", ExState.EXPIRED, event_name="ExpectationExpired", payload={},
            event_producer="EX-7", actor_type="system", actor_id=actor_id, writes="", write_args=(),
            correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
            event_id=event_id)

    # --- the durable-timer handler ----------------------------------------------------------------

    def handle_timer_fired(self, trigger: TimerFired, **kw: Any) -> TransitionResult | None:
        """### THE DEADLINE AND THE TERMINAL AGE RIDE DURABLE TIMERS — NEVER A SLEEP OR A SWEEP (machine
        §37, M-36). The deadline timer fires EX-3/EX-3i; the terminal-age timer fires EX-7. Any other
        kind arriving here is ILLEGAL (GR-1). A timer fires AT LEAST once and the machine acts EXACTLY
        once, because the guards are idempotent (GR-4)."""
        actor_id = kw.get("actor_id", "timer")
        if trigger.timer_kind == TIMER_KIND_DEADLINE:
            payload = trigger.payload or {}
            return self.evaluate_deadline(
                trigger.aggregate_id, owner_id=payload.get("owner_id"),
                terminal_age_ms=payload.get("terminal_age_ms"),
                correlation_id=trigger.correlation_id, causation_id=trigger.causation_id,
                actor_id=actor_id)
        if trigger.timer_kind == TIMER_KIND_TERMINAL_AGE:
            expectation = self.get(trigger.aggregate_id)
            if expectation is None or expectation.state not in (ExState.OVERDUE,
                                                                ExState.INDETERMINATE):
                # A redelivered or superseded terminal-age timer against a discharged/cancelled/expired
                # expectation is a no-op (GR-4) — a late discharge from OVERDUE never expires afterwards.
                return None
            return self.expire(trigger.aggregate_id, correlation_id=trigger.correlation_id,
                               causation_id=trigger.causation_id, actor_id=actor_id)
        self._refuse_illegal(trigger.aggregate_id, Trigger.TIMER_FIRED, actor_id=actor_id)
        raise IllegalTransition(
            f"a durable timer fired with kind {trigger.timer_kind!r} on expectation "
            f"{trigger.aggregate_id!r}; the only M8 timers are the deadline (EX-3/EX-3i) and the "
            f"terminal age (EX-7). No timer reaches DISCHARGED or CANCELLED. Recorded to audit and "
            f"security under GR-1.")

    # --- replay & park/drain ----------------------------------------------------------------------

    def reference_resolver(self, aggregate_type: str, aggregate_id: str) -> bool:
        """M-26's question, tenant-scoped. ### A DISCHARGE ARRIVING BEFORE ITS RAISE IS PARKED and
        drained the moment the raise lands — the same mechanism M3/M5/M6/M7 use, no second parking
        invented (### M8-AQ-5: absence of a version is never read as 'nothing before me')."""
        if aggregate_type == AGGREGATE_TYPE:
            return self._conn.execute(
                "SELECT 1 FROM expectations WHERE tenant = ? AND expectation_id = ?",
                (self._tenant, aggregate_id)).fetchone() is not None
        return True

    def consume_event(
        self, envelope: EventEnvelope, *, inbox: DedupInbox | None = None,
        requires_existing: tuple[tuple[str, str], ...] = (), drain: bool = True,
    ) -> ConsumedTransition:
        """Consume one canonical `expectation` event idempotently through P5's dedup inbox.

        ### REPLAY MINTS NO AUTHORITY, DUPLICATES NOTHING, FLIPS NO STATE AND CAUSES NO EXTERNAL EFFECT
        (GR-11, K-3). Reconstruction advances an EXISTING durable row's state to match a state-marking
        event WITHOUT re-deciding it or re-reading the live channel; a redelivery is a no-op (GR-4)."""
        box = inbox or DedupInbox(
            self._conn, tenant=self._tenant, consumer_id=CONSUMER_ID, clock=self._clock,
            reference_resolver=self.reference_resolver)
        outcome: dict[str, Any] = {"transition": None, "refusal": None}

        def handler(event: EventEnvelope) -> None:
            expectation = self.get(event.aggregate_id)
            if expectation is None:
                outcome["refusal"] = (
                    f"{event.event_name} references expectation {event.aggregate_id!r}, which does not "
                    f"exist for tenant {self._tenant!r}. Consumed once, nothing persisted.")
                return
            target = _event_target_state(event)
            if target is None or expectation.state is target or expectation.is_terminal:
                return
            outcome["transition"] = self._reconstruct_locked(expectation, target)

        default_reqs: tuple[tuple[str, str], ...] = ((AGGREGATE_TYPE, envelope.aggregate_id),)
        result = box.consume(
            envelope, handler,
            requires_existing=(requires_existing or default_reqs),
            drain_handler_for=((lambda _env: handler) if drain else None))
        return ConsumedTransition(
            consume=result, transition=outcome["transition"], refusal=outcome["refusal"])

    def rebuild(self, expectation_id: str, *,
                events: list[EventEnvelope] | None = None) -> ReconstructedExpectation:
        """### A FULL-HISTORY FOLD OF ONE EXPECTATION — SANDBOXED, ZERO AUTHORITY (GR-11, ER-2).

        ### THE OVERDUE-VS-INDETERMINATE VERDICT IS READ FROM WHICH EVENT WAS RECORDED, NOT FROM THE
        CHANNEL NOW (entity §34, machine §21). The stream is folded event by event; the coverage table
        is NEVER consulted, so a rebuild reaches the same verdict whatever the channel's live state.
        It creates NOTHING: no authority, no external effect, no coverage rewrite, no state flip."""
        stream = events if events is not None else self._event_stream(expectation_id)
        state: ExState | None = None
        coverage_basis: str | None = None
        for event in stream:
            target = _event_target_state(event)
            if target is not None:
                state = target
            elif event.event_name == "ExpectationRaised" and state is None:
                state = ExState.RAISED
            if event.event_name == "ExpectationOverdue":
                coverage_basis = str(event.payload.get("coverage_ref"))
            elif event.event_name == "ExpectationIndeterminate":
                coverage_basis = str(event.payload.get("coverage_gap"))
        return ReconstructedExpectation(
            expectation_id=expectation_id, state=state, coverage_basis=coverage_basis,
            new_authority=0, external_effects=0, coverage_rewritten=0, state_flips=0)

    # --- coverage -------------------------------------------------------------------------------

    def record_coverage(
        self, *, coverage_id: str, channel: str, window_start: str, window_end: str, health: str,
        probe_source: str,
    ) -> str:
        """Insert one persisted `observation_coverage` record. ### THIS IS THE CHANNEL HEALTH PROBE'S
        WRITE, DONE HERE ONLY FOR TEST/PROBE COVERAGE (task §3.6). Health is a POSITIVE, PERSISTED
        assertion from the closed vocabulary; there is no ABSENT value, because absence is NO ROW. M8
        ships NO production probe, poller or importer — this exists so the tests and the probe can
        write the window under test, exactly as the channel's own probe (P9+) will."""
        if health not in COVERAGE_HEALTH:
            raise MalformedExpectation(
                f"coverage health {health!r} is not one of {list(COVERAGE_HEALTH)}: health is a closed, "
                f"positive assertion — there is no ABSENT value, absence is modelled as no row (M-32).")
        now = format_instant(self._clock())
        self._conn.execute(
            "INSERT INTO observation_coverage (tenant, coverage_id, channel, window_start, window_end, "
            "health, probe_source, recorded_at) VALUES (?,?,?,?,?,?,?,?)",
            (self._tenant, coverage_id, channel, window_start, window_end, health, probe_source, now))
        self._conn.commit()
        return coverage_id

    def _coverage_verdict(self, channel: str, window_start: str,
                          window_end: str) -> tuple[str, str | None]:
        """### THE COVERAGE READ THAT DECIDES OVERDUE VS INDETERMINATE (M-32). Returns a health label
        and, when a real covering row exists, its coverage_id.

        ### THE ABSENCE OF A COVERAGE RECORD IS NOT HEALTH: no row ⇒ 'ABSENT'. A row that does not span
        the WHOLE required window is 'PARTIAL' — the 'throughout the window' half of EX-3. Only a
        HEALTHY row that covers the whole window returns HEALTHY. Health is read from the persisted
        record, never inferred from an empty error table, a live poll or the process being up."""
        rows = self._conn.execute(
            "SELECT coverage_id, window_start, window_end, health FROM observation_coverage "
            "WHERE tenant = ? AND channel = ? ORDER BY window_start, coverage_id",
            (self._tenant, channel)).fetchall()
        if not rows:
            return ("ABSENT", None)
        covering = [r for r in rows
                    if r["window_start"] <= window_start and r["window_end"] >= window_end]
        if not covering:
            # Coverage exists but not THROUGHOUT the required window — partial, not health.
            return ("PARTIAL", None)
        row = covering[0]
        return (row["health"], row["coverage_id"])

    # --- shared transition plumbing ---------------------------------------------------------------

    def _advance(
        self, expectation: Expectation, transition_id: str, to_state: ExState, *,
        event_name: str, payload: Mapping[str, Any], event_producer: str, actor_type: str,
        actor_id: str, writes: str, write_args: tuple[Any, ...], correlation_id: str | None,
        causation_id: str | None, trace_id: str | None, event_id: str | None,
        now: str | None = None, after_write: Callable[[str], None] | None = None,
    ) -> TransitionResult:
        """One state transition: the state row and its event, or neither (GR-2). OCC on the version the
        decision was read at (GR-3): zero rows is a lost update that raises, never a silent overwrite.
        ### THE TIMER ARRIVAL, THE COVERAGE READ, THE STATE AND ITS EVENT ARE ONE COMMIT."""
        now = now or format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            set_clause = "state = ?, version = version + 1, updated_at = ?"
            if writes:
                set_clause += ", " + writes
            args: list[Any] = [to_state.value, now, *write_args,
                               self._tenant, expectation.expectation_id, expectation.state.value,
                               expectation.version]
            cursor = conn.execute(
                f"UPDATE expectations SET {set_clause} "
                f"WHERE tenant = ? AND expectation_id = ? AND state = ? AND version = ?", args)
            if cursor.rowcount != 1:
                raise StateConflict(
                    f"{transition_id} matched {cursor.rowcount} rows for "
                    f"{expectation.expectation_id!r}: it moved under us (GR-3). Reload — a lost update "
                    f"on an expectation is refused, never a write that silently wins.")
            if after_write is not None:
                after_write(now)
            after = self.require(expectation.expectation_id)
            envelope = self._envelope(
                event_name=event_name, event_producer=event_producer, expectation=after,
                aggregate_version=self._next_version(expectation.expectation_id), actor_type=actor_type,
                actor_id=actor_id, payload=dict(payload), correlation_id=correlation_id,
                causation_id=causation_id, trace_id=trace_id, event_id=event_id, now=now)
            self._outbox().emit(envelope)
            conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        return TransitionResult(
            transition_id=transition_id, expectation=after, from_state=expectation.state,
            to_state=to_state, event_ids=(envelope.event_id,), event_names=(event_name,),
            event_producer=event_producer)

    def _reconstruct_locked(self, expectation: Expectation, target: ExState) -> TransitionResult:
        """Advance a durable row to match a durable event — reconstruction, not a live transition.

        Runs inside the inbox's own commit (M-24): no BEGIN, no COMMIT. ### IT MINTS NO AUTHORITY and
        NEVER re-reads the live channel: it moves only `state` to what the event already recorded."""
        conn = self._conn
        now = format_instant(self._clock())
        conn.execute(
            "UPDATE expectations SET state = ?, version = version + 1, updated_at = ? "
            "WHERE tenant = ? AND expectation_id = ? AND state = ?",
            (target.value, now, self._tenant, expectation.expectation_id, expectation.state.value))
        after = self.require(expectation.expectation_id)
        return TransitionResult(
            transition_id="replay", expectation=after, from_state=expectation.state, to_state=target)

    # --- the durable timers -----------------------------------------------------------------------

    def _arm_deadline_timer(self, expectation: Expectation, owner: str,
                            terminal_age_ms: int | None, correlation_id: str | None) -> None:
        """Arm the durable deadline timer IN THE CALLER'S OPEN TRANSACTION (machine §37; AP-3's shape).
        The owner and terminal age ride the payload so the fired deadline knows who owns the resulting
        obligation. No in-memory sleep, no second timer mechanism."""
        payload: dict[str, Any] = {"owner_id": owner}
        if terminal_age_ms is not None:
            payload["terminal_age_ms"] = terminal_age_ms
        DurableTimers(self._conn, tenant=self._tenant, clock=self._clock).schedule(
            timer_id=f"{TIMER_KIND_DEADLINE}:{expectation.expectation_id}:v{expectation.version}",
            aggregate_type=AGGREGATE_TYPE, aggregate_id=expectation.expectation_id,
            timer_kind=TIMER_KIND_DEADLINE, fire_at=expectation.deadline_utc, payload=payload,
            correlation_id=correlation_id or expectation.expectation_id)

    def _arm_terminal_age_after(self, expectation_id: str, terminal_age_ms: int | None,
                                overdue_at: str, correlation_id: str | None) -> Callable[[str], None]:
        """### THE TERMINAL-AGE TIMER, ARMED IN THE SAME COMMIT AS THE OVERDUE/INDETERMINATE TRANSITION
        (V10, task §3.11). The THRESHOLD is a caller-supplied parameter with no default that means
        anything — the MECHANISM (EX-7) is complete. With no threshold, no terminal-age timer is armed
        and the obligation ages without silently expiring, which is the fail-closed default."""
        def _arm(_now: str) -> None:
            if terminal_age_ms is None:
                return
            fire_at = _parse_instant(overdue_at) + timedelta(milliseconds=int(terminal_age_ms))
            DurableTimers(self._conn, tenant=self._tenant, clock=self._clock).schedule(
                timer_id=f"{TIMER_KIND_TERMINAL_AGE}:{expectation_id}",
                aggregate_type=AGGREGATE_TYPE, aggregate_id=expectation_id,
                timer_kind=TIMER_KIND_TERMINAL_AGE, fire_at=fire_at,
                correlation_id=correlation_id or expectation_id)
        return _arm

    def _rearm_deadline_after(self, expectation: Expectation, new_deadline: datetime, now: str,
                              correlation_id: str | None) -> Callable[[str], None]:
        """Cancel the old deadline timer and arm one for the new instant — a re-versioned deadline
        moves the durable timer with it, in the same commit as the transition."""
        def _arm(_now: str) -> None:
            timers = DurableTimers(self._conn, tenant=self._tenant, clock=self._clock)
            timers.cancel_for_aggregate(
                AGGREGATE_TYPE, expectation.expectation_id, reason="deadline re-versioned (EX-5)")
            timers.schedule(
                timer_id=(f"{TIMER_KIND_DEADLINE}:{expectation.expectation_id}"
                          f":v{expectation.version + 1}"),
                aggregate_type=AGGREGATE_TYPE, aggregate_id=expectation.expectation_id,
                timer_kind=TIMER_KIND_DEADLINE, fire_at=new_deadline,
                payload={"owner_id": expectation.owner_id} if expectation.owner_id else {},
                correlation_id=correlation_id or expectation.expectation_id)
        return _arm

    def _cancel_timers_after(self, expectation_id: str, reason: str) -> Callable[[str], None]:
        """Cancel every scheduled timer on this aggregate — what a discharge or a cancel does, so a
        terminal expectation does not later fire a deadline or a terminal age. Correctness does not
        DEPEND on it — every timer handler is idempotent and no-ops on a non-live state (GR-4) — but a
        terminal row should not leave a live deadline armed."""
        def _cancel(_now: str) -> None:
            DurableTimers(self._conn, tenant=self._tenant, clock=self._clock).cancel_for_aggregate(
                AGGREGATE_TYPE, expectation_id, reason=reason)
        return _cancel

    # --- the named-human guard --------------------------------------------------------------------

    def _require_named_human(self, human_id: str | None, role: str, *, actor_kind: str) -> str:
        """### A NAMED ACTIVE HUMAN, FK-BACKED (entity §11, machine §5, AC-SAFE-028). "A human" is
        decoration while the column is free text: it must be a recorded, ACTIVE human of THIS tenant
        (M1's precedent). `system` is not a human, a model is not a human, and a wrong-tenant, inactive
        or forged human fails closed."""
        text = str(human_id or "").strip()
        if str(actor_kind).lower() == "model":
            raise GuardNotSatisfied(
                f"{role} cannot be a model actor (ER-9, [C-6]): a model states no facts and owns no "
                f"obligation. The caller supplies a named ACTIVE human; the machine never picks one.")
        if not text:
            raise GuardNotSatisfied(
                f"{role} is a named human, FK-backed into tenant_humans (entity §11, AC-SAFE-028): an "
                f"ownerless or unnamed value is a silent drop wearing a status.")
        row = self._conn.execute(
            "SELECT state FROM tenant_humans WHERE tenant = ? AND human_id = ?",
            (self._tenant, text)).fetchone()
        if row is None or row["state"] != "ACTIVE":
            raise GuardNotSatisfied(
                f"{role} names {text!r}, who is not an ACTIVE recorded human of {self._tenant!r}. A "
                f"forged, inactive or wrong-tenant human fails closed — the owner is FK-backed, not a "
                f"free-text string, and `system` is not a human.")
        return text

    # --- deadline resolution ----------------------------------------------------------------------

    def _resolve_deadline(
        self, *, deadline_utc: datetime | str | None, appointment_local: datetime | None,
        originating_timezone: str, evaluate_in_utc: bool, subject: str, etype: str, actor_id: str,
    ) -> datetime:
        """Resolve the deadline instant. From a facility appointment it is localised FACILITY-LOCAL
        (honouring DST); from a UTC instant it is taken as given. ### EVALUATING A FACILITY APPOINTMENT
        IN UTC IS ILLEGAL (machine §15, F-25) — recorded under GR-1 and refused."""
        if appointment_local is not None:
            if evaluate_in_utc and originating_timezone.upper() not in ("UTC", "ETC/UTC"):
                self._refuse_illegal(_expectation_key(subject, etype), Trigger.UTC_WINDOW,
                                     actor_id=actor_id)
                raise IllegalTransition(
                    f"evaluating a facility appointment window in UTC instead of the facility's local "
                    f"timezone ({originating_timezone!r}) is ILLEGAL (machine §15, F-25): a 17:00 "
                    f"Denver appointment is not 17:00 UTC, and a DST boundary is a real freight event. "
                    f"Recorded to audit and security under GR-1; nothing persisted.")
            return facility_local_deadline(appointment_local, originating_timezone)
        if deadline_utc is None:
            raise MalformedExpectation(
                "an expectation has a deadline (entity §16): pass either a UTC `deadline_utc` or a "
                "facility `appointment_local` with the facility timezone. An expectation with no "
                "deadline has no honest deadline behaviour to have.")
        if isinstance(deadline_utc, datetime):
            if deadline_utc.tzinfo is None:
                raise MalformedExpectation(
                    "a naive deadline is an instant nobody can order against another clock; pass an "
                    "aware UTC datetime or a facility appointment.")
            return deadline_utc.astimezone(timezone.utc)
        # a pre-formatted RFC-3339 UTC string
        return _parse_instant(str(deadline_utc))

    # --- F14 recording ----------------------------------------------------------------------------

    def _refuse_illegal(self, aggregate_id: str, trigger: Trigger, *, actor_id: str) -> None:
        """### GR-1 — record `IllegalTransitionAttempted` to audit AND security, then the caller
        raises. The illegal shapes machine §15 and the EX-6/EX-7 from-sets name by hand all pass here."""
        expectation = self.get(aggregate_id)
        state = expectation.state.value if expectation is not None else "-"
        self._record_f14(
            aggregate_id=aggregate_id, event_name="IllegalTransitionAttempted",
            identity_suffix=f"{trigger.value}|{actor_id}",
            payload={"machine": "M8", "state": state, "trigger": trigger.value,
                     "attempted_by": actor_id},
            actor_type="system", actor_id=actor_id)

    def _record_f14(self, *, aggregate_id: str, event_name: str, identity_suffix: str,
                    payload: Mapping[str, Any], actor_type: str, actor_id: str) -> None:
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            version = max(1, self._outbox().last_emitted_version(AGGREGATE_TYPE, aggregate_id))
            identity = (f"{ILLEGAL_ATTEMPT_IDENTITY_PREFIX}|{self._tenant}|{AGGREGATE_TYPE}"
                        f"|{aggregate_id}|{version}|{identity_suffix}")
            existing = conn.execute(
                "SELECT event_id FROM event_outbox WHERE tenant = ? AND idempotency_identity = ?",
                (self._tenant, identity)).fetchone()
            if existing is None:
                now = format_instant(self._clock())
                envelope = EventEnvelope(
                    event_id=str(uuid.uuid4()), event_name=event_name,
                    event_version=CONTRACTS[event_name].current_version, occurred_at=now,
                    recorded_at=now, tenant_id=self._tenant, aggregate_type=AGGREGATE_TYPE,
                    aggregate_id=aggregate_id, aggregate_version=version,
                    previous_aggregate_version=None, causation_id=None,
                    correlation_id=aggregate_id, producer_component=self._component,
                    producer_transition_id=ILLEGAL_TRANSITION_PRODUCER, actor_type=actor_type,
                    actor_id=actor_id, trace_id=f"trace-{aggregate_id}", payload=dict(payload),
                    idempotency_identity=identity)
                self._outbox().emit(envelope)
                self._store_security_event(envelope, actor_id, event_name)
            conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise

    def _store_security_event(self, envelope: EventEnvelope, actor_id: str, event_type: str) -> None:
        next_id = self._conn.execute(
            "SELECT COALESCE(MAX(id), 0) + 1 FROM security_events WHERE tenant = ?",
            (self._tenant,)).fetchone()[0]
        self._conn.execute(
            "INSERT INTO security_events (tenant, id, event_type, actor, payload_json, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (self._tenant, next_id, event_type, actor_id,
             json.dumps(envelope.payload, sort_keys=True), format_instant(self._clock())))

    # --- outbox / envelope plumbing ---------------------------------------------------------------

    def _event_stream(self, expectation_id: str) -> list[EventEnvelope]:
        rows = self._conn.execute(
            "SELECT envelope_json FROM event_outbox WHERE tenant = ? AND aggregate_type = ? "
            "AND aggregate_id = ? ORDER BY aggregate_version, sequence",
            (self._tenant, AGGREGATE_TYPE, expectation_id)).fetchall()
        return [EventEnvelope.from_json(r["envelope_json"]) for r in rows]

    def _next_version(self, expectation_id: str) -> int:
        return self._outbox().last_emitted_version(AGGREGATE_TYPE, expectation_id) + 1

    def _outbox(self):
        from .event_outbox import TransactionalOutbox
        return TransactionalOutbox(self._conn, tenant=self._tenant, clock=self._clock)

    def _raise_envelope(
        self, expectation: Expectation, *, actor_kind: str, actor_id: str, correlation_id: str | None,
        causation_id: str | None, trace_id: str | None, event_id: str | None, now: str,
    ) -> EventEnvelope:
        """The `ExpectationRaised` envelope on the `expectation` aggregate at version 1. The payload is
        EXACTLY the four declared F8 fields — deadline_utc, originating_timezone, expected_source,
        expectation_key — no more, because the outbox validates in PRODUCER mode."""
        actor_type = "human" if str(actor_kind).upper() == HUMAN else str(actor_kind).lower()
        payload = {
            "deadline_utc": expectation.deadline_utc,
            "originating_timezone": expectation.originating_timezone,
            "expected_source": expectation.expected_source,
            "expectation_key": expectation.expectation_key,
        }
        return EventEnvelope(
            event_id=event_id or str(uuid.uuid4()), event_name="ExpectationRaised",
            event_version=CONTRACTS["ExpectationRaised"].current_version, occurred_at=now,
            recorded_at=now, tenant_id=self._tenant, aggregate_type=AGGREGATE_TYPE,
            aggregate_id=expectation.expectation_id, aggregate_version=1,
            previous_aggregate_version=None, causation_id=causation_id,
            correlation_id=correlation_id or expectation.expectation_id,
            producer_component=self._component, producer_transition_id="EX-1",
            actor_type=actor_type, actor_id=actor_id,
            trace_id=trace_id or f"trace-{expectation.expectation_id}", payload=payload)

    def _envelope(
        self, *, event_name: str, event_producer: str, expectation: Expectation,
        aggregate_version: int, actor_type: str, actor_id: str, payload: Mapping[str, Any],
        correlation_id: str | None, causation_id: str | None, trace_id: str | None,
        event_id: str | None, now: str,
    ) -> EventEnvelope:
        """One canonical envelope on the `expectation` aggregate for EX-2…EX-7. F8 is order-tolerant, so
        no `previous_aggregate_version` travels on it (### M8-AQ-5). The human owner, once assigned, is
        pinned as the accountable owner so the audit names who owns the blindness."""
        return EventEnvelope(
            event_id=event_id or str(uuid.uuid4()), event_name=event_name,
            event_version=CONTRACTS[event_name].current_version, occurred_at=now, recorded_at=now,
            tenant_id=self._tenant, aggregate_type=AGGREGATE_TYPE,
            aggregate_id=expectation.expectation_id, aggregate_version=aggregate_version,
            previous_aggregate_version=None, causation_id=causation_id,
            correlation_id=correlation_id or expectation.expectation_id,
            producer_component=self._component, producer_transition_id=event_producer,
            actor_type=actor_type, actor_id=actor_id,
            trace_id=trace_id or f"trace-{expectation.expectation_id}", payload=dict(payload),
            accountable_owner_id=expectation.owner_id)


# ------------------------------------------------------------------------------------- plumbing

def _expectation_key(subject_ref: str, expected_type: str) -> str:
    """### THE DUPLICATE-PREVENTION KEY = (subject_ref, expected_type) (entity §9), joined the same way
    the database CHECK expects it. Deterministic, so two raisers of one owed observation collide."""
    return f"{subject_ref}::{expected_type}"


def _coverage_gap(health: str, coverage_id: str | None) -> str:
    """A human-legible description of WHY an INDETERMINATE window was blind — the ExpectationIndeterminate
    payload's required `coverage_gap`."""
    if coverage_id is None and health == "ABSENT":
        return "ABSENT: no coverage record for the channel over the window"
    if coverage_id is None:
        return "PARTIAL_WINDOW: coverage exists but not throughout the required window"
    return f"{health}: the channel was {health.lower()} over the window"


def _event_target_state(event: EventEnvelope) -> ExState | None:
    """The state an expectation event reconstructs to, or None for an event that is not a state marker
    (ExpectationRaised's own marker is handled by the rebuild; ExpectationReVersioned keeps RAISED; an
    F14 event riding the aggregate does not move the state)."""
    name = event.event_name
    if name == "ExpectationDischarged":
        return ExState.DISCHARGED
    if name == "ExpectationOverdue":
        return ExState.OVERDUE
    if name == "ExpectationIndeterminate":
        return ExState.INDETERMINATE
    if name == "ExpectationCancelled":
        return ExState.CANCELLED
    if name == "ExpectationExpired":
        return ExState.EXPIRED
    # ExpectationRaised (creation marker), ExpectationReVersioned, IllegalTransitionAttempted, etc.
    return None


def _parse_instant(text: str) -> datetime:
    """One canonical RFC-3339 UTC-milliseconds string back to an aware datetime."""
    normalized = text.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).astimezone(timezone.utc)


def _require_text(value: str, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise MalformedExpectation(f"{field_name} is required and was empty.")
    return text


def _row_to_expectation(row: Any) -> Expectation:
    return Expectation(
        tenant=row["tenant"], expectation_id=row["expectation_id"], subject_ref=row["subject_ref"],
        subject_kind=row["subject_kind"], expected_type=row["expected_type"],
        expected_source=row["expected_source"], expectation_key=row["expectation_key"],
        deadline_utc=row["deadline_utc"], originating_timezone=row["originating_timezone"],
        state=ExState(row["state"]), version=row["version"],
        discharge_observation_id=row["discharge_observation_id"], late=row["late"],
        coverage_ref=row["coverage_ref"], coverage_health=row["coverage_health"],
        coverage_gap=row["coverage_gap"], overdue_at=row["overdue_at"], owner_id=row["owner_id"],
        deadline_history=row["deadline_history"], terminal_age_ms=row["terminal_age_ms"],
        proposed_confidence=row["proposed_confidence"], created_at=row["created_at"])


# Re-exported so a caller reads one name rather than importing the migration for a constant.
STATES: tuple[str, ...] = EXPECTATION_STATES
