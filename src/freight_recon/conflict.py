"""Machine M7 — the Conflict: one `conflicts` row per disputed field that makes disagreement a
DECISION A HUMAN OWNS rather than a winner a machine PICKED.

    ### A CONFLICT IS TWO OR MORE MUTUALLY EXCLUSIVE CLAIMS OR OBSERVATIONS ON THE SAME FIELD. ITS
    ### PURPOSE IS TO MAKE DISAGREEMENT VISIBLE AND BLOCKING — THE MECHANISM BY WHICH NEYMA NEVER
    ### SILENTLY CHOOSES. IT IS NOT `unknown`, NOT AN ERROR, AND NOT RESOLVABLE BY RECENCY,
    ### CONFIDENCE, A MODEL, OR A CLOCK (entity §2/§3/§4, ADR-007 §5).

    ### THE INVARIANT: WHILE A CONFLICT IS RAISED, OPEN OR ESCALATED, THE FIELD IS `conflicting` AND
    ### BLOCKS EVERY CONSEQUENTIAL ACTION ON THAT ENTITY (entity §36, machine §16, GR-10, ADR-002 C6).

### WHAT THIS MACHINE OWNS, AND WHAT IT ONLY FEEDS.

It owns the five states and the CF-1…CF-7 transitions of `07-conflict.machine.md` §14, and it is A
registered producer of the five already-registered F7 `Conflict*` events (`ConflictRaised` is a
coordination event with three producers — CF-1 here, IB-6 in M6, EF-4c in M3; M7 owns the CF-1 half).
It rides P5's transactional outbox, dedup inbox and durable timers exactly as M3…M6 do.

### THE CONFLICT ROW IS THE DURABLE FIELD CONDITION (task §3.9). There is no separate field-condition
table (that is M8+); `(tenant, entity_ref, field)` plus the partial unique index over the three OPEN
states makes "is this field `conflicting`?" one tenant-first read. `native_projection()` projects the
row into the checkpoint's EXISTING `NativeClaim(conflicting=…)` and `EvidenceCondition.CONFLICTING`
types WITHOUT importing the checkpoint — a conflict is an INPUT to the gate and never a gate. P3 stays
the sole gate minter and M3 the single effect authority (CLAUDE.md rule 17); M7 mints no gate decision.

### CLOSURE HAS EXACTLY TWO WAYS AND NEVER A THIRD (ADR-007 §5.3). CF-3 needs a REGISTERED, versioned,
deterministic rule with an id; CF-4 needs a valid `decision_ref` naming an authenticated ACTIVE human.
Not recency. Not confidence. Not source priority — unless a registered rule says so, with an id. Not a
model. Not a timer. `AutoResolve` and any `TimerFired`-to-resolved is ILLEGAL (machine §15): a clock
knows nothing about freight. The rule SET ships EMPTY (V5 stays open); the fail-closed default is that
every conflict goes to a human, and the CF-3 MECHANISM is complete and exercised against a rule the
caller registers for itself.

### THE TIMER ESCALATES AND NEVER RESOLVES (CF-5). `AgeThresholdCrossed` on the existing P5 durable
timer substrate moves OPEN → ESCALATED and nothing else. A CONFLICT NEVER EXPIRES (entity §26, machine
§12/§23): it ages, and it escalates. No sweep, no second timer mechanism.

### THE NEW PARTY ATTACHES (CF-7). A second detection of the same `(entity, field)` disagreement
ATTACHES a party to the existing open Conflict (entity §33, machine §17) — the partial unique index is
the serialization point, and `ConflictPartyAttached` is load-bearing for replay: without it a
full-history rebuild reproduces a STALE PARTY SET. Each party carries its OWN `provenance_class`,
carried and NEVER strengthened (ER-14, R-P2); an INFERRER_VS_OWNER conflict specifically records that
one party is OWNER_ASSERTED — the evidence of why the inferrer did not overwrite it.

### THE M6 SEAM (task §3.6, M7-AQ-1). `IB-6` already emits a `ConflictRaised` for its
INFERRER_VS_OWNER disagreement, minting its own conflict id and writing NO M7 row (there was no table
when M6 shipped). M7 DOES NOT REWRITE M6, DOES NOT mint a second `ConflictRaised` for a disagreement M6
already announced, and DOES NOT silently swallow the seam: it is recorded as an M7-owned obligation
(`M7_AQ1_SEAM`) and REPORTED. M7 builds CF-1 fully for the conflicts it raises.

### THE M3 SEAM (task §3.7, M7-AQ-2). `EF-4c` (a readback contradicting the approved fingerprint) is a
registered producer of `ConflictRaised` but the shipped M3 emits `VerificationConflict` alone and moves
ATTEMPTED → UNKNOWN_OUTCOME. M7 DOES NOT edit `external_effect.py`, DOES NOT rewrite/shorten/route around
`UNKNOWN_OUTCOME`, and never launders a readback contradiction into a normal failure. A
`READBACK_VS_APPROVED` conflict M7 raises blocks like any other. M7-AQ-2 is REPORTED, not answered.

### THE F14 TRIPWIRE THAT IS MINE (task §3.10). `IllegalTransitionAttempted` (GR-1, mandatory) on every
illegal `(state, trigger)`, to audit AND security. NOT mine: `ProvenanceStrengtheningAttempted` (P7's
emission half — the party-provenance REFUSAL is present now, the F14 emission is not),
`OwnerAssertedOverwriteAttempted` (M6's), `CrossTenantAccessAttempted` (the inbox's).

### IT SHIPS DARK. Nothing under `src/freight_recon/` imports this module; the only script that may is
`scripts/probe_phase6_conflict.py`. It joins no importer, queue or live channel, authorizes no effect,
mints no gate decision, and the production `GateRegistry` stays EMPTY. M7's product form is a conflict
inbox a human works through — so that inbox is precisely the thing that does not arrive with it.
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
from .event_timers import DurableTimers, TimerFired
from .migrations.phase6_conflicts import (
    CONFLICT_KINDS,
    CONFLICT_STATES,
    DECISION_REF_KINDS,
    OPEN_CONFLICT_STATES,
    PARTY_KINDS,
    PROVENANCE_CLASSES,
    TERMINAL_CONFLICT_STATES,
)
from .tenant import require_tenant

# The aggregate this machine owns. The same string M6's IB-6 rides its co-committed ConflictRaised on,
# because it is the same coordination event on the same aggregate type — several origins, one fact.
AGGREGATE_TYPE = "conflict"

# entity §5 — the Reconciliation Service raises and owns conflicts.
PRODUCER_COMPONENT = "reconciliation_service"

# The one consumer identity M7 presents to the dedup inbox. Fixed, because the dedup key is
# `(tenant, consumer_id, event_id)` and a renamed consumer would re-arm every duplicate.
CONSUMER_ID = "m7-conflict"

# GR-1's producer id for `IllegalTransitionAttempted` — the RULE, not a transition. Identical to
# M1..M6's, for the same reason.
ILLEGAL_TRANSITION_PRODUCER = "GR-1"

# A refusal advances no version; two refusals against one conflict at one version would otherwise
# collide on one idempotency identity — the poison-loop defect M1 shipped. Applied here.
ILLEGAL_ATTEMPT_IDENTITY_PREFIX = "ita_v1"

# The durable-timer kind CF-5 arms and reads. There is EXACTLY ONE conflict timer kind, and it maps to
# ESCALATION and to nothing else — that is how "a timer never resolves a conflict" is structural rather
# than a promise. No timer_kind maps to a resolution.
TIMER_KIND_AGE_THRESHOLD = "conflict_age_threshold"

HUMAN = "HUMAN"
OWNER_ASSERTED = "OWNER_ASSERTED"

# ### THE M7-OWNED SEAM RECORD (task §3.6, M7-AQ-1 / §3.7, M7-AQ-2). A registered non-CF-1 producer
# (IB-6, EF-4c) may emit `ConflictRaised` with no M7 aggregate row. M7 does not rewrite those machines
# and does not mint a second event; it names the seam here and REPORTS it. `conflict_raised_producers`
# is read straight off the canonical contract so this record can never drift from the registry.
M7_AQ1_SEAM = (
    "IB-6 (M6) emits a registered ConflictRaised for an INFERRER_VS_OWNER disagreement and writes NO "
    "M7 conflicts row; EF-4c (M3) is a registered producer of ConflictRaised but the shipped M3 emits "
    "VerificationConflict alone. M7 does not rewrite M6 or M3, does not mint a second ConflictRaised "
    "for a disagreement already announced, and does not silently swallow the seam. REPORTED as "
    "M7-AQ-1 / M7-AQ-2; only what every reading agrees on is built (task §3.6/§3.7)."
)


class M7Error(RuntimeError):
    """This machine will not do what was asked. Never degraded into a partial transition."""


class UnknownConflict(M7Error):
    """No `conflicts` row with this id exists FOR THIS TENANT. Indistinguishable from "belongs to
    another tenant" on purpose — [C-1] rejects a cross-tenant question."""


class GuardNotSatisfied(M7Error):
    """The (state, trigger) pair IS legal here and a precondition is false. No event is emitted."""


class IllegalTransition(M7Error):
    """GR-1 / [C-4]. The (state, trigger) pair is not enumerated (or §15 forbids the shape). Raised
    AFTER `IllegalTransitionAttempted` is recorded, which is the point of recording it."""


class StateConflict(M7Error):
    """A state-guarded UPDATE matched zero rows: the conflict moved under us (GR-3). Reload."""


class MalformedConflict(M7Error):
    """The inputs to a raise are not a canonical conflict — a kind off the closed set, an empty field,
    a party with no reference. Fail closed; nothing is persisted."""


# --------------------------------------------------------------------------------- the state set

class ConflictState(str, Enum):
    RAISED = "RAISED"
    OPEN = "OPEN"
    ESCALATED = "ESCALATED"
    RESOLVED_BY_RULE = "RESOLVED_BY_RULE"
    RESOLVED_BY_HUMAN = "RESOLVED_BY_HUMAN"


class ConflictKind(str, Enum):
    SYSTEM_VS_SYSTEM = "SYSTEM_VS_SYSTEM"
    CLAIM_VS_CLAIM = "CLAIM_VS_CLAIM"
    CLAIM_VS_OBSERVATION = "CLAIM_VS_OBSERVATION"
    INFERRER_VS_OWNER = "INFERRER_VS_OWNER"
    READBACK_VS_APPROVED = "READBACK_VS_APPROVED"
    RULE_VS_RULE = "RULE_VS_RULE"


class Trigger(str, Enum):
    """The closed set of driving facts, named from §14's triggers and §33's "Consumes", plus the
    illegal triggers §15 names by hand so GR-1 answers them uniformly."""

    CONFLICT_DETECTED = "ConflictDetected"                # CF-1 (raise) / CF-7 (a second detection)
    ACKNOWLEDGED = "Acknowledged"                          # CF-2
    DETERMINISTIC_RULE_APPLIES = "DeterministicRuleApplies"  # CF-3 / CF-6-rule
    HUMAN_RESOLVED = "HumanResolved"                       # CF-4 / CF-6-human
    AGE_THRESHOLD_CROSSED = "AgeThresholdCrossed"          # CF-5 (durable timer)
    # ### THE ILLEGAL TRIGGERS (machine §15). A clock knows nothing about freight; a model states no
    # facts; a resolution with no basis is not a resolution.
    AUTO_RESOLVE = "AutoResolve"
    TIMER_FIRED_TO_RESOLVED = "TimerFiredToResolved"


OPEN_STATES: frozenset[ConflictState] = frozenset(ConflictState(s) for s in OPEN_CONFLICT_STATES)
TERMINAL_STATES: frozenset[ConflictState] = frozenset(
    ConflictState(s) for s in TERMINAL_CONFLICT_STATES)

# The five F7 contracts this machine MINTS — exactly the registered set, no sixth `Conflict*` name.
PRODUCED_CONTRACTS: frozenset[str] = frozenset(
    ("ConflictRaised", "ConflictOpened", "ConflictPartyAttached", "ConflictEscalated",
     "ConflictResolved"))

# Read straight off the canonical contract so the seam record cannot drift from the registry.
CONFLICT_RAISED_PRODUCERS: tuple[str, ...] = tuple(CONTRACTS["ConflictRaised"].producers)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------------------------ the inputs

@dataclass(frozen=True)
class Party:
    """One disagreeing claim or observation on the disputed field. `provenance_class` is the party's
    OWN, assigned at detection and carried verbatim — never strengthened (ER-14, R-P2). `party_kind`
    is the polymorphic discriminator; `party_ref` is the reference (a claim id, an observation id, a
    readback token, a rule id, a system reading)."""

    party_ref: str
    party_kind: str                    # one of PARTY_KINDS
    provenance_class: str              # one of the six canonical classes
    stated_value: str | None = None    # what this party says the field is (the conflicting value)

    def _validate(self) -> None:
        if not str(self.party_ref or "").strip():
            raise MalformedConflict("a conflict party carries a reference; an empty party_ref is not "
                                    "a party.")
        if self.party_kind not in PARTY_KINDS:
            raise MalformedConflict(
                f"party_kind {self.party_kind!r} is not one of {list(PARTY_KINDS)} (task §3.9).")
        if self.provenance_class not in PROVENANCE_CLASSES:
            raise MalformedConflict(
                f"party provenance_class {self.provenance_class!r} is not one of the six canonical "
                f"classes {list(PROVENANCE_CLASSES)} ([C-7]).")


# ------------------------------------------------------------------------------------ the row

@dataclass(frozen=True)
class Conflict:
    """One `conflicts` row, as the machine reads it."""

    tenant: str
    conflict_id: str
    entity_ref: str
    field: str
    kind: str
    state: ConflictState
    version: int
    owner_id: str
    rule_id: str | None
    decision_ref: str | None
    decision_ref_kind: str | None
    decision_human_id: str | None
    escalation_at: str | None
    exposure: str | None

    @property
    def is_open(self) -> bool:
        return self.state in OPEN_STATES

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    def native_projection(self) -> "NativeConflictProjection":
        """### THE SEAM WITH THE CHECKPOINT (task §3.9). Project this conflict into the shapes step 4
        reads (`checkpoint.NativeClaim` and `checkpoint.ProvenancedFact`) WITHOUT importing the
        checkpoint. While the conflict is OPEN the field is `conflicting` and step 4 refuses
        (`CLAIM_CONFLICTING` / `EVIDENCE_NOT_CONSISTENT`); once resolved it leaves the open set, the
        projection is no longer conflicting, and the field unfreezes."""
        conflicting = self.is_open
        return NativeConflictProjection(
            claim_id=self.conflict_id, status="ACTIVE", conflicting=conflicting,
            provenance="SYSTEM_IMPORTED", field=self.field, entity_ref=self.entity_ref,
            evidence_condition=("conflicting" if conflicting else "consistent"))


@dataclass(frozen=True)
class NativeConflictProjection:
    """The fields `checkpoint.NativeClaim` and `checkpoint.ProvenancedFact` read, projected from an M7
    conflict without importing the checkpoint. The probe builds the real types from these and shows
    step 4 refuses — M7 FEEDS the one gate authority, it never duplicates it."""

    claim_id: str
    status: str
    conflicting: bool
    provenance: str
    field: str
    entity_ref: str
    evidence_condition: str


@dataclass(frozen=True)
class TransitionResult:
    transition_id: str                 # the machine row: CF-1..CF-7
    conflict: Conflict
    from_state: ConflictState | None
    to_state: ConflictState
    event_ids: tuple[str, ...] = ()
    event_names: tuple[str, ...] = ()
    event_producer: str | None = None  # the transition id the emitted event names (CF-3/CF-4 for CF-6)
    attached_party_ref: str | None = None
    coalesced: bool = False            # a raise that found an existing open conflict and attached


@dataclass(frozen=True)
class ReconstructedConflict:
    """A full-history fold of one conflict's event stream — sandboxed, zero authority (GR-11, K-3).

    Every count is of what the REBUILD created, which is always zero: no resolution minted, no
    duplicate conflict, no lost party, no new authority, no external effect. The parties set is the
    UNION of ConflictRaised's set with every subsequent attach (order-independent)."""

    conflict_id: str
    state: ConflictState | None
    parties: tuple[str, ...]
    frozen: bool
    resolutions: int = 0
    duplicate_conflicts: int = 0
    lost_parties: int = 0
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

class M7Machine:
    """M7, on an existing connection, bound to ONE tenant. Bound at construction so a caller cannot
    re-point it at another tenant and put [C-1] in its own hands.

    `registered_rules` is the CF-3 registry: a rule may resolve a conflict only if it is registered
    here, with an id. It defaults to EMPTY — V5 is open, and the fail-closed default is that every
    conflict goes to a human. A test or probe registers its own rule to exercise the CF-3 mechanism;
    NO freight resolution rule is invented in this module (ADR-007 §8, task §3.11)."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        tenant: str,
        registered_rules: frozenset[str] | Sequence[str] | None = None,
        clock: Callable[[], datetime] | None = None,
        producer_component: str = PRODUCER_COMPONENT,
    ) -> None:
        if getattr(conn, "row_factory", None) is not sqlite3.Row:
            raise M7Error(
                "M7Machine reads columns by name and requires `row_factory = sqlite3.Row`.")
        self._conn = conn
        self._tenant = require_tenant(tenant, context="M7Machine")
        self._registered_rules = frozenset(registered_rules or ())
        self._clock = clock or _utc_now
        self._component = producer_component

    @property
    def tenant(self) -> str:
        return self._tenant

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    # --- reads -----------------------------------------------------------------------------------

    def get(self, conflict_id: str) -> Conflict | None:
        row = self._conn.execute(
            "SELECT * FROM conflicts WHERE tenant = ? AND conflict_id = ?",
            (self._tenant, conflict_id),
        ).fetchone()
        return _row_to_conflict(row) if row is not None else None

    def require(self, conflict_id: str) -> Conflict:
        found = self.get(conflict_id)
        if found is None:
            raise UnknownConflict(
                f"no conflict {conflict_id!r} for tenant {self._tenant!r}. This machine does not look "
                f"outside its tenant to find out whether it exists elsewhere ([C-1]).")
        return found

    def open_conflict_for(self, entity_ref: str, field: str) -> Conflict | None:
        """### THE FIELD CONDITION READ (task §3.9). At most one row can match — the partial unique
        index guarantees it. The conflict row IS the durable "(tenant, entity_ref, field) is
        conflicting" fact."""
        row = self._conn.execute(
            "SELECT * FROM conflicts WHERE tenant = ? AND entity_ref = ? AND field = ? "
            f"AND state IN ({','.join('?' for _ in OPEN_CONFLICT_STATES)})",
            (self._tenant, entity_ref, field, *OPEN_CONFLICT_STATES),
        ).fetchone()
        return _row_to_conflict(row) if row is not None else None

    def is_field_conflicting(self, entity_ref: str, field: str) -> bool:
        return self.open_conflict_for(entity_ref, field) is not None

    def parties(self, conflict_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM conflict_parties WHERE tenant = ? AND conflict_id = ? "
            "ORDER BY attach_seq, party_id",
            (self._tenant, conflict_id)).fetchall()
        return [dict(r) for r in rows]

    def party_refs(self, conflict_id: str) -> frozenset[str]:
        return frozenset(p["party_ref"] for p in self.parties(conflict_id))

    # --- CF-1: the raise (and its coalescing into CF-7) -------------------------------------------

    def raise_conflict(
        self,
        *,
        kind: str | ConflictKind,
        entity_ref: str,
        field: str,
        parties: Sequence[Party],
        owner_id: str,
        conflict_id: str | None = None,
        exposure: str | None = None,
        actor_id: str = "reconciliation",
        actor_kind: str = "system",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """CF-1 — ### DETECTION RAISES A CONFLICT, ASSIGNS A NAMED HUMAN OWNER, AND FREEZES THE FIELD
        IN ONE COMMIT (entity §15, machine §4/§35, GR-10).

        The `conflicts` row is inserted (state RAISED) and every party is written in ONE transaction —
        the row IS the field condition, so the raise and the freeze cannot be two commits and there is
        never a durable state in which the conflict exists while the field is still usable. If an OPEN
        conflict already exists for `(entity_ref, field)` the partial unique index refuses the insert
        and the detection COALESCES into a CF-7 attach — a second detection never creates a second
        conflict (entity §17/§33)."""
        kind_value = _kind_value(kind)
        entity = _require_text(entity_ref, "entity_ref")
        field_name = _require_text(field, "field")
        party_list = list(parties)
        if len(party_list) < 2:
            raise MalformedConflict(
                "a conflict is TWO OR MORE mutually exclusive claims/observations on one field "
                "(entity §2): a single party is not a disagreement.")
        for party in party_list:
            party._validate()
        owner = self._require_named_human(owner_id, "the conflict owner", actor_kind=actor_kind)

        cid = conflict_id or f"conf-{uuid.uuid4().hex[:16]}"
        now = format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            try:
                conn.execute(
                    """
                    INSERT INTO conflicts (
                        tenant, conflict_id, entity_ref, field, kind, state, version, owner_id,
                        rule_id, decision_ref, decision_ref_kind, decision_human_id, escalation_at,
                        exposure, created_at, updated_at
                    ) VALUES (?,?,?,?,?, 'RAISED', 1, ?, NULL, NULL, NULL, NULL, NULL, ?, ?, ?)
                    """,
                    (self._tenant, cid, entity, field_name, kind_value, owner, exposure, now, now),
                )
            except sqlite3.IntegrityError:
                # ### AT MOST ONE OPEN CONFLICT PER FIELD. An OPEN conflict already exists — coalesce
                # this detection into a party attach rather than raise a second conflict (entity §17).
                # EVERY party this detector brought is attached (idempotent for ones already present),
                # so a concurrent detector loses no party and never creates a duplicate conflict.
                conn.rollback()
                existing = self.open_conflict_for(entity, field_name)
                if existing is None:
                    raise
                result: TransitionResult | None = None
                for party in party_list:
                    result = self.attach_party(
                        existing.conflict_id, party, actor_id=actor_id,
                        correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id)
                assert result is not None
                return TransitionResult(
                    transition_id=result.transition_id, conflict=self.require(existing.conflict_id),
                    from_state=result.from_state, to_state=result.to_state,
                    event_ids=result.event_ids, event_names=result.event_names,
                    event_producer=result.event_producer,
                    attached_party_ref=result.attached_party_ref, coalesced=True)
            for seq, party in enumerate(party_list, start=1):
                self._insert_party(cid, party, seq, now)
            created = self.require(cid)
            envelope = self._raise_envelope(created, party_list, owner, actor_kind=actor_kind,
                                            actor_id=actor_id, correlation_id=correlation_id,
                                            causation_id=causation_id, trace_id=trace_id,
                                            event_id=event_id, now=now)
            self._outbox().emit(envelope)
            conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        return TransitionResult(
            transition_id="CF-1", conflict=created, from_state=None, to_state=ConflictState.RAISED,
            event_ids=(envelope.event_id,), event_names=("ConflictRaised",), event_producer="CF-1")

    # --- CF-2: acknowledgement, and arming the escalation timer -----------------------------------

    def acknowledge(
        self,
        conflict_id: str,
        *,
        escalation_at: datetime | str | None = None,
        expected: Conflict | None = None,
        actor_id: str = "operator",
        actor_kind: str = "human",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """CF-2 — RAISED → OPEN. A human acknowledged and owns it. Optionally arms the durable-timer
        escalation deadline (CF-5) IN THE SAME COMMIT — a deadline written separately from the
        transition can be lost while the obligation survives (M-23)."""
        conflict = expected or self.require(conflict_id)
        if conflict.state is not ConflictState.RAISED:
            raise GuardNotSatisfied(
                f"CF-2 acknowledges a RAISED conflict; {conflict_id!r} is {conflict.state.value}.")
        return self._advance(
            conflict, "CF-2", ConflictState.OPEN, event_name="ConflictOpened", payload={},
            event_producer="CF-2", actor_type=("human" if str(actor_kind).upper() == HUMAN
                                               else "system"),
            actor_id=actor_id, writes="", write_args=(), correlation_id=correlation_id,
            causation_id=causation_id, trace_id=trace_id, event_id=event_id,
            after_write=((lambda _now: self._arm_escalation(conflict_id, escalation_at))
                         if escalation_at is not None else None))

    # --- CF-5: escalation, on the existing durable-timer substrate --------------------------------

    def escalate(
        self,
        conflict_id: str,
        *,
        expected: Conflict | None = None,
        actor_id: str = "timer",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """CF-5 — OPEN → ESCALATED on `AgeThresholdCrossed`. ### IT AGES AND ESCALATES; IT NEVER
        RESOLVES (entity §26, machine §37). A conflict never expires — the timer only escalates."""
        conflict = expected or self.require(conflict_id)
        if conflict.state is not ConflictState.OPEN:
            raise GuardNotSatisfied(
                f"CF-5 escalates an OPEN conflict; {conflict_id!r} is {conflict.state.value}.")
        now = format_instant(self._clock())
        return self._advance(
            conflict, "CF-5", ConflictState.ESCALATED, event_name="ConflictEscalated", payload={},
            event_producer="CF-5", actor_type="system", actor_id=actor_id,
            writes="escalation_at = ?", write_args=(now,), correlation_id=correlation_id,
            causation_id=causation_id, trace_id=trace_id, event_id=event_id, now=now)

    def handle_timer_fired(self, trigger: TimerFired, **kw: Any) -> TransitionResult:
        """The durable-timer handler. ### A TIMER ONLY ESCALATES — IT NEVER RESOLVES (machine §15/§37).

        The ONLY timer_kind M7 arms maps to escalation; any other kind arriving here is a
        TimerFired-to-something-else and is ILLEGAL under GR-1. So "a timer never resolves a conflict"
        is structural: there is no timer_kind that reaches a resolution."""
        if trigger.timer_kind != TIMER_KIND_AGE_THRESHOLD:
            self._refuse_illegal(trigger.aggregate_id, Trigger.TIMER_FIRED_TO_RESOLVED,
                                 actor_id=kw.get("actor_id", "timer"))
            raise IllegalTransition(
                f"a durable timer fired with kind {trigger.timer_kind!r} on conflict "
                f"{trigger.aggregate_id!r}; the ONLY conflict timer is an age-threshold ESCALATION "
                f"(machine §15/§37). A clock knows nothing about freight and never resolves a "
                f"conflict — recorded to audit and security under GR-1.")
        return self.escalate(trigger.aggregate_id, correlation_id=trigger.correlation_id,
                             causation_id=trigger.causation_id, actor_id=kw.get("actor_id", "timer"))

    # --- CF-3 / CF-4 / CF-6: resolution -----------------------------------------------------------

    def resolve(
        self,
        conflict_id: str,
        *,
        rule_id: str | None = None,
        decision_ref: str | None = None,
        decision_human_id: str | None = None,
        decision_ref_kind: str = "audit_event",
        expected: Conflict | None = None,
        actor_id: str = "reconciliation",
        actor_kind: str = "system",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """### CLOSURE HAS EXACTLY TWO WAYS AND NEVER A THIRD (ADR-007 §5.3). Resolve by a REGISTERED
        rule (CF-3) or an authenticated human `decision_ref` (CF-4); from ESCALATED the transition is
        CF-6, which DELEGATES to CF-3/CF-4 BY TARGET STATE — never positionally. A resolution with
        neither basis, with both, by a model, by a counterparty, by a timer, or by an unregistered
        rule does NOT resolve."""
        conflict = expected or self.require(conflict_id)
        has_rule = bool(str(rule_id or "").strip())
        has_decision = bool(str(decision_ref or "").strip())

        # ### A RESOLUTION WITH NEITHER A RULE NOR A DECISION IS ILLEGAL (machine §15). Recorded.
        if not has_rule and not has_decision:
            self._refuse_illegal(conflict.conflict_id, Trigger.AUTO_RESOLVE, actor_id=actor_id)
            raise IllegalTransition(
                "a resolution carries a registered rule_id OR an authenticated decision_ref and one "
                "of the two ONLY (ADR-007 §5.3, machine §15). This attempt carried neither — there is "
                "no third way, and a conflict that closes on nothing is a winner nobody chose. "
                "Recorded to audit and security under GR-1.")
        # ### TWO RESOLUTION BASES ARE NOT EXTRA INFORMATION — THEY ARE AN UNRESOLVABLE FACT.
        if has_rule and has_decision:
            raise GuardNotSatisfied(
                "a resolution carries EXACTLY ONE of rule_id | decision_ref (entity §16, ADR-007 "
                "§5.3): both together is two answers to a one-of, and the database CHECK, the event "
                "contract and this guard all refuse it.")

        if conflict.state not in (ConflictState.OPEN, ConflictState.ESCALATED):
            raise GuardNotSatisfied(
                f"a conflict is resolved from OPEN (CF-3/CF-4) or ESCALATED (CF-6); {conflict_id!r} "
                f"is {conflict.state.value}. A RAISED conflict is acknowledged first (CF-2).")

        if has_rule:
            return self._resolve_by_rule(
                conflict, str(rule_id).strip(), actor_id=actor_id, actor_kind=actor_kind,
                correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                event_id=event_id)
        return self._resolve_by_human(
            conflict, str(decision_ref).strip(), decision_human_id, decision_ref_kind,
            actor_id=actor_id, actor_kind=actor_kind, correlation_id=correlation_id,
            causation_id=causation_id, trace_id=trace_id, event_id=event_id)

    def resolve_by_rule(self, conflict_id: str, *, rule_id: str, **kw: Any) -> TransitionResult:
        """CF-3 / CF-6-rule — a REGISTERED, versioned, deterministic rule applies."""
        return self.resolve(conflict_id, rule_id=rule_id, actor_kind=kw.pop("actor_kind", "system"),
                            **kw)

    def resolve_by_human(self, conflict_id: str, *, decision_ref: str, decision_human_id: str,
                         **kw: Any) -> TransitionResult:
        """CF-4 / CF-6-human — an authenticated ACTIVE human resolves with a decision_ref."""
        return self.resolve(conflict_id, decision_ref=decision_ref,
                            decision_human_id=decision_human_id,
                            actor_kind=kw.pop("actor_kind", "human"), **kw)

    def _resolve_by_rule(
        self, conflict: Conflict, rule_id: str, *, actor_id: str, actor_kind: str,
        correlation_id: str | None, causation_id: str | None, trace_id: str | None,
        event_id: str | None,
    ) -> TransitionResult:
        # ### A REGISTERED, VERSIONED RULE — NEVER RECENCY, CONFIDENCE, OR A MODEL. A model actor
        # applying a rule is a model resolving (ER-9/GR-7); the deterministic engine is `system`.
        if str(actor_kind).lower() == "model":
            self._refuse_illegal(conflict.conflict_id, Trigger.DETERMINISTIC_RULE_APPLIES,
                                 actor_id=actor_id)
            raise IllegalTransition(
                "a model never resolves a conflict (GR-7, ER-9): a rule resolution is applied by the "
                "deterministic rule engine, not by a model. Recorded to audit and security under GR-1.")
        if rule_id not in self._registered_rules:
            raise GuardNotSatisfied(
                f"rule {rule_id!r} is not REGISTERED, so it may not resolve this conflict (CF-3, "
                f"ADR-007 §5.3/§8). A confidence threshold, a recency heuristic or a source-priority "
                f"preference wearing a rule's name is not a registered rule — source priority is a "
                f"registered rule with an id or it is NOTHING. The rule SET ships empty (V5 open); "
                f"every conflict goes to a human until a real rule is registered.")
        target = ConflictState.RESOLVED_BY_RULE
        # ### RESOLVED BY TARGET STATE, NEVER POSITIONALLY (machine §14 CF-6). The emitted event names
        # CF-3 whether the conflict came from OPEN or ESCALATED — the producer is chosen by the RESOLVED
        # state it reaches, not by the state it came from.
        row_id = "CF-3" if conflict.state is ConflictState.OPEN else "CF-6"
        return self._advance(
            conflict, row_id, target, event_name="ConflictResolved", payload={"rule_id": rule_id},
            event_producer="CF-3", actor_type="system", actor_id=actor_id,
            writes="rule_id = ?", write_args=(rule_id,), correlation_id=correlation_id,
            causation_id=causation_id, trace_id=trace_id, event_id=event_id)

    def _resolve_by_human(
        self, conflict: Conflict, decision_ref: str, decision_human_id: str | None,
        decision_ref_kind: str, *, actor_id: str, actor_kind: str, correlation_id: str | None,
        causation_id: str | None, trace_id: str | None, event_id: str | None,
    ) -> TransitionResult:
        # ### A COUNTERPARTY NEVER RESOLVES, AND A MODEL NEVER RESOLVES ([C-6], GR-7, ER-9). Only an
        # authenticated, ACTIVE tenant human closes a conflict by decision.
        if str(actor_kind).upper() != HUMAN:
            self._refuse_illegal(conflict.conflict_id, Trigger.HUMAN_RESOLVED, actor_id=actor_id)
            raise IllegalTransition(
                f"a human resolution names an authenticated HUMAN (CF-4, [C-6], ER-9). "
                f"actor_kind={actor_kind!r} — a model, a counterparty's 'per our call we agree', a "
                f"document and a confidence score are each data, never a decision, and none resolves "
                f"a conflict. Recorded to audit and security under GR-1.")
        if decision_ref_kind not in DECISION_REF_KINDS:
            raise GuardNotSatisfied(
                f"decision_ref_kind {decision_ref_kind!r} is not one of {list(DECISION_REF_KINDS)} "
                f"(K-1). A human decision resolves into an audit_events row; a rule-basis decision_ref "
                f"resolves into a rule (M12, not built — carried, not FK-backed).")
        human = self._require_named_human(decision_human_id, "the human behind decision_ref",
                                          actor_kind="human")
        return self._advance(
            conflict, ("CF-4" if conflict.state is ConflictState.OPEN else "CF-6"),
            ConflictState.RESOLVED_BY_HUMAN, event_name="ConflictResolved",
            payload={"decision_ref": decision_ref}, event_producer="CF-4", actor_type="human",
            actor_id=actor_id,
            writes="decision_ref = ?, decision_ref_kind = ?, decision_human_id = ?",
            write_args=(decision_ref, decision_ref_kind, human), correlation_id=correlation_id,
            causation_id=causation_id, trace_id=trace_id, event_id=event_id)

    # --- CF-7: the new party attaches -------------------------------------------------------------

    def attach_party(
        self,
        conflict_id: str,
        party: Party,
        *,
        expected: Conflict | None = None,
        actor_id: str = "reconciliation",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """CF-7 — ### A NEW DISAGREEING PARTY ATTACHES TO THE EXISTING OPEN CONFLICT, NEVER A SECOND ONE
        (entity §33, machine §17). The party carries its OWN provenance_class, CARRIED and NEVER
        STRENGTHENED (ER-14, R-P2). Redelivery of the same party is a no-op (GR-4). §14 names CF-7 from
        {RAISED, OPEN}; §17's dedup index spans the three OPEN states, so a party detected while the
        conflict is ESCALATED attaches to it too rather than orphaning — the index is the authority for
        'one open conflict per field', and a second detection may not create a second conflict."""
        party._validate()
        conflict = expected or self.require(conflict_id)
        if not conflict.is_open:
            raise GuardNotSatisfied(
                f"CF-7 attaches a party to an OPEN conflict; {conflict_id!r} is "
                f"{conflict.state.value} (terminal). New conflicting evidence after a resolution "
                f"raises a NEW conflict (CF-1, machine §24), it does not re-open this one.")
        # ### IDEMPOTENT UNDER REDELIVERY — a second detection of the SAME party attaches nothing new
        # and raises nothing new (entity §33, GR-4). Read-then-act is backstopped by the dedup unique
        # index inside the transaction.
        if party.party_ref in self.party_refs(conflict_id):
            return TransitionResult(
                transition_id="CF-7", conflict=conflict, from_state=conflict.state,
                to_state=conflict.state, attached_party_ref=party.party_ref)
        now = format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            seq = int(conn.execute(
                "SELECT COALESCE(MAX(attach_seq), 0) + 1 FROM conflict_parties "
                "WHERE tenant = ? AND conflict_id = ?", (self._tenant, conflict_id)).fetchone()[0])
            try:
                self._insert_party(conflict_id, party, seq, now)
            except sqlite3.IntegrityError:
                # The dedup unique index refused it — a concurrent redelivery already attached this
                # exact party. A no-op, not an error (GR-4).
                conn.rollback()
                return TransitionResult(
                    transition_id="CF-7", conflict=self.require(conflict_id),
                    from_state=conflict.state, to_state=conflict.state,
                    attached_party_ref=party.party_ref)
            # Advance the aggregate version (OCC) without changing state — the version-advances trigger
            # only fires on a state change, so a same-state party attach may advance version freely.
            cursor = conn.execute(
                "UPDATE conflicts SET version = version + 1, updated_at = ? "
                "WHERE tenant = ? AND conflict_id = ? AND version = ?",
                (now, self._tenant, conflict_id, conflict.version))
            if cursor.rowcount != 1:
                raise StateConflict(
                    f"CF-7 matched {cursor.rowcount} rows for {conflict_id!r}: it moved under us "
                    f"(GR-3). Reload and attach again.")
            after = self.require(conflict_id)
            resulting = self.party_refs(conflict_id)
            envelope = self._attach_envelope(
                after, party, sorted(resulting), actor_id=actor_id, correlation_id=correlation_id,
                causation_id=causation_id, trace_id=trace_id, event_id=event_id, now=now)
            self._outbox().emit(envelope)
            conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        return TransitionResult(
            transition_id="CF-7", conflict=after, from_state=conflict.state, to_state=conflict.state,
            event_ids=(envelope.event_id,), event_names=("ConflictPartyAttached",),
            event_producer="CF-7", attached_party_ref=party.party_ref)

    # --- replay & park/drain ----------------------------------------------------------------------

    def reference_resolver(self, aggregate_type: str, aggregate_id: str) -> bool:
        """M-26's question, tenant-scoped. A reference to a not-yet-existing conflict is PARKED and
        drained the moment it lands — the same mechanism M3/M5/M6 use, no second parking invented."""
        if aggregate_type == AGGREGATE_TYPE:
            return self._conn.execute(
                "SELECT 1 FROM conflicts WHERE tenant = ? AND conflict_id = ?",
                (self._tenant, aggregate_id)).fetchone() is not None
        return True

    def consume_event(
        self, envelope: EventEnvelope, *, inbox: DedupInbox | None = None,
        requires_existing: tuple[tuple[str, str], ...] = (), drain: bool = True,
    ) -> ConsumedTransition:
        """Consume one canonical `conflict` event idempotently through P5's dedup inbox.

        ### REPLAY RESOLVES NOTHING, DUPLICATES NOTHING, LOSES NO PARTY, MINTS NO AUTHORITY AND CAUSES
        NO EXTERNAL EFFECT (GR-11, K-3). Reconstruction advances an EXISTING durable row's state to
        match a state-marking event WITHOUT re-deciding it; a redelivery is a no-op (GR-4). It never
        independently resolves a conflict or changes which party stands."""
        box = inbox or DedupInbox(
            self._conn, tenant=self._tenant, consumer_id=CONSUMER_ID, clock=self._clock,
            reference_resolver=self.reference_resolver)
        outcome: dict[str, Any] = {"transition": None, "refusal": None}

        def handler(event: EventEnvelope) -> None:
            conflict = self.get(event.aggregate_id)
            if conflict is None:
                outcome["refusal"] = (
                    f"{event.event_name} references conflict {event.aggregate_id!r}, which does not "
                    f"exist for tenant {self._tenant!r}. Consumed once, nothing persisted.")
                return
            target = _event_target_state(event)
            if target is None or conflict.state is target or conflict.is_terminal:
                return
            outcome["transition"] = self._reconstruct_locked(conflict, target)

        default_reqs: tuple[tuple[str, str], ...] = ((AGGREGATE_TYPE, envelope.aggregate_id),)
        result = box.consume(
            envelope, handler,
            requires_existing=(requires_existing or default_reqs),
            drain_handler_for=((lambda _env: handler) if drain else None))
        return ConsumedTransition(
            consume=result, transition=outcome["transition"], refusal=outcome["refusal"])

    def rebuild(self, conflict_id: str, *,
                events: list[EventEnvelope] | None = None) -> ReconstructedConflict:
        """### A FULL-HISTORY FOLD OF ONE CONFLICT — SANDBOXED, ZERO AUTHORITY (GR-11, ER-2).

        It reconstructs state and the parties set from the event stream and creates NOTHING: no
        resolution, no duplicate conflict, no lost party, no new authority, the outside world
        untouched. The parties set is the UNION of ConflictRaised's set with every subsequent attach,
        so it is order-independent, and the field stays frozen iff the reconstructed state is open."""
        stream = events if events is not None else self._event_stream(conflict_id)
        state: ConflictState | None = None
        parties: set[str] = set()
        for event in stream:
            target = _event_target_state(event)
            if target is not None:
                state = target
            elif event.event_name == "ConflictRaised" and state is None:
                state = ConflictState.RAISED
            if event.event_name == "ConflictRaised":
                for party in event.payload.get("parties", []) or []:
                    ref = party.get("party_ref") if isinstance(party, Mapping) else None
                    if ref:
                        parties.add(str(ref))
            elif event.event_name == "ConflictPartyAttached":
                ref = event.payload.get("party_ref")
                if ref:
                    parties.add(str(ref))
                for member in event.payload.get("parties", []) or []:
                    if isinstance(member, str):
                        parties.add(member)
                    elif isinstance(member, Mapping) and member.get("party_ref"):
                        parties.add(str(member["party_ref"]))
        frozen = state in OPEN_STATES if state is not None else False
        return ReconstructedConflict(
            conflict_id=conflict_id, state=state, parties=tuple(sorted(parties)), frozen=frozen,
            resolutions=0, duplicate_conflicts=0, lost_parties=0, new_authority=0,
            external_effects=0)

    # --- shared transition plumbing ---------------------------------------------------------------

    def _advance(
        self, conflict: Conflict, transition_id: str, to_state: ConflictState, *,
        event_name: str, payload: Mapping[str, Any], event_producer: str, actor_type: str,
        actor_id: str, writes: str, write_args: tuple[Any, ...], correlation_id: str | None,
        causation_id: str | None, trace_id: str | None, event_id: str | None,
        now: str | None = None, after_write: Callable[[str], None] | None = None,
    ) -> TransitionResult:
        """One state transition: the state row and its event, or neither (GR-2). OCC on the version the
        decision was read at (GR-3): zero rows is a lost update that raises, never a silent overwrite."""
        now = now or format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            set_clause = "state = ?, version = version + 1, updated_at = ?"
            if writes:
                set_clause += ", " + writes
            args: list[Any] = [to_state.value, now, *write_args,
                               self._tenant, conflict.conflict_id, conflict.state.value,
                               conflict.version]
            cursor = conn.execute(
                f"UPDATE conflicts SET {set_clause} "
                f"WHERE tenant = ? AND conflict_id = ? AND state = ? AND version = ?", args)
            if cursor.rowcount != 1:
                raise StateConflict(
                    f"{transition_id} matched {cursor.rowcount} rows for "
                    f"{conflict.conflict_id!r}: it moved under us (GR-3). Reload — a lost update on a "
                    f"conflict is refused, never a write that silently wins.")
            if after_write is not None:
                after_write(now)
            after = self.require(conflict.conflict_id)
            envelope = self._envelope(
                event_name=event_name, event_producer=event_producer, conflict=after,
                aggregate_version=self._next_version(conflict.conflict_id), actor_type=actor_type,
                actor_id=actor_id, payload=dict(payload), correlation_id=correlation_id,
                causation_id=causation_id, trace_id=trace_id, event_id=event_id, now=now)
            self._outbox().emit(envelope)
            conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        return TransitionResult(
            transition_id=transition_id, conflict=after, from_state=conflict.state,
            to_state=to_state, event_ids=(envelope.event_id,), event_names=(event_name,),
            event_producer=event_producer)

    def _reconstruct_locked(self, conflict: Conflict, target: ConflictState) -> TransitionResult:
        """Advance a durable row to match a durable event — reconstruction, not a live transition.

        Runs inside the inbox's own commit (M-24): no BEGIN, no COMMIT. ### IT MINTS NO AUTHORITY: it
        moves only the `state` (and escalation_at) to what the event already recorded and never
        re-derives a resolution or a winner."""
        conn = self._conn
        now = format_instant(self._clock())
        writes = ["state = ?", "version = version + 1", "updated_at = ?"]
        args: list[Any] = [target.value, now]
        if target is ConflictState.ESCALATED and conflict.escalation_at is None:
            writes.append("escalation_at = ?")
            args.append(now)
        conn.execute(
            f"UPDATE conflicts SET {', '.join(writes)} "
            f"WHERE tenant = ? AND conflict_id = ? AND state = ?",
            (*args, self._tenant, conflict.conflict_id, conflict.state.value))
        after = self.require(conflict.conflict_id)
        return TransitionResult(
            transition_id="replay", conflict=after, from_state=conflict.state, to_state=target)

    def _insert_party(self, conflict_id: str, party: Party, seq: int, now: str) -> None:
        claim_ref = party.party_ref if party.party_kind == "identity_binding_claim" else None
        observation_ref = party.party_ref if party.party_kind == "observation" else None
        self._conn.execute(
            """
            INSERT INTO conflict_parties (
                tenant, party_id, conflict_id, party_ref, party_kind, claim_ref, observation_ref,
                provenance_class, stated_value, attach_seq, attached_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (self._tenant, f"cp-{uuid.uuid4().hex[:16]}", conflict_id, party.party_ref,
             party.party_kind, claim_ref, observation_ref, party.provenance_class,
             party.stated_value, seq, now),
        )

    def _arm_escalation(self, conflict_id: str, escalation_at: datetime | str) -> None:
        """Arm the durable-timer escalation deadline IN THE CALLER'S OPEN TRANSACTION (CF-5 rides the
        existing P5 substrate; no second timer mechanism, no sweep)."""
        DurableTimers(self._conn, tenant=self._tenant, clock=self._clock).schedule(
            timer_id=f"conf-esc-{conflict_id}", aggregate_type=AGGREGATE_TYPE,
            aggregate_id=conflict_id, timer_kind=TIMER_KIND_AGE_THRESHOLD, fire_at=escalation_at,
            correlation_id=conflict_id)

    # --- the named-human guard --------------------------------------------------------------------

    def _require_named_human(self, human_id: str | None, role: str, *, actor_kind: str) -> str:
        """### A NAMED ACTIVE HUMAN, FK-BACKED (entity §10/§16/§35, machine §5). "A human" is
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
                f"{role} is a named human, FK-backed into tenant_humans (entity §16/§37): an ownerless "
                f"or unnamed value is a silent drop wearing a status.")
        row = self._conn.execute(
            "SELECT state FROM tenant_humans WHERE tenant = ? AND human_id = ?",
            (self._tenant, text)).fetchone()
        if row is None or row["state"] != "ACTIVE":
            raise GuardNotSatisfied(
                f"{role} names {text!r}, who is not an ACTIVE recorded human of {self._tenant!r}. A "
                f"forged, inactive or wrong-tenant human fails closed — the owner is FK-backed, not a "
                f"free-text string, and `system` is not a human.")
        return text

    # --- F14 recording ----------------------------------------------------------------------------

    def _refuse_illegal(self, conflict_id: str, trigger: Trigger, *, actor_id: str) -> None:
        """### GR-1 — record `IllegalTransitionAttempted` to audit AND security, then the caller
        raises. The five illegal shapes machine §15 names by hand all pass through here."""
        conflict = self.get(conflict_id)
        state = conflict.state.value if conflict is not None else "-"
        self._record_f14(
            aggregate_id=conflict_id, event_name="IllegalTransitionAttempted",
            identity_suffix=f"{trigger.value}|{actor_id}",
            payload={"machine": "M7", "state": state, "trigger": trigger.value,
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

    def _event_stream(self, conflict_id: str) -> list[EventEnvelope]:
        rows = self._conn.execute(
            "SELECT envelope_json FROM event_outbox WHERE tenant = ? AND aggregate_type = ? "
            "AND aggregate_id = ? ORDER BY aggregate_version, sequence",
            (self._tenant, AGGREGATE_TYPE, conflict_id)).fetchall()
        return [EventEnvelope.from_json(r["envelope_json"]) for r in rows]

    def _next_version(self, conflict_id: str) -> int:
        return self._outbox().last_emitted_version(AGGREGATE_TYPE, conflict_id) + 1

    def _outbox(self):
        from .event_outbox import TransactionalOutbox
        return TransactionalOutbox(self._conn, tenant=self._tenant, clock=self._clock)

    def _raise_envelope(
        self, conflict: Conflict, parties: Sequence[Party], owner: str, *, actor_kind: str,
        actor_id: str, correlation_id: str | None, causation_id: str | None, trace_id: str | None,
        event_id: str | None, now: str,
    ) -> EventEnvelope:
        """The `ConflictRaised` envelope on the `conflict` aggregate at version 1.

        ### THE PARTIES DESCRIBE THE CONFLICT; they do not ASSERT provenance. The inner key is
        `provenance` (not `provenance_class`) precisely so a system-actor raise recording an
        OWNER_ASSERTED party (an INFERRER_VS_OWNER conflict) is not read by the ER-10 owner-provenance
        detector as the EVENT asserting OWNER_ASSERTED — the event RECORDS that one party's binding is
        owner-asserted, it does not claim to BE one. This is the exact seam M6's IB-6 already uses."""
        actor_type = "human" if str(actor_kind).upper() == HUMAN else str(actor_kind).lower()
        payload = {
            "kind": conflict.kind, "entity_ref": conflict.entity_ref, "field": conflict.field,
            "owner_id": owner,
            "parties": [
                {"party_ref": p.party_ref, "party_kind": p.party_kind,
                 "provenance": p.provenance_class, "stated_value": p.stated_value}
                for p in parties
            ],
        }
        return EventEnvelope(
            event_id=event_id or str(uuid.uuid4()), event_name="ConflictRaised",
            event_version=CONTRACTS["ConflictRaised"].current_version, occurred_at=now,
            recorded_at=now, tenant_id=self._tenant, aggregate_type=AGGREGATE_TYPE,
            aggregate_id=conflict.conflict_id, aggregate_version=1, previous_aggregate_version=None,
            causation_id=causation_id, correlation_id=correlation_id or conflict.conflict_id,
            producer_component=self._component, producer_transition_id="CF-1",
            actor_type=actor_type, actor_id=actor_id,
            trace_id=trace_id or f"trace-{conflict.conflict_id}", payload=payload,
            accountable_owner_id=owner)

    def _attach_envelope(
        self, conflict: Conflict, party: Party, resulting: Sequence[str], *, actor_id: str,
        correlation_id: str | None, causation_id: str | None, trace_id: str | None,
        event_id: str | None, now: str,
    ) -> EventEnvelope:
        """The `ConflictPartyAttached` envelope. Its top-level `provenance_class` is the ATTACHING
        party's own, carried verbatim; `parties[]` is the resulting reference set for the rebuild."""
        payload = {
            "party_ref": party.party_ref, "provenance_class": party.provenance_class,
            "parties": list(resulting), "entity_ref": conflict.entity_ref, "field": conflict.field,
        }
        return EventEnvelope(
            event_id=event_id or str(uuid.uuid4()), event_name="ConflictPartyAttached",
            event_version=CONTRACTS["ConflictPartyAttached"].current_version, occurred_at=now,
            recorded_at=now, tenant_id=self._tenant, aggregate_type=AGGREGATE_TYPE,
            aggregate_id=conflict.conflict_id, aggregate_version=self._next_version(
                conflict.conflict_id),
            previous_aggregate_version=None, causation_id=causation_id,
            correlation_id=correlation_id or conflict.conflict_id,
            producer_component=self._component, producer_transition_id="CF-7", actor_type="system",
            actor_id=actor_id, trace_id=trace_id or f"trace-{conflict.conflict_id}", payload=payload,
            accountable_owner_id=conflict.owner_id)

    def _envelope(
        self, *, event_name: str, event_producer: str, conflict: Conflict, aggregate_version: int,
        actor_type: str, actor_id: str, payload: Mapping[str, Any], correlation_id: str | None,
        causation_id: str | None, trace_id: str | None, event_id: str | None, now: str,
    ) -> EventEnvelope:
        """One canonical envelope on the `conflict` aggregate for CF-2/CF-5 and the CF-3/CF-4
        resolution. F7 is order-tolerant, so no `previous_aggregate_version` travels on it. The
        producer transition is the one the emitted contract registers — CF-3/CF-4 for a resolution,
        even when the machine row is CF-6, which is 'resolved by target state, never positionally'."""
        return EventEnvelope(
            event_id=event_id or str(uuid.uuid4()), event_name=event_name,
            event_version=CONTRACTS[event_name].current_version, occurred_at=now, recorded_at=now,
            tenant_id=self._tenant, aggregate_type=AGGREGATE_TYPE,
            aggregate_id=conflict.conflict_id, aggregate_version=aggregate_version,
            previous_aggregate_version=None, causation_id=causation_id,
            correlation_id=correlation_id or conflict.conflict_id,
            producer_component=self._component, producer_transition_id=event_producer,
            actor_type=actor_type, actor_id=actor_id,
            trace_id=trace_id or f"trace-{conflict.conflict_id}", payload=dict(payload),
            accountable_owner_id=conflict.owner_id)


# ------------------------------------------------------------------------------------- plumbing

def _kind_value(kind: str | ConflictKind) -> str:
    value = kind.value if isinstance(kind, ConflictKind) else str(kind)
    if value not in CONFLICT_KINDS:
        raise MalformedConflict(
            f"kind {value!r} is not one of the six canonical kinds {list(CONFLICT_KINDS)} (entity "
            f"§12, ADR-007 §5.1). There is no seventh, and the ConflictRaised contract refuses one.")
    return value


def _event_target_state(event: EventEnvelope) -> ConflictState | None:
    """The state a conflict event reconstructs to, or None for an event that is not a state marker on
    this aggregate (ConflictRaised's own marker is handled by the rebuild; an attach or an F14 event
    riding the aggregate does not move the state)."""
    name = event.event_name
    if name == "ConflictOpened":
        return ConflictState.OPEN
    if name == "ConflictEscalated":
        return ConflictState.ESCALATED
    if name == "ConflictResolved":
        # CF-3 (rule) and CF-4 (human) share this contract; the target is read from the producer
        # transition the event names, never guessed positionally.
        return (ConflictState.RESOLVED_BY_RULE if event.producer_transition_id == "CF-3"
                else ConflictState.RESOLVED_BY_HUMAN)
    # ConflictRaised (creation marker), ConflictPartyAttached, IllegalTransitionAttempted, etc.
    return None


def _require_text(value: str, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise MalformedConflict(f"{field_name} is required and was empty.")
    return text


def _row_to_conflict(row: Any) -> Conflict:
    return Conflict(
        tenant=row["tenant"], conflict_id=row["conflict_id"], entity_ref=row["entity_ref"],
        field=row["field"], kind=row["kind"], state=ConflictState(row["state"]),
        version=row["version"], owner_id=row["owner_id"], rule_id=row["rule_id"],
        decision_ref=row["decision_ref"], decision_ref_kind=row["decision_ref_kind"],
        decision_human_id=row["decision_human_id"], escalation_at=row["escalation_at"],
        exposure=row["exposure"])


# Re-exported so a caller reads one name rather than importing the migration for a constant.
STATES: tuple[str, ...] = CONFLICT_STATES
KINDS: tuple[str, ...] = CONFLICT_KINDS
