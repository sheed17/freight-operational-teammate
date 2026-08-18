"""Machine M2 — the Pipeline Instance: one durable attempt to get one Work Item's effect done.

M1 answered *"what operational work exists, and who is accountable for it?"* This answers the next
question a dispatcher actually asks:

    Work Item          "Get the POD for load 4471 and bill it."   — the obligation, and its owner
    Pipeline Instance  "Attempt #1 to raise the invoice."         — what Neyma is doing about it

`02-pipeline-instance.machine.md` §3: *"One durable attempt to produce one effect; the Pipeline
Instance IS the command."* There is no separate command object to lose, and no in-memory "current
step" that a restart forgets. The attempt is a row.

### WHAT THIS MACHINE OWNS, AND WHAT IT ONLY REFLECTS.

It owns the sixteen states of §7 and the twenty-five transitions of §14. It does **not** own the
effect grant: SD-2 gives the effect ONE ledger row with EIGHT states and M3 owns it, so M2's
`GRANTED`/`CLAIMED` **reflect** that row and are co-transitioned with it in one commit. That is why
`PL-8` and `PL-9` do not re-implement the checkpoint or the CAS — they call P3's kernel through its
locked entry points and put the pipeline's own write inside the kernel's transaction. A second
implementation of either would be the dual effect-authority system CLAUDE.md rule 17 forbids, and
the two would disagree the first time one was changed.

### THE TWO PROPERTIES THIS MACHINE EXISTS FOR.

**One attempt at a time, one effect ever.** PL-1 acquires the Layer-1 reservation
`UNIQUE(tenant, commit_key) WHERE state ∉ terminal`; a second proposal for the same logical effect
is ABSORBED onto the holder (PL-1b) and produces one operator card, not two invoices. Layer 2 is
P3's `ix_effect_grants_live_hold`, which holds a VERIFIED effect's commit key forever. Neither is
the other's backup.

**Never both, never neither.** §30: a brake engaged between the checkpoint and the claim makes the
CAS match zero rows, so *"the adapter does nothing"*. Because the CAS and the pipeline's own
`GRANTED → CLAIMED` share one transaction, there is no interval in which the ledger says CLAIMED
and the pipeline does not, or the reverse.

### AND THE PROPERTY IT REFUSES TO GIVE YOU.

`CLAIMED` or `EXECUTED` plus a crash is `NEEDS_VERIFICATION` — never `FAILED` (§36, GR-5, GR-6). It
never auto-resolves, no timer may move it (PL-15x is ILLEGAL, and recorded as a security event when
attempted), and it is **non-terminal**, so it keeps holding the Layer-1 reservation and nothing may
retry the effect while we cannot say whether it happened. That last sentence is enforced by a
partial index, not by a code path somebody has to remember.

### WHAT IS NOT BUILT HERE, STATED RATHER THAN IMPLIED.

M3 (the Effect Grant machine), M4 (Approval), M9 (Exception) and M10 (Compensation) are later units.
Where §14 declares a co-commit into one of them, this machine performs **its own half** and emits
**only the events the canonical registry attributes to a PL-* transition**. It does not emit
`GrantClaimed`, `EffectAttempted`, `EffectGranted` or `ApprovalRequested` — the contract gate would
refuse them, correctly, because `events/registry.md` §3 attributes each to an EF-* or AP-* producer.
The owed halves are recorded as debt, not faked: see `CONSUMED_CONTRACTS` and the unit's evidence.

### IT SHIPS DARK. Nothing in the repository calls it.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .checkpoint import (
    CheckpointAuthorized,
    CheckpointInputs,
    CheckpointRefused,
    CheckpointRequest,
    ClaimParams,
    EffectGrantHandle,
    GateDecision,
    claim_grant_cas_locked,
    flush_claim_records,
    record_checkpoint_refusal,
    run_checkpoint_locked,
)
from .commit_key import LogicalEffect
from .event_contracts import CONTRACTS
from .event_envelope import EventEnvelope, format_instant
from .event_inbox import ConsumeResult, DedupInbox
from .event_outbox import DuplicateEmission, TransactionalOutbox
from .migrations.phase6_pipeline_instances import (
    HUMAN_OWNED_PIPELINE_STATES,
    PIPELINE_STATES,
    POST_CHECKPOINT_STATES,
    RECOVERABLE_PIPELINE_STATES,
    TERMINAL_PIPELINE_STATES,
)
from .persistence import integrity_errors
from .tenant import require_tenant
from .work_item import WorkItemMachine, WorkItemState

# The aggregate this machine owns. `pipeline_instance` is in `STRICT_ORDER_AGGREGATE_TYPES`
# (`events/registry.md` §8, F2) because its transitions are version-monotonic: an out-of-order F2
# event is a gap, not a tolerable reordering, and the inbox parks it until the gap fills.
AGGREGATE_TYPE = "pipeline_instance"

# `entities/02-pipeline-instance.md`: the Execution Service owns the attempt.
PRODUCER_COMPONENT = "execution_service"

# The one consumer identity M2 presents to the dedup inbox. Fixed, because the dedup key is
# `(tenant, consumer_id, event_id)` and a consumer that renamed itself would re-arm every duplicate
# it had already absorbed.
CONSUMER_ID = "m2-pipeline-instance"

# GR-1's producer id for `IllegalTransitionAttempted` — the RULE, not a transition. Identical to
# M1's, and for the same reason: `events/registry.md` §3 states this contract's producer as
# "‡(any machine, GR-1)", so the contract carries an empty `producers` tuple.
ILLEGAL_TRANSITION_PRODUCER = "GR-1"

# The identity of ONE refused attempt. Same shape and same reasoning as M1's `ita_v1`: §4's
# transition-natural identity contains the aggregate version, an illegal transition does not advance
# it, and without the attempt component every hostile attempt against one pipeline at one version
# would collide on `idempotency_identity` — recording only the first and turning redelivery of the
# second into a poison loop. M1 shipped that defect and it was rejected in independent review; the
# same identity discipline is applied here rather than rediscovered.
ILLEGAL_ATTEMPT_IDENTITY_PREFIX = "ita_v1"

# The identity of ONE absorbed duplicate proposal (PL-1b). Same problem, same answer: PL-1b records
# a fact about a proposal that produced no transition, so it advances no version, so two DIFFERENT
# absorbed proposals against one holder would claim one identity. Keyed on the absorbed proposal's
# own reference, which makes redelivery idempotent by construction rather than by luck.
ABSORBED_PROPOSAL_IDENTITY_PREFIX = "dpa_v1";

# The actor kinds that may drive this machine. `model` is absent, and absent deliberately: C-6 and
# GR-7 give a model exactly one output, an inert `ProposedIntent`. §40: *"agents emit inert proposals
# only."* A model may propose that an effect is needed; it may never validate, admit, checkpoint,
# claim, verify or close one.
PERMITTED_ACTOR_TYPES: frozenset[str] = frozenset({"human", "system", "detector"})

# §14 PL-6: the two gates that route to a human. Read from the kernel's enum rather than restated,
# so a fifth gate or a renamed one is a type error here and not a silently-unmatched branch.
#
# ### THE AUTHORITY FOR EVERY GATE DECISION THIS MODULE NAMES IS ADR-010, AND M2 DOES NOT HOLD IT.
# ADR-010 §3.1 defines the four-member gate ladder and puts its EVALUATION at the checkpoint
# kernel; §8's fallback is `HUMAN_APPROVAL_REQUIRED`, so forgetting to classify an action class can
# only ever cost a human tap. This machine ROUTES on the decision the kernel returns — PL-2 records
# it, PL-3 rejects a forbidden one, PL-6 asks a human, PL-7a admits autonomously — and it MINTS
# none: no `GateEntry` or `GateRegistry` is constructed anywhere in this file, which
# `test_phase0_null_gate.py` asserts by AST. The policy RUNTIME that decides these is P8's, and
# the production `GateRegistry` population stays EMPTY until U8.1.
HUMAN_GATES: frozenset[GateDecision] = frozenset({
    GateDecision.HUMAN_APPROVAL_REQUIRED, GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED,
})

# K-1(a), as M1 resolves it. PL-15 closes an UNKNOWN OUTCOME, and §14 requires
# `HumanEstablishedReality{decision_ref}` — a reference that resolves to an authenticated human
# decision. The resolver is M1's, imported rather than re-written: two implementations of "does this
# decision_ref resolve" is two places for one of them to start accepting the string "done".
from .work_item import (  # noqa: E402  — grouped here because it is a REUSE statement, not plumbing
    DecisionRefUnresolvable,
    resolve_decision_ref,
)


class PipelineError(RuntimeError):
    """This machine will not do what was asked. Never degraded into a partial transition."""


class UnknownPipeline(PipelineError):
    """No Pipeline Instance with this id exists FOR THIS TENANT.

    Deliberately indistinguishable from "it belongs to another tenant" — establishing the difference
    needs a read across the tenant boundary, and [C-1] rejects a cross-tenant question rather than
    answering it carefully.
    """


class ReservationHeld(PipelineError):
    """The Layer-1 reservation for this logical effect is held by a live attempt. PL-1b's condition.

    Raised only where the caller asked for a NEW attempt and absorption was refused; the ordinary
    path returns an absorbed outcome rather than raising, because absorbing is what §14 PL-1b says
    to do and an exception would make the normal case look like a failure.
    """


class AuthorityRefused(PipelineError):
    """The ACTOR driving this transition does not hold the authority the transition requires."""


class GuardNotSatisfied(PipelineError):
    """The (state, trigger) pair IS legal here and a precondition is false.

    ### No event is emitted — not even a security one. The trigger was legal; the world was not
    ready. Blurring this line is how `IllegalTransitionAttempted` becomes noise an operator learns
    to ignore.
    """


class IllegalTransition(PipelineError):
    """GR-1 / [C-4]. Either the (state, trigger) pair is NOT in the table, or §15 declares the
    resulting shape impossible.

    ### §15 IS PART OF GR-1, NOT A SOFTER RULE BESIDE IT. *"`GRANTED` reachable without a
    `CheckpointPassed` witness → impossible (PL-8 co-commits). `CLAIMED` without a successful CAS →
    impossible."* Those two are enumerated pairs — PL-8 and PL-9 are real rows — so the illegality
    is not the pair, it is the PATH: a consequential row driven by anything other than the kernel
    that owns it. Both refusals carry the same durable consequence, so both are this exception.

    Raised AFTER `IllegalTransitionAttempted` has been committed to the outbox and to
    `security_events` — the record survives the refusal, which is the point of recording it.
    """


class VersionConflict(PipelineError):
    """A stale `expected_version`: zero rows matched, so somebody else transitioned first. GR-3."""


class OwnershipRefused(PipelineError):
    """This attempt cannot be tied to the accountable human its Work Item names. Rule 13, §5."""


# --------------------------------------------------------------------------------- the state set

class PipelineState(str, Enum):
    PROPOSED = "PROPOSED"
    POLICY_CHECKED = "POLICY_CHECKED"
    VALIDATED = "VALIDATED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    CHECKPOINT = "CHECKPOINT"
    GRANTED = "GRANTED"
    CLAIMED = "CLAIMED"
    EXECUTED = "EXECUTED"
    VERIFIED = "VERIFIED"
    RECORDED = "RECORDED"
    PROJECTED = "PROJECTED"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"
    VOIDED = "VOIDED"
    FAILED = "FAILED"
    NEEDS_VERIFICATION = "NEEDS_VERIFICATION"


class Trigger(str, Enum):
    """The closed set of driving facts, named from §14's guards and §33's "Events consumed".

    ### `TimerFired` IS IN THIS ENUM AND HAS NO LEGAL ROW ANYWHERE, WHICH IS THE POINT.
    §14's PL-15x is the only row in the table that declares an ILLEGAL outcome, and
    `foundational-machine-acceptance.md` names it `AC-MACH-215x`: *"no timer moves
    `NEEDS_VERIFICATION` (ILLEGAL)"*. Modelling it as a trigger with no legal row makes GR-1 answer
    it uniformly — a timer fired at ANY of the sixteen states raises, persists nothing and records
    `IllegalTransitionAttempted` — which is strictly stronger than a special case at one state, and
    it is derived from the table rather than written twice.
    """

    INTENT_PROPOSED = "IntentProposed"
    POLICY_EVALUATED = "PolicyEvaluated"
    VALIDATION_COMPLETED = "ValidationCompleted"
    GATE_ROUTED = "GateRouted"
    APPROVAL_GRANTED = "ApprovalGranted"
    APPROVAL_DENIED = "ApprovalDenied"
    APPROVAL_EXPIRED = "ApprovalExpired"
    POLICY_VERSION_CHANGED = "PolicyVersionChanged"
    BRAKE_ENGAGED = "BrakeEngaged"
    CHECKPOINT_RUN = "CheckpointRun"
    CLAIM_ATTEMPTED = "ClaimAttempted"
    GRANT_EXPIRED = "GrantExpired"
    GRANT_REVOKED = "GrantRevoked"
    ADAPTER_RETURNED_SUCCESS = "AdapterReturnedSuccess"
    ADAPTER_REJECTED_PRE_FLIGHT = "AdapterRejectedPreFlight"
    ADAPTER_TIMED_OUT = "AdapterTimedOut"
    READBACK_MATCHED = "ReadbackMatched"
    READBACK_CONFLICTING = "ReadbackConflicting"
    READBACK_UNAVAILABLE = "ReadbackUnavailable"
    READBACK_DEFERRED = "ReadbackDeferred"
    PROJECTION_UPDATED = "ProjectionUpdated"
    CLOSE_REQUESTED = "CloseRequested"
    HUMAN_ESTABLISHED_REALITY = "HumanEstablishedReality"
    LATER_OBSERVATION_PROVES = "LaterObservationProves"
    TIMER_FIRED = "TimerFired"


class RowKind(str, Enum):
    """How a §14 row relates to the canonical event registry. Structured, never prose.

    The G2 adjudication settled that a transition's relationship to its event is a CLASSIFICATION,
    not a sentence: `events/registry.md` §3 names one producer transition per event, and a row that
    performs a durable write while naming somebody else's event is a `CONSUMES` row that must prove
    the relationship. These three values are the ones M2's twenty-five rows actually take.
    """

    PRODUCER = "PRODUCER"
    CONSUMES = "CONSUMES"
    NON_PRODUCING = "NON_PRODUCING"


# --------------------------------------------------------------------------- the transition table

@dataclass(frozen=True)
class TransitionRow:
    """One row of §14. Data, so `AC-MACH-000` can enumerate it and compare it to the specification."""

    id: str
    from_states: tuple[PipelineState, ...]
    to_state: PipelineState | None
    triggers: tuple[Trigger, ...]
    trigger_types: tuple[str, ...]           # H|S|X|T|P|B|R — the registry §1 codes
    kind: RowKind
    event_name: str | None = None            # set iff kind is PRODUCER
    consumes: tuple[str, ...] = ()           # set iff kind is CONSUMES
    creates: bool = False                    # PL-1 only: the row that brings the attempt into being
    absorbs: bool = False                    # PL-1b only: a clash, which is not a transition
    illegal: bool = False                    # PL-15x only: declared ILLEGAL by the specification
    co_commits_with: str | None = None       # PL-12 only: "SAME commit as verify"
    # ### PL-11d ONLY — A PRODUCER ROW WHOSE EVENT RIDES ON SOMEBODY ELSE'S AGGREGATE.
    # `VerificationDeferred` is the one contract the registry attributes to a PL-* transition while
    # declaring `aggregate_type: effect_grant` (family F3's default). Its ordering key is therefore
    # `(tenant, effect_grant:<grant_id>, <the GRANT's version>)` — and the grant's version is M3's,
    # which is a later unit. M2 performs PL-11d's durable write (`recheck_at`) and does NOT emit,
    # because emitting on a version this machine would have to GUESS is worse than not emitting:
    # a guessed version misorders a strict stream permanently and silently. Debt P6-D13.
    emits_on_foreign_aggregate: str | None = None
    # PL-15 reaches TWO states, resolved at runtime by the establishing event's own `outcome`.
    alternate_to_state: PipelineState | None = None
    # ### THE SPECIFICATION'S OWN CLASSIFICATION, NAMED HERE SO IT IS DATA RATHER THAN A COMMENT.
    # §7 "Machine defaults": *"consequential transitions = **PL-8 (checkpoint) and PL-9 (claim)
    # only**; all others administrative."* The value is the KERNEL PATH that owns the row, so the
    # declaration answers both questions a caller has — *is this consequential?* and *who executes
    # it?* — from one place. `None` means administrative.
    consequential: str | None = None

    @property
    def independently_fireable(self) -> bool:
        """Can a caller drive this row by presenting its trigger? Four rows cannot, each for a
        different reason the specification states outright, and each is excluded HERE rather than at
        four call sites."""
        return not (self.creates or self.absorbs or self.illegal or self.co_commits_with)


# ### THE TWENTY-FIVE ROWS OF `state-machines/02-pipeline-instance.machine.md` §14, VERBATIM IN
# STRUCTURE. Order follows the specification so the two can be read side by side. `AC-MACH-000`
# asserts the identifier sets are EQUAL — not that the counts match.
TRANSITIONS: tuple[TransitionRow, ...] = (
    TransitionRow(
        id="PL-1", from_states=(), to_state=PipelineState.PROPOSED,
        triggers=(Trigger.INTENT_PROPOSED,), trigger_types=("S", "H"),
        kind=RowKind.PRODUCER, event_name="PipelineStarted", creates=True,
    ),
    TransitionRow(
        # No From→To at all: §14's cell is "*(reservation clash)*". A second proposal for a logical
        # effect a live attempt already holds is ABSORBED — one card, not a race.
        id="PL-1b", from_states=(), to_state=None,
        triggers=(Trigger.INTENT_PROPOSED,), trigger_types=("S",),
        kind=RowKind.PRODUCER, event_name="DuplicateProposalAbsorbed", absorbs=True,
    ),
    TransitionRow(
        id="PL-2", from_states=(PipelineState.PROPOSED,), to_state=PipelineState.POLICY_CHECKED,
        triggers=(Trigger.POLICY_EVALUATED,), trigger_types=("S",),
        kind=RowKind.PRODUCER, event_name="PolicyEvaluated",
    ),
    TransitionRow(
        id="PL-3", from_states=(PipelineState.PROPOSED,), to_state=PipelineState.REJECTED,
        triggers=(Trigger.POLICY_EVALUATED,), trigger_types=("S",),
        kind=RowKind.PRODUCER, event_name="PipelineRejected",
    ),
    TransitionRow(
        id="PL-4", from_states=(PipelineState.POLICY_CHECKED,), to_state=PipelineState.VALIDATED,
        triggers=(Trigger.VALIDATION_COMPLETED,), trigger_types=("S",),
        kind=RowKind.PRODUCER, event_name="IntentValidated",
    ),
    TransitionRow(
        id="PL-5", from_states=(PipelineState.POLICY_CHECKED,), to_state=PipelineState.REJECTED,
        triggers=(Trigger.VALIDATION_COMPLETED,), trigger_types=("S",),
        kind=RowKind.PRODUCER, event_name="PipelineRejected",
    ),
    TransitionRow(
        # CONSUMES: `ApprovalRequested` is AP-1's (M4). §14's Writes cell is "co-commit M4
        # `REQUESTED`" — M2 moves its own row; the event belongs to the machine that creates the
        # request, and M2 emitting it would be M2 asserting an approval request it did not create.
        id="PL-6", from_states=(PipelineState.VALIDATED,),
        to_state=PipelineState.AWAITING_APPROVAL,
        triggers=(Trigger.GATE_ROUTED,), trigger_types=("S",),
        kind=RowKind.CONSUMES, consumes=("ApprovalRequested",),
    ),
    TransitionRow(
        id="PL-7a", from_states=(PipelineState.VALIDATED,), to_state=PipelineState.CHECKPOINT,
        triggers=(Trigger.GATE_ROUTED,), trigger_types=("S",),
        kind=RowKind.PRODUCER, event_name="AutonomousAdmissionRecorded",
    ),
    TransitionRow(
        id="PL-7b", from_states=(PipelineState.AWAITING_APPROVAL,),
        to_state=PipelineState.CHECKPOINT,
        triggers=(Trigger.APPROVAL_GRANTED,), trigger_types=("H",),
        kind=RowKind.PRODUCER, event_name="ApprovalBound",
    ),
    TransitionRow(
        id="PL-7v", from_states=(PipelineState.AWAITING_APPROVAL,), to_state=PipelineState.VOIDED,
        triggers=(Trigger.APPROVAL_DENIED, Trigger.APPROVAL_EXPIRED,
                  Trigger.POLICY_VERSION_CHANGED, Trigger.BRAKE_ENGAGED),
        trigger_types=("H", "P", "B"),
        kind=RowKind.PRODUCER, event_name="PipelineVoided",
    ),
    TransitionRow(
        id="PL-8", from_states=(PipelineState.CHECKPOINT,), to_state=PipelineState.GRANTED,
        triggers=(Trigger.CHECKPOINT_RUN,), trigger_types=("S",),
        kind=RowKind.PRODUCER, event_name="CheckpointPassed", consequential="checkpoint",
    ),
    TransitionRow(
        id="PL-8f", from_states=(PipelineState.CHECKPOINT,), to_state=PipelineState.VOIDED,
        triggers=(Trigger.CHECKPOINT_RUN,), trigger_types=("S",),
        kind=RowKind.PRODUCER, event_name="CheckpointFailed",
    ),
    TransitionRow(
        # CONSUMES: `GrantClaimed` is EF-2's (M3). M2 PERFORMS the CAS — §17 makes it *"the
        # serialization point"* — and the ledger row it wins is M3's, so the event is M3's too.
        # §14's Event cell names `GrantClaimed` alone; `EffectAttempted` is in the Writes cell as
        # part of EF-2's co-commit ("emitted BEFORE the call"). Both are M3's, and neither is this
        # machine's to emit — but only the first is what §14 declares PL-9 CONSUMES.
        id="PL-9", from_states=(PipelineState.GRANTED,), to_state=PipelineState.CLAIMED,
        triggers=(Trigger.CLAIM_ATTEMPTED,), trigger_types=("S",),
        kind=RowKind.CONSUMES, consumes=("GrantClaimed",), consequential="claim",
    ),
    TransitionRow(
        id="PL-9v", from_states=(PipelineState.GRANTED,), to_state=PipelineState.VOIDED,
        triggers=(Trigger.GRANT_EXPIRED, Trigger.GRANT_REVOKED), trigger_types=("T", "B", "P"),
        kind=RowKind.PRODUCER, event_name="PipelineVoided",
    ),
    TransitionRow(
        id="PL-10", from_states=(PipelineState.CLAIMED,), to_state=PipelineState.EXECUTED,
        triggers=(Trigger.ADAPTER_RETURNED_SUCCESS,), trigger_types=("X",),
        kind=RowKind.CONSUMES, consumes=("EffectExecuted",),
    ),
    TransitionRow(
        id="PL-10f", from_states=(PipelineState.CLAIMED,), to_state=PipelineState.FAILED,
        triggers=(Trigger.ADAPTER_REJECTED_PRE_FLIGHT,), trigger_types=("S",),
        kind=RowKind.CONSUMES, consumes=("EffectFailed",),
    ),
    TransitionRow(
        id="PL-10u", from_states=(PipelineState.CLAIMED,),
        to_state=PipelineState.NEEDS_VERIFICATION,
        triggers=(Trigger.ADAPTER_TIMED_OUT,), trigger_types=("S", "R"),
        kind=RowKind.CONSUMES, consumes=("OutcomeUnknown",),
    ),
    TransitionRow(
        id="PL-11", from_states=(PipelineState.EXECUTED,), to_state=PipelineState.VERIFIED,
        triggers=(Trigger.READBACK_MATCHED,), trigger_types=("X",),
        kind=RowKind.CONSUMES, consumes=("EffectVerified",),
    ),
    TransitionRow(
        id="PL-11c", from_states=(PipelineState.EXECUTED,),
        to_state=PipelineState.NEEDS_VERIFICATION,
        triggers=(Trigger.READBACK_CONFLICTING, Trigger.READBACK_UNAVAILABLE),
        trigger_types=("X",),
        kind=RowKind.CONSUMES, consumes=("VerificationConflict", "VerificationUnavailable"),
    ),
    TransitionRow(
        id="PL-11d", from_states=(PipelineState.EXECUTED,), to_state=PipelineState.EXECUTED,
        triggers=(Trigger.READBACK_DEFERRED,), trigger_types=("X",),
        kind=RowKind.PRODUCER, event_name="VerificationDeferred",
        emits_on_foreign_aggregate="effect_grant",
    ),
    TransitionRow(
        # ### NO TRIGGER OF ITS OWN, BECAUSE §14 SAYS "SAME commit as verify". PL-12 is not a step a
        # caller may take; it is the second half of PL-11's commit, and acceptance item (f) is that
        # verify and record are one commit. A separately-fireable PL-12 would make a VERIFIED
        # pipeline that is not yet RECORDED an observable state, which is exactly the window in
        # which a crash loses the record of a verified effect.
        id="PL-12", from_states=(PipelineState.VERIFIED,), to_state=PipelineState.RECORDED,
        triggers=(), trigger_types=("S",),
        kind=RowKind.PRODUCER, event_name="EffectRecorded", co_commits_with="PL-11",
    ),
    TransitionRow(
        id="PL-13", from_states=(PipelineState.RECORDED,), to_state=PipelineState.PROJECTED,
        triggers=(Trigger.PROJECTION_UPDATED,), trigger_types=("S",),
        kind=RowKind.PRODUCER, event_name="ProjectionUpdated",
    ),
    TransitionRow(
        id="PL-14", from_states=(PipelineState.PROJECTED,), to_state=PipelineState.CLOSED,
        triggers=(Trigger.CLOSE_REQUESTED,), trigger_types=("S",),
        kind=RowKind.PRODUCER, event_name="PipelineClosed",
    ),
    TransitionRow(
        # Two target states, chosen by the establishing event's own `outcome` — never by the caller
        # and never positionally.
        id="PL-15", from_states=(PipelineState.NEEDS_VERIFICATION,), to_state=PipelineState.VERIFIED,
        alternate_to_state=PipelineState.FAILED,
        triggers=(Trigger.HUMAN_ESTABLISHED_REALITY, Trigger.LATER_OBSERVATION_PROVES),
        trigger_types=("H", "X"),
        kind=RowKind.CONSUMES, consumes=("RealityEstablished",),
    ),
    TransitionRow(
        # ⛔ ILLEGAL (GR-6). Declared in the table because `AC-MACH-000` compares the specification's
        # TWENTY-FIVE identifiers, and because a rule that is never expressible is a rule nobody can
        # test. Excluded from `legal_transitions`, so GR-1 refuses it like any unenumerated pair.
        id="PL-15x", from_states=(PipelineState.NEEDS_VERIFICATION,), to_state=None,
        triggers=(Trigger.TIMER_FIRED,), trigger_types=("T",),
        kind=RowKind.NON_PRODUCING, illegal=True,
    ),
)

TRANSITIONS_BY_ID: Mapping[str, TransitionRow] = {row.id: row for row in TRANSITIONS}

# ============================================================ THE KERNEL-OWNED POPULATION (§7/§15)
#
# ### THE INVARIANT THIS BLOCK EXISTS FOR, IN THE SPECIFICATION'S OWN WORDS (§15):
#     *"`GRANTED` reachable without a `CheckpointPassed` witness → impossible (PL-8 co-commits).
#      `CLAIMED` without a successful CAS → impossible."*
#
# Those two states are reachable ONLY through P3's kernel — the seven checks plus the witness insert
# plus the grant mint for one, the atomic revalidating CAS for the other. The danger is not that the
# kernel is wrong; it is that the ORDINARY row-guard path can reach the same rows. It could: a
# consumed canonical `GrantClaimed` selected PL-9, satisfied a guard branch that did not exist, and
# wrote `CLAIMED` with no CAS, no grant handle and a grant ledger still reading `GRANTED`. That was
# a real defect on the first P6-CP-2 candidate, found in independent review.
#
# ### THE POPULATION IS DERIVED, NOT LISTED — that is the whole point. A hand-kept list of "the
# dangerous rows" is correct on the day it is written and silently wrong on the day a row is added.
#
#   SEED    the rows §7 declares consequential (`row.consequential`), which is PL-8 and PL-9.
#   CLOSURE every row sharing a (from-state, trigger) pair with a seed — because a row reachable by
#           the SAME pair is a row the ordinary path can select INSTEAD of the kernel's. PL-8f is in
#           the population for exactly this reason: it is the checkpoint's failure branch, its
#           `{step, reason}` are the kernel's refusal output, and nothing but the kernel can supply
#           them. A consumed CHECKPOINT_RUN picked it by precedence and then raised a payload
#           violation INSIDE the inbox transaction, rolling the receipt back and redelivering
#           forever. Same root cause, so it is closed by the same derivation rather than patched.
def _kernel_owned_row_ids() -> frozenset[str]:
    seeds = tuple(row for row in TRANSITIONS if row.consequential)
    pairs = {(state, trig) for row in seeds for state in row.from_states for trig in row.triggers}
    return frozenset(
        row.id for row in TRANSITIONS
        if row.consequential
        or any((state, trig) in pairs for state in row.from_states for trig in row.triggers)
    )


CONSEQUENTIAL_ROW_IDS: frozenset[str] = frozenset(
    row.id for row in TRANSITIONS if row.consequential)
KERNEL_OWNED_ROW_IDS: frozenset[str] = _kernel_owned_row_ids()

# Which kernel path a trigger routes to. Derived from the SEED rows, because a closure member is
# executed by its seed's path (PL-8f is an outcome of the checkpoint run, not a path of its own).
KERNEL_PATH_BY_TRIGGER: Mapping[Trigger, str] = {
    trig: row.consequential
    for row in TRANSITIONS if row.consequential
    for trig in row.triggers
}

# ### THE ONLY METHODS ALLOWED TO EXECUTE A KERNEL-OWNED ROW, KEYED BY THE DECLARED PATH.
# A declared path with no entry point here FAILS CLOSED at `apply` rather than falling through to
# the ordinary path — the fall-through is precisely how a new consequential row would silently
# acquire an unguarded execution route. `AC-MACH-000`'s companion guard asserts these keys are
# exactly the declared path set, so adding a row without its executor breaks the build.
KERNEL_ENTRY_POINTS: Mapping[str, str] = {
    "checkpoint": "_run_checkpoint",
    "claim": "_run_claim",
}

# §32 "Events emitted", derived from the table rather than listed. The contract gate refuses an
# envelope whose `producer_transition_id` is not among the contract's declared producers, so this
# set is also the set the outbox will accept from this machine — enumerating it by hand would be a
# second list that stops matching.
PRODUCED_CONTRACTS: frozenset[str] = frozenset(
    row.event_name for row in TRANSITIONS
    if row.kind is RowKind.PRODUCER and row.event_name and not row.emits_on_foreign_aggregate
)

# ### THE ONE PRODUCER ROW WHOSE EMISSION THIS UNIT CANNOT PERFORM, NAMED RATHER THAN OMITTED.
# Recorded as debt P6-D13. A reader who sees `VerificationDeferred` missing from the outbox should
# find the reason here and not have to infer it from an absence.
DEFERRED_EMISSIONS: Mapping[str, str] = {
    row.event_name: row.emits_on_foreign_aggregate
    for row in TRANSITIONS
    if row.emits_on_foreign_aggregate and row.event_name
}

# ### THE EVENTS THIS MACHINE CONSUMES AND DOES NOT EMIT, AND THE DEBT THAT COMES WITH THEM.
# Each belongs to an EF-* or AP-* producer, i.e. to M3 or M4, which are later P6 units. M2 performs
# its own half of each co-commit; the partner's half — the grant-state write, the approval consume,
# and the emission of these contracts — lands when those machines do. Recorded as P6-D10 rather than
# faked: emitting one of these with a PL-* producer id is refused by the contract gate, and it
# SHOULD be, because the event would assert a fact about a machine that does not exist.
CONSUMED_CONTRACTS: frozenset[str] = frozenset(
    name for row in TRANSITIONS for name in row.consumes
)

# §16's precedence. Consulted ONLY if more than one row survives its guards for one (state, trigger)
# — which every discriminated pair here is built never to do, and a test asserts it. It exists
# because the specification states it, and a precedence rule that is never expressible is untestable.
# §16: *"`BrakeEngaged` and `PolicyVersionChanged` void a pre-claim pipeline with priority over
# advancement. Drift > approval-bind."*
PRECEDENCE: tuple[str, ...] = (
    "PL-7v", "PL-9v", "PL-3", "PL-5", "PL-8f", "PL-2", "PL-4", "PL-6", "PL-7a", "PL-7b",
    "PL-8", "PL-9", "PL-10f", "PL-10u", "PL-10", "PL-11c", "PL-11", "PL-11d", "PL-13", "PL-14",
    "PL-15",
)


def legal_transitions(state: PipelineState, trigger: Trigger) -> tuple[TransitionRow, ...]:
    """Every independently-fireable row whose (from-state, trigger) matches. Empty ⇒ ILLEGAL (GR-1)."""
    return tuple(
        row for row in TRANSITIONS
        if row.independently_fireable and state in row.from_states and trigger in row.triggers
    )


def rows_for_trigger(trigger: Trigger) -> tuple[TransitionRow, ...]:
    return tuple(row for row in TRANSITIONS if row.independently_fireable and trigger in row.triggers)


def pipeline_must_exist(trigger: Trigger) -> bool:
    """Is an existing attempt a PREREQUISITE of this trigger, or is it the trigger's PRODUCT?

    ### DERIVED FROM §14, NOT LISTED — M1's `work_item_must_exist`, same argument. A hand-kept list
    of "the creation triggers" is right on the day it is written. `IntentProposed` brings the attempt
    into existence (PL-1) and absorbs a clash onto an existing one (PL-1b); every other trigger is
    ABOUT an attempt that must already be there, and a trigger with NO row at all answers True
    because parking a stranger is recoverable where skipping one is not.
    """
    rows = tuple(row for row in TRANSITIONS if trigger in row.triggers)
    return not (rows and all(row.creates or row.absorbs for row in rows))


TERMINAL_STATES: frozenset[PipelineState] = frozenset(
    PipelineState(s) for s in TERMINAL_PIPELINE_STATES
)
POST_CHECKPOINT: frozenset[PipelineState] = frozenset(
    PipelineState(s) for s in POST_CHECKPOINT_STATES
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------------------------ the row

@dataclass(frozen=True)
class PipelineInstance:
    """One attempt, as the machine reads it."""

    tenant: str
    pipeline_instance_id: str
    work_item_id: str
    state: PipelineState
    version: int
    owner_id: str
    action_class: str
    target_system: str
    target_resource_id: str
    target_operation: str
    occurrence_key: str
    commit_key: str
    attempt_seq: int
    absorbed_count: int
    created_at: str
    updated_at: str
    supersedes: str | None = None
    last_absorbed_ref: str | None = None
    policy_version: str | None = None
    gate_decision: str | None = None
    gate_reason: str | None = None
    approval_id: str | None = None
    material_facts_fingerprint: str | None = None
    checkpoint_id: str | None = None
    grant_id: str | None = None
    claimed_at: str | None = None
    reason: str | None = None
    refused_step: int | None = None
    failure_proof: str | None = None
    unknown_reason: str | None = None
    unknown_outcome_ref: str | None = None
    recheck_at: str | None = None
    decision_ref: str | None = None
    decision_ref_kind: str | None = None

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    @property
    def effect(self) -> LogicalEffect:
        """The logical effect this attempt is at — re-derived from the row, never from a caller.

        §20 requires a retry to carry the SAME commit key, and the only way that is a fact rather
        than a hope is for the key to come from the row that already holds it.
        """
        return LogicalEffect(
            tenant=self.tenant, action_class=self.action_class, target_system=self.target_system,
            target_resource_id=self.target_resource_id, target_operation=self.target_operation,
            occurrence_key=self.occurrence_key,
        )


@dataclass(frozen=True)
class TransitionResult:
    """What one transition did. Every field is read back from the row, never from the intention.

    `event_id` is `None` for a `CONSUMES` row and that is information, not a gap: this machine
    performed the state change and emitted nothing, because the canonical event belongs to the
    machine it co-commits with.
    """

    transition_id: str
    pipeline: PipelineInstance
    from_state: PipelineState | None
    to_state: PipelineState
    event_id: str | None = None
    event_name: str | None = None
    co_commits: tuple["TransitionResult", ...] = ()
    # ### PL-8 ONLY, AND DELIBERATELY NOT DURABLE. The signed grant handle is the capability PL-9
    # presents to the CAS. P3 keeps the raw token out of the ledger — only its digest lands on the
    # grant row — and holds the signing key in memory, so a restart between PL-8 and PL-9 loses the
    # handle, the grant expires unclaimed, and NOTHING HAPPENED. That is the fail-closed direction
    # and §35's "no async work between PL-8 and PL-9" is what makes it cheap. Persisting the handle
    # to make a restart survivable would turn a lost capability into a resumable one, which is
    # precisely the property the two-key rule declines to offer.
    grant_handle: EffectGrantHandle | None = None


@dataclass(frozen=True)
class AbsorbedProposal:
    """PL-1b. A duplicate proposal absorbed onto the live attempt that already holds the key."""

    holder: PipelineInstance
    absorbed_ref: str
    event_id: str
    idempotency_identity: str
    already_absorbed: bool


@dataclass(frozen=True)
class ProposalOutcome:
    """What proposing an intent did — a NEW attempt, or absorption onto the one already running.

    Both are correct outcomes and neither is a failure. Returning a union rather than raising on the
    clash is §14 PL-1b's own instruction: *"one card"*.
    """

    started: TransitionResult | None = None
    absorbed: AbsorbedProposal | None = None

    @property
    def is_new_attempt(self) -> bool:
        return self.started is not None


@dataclass(frozen=True)
class IllegalAttemptRecord:
    """What recording ONE refused attempt did — including the case where it had already been done."""

    event_id: str
    idempotency_identity: str
    already_recorded: bool


@dataclass(frozen=True)
class ConsumedTransition:
    """What consuming one canonical trigger did — including the case where it did nothing.

    `consume.outcome` is P5's and is about DELIVERY. `transition`, `refusal` and `refusal_kind` are
    about the MACHINE. Keeping them apart is what stops "the event was delivered" being read as
    "the attempt moved".
    """

    consume: ConsumeResult
    transition: TransitionResult | None = None
    refusal: str | None = None
    refusal_kind: str | None = None
    illegal_record: IllegalAttemptRecord | None = None

    @property
    def moved(self) -> bool:
        return self.transition is not None


@dataclass
class _Facts:
    """The caller-supplied facts a guard may read. Deliberately explicit and deliberately dumb.

    ### NOTHING HERE IS INFERRED, AND TWO ENTRIES ARE THE REASON THE WHOLE CLASS IS EXPLICIT.
    `model_inferred_material_fact` is GR-8: the machine cannot discover it, so a caller that does not
    state it is treated as not having checked, and PL-2 refuses. `failure_proof` is GR-5: a caller
    that cannot produce affirmative evidence the effect did NOT happen gets `NEEDS_VERIFICATION`,
    never `FAILED`. A machine that derived either would be right most of the time, which is the
    worst possible failure profile for money.
    """

    policy_version: str | None = None
    gate_decision: GateDecision | str | None = None
    policy_decision: str | None = None            # PERMIT | DENY
    rules_matched: Sequence[str] | None = None
    reason: str | None = None
    model_inferred_material_fact: bool | None = None
    validation_passed: bool | None = None
    money_fence_passed: bool | None = None
    document_fence_passed: bool | None = None
    material_fields_consistent: bool | None = None
    open_conflict: bool | None = None
    caps_evaluated: Mapping[str, Any] | None = None
    brake_version: str | None = None
    approval_id: str | None = None
    approval_commit_key: str | None = None
    approval_fingerprint: str | None = None
    grant_id: str | None = None
    failure_proof: str | None = None
    unknown_reason: str | None = None
    unknown_outcome_ref: str | None = None
    matched_fingerprint: str | None = None
    verification_outcome: str | None = None
    health_signal: str | None = None
    recheck_at: str | None = None
    deferral_bound_until: str | None = None
    entity_ref: str | None = None
    from_effect_id: str | None = None
    outcome: str | None = None                    # PL-15: VERIFIED | FAILED
    decision_ref: str | None = None
    decision_ref_kind: str | None = None
    # PL-8 / PL-9 — the kernel and its typed inputs. Never constructed here: the machine is handed a
    # kernel, it does not make one, and it certainly does not make a GateRegistry.
    kernel: Any = None
    checkpoint_inputs: CheckpointInputs | None = None
    handle: EffectGrantHandle | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------------- the machine

class PipelineMachine:
    """M2, on an existing connection, bound to ONE tenant.

    Bound at construction rather than per call, for the reason `DedupInbox`, `CheckpointKernel` and
    `WorkItemMachine` are: a machine that could be re-pointed at another tenant per call would put
    [C-1] in the caller's hands.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        tenant: str,
        clock: Callable[[], datetime] | None = None,
        producer_component: str = PRODUCER_COMPONENT,
    ) -> None:
        if getattr(conn, "row_factory", None) is not sqlite3.Row:
            raise PipelineError(
                "PipelineMachine reads columns by name and requires `row_factory = sqlite3.Row` "
                "(WorkflowStore sets it; PostgresConnection reports it)."
            )
        self._conn = conn
        self._tenant = require_tenant(tenant, context="PipelineMachine")
        self._clock = clock or _utc_now
        self._component = producer_component

    @property
    def tenant(self) -> str:
        return self._tenant

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    # --- reads -----------------------------------------------------------------------------------

    def get(self, pipeline_instance_id: str) -> PipelineInstance | None:
        row = self._conn.execute(
            "SELECT * FROM pipeline_instances WHERE tenant = ? AND pipeline_instance_id = ?",
            (self._tenant, pipeline_instance_id),
        ).fetchone()
        return _row_to_pipeline(row) if row is not None else None

    def require(self, pipeline_instance_id: str) -> PipelineInstance:
        found = self.get(pipeline_instance_id)
        if found is None:
            raise UnknownPipeline(
                f"no Pipeline Instance {pipeline_instance_id!r} for tenant {self._tenant!r}. This "
                f"machine does not look outside its tenant to find out whether it exists elsewhere "
                f"— [C-1] rejects a cross-tenant question rather than answering it carefully."
            )
        return found

    def live_holder(self, commit_key: str) -> PipelineInstance | None:
        """The non-terminal attempt holding this logical effect's Layer-1 reservation, if any.

        The index guarantees there is at most one; this reads it rather than trusting that, because
        the answer is what PL-1b absorbs onto and naming the wrong holder would attach evidence of a
        duplicate to an attempt that is not the duplicate of anything.
        """
        placeholders = ",".join("?" for _ in TERMINAL_PIPELINE_STATES)
        row = self._conn.execute(
            f"SELECT * FROM pipeline_instances "
            f" WHERE tenant = ? AND commit_key = ? AND state NOT IN ({placeholders})",
            (self._tenant, commit_key, *TERMINAL_PIPELINE_STATES),
        ).fetchone()
        return _row_to_pipeline(row) if row is not None else None

    def attempts_for(self, commit_key: str) -> list[PipelineInstance]:
        """Every attempt at one logical effect, oldest first. "Attempt #1, #2" in an operator's words."""
        return [
            _row_to_pipeline(r) for r in self._conn.execute(
                "SELECT * FROM pipeline_instances WHERE tenant = ? AND commit_key = ? "
                " ORDER BY attempt_seq",
                (self._tenant, commit_key),
            ).fetchall()
        ]

    def for_work_item(self, work_item_id: str) -> list[PipelineInstance]:
        return [
            _row_to_pipeline(r) for r in self._conn.execute(
                "SELECT * FROM pipeline_instances WHERE tenant = ? AND work_item_id = ? "
                " ORDER BY created_at, pipeline_instance_id",
                (self._tenant, work_item_id),
            ).fetchall()
        ]

    def needs_verification(self) -> list[PipelineInstance]:
        """§38's Sev-1 queue: the attempts nobody can say happened or did not, with their owners.

        ### A NEGATIVE ASSERTION NEEDS A PROVEN POPULATION (CLAUDE.md §9), so this returns the rows
        and the caller is expected to assert against a non-empty attempt population. A "no unknown
        outcomes" check over an empty table is a green check that parsed nothing.
        """
        return [
            _row_to_pipeline(r) for r in self._conn.execute(
                "SELECT * FROM pipeline_instances WHERE tenant = ? AND state = ? "
                " ORDER BY created_at, pipeline_instance_id",
                (self._tenant, PipelineState.NEEDS_VERIFICATION.value),
            ).fetchall()
        ]

    def ownerless(self) -> list[str]:
        """Attempts whose accountable human is not an ACTIVE recorded authority. Should be empty."""
        placeholders = ",".join("?" for _ in TERMINAL_PIPELINE_STATES)
        return [
            r["pipeline_instance_id"] for r in self._conn.execute(
                f"""
                SELECT p.pipeline_instance_id FROM pipeline_instances p
                 WHERE p.tenant = ? AND p.state NOT IN ({placeholders})
                   AND NOT EXISTS (SELECT 1 FROM tenant_humans h
                                    WHERE h.tenant = p.tenant AND h.human_id = p.owner_id
                                      AND h.state = 'ACTIVE')
                 ORDER BY p.pipeline_instance_id
                """,
                (self._tenant, *TERMINAL_PIPELINE_STATES),
            ).fetchall()
        ]

    # --- PL-1 / PL-1b -----------------------------------------------------------------------------

    def propose(
        self,
        *,
        pipeline_instance_id: str,
        work_item_id: str,
        effect: LogicalEffect,
        actor_type: str,
        actor_id: str,
        proposal_ref: str | None = None,
        supersedes: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> ProposalOutcome:
        """PL-1, or PL-1b when a live attempt already holds this logical effect's reservation.

        ### THE COMMIT KEY IS DERIVED, NEVER SUPPLIED. It comes from the `LogicalEffect`, whose six
        fields ARE the identity of the effect and among which **the amount does not appear**
        (ADR-009, CLAUDE.md rule 8). So "bill load 4471" is one logical effect whether a model
        proposed $1,400 or $1,450 — which is precisely why the second proposal must be absorbed
        rather than raced, and why a caller cannot vary the key between retries.

        ### THE INTENT IS INERT (GR-7). `actor_type='model'` is refused before anything is read: a
        model may emit a `ProposedIntent`, which is data. Turning that data into an attempt is a
        deterministic act, and this machine will not accept a model as the actor who took it.
        """
        self._require_actor(actor_type)
        if effect.tenant.strip().lower() != self._tenant.strip().lower():
            raise PipelineError(
                f"the effect names tenant {effect.tenant!r}; this machine is bound to "
                f"{self._tenant!r}. An attempt never crosses a tenant [C-1]."
            )
        key = effect.key()
        owner = self._require_work_item_owner(work_item_id)

        # ### A RETRY IS NOT A DUPLICATE PROPOSAL, AND THE ORDER HERE IS WHAT KEEPS THEM APART.
        # A caller that names `supersedes` is stating "this replaces attempt X", so its lineage is
        # checked FIRST and an attempt that has not finished is REFUSED by name. Absorbing it
        # instead would answer a retry request with silence — the operator would see one card, be
        # told nothing, and never learn that the reason they cannot retry is that we still cannot
        # say whether the first attempt touched the outside world (§20).
        if supersedes is not None:
            self._attempt_lineage(key, supersedes)

        holder = self.live_holder(key)
        if holder is not None:
            return ProposalOutcome(absorbed=self._absorb_duplicate(
                holder, proposal_ref=proposal_ref or pipeline_instance_id,
                actor_type=actor_type, actor_id=actor_id, correlation_id=correlation_id,
                causation_id=causation_id, trace_id=trace_id,
            ))

        attempt_seq, supersedes_id = self._attempt_lineage(key, supersedes)
        now = format_instant(self._clock())
        envelope = self._envelope(
            event_name="PipelineStarted", transition_id="PL-1",
            pipeline_instance_id=pipeline_instance_id, work_item_id=work_item_id,
            aggregate_version=1, owner_id=owner, actor_type=actor_type, actor_id=actor_id,
            payload={"commit_key": key},
            correlation_id=correlation_id or work_item_id, causation_id=causation_id,
            trace_id=trace_id, event_id=event_id, now=now,
        )
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                """
                INSERT INTO pipeline_instances (
                    tenant, pipeline_instance_id, work_item_id, state, version, owner_id,
                    action_class, target_system, target_resource_id, target_operation,
                    occurrence_key, commit_key, attempt_seq, supersedes, absorbed_count,
                    created_at, updated_at
                ) VALUES (?,?,?, 'PROPOSED', 1, ?, ?,?,?,?,?,?, ?,?, 0, ?,?)
                """,
                (self._tenant, pipeline_instance_id, work_item_id, owner,
                 effect.action_class, effect.target_system, effect.target_resource_id,
                 effect.target_operation, effect.occurrence_key or "", key,
                 attempt_seq, supersedes_id, now, now),
            )
            TransactionalOutbox(self._conn, tenant=self._tenant, clock=self._clock).emit(envelope)
            self._conn.commit()
        except integrity_errors() as exc:
            self._conn.rollback()
            # The reservation is a UNIQUE index, so a competitor that inserted between the read
            # above and this write loses HERE rather than producing a second attempt. Reported as
            # the reservation being held — which is what it is — not as a generic write failure.
            raise ReservationHeld(
                f"cannot start attempt {pipeline_instance_id!r} for {self._tenant!r}: {exc}. If "
                f"this is the Layer-1 reservation, another live attempt acquired {key[:12]}… first "
                f"and this proposal should be absorbed onto it (PL-1b), not retried."
            ) from exc
        except BaseException:
            self._conn.rollback()
            raise
        started = self.require(pipeline_instance_id)
        return ProposalOutcome(started=TransitionResult(
            transition_id="PL-1", pipeline=started, from_state=None,
            to_state=PipelineState.PROPOSED, event_id=envelope.event_id,
            event_name="PipelineStarted",
        ))

    def _attempt_lineage(self, key: str, supersedes: str | None) -> tuple[int, str | None]:
        """Which attempt number this is, and which prior attempt it replaces. §20.

        ### A RETRY IS A NEW INSTANCE, AND IT MUST SAY WHAT IT IS RETRYING. The attempt number is
        derived from the attempts that already exist rather than taken from the caller, so "attempt
        #2" cannot be claimed by an attempt that is actually the fourth. `supersedes` is the caller's
        because only the caller knows which prior attempt it is replacing — but it is checked: the
        named attempt must exist, share this commit key, and be finished. Retrying a live attempt is
        the double-effect defect, and retrying from `NEEDS_VERIFICATION` is the one the Layer-1 index
        already refuses (that state is non-terminal and keeps the key).
        """
        prior = self.attempts_for(key)
        if not prior:
            if supersedes is not None:
                raise PipelineError(
                    f"this is the FIRST attempt at {key[:12]}… and it names {supersedes!r} as the "
                    f"attempt it supersedes. A first attempt supersedes nothing."
                )
            return 1, None
        if supersedes is None:
            raise PipelineError(
                f"{len(prior)} attempt(s) at {key[:12]}… already exist and this proposal names none "
                f"of them. §20: a retry is a NEW instance at the SAME commit key, and an attempt "
                f"that does not say what it retries makes the lineage unreadable — 'attempt #2' "
                f"would be a number nobody could check."
            )
        superseded = self.get(supersedes)
        if superseded is None or superseded.commit_key != key:
            raise PipelineError(
                f"{supersedes!r} is not a prior attempt at this logical effect. A retry supersedes "
                f"an attempt at the SAME commit key; superseding one at another effect would attach "
                f"this attempt's lineage to a different obligation."
            )
        if not superseded.is_terminal:
            raise PipelineError(
                f"{supersedes!r} is {superseded.state.value} and has not finished. §20 permits a "
                f"retry only after a PROVABLE FAILED or a pre-claim VOIDED/REJECTED — and "
                f"NEEDS_VERIFICATION blocks it outright, because we cannot say whether the effect "
                f"happened. Retrying now is how one effect becomes two."
            )
        return max(p.attempt_seq for p in prior) + 1, supersedes

    def absorbed_proposal_identity(self, holder: PipelineInstance, absorbed_ref: str) -> str:
        """The idempotency identity of ONE absorbed duplicate. Exposed so a test can recompute it."""
        text = str(absorbed_ref or "").strip()
        if not text:
            raise PipelineError(
                "absorbing a duplicate proposal requires the identity of the proposal being "
                "absorbed. Blank would collapse every duplicate onto one record, which is the "
                "defect the explicit identity exists to remove — quietly, on the surface an "
                "operator reads to find out how often this is happening."
            )
        return "|".join((
            ABSORBED_PROPOSAL_IDENTITY_PREFIX, self._tenant, AGGREGATE_TYPE,
            holder.pipeline_instance_id, holder.commit_key, "PL-1b",
            "DuplicateProposalAbsorbed", text,
        ))

    def _absorb_duplicate(
        self,
        holder: PipelineInstance,
        *,
        proposal_ref: str,
        actor_type: str,
        actor_id: str,
        correlation_id: str | None,
        causation_id: str | None,
        trace_id: str | None,
    ) -> AbsorbedProposal:
        """PL-1b. `DuplicateProposalAbsorbed{commit_key, absorbed_ref}`, and the evidence it attaches.

        ### §14's WRITES CELL SAYS "attach evidence", AND THE TRANSPORT PROVES IT MEANS A DURABLE
        WRITE. The first version of this method attached the evidence only as the outbox event, on
        the reading that PL-1b's From→To cell — *(reservation clash)* — declares no transition. That
        is refused, mechanically and correctly: `DuplicateProposalAbsorbed` is an **F2** contract,
        `events/registry.md` §8 makes F2 STRICTLY ordered, and a strict event must OWN the
        `(tenant, aggregate, version)` it rides at. Riding at the holder's unchanged version means
        colliding with the transition that reached it, and the outbox aborts with
        `StrictOrderViolation`. So the absorption advances the holder's version and writes what it
        absorbed — the state does not change, which is what "no transition" actually meant.

        The identity carries the ABSORBED proposal's reference, so absorbing the same duplicate
        twice is one record and absorbing two different duplicates is two — decided under the write
        lock rather than discovered by exception, because a raise here on a redelivered proposal
        would be the poison loop M1's first candidate shipped.
        """
        identity = self.absorbed_proposal_identity(holder, proposal_ref)
        now = format_instant(self._clock())
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            already = self._recorded_identity(identity)
            if already is not None:
                self._conn.rollback()
                return AbsorbedProposal(
                    holder=holder, absorbed_ref=proposal_ref, event_id=already,
                    idempotency_identity=identity, already_absorbed=True,
                )
            new_version = holder.version + 1
            cursor = self._conn.execute(
                """
                UPDATE pipeline_instances
                   SET version = ?, updated_at = ?, absorbed_count = absorbed_count + 1,
                       last_absorbed_ref = ?
                 WHERE tenant = ? AND pipeline_instance_id = ? AND version = ? AND state = ?
                """,
                (new_version, now, proposal_ref, self._tenant, holder.pipeline_instance_id,
                 holder.version, holder.state.value),
            )
            if cursor.rowcount != 1:
                raise VersionConflict(
                    f"{holder.pipeline_instance_id!r} moved under PL-1b: the UPDATE matched "
                    f"{cursor.rowcount} rows at version {holder.version}. Reload and retry (GR-3)."
                )
            envelope = self._envelope(
                event_name="DuplicateProposalAbsorbed", transition_id="PL-1b",
                pipeline_instance_id=holder.pipeline_instance_id,
                work_item_id=holder.work_item_id, aggregate_version=new_version,
                owner_id=holder.owner_id, actor_type=actor_type, actor_id=actor_id,
                payload={"commit_key": holder.commit_key, "absorbed_ref": proposal_ref},
                correlation_id=correlation_id or holder.work_item_id, causation_id=causation_id,
                trace_id=trace_id, event_id=None, now=now, idempotency_identity=identity,
            )
            TransactionalOutbox(self._conn, tenant=self._tenant, clock=self._clock).emit(envelope)
            self._conn.commit()
        except DuplicateEmission:
            self._conn.rollback()
            repeat = self._recorded_identity(identity)
            if repeat is None:
                raise
            return AbsorbedProposal(
                holder=self._reread(holder.pipeline_instance_id), absorbed_ref=proposal_ref,
                event_id=repeat, idempotency_identity=identity, already_absorbed=True,
            )
        except BaseException:
            self._conn.rollback()
            raise
        return AbsorbedProposal(
            holder=self._reread(holder.pipeline_instance_id), absorbed_ref=proposal_ref,
            event_id=envelope.event_id, idempotency_identity=identity, already_absorbed=False,
        )

    # --- PL-2 … PL-15 -----------------------------------------------------------------------------

    def apply(
        self,
        pipeline_instance_id: str,
        trigger: Trigger,
        *,
        actor_type: str,
        actor_id: str,
        expected_version: int | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
        **facts: Any,
    ) -> TransitionResult:
        """ONE transition, in ONE commit: the state row and whatever it emits, or neither.

        PL-8 and PL-9 additionally carry the checkpoint kernel's own writes into that same commit —
        see `_checkpoint_locked` and `_claim_locked`. Everything else is the ordinary path.
        """
        self._require_actor(actor_type)
        item = self.require(pipeline_instance_id)
        if expected_version is not None and expected_version != item.version:
            raise VersionConflict(
                f"expected_version {expected_version} but {pipeline_instance_id!r} is at version "
                f"{item.version}: somebody else transitioned it first. Reload and retry (GR-3) — a "
                f"lost update here is a transition that silently did not happen."
            )
        parsed = _Facts(**_split_facts(facts))
        # ### LEGALITY IS DECIDED BEFORE ANY TRANSACTION IS OPENED, and that ordering is what lets
        # PL-8/PL-9 hand the transaction to the kernel. An illegal trigger must never reach the
        # kernel at all: running seven checks to discover that a CLOSED attempt cannot be
        # checkpointed would be a refusal that costs a live authoritative read.
        if not legal_transitions(item.state, trigger):
            self._record_illegal(
                item, trigger, actor_type=actor_type, actor_id=actor_id,
                correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                attempt_id=event_id or str(uuid.uuid4()), event_id=event_id,
            )
            raise IllegalTransition(
                f"{trigger.value} is not legal for a Pipeline Instance in {item.state.value} "
                f"(GR-1, [C-4]). No state change was persisted; `IllegalTransitionAttempted` is "
                f"recorded to the audit backbone AND to `security_events`, atomically with each "
                f"other, in a commit of their own."
            )
        # ### THE KERNEL DISPATCH IS DERIVED FROM THE SAME DECLARATION THAT REFUSES THE ORDINARY
        # PATH, so the two can never disagree. A trigger routed here can never also be executed by
        # `_apply_locked`, and a consequential row declared without an executor FAILS CLOSED — it
        # does not fall through to the ordinary path, which is how one would silently acquire an
        # unguarded route.
        path = KERNEL_PATH_BY_TRIGGER.get(trigger)
        if path is not None:
            entry = KERNEL_ENTRY_POINTS.get(path)
            if entry is None:
                raise AuthorityRefused(
                    f"{trigger.value} drives a consequential transition whose kernel path "
                    f"{path!r} has no executor on this machine. §15 makes the resulting state "
                    f"unreachable without the kernel, so this refuses rather than falling through "
                    f"to the ordinary guard path."
                )
            return getattr(self, entry)(
                item, actor_type=actor_type, actor_id=actor_id, correlation_id=correlation_id,
                causation_id=causation_id, trace_id=trace_id, event_id=event_id, facts=parsed,
            )

        self._conn.execute("BEGIN IMMEDIATE")
        try:
            result = self._apply_locked(
                item, trigger, actor_type=actor_type, actor_id=actor_id,
                correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                event_id=event_id, facts=parsed,
            )
            self._conn.commit()
        except BaseException:
            self._conn.rollback()
            raise
        return result

    def _apply_locked(
        self,
        item: PipelineInstance,
        trigger: Trigger,
        *,
        actor_type: str,
        actor_id: str,
        correlation_id: str | None,
        causation_id: str | None,
        trace_id: str | None,
        event_id: str | None,
        facts: _Facts,
    ) -> TransitionResult:
        """The transition itself. Requires a transaction to be open; never opens or commits one.

        Separated from `apply` so the SAME body serves a consumed trigger, where `DedupInbox` owns
        the transaction (M-24) and the handler must not begin, commit or roll back. Two copies of a
        transition body is how one of them quietly stops emitting an event.
        """
        candidates = legal_transitions(item.state, trigger)
        if not candidates:
            raise IllegalTransition(
                f"{trigger.value} is not legal for a Pipeline Instance in {item.state.value} "
                f"(GR-1, [C-4])."
            )
        surviving: list[TransitionRow] = []
        refusals: list[str] = []
        for row in candidates:
            problem = self._guard_problem(row, item, trigger, facts, actor_type, actor_id)
            if problem is None:
                surviving.append(row)
            else:
                refusals.append(f"{row.id}: {problem}")
        if not surviving:
            # ### A REFUSAL BECAUSE EVERY CANDIDATE IS KERNEL-OWNED IS §15 ILLEGALITY, NOT AN
            # ORDINARY UNSATISFIED GUARD, AND THE DIFFERENCE IS DURABLE. GR-1's record —
            # `IllegalTransitionAttempted` to the audit backbone AND `security_events` — is what an
            # operator sees when something tried to reach `CLAIMED` without a CAS. Classifying it as
            # a guard failure would leave that attempt with no security record at all, which is the
            # quiet half of the same defect. The classification is DERIVED from the candidate set,
            # so it cannot drift from the refusal that produced it.
            if all(row.id in KERNEL_OWNED_ROW_IDS for row in candidates):
                raise IllegalTransition(
                    f"{trigger.value} in {item.state.value} selects only kernel-owned rows "
                    f"({', '.join(row.id for row in candidates)}), and this is not the kernel path. "
                    f"§15: `GRANTED` without a `CheckpointPassed` witness and `CLAIMED` without a "
                    f"successful CAS are IMPOSSIBLE, so the row is refused here rather than "
                    f"executed with the kernel's own writes missing. No state change was persisted; "
                    f"`IllegalTransitionAttempted` records the attempt. Drive it through "
                    f"`apply({trigger.value})`, which routes to the kernel."
                )
            raise GuardNotSatisfied(
                f"{trigger.value} is legal for {item.state.value} but no guard is satisfied. "
                + " · ".join(refusals)
            )
        if len(surviving) > 1:
            surviving.sort(key=lambda r: PRECEDENCE.index(r.id))
        row = surviving[0]
        result = self._commit_transition_locked(
            row, item, trigger, actor_type=actor_type, actor_id=actor_id,
            correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
            event_id=event_id, facts=facts,
        )
        # ### PL-12 IS NOT A SEPARATE STEP: §14 says "SAME commit as verify", and acceptance item
        # (f) is that verify and record are one commit. It is applied here, inside the same open
        # transaction, and it is looked up by the DECLARED co-commit rather than by an `if
        # row.id == "PL-11"` — so a §14 change that moves the co-commit moves this too.
        follower = next(
            (r for r in TRANSITIONS if r.co_commits_with == row.id), None)
        if follower is not None:
            second = self._commit_transition_locked(
                follower, result.pipeline, trigger, actor_type=actor_type, actor_id=actor_id,
                correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                event_id=None, facts=facts,
            )
            return TransitionResult(
                transition_id=result.transition_id, pipeline=second.pipeline,
                from_state=result.from_state, to_state=result.to_state,
                event_id=result.event_id, event_name=result.event_name, co_commits=(second,),
            )
        return result

    # --- PL-8: the checkpoint ---------------------------------------------------------------------

    def _run_checkpoint(
        self,
        item: PipelineInstance,
        *,
        actor_type: str,
        actor_id: str,
        correlation_id: str | None,
        causation_id: str | None,
        trace_id: str | None,
        event_id: str | None,
        facts: _Facts,
    ) -> TransitionResult:
        """PL-8, or PL-8f — ### ONE TRANSACTION CARRIES THE SEVEN CHECKS, THE WITNESS, THE GRANT AND
        THIS ROW.

        §4: *"the `CHECKPOINT→GRANTED` transition co-commits the Checkpoint Witness insert + the
        grant mint (M3) in ONE transaction"*. §35: *"no async work between PL-8 and PL-9."* So this
        does not call `run_checkpoint` and then write — it opens the transaction, hands it to
        `run_checkpoint_locked`, and puts the pipeline's own UPDATE and its `CheckpointPassed`
        emission inside it. There is no interval in which a witness and a grant exist for an attempt
        that is not GRANTED.

        ### THE REQUEST IS BUILT FROM THE ROW, NOT FROM THE CALLER. The effect, and therefore the
        commit key, come from `item.effect`; the accountable owner comes from the row. A caller who
        could vary either between the proposal and the checkpoint could have one attempt authorize a
        different effect than the one that was validated.

        On refusal the transaction is abandoned FIRST and PL-8f is written in a commit of its own —
        the same ordering M1's `IllegalTransitionAttempted` path uses, and for the same reason: the
        record of a refusal must not be inside the transaction the refusal abandons.
        """
        kernel = facts.kernel
        inputs = facts.checkpoint_inputs
        if kernel is None or not isinstance(inputs, CheckpointInputs):
            raise GuardNotSatisfied(
                "PL-8 requires the checkpoint kernel and its typed `CheckpointInputs`. This machine "
                "does not construct either: the seven checks are P3's, the gate registry is the "
                "kernel's, and a Pipeline Instance that built its own would be a second effect "
                "authority (CLAUDE.md rule 17)."
            )
        request = CheckpointRequest(
            effect=item.effect, actor=actor_id, accountable_owner=item.owner_id,
            target_entity_ref=item.target_resource_id,
        )
        now = format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            outcome = run_checkpoint_locked(kernel, request, inputs, now=self._clock())
            if isinstance(outcome, CheckpointAuthorized):
                result = self._commit_checkpoint_pass_locked(
                    item, outcome, actor_type=actor_type, actor_id=actor_id,
                    correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                    event_id=event_id, now=now,
                )
                conn.commit()
            else:
                conn.rollback()
                result = None
        except BaseException:
            conn.rollback()
            raise
        if result is not None:
            kernel.observe({
                "kind": "CheckpointPassed", "tenant": self._tenant,
                "checkpoint_id": result.pipeline.checkpoint_id,
                "grant_id": result.pipeline.grant_id, "commit_key": item.commit_key,
            })
            return result

        assert isinstance(outcome, CheckpointRefused)
        # The kernel's own Sev-0/observability record, written after the rollback so it survives it.
        record_checkpoint_refusal(kernel, request, outcome)
        return self._commit_checkpoint_failure(
            item, outcome, actor_type=actor_type, actor_id=actor_id,
            correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
        )

    def _commit_checkpoint_pass_locked(
        self,
        item: PipelineInstance,
        authorized: CheckpointAuthorized,
        *,
        actor_type: str,
        actor_id: str,
        correlation_id: str | None,
        causation_id: str | None,
        trace_id: str | None,
        event_id: str | None,
        now: str,
    ) -> TransitionResult:
        witness = authorized.witness
        new_version = item.version + 1
        cursor = self._conn.execute(
            """
            UPDATE pipeline_instances
               SET state = 'GRANTED', version = ?, updated_at = ?, checkpoint_id = ?, grant_id = ?,
                   material_facts_fingerprint = ?, approval_id = ?, policy_version = ?,
                   gate_decision = ?
             WHERE tenant = ? AND pipeline_instance_id = ? AND version = ? AND state = ?
            """,
            (new_version, now, witness.checkpoint_id, witness.grant_id,
             witness.material_facts_fingerprint, witness.approval_id, witness.policy_version,
             witness.gate_decision.value, self._tenant, item.pipeline_instance_id, item.version,
             item.state.value),
        )
        if cursor.rowcount != 1:
            raise VersionConflict(
                f"{item.pipeline_instance_id!r} moved under PL-8: the UPDATE matched "
                f"{cursor.rowcount} rows at version {item.version}/state {item.state.value}. The "
                f"witness and the grant minted in this transaction are rolled back with it, which "
                f"is the point of them sharing it."
            )
        envelope = self._envelope(
            event_name="CheckpointPassed", transition_id="PL-8",
            pipeline_instance_id=item.pipeline_instance_id, work_item_id=item.work_item_id,
            aggregate_version=new_version, owner_id=item.owner_id, actor_type=actor_type,
            actor_id=actor_id,
            payload=_prune({
                "checkpoint_id": witness.checkpoint_id,
                "material_facts_fingerprint": witness.material_facts_fingerprint,
                "entity_versions": dict(witness.entity_versions),
                "policy_version": witness.policy_version,
                "brake_version": witness.brake_version,
                "projected_observations_used": list(witness.projected_observations_used),
                "native_claims_used": list(witness.native_claims_used),
                "approval_id": witness.approval_id,
            }),
            correlation_id=correlation_id or item.work_item_id, causation_id=causation_id,
            trace_id=trace_id, event_id=event_id, now=now,
            # ER-13: `CheckpointPassed` is CONSEQUENTIAL (`events/registry.md` §5), so the envelope
            # pins the decision context — and it pins the WITNESS's copy of it, not a re-read. An
            # audit that reconstructed the pins from today's state could not say why the effect was
            # allowed THEN, which is the difference between a log and evidence.
            entity_versions=dict(witness.entity_versions),
            policy_version=witness.policy_version, brake_version=witness.brake_version,
            material_facts_fingerprint=witness.material_facts_fingerprint,
        )
        TransactionalOutbox(self._conn, tenant=self._tenant, clock=self._clock).emit(envelope)
        return TransitionResult(
            transition_id="PL-8", pipeline=self._reread(item.pipeline_instance_id),
            from_state=item.state, to_state=PipelineState.GRANTED,
            event_id=envelope.event_id, event_name="CheckpointPassed",
            grant_handle=authorized.handle,
        )

    def _commit_checkpoint_failure(
        self,
        item: PipelineInstance,
        refused: CheckpointRefused,
        *,
        actor_type: str,
        actor_id: str,
        correlation_id: str | None,
        causation_id: str | None,
        trace_id: str | None,
    ) -> TransitionResult:
        """PL-8f. `CHECKPOINT → VOIDED`, with the FIRST failing step named (SD-7).

        ### §14's EVENT CELL READS `CheckpointFailed{step,reason}` + `PipelineVoided`, AND ONLY THE
        FIRST IS EMITTED HERE. `events/registry.md` §3 attributes `PipelineVoided` to **PL-7v/PL-9v**
        and to nothing else, and the contract gate enforces that attribution — an envelope naming
        PL-8f as its producer is refused, correctly, because the registry is what the G2 adjudication
        settled as authoritative for producer attribution. Emitting it anyway would mean this machine
        deciding a canonical producer set, which is not its authority.

        The state still becomes VOIDED, so nothing about the machine's behaviour is weakened; what
        is missing is a second event that would duplicate the first one's fact. Recorded as debt
        P6-D9 with both texts, so the disagreement is visible rather than resolved by whoever reads
        it next.
        """
        now = format_instant(self._clock())
        new_version = item.version + 1
        reason = f"{refused.reason}: {refused.detail}"
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            cursor = self._conn.execute(
                """
                UPDATE pipeline_instances
                   SET state = 'VOIDED', version = ?, updated_at = ?, reason = ?, refused_step = ?
                 WHERE tenant = ? AND pipeline_instance_id = ? AND version = ? AND state = ?
                """,
                (new_version, now, reason,
                 refused.step if 1 <= refused.step <= 7 else None,
                 self._tenant, item.pipeline_instance_id, item.version, item.state.value),
            )
            if cursor.rowcount != 1:
                raise VersionConflict(
                    f"{item.pipeline_instance_id!r} moved under PL-8f: the UPDATE matched "
                    f"{cursor.rowcount} rows at version {item.version}."
                )
            envelope = self._envelope(
                event_name="CheckpointFailed", transition_id="PL-8f",
                pipeline_instance_id=item.pipeline_instance_id, work_item_id=item.work_item_id,
                aggregate_version=new_version, owner_id=item.owner_id, actor_type=actor_type,
                actor_id=actor_id,
                payload={"step": refused.step_name, "reason": reason},
                correlation_id=correlation_id or item.work_item_id, causation_id=causation_id,
                trace_id=trace_id, event_id=None, now=now,
            )
            TransactionalOutbox(self._conn, tenant=self._tenant, clock=self._clock).emit(envelope)
            self._conn.commit()
        except BaseException:
            self._conn.rollback()
            raise
        return TransitionResult(
            transition_id="PL-8f", pipeline=self._reread(item.pipeline_instance_id),
            from_state=item.state, to_state=PipelineState.VOIDED,
            event_id=envelope.event_id, event_name="CheckpointFailed",
        )

    # --- PL-9: the claim ---------------------------------------------------------------------------

    def _run_claim(
        self,
        item: PipelineInstance,
        *,
        actor_type: str,
        actor_id: str,
        facts: _Facts,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """PL-9 — ### THE CAS AND THIS ROW MOVE IN ONE TRANSACTION, WHICH IS WHAT §30 BUYS.

        The four envelope identifiers are accepted so every kernel entry point has ONE signature and
        `apply` can dispatch from the declared path rather than from a hand-written `if` per
        trigger. They are unused HERE, and the reason is the docstring's third paragraph: PL-9 is a
        `CONSUMES` row that emits nothing, so there is no envelope for them to ride on.

        *"A brake engaged between PL-8 and PL-9 makes the CAS match zero rows — the adapter does
        nothing (never both, never neither)."* The CAS is the serialization point (§17) and it is
        P3's, called through its locked entry point so the pipeline's own `GRANTED → CLAIMED` is in
        the commit that wins it.

        ### THIS MACHINE EMITS NOTHING HERE, AND THAT IS THE CANONICAL ANSWER, NOT AN OMISSION.
        `GrantClaimed` and `EffectAttempted` are EF-2's — M3's — and §14 marks PL-9 `CONSUMES`. The
        contract gate would refuse an envelope naming PL-9 as their producer. The state change is
        real, durable and version-monotonic; the events arrive with M3.

        ### A REFUSED CLAIM IS A GUARD FAILURE, NOT A TRANSITION. §14 has no row for it: the attempt
        stays GRANTED and is voided by PL-9v when the grant expires or is revoked. So nothing is
        persisted and nothing is emitted — the honest reading of "the adapter does nothing".
        """
        kernel = facts.kernel
        handle = facts.handle
        if kernel is None or not isinstance(handle, EffectGrantHandle):
            raise GuardNotSatisfied(
                "PL-9 requires the checkpoint kernel and the signed grant handle PL-8 produced. The "
                "claim CAS is the single serialization point of the effect (§17) and it belongs to "
                "the kernel; a Pipeline Instance that claimed by writing its own UPDATE would be "
                "the second effect authority CLAUDE.md rule 17 forbids."
            )
        if item.grant_id and handle.grant_id != item.grant_id:
            raise GuardNotSatisfied(
                f"PL-9 was handed grant {handle.grant_id!r}; this attempt was granted "
                f"{item.grant_id!r} at PL-8. Claiming a grant this attempt does not hold is the "
                f"confused-deputy shape the CAS refuses at step 4 — refused here first, so no "
                f"ledger read is spent on it."
            )
        params = ClaimParams(
            tenant=self._tenant, action_class=item.action_class,
            target_system=item.target_system, target_resource_id=item.target_resource_id,
            target_operation=item.target_operation,
        )
        now = format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            pending = claim_grant_cas_locked(kernel, handle, params, now=self._clock())
            if pending.outcome.claimed:
                cursor = conn.execute(
                    """
                    UPDATE pipeline_instances
                       SET state = 'CLAIMED', version = ?, updated_at = ?, claimed_at = ?
                     WHERE tenant = ? AND pipeline_instance_id = ? AND version = ? AND state = ?
                    """,
                    (item.version + 1, now, now, self._tenant, item.pipeline_instance_id,
                     item.version, item.state.value),
                )
                if cursor.rowcount != 1:
                    raise VersionConflict(
                        f"{item.pipeline_instance_id!r} moved under PL-9: the UPDATE matched "
                        f"{cursor.rowcount} rows at version {item.version}. The CAS in this "
                        f"transaction is rolled back with it — never both, never neither."
                    )
                conn.commit()
            else:
                conn.rollback()
        except BaseException:
            conn.rollback()
            raise
        outcome = flush_claim_records(kernel, pending)
        if not outcome.claimed:
            raise GuardNotSatisfied(
                f"PL-9's guard is that the atomic GRANTED→CLAIMED CAS succeeds, and it matched zero "
                f"rows: {outcome.cause}. The attempt stays GRANTED and nothing was attempted "
                f"externally. §30: the adapter does nothing — never both, never neither."
            )
        return TransitionResult(
            transition_id="PL-9", pipeline=self._reread(item.pipeline_instance_id),
            from_state=item.state, to_state=PipelineState.CLAIMED,
        )

    # --- consumed triggers --------------------------------------------------------------------------

    def reference_resolver(self, aggregate_type: str, aggregate_id: str) -> bool:
        """Does this aggregate exist yet, FOR THIS TENANT? M-26's question, tenant-scoped.

        Only `pipeline_instance` is answerable here — this machine owns one aggregate. An unknown
        aggregate TYPE resolves **False** rather than True: "we cannot confirm this exists" must
        park. Answering True would let an event referencing a machine nobody has built be applied as
        though its referent were fine, which is the optimistic direction and the wrong one.
        """
        if aggregate_type != AGGREGATE_TYPE:
            return False
        return self._conn.execute(
            "SELECT 1 FROM pipeline_instances WHERE tenant = ? AND pipeline_instance_id = ?",
            (self._tenant, aggregate_id),
        ).fetchone() is not None

    def consume(
        self,
        envelope: EventEnvelope,
        *,
        pipeline_instance_id: str,
        trigger: Trigger,
        inbox: DedupInbox | None = None,
        accountable_owner_id: str | None = None,
        **facts: Any,
    ) -> ConsumedTransition:
        """Drive ONE transition from a canonical event, idempotently, through P5's dedup inbox.

        ### THE IDEMPOTENCY IS NOT REIMPLEMENTED HERE. GR-4's mechanism is
        `(tenant, consumer_id, event_id)` in `event_inbox`, and `DedupInbox.consume` already owns the
        one commit that carries both the handler's writes and the inbox row (M-24). A redelivered
        `EffectExecuted` is a no-op because the inbox says so, not because this machine remembered.

        ### AN EVENT FOR AN ATTEMPT THAT DOES NOT EXIST YET IS PARKED, NOT LOOPED (M-26), AND IT
        PARKS ON A NAMED HUMAN. M1 shipped both halves of this defect and had them found in
        independent review: without the explicit prerequisite the inbox skipped the check and the
        handler raised inside the inbox's transaction, rolling back the receipt and redelivering
        forever; and a park could be written with a NULL accountable owner, which is rule 13's one
        exception created by the method whose contract promises otherwise. Both are answered here by
        construction rather than rediscovered.

        ### A REFUSAL IS A CONSUMPTION, NOT A DELIVERY FAILURE. If the handler raised on a refusal,
        the inbox would roll back its own row and the transport would redeliver forever — an
        unsatisfiable guard would become an infinite loop. So both refusals are OUTCOMES:

            guard unsatisfied ⇒ no state change, NO event. The ordinary case.
            illegal trigger   ⇒ no state change, `IllegalTransitionAttempted` recorded INSIDE the
                                inbox commit — here the record and the consumption genuinely are one
                                act, so they are one commit.
        """
        box = inbox or DedupInbox(
            self._conn, tenant=self._tenant, consumer_id=CONSUMER_ID, clock=self._clock,
            reference_resolver=self.reference_resolver,
        )
        owner = (
            self._accountable_owner_for(box, envelope, pipeline_instance_id, accountable_owner_id)
            if pipeline_must_exist(trigger) else accountable_owner_id
        )
        parsed = _Facts(**_split_facts(facts))
        outcome: dict[str, Any] = {"transition": None, "refusal": None, "refusal_kind": None,
                                   "illegal_record": None}

        def handler(event: EventEnvelope) -> None:
            item = self.get(pipeline_instance_id)
            if item is None:
                # Only a creation/absorption trigger can reach this, because every other one named
                # the attempt in `requires_existing` and the inbox held it under M-26. PL-1 is
                # originated through `propose()`, never consumed, so there is no transition to
                # attempt — refused as an OUTCOME, not raised, because raising is what rolled the
                # receipt back and looped the event forever. And it is NOT recorded as an illegal
                # attempt: `IllegalTransitionAttempted` must name the attempt's state and version
                # (GR-1, [C-4]) and there is no attempt to name. A fabricated security record is
                # worse than none.
                outcome["refusal"], outcome["refusal_kind"] = (
                    f"{trigger.value} does not transition a Pipeline Instance — PL-1 CREATES one "
                    f"and a creation is originated through propose(), never consumed. There is no "
                    f"{pipeline_instance_id!r} to move and this event does not make one. Consumed "
                    f"once, nothing persisted, nothing emitted.",
                    "NOT_CONSUMABLE",
                )
                return
            try:
                outcome["transition"] = self._apply_locked(
                    item, trigger, actor_type=event.actor_type, actor_id=event.actor_id,
                    correlation_id=event.correlation_id, causation_id=event.event_id,
                    trace_id=event.trace_id, event_id=None, facts=parsed,
                )
            except IllegalTransition as exc:
                record = self._record_illegal_locked(
                    item, trigger, actor_type=event.actor_type, actor_id=event.actor_id,
                    correlation_id=event.correlation_id, causation_id=event.event_id,
                    trace_id=event.trace_id, attempt_id=event.event_id,
                )
                outcome["refusal"], outcome["refusal_kind"] = str(exc), "ILLEGAL"
                outcome["illegal_record"] = record
            except GuardNotSatisfied as exc:
                outcome["refusal"], outcome["refusal_kind"] = str(exc), "GUARD"

        result = box.consume(
            envelope, handler,
            requires=((AGGREGATE_TYPE, pipeline_instance_id),),
            requires_existing=(
                ((AGGREGATE_TYPE, pipeline_instance_id),) if pipeline_must_exist(trigger) else ()
            ),
            accountable_owner_id=owner,
        )
        return ConsumedTransition(
            consume=result, transition=outcome["transition"], refusal=outcome["refusal"],
            refusal_kind=outcome["refusal_kind"], illegal_record=outcome["illegal_record"],
        )

    def _accountable_owner_for(
        self,
        box: DedupInbox,
        envelope: EventEnvelope,
        pipeline_instance_id: str,
        accountable_owner_id: str | None,
    ) -> str | None:
        """The human this consumption would park work on — resolved, or the call refuses.

        The same four-step ladder M1 established, over this machine's own authoritative state:
        the caller's explicit owner (checked against the recorded roster), the attempt's own owner,
        the park this event is already held in, and the envelope's own `accountable_owner_id`. There
        is no fifth branch: no `system`, no `ops`, no `unassigned`. Every one of those is an owner
        nobody agreed to be, and M-26's expiry with no name is the silent drop it exists to forbid.
        """
        m1 = WorkItemMachine(self._conn, tenant=self._tenant, clock=self._clock)
        if str(accountable_owner_id or "").strip():
            return self._require_active_human(m1, accountable_owner_id)
        item = self.get(pipeline_instance_id)
        if item is not None:
            return item.owner_id
        held = next((p for p in box.parked() if p.event_id == envelope.event_id), None)
        if held is not None:
            return held.accountable_owner_id
        if str(envelope.accountable_owner_id or "").strip():
            return self._require_active_human(m1, envelope.accountable_owner_id)
        raise OwnershipRefused(
            f"{envelope.event_name} references Pipeline Instance {pipeline_instance_id!r}, which "
            f"does not exist for tenant {self._tenant!r}, and names no accountable human — not on "
            f"the call, not on the envelope. Consuming it would park an obligation under M-26 with "
            f"NO accountable owner, and every open obligation has exactly one (CLAUDE.md rule 13). "
            f"Refused with nothing written: supply `accountable_owner_id`, or propose the attempt "
            f"first."
        )

    # --- the write ----------------------------------------------------------------------------------

    def _commit_transition_locked(
        self,
        row: TransitionRow,
        item: PipelineInstance,
        trigger: Trigger,
        *,
        actor_type: str,
        actor_id: str,
        correlation_id: str | None,
        causation_id: str | None,
        trace_id: str | None,
        event_id: str | None,
        facts: _Facts,
    ) -> TransitionResult:
        to_state = self._resolve_target(row, facts)
        now = format_instant(self._clock())
        new_version = item.version + 1

        sets = ["state = ?", "version = ?", "updated_at = ?"]
        params: list[Any] = [to_state.value, new_version, now]
        for column, value in self._columns_written(row, item, facts).items():
            sets.append(f"{column} = ?")
            params.append(value)

        # ### THE OCC WRITE. `WHERE version = :expected` is GR-3, and zero rows is a lost update
        # rather than a no-op. The `state = ?` predicate travels with it, so a concurrent transition
        # that moved the state without moving the version could not slip past either — a revalidating
        # WHERE clause never loses a predicate (the P3 claim-CAS rule, kept).
        cursor = self._conn.execute(
            f"UPDATE pipeline_instances SET {', '.join(sets)} "
            f" WHERE tenant = ? AND pipeline_instance_id = ? AND version = ? AND state = ?",
            (*params, self._tenant, item.pipeline_instance_id, item.version, item.state.value),
        )
        if cursor.rowcount != 1:
            raise VersionConflict(
                f"{item.pipeline_instance_id!r} moved under {row.id}: the UPDATE matched "
                f"{cursor.rowcount} rows at version {item.version}/state {item.state.value}. "
                f"Reload and retry (GR-3)."
            )
        event_uuid: str | None = None
        if row.kind is RowKind.PRODUCER and row.event_name and not row.emits_on_foreign_aggregate:
            envelope = self._envelope(
                event_name=row.event_name, transition_id=row.id,
                pipeline_instance_id=item.pipeline_instance_id, work_item_id=item.work_item_id,
                aggregate_version=new_version, owner_id=item.owner_id, actor_type=actor_type,
                actor_id=actor_id, payload=self._payload(row, item, facts),
                correlation_id=correlation_id or item.work_item_id, causation_id=causation_id,
                trace_id=trace_id, event_id=event_id, now=now,
            )
            TransactionalOutbox(self._conn, tenant=self._tenant, clock=self._clock).emit(envelope)
            event_uuid = envelope.event_id
        del trigger
        return TransitionResult(
            transition_id=row.id, pipeline=self._reread(item.pipeline_instance_id),
            from_state=item.state, to_state=to_state, event_id=event_uuid,
            event_name=(row.event_name
                        if row.kind is RowKind.PRODUCER and event_uuid is not None else None),
        )

    def _resolve_target(self, row: TransitionRow, facts: _Facts) -> PipelineState:
        """PL-15 reaches VERIFIED or FAILED, and the establishing event decides — never the caller.

        §14: *"`HumanEstablishedReality{decision_ref}` **or** `LaterObservationProves`
        (deterministic, our commit_key)"*, resolving to `{VERIFIED, FAILED}`. `RealityEstablished`
        carries `outcome`, so the answer is on the canonical event rather than in an argument
        somebody could get backwards.
        """
        if row.alternate_to_state is None:
            assert row.to_state is not None
            return row.to_state
        stated = str(facts.outcome or "").strip().upper()
        for candidate in (row.to_state, row.alternate_to_state):
            if candidate is not None and stated == candidate.value:
                return candidate
        raise GuardNotSatisfied(
            f"{row.id} reaches {row.to_state.value if row.to_state else '?'} or "
            f"{row.alternate_to_state.value}, decided by the establishing event's own `outcome`; it "
            f"says {facts.outcome!r}. GR-6: an UNKNOWN OUTCOME never silently becomes success or "
            f"failure, so an unreadable outcome resolves to neither."
        )

    def _columns_written(
        self, row: TransitionRow, item: PipelineInstance, facts: _Facts,
    ) -> dict[str, Any]:
        """§14's Writes cell, per row, as data the UPDATE consumes."""
        if row.id == "PL-2":
            return {"policy_version": facts.policy_version,
                    "gate_decision": _gate_value(facts.gate_decision),
                    "gate_reason": facts.reason}
        if row.id == "PL-3":
            return {"reason": facts.reason,
                    "gate_decision": _gate_value(facts.gate_decision) or item.gate_decision,
                    "policy_version": facts.policy_version or item.policy_version}
        if row.id == "PL-5":
            return {"reason": facts.reason}
        if row.id in ("PL-7v", "PL-9v"):
            return {"reason": facts.reason}
        if row.id == "PL-7b":
            return {"approval_id": facts.approval_id,
                    "material_facts_fingerprint": facts.approval_fingerprint}
        if row.id == "PL-10f":
            return {"failure_proof": facts.failure_proof}
        if row.id in ("PL-10u", "PL-11c"):
            return {"unknown_reason": facts.unknown_reason,
                    "unknown_outcome_ref": facts.unknown_outcome_ref}
        if row.id == "PL-11d":
            return {"recheck_at": facts.recheck_at}
        if row.id == "PL-15":
            written: dict[str, Any] = {"decision_ref": facts.decision_ref,
                                       "decision_ref_kind": facts.decision_ref_kind}
            if str(facts.outcome or "").strip().upper() == PipelineState.FAILED.value:
                written["failure_proof"] = facts.failure_proof
            return written
        return {}

    def _payload(
        self, row: TransitionRow, item: PipelineInstance, facts: _Facts,
    ) -> Mapping[str, Any]:
        """The event body §5 declares for this transition's contract.

        ### THE DERIVED FIELDS ARE READ FROM THE ROW, NOT FROM THE CALLER. `commit_key` on
        `PipelineStarted` and `DuplicateProposalAbsorbed` is the row's; a caller-supplied one could
        claim a reservation the attempt does not hold.
        """
        if row.id == "PL-2":
            return {"policy_version": facts.policy_version,
                    "gate_decision": _gate_value(facts.gate_decision),
                    "decision": facts.policy_decision,
                    "rules_matched": list(facts.rules_matched or []),
                    "reason": facts.reason or ""}
        if row.id in ("PL-3", "PL-5"):
            return {"reason": facts.reason}
        if row.id == "PL-4":
            return {}
        if row.id == "PL-7a":
            return {"gate_decision": _gate_value(facts.gate_decision),
                    "caps_evaluated": json.dumps(dict(facts.caps_evaluated or {}), sort_keys=True),
                    "policy_version": facts.policy_version or item.policy_version,
                    "brake_version": facts.brake_version}
        if row.id == "PL-7b":
            return {"approval_id": facts.approval_id,
                    "material_facts_fingerprint": facts.approval_fingerprint}
        if row.id in ("PL-7v", "PL-9v"):
            return {"reason": facts.reason}
        if row.id == "PL-11d":
            return {"recheck_at": facts.recheck_at}
        if row.id == "PL-13":
            return {"entity_ref": facts.entity_ref, "from_effect_id": facts.from_effect_id}
        return {}

    # --- GR-1 ----------------------------------------------------------------------------------------

    def illegal_attempt_identity(self, item: PipelineInstance, attempt_id: str) -> str:
        """The idempotency identity of ONE refused attempt. §4's shape, plus the attempt."""
        text = _require_attempt_id(attempt_id)
        return "|".join((
            ILLEGAL_ATTEMPT_IDENTITY_PREFIX, self._tenant, AGGREGATE_TYPE,
            item.pipeline_instance_id, str(item.version), ILLEGAL_TRANSITION_PRODUCER,
            "IllegalTransitionAttempted", text,
        ))

    def _recorded_identity(self, identity: str) -> str | None:
        row = self._conn.execute(
            "SELECT event_id FROM event_outbox WHERE tenant = ? AND idempotency_identity = ?",
            (self._tenant, identity),
        ).fetchone()
        return None if row is None else row["event_id"]

    def _record_illegal(
        self,
        item: PipelineInstance,
        trigger: Trigger,
        *,
        actor_type: str,
        actor_id: str,
        correlation_id: str | None,
        causation_id: str | None,
        trace_id: str | None,
        attempt_id: str,
        event_id: str | None,
    ) -> IllegalAttemptRecord:
        """GR-1 on the direct API: the refusal persists nothing and its RECORD gets its own commit."""
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            record = self._record_illegal_locked(
                item, trigger, actor_type=actor_type, actor_id=actor_id,
                correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                attempt_id=attempt_id, event_id=event_id,
            )
            self._conn.commit()
        except BaseException:
            self._conn.rollback()
            raise
        return record

    def _record_illegal_locked(
        self,
        item: PipelineInstance,
        trigger: Trigger,
        *,
        actor_type: str,
        actor_id: str,
        correlation_id: str | None,
        causation_id: str | None,
        trace_id: str | None,
        attempt_id: str,
        event_id: str | None = None,
    ) -> IllegalAttemptRecord:
        """`IllegalTransitionAttempted` — into the audit backbone AND `security_events`, ONE commit.

        ### BOTH, ATOMICALLY, BECAUSE [C-4] SAYS BOTH, AND THE ALREADY-RECORDED CASE IS DECIDED
        RATHER THAN DISCOVERED BY EXCEPTION. On a consumed trigger this runs inside the inbox's one
        transaction (M-24), so anything it raises rolls the receipt back and the event redelivers
        forever. M1's first candidate was rejected in independent review for exactly that: a
        `DuplicateEmission` escaping here was not a loud failure but an infinite loop recording
        nothing on any pass. The identity is looked up under the write lock this is always called
        with, and a second attempt at recording ONE attempt writes nothing and says so.
        """
        now = format_instant(self._clock())
        identity = self.illegal_attempt_identity(item, attempt_id)
        already = self._recorded_identity(identity)
        if already is not None:
            return IllegalAttemptRecord(
                event_id=already, idempotency_identity=identity, already_recorded=True)
        envelope = self._envelope(
            event_name="IllegalTransitionAttempted", transition_id=ILLEGAL_TRANSITION_PRODUCER,
            pipeline_instance_id=item.pipeline_instance_id, work_item_id=item.work_item_id,
            aggregate_version=item.version, owner_id=item.owner_id, actor_type=actor_type,
            actor_id=actor_id,
            payload={"machine": "M2", "state": item.state.value, "trigger": trigger.value,
                     "attempted_by": actor_id},
            correlation_id=correlation_id or item.work_item_id, causation_id=causation_id,
            trace_id=trace_id, event_id=event_id, now=now, idempotency_identity=identity,
        )
        try:
            TransactionalOutbox(self._conn, tenant=self._tenant, clock=self._clock).emit(envelope)
        except DuplicateEmission as exc:
            repeat = self._recorded_identity(identity)
            if repeat is None:
                raise PipelineError(
                    f"the refusal of {trigger.value} on {item.pipeline_instance_id!r} could not be "
                    f"recorded: {exc}. The attempt identity {identity!r} is NOT in the outbox, so "
                    f"this is a genuine failure to write the evidence and not the same attempt "
                    f"arriving twice. Reported as a refusal of this machine — an operator must not "
                    f"be told the attempt was recorded when it was not."
                ) from exc
            return IllegalAttemptRecord(
                event_id=repeat, idempotency_identity=identity, already_recorded=True)
        next_id = int(self._conn.execute(
            "SELECT COALESCE(MAX(id), 0) + 1 FROM security_events WHERE tenant = ?",
            (self._tenant,),
        ).fetchone()[0])
        self._conn.execute(
            "INSERT INTO security_events (tenant, id, event_type, actor, payload_json, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (self._tenant, next_id, "IllegalTransitionAttempted", actor_id,
             json.dumps({"machine": "M2", "pipeline_instance_id": item.pipeline_instance_id,
                         "state": item.state.value, "trigger": trigger.value,
                         "event_id": envelope.event_id, "attempted_by": actor_id,
                         "attempt_id": _require_attempt_id(attempt_id)}, sort_keys=True),
             now),
        )
        return IllegalAttemptRecord(
            event_id=envelope.event_id, idempotency_identity=identity, already_recorded=False)

    # --- guards ---------------------------------------------------------------------------------------

    def _guard_problem(
        self,
        row: TransitionRow,
        item: PipelineInstance,
        trigger: Trigger,
        facts: _Facts,
        actor_type: str,
        actor_id: str,
    ) -> str | None:
        """The EXACT guards of §14, one branch per row. `None` means satisfied.

        ### THIS FUNCTION CAN NEVER SATISFY A KERNEL-OWNED ROW — that is a structural property of
        the function, not a property of its callers. `_apply_locked` is the ordinary path, reached
        from `apply` for administrative triggers and from `consume` for every consumed event; the
        kernel paths (`_run_checkpoint`, `_run_claim`) do not come through here at all. So refusing
        the whole kernel-owned population HERE makes §15's two impossibilities impossible for every
        present and future caller of the ordinary path, rather than for the two call sites somebody
        remembered to check.
        """
        # ### §15, FIRST — BEFORE TRIGGER-TYPE AUTHORITY AND BEFORE EVERY ROW BRANCH.
        # A guard branch that ran first could return `None` and satisfy a row whose real
        # precondition is the kernel's own atomic write. The population is derived from §7's
        # consequential declaration and its (state, trigger) closure, so a new consequential row is
        # refused here the moment it is declared — before anybody writes its guard.
        if row.id in KERNEL_OWNED_ROW_IDS:
            return (
                f"{row.id} is a kernel-owned transition (§7: consequential; §15: the resulting "
                f"state is unreachable without the checkpoint kernel or the claim CAS). The "
                f"ordinary guard path cannot satisfy it at any set of facts — the precondition is "
                f"the kernel's own atomic write, not a value a caller can state. A consumed event "
                f"can never drive it; only `apply` routes this trigger to the kernel."
            )
        # Trigger-type authority, before any row-specific guard. An `H` transition is an
        # authenticated human action (registry §1). PL-7b is the one H-only row on this machine, and
        # it is the moment a human's authority enters the effect path.
        if "H" in row.trigger_types and len(row.trigger_types) == 1:
            if actor_type != "human":
                return (
                    f"{row.id} is an H transition (authenticated human action) and the actor is "
                    f"actor_type={actor_type!r}. Automation may narrow authority and never broaden "
                    f"it (§7)."
                )
            m1 = WorkItemMachine(self._conn, tenant=self._tenant, clock=self._clock)
            try:
                self._require_active_human(m1, actor_id)
            except OwnershipRefused as exc:
                return str(exc)

        if row.id == "PL-2":
            gate = _gate_value(facts.gate_decision)
            if not gate:
                return (
                    "PL-2 requires `gate_decision` NOT NULL (GR-8, F-20). A gate expressible as an "
                    "absence is not a gate: the system fails closed rather than advancing an intent "
                    "nobody classified."
                )
            if not (facts.policy_version or "").strip():
                return "PL-2 records WHICH policy decided; a decision with no version is unreplayable"
            if facts.model_inferred_material_fact is not False:
                return (
                    "PL-2 requires `model_inferred_material_fact=False` to be STATED. GR-8: a "
                    "MODEL_INFERRED fact never gates a consequential transition at any confidence, "
                    "and 'we did not check' is not 'there is none'."
                )
            if _is_denied(facts):
                return (
                    "PL-2 is the ADVANCING branch and the policy denied (or the gate is FORBIDDEN). "
                    "That is PL-3 — the pair is total and mutually exclusive so neither precedence "
                    "nor ordering decides which one an intent takes."
                )
            return None
        if row.id == "PL-3":
            if not _is_denied(facts):
                return (
                    "PL-3 requires the policy to DENY, or the gate to be FORBIDDEN. An intent that "
                    "was permitted is not rejected."
                )
            if not (facts.reason or "").strip():
                return "PL-3 writes `reason`: a rejection nobody can read is a rejection nobody can appeal"
            return None
        if row.id == "PL-4":
            for name, value in (("money_fence_passed", facts.money_fence_passed),
                                ("document_fence_passed", facts.document_fence_passed),
                                ("material_fields_consistent", facts.material_fields_consistent)):
                if value is not True:
                    return (
                        f"PL-4 requires `{name}` to be stated TRUE. §14: the money fence and the "
                        f"document fence pass and every material field is `consistent` (GR-10). "
                        f"This machine will not infer a fence it did not run."
                    )
            if facts.open_conflict is not False:
                return (
                    "PL-4 requires `open_conflict=False` to be stated. GR-10: an open Conflict on a "
                    "material field blocks every consequential transition on the affected entity, "
                    "and fails closed."
                )
            if facts.validation_passed is False:
                return "PL-4 is the passing branch; a failed validation is PL-5"
            return None
        if row.id == "PL-5":
            if facts.validation_passed is not False:
                return (
                    "PL-5 requires `validation_passed=False`. The PL-4/PL-5 pair is total and "
                    "mutually exclusive: one of them is taken, never both and never neither."
                )
            if not (facts.reason or "").strip():
                return "PL-5 writes `reason`: a validation failure with no stated cause is unfixable"
            return None
        if row.id == "PL-6":
            gate = _gate_value(facts.gate_decision) or item.gate_decision
            if gate not in {g.value for g in HUMAN_GATES}:
                return (
                    f"PL-6 routes to a human only on {sorted(g.value for g in HUMAN_GATES)}; the "
                    f"gate is {gate!r}. Requesting an approval for an autonomous decision would "
                    f"train an operator to approve things nobody needed them to approve."
                )
            return None
        if row.id == "PL-7a":
            gate = _gate_value(facts.gate_decision) or item.gate_decision
            if gate != GateDecision.AUTONOMOUS_WITHIN_CAPS.value:
                return (
                    f"PL-7a admits autonomously only on "
                    f"{GateDecision.AUTONOMOUS_WITHIN_CAPS.value}; the gate is {gate!r}."
                )
            caps = facts.caps_evaluated
            if not caps:
                return (
                    "PL-7a requires the caps that were EVALUATED. §14: 'and every cap holds' — a "
                    "cap set nobody evaluated is an autonomy grant with no ceiling, and "
                    "`AutonomousAdmissionRecorded` exists so the evaluation is auditable."
                )
            breached = sorted(k for k, v in caps.items() if v is not True)
            if breached:
                return (
                    f"PL-7a requires EVERY cap to hold; these did not: {breached}. A breached cap is "
                    f"a human decision, not a smaller autonomous one."
                )
            if not (facts.brake_version or "").strip():
                return (
                    "PL-7a records the brake version it was admitted under. An autonomous admission "
                    "that cannot say which brake state allowed it cannot be replayed."
                )
            return None
        if row.id == "PL-7b":
            if not (facts.approval_id or "").strip():
                return "PL-7b binds an approval and none was named"
            if facts.approval_commit_key != item.commit_key:
                return (
                    f"PL-7b requires the approval to bind THIS commit key. The approval names "
                    f"{str(facts.approval_commit_key)[:12]}…; this attempt holds "
                    f"{item.commit_key[:12]}…. An approval for one effect authorising another is "
                    f"the confused-deputy shape the checkpoint refuses at step 4 — refused here at "
                    f"the bind, before a witness exists."
                )
            if not (facts.approval_fingerprint or "").strip():
                return (
                    "PL-7b binds the approval's material-facts fingerprint. Without it, drift after "
                    "approval has nothing to be detected against, and F-01 (drift voids) becomes "
                    "unenforceable at step 2."
                )
            return None
        if row.id in ("PL-7v", "PL-9v"):
            if not (facts.reason or "").strip():
                return f"{row.id} writes `reason`: a void with no cause is an attempt that vanished"
            if row.id == "PL-9v" and trigger in (Trigger.GRANT_EXPIRED, Trigger.GRANT_REVOKED):
                if facts.grant_id and item.grant_id and facts.grant_id != item.grant_id:
                    return (
                        f"PL-9v was told grant {facts.grant_id!r} ended; this attempt holds "
                        f"{item.grant_id!r}. One grant expiring does not void another attempt."
                    )
            return None
        if row.id == "PL-10":
            if item.claimed_at is None:
                return (
                    "PL-10 follows a CLAIM. An attempt in CLAIMED with no `claimed_at` did not pass "
                    "through the CAS, and an adapter success against an unclaimed grant is an "
                    "orphan effect, not a transition."
                )
            return None
        if row.id == "PL-10f":
            if not (facts.failure_proof or "").strip():
                return (
                    "PL-10f requires a `failure_proof` — affirmative evidence the effect did NOT "
                    "occur (GR-5, §11). A timeout, a lost response or a crash proves nothing and is "
                    "PL-10u: NEEDS_VERIFICATION, never FAILED. This is the transition whose wrong "
                    "answer pays an invoice twice."
                )
            return None
        if row.id in ("PL-10u", "PL-11c"):
            if not (facts.unknown_reason or "").strip():
                return (
                    f"{row.id} requires `unknown_reason`: §38 makes NEEDS_VERIFICATION a Sev-1 queue "
                    f"carrying 'the specific question', and an unknown outcome with no question is a "
                    f"row nobody can act on."
                )
            return None
        if row.id == "PL-11":
            if not (facts.matched_fingerprint or "").strip():
                return (
                    "PL-11 requires the readback's fingerprint. §14: a healthy-channel readback "
                    "MATCHES the APPROVED fingerprint — 'it looked fine' is not a match."
                )
            approved = item.material_facts_fingerprint
            if not approved:
                return (
                    "PL-11 compares against the fingerprint pinned at the checkpoint, and this "
                    "attempt has none. Verifying against nothing is verifying nothing."
                )
            if facts.matched_fingerprint != approved:
                return (
                    f"PL-11 requires the readback to match the APPROVED fingerprint; it read "
                    f"{facts.matched_fingerprint[:12]}… against {approved[:12]}…. A mismatch is "
                    f"PL-11c (OBSERVATION_CONFLICTING), not a weaker verification."
                )
            if (facts.health_signal or "").strip().upper() not in ("HEALTHY", "OK"):
                return (
                    f"PL-11 requires a HEALTHY channel; the signal is {facts.health_signal!r}. §14 "
                    f"routes an unavailable or blind channel to PL-11c, because a readback we could "
                    f"not trust is not a readback."
                )
            return None
        if row.id == "PL-11d":
            if not (facts.recheck_at or "").strip():
                return (
                    "PL-11d defers verification to a DECLARED bound (a durable timer). A deferral "
                    "with no recheck time is an attempt that stops being looked at."
                )
            if facts.deferral_bound_until and facts.recheck_at > facts.deferral_bound_until:
                return (
                    f"PL-11d defers only WITHIN the declared bound: {facts.recheck_at} is past "
                    f"{facts.deferral_bound_until}. Deferring past the bound is how a verification "
                    f"is postponed forever one step at a time (open validation V6)."
                )
            return None
        if row.id == "PL-13":
            if not (facts.from_effect_id or "").strip():
                return (
                    "PL-13 requires the verified effect the projection is derived from. M-2: a "
                    "projection is updated ONLY from verified evidence, and evidence with no "
                    "identity cannot be checked."
                )
            if facts.from_effect_id != item.grant_id:
                return (
                    f"PL-13 projects from THIS attempt's verified effect. It was handed "
                    f"{facts.from_effect_id!r}; this attempt's effect is {item.grant_id!r}. "
                    f"Projecting one effect's readback onto another's entity is how a projection "
                    f"states something nobody observed."
                )
            if not (facts.entity_ref or "").strip():
                return "PL-13 names the entity it projected onto; an unnamed projection is unauditable"
            return None
        if row.id == "PL-15":
            problem = self._decision_problem(facts)
            if problem is not None:
                return problem
            stated = str(facts.outcome or "").strip().upper()
            if stated == PipelineState.FAILED.value and not (facts.failure_proof or "").strip():
                return (
                    "PL-15 may close an UNKNOWN OUTCOME as FAILED only on affirmative evidence the "
                    "effect did not occur (GR-5). A human saying 'it probably did not go through' "
                    "is the guess this state exists to prevent."
                )
            return None
        # PL-14: no precondition beyond "current state matches" (registry §2's default).
        return None

    def _decision_problem(self, facts: _Facts) -> str | None:
        """GR-14 / K-1, executed through M1's resolver rather than a second implementation."""
        if not (facts.decision_ref or "").strip() or not facts.decision_ref_kind:
            return (
                "PL-15 requires a `decision_ref` AND its kind (GR-14, K-1). GR-6: an UNKNOWN "
                "OUTCOME never silently becomes success or failure, and a reference with no "
                "namespace is a reference that resolves differently tomorrow."
            )
        try:
            resolve_decision_ref(
                self._conn, tenant=self._tenant, ref=facts.decision_ref,
                kind=facts.decision_ref_kind,
            )
        except DecisionRefUnresolvable as exc:
            return str(exc)
        return None

    # --- helpers ---------------------------------------------------------------------------------------

    def _require_actor(self, actor_type: str) -> None:
        if actor_type not in PERMITTED_ACTOR_TYPES:
            raise AuthorityRefused(
                f"actor_type={actor_type!r} may not drive machine M2. Permitted: "
                f"{sorted(PERMITTED_ACTOR_TYPES)}. ### `model` is absent deliberately — C-6, GR-7 "
                f"and §40 give a model exactly one output, an inert `ProposedIntent`. A model may "
                f"propose that an effect is needed; it may never validate, admit, checkpoint, claim, "
                f"verify or close one."
            )

    def _require_work_item_owner(self, work_item_id: str) -> str:
        """§5: the attempt's owner IS the Work Item's owner, read from M1 rather than supplied.

        Taking the owner from the caller would let an attempt be accountable to somebody other than
        the human who owes the work — which is rule 13 satisfied by a column and violated in fact.
        """
        m1 = WorkItemMachine(self._conn, tenant=self._tenant, clock=self._clock)
        item = m1.get(work_item_id)
        if item is None:
            raise OwnershipRefused(
                f"no Work Item {work_item_id!r} for tenant {self._tenant!r}. An attempt exists to "
                f"discharge an obligation; there is no obligation here, so there is nothing to "
                f"attempt and nobody accountable for it."
            )
        if item.state in (WorkItemState.CLOSED, WorkItemState.CANCELLED):
            raise OwnershipRefused(
                f"Work Item {work_item_id!r} is {item.state.value}. Starting a new attempt at work "
                f"that is finished would produce an effect nobody currently owes — reopen it "
                f"(WI-13) if the obligation is live again."
            )
        self._require_active_human(m1, item.owner_id)
        return item.owner_id

    def _require_active_human(self, m1: WorkItemMachine, human_id: str | None) -> str:
        """Ownership comes from the recorded roster, through M1's own reader. Never from a string."""
        from .work_item import human_authority  # local: this is a REUSE of M1's roster reader

        text = str(human_id or "").strip()
        if not text:
            raise OwnershipRefused(
                "an attempt names an accountable human; blank is never one (I1, M-35)."
            )
        found = human_authority(self._conn, tenant=m1.tenant, human_id=text)
        if found is None:
            raise OwnershipRefused(
                f"{text!r} is not a recorded human of tenant {self._tenant!r}. Ownership comes from "
                f"a recorded, attributed authority (`tenant_humans`) — never from a name that "
                f"appeared in a message, an event actor, or a caller argument."
            )
        if not found.is_active:
            raise OwnershipRefused(
                f"{text!r} is {found.state} in tenant {self._tenant!r}. An attempt accountable to "
                f"somebody who has left does not silently continue."
            )
        return found.human_id

    def _reread(self, pipeline_instance_id: str) -> PipelineInstance:
        row = self._conn.execute(
            "SELECT * FROM pipeline_instances WHERE tenant = ? AND pipeline_instance_id = ?",
            (self._tenant, pipeline_instance_id),
        ).fetchone()
        assert row is not None
        return _row_to_pipeline(row)

    def _envelope(
        self,
        *,
        event_name: str,
        transition_id: str,
        pipeline_instance_id: str,
        work_item_id: str,
        aggregate_version: int,
        owner_id: str,
        actor_type: str,
        actor_id: str,
        payload: Mapping[str, Any],
        correlation_id: str | None,
        causation_id: str | None,
        trace_id: str | None,
        event_id: str | None,
        now: str,
        idempotency_identity: str | None = None,
        entity_versions: Mapping[str, int] | None = None,
        policy_version: str | None = None,
        brake_version: str | None = None,
        material_facts_fingerprint: str | None = None,
    ) -> EventEnvelope:
        """One canonical envelope. ### `work_item_id` AND `accountable_owner_id` TRAVEL ON EVERY ONE.

        §1 marks both `C` (required-when-applicable), and on an attempt both are always applicable:
        every Pipeline Instance serves exactly one Work Item and is owned by that item's accountable
        human. Carrying them means `event_audit.explain(...)` reconstructs *who owed this* from the
        beliefs of that day rather than by asking who owns it now — an audit that answers with
        today's roster is one that cannot be trusted about the past.

        ### AND `previous_aggregate_version` TRAVELS ON EVERY ONE, WHICH IS WHY THIS FACTORY IS THE
        ONLY PLACE THIS MACHINE BUILDS AN ENVELOPE (P6-D11). `pipeline_instance` is a STRICT-ORDER
        aggregate and eight of §14's twenty-five rows are `CONSUMES`: they advance the attempt's
        version and emit nothing here, because the canonical event belongs to M3 or M4. The version
        sequence on this stream is therefore NOT contiguous, by canonical design and not by defect,
        and a consumer that read a missing version as "an earlier event is still coming" would park
        at the first one and never unpark. Declaring the predecessor is what makes an intentional
        non-emission legible as nothing instead of as a loss — see `events/registry.md` §8.

        Derived from the outbox's own emitted record (`last_emitted_version`), never from a counter
        this machine keeps: a counter is a second version to get wrong, and this machine already has
        one. `emit` re-derives it and REFUSES a mismatch, so this value cannot become a lie about
        what was emitted even if this method is wrong.
        """
        return EventEnvelope(
            event_id=event_id or str(uuid.uuid4()),
            event_name=event_name,
            event_version=CONTRACTS[event_name].current_version,
            occurred_at=now,
            recorded_at=now,
            tenant_id=self._tenant,
            aggregate_type=AGGREGATE_TYPE,
            aggregate_id=pipeline_instance_id,
            aggregate_version=aggregate_version,
            previous_aggregate_version=TransactionalOutbox(
                self._conn, tenant=self._tenant, clock=self._clock,
            ).last_emitted_version(
                AGGREGATE_TYPE, pipeline_instance_id, below=aggregate_version),
            causation_id=causation_id,
            correlation_id=correlation_id or work_item_id,
            producer_component=self._component,
            producer_transition_id=transition_id,
            actor_type=actor_type,
            actor_id=actor_id,
            trace_id=trace_id or f"trace-{pipeline_instance_id}",
            payload=dict(payload),
            work_item_id=work_item_id,
            pipeline_instance_id=pipeline_instance_id,
            accountable_owner_id=owner_id,
            idempotency_identity=idempotency_identity,
            entity_versions=entity_versions,
            policy_version=policy_version,
            brake_version=brake_version,
            material_facts_fingerprint=material_facts_fingerprint,
        )


# ------------------------------------------------------------------------------------- plumbing

def _gate_value(gate: GateDecision | str | None) -> str | None:
    if gate is None:
        return None
    return gate.value if isinstance(gate, GateDecision) else str(gate).strip() or None


def _is_denied(facts: _Facts) -> bool:
    """PL-3's condition, in one place so PL-2's exclusion and PL-3's admission cannot disagree.

    §14 PL-3: *"policy **DENIES**, or gate = `FORBIDDEN`"*. Written once and read by both rows,
    because a total-and-mutually-exclusive pair implemented as two independent predicates stops
    being either the first time one of them is edited.
    """
    return (
        str(facts.policy_decision or "").strip().upper() == "DENY"
        or _gate_value(facts.gate_decision) == GateDecision.FORBIDDEN.value
    )


def _prune(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Drop absent OPTIONAL fields. `null` and absent are different facts inside a payload (`ev_v1`)."""
    return {k: v for k, v in payload.items() if v is not None}


def _require_attempt_id(attempt_id: str | None) -> str:
    text = str(attempt_id or "").strip()
    if not text:
        raise PipelineError(
            "an illegal-transition record requires the identity of the ATTEMPT it records. On a "
            "consumed trigger that is the incoming event's `event_id`; on the direct API it is the "
            "caller's `event_id` when one was supplied and a fresh identity for the call otherwise."
        )
    return text


_FACT_NAMES = frozenset(_Facts.__dataclass_fields__) - {"extra"}


def _split_facts(facts: Mapping[str, Any]) -> dict[str, Any]:
    known = {k: v for k, v in facts.items() if k in _FACT_NAMES}
    extra = {k: v for k, v in facts.items() if k not in _FACT_NAMES}
    if extra:
        known["extra"] = extra
    return known


def _row_to_pipeline(row: Any) -> PipelineInstance:
    return PipelineInstance(
        tenant=row["tenant"], pipeline_instance_id=row["pipeline_instance_id"],
        work_item_id=row["work_item_id"], state=PipelineState(row["state"]),
        version=int(row["version"]), owner_id=row["owner_id"],
        action_class=row["action_class"], target_system=row["target_system"],
        target_resource_id=row["target_resource_id"], target_operation=row["target_operation"],
        # CANONICAL-ROW-READ: this reads back the occurrence THIS SYSTEM derived and persisted at
        # PL-1, off its own row, so `PipelineInstance.effect` can reconstruct the exact
        # `LogicalEffect` the attempt was created for. P1's prohibition is on a CALLER-AUTHORED
        # occurrence key entering an effect's identity (`params.get("occurrence_key")`); this is
        # the opposite act, and it is what makes §20's "a retry carries the SAME commit key" a
        # fact rather than a hope. The column is immutable by trigger.
        occurrence_key=row["occurrence_key"], commit_key=row["commit_key"],
        attempt_seq=int(row["attempt_seq"]), absorbed_count=int(row["absorbed_count"]),
        last_absorbed_ref=row["last_absorbed_ref"], supersedes=row["supersedes"],
        policy_version=row["policy_version"], gate_decision=row["gate_decision"],
        gate_reason=row["gate_reason"], approval_id=row["approval_id"],
        material_facts_fingerprint=row["material_facts_fingerprint"],
        checkpoint_id=row["checkpoint_id"], grant_id=row["grant_id"],
        claimed_at=row["claimed_at"], reason=row["reason"],
        refused_step=(None if row["refused_step"] is None else int(row["refused_step"])),
        failure_proof=row["failure_proof"], unknown_reason=row["unknown_reason"],
        unknown_outcome_ref=row["unknown_outcome_ref"], recheck_at=row["recheck_at"],
        decision_ref=row["decision_ref"], decision_ref_kind=row["decision_ref_kind"],
        created_at=row["created_at"], updated_at=row["updated_at"],
    )


# Re-exported so a caller reads one name rather than importing the migration for a constant.
STATES: tuple[str, ...] = PIPELINE_STATES
TERMINAL: tuple[str, ...] = TERMINAL_PIPELINE_STATES
HUMAN_OWNED: tuple[str, ...] = HUMAN_OWNED_PIPELINE_STATES
RECOVERABLE: tuple[str, ...] = RECOVERABLE_PIPELINE_STATES
