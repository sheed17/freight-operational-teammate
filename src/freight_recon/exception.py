"""Machine M9 — the Exception: one `exceptions` row per thing that needs a human, and the one machine
in Neyma whose whole job is to make sure it REACHES A NAMED PERSON and is NEVER QUIETLY FORGOTTEN.

    ### AN EXCEPTION IS SOMETHING THAT NEEDS A HUMAN. IT REACHES A NAMED HUMAN OWNER FROM CREATION,
    ### AND IT IS NEVER CLOSED BY SILENCE. AN EXCEPTION CLOSED WITHOUT A DECISION IS NOT CLOSED — IT
    ### IS FORGOTTEN (entity §3/§4/§36, F-30).

Every other machine in this repository has a state that means "a human has to look at this": M3's
UNKNOWN_OUTCOME, M5's UNPARSEABLE/UNBOUND, M6's AMBIGUOUS/CONFLICTING, M7's OPEN/ESCALATED, M8's
OVERDUE/INDETERMINATE, M1's BLOCKED/AWAITING_HUMAN. ### M9 IS THE MACHINE THOSE STATES POINT AT — the
place where "Neyma could not resolve this deterministically" becomes "a named person owns it, and the
system will not stop asking." It carries exactly one hard honesty rule, which is why it is NOT an alert:

    ### IT IS NOT AN ERROR LOG, AN ALERT, OR AN ISSUE TRACKER ROW. IT IS NOT AUTO-CLOSABLE. IT IS NOT
    ### OUTLIVABLE (entity §4).

An alert that nobody acknowledges disappears; a log line rotates out; a ticket auto-closes after thirty
quiet days. Every one of those is a mechanism for FORGETTING, and in freight the things Neyma cannot
resolve are exactly the things that cost money. So closure is not a status change. ### CLOSURE IS AN
EVENT WITH A RESOLVING `decision_ref` (I11, GR-14, K-1, AC-MACH-903), and there is no other way out —
not inactivity, not AutoClose, not expiry, not a sweep, not a reaper, not a timer, and NEVER A MODEL.
The one thing a timer may do is make the exception LOUDER: EC-4 ages it and EC-5 escalates it. ### A
TIMER NEVER RESOLVES (machine §37).

### WHAT THIS MACHINE OWNS, AND WHAT IT ONLY FEEDS.

It owns the five states and the EC-1…EC-7 transitions of `09-exception.machine.md` §14, and it is the
canonical PRODUCER of the SIX already-registered F9 `Exception*` events on the `exception` aggregate. It
rides P5's transactional outbox, dedup inbox and durable timers exactly as M3…M8 do.

### CLOSURE IMPORTS M1's RESOLVER — NEVER A SECOND ONE (task §3.5.2, CLAUDE.md rule 17). EC-3/EC-6 call
`work_item.resolve_decision_ref`, the landed K-1 executor M3 already imports for EF-5. Two
implementations of "does this decision_ref resolve" is two places for one of them to start accepting the
string "done". The database CHECK is the STRUCTURAL half (a RESOLVED row with no decision_ref is not
insertable); the resolver is the "RESOLVES" half. ### M9-AQ-1 is REPORTED: three files say resolution
requires a HUMAN and GR-14/K-1/AC-SAFE-024/F9 say a human OR an ACTIVE rule — every reading agrees a bare
string is not a decision_ref, a model may NEVER resolve, and the RULE branch REFUSES today (debt P6-D4,
closes at M12, NOT here). This machine builds the human branch and imports the resolver unchanged.

### THE FREEZE IS CONDITIONAL AND PROJECTED, NEVER A NEW TABLE (### M9-AQ-5, entity §38). NOT every
Exception freezes an entity — only those that make a material field non-`consistent`. `native_projection`
projects a freezing OPEN exception into the checkpoint's EXISTING `NativeClaim(conflicting=…)` type
WITHOUT importing the checkpoint (M7/M8's shape), so step 4 refuses — an Exception is an INPUT to the
gate and NEVER a gate. P3 stays the sole gate minter and M3 the single effect authority; M9 mints no gate
decision, writes no `effect_grants` row, engages NO brake (a Sev-0 exception CARRIES SEV0; the brake is
the source detector's act, F9 cross-cutting), and takes no external action.

### THE FAILURE CLASSIFICATION IS SUPPLIED, NEVER INFERRED (entity §13, L-D, M-74). EC-1 takes M1's
landed `FailureDisposition` enum and RECORDS it; a PERMANENT (auth/config) failure is raised IMMEDIATELY
with zero retries. There is NO classifier here — mapping a vendor error to PERMANENT is P9+ adapter work,
and inferring it from a message is the defect.

### THE F14 TRIPWIRE THAT IS MINE (task §3.10). `IllegalTransitionAttempted` (GR-1, mandatory) on every
illegal `(state, trigger)`, to audit AND security — closure without a resolving decision_ref, AutoClose /
inactivity, resolving from AGEING, ageing an already-AGEING/ESCALATED exception, a severity change from
AGEING, and a model acting. NOT mine: the three Sev-0 source detectors (`OrphanAdapterInvocation`,
`CrossTenantAccessAttempted`, `ProjectionRebuildDiverged`) that auto-engage a brake at their source; and
`CrossTenantAccessAttempted` is the inbox's — M9 fails a cross-tenant question closed, it does not mint it.

### IT SHIPS DARK. Nothing under `src/freight_recon/` imports this module; the only script that may is
`scripts/probe_phase6_exception.py`. It joins no importer, oversight queue, dashboard, notifier, pager,
on-call rotation or MTTR emitter, authorizes no effect, mints no gate decision, and the production
production gate registry stays EMPTY. M9's product form is an exception queue with owners, notifications
and an MTTR dashboard — so that product is precisely the thing that does not arrive with it.
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

from .event_contracts import CONTRACTS
from .event_envelope import EventEnvelope, format_instant
from .event_inbox import ConsumeResult, DedupInbox
from .event_timers import DurableTimers, TimerFired
from .migrations.phase6_exceptions import (
    EXCEPTION_SEVERITIES,
    EXCEPTION_STATES,
    FAILURE_CLASSIFICATIONS,
    HUMAN_OWNED_EXCEPTION_STATES,
    SOURCE_KIND_TABLE,
    SOURCE_KINDS,
    SUB_STATUSES,
    TERMINAL_EXCEPTION_STATES,
)
from .tenant import require_tenant
from .work_item import (
    DecisionRefUnresolvable,
    FailureDisposition,
    resolve_decision_ref,
)

# The aggregate this machine owns. `exception` is NOT in `STRICT_ORDER_AGGREGATE_TYPES`: F9 is
# ORDER-TOLERANT (events/registry.md §8), so this machine declares no `previous_aggregate_version`,
# exactly as M5 and M8 (the other order-tolerant P6 machines) do.
AGGREGATE_TYPE = "exception"

# entity §5 — the Exception Service raises and owns exceptions.
PRODUCER_COMPONENT = "exception_service"

# The one consumer identity M9 presents to the dedup inbox. Fixed, because the dedup key is
# `(tenant, consumer_id, event_id)` and a renamed consumer would re-arm every duplicate.
CONSUMER_ID = "m9-exception"

# GR-1's producer id for `IllegalTransitionAttempted` — the RULE, not a transition. Identical to
# M1..M8's, for the same reason.
ILLEGAL_TRANSITION_PRODUCER = "GR-1"

# A refusal advances no version; two refusals against one exception at one version would otherwise
# collide on one idempotency identity — the poison-loop defect M1 shipped. Applied here.
ILLEGAL_ATTEMPT_IDENTITY_PREFIX = "ita_v1"

# ### THE TWO DURABLE-TIMER KINDS, AND ONLY TWO (machine §37, M-36, ADR-008). The AGE timer is armed at
# the raise and fires EC-4 (OPEN/ACKNOWLEDGED → AGEING); the ESCALATION timer is armed at EC-4 and fires
# EC-5 (AGEING → ESCALATED). ### NEITHER MAPS TO A RESOLUTION — that is how "a timer never resolves" is
# STRUCTURAL rather than a promise. No timer_kind reaches RESOLVED.
TIMER_KIND_AGE = "exception_age_threshold"
TIMER_KIND_ESCALATION = "exception_escalation_threshold"

# The K-1 kind M9 offers to M1's resolver for a human closure — the audit_events referent. The RULE kind
# is in DECISION_REF_KINDS (so the DB CHECK admits it) but REFUSES in the resolver today (debt P6-D4).
DECISION_KIND_AUDIT = "AUDIT_EVENT"

HUMAN = "HUMAN"

# The SIX F9 contracts this machine MINTS — exactly the registered set, no seventh `Exception*` name.
PRODUCED_CONTRACTS: frozenset[str] = frozenset(
    ("ExceptionRaised", "ExceptionAcknowledged", "ExceptionAgeing", "ExceptionEscalated",
     "ExceptionSeverityChanged", "ExceptionResolved"))


class M9Error(RuntimeError):
    """This machine will not do what was asked. Never degraded into a partial transition."""


class UnknownException(M9Error):
    """No `exceptions` row with this id exists FOR THIS TENANT. Indistinguishable from "belongs to
    another tenant" on purpose — [C-1] rejects a cross-tenant question."""


class GuardNotSatisfied(M9Error):
    """The (state, trigger) pair IS legal here and a precondition is false. No event is emitted."""


class IllegalTransition(M9Error):
    """GR-1 / [C-4]. The (state, trigger) pair is not enumerated (or §15 forbids the shape). Raised
    AFTER `IllegalTransitionAttempted` is recorded, which is the point of recording it."""


class StateConflict(M9Error):
    """A state-guarded UPDATE matched zero rows: the exception moved under us (GR-3). Reload."""


class MalformedException(M9Error):
    """The inputs to a raise are not a canonical exception — a severity off the closed set, a source
    kind that is not enumerated, an inferred failure classification, a permanent failure with retries.
    Fail closed; nothing is persisted."""


# --------------------------------------------------------------------------------- the state set

# ### THESE ENUM CLASS NAMES ARE DELIBERATELY PREFIXED `Ec…`, NOT `Exception…`. A canonical scan flags
# any `Exception[A-Z]…` identifier in the machine that is not one of the SIX registered F9 event
# contracts — an internal type sharing that shape reads as an unregistered event name minted in the
# machine (registry §5: no machine may define a local synonym). An invented seventh event (an "auto
# closed" one, say) is exactly that shape, so these internal types carry a machine-local `Ec` prefix.
class EcState(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    AGEING = "AGEING"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"


class EcSeverity(str, Enum):
    SEV0 = "SEV0"
    SEV1 = "SEV1"
    SEV2 = "SEV2"


class EcSubStatus(str, Enum):
    """The machine header's finer sub-states as a closed FIELD vocabulary — NOT lifecycle states. The
    VALUES are lowercase so a sub_status can never be confused with a canonical state (UPPERCASE), and
    `awaiting_human` here is a sub_status VALUE, never M1's AWAITING_HUMAN lifecycle state."""

    TRIAGE = "triage"
    ASSIGNED = "assigned"
    INVESTIGATING = "investigating"
    AWAITING_EXTERNAL = "awaiting_external"
    AWAITING_HUMAN = "awaiting_human"
    RESOLUTION_PROPOSED = "resolution_proposed"


class Trigger(str, Enum):
    """The closed set of driving facts, named from §14's triggers and §33's "Consumes", plus the
    illegal triggers §15 names by hand so GR-1 answers them uniformly.

    The values are spelled so the machine carries no `Exception[A-Z]…` identifier other than the six
    registered F9 event names — an internal token sharing that shape reads as an unregistered event
    minted here (registry §5)."""

    ACKNOWLEDGED = "Acknowledged"                 # EC-2
    RESOLVED = "Resolved"                         # EC-3 / EC-6
    TIMER_FIRED = "TimerFired"                    # EC-4 / EC-5 (durable timers)
    SEVERITY_CHANGE = "SeverityReassessed"        # EC-7
    # ### THE ILLEGAL TRIGGERS (machine §15, target spec §12.9). Silence closes nothing; a clock never
    # resolves; a model states no facts.
    AUTO_CLOSE = "AutoClose"
    INACTIVITY = "Inactivity"
    TIMER_RESOLVE = "TimerFiredToResolved"


OPEN_STATES: frozenset[EcState] = frozenset(EcState(s) for s in HUMAN_OWNED_EXCEPTION_STATES)
TERMINAL_STATES: frozenset[EcState] = frozenset(
    EcState(s) for s in TERMINAL_EXCEPTION_STATES)

# EC-3's from-set is {OPEN, ACKNOWLEDGED}; EC-6's is {ESCALATED}. AGEING is in NEITHER — resolving an
# AGEING exception directly is ILLEGAL (task §3.4). EC-4 ages from {OPEN, ACKNOWLEDGED} only; EC-7
# reassesses severity from {OPEN, ACKNOWLEDGED, ESCALATED} only. Read literally, they are the guard.
EC3_FROM: frozenset[EcState] = frozenset((EcState.OPEN, EcState.ACKNOWLEDGED))
EC6_FROM: frozenset[EcState] = frozenset((EcState.ESCALATED,))
EC4_FROM: frozenset[EcState] = frozenset((EcState.OPEN, EcState.ACKNOWLEDGED))
EC7_FROM: frozenset[EcState] = frozenset((EcState.OPEN, EcState.ACKNOWLEDGED, EcState.ESCALATED))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------------------------ the row

@dataclass(frozen=True)
class EcRecord:
    """One `exceptions` row, as the machine reads it."""

    tenant: str
    exception_id: str
    type: str
    severity: EcSeverity
    state: EcState
    version: int
    owner_id: str
    source_ref: str
    source_kind: str
    entity_ref: str | None
    frozen_field: str | None
    freezes_entity: bool
    sub_status: str | None
    failure_classification: str | None
    exposure: str | None
    specific_question: str | None
    summary: str
    acknowledged_at: str | None
    acknowledged_by: str | None
    ageing_at: str | None
    escalation_at: str | None
    decision_ref: str | None
    decision_ref_kind: str | None
    decision_human_id: str | None
    created_at: str

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    @property
    def is_open(self) -> bool:
        """### AN OWED-BUT-UNRESOLVED EXCEPTION (OPEN / ACKNOWLEDGED / AGEING / ESCALATED). A RESOLVED
        one is decided; every other state is human-owned open work that still ages."""
        return self.state in OPEN_STATES

    def native_projection(self) -> "NativeExceptionProjection":
        """### THE SEAM WITH THE CHECKPOINT (task §3.9, entity §38). Project this exception into the shape
        step 4 reads (`checkpoint.NativeClaim`) WITHOUT importing the checkpoint. ### NOT EVERY EXCEPTION
        FREEZES AN ENTITY — only a FREEZING one that is still open makes its field `conflicting`, so step
        4 refuses (`CLAIM_CONFLICTING`, via GR-10 / the frozen field, machine §28); a non-freezing or a
        RESOLVED one is not conflicting and the field unfreezes. M9 FEEDS the one gate authority, it never
        duplicates it, and it mints no gate decision."""
        frozen = self.freezes_entity and not self.is_terminal
        return NativeExceptionProjection(
            claim_id=self.exception_id, status="ACTIVE", conflicting=frozen,
            provenance="SYSTEM_IMPORTED",
            field=self.frozen_field or self.type, entity_ref=self.entity_ref or self.source_ref,
            evidence_condition=("conflicting" if frozen else "consistent"))


@dataclass(frozen=True)
class NativeExceptionProjection:
    """The fields `checkpoint.NativeClaim` / `checkpoint.ProvenancedFact` read, projected from an M9
    exception without importing the checkpoint. The probe builds the real types from these and shows step
    4 refuses a freezing open exception — an INPUT to the gate, never a gate."""

    claim_id: str
    status: str
    conflicting: bool
    provenance: str
    field: str
    entity_ref: str
    evidence_condition: str


@dataclass(frozen=True)
class TransitionResult:
    transition_id: str                 # the machine row: EC-1..EC-7
    exception: EcRecord
    from_state: EcState | None
    to_state: EcState
    event_ids: tuple[str, ...] = ()
    event_names: tuple[str, ...] = ()
    event_producer: str | None = None  # the transition id the emitted event names (EC-3/EC-6 both)
    coalesced: bool = False            # a raise that found an existing open exception for the cause


@dataclass(frozen=True)
class ReconstructedException:
    """A full-history fold of one exception's event stream — sandboxed, zero authority (GR-11, K-3).

    ### THE CURRENT SEVERITY IS REBUILT FROM THE RECORDED SEVERITY-CHANGE EVENTS, NEVER FROM THE LIVE ROW
    (entity §34, events/registry.md §8 last bullet). ExceptionRaised records the birth severity; each
    ExceptionSeverityChanged folds over it at increasing aggregate_version, so a rebuild reproduces the
    LIVE severity — without the events it would reproduce the ORIGINAL and UNDER-STATE a Sev-0. Every
    count is of what the REBUILD created, which is always zero: no resolution minted, no decision_ref
    manufactured, no new authority, the outside world untouched, no state flip."""

    exception_id: str
    state: EcState | None
    severity: EcSeverity | None
    frozen: bool
    new_authority: int = 0
    external_effects: int = 0
    decision_refs_minted: int = 0
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

class M9Machine:
    """M9, on an existing connection, bound to ONE tenant. Bound at construction so a caller cannot
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
            raise M9Error(
                "M9Machine reads columns by name and requires `row_factory = sqlite3.Row`.")
        self._conn = conn
        self._tenant = require_tenant(tenant, context="M9Machine")
        self._clock = clock or _utc_now
        self._component = producer_component

    @property
    def tenant(self) -> str:
        return self._tenant

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    # --- reads -----------------------------------------------------------------------------------

    def get(self, exception_id: str) -> EcRecord | None:
        row = self._conn.execute(
            "SELECT * FROM exceptions WHERE tenant = ? AND exception_id = ?",
            (self._tenant, exception_id),
        ).fetchone()
        return _row_to_exception(row) if row is not None else None

    def require(self, exception_id: str) -> EcRecord:
        found = self.get(exception_id)
        if found is None:
            raise UnknownException(
                f"no exception {exception_id!r} for tenant {self._tenant!r}. This machine does not look "
                f"outside its tenant to find out whether it exists elsewhere ([C-1]).")
        return found

    def open_exception_for(self, source_ref: str, type_: str) -> EcRecord | None:
        """### THE DEDUP READ (task §3.5.9). At most one OPEN exception can match — the optional partial
        unique index (which this build built) guarantees it. A re-raise of the same cause coalesces."""
        row = self._conn.execute(
            "SELECT * FROM exceptions WHERE tenant = ? AND source_ref = ? AND type = ? "
            "AND state != 'RESOLVED' ORDER BY created_at, exception_id",
            (self._tenant, source_ref, type_),
        ).fetchone()
        return _row_to_exception(row) if row is not None else None

    def owner_queue(self, *, owner_id: str | None = None) -> list[EcRecord]:
        """### THE OWNER QUEUE IS AN ORDERING, NOT A PRODUCT (task §3.6). The open exceptions this
        brokerage's named human owns, by severity then age. M9 owes the row and this tenant-first read;
        it does NOT build the queue UI, dashboard, notifier or MTTR emitter."""
        sql = ("SELECT * FROM exceptions WHERE tenant = ? AND state != 'RESOLVED'")
        params: list[Any] = [self._tenant]
        if owner_id is not None:
            sql += " AND owner_id = ?"
            params.append(owner_id)
        sql += " ORDER BY severity, created_at, exception_id"
        return [_row_to_exception(r) for r in self._conn.execute(sql, params).fetchall()]

    # --- EC-1: the raise ---------------------------------------------------------------------------

    def raise_exception(
        self,
        *,
        type: str,
        severity: str | EcSeverity,
        source_ref: str,
        source_kind: str,
        owner_id: str,
        summary: str,
        entity_ref: str | None = None,
        freezes_entity: bool = False,
        frozen_field: str | None = None,
        sub_status: str | EcSubStatus | None = None,
        failure_classification: FailureDisposition | str | None = None,
        attempts_before_raise: int = 0,
        exposure: str | None = None,
        specific_question: str | None = None,
        exception_id: str | None = None,
        actor_id: str = "exception",
        actor_kind: str = "system",
        age_threshold_ms: int | None = None,
        escalation_threshold_ms: int | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
        schedule_timer: bool = True,
    ) -> TransitionResult:
        """EC-1 — ### RAISE ASSIGNS A NAMED HUMAN OWNER AT CREATION, RECORDS SEVERITY AND THE SOURCE THAT
        RAISED IT, AND (WHERE APPLICABLE) FREEZES THE ENTITY — ALL IN ONE COMMIT (entity §10/§15/§16/§37,
        machine §4/§5/§35, I1).

        The `exceptions` row (state OPEN) and the durable AGE timer are written in ONE transaction, so a
        persistence failure leaves NO half-raised exception and no orphaned timer. A PERMANENT (auth/
        config) failure is raised IMMEDIATELY with zero retries (L-D, M-74): the classification is
        SUPPLIED as an enumerated `FailureDisposition`, never inferred from a message. If an OPEN
        exception already exists for `(source_ref, type)` the optional dedup index refuses the insert and
        the raise COALESCES onto it — a re-raise of the same cause is a no-op (entity §17/§33)."""
        etype = _require_text(type, "type")
        source = _require_text(source_ref, "source_ref")
        summary_text = _require_text(summary, "summary")
        sev = _severity_value(severity)
        kind = _source_kind_value(source_kind)
        classification = _require_classification(failure_classification)
        # ### A PERMANENT FAILURE RAISES IMMEDIATELY, WITH ZERO RETRIES (task §3.5.8, L-D). The retry
        # count is the caller's evidence that it did not spin on an auth/config failure before raising.
        if classification is FailureDisposition.PERMANENT and int(attempts_before_raise) != 0:
            raise MalformedException(
                f"a PERMANENT (auth/config) failure is raised IMMEDIATELY and NEVER retried (L-D, M-74, "
                f"entity §43(d)): attempts_before_raise={attempts_before_raise} — a permanent failure "
                f"that was retried before raising has already wasted the effect it could not perform.")
        sub = _sub_status_value(sub_status)
        if freezes_entity and (not str(entity_ref or "").strip() or not str(frozen_field or "").strip()):
            raise MalformedException(
                "a freezing exception names the entity it freezes and the field it froze (### M9-AQ-5, "
                "entity §38): freezes_entity is set but entity_ref/frozen_field is empty. A freeze with "
                "no field to block is a freeze that blocks nothing.")
        owner = self._require_named_human(owner_id, "the exception owner", actor_kind=actor_kind)

        mirror = SOURCE_KIND_TABLE.get(kind)
        mirror_col = mirror[0] if mirror else None
        xid = exception_id or f"exc-{uuid.uuid4().hex[:16]}"
        now = format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            columns = [
                "tenant", "exception_id", "type", "severity", "state", "version", "owner_id",
                "source_ref", "source_kind", "entity_ref", "frozen_field", "freezes_entity",
                "sub_status", "failure_classification", "exposure", "specific_question", "summary",
                "acknowledged_at", "acknowledged_by", "ageing_at", "escalation_at", "decision_ref",
                "decision_ref_kind", "decision_human_id", "created_at", "updated_at",
            ]
            values: list[Any] = [
                self._tenant, xid, etype, sev, "OPEN", 1, owner, source, kind,
                entity_ref, frozen_field, 1 if freezes_entity else 0, sub,
                classification.value if classification is not None else None, exposure,
                specific_question, summary_text, None, None, None, None, None, None, None, now, now,
            ]
            if mirror_col is not None:
                columns.append(mirror_col)
                values.append(source)
            placeholders = ",".join("?" for _ in columns)
            try:
                conn.execute(
                    f"INSERT INTO exceptions ({','.join(columns)}) VALUES ({placeholders})", values)
            except sqlite3.IntegrityError:
                # ### AT MOST ONE OPEN EXCEPTION PER CAUSE (the optional dedup index this build built).
                # An OPEN exception already exists — coalesce onto it rather than raise a second (entity
                # §17/§33). A concurrent raiser loses no obligation and never creates a duplicate.
                conn.rollback()
                existing = self.open_exception_for(source, etype)
                if existing is None:
                    raise
                return TransitionResult(
                    transition_id="EC-1", exception=existing, from_state=None,
                    to_state=existing.state, coalesced=True)
            created = self.require(xid)
            if schedule_timer and age_threshold_ms is not None:
                # ### AGEING RIDES A DURABLE TIMER, IN THE SAME COMMIT AS THE RAISE (machine §37, M-36,
                # AP-3's shape). The owner and the escalation threshold ride the payload so the fired age
                # timer knows who owns the resulting AGEING obligation and when it escalates. ### V10: the
                # THRESHOLD is caller-supplied with no business default — the MECHANISM is complete.
                self._arm_age_timer(created, owner, age_threshold_ms, escalation_threshold_ms,
                                    correlation_id)
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
            transition_id="EC-1", exception=created, from_state=None, to_state=EcState.OPEN,
            event_ids=(envelope.event_id,), event_names=("ExceptionRaised",), event_producer="EC-1")

    def raise_from_failure(
        self, *, classification: FailureDisposition, attempts_before_raise: int = 0, **kw: Any,
    ) -> TransitionResult:
        """EC-1 for a failure-derived exception — the classification is SUPPLIED, never inferred. A
        PERMANENT failure raises immediately with zero retries; a TRANSIENT one records that it was
        transient. Neither is decided from a message, an HTTP status or a model's opinion (M-74)."""
        return self.raise_exception(
            failure_classification=classification, attempts_before_raise=attempts_before_raise, **kw)

    # --- EC-2: acknowledgement --------------------------------------------------------------------

    def acknowledge(
        self,
        exception_id: str,
        *,
        acknowledged_by: str,
        expected: EcRecord | None = None,
        actor_id: str = "operator",
        actor_kind: str = "human",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """EC-2 — OPEN → ACKNOWLEDGED. ### AN AUTHENTICATED HUMAN SAW IT — AND THAT PROVES SEEN, NOT
        RESOLVED (entity §31, F9: actor_type=human). The obligation is unchanged: an ACKNOWLEDGED
        exception is still open work with a named owner, and it still ages. A model or a system actor may
        NOT acknowledge (EC-2's trigger is H); each is recorded under GR-1 and refused."""
        exception = expected or self.require(exception_id)
        if str(actor_kind).upper() != HUMAN:
            self._refuse_illegal(exception_id, Trigger.ACKNOWLEDGED, actor_id=actor_id)
            raise IllegalTransition(
                f"EC-2 records that an AUTHENTICATED HUMAN saw the exception (trigger H, F9 "
                f"actor_type=human). actor_kind={actor_kind!r} — a model states no facts ([C-6], GR-7) "
                f"and `system` is not a human, so neither may acknowledge. Recorded to audit and "
                f"security under GR-1.")
        human = self._require_named_human(acknowledged_by, "the acknowledging human", actor_kind="human")
        if exception.state is not EcState.OPEN:
            raise GuardNotSatisfied(
                f"EC-2 acknowledges an OPEN exception; {exception_id!r} is {exception.state.value}. An "
                f"AGEING or ESCALATED exception is already past acknowledgement, and a RESOLVED one is "
                f"decided.")
        now = format_instant(self._clock())
        return self._advance(
            exception, "EC-2", EcState.ACKNOWLEDGED, event_name="ExceptionAcknowledged",
            payload={"acknowledged_by": human}, event_producer="EC-2", actor_type="human",
            actor_id=actor_id, writes="acknowledged_by = ?, acknowledged_at = ?",
            write_args=(human, now), correlation_id=correlation_id, causation_id=causation_id,
            trace_id=trace_id, event_id=event_id, now=now)

    # --- EC-3 / EC-6: resolution ------------------------------------------------------------------

    def resolve(
        self,
        exception_id: str,
        *,
        decision_ref: str | None = None,
        decision_human_id: str | None = None,
        decision_ref_kind: str = DECISION_KIND_AUDIT,
        expected: EcRecord | None = None,
        actor_id: str = "operator",
        actor_kind: str = "human",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """EC-3 (from OPEN/ACKNOWLEDGED) / EC-6 (from ESCALATED) → RESOLVED. ### CLOSURE IS AN EVENT WITH
        A `decision_ref` THAT RESOLVES — AN EXCEPTION CLOSED WITHOUT A DECISION IS NOT CLOSED, IT IS
        FORGOTTEN (entity §16/§36, GR-14, K-1, I11, F-30).

        The decision_ref is validated by M1's landed resolver (imported, never re-written): it must
        resolve to an `audit_events` human-decision row recording an AUTHENTICATED HUMAN. A bare string,
        the string `done`, a reference to nothing, an event that is not a human decision, and a
        human-decision event recorded by automation (ER-11) each FAIL — recorded under GR-1 and refused.
        ### A MODEL MAY NEVER RESOLVE, at any confidence including 1.0 ([C-6], GR-7, GR-8, ER-9). ###
        RESOLVING AN AGEING EXCEPTION IS ILLEGAL — AGEING is in neither from-set (task §3.4)."""
        exception = expected or self.require(exception_id)
        # ### A MODEL NEVER RESOLVES (entity §35, [C-6], GR-7, ER-9). Recorded and refused.
        if str(actor_kind).upper() != HUMAN:
            self._refuse_illegal(exception.exception_id, Trigger.RESOLVED, actor_id=actor_id)
            raise IllegalTransition(
                f"resolution requires an AUTHENTICATED HUMAN (EC-3/EC-6, entity §35, [C-6], ER-9). "
                f"actor_kind={actor_kind!r} — a model, a counterparty, a confidence score and a timer "
                f"are each data, never a decision, and none resolves an exception. Confidence is not a "
                f"guard input at any value including 1.0 (GR-8). Recorded to audit and security under "
                f"GR-1.")
        # ### THE FROM-SET IS THE GUARD, READ LITERALLY (machine §14/§15, task §3.4). AGEING is in
        # neither EC-3 nor EC-6, so resolving from AGEING is ILLEGAL; a RESOLVED one is terminal.
        if exception.state not in (EC3_FROM | EC6_FROM):
            self._refuse_illegal(exception.exception_id, Trigger.RESOLVED, actor_id=actor_id)
            raise IllegalTransition(
                f"an exception resolves from OPEN/ACKNOWLEDGED (EC-3) or ESCALATED (EC-6); "
                f"{exception_id!r} is {exception.state.value}. Resolving an AGEING exception directly is "
                f"an ILLEGAL transition — AGEING is in neither from-set, and nothing at all moves a "
                f"RESOLVED one (registry §4: RESOLVED is terminal). Recorded to audit and security under "
                f"GR-1.")
        # ### CLOSURE WITHOUT A VALID decision_ref IS ILLEGAL (machine §15, target spec §12.9, GR-14).
        ref = str(decision_ref or "").strip()
        if not ref:
            self._refuse_illegal(exception.exception_id, Trigger.AUTO_CLOSE, actor_id=actor_id)
            raise IllegalTransition(
                "closure without a decision_ref is ILLEGAL (machine §15, GR-14, F-30): an exception "
                "closed without a decision is not closed, it is FORGOTTEN. There is no AutoClose, no "
                "inactivity close, and the string 'done' is not a decision. Recorded under GR-1.")
        human = self._require_named_human(decision_human_id, "the human behind decision_ref",
                                          actor_kind="human")
        # ### THE decision_ref MUST RESOLVE, NOT MERELY BE NON-NULL (K-1). M1's resolver is imported and
        # called — never a second implementation of "does this decision_ref resolve" (CLAUDE.md rule 17).
        try:
            resolved: Any = resolve_decision_ref(
                self._conn, tenant=self._tenant, ref=ref, kind=decision_ref_kind)
        except DecisionRefUnresolvable as exc:
            self._refuse_illegal(exception.exception_id, Trigger.AUTO_CLOSE, actor_id=actor_id)
            raise IllegalTransition(
                f"decision_ref {ref!r} does not RESOLVE (K-1, GR-14): {exc} The CHECK is not 'non-null' "
                f"but 'resolves to an authenticated human decision'. Recorded under GR-1.") from exc
        del resolved
        row_id = "EC-3" if exception.state in EC3_FROM else "EC-6"
        return self._advance(
            exception, row_id, EcState.RESOLVED, event_name="ExceptionResolved",
            payload={"decision_ref": ref}, event_producer=row_id, actor_type="human",
            actor_id=actor_id,
            writes="decision_ref = ?, decision_ref_kind = ?, decision_human_id = ?",
            write_args=(ref, decision_ref_kind, human), correlation_id=correlation_id,
            causation_id=causation_id, trace_id=trace_id, event_id=event_id,
            after_write=self._cancel_timers_after(exception.exception_id, "resolved (EC-3/EC-6)"))

    # --- EC-4 / EC-5: ageing and escalation, on the durable-timer substrate ------------------------

    def age(
        self,
        exception_id: str,
        *,
        escalation_threshold_ms: int | None = None,
        expected: EcRecord | None = None,
        actor_id: str = "timer",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """EC-4 — {OPEN, ACKNOWLEDGED} → AGEING on the durable AGE timer. ### IT GETS LOUDER, IT NEVER
        RESOLVES (machine §16/§37); AGEING REMAINS HUMAN-OWNED. Ageing an already-AGEING or ESCALATED
        exception is ILLEGAL — AGEING/ESCALATED/RESOLVED are not in EC-4's from-set (task §3.4). Arms the
        escalation timer (EC-5) IN THE SAME COMMIT."""
        exception = expected or self.require(exception_id)
        if exception.state not in EC4_FROM:
            self._refuse_illegal(exception.exception_id, Trigger.TIMER_FIRED, actor_id=actor_id)
            raise IllegalTransition(
                f"EC-4 ages an OPEN or ACKNOWLEDGED exception; {exception_id!r} is "
                f"{exception.state.value}. A timer may not re-age an already-AGEING or ESCALATED "
                f"exception, and nothing moves a RESOLVED one. Recorded to audit and security under "
                f"GR-1.")
        now = format_instant(self._clock())
        after = (self._arm_escalation_after(exception_id, escalation_threshold_ms, now, correlation_id)
                 if escalation_threshold_ms is not None else None)
        return self._advance(
            exception, "EC-4", EcState.AGEING, event_name="ExceptionAgeing", payload={},
            event_producer="EC-4", actor_type="system", actor_id=actor_id,
            writes="ageing_at = ?", write_args=(now,), correlation_id=correlation_id,
            causation_id=causation_id, trace_id=trace_id, event_id=event_id, now=now,
            after_write=after)

    def escalate(
        self,
        exception_id: str,
        *,
        expected: EcRecord | None = None,
        actor_id: str = "timer",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """EC-5 — AGEING → ESCALATED on the durable escalation timer. ### IT ESCALATES AND NEVER RESOLVES
        (machine §37); ESCALATED REMAINS HUMAN-OWNED. Escalating a non-AGEING exception is ILLEGAL."""
        exception = expected or self.require(exception_id)
        if exception.state is not EcState.AGEING:
            self._refuse_illegal(exception.exception_id, Trigger.TIMER_FIRED, actor_id=actor_id)
            raise IllegalTransition(
                f"EC-5 escalates an AGEING exception; {exception_id!r} is {exception.state.value}. A "
                f"timer never escalates an OPEN, ESCALATED or RESOLVED exception, and it never resolves "
                f"one. Recorded to audit and security under GR-1.")
        now = format_instant(self._clock())
        return self._advance(
            exception, "EC-5", EcState.ESCALATED, event_name="ExceptionEscalated", payload={},
            event_producer="EC-5", actor_type="system", actor_id=actor_id,
            writes="escalation_at = ?", write_args=(now,), correlation_id=correlation_id,
            causation_id=causation_id, trace_id=trace_id, event_id=event_id, now=now)

    def handle_timer_fired(self, trigger: TimerFired, **kw: Any) -> TransitionResult | None:
        """### THE AGE AND ESCALATION TIMERS RIDE DURABLE TIMERS — NEVER A SLEEP OR A SWEEP (machine §37,
        M-36). The age timer fires EC-4; the escalation timer fires EC-5. ### NO TIMER REACHES RESOLVED —
        a timer that resolves is structurally impossible because no timer_kind maps to a resolution. A
        timer fires AT LEAST once and the machine acts EXACTLY once: a redelivered timer whose transition
        already happened is a NO-OP (GR-4)."""
        actor_id = kw.get("actor_id", "timer")
        exception = self.get(trigger.aggregate_id)
        if trigger.timer_kind == TIMER_KIND_AGE:
            if exception is None or exception.state not in EC4_FROM:
                # A redelivered age timer against an already-aged / resolved exception is a no-op (GR-4).
                return None
            payload = trigger.payload or {}
            return self.age(
                trigger.aggregate_id, escalation_threshold_ms=payload.get("escalation_threshold_ms"),
                correlation_id=trigger.correlation_id, causation_id=trigger.causation_id,
                actor_id=actor_id)
        if trigger.timer_kind == TIMER_KIND_ESCALATION:
            if exception is None or exception.state is not EcState.AGEING:
                # A redelivered escalation timer against a non-AGEING exception is a no-op (GR-4).
                return None
            return self.escalate(
                trigger.aggregate_id, correlation_id=trigger.correlation_id,
                causation_id=trigger.causation_id, actor_id=actor_id)
        # ### A TIMER OF ANY OTHER KIND IS ILLEGAL — no M9 timer resolves (machine §15/§37).
        self._refuse_illegal(trigger.aggregate_id, Trigger.TIMER_RESOLVE, actor_id=actor_id)
        raise IllegalTransition(
            f"a durable timer fired with kind {trigger.timer_kind!r} on exception "
            f"{trigger.aggregate_id!r}; the only M9 timers are the age threshold (EC-4) and the "
            f"escalation threshold (EC-5). No timer reaches RESOLVED — a timer never resolves an "
            f"exception (machine §37). Recorded to audit and security under GR-1.")

    # --- EC-7: severity reassessment (a FIELD mutation, NOT a state change) ------------------------

    def change_severity(
        self,
        exception_id: str,
        *,
        severity: str | EcSeverity,
        changed_by: str,
        reason: str,
        expected: EcRecord | None = None,
        actor_id: str = "operator",
        actor_kind: str = "human",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """EC-7 — ### SEVERITY IS A FIELD; REASSESSING IT DOES NOT CHANGE STATE (machine §14, F9). From
        {OPEN, ACKNOWLEDGED, ESCALATED} only — NOT AGEING, NOT RESOLVED. The event carries `severity`,
        `previous_severity`, `changed_by` AND `reason` — all four required — so a rebuild reproduces the
        LIVE severity by folding the recorded change events, never the ORIGINAL (F9). ### A MODEL MAY
        NEVER CHANGE SEVERITY: actor_type ∈ {human, system}, never `model` (GR-7)."""
        exception = expected or self.require(exception_id)
        if str(actor_kind).lower() == "model":
            self._refuse_illegal(exception.exception_id, Trigger.SEVERITY_CHANGE, actor_id=actor_id)
            raise IllegalTransition(
                "a model may never change an exception's severity (F9: actor_type ∈ {human, system}, "
                "GR-7): under-stating a Sev-0 by model opinion is a safety loss, not a cosmetic one. "
                "Recorded to audit and security under GR-1.")
        new_sev = _severity_value(severity)
        reason_text = str(reason or "").strip()
        if not reason_text:
            raise GuardNotSatisfied(
                "a severity change requires a reason (F9: reason is REQUIRED): a reassessment with no "
                "recorded reason is a number changing in the dark.")
        actor_type = "human" if str(actor_kind).upper() == HUMAN else "system"
        who = (self._require_named_human(changed_by, "the human changing severity", actor_kind="human")
               if actor_type == "human" else _require_text(changed_by, "changed_by"))
        if exception.state not in EC7_FROM:
            self._refuse_illegal(exception.exception_id, Trigger.SEVERITY_CHANGE, actor_id=actor_id)
            raise IllegalTransition(
                f"EC-7 reassesses severity from OPEN, ACKNOWLEDGED or ESCALATED; {exception_id!r} is "
                f"{exception.state.value}. AGEING is NOT in the from-set, and a RESOLVED exception is "
                f"decided. Recorded to audit and security under GR-1.")
        previous = exception.severity.value
        # ### EC-7 DOES NOT CHANGE state — the target IS the current state, so the version-advances
        # trigger (which fires only on a state change) does not fire and this may bump version freely. A
        # build that implemented severity as five more states would have minted a sixth state by another
        # name; here it is one column and one registered event.
        return self._advance(
            exception, "EC-7", exception.state, event_name="ExceptionSeverityChanged",
            payload={"severity": new_sev, "previous_severity": previous, "changed_by": who,
                     "reason": reason_text},
            event_producer="EC-7", actor_type=actor_type, actor_id=actor_id,
            writes="severity = ?", write_args=(new_sev,), correlation_id=correlation_id,
            causation_id=causation_id, trace_id=trace_id, event_id=event_id)

    # --- replay & park/drain ----------------------------------------------------------------------

    def reference_resolver(self, aggregate_type: str, aggregate_id: str) -> bool:
        """M-26's question, tenant-scoped. A reference to a not-yet-existing exception is PARKED and
        drained the moment it lands — the same mechanism M3/M5/M6/M7/M8 use, no second parking invented."""
        if aggregate_type == AGGREGATE_TYPE:
            return self._conn.execute(
                "SELECT 1 FROM exceptions WHERE tenant = ? AND exception_id = ?",
                (self._tenant, aggregate_id)).fetchone() is not None
        return True

    def consume_event(
        self, envelope: EventEnvelope, *, inbox: DedupInbox | None = None,
        requires_existing: tuple[tuple[str, str], ...] = (), drain: bool = True,
    ) -> ConsumedTransition:
        """Consume one canonical `exception` event idempotently through P5's dedup inbox.

        ### REPLAY RECONSTRUCTS; IT NEVER MANUFACTURES (GR-11, K-3, AC-SAFE-019). Reconstruction advances
        an EXISTING durable row's state to match a state-marking event WITHOUT re-deciding it; a
        redelivery is a no-op (GR-4). It NEVER independently resolves an exception and — above all — CAN
        NEVER MANUFACTURE A `decision_ref`, because it only moves `state` to what the event recorded."""
        box = inbox or DedupInbox(
            self._conn, tenant=self._tenant, consumer_id=CONSUMER_ID, clock=self._clock,
            reference_resolver=self.reference_resolver)
        outcome: dict[str, Any] = {"transition": None, "refusal": None}

        def handler(event: EventEnvelope) -> None:
            exception = self.get(event.aggregate_id)
            if exception is None:
                outcome["refusal"] = (
                    f"{event.event_name} references exception {event.aggregate_id!r}, which does not "
                    f"exist for tenant {self._tenant!r}. Consumed once, nothing persisted.")
                return
            target = _event_target_state(event)
            if target is None or exception.state is target or exception.is_terminal:
                return
            outcome["transition"] = self._reconstruct_locked(exception, target)

        default_reqs: tuple[tuple[str, str], ...] = ((AGGREGATE_TYPE, envelope.aggregate_id),)
        result = box.consume(
            envelope, handler,
            requires_existing=(requires_existing or default_reqs),
            drain_handler_for=((lambda _env: handler) if drain else None))
        return ConsumedTransition(
            consume=result, transition=outcome["transition"], refusal=outcome["refusal"])

    def rebuild(self, exception_id: str, *,
                events: list[EventEnvelope] | None = None) -> ReconstructedException:
        """### A FULL-HISTORY FOLD OF ONE EXCEPTION — SANDBOXED, ZERO AUTHORITY (GR-11, ER-2, K-3).

        It reconstructs `state` and the CURRENT SEVERITY from the event stream and creates NOTHING: no
        resolution, no decision_ref, no new authority, the outside world untouched, no state flip. ### THE
        SEVERITY IS FOLDED FROM ExceptionRaised + EVERY ExceptionSeverityChanged, IN aggregate_version
        ORDER — NEVER READ FROM THE LIVE ROW (entity §34, events/registry.md §8). An open exception stays
        open and its frozen entity stays blocked (machine §36)."""
        stream = events if events is not None else self._event_stream(exception_id)
        state: EcState | None = None
        severity: EcSeverity | None = None
        # Fold in aggregate_version order so a severity change at a higher version wins. ### THE MUTABLE
        # state and severity come ONLY from the events; whether the exception freezes an entity is an
        # IMMUTABLE creation attribute (trg_exceptions_identity_immutable enforces it and F9's payload
        # does not carry it), so reading it is reconstructing a structural fact, NOT the mutable state or
        # authority replay may never manufacture.
        for event in sorted(stream, key=lambda e: (e.aggregate_version or 0)):
            target = _event_target_state(event)
            if target is not None:
                state = target
            elif event.event_name == "ExceptionRaised" and state is None:
                state = EcState.OPEN
            if event.event_name in ("ExceptionRaised", "ExceptionSeverityChanged"):
                raw = event.payload.get("severity")
                if raw in EXCEPTION_SEVERITIES:
                    severity = EcSeverity(raw)
        row = self.get(exception_id)
        freezes = bool(row.freezes_entity) if row is not None else False
        frozen = freezes and state is not None and state not in TERMINAL_STATES
        return ReconstructedException(
            exception_id=exception_id, state=state, severity=severity, frozen=frozen,
            new_authority=0, external_effects=0, decision_refs_minted=0, state_flips=0)

    # --- shared transition plumbing ---------------------------------------------------------------

    def _advance(
        self, exception: EcRecord, transition_id: str, to_state: EcState, *,
        event_name: str, payload: Mapping[str, Any], event_producer: str, actor_type: str,
        actor_id: str, writes: str, write_args: tuple[Any, ...], correlation_id: str | None,
        causation_id: str | None, trace_id: str | None, event_id: str | None,
        now: str | None = None, after_write: Callable[[str], None] | None = None,
    ) -> TransitionResult:
        """One transition: the state row and its event, or neither (GR-2). OCC on the version the decision
        was read at (GR-3): zero rows is a lost update that raises, never a silent overwrite. EC-7 passes
        `to_state == exception.state` (a severity FIELD change, no state change) and so advances version
        without tripping the state-change version trigger."""
        now = now or format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            set_clause = "state = ?, version = version + 1, updated_at = ?"
            if writes:
                set_clause += ", " + writes
            args: list[Any] = [to_state.value, now, *write_args,
                               self._tenant, exception.exception_id, exception.state.value,
                               exception.version]
            cursor = conn.execute(
                f"UPDATE exceptions SET {set_clause} "
                f"WHERE tenant = ? AND exception_id = ? AND state = ? AND version = ?", args)
            if cursor.rowcount != 1:
                raise StateConflict(
                    f"{transition_id} matched {cursor.rowcount} rows for "
                    f"{exception.exception_id!r}: it moved under us (GR-3). Reload — a lost update on an "
                    f"exception is refused, never a write that silently wins.")
            if after_write is not None:
                after_write(now)
            after = self.require(exception.exception_id)
            envelope = self._envelope(
                event_name=event_name, event_producer=event_producer, exception=after,
                aggregate_version=self._next_version(exception.exception_id), actor_type=actor_type,
                actor_id=actor_id, payload=dict(payload), correlation_id=correlation_id,
                causation_id=causation_id, trace_id=trace_id, event_id=event_id, now=now)
            self._outbox().emit(envelope)
            conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        return TransitionResult(
            transition_id=transition_id, exception=after, from_state=exception.state,
            to_state=to_state, event_ids=(envelope.event_id,), event_names=(event_name,),
            event_producer=event_producer)

    def _reconstruct_locked(self, exception: EcRecord, target: EcState) -> TransitionResult:
        """Advance a durable row to match a durable event — reconstruction, not a live transition.

        Runs inside the inbox's own commit (M-24): no BEGIN, no COMMIT. ### IT MINTS NO AUTHORITY and
        NEVER MANUFACTURES A decision_ref: it moves only `state` (and the ageing/escalation stamp) to what
        the event already recorded. A reconstruction to RESOLVED copies the state the event proved a human
        decided; it does not decide, and it writes no decision_ref of its own."""
        conn = self._conn
        now = format_instant(self._clock())
        writes = ["state = ?", "version = version + 1", "updated_at = ?"]
        args: list[Any] = [target.value, now]
        if target is EcState.AGEING and exception.ageing_at is None:
            writes.append("ageing_at = ?")
            args.append(now)
        if target is EcState.ESCALATED and exception.escalation_at is None:
            writes.append("escalation_at = ?")
            args.append(now)
        conn.execute(
            f"UPDATE exceptions SET {', '.join(writes)} "
            f"WHERE tenant = ? AND exception_id = ? AND state = ?",
            (*args, self._tenant, exception.exception_id, exception.state.value))
        after = self.require(exception.exception_id)
        return TransitionResult(
            transition_id="replay", exception=after, from_state=exception.state, to_state=target)

    # --- the durable timers -----------------------------------------------------------------------

    def _arm_age_timer(self, exception: EcRecord, owner: str, age_threshold_ms: int,
                       escalation_threshold_ms: int | None, correlation_id: str | None) -> None:
        """Arm the durable AGE timer IN THE CALLER'S OPEN TRANSACTION (machine §37; AP-3's shape). The
        owner and the escalation threshold ride the payload so the fired age timer knows who owns the
        AGEING obligation and when it escalates. No in-memory sleep, no second timer mechanism."""
        fire_at = _parse_instant(exception.created_at) + timedelta(milliseconds=int(age_threshold_ms))
        payload: dict[str, Any] = {"owner_id": owner}
        if escalation_threshold_ms is not None:
            payload["escalation_threshold_ms"] = escalation_threshold_ms
        DurableTimers(self._conn, tenant=self._tenant, clock=self._clock).schedule(
            timer_id=f"{TIMER_KIND_AGE}:{exception.exception_id}", aggregate_type=AGGREGATE_TYPE,
            aggregate_id=exception.exception_id, timer_kind=TIMER_KIND_AGE, fire_at=fire_at,
            payload=payload, correlation_id=correlation_id or exception.exception_id)

    def _arm_escalation_after(self, exception_id: str, escalation_threshold_ms: int, ageing_at: str,
                              correlation_id: str | None) -> Callable[[str], None]:
        """### THE ESCALATION TIMER, ARMED IN THE SAME COMMIT AS THE AGEING TRANSITION (EC-4 → EC-5). The
        THRESHOLD is caller-supplied with no business default (V10, task §3.11); the MECHANISM is
        complete. With no threshold, no escalation timer is armed and the exception ages without silently
        escalating — the fail-closed default is ages, escalates, NEVER expires."""
        def _arm(_now: str) -> None:
            fire_at = _parse_instant(ageing_at) + timedelta(milliseconds=int(escalation_threshold_ms))
            DurableTimers(self._conn, tenant=self._tenant, clock=self._clock).schedule(
                timer_id=f"{TIMER_KIND_ESCALATION}:{exception_id}", aggregate_type=AGGREGATE_TYPE,
                aggregate_id=exception_id, timer_kind=TIMER_KIND_ESCALATION, fire_at=fire_at,
                correlation_id=correlation_id or exception_id)
        return _arm

    def _cancel_timers_after(self, exception_id: str, reason: str) -> Callable[[str], None]:
        """Cancel every scheduled timer on this aggregate — what a resolution does, so a RESOLVED
        exception does not later fire an age or escalation timer. Correctness does not DEPEND on it —
        every timer handler no-ops on a non-live state (GR-4) — but a terminal row should not leave a
        live timer armed. ### A TIMER NEVER RESOLVES: cancelling a timer at resolution is the opposite of
        a timer resolving one."""
        def _cancel(_now: str) -> None:
            DurableTimers(self._conn, tenant=self._tenant, clock=self._clock).cancel_for_aggregate(
                AGGREGATE_TYPE, exception_id, reason=reason)
        return _cancel

    # --- the named-human guard --------------------------------------------------------------------

    def _require_named_human(self, human_id: str | None, role: str, *, actor_kind: str) -> str:
        """### A NAMED ACTIVE HUMAN, FK-BACKED (entity §10/§16/§35/§37, machine §5, I1, AC-SAFE-028). "A
        human" is decoration while the column is free text: it must be a recorded, ACTIVE human of THIS
        tenant (M1's precedent). `system` is not a human, a model is not a human, an OFFBOARDED human may
        not own a new exception, and a wrong-tenant or forged human fails closed."""
        text = str(human_id or "").strip()
        if str(actor_kind).lower() == "model":
            raise GuardNotSatisfied(
                f"{role} cannot be a model actor (ER-9, [C-6]): a model states no facts and owns no "
                f"obligation. The caller supplies a named ACTIVE human; the machine never picks one.")
        if not text:
            raise GuardNotSatisfied(
                f"{role} is a named human, FK-backed into tenant_humans (entity §16/§37, I1): an "
                f"ownerless or unnamed value is a silent drop wearing a status.")
        row = self._conn.execute(
            "SELECT state FROM tenant_humans WHERE tenant = ? AND human_id = ?",
            (self._tenant, text)).fetchone()
        if row is None or row["state"] != "ACTIVE":
            raise GuardNotSatisfied(
                f"{role} names {text!r}, who is not an ACTIVE recorded human of {self._tenant!r}. A "
                f"forged, inactive/offboarded or wrong-tenant human fails closed — the human is "
                f"FK-backed, not a free-text string, and `system` is not a human.")
        return text

    # --- F14 recording ----------------------------------------------------------------------------

    def _refuse_illegal(self, aggregate_id: str, trigger: Trigger, *, actor_id: str) -> None:
        """### GR-1 — record `IllegalTransitionAttempted` to audit AND security, then the caller raises.
        The illegal shapes machine §15 names by hand — closure without a decision_ref, AutoClose /
        inactivity, resolving from AGEING, ageing an already-aged exception, a model acting — all pass
        here. M9 records this tripwire; it engages NO brake (the Sev-0 detectors do that at their
        source)."""
        exception = self.get(aggregate_id)
        state = exception.state.value if exception is not None else "-"
        self._record_f14(
            aggregate_id=aggregate_id, event_name="IllegalTransitionAttempted",
            identity_suffix=f"{trigger.value}|{actor_id}",
            payload={"machine": "M9", "state": state, "trigger": trigger.value,
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

    def _event_stream(self, exception_id: str) -> list[EventEnvelope]:
        rows = self._conn.execute(
            "SELECT envelope_json FROM event_outbox WHERE tenant = ? AND aggregate_type = ? "
            "AND aggregate_id = ? ORDER BY aggregate_version, sequence",
            (self._tenant, AGGREGATE_TYPE, exception_id)).fetchall()
        return [EventEnvelope.from_json(r["envelope_json"]) for r in rows]

    def _next_version(self, exception_id: str) -> int:
        return self._outbox().last_emitted_version(AGGREGATE_TYPE, exception_id) + 1

    def _outbox(self):
        from .event_outbox import TransactionalOutbox
        return TransactionalOutbox(self._conn, tenant=self._tenant, clock=self._clock)

    def _raise_envelope(
        self, exception: EcRecord, *, actor_kind: str, actor_id: str, correlation_id: str | None,
        causation_id: str | None, trace_id: str | None, event_id: str | None, now: str,
    ) -> EventEnvelope:
        """The `ExceptionRaised` envelope on the `exception` aggregate at version 1. The payload carries
        the two required F9 fields (severity, source_ref) and only the optional fields that are set
        (exposure, specific_question, sub_status), because the outbox validates in PRODUCER mode and an
        undeclared field is a refusal — which is why the immutable `freezes_entity` is NOT a payload
        field and a rebuild reads it as the structural creation attribute it is (see `rebuild`)."""
        actor_type = "human" if str(actor_kind).upper() == HUMAN else str(actor_kind).lower()
        payload: dict[str, Any] = {"severity": exception.severity.value,
                                   "source_ref": exception.source_ref}
        if exception.exposure is not None:
            payload["exposure"] = exception.exposure
        if exception.specific_question is not None:
            payload["specific_question"] = exception.specific_question
        if exception.sub_status is not None:
            payload["sub_status"] = exception.sub_status
        return EventEnvelope(
            event_id=event_id or str(uuid.uuid4()), event_name="ExceptionRaised",
            event_version=CONTRACTS["ExceptionRaised"].current_version, occurred_at=now,
            recorded_at=now, tenant_id=self._tenant, aggregate_type=AGGREGATE_TYPE,
            aggregate_id=exception.exception_id, aggregate_version=1,
            previous_aggregate_version=None, causation_id=causation_id,
            correlation_id=correlation_id or exception.exception_id,
            producer_component=self._component, producer_transition_id="EC-1",
            actor_type=actor_type, actor_id=actor_id,
            trace_id=trace_id or f"trace-{exception.exception_id}", payload=payload,
            accountable_owner_id=exception.owner_id)

    def _envelope(
        self, *, event_name: str, event_producer: str, exception: EcRecord, aggregate_version: int,
        actor_type: str, actor_id: str, payload: Mapping[str, Any], correlation_id: str | None,
        causation_id: str | None, trace_id: str | None, event_id: str | None, now: str,
    ) -> EventEnvelope:
        """One canonical envelope on the `exception` aggregate for EC-2…EC-7. F9 is order-tolerant, so no
        `previous_aggregate_version` travels on it. The human owner, assigned at creation, is pinned as
        the accountable owner so the audit names who owns the obligation."""
        return EventEnvelope(
            event_id=event_id or str(uuid.uuid4()), event_name=event_name,
            event_version=CONTRACTS[event_name].current_version, occurred_at=now, recorded_at=now,
            tenant_id=self._tenant, aggregate_type=AGGREGATE_TYPE,
            aggregate_id=exception.exception_id, aggregate_version=aggregate_version,
            previous_aggregate_version=None, causation_id=causation_id,
            correlation_id=correlation_id or exception.exception_id,
            producer_component=self._component, producer_transition_id=event_producer,
            actor_type=actor_type, actor_id=actor_id,
            trace_id=trace_id or f"trace-{exception.exception_id}", payload=dict(payload),
            accountable_owner_id=exception.owner_id)


# ------------------------------------------------------------------------------------- plumbing

def _severity_value(severity: str | EcSeverity) -> str:
    value = severity.value if isinstance(severity, EcSeverity) else str(severity)
    if value not in EXCEPTION_SEVERITIES:
        raise MalformedException(
            f"severity {value!r} is not one of {list(EXCEPTION_SEVERITIES)} (entity §12, registry §4). "
            f"SEV0 | SEV1 | SEV2 and no fourth; the ExceptionRaised/ExceptionSeverityChanged contracts "
            f"and the database CHECK all refuse another.")
    return value


def _source_kind_value(source_kind: str) -> str:
    value = str(source_kind or "").strip()
    if value not in SOURCE_KINDS:
        raise MalformedException(
            f"source_kind {value!r} is not one of the closed vocabulary {list(SOURCE_KINDS)} (### "
            f"M9-AQ-3, entity §9): the source reference is polymorphic and its kind is what tells a "
            f"reader which machine raised it. There is no other kind.")
    return value


def _sub_status_value(sub_status: str | EcSubStatus | None) -> str | None:
    if sub_status is None:
        return None
    value = sub_status.value if isinstance(sub_status, EcSubStatus) else str(sub_status)
    if value not in SUB_STATUSES:
        raise MalformedException(
            f"sub_status {value!r} is not one of {list(SUB_STATUSES)} (machine header): sub_status is a "
            f"FIELD from a closed vocabulary DISJOINT from the five states, never a lifecycle state.")
    return value


def _require_classification(
    classification: FailureDisposition | str | None,
) -> FailureDisposition | None:
    """### THE FAILURE CLASSIFICATION IS SUPPLIED, NEVER INFERRED FROM A MESSAGE (entity §13, M-74). A
    `FailureDisposition` (or its exact enum value) is accepted; ANY other string is REFUSED, because
    mapping a message / an HTTP status / a vendor error to PERMANENT is the classifier that must not
    exist. There is no message-to-class inference function in this module."""
    if classification is None:
        return None
    if isinstance(classification, FailureDisposition):
        return classification
    text = str(classification)
    if text in FAILURE_CLASSIFICATIONS:
        return FailureDisposition(text)
    raise MalformedException(
        f"failure_classification {classification!r} is not a supplied FailureDisposition (one of "
        f"{list(FAILURE_CLASSIFICATIONS)}): TRANSIENT vs PERMANENT is SUPPLIED as an enumerated value, "
        f"never INFERRED from a message, an HTTP status, a vendor error string or a model's opinion "
        f"(M-74: a catch-all base class is NOT a classification). Mapping an error to a class is P9+ "
        f"adapter work, not M9's.")


def _event_target_state(event: EventEnvelope) -> EcState | None:
    """The state an exception event reconstructs to, or None for an event that is not a state marker
    (ExceptionRaised's creation marker is handled by the rebuild; ExceptionSeverityChanged changes a
    FIELD, not the state; an F14 event riding the aggregate does not move the state)."""
    name = event.event_name
    if name == "ExceptionAcknowledged":
        return EcState.ACKNOWLEDGED
    if name == "ExceptionAgeing":
        return EcState.AGEING
    if name == "ExceptionEscalated":
        return EcState.ESCALATED
    if name == "ExceptionResolved":
        return EcState.RESOLVED
    # ExceptionRaised (creation marker), ExceptionSeverityChanged (a field change),
    # IllegalTransitionAttempted, etc. — none move the lifecycle state.
    return None


def _parse_instant(text: str) -> datetime:
    """One canonical RFC-3339 UTC-milliseconds string back to an aware datetime."""
    normalized = text.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).astimezone(timezone.utc)


def _require_text(value: str, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise MalformedException(f"{field_name} is required and was empty.")
    return text


def _row_to_exception(row: Any) -> EcRecord:
    return EcRecord(
        tenant=row["tenant"], exception_id=row["exception_id"], type=row["type"],
        severity=EcSeverity(row["severity"]), state=EcState(row["state"]), version=row["version"],
        owner_id=row["owner_id"], source_ref=row["source_ref"], source_kind=row["source_kind"],
        entity_ref=row["entity_ref"], frozen_field=row["frozen_field"],
        freezes_entity=bool(row["freezes_entity"]), sub_status=row["sub_status"],
        failure_classification=row["failure_classification"], exposure=row["exposure"],
        specific_question=row["specific_question"], summary=row["summary"],
        acknowledged_at=row["acknowledged_at"], acknowledged_by=row["acknowledged_by"],
        ageing_at=row["ageing_at"], escalation_at=row["escalation_at"],
        decision_ref=row["decision_ref"], decision_ref_kind=row["decision_ref_kind"],
        decision_human_id=row["decision_human_id"], created_at=row["created_at"])


# Re-exported so a caller reads one name rather than importing the migration for a constant.
STATES: tuple[str, ...] = EXCEPTION_STATES
SEVERITIES: tuple[str, ...] = EXCEPTION_SEVERITIES
