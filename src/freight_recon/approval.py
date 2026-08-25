"""Machine M4 — the Approval: one `approvals` row that binds a human's consent to the EXACT facts
that made it correct, so a drifted fact is not a weaker approval — it is a new question.

    ### A HUMAN APPROVES AN ACTION PLUS THE EXACT MATERIAL FACTS THAT MADE IT CORRECT.
    ### IF THOSE FACTS CHANGE THERE IS NO APPROVAL. THERE IS A NEW QUESTION. (ADR-005 §3.1)

The owner approved invoicing load 4471 at £2,850, read from the TMS invoice screen. Forty minutes
later the TMS says £3,100. The old architecture invoiced £3,100 and the audit log recorded a human
approval (ADR-005 F-01). This machine closes that STRUCTURALLY: the approval carries a
`material_facts_fingerprint` computed from RUNTIME reads (never model output) plus the full
`canonical_payload` it was hashed from, and at checkpoint step 2 the facts are re-read LIVE and
re-fingerprinted under the approval's STORED version. Unequal ⇒ `VOID_ON_DRIFT`, no grant, no effect.

### WHAT THIS MACHINE OWNS, AND WHAT IT ONLY BORROWS.

It owns the eight states and the AP-1…AP-9 transitions of `04-approval.machine.md` §14, and it is the
canonical PRODUCER of the `Approval*` event stream on the `approval` aggregate. It does NOT own the
fingerprint (that is `fingerprint.py`'s `fp_v1`, CONSUMED not reimplemented — a serialization change
is the single most dangerous bug in ADR-005 §7, because it produces false no-drift, which is a wrong
payment), the checkpoint (that is P3's, which already reads an approval at steps 1–2), or the claim
CAS (that is P3's single serialization point). ### CONSUMPTION CO-COMMITS WITH THE M3 CLAIM CAS by
calling the kernel's `claim_grant_cas_locked` — the very seam that function's docstring anticipates
("M3 `CLAIMED` + M4 `ApprovalConsumed` + `EffectAttempted`"). M4 adds NO second effect authority and
mints NO gate decision; M3 remains the single effect authority.

### THE KNOWN AUTHORITY QUESTION (task §3.9 / entity §15 vs machine §4 vs EF-2), REPORTED NOT RESOLVED.
Three authorities put `GRANTED → CONSUMED` inside the CLAIM transaction (entity §15, machine §4 AP-7,
`EF-2`). Two rows are written from `GRANTED` on triggers that can only arrive AFTER that transaction
committed (`AP-8` on `AttemptFailedProvably` = `EF-3f` from `CLAIMED`; `AP-9` on
`AttemptOutcomeUnknown` = `EF-3u` from `CLAIMED`). Under the claim-time reading `AP-8`/`AP-9` are
unreachable (§15 makes `CONSUMED` + anything illegal); under the commit-time reading `AP-7`'s "same
txn as the claim" is false. ### THIS CODE IMPLEMENTS `AP-7` EXACTLY AS THE THREE CLAIM-TXN CLAUSES
STATE IT (consume co-commits with the claim CAS), AND `AP-8`/`AP-9` EXACTLY AS WRITTEN (from
`GRANTED`, before consumption). It invents no reconciliation — no state, no flag, no un-consume path
— and therefore cannot prove which reading is canonical at that seam. What it DOES guarantee, which
every reading agrees on, is: no second effect, no second grant of authority, nothing reusable.

### THE UNFREEZE DIRECTION IS AN OPEN RESIDUAL (`G2-D15`), AND THIS MACHINE PRESERVES IT.
`AP-9` sets `frozen=true`; a frozen approval accepts NO trigger (reuse is ILLEGAL, no timer moves it,
GR-6). There is no un-freeze event of any kind, no un-freeze transition, no side-effect that clears the
flag. A full-history rebuild reconstructs a frozen approval as STILL frozen — strictly safer than the
original — which is why the residual is nonblocking. `ER-16`: `frozen` is reconstructed from the
PRESENCE of `ApprovalFrozen`, never from `OutcomeUnknown` AND NOT `RealityEstablished`.

### IT SHIPS DARK. Nothing under `src/freight_recon/` imports this module; the only script that may is
`scripts/probe_phase6_approval.py`. It does NOT import M3 (`external_effect`) — M3's ship-dark guard
forbids any importer but M3's own probe, and the consume seam runs through P3's kernel, not M3.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from .brake import TENANT_WIDE, BrakeStore, BrakeStoreUnreachable
from .checkpoint import (
    ApprovalRecord,
    AuthoritativeSourceReader,
    CheckpointKernel,
    ClaimParams,
    EffectGrantHandle,
    SourceUnreadable,
    claim_grant_cas_locked,
    flush_claim_records,
    material_fact_set,
)
from .commit_key import LogicalEffect
from .event_contracts import CONTRACTS
from .event_envelope import EventEnvelope, format_instant
from .event_inbox import ConsumeResult, DedupInbox
from .event_outbox import TransactionalOutbox
from .event_timers import DurableTimers, TimerFired
from .fingerprint import FINGERPRINT_VERSION, canonical_payload, drift_diff
from .migrations.phase6_approvals import (
    APPROVAL_GATE_DECISIONS,
    APPROVAL_STATES,
    NON_TERMINAL_APPROVAL_STATES,
    TERMINAL_APPROVAL_STATES,
)
from .tenant import require_tenant

# The aggregate this machine owns. `approval` is in `STRICT_ORDER_AGGREGATE_TYPES` (F4,
# events/registry.md §8): its transitions are version-monotonic, so an out-of-order F4 event is a
# gap, and the inbox parks it until the gap fills.
AGGREGATE_TYPE = "approval"

# entity §5: the Approval Service renders the card, receives the tap, holds the fingerprint.
PRODUCER_COMPONENT = "approval_service"

# The one consumer identity M4 presents to the dedup inbox. Fixed, because the dedup key is
# `(tenant, consumer_id, event_id)` and a renamed consumer would re-arm every duplicate.
CONSUMER_ID = "m4-approval"

# GR-1's producer id for `IllegalTransitionAttempted` — the RULE, not a transition (§3 "‡(any
# machine, GR-1)"). Identical to M1/M2/M3's, for the same reason.
ILLEGAL_TRANSITION_PRODUCER = "GR-1"

# A refusal advances no version; every refusal against one approval at one version would otherwise
# collide on one `idempotency_identity` — the poison-loop defect M1 shipped. Applied here.
ILLEGAL_ATTEMPT_IDENTITY_PREFIX = "ita_v1"
FRAUD_IDENTITY_PREFIX = "fraud_v1"

# The permanent-human-assertion gate, DERIVED from the migration's (kernel-derived) human gates
# rather than typed — the Phase-0 confinement guard scans every `.py` for gate-decision tokens and
# confines them to the checkpoint kernel, so this machine names none.
HUMAN_ASSERTION_GATE = next(g for g in APPROVAL_GATE_DECISIONS if "ASSERTION" in g)

# The timer kind AP-3's durable timer fires under. entity §26 / ADR-005 §3.9: an absolute TTL per
# action class, fired by a durable timer emitting `TimerFired` — never a background sweep.
TTL_TIMER_KIND = "approval_ttl"

# ### V2 (NEEDS VALIDATION) — the TTLs of ADR-005 §3.9 (money-out 1h · money-in 8h · docs/status
# 24h). ### THE MECHANISM DOES NOT DEPEND ON THE ANSWER. The fail-closed default is the SHORTEST
# (money-out), because a too-short TTL asks again and a too-long one lets a stale approval execute —
# and the safe direction is to ask again. A caller may pass an explicit ttl; nothing here guesses a
# "better" number.
DEFAULT_APPROVAL_TTL = timedelta(hours=1)  # NEEDS VALIDATION (V2)

# ### V3 (NEEDS VALIDATION) — which classes need dual control, at what threshold. Fail-closed
# default: single approval unless configured. The mechanism is complete and does not depend on this.
DEFAULT_REQUIRED_SIGNATURES = 1  # NEEDS VALIDATION (V3)

HUMAN = "HUMAN"

# ADR-005 §3.15 layer 1: the transport token's HMAC key. A fixed, non-secret default for the dark
# unit (no Slack surface exists); a real deployment injects its own. The token is NOT the control —
# layer 2 is the DB CAS — so a weak key cannot mint authority, only fail an already-caught replay.
_DEFAULT_TRANSPORT_KEY = b"m4-approval-transport-v1"


class ApprovalError(RuntimeError):
    """This machine will not do what was asked. Never degraded into a partial transition."""


class UnknownApproval(ApprovalError):
    """No `approvals` row with this id exists FOR THIS TENANT. Indistinguishable from "belongs to
    another tenant" on purpose — [C-1] rejects a cross-tenant question rather than answering it."""


class GuardNotSatisfied(ApprovalError):
    """The (state, trigger) pair IS legal here and a precondition is false. No event is emitted."""


class IllegalTransition(ApprovalError):
    """GR-1 / [C-4]. The (state, trigger) pair is not enumerated (or §15 forbids the shape). Raised
    AFTER `IllegalTransitionAttempted` is recorded, which is the point of recording it."""


class StateConflict(ApprovalError):
    """A state-guarded UPDATE matched zero rows: the approval moved under us (GR-3). Reload."""


class AuthorityRefused(ApprovalError):
    """### ONLY AN AUTHENTICATED, AUTHORIZED HUMAN GRANTS. A model, a counterparty, a document, a
    confidence score, a policy default, a retry handler, an agent or an admin tool cannot — and a
    counterparty's "per our call you approved this" is a FRAUD SIGNAL, never an approval (ADR-003)."""


# --------------------------------------------------------------------------------- the state set

class ApprovalState(str, Enum):
    REQUESTED = "REQUESTED"
    GRANTED = "GRANTED"
    CONSUMED = "CONSUMED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    VOID_ON_DRIFT = "VOID_ON_DRIFT"
    VOID_ON_BRAKE = "VOID_ON_BRAKE"


class Trigger(str, Enum):
    """The closed set of driving facts, named from §14's triggers and §33's "Events consumed".

    ### `TIMER_FIRED` HAS NO LEGAL ROW ON A FROZEN APPROVAL, WHICH IS THE POINT (GR-6). AP-3 expires
    a live approval; a frozen one accepts no trigger at all, so a timer neither expires nor unfreezes
    it — the same shape M3 uses for EF-5x.
    """

    HUMAN_APPROVED = "HumanApproved"
    HUMAN_DENIED = "HumanDenied"
    MATERIAL_FACTS_CHANGED = "MaterialFactsChanged"   # AP-4 (drift)
    POLICY_VERSION_CHANGED = "PolicyVersionChanged"   # AP-4p
    BRAKE_ENGAGED = "BrakeEngaged"                     # AP-5
    HUMAN_REVOKED = "HumanRevoked"                     # AP-6
    EFFECT_COMMITTED = "EffectCommitted"              # AP-7 (consume, in the claim txn)
    ATTEMPT_FAILED_PROVABLY = "AttemptFailedProvably"  # AP-8
    ATTEMPT_OUTCOME_UNKNOWN = "AttemptOutcomeUnknown"  # AP-9 (freeze)
    TIMER_FIRED = "TimerFired"                         # AP-3


# The drift cause an ApprovalVoided carries (registry §5: cause ∈ {drift, policy, brake}).
VOID_CAUSE_DRIFT = "drift"
VOID_CAUSE_POLICY = "policy"
VOID_CAUSE_BRAKE = "brake"


class RowKind(str, Enum):
    PRODUCER = "PRODUCER"              # emits a canonical event attributed to this transition
    NON_PRODUCING = "NON_PRODUCING"   # AP-8 only: ENUMERATED_NO_OP, survives a provable failure


# --------------------------------------------------------------------------- the transition table

@dataclass(frozen=True)
class TransitionRow:
    """One row of §14. Data, so the acceptance battery can enumerate it against the specification."""

    id: str
    from_states: tuple[ApprovalState, ...]
    to_state: ApprovalState | None
    triggers: tuple[Trigger, ...]
    trigger_types: tuple[str, ...]     # H|S|X|T|P|B|R — the registry §1 codes
    kind: RowKind
    events: tuple[str, ...] = ()
    consequential: bool = False        # §5: pins the SD-3 set + policy/brake/fingerprint at emission
    human_only: bool = False           # AP-2: an authenticated human ONLY (ER-10)
    no_op: bool = False                 # AP-8: changes nothing, writes nothing, emits nothing


TRANSITIONS: tuple[TransitionRow, ...] = (
    TransitionRow(
        id="AP-1", from_states=(), to_state=ApprovalState.REQUESTED,
        triggers=(), trigger_types=("S",), kind=RowKind.PRODUCER,
        events=("ApprovalRequested",), consequential=True,
    ),
    TransitionRow(
        id="AP-2", from_states=(ApprovalState.REQUESTED,), to_state=ApprovalState.GRANTED,
        triggers=(Trigger.HUMAN_APPROVED,), trigger_types=("H",), kind=RowKind.PRODUCER,
        events=("ApprovalGranted",), consequential=True, human_only=True,
    ),
    TransitionRow(
        id="AP-2d", from_states=(ApprovalState.REQUESTED,), to_state=ApprovalState.DENIED,
        triggers=(Trigger.HUMAN_DENIED,), trigger_types=("H",), kind=RowKind.PRODUCER,
        events=("ApprovalDenied",), human_only=True,
    ),
    TransitionRow(
        id="AP-3", from_states=(ApprovalState.REQUESTED, ApprovalState.GRANTED),
        to_state=ApprovalState.EXPIRED,
        triggers=(Trigger.TIMER_FIRED,), trigger_types=("T",), kind=RowKind.PRODUCER,
        events=("ApprovalExpired",),
    ),
    TransitionRow(
        id="AP-4", from_states=(ApprovalState.GRANTED,), to_state=ApprovalState.VOID_ON_DRIFT,
        triggers=(Trigger.MATERIAL_FACTS_CHANGED,), trigger_types=("S",), kind=RowKind.PRODUCER,
        events=("ApprovalVoided",),
    ),
    TransitionRow(
        id="AP-4p", from_states=(ApprovalState.GRANTED,), to_state=ApprovalState.VOID_ON_DRIFT,
        triggers=(Trigger.POLICY_VERSION_CHANGED,), trigger_types=("P",), kind=RowKind.PRODUCER,
        events=("ApprovalVoided",),
    ),
    TransitionRow(
        id="AP-5", from_states=(ApprovalState.GRANTED,), to_state=ApprovalState.VOID_ON_BRAKE,
        triggers=(Trigger.BRAKE_ENGAGED,), trigger_types=("B",), kind=RowKind.PRODUCER,
        events=("ApprovalVoided",),
    ),
    TransitionRow(
        id="AP-6", from_states=(ApprovalState.GRANTED,), to_state=ApprovalState.REVOKED,
        triggers=(Trigger.HUMAN_REVOKED,), trigger_types=("H",), kind=RowKind.PRODUCER,
        events=("ApprovalRevoked",), human_only=True,
    ),
    TransitionRow(
        id="AP-7", from_states=(ApprovalState.GRANTED,), to_state=ApprovalState.CONSUMED,
        triggers=(Trigger.EFFECT_COMMITTED,), trigger_types=("S",), kind=RowKind.PRODUCER,
        events=("ApprovalConsumed",), consequential=True,
    ),
    TransitionRow(
        id="AP-8", from_states=(ApprovalState.GRANTED,), to_state=ApprovalState.GRANTED,
        triggers=(Trigger.ATTEMPT_FAILED_PROVABLY,), trigger_types=("S",),
        kind=RowKind.NON_PRODUCING, no_op=True,
    ),
    TransitionRow(
        id="AP-9", from_states=(ApprovalState.GRANTED,), to_state=ApprovalState.GRANTED,
        triggers=(Trigger.ATTEMPT_OUTCOME_UNKNOWN,), trigger_types=("S",), kind=RowKind.PRODUCER,
        events=("ApprovalFrozen",),
    ),
)

TRANSITIONS_BY_ID: Mapping[str, TransitionRow] = {row.id: row for row in TRANSITIONS}

PRODUCED_CONTRACTS: frozenset[str] = frozenset(
    ev for row in TRANSITIONS for ev in row.events)

TERMINAL_STATES: frozenset[ApprovalState] = frozenset(
    ApprovalState(s) for s in TERMINAL_APPROVAL_STATES)
NON_TERMINAL_STATES: frozenset[ApprovalState] = frozenset(
    ApprovalState(s) for s in NON_TERMINAL_APPROVAL_STATES)


def legal_transitions(
    state: ApprovalState, trigger: Trigger, *, frozen: bool = False,
) -> tuple[TransitionRow, ...]:
    """Every fireable row whose (from-state, trigger) matches. Empty ⇒ ILLEGAL (GR-1).

    ### A FROZEN APPROVAL ACCEPTS NO TRIGGER. It is quarantined until reality is established, and M4
    has no unfreeze path (G2-D15). So a timer neither expires nor unfreezes it, a consume (reuse) is
    illegal, and everything else on it is illegal too — the strictest fail-closed reading, and the
    one that preserves the recorded residual. AP-1 is excluded (a request is not a public trigger).
    """
    if frozen:
        return ()
    return tuple(
        row for row in TRANSITIONS
        if row.id != "AP-1" and state in row.from_states and trigger in row.triggers
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_instant(text: str | None) -> datetime:
    value = str(text or "").strip()
    if not value:
        raise ApprovalError("an approval timestamp is required and was empty")
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


# ------------------------------------------------------------------------------------ the row

@dataclass(frozen=True)
class Approval:
    """One `approvals` row, as the machine reads it."""

    tenant: str
    approval_id: str
    commit_key: str
    action_class: str
    state: ApprovalState
    version: int
    material_facts_fingerprint: str
    canonical_payload: str
    fingerprint_version: str
    entity_versions_json: str
    policy_version: str
    brake_version: str
    gate_decision: str
    required_authority: str | None
    required_signatures: int
    rendered_facts: str
    requested_at: str
    expires_at: str
    granted_by: str | None
    granted_at: str | None
    consumed_at: str | None
    void_reason: str | None
    drift_diff: str | None
    frozen: bool
    unknown_outcome_ref: str | None
    effect_grant_id: str | None
    frozen_at: str | None

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    @property
    def entity_versions(self) -> dict[str, int]:
        try:
            loaded = json.loads(self.entity_versions_json) if self.entity_versions_json else {}
        except (TypeError, ValueError):
            return {}
        return {str(k): int(v) for k, v in loaded.items()} if isinstance(loaded, dict) else {}

    def pins(self) -> dict[str, Any]:
        """The decision context §5 requires on a CONSEQUENTIAL approval event — read from the row the
        request pinned from RUNTIME reads, never re-derived."""
        return {
            "entity_versions": self.entity_versions,
            "policy_version": self.policy_version,
            "brake_version": self.brake_version,
            "material_facts_fingerprint": self.material_facts_fingerprint,
        }


@dataclass(frozen=True)
class RequestOutcome:
    approval_id: str
    fingerprint: str
    event_id: str


@dataclass(frozen=True)
class GrantOutcome:
    """What one grant attempt did. `granted` is the completed quorum; `resigned` means signature
    drift voided every prior signature and the fingerprint was refreshed (all humans re-sign)."""

    granted: bool
    approval_id: str
    signatures: int
    required: int
    event_id: str | None = None
    resigned: bool = False


@dataclass(frozen=True)
class TransitionResult:
    transition_id: str
    approval: Approval
    from_state: ApprovalState
    to_state: ApprovalState
    event_ids: tuple[str, ...] = ()
    event_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConsumeAttempt:
    """What AP-7 did. `consumed` is the winner; `already_done` is the idempotent double-tap; a
    refusal names its cause and did nothing (never both, never neither)."""

    consumed: bool
    approval_id: str
    already_done: bool = False
    grant_claimed: bool = False
    cause: str = ""
    event_id: str | None = None


@dataclass(frozen=True)
class DriftOutcome:
    """What a live drift re-check found. `drifted` ⇒ VOID_ON_DRIFT with the field-level diff."""

    drifted: bool
    approval_id: str
    diff: str = ""
    fields: tuple[str, ...] = ()
    event_id: str | None = None


@dataclass(frozen=True)
class ReconstructedApproval:
    """A full-history fold of one approval's event stream — sandboxed, zero authority (GR-11, K-3).

    Every count is of what the REBUILD created, which is always zero: it mints no grant, grants no
    authority, consumes into no effect, and touches the outside world not at all.
    """

    approval_id: str
    state: ApprovalState | None
    frozen: bool
    grants_minted: int = 0
    approvals_granted: int = 0
    approvals_consumed: int = 0
    external_effects: int = 0


@dataclass(frozen=True)
class IllegalAttemptRecord:
    event_id: str
    idempotency_identity: str
    already_recorded: bool


@dataclass(frozen=True)
class ConsumedTransition:
    """What consuming one canonical trigger did — the DELIVERY (`consume`) kept apart from the
    MACHINE effect (`transition`), so "the event was delivered" is never read as "the approval
    moved"."""

    consume: ConsumeResult
    transition: TransitionResult | None = None
    refusal: str | None = None

    @property
    def moved(self) -> bool:
        return self.transition is not None


@dataclass(frozen=True)
class TransportToken:
    """ADR-005 §3.15 layer 1 — the single-use HMAC the approval card carries, bound to
    `(tenant, approval_id, channel, thread, user)`.

    ### THE TOKEN IS NOT THE CONTROL: layer 2 is the database CAS, and a token that somehow passed
    still meets it. But a replayed callback, one presented by the wrong actor, one for the wrong
    target or a forged one is refused HERE, at the transport, before the CAS is even reached — and a
    forged authority names no real approval.
    """

    tenant: str
    approval_id: str
    channel: str
    thread: str
    user: str
    mac: str


# --------------------------------------------------------------------------------- the machine

class ApprovalMachine:
    """M4, on an existing connection, bound to ONE tenant. Bound at construction rather than per
    call, so a caller cannot re-point it at another tenant and put [C-1] in its own hands."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        tenant: str,
        kernel: CheckpointKernel | None = None,
        clock: Callable[[], datetime] | None = None,
        producer_component: str = PRODUCER_COMPONENT,
        transport_key: bytes = _DEFAULT_TRANSPORT_KEY,
    ) -> None:
        if getattr(conn, "row_factory", None) is not sqlite3.Row:
            raise ApprovalError(
                "ApprovalMachine reads columns by name and requires `row_factory = sqlite3.Row`."
            )
        self._conn = conn
        self._tenant = require_tenant(tenant, context="ApprovalMachine")
        self._kernel = kernel
        self._clock = clock or _utc_now
        self._component = producer_component
        self._transport_key = transport_key
        # ADR-005 §3.15 layer 1's single-use ledger. In-memory because the transport (Slack) is not
        # built (M4 ships dark); a real deployment persists it. Layer 2 (the DB CAS) is the durable
        # single-use guarantee for CONSUMPTION regardless.
        self._spent_tokens: set[str] = set()

    @property
    def tenant(self) -> str:
        return self._tenant

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    # --- reads -----------------------------------------------------------------------------------

    def get(self, approval_id: str) -> Approval | None:
        row = self._conn.execute(
            "SELECT * FROM approvals WHERE tenant = ? AND approval_id = ?",
            (self._tenant, approval_id),
        ).fetchone()
        return _row_to_approval(row) if row is not None else None

    def require(self, approval_id: str) -> Approval:
        found = self.get(approval_id)
        if found is None:
            raise UnknownApproval(
                f"no approval {approval_id!r} for tenant {self._tenant!r}. This machine does not "
                f"look outside its tenant to find out whether it exists elsewhere ([C-1])."
            )
        return found

    def live_holder(self, commit_key: str) -> Approval | None:
        """The at-most-one REQUESTED/GRANTED approval reserving this commit key (entity §17)."""
        row = self._conn.execute(
            "SELECT * FROM approvals WHERE tenant = ? AND commit_key = ? "
            "AND state IN ('REQUESTED','GRANTED')",
            (self._tenant, commit_key),
        ).fetchone()
        return _row_to_approval(row) if row is not None else None

    def signatures(self, approval_id: str) -> list[sqlite3.Row]:
        return list(self._conn.execute(
            "SELECT * FROM approval_signatures WHERE tenant = ? AND approval_id = ? "
            "ORDER BY signed_at, actor_id",
            (self._tenant, approval_id),
        ).fetchall())

    # --- the transport (ADR-005 §3.15 layer 1) ----------------------------------------------------

    def mint_transport_token(
        self, approval_id: str, *, channel: str, thread: str, user: str,
    ) -> TransportToken:
        """The single-use HMAC the approval card carries, bound to (tenant, approval_id, channel,
        thread, user). Minting it is not authority; presenting a valid, unspent, correctly-bound one
        is only LAYER 1 of two."""
        mac = self._transport_mac(approval_id, channel, thread, user)
        return TransportToken(
            tenant=self._tenant, approval_id=approval_id, channel=channel, thread=thread,
            user=user, mac=mac)

    def verify_transport_token(
        self, token: TransportToken, *, approval_id: str, channel: str, thread: str, user: str,
    ) -> None:
        """### LAYER 1 (transport). Refuses a FORGED token (names no approval / bad HMAC), one for the
        WRONG TARGET or WRONG ACTOR (the HMAC over the presented binding does not match), and a
        REPLAYED one (single-use). Spends the token on success. Raises `AuthorityRefused` otherwise —
        never a silent pass. The DB CAS (layer 2) is still the control; this is defense in front of it.
        """
        if self.get(approval_id) is None:
            raise AuthorityRefused(
                f"transport token names approval {approval_id!r}, which does not exist for tenant "
                f"{self._tenant!r}: a forged authority names no approval (§40).")
        expected = self._transport_mac(approval_id, channel, thread, user)
        if not hmac.compare_digest(str(token.mac), expected):
            raise AuthorityRefused(
                "transport token refused: its HMAC over (tenant, approval_id, channel, thread, user) "
                "does not match — it is forged, presented by another actor, or bound to a different "
                "target or tenant (§40). Authority is bound to ONE target and ONE actor.")
        if token.mac in self._spent_tokens:
            raise AuthorityRefused(
                "transport token refused: a single-use token was replayed at the transport "
                "(ADR-005 §3.15 layer 1). A replayed callback fails the token check.")
        self._spent_tokens.add(token.mac)

    def _transport_mac(self, approval_id: str, channel: str, thread: str, user: str) -> str:
        binding = f"{self._tenant}|{approval_id}|{channel}|{thread}|{user}"
        return hmac.new(self._transport_key, binding.encode("utf-8"), hashlib.sha256).hexdigest()

    # --- AP-1: the request ------------------------------------------------------------------------

    def request(
        self,
        *,
        approval_id: str,
        effect: LogicalEffect,
        material_facts_reader: AuthoritativeSourceReader,
        entity_versions: Mapping[str, int],
        policy_version: str,
        gate_decision: str,
        rendered_facts: Mapping[str, Any] | str,
        brake_version: str | None = None,
        required_authority: str | None = None,
        required_signatures: int = DEFAULT_REQUIRED_SIGNATURES,
        ttl: timedelta | None = None,
        actor_type: str = "system",
        actor_id: str = "execution-service",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
        schedule_timer: bool = True,
    ) -> RequestOutcome:
        """AP-1 — ### THE FINGERPRINT AND PAYLOAD ARE COMPUTED FROM RUNTIME READS, NEVER MODEL OUTPUT.

        A compromised model produces a bad proposed intent; the runtime resolves the values itself
        (M-13/M-55) via `material_fact_set` + `canonical_payload` — the ONE composer, CONSUMED not
        reimplemented. The approval, the absolute TTL timer and the `ApprovalRequested` event
        co-commit (GR-2); M2's PL-6 consumes that event to move its own row to `AWAITING_APPROVAL`,
        so a crash leaves neither an orphan approval nor a pipeline waiting on one that never existed.
        """
        if effect.tenant.strip().lower() != self._tenant.strip().lower():
            raise ApprovalError(
                f"the effect names tenant {effect.tenant!r}; this machine is bound to "
                f"{self._tenant!r}. An approval never crosses a tenant ([C-1]).")
        if str(gate_decision) not in APPROVAL_GATE_DECISIONS:
            raise GuardNotSatisfied(
                f"an Approval exists ONLY for a human gate {list(APPROVAL_GATE_DECISIONS)}; "
                f"{gate_decision!r} is not one. A money-affecting autonomous action class "
                f"cannot have an approval (entity §12/§16).")
        if int(required_signatures) < 1:
            raise GuardNotSatisfied("required_signatures must be >= 1 (fail-closed single approval).")
        commit_key = effect.key()
        versions = {str(k): int(v) for k, v in dict(entity_versions).items()}
        payload_bytes = self._compose_payload(
            effect, commit_key, material_facts_reader, versions, policy_version, FINGERPRINT_VERSION)
        fingerprint = _sha256_hex(payload_bytes)
        brake_token = brake_version if brake_version is not None else self._brake_token()
        now_dt = self._clock()
        now = format_instant(now_dt)
        expires_dt = now_dt + (ttl or DEFAULT_APPROVAL_TTL)
        expires = format_instant(expires_dt)
        rendered = rendered_facts if isinstance(rendered_facts, str) else json.dumps(
            rendered_facts, sort_keys=True)
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                """
                INSERT INTO approvals (
                    tenant, approval_id, commit_key, action_class, state, version,
                    material_facts_fingerprint, canonical_payload, fingerprint_version,
                    entity_versions_json, policy_version, brake_version, gate_decision,
                    required_authority, required_signatures, rendered_facts, requested_at,
                    expires_at, granted_by, granted_at, consumed_at, void_reason, drift_diff,
                    frozen, unknown_outcome_ref, effect_grant_id, frozen_at, created_at, updated_at
                ) VALUES (?,?,?,?, 'REQUESTED', 1, ?,?,?,?,?,?,?,?,?,?,?,?,
                          NULL, NULL, NULL, NULL, NULL, 0, NULL, NULL, NULL, ?, ?)
                """,
                (self._tenant, approval_id, commit_key, effect.action_class,
                 fingerprint, payload_bytes.decode("utf-8"), FINGERPRINT_VERSION,
                 json.dumps(versions, sort_keys=True), str(policy_version), brake_token,
                 str(gate_decision), required_authority, int(required_signatures), rendered,
                 now, expires, now, now),
            )
            approval = self.require(approval_id)
            if schedule_timer:
                # AP-3's durable timer, in the SAME commit as the request (never a background sweep).
                DurableTimers(conn, tenant=self._tenant, clock=self._clock).schedule(
                    timer_id=f"{TTL_TIMER_KIND}:{approval_id}", aggregate_type=AGGREGATE_TYPE,
                    aggregate_id=approval_id, timer_kind=TTL_TIMER_KIND, fire_at=expires,
                    correlation_id=(correlation_id or commit_key))
            envelope = self._envelope(
                event_name="ApprovalRequested", transition_id="AP-1", approval=approval,
                aggregate_version=self._next_version(approval_id), actor_type=actor_type,
                actor_id=actor_id, payload={
                    "fingerprint": fingerprint, "gate_decision": str(gate_decision),
                    "rendered_facts": rendered, "expires_at": expires},
                correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                event_id=event_id, now=now, consequential=True)
            self._outbox().emit(envelope)
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        return RequestOutcome(
            approval_id=approval_id, fingerprint=fingerprint, event_id=envelope.event_id)

    # --- AP-2 / AP-2d / AP-6: the human decisions -------------------------------------------------

    def grant(
        self,
        approval_id: str,
        *,
        actor_id: str,
        actor_kind: str = HUMAN,
        authority: str | None = None,
        assertion: str | None = None,
        token: TransportToken | None = None,
        channel: str | None = None,
        thread: str | None = None,
        effect: LogicalEffect | None = None,
        material_facts_reader: AuthoritativeSourceReader | None = None,
        entity_versions: Mapping[str, int] | None = None,
        policy_version: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> GrantOutcome:
        """AP-2 — ### ONLY AN AUTHENTICATED, AUTHORIZED HUMAN GRANTS, on quorum by DISTINCT actors.

        The signature is recorded first (a duplicate actor is a no-op — the DB PK counts distinct
        authenticated actors, not signatures), then quorum is evaluated. For `required_signatures = 1`
        the first valid human signature grants. For dual control, pass `material_facts_reader`/effect
        so drift between signatures is detected: ### DRIFT VOIDS ALL SIGNATURES ⇒ the approval returns
        to REQUESTED with a fresh fingerprint and every human signs again.
        """
        approval = self.require(approval_id)
        if approval.state is not ApprovalState.REQUESTED:
            raise GuardNotSatisfied(
                f"AP-2 grants only a REQUESTED approval; {approval_id!r} is {approval.state.value}.")
        # Layer 1 first (transport), if a token was presented — it is defense in front of the CAS.
        if token is not None:
            self.verify_transport_token(
                token, approval_id=approval_id, channel=(channel or ""), thread=(thread or ""),
                user=actor_id)
        self._require_human_authority(approval, actor_id, actor_kind, authority, trigger="grant")
        if approval.gate_decision == HUMAN_ASSERTION_GATE and not str(assertion or "").strip():
            raise GuardNotSatisfied(
                f"gate {HUMAN_ASSERTION_GATE} requires a human ASSERTION, not merely a tap "
                f"(entity §21 / AP-2). None was supplied.")

        # Dual-control drift: recompute live; if it moved since the fingerprint the earlier signers
        # signed, VOID ALL SIGNATURES and re-fingerprint while still REQUESTED (ADR-005 §3.16).
        if material_facts_reader is not None and effect is not None:
            new_bytes = self._compose_payload(
                effect, approval.commit_key, material_facts_reader,
                (dict(entity_versions) if entity_versions is not None else approval.entity_versions),
                (policy_version if policy_version is not None else approval.policy_version),
                approval.fingerprint_version)
            new_fp = _sha256_hex(new_bytes)
            if new_fp != approval.material_facts_fingerprint:
                self._refingerprint_and_void_signatures(approval, new_fp, new_bytes)
                return GrantOutcome(granted=False, approval_id=approval_id, signatures=0,
                                    required=approval.required_signatures, resigned=True)

        conn = self._conn
        now = format_instant(self._clock())
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "INSERT OR IGNORE INTO approval_signatures "
                "(tenant, approval_id, actor_id, signed_fingerprint, signed_at) VALUES (?,?,?,?,?)",
                (self._tenant, approval_id, actor_id, approval.material_facts_fingerprint, now))
            signed = [r["actor_id"] for r in conn.execute(
                "SELECT actor_id FROM approval_signatures WHERE tenant = ? AND approval_id = ? "
                "AND signed_fingerprint = ? ORDER BY signed_at, actor_id",
                (self._tenant, approval_id, approval.material_facts_fingerprint)).fetchall()]
            count = len(signed)
            if count < approval.required_signatures:
                conn.commit()
                return GrantOutcome(granted=False, approval_id=approval_id, signatures=count,
                                    required=approval.required_signatures)
            # Quorum met — AP-2: REQUESTED -> GRANTED, in this commit.
            cursor = conn.execute(
                "UPDATE approvals SET state = 'GRANTED', version = version + 1, granted_by = ?, "
                "granted_at = ?, updated_at = ? "
                "WHERE tenant = ? AND approval_id = ? AND state = 'REQUESTED' AND frozen = 0",
                (actor_id, now, now, self._tenant, approval_id))
            if cursor.rowcount != 1:
                raise StateConflict(
                    f"AP-2 matched {cursor.rowcount} rows for {approval_id!r}: it moved under us.")
            granted = self.require(approval_id)
            payload: dict[str, Any] = {"granted_by": actor_id}
            if approval.required_signatures > 1:
                payload["signatures"] = signed
            envelope = self._envelope(
                event_name="ApprovalGranted", transition_id="AP-2", approval=granted,
                aggregate_version=self._next_version(approval_id), actor_type="human",
                actor_id=actor_id, payload=payload, correlation_id=correlation_id,
                causation_id=causation_id, trace_id=trace_id, event_id=event_id, now=now,
                consequential=True)
            self._outbox().emit(envelope)
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        return GrantOutcome(granted=True, approval_id=approval_id, signatures=count,
                            required=approval.required_signatures, event_id=envelope.event_id)

    def deny(
        self, approval_id: str, *, actor_id: str, actor_kind: str = HUMAN,
        correlation_id: str | None = None, causation_id: str | None = None,
        trace_id: str | None = None, event_id: str | None = None,
    ) -> TransitionResult:
        """AP-2d — a human declines. ### A DENIAL IS TERMINAL: a denied approval can never execute."""
        approval = self.require(approval_id)
        self._require_human_authority(approval, actor_id, actor_kind, None, trigger="deny")
        return self._simple_transition(
            approval, Trigger.HUMAN_DENIED, actor_type="human", actor_id=actor_id, payload={},
            correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
            event_id=event_id)

    def revoke(
        self, approval_id: str, *, actor_id: str, actor_kind: str = HUMAN,
        correlation_id: str | None = None, causation_id: str | None = None,
        trace_id: str | None = None, event_id: str | None = None,
    ) -> TransitionResult:
        """AP-6 — an authenticated human revokes a GRANTED approval before consumption."""
        approval = self.require(approval_id)
        self._require_human_authority(approval, actor_id, actor_kind, None, trigger="revoke")
        return self._simple_transition(
            approval, Trigger.HUMAN_REVOKED, actor_type="human", actor_id=actor_id, payload={},
            correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
            event_id=event_id)

    # --- AP-3: expiry, driven by a durable timer --------------------------------------------------

    def on_timer(self, trigger: TimerFired, *, actor_id: str = "approval-ttl") -> TransitionResult:
        """AP-3 — the durable timer fired. ### AN EXPIRED APPROVAL IS NOT A WEAKER APPROVAL; IT IS
        NOT AN APPROVAL. A frozen approval accepts no timer (GR-6): NO TIMER UNFREEZES AN APPROVAL."""
        if trigger.timer_kind != TTL_TIMER_KIND:
            raise GuardNotSatisfied(
                f"M4 handles only {TTL_TIMER_KIND!r} timers; got {trigger.timer_kind!r}.")
        approval = self.require(trigger.aggregate_id)
        return self._simple_transition(
            approval, Trigger.TIMER_FIRED, actor_type="system", actor_id=actor_id, payload={},
            correlation_id=trigger.correlation_id, causation_id=trigger.causation_id, trace_id=None,
            event_id=None)

    # --- AP-4 / AP-4p / AP-5: the voids -----------------------------------------------------------

    def check_drift(
        self,
        approval_id: str,
        *,
        effect: LogicalEffect,
        material_facts_reader: AuthoritativeSourceReader,
        entity_version_reader: AuthoritativeSourceReader | None = None,
        actor_id: str = "checkpoint",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
    ) -> DriftOutcome:
        """AP-4 — re-read every material fact LIVE, recompute under the approval's STORED version,
        compare (ADR-005 §3.12). This is the checkpoint step-2 mechanism on the durable approval.

        ### A RE-READ THAT FAILS IS NOT "NO DRIFT". An unreadable authoritative source raises
        `SourceUnreadable` (the reader's own): we do not execute money against a source we could not
        read, and the approval stays GRANTED (unusable now), never silently voided-away or proceeded.
        ### SAME VALUE, CHANGED PROVENANCE OR DEGRADED EVIDENCE, VOID: provenance_class and
        evidence_condition are INSIDE the fingerprint, so they recompute to different bytes.
        Entity-version drift is a separate comparison (the versions the decision read).
        """
        approval = self.require(approval_id)
        if approval.frozen:
            self._record_illegal(approval, Trigger.MATERIAL_FACTS_CHANGED, actor_id=actor_id)
            raise IllegalTransition("a frozen approval is quarantined; no transition moves it.")
        if approval.state is not ApprovalState.GRANTED:
            raise GuardNotSatisfied(
                f"AP-4 checks a GRANTED approval; {approval_id!r} is {approval.state.value}.")
        # ### THE RE-READ FAILS CLOSED. An unreadable authoritative source is NOT "no drift" (ADR-005
        # §3.12): we do not execute money against a source we could not read. Caught explicitly and
        # re-raised so the fail-closed direction is a guard a mutation can flip, not an accident of
        # propagation — and the approval stays GRANTED (unusable now), never voided-away, never
        # proceeded.
        try:
            current_bytes = self._compose_payload(
                effect, approval.commit_key, material_facts_reader, approval.entity_versions,
                approval.policy_version, approval.fingerprint_version)
        except SourceUnreadable as exc:
            raise SourceUnreadable(
                f"AP-4 re-read of {approval_id!r}'s material facts failed ({exc}); an unreadable "
                f"source is not 'no drift'. The approval stays GRANTED and does not execute.") from exc
        current_fp = _sha256_hex(current_bytes)
        fields: list[str] = []
        parts: list[str] = []
        if current_fp != approval.material_facts_fingerprint:
            for d in drift_diff(approval.canonical_payload.encode("utf-8"), current_bytes):
                fields.append(d.field)
                parts.append(f"{d.field}: {d.approved!r} -> {d.current!r}")
        if entity_version_reader is not None:
            live_versions = self._read_entity_versions(entity_version_reader)
            for name, was in sorted(approval.entity_versions.items()):
                now_v = live_versions.get(name)
                if now_v is not None and int(now_v) != int(was):
                    label = f"entity_version.{name}"
                    fields.append(label)
                    parts.append(f"{label}: {was!r} -> {now_v!r}")
        if not fields:
            return DriftOutcome(drifted=False, approval_id=approval_id)
        diff = "; ".join(parts)
        result = self._void(
            approval, ApprovalState.VOID_ON_DRIFT, VOID_CAUSE_DRIFT,
            drift_diff=diff, actor_id=actor_id, correlation_id=correlation_id,
            causation_id=causation_id, trace_id=trace_id)
        return DriftOutcome(drifted=True, approval_id=approval_id, diff=diff,
                            fields=tuple(fields), event_id=result.event_ids[0])

    def void_on_policy(
        self, approval_id: str, *, current_policy_version: str, actor_id: str = "policy",
        correlation_id: str | None = None, causation_id: str | None = None,
        trace_id: str | None = None,
    ) -> TransitionResult | None:
        """AP-4p — ### A POLICY CHANGE VOIDS AN IN-FLIGHT APPROVAL. You cannot act under a policy that
        no longer exists (ADR-005 §3.11). No stale approval survives a policy tightening."""
        approval = self.require(approval_id)
        if approval.frozen:
            self._record_illegal(approval, Trigger.POLICY_VERSION_CHANGED, actor_id=actor_id)
            raise IllegalTransition("a frozen approval is quarantined; no transition moves it.")
        if approval.state is not ApprovalState.GRANTED:
            raise GuardNotSatisfied(
                f"AP-4p voids a GRANTED approval; {approval_id!r} is {approval.state.value}.")
        if str(current_policy_version) == approval.policy_version:
            return None
        diff = (f"policy_version: {approval.policy_version!r} -> {str(current_policy_version)!r}")
        return self._void(
            approval, ApprovalState.VOID_ON_DRIFT, VOID_CAUSE_POLICY,
            drift_diff=diff, actor_id=actor_id, correlation_id=correlation_id,
            causation_id=causation_id, trace_id=trace_id)

    def void_on_brake(
        self, approval_id: str, *, actor_id: str = "ops", correlation_id: str | None = None,
        causation_id: str | None = None, trace_id: str | None = None,
    ) -> TransitionResult | None:
        """AP-5 — ### A BRAKE ENGAGED IN SCOPE BEFORE CONSUMPTION VOIDS THE APPROVAL, zero effect.
        Fail-closed: an unreadable brake is a refusal (never read as "no brake")."""
        approval = self.require(approval_id)
        if approval.frozen:
            self._record_illegal(approval, Trigger.BRAKE_ENGAGED, actor_id=actor_id)
            raise IllegalTransition("a frozen approval is quarantined; no transition moves it.")
        if approval.state is not ApprovalState.GRANTED:
            raise GuardNotSatisfied(
                f"AP-5 voids a GRANTED approval; {approval_id!r} is {approval.state.value}.")
        if not self._brake_in_scope(approval.action_class):
            return None
        return self._void(
            approval, ApprovalState.VOID_ON_BRAKE, VOID_CAUSE_BRAKE,
            drift_diff=None, actor_id=actor_id, correlation_id=correlation_id,
            causation_id=causation_id, trace_id=trace_id)

    # --- AP-7: consumption, co-committed with the M3 claim CAS -------------------------------------

    def consume(
        self,
        handle: EffectGrantHandle,
        params: ClaimParams,
        *,
        approval_id: str,
        kernel: CheckpointKernel | None = None,
        actor_type: str = "system",
        actor_id: str = "execution-service",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> ConsumeAttempt:
        """AP-7 — ### `GRANTED → CONSUMED` IS AN ATOMIC CAS IN THE SAME TRANSACTION AS THE M3 CLAIM.

        The claim CAS is P3's single serialization point, called through `claim_grant_cas_locked` so
        the approval's consume moves in the commit that wins it (entity §15, machine §4, EF-2,
        spec §21.3 layer 2) — M4 adds no second serialization point and mints no gate.

        ### A DOUBLE TAP IS ALREADY DONE, NOT AN ERROR. The second finds `CONSUMED` and replies with
        the recorded outcome, raising nothing and acting nothing. ### THERE IS NO STATE WHERE THE
        APPROVAL IS CONSUMED BUT THE CLAIM WAS NOT DURABLY WON, AND NONE WHERE THE CLAIM SUCCEEDED
        AND THE APPROVAL REMAINS REUSABLE: if the approval CAS matches zero rows (a void raced in
        first — §16 precedence), the WHOLE transaction rolls back, so the claim does not stand either.
        Reuse of a FROZEN approval is ILLEGAL (§15).
        """
        kern = kernel or self._kernel
        if kern is None:
            raise GuardNotSatisfied(
                "AP-7 requires the checkpoint kernel: the claim CAS is P3's (§17, rule 17).")
        approval = self.require(approval_id)
        if approval.state is ApprovalState.CONSUMED:
            # Idempotent double-tap: already done, nothing raised, nothing acted.
            return ConsumeAttempt(consumed=False, approval_id=approval_id, already_done=True,
                                  cause="ALREADY_CONSUMED")
        if approval.frozen:
            self._record_illegal(approval, Trigger.EFFECT_COMMITTED, actor_id=actor_id)
            raise IllegalTransition(
                "a frozen approval is not reusable (§15): an approval consumed by an attempt of "
                "unknown outcome is spent until a human establishes reality.")
        if approval.state is not ApprovalState.GRANTED:
            raise GuardNotSatisfied(
                f"AP-7 consumes only a GRANTED approval; {approval_id!r} is {approval.state.value}. "
                f"A voided, expired, denied or revoked approval can never execute.")
        grant_row = self._conn.execute(
            "SELECT commit_key FROM effect_grants WHERE tenant = ? AND grant_id = ?",
            (self._tenant, handle.grant_id)).fetchone()
        if grant_row is not None and grant_row["commit_key"] != approval.commit_key:
            raise GuardNotSatisfied(
                f"AP-7 requires commit_key to match: approval authorizes {approval.commit_key!r}, "
                f"the grant is for {grant_row['commit_key']!r}. An approval authorizes ONE effect.")
        now = format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            pending = claim_grant_cas_locked(kern, handle, params, now=self._clock())
            if not pending.outcome.claimed:
                conn.rollback()
                flush_claim_records(kern, pending)
                return ConsumeAttempt(
                    consumed=False, approval_id=approval_id, grant_claimed=False,
                    cause=pending.outcome.cause)
            cursor = conn.execute(
                "UPDATE approvals SET state = 'CONSUMED', consumed_at = ?, version = version + 1, "
                "updated_at = ? "
                "WHERE tenant = ? AND approval_id = ? AND state = 'GRANTED' AND frozen = 0 "
                "AND commit_key = ?",
                (now, now, self._tenant, approval_id, approval.commit_key))
            if cursor.rowcount != 1:
                # The approval moved under us (a drift/brake void committed first — §16 precedence).
                # Roll back the claim too: never consumed-without-claim, never claim-with-reusable.
                conn.rollback()
                flush_claim_records(kern, pending)
                raise StateConflict(
                    f"AP-7 matched {cursor.rowcount} rows for {approval_id!r}: a void won the race, "
                    f"so the claim is abandoned with it (§16: voids precede consume).")
            consumed = self.require(approval_id)
            envelope = self._envelope(
                event_name="ApprovalConsumed", transition_id="AP-7", approval=consumed,
                aggregate_version=self._next_version(approval_id), actor_type=actor_type,
                actor_id=actor_id, payload={}, correlation_id=correlation_id,
                causation_id=causation_id, trace_id=trace_id, event_id=event_id, now=now,
                consequential=True)
            self._outbox().emit(envelope)
            conn.commit()
            flush_claim_records(kern, pending)
        except BaseException:
            # A rollback already ran on the two handled returns above; this covers everything else.
            if conn.in_transaction:
                conn.rollback()
            raise
        return ConsumeAttempt(consumed=True, approval_id=approval_id, grant_claimed=True,
                              cause="CONSUMED", event_id=envelope.event_id)

    # --- AP-8 / AP-9: survives a provable failure; frozen after an unknown outcome -----------------

    def note_provable_failure(self, approval_id: str) -> Approval:
        """AP-8 — ### SURVIVES A PROVABLY-FAILED ATTEMPT. NON_PRODUCING:ENUMERATED_NO_OP: it writes
        nothing and emits nothing, and the approval remains GRANTED, free to authorize a NEW pipeline
        instance under the same commit_key, consumed exactly once (§20). (See the module note on the
        §3.9 authority question: this row is written from GRANTED, as the table states.)"""
        approval = self.require(approval_id)
        if approval.frozen or approval.state is not ApprovalState.GRANTED:
            self._record_illegal(approval, Trigger.ATTEMPT_FAILED_PROVABLY, actor_id="system")
            raise IllegalTransition(
                f"AP-8 applies to a live GRANTED approval; {approval_id!r} is "
                f"{approval.state.value}{' (frozen)' if approval.frozen else ''}.")
        return approval  # a true no-op: nothing written, nothing emitted

    def freeze(
        self, approval_id: str, *, unknown_outcome_ref: str, effect_grant_id: str,
        actor_id: str = "system", correlation_id: str | None = None,
        causation_id: str | None = None, trace_id: str | None = None, event_id: str | None = None,
    ) -> TransitionResult:
        """AP-9 — ### FROZEN AFTER AN UNKNOWN-OUTCOME ATTEMPT, NOT REUSABLE until reality established.

        `ApprovalFrozen` is the SOLE canonical evidence of the freeze (ER-16): the rebuild sets
        `frozen=true` from its PRESENCE, never from `OutcomeUnknown` AND NOT `RealityEstablished`.
        The event binds the exact chain that froze it (`unknown_outcome_ref`, `effect_grant_id`).
        """
        if not str(unknown_outcome_ref or "").strip() or not str(effect_grant_id or "").strip():
            raise GuardNotSatisfied(
                "AP-9 binds the exact unknown-outcome chain that froze it (ER-16): both "
                "unknown_outcome_ref and effect_grant_id are required.")
        approval = self.require(approval_id)
        if approval.frozen or approval.state is not ApprovalState.GRANTED:
            self._record_illegal(approval, Trigger.ATTEMPT_OUTCOME_UNKNOWN, actor_id=actor_id)
            raise IllegalTransition(
                f"AP-9 freezes a live GRANTED approval; {approval_id!r} is "
                f"{approval.state.value}{' (already frozen)' if approval.frozen else ''}.")
        now = format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            cursor = conn.execute(
                "UPDATE approvals SET frozen = 1, unknown_outcome_ref = ?, effect_grant_id = ?, "
                "frozen_at = ?, version = version + 1, updated_at = ? "
                "WHERE tenant = ? AND approval_id = ? AND state = 'GRANTED' AND frozen = 0",
                (unknown_outcome_ref, effect_grant_id, now, now, self._tenant, approval_id))
            if cursor.rowcount != 1:
                raise StateConflict(
                    f"AP-9 matched {cursor.rowcount} rows for {approval_id!r}: it moved under us.")
            frozen = self.require(approval_id)
            envelope = self._envelope(
                event_name="ApprovalFrozen", transition_id="AP-9", approval=frozen,
                aggregate_version=self._next_version(approval_id), actor_type="system",
                actor_id=actor_id, payload={
                    "frozen": True, "unknown_outcome_ref": unknown_outcome_ref,
                    "effect_grant_id": effect_grant_id, "frozen_at": now},
                correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                event_id=event_id, now=now)
            self._outbox().emit(envelope)
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        return TransitionResult(
            transition_id="AP-9", approval=frozen, from_state=ApprovalState.GRANTED,
            to_state=ApprovalState.GRANTED, event_ids=(envelope.event_id,),
            event_names=("ApprovalFrozen",))

    # --- the dark seam: render the durable approval for the checkpoint -----------------------------

    def as_approval_record(self, approval_id: str) -> ApprovalRecord:
        """### THE INERT DARK SEAM (entity §38, task §0.10). The checkpoint validates an approval at
        steps 1–2 and already takes an `ApprovalRecord` as a typed INPUT; M4 is the durable approval
        it reads. This renders one from the row so a checkpoint COULD consume it. It is inert: no
        production caller exists, and nothing here enables a live effect."""
        approval = self.require(approval_id)
        return ApprovalRecord(
            approval_id=approval.approval_id, tenant=approval.tenant,
            actor_id=(approval.granted_by or ""), actor_kind=HUMAN,
            authority=(approval.required_authority or "owner"), state=approval.state.value,
            fingerprint=approval.material_facts_fingerprint,
            canonical_payload=approval.canonical_payload.encode("utf-8"),
            fingerprint_version=approval.fingerprint_version,
            entity_versions=approval.entity_versions, policy_version=approval.policy_version,
            granted_at=_parse_instant(approval.granted_at or approval.requested_at),
            expires_at=_parse_instant(approval.expires_at))

    # --- the strict-order consumer & replay -------------------------------------------------------

    def reference_resolver(self, aggregate_type: str, aggregate_id: str) -> bool:
        """Does the referenced approval exist yet, FOR THIS TENANT? M-26's question, tenant-scoped."""
        if aggregate_type != AGGREGATE_TYPE:
            return True
        return self._conn.execute(
            "SELECT 1 FROM approvals WHERE tenant = ? AND approval_id = ?",
            (self._tenant, aggregate_id)).fetchone() is not None

    def consume_event(
        self, envelope: EventEnvelope, *, inbox: DedupInbox | None = None, drain: bool = True,
    ) -> ConsumedTransition:
        """Consume one canonical `approval` event idempotently through P5's dedup inbox.

        ### THE DRIVING FACT COMES FROM THE EVENT, AND REPLAY CREATES ZERO AUTHORITY. Reconstruction
        advances the durable row to match the event's state WITHOUT re-granting, WITHOUT running the
        claim CAS, and WITHOUT any external effect (GR-11, K-3). ### IT CONSUMES THE COMPLETE
        AGGREGATE STREAM (P6-D11): an event that names no M4 state change (an `IllegalTransition
        Attempted` riding the strict aggregate, an already-applied event) is a cursor advance and
        nothing else — a consumer that filtered to the Approval family alone would block on a
        predecessor it discarded and never unblock. Redelivery is a no-op by the inbox (GR-4);
        an out-of-order event parks on its unapplied `previous_aggregate_version` (§8), and
        `drain_handler_for` releases a parked cohort the moment its predecessor lands.
        """
        target_id = envelope.aggregate_id
        box = inbox or DedupInbox(
            self._conn, tenant=self._tenant, consumer_id=CONSUMER_ID, clock=self._clock,
            reference_resolver=self.reference_resolver)
        outcome: dict[str, Any] = {"transition": None, "refusal": None}

        def handler(event: EventEnvelope) -> None:
            approval = self.get(event.aggregate_id)
            if approval is None:
                outcome["refusal"] = (
                    f"{event.event_name} references approval {event.aggregate_id!r}, which does not "
                    f"exist for tenant {self._tenant!r}. Consumed once, nothing persisted.")
                return
            target = _event_target_state(event)
            if target is None or approval.state is target or approval.is_terminal:
                # A marker, an already-reconstructed state, or a terminal row: advance the cursor
                # over the COMPLETE stream, change nothing (and never re-grant into an effect).
                return
            outcome["transition"] = self._reconstruct_locked(approval, event, target)

        result = box.consume(
            envelope, handler,
            requires=((AGGREGATE_TYPE, target_id),),
            requires_existing=((AGGREGATE_TYPE, target_id),),
            drain_handler_for=((lambda _parked: handler) if drain else None))
        return ConsumedTransition(
            consume=result, transition=outcome["transition"], refusal=outcome["refusal"])

    def rebuild(self, approval_id: str, *, events: list[EventEnvelope] | None = None,
                infer_frozen_from_absence: bool = False) -> ReconstructedApproval:
        """### A FULL-HISTORY FOLD OF ONE APPROVAL — SANDBOXED, ZERO AUTHORITY (GR-11, ER-2).

        It reconstructs state from the event stream and creates NOTHING: no grant is minted, no
        authority is granted, nothing is consumed into an effect, the outside world is untouched.

        ### `frozen` IS REBUILT FROM THE PRESENCE OF `ApprovalFrozen`, NEVER FROM AN ABSENCE (ER-16).
        `infer_frozen_from_absence` exists ONLY to prove the wrong way stays wrong: this method never
        derives `frozen` from `OutcomeUnknown` AND NOT `RealityEstablished`, so the flag is honoured
        only when the parameter is False (the real path); passing True is a fault the probe injects to
        show M4 does not do it. An absence is only as true as the fold is complete and correctly
        ordered, and a safety-critical quarantine may not depend on either.
        """
        stream = events if events is not None else self._event_stream(approval_id)
        state: ApprovalState | None = None
        frozen = False
        for event in stream:
            target = _event_target_state(event)
            if target is not None:
                state = target
            if event.event_name == "ApprovalFrozen":
                frozen = True  # POSITIVE evidence, the only way this becomes true
        if infer_frozen_from_absence:
            # DELIBERATELY LEFT INERT. The wrong inference would set frozen from an M3-chain absence;
            # M4 refuses to, so this branch changes nothing. The probe checks the flag is unmoved.
            pass
        return ReconstructedApproval(
            approval_id=approval_id, state=state, frozen=frozen,
            grants_minted=0, approvals_granted=0, approvals_consumed=0, external_effects=0)

    # --- shared transition plumbing ---------------------------------------------------------------

    def _simple_transition(
        self, approval: Approval, trigger: Trigger, *, actor_type: str, actor_id: str,
        payload: Mapping[str, Any], correlation_id: str | None, causation_id: str | None,
        trace_id: str | None, event_id: str | None,
    ) -> TransitionResult:
        """One state-only transition (deny/revoke/expire): the state row and its event, or neither."""
        candidates = legal_transitions(approval.state, trigger, frozen=approval.frozen)
        if not candidates:
            self._record_illegal(approval, trigger, actor_id=actor_id)
            raise IllegalTransition(
                f"{trigger.value} is not legal for an approval in {approval.state.value}"
                f"{' (frozen)' if approval.frozen else ''} (GR-1, [C-4]). No state change persisted; "
                f"`IllegalTransitionAttempted` recorded to audit and security."
                + (" No timer moves or unfreezes a frozen approval (GR-6)."
                   if trigger is Trigger.TIMER_FIRED else ""))
        row = candidates[0]
        assert row.to_state is not None
        now = format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            cursor = conn.execute(
                "UPDATE approvals SET state = ?, version = version + 1, updated_at = ? "
                "WHERE tenant = ? AND approval_id = ? AND state = ? AND frozen = 0",
                (row.to_state.value, now, self._tenant, approval.approval_id, approval.state.value))
            if cursor.rowcount != 1:
                raise StateConflict(
                    f"{row.id} matched {cursor.rowcount} rows for {approval.approval_id!r}: it moved "
                    f"under us (GR-3). Reload and decide again.")
            after = self.require(approval.approval_id)
            event_ids: list[str] = []
            for name in row.events:
                envelope = self._envelope(
                    event_name=name, transition_id=row.id, approval=after,
                    aggregate_version=self._next_version(approval.approval_id),
                    actor_type=actor_type, actor_id=actor_id, payload=dict(payload),
                    correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                    event_id=event_id, now=now, consequential=row.consequential)
                self._outbox().emit(envelope)
                event_ids.append(envelope.event_id)
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        return TransitionResult(
            transition_id=row.id, approval=after, from_state=approval.state, to_state=row.to_state,
            event_ids=tuple(event_ids), event_names=row.events)

    def _void(
        self, approval: Approval, to_state: ApprovalState, cause: str, *,
        drift_diff: str | None, actor_id: str, correlation_id: str | None,
        causation_id: str | None, trace_id: str | None,
    ) -> TransitionResult:
        """AP-4/4p/5 — GRANTED → VOID_ON_*, writing the void reason and (for drift) the diff, and
        emitting `ApprovalVoided{cause, drift_diff?}`. No grant is minted; no effect occurs."""
        now = format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            cursor = conn.execute(
                "UPDATE approvals SET state = ?, version = version + 1, void_reason = ?, "
                "drift_diff = ?, updated_at = ? "
                "WHERE tenant = ? AND approval_id = ? AND state = 'GRANTED' AND frozen = 0",
                (to_state.value, cause, drift_diff, now, self._tenant, approval.approval_id))
            if cursor.rowcount != 1:
                raise StateConflict(
                    f"AP void matched {cursor.rowcount} rows for {approval.approval_id!r}: it moved "
                    f"under us (GR-3).")
            after = self.require(approval.approval_id)
            payload: dict[str, Any] = {"cause": cause}
            if drift_diff is not None:
                payload["drift_diff"] = drift_diff
            envelope = self._envelope(
                event_name="ApprovalVoided", transition_id=TRANSITIONS_BY_ID[
                    {"drift": "AP-4", "policy": "AP-4p", "brake": "AP-5"}[cause]].id,
                approval=after, aggregate_version=self._next_version(approval.approval_id),
                actor_type="system", actor_id=actor_id, payload=payload,
                correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                event_id=None, now=now)
            self._outbox().emit(envelope)
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        return TransitionResult(
            transition_id="AP-4" if cause == "drift" else "AP-4p" if cause == "policy" else "AP-5",
            approval=after, from_state=ApprovalState.GRANTED, to_state=to_state,
            event_ids=(envelope.event_id,), event_names=("ApprovalVoided",))

    def _reconstruct_locked(
        self, approval: Approval, event: EventEnvelope, target: ApprovalState,
    ) -> TransitionResult:
        """Advance the durable row to match a durable event — reconstruction, not a live transition.

        Runs inside the inbox's own commit (M-24): no BEGIN, no COMMIT. It sets state, and for a
        freeze the flag and its chain, WITHOUT re-granting, WITHOUT the claim CAS, WITHOUT any effect.
        A frozen reconstruction reads the flag from `ApprovalFrozen`'s presence (ER-16).
        """
        conn = self._conn
        now = format_instant(self._clock())
        if event.event_name == "ApprovalFrozen":
            conn.execute(
                "UPDATE approvals SET frozen = 1, unknown_outcome_ref = ?, effect_grant_id = ?, "
                "frozen_at = ?, version = version + 1, updated_at = ? "
                "WHERE tenant = ? AND approval_id = ? AND frozen = 0",
                (event.payload.get("unknown_outcome_ref"), event.payload.get("effect_grant_id"),
                 event.payload.get("frozen_at") or now, now, self._tenant, approval.approval_id))
            after = self.require(approval.approval_id)
            return TransitionResult(
                transition_id="AP-9", approval=after, from_state=approval.state,
                to_state=approval.state, event_names=("ApprovalFrozen",))
        writes = ["state = ?", "version = version + 1", "updated_at = ?"]
        args: list[Any] = [target.value, now]
        if target is ApprovalState.GRANTED:
            writes.append("granted_by = ?")
            args.append(event.payload.get("granted_by") or event.actor_id)
            writes.append("granted_at = ?")
            args.append(now)
        elif target is ApprovalState.CONSUMED:
            writes.append("consumed_at = ?")
            args.append(now)
        elif target in (ApprovalState.VOID_ON_DRIFT, ApprovalState.VOID_ON_BRAKE):
            writes.append("void_reason = ?")
            args.append(event.payload.get("cause"))
            writes.append("drift_diff = ?")
            args.append(event.payload.get("drift_diff"))
        conn.execute(
            f"UPDATE approvals SET {', '.join(writes)} "
            f"WHERE tenant = ? AND approval_id = ? AND state = ? AND frozen = 0",
            (*args, self._tenant, approval.approval_id, approval.state.value))
        after = self.require(approval.approval_id)
        return TransitionResult(
            transition_id="replay", approval=after, from_state=approval.state, to_state=target)

    # --- authority, brake, fingerprint helpers ----------------------------------------------------

    def _require_human_authority(
        self, approval: Approval, actor_id: str, actor_kind: str, authority: str | None, *,
        trigger: str,
    ) -> None:
        """### A MODEL CANNOT GRANT. A COUNTERPARTY CANNOT. Only an authenticated, AUTHORIZED tenant
        human, recorded and ACTIVE (a FK-backed identity, not a text column). A non-human attempt is
        an ILLEGAL transition AND a Sev-0 fraud signal (`CounterpartySelfAuthorizationDetected`)."""
        text = str(actor_id or "").strip()
        if str(actor_kind).upper() != HUMAN:
            self._record_fraud(approval, actor_id=text or "(none)", actor_kind=actor_kind,
                               claimed_action=trigger)
            raise AuthorityRefused(
                f"{trigger} requires an authenticated HUMAN (ADR-003, permanent). actor_kind="
                f"{actor_kind!r} cannot approve — a model, a counterparty claim ('per our call you "
                f"approved this'), a document, a confidence score, a policy default, a retry handler, "
                f"an agent and an admin tool are each MODEL_EXTRACTED at best and a fraud signal, "
                f"never an approval, and no evidence can promote one.")
        row = self._conn.execute(
            "SELECT state, authority_role FROM tenant_humans WHERE tenant = ? AND human_id = ?",
            (self._tenant, text)).fetchone()
        if row is None or row["state"] != "ACTIVE":
            raise AuthorityRefused(
                f"{trigger} names {text!r}, who is not an ACTIVE recorded human of "
                f"{self._tenant!r}. 'An authenticated human' is decoration while granted_by is a "
                f"text column any string satisfies (the argument M1 made for owner_id).")
        required = authority or approval.required_authority
        if required and str(row["authority_role"]) != str(required) and str(required) != "owner":
            raise AuthorityRefused(
                f"{trigger} requires authority {required!r}; {text!r} carries "
                f"{row['authority_role']!r}.")

    def _brake_in_scope(self, action_class: str) -> bool:
        """AP-5's scope test: an ACTIVE brake tenant-wide, on this action class, or platform-global.
        Fail-closed: an unreadable brake is a refusal, never read as "no brake"."""
        try:
            active = BrakeStore(self._conn).active_report(tenant=self._tenant)
        except BrakeStoreUnreachable as exc:
            raise GuardNotSatisfied(
                f"the brake could not be read ({exc}); cannot read the brake NEVER means off.") from exc
        scope = f"action:{str(action_class).strip().lower()}"
        return any(b.scope in (TENANT_WIDE, scope) or b.tenant is None for b in active)

    def _brake_token(self) -> str:
        try:
            return BrakeStore(self._conn).version_token(tenant=self._tenant)
        except BrakeStoreUnreachable as exc:
            raise ApprovalError(
                f"the brake version could not be read at request time ({exc}); an approval pins the "
                f"admission context, and an unreadable brake fails closed.") from exc

    def _refingerprint_and_void_signatures(
        self, approval: Approval, new_fingerprint: str, new_payload: bytes,
    ) -> None:
        """Dual-control signature drift (ADR-005 §3.16): ### DRIFT VOIDS ALL SIGNATURES ⇒ back to
        REQUESTED with a fresh fingerprint, every human signs again. Legal only while REQUESTED (the
        DDL trigger forbids re-fingerprinting a GRANTED approval), and that is the whole point: a
        second approver shown different facts from the first is not a control."""
        conn = self._conn
        now = format_instant(self._clock())
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "DELETE FROM approval_signatures WHERE tenant = ? AND approval_id = ?",
                (self._tenant, approval.approval_id))
            cursor = conn.execute(
                "UPDATE approvals SET material_facts_fingerprint = ?, canonical_payload = ?, "
                "version = version + 1, updated_at = ? "
                "WHERE tenant = ? AND approval_id = ? AND state = 'REQUESTED'",
                (new_fingerprint, new_payload.decode("utf-8"), now, self._tenant,
                 approval.approval_id))
            if cursor.rowcount != 1:
                raise StateConflict(
                    f"signature-drift refresh matched {cursor.rowcount} rows for "
                    f"{approval.approval_id!r}: it moved under us.")
            conn.commit()
        except BaseException:
            conn.rollback()
            raise

    def _compose_payload(
        self, effect: LogicalEffect, commit_key: str, reader: AuthoritativeSourceReader,
        entity_versions: Mapping[str, int], policy_version: str, fingerprint_version: str,
    ) -> bytes:
        """The ONE composer, CONSUMED not reimplemented: live runtime facts -> fp_v1 canonical bytes.
        `reader.read()` raises `SourceUnreadable` on failure, which the caller lets propagate."""
        live_facts = reader.read()
        return canonical_payload(
            material_fact_set(
                effect=effect, commit_key=commit_key, business_facts=live_facts,
                entity_versions=dict(entity_versions), policy_version=str(policy_version)),
            version=fingerprint_version)

    def _read_entity_versions(self, reader: AuthoritativeSourceReader) -> dict[str, int]:
        live = reader.read()
        if not isinstance(live, Mapping):
            return {}
        return {str(k): int(v) for k, v in live.items()}

    # --- illegal-transition & fraud recording -----------------------------------------------------

    def _record_illegal(self, approval: Approval, trigger: Trigger, *, actor_id: str) -> None:
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            version = max(1, self._outbox().last_emitted_version(
                AGGREGATE_TYPE, approval.approval_id))
            identity = (f"{ILLEGAL_ATTEMPT_IDENTITY_PREFIX}|{self._tenant}|{AGGREGATE_TYPE}"
                        f"|{approval.approval_id}|{version}|{trigger.value}|{actor_id}")
            existing = conn.execute(
                "SELECT event_id FROM event_outbox WHERE tenant = ? AND idempotency_identity = ?",
                (self._tenant, identity)).fetchone()
            if existing is None:
                now = format_instant(self._clock())
                envelope = self._envelope(
                    event_name="IllegalTransitionAttempted",
                    transition_id=ILLEGAL_TRANSITION_PRODUCER, approval=approval,
                    aggregate_version=version, actor_type="system", actor_id=actor_id,
                    payload={"machine": "M4", "state": approval.state.value,
                             "trigger": trigger.value, "attempted_by": actor_id},
                    correlation_id=None, causation_id=None, trace_id=None, event_id=None, now=now,
                    idempotency_identity=identity)
                self._outbox().emit(envelope)
                self._store_security_event(envelope, actor_id, "IllegalTransitionAttempted")
            conn.commit()
        except BaseException:
            conn.rollback()
            raise

    def _record_fraud(
        self, approval: Approval, *, actor_id: str, actor_kind: str, claimed_action: str,
    ) -> None:
        """### A COUNTERPARTY CLAIM IS A FRAUD SIGNAL, NEVER AN APPROVAL (ADR-003, F4 security).
        Records both the illegal grant attempt and `CounterpartySelfAuthorizationDetected`."""
        self._record_illegal(approval, Trigger.HUMAN_APPROVED, actor_id=actor_id)
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            identity = (f"{FRAUD_IDENTITY_PREFIX}|{self._tenant}|{approval.approval_id}"
                        f"|{actor_id}|{actor_kind}")
            existing = conn.execute(
                "SELECT event_id FROM event_outbox WHERE tenant = ? AND idempotency_identity = ?",
                (self._tenant, identity)).fetchone()
            if existing is None:
                now = format_instant(self._clock())
                envelope = self._envelope(
                    event_name="CounterpartySelfAuthorizationDetected",
                    transition_id=ILLEGAL_TRANSITION_PRODUCER, approval=approval,
                    aggregate_version=max(1, self._outbox().last_emitted_version(
                        AGGREGATE_TYPE, approval.approval_id)),
                    actor_type="detector", actor_id=actor_id,
                    payload={"source_observation_id": f"{actor_kind}:{actor_id}",
                             "claimed_action": f"{claimed_action} {approval.commit_key}"},
                    correlation_id=None, causation_id=None, trace_id=None, event_id=None, now=now,
                    idempotency_identity=identity)
                self._outbox().emit(envelope)
                self._store_security_event(
                    envelope, actor_id, "CounterpartySelfAuthorizationDetected")
            conn.commit()
        except BaseException:
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

    def _event_stream(self, approval_id: str) -> list[EventEnvelope]:
        rows = self._conn.execute(
            "SELECT envelope_json FROM event_outbox WHERE tenant = ? AND aggregate_type = ? "
            "AND aggregate_id = ? ORDER BY aggregate_version, sequence",
            (self._tenant, AGGREGATE_TYPE, approval_id)).fetchall()
        return [EventEnvelope.from_json(r["envelope_json"]) for r in rows]

    def _next_version(self, approval_id: str) -> int:
        return self._outbox().last_emitted_version(AGGREGATE_TYPE, approval_id) + 1

    def _outbox(self) -> TransactionalOutbox:
        return TransactionalOutbox(self._conn, tenant=self._tenant, clock=self._clock)

    def _envelope(
        self, *, event_name: str, transition_id: str, approval: Approval, aggregate_version: int,
        actor_type: str, actor_id: str, payload: Mapping[str, Any], correlation_id: str | None,
        causation_id: str | None, trace_id: str | None, event_id: str | None, now: str,
        consequential: bool = False, idempotency_identity: str | None = None,
    ) -> EventEnvelope:
        """One canonical envelope on the `approval` aggregate. ### `previous_aggregate_version`
        TRAVELS ON EVERY ONE (P6-D11), which is why this factory is the only place M4 builds one:
        `approval` is STRICT-ORDER, so a consumer tells an intentionally silent version from a lost
        event by the declared predecessor, never by an absence. `emit` re-derives it and REFUSES a
        mismatch, so the link cannot become a lie."""
        pins = approval.pins() if consequential else {}
        return EventEnvelope(
            event_id=event_id or str(uuid.uuid4()),
            event_name=event_name,
            event_version=CONTRACTS[event_name].current_version,
            occurred_at=now, recorded_at=now, tenant_id=self._tenant,
            aggregate_type=AGGREGATE_TYPE, aggregate_id=approval.approval_id,
            aggregate_version=aggregate_version,
            previous_aggregate_version=self._outbox().last_emitted_version(
                AGGREGATE_TYPE, approval.approval_id, below=aggregate_version),
            causation_id=causation_id,
            correlation_id=correlation_id or approval.commit_key,
            producer_component=self._component, producer_transition_id=transition_id,
            actor_type=actor_type, actor_id=actor_id,
            trace_id=trace_id or f"trace-{approval.approval_id}",
            payload=dict(payload), accountable_owner_id=approval.granted_by,
            idempotency_identity=idempotency_identity,
            entity_versions=(pins.get("entity_versions") if consequential else None),
            policy_version=(pins.get("policy_version") if consequential else None),
            brake_version=(pins.get("brake_version") if consequential else None),
            material_facts_fingerprint=(
                pins.get("material_facts_fingerprint") if consequential else None))


# ------------------------------------------------------------------------------------- plumbing

def _event_target_state(event: EventEnvelope) -> ApprovalState | None:
    """The state an approval event reconstructs to, or None for a non-state event (a marker or the
    request that IS the row's creation). `ApprovalVoided` resolves by its `cause`."""
    name = event.event_name
    if name == "ApprovalGranted":
        return ApprovalState.GRANTED
    if name == "ApprovalDenied":
        return ApprovalState.DENIED
    if name == "ApprovalExpired":
        return ApprovalState.EXPIRED
    if name == "ApprovalRevoked":
        return ApprovalState.REVOKED
    if name == "ApprovalConsumed":
        return ApprovalState.CONSUMED
    if name == "ApprovalVoided":
        return (ApprovalState.VOID_ON_BRAKE
                if event.payload.get("cause") == VOID_CAUSE_BRAKE else ApprovalState.VOID_ON_DRIFT)
    return None  # ApprovalRequested (creation), ApprovalFrozen (flag), F14 markers


def _sha256_hex(payload: bytes) -> str:
    import hashlib
    return hashlib.sha256(payload).hexdigest()


def _row_to_approval(row: Any) -> Approval:
    return Approval(
        tenant=row["tenant"], approval_id=row["approval_id"], commit_key=row["commit_key"],
        action_class=row["action_class"], state=ApprovalState(row["state"]), version=row["version"],
        material_facts_fingerprint=row["material_facts_fingerprint"],
        canonical_payload=row["canonical_payload"], fingerprint_version=row["fingerprint_version"],
        entity_versions_json=row["entity_versions_json"], policy_version=row["policy_version"],
        brake_version=row["brake_version"], gate_decision=row["gate_decision"],
        required_authority=row["required_authority"], required_signatures=row["required_signatures"],
        rendered_facts=row["rendered_facts"], requested_at=row["requested_at"],
        expires_at=row["expires_at"], granted_by=row["granted_by"], granted_at=row["granted_at"],
        consumed_at=row["consumed_at"], void_reason=row["void_reason"], drift_diff=row["drift_diff"],
        frozen=bool(row["frozen"]), unknown_outcome_ref=row["unknown_outcome_ref"],
        effect_grant_id=row["effect_grant_id"], frozen_at=row["frozen_at"])


# Re-exported so a caller reads one name rather than importing the migration for a constant.
STATES: tuple[str, ...] = APPROVAL_STATES
TERMINAL: tuple[str, ...] = TERMINAL_APPROVAL_STATES
