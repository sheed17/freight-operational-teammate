"""Machine M10 — the Compensation: the undoing of an external effect that should not have happened, and
the one machine in Neyma whose whole job is to prove that an UNDO gets NO privileged path.

    ### A COMPENSATION IS THE UNDOING OF AN EXTERNAL EFFECT THAT SHOULD NOT HAVE HAPPENED.
    ### THE COMPENSATION IS ITSELF A SEPARATELY GATED EXTERNAL EFFECT. IT RECEIVES NO PRIVILEGED PATH.
    ### YOU CANNOT UNDO WHAT YOU CANNOT PROVE YOU DID.
    ### AN "UNDO" THAT BYPASSES THE GATES IS AN UNGATED WRITE WITH A GOOD EXCUSE.

A carrier's POD was bound to the wrong load. An invoice for GBP 2,850 went out to Acme on the strength
of it. A human corrects the binding, and that invoice now rests on a fact known to be wrong. The money
left the building; something has to credit it back.

The tempting implementation is a rollback: find the effect, call the adapter's void endpoint, mark the
row undone. ### THAT IS A SECOND, UNGATED WRITE ROUTE INTO A CUSTOMER'S ACCOUNTING SYSTEM, reached
precisely when the system is already known to be wrong about something. So M10 does the opposite: the
credit note is a NEW external effect — its own Pipeline Instance (M2), its own policy evaluation, its own
brake check, its own human approval (M4), its own checkpoint witness (P3), its own single-use Effect
Grant (M3), its own commit key, its own readback. The `compensations` row is only the OBLIGATION to do
that, with a named human owner and the dollar amount at stake written on it from the moment it exists.

    ### COMPENSATION IS FORBIDDEN ON AN UNKNOWN OUTCOME (M-33). When the original effect's outcome is
    UNKNOWN — the TMS timed out and nobody can say whether the invoice was issued — M10 REFUSES to
    compensate at all. "Cancel invoice #560010" against a system where no such invoice exists can CREATE
    a credit note out of nothing. A human resolves the unknown to VERIFIED or FAILED first (M3's EF-5).
    Only then may compensation be considered. This is the single most important rule in this unit.

### WHAT THIS MACHINE OWNS, AND WHAT IT ONLY FEEDS.

It owns the six states and the nine CM-1…CM-5x transitions of `10-compensation.machine.md` §14, and it is
the canonical producer of the SEVEN already-registered F10 `Compensation*` events. It also EMITS the
shared F3 `RealityEstablished` (‡ coordination, producers EF-5 and CM-5) with `subject="compensation"` —
### THE EXACT REGISTERED CONTRACT, NEVER AN F10-LOCAL SECOND ONE (rule 17). It rides P5's transactional
outbox and dedup inbox exactly as M1…M9 do.

### IT FEEDS THE ONE GATE AUTHORITY, IT NEVER BECOMES ONE. CM-3 starts a NEW M2 pipeline through the
landed `PipelineMachine.propose` — M10 invokes NO adapter, performs NO direct write into a target system,
mints NO gate decision, engages NO brake, reuses NEITHER the original pipeline's authority NOR the
original Effect Grant. `checkpoint.py` stays the sole gate minter; M3 the single effect authority; the
production `GateRegistry` stays EMPTY, so the compensating action class ("adjust_invoice") resolves to the
default `HUMAN_APPROVAL_REQUIRED` — money-affecting compensation is ALWAYS human-approved, structurally,
without registering anything.

### CLOSURE OF THE LOUD STATES IMPORTS M1's RESOLVER — NEVER A SECOND ONE (rule 17, K-1). CM-1's
invalidating `decision_ref` and CM-5's reality `decision_ref` are validated by `work_item.resolve_
decision_ref`, the one K-1 executor M3 and M9 already import. A model may NEVER raise, approve, own or
resolve a compensation, at any confidence (GR-8). Confidence orders a queue and gates nothing.

### COMPENSATION_FAILED AND NOT_POSSIBLE ARE THE MOST DANGEROUS STATES THE SYSTEM CAN BE IN — reality and
the projection are KNOWN to diverge. No timer moves them, no retry loop moves them, no sweep moves them,
no reaper moves them, no model moves them; there is no automatic best-effort retry. They stay loud, keep
their named human owner and CARRY THE EXPOSURE until a human establishes reality through CM-5.

### IT SHIPS DARK. Nothing under `src/freight_recon/` imports this module; the only script that may is
`scripts/probe_phase6_compensation.py`. It joins no importer, oversight queue, dashboard, notifier or MTTR
emitter; it creates no M9 Exception row (the F10→M9 escalation seam is named and left UNWIRED, ### M10-
AQ-12); it builds no part of M11 (Policy), M12 (Rule) or M13 (Brake).
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .commit_key import (
    CanonicalOccurrence,
    LogicalEffect,
    occurrence_key_for,
)
from .event_contracts import CONTRACTS
from .event_envelope import EventEnvelope, format_instant
from .event_inbox import ConsumeResult, DedupInbox
from .fingerprint import Money
from .migrations.phase6_compensations import (
    COMPENSATION_STATES,
    HUMAN_OWNED_COMPENSATION_STATES,
    RECOVERABLE_COMPENSATION_STATES,
    TERMINAL_COMPENSATION_STATES,
)
from .pipeline_instance import PipelineMachine
from .tenant import require_tenant
from .work_item import DecisionRefUnresolvable, resolve_decision_ref

# The aggregate this machine owns. `compensation` is NOT in `STRICT_ORDER_AGGREGATE_TYPES`: the seven F10
# contracts are order-tolerant (strict_order=false), so this machine declares no `previous_aggregate_
# version` on its own events — exactly as M5/M8/M9. The shared `RealityEstablished` it emits rides the
# STRICT-ORDER `effect_grant` aggregate, and its predecessor is derived from that stream (see CM-5).
AGGREGATE_TYPE = "compensation"

# The aggregate the shared F3 `RealityEstablished` contract belongs to (its registered family default).
REALITY_AGGREGATE_TYPE = "effect_grant"

# entity §5 — the Compensation Service raises and owns compensations.
PRODUCER_COMPONENT = "compensation_service"

# The one consumer identity M10 presents to the dedup inbox. Fixed, because the dedup key is
# `(tenant, consumer_id, event_id)` and a renamed consumer would re-arm every duplicate.
CONSUMER_ID = "m10-compensation"

# GR-1's producer id for `IllegalTransitionAttempted` — the RULE, not a transition. Identical to M1..M9's.
ILLEGAL_TRANSITION_PRODUCER = "GR-1"

# A refusal advances no version; two refusals against one compensation at one version would otherwise
# collide on one idempotency identity — the poison-loop defect M1 shipped. Applied here.
ILLEGAL_ATTEMPT_IDENTITY_PREFIX = "ita_v1"

# ### THE COMPENSATING EFFECT'S ACTION CLASS (commit_key.py). A void/credit IS a Compensation (a gated
# effect); `CANONICAL_OCCURRENCE_SOURCES["adjust_invoice"]` names the field `compensation_id` and the
# entity `Compensation`, and `OCCURRENCE_RULES["adjust_invoice"]` is CANONICAL_OCCURRENCE_REQUIRED. This
# is the one action class whose occurrence source IS a Compensation, which is why the compensating effect
# uses it. Its gate is unregistered, so the checkpoint resolves it to HUMAN_APPROVAL_REQUIRED.
COMPENSATING_ACTION_CLASS = "adjust_invoice"

# The compensating operation on the original resource (the invoice). Fixed and deterministic so that CM-1
# (which computes and stores the commit key) and CM-3 (which builds the LogicalEffect for propose) agree
# byte-for-byte; the Compensation occurrence, not this string, is what makes each compensation distinct.
COMPENSATING_TARGET_OPERATION = "reverse"

# The K-1 kind M10 offers to M1's resolver for a human decision_ref — the event_outbox referent.
DECISION_KIND_AUDIT = "AUDIT_EVENT"

# The fixed cause of CM-1r's refusal (the CompensationRefused contract pins `cause="unknown_outcome"`).
REFUSAL_CAUSE_UNKNOWN = "unknown_outcome"

HUMAN = "HUMAN"

# The two established-reality outcomes CM-5 may carry (the RealityEstablished `outcome` enum). They name
# the reality of the underlying EFFECT, never the compensation's own state (### M10-AQ-5): COMPLETED is
# not in this enum, and is never emitted as an outcome.
REALITY_OUTCOMES: frozenset[str] = frozenset(("VERIFIED", "FAILED"))

# The eight M3 states, read out of the ledger — the axis CM-1/CM-1r turn on. Named here so this machine
# does not import M3 for a constant; the values match `EffectGrantState`.
ORIGINAL_VERIFIED = "VERIFIED"
ORIGINAL_UNKNOWN = "UNKNOWN_OUTCOME"

# ### THE M2 PIPELINE STATES THAT MEAN "READBACK MATCHED" (CM-4). PL-11 (READBACK_MATCHED) moves the
# executing pipeline to VERIFIED, and PL-12…PL-14 carry it on to RECORDED/PROJECTED/CLOSED — all of them
# past the readback. EXECUTED (adapter returned success, PL-10) is DELIBERATELY EXCLUDED: adapter success
# is not readback, and a return code is not completion.
POST_READBACK_PIPELINE_STATES: frozenset[str] = frozenset(
    ("VERIFIED", "RECORDED", "PROJECTED", "CLOSED"))


class M10Error(RuntimeError):
    """This machine will not do what was asked. Never degraded into a partial transition."""


class UnknownCompensation(M10Error):
    """No `compensations` row with this id exists FOR THIS TENANT. Indistinguishable from "belongs to
    another tenant" on purpose — [C-1] rejects a cross-tenant question."""


class GuardNotSatisfied(M10Error):
    """The (state, trigger) pair IS legal here and a precondition is false. No event is emitted."""


class IllegalTransition(M10Error):
    """GR-1 / [C-4]. The (state, trigger) pair is not enumerated. Raised AFTER `IllegalTransition
    Attempted` is recorded, which is the point of recording it."""


class StateConflict(M10Error):
    """A state-guarded UPDATE matched zero rows: the compensation moved under us (GR-3). Reload."""


class MalformedCompensation(M10Error):
    """The inputs are not a canonical compensation — an exposure that is not canonical Money, a blank
    owner/reason, an original effect that no ledger row backs. Fail closed; nothing is persisted."""


class OriginalNotCompensable(M10Error):
    """CM-1's guard is not satisfied: the original effect is not a VERIFIED landed effect known wrong.
    No Compensation is created and — for the six states that are neither VERIFIED nor UNKNOWN_OUTCOME —
    NO refusal variant is minted (### M10-AQ-10); the one refusal cause is fixed to unknown_outcome."""


# --------------------------------------------------------------------------------- the state set

# ### THESE ENUM CLASS NAMES ARE DELIBERATELY PREFIXED `Cm…`, NOT `Compensation…`. A canonical scan flags
# any `Compensation[A-Z]…` identifier in the machine that is not one of the SEVEN registered F10 event
# contracts — an internal type sharing that shape reads as an unregistered event name minted in the
# machine (registry §5: no machine may define a local synonym).
class CmState(str, Enum):
    REQUIRED = "REQUIRED"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    COMPENSATION_FAILED = "COMPENSATION_FAILED"
    NOT_POSSIBLE = "NOT_POSSIBLE"


class Trigger(str, Enum):
    """The closed set of driving facts, named from §14's triggers and §33's "Events consumed", plus the
    illegal `TimerFired` §14 names by hand so GR-1 answers it uniformly.

    ### `TIMER_FIRED` IS IN THIS ENUM AND HAS NO LEGAL ROW AT ANY STATE, WHICH IS THE POINT. §14's CM-5x
    declares the illegal outcome (NO timer moves COMPENSATION_FAILED, GR-6). Modelling it as a trigger
    with no legal row makes GR-1 answer it uniformly at every one of the six states — stronger than a
    special case at COMPENSATION_FAILED, and derived from the table rather than written twice.

    The values are spelled so the machine carries no `Compensation[A-Z]…` identifier other than the seven
    registered F10 event names."""

    HUMAN_APPROVED = "HumanApproved"                     # CM-2
    NO_UNDO_EXISTS = "NoCompensatingActionExists"        # CM-2n
    PIPELINE_STARTED = "PipelineStarted"                 # CM-3
    PIPELINE_VERIFIED = "PipelineVerifiedByReadback"     # CM-4
    PIPELINE_UNVERIFIED = "PipelineFailedOrUnverified"   # CM-4f
    HUMAN_ESTABLISHED_REALITY = "HumanEstablishedReality"  # CM-5
    TIMER_FIRED = "TimerFired"                           # CM-5x — ILLEGAL, no legal row anywhere


class RowKind(str, Enum):
    PRODUCER = "PRODUCER"            # emits a canonical event attributed to this transition
    NON_PRODUCING = "NON_PRODUCING"  # CM-5x only: declared ILLEGAL by the specification


# --------------------------------------------------------------------------- the transition table

@dataclass(frozen=True)
class TransitionRow:
    """One row of §14. Data, so `AC-MACH-000` can enumerate it and compare to the specification — a
    transition table written as if/elif cannot be enumerated, and a rule nobody can enumerate is a rule
    nobody can test."""

    id: str
    from_states: tuple[CmState, ...]
    to_state: CmState | None
    triggers: tuple[Trigger, ...]
    trigger_types: tuple[str, ...]     # H|S|X|T — the registry §1 codes
    kind: RowKind
    events: tuple[str, ...] = ()       # the canonical events this row emits
    consequential: bool = False        # §5: pins the decision context at emission
    illegal: bool = False              # CM-5x only
    refusal_only: bool = False         # CM-1r: a refusal, not a state change — emits, moves nothing

    @property
    def independently_fireable(self) -> bool:
        return not (self.illegal or self.refusal_only)


TRANSITIONS: tuple[TransitionRow, ...] = (
    TransitionRow(
        # ### CM-1 — the raise, from a VERIFIED effect now known wrong (M-33). A creation row (no
        # from-state): reads the ORIGINAL effect's state FROM THE LEDGER, not a caller flag.
        id="CM-1", from_states=(), to_state=CmState.REQUIRED,
        triggers=(), trigger_types=("S",), kind=RowKind.PRODUCER,
        events=("CompensationRequired",),
    ),
    TransitionRow(
        # ### CM-1r — REFUSED because the original is UNKNOWN_OUTCOME. Emits CompensationRefused{unknown},
        # persists ZERO rows, WAITS for the human (M-33). A refusal, not a state change.
        id="CM-1r", from_states=(), to_state=None,
        triggers=(), trigger_types=("S",), kind=RowKind.PRODUCER,
        events=("CompensationRefused",), refusal_only=True,
    ),
    TransitionRow(
        id="CM-2", from_states=(CmState.REQUIRED,), to_state=CmState.APPROVED,
        triggers=(Trigger.HUMAN_APPROVED,), trigger_types=("H",), kind=RowKind.PRODUCER,
        events=("CompensationApproved",), consequential=True,
    ),
    TransitionRow(
        id="CM-2n", from_states=(CmState.REQUIRED,), to_state=CmState.NOT_POSSIBLE,
        triggers=(Trigger.NO_UNDO_EXISTS,), trigger_types=("S",), kind=RowKind.PRODUCER,
        events=("CompensationImpossible",),
    ),
    TransitionRow(
        id="CM-3", from_states=(CmState.APPROVED,), to_state=CmState.EXECUTING,
        triggers=(Trigger.PIPELINE_STARTED,), trigger_types=("S",), kind=RowKind.PRODUCER,
        events=("CompensationStarted",), consequential=True,
    ),
    TransitionRow(
        id="CM-4", from_states=(CmState.EXECUTING,), to_state=CmState.COMPLETED,
        triggers=(Trigger.PIPELINE_VERIFIED,), trigger_types=("X",), kind=RowKind.PRODUCER,
        events=("CompensationCompleted",), consequential=True,
    ),
    TransitionRow(
        id="CM-4f", from_states=(CmState.EXECUTING,), to_state=CmState.COMPENSATION_FAILED,
        triggers=(Trigger.PIPELINE_UNVERIFIED,), trigger_types=("S",), kind=RowKind.PRODUCER,
        events=("CompensationFailed",),
    ),
    TransitionRow(
        id="CM-5", from_states=(CmState.COMPENSATION_FAILED, CmState.NOT_POSSIBLE),
        to_state=CmState.COMPLETED,
        triggers=(Trigger.HUMAN_ESTABLISHED_REALITY,), trigger_types=("H",), kind=RowKind.PRODUCER,
        events=("RealityEstablished",), consequential=True,
    ),
    TransitionRow(
        # ### CM-5x — ⛔ ILLEGAL (GR-6, NON_PRODUCING:GR1_ILLEGAL_REFUSAL). Declared in the table because
        # AC-MACH-000 compares the nine identifiers, and a rule that is never expressible is untestable.
        # `TIMER_FIRED` has no legal row at ANY state, so GR-1 refuses it uniformly.
        id="CM-5x", from_states=(CmState.COMPENSATION_FAILED,), to_state=None,
        triggers=(Trigger.TIMER_FIRED,), trigger_types=("T",), kind=RowKind.NON_PRODUCING,
        illegal=True,
    ),
)

TRANSITIONS_BY_ID: Mapping[str, TransitionRow] = {row.id: row for row in TRANSITIONS}

# §32 "Events emitted", derived from the table: the seven F10 contracts plus the shared RealityEstablished
# (F3). A second hand-kept list would stop matching. The contract gate refuses an envelope whose
# producer_transition_id is not among the contract's declared producers, so this is also what the outbox
# accepts from this machine.
PRODUCED_CONTRACTS: frozenset[str] = frozenset(
    ev for row in TRANSITIONS for ev in row.events)

# The F10 subset — the seven Compensation* names this machine is the canonical producer of.
F10_CONTRACTS: frozenset[str] = frozenset(
    n for n in PRODUCED_CONTRACTS if CONTRACTS[n].family == "F10")

TERMINAL_STATES: frozenset[CmState] = frozenset(CmState(s) for s in TERMINAL_COMPENSATION_STATES)
HUMAN_OWNED_STATES: frozenset[CmState] = frozenset(
    CmState(s) for s in HUMAN_OWNED_COMPENSATION_STATES)
RECOVERABLE_STATES: frozenset[CmState] = frozenset(
    CmState(s) for s in RECOVERABLE_COMPENSATION_STATES)


def legal_transitions(state: CmState, trigger: Trigger) -> tuple[TransitionRow, ...]:
    """Every independently-fireable row whose (from-state, trigger) matches. Empty ⇒ GR-1 refuses it.

    `TIMER_FIRED` matches no legal row at any state (CM-5x is `illegal`), so a timer fired at any of the
    six states is refused uniformly — that is how "no timer moves a compensation" is STRUCTURAL rather
    than a special case."""
    return tuple(
        row for row in TRANSITIONS
        if row.independently_fireable and state in row.from_states and trigger in row.triggers)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------------------------ the row

@dataclass(frozen=True)
class CmRecord:
    """One `compensations` row, as the machine reads it. The exposure is canonical `Money`, reconstructed
    from the integer minor units and the currency the row stores."""

    tenant: str
    compensation_id: str
    original_effect_id: str
    commit_key: str
    state: CmState
    version: int
    exposure: Money
    owner_id: str
    reason: str
    pipeline_instance_id: str | None
    approval_id: str | None
    reality_decision_ref: str | None
    created_at: str

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    @property
    def is_human_owned(self) -> bool:
        """### REQUIRED, COMPENSATION_FAILED and NOT_POSSIBLE are non-terminal and human-owned — two of
        them are states where reality and the projection are KNOWN to diverge (entity §42)."""
        return self.state in HUMAN_OWNED_STATES


@dataclass(frozen=True)
class TransitionResult:
    transition_id: str                  # the machine row: CM-1..CM-5x
    compensation: CmRecord | None
    from_state: CmState | None
    to_state: CmState | None
    event_ids: tuple[str, ...] = ()
    event_names: tuple[str, ...] = ()
    event_producer: str | None = None
    refused: bool = False               # CM-1r: refused on UNKNOWN_OUTCOME, zero rows
    refusal_cause: str | None = None


@dataclass(frozen=True)
class ReconstructedCompensation:
    """A full-history fold of one compensation's F10 event stream — sandboxed, zero authority (GR-11,
    ER-2, K-3). Every count of what the REBUILD created is zero: no pipeline, no grant, no claim, no
    external effect, no approval, no authority, no state flip. The compensating effect, like any effect,
    is never produced by replay."""

    compensation_id: str
    state: CmState | None
    pipelines_minted: int = 0
    grants_minted: int = 0
    claims: int = 0
    external_effects: int = 0
    approvals_minted: int = 0
    new_authority: int = 0


@dataclass(frozen=True)
class ConsumedTransition:
    consume: ConsumeResult
    transition: TransitionResult | None = None
    refusal: str | None = None

    @property
    def moved(self) -> bool:
        return self.transition is not None


# --------------------------------------------------------------------------------- the machine

class M10Machine:
    """M10, on an existing connection, bound to ONE tenant. Bound at construction so a caller cannot
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
            raise M10Error(
                "M10Machine reads columns by name and requires `row_factory = sqlite3.Row`.")
        self._conn = conn
        self._tenant = require_tenant(tenant, context="M10Machine")
        self._clock = clock or _utc_now
        self._component = producer_component

    @property
    def tenant(self) -> str:
        return self._tenant

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    # --- reads -----------------------------------------------------------------------------------

    def get(self, compensation_id: str) -> CmRecord | None:
        row = self._conn.execute(
            "SELECT * FROM compensations WHERE tenant = ? AND compensation_id = ?",
            (self._tenant, compensation_id),
        ).fetchone()
        return _row_to_compensation(row) if row is not None else None

    def require(self, compensation_id: str) -> CmRecord:
        found = self.get(compensation_id)
        if found is None:
            raise UnknownCompensation(
                f"no compensation {compensation_id!r} for tenant {self._tenant!r}. This machine does not "
                f"look outside its tenant to find out whether it exists elsewhere ([C-1]).")
        return found

    def active_for_effect(self, original_effect_id: str) -> CmRecord | None:
        """### THE DEDUP READ (entity §17). At most one ACTIVE compensation per invalidated effect — the
        partial unique index guarantees it (NOT_POSSIBLE excluded, ### M10-AQ-9)."""
        row = self._conn.execute(
            "SELECT * FROM compensations WHERE tenant = ? AND original_effect_id = ? "
            "AND state != 'NOT_POSSIBLE' ORDER BY created_at, compensation_id",
            (self._tenant, original_effect_id),
        ).fetchone()
        return _row_to_compensation(row) if row is not None else None

    def owner_queue(self, *, owner_id: str | None = None) -> list[CmRecord]:
        """### THE OWNER QUEUE IS AN ORDERING, NOT A PRODUCT. The open compensations this brokerage's
        named human owns. M10 owes the row and this tenant-first read; it does NOT build the queue UI,
        dashboard or notifier."""
        sql = "SELECT * FROM compensations WHERE tenant = ? AND state != 'COMPLETED'"
        params: list[Any] = [self._tenant]
        if owner_id is not None:
            sql += " AND owner_id = ?"
            params.append(owner_id)
        sql += " ORDER BY created_at, compensation_id"
        return [_row_to_compensation(r) for r in self._conn.execute(sql, params).fetchall()]

    # --- the compensating effect's identity -------------------------------------------------------

    def compensating_effect(self, original: "OriginalEffect", compensation_id: str) -> LogicalEffect:
        """### THE COMPENSATING EFFECT'S OWN LOGICAL IDENTITY (entity §9/§17, ADR-009, commit_key.py).

        A void/credit IS a Compensation, so the action class is `adjust_invoice`, whose occurrence source
        `CANONICAL_OCCURRENCE_SOURCES["adjust_invoice"]` names the entity `Compensation` and the field
        `compensation_id`. The occurrence is a RESOLVED `CanonicalOccurrence(entity="Compensation",
        occurrence_id=<compensation_id>)` — `occurrence_key_for` refuses everything else and fails closed
        with `UnresolvedCanonicalOccurrence` when handed nothing. The target system and resource are the
        ORIGINAL effect's (the same invoice, the same system); the operation is the fixed compensating
        one. ### THE KEY IS NEVER DERIVED FROM THE ORIGINAL — two different compensations of one invoice
        carry two distinct `compensation_id`s, hence two distinct occurrences and two distinct keys.

        Used by BOTH CM-1 (to compute and store the commit key) and CM-3 (to build the LogicalEffect for
        `propose`), so a retry of the SAME compensation converges on one commit key (commit-once)."""
        occurrence = CanonicalOccurrence(entity="Compensation", occurrence_id=compensation_id)
        occurrence_key = occurrence_key_for(COMPENSATING_ACTION_CLASS, resolved=occurrence)
        return LogicalEffect(
            tenant=self._tenant,
            action_class=COMPENSATING_ACTION_CLASS,
            target_system=original.target_system,
            target_resource_id=original.target_resource_id,
            target_operation=COMPENSATING_TARGET_OPERATION,
            occurrence_key=occurrence_key,
        )

    # --- CM-1 / CM-1r: the raise, evaluated against the LEDGER ------------------------------------

    def raise_from_correction(
        self,
        *,
        original_effect_id: str,
        owner_id: str,
        exposure: Money,
        reason: str,
        decision_ref: str,
        decision_human_id: str | None = None,
        decision_ref_kind: str = DECISION_KIND_AUDIT,
        compensation_id: str | None = None,
        actor_kind: str = "system",
        actor_id: str = "compensation",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """CM-1 / CM-1r — ### THE ONE CREATION SEAM (### M10-AQ-1). It takes the already-registered
        correction facts (M6's `ClaimCorrected` / its `propagation_obligation` name the completed effects
        that rested on the wrong binding; `CorrectionInvalidatedAnEffect` is NOT a canonical event and is
        NEVER minted here) plus a resolved `decision_ref`, and creates the Compensation.

        ### THE ORIGINAL EFFECT'S STATE IS READ FROM THE `effect_grants` LEDGER, NOT A CALLER FLAG
        (requirement 1, M-33). If it is VERIFIED and now known wrong ⇒ CM-1 (create REQUIRED). If it is
        UNKNOWN_OUTCOME ⇒ CM-1r: emit `CompensationRefused{unknown}`, persist ZERO rows, mint ZERO
        pipelines/grants/effects — it WAITS for the human. For the other six M3 states no Compensation is
        created and NO refusal variant is minted (### M10-AQ-10): the one refusal cause is fixed to
        `unknown_outcome`.

        ### THE INVALIDATING AUTHORITY IS NEVER MODEL_INFERRED (GR-8). The `decision_ref` is resolved
        through M1's landed `resolve_decision_ref` (imported, never re-implemented) — it refuses a blank
        string, a reference to nothing, a non-human-decision event, and a human-decision event recorded by
        automation (ER-11). Confidence is not a parameter; it gates nothing at any value."""
        owner = self._require_named_human(owner_id, "the compensation owner", actor_kind=actor_kind)
        exposure_money = _require_money(exposure)
        reason_text = _require_text(reason, "reason")
        original = self._require_original_effect(original_effect_id)

        # ### THE INVALIDATING decision_ref MUST RESOLVE (K-1). Resolved BEFORE any state is written, so a
        # model-inferred or automation-recorded invalidation is refused before a row exists. A compensation
        # is never raised from a MODEL_INFERRED conclusion.
        self._require_resolving_decision_ref(decision_ref, decision_ref_kind, context="the invalidating")
        if decision_human_id is not None:
            self._require_named_human(
                decision_human_id, "the human behind the invalidating decision_ref", actor_kind="human")

        # ### THE LEDGER DECIDES (requirement 1/3, M-33). Read the persisted state; act on it.
        if original.state == ORIGINAL_UNKNOWN:
            return self._refuse_on_unknown(
                original_effect_id, compensation_id=compensation_id, actor_kind=actor_kind,
                actor_id=actor_id, correlation_id=correlation_id, causation_id=causation_id,
                trace_id=trace_id, event_id=event_id)
        if original.state != ORIGINAL_VERIFIED:
            # ### THE OTHER SIX STATES — fail closed, no row, NO refusal variant (### M10-AQ-10).
            raise OriginalNotCompensable(
                f"CM-1 may create a Compensation ONLY for a VERIFIED landed effect now known wrong "
                f"(entity §21, M-33). effect {original_effect_id!r} is {original.state!r}. "
                f"UNKNOWN_OUTCOME is refused (CM-1r, waits for the human); FAILED / REVOKED / "
                f"EXPIRED_UNCLAIMED / GRANTED / CLAIMED / ATTEMPTED satisfy no guard, so no Compensation "
                f"is created — and NO refusal variant is minted, because the CompensationRefused contract "
                f"fixes `cause` to the literal {REFUSAL_CAUSE_UNKNOWN!r} (### M10-AQ-10).")

        cid = compensation_id or f"cmp-{uuid.uuid4().hex[:16]}"
        effect = self.compensating_effect(original, cid)
        commit_key = effect.key()
        resolved_ref = str(decision_ref or "").strip()
        now = format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            try:
                conn.execute(
                    "INSERT INTO compensations (tenant, compensation_id, original_effect_id, commit_key, "
                    "state, version, exposure_amount_minor, exposure_currency, owner_id, reason, "
                    "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (self._tenant, cid, original_effect_id, commit_key, CmState.REQUIRED.value, 1,
                     exposure_money.amount_minor, exposure_money.currency, owner, reason_text, now, now))
            except sqlite3.IntegrityError:
                # ### AT MOST ONE ACTIVE COMPENSATION PER INVALIDATED EFFECT (entity §17). A concurrent
                # raiser lost the race on the partial unique index — coalesce onto the existing active one.
                conn.rollback()
                existing = self.active_for_effect(original_effect_id)
                if existing is None:
                    raise
                return TransitionResult(
                    transition_id="CM-1", compensation=existing, from_state=None,
                    to_state=existing.state)
            created = self.require(cid)
            envelope = self._compensation_envelope(
                event_name="CompensationRequired", transition_id="CM-1", compensation=created,
                aggregate_version=1, actor_type=self._actor_type(actor_kind), actor_id=actor_id,
                payload={
                    "original_effect_id": original_effect_id,
                    "exposure": exposure_money.canonical(),
                    "reason": reason_text,
                    "decision_ref": resolved_ref,
                },
                correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                event_id=event_id, now=now)
            self._outbox().emit(envelope)
            conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        return TransitionResult(
            transition_id="CM-1", compensation=created, from_state=None, to_state=CmState.REQUIRED,
            event_ids=(envelope.event_id,), event_names=("CompensationRequired",), event_producer="CM-1")

    def _refuse_on_unknown(
        self, original_effect_id: str, *, compensation_id: str | None,
        actor_kind: str, actor_id: str, correlation_id: str | None, causation_id: str | None,
        trace_id: str | None, event_id: str | None,
    ) -> TransitionResult:
        """### CM-1r — COMPENSATION IS FORBIDDEN ON AN UNKNOWN OUTCOME (M-33). Emits
        `CompensationRefused{unknown}` and NOTHING ELSE: zero `compensations` rows, zero Pipeline
        Instances, zero Effect Grants, zero adapter calls, zero external effects. It WAITS for the human,
        who resolves the original to VERIFIED or FAILED first (M3 EF-5)."""
        # The refusal event names the effect it declined to compensate; there is no row, so the aggregate
        # id is a would-be compensation id used only to carry the audit. No compensation is persisted.
        cid = compensation_id or f"cmp-refused-{uuid.uuid4().hex[:16]}"
        now = format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            envelope = EventEnvelope(
                event_id=event_id or str(uuid.uuid4()), event_name="CompensationRefused",
                event_version=CONTRACTS["CompensationRefused"].current_version, occurred_at=now,
                recorded_at=now, tenant_id=self._tenant, aggregate_type=AGGREGATE_TYPE,
                aggregate_id=cid, aggregate_version=1, previous_aggregate_version=None,
                causation_id=causation_id, correlation_id=correlation_id or original_effect_id,
                producer_component=self._component, producer_transition_id="CM-1r",
                actor_type=self._actor_type(actor_kind), actor_id=actor_id,
                trace_id=trace_id or f"trace-{cid}",
                payload={"original_effect_id": original_effect_id, "cause": REFUSAL_CAUSE_UNKNOWN})
            self._outbox().emit(envelope)
            conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        return TransitionResult(
            transition_id="CM-1r", compensation=None, from_state=None, to_state=None,
            event_ids=(envelope.event_id,), event_names=("CompensationRefused",),
            event_producer="CM-1r", refused=True, refusal_cause=REFUSAL_CAUSE_UNKNOWN)

    # --- CM-2: human approval ---------------------------------------------------------------------

    def approve(
        self,
        compensation_id: str,
        *,
        approval_id: str,
        expected: CmRecord | None = None,
        actor_id: str = "operator",
        actor_kind: str = "human",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """CM-2 — REQUIRED → APPROVED. ### MONEY-AFFECTING COMPENSATION IS ALWAYS HUMAN_APPROVAL_REQUIRED
        (M4, ADR-003). The `approval_id` must resolve to an ACTUAL same-tenant M4 approval in GRANTED,
        bound to THIS compensation's own commit key (the confused-deputy check). ### M10 BUILDS NO SECOND
        APPROVAL SYSTEM AND DOES NOT MODIFY M4: it reads M4's row, which already enforces `granted_by` is
        a recorded human via an FK + CHECK, so a model cannot have granted it. `Compensation.APPROVED` is
        NOT `Approval.GRANTED/CONSUMED`: they are separate aggregates; the M4 approval is CONSUMED later,
        inside the executing pipeline's claim (AP-7), not here (### M10-AQ-6)."""
        comp = expected or self.require(compensation_id)
        self._require_legal(comp, Trigger.HUMAN_APPROVED, actor_id=actor_id)
        if str(actor_kind).upper() != HUMAN:
            self._refuse_illegal(comp.compensation_id, Trigger.HUMAN_APPROVED, actor_id=actor_id)
            raise IllegalTransition(
                f"CM-2 binds an authenticated HUMAN approval (trigger H, ADR-003). actor_kind="
                f"{actor_kind!r} — a model states no facts and cannot approve at any confidence (GR-8). "
                f"Recorded to audit and security under GR-1.")
        approval = self._require_bound_approval(approval_id, comp.commit_key)
        pins = self._pins_from_approval(approval)
        return self._advance(
            comp, "CM-2", CmState.APPROVED, event_name="CompensationApproved",
            payload={"approval_id": approval_id}, consequential=True, pins=pins,
            actor_type="human", actor_id=actor_id, writes="approval_id = ?",
            write_args=(approval_id,), correlation_id=correlation_id, causation_id=causation_id,
            trace_id=trace_id, event_id=event_id)

    # --- CM-2n: the world offers no undo ----------------------------------------------------------

    def mark_not_possible(
        self,
        compensation_id: str,
        *,
        impossibility_evidence: str,
        expected: CmRecord | None = None,
        actor_id: str = "compensation",
        actor_kind: str = "system",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """CM-2n — REQUIRED → NOT_POSSIBLE. ### THE WORLD OFFERS NO UNDO — a sent email, a wire — SO THE
        SYSTEM SAYS SO (entity §36, spec §12.10). It keeps the exposure, keeps the human owner, escalates.
        ### NO FAKE WRITE, NO FAKE COMPLETED, AND NO MODEL DECISION. Impossibility must rest on trusted
        deterministic evidence: a model saying "this cannot be undone" is insufficient at any confidence.

        ### M10-AQ-11 (REPORTED, NOT RESOLVED): the corpus provides NO canonical mechanism for proving
        impossibility — `NoCompensatingActionExists` is not a registered event, and no adapter-capability
        registry exists or is specified. §14's trigger type for CM-2n is `S` (system), yet entity §13
        forbids a MODEL_INFERRED basis. This build takes the narrow, fail-closed reading: a non-empty
        DETERMINISTIC evidence token supplied by a non-model caller, and it BUILDS NO capability registry
        to close the gap."""
        comp = expected or self.require(compensation_id)
        self._require_legal(comp, Trigger.NO_UNDO_EXISTS, actor_id=actor_id)
        if str(actor_kind).lower() == "model":
            self._refuse_illegal(comp.compensation_id, Trigger.NO_UNDO_EXISTS, actor_id=actor_id)
            raise IllegalTransition(
                "a model may never decide a compensation is impossible (entity §13, GR-8): "
                "impossibility rests on trusted deterministic evidence, never model output at any "
                "confidence. Recorded to audit and security under GR-1.")
        if not str(impossibility_evidence or "").strip():
            raise GuardNotSatisfied(
                "CM-2n requires deterministic evidence that the world offers no undo (### M10-AQ-11): a "
                "NOT_POSSIBLE with no basis is a silent write-off of exposure. What that evidence IS is "
                "an open authority question; a blank one fails closed.")
        return self._advance(
            comp, "CM-2n", CmState.NOT_POSSIBLE, event_name="CompensationImpossible",
            payload={"exposure": comp.exposure.canonical()}, consequential=False, pins=None,
            actor_type=self._actor_type(actor_kind), actor_id=actor_id, writes="", write_args=(),
            correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
            event_id=event_id)

    # --- CM-3: a NEW M2 Pipeline Instance starts, fully gated --------------------------------------

    def start_execution(
        self,
        compensation_id: str,
        *,
        work_item_id: str,
        pipeline_instance_id: str | None = None,
        expected: CmRecord | None = None,
        actor_id: str = "compensation",
        actor_kind: str = "system",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """CM-3 — APPROVED → EXECUTING. ### A NEW M2 PIPELINE INSTANCE STARTS — FULL CHECKPOINT, GRANT,
        BRAKE, POLICY (entity §15, machine §4, AC-REC-002). M10 REUSES M2 through the landed
        `PipelineMachine.propose`; it does NOT create a second pipeline and does NOT edit M2's state
        machine. The compensating effect gets its OWN new pipeline_instance_id (distinct from the
        original's), its OWN commit key, its OWN approval bound at PL-7b, its OWN checkpoint witness, its
        OWN single-use grant claimed through P3's untouched CAS, and its OWN readback — reusing NEITHER
        the original pipeline's authority NOR the original Effect Grant.

        ### M10 INVOKES NO ADAPTER AND PERFORMS NO DIRECT SYSTEM WRITE. It starts the gated attempt and
        records its id; the pipeline advances through the checkpoint on its own machinery. The DB CHECK
        `state <> 'EXECUTING' OR pipeline_instance_id IS NOT NULL` makes "execution is a gated attempt" a
        fact the database states.

        ### M10-AQ-7 (REPORTED): `PipelineMachine.propose` requires a `work_item_id` owned by an ACTIVE
        human, so the CALLER supplies the compensating Work Item — M10 creates none, exactly the P6-D2
        "creates a NEW Work Item" seam. M2 is reused, not extended."""
        comp = expected or self.require(compensation_id)
        self._require_legal(comp, Trigger.PIPELINE_STARTED, actor_id=actor_id)
        original = self._require_original_effect(comp.original_effect_id)
        effect = self.compensating_effect(original, comp.compensation_id)
        pid = pipeline_instance_id or f"pi-cmp-{uuid.uuid4().hex[:16]}"
        # ### START THE NEW, FULLY-GATED M2 PIPELINE (rule 17: M2 owns pipelines; M10 writes no
        # pipeline_instances row directly). propose() rejects actor_type=model and reads the Work Item's
        # ACTIVE-human owner from M1 — M10 supplies neither an owner nor a checkpoint kernel.
        m2 = PipelineMachine(self._conn, tenant=self._tenant, clock=self._clock)
        outcome = m2.propose(
            pipeline_instance_id=pid, work_item_id=work_item_id, effect=effect,
            actor_type=self._actor_type(actor_kind), actor_id=actor_id,
            correlation_id=correlation_id or comp.commit_key)
        if outcome.started is None:
            # The commit key is already reserved by a live attempt (PL-1b). A compensation's key is
            # unique per compensation_id, so this is a genuine re-proposal of the same compensation.
            absorbed = outcome.absorbed
            pid = absorbed.holder.pipeline_instance_id if absorbed is not None else pid
        else:
            pid = outcome.started.pipeline.pipeline_instance_id
        pins = self._pins_from_approval_id(comp.approval_id)
        return self._advance(
            comp, "CM-3", CmState.EXECUTING, event_name="CompensationStarted",
            payload={"pipeline_instance_id": pid}, consequential=True, pins=pins,
            actor_type=self._actor_type(actor_kind), actor_id=actor_id,
            writes="pipeline_instance_id = ?", write_args=(pid,), correlation_id=correlation_id,
            causation_id=causation_id, trace_id=trace_id, event_id=event_id)

    # --- CM-4 / CM-4f: the executing pipeline's outcome, read from its row -------------------------

    def observe_pipeline(
        self,
        compensation_id: str,
        *,
        expected: CmRecord | None = None,
        actor_id: str = "compensation",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """CM-4 / CM-4f — EXECUTING → COMPLETED or COMPENSATION_FAILED, ### DECIDED BY THE EXECUTING
        PIPELINE'S PERSISTED STATE (### M10-AQ-2). The trigger is the pipeline REACHING a state, read from
        the M2 row — not a delivery of a `PipelineFailed` event (which is not a canonical contract).

        ### CM-4 REQUIRES READBACK (ADR-006): completion requires the compensating effect to be M3
        VERIFIED — the pipeline reached VERIFIED. "The API returned 200" is not completion; write
        acceptance is not completion; a timeout is not a failure. A pipeline that is FAILED or
        NEEDS_VERIFICATION routes to CM-4f (COMPENSATION_FAILED), never to a silent success. A pipeline
        still in flight satisfies neither guard and this refuses (GuardNotSatisfied)."""
        comp = expected or self.require(compensation_id)
        if comp.state is not CmState.EXECUTING:
            raise GuardNotSatisfied(
                f"CM-4/CM-4f observe an EXECUTING compensation; {compensation_id!r} is {comp.state.value}.")
        pipeline = self._read_pipeline(comp.pipeline_instance_id)
        if pipeline is None:
            raise GuardNotSatisfied(
                f"CM-4/CM-4f read the executing pipeline's state; compensation {compensation_id!r} names "
                f"pipeline {comp.pipeline_instance_id!r}, which has no row for tenant {self._tenant!r}.")
        pipeline_state = pipeline["state"]
        grant_state = self._read_grant_state(pipeline["grant_id"])
        # ### CM-4 REQUIRES READBACK: the executing pipeline's PL-11 (READBACK_MATCHED) verified the
        # compensating effect, so its state reached VERIFIED and beyond (RECORDED/PROJECTED/CLOSED). ###
        # THAT IS NOT THE SAME AS EXECUTED: an EXECUTED pipeline is adapter success WITHOUT readback — a
        # return code, not completion. The pipeline is M2's authoritative statement that readback matched;
        # M3 is the effect authority and its grant carries the pins the CompensationCompleted event pins.
        if pipeline_state in POST_READBACK_PIPELINE_STATES:
            grant_pins = self._pins_from_grant_id(pipeline["grant_id"])
            return self._advance(
                comp, "CM-4", CmState.COMPLETED, event_name="CompensationCompleted",
                payload={}, consequential=True, pins=grant_pins, actor_type="system",
                actor_id=actor_id, writes="", write_args=(), correlation_id=correlation_id,
                causation_id=causation_id, trace_id=trace_id, event_id=event_id)
        if pipeline_state in ("FAILED", "NEEDS_VERIFICATION"):
            return self._advance(
                comp, "CM-4f", CmState.COMPENSATION_FAILED, event_name="CompensationFailed",
                payload={"exposure": comp.exposure.canonical()}, consequential=False, pins=None,
                actor_type="system", actor_id=actor_id, writes="", write_args=(),
                correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                event_id=event_id)
        raise GuardNotSatisfied(
            f"CM-4 completes only on a VERIFIED compensating effect (readback, M3 VERIFIED) and CM-4f "
            f"fails only on FAILED / NEEDS_VERIFICATION; the executing pipeline {comp.pipeline_instance_id!r} "
            f"is {pipeline_state!r} with grant state {grant_state!r} — still in flight. A timeout is not a "
            f"failure and a return code is not completion; neither guard is satisfied yet.")

    # --- CM-5: a human establishes reality --------------------------------------------------------

    def establish_reality(
        self,
        compensation_id: str,
        *,
        decision_ref: str,
        outcome: str,
        decision_human_id: str | None = None,
        decision_ref_kind: str = DECISION_KIND_AUDIT,
        expected: CmRecord | None = None,
        actor_id: str = "operator",
        actor_kind: str = "human",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """CM-5 — {COMPENSATION_FAILED, NOT_POSSIBLE} → COMPLETED on `HumanEstablishedReality{decision_ref}`
        (GR-14, K-1). ### A MODEL CANNOT ESTABLISH REALITY; A TIMER CANNOT; AN ABSENCE CANNOT. The
        `decision_ref` is resolved through M1's resolver (imported, never re-written), same tenant.

        ### IT EMITS THE SHARED F3 `RealityEstablished` WITH `subject="compensation"` — the EXACT
        registered contract (‡ producers EF-5 and CM-5), NEVER an F10-local second RealityEstablished
        (rule 17). The contract's `aggregate_type` is `effect_grant` and its `outcome ∈ {VERIFIED,FAILED}`
        (### M10-AQ-5): the outcome names the established reality of the underlying EFFECT, not the
        compensation's own COMPLETED state, so it rides a REAL effect grant. For COMPENSATION_FAILED that
        is the compensating grant from the executing pipeline; for NOT_POSSIBLE, where there is no pipeline
        and none is fabricated (### M10-AQ-4), it is the ORIGINAL effect grant. The M2 `PL-15` co-commit
        is event-driven coordination (M2 consumes this shared event) and its consumer half is unwired
        debt, exactly as `pipeline_instance.py` records for its own PL-15 — M10 emits its half and stops.
        """
        comp = expected or self.require(compensation_id)
        self._require_legal(comp, Trigger.HUMAN_ESTABLISHED_REALITY, actor_id=actor_id)
        if str(actor_kind).upper() != HUMAN:
            self._refuse_illegal(comp.compensation_id, Trigger.HUMAN_ESTABLISHED_REALITY, actor_id=actor_id)
            raise IllegalTransition(
                f"CM-5 requires an authenticated HUMAN to establish reality (GR-14, K-1). actor_kind="
                f"{actor_kind!r} — a model, a timer and an absence each establish nothing (GR-8). "
                f"Recorded to audit and security under GR-1.")
        stated = str(outcome or "").strip().upper()
        if stated not in REALITY_OUTCOMES:
            raise GuardNotSatisfied(
                f"CM-5's RealityEstablished outcome names the reality of the underlying effect and is one "
                f"of {sorted(REALITY_OUTCOMES)} (### M10-AQ-5); got {outcome!r}. COMPLETED is the "
                f"compensation's own state, never the event's outcome.")
        self._require_resolving_decision_ref(decision_ref, decision_ref_kind, context="the reality")
        if decision_human_id is not None:
            self._require_named_human(
                decision_human_id, "the human behind the reality decision_ref", actor_kind="human")
        resolved_ref = str(decision_ref or "").strip()
        grant_id = self._reality_grant_id(comp)
        pins = self._pins_from_grant_id(grant_id)
        prev = self._outbox().last_emitted_version(REALITY_AGGREGATE_TYPE, grant_id)
        reality = _RealityEmission(
            grant_id=grant_id, aggregate_version=prev + 1,
            previous_aggregate_version=(prev if prev >= 1 else None), pins=pins,
            payload={"decision_ref": resolved_ref, "outcome": stated, "subject": "compensation"})
        return self._advance(
            comp, "CM-5", CmState.COMPLETED, event_name="RealityEstablished",
            payload=reality.payload, consequential=True, pins=pins, actor_type="human",
            actor_id=actor_id, writes="reality_decision_ref = ?", write_args=(resolved_ref,),
            correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
            event_id=event_id, reality=reality)

    # --- CM-5x: the illegal timer -----------------------------------------------------------------

    def handle_timer_fired(
        self, compensation_id: str, *, timer_kind: str | None = None, actor_id: str = "timer",
    ) -> TransitionResult:
        """CM-5x — ### ⛔ ILLEGAL. NO TIMER MOVES COMPENSATION_FAILED, AND NO TIMER MOVES ANY COMPENSATION
        STATE (machine §15/§20, GR-6, AC-REC-004, AC-RACE-013). `TIMER_FIRED` has no legal row at any of
        the six states, so GR-1 refuses it uniformly: it raises, persists nothing, and records
        `IllegalTransitionAttempted`. There is no automatic retry from COMPENSATION_FAILED; a human
        decides (CM-5). M10 arms NO timers — this exists only to refuse one that is delivered."""
        comp = self.get(compensation_id)
        self._refuse_illegal(compensation_id, Trigger.TIMER_FIRED, actor_id=actor_id)
        state = comp.state.value if comp is not None else "-"
        raise IllegalTransition(
            f"a timer fired on compensation {compensation_id!r} (state {state}, kind {timer_kind!r}); NO "
            f"timer moves a compensation — not COMPENSATION_FAILED, not NOT_POSSIBLE, not any state "
            f"(machine §15, GR-6). A failed compensation is not auto-retried; a human establishes reality "
            f"(CM-5). Recorded to audit and security under GR-1.")

    # --- the uniform (state, trigger) dispatcher — for the illegal-transition sweep ---------------

    def apply(self, compensation_id: str, trigger: Trigger, *, actor_id: str = "compensation",
              **kw: Any) -> TransitionResult:
        """The uniform driver for the exhaustive `(state × trigger)` sweep. It reads the compensation,
        answers legality from the TABLE (`legal_transitions`), and refuses an illegal pair under GR-1
        before any handler runs — so an omitted transition raises, persists nothing, and records
        `IllegalTransitionAttempted`, exactly as CM-5x's timer does at every state."""
        comp = self.require(compensation_id)
        self._require_legal(comp, trigger, actor_id=actor_id)
        handler = _APPLY_DISPATCH.get(trigger)
        if handler is None:  # a legal trigger with no direct dispatcher is a build error, not a refusal.
            raise M10Error(f"no handler wired for legal trigger {trigger!r} at state {comp.state.value}.")
        return handler(self, compensation_id, actor_id=actor_id, **kw)

    # --- replay & park/drain ----------------------------------------------------------------------

    def reference_resolver(self, aggregate_type: str, aggregate_id: str) -> bool:
        """M-26's question, tenant-scoped. A reference to a not-yet-existing compensation is PARKED and
        drained the moment it lands — the same mechanism M3/M5/M6/M7/M8/M9 use, no second parking."""
        if aggregate_type == AGGREGATE_TYPE:
            return self._conn.execute(
                "SELECT 1 FROM compensations WHERE tenant = ? AND compensation_id = ?",
                (self._tenant, aggregate_id)).fetchone() is not None
        return True

    def consume_event(
        self, envelope: EventEnvelope, *, inbox: DedupInbox | None = None,
        requires_existing: tuple[tuple[str, str], ...] = (), drain: bool = True,
    ) -> ConsumedTransition:
        """Consume one canonical `compensation` event idempotently through P5's dedup inbox.

        ### REPLAY RECONSTRUCTS; IT NEVER MANUFACTURES (GR-11, ER-2, K-3). Reconstruction advances an
        EXISTING durable row's state to match a state-marking F10 event WITHOUT re-deciding it; a
        redelivery is a no-op (GR-4). It mints ZERO pipelines, grants, claims, approvals and external
        effects, and it can NEVER manufacture authority — it only moves `state` to what the event
        recorded. The compensating effect, like any effect, is never produced by replay."""
        box = inbox or DedupInbox(
            self._conn, tenant=self._tenant, consumer_id=CONSUMER_ID, clock=self._clock,
            reference_resolver=self.reference_resolver)
        outcome: dict[str, Any] = {"transition": None, "refusal": None}

        def handler(event: EventEnvelope) -> None:
            comp = self.get(event.aggregate_id)
            if comp is None:
                outcome["refusal"] = (
                    f"{event.event_name} references compensation {event.aggregate_id!r}, which does not "
                    f"exist for tenant {self._tenant!r}. Consumed once, nothing persisted.")
                return
            target = _event_target_state(event)
            if target is None or comp.state is target or comp.is_terminal:
                return
            outcome["transition"] = self._reconstruct_locked(comp, target)

        default_reqs: tuple[tuple[str, str], ...] = ((AGGREGATE_TYPE, envelope.aggregate_id),)
        result = box.consume(
            envelope, handler,
            requires_existing=(requires_existing or default_reqs),
            drain_handler_for=((lambda _env: handler) if drain else None))
        return ConsumedTransition(
            consume=result, transition=outcome["transition"], refusal=outcome["refusal"])

    def rebuild(self, compensation_id: str, *,
                events: list[EventEnvelope] | None = None) -> ReconstructedCompensation:
        """### A FULL-HISTORY FOLD OF ONE COMPENSATION — SANDBOXED, ZERO AUTHORITY (GR-11, ER-2, K-3).

        It reconstructs `state` from the F10 event stream and creates NOTHING: no pipeline, no grant, no
        claim, no approval, no external effect, no authority, no state flip. The COMPLETED-via-CM-5 case
        is established by the shared RealityEstablished coordination event (on the effect_grant aggregate)
        plus the persisted `reality_decision_ref`, reported as ### M10-AQ-5, not silently folded here."""
        stream = events if events is not None else self._event_stream(compensation_id)
        state: CmState | None = None
        for event in sorted(stream, key=lambda e: (e.aggregate_version or 0)):
            target = _event_target_state(event)
            if target is not None:
                state = target
            elif event.event_name == "CompensationRequired" and state is None:
                state = CmState.REQUIRED
        return ReconstructedCompensation(compensation_id=compensation_id, state=state)

    # --- shared transition plumbing ---------------------------------------------------------------

    def _advance(
        self, comp: CmRecord, transition_id: str, to_state: CmState, *,
        event_name: str, payload: Mapping[str, Any], consequential: bool, pins: dict[str, Any] | None,
        actor_type: str, actor_id: str, writes: str, write_args: tuple[Any, ...],
        correlation_id: str | None, causation_id: str | None, trace_id: str | None,
        event_id: str | None, reality: "_RealityEmission | None" = None,
    ) -> TransitionResult:
        """One transition: the state row and its event, in ONE transaction, or neither (GR-2). OCC on the
        version the decision was read at (GR-3): zero rows is a lost update that raises, never a silent
        overwrite. Every M10 transition changes state, so version always advances by one."""
        now = format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            set_clause = "state = ?, version = version + 1, updated_at = ?"
            if writes:
                set_clause += ", " + writes
            args: list[Any] = [to_state.value, now, *write_args,
                               self._tenant, comp.compensation_id, comp.state.value, comp.version]
            cursor = conn.execute(
                f"UPDATE compensations SET {set_clause} "
                f"WHERE tenant = ? AND compensation_id = ? AND state = ? AND version = ?", args)
            if cursor.rowcount != 1:
                raise StateConflict(
                    f"{transition_id} matched {cursor.rowcount} rows for {comp.compensation_id!r}: it "
                    f"moved under us (GR-3). Reload — a lost update on a compensation is refused.")
            after = self.require(comp.compensation_id)
            if reality is not None:
                # ### CM-5: the shared F3 RealityEstablished rides the STRICT-ORDER effect_grant aggregate.
                envelope = self._reality_envelope(
                    reality, comp=after, actor_type=actor_type, actor_id=actor_id,
                    correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                    event_id=event_id, now=now)
            else:
                envelope = self._compensation_envelope(
                    event_name=event_name, transition_id=transition_id, compensation=after,
                    aggregate_version=self._next_version(comp.compensation_id), actor_type=actor_type,
                    actor_id=actor_id, payload=dict(payload), consequential=consequential, pins=pins,
                    correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                    event_id=event_id, now=now)
            self._outbox().emit(envelope)
            conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        return TransitionResult(
            transition_id=transition_id, compensation=after, from_state=comp.state, to_state=to_state,
            event_ids=(envelope.event_id,), event_names=(event_name,), event_producer=transition_id)

    def _reconstruct_locked(self, comp: CmRecord, target: CmState) -> TransitionResult:
        """Advance a durable row to match a durable F10 event — reconstruction, not a live transition.
        Runs inside the inbox's own commit (M-24): no BEGIN, no COMMIT. ### IT MINTS NO AUTHORITY, no
        pipeline, no grant and no decision_ref: it moves only `state` to what the event already recorded.
        """
        now = format_instant(self._clock())
        self._conn.execute(
            "UPDATE compensations SET state = ?, version = version + 1, updated_at = ? "
            "WHERE tenant = ? AND compensation_id = ? AND state = ?",
            (target.value, now, self._tenant, comp.compensation_id, comp.state.value))
        after = self.require(comp.compensation_id)
        return TransitionResult(
            transition_id="replay", compensation=after, from_state=comp.state, to_state=target)

    # --- guards & reads ---------------------------------------------------------------------------

    def _require_legal(self, comp: CmRecord, trigger: Trigger, *, actor_id: str) -> None:
        """### GR-1, DERIVED FROM THE TABLE. If (state, trigger) is not an enumerated legal row, record
        `IllegalTransitionAttempted` and raise — nothing is persisted."""
        if not legal_transitions(comp.state, trigger):
            self._refuse_illegal(comp.compensation_id, trigger, actor_id=actor_id)
            raise IllegalTransition(
                f"{trigger.value} is not a legal transition from {comp.state.value} (machine §14, GR-1): "
                f"an omitted (state, trigger) pair raises, persists nothing, and is recorded. Recorded to "
                f"audit and security under GR-1.")

    def _require_named_human(self, human_id: str | None, role: str, *, actor_kind: str) -> str:
        """### A NAMED ACTIVE HUMAN, FK-BACKED (entity §10/§16, machine §5, I1, AC-SAFE-028). "A human" is
        decoration while the column is free text: it must be a recorded, ACTIVE human of THIS tenant.
        `system` is not a human, a model is not a human, an OFFBOARDED human may not own a new
        compensation, and a wrong-tenant or forged human fails closed."""
        text = str(human_id or "").strip()
        if str(actor_kind).lower() == "model":
            raise GuardNotSatisfied(
                f"{role} cannot be a model actor (ER-9, [C-6]): a model states no facts and owns no "
                f"obligation. The caller supplies a named ACTIVE human; the machine never picks one.")
        if not text:
            raise GuardNotSatisfied(
                f"{role} is a named human, FK-backed into tenant_humans (entity §16, I1): an ownerless or "
                f"unnamed value is a silent write-off wearing a status.")
        row = self._conn.execute(
            "SELECT state FROM tenant_humans WHERE tenant = ? AND human_id = ?",
            (self._tenant, text)).fetchone()
        if row is None or row["state"] != "ACTIVE":
            raise GuardNotSatisfied(
                f"{role} names {text!r}, who is not an ACTIVE recorded human of {self._tenant!r}. A "
                f"forged, inactive/offboarded or wrong-tenant human fails closed — the human is FK-backed, "
                f"not a free-text string, and `system` is not a human.")
        return text

    def _require_resolving_decision_ref(self, decision_ref: str, kind: str, *, context: str) -> None:
        """### THE decision_ref MUST RESOLVE, NOT MERELY BE NON-NULL (K-1). M1's resolver is imported and
        called — never a second implementation of "does this decision_ref resolve" (rule 17). It refuses a
        blank string, a reference to nothing, a non-human-decision event, a human-decision event recorded
        by automation (ER-11), and a RULE kind (M12 not built — refuses today, debt P6-D4)."""
        ref = str(decision_ref or "").strip()
        if not ref:
            raise GuardNotSatisfied(
                f"{context} decision_ref is required and resolves to an authenticated human decision "
                f"(K-1, GR-14): a compensation is never raised or resolved from silence.")
        try:
            resolve_decision_ref(self._conn, tenant=self._tenant, ref=ref, kind=kind)
        except DecisionRefUnresolvable as exc:
            raise GuardNotSatisfied(
                f"{context} decision_ref {ref!r} does not RESOLVE (K-1, GR-8): {exc} A MODEL_INFERRED "
                f"conclusion, an automation-recorded event and confidence at any value are each data, "
                f"never authority.") from exc

    def _require_original_effect(self, original_effect_id: str) -> "OriginalEffect":
        """### READ THE ORIGINAL EFFECT FROM THE `effect_grants` LEDGER (requirement 1). Not a caller flag,
        not a parameter named `original_was_verified`, not a model's summary — the actual persisted row,
        tenant-scoped so a cross-tenant original fails closed."""
        row = self._conn.execute(
            "SELECT grant_id, state, target_system, target_resource_id, target_operation, action_class "
            "FROM effect_grants WHERE tenant = ? AND grant_id = ?",
            (self._tenant, original_effect_id)).fetchone()
        if row is None:
            raise MalformedCompensation(
                f"no effect_grants row {original_effect_id!r} for tenant {self._tenant!r}: a compensation "
                f"may be created only for a landed M3 effect of THIS tenant (entity §21, [C-1]).")
        return OriginalEffect(
            grant_id=row["grant_id"], state=row["state"], target_system=row["target_system"],
            target_resource_id=row["target_resource_id"], target_operation=row["target_operation"],
            action_class=row["action_class"])

    def _require_bound_approval(self, approval_id: str, commit_key: str) -> sqlite3.Row:
        """### THE APPROVAL RESOLVES TO A SAME-TENANT M4 GRANTED APPROVAL BOUND TO THIS COMMIT KEY. A
        stale, wrong-commit-key, expired, revoked, consumed, void or cross-tenant approval is refused. M10
        reads M4's row; it does not restate M4's `granted_by` human CHECK (### M10-AQ-6)."""
        text = str(approval_id or "").strip()
        if not text:
            raise GuardNotSatisfied("CM-2 binds a named M4 approval; none was given.")
        row = self._conn.execute(
            "SELECT approval_id, state, commit_key, entity_versions_json, policy_version, brake_version "
            "FROM approvals WHERE tenant = ? AND approval_id = ?",
            (self._tenant, text)).fetchone()
        if row is None:
            raise GuardNotSatisfied(
                f"approval {text!r} is not an approval of tenant {self._tenant!r}: a cross-tenant or "
                f"non-existent approval fails closed ([C-1]).")
        if row["state"] != "GRANTED":
            raise GuardNotSatisfied(
                f"approval {text!r} is {row['state']!r}, not GRANTED: a stale, expired, revoked, consumed "
                f"or void approval does not authorise a compensating write (M4).")
        if row["commit_key"] != commit_key:
            raise GuardNotSatisfied(
                f"approval {text!r} binds commit key {row['commit_key']!r}, not this compensation's own "
                f"{commit_key!r}: an approval for one effect authorising another is the confused-deputy "
                f"shape the checkpoint refuses (ADR-005, fp_v1 is over the commit key).")
        return row

    def _read_pipeline(self, pipeline_instance_id: str | None) -> sqlite3.Row | None:
        if not pipeline_instance_id:
            return None
        return self._conn.execute(
            "SELECT state, grant_id FROM pipeline_instances WHERE tenant = ? AND pipeline_instance_id = ?",
            (self._tenant, pipeline_instance_id)).fetchone()

    def _read_grant_state(self, grant_id: str | None) -> str | None:
        """### THE COMPENSATING EFFECT GRANT'S STATE — M3 is the sole effect authority, so CM-4's
        "verified by readback" reads the LEDGER, not the pipeline's opinion. A missing grant is None
        (the pipeline failed before minting one)."""
        if not grant_id:
            return None
        row = self._conn.execute(
            "SELECT state FROM effect_grants WHERE tenant = ? AND grant_id = ?",
            (self._tenant, grant_id)).fetchone()
        return row["state"] if row is not None else None

    def _reality_grant_id(self, comp: CmRecord) -> str:
        """The REAL effect grant CM-5's RealityEstablished names (### M10-AQ-4/AQ-5). COMPENSATION_FAILED
        has an executing pipeline whose compensating grant is the subject; NOT_POSSIBLE has none and none
        is fabricated, so the ORIGINAL effect grant is named. A FAILED pipeline that never minted a grant
        also falls back to the original — no pipeline or grant is invented."""
        if comp.state is CmState.COMPENSATION_FAILED and comp.pipeline_instance_id:
            row = self._read_pipeline(comp.pipeline_instance_id)
            if row is not None and row["grant_id"]:
                return row["grant_id"]
        return comp.original_effect_id

    def _pins_from_approval_id(self, approval_id: str | None) -> dict[str, Any]:
        if not approval_id:
            raise GuardNotSatisfied(
                "CM-3 pins the decision context of the human approval; the compensation has no bound "
                "approval_id (it did not pass CM-2).")
        row = self._conn.execute(
            "SELECT entity_versions_json, policy_version, brake_version FROM approvals "
            "WHERE tenant = ? AND approval_id = ?", (self._tenant, approval_id)).fetchone()
        if row is None:
            raise GuardNotSatisfied(f"approval {approval_id!r} is not an approval of this tenant.")
        return self._pins_from_approval(row)

    def _pins_from_approval(self, row: sqlite3.Row) -> dict[str, Any]:
        return _require_pins(
            entity_versions=_parse_versions(row["entity_versions_json"]),
            policy_version=row["policy_version"], brake_version=row["brake_version"],
            context="the bound M4 approval")

    def _pins_from_grant_id(self, grant_id: str | None) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT entity_versions_json, policy_version, brake_version FROM effect_grants "
            "WHERE tenant = ? AND grant_id = ?", (self._tenant, grant_id)).fetchone()
        if row is None:
            raise GuardNotSatisfied(
                f"effect grant {grant_id!r} is not a grant of this tenant: a consequential compensation "
                f"event pins the decision context of a REAL effect grant.")
        return _require_pins(
            entity_versions=_parse_versions(row["entity_versions_json"]),
            policy_version=row["policy_version"], brake_version=row["brake_version"],
            context="the effect grant")

    # --- F14 recording ----------------------------------------------------------------------------

    def _refuse_illegal(self, aggregate_id: str, trigger: Trigger, *, actor_id: str) -> None:
        """### GR-1 — record `IllegalTransitionAttempted` to audit AND security, then the caller raises.
        M10 records this tripwire; it engages NO brake — not on an illegal transition, not on a Sev-0, not
        ever (the Sev-0 detectors are the checkpoint's)."""
        comp = self.get(aggregate_id)
        state = comp.state.value if comp is not None else "-"
        self._record_f14(
            aggregate_id=aggregate_id, event_name="IllegalTransitionAttempted",
            identity_suffix=f"{trigger.value}|{actor_id}",
            payload={"machine": "M10", "state": state, "trigger": trigger.value,
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

    def _event_stream(self, compensation_id: str) -> list[EventEnvelope]:
        rows = self._conn.execute(
            "SELECT envelope_json FROM event_outbox WHERE tenant = ? AND aggregate_type = ? "
            "AND aggregate_id = ? ORDER BY aggregate_version, sequence",
            (self._tenant, AGGREGATE_TYPE, compensation_id)).fetchall()
        return [EventEnvelope.from_json(r["envelope_json"]) for r in rows]

    def _next_version(self, compensation_id: str) -> int:
        return self._outbox().last_emitted_version(AGGREGATE_TYPE, compensation_id) + 1

    def _outbox(self):
        from .event_outbox import TransactionalOutbox
        return TransactionalOutbox(self._conn, tenant=self._tenant, clock=self._clock)

    def _actor_type(self, actor_kind: str) -> str:
        return "human" if str(actor_kind).upper() == HUMAN else str(actor_kind).lower()

    def _compensation_envelope(
        self, *, event_name: str, transition_id: str, compensation: CmRecord, aggregate_version: int,
        actor_type: str, actor_id: str, payload: Mapping[str, Any], correlation_id: str | None,
        causation_id: str | None, trace_id: str | None, event_id: str | None, now: str,
        consequential: bool = False, pins: dict[str, Any] | None = None,
    ) -> EventEnvelope:
        """One canonical envelope on the `compensation` aggregate for CM-1..CM-4f. F10 is order-tolerant,
        so no `previous_aggregate_version` travels on it. A CONSEQUENTIAL event (CM-2/CM-3/CM-4) pins the
        decision context §5 requires, read from the bound approval or the compensating grant."""
        pinset = pins or {}
        return EventEnvelope(
            event_id=event_id or str(uuid.uuid4()), event_name=event_name,
            event_version=CONTRACTS[event_name].current_version, occurred_at=now, recorded_at=now,
            tenant_id=self._tenant, aggregate_type=AGGREGATE_TYPE,
            aggregate_id=compensation.compensation_id, aggregate_version=aggregate_version,
            previous_aggregate_version=None, causation_id=causation_id,
            correlation_id=correlation_id or compensation.commit_key,
            producer_component=self._component, producer_transition_id=transition_id,
            actor_type=actor_type, actor_id=actor_id,
            trace_id=trace_id or f"trace-{compensation.compensation_id}", payload=dict(payload),
            accountable_owner_id=compensation.owner_id,
            entity_versions=(pinset.get("entity_versions") if consequential else None),
            policy_version=(pinset.get("policy_version") if consequential else None),
            brake_version=(pinset.get("brake_version") if consequential else None))

    def _reality_envelope(
        self, reality: "_RealityEmission", *, comp: CmRecord, actor_type: str, actor_id: str,
        correlation_id: str | None, causation_id: str | None, trace_id: str | None,
        event_id: str | None, now: str,
    ) -> EventEnvelope:
        """### THE SHARED F3 `RealityEstablished`, ON THE STRICT-ORDER `effect_grant` AGGREGATE, WITH
        `subject="compensation"` (### M10-AQ-5). The exact registered contract (‡ producer CM-5), never an
        F10-local one; its `aggregate_type` is `effect_grant` and its predecessor is derived from that
        grant's own stream."""
        return EventEnvelope(
            event_id=event_id or str(uuid.uuid4()), event_name="RealityEstablished",
            event_version=CONTRACTS["RealityEstablished"].current_version, occurred_at=now,
            recorded_at=now, tenant_id=self._tenant, aggregate_type=REALITY_AGGREGATE_TYPE,
            aggregate_id=reality.grant_id, aggregate_version=reality.aggregate_version,
            previous_aggregate_version=reality.previous_aggregate_version, causation_id=causation_id,
            correlation_id=correlation_id or comp.commit_key, producer_component=self._component,
            producer_transition_id="CM-5", actor_type=actor_type, actor_id=actor_id,
            trace_id=trace_id or f"trace-{comp.compensation_id}", payload=dict(reality.payload),
            accountable_owner_id=comp.owner_id,
            entity_versions=reality.pins.get("entity_versions"),
            policy_version=reality.pins.get("policy_version"),
            brake_version=reality.pins.get("brake_version"))


# ------------------------------------------------------------------------------------- plumbing

@dataclass(frozen=True)
class OriginalEffect:
    """The original effect being undone, read from the `effect_grants` ledger at CM-1/CM-3."""

    grant_id: str
    state: str
    target_system: str
    target_resource_id: str
    target_operation: str
    action_class: str


@dataclass(frozen=True)
class _RealityEmission:
    """Everything CM-5's shared RealityEstablished needs to ride the strict-order effect_grant aggregate."""

    grant_id: str
    aggregate_version: int
    previous_aggregate_version: int | None
    pins: dict[str, Any]
    payload: dict[str, Any]


# The uniform-dispatch table for `apply` — a legal trigger to the method that performs its transition.
# TIMER_FIRED is DELIBERATELY ABSENT: it has no legal row, so `_require_legal` refuses it before dispatch.
_APPLY_DISPATCH: Mapping[Trigger, Callable[..., TransitionResult]] = {
    Trigger.HUMAN_APPROVED: lambda m, cid, **kw: m.approve(cid, **kw),
    Trigger.NO_UNDO_EXISTS: lambda m, cid, **kw: m.mark_not_possible(cid, **kw),
    Trigger.PIPELINE_STARTED: lambda m, cid, **kw: m.start_execution(cid, **kw),
    Trigger.PIPELINE_VERIFIED: lambda m, cid, **kw: m.observe_pipeline(cid, **kw),
    Trigger.PIPELINE_UNVERIFIED: lambda m, cid, **kw: m.observe_pipeline(cid, **kw),
    Trigger.HUMAN_ESTABLISHED_REALITY: lambda m, cid, **kw: m.establish_reality(cid, **kw),
}


def _require_money(value: Any) -> Money:
    """### THE EXPOSURE IS CANONICAL MONEY (K-4, requirement 6). A float, a Decimal and a bool are refused
    at `Money` construction, so they can never reach the row; a bare non-Money value is refused here."""
    if isinstance(value, Money):
        return value
    raise MalformedCompensation(
        f"exposure must be canonical Money(amount_minor: int, currency) (fingerprint.py, K-4); got "
        f"{type(value).__name__} {value!r}. A float and a Decimal are refused at Money construction — "
        f"2850.00 and 2850.0 are the same money and different bytes — and the amount is never a float.")


def _require_pins(*, entity_versions: dict[str, int], policy_version: str | None,
                  brake_version: str | None, context: str) -> dict[str, Any]:
    """The three consequential pins §5 requires, verified non-empty. A CONSEQUENTIAL compensation event
    that could not pin its decision context is refused BEFORE it is emitted, rather than by the outbox."""
    if not entity_versions:
        raise GuardNotSatisfied(
            f"{context} pins no entity_versions: a consequential compensation event (§5, ER-13) must "
            f"carry the SD-3 version set to reproduce its decision context.")
    if not str(policy_version or "").strip():
        raise GuardNotSatisfied(f"{context} pins no policy_version (§5, ER-13).")
    if not str(brake_version or "").strip():
        raise GuardNotSatisfied(f"{context} pins no brake_version (§5, ER-13).")
    return {"entity_versions": dict(entity_versions), "policy_version": policy_version,
            "brake_version": brake_version}


def _parse_versions(raw: str | None) -> dict[str, int]:
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return {str(k): int(v) for k, v in loaded.items()} if isinstance(loaded, dict) else {}


def _event_target_state(event: EventEnvelope) -> CmState | None:
    """The state a compensation F10 event reconstructs to, or None for an event that is not a state
    marker. CompensationRequired's creation marker is handled by the rebuild; the shared RealityEstablished
    is on the effect_grant aggregate, not this one, so it never reaches this fold (### M10-AQ-5)."""
    return {
        "CompensationApproved": CmState.APPROVED,
        "CompensationImpossible": CmState.NOT_POSSIBLE,
        "CompensationStarted": CmState.EXECUTING,
        "CompensationCompleted": CmState.COMPLETED,
        "CompensationFailed": CmState.COMPENSATION_FAILED,
    }.get(event.event_name)


def _require_text(value: str, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise MalformedCompensation(f"{field_name} is required and was empty.")
    return text


def _row_to_compensation(row: Any) -> CmRecord:
    return CmRecord(
        tenant=row["tenant"], compensation_id=row["compensation_id"],
        original_effect_id=row["original_effect_id"], commit_key=row["commit_key"],
        state=CmState(row["state"]), version=row["version"],
        exposure=Money(amount_minor=row["exposure_amount_minor"], currency=row["exposure_currency"]),
        owner_id=row["owner_id"], reason=row["reason"],
        pipeline_instance_id=row["pipeline_instance_id"], approval_id=row["approval_id"],
        reality_decision_ref=row["reality_decision_ref"], created_at=row["created_at"])


# Re-exported so a caller reads one name rather than importing the migration for a constant.
STATES: tuple[str, ...] = COMPENSATION_STATES
