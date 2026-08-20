"""Machine M3 — the External Effect / Effect Grant: the ONE `effect_grants` row that is the only
serialization point between a decision and the outside world.

    Effect Grant (capability aspect)   "may this attempt touch the world, once, right now?"
    External Effect (outcome aspect)   "what happened when it did — verified, failed, or unknown?"

SD-2 is emphatic (`entities/03-external-effect.md`, `entities/04-effect-grant.md`): these are the
SAME durable ledger row, eight states, ONE machine, `CLAIMED` the single join. This module is that
machine. It is NOT two machines and NOT two commit-key namespaces.

    GRANTED  CLAIMED  ATTEMPTED  VERIFIED  FAILED  EXPIRED_UNCLAIMED  REVOKED  UNKNOWN_OUTCOME

### WHAT THIS MACHINE OWNS, AND WHAT IT ONLY REFLECTS.

It owns the eight states and the thirteen transitions of `03-external-effect-grant.machine.md` §14,
and it is the canonical PRODUCER of the `EF-*` event stream on the `effect_grant` aggregate. It does
NOT own the checkpoint or the claim CAS: those are P3's, and `mint` and `claim` call the kernel
through its locked entry points and co-commit M3's own event with the kernel's write. A second
implementation of the checkpoint or the CAS would be the dual effect-authority system CLAUDE.md
rule 17 forbids, and the two would disagree the first time one of them changed. The kernel already
performs EF-1 (mint), EF-2 (the CAS), EF-2x (expire) and EF-2r (revoke) as durable STATE writes and
records them as process-local OBSERVATIONS; what it does NOT do is emit the canonical `EffectGranted`
/`GrantClaimed`/`EffectAttempted`/… events to the P5 outbox, because those belong to M3 by the event
registry. So M3 is a thin, event-emitting wrapper over the kernel for the capability aspect, and the
full owner of the outcome aspect (EF-3…EF-5).

### THE THREE SAFETY-CRITICAL COMMITS (§35), AND THE ONE PROPERTY EACH BUYS.

  * the MINT txn      — seven checks + witness + grant + `EffectGranted`, or none of them.
  * the CLAIM-CAS txn — the atomic `GRANTED → CLAIMED` + `GrantClaimed` + `EffectAttempted` (emitted
    BEFORE anything touches the world), or none of them. A brake between mint and claim makes the CAS
    match zero rows and the adapter does NOTHING — never both, never neither.
  * the VERIFY+RECORD txn — the readback match and the `VERIFIED` record are one commit, so the
    "verified but not recorded" window does not exist.

### AND THE PROPERTY IT REFUSES TO GIVE YOU.

`CLAIMED` plus a crash, a timeout or a lost response is `UNKNOWN_OUTCOME`, NEVER `FAILED` (§36,
GR-5, GR-6). `FAILED` requires affirmative proof of non-occurrence. `UNKNOWN_OUTCOME` is non-terminal,
owned by a named human, moved by no timer, and resolved only by an authenticated human determination
or a later deterministic proof. A blind readback is `OBSERVATION_UNAVAILABLE`, never a failure.

### IT IS A STRICT-ORDER CONSUMER (P6-D24, P6-D11).

`effect_grant` is a STRICT-ORDER aggregate (F3, `events/registry.md` §8). `consume` drives one
transition from a canonical `effect_grant` envelope through P5's `DedupInbox` — idempotent by the
inbox (GR-4), parked on a missing grant or an UNAPPLIED PREDECESSOR (M-26, §8: strict order is ORDER,
not CONTIGUITY), and it supplies `drain_handler_for` so a parked cohort is released the moment its
predecessor applies rather than waiting for M-26 expiry. M3 is the first strict consumer, so P6-D24
closes here.

### IT SHIPS DARK. Nothing under `src/freight_recon/` imports this module, and the only script that
may is `scripts/probe_phase6_external_effect.py`.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .checkpoint import (
    CheckpointAuthorized,
    CheckpointInputs,
    CheckpointKernel,
    CheckpointRefused,
    CheckpointRequest,
    ClaimParams,
    EffectGrantHandle,
    claim_grant_cas_locked,
    expire_unclaimed,
    flush_claim_records,
    record_checkpoint_refusal,
    revoke_unclaimed,
    run_checkpoint_locked,
)
from .event_contracts import CONTRACTS
from .event_envelope import EventEnvelope, format_instant
from .event_inbox import ConsumeResult, DedupInbox
from .event_outbox import TransactionalOutbox
from .migrations.phase6_external_effects import (
    EF_HUMAN_OWNED_STATES,
    EF_RECOVERABLE_STATES,
    EF_STATES,
    EF_TERMINAL_STATES,
)
from .tenant import require_tenant
from .work_item import DecisionRefUnresolvable, resolve_decision_ref

# The aggregate this machine owns. `effect_grant` is in `STRICT_ORDER_AGGREGATE_TYPES`
# (`events/registry.md` §8, F3): its transitions are version-monotonic, so an out-of-order F3 event
# is a gap, not a tolerable reordering, and the inbox parks it until the gap fills.
AGGREGATE_TYPE = "effect_grant"

# `entities/04-effect-grant.md` point 5: the Effect Grant Ledger (Safety Kernel) owns the row.
PRODUCER_COMPONENT = "effect_grant_ledger"

# The one consumer identity M3 presents to the dedup inbox. Fixed, because the dedup key is
# `(tenant, consumer_id, event_id)` and a consumer that renamed itself would re-arm every duplicate.
CONSUMER_ID = "m3-external-effect"

# GR-1's producer id for `IllegalTransitionAttempted` — the RULE, not a transition. Identical to
# M1's/M2's and for the same reason: `events/registry.md` §3 states this contract's producer as
# "‡(any machine, GR-1)".
ILLEGAL_TRANSITION_PRODUCER = "GR-1"

# The identity of ONE refused attempt / ONE refused claim: §4's transition-natural identity plus the
# attempt id, because a refusal advances no version and every refusal against one grant at one
# version would otherwise collide on `idempotency_identity` — the poison-loop defect M1 shipped and
# had corrected in review. Applied here rather than rediscovered.
ILLEGAL_ATTEMPT_IDENTITY_PREFIX = "ita_v1"
CLAIM_REFUSED_IDENTITY_PREFIX = "clr_v1"

# The three `unknown_reason` values (`entities/03` point 12). `UNKNOWN_OUTCOME` is EF-3u's (a crash,
# timeout or lost response); the two `OBSERVATION_*` are EF-4c/EF-4u's readback verdicts.
UNKNOWN_REASON_CRASHED = "UNKNOWN_OUTCOME"
UNKNOWN_REASON_CONFLICTING = "OBSERVATION_CONFLICTING"
UNKNOWN_REASON_UNAVAILABLE = "OBSERVATION_UNAVAILABLE"

# EF-4's single verification outcome: a healthy readback matching the approved fingerprint.
VERIFIED_SUCCESS = "VERIFIED_SUCCESS"

# The kernel's `ClaimOutcome.cause` values that mean "the CAS found the grant not-GRANTED" — the
# EF-2f case that emits `ClaimRefused`. Every other refusal cause is a Sev-0 the kernel records
# itself (a forged handle, a replayed handle, a wrong-target claim, a stale witness); those never
# reach a claimant as a `ClaimRefused`, and mapping them into one would launder an attack into an
# ordinary refusal.
_CLAIM_REFUSED_CAUSE: Mapping[str, str] = {
    "ALREADY_CLAIMED": "already_claimed",
    "ALREADY_ATTEMPTED": "already_claimed",
    "ALREADY_VERIFIED": "already_claimed",
    "ALREADY_FAILED": "already_claimed",
    "ALREADY_UNKNOWN_OUTCOME": "already_claimed",
    "ALREADY_EXPIRED_UNCLAIMED": "expired",
    "ALREADY_REVOKED": "revoked",
    "EXPIRED": "expired",
    "BRAKE_CHANGED": "brake",
    "POLICY_CHANGED": "policy",
}


class EffectGrantError(RuntimeError):
    """This machine will not do what was asked. Never degraded into a partial transition."""


class UnknownGrant(EffectGrantError):
    """No `effect_grants` row with this id exists FOR THIS TENANT.

    Deliberately indistinguishable from "it belongs to another tenant": establishing the difference
    needs a read across the tenant boundary, and [C-1] rejects a cross-tenant question rather than
    answering it carefully.
    """


class GuardNotSatisfied(EffectGrantError):
    """The (state, trigger) pair IS legal here and a precondition is false. No event is emitted."""


class IllegalTransition(EffectGrantError):
    """GR-1 / [C-4]. The (state, trigger) pair is not in the table (or §15 forbids the shape).

    Raised AFTER `IllegalTransitionAttempted` has been recorded, which is the point of recording it.
    """


class StateConflict(EffectGrantError):
    """A state-guarded UPDATE matched zero rows: the grant moved under us. The M3 analogue of GR-3,
    over the state predicate that IS this row's concurrency control (the ledger has no OCC column;
    the CAS and the state predicates are the guard)."""


class AuthorityRefused(EffectGrantError):
    """The ACTOR driving this transition does not hold the authority the transition requires."""


class OwnershipRefused(EffectGrantError):
    """An `UNKNOWN_OUTCOME` cannot be tied to a named, ACTIVE human. §9, rule 13.

    `UNKNOWN_OUTCOME` is non-terminal and human-owned; a machine that produced one with no
    accountable human would be creating the one obligation nobody owes — the silent drop rule 13
    exists to forbid.
    """


# --------------------------------------------------------------------------------- the state set

class EffectGrantState(str, Enum):
    GRANTED = "GRANTED"
    CLAIMED = "CLAIMED"
    ATTEMPTED = "ATTEMPTED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    EXPIRED_UNCLAIMED = "EXPIRED_UNCLAIMED"
    REVOKED = "REVOKED"
    UNKNOWN_OUTCOME = "UNKNOWN_OUTCOME"


class Trigger(str, Enum):
    """The closed set of driving facts, named from §14's guards and §33's "Events consumed".

    ### `TIMER_FIRED` IS IN THIS ENUM AND HAS NO LEGAL ROW ON `UNKNOWN_OUTCOME`, WHICH IS THE POINT.
    §14's EF-5x is the one row that declares an ILLEGAL outcome (GR-6: no timer moves an
    `UNKNOWN_OUTCOME`). Modelling it as a trigger with no legal row makes GR-1 answer it uniformly —
    a timer fired at `UNKNOWN_OUTCOME` raises, persists nothing and records
    `IllegalTransitionAttempted` — which is stronger than a special case and derived from the table.
    """

    CLAIM_ATTEMPTED = "ClaimAttempted"
    GRANT_EXPIRED = "GrantExpired"
    GRANT_REVOKED = "GrantRevoked"
    ADAPTER_RETURNED = "AdapterReturnedSuccess"
    ADAPTER_REJECTED_PRE_FLIGHT = "AdapterRejectedPreFlight"
    ADAPTER_TIMED_OUT = "AdapterTimedOut"
    PROCESS_CRASHED = "ProcessCrashed"
    LOST_RESPONSE = "LostResponse"
    READBACK_MATCHED = "ReadbackMatched"
    READBACK_CONFLICTING = "ReadbackConflicting"
    READBACK_UNAVAILABLE = "ReadbackUnavailable"
    HUMAN_ESTABLISHED_REALITY = "HumanEstablishedReality"
    LATER_OBSERVATION_PROVES = "LaterObservationProves"
    TIMER_FIRED = "TimerFired"


class RowKind(str, Enum):
    PRODUCER = "PRODUCER"          # emits a canonical event attributed to this transition
    NON_PRODUCING = "NON_PRODUCING"  # EF-5x only: declared ILLEGAL by the specification


# --------------------------------------------------------------------------- the transition table

@dataclass(frozen=True)
class TransitionRow:
    """One row of §14. Data, so `AC-MACH-301..313` can enumerate it and compare to the specification."""

    id: str
    from_states: tuple[EffectGrantState, ...]
    to_state: EffectGrantState | None
    triggers: tuple[Trigger, ...]
    trigger_types: tuple[str, ...]     # H|S|X|T|P|B|R — the registry §1 codes
    kind: RowKind
    events: tuple[str, ...] = ()       # the canonical events this row emits (EF-2 emits two)
    consequential: bool = False        # §5: pins the SD-3 set + policy/brake at emission
    kernel_path: str | None = None     # "mint" | "claim" | "expire" | "revoke" — a kernel-owned row
    illegal: bool = False              # EF-5x only
    # EF-5 reaches TWO states, resolved at runtime by the establishing event's own `outcome`.
    alternate_to_state: EffectGrantState | None = None
    # EF-2f is a refusal, not a state change: it emits `ClaimRefused` and moves nothing.
    refusal_only: bool = False

    @property
    def independently_fireable(self) -> bool:
        return not (self.illegal or self.refusal_only)


TRANSITIONS: tuple[TransitionRow, ...] = (
    TransitionRow(
        id="EF-1", from_states=(), to_state=EffectGrantState.GRANTED,
        triggers=(), trigger_types=("S",), kind=RowKind.PRODUCER,
        events=("EffectGranted",), consequential=True, kernel_path="mint",
    ),
    TransitionRow(
        id="EF-2", from_states=(EffectGrantState.GRANTED,), to_state=EffectGrantState.CLAIMED,
        triggers=(Trigger.CLAIM_ATTEMPTED,), trigger_types=("S",), kind=RowKind.PRODUCER,
        events=("GrantClaimed", "EffectAttempted"), consequential=True, kernel_path="claim",
    ),
    TransitionRow(
        id="EF-2r", from_states=(EffectGrantState.GRANTED,), to_state=EffectGrantState.REVOKED,
        triggers=(Trigger.GRANT_REVOKED,), trigger_types=("B", "P", "H"),
        kind=RowKind.PRODUCER, events=("GrantRevoked",), kernel_path="revoke",
    ),
    TransitionRow(
        id="EF-2x", from_states=(EffectGrantState.GRANTED,),
        to_state=EffectGrantState.EXPIRED_UNCLAIMED,
        triggers=(Trigger.GRANT_EXPIRED,), trigger_types=("T",),
        kind=RowKind.PRODUCER, events=("GrantExpired",), kernel_path="expire",
    ),
    TransitionRow(
        # A refusal, not a transition: §14's Writes cell is "—". The CAS found the grant not-GRANTED;
        # the grant is unchanged, the adapter does nothing, and `ClaimRefused` is the audit of it.
        id="EF-2f", from_states=(EffectGrantState.GRANTED,), to_state=None,
        triggers=(Trigger.CLAIM_ATTEMPTED,), trigger_types=("S",),
        kind=RowKind.PRODUCER, events=("ClaimRefused",), refusal_only=True,
    ),
    TransitionRow(
        id="EF-3", from_states=(EffectGrantState.CLAIMED,), to_state=EffectGrantState.ATTEMPTED,
        triggers=(Trigger.ADAPTER_RETURNED,), trigger_types=("X",),
        kind=RowKind.PRODUCER, events=("EffectExecuted",), consequential=True,
    ),
    TransitionRow(
        id="EF-3f", from_states=(EffectGrantState.CLAIMED,), to_state=EffectGrantState.FAILED,
        triggers=(Trigger.ADAPTER_REJECTED_PRE_FLIGHT,), trigger_types=("S",),
        kind=RowKind.PRODUCER, events=("EffectFailed",), consequential=True,
    ),
    TransitionRow(
        id="EF-3u", from_states=(EffectGrantState.CLAIMED,),
        to_state=EffectGrantState.UNKNOWN_OUTCOME,
        triggers=(Trigger.ADAPTER_TIMED_OUT, Trigger.PROCESS_CRASHED, Trigger.LOST_RESPONSE),
        trigger_types=("S", "R"),
        kind=RowKind.PRODUCER, events=("OutcomeUnknown",), consequential=True,
    ),
    TransitionRow(
        id="EF-4", from_states=(EffectGrantState.ATTEMPTED,), to_state=EffectGrantState.VERIFIED,
        triggers=(Trigger.READBACK_MATCHED,), trigger_types=("X",),
        kind=RowKind.PRODUCER, events=("EffectVerified",), consequential=True,
    ),
    TransitionRow(
        id="EF-4c", from_states=(EffectGrantState.ATTEMPTED,),
        to_state=EffectGrantState.UNKNOWN_OUTCOME,
        triggers=(Trigger.READBACK_CONFLICTING,), trigger_types=("X",),
        kind=RowKind.PRODUCER, events=("VerificationConflict",),
    ),
    TransitionRow(
        id="EF-4u", from_states=(EffectGrantState.ATTEMPTED,),
        to_state=EffectGrantState.UNKNOWN_OUTCOME,
        triggers=(Trigger.READBACK_UNAVAILABLE,), trigger_types=("X",),
        kind=RowKind.PRODUCER, events=("VerificationUnavailable",),
    ),
    TransitionRow(
        id="EF-5", from_states=(EffectGrantState.UNKNOWN_OUTCOME,),
        to_state=EffectGrantState.VERIFIED, alternate_to_state=EffectGrantState.FAILED,
        triggers=(Trigger.HUMAN_ESTABLISHED_REALITY, Trigger.LATER_OBSERVATION_PROVES),
        trigger_types=("H", "X"),
        kind=RowKind.PRODUCER, events=("RealityEstablished",), consequential=True,
    ),
    TransitionRow(
        # ⛔ ILLEGAL (GR-6). Declared in the table because `AC-MACH-301..313` compares the
        # specification's thirteen identifiers, and a rule that is never expressible is untestable.
        # Excluded from `legal_transitions`, so GR-1 refuses it like any unenumerated pair.
        id="EF-5x", from_states=(EffectGrantState.UNKNOWN_OUTCOME,), to_state=None,
        triggers=(Trigger.TIMER_FIRED,), trigger_types=("T",),
        kind=RowKind.NON_PRODUCING, illegal=True,
    ),
)

TRANSITIONS_BY_ID: Mapping[str, TransitionRow] = {row.id: row for row in TRANSITIONS}

# §32 "Events emitted", derived from the table. The contract gate refuses an envelope whose
# `producer_transition_id` is not among the contract's declared producers, so this is also the set
# the outbox accepts from this machine — a second hand-kept list would stop matching.
PRODUCED_CONTRACTS: frozenset[str] = frozenset(
    ev for row in TRANSITIONS for ev in row.events)

# Which kernel path a trigger routes to (EF-2 → claim). EF-1/EF-2x/EF-2r are not driven by a public
# trigger — mint/expire/revoke are their own methods — so only the claim trigger appears here.
KERNEL_PATH_BY_TRIGGER: Mapping[Trigger, str] = {
    Trigger.CLAIM_ATTEMPTED: "claim",
}

TERMINAL_STATES: frozenset[EffectGrantState] = frozenset(
    EffectGrantState(s) for s in EF_TERMINAL_STATES)
HUMAN_OWNED_STATES: frozenset[EffectGrantState] = frozenset(
    EffectGrantState(s) for s in EF_HUMAN_OWNED_STATES)
RECOVERABLE_STATES: frozenset[EffectGrantState] = frozenset(
    EffectGrantState(s) for s in EF_RECOVERABLE_STATES)


def legal_transitions(state: EffectGrantState, trigger: Trigger) -> tuple[TransitionRow, ...]:
    """Every independently-fireable, non-refusal row whose (from-state, trigger) matches.

    Empty ⇒ ILLEGAL (GR-1). EF-2f is excluded because a refusal is not a transition; EF-1 is
    excluded because a mint is not driven by a public trigger. EF-2's `CLAIM_ATTEMPTED` on a GRANTED
    grant IS legal (it routes to the kernel); the same trigger on a not-GRANTED grant is EF-2f's
    refusal, handled by `claim`, not by the ordinary transition path.
    """
    return tuple(
        row for row in TRANSITIONS
        if row.independently_fireable and row.kernel_path is None
        and state in row.from_states and trigger in row.triggers
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------------------------ the row

@dataclass(frozen=True)
class EffectGrant:
    """One `effect_grants` row, as the machine reads it. The columns M3 touches, named."""

    tenant: str
    grant_id: str
    commit_key: str
    state: EffectGrantState
    action_class: str
    target_system: str
    target_resource_id: str
    target_operation: str
    checkpoint_id: str | None
    pipeline_instance_id: str | None
    material_facts_fingerprint: str | None
    entity_versions_json: str | None
    policy_version: str | None
    brake_version: str | None
    approval_id: str | None
    expires_at: str | None
    claimed_at: str | None
    attempted_at: str | None
    verified_at: str | None
    verification_outcome: str | None
    unknown_reason: str | None
    failure_proof: str | None
    exposure: str | None
    health_signal: str | None
    reality_decision_ref: str | None

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    def pins(self) -> dict[str, Any]:
        """The decision context §5 requires on a CONSEQUENTIAL event — read from the row the mint
        pinned, never re-derived. An audit that reconstructed these from today's state could say what
        was decided but never why it was allowed then."""
        try:
            versions = json.loads(self.entity_versions_json) if self.entity_versions_json else {}
        except (TypeError, ValueError):
            versions = {}
        return {
            "entity_versions": versions,
            "policy_version": self.policy_version,
            "brake_version": self.brake_version,
            "material_facts_fingerprint": self.material_facts_fingerprint,
        }


@dataclass(frozen=True)
class MintOutcome:
    """What EF-1 did — a minted grant with its claimable handle, or a checkpoint refusal."""

    authorized: bool
    grant_id: str | None = None
    handle: EffectGrantHandle | None = None
    event_id: str | None = None
    refusal: CheckpointRefused | None = None


@dataclass(frozen=True)
class ClaimResult:
    """What EF-2 / EF-2f did. `claimed` is the winner; a refusal names its cause and did nothing."""

    claimed: bool
    grant_id: str
    cause: str
    grant_claimed_event_id: str | None = None
    effect_attempted_event_id: str | None = None
    claim_refused_event_id: str | None = None


@dataclass(frozen=True)
class TransitionResult:
    """What one outcome transition did. Every field is read back from the row, never the intention."""

    transition_id: str
    grant: EffectGrant
    from_state: EffectGrantState
    to_state: EffectGrantState
    event_ids: tuple[str, ...] = ()
    event_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class IllegalAttemptRecord:
    event_id: str
    idempotency_identity: str
    already_recorded: bool


@dataclass(frozen=True)
class ConsumedTransition:
    """What consuming one canonical trigger did — including the case where it did nothing.

    `consume.outcome` is P5's and is about DELIVERY. `transition`, `refusal` and `refusal_kind` are
    about the MACHINE. Keeping them apart is what stops "the event was delivered" being read as "the
    grant moved".
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

    ### NOTHING HERE IS INFERRED, AND TWO ENTRIES ARE THE REASON THE CLASS IS EXPLICIT.
    `failure_proof` is GR-5: a caller that cannot produce affirmative evidence the effect did NOT
    happen gets `UNKNOWN_OUTCOME`, never `FAILED`. `matched_fingerprint` is M-70/71: EF-4 verifies
    only when a healthy-channel readback MATCHES the approved fingerprint — the machine will not
    derive either, because a machine that derived them would be right most of the time, which is the
    worst possible failure profile for money.
    """

    failure_proof: str | None = None
    exposure: str | None = None
    unknown_reason: str | None = None
    matched_fingerprint: str | None = None
    health_signal: str | None = None
    channel: str | None = None
    outcome: str | None = None          # EF-5: VERIFIED | FAILED
    decision_ref: str | None = None
    decision_ref_kind: str | None = None
    accountable_owner_id: str | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------------- the machine

class ExternalEffectMachine:
    """M3, on an existing connection, bound to ONE tenant and ONE checkpoint kernel.

    Bound at construction rather than per call, for the reason `DedupInbox` and `CheckpointKernel`
    are: a machine that could be re-pointed at another tenant per call would put [C-1] in the
    caller's hands, and one that could be handed a different kernel per claim could claim a grant
    minted under different authority.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        tenant: str,
        kernel: CheckpointKernel | None = None,
        clock: Callable[[], datetime] | None = None,
        producer_component: str = PRODUCER_COMPONENT,
    ) -> None:
        if getattr(conn, "row_factory", None) is not sqlite3.Row:
            raise EffectGrantError(
                "ExternalEffectMachine reads columns by name and requires "
                "`row_factory = sqlite3.Row` (WorkflowStore sets it; PostgresConnection reports it)."
            )
        self._conn = conn
        self._tenant = require_tenant(tenant, context="ExternalEffectMachine")
        self._kernel = kernel
        self._clock = clock or _utc_now
        self._component = producer_component

    @property
    def tenant(self) -> str:
        return self._tenant

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    @property
    def kernel(self) -> CheckpointKernel | None:
        return self._kernel

    # --- reads -----------------------------------------------------------------------------------

    def get(self, grant_id: str) -> EffectGrant | None:
        row = self._conn.execute(
            "SELECT * FROM effect_grants WHERE tenant = ? AND grant_id = ?",
            (self._tenant, grant_id),
        ).fetchone()
        return _row_to_grant(row) if row is not None else None

    def require(self, grant_id: str) -> EffectGrant:
        found = self.get(grant_id)
        if found is None:
            raise UnknownGrant(
                f"no effect grant {grant_id!r} for tenant {self._tenant!r}. This machine does not "
                f"look outside its tenant to find out whether it exists elsewhere — [C-1] rejects a "
                f"cross-tenant question rather than answering it carefully."
            )
        return found

    def unknown_outcomes(self) -> list[EffectGrant]:
        """§42's Sev-1 queue: the effects nobody can say happened or did not.

        ### A NEGATIVE ASSERTION NEEDS A PROVEN POPULATION (CLAUDE.md §9), so this returns the rows
        and the caller is expected to assert against a non-empty population. A "no unknown outcomes"
        check over an empty table is a green check that parsed nothing.
        """
        return [
            _row_to_grant(r) for r in self._conn.execute(
                "SELECT * FROM effect_grants WHERE tenant = ? AND state = ? ORDER BY grant_id",
                (self._tenant, EffectGrantState.UNKNOWN_OUTCOME.value),
            ).fetchall()
        ]

    # --- EF-1: the mint ---------------------------------------------------------------------------

    def mint(
        self,
        request: CheckpointRequest,
        inputs: CheckpointInputs,
        *,
        actor_type: str = "system",
        actor_id: str,
        pipeline_instance_id: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> MintOutcome:
        """EF-1 — ### ONE TRANSACTION carries the seven checks, the witness, the grant AND
        `EffectGranted`.

        Mint requires REAL checkpoint authority: `run_checkpoint_locked` will not mint without a
        `CheckpointPassed`, which has no public constructor. This machine constructs neither the
        kernel nor a `GateRegistry` — the seven checks are P3's, and a machine that built its own
        would be the second effect authority CLAUDE.md rule 17 forbids. What M3 adds is the canonical
        `EffectGranted` event the kernel does not emit, co-committed with the mint.

        On refusal the transaction is abandoned FIRST and the kernel's Sev-0/observability record is
        written AFTER — the same ordering M1's illegal-transition path uses, and for the same reason.
        No EF event is emitted on a refused checkpoint: EF-1 has no failure event.
        """
        kernel = self._kernel
        if kernel is None:
            raise GuardNotSatisfied(
                "EF-1 requires the checkpoint kernel. This machine does not construct one — the "
                "seven checks and the gate registry are P3's (CLAUDE.md rule 17)."
            )
        if request.effect.tenant.strip().lower() != self._tenant.strip().lower():
            raise EffectGrantError(
                f"the effect names tenant {request.effect.tenant!r}; this machine is bound to "
                f"{self._tenant!r}. A mint never crosses a tenant [C-1]."
            )
        now = format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            outcome = run_checkpoint_locked(kernel, request, inputs, now=self._clock())
            if isinstance(outcome, CheckpointAuthorized):
                grant_id = outcome.witness.grant_id
                if pipeline_instance_id is not None:
                    # Bind the Pipeline Instance in the mint commit. The FK refuses an id with no
                    # referent, which is the whole point of it being a foreign key.
                    conn.execute(
                        "UPDATE effect_grants SET pipeline_instance_id = ? "
                        " WHERE tenant = ? AND grant_id = ?",
                        (pipeline_instance_id, self._tenant, grant_id),
                    )
                grant = self.require(grant_id)
                envelope = self._envelope(
                    event_name="EffectGranted", transition_id="EF-1", grant=grant,
                    aggregate_version=self._next_version(grant_id), actor_type=actor_type,
                    actor_id=actor_id, payload=_prune({
                        "grant_id": grant_id,
                        "checkpoint_id": grant.checkpoint_id,
                        "commit_key": grant.commit_key,
                        "material_facts_fingerprint": grant.material_facts_fingerprint,
                        "entity_versions": grant.pins()["entity_versions"],
                        "policy_version": grant.policy_version,
                        "brake_version": grant.brake_version,
                        "approval_id": grant.approval_id,
                        "expires_at": grant.expires_at,
                    }),
                    correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                    event_id=event_id, now=now, consequential=True,
                )
                self._outbox().emit(envelope)
                conn.commit()
                return MintOutcome(
                    authorized=True, grant_id=grant_id, handle=outcome.handle,
                    event_id=envelope.event_id)
            conn.rollback()
        except BaseException:
            conn.rollback()
            raise
        assert isinstance(outcome, CheckpointRefused)
        record_checkpoint_refusal(kernel, request, outcome)
        return MintOutcome(authorized=False, refusal=outcome)

    # --- EF-2 / EF-2f: the claim ------------------------------------------------------------------

    def claim(
        self,
        handle: EffectGrantHandle,
        params: ClaimParams,
        *,
        actor_type: str = "system",
        actor_id: str,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        attempt_id: str | None = None,
    ) -> ClaimResult:
        """EF-2 — ### THE CAS AND ITS EVENTS MOVE IN ONE TRANSACTION.

        The claim CAS is the sole serialization point of the effect (§17) and it is P3's, called
        through its locked entry point so `GrantClaimed` and `EffectAttempted` are in the commit that
        wins it. `EffectAttempted` is emitted BEFORE anything touches the world, so a lost response is
        detectable; it is emitted EXACTLY ONCE (EF-3 must not emit a second — §19/§38).

        A zero-row CAS is EF-2f: the adapter does nothing. When the cause is one the CAS itself found
        (already-claimed / expired / revoked / brake / policy) it is `ClaimRefused`; when it is a
        forged, replayed, wrong-target or stale-witness handle the kernel records a Sev-0 and no
        `ClaimRefused` is minted — laundering an attack into an ordinary refusal is exactly what the
        distinct records exist to prevent.
        """
        kernel = self._kernel
        if kernel is None:
            raise GuardNotSatisfied(
                "EF-2 requires the checkpoint kernel: the claim CAS belongs to it (§17, rule 17)."
            )
        now = format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            pending = claim_grant_cas_locked(kernel, handle, params, now=self._clock())
            if pending.outcome.claimed:
                grant = self.require(handle.grant_id)
                version = self._next_version(handle.grant_id)
                claimed_env = self._envelope(
                    event_name="GrantClaimed", transition_id="EF-2", grant=grant,
                    aggregate_version=version, actor_type=actor_type, actor_id=actor_id,
                    payload={"grant_id": handle.grant_id},
                    correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                    event_id=None, now=now, consequential=True,
                )
                self._outbox().emit(claimed_env)
                attempted_env = self._envelope(
                    event_name="EffectAttempted", transition_id="EF-2", grant=grant,
                    aggregate_version=version, actor_type=actor_type, actor_id=actor_id,
                    payload={"grant_id": handle.grant_id},
                    correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                    event_id=None, now=now, consequential=True,
                )
                self._outbox().emit(attempted_env)
                conn.commit()
                flush_claim_records(kernel, pending)
                return ClaimResult(
                    claimed=True, grant_id=handle.grant_id, cause="CLAIMED",
                    grant_claimed_event_id=claimed_env.event_id,
                    effect_attempted_event_id=attempted_env.event_id)
            conn.rollback()
        except BaseException:
            conn.rollback()
            raise
        # Refused: settle the kernel's records (its Sev-0s and observations) OUTSIDE the abandoned
        # transaction, then — only for a CAS-found refusal — record EF-2f's `ClaimRefused`.
        outcome = flush_claim_records(kernel, pending)
        refused_event_id = self._record_claim_refused(
            handle.grant_id, outcome.cause, actor_type=actor_type, actor_id=actor_id,
            correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
            attempt_id=attempt_id or handle.token,
        )
        return ClaimResult(
            claimed=False, grant_id=handle.grant_id, cause=outcome.cause,
            claim_refused_event_id=refused_event_id)

    def _record_claim_refused(
        self,
        grant_id: str,
        cause: str,
        *,
        actor_type: str,
        actor_id: str,
        correlation_id: str | None,
        causation_id: str | None,
        trace_id: str | None,
        attempt_id: str,
    ) -> str | None:
        mapped = _CLAIM_REFUSED_CAUSE.get(cause)
        if mapped is None:
            # A Sev-0 refusal (forged / replayed / wrong-target / stale witness / unreadable brake).
            # The kernel recorded it; EF-2f does not fire, so the grant carries no ordinary refusal.
            return None
        grant = self.get(grant_id)
        if grant is None:
            return None
        now = format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            envelope = self._envelope(
                event_name="ClaimRefused", transition_id="EF-2f", grant=grant,
                aggregate_version=self._next_version(grant_id), actor_type=actor_type,
                actor_id=actor_id, payload={"grant_id": grant_id, "cause": mapped},
                correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                event_id=None, now=now,
                idempotency_identity=f"{CLAIM_REFUSED_IDENTITY_PREFIX}|{self._tenant}"
                                     f"|{grant_id}|{attempt_id}",
            )
            self._outbox().emit(envelope)
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        return envelope.event_id

    # --- EF-2x / EF-2r: the unclaimed lifecycle ---------------------------------------------------

    def expire(
        self,
        grant_id: str,
        *,
        actor_type: str = "system",
        actor_id: str = "grant-ttl",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
    ) -> TransitionResult:
        """EF-2x — GRANTED past its TTL becomes EXPIRED_UNCLAIMED. Nothing happened. The state write
        is the kernel's `expire_unclaimed`; M3 co-commits `GrantExpired`. NEVER touches a claimed row:
        an expiry that could reach `CLAIMED` would convert "the world may have changed" into "pretend
        it did not" — that is what makes this DISTINCT from `UNKNOWN_OUTCOME`."""
        return self._unclaimed_lifecycle(
            grant_id, "EF-2x", "GrantExpired", EffectGrantState.EXPIRED_UNCLAIMED,
            payload_extra={}, actor_type=actor_type, actor_id=actor_id,
            correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id)

    def revoke(
        self,
        grant_id: str,
        *,
        cause: str,
        actor_id: str,
        actor_type: str = "system",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
    ) -> TransitionResult:
        """EF-2r — GRANTED becomes REVOKED (brake engaged, policy changed, approval revoked).

        ### REVOKED IS NOT EXPIRED_UNCLAIMED. Deliberately withdrawn is not the same fact as quietly
        lapsed, so the two are distinct terminal states with distinct events. Revoking an unclaimed
        grant is always safe — nothing happened. Revoking a CLAIMED grant does NOTHING: the effect may
        already exist, and pretending otherwise is how an unknown outcome gets laundered into a clean
        ledger (the kernel's `revoke_unclaimed` only touches GRANTED, and this refuses if it moved 0).
        """
        if not str(cause or "").strip():
            raise GuardNotSatisfied("a revocation records its cause (§14 GrantRevoked{cause}).")
        return self._unclaimed_lifecycle(
            grant_id, "EF-2r", "GrantRevoked", EffectGrantState.REVOKED,
            payload_extra={"cause": cause}, actor_type=actor_type, actor_id=actor_id,
            correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
            cause=cause)

    def _unclaimed_lifecycle(
        self,
        grant_id: str,
        transition_id: str,
        event_name: str,
        to_state: EffectGrantState,
        *,
        payload_extra: Mapping[str, Any],
        actor_type: str,
        actor_id: str,
        correlation_id: str | None,
        causation_id: str | None,
        trace_id: str | None,
        cause: str | None = None,
    ) -> TransitionResult:
        kernel = self._kernel
        if kernel is None:
            raise GuardNotSatisfied(
                f"{transition_id} moves the grant state through the kernel's lifecycle writer.")
        before = self.require(grant_id)
        if before.state is not EffectGrantState.GRANTED:
            raise GuardNotSatisfied(
                f"{transition_id} applies only to a GRANTED grant; {grant_id!r} is "
                f"{before.state.value}. A claimed effect may have touched the world — that is "
                f"UNKNOWN_OUTCOME territory, not revocation or expiry (§22/§36)."
            )
        now = format_instant(self._clock())
        conn = self._conn
        # The kernel owns its own transaction for the state write; M3 emits its event in a co-commit
        # transaction immediately after. The event carries the pre-change grant read, which is the
        # audit fact — "what was withdrawn".
        if transition_id == "EF-2x":
            moved = expire_unclaimed(kernel, now=self._clock())
            changed = moved >= 1 and self.require(grant_id).state is to_state
        else:
            changed = revoke_unclaimed(
                kernel, grant_id=grant_id, cause=cause or "", actor=actor_id)
        if not changed:
            raise StateConflict(
                f"{transition_id} matched zero rows for {grant_id!r}: it moved under us (another "
                f"claim, expiry or revocation won first). Reload and decide again."
            )
        after = self.require(grant_id)
        conn.execute("BEGIN IMMEDIATE")
        try:
            envelope = self._envelope(
                event_name=event_name, transition_id=transition_id, grant=after,
                aggregate_version=self._next_version(grant_id), actor_type=actor_type,
                actor_id=actor_id, payload=_prune({"grant_id": grant_id, **payload_extra}),
                correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                event_id=None, now=now,
            )
            self._outbox().emit(envelope)
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        return TransitionResult(
            transition_id=transition_id, grant=after, from_state=before.state, to_state=to_state,
            event_ids=(envelope.event_id,), event_names=(event_name,))

    # --- EF-3 … EF-5: the outcome aspect ----------------------------------------------------------

    def apply(
        self,
        grant_id: str,
        trigger: Trigger,
        *,
        actor_type: str = "system",
        actor_id: str,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
        **facts: Any,
    ) -> TransitionResult:
        """ONE outcome transition, in ONE commit: the state row and the event it emits, or neither.

        The mint (EF-1), the claim (EF-2/EF-2f) and the unclaimed lifecycle (EF-2x/EF-2r) have their
        own methods because each carries a kernel write; everything downstream of `CLAIMED` is here.
        """
        grant = self.require(grant_id)
        if not legal_transitions(grant.state, trigger):
            self._record_illegal(
                grant, trigger, actor_type=actor_type, actor_id=actor_id,
                correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                attempt_id=event_id or str(uuid.uuid4()))
            raise IllegalTransition(
                f"{trigger.value} is not legal for an effect grant in {grant.state.value} "
                f"(GR-1, [C-4]). No state change was persisted; `IllegalTransitionAttempted` is "
                f"recorded to the audit backbone AND to `security_events`, in a commit of its own. "
                + ("A timer NEVER moves an UNKNOWN_OUTCOME (GR-6, EF-5x is ILLEGAL). "
                   if trigger is Trigger.TIMER_FIRED else "")
            )
        parsed = _Facts(**_split_facts(facts))
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            result = self._apply_locked(
                grant, trigger, actor_type=actor_type, actor_id=actor_id,
                correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                event_id=event_id, facts=parsed)
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        return result

    def _apply_locked(
        self,
        grant: EffectGrant,
        trigger: Trigger,
        *,
        actor_type: str,
        actor_id: str,
        correlation_id: str | None,
        causation_id: str | None,
        trace_id: str | None,
        event_id: str | None,
        facts: _Facts,
        emit: bool = True,
    ) -> TransitionResult:
        """The transition itself. Requires a transaction to be open; never opens or commits one.

        Separated from `apply` so the SAME body serves a consumed trigger, where `DedupInbox` owns
        the transaction (M-24) and the handler must not begin, commit or roll back. Two copies of a
        transition body is how one of them quietly stops emitting an event.

        `emit` is `True` on the PRODUCER path (`apply`): the observation arrived fresh, the state
        advances and the canonical EF event is emitted. It is `False` on the CONSUMER path
        (`consume`): the durable EF event IS the record being applied, so the state advances to match
        it and NOTHING new is emitted — re-emitting a canonical event that already exists would be a
        second copy of one fact. The guards run either way, so consuming re-validates (a verified
        readback still has to match the approved fingerprint) rather than trusting the stream.
        """
        candidates = legal_transitions(grant.state, trigger)
        if not candidates:
            raise IllegalTransition(
                f"{trigger.value} is not legal for an effect grant in {grant.state.value} (GR-1).")
        row = candidates[0]
        to_state = self._resolve_target(row, facts)
        columns, event_payload = self._writes_and_payload(row, grant, facts, to_state)
        # Owner check for the human-owned states — refused BEFORE the write, so an UNKNOWN_OUTCOME is
        # never created without a named human (§9, rule 13).
        if to_state in HUMAN_OWNED_STATES:
            self._require_active_human(facts.accountable_owner_id, row.id)

        sets = ["state = ?"]
        params: list[Any] = [to_state.value]
        for column, value in columns.items():
            sets.append(f"{column} = ?")
            params.append(value)
        cursor = self._conn.execute(
            f"UPDATE effect_grants SET {', '.join(sets)} "
            f" WHERE tenant = ? AND grant_id = ? AND state = ?",
            (*params, self._tenant, grant.grant_id, grant.state.value),
        )
        if cursor.rowcount != 1:
            raise StateConflict(
                f"{row.id} matched {cursor.rowcount} rows for {grant.grant_id!r} in "
                f"{grant.state.value}: it moved under us. The state predicate IS this row's "
                f"concurrency control — reload and retry.")
        after = self.require(grant.grant_id)
        event_ids: list[str] = []
        event_names: list[str] = []
        owner = (facts.accountable_owner_id if to_state in HUMAN_OWNED_STATES else None)
        if emit:
            for name in row.events:
                envelope = self._envelope(
                    event_name=name, transition_id=row.id, grant=after,
                    aggregate_version=self._next_version(grant.grant_id, precomputed=event_ids),
                    actor_type=actor_type, actor_id=actor_id, payload=event_payload,
                    correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                    event_id=event_id if not event_ids else None,
                    now=format_instant(self._clock()),
                    consequential=row.consequential, accountable_owner_id=owner)
                self._outbox().emit(envelope)
                event_ids.append(envelope.event_id)
                event_names.append(name)
        return TransitionResult(
            transition_id=row.id, grant=after, from_state=grant.state, to_state=to_state,
            event_ids=tuple(event_ids), event_names=tuple(event_names))

    def _resolve_target(self, row: TransitionRow, facts: _Facts) -> EffectGrantState:
        """EF-5 reaches VERIFIED or FAILED, decided by the establishing event's own `outcome` —
        never by the caller positionally. GR-6: an unreadable outcome resolves to neither."""
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
            f"failure, so an unreadable outcome resolves to neither.")

    def _writes_and_payload(
        self, row: TransitionRow, grant: EffectGrant, facts: _Facts, to_state: EffectGrantState,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """§14's Writes cell and §32's event payload, per row. The invariants §16 states as CHECKs are
        enforced HERE (a machine guard proven by mutation), not as a DB CHECK on the shared ledger."""
        now = format_instant(self._clock())
        pins = grant.pins()
        if row.id == "EF-3":
            return {"attempted_at": now}, {}
        if row.id == "EF-3f":
            proof = str(facts.failure_proof or "").strip()
            if not proof:
                # ### GR-5 AT THE ROW: FAILED REQUIRES AFFIRMATIVE PROOF OF NON-OCCURRENCE. A timeout
                # alone never proves failure; a FAILED with no proof is an UNKNOWN OUTCOME wearing a
                # resolution, and the wrong one of those two is a retry that pays an invoice twice.
                raise GuardNotSatisfied(
                    "EF-3f (FAILED) requires affirmative proof of non-occurrence (GR-5, §36). "
                    "Without a `failure_proof` the outcome is UNKNOWN_OUTCOME, never FAILED.")
            return {"failure_proof": proof}, {"failure_proof": proof}
        if row.id == "EF-3u":
            return (
                {"exposure": facts.exposure, "unknown_reason": UNKNOWN_REASON_CRASHED},
                {"exposure": _required(facts.exposure, "OutcomeUnknown.exposure"),
                 "unknown_reason": UNKNOWN_REASON_CRASHED},
            )
        if row.id == "EF-4":
            health = str(facts.health_signal or "").strip()
            matched = str(facts.matched_fingerprint or "").strip()
            approved = str(grant.material_facts_fingerprint or "").strip()
            if not health:
                # ### BLIND IS NOT VERIFIED. No positive health signal is EF-4u's OBSERVATION_UNAVAILABLE,
                # never a VERIFIED and never a FAILED (§36, M-71).
                raise GuardNotSatisfied(
                    "EF-4 (VERIFIED) requires a positive health signal on the verifying read. No "
                    "health signal is OBSERVATION_UNAVAILABLE (EF-4u), never VERIFIED.")
            if not approved or matched != approved:
                # ### VERIFIED REQUIRES A HEALTHY READBACK MATCHING THE APPROVED FINGERPRINT (M-70).
                # A mismatch is OBSERVATION_CONFLICTING (EF-4c), not a verification.
                raise GuardNotSatisfied(
                    f"EF-4 (VERIFIED) requires the readback to MATCH the approved fingerprint "
                    f"({approved[:12]}…); it presented {matched[:12] or '(none)'!r}. A mismatch is "
                    f"OBSERVATION_CONFLICTING (EF-4c), never VERIFIED.")
            return (
                {"verified_at": now, "verification_outcome": VERIFIED_SUCCESS,
                 "health_signal": health},
                {"verification_outcome": VERIFIED_SUCCESS, "health_signal": health,
                 "matched_fingerprint": matched},
            )
        if row.id == "EF-4c":
            return (
                {"unknown_reason": UNKNOWN_REASON_CONFLICTING},
                {"unknown_reason": UNKNOWN_REASON_CONFLICTING},
            )
        if row.id == "EF-4u":
            return (
                {"unknown_reason": UNKNOWN_REASON_UNAVAILABLE},
                {"unknown_reason": UNKNOWN_REASON_UNAVAILABLE,
                 "channel": _required(facts.channel, "VerificationUnavailable.channel")},
            )
        if row.id == "EF-5":
            self._resolve_decision(facts, to_state)
            writes: dict[str, Any] = {"reality_decision_ref": facts.decision_ref}
            if to_state is EffectGrantState.FAILED:
                proof = str(facts.failure_proof or "").strip()
                if not proof:
                    raise GuardNotSatisfied(
                        "EF-5 resolving to FAILED still requires affirmative proof (GR-5): a human "
                        "may only establish FAILED against evidence the effect did not occur.")
                writes["failure_proof"] = proof
            return (
                writes,
                {"decision_ref": facts.decision_ref, "outcome": to_state.value, "subject": "effect"},
            )
        del pins  # not every row pins; consequential ones read pins in `_envelope`
        return {}, {}

    def _resolve_decision(self, facts: _Facts, to_state: EffectGrantState) -> None:
        """EF-5 closes an UNKNOWN_OUTCOME, and §14/GR-14 require a `decision_ref` that RESOLVES to an
        authenticated human decision (or an ACTIVE rule) — never a timer and never silence. The
        resolver is M1's, imported rather than re-written: two implementations of "does this
        decision_ref resolve" is two places for one of them to start accepting the string "done".

        A `LaterObservationProves` resolution (deterministic, our commit_key in the external record —
        V7) needs no human decision_ref; it carries the observation reference as its decision_ref.
        """
        ref = str(facts.decision_ref or "").strip()
        if not ref:
            raise GuardNotSatisfied(
                "EF-5 requires a decision_ref: an UNKNOWN_OUTCOME resolves ONLY by an authenticated "
                "human determination or a later deterministic proof, never by a timer and never by "
                "silence (GR-6, GR-14).")
        kind = str(facts.decision_ref_kind or "").strip()
        if kind:
            try:
                resolve_decision_ref(self._conn, tenant=self._tenant, ref=ref, kind=kind)
            except DecisionRefUnresolvable as exc:
                raise GuardNotSatisfied(
                    f"EF-5's decision_ref {ref!r} does not resolve: {exc}") from exc

    # --- the strict-order consumer (P6-D24, P6-D11) ----------------------------------------------

    def reference_resolver(self, aggregate_type: str, aggregate_id: str) -> bool:
        """Does the referenced thing exist yet, FOR THIS TENANT? M-26's question, tenant-scoped.

        ### THE ONLY AGGREGATE THIS CONSUMER AWAITS IS THE GRANT ITSELF. An `effect_grant` event
        carries the grant's SD-3 `entity_versions` — decision PINS on business entities (a load, a
        document), which the inbox derives as `type:id` references when the consumer passes no
        explicit `requires` (as `_drain_for` does). Those entities are NOT aggregates this machine
        blocks on: they were revalidated live at the checkpoint that minted the grant (kernel step 5),
        so a consumer that parked until "load:4471" appeared as an inbox aggregate would wait for
        something that will never arrive there, and a legitimately drained verification would re-park
        forever. So the grant is resolved by existence; any OTHER referent on an effect_grant event is
        a settled decision pin and resolves True — the parking gate M3 needs is the version gap and
        the missing GRANT, both of which still fire.
        """
        if aggregate_type != AGGREGATE_TYPE:
            return True
        return self._conn.execute(
            "SELECT 1 FROM effect_grants WHERE tenant = ? AND grant_id = ?",
            (self._tenant, aggregate_id),
        ).fetchone() is not None

    def consume(
        self,
        envelope: EventEnvelope,
        *,
        grant_id: str | None = None,
        inbox: DedupInbox | None = None,
        accountable_owner_id: str | None = None,
        drain: bool = True,
    ) -> ConsumedTransition:
        """Consume one canonical `effect_grant` event, idempotently, through P5's dedup inbox.

        ### THE DRIVING TRIGGER AND THE FACTS COME FROM THE EVENT ITSELF, NEVER FROM THE CALL.
        The event IS the durable record of a transition, so consuming it ADVANCES the ledger's outcome
        state to match — the guards re-run (a verified readback still has to match the approved
        fingerprint), and nothing new is emitted (the event already exists; re-emitting it would be a
        second copy of one fact). An event that names no M3 transition, or whose transition is not
        legal from the current state (an audit marker, an already-applied event, an F14
        `IllegalTransitionAttempted` riding the stream), is a CURSOR ADVANCE and nothing else — which
        is exactly how a strict consumer consumes the COMPLETE stream (P6-D11) instead of a family
        subset.

        ### THE IDEMPOTENCY IS NOT REIMPLEMENTED HERE. GR-4's mechanism is
        `(tenant, consumer_id, event_id)` in `event_inbox`, and `DedupInbox.consume` owns the one
        commit that carries both the handler's writes and the inbox row (M-24). A redelivered event is
        a no-op because the inbox says so — so a second delivery performs no second effect.

        ### AN EVENT FOR A GRANT THAT DOES NOT EXIST YET, OR WHOSE PREDECESSOR IS UNAPPLIED, PARKS
        (M-26, P6-D11). `effect_grant` is STRICT-ORDER, and strict order is ORDER, not CONTIGUITY: the
        inbox blocks on an *unapplied predecessor* declared by `previous_aggregate_version`, not on an
        absent version.

        ### AND IT SUPPLIES `drain_handler_for` (P6-D24). M3 is the first strict consumer. Without a
        drain factory a parked cohort leaves the park only by M-26 expiry; with it, an event unblocked
        by this apply is released the moment its predecessor lands — released as ITSELF, through the
        handler derived from ITS OWN envelope, never through this call's handler.
        """
        target_id = grant_id or envelope.aggregate_id
        box = inbox or DedupInbox(
            self._conn, tenant=self._tenant, consumer_id=CONSUMER_ID, clock=self._clock,
            reference_resolver=self.reference_resolver,
        )
        outcome: dict[str, Any] = {"transition": None, "refusal": None, "refusal_kind": None,
                                   "illegal_record": None}

        def handler(event: EventEnvelope) -> None:
            grant = self.get(event.aggregate_id)
            if grant is None:
                # Unreachable while the reference resolver is set (the inbox parks a missing grant
                # first). Refused as an OUTCOME, never raised — raising rolls the inbox receipt back
                # and loops the event forever.
                outcome["refusal"], outcome["refusal_kind"] = (
                    f"{event.event_name} references effect grant {event.aggregate_id!r}, which does "
                    f"not exist for tenant {self._tenant!r}. Consumed once, nothing persisted.",
                    "NOT_CONSUMABLE")
                return
            trig = _EVENT_TO_TRIGGER.get(event.event_name)
            if trig is None or not legal_transitions(grant.state, trig):
                # A marker, an already-applied event, or an event whose transition is not legal from
                # here: consume it to advance the cursor over the COMPLETE stream, change nothing.
                return
            facts = _Facts(**_split_facts(_payload_facts(event)))
            try:
                outcome["transition"] = self._apply_locked(
                    grant, trig, actor_type=event.actor_type, actor_id=event.actor_id,
                    correlation_id=event.correlation_id, causation_id=event.event_id,
                    trace_id=event.trace_id, event_id=None, facts=facts, emit=False)
            except GuardNotSatisfied as exc:
                outcome["refusal"], outcome["refusal_kind"] = str(exc), "GUARD"

        # P6-D24: a factory from a parked envelope to the handler for THAT envelope. The invariant is
        # that event E is consumed only through semantics derived from E — the handler above already
        # reads everything it needs off `event`, so ONE handler serves both the direct call and the
        # drain, and a drained event is applied through its own semantics by construction.
        result = box.consume(
            envelope, handler,
            requires=((AGGREGATE_TYPE, target_id),),
            requires_existing=((AGGREGATE_TYPE, target_id),),
            accountable_owner_id=(accountable_owner_id or envelope.accountable_owner_id),
            drain_handler_for=((lambda _parked: handler) if drain else None),
        )
        return ConsumedTransition(
            consume=result, transition=outcome["transition"], refusal=outcome["refusal"],
            refusal_kind=outcome["refusal_kind"], illegal_record=outcome["illegal_record"])

    # --- illegal-transition recording -------------------------------------------------------------

    def _record_illegal(
        self, grant: EffectGrant, trigger: Trigger, *, actor_type: str, actor_id: str,
        correlation_id: str | None, causation_id: str | None, trace_id: str | None, attempt_id: str,
    ) -> IllegalAttemptRecord:
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            record = self._record_illegal_locked(
                grant, trigger, actor_type=actor_type, actor_id=actor_id,
                correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                attempt_id=attempt_id)
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        return record

    def _record_illegal_locked(
        self, grant: EffectGrant, trigger: Trigger, *, actor_type: str, actor_id: str,
        correlation_id: str | None, causation_id: str | None, trace_id: str | None, attempt_id: str,
    ) -> IllegalAttemptRecord:
        """GR-1 / [C-4]: `IllegalTransitionAttempted` to the outbox AND `security_events`, one commit.

        The identity is §4's transition-natural key plus the attempt id, because an illegal transition
        advances no version and every hostile attempt against one grant at one version would otherwise
        collide on one `idempotency_identity` — the poison-loop defect. The event RIDES the current
        version rather than advancing it: `IllegalTransitionAttempted` is non-strict (its contract
        declares no strict order), so it may share the top version without tripping the
        strict-version-owner guard, and it must NOT open a new strict-stream slot that a consumer
        would then have to traverse.
        """
        version = max(1, self._outbox().last_emitted_version(AGGREGATE_TYPE, grant.grant_id))
        identity = (f"{ILLEGAL_ATTEMPT_IDENTITY_PREFIX}|{self._tenant}|{AGGREGATE_TYPE}"
                    f"|{grant.grant_id}|{version}|{trigger.value}|{attempt_id}")
        existing = self._conn.execute(
            "SELECT event_id FROM event_outbox WHERE tenant = ? AND idempotency_identity = ?",
            (self._tenant, identity),
        ).fetchone()
        if existing is not None:
            return IllegalAttemptRecord(
                event_id=existing["event_id"], idempotency_identity=identity, already_recorded=True)
        now = format_instant(self._clock())
        envelope = self._envelope(
            event_name="IllegalTransitionAttempted", transition_id=ILLEGAL_TRANSITION_PRODUCER,
            grant=grant, aggregate_version=version, actor_type=actor_type, actor_id=actor_id,
            payload={"machine": "M3", "state": grant.state.value, "trigger": trigger.value,
                     "attempted_by": actor_id},
            correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
            event_id=None, now=now, idempotency_identity=identity)
        self._outbox().emit(envelope)
        try:
            self._store_security_event(envelope, actor_id)
        except Exception:  # noqa: BLE001 — the outbox record is the audit; a security-store hiccup
            pass           # must not turn a refusal into a crash inside the inbox transaction.
        return IllegalAttemptRecord(
            event_id=envelope.event_id, idempotency_identity=identity, already_recorded=False)

    def _store_security_event(self, envelope: EventEnvelope, actor_id: str) -> None:
        # `security_events.id` is a per-tenant assigned key, not an autoincrement — the same shape
        # `WorkflowStore.add_security_event` writes, computed here so M3 needs no store handle.
        next_id = self._conn.execute(
            "SELECT COALESCE(MAX(id), 0) + 1 FROM security_events WHERE tenant = ?",
            (self._tenant,),
        ).fetchone()[0]
        self._conn.execute(
            "INSERT INTO security_events (tenant, id, event_type, actor, payload_json, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (self._tenant, next_id, "IllegalTransitionAttempted", actor_id,
             json.dumps(envelope.payload, sort_keys=True), format_instant(self._clock())),
        )

    # --- helpers ----------------------------------------------------------------------------------

    def _require_active_human(self, owner_id: str | None, transition_id: str) -> str:
        text = str(owner_id or "").strip()
        if not text:
            raise OwnershipRefused(
                f"{transition_id} reaches UNKNOWN_OUTCOME, which is human-owned (§9), and names no "
                f"accountable human. Every open obligation has exactly one (rule 13); refused with "
                f"nothing written. Supply `accountable_owner_id`.")
        row = self._conn.execute(
            "SELECT state FROM tenant_humans WHERE tenant = ? AND human_id = ?",
            (self._tenant, text),
        ).fetchone()
        if row is None or row["state"] != "ACTIVE":
            raise OwnershipRefused(
                f"{transition_id} would own an UNKNOWN_OUTCOME on {text!r}, who is not an ACTIVE "
                f"recorded human of {self._tenant!r}. An owner nobody agreed to be is an owner "
                f"nobody owes (rule 13, M-35).")
        return text

    def _next_version(self, grant_id: str, *, precomputed: list[str] | None = None) -> int:
        """The next `aggregate_version` for this grant's strict-order stream: one above the highest
        already emitted. Derived from the outbox's own record, never a counter this machine keeps.

        `precomputed` lets EF-2's two events (and any co-emitted siblings) share ONE version: once the
        first event of a transition has been emitted, the rest ride at the SAME version (same producer
        transition — the strict-version-owner trigger allows that), so the second call returns the
        version the first already claimed rather than one above it.
        """
        last = self._outbox().last_emitted_version(AGGREGATE_TYPE, grant_id)
        if precomputed:
            return last  # the sibling already emitted at `last`; ride the same version
        return last + 1

    def _outbox(self) -> TransactionalOutbox:
        return TransactionalOutbox(self._conn, tenant=self._tenant, clock=self._clock)

    def _envelope(
        self,
        *,
        event_name: str,
        transition_id: str,
        grant: EffectGrant,
        aggregate_version: int,
        actor_type: str,
        actor_id: str,
        payload: Mapping[str, Any],
        correlation_id: str | None,
        causation_id: str | None,
        trace_id: str | None,
        event_id: str | None,
        now: str,
        consequential: bool = False,
        idempotency_identity: str | None = None,
        accountable_owner_id: str | None = None,
    ) -> EventEnvelope:
        """One canonical envelope on the `effect_grant` aggregate.

        ### `previous_aggregate_version` TRAVELS ON EVERY ONE, WHICH IS WHY THIS FACTORY IS THE ONLY
        PLACE THIS MACHINE BUILDS AN ENVELOPE (P6-D11). `effect_grant` is STRICT-ORDER, and EF-2f's
        `ClaimRefused` and GR-1's `IllegalTransitionAttempted` ride the stream without a state change,
        so the version sequence is NOT contiguous by design. Declaring the predecessor is what makes
        an intentional non-emission legible as nothing rather than as a loss. Derived from the
        outbox's own emitted record, and `emit` re-derives it and REFUSES a mismatch — so it cannot
        become a lie about what was emitted.

        A CONSEQUENTIAL event additionally pins the decision context §5 requires (`entity_versions`,
        `policy_version`, `brake_version`, and the fingerprint), read from the grant the mint pinned.
        """
        pins = grant.pins() if consequential else {}
        return EventEnvelope(
            event_id=event_id or str(uuid.uuid4()),
            event_name=event_name,
            event_version=CONTRACTS[event_name].current_version,
            occurred_at=now,
            recorded_at=now,
            tenant_id=self._tenant,
            aggregate_type=AGGREGATE_TYPE,
            aggregate_id=grant.grant_id,
            aggregate_version=aggregate_version,
            previous_aggregate_version=self._outbox().last_emitted_version(
                AGGREGATE_TYPE, grant.grant_id, below=aggregate_version),
            causation_id=causation_id,
            correlation_id=correlation_id or grant.commit_key,
            producer_component=self._component,
            producer_transition_id=transition_id,
            actor_type=actor_type,
            actor_id=actor_id,
            trace_id=trace_id or f"trace-{grant.grant_id}",
            payload=dict(payload),
            pipeline_instance_id=grant.pipeline_instance_id,
            accountable_owner_id=accountable_owner_id,
            idempotency_identity=idempotency_identity,
            entity_versions=(pins.get("entity_versions") if consequential else None),
            policy_version=(pins.get("policy_version") if consequential else None),
            brake_version=(pins.get("brake_version") if consequential else None),
            material_facts_fingerprint=(
                pins.get("material_facts_fingerprint") if consequential else None),
        )


# ------------------------------------------------------------------------------------- plumbing

_EVENT_TO_TRIGGER: Mapping[str, Trigger] = {
    "EffectExecuted": Trigger.ADAPTER_RETURNED,
    "EffectFailed": Trigger.ADAPTER_REJECTED_PRE_FLIGHT,
    "OutcomeUnknown": Trigger.ADAPTER_TIMED_OUT,
    "EffectVerified": Trigger.READBACK_MATCHED,
    "VerificationConflict": Trigger.READBACK_CONFLICTING,
    "VerificationUnavailable": Trigger.READBACK_UNAVAILABLE,
    "RealityEstablished": Trigger.HUMAN_ESTABLISHED_REALITY,
}


def _payload_facts(envelope: EventEnvelope) -> dict[str, Any]:
    """The facts a drained event carries in its own payload, so it is applied through semantics
    derived from itself (P6-D24) rather than from the call that unblocked it."""
    payload = dict(envelope.payload)
    facts: dict[str, Any] = {}
    for key in ("failure_proof", "exposure", "unknown_reason", "matched_fingerprint",
                "health_signal", "channel", "outcome", "decision_ref"):
        if key in payload:
            facts[key] = payload[key]
    if envelope.accountable_owner_id:
        facts["accountable_owner_id"] = envelope.accountable_owner_id
    return facts


def _required(value: Any, field_name: str) -> Any:
    text = value if not isinstance(value, str) else value.strip()
    if not text:
        raise GuardNotSatisfied(
            f"{field_name} is required by the event contract and was not supplied.")
    return value


def _prune(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Drop absent OPTIONAL fields. `null` and absent are different facts inside a payload (`ev_v1`)."""
    return {k: v for k, v in payload.items() if v is not None}


_FACT_NAMES = frozenset(_Facts.__dataclass_fields__) - {"extra"}


def _split_facts(facts: Mapping[str, Any]) -> dict[str, Any]:
    known = {k: v for k, v in facts.items() if k in _FACT_NAMES}
    extra = {k: v for k, v in facts.items() if k not in _FACT_NAMES}
    if extra:
        known["extra"] = extra
    return known


def _row_to_grant(row: Any) -> EffectGrant:
    keys = row.keys() if hasattr(row, "keys") else ()

    def col(name: str) -> Any:
        return row[name] if name in keys else None

    return EffectGrant(
        tenant=row["tenant"], grant_id=row["grant_id"], commit_key=row["commit_key"],
        state=EffectGrantState(row["state"]), action_class=row["action_class"],
        target_system=row["target_system"], target_resource_id=row["target_resource_id"],
        target_operation=row["target_operation"], checkpoint_id=col("checkpoint_id"),
        pipeline_instance_id=col("pipeline_instance_id"),
        material_facts_fingerprint=col("material_facts_fingerprint"),
        entity_versions_json=col("entity_versions_json"), policy_version=col("policy_version"),
        brake_version=col("brake_version"), approval_id=col("approval_id"),
        expires_at=col("expires_at"), claimed_at=col("claimed_at"),
        attempted_at=col("attempted_at"), verified_at=col("verified_at"),
        verification_outcome=col("verification_outcome"), unknown_reason=col("unknown_reason"),
        failure_proof=col("failure_proof"), exposure=col("exposure"),
        health_signal=col("health_signal"), reality_decision_ref=col("reality_decision_ref"),
    )


# Re-exported so a caller reads one name rather than importing the migration for a constant.
STATES: tuple[str, ...] = EF_STATES
TERMINAL: tuple[str, ...] = EF_TERMINAL_STATES
HUMAN_OWNED: tuple[str, ...] = EF_HUMAN_OWNED_STATES
RECOVERABLE: tuple[str, ...] = EF_RECOVERABLE_STATES
