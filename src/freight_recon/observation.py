"""Machine M5 — the Observation: one `observations` row that records a source *said* something, at
a time, and can never quietly rewrite, duplicate, guess at, obey, or age out that it did.

    ### AN OBSERVATION IS AN IMMUTABLE RECORD THAT A SOURCE *SAID* SOMETHING, AT A TIME. IT IS NOT A
    ### CLAIM THAT THE THING IS TRUE. THE TMS CAN BE WRONG; THAT IT SAID SO IS STILL A FACT.

    ### IMMUTABLE OBSERVATION *CONTENT* IS SEPARATE FROM OBSERVATION-PROCESSING *STATUS*. The `state`
    ### machine governs PROCESSING STATUS ONLY. `raw_value` and `content_digest` are written once and
    ### never mutate (05-observation.machine.md opening line; entity §16/§22).

### WHAT THIS MACHINE OWNS, AND WHAT IT ONLY BORROWS.

It owns the seven states and the OB-1…OB-5 transitions of `05-observation.machine.md` §14, and it is
the canonical PRODUCER of the seven already-registered F5 `Observation*` events on the `observation`
aggregate. It does NOT compute bindings (that is M6, which is NOT built — see the M6 seam below), does
NOT mint an `ExceptionRaised` (that is M9's contract, P6/U5.3 — see the Exception seam below), and
does NOT emit `ProvenanceStrengtheningAttempted` (that F14 emission half lands in Implementation
Phase 7 per CURRENT.md — see the provenance seam below). It rides P5's transactional outbox and dedup
inbox exactly as M3 and M4 do.

### F5 IS ORDER-TOLERANT, AND THAT IS A REQUIREMENT, NOT A RELAXATION (events/registry.md §8).
`observation` is NOT in `STRICT_ORDER_AGGREGATE_TYPES`. So — unlike M3 and M4 — this machine declares
NO `previous_aggregate_version` on its events: the natural key is what makes ingestion commutative,
and an order-tolerant producer that declared a predecessor would be inventing a guarantee canon did
not ask for. Out-of-order delivery is tolerated; a reference to a not-yet-received observation is
PARKED (M-26) and drained when it arrives.

### THE §3.9 AUTHORITY QUESTIONS — REPORTED, NOT RESOLVED. The corpus disagrees with itself on three
points about M5, and this machine implements only what EVERY reading agrees on, reporting the rest:

  * `M5-AQ-1` — is `BOUND` terminal? Registry §4 / entity §12 / machine §8 / target spec §12.5 all
    mark `BOUND (T)`; yet the SAME documents carry `OB-5: {BOUND,PARSED} → SUPERSEDED`, giving BOUND an
    outgoing edge. Every reading agrees: supersession requires a deterministic rule or a human, never
    an inferrer re-run; the superseded row is RETAINED; `raw_value`/`content_digest` never mutate.
    ### THIS CODE IMPLEMENTS OB-5 EXACTLY AS WRITTEN (BOUND and PARSED may be superseded) and does not
    "fix" the classification in either direction. So the only states with no outgoing edge — the ones
    this machine and its migration make ABSOLUTELY final — are `SUPERSEDED` and `UNPARSEABLE`.

  * `M5-AQ-2` — is `UNPARSEABLE` terminal or non-terminal human-owned? Entity §12 / machine §8 / target
    spec §12.5 say terminal; registry §4 (`UNPARSEABLE (NH)`) and machine §9 say non-terminal
    human-owned — machine §8 and §9 contradict each other in one file. Every reading agrees:
    `UNPARSEABLE` is never a silent drop, feeds the Exception path, and is HUMAN-OWNED. ### THIS CODE
    BUILDS THAT: `UNPARSEABLE` names an accountable human (the FK-backed `owner_id`), has no outgoing
    transition, and nothing sweeps or drops it.

  * `M5-AQ-3` — what does a duplicate do to a row that has already advanced? `OB-1c`'s From→To says
    `(re-ingest) → CONFIRMED`, but its Writes column says `as_of updated only`, F5 calls the event *"a
    FRESHNESS update, NOT a new business fact"*, and machine §16 says `CONFIRMED` short-circuits before
    any parse/bind re-work. Every reading agrees: one row, one `ObservationConfirmed`, zero downstream
    work, `raw_value`/`content_digest` unchanged, and the immutable CONTENT untouched. ### THIS CODE
    IMPLEMENTS THE `as_of`-ONLY READING: a re-ingest updates `as_of` (never backwards) and emits
    `ObservationConfirmed`, and NEVER rewrites `state` — because the required-observable sentence "A
    CONFIRMATION UPDATES as_of AND NOTHING ELSE" is decisive, and discarding a processing status the
    machine already established (a BOUND row reverting to CONFIRMED) is the loss §3.1 warns against. So
    `CONFIRMED` stays in the seven-state vocabulary (the CHECK admits it) but the `state` column is
    never moved into it; the confirmation is carried by the EVENT, not by a state rewrite.

### THE M6 BINDING SEAM IS INERT (task §3.7). `OB-3` binds *"via M6"*, and M5 CONSUMES M6's
`BindingConfirmed`/`BindingAmbiguous`/`BindingAbsent`. M6 does not exist and is not built here. So
`bind`/`resolve_unbound` accept a `BindingDecision` — a typed INPUT — apply their own deterministic
guard, and transition. They compute nothing, rank no candidates, build no `identity_binding_claims`
table, and implement no `IB-*`. `binding_claim_id` is entity §11 OPTIONAL; it is carried as the M6
claim reference a decision hands in, with NO foreign key into a table this unit does not own.

### THE EXCEPTION SEAM DOES NOT MINT M9's CONTRACT (task §3.8). `OB-2f` and `OB-3u` end "→ Exception".
M9 is not built and `ExceptionRaised` is M9's contract. Like `event_inbox.expire_overdue`, this
machine emits its OWN canonical events (`ObservationUnparseable`, `ObservationUnbound`, whose F5
consumer is M9) and leaves a DURABLE, HUMAN-OWNED record — the row sits in `UNPARSEABLE`/`UNBOUND`,
names an accountable human, and nothing silently drops or closes it. It mints no `ExceptionRaised`,
builds no `exceptions` table, and implements no `EC-*`.

### THE PROVENANCE SEAM REFUSES THE LAUNDERING BUT DOES NOT MINT THE F14 EVENT (task §3.10). Inbound
content that carries, implies or asks for a `provenance_class` is REFUSED — provenance is
runtime-assigned (M-13, R-P1), and this refusal is mandatory and not deferred anywhere. The F14
`ProvenanceStrengtheningAttempted` EMISSION half is scoped to Implementation Phase 7 by CURRENT.md and
P5's `IR-R9`, so it is NOT minted here.

### IT SHIPS DARK. Nothing under `src/freight_recon/` imports this module; the only script that may is
`scripts/probe_phase6_observation.py`. It joins no importer, mailbox or live channel, authorizes no
effect, and mints no gate decision — an Observation may *evidence* a claim and can never *make* one
(entity §35).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .event_contracts import CONTRACTS
from .event_envelope import EventEnvelope, format_instant
from .event_inbox import ConsumeResult, DedupInbox
from .migrations.phase6_observations import (
    ABSOLUTELY_TERMINAL_OBSERVATION_STATES,
    DETERMINISTIC_MATCH_METHODS,
    HUMAN_OWNED_OBSERVATION_STATES,
    OBSERVATION_FORBIDDEN_PROVENANCE,
    OBSERVATION_PROVENANCE_ALLOWED,
    OBSERVATION_STATES,
)
from .tenant import require_tenant

# The aggregate this machine owns. `observation` is NOT in `STRICT_ORDER_AGGREGATE_TYPES` (F5 is
# ORDER-TOLERANT, events/registry.md §8): the natural key makes ingestion commutative, so no F5 event
# declares a strict-order predecessor and the inbox falls back to contiguity for it.
AGGREGATE_TYPE = "observation"

# entity §5: the Ingestion Service records what a source said.
PRODUCER_COMPONENT = "ingestion_service"

# The one consumer identity M5 presents to the dedup inbox. Fixed, because the dedup key is
# `(tenant, consumer_id, event_id)` and a renamed consumer would re-arm every duplicate.
CONSUMER_ID = "m5-observation"

# GR-1's producer id for `IllegalTransitionAttempted` — the RULE, not a transition (§3 "‡(any
# machine, GR-1)"). Identical to M1/M2/M3/M4's, for the same reason.
ILLEGAL_TRANSITION_PRODUCER = "GR-1"

# A refusal advances no version; every refusal against one observation at one version would otherwise
# collide on one `idempotency_identity` — the poison-loop defect M1 shipped. Applied here.
ILLEGAL_ATTEMPT_IDENTITY_PREFIX = "ita_v1"

HUMAN = "HUMAN"

# The provenance an Observation carries when no runtime source is stated. SYSTEM_IMPORTED is a system
# of record (entity §17); a counterparty-authored value is MODEL_EXTRACTED at best (entity §35).
DEFAULT_PROVENANCE = "SYSTEM_IMPORTED"

# The full six-member canonical provenance vocabulary (C-7): the five an Observation MAY carry plus
# the one it may NEVER. Used only to distinguish "unknown provenance class" from "known but
# forbidden", so the MODEL_INFERRED refusal is a SINGLE guard — the `!= OBSERVATION_FORBIDDEN_PROVENANCE` clause — and
# not a rule split across two overlapping checks a mutation would have to flip together.
_KNOWN_PROVENANCE: frozenset[str] = frozenset(
    (*OBSERVATION_PROVENANCE_ALLOWED, OBSERVATION_FORBIDDEN_PROVENANCE))


class ObservationError(RuntimeError):
    """This machine will not do what was asked. Never degraded into a partial transition."""


class UnknownObservation(ObservationError):
    """No `observations` row with this id exists FOR THIS TENANT. Indistinguishable from "belongs to
    another tenant" on purpose — [C-1] rejects a cross-tenant question rather than answering it."""


class GuardNotSatisfied(ObservationError):
    """The (state, trigger) pair IS legal here and a precondition is false. No event is emitted."""


class IllegalTransition(ObservationError):
    """GR-1 / [C-4]. The (state, trigger) pair is not enumerated (or §15 forbids the shape). Raised
    AFTER `IllegalTransitionAttempted` is recorded, which is the point of recording it."""


class StateConflict(ObservationError):
    """A state-guarded UPDATE matched zero rows: the observation moved under us (GR-3). Reload."""


class ContentIsData(ObservationError):
    """### INBOUND CONTENT IS DATA, NEVER INSTRUCTION, NEVER AUTHORITY (M-66). Raised when a caller
    tries to let inbound content choose its own provenance — provenance is runtime-assigned (M-13,
    R-P1), never carried in content, never settable through an API untrusted data can reach."""


# --------------------------------------------------------------------------------- the state set

class ObservationState(str, Enum):
    RECEIVED = "RECEIVED"
    PARSED = "PARSED"
    BOUND = "BOUND"
    UNBOUND = "UNBOUND"
    CONFIRMED = "CONFIRMED"
    SUPERSEDED = "SUPERSEDED"
    UNPARSEABLE = "UNPARSEABLE"


class Trigger(str, Enum):
    """The closed set of driving facts, named from §14's triggers and §33's "Events consumed"."""

    OBSERVATION_INGESTED = "ObservationIngested"        # OB-1 / OB-1c (X)
    PARSED = "Parsed"                                   # OB-2 (S)
    PARSE_FAILED = "ParseFailed"                        # OB-2f (S)
    BINDING_CONFIRMED = "BindingConfirmed"              # OB-3 / OB-4 (S | H)
    BINDING_AMBIGUOUS = "BindingAmbiguous"              # OB-3u (S)
    BINDING_ABSENT = "BindingAbsent"                    # OB-3u (S)
    NEWER_OBSERVATION_SUPERSEDES = "NewerObservationSupersedes"   # OB-5 (S | H)


class BindingKind(str, Enum):
    """What a binding decision (from M6, the inert seam) says. Only CONFIRMED-with-a-deterministic-
    method binds; everything else — ambiguous, absent, a single weak candidate, or a model guess —
    fails closed to UNBOUND (machine OB-3u, GR-8). Confidence is NEVER a guard input."""

    CONFIRMED = "CONFIRMED"
    AMBIGUOUS = "AMBIGUOUS"
    ABSENT = "ABSENT"
    WEAK = "WEAK"


# --------------------------------------------------------------------------- the transition table

@dataclass(frozen=True)
class TransitionRow:
    """One row of §14. Data, so the acceptance battery can enumerate it against the specification."""

    id: str
    from_states: tuple[ObservationState, ...]
    to_state: ObservationState
    triggers: tuple[Trigger, ...]
    trigger_types: tuple[str, ...]     # X|S|H — the registry §1 codes
    event: str
    human_owned_result: bool = False   # OB-3u: the result state names an accountable human


TRANSITIONS: tuple[TransitionRow, ...] = (
    TransitionRow(
        id="OB-1", from_states=(), to_state=ObservationState.RECEIVED,
        triggers=(Trigger.OBSERVATION_INGESTED,), trigger_types=("X",),
        event="ObservationReceived"),
    TransitionRow(
        # OB-1c writes as_of only and emits ObservationConfirmed; it does NOT move the `state` column
        # (§3.9 M5-AQ-3, reported). Modelled here with from==to==CONFIRMED so the table enumerates the
        # canonical state, while `confirm()` implements the as_of-only reading.
        id="OB-1c", from_states=(ObservationState.RECEIVED,), to_state=ObservationState.CONFIRMED,
        triggers=(Trigger.OBSERVATION_INGESTED,), trigger_types=("X",),
        event="ObservationConfirmed"),
    TransitionRow(
        id="OB-2", from_states=(ObservationState.RECEIVED,), to_state=ObservationState.PARSED,
        triggers=(Trigger.PARSED,), trigger_types=("S",), event="ObservationParsed"),
    TransitionRow(
        id="OB-2f", from_states=(ObservationState.RECEIVED,), to_state=ObservationState.UNPARSEABLE,
        triggers=(Trigger.PARSE_FAILED,), trigger_types=("S",), event="ObservationUnparseable",
        human_owned_result=True),
    TransitionRow(
        id="OB-3", from_states=(ObservationState.PARSED,), to_state=ObservationState.BOUND,
        triggers=(Trigger.BINDING_CONFIRMED,), trigger_types=("S",), event="ObservationBound"),
    TransitionRow(
        id="OB-3u", from_states=(ObservationState.PARSED,), to_state=ObservationState.UNBOUND,
        triggers=(Trigger.BINDING_AMBIGUOUS, Trigger.BINDING_ABSENT), trigger_types=("S",),
        event="ObservationUnbound", human_owned_result=True),
    TransitionRow(
        id="OB-4", from_states=(ObservationState.UNBOUND,), to_state=ObservationState.BOUND,
        triggers=(Trigger.BINDING_CONFIRMED,), trigger_types=("H", "S"), event="ObservationBound"),
    TransitionRow(
        id="OB-5", from_states=(ObservationState.BOUND, ObservationState.PARSED),
        to_state=ObservationState.SUPERSEDED, triggers=(Trigger.NEWER_OBSERVATION_SUPERSEDES,),
        trigger_types=("S", "H"), event="ObservationSuperseded"),
)

TRANSITIONS_BY_ID: Mapping[str, TransitionRow] = {row.id: row for row in TRANSITIONS}

PRODUCED_CONTRACTS: frozenset[str] = frozenset(row.event for row in TRANSITIONS)

TERMINAL_STATES: frozenset[ObservationState] = frozenset(
    ObservationState(s) for s in ABSOLUTELY_TERMINAL_OBSERVATION_STATES)
HUMAN_OWNED_STATES: frozenset[ObservationState] = frozenset(
    ObservationState(s) for s in HUMAN_OWNED_OBSERVATION_STATES)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------------------------ the inputs

@dataclass(frozen=True)
class BindingDecision:
    """A binding decision handed to M5 by the (inert) M6 seam. M5 does not compute it — it applies its
    own deterministic guard and transitions. `kind=CONFIRMED` with a deterministic `match_method` and
    a non-`MODEL_INFERRED` `provenance_class` binds; anything else fails closed to UNBOUND."""

    kind: BindingKind
    bound_entity_ref: str | None = None
    binding_claim_id: str | None = None
    match_method: str | None = None          # EXACT_ID / RULE / RECONCILE / HUMAN when CONFIRMED
    provenance_class: str = DEFAULT_PROVENANCE
    candidate_count: int = 0

    @property
    def is_deterministic(self) -> bool:
        """### A GUESS NEVER AUTO-BINDS, AT ANY CONFIDENCE (GR-8). Deterministic means: a confirmed
        decision, an enumerated deterministic match method, a non-MODEL_INFERRED provenance, and an
        entity plus a claim reference to point at. Confidence is not read at all."""
        return (
            self.kind is BindingKind.CONFIRMED
            and self.match_method in DETERMINISTIC_MATCH_METHODS
            and self.provenance_class != OBSERVATION_FORBIDDEN_PROVENANCE
            and self.provenance_class in _KNOWN_PROVENANCE
            and bool(str(self.bound_entity_ref or "").strip())
            and bool(str(self.binding_claim_id or "").strip())
        )


# ------------------------------------------------------------------------------------ the row

@dataclass(frozen=True)
class Observation:
    """One `observations` row, as the machine reads it."""

    tenant: str
    observation_id: str
    source_system: str
    external_id: str
    content_digest: str
    raw_value: str
    as_of: str
    received_at: str
    state: ObservationState
    version: int
    provenance_class: str
    parsed_value: str | None
    bound_entity_ref: str | None
    binding_claim_id: str | None
    match_method: str | None
    owner_id: str | None
    unparse_reason: str | None
    supersedes: str | None
    superseded_by: str | None

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    @property
    def natural_key(self) -> dict[str, str]:
        return {"source_system": self.source_system, "external_id": self.external_id,
                "content_digest": self.content_digest}


@dataclass(frozen=True)
class IngestOutcome:
    """What one ingest did. `created` is a NEW fact (OB-1); `confirmed` is an identical re-ingest
    (OB-1c) — one row, one confirmation, zero downstream work. Never both, never neither."""

    observation_id: str
    created: bool
    confirmed: bool
    state: ObservationState
    content_digest: str
    event_id: str


@dataclass(frozen=True)
class TransitionResult:
    transition_id: str
    observation: Observation
    from_state: ObservationState
    to_state: ObservationState
    event_ids: tuple[str, ...] = ()
    event_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReconstructedObservation:
    """A full-history fold of one observation's event stream — sandboxed, zero authority (GR-11, K-3).

    Every count is of what the REBUILD created, which is always zero: it creates no new observation,
    no duplicate row, no downstream work, and touches the outside world not at all.
    """

    observation_id: str
    state: ObservationState | None
    new_observations: int = 0
    duplicate_rows: int = 0
    downstream_work: int = 0
    external_effects: int = 0


@dataclass(frozen=True)
class ConsumedTransition:
    """What consuming one canonical trigger did — the DELIVERY (`consume`) kept apart from the MACHINE
    effect (`transition`), so "the event was delivered" is never read as "the observation moved"."""

    consume: ConsumeResult
    transition: TransitionResult | None = None
    refusal: str | None = None

    @property
    def moved(self) -> bool:
        return self.transition is not None


# --------------------------------------------------------------------------------- the machine

class ObservationMachine:
    """M5, on an existing connection, bound to ONE tenant. Bound at construction rather than per call,
    so a caller cannot re-point it at another tenant and put [C-1] in its own hands."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        tenant: str,
        clock: Callable[[], datetime] | None = None,
        producer_component: str = PRODUCER_COMPONENT,
    ) -> None:
        if getattr(conn, "row_factory", None) is not sqlite3.Row:
            raise ObservationError(
                "ObservationMachine reads columns by name and requires `row_factory = sqlite3.Row`."
            )
        self._conn = conn
        self._tenant = require_tenant(tenant, context="ObservationMachine")
        self._clock = clock or _utc_now
        self._component = producer_component

    @property
    def tenant(self) -> str:
        return self._tenant

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    # --- reads -----------------------------------------------------------------------------------

    def get(self, observation_id: str) -> Observation | None:
        row = self._conn.execute(
            "SELECT * FROM observations WHERE tenant = ? AND observation_id = ?",
            (self._tenant, observation_id),
        ).fetchone()
        return _row_to_observation(row) if row is not None else None

    def require(self, observation_id: str) -> Observation:
        found = self.get(observation_id)
        if found is None:
            raise UnknownObservation(
                f"no observation {observation_id!r} for tenant {self._tenant!r}. This machine does "
                f"not look outside its tenant to find out whether it exists elsewhere ([C-1])."
            )
        return found

    def by_natural_key(
        self, source_system: str, external_id: str, content_digest: str,
    ) -> Observation | None:
        row = self._conn.execute(
            "SELECT * FROM observations WHERE tenant = ? AND source_system = ? AND external_id = ? "
            "AND content_digest = ?",
            (self._tenant, source_system, external_id, content_digest),
        ).fetchone()
        return _row_to_observation(row) if row is not None else None

    @staticmethod
    def content_digest(raw_value: str | Mapping[str, Any]) -> str:
        """### THE DIGEST IS RUNTIME-COMPUTED FROM THE CONTENT, NEVER TAKEN FROM IT. A forged
        `content_digest` in the payload is ignored: identical content collides on the natural key and
        becomes a confirmation; one byte different is a new digest and a NEW observation (entity §19).
        """
        text = _canonical_text(raw_value)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    # --- OB-1 / OB-1c: ingest ---------------------------------------------------------------------

    def ingest(
        self,
        *,
        source_system: str,
        external_id: str,
        raw_value: str | Mapping[str, Any],
        as_of: str,
        observation_id: str | None = None,
        provenance_class: str = DEFAULT_PROVENANCE,
        received_at: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> IngestOutcome:
        """OB-1 / OB-1c — ### THE SAME EMAIL TWICE IS ONE OBSERVATION. An idempotent upsert on the
        natural key `(tenant, source_system, external_id, content_digest)`: new content creates a
        RECEIVED row (OB-1); identical content collides on the UNIQUE index and becomes a confirmation
        (OB-1c) — one row, one `ObservationConfirmed`, ZERO downstream work.

        ### INBOUND CONTENT IS DATA (M-66) and CANNOT CHOOSE ITS OWN PROVENANCE (M-13). `raw_value` is
        stored EXACTLY as observed and never interpreted as instruction; `provenance_class` is the
        runtime's, not the content's, and a MODEL_INFERRED observation is refused (entity §37).
        """
        source_system = _require_text(source_system, "source_system")
        external_id = _require_text(external_id, "external_id")
        as_of = _require_text(as_of, "as_of")
        text = _canonical_text(raw_value)
        if not text.strip():
            raise GuardNotSatisfied("raw_value is required and was empty: a fact has content.")
        self._reject_provenance_from_content(raw_value)
        self._require_runtime_provenance(provenance_class)
        digest = self.content_digest(raw_value)

        existing = self.by_natural_key(source_system, external_id, digest)
        if existing is not None:
            # OB-1c: identical content already present -> a confirmation, before any parse/bind rework.
            return self._confirm(existing, as_of, correlation_id, causation_id, trace_id)

        oid = observation_id or f"obs-{uuid.uuid4().hex[:16]}"
        now = format_instant(self._clock())
        recv = received_at or now
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            try:
                conn.execute(
                    """
                    INSERT INTO observations (
                        tenant, observation_id, source_system, external_id, content_digest,
                        raw_value, as_of, received_at, state, version, provenance_class,
                        parsed_value, bound_entity_ref, binding_claim_id, match_method, owner_id,
                        unparse_reason, supersedes, superseded_by, created_at, updated_at
                    ) VALUES (?,?,?,?,?,?,?,?, 'RECEIVED', 1, ?, NULL, NULL, NULL, NULL, NULL,
                              NULL, NULL, NULL, ?, ?)
                    """,
                    (self._tenant, oid, source_system, external_id, digest, text, as_of, recv,
                     provenance_class, now, now),
                )
            except sqlite3.IntegrityError:
                # ### THE UNIQUE INDEX IS THE SERIALIZATION POINT (machine §17). A concurrent writer
                # created the row between our read and our insert. Roll back and confirm: one ingestion
                # wins, the others confirm. If the collision was NOT the natural key, re-raise.
                conn.rollback()
                racer = self.by_natural_key(source_system, external_id, digest)
                if racer is None:
                    raise
                return self._confirm(racer, as_of, correlation_id, causation_id, trace_id)
            created = self.require(oid)
            envelope = self._envelope(
                event_name="ObservationReceived", transition_id="OB-1", observation=created,
                aggregate_version=self._next_version(oid), actor_type="system",
                actor_id=source_system, payload={"natural_key": created.natural_key, "as_of": as_of},
                correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                event_id=event_id, now=now)
            self._outbox().emit(envelope)
            conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        return IngestOutcome(observation_id=oid, created=True, confirmed=False,
                             state=ObservationState.RECEIVED, content_digest=digest,
                             event_id=envelope.event_id)

    def _confirm(
        self, existing: Observation, as_of: str, correlation_id: str | None,
        causation_id: str | None, trace_id: str | None,
    ) -> IngestOutcome:
        """OB-1c — ### A CONFIRMATION UPDATES as_of AND NOTHING ELSE (§3.9 M5-AQ-3, the as_of-only
        reading). `as_of` moves to the freshest sighting (never backwards — a stale re-delivery is
        still a fact but does not un-freshen). The `state` column is NOT touched, `raw_value` and
        `content_digest` are NOT touched, and ZERO downstream work is triggered. One row, one
        `ObservationConfirmed`."""
        now = format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                # MAX(as_of, ?) — freshness never regresses (entity §26: a stale observation is still
                # a fact). No version predicate: a confirmation is natural-key idempotent, not an OCC
                # transition, so concurrent confirmations each apply and none is a lost update.
                "UPDATE observations SET as_of = MAX(as_of, ?), version = version + 1, "
                "updated_at = ? WHERE tenant = ? AND observation_id = ?",
                (as_of, now, self._tenant, existing.observation_id))
            confirmed = self.require(existing.observation_id)
            envelope = self._envelope(
                event_name="ObservationConfirmed", transition_id="OB-1c", observation=confirmed,
                aggregate_version=self._next_version(existing.observation_id), actor_type="system",
                actor_id=existing.source_system,
                payload={"natural_key": existing.natural_key, "as_of": as_of},
                correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                event_id=None, now=now)
            self._outbox().emit(envelope)
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        # ### THE STATE IS RETURNED UNCHANGED — a confirmation never rewrites processing status.
        return IngestOutcome(observation_id=existing.observation_id, created=False, confirmed=True,
                             state=existing.state, content_digest=existing.content_digest,
                             event_id=envelope.event_id)

    # --- OB-2 / OB-2f: parse ----------------------------------------------------------------------

    def parse(
        self,
        observation_id: str,
        *,
        parsed_value: Any = None,
        ok: bool = True,
        owner_id: str | None = None,
        unparse_reason: str | None = None,
        expected: Observation | None = None,
        actor_id: str = "extractor",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """OB-2 (extraction succeeded → PARSED) or OB-2f (extraction failed → UNPARSEABLE).

        ### A PARSE FAILURE IS UNPARSEABLE, NEVER A SILENT DROP (entity §36). UNPARSEABLE feeds the
        Exception path and is HUMAN-OWNED: it names an accountable recorded human (`owner_id`), the
        way M1's `owner_id` does. This machine mints NO `ExceptionRaised` (that is M9's, §3.8)."""
        obs = expected or self.require(observation_id)
        if ok:
            value = _canonical_text(parsed_value if parsed_value is not None else "")
            if not value.strip():
                raise GuardNotSatisfied(
                    "OB-2 records the parsed value the extractor produced; it was empty. A parse that "
                    "produced nothing is a parse failure (OB-2f), not a PARSED observation.")
            return self._advance(
                obs, Trigger.PARSED, ObservationState.PARSED, event_name="ObservationParsed",
                payload={"parsed_value": value}, writes="parsed_value = ?", write_args=(value,),
                actor_type="system", actor_id=actor_id, correlation_id=correlation_id,
                causation_id=causation_id, trace_id=trace_id, event_id=event_id)
        owner = self._require_named_human(owner_id, ObservationState.UNPARSEABLE)
        reason = str(unparse_reason or "extraction failed").strip()
        return self._advance(
            obs, Trigger.PARSE_FAILED, ObservationState.UNPARSEABLE,
            event_name="ObservationUnparseable", payload={},
            writes="owner_id = ?, unparse_reason = ?", write_args=(owner, reason),
            actor_type="system", actor_id=actor_id, correlation_id=correlation_id,
            causation_id=causation_id, trace_id=trace_id, event_id=event_id)

    # --- OB-3 / OB-3u: bind -----------------------------------------------------------------------

    def bind(
        self,
        observation_id: str,
        decision: BindingDecision,
        *,
        owner_id: str | None = None,
        expected: Observation | None = None,
        actor_id: str = "identity-service",
        actor_kind: str = "system",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """OB-3 (deterministic binding confirmed → BOUND) or OB-3u (ambiguous / absent / single weak
        candidate → UNBOUND).

        ### AN AMBIGUOUS BINDING IS UNBOUND, NEVER A GUESS. A guess never auto-binds at any confidence
        (GR-8): only a CONFIRMED decision with a deterministic match method binds; everything else
        fails closed to UNBOUND (human-owned). M5 does NOT compute the binding — the decision is M6's
        (inert seam, §3.7); M5 applies its own deterministic guard."""
        obs = expected or self.require(observation_id)
        if decision.is_deterministic:
            return self._advance(
                obs, Trigger.BINDING_CONFIRMED, ObservationState.BOUND,
                event_name="ObservationBound",
                payload={"provenance_class": decision.provenance_class,
                         "bound_entity_ref": decision.bound_entity_ref,
                         "binding_claim_id": decision.binding_claim_id},
                writes="bound_entity_ref = ?, binding_claim_id = ?, match_method = ?, "
                       "provenance_class = ?",
                write_args=(decision.bound_entity_ref, decision.binding_claim_id,
                            decision.match_method, decision.provenance_class),
                actor_type=("human" if str(actor_kind).upper() == HUMAN else "system"),
                actor_id=actor_id, correlation_id=correlation_id, causation_id=causation_id,
                trace_id=trace_id, event_id=event_id)
        owner = self._require_named_human(owner_id, ObservationState.UNBOUND)
        return self._advance(
            obs, Trigger.BINDING_AMBIGUOUS, ObservationState.UNBOUND,
            event_name="ObservationUnbound", payload={}, writes="owner_id = ?", write_args=(owner,),
            actor_type="system", actor_id=actor_id, correlation_id=correlation_id,
            causation_id=causation_id, trace_id=trace_id, event_id=event_id)

    def resolve_unbound(
        self,
        observation_id: str,
        decision: BindingDecision,
        *,
        expected: Observation | None = None,
        actor_id: str = "identity-service",
        actor_kind: str = "system",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """OB-4 — ### A LATER DETERMINISTIC MATCH OR AN OWNER ASSERTION RESOLVES UNBOUND. An
        `OWNER_ASSERTED` binding is a HUMAN action (match_method=HUMAN); a later deterministic match is
        a system decision. Either way the decision must be deterministic — a guess still never binds
        (GR-8), and GR-9 forbids a machine recompute from overwriting an owner-asserted value."""
        obs = expected or self.require(observation_id)
        if obs.state is not ObservationState.UNBOUND:
            raise GuardNotSatisfied(
                f"OB-4 resolves an UNBOUND observation; {observation_id!r} is {obs.state.value}.")
        if not decision.is_deterministic:
            self._record_illegal(obs, Trigger.BINDING_CONFIRMED, actor_id=actor_id)
            raise IllegalTransition(
                "OB-4 resolves UNBOUND only on a later DETERMINISTIC match or an OWNER_ASSERTED "
                "binding — a guess never auto-binds at any confidence (GR-8).")
        if decision.provenance_class == "OWNER_ASSERTED" and str(actor_kind).upper() != HUMAN:
            self._record_illegal(obs, Trigger.BINDING_CONFIRMED, actor_id=actor_id)
            raise IllegalTransition(
                "an OWNER_ASSERTED binding is a human assertion (machine OB-4); a machine actor "
                "cannot assert it (GR-9 / ER-10).")
        return self._advance(
            obs, Trigger.BINDING_CONFIRMED, ObservationState.BOUND, event_name="ObservationBound",
            payload={"provenance_class": decision.provenance_class,
                     "bound_entity_ref": decision.bound_entity_ref,
                     "binding_claim_id": decision.binding_claim_id},
            writes="bound_entity_ref = ?, binding_claim_id = ?, match_method = ?, "
                   "provenance_class = ?",
            write_args=(decision.bound_entity_ref, decision.binding_claim_id,
                        decision.match_method, decision.provenance_class),
            actor_type=("human" if str(actor_kind).upper() == HUMAN else "system"),
            actor_id=actor_id, correlation_id=correlation_id, causation_id=causation_id,
            trace_id=trace_id, event_id=event_id)

    # --- OB-5: supersession -----------------------------------------------------------------------

    def supersede(
        self,
        observation_id: str,
        *,
        superseded_by: str,
        rule_id: str | None = None,
        actor_id: str = "system",
        actor_kind: str = "system",
        expected: Observation | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """OB-5 — ### SUPERSESSION REQUIRES A DETERMINISTIC RULE OR A HUMAN, NEVER A RE-RUN OF THE
        INFERRER (entity §24, GR-9). A newer observation supersedes a BOUND or PARSED one; the old row
        is RETAINED — it was true when made. A model re-run offered as a supersession is REFUSED.

        The `superseded_by` observation must already exist (self-FK) — a NEWER observation, not a
        promise of one.
        """
        obs = expected or self.require(observation_id)
        newer = str(superseded_by or "").strip()
        if not newer:
            raise GuardNotSatisfied("OB-5 names the newer observation that supersedes this one.")
        is_human = str(actor_kind).upper() == HUMAN and bool(str(actor_id or "").strip())
        is_rule = bool(str(rule_id or "").strip())
        is_model = str(actor_kind).lower() == "model"
        if is_model or (not is_human and not is_rule):
            # ### A MODEL RE-RUN NEVER SUPERSEDES AN OBSERVATION. Neither a rule nor a human authorised
            # it, or it is explicitly an inferrer re-run — refused, recorded, nothing persisted.
            self._record_illegal(obs, Trigger.NEWER_OBSERVATION_SUPERSEDES, actor_id=actor_id)
            raise IllegalTransition(
                "OB-5 supersession requires a deterministic rule (rule_id) or an authenticated human, "
                "never a re-run of the inferrer (entity §24, GR-9). A wrong reading is superseded by a "
                "newer observation on a RULE or a HUMAN decision, not by re-running the model.")
        if self.get(newer) is None:
            raise GuardNotSatisfied(
                f"OB-5's superseded_by {newer!r} names an observation that does not exist for tenant "
                f"{self._tenant!r}: a NEWER observation supersedes, not a promise of one.")
        return self._advance(
            obs, Trigger.NEWER_OBSERVATION_SUPERSEDES, ObservationState.SUPERSEDED,
            event_name="ObservationSuperseded", payload={"superseded_by": newer},
            writes="superseded_by = ?", write_args=(newer,),
            actor_type=("human" if is_human else "system"), actor_id=actor_id,
            correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
            event_id=event_id)

    # --- the strict-order consumer, replay & park/drain -------------------------------------------

    def reference_resolver(self, aggregate_type: str, aggregate_id: str) -> bool:
        """Does the referenced observation exist yet, FOR THIS TENANT? M-26's question, tenant-scoped.
        A reference to a not-yet-received observation is PARKED, never dropped (events/registry.md §8).
        """
        if aggregate_type != AGGREGATE_TYPE:
            return True
        return self._conn.execute(
            "SELECT 1 FROM observations WHERE tenant = ? AND observation_id = ?",
            (self._tenant, aggregate_id)).fetchone() is not None

    def consume_event(
        self, envelope: EventEnvelope, *, inbox: DedupInbox | None = None,
        requires_existing: tuple[tuple[str, str], ...] = (), drain: bool = True,
    ) -> ConsumedTransition:
        """Consume one canonical `observation` event idempotently through P5's dedup inbox.

        ### REPLAY CREATES ZERO NEW OBSERVATIONS AND ZERO DOWNSTREAM EFFECTS (GR-11, K-3). Reconstruction
        advances an EXISTING durable row's processing status to match the event WITHOUT re-ingesting,
        WITHOUT re-emitting, and WITHOUT any external effect. `ObservationReceived`/`ObservationConfirmed`
        are creation/freshness MARKERS (the row is created by `ingest`, not by a fold). Redelivery is a
        no-op by the inbox (GR-4). ### A REFERENCE TO A NOT-YET-RECEIVED OBSERVATION IS PARKED (M-26)
        and released the moment that observation arrives — pass it as `requires_existing`.
        """
        target_id = envelope.aggregate_id
        box = inbox or DedupInbox(
            self._conn, tenant=self._tenant, consumer_id=CONSUMER_ID, clock=self._clock,
            reference_resolver=self.reference_resolver)
        outcome: dict[str, Any] = {"transition": None, "refusal": None}

        def handler(event: EventEnvelope) -> None:
            obs = self.get(event.aggregate_id)
            if obs is None:
                outcome["refusal"] = (
                    f"{event.event_name} references observation {event.aggregate_id!r}, which does "
                    f"not exist for tenant {self._tenant!r}. Consumed once, nothing persisted.")
                return
            target = _event_target_state(event)
            if target is None or obs.state is target or obs.is_terminal:
                # A marker (received/confirmed/illegal), an already-reconstructed state, or a terminal
                # row: advance the cursor over the COMPLETE stream, change nothing.
                return
            outcome["transition"] = self._reconstruct_locked(obs, event, target)

        result = box.consume(
            envelope, handler,
            requires_existing=(requires_existing or ((AGGREGATE_TYPE, target_id),)),
            drain_handler_for=((lambda _env: handler) if drain else None))
        return ConsumedTransition(
            consume=result, transition=outcome["transition"], refusal=outcome["refusal"])

    def rebuild(self, observation_id: str, *,
                events: list[EventEnvelope] | None = None) -> ReconstructedObservation:
        """### A FULL-HISTORY FOLD OF ONE OBSERVATION — SANDBOXED, ZERO AUTHORITY (GR-11, ER-2).

        It reconstructs processing status from the event stream and creates NOTHING: no new
        observation, no duplicate row, no downstream work, the outside world untouched. Re-applying
        `ObservationReceived` is idempotent by the natural key, so replay produces zero duplicates.
        """
        stream = events if events is not None else self._event_stream(observation_id)
        state: ObservationState | None = None
        for event in stream:
            target = _event_target_state(event)
            if target is not None:
                state = target
            elif event.event_name == "ObservationReceived" and state is None:
                state = ObservationState.RECEIVED
        return ReconstructedObservation(
            observation_id=observation_id, state=state, new_observations=0, duplicate_rows=0,
            downstream_work=0, external_effects=0)

    # --- shared transition plumbing ---------------------------------------------------------------

    def _advance(
        self, obs: Observation, trigger: Trigger, to_state: ObservationState, *,
        event_name: str, payload: Mapping[str, Any], writes: str, write_args: tuple[Any, ...],
        actor_type: str, actor_id: str, correlation_id: str | None, causation_id: str | None,
        trace_id: str | None, event_id: str | None,
    ) -> TransitionResult:
        """One processing-status transition: the state row and its event, or neither (GR-2). OCC on the
        version the decision was read at (GR-3): zero rows is a lost update that raises."""
        candidates = tuple(
            row for row in TRANSITIONS
            if row.id != "OB-1" and obs.state in row.from_states and trigger in row.triggers
            and row.to_state is to_state)
        if not candidates:
            self._record_illegal(obs, trigger, actor_id=actor_id)
            raise IllegalTransition(
                f"{trigger.value} is not legal for an observation in {obs.state.value} "
                f"(GR-1, [C-4]). No state change persisted; `IllegalTransitionAttempted` recorded to "
                f"audit and security. A SUPERSEDED or UNPARSEABLE observation is final; a stale one is "
                f"still a fact and is never swept.")
        row = candidates[0]
        now = format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            set_clause = "state = ?, version = version + 1, updated_at = ?"
            if writes:
                set_clause += ", " + writes
            args: list[Any] = [to_state.value, now, *write_args,
                               self._tenant, obs.observation_id, obs.state.value, obs.version]
            cursor = conn.execute(
                f"UPDATE observations SET {set_clause} "
                f"WHERE tenant = ? AND observation_id = ? AND state = ? AND version = ?",
                args)
            if cursor.rowcount != 1:
                raise StateConflict(
                    f"{row.id} matched {cursor.rowcount} rows for {obs.observation_id!r}: it moved "
                    f"under us (GR-3). Reload and decide again — a lost update on processing status "
                    f"is refused, never a write that silently wins.")
            after = self.require(obs.observation_id)
            envelope = self._envelope(
                event_name=event_name, transition_id=row.id, observation=after,
                aggregate_version=self._next_version(obs.observation_id), actor_type=actor_type,
                actor_id=actor_id, payload=dict(payload), correlation_id=correlation_id,
                causation_id=causation_id, trace_id=trace_id, event_id=event_id, now=now)
            self._outbox().emit(envelope)
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        return TransitionResult(
            transition_id=row.id, observation=after, from_state=obs.state, to_state=to_state,
            event_ids=(envelope.event_id,), event_names=(event_name,))

    def _reconstruct_locked(
        self, obs: Observation, event: EventEnvelope, target: ObservationState,
    ) -> TransitionResult:
        """Advance a durable row to match a durable event — reconstruction, not a live transition.

        Runs inside the inbox's own commit (M-24): no BEGIN, no COMMIT. It sets the processing status
        and its payload fields WITHOUT re-emitting and WITHOUT any effect. It never touches the
        immutable content (`raw_value`, `content_digest`).
        """
        conn = self._conn
        now = format_instant(self._clock())
        writes = ["state = ?", "version = version + 1", "updated_at = ?"]
        args: list[Any] = [target.value, now]
        if target is ObservationState.PARSED:
            writes.append("parsed_value = ?")
            args.append(event.payload.get("parsed_value"))
        elif target is ObservationState.BOUND:
            writes.append("bound_entity_ref = ?")
            args.append(event.payload.get("bound_entity_ref"))
            writes.append("binding_claim_id = ?")
            args.append(event.payload.get("binding_claim_id"))
            writes.append("provenance_class = ?")
            args.append(event.payload.get("provenance_class") or obs.provenance_class)
        elif target is ObservationState.SUPERSEDED:
            writes.append("superseded_by = ?")
            args.append(event.payload.get("superseded_by"))
        conn.execute(
            f"UPDATE observations SET {', '.join(writes)} "
            f"WHERE tenant = ? AND observation_id = ? AND state = ?",
            (*args, self._tenant, obs.observation_id, obs.state.value))
        after = self.require(obs.observation_id)
        return TransitionResult(
            transition_id="replay", observation=after, from_state=obs.state, to_state=target)

    # --- content / provenance / owner guards ------------------------------------------------------

    def _reject_provenance_from_content(self, raw_value: str | Mapping[str, Any]) -> None:
        """### CONTENT CANNOT CHOOSE ITS OWN PROVENANCE (M-13, R-P1). A mapping that carries a
        `provenance_class` key is inbound data trying to strengthen itself; refused. (The F14
        `ProvenanceStrengtheningAttempted` EMISSION half is Implementation Phase 7's, not M5's — §3.10.)
        """
        if isinstance(raw_value, Mapping) and "provenance_class" in {str(k) for k in raw_value}:
            raise ContentIsData(
                "inbound content carries a `provenance_class`, and provenance is RUNTIME-ASSIGNED "
                "(M-13, R-P1), never set from content. The content is filed as DATA; it does not get "
                "to say how much it can bear. (This is the refusal half; the F14 audit record of the "
                "attempt lands in Implementation Phase 7, not here — §3.10.)")

    def _require_runtime_provenance(self, provenance_class: str) -> None:
        """### A MODEL_INFERRED OBSERVATION IS NOT AN OBSERVATION (entity §13/§37). An Observation is
        what a source SAID, not a guess. The DB CHECK is defense in depth; this is the guard a mutation
        flips."""
        value = str(provenance_class or "").strip()
        if value == OBSERVATION_FORBIDDEN_PROVENANCE:
            raise GuardNotSatisfied(
                "a MODEL_INFERRED observation cannot exist (entity §37): an Observation records what a "
                "source said, not what a model guessed. A guess is a Claim (M6), never an Observation.")
        if value not in _KNOWN_PROVENANCE:
            raise GuardNotSatisfied(
                f"provenance_class {value!r} is not a canonical provenance class "
                f"{sorted(_KNOWN_PROVENANCE)} — it is runtime-assigned (M-13).")

    def _require_named_human(self, owner_id: str | None, state: ObservationState) -> str:
        """### UNBOUND / UNPARSEABLE IS OWNED BY A NAMED HUMAN (entity §36, machine §9). "A human" is
        decoration while owner_id is a text column any string satisfies (M1's argument for owner_id):
        it must be a recorded, ACTIVE human of this tenant, FK-backed."""
        owner = str(owner_id or "").strip()
        if not owner:
            raise GuardNotSatisfied(
                f"an observation moving to {state.value} names the accountable human who owns the "
                f"exception (entity §36): '{state.value} without a human owner' is a silent drop "
                f"wearing a status.")
        human = self._conn.execute(
            "SELECT state FROM tenant_humans WHERE tenant = ? AND human_id = ?",
            (self._tenant, owner)).fetchone()
        if human is None or human["state"] != "ACTIVE":
            raise GuardNotSatisfied(
                f"{state.value} names owner {owner!r}, who is not an ACTIVE recorded human of "
                f"{self._tenant!r}. The exception owner is FK-backed, not a free-text string.")
        return owner

    # --- illegal-transition recording -------------------------------------------------------------

    def _record_illegal(self, obs: Observation, trigger: Trigger, *, actor_id: str) -> None:
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            version = max(1, self._outbox().last_emitted_version(
                AGGREGATE_TYPE, obs.observation_id))
            identity = (f"{ILLEGAL_ATTEMPT_IDENTITY_PREFIX}|{self._tenant}|{AGGREGATE_TYPE}"
                        f"|{obs.observation_id}|{version}|{trigger.value}|{actor_id}")
            existing = conn.execute(
                "SELECT event_id FROM event_outbox WHERE tenant = ? AND idempotency_identity = ?",
                (self._tenant, identity)).fetchone()
            if existing is None:
                now = format_instant(self._clock())
                envelope = self._envelope(
                    event_name="IllegalTransitionAttempted",
                    transition_id=ILLEGAL_TRANSITION_PRODUCER, observation=obs,
                    aggregate_version=version, actor_type="system", actor_id=actor_id,
                    payload={"machine": "M5", "state": obs.state.value,
                             "trigger": trigger.value, "attempted_by": actor_id},
                    correlation_id=None, causation_id=None, trace_id=None, event_id=None, now=now,
                    idempotency_identity=identity)
                self._outbox().emit(envelope)
                self._store_security_event(envelope, actor_id, "IllegalTransitionAttempted")
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

    def _event_stream(self, observation_id: str) -> list[EventEnvelope]:
        rows = self._conn.execute(
            "SELECT envelope_json FROM event_outbox WHERE tenant = ? AND aggregate_type = ? "
            "AND aggregate_id = ? ORDER BY aggregate_version, sequence",
            (self._tenant, AGGREGATE_TYPE, observation_id)).fetchall()
        return [EventEnvelope.from_json(r["envelope_json"]) for r in rows]

    def _next_version(self, observation_id: str) -> int:
        return self._outbox().last_emitted_version(AGGREGATE_TYPE, observation_id) + 1

    def _outbox(self):
        from .event_outbox import TransactionalOutbox
        return TransactionalOutbox(self._conn, tenant=self._tenant, clock=self._clock)

    def _envelope(
        self, *, event_name: str, transition_id: str, observation: Observation,
        aggregate_version: int, actor_type: str, actor_id: str, payload: Mapping[str, Any],
        correlation_id: str | None, causation_id: str | None, trace_id: str | None,
        event_id: str | None, now: str, idempotency_identity: str | None = None,
    ) -> EventEnvelope:
        """One canonical envelope on the `observation` aggregate. ### NO `previous_aggregate_version`
        TRAVELS ON IT: `observation` is ORDER-TOLERANT (events/registry.md §8), so declaring a
        strict-order predecessor would invent a guarantee canon did not ask for. The natural key is
        the only ordering mechanism, and it makes ingestion commutative."""
        return EventEnvelope(
            event_id=event_id or str(uuid.uuid4()),
            event_name=event_name,
            event_version=CONTRACTS[event_name].current_version,
            occurred_at=now, recorded_at=now, tenant_id=self._tenant,
            aggregate_type=AGGREGATE_TYPE, aggregate_id=observation.observation_id,
            aggregate_version=aggregate_version,
            previous_aggregate_version=None,      # ### F5 IS ORDER-TOLERANT: NONE DECLARED (§3.6)
            causation_id=causation_id,
            correlation_id=correlation_id or observation.observation_id,
            producer_component=self._component, producer_transition_id=transition_id,
            actor_type=actor_type, actor_id=actor_id,
            trace_id=trace_id or f"trace-{observation.observation_id}",
            payload=dict(payload), accountable_owner_id=observation.owner_id,
            idempotency_identity=idempotency_identity)


# ------------------------------------------------------------------------------------- plumbing

def _event_target_state(event: EventEnvelope) -> ObservationState | None:
    """The processing status an observation event reconstructs to, or None for a non-state event (a
    creation/freshness marker or an F14 marker riding the aggregate)."""
    name = event.event_name
    if name == "ObservationParsed":
        return ObservationState.PARSED
    if name == "ObservationUnparseable":
        return ObservationState.UNPARSEABLE
    if name == "ObservationBound":
        return ObservationState.BOUND
    if name == "ObservationUnbound":
        return ObservationState.UNBOUND
    if name == "ObservationSuperseded":
        return ObservationState.SUPERSEDED
    # ObservationReceived (creation), ObservationConfirmed (freshness), IllegalTransitionAttempted.
    return None


def _canonical_text(raw_value: str | Mapping[str, Any] | Any) -> str:
    """The exact observed value as text. A mapping is canonicalised (sorted keys) so an identical
    payload hashes identically regardless of key order; a string is taken verbatim."""
    if isinstance(raw_value, str):
        return raw_value
    if isinstance(raw_value, Mapping):
        return json.dumps(raw_value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return str(raw_value)


def _require_text(value: str, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise GuardNotSatisfied(f"{field_name} is required and was empty.")
    return text


def _row_to_observation(row: Any) -> Observation:
    return Observation(
        tenant=row["tenant"], observation_id=row["observation_id"],
        source_system=row["source_system"], external_id=row["external_id"],
        content_digest=row["content_digest"], raw_value=row["raw_value"], as_of=row["as_of"],
        received_at=row["received_at"], state=ObservationState(row["state"]), version=row["version"],
        provenance_class=row["provenance_class"], parsed_value=row["parsed_value"],
        bound_entity_ref=row["bound_entity_ref"], binding_claim_id=row["binding_claim_id"],
        match_method=row["match_method"], owner_id=row["owner_id"],
        unparse_reason=row["unparse_reason"], supersedes=row["supersedes"],
        superseded_by=row["superseded_by"])


# Re-exported so a caller reads one name rather than importing the migration for a constant.
STATES: tuple[str, ...] = OBSERVATION_STATES
