"""Machine M6 — the Identity Binding Claim: one `identity_binding_claims` row that makes identity a
first-class, evidenced, correctable, escalatable DECISION and never a silent guess.

    ### AN IDENTITY BINDING CLAIM IS A CLAIM THAT ARTIFACT X BELONGS TO ENTITY Y. IT IS EVIDENCED,
    ### CORRECTABLE AND ESCALATABLE. IT IS NOT AN OBSERVATION, NOT A FACT, NOT AUTHORITY, NOT A
    ### CARGO/FREIGHT `Claim`, AND NOT SOMETHING A MODEL MAY CONFIRM (entity §2/§4, ADR-007 §2/§3).

    ### SD-6 — `provenance_class` IS A DETERMINISTIC, IMMUTABLE FUNCTION OF `match_method`, computed
    ### ONCE at creation and never independently edited (entity §13, ADR-002 §2.3). This module never
    ### accepts a `provenance_class` argument: it DERIVES it from `match_method`, so a caller cannot
    ### choose it and inbound content cannot set it (M-13, R-P1). The database CHECK is the derivation
    ### verbatim, and the immutability trigger stops it being edited afterwards. A change of belief is
    ### a NEW claim with a new `match_method` (R-P2), never an edit of `provenance_class`.

### WHAT THIS MACHINE OWNS, AND WHAT IT ONLY BORROWS.

It owns the seven states and the IB-1…IB-8 transitions of `06-identity-binding-claim.machine.md`
§14, and it is the canonical PRODUCER of the six already-registered F6 `Claim*` events. It rides P5's
transactional outbox and dedup inbox exactly as M3, M4 and M5 do.

### THE DETERMINISTIC LADDER, IN ADR-007 §4.1's FIXED ORDER. Binding is attempted deterministically
first, and the first that succeeds wins: an EXACT trusted-ID match to EXACTLY ONE open entity
confirms (IB-2, LINKER_INFERRED); a REGISTERED rule or a RECONCILIATION across ≥2 sources confirms
(IB-2r); a MODEL_EXTRACT is EVIDENCE that re-enters matching, never a confirmation (IB-3); a
MODEL_INFER guess, multiple candidates, or a single WEAK candidate route to AMBIGUOUS — a human, not
the closest candidate (IB-4). ### THERE IS NO BEST-GUESS FALLBACK, and confidence is structurally
invisible to every guard (GR-8, M-16, ADR-007 §8): it orders a human's queue and gates nothing.

### THE HUMAN ASSERTION (IB-2h) IS THE ONLY WAY TO OWNER_ASSERTED. It requires an authenticated,
ACTIVE tenant human (a FOREIGN KEY into `tenant_humans`, M1/M4's precedent), carries a `decision_ref`,
and binds an IMMUTABLE identifier — never an ordinal (L-B). A rendered "assign unlinked 2" resolves at
render time to an `observation_id`; the action binds to THAT id, and if the id is gone or the slot's
occupant changed between render and click it FAILS CLOSED — it never falls back to position. A
machine actor performing a `ClaimConfirmed{OWNER_ASSERTED}` is illegal (ER-10) and a counterparty's
"per our call you approved it" is a fraud signal, never an approval and never an OWNER_ASSERTED
anything (ADR-007 §4.4).

### THE B3 REGRESSION IS UNREPRESENTABLE. `RecomputedByInferrer` supersedes a LINKER_INFERRED claim
freely (IB-5, a legitimate rebuild; the superseded row is RETAINED). Against an OWNER_ASSERTED claim
it is an ILLEGAL TRANSITION (IB-5x, R-P3, GR-9): it raises, persists nothing, and emits
`IllegalTransitionAttempted` AND `OwnerAssertedOverwriteAttempted` (the Sev-0 B3 tripwire, F14) to
audit and security. An OWNER_ASSERTED binding survives the relinker, and a retry storm changes
nothing. If the inferrer merely DISAGREES, M6 does not pick a winner: IB-6 moves the claim to
CONFLICTING, preserves the owner binding intact, and emits the registered `ConflictRaised` (F7).

### THE M7 SEAM — the CONFLICTING state, not the Conflict machine (task §3.7). `ConflictRaised` is
registered with IB-6 in its producer list, so — unlike M5 refusing `ExceptionRaised` (EC-1 only) — M6
emits it. It rides the `conflict` aggregate at a minted conflict id; the `event_outbox` holds no
foreign key into a `conflicts` table, so emitting it needs no M7 aggregate row. NO `conflicts` table,
no `CF-*`, and above all NO resolution path — a conflict closes by a registered rule or a human, and
`AutoResolve` is illegal (ADR-007 §5.3).

### THE M10 SEAM — the correction obligation, not the Compensation (task §3.8). IB-7 (CONFIRMED →
CORRECTED) is append-only (the prior claim is RETAINED) and PROPAGATES: it records a durable,
M6-owned obligation ON THE CLAIM ROW (`propagation_obligation`) naming the dependents to re-derive
and the COMPLETED effects that rested on the wrong binding and therefore need a Compensation. It
NAMES them; nothing silently drops or closes it, and NO Compensation is fabricated as completed. NO
`compensations` table, no `CM-*`, no `CompensationRequired`, and no unregistered event name — M6-AQ-1
is reported, not closed (task §3.9). Correction-of-correction re-runs propagation.

### THE F14 TRIPWIRES THAT ARE MINE (task §3.10). `IllegalTransitionAttempted` (GR-1, mandatory) and
`OwnerAssertedOverwriteAttempted` (the B3 tripwire, F14 names M6 its sole producer). A counterparty
self-authorization is `CounterpartySelfAuthorizationDetected` (F14 names M4/M6). ### NOT mine:
`ProvenanceStrengtheningAttempted` — CURRENT.md scopes its emission half to Implementation Phase 7,
exactly as M5 handled it. The laundering REFUSAL is mandatory and present now; the F14 emission is
not.

### IT SHIPS DARK. Nothing under `src/freight_recon/` imports this module; the only script that may is
`scripts/probe_phase6_identity_binding_claim.py`. It joins no importer, queue or live channel,
authorizes no effect, and mints no gate decision — a claim may be an INPUT to the checkpoint and can
never MAKE one. The production `GateRegistry` stays EMPTY; the checkpoint stays the one gate authority
and M3 the one effect authority (CLAUDE.md rule 17).
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .event_contracts import CONTRACTS
from .event_envelope import EventEnvelope, format_instant
from .event_inbox import ConsumeResult, DedupInbox
from .migrations.phase6_identity_binding_claims import (
    AMBIGUOUS_REASONS,
    CLAIM_STATES,
    CONFIRMED_ALLOWED_PROVENANCE,
    HUMAN_OWNED_CLAIM_STATES,
    LAUNDERABLE_MODEL_PROVENANCE,
    MATCH_METHODS,
    PROVENANCE_BY_METHOD,
    TERMINAL_CLAIM_STATES,
)
from .tenant import require_tenant

# The aggregate this machine owns.
AGGREGATE_TYPE = "identity_binding_claim"

# The aggregate the co-committed ConflictRaised (IB-6) rides on. M6 emits the registered event but
# builds NO `conflict` table — M7 is not built (task §3.7). The outbox holds no FK into a conflicts
# table, so the event is a durable record at a minted conflict id and needs no M7 aggregate row.
CONFLICT_AGGREGATE_TYPE = "conflict"

# entity §5 — the Identity Service proposes and links.
PRODUCER_COMPONENT = "identity_service"

# The one consumer identity M6 presents to the dedup inbox. Fixed, because the dedup key is
# `(tenant, consumer_id, event_id)` and a renamed consumer would re-arm every duplicate.
CONSUMER_ID = "m6-identity-binding-claim"

# GR-1's producer id for `IllegalTransitionAttempted` — the RULE, not a transition (§3 "‡(any
# machine, GR-1)"). Identical to M1..M5's, for the same reason.
ILLEGAL_TRANSITION_PRODUCER = "GR-1"

# A refusal advances no version; two refusals against one claim at one version would otherwise
# collide on one `idempotency_identity` — the poison-loop defect M1 shipped. Applied here.
ILLEGAL_ATTEMPT_IDENTITY_PREFIX = "ita_v1"
OWNER_OVERWRITE_IDENTITY_PREFIX = "oao_v1"
FRAUD_IDENTITY_PREFIX = "csad_v1"

HUMAN = "HUMAN"
OWNER_ASSERTED = "OWNER_ASSERTED"
MODEL_EXTRACTED = "MODEL_EXTRACTED"

# ### M6-AQ-2 (task §3.9): entity §16's CHECK requires LINKER_INFERRED/RECONCILED to carry a rule_id.
# This machine keeps the CHECK and, for the deterministic mechanisms that carry no customer rule
# (exact-trusted-ID match, reconciliation), supplies a BUILT-IN mechanism id. That honours the CHECK
# WITHOUT inventing a freight identity rule — V4 stays open, and no MC+date+amount / BOL / PRO rule is
# defined here. The alternative reading (IB-2 carries no rule_id, ADR-007 §4.1 step 1) is REPORTED.
EXACT_ID_RULE = "rule:builtin-exact-trusted-id"
RECONCILIATION_RULE = "rule:builtin-reconciliation"


class M6Error(RuntimeError):
    """This machine will not do what was asked. Never degraded into a partial transition."""


class UnknownClaim(M6Error):
    """No `identity_binding_claims` row with this id exists FOR THIS TENANT. Indistinguishable from
    "belongs to another tenant" on purpose — [C-1] rejects a cross-tenant question."""


class GuardNotSatisfied(M6Error):
    """The (state, trigger) pair IS legal here and a precondition is false. No event is emitted."""


class IllegalTransition(M6Error):
    """GR-1 / [C-4]. The (state, trigger) pair is not enumerated (or §15 forbids the shape). Raised
    AFTER `IllegalTransitionAttempted` is recorded, which is the point of recording it."""


class StateConflict(M6Error):
    """A state-guarded UPDATE matched zero rows: the claim moved under us (GR-3). Reload."""


class OwnerAssertedOverwrite(IllegalTransition):
    """IB-5x, the B3 regression. A machine tried to recompute an OWNER_ASSERTED binding. Raised after
    `IllegalTransitionAttempted` AND `OwnerAssertedOverwriteAttempted` are recorded."""


class ContentSetProvenance(M6Error):
    """### INBOUND CONTENT CANNOT CHOOSE ITS OWN PROVENANCE (M-13, R-P1). Raised when a caller tries
    to carry a `provenance_class` in content — provenance is runtime-assigned, derived from
    match_method, never carried in content."""


class FailClosed(M6Error):
    """### AN ORDINAL WHOSE IMMUTABLE ID CANNOT BE PROVEN FAILS CLOSED (L-B). The observation the
    ordinal resolved to is gone, or the slot's occupant changed between render and click. The action
    never falls back to position."""


class ForgedEvidence(M6Error):
    """A `MODEL_EXTRACTED` claim's evidence span could not be proven against the retained artifact."""


# --------------------------------------------------------------------------------- the state set

class ClaimState(str, Enum):
    PROPOSED = "PROPOSED"
    CONFIRMED = "CONFIRMED"
    AMBIGUOUS = "AMBIGUOUS"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    CORRECTED = "CORRECTED"
    CONFLICTING = "CONFLICTING"


class MatchMethod(str, Enum):
    EXACT_ID = "EXACT_ID"
    RULE = "RULE"
    RECONCILIATION = "RECONCILIATION"
    MODEL_EXTRACT = "MODEL_EXTRACT"
    MODEL_INFER = "MODEL_INFER"
    HUMAN = "HUMAN"


class Trigger(str, Enum):
    """The closed set of driving facts, named from §14's triggers and §33's "Consumes"."""

    DETERMINISTIC_MATCH = "DeterministicMatch"          # IB-2 / IB-2r
    HUMAN_ASSERTED = "HumanAsserted"                     # IB-2h
    MODEL_READ_ARTIFACT = "ModelReadItOffAnArtifact"     # IB-3
    MODEL_GUESSED = "ModelGuessed"                        # IB-4
    MULTIPLE_CANDIDATES = "MultipleCandidates"           # IB-4
    SINGLE_WEAK_CANDIDATE = "SingleWeakCandidate"        # IB-4
    RECOMPUTED_BY_INFERRER = "RecomputedByInferrer"      # IB-5 / IB-5x
    INFERRER_DISAGREES = "InferrerDisagrees"             # IB-6
    HUMAN_CORRECTED = "HumanCorrected"                   # IB-7
    DISPROVEN = "Disproven"                              # IB-8
    ENTITY_CANCELLED = "EntityCancelled"                 # entity §25 (CONFIRMED → SUPERSEDED)


# --------------------------------------------------------------------------- the transition table

@dataclass(frozen=True)
class TransitionRow:
    """One row of §14. Data, so the acceptance battery can enumerate it against the specification."""

    id: str
    from_states: tuple[ClaimState, ...]
    to_state: ClaimState
    trigger: Trigger
    trigger_types: tuple[str, ...]     # S|H|X — registry §1
    event: str                         # the canonical event this transition emits (or the F14 one)
    provenance: tuple[str, ...] = ()   # the provenance(s) this transition's result may carry


TRANSITIONS: tuple[TransitionRow, ...] = (
    TransitionRow("IB-1", (), ClaimState.PROPOSED, Trigger.DETERMINISTIC_MATCH, ("S", "X"),
                  "ClaimProposed"),
    TransitionRow("IB-2", (ClaimState.PROPOSED,), ClaimState.CONFIRMED, Trigger.DETERMINISTIC_MATCH,
                  ("S",), "ClaimConfirmed", ("LINKER_INFERRED",)),
    TransitionRow("IB-2r", (ClaimState.PROPOSED,), ClaimState.CONFIRMED, Trigger.DETERMINISTIC_MATCH,
                  ("S",), "ClaimConfirmed", ("LINKER_INFERRED", "RECONCILED")),
    TransitionRow("IB-2h", (ClaimState.PROPOSED, ClaimState.AMBIGUOUS), ClaimState.CONFIRMED,
                  Trigger.HUMAN_ASSERTED, ("H",), "ClaimConfirmed", ("OWNER_ASSERTED",)),
    TransitionRow("IB-3", (ClaimState.PROPOSED,), ClaimState.PROPOSED, Trigger.MODEL_READ_ARTIFACT,
                  ("S",), "ClaimEvidenced", ("MODEL_EXTRACTED",)),
    TransitionRow("IB-4", (ClaimState.PROPOSED,), ClaimState.AMBIGUOUS, Trigger.MODEL_GUESSED,
                  ("S",), "ClaimAmbiguous"),
    TransitionRow("IB-5", (ClaimState.CONFIRMED,), ClaimState.SUPERSEDED,
                  Trigger.RECOMPUTED_BY_INFERRER, ("S",), "ClaimSuperseded",
                  ("LINKER_INFERRED", "RECONCILED")),
    TransitionRow("IB-6", (ClaimState.CONFIRMED,), ClaimState.CONFLICTING,
                  Trigger.INFERRER_DISAGREES, ("S",), "ConflictRaised", ("OWNER_ASSERTED",)),
    TransitionRow("IB-7", (ClaimState.CONFIRMED,), ClaimState.CORRECTED, Trigger.HUMAN_CORRECTED,
                  ("H",), "ClaimCorrected", ("OWNER_ASSERTED",)),
    TransitionRow("IB-8", (ClaimState.PROPOSED, ClaimState.AMBIGUOUS), ClaimState.REJECTED,
                  Trigger.DISPROVEN, ("H", "S"), "ClaimSuperseded"),
)

TRANSITIONS_BY_ID: Mapping[str, TransitionRow] = {row.id: row for row in TRANSITIONS}

# The six F6 contracts this machine MINTS — exactly the registered set, no seventh `Claim*` name.
PRODUCED_CONTRACTS: frozenset[str] = frozenset(
    ("ClaimProposed", "ClaimConfirmed", "ClaimEvidenced", "ClaimAmbiguous", "ClaimSuperseded",
     "ClaimCorrected"))

TERMINAL_STATES: frozenset[ClaimState] = frozenset(ClaimState(s) for s in TERMINAL_CLAIM_STATES)
HUMAN_OWNED_STATES: frozenset[ClaimState] = frozenset(
    ClaimState(s) for s in HUMAN_OWNED_CLAIM_STATES)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------------------------ the inputs

@dataclass(frozen=True)
class MatchAttempt:
    """The deterministic linker's view of one binding attempt. M6 DERIVES provenance from
    `match_method`; there is NO `provenance_class` field, so a caller cannot choose provenance and
    content cannot set it. Confidence is carried for queue ordering ONLY — no guard reads it."""

    subject_ref: str
    entity_ref: str
    match_method: MatchMethod
    open_entity_count: int = 1        # EXACT_ID: how many OPEN entities the id resolves to
    candidate_count: int = 1          # candidates the matcher saw
    weak: bool = False                # a single WEAK candidate
    rule_id: str | None = None        # a REGISTERED deterministic rule id (RULE)
    rule_registered: bool = True      # whether the rule is registered (an unregistered one may not confirm)
    source_count: int = 1             # RECONCILIATION: agreeing sources (needs ≥2)
    evidence_id: str | None = None    # MODEL_EXTRACT: the retained artifact
    span: str | None = None           # MODEL_EXTRACT: the region within it
    extracted_identifier: str | None = None   # MODEL_EXTRACT: the string the model READ
    confidence: float | None = None   # queue ordering ONLY (GR-8, M-16)
    content: Mapping[str, Any] | None = None   # the raw artifact/observation content, if any

    @property
    def provenance(self) -> str:
        """### PROVENANCE IS DERIVED FROM match_method (SD-6), never chosen."""
        return PROVENANCE_BY_METHOD[self.match_method.value]


@dataclass(frozen=True)
class OrdinalTarget:
    """A rendered "assign unlinked N" action (L-B). `ordinal` is the position the human SAW;
    `resolved_observation_id` is the immutable id it resolved to AT RENDER TIME. The action binds to
    that id, or fails closed — never to whatever now occupies position `ordinal`."""

    ordinal: int
    resolved_observation_id: str


# ------------------------------------------------------------------------------------ the row

@dataclass(frozen=True)
class IdentityBindingClaim:
    """One `identity_binding_claims` row, as the machine reads it."""

    tenant: str
    binding_claim_id: str
    subject_ref: str
    entity_ref: str
    provenance_class: str
    state: ClaimState
    version: int
    match_method: str
    confidence: float | None
    evidence_id: str | None
    span: str | None
    rule_id: str | None
    decision_ref: str | None
    decision_human_id: str | None
    owner_id: str | None
    ambiguous_reason: str | None
    corrected_from: str | None
    superseded_by: str | None
    conflict_id: str | None
    propagation_obligation: str | None

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    @property
    def is_owner_asserted(self) -> bool:
        return self.provenance_class == OWNER_ASSERTED

    def native_projection(self) -> "NativeClaimProjection":
        """### THE SEAM WITH THE CHECKPOINT (task §3.12). Project this claim into the shape checkpoint
        step 4 reads (`checkpoint.NativeClaim`) WITHOUT importing the checkpoint — a claim is an INPUT
        to the gate and never a gate. `status` is ACTIVE only for a live CONFIRMED/CORRECTED binding;
        a CONFLICTING/SUPERSEDED/REJECTED binding blocks (entity §38)."""
        conflicting = self.state is ClaimState.CONFLICTING
        if self.state in (ClaimState.CONFIRMED, ClaimState.CORRECTED):
            status = "ACTIVE"
        elif self.state is ClaimState.SUPERSEDED:
            status = "SUPERSEDED"
        elif self.state is ClaimState.REJECTED:
            status = "RETRACTED"
        else:
            status = self.state.value          # PROPOSED / AMBIGUOUS / CONFLICTING — not ACTIVE
        return NativeClaimProjection(
            claim_id=self.binding_claim_id, status=status, conflicting=conflicting,
            provenance=self.provenance_class)


@dataclass(frozen=True)
class NativeClaimProjection:
    """The four fields `checkpoint.NativeClaim` reads, projected from an M6 claim without importing
    the checkpoint. The probe builds a real `NativeClaim` from these and shows step 4 refuses."""

    claim_id: str
    status: str
    conflicting: bool
    provenance: str


@dataclass(frozen=True)
class TransitionResult:
    transition_id: str
    claim: IdentityBindingClaim
    from_state: ClaimState | None
    to_state: ClaimState
    event_ids: tuple[str, ...] = ()
    event_names: tuple[str, ...] = ()
    conflict_id: str | None = None
    corrected_claim_id: str | None = None


@dataclass(frozen=True)
class ReconstructedClaim:
    """A full-history fold of one claim's event stream — sandboxed, zero authority (GR-11, K-3).

    Every count is of what the REBUILD created, which is always zero: no new claim, no rewritten
    provenance, no new authority, no external effect.
    """

    binding_claim_id: str
    state: ClaimState | None
    provenance_class: str | None
    new_claims: int = 0
    rewritten_provenance: int = 0
    new_authority: int = 0
    external_effects: int = 0


@dataclass(frozen=True)
class ConsumedTransition:
    consume: ConsumeResult
    transition: TransitionResult | None = None
    refusal: str | None = None

    @property
    def moved(self) -> bool:
        return self.transition is not None


# --------------------------------------------------------------------------------- the machine

class M6Machine:
    """M6, on an existing connection, bound to ONE tenant. Bound at construction so a caller cannot
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
            raise M6Error(
                "M6Machine reads columns by name and requires `row_factory = sqlite3.Row`.")
        self._conn = conn
        self._tenant = require_tenant(tenant, context="M6Machine")
        self._clock = clock or _utc_now
        self._component = producer_component

    @property
    def tenant(self) -> str:
        return self._tenant

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    # --- reads -----------------------------------------------------------------------------------

    def get(self, binding_claim_id: str) -> IdentityBindingClaim | None:
        row = self._conn.execute(
            "SELECT * FROM identity_binding_claims WHERE tenant = ? AND binding_claim_id = ?",
            (self._tenant, binding_claim_id),
        ).fetchone()
        return _row_to_claim(row) if row is not None else None

    def require(self, binding_claim_id: str) -> IdentityBindingClaim:
        found = self.get(binding_claim_id)
        if found is None:
            raise UnknownClaim(
                f"no binding claim {binding_claim_id!r} for tenant {self._tenant!r}. This machine "
                f"does not look outside its tenant to find out whether it exists elsewhere ([C-1]).")
        return found

    def confirmed_binding_for(self, subject_ref: str) -> IdentityBindingClaim | None:
        row = self._conn.execute(
            "SELECT * FROM identity_binding_claims WHERE tenant = ? AND subject_ref = ? "
            "AND state = 'CONFIRMED'",
            (self._tenant, subject_ref)).fetchone()
        return _row_to_claim(row) if row is not None else None

    # --- IB-1 / IB-3: propose ---------------------------------------------------------------------

    def propose(
        self,
        attempt: MatchAttempt,
        *,
        binding_claim_id: str | None = None,
        actor_id: str = "identity-linker",
        actor_kind: str = "system",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """IB-1 (a candidate binding) or IB-3 (a MODEL_EXTRACT reading — evidence).

        ### PROVENANCE IS DERIVED, NEVER CHOSEN. `provenance_class = f(match_method)`; there is no
        provenance argument. A MODEL_EXTRACT proposal REQUIRES an evidence span (entity §16/§37) and a
        forged span fails closed; it stays PROPOSED as EVIDENCE — the extracted identifier re-enters
        deterministic matching (a NEW attempt), it never itself confirms. A MODEL_INFER proposal
        carries MODEL_INFERRED provenance and is bound for AMBIGUOUS (never CONFIRMED)."""
        subject = _require_text(attempt.subject_ref, "subject_ref")
        entity = _require_text(attempt.entity_ref, "entity_ref")
        self._reject_provenance_from_content(attempt.content)
        provenance = attempt.provenance
        method = attempt.match_method.value

        rule_id = self._rule_id_for(attempt)
        evidence_id, span = None, None
        if provenance == MODEL_EXTRACTED:
            evidence_id, span = self._require_evidence_span(attempt)
            transition_id, event_name = "IB-3", "ClaimEvidenced"
        else:
            transition_id, event_name = "IB-1", "ClaimProposed"

        claim_id = binding_claim_id or f"ibc-{uuid.uuid4().hex[:16]}"
        now = format_instant(self._clock())
        actor_type = "human" if str(actor_kind).upper() == HUMAN else str(actor_kind).lower()
        payload = self._creation_payload(event_name, subject, entity, method, provenance,
                                         rule_id, evidence_id, span)
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                """
                INSERT INTO identity_binding_claims (
                    tenant, binding_claim_id, subject_ref, entity_ref, provenance_class, state,
                    version, match_method, confidence, evidence_id, span, rule_id, decision_ref,
                    decision_human_id, owner_id, ambiguous_reason, corrected_from, superseded_by,
                    conflict_id, propagation_obligation, created_at, updated_at
                ) VALUES (?,?,?,?,?, 'PROPOSED', 1, ?,?,?,?,?, NULL, NULL, NULL, NULL, NULL, NULL,
                          NULL, NULL, ?, ?)
                """,
                (self._tenant, claim_id, subject, entity, provenance, method, attempt.confidence,
                 evidence_id, span, rule_id, now, now),
            )
            created = self.require(claim_id)
            envelope = self._envelope(
                event_name=event_name, transition_id=transition_id, claim=created,
                aggregate_version=self._next_version(claim_id), actor_type=actor_type,
                actor_id=actor_id, payload=payload, correlation_id=correlation_id,
                causation_id=causation_id, trace_id=trace_id, event_id=event_id, now=now)
            self._outbox().emit(envelope)
            conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        return TransitionResult(
            transition_id=transition_id, claim=created, from_state=None,
            to_state=ClaimState.PROPOSED, event_ids=(envelope.event_id,), event_names=(event_name,))

    # --- IB-2 / IB-2r / IB-4: the deterministic ladder --------------------------------------------

    def resolve(
        self,
        binding_claim_id: str,
        attempt: MatchAttempt,
        *,
        owner_id: str | None = None,
        expected: IdentityBindingClaim | None = None,
        actor_id: str = "identity-linker",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """IB-2/IB-2r (deterministic confirm) or IB-4 (ambiguous) — ADR-007 §4.1's fixed order.

        ### THERE IS NO BEST-GUESS FALLBACK. An EXACT trusted-ID match to EXACTLY ONE open entity
        confirms; a REGISTERED rule or a RECONCILIATION across ≥2 sources confirms. A MODEL_INFER
        guess, multiple candidates, a single WEAK candidate, an exact id resolving to zero-or-many, an
        UNREGISTERED rule, or a single-source reconciliation all route to AMBIGUOUS — a human, not the
        closest candidate. Confidence is never read."""
        claim = expected or self.require(binding_claim_id)
        if claim.state is not ClaimState.PROPOSED:
            raise GuardNotSatisfied(
                f"the deterministic ladder resolves a PROPOSED claim; {binding_claim_id!r} is "
                f"{claim.state.value}.")
        if claim.provenance_class == MODEL_EXTRACTED:
            raise GuardNotSatisfied(
                "a MODEL_EXTRACTED claim is EVIDENCE (IB-3): the extracted identifier re-enters "
                "deterministic matching as a NEW attempt; this claim does not itself confirm.")
        outcome, reason = _classify(attempt)
        if outcome == "CONFIRMED":
            return self._confirm(claim, attempt, transition_id=_confirm_transition(attempt),
                                 actor_type="system", actor_id=actor_id, decision_ref=None,
                                 decision_human_id=None, correlation_id=correlation_id,
                                 causation_id=causation_id, trace_id=trace_id, event_id=event_id)
        # IB-4 → AMBIGUOUS, human-owned.
        owner = self._require_named_human(owner_id, ClaimState.AMBIGUOUS)
        return self._advance(
            claim, "IB-4", ClaimState.AMBIGUOUS, event_name="ClaimAmbiguous",
            payload={"reason": reason}, writes="ambiguous_reason = ?, owner_id = ?",
            write_args=(reason, owner), actor_type="system", actor_id=actor_id,
            correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
            event_id=event_id)

    def link(
        self,
        attempt: MatchAttempt,
        *,
        owner_id: str | None = None,
        binding_claim_id: str | None = None,
        actor_id: str = "identity-linker",
        actor_kind: str = "system",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
    ) -> TransitionResult:
        """Propose then resolve in the deterministic-first order — the linker's whole decision.

        A MODEL_EXTRACT stays at its evidence proposal (IB-3): the extracted identifier re-enters as a
        NEW attempt via `link` again, so `link` never confirms it directly."""
        proposed = self.propose(attempt, binding_claim_id=binding_claim_id, actor_id=actor_id,
                                 actor_kind=actor_kind, correlation_id=correlation_id,
                                 causation_id=causation_id, trace_id=trace_id)
        if attempt.match_method is MatchMethod.MODEL_EXTRACT:
            return proposed
        return self.resolve(proposed.claim.binding_claim_id, attempt, owner_id=owner_id,
                            actor_id=actor_id, correlation_id=correlation_id,
                            causation_id=causation_id, trace_id=trace_id)

    # --- IB-2h: the human assertion ---------------------------------------------------------------

    def assert_human(
        self,
        *,
        entity_ref: str,
        decision_ref: str,
        decision_human_id: str,
        actor_id: str,
        actor_kind: str = "human",
        subject_ref: str | None = None,
        ordinal_target: OrdinalTarget | None = None,
        current_unlinked: Sequence[str] | None = None,
        confidence: float | None = None,
        binding_claim_id: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """IB-2h — ### AN AUTHENTICATED HUMAN, BOUND TO AN IMMUTABLE ID, PRODUCES OWNER_ASSERTED.

        Requires an ACTIVE recorded tenant human (a FK-backed identity, M1/M4's precedent) and a
        `decision_ref`. A machine/model/counterparty actor is illegal AND a fraud signal
        (`CounterpartySelfAuthorizationDetected`) — it never becomes OWNER_ASSERTED. The subject is an
        IMMUTABLE id: a rendered ordinal resolves to an `observation_id` or FAILS CLOSED (L-B), never
        falling back to position."""
        claim_id = binding_claim_id or f"ibc-{uuid.uuid4().hex[:16]}"
        self._require_authenticated_human(
            decision_human_id, actor_kind, actor_id, claimed_action="confirm",
            aggregate_id=claim_id)
        if not str(decision_ref or "").strip():
            raise GuardNotSatisfied(
                "IB-2h carries a decision_ref: an owner assertion the audit cannot point a human at "
                "is not an owner assertion (entity §35).")
        subject = self._resolve_subject(subject_ref, ordinal_target, current_unlinked)
        entity = _require_text(entity_ref, "entity_ref")
        now = format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                """
                INSERT INTO identity_binding_claims (
                    tenant, binding_claim_id, subject_ref, entity_ref, provenance_class, state,
                    version, match_method, confidence, evidence_id, span, rule_id, decision_ref,
                    decision_human_id, owner_id, ambiguous_reason, corrected_from, superseded_by,
                    conflict_id, propagation_obligation, created_at, updated_at
                ) VALUES (?,?,?,?, 'OWNER_ASSERTED', 'CONFIRMED', 1, 'HUMAN', ?, NULL, NULL, NULL,
                          ?, ?, NULL, NULL, NULL, NULL, NULL, NULL, ?, ?)
                """,
                (self._tenant, claim_id, subject, entity, confidence, decision_ref,
                 decision_human_id, now, now),
            )
            created = self.require(claim_id)
            envelope = self._envelope(
                event_name="ClaimConfirmed", transition_id="IB-2h", claim=created,
                aggregate_version=self._next_version(claim_id), actor_type="human",
                actor_id=actor_id,
                payload={"provenance_class": OWNER_ASSERTED, "decision_ref": decision_ref},
                correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                event_id=event_id, now=now)
            self._outbox().emit(envelope)
            conn.commit()
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            raise GuardNotSatisfied(
                f"the human assertion was refused by the database: {exc}. At most one CONFIRMED "
                f"binding per subject (entity §17), and provenance must be the derived function of "
                f"match_method (SD-6).") from exc
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        return TransitionResult(
            transition_id="IB-2h", claim=created, from_state=None, to_state=ClaimState.CONFIRMED,
            event_ids=(envelope.event_id,), event_names=("ClaimConfirmed",))

    # --- IB-5 / IB-5x: the relinker ---------------------------------------------------------------

    def recompute(
        self,
        binding_claim_id: str,
        *,
        superseded_by: str | None = None,
        actor_id: str = "identity-linker",
        actor_kind: str = "system",
        expected: IdentityBindingClaim | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """`RecomputedByInferrer` — IB-5 (a legitimate rebuild) or IB-5x (### THE B3 REGRESSION).

        ### AN OWNER_ASSERTED BINDING SURVIVES THE RELINKER. Against a LINKER_INFERRED/RECONCILED
        claim the inferrer may recompute freely: the claim is SUPERSEDED and the superseded row is
        RETAINED. Against an OWNER_ASSERTED claim it is an ILLEGAL TRANSITION (R-P3, GR-9): it raises,
        persists nothing, and emits `IllegalTransitionAttempted` AND `OwnerAssertedOverwriteAttempted`
        (the Sev-0 B3 tripwire). A retry storm changes nothing — the row does not move."""
        claim = expected or self.require(binding_claim_id)
        if claim.state is not ClaimState.CONFIRMED:
            raise GuardNotSatisfied(
                f"IB-5 recomputes a CONFIRMED binding; {binding_claim_id!r} is {claim.state.value}.")
        if claim.is_owner_asserted:
            # ### IB-5x — the row does NOT move, and BOTH F14 tripwires fire (audit + security).
            self._record_illegal(claim, Trigger.RECOMPUTED_BY_INFERRER, actor_id=actor_id)
            self._record_owner_overwrite(claim, actor_id=actor_id)
            raise OwnerAssertedOverwrite(
                f"IB-5x (GR-9, R-P3, the B3 regression): a machine actor tried to recompute the "
                f"OWNER_ASSERTED binding {binding_claim_id!r}. It raises, persists nothing, and is "
                f"recorded to audit and security. A projection rebuild rebuilds projections, not the "
                f"owner's mind.")
        return self._advance(
            claim, "IB-5", ClaimState.SUPERSEDED, event_name="ClaimSuperseded",
            payload=({"superseded_by": superseded_by} if superseded_by else {}),
            writes=("superseded_by = ?" if superseded_by else ""),
            write_args=((superseded_by,) if superseded_by else ()),
            actor_type="system", actor_id=actor_id, correlation_id=correlation_id,
            causation_id=causation_id, trace_id=trace_id, event_id=event_id)

    # --- IB-6: the inferrer disagrees -------------------------------------------------------------

    def inferrer_disagrees(
        self,
        binding_claim_id: str,
        *,
        disagreeing_entity_ref: str,
        owner_id: str,
        field_name: str = "entity_ref",
        actor_id: str = "identity-linker",
        expected: IdentityBindingClaim | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """IB-6 — ### THE INFERRER DISAGREEING WITH THE OWNER RAISES A CONFLICT, NOT A WINNER.

        The claim moves CONFIRMED → CONFLICTING, the OWNER_ASSERTED binding is PRESERVED intact (the
        disagreeing value is never written), the state is human-owned, and a registered
        `ConflictRaised{kind=INFERRER_VS_OWNER}` (F7) is co-committed on the `conflict` aggregate — M6
        emits it because IB-6 is a registered producer, and it builds no M7 machine (task §3.7).
        Every consequential action on the entity then blocks (ADR-002 C5/C6, checkpoint step 4)."""
        claim = expected or self.require(binding_claim_id)
        if claim.state is not ClaimState.CONFIRMED:
            raise GuardNotSatisfied(
                f"IB-6 acts on a CONFIRMED binding; {binding_claim_id!r} is {claim.state.value}.")
        if not claim.is_owner_asserted:
            raise GuardNotSatisfied(
                "IB-6 is the inferrer disagreeing with an OWNER_ASSERTED binding; a disagreement over "
                "a machine-derived binding is an ordinary recompute (IB-5), not a conflict.")
        owner = self._require_named_human(owner_id, ClaimState.CONFLICTING)
        conflict_id = f"conf-{uuid.uuid4().hex[:16]}"
        now = format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            cursor = conn.execute(
                "UPDATE identity_binding_claims SET state = 'CONFLICTING', version = version + 1, "
                "conflict_id = ?, owner_id = ?, updated_at = ? "
                "WHERE tenant = ? AND binding_claim_id = ? AND state = 'CONFIRMED' AND version = ?",
                (conflict_id, owner, now, self._tenant, claim.binding_claim_id, claim.version))
            if cursor.rowcount != 1:
                raise StateConflict(
                    f"IB-6 matched {cursor.rowcount} rows for {binding_claim_id!r}: it moved under us "
                    f"(GR-3). Reload and decide again.")
            after = self.require(claim.binding_claim_id)
            # ### THE OWNER BINDING IS PRESERVED: entity_ref is untouched, and the CONFIRMED claim
            # merely gains a conflict overlay. The co-committed event rides the conflict aggregate.
            conflict_env = self._conflict_envelope(
                conflict_id=conflict_id, aggregate_version=1, actor_id=actor_id,
                payload={
                    "kind": "INFERRER_VS_OWNER", "entity_ref": claim.entity_ref,
                    "field": field_name, "owner_id": owner,
                    # ### THE PARTIES DESCRIBE THE CONFLICT; they do not ASSERT provenance. The inner
                    # key is `provenance` (not `provenance_class`) precisely so ER-10's owner-provenance
                    # detection does not read this system-emitted description as the event asserting
                    # OWNER_ASSERTED — the event RECORDS that one party's binding is owner-asserted, it
                    # does not claim to BE one (the owner did, at IB-2h).
                    "parties": [
                        {"binding_claim_id": claim.binding_claim_id, "provenance": OWNER_ASSERTED,
                         "entity_ref": claim.entity_ref},
                        {"provenance": "LINKER_INFERRED", "entity_ref": disagreeing_entity_ref},
                    ],
                },
                correlation_id=correlation_id or claim.binding_claim_id,
                causation_id=causation_id, trace_id=trace_id, event_id=event_id, now=now)
            self._outbox().emit(conflict_env)
            conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        return TransitionResult(
            transition_id="IB-6", claim=after, from_state=ClaimState.CONFIRMED,
            to_state=ClaimState.CONFLICTING, event_ids=(conflict_env.event_id,),
            event_names=("ConflictRaised",), conflict_id=conflict_id)

    # --- IB-7: the human correction ---------------------------------------------------------------

    def correct(
        self,
        binding_claim_id: str,
        *,
        new_entity_ref: str,
        decision_ref: str,
        decision_human_id: str,
        actor_id: str,
        actor_kind: str = "human",
        dependent_refs: Sequence[str] = (),
        completed_effects: Sequence[str] = (),
        expected: IdentityBindingClaim | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """IB-7 — ### CONFIRMED → CORRECTED, APPEND-ONLY AND PROPAGATING (ADR-007 §6, GR-12, M-20).

        The prior claim is RETAINED (moved to CORRECTED, never deleted or edited). A NEW OWNER_ASSERTED
        CONFIRMED claim carries the corrected value with `corrected_from` pointing back — so
        correction-of-correction is supported and re-runs propagation. The correction records a
        durable, M6-owned PROPAGATION OBLIGATION naming the dependents to re-derive and the COMPLETED
        effects that rested on the wrong binding and therefore need a Compensation (M10). It names
        them; nothing silently drops or closes it, and NO Compensation is fabricated as completed —
        M10 is not built here (task §3.8)."""
        claim = expected or self.require(binding_claim_id)
        if claim.state is not ClaimState.CONFIRMED:
            raise GuardNotSatisfied(
                f"IB-7 corrects a CONFIRMED binding; {binding_claim_id!r} is {claim.state.value}. "
                f"Correction-of-correction acts on the newly-corrected CONFIRMED claim.")
        self._require_authenticated_human(
            decision_human_id, actor_kind, actor_id, claimed_action="correct",
            aggregate_id=claim.binding_claim_id)
        if not str(decision_ref or "").strip():
            raise GuardNotSatisfied("IB-7 carries a decision_ref (GR-14, ER-7).")
        new_entity = _require_text(new_entity_ref, "new_entity_ref")
        now = format_instant(self._clock())
        # ### THE PROPAGATION OBLIGATION — NAMED, DURABLE, NEVER SILENTLY CLOSED. It records the
        # dependents to re-derive and the completed effects that need a Compensation. No Compensation
        # is fabricated as completed: this is the OBLIGATION, not its discharge.
        obligation = json.dumps({
            "corrected_from_entity": claim.entity_ref,
            "new_entity": new_entity,
            "dependents_to_rederive": list(dependent_refs),
            "completed_effects_needing_compensation": list(completed_effects),
            "compensation_owner": "M10",
            "recorded_at": now,
        }, sort_keys=True)
        new_claim_id = f"ibc-{uuid.uuid4().hex[:16]}"
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            cursor = conn.execute(
                "UPDATE identity_binding_claims SET state = 'CORRECTED', version = version + 1, "
                "propagation_obligation = ?, updated_at = ? "
                "WHERE tenant = ? AND binding_claim_id = ? AND state = 'CONFIRMED' AND version = ?",
                (obligation, now, self._tenant, claim.binding_claim_id, claim.version))
            if cursor.rowcount != 1:
                raise StateConflict(
                    f"IB-7 matched {cursor.rowcount} rows for {binding_claim_id!r}: it moved under "
                    f"us (GR-3).")
            corrected = self.require(claim.binding_claim_id)
            # The corrected value as a NEW OWNER_ASSERTED CONFIRMED claim (append-only lineage).
            conn.execute(
                """
                INSERT INTO identity_binding_claims (
                    tenant, binding_claim_id, subject_ref, entity_ref, provenance_class, state,
                    version, match_method, confidence, evidence_id, span, rule_id, decision_ref,
                    decision_human_id, owner_id, ambiguous_reason, corrected_from, superseded_by,
                    conflict_id, propagation_obligation, created_at, updated_at
                ) VALUES (?,?,?,?, 'OWNER_ASSERTED', 'CONFIRMED', 1, 'HUMAN', NULL, NULL, NULL, NULL,
                          ?, ?, NULL, NULL, ?, NULL, NULL, NULL, ?, ?)
                """,
                (self._tenant, new_claim_id, claim.subject_ref, new_entity, decision_ref,
                 decision_human_id, claim.binding_claim_id, now, now),
            )
            corrected_env = self._envelope(
                event_name="ClaimCorrected", transition_id="IB-7", claim=corrected,
                aggregate_version=self._next_version(claim.binding_claim_id), actor_type="human",
                actor_id=actor_id,
                payload={"decision_ref": decision_ref, "prior": claim.entity_ref, "new": new_entity,
                         "provenance_class": OWNER_ASSERTED},
                correlation_id=correlation_id or claim.binding_claim_id, causation_id=causation_id,
                trace_id=trace_id, event_id=event_id, now=now)
            self._outbox().emit(corrected_env)
            new_claim = self.require(new_claim_id)
            confirm_env = self._envelope(
                event_name="ClaimConfirmed", transition_id="IB-2h", claim=new_claim,
                aggregate_version=self._next_version(new_claim_id), actor_type="human",
                actor_id=actor_id,
                payload={"provenance_class": OWNER_ASSERTED, "decision_ref": decision_ref},
                correlation_id=correlation_id or claim.binding_claim_id, causation_id=causation_id,
                trace_id=trace_id, event_id=None, now=now)
            self._outbox().emit(confirm_env)
            conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        return TransitionResult(
            transition_id="IB-7", claim=corrected, from_state=ClaimState.CONFIRMED,
            to_state=ClaimState.CORRECTED, event_ids=(corrected_env.event_id, confirm_env.event_id),
            event_names=("ClaimCorrected", "ClaimConfirmed"), corrected_claim_id=new_claim_id)

    # --- IB-8 / §25: rejection & cancellation -----------------------------------------------------

    def reject(
        self,
        binding_claim_id: str,
        *,
        reason: str = "disproven",
        actor_id: str = "identity-linker",
        actor_kind: str = "system",
        expected: IdentityBindingClaim | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """IB-8 — a PROPOSED or AMBIGUOUS claim, disproven or its entity cancelled, is REJECTED
        (emitting `ClaimSuperseded`)."""
        claim = expected or self.require(binding_claim_id)
        return self._advance(
            claim, "IB-8", ClaimState.REJECTED, event_name="ClaimSuperseded",
            payload={}, writes="", write_args=(),
            actor_type=("human" if str(actor_kind).upper() == HUMAN else "system"),
            actor_id=actor_id, correlation_id=correlation_id, causation_id=causation_id,
            trace_id=trace_id, event_id=event_id)

    def cancel_entity(
        self,
        binding_claim_id: str,
        *,
        owner_id: str,
        actor_id: str = "reconciliation",
        actor_kind: str = "system",
        expected: IdentityBindingClaim | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """entity §25 — ### A CONFIRMED BINDING ON A CANCELLED ENTITY IS SUPERSEDED, and the subject
        returns to a human. The entity being cancelled is an authoritative external fact, not the
        inferrer second-guessing, so it supersedes ANY provenance (it is not the B3 case). The
        superseded row is RETAINED and names the accountable human for the now-unbound subject."""
        claim = expected or self.require(binding_claim_id)
        if claim.state is not ClaimState.CONFIRMED:
            raise GuardNotSatisfied(
                f"entity cancellation supersedes a CONFIRMED binding; {binding_claim_id!r} is "
                f"{claim.state.value}.")
        owner = self._require_named_human(owner_id, ClaimState.CONFLICTING)
        return self._advance(
            claim, "IB-5", ClaimState.SUPERSEDED, event_name="ClaimSuperseded",
            payload={}, writes="owner_id = ?", write_args=(owner,),
            actor_type=("human" if str(actor_kind).upper() == HUMAN else "system"),
            actor_id=actor_id, correlation_id=correlation_id, causation_id=causation_id,
            trace_id=trace_id, event_id=event_id)

    # --- replay & park/drain ----------------------------------------------------------------------

    def reference_resolver(self, aggregate_type: str, aggregate_id: str) -> bool:
        """M-26's question, tenant-scoped. A reference to a not-yet-existing claim is PARKED.

        ### CORRECTION/SUPERSESSION ARE STRICT (events/registry.md §8): a `ClaimCorrected` arriving
        before its `ClaimConfirmed` is PARKED, not dropped. That is expressed HERE, through the same
        M-26 park/drain mechanism M5 uses — a synthetic `identity_binding_claim_confirmed` reference
        that resolves only once the claim is a live CONFIRMED/CORRECTED binding. No second parking
        mechanism is invented."""
        if aggregate_type == AGGREGATE_TYPE:
            return self._conn.execute(
                "SELECT 1 FROM identity_binding_claims WHERE tenant = ? AND binding_claim_id = ?",
                (self._tenant, aggregate_id)).fetchone() is not None
        if aggregate_type == "identity_binding_claim_confirmed":
            row = self._conn.execute(
                "SELECT state FROM identity_binding_claims WHERE tenant = ? AND binding_claim_id = ?",
                (self._tenant, aggregate_id)).fetchone()
            return row is not None and row["state"] in ("CONFIRMED", "CORRECTED")
        return True

    def consume_event(
        self, envelope: EventEnvelope, *, inbox: DedupInbox | None = None,
        requires_existing: tuple[tuple[str, str], ...] = (), drain: bool = True,
    ) -> ConsumedTransition:
        """Consume one canonical `identity_binding_claim` event idempotently through P5's dedup inbox.

        ### REPLAY CREATES ZERO NEW CLAIMS, ZERO REWRITTEN PROVENANCE, ZERO NEW AUTHORITY AND ZERO
        EXTERNAL EFFECTS (GR-11, K-3). Reconstruction advances an EXISTING durable row's state to
        match the event WITHOUT re-proposing, re-emitting, or any external effect. Every OWNER_ASSERTED
        binding replays byte-identical: the fold never re-derives an owner's decision. Redelivery is a
        no-op (GR-4). A `ClaimCorrected` before its `ClaimConfirmed` is PARKED via the
        `requires_existing` prerequisite and drained the moment the confirmation lands."""
        target_id = envelope.aggregate_id
        box = inbox or DedupInbox(
            self._conn, tenant=self._tenant, consumer_id=CONSUMER_ID, clock=self._clock,
            reference_resolver=self.reference_resolver)
        outcome: dict[str, Any] = {"transition": None, "refusal": None}

        def handler(event: EventEnvelope) -> None:
            claim = self.get(event.aggregate_id)
            if claim is None:
                outcome["refusal"] = (
                    f"{event.event_name} references claim {event.aggregate_id!r}, which does not "
                    f"exist for tenant {self._tenant!r}. Consumed once, nothing persisted.")
                return
            target = _event_target_state(event)
            if target is None or claim.state is target or claim.is_terminal:
                return
            outcome["transition"] = self._reconstruct_locked(claim, event, target)

        default_reqs: tuple[tuple[str, str], ...] = ((AGGREGATE_TYPE, target_id),)
        if envelope.event_name == "ClaimCorrected":
            # ### THE STRICT PREREQUISITE: the correction may apply only once its claim is a live
            # CONFIRMED/CORRECTED binding. Before that it PARKS, not drops (§8, T13).
            default_reqs = ((AGGREGATE_TYPE, target_id),
                            ("identity_binding_claim_confirmed", target_id))
        result = box.consume(
            envelope, handler,
            requires_existing=(requires_existing or default_reqs),
            drain_handler_for=((lambda _env: handler) if drain else None))
        return ConsumedTransition(
            consume=result, transition=outcome["transition"], refusal=outcome["refusal"])

    def rebuild(self, binding_claim_id: str, *,
                events: list[EventEnvelope] | None = None) -> ReconstructedClaim:
        """### A FULL-HISTORY FOLD OF ONE CLAIM — SANDBOXED, ZERO AUTHORITY (GR-11, ER-2).

        It reconstructs state and provenance from the event stream and creates NOTHING: no new claim,
        no rewritten provenance, no new authority, the outside world untouched. An OWNER_ASSERTED
        binding is reproduced byte-identical from the OWNER_ASSERTED event that recorded it — never
        re-derived by the inferrer (ADR-007 §7)."""
        stream = events if events is not None else self._event_stream(binding_claim_id)
        state: ClaimState | None = None
        provenance: str | None = None
        for event in stream:
            target = _event_target_state(event)
            if target is not None:
                state = target
            elif event.event_name in ("ClaimProposed", "ClaimEvidenced") and state is None:
                state = ClaimState.PROPOSED
            # ### PROVENANCE COMES FROM THE POSITIVE EVIDENCE OF THE EVENT, NEVER RE-DERIVED.
            carried = event.payload.get("provenance_class")
            if isinstance(carried, str) and carried:
                provenance = carried
        return ReconstructedClaim(
            binding_claim_id=binding_claim_id, state=state, provenance_class=provenance,
            new_claims=0, rewritten_provenance=0, new_authority=0, external_effects=0)

    # --- shared transition plumbing ---------------------------------------------------------------

    def _confirm(
        self, claim: IdentityBindingClaim, attempt: MatchAttempt, *, transition_id: str,
        actor_type: str, actor_id: str, decision_ref: str | None, decision_human_id: str | None,
        correlation_id: str | None, causation_id: str | None, trace_id: str | None,
        event_id: str | None,
    ) -> TransitionResult:
        """IB-2 / IB-2r — PROPOSED → CONFIRMED. The provenance is already the derived one; the
        one-CONFIRMED-per-subject partial index serializes competing confirmations."""
        payload: dict[str, Any] = {"provenance_class": claim.provenance_class}
        if claim.rule_id:
            payload["rule_id"] = claim.rule_id
        if decision_ref:
            payload["decision_ref"] = decision_ref
        try:
            return self._advance(
                claim, transition_id, ClaimState.CONFIRMED, event_name="ClaimConfirmed",
                payload=payload, writes="", write_args=(), actor_type=actor_type, actor_id=actor_id,
                correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                event_id=event_id)
        except sqlite3.IntegrityError as exc:
            # ### COMPETING CONFIRMATIONS SERIALIZE: the partial UNIQUE index refused this one because
            # another CONFIRMED binding already exists for this subject (entity §17).
            raise GuardNotSatisfied(
                f"a CONFIRMED binding already exists for subject {claim.subject_ref!r} "
                f"(entity §17): at most one CONFIRMED binding per subject. Refused: {exc}.") from exc

    def _advance(
        self, claim: IdentityBindingClaim, transition_id: str, to_state: ClaimState, *,
        event_name: str, payload: Mapping[str, Any], writes: str, write_args: tuple[Any, ...],
        actor_type: str, actor_id: str, correlation_id: str | None, causation_id: str | None,
        trace_id: str | None, event_id: str | None,
    ) -> TransitionResult:
        """One state transition: the state row and its event, or neither (GR-2). OCC on the version
        the decision was read at (GR-3): zero rows is a lost update that raises."""
        row = TRANSITIONS_BY_ID.get(transition_id)
        if row is None or (row.from_states and claim.state not in row.from_states):
            self._record_illegal(claim, row.trigger if row else Trigger.DETERMINISTIC_MATCH,
                                 actor_id=actor_id)
            raise IllegalTransition(
                f"{transition_id} is not legal for a claim in {claim.state.value} (GR-1, [C-4]). No "
                f"state change persisted; `IllegalTransitionAttempted` recorded to audit and "
                f"security.")
        now = format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            set_clause = "state = ?, version = version + 1, updated_at = ?"
            if writes:
                set_clause += ", " + writes
            args: list[Any] = [to_state.value, now, *write_args,
                               self._tenant, claim.binding_claim_id, claim.state.value, claim.version]
            cursor = conn.execute(
                f"UPDATE identity_binding_claims SET {set_clause} "
                f"WHERE tenant = ? AND binding_claim_id = ? AND state = ? AND version = ?",
                args)
            if cursor.rowcount != 1:
                raise StateConflict(
                    f"{transition_id} matched {cursor.rowcount} rows for "
                    f"{claim.binding_claim_id!r}: it moved under us (GR-3). Reload — a lost update on "
                    f"a claim is refused, never a write that silently wins.")
            after = self.require(claim.binding_claim_id)
            envelope = self._envelope(
                event_name=event_name, transition_id=transition_id, claim=after,
                aggregate_version=self._next_version(claim.binding_claim_id), actor_type=actor_type,
                actor_id=actor_id, payload=dict(payload), correlation_id=correlation_id,
                causation_id=causation_id, trace_id=trace_id, event_id=event_id, now=now)
            self._outbox().emit(envelope)
            conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        return TransitionResult(
            transition_id=transition_id, claim=after, from_state=claim.state, to_state=to_state,
            event_ids=(envelope.event_id,), event_names=(event_name,))

    def _reconstruct_locked(
        self, claim: IdentityBindingClaim, event: EventEnvelope, target: ClaimState,
    ) -> TransitionResult:
        """Advance a durable row to match a durable event — reconstruction, not a live transition.

        Runs inside the inbox's own commit (M-24): no BEGIN, no COMMIT. ### IT NEVER REWRITES
        OWNER_ASSERTED PROVENANCE. provenance_class is immutable by trigger and by SD-6, so the fold
        moves only the `state` (and lineage) and re-affirms the SAME provenance the event carries."""
        conn = self._conn
        now = format_instant(self._clock())
        writes = ["state = ?", "version = version + 1", "updated_at = ?"]
        args: list[Any] = [target.value, now]
        if target is ClaimState.SUPERSEDED and event.payload.get("superseded_by"):
            writes.append("superseded_by = ?")
            args.append(event.payload.get("superseded_by"))
        elif target is ClaimState.AMBIGUOUS and event.payload.get("reason"):
            writes.append("ambiguous_reason = ?")
            args.append(event.payload.get("reason"))
        elif target is ClaimState.CORRECTED:
            # ### THE CORRECTED STATE CARRIES ITS OBLIGATION (CHECK). A foreign correction replayed
            # through the inbox reconstructs a minimal obligation from the POSITIVE evidence the event
            # carries (prior/new); the full dependents/effects lived on the originating node's live
            # `correct()` call. The obligation is never silently absent — the CHECK forbids it.
            if claim.propagation_obligation is None:
                writes.append("propagation_obligation = ?")
                args.append(json.dumps({
                    "corrected_from_entity": event.payload.get("prior"),
                    "new_entity": event.payload.get("new"),
                    "dependents_to_rederive": [],
                    "completed_effects_needing_compensation": [],
                    "compensation_owner": "M10",
                    "reconstructed_from_event": True,
                    "recorded_at": now,
                }, sort_keys=True))
        conn.execute(
            f"UPDATE identity_binding_claims SET {', '.join(writes)} "
            f"WHERE tenant = ? AND binding_claim_id = ? AND state = ?",
            (*args, self._tenant, claim.binding_claim_id, claim.state.value))
        after = self.require(claim.binding_claim_id)
        return TransitionResult(
            transition_id="replay", claim=after, from_state=claim.state, to_state=target)

    # --- content / evidence / rule / ordinal / human guards ---------------------------------------

    def _reject_provenance_from_content(self, content: Mapping[str, Any] | None) -> None:
        """### CONTENT CANNOT CHOOSE ITS OWN PROVENANCE (M-13, R-P1). Provenance is derived from
        match_method and runtime-assigned; content that carries a `provenance_class` is inbound data
        trying to strengthen itself. (Refusal half; the F14 `ProvenanceStrengtheningAttempted`
        emission is Implementation Phase 7's, per CURRENT.md — task §3.10.)"""
        if isinstance(content, Mapping) and "provenance_class" in {str(k) for k in content}:
            raise ContentSetProvenance(
                "inbound content carries a `provenance_class`, and provenance is RUNTIME-ASSIGNED and "
                "DERIVED from match_method (SD-6, M-13, R-P1), never set from content. The content is "
                "data; it does not get to say how much it can bear.")

    def _rule_id_for(self, attempt: MatchAttempt) -> str | None:
        """### M6-AQ-2: LINKER_INFERRED/RECONCILED carry a rule_id (entity §16, kept as written). The
        exact-ID match and reconciliation carry a BUILT-IN mechanism id — which honours the CHECK
        without inventing a customer freight rule (V4 stays open)."""
        method = attempt.match_method
        if method is MatchMethod.EXACT_ID:
            return EXACT_ID_RULE
        if method is MatchMethod.RECONCILIATION:
            return RECONCILIATION_RULE
        if method is MatchMethod.RULE:
            return str(attempt.rule_id).strip() if attempt.rule_id else None
        return None

    def _require_evidence_span(self, attempt: MatchAttempt) -> tuple[str, str]:
        """### A MODEL_EXTRACTED CLAIM REQUIRES A NON-FORGED EVIDENCE SPAN (entity §16/§37). The span
        must reference a retained artifact and be a real region; a forged one (no evidence id, an empty
        or malformed span) fails closed — the line between MODEL_EXTRACTED (a human can look) and
        MODEL_INFERRED (nothing to look at)."""
        evidence_id = str(attempt.evidence_id or "").strip()
        span = str(attempt.span or "").strip()
        if not evidence_id or not span:
            raise ForgedEvidence(
                "a MODEL_EXTRACTED claim is EVIDENCE and REQUIRES a non-null evidence_id and span "
                "(entity §16/§37): a claim a human cannot open the document and check is a guess, and "
                "a guess is MODEL_INFERRED, never MODEL_EXTRACTED.")
        if not _looks_like_span(span):
            raise ForgedEvidence(
                f"the evidence span {span!r} is not a real artifact region (expected e.g. `page:1` or "
                f"`0:12` or a coordinate box): a forged span fails closed, it is never accepted as "
                f"evidence.")
        return evidence_id, span

    def _resolve_subject(
        self, subject_ref: str | None, ordinal_target: OrdinalTarget | None,
        current_unlinked: Sequence[str] | None,
    ) -> str:
        """### AN OWNER ASSERTION BINDS AN IMMUTABLE ID, NEVER AN ORDINAL (L-B). A rendered ordinal
        resolves to the `observation_id` it named AT RENDER TIME, and the action binds to THAT id — or
        fails closed if the id is gone or the slot's occupant changed between render and click. It
        never falls back to position."""
        if ordinal_target is not None:
            current = list(current_unlinked or [])
            resolved = ordinal_target.resolved_observation_id
            if resolved not in current:
                raise FailClosed(
                    f"the observation the ordinal resolved to ({resolved!r}) is gone from the "
                    f"unlinked list between render and click: the action FAILS CLOSED and does not "
                    f"fall back to position (L-B).")
            idx = ordinal_target.ordinal - 1
            if idx < 0 or idx >= len(current) or current[idx] != resolved:
                raise FailClosed(
                    f"the occupant of slot {ordinal_target.ordinal} changed between render and click "
                    f"(rendered {resolved!r}, now "
                    f"{current[idx] if 0 <= idx < len(current) else 'nothing'!r}): the action FAILS "
                    f"CLOSED — it binds the immutable id it was shown or nothing, never the new "
                    f"occupant of the slot (L-B).")
            return resolved
        subject = str(subject_ref or "").strip()
        if not subject:
            raise GuardNotSatisfied("IB-2h binds a subject (an observation id or a resolved ordinal).")
        return subject

    def _require_named_human(self, owner_id: str | None, state: ClaimState) -> str:
        """### AMBIGUOUS / CONFLICTING IS OWNED BY A NAMED HUMAN (machine §5/§9). "A human" is
        decoration while owner_id is a free-text column: it must be a recorded, ACTIVE human of this
        tenant, FK-backed (M1's argument for owner_id, M5's for UNBOUND)."""
        owner = str(owner_id or "").strip()
        if not owner:
            raise GuardNotSatisfied(
                f"a claim moving to {state.value} names the accountable human who owns it (machine "
                f"§5/§9): '{state.value} without a human owner' is a silent drop wearing a status.")
        human = self._conn.execute(
            "SELECT state FROM tenant_humans WHERE tenant = ? AND human_id = ?",
            (self._tenant, owner)).fetchone()
        if human is None or human["state"] != "ACTIVE":
            raise GuardNotSatisfied(
                f"{state.value} names owner {owner!r}, who is not an ACTIVE recorded human of "
                f"{self._tenant!r}. The owner is FK-backed, not a free-text string.")
        return owner

    def _require_authenticated_human(
        self, decision_human_id: str, actor_kind: str, actor_id: str, *, claimed_action: str,
        aggregate_id: str,
    ) -> None:
        """### ONLY AN AUTHENTICATED, ACTIVE TENANT HUMAN PRODUCES OWNER_ASSERTED (entity §35, ER-10).

        A machine, a model, a counterparty ("per our call you approved it"), a document, a confidence
        score — each is MODEL_EXTRACTED at best and a fraud signal, never an OWNER_ASSERTED anything,
        and no evidence can promote one. A non-human attempt is an ILLEGAL transition AND a Sev-0
        `CounterpartySelfAuthorizationDetected`. A wrong-tenant / inactive / forged human fails
        closed."""
        text = str(decision_human_id or "").strip()
        if str(actor_kind).upper() != HUMAN:
            self._record_fraud(aggregate_id, actor_id=text or actor_id or "(none)",
                               actor_kind=actor_kind, claimed_action=claimed_action)
            raise IllegalTransition(
                f"{claimed_action} requires an authenticated HUMAN (ADR-003, permanent; ER-10). "
                f"actor_kind={actor_kind!r} cannot assert an identity binding — a model, a "
                f"counterparty's 'per our call you approved this', a document and a confidence score "
                f"are each MODEL_EXTRACTED at best and a fraud signal, never OWNER_ASSERTED, and no "
                f"evidence can promote one.")
        if not text:
            raise GuardNotSatisfied(
                "an OWNER_ASSERTED assertion names the human behind decision_ref, FK-backed into "
                "tenant_humans (entity §35).")
        row = self._conn.execute(
            "SELECT state FROM tenant_humans WHERE tenant = ? AND human_id = ?",
            (self._tenant, text)).fetchone()
        if row is None or row["state"] != "ACTIVE":
            raise GuardNotSatisfied(
                f"{claimed_action} names {text!r}, who is not an ACTIVE recorded human of "
                f"{self._tenant!r}. A forged, inactive or wrong-tenant human fails closed — 'an "
                f"authenticated human' is decoration while decision_human_id is a free-text column.")

    # --- F14 recording ----------------------------------------------------------------------------

    def _record_illegal(self, claim: IdentityBindingClaim, trigger: Trigger, *, actor_id: str) -> None:
        self._record_f14(
            aggregate_id=claim.binding_claim_id, event_name="IllegalTransitionAttempted",
            identity_prefix=ILLEGAL_ATTEMPT_IDENTITY_PREFIX,
            identity_suffix=f"{trigger.value}|{actor_id}",
            payload={"machine": "M6", "state": claim.state.value, "trigger": trigger.value,
                     "attempted_by": actor_id},
            actor_type="system", actor_id=actor_id)

    def _record_owner_overwrite(self, claim: IdentityBindingClaim, *, actor_id: str) -> None:
        """### THE B3 TRIPWIRE (GR-9, F14, Sev-0). F14 names M6 the sole producer of
        `OwnerAssertedOverwriteAttempted`."""
        self._record_f14(
            aggregate_id=claim.binding_claim_id, event_name="OwnerAssertedOverwriteAttempted",
            identity_prefix=OWNER_OVERWRITE_IDENTITY_PREFIX, identity_suffix=actor_id,
            payload={"binding_claim_id": claim.binding_claim_id},
            actor_type="detector", actor_id=actor_id)

    def _record_fraud(self, aggregate_id: str, *, actor_id: str, actor_kind: str,
                      claimed_action: str) -> None:
        """### A COUNTERPARTY SELF-AUTHORIZATION IS A FRAUD SIGNAL, NEVER AN OWNER_ASSERTED (ADR-007
        §4.4, F14 names M4/M6). Records the illegal attempt AND
        `CounterpartySelfAuthorizationDetected`."""
        self._record_f14(
            aggregate_id=aggregate_id, event_name="IllegalTransitionAttempted",
            identity_prefix=ILLEGAL_ATTEMPT_IDENTITY_PREFIX,
            identity_suffix=f"{Trigger.HUMAN_ASSERTED.value}|{actor_id}|{actor_kind}",
            payload={"machine": "M6", "state": "PROPOSED",
                     "trigger": Trigger.HUMAN_ASSERTED.value, "attempted_by": actor_id},
            actor_type="system", actor_id=actor_id)
        self._record_f14(
            aggregate_id=aggregate_id, event_name="CounterpartySelfAuthorizationDetected",
            identity_prefix=FRAUD_IDENTITY_PREFIX, identity_suffix=f"{actor_id}|{actor_kind}",
            payload={"source_observation_id": f"{actor_kind}:{actor_id}",
                     "claimed_action": f"{claimed_action} identity binding"},
            actor_type="detector", actor_id=actor_id)

    def _record_f14(self, *, aggregate_id: str, event_name: str, identity_prefix: str,
                    identity_suffix: str, payload: Mapping[str, Any], actor_type: str,
                    actor_id: str) -> None:
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            version = max(1, self._outbox().last_emitted_version(AGGREGATE_TYPE, aggregate_id))
            identity = (f"{identity_prefix}|{self._tenant}|{AGGREGATE_TYPE}|{aggregate_id}"
                        f"|{version}|{identity_suffix}")
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

    def _event_stream(self, binding_claim_id: str) -> list[EventEnvelope]:
        rows = self._conn.execute(
            "SELECT envelope_json FROM event_outbox WHERE tenant = ? AND aggregate_type = ? "
            "AND aggregate_id = ? ORDER BY aggregate_version, sequence",
            (self._tenant, AGGREGATE_TYPE, binding_claim_id)).fetchall()
        return [EventEnvelope.from_json(r["envelope_json"]) for r in rows]

    def _next_version(self, binding_claim_id: str) -> int:
        return self._outbox().last_emitted_version(AGGREGATE_TYPE, binding_claim_id) + 1

    def _outbox(self):
        from .event_outbox import TransactionalOutbox
        return TransactionalOutbox(self._conn, tenant=self._tenant, clock=self._clock)

    def _creation_payload(self, event_name: str, subject: str, entity: str, method: str,
                          provenance: str, rule_id: str | None, evidence_id: str | None,
                          span: str | None) -> dict[str, Any]:
        if event_name == "ClaimEvidenced":
            return {"provenance_class": provenance, "evidence_ref": evidence_id, "span": span}
        payload: dict[str, Any] = {
            "provenance_class": provenance, "subject_ref": subject, "entity_ref": entity,
            "match_method": method}
        return payload

    def _envelope(
        self, *, event_name: str, transition_id: str, claim: IdentityBindingClaim,
        aggregate_version: int, actor_type: str, actor_id: str, payload: Mapping[str, Any],
        correlation_id: str | None, causation_id: str | None, trace_id: str | None,
        event_id: str | None, now: str,
    ) -> EventEnvelope:
        """One canonical envelope on the `identity_binding_claim` aggregate. F6 proposals are
        order-tolerant, so no `previous_aggregate_version` travels on them; the STRICT ordering of
        correction/supersession is realized through the consumer's `requires_existing` prerequisite
        (§8, task §3.5)."""
        return EventEnvelope(
            event_id=event_id or str(uuid.uuid4()), event_name=event_name,
            event_version=CONTRACTS[event_name].current_version, occurred_at=now, recorded_at=now,
            tenant_id=self._tenant, aggregate_type=AGGREGATE_TYPE,
            aggregate_id=claim.binding_claim_id, aggregate_version=aggregate_version,
            previous_aggregate_version=None, causation_id=causation_id,
            correlation_id=correlation_id or claim.binding_claim_id,
            producer_component=self._component, producer_transition_id=transition_id,
            actor_type=actor_type, actor_id=actor_id,
            trace_id=trace_id or f"trace-{claim.binding_claim_id}", payload=dict(payload),
            accountable_owner_id=claim.owner_id)

    def _conflict_envelope(
        self, *, conflict_id: str, aggregate_version: int, actor_id: str, payload: Mapping[str, Any],
        correlation_id: str | None, causation_id: str | None, trace_id: str | None,
        event_id: str | None, now: str,
    ) -> EventEnvelope:
        """The co-committed `ConflictRaised` (IB-6), riding the `conflict` aggregate at a minted id.
        The `event_outbox` holds no FK into a conflicts table, so this needs no M7 aggregate row."""
        return EventEnvelope(
            event_id=event_id or str(uuid.uuid4()), event_name="ConflictRaised",
            event_version=CONTRACTS["ConflictRaised"].current_version, occurred_at=now,
            recorded_at=now, tenant_id=self._tenant, aggregate_type=CONFLICT_AGGREGATE_TYPE,
            aggregate_id=conflict_id, aggregate_version=aggregate_version,
            previous_aggregate_version=None, causation_id=causation_id,
            correlation_id=correlation_id or conflict_id, producer_component=self._component,
            producer_transition_id="IB-6", actor_type="system", actor_id=actor_id,
            trace_id=trace_id or f"trace-{conflict_id}", payload=dict(payload))


# ------------------------------------------------------------------------------------- plumbing

def _classify(attempt: MatchAttempt) -> tuple[str, str | None]:
    """The deterministic-first ladder (ADR-007 §4.1). Returns (outcome, ambiguous_reason).

    ### PROVENANCE GATES; CONFIDENCE SORTS. Confidence is never read here — a MODEL_INFER guess routes
    to AMBIGUOUS at confidence 1.0 exactly as it would at 0.4."""
    method = attempt.match_method
    if method is MatchMethod.MODEL_INFER:
        return "AMBIGUOUS", "model_inferred"
    if method is MatchMethod.MODEL_EXTRACT:
        return "EVIDENCE", None
    if attempt.weak:
        return "AMBIGUOUS", "single_weak"
    if attempt.candidate_count > 1 or attempt.open_entity_count > 1:
        return "AMBIGUOUS", "multiple"
    if method is MatchMethod.EXACT_ID and attempt.open_entity_count == 1:
        return "CONFIRMED", None
    if method is MatchMethod.RULE and attempt.rule_registered and bool(attempt.rule_id):
        return "CONFIRMED", None
    if method is MatchMethod.RECONCILIATION and attempt.source_count >= 2:
        return "CONFIRMED", None
    # Exact id resolving to zero, an unregistered rule, a single-source reconciliation: there is no
    # best guess — it goes to a human.
    return "AMBIGUOUS", "multiple"


def _confirm_transition(attempt: MatchAttempt) -> str:
    """IB-2 for the exact-trusted-ID match; IB-2r for a registered rule or a reconciliation."""
    return "IB-2" if attempt.match_method is MatchMethod.EXACT_ID else "IB-2r"


def _event_target_state(event: EventEnvelope) -> ClaimState | None:
    """The state a claim event reconstructs to, or None for an event that is not a state marker on
    this aggregate (a proposal/evidence marker, or an F14 event riding the aggregate)."""
    name = event.event_name
    if name == "ClaimConfirmed":
        return ClaimState.CONFIRMED
    if name == "ClaimAmbiguous":
        return ClaimState.AMBIGUOUS
    if name == "ClaimCorrected":
        return ClaimState.CORRECTED
    if name == "ClaimSuperseded":
        # IB-5 (CONFIRMED→SUPERSEDED) and IB-8 (→REJECTED) share this event; the target is read from
        # the producer transition rather than guessed.
        return ClaimState.REJECTED if event.producer_transition_id == "IB-8" else ClaimState.SUPERSEDED
    # ClaimProposed / ClaimEvidenced (creation/evidence markers), IllegalTransitionAttempted, etc.
    return None


def _looks_like_span(span: str) -> bool:
    """A real artifact region: `page:N`, an offset range `A:B`, or a coordinate box `x,y,w,h`. A
    bare word or an empty value is a forged span and fails closed."""
    s = span.strip()
    if not s:
        return False
    if s.lower().startswith(("page:", "region:", "box:", "line:")):
        return len(s.split(":", 1)[1].strip()) > 0
    if ":" in s:
        a, _, b = s.partition(":")
        return a.strip().isdigit() and b.strip().isdigit()
    if "," in s:
        return all(part.strip().lstrip("-").isdigit() for part in s.split(",") if part.strip())
    return False


def _require_text(value: str, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise GuardNotSatisfied(f"{field_name} is required and was empty.")
    return text


def _row_to_claim(row: Any) -> IdentityBindingClaim:
    return IdentityBindingClaim(
        tenant=row["tenant"], binding_claim_id=row["binding_claim_id"],
        subject_ref=row["subject_ref"], entity_ref=row["entity_ref"],
        provenance_class=row["provenance_class"], state=ClaimState(row["state"]),
        version=row["version"], match_method=row["match_method"], confidence=row["confidence"],
        evidence_id=row["evidence_id"], span=row["span"], rule_id=row["rule_id"],
        decision_ref=row["decision_ref"], decision_human_id=row["decision_human_id"],
        owner_id=row["owner_id"], ambiguous_reason=row["ambiguous_reason"],
        corrected_from=row["corrected_from"], superseded_by=row["superseded_by"],
        conflict_id=row["conflict_id"], propagation_obligation=row["propagation_obligation"])


# Re-exported so a caller reads one name rather than importing the migration for a constant.
STATES: tuple[str, ...] = CLAIM_STATES
METHODS: tuple[str, ...] = MATCH_METHODS
REASONS: tuple[str, ...] = AMBIGUOUS_REASONS
ALLOWED_CONFIRMED_PROVENANCE: tuple[str, ...] = CONFIRMED_ALLOWED_PROVENANCE
MODEL_PROVENANCE: tuple[str, ...] = LAUNDERABLE_MODEL_PROVENANCE
