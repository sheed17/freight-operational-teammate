"""P9 — the ONE composition point between the freight domain and the P6-P8 foundational machines.

### WHY THERE IS EXACTLY ONE. Each foundational machine shipped with a guard asserting that nothing in
production imported it, and for its whole life that was right. P9 is the phase those machines were
built for, so "zero importers" became false the day freight arrived. The property the guards really
protect is that a machine must not acquire importers scattered across the codebase, each free to
compose it its own way. So every one of those guards now names THIS module, by exact set — the same
replacement `test_phase6_policy.py` made when P8 wired M11 through `policy_admission.py`.

Every other module in `freight_domain/` reaches a machine through `FreightFoundation`. None of them
imports `observation`, `identity_binding_claim`, `conflict`, `expectation`, `exception`, `work_item`,
`evidence`, `provenance` or `linker` directly.

### WHAT THIS MODULE DECIDES, AND WHAT IT DOES NOT. It decides nothing about freight. It sequences
calls the machines already define — ingest then parse then bind; propose then resolve — and it mints
deterministic ids so that replaying a freight history reproduces the same canonical records. Every
guard that matters (a guess never binds, an owner is a recorded ACTIVE human, OVERDUE needs proven
coverage, a second detection coalesces) lives in the machine and is not restated here.

### IT REACHES NOTHING EFFECT-CAPABLE. No checkpoint minting, no Effect Grant, no approval, no
compensation, no adapter, no transport relay. `effect_surface_counts` exists so a caller can PROVE
that — a negative assertion over a population it reads rather than assumes.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..checkpoint import EvidenceCondition, ProvenanceClass
from ..conflict import M7Machine, Party
from ..event_envelope import EventEnvelope, format_instant
from ..evidence import EvidenceStore
from ..exception import M9Machine
from ..expectation import HEALTHY_COVERAGE, ExState, M8Machine, facility_local_deadline
from ..identity_binding_claim import M6Machine, MatchAttempt, MatchMethod
from ..linker import LinkStatus, Signal, link
from ..observation import BindingDecision, BindingKind, M5Machine, ProcessingState
from ..provenance import (
    Acquisition,
    ProvenanceFromContent,
    as_class,
    assign_at_runtime,
    may_gate_consequential_action,
    reject_content_supplied_provenance,
)
from ..tenant import require_tenant
from ..work_item import WorkItemMachine, record_human_authority

__all__ = [
    "Acquisition",
    "BindingOutcome",
    "EvidenceCondition",
    "FreightFoundation",
    "HEALTHY_COVERAGE",
    "LinkDecision",
    "Observed",
    "ProvenanceClass",
    "ProvenanceFromContent",
    "as_class",
    "assign_at_runtime",
    "facility_local_deadline",
    "format_instant",
    "may_gate_consequential_action",
    "stable_id",
]

#: Tables that would hold a row if this package had caused an external effect or minted authority.
#: FIXED-SPECIFICATION: these are the effect/authority ledgers of ARCHITECTURE.md, not a population to
#: discover — discovering them would mean asking the schema which tables matter, which is the question.
EFFECT_SURFACE_TABLES: tuple[str, ...] = (
    "effect_grants", "checkpoint_witnesses", "approvals", "compensations", "pipeline_instances",
)

#: The M8 states in which a thing is still owed.
OWED_EXPECTATION_STATES: tuple[str, ...] = (
    ExState.RAISED.value, ExState.OVERDUE.value, ExState.INDETERMINATE.value,
)


def stable_id(prefix: str, *parts: object, length: int = 20) -> str:
    """A deterministic id from the facts that identify a record. Same history, same id, every run —
    which is what lets a replayed freight history reproduce the same canonical projection instead of
    a second copy of it."""
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest[:length]}"


def _reject_nested_provenance(content: object) -> None:
    """R-P1 at every depth. `reject_content_supplied_provenance` reads one mapping; an inbound record
    nests, and a `provenance_class` three levels down is the same attempt wearing more braces."""
    if isinstance(content, Mapping):
        reject_content_supplied_provenance(content)
        for value in content.values():
            _reject_nested_provenance(value)
    elif isinstance(content, (list, tuple)):
        for item in content:
            _reject_nested_provenance(item)


@dataclass(frozen=True)
class Observed:
    """What one intake did. `duplicate` is an identical re-delivery: one row, zero downstream work."""

    observation_id: str
    created: bool
    duplicate: bool
    state: str
    content_digest: str


@dataclass(frozen=True)
class LinkDecision:
    """The deterministic linker's verdict over the candidates a record's references resolved to."""

    status: str                       # CONFIRMED | AMBIGUOUS | CONFLICT (linker.LinkStatus values)
    entity_ref: str | None = None
    reason: str | None = None         # the M6 ClaimAmbiguous reason when not CONFIRMED
    candidates: tuple[str, ...] = ()


@dataclass(frozen=True)
class BindingOutcome:
    """What the artifact-to-entity binding ended as."""

    observation_id: str
    state: str                        # BOUND | UNBOUND
    entity_ref: str | None
    match_method: str | None
    candidates: tuple[str, ...] = ()
    reason: str | None = None


class FreightFoundation:
    """The foundational machines for ONE tenant on ONE connection, behind freight-shaped verbs.

    Bound to its tenant at construction, exactly as the machines are, so a caller cannot re-point it
    at another brokerage and put tenant isolation in its own hands [C-1]."""

    def __init__(self, conn: sqlite3.Connection, *, tenant: str,
                 clock: Callable[[], datetime]) -> None:
        self._conn = conn
        self._tenant = require_tenant(tenant, context="FreightFoundation")
        self._clock = clock
        self._m1 = WorkItemMachine(conn, tenant=self._tenant, clock=clock)
        self._m5 = M5Machine(conn, tenant=self._tenant, clock=clock)
        self._m6 = M6Machine(conn, tenant=self._tenant, clock=clock)
        self._m7 = M7Machine(conn, tenant=self._tenant, clock=clock)
        self._m8 = M8Machine(conn, tenant=self._tenant, clock=clock)
        self._m9 = M9Machine(conn, tenant=self._tenant, clock=clock)
        self._evidence = EvidenceStore(conn)

    @property
    def tenant(self) -> str:
        return self._tenant

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    def now(self) -> str:
        return format_instant(self._clock())

    # ------------------------------------------------------------------ people (E1's roster)

    def provision_human(self, *, human_id: str, display_name: str, authority_role: str,
                        recorded_by: str) -> None:
        """Admit a named human to this tenant, once. Ownership must come from a recorded authority;
        an owner the machines cannot find FK-backed is refused by every one of them."""
        row = self._conn.execute(
            "SELECT 1 FROM tenant_humans WHERE tenant = ? AND human_id = ?",
            (self._tenant, human_id)).fetchone()
        if row is None:
            record_human_authority(
                self._conn, tenant=self._tenant, human_id=human_id, display_name=display_name,
                authority_role=authority_role, recorded_by=recorded_by, now=self._clock())

    def is_active_human(self, human_id: str | None) -> bool:
        row = self._conn.execute(
            "SELECT state FROM tenant_humans WHERE tenant = ? AND human_id = ?",
            (self._tenant, str(human_id or ""))).fetchone()
        return row is not None and row["state"] == "ACTIVE"

    # ------------------------------------------------------------------ intake (M5)

    def observe(self, *, source_system: str, external_id: str, content: Mapping[str, Any],
                as_of: str, received_at: str, acquisition: Acquisition) -> Observed:
        """Record that a source SAID something. Identical content re-delivered is a confirmation —
        one row, zero downstream work. Provenance is assigned HERE, from how the record was obtained
        (R-P1); content that tries to carry its own is refused at any depth."""
        _reject_nested_provenance(content)
        provenance = assign_at_runtime(acquisition).value
        digest = M5Machine.content_digest(content)
        observation_id = stable_id("obs", self._tenant, source_system, external_id, digest)
        outcome = self._m5.ingest(
            source_system=source_system, external_id=external_id, raw_value=content, as_of=as_of,
            observation_id=observation_id, provenance_class=provenance, received_at=received_at)
        return Observed(
            observation_id=outcome.observation_id, created=outcome.created,
            duplicate=outcome.confirmed, state=outcome.state.value,
            content_digest=outcome.content_digest)

    def mark_parsed(self, observation_id: str, parsed: Mapping[str, Any]) -> None:
        self._m5.parse(observation_id, parsed_value=parsed, actor_id="freight-domain-parser")

    def mark_unparseable(self, observation_id: str, *, owner_id: str, reason: str) -> None:
        """A record the parser cannot read is UNPARSEABLE and human-owned — never dropped."""
        self._m5.parse(observation_id, ok=False, owner_id=owner_id, unparse_reason=reason,
                       actor_id="freight-domain-parser")

    # ------------------------------------------------------------------ the linker (P7)

    def decide_link(self, observation_id: str, *, exact: Sequence[tuple[str, str]],
                    weak: Sequence[str] = (),
                    model_candidates: Sequence[tuple[str, str]] = ()) -> LinkDecision:
        """Decide which entity an artifact belongs to, in ADR-007 sec 4.1's fixed order.

        `exact` is `(entity_ref, mapping_id)` for every reference that resolved through an ACTIVE
        External Entity Mapping. `weak` is entities reachable only through a retired mapping or an
        unqualified reference. `model_candidates` is `(entity_ref, source)` proposed by a model for a
        record exact resolution could not place (`interpretation.py`). Whatever is passed through it
        can never confirm: the linker routes a model inference to AMBIGUOUS at any confidence
        (GR-8)."""
        signals = [Signal(match_method="EXACT_ID", identifier=entity_ref, source=mapping_id)
                   for entity_ref, mapping_id in exact]
        signals.extend(Signal(match_method="MODEL_INFER", identifier=entity_ref, source=source)
                       for entity_ref, source in model_candidates)
        if not signals:
            candidates = tuple(dict.fromkeys(weak))
            return LinkDecision(status=LinkStatus.AMBIGUOUS.value, reason="single_weak",
                                candidates=candidates)
        outcome = link(observation_id, signals)
        if outcome.status is LinkStatus.CONFIRMED:
            return LinkDecision(status=LinkStatus.CONFIRMED.value,
                                entity_ref=outcome.bound_identifier)
        if outcome.status is LinkStatus.CONFLICT:
            return LinkDecision(status=LinkStatus.CONFLICT.value, reason="multiple",
                                candidates=tuple(outcome.conflict_parties))
        candidates = tuple(dict.fromkeys([s.identifier for s in signals]))
        return LinkDecision(status=LinkStatus.AMBIGUOUS.value, reason=outcome.reason,
                            candidates=candidates)

    # ------------------------------------------------------------------ binding (M6 + M5)

    def bind_exact(self, observation_id: str, entity_ref: str) -> BindingOutcome:
        """An exact, tenant-scoped reference resolved to exactly one entity: M6 confirms it
        (LINKER_INFERRED) and M5 binds. Idempotent, and it resolves an earlier UNBOUND (OB-4) — a late
        deterministic match is the machine's own legal way out of UNBOUND."""
        obs = self._m5.require(observation_id)
        existing = self._m6.confirmed_binding_for(observation_id)
        if existing is not None:
            return BindingOutcome(observation_id, ProcessingState.BOUND.value, existing.entity_ref,
                                  existing.match_method)
        self._reject_open_claims(observation_id, reason="a later deterministic match")
        attempt = MatchAttempt(subject_ref=observation_id, entity_ref=entity_ref,
                               match_method=MatchMethod.EXACT_ID)
        claim = self._m6.link(
            attempt, binding_claim_id=stable_id("ibc", self._tenant, observation_id, entity_ref,
                                                "EXACT_ID", obs.version),
            actor_id="freight-domain-linker").claim
        decision = BindingDecision(
            kind=BindingKind.CONFIRMED, bound_entity_ref=entity_ref,
            binding_claim_id=claim.binding_claim_id, match_method="EXACT_ID",
            provenance_class=claim.provenance_class)
        self._apply_binding(obs, decision, actor_id="freight-domain-linker", actor_kind="system")
        return BindingOutcome(observation_id, ProcessingState.BOUND.value, entity_ref, "EXACT_ID")

    def bind_ambiguous(self, observation_id: str, *, candidates: Sequence[str], owner_id: str,
                       reason: str) -> BindingOutcome:
        """Several plausible entities, or only a weak one: NO bind. Each candidate is recorded as an
        AMBIGUOUS claim owned by a named human, and the observation is UNBOUND. Neyma does not pick
        the closest candidate."""
        obs = self._m5.require(observation_id)
        distinct = tuple(dict.fromkeys(candidates))
        weak = reason == "single_weak"
        for entity_ref in distinct:
            claim_id = stable_id("ibc", self._tenant, observation_id, entity_ref, "AMBIGUOUS")
            if self._m6.get(claim_id) is not None:
                continue
            attempt = MatchAttempt(
                subject_ref=observation_id, entity_ref=entity_ref,
                match_method=MatchMethod.EXACT_ID, candidate_count=max(len(distinct), 1),
                open_entity_count=max(len(distinct), 1), weak=weak)
            self._m6.link(attempt, owner_id=owner_id, binding_claim_id=claim_id,
                          actor_id="freight-domain-linker")
        if obs.state is ProcessingState.PARSED:
            kind = BindingKind.WEAK if weak else BindingKind.AMBIGUOUS
            self._m5.bind(observation_id,
                          BindingDecision(kind=kind, candidate_count=len(distinct)),
                          owner_id=owner_id, actor_id="freight-domain-linker")
        return BindingOutcome(observation_id, ProcessingState.UNBOUND.value, None, None,
                              candidates=distinct, reason=reason)

    def bind_model_candidates(self, observation_id: str, *,
                              candidates: Sequence[tuple[str, float | None]],
                              owner_id: str) -> BindingOutcome:
        """A model PROPOSED which entity an artifact belongs to: NO bind, whatever it proposed. Each
        candidate is recorded through M6 as a `MODEL_INFER` attempt, which M6 routes to AMBIGUOUS
        ("model_inferred", `MODEL_INFERRED`) and a named human — for one candidate exactly as for
        five, and at any stated support (GR-8). The number carried with a candidate orders that
        human's queue; no guard here or in M6 reads it."""
        obs = self._m5.require(observation_id)
        distinct = tuple(dict.fromkeys(ref for ref, _ in candidates))
        for entity_ref, queue_order in candidates:
            claim_id = stable_id("ibc", self._tenant, observation_id, entity_ref, "MODEL_INFER")
            if self._m6.get(claim_id) is not None:
                continue
            attempt = MatchAttempt(
                subject_ref=observation_id, entity_ref=entity_ref,
                match_method=MatchMethod.MODEL_INFER, candidate_count=max(len(distinct), 1),
                confidence=queue_order)
            self._m6.link(attempt, owner_id=owner_id, binding_claim_id=claim_id,
                          actor_id="freight-domain-interpreter")
        if obs.state is ProcessingState.PARSED:
            self._m5.bind(observation_id,
                          BindingDecision(kind=BindingKind.AMBIGUOUS,
                                          candidate_count=len(distinct)),
                          owner_id=owner_id, actor_id="freight-domain-linker")
        return BindingOutcome(observation_id, ProcessingState.UNBOUND.value, None, None,
                              candidates=distinct, reason="model_inferred")

    def leave_unbound(self, observation_id: str, *, owner_id: str) -> BindingOutcome:
        """No reference resolved to anything this tenant knows. UNBOUND, human-owned, and retried
        when a later mapping makes the reference resolvable."""
        obs = self._m5.require(observation_id)
        if obs.state is ProcessingState.PARSED:
            self._m5.bind(observation_id, BindingDecision(kind=BindingKind.ABSENT),
                          owner_id=owner_id, actor_id="freight-domain-linker")
        return BindingOutcome(observation_id, ProcessingState.UNBOUND.value, None, None,
                              reason="absent")

    def bind_by_human(self, observation_id: str, *, entity_ref: str, human_id: str,
                      decision_ref: str) -> BindingOutcome:
        """IB-2h — the only route to an OWNER_ASSERTED binding. M6 requires an ACTIVE recorded human
        of this tenant and refuses a machine or a counterparty in that seat."""
        obs = self._m5.require(observation_id)
        self._reject_open_claims(observation_id, reason="an owner assertion")
        claim = self._m6.assert_human(
            entity_ref=entity_ref, decision_ref=decision_ref, decision_human_id=human_id,
            actor_id=human_id, actor_kind="human", subject_ref=observation_id,
            binding_claim_id=stable_id("ibc", self._tenant, observation_id, entity_ref, "HUMAN",
                                       decision_ref)).claim
        decision = BindingDecision(
            kind=BindingKind.CONFIRMED, bound_entity_ref=entity_ref,
            binding_claim_id=claim.binding_claim_id, match_method="HUMAN",
            provenance_class=claim.provenance_class)
        self._apply_binding(obs, decision, actor_id=human_id, actor_kind="HUMAN")
        return BindingOutcome(observation_id, ProcessingState.BOUND.value, entity_ref, "HUMAN")

    def correct_binding(self, observation_id: str, *, new_entity_ref: str, human_id: str,
                        decision_ref: str, dependent_refs: Sequence[str] = ()) -> BindingOutcome:
        """IB-7 — a human declares a CONFIRMED binding wrong. The prior claim is RETAINED as
        CORRECTED and a new OWNER_ASSERTED claim carries the right entity; M6 records the propagation
        obligation naming what rested on the wrong binding [CD-6, CD-7]."""
        current = self._m6.confirmed_binding_for(observation_id)
        if current is None:
            return self.bind_by_human(observation_id, entity_ref=new_entity_ref, human_id=human_id,
                                      decision_ref=decision_ref)
        self._m6.correct(
            current.binding_claim_id, new_entity_ref=new_entity_ref, decision_ref=decision_ref,
            decision_human_id=human_id, actor_id=human_id, actor_kind="human",
            dependent_refs=tuple(dependent_refs))
        return BindingOutcome(observation_id, ProcessingState.BOUND.value, new_entity_ref, "HUMAN")

    def _apply_binding(self, obs: Any, decision: BindingDecision, *, actor_id: str,
                       actor_kind: str) -> None:
        if obs.state is ProcessingState.UNBOUND:
            self._m5.resolve_unbound(obs.observation_id, decision, actor_id=actor_id,
                                     actor_kind=actor_kind)
        elif obs.state is ProcessingState.PARSED:
            self._m5.bind(obs.observation_id, decision, actor_id=actor_id, actor_kind=actor_kind)

    def _reject_open_claims(self, observation_id: str, *, reason: str) -> None:
        """IB-8 — a claim that never confirmed is REJECTED once the subject is bound elsewhere. The
        rows are retained; only their state moves."""
        rows = self._conn.execute(
            "SELECT binding_claim_id FROM identity_binding_claims WHERE tenant = ? "
            "AND subject_ref = ? AND state IN ('PROPOSED','AMBIGUOUS') ORDER BY binding_claim_id",
            (self._tenant, observation_id)).fetchall()
        for row in rows:
            self._m6.reject(row["binding_claim_id"], reason=reason,
                            actor_id="freight-domain-linker")

    # ------------------------------------------------------------------ evidence (P7)

    def retain_document(self, *, observation_id: str, content: bytes, media_type: str) -> str:
        """Retain an artifact content-addressed. Identical bytes are ONE Evidence, whichever message
        carried them."""
        return self._evidence.retain(
            self._tenant, content=content, media_type=media_type,
            source_observation_id=observation_id, now=self.now(),
            evidence_id=stable_id("ev", self._tenant, hashlib.sha256(content).hexdigest()))

    def attach_span(self, evidence_id: str, *, locator: str, extracted_text: str | None) -> None:
        if not self._evidence.spans_for(self._tenant, evidence_id):
            self._evidence.attach_span(
                self._tenant, evidence_id, locator=locator, extracted_text=extracted_text,
                now=self.now(), span_id=stable_id("span", self._tenant, evidence_id, locator))

    def attach_field_spans(self, evidence_id: str, spans: Sequence[Mapping[str, Any]]) -> int:
        """Point each value a model READ off a document at the place in the retained artifact it was
        read from. One span per `(evidence, locator, field)`, written once: the same bytes arriving
        again add nothing. Returns how many spans were newly written."""
        known = {s["span_id"] for s in self._evidence.spans_for(self._tenant, evidence_id)}
        written = 0
        for span in spans:
            span_id = stable_id("span", self._tenant, evidence_id, span["locator"], span["field"])
            if span_id in known:
                continue
            self._evidence.attach_span(
                self._tenant, evidence_id, locator=span["locator"], region=span["field"],
                extracted_text=span["text"], now=self.now(), span_id=span_id)
            known.add(span_id)
            written += 1
        return written

    def mark_illegible(self, evidence_id: str) -> None:
        self._evidence.mark_illegible(self._tenant, evidence_id)

    def evidence_condition(self, evidence_id: str) -> str:
        return self._evidence.evidence_condition(self._tenant, evidence_id)

    # ------------------------------------------------------------------ conflict (M7)

    def raise_conflict(self, *, conflict_id: str, kind: str, entity_ref: str, field: str,
                       parties: Sequence[tuple[str, str, str]], owner_id: str,
                       exposure: str | None = None) -> bool:
        """Two or more mutually exclusive statements about one field. M7 freezes the field and names a
        human; a second detection of the same disagreement attaches a party rather than raising a
        second Conflict. `parties` is `(observation_id, provenance_class, stated_value)` — each
        party's OWN provenance, carried and never strengthened. Returns True when a row was written.
        """
        if self._m7.get(conflict_id) is not None:
            known = self._m7.party_refs(conflict_id)
            for observation_id, provenance, stated in parties:
                if observation_id not in known and self._m7.require(conflict_id).is_open:
                    self._m7.attach_party(
                        conflict_id, Party(observation_id, "observation", provenance, stated),
                        actor_id="freight-domain")
            return False
        result = self._m7.raise_conflict(
            kind=kind, entity_ref=entity_ref, field=field, owner_id=owner_id,
            conflict_id=conflict_id, exposure=exposure, actor_id="freight-domain",
            correlation_id=entity_ref,
            parties=[Party(observation_id, "observation", provenance, stated)
                     for observation_id, provenance, stated in parties])
        return not result.coalesced

    def resolve_conflict_by_human(self, *, entity_ref: str, field: str, human_id: str,
                                  decision_ref: str) -> str | None:
        """CF-4 — a recorded, ACTIVE human of this tenant decides a disputed field. M7 refuses a
        machine, a model or a counterparty in that seat, and it keeps every party's statement: the
        row moves to RESOLVED_BY_HUMAN and nothing is deleted. A RAISED conflict is acknowledged by
        the same human first (CF-2), because M7 resolves only a conflict somebody owns. Returns the
        conflict id, or None when the field has no open conflict."""
        conflict = self._m7.open_conflict_for(entity_ref, field)
        if conflict is None:
            return None
        if conflict.state.value == "RAISED":
            self._m7.acknowledge(conflict.conflict_id, actor_id=human_id, actor_kind="human")
        self._m7.resolve_by_human(
            conflict.conflict_id, decision_ref=decision_ref, decision_human_id=human_id,
            actor_id=human_id, actor_kind="human")
        return conflict.conflict_id

    # ------------------------------------------------------------------ expectation (M8)

    def record_coverage(self, *, coverage_id: str, channel: str, window_start: str,
                        window_end: str, health: str, probe_source: str) -> bool:
        """A persisted statement about a CHANNEL over a WINDOW. Without one, a missed deadline is
        INDETERMINATE: we cannot call a carrier late over a channel we cannot prove we were watching.
        """
        row = self._conn.execute(
            "SELECT 1 FROM observation_coverage WHERE tenant = ? AND coverage_id = ?",
            (self._tenant, coverage_id)).fetchone()
        if row is not None:
            return False
        self._m8.record_coverage(coverage_id=coverage_id, channel=channel,
                                 window_start=window_start, window_end=window_end, health=health,
                                 probe_source=probe_source)
        return True

    def expectation_exists(self, expectation_id: str) -> bool:
        return self._m8.get(expectation_id) is not None

    def raise_expectation(self, *, expectation_id: str, subject_ref: str, expected_type: str,
                          expected_source: str, owner_id: str, originating_timezone: str,
                          deadline_utc: str | None = None,
                          appointment_local: datetime | None = None) -> bool:
        """What should happen by when. Returns True when a NEW expectation was raised; an id already
        present (in any state) or a live expectation for the same subject and type is not raised
        twice."""
        if self._m8.get(expectation_id) is not None:
            return False
        result = self._m8.raise_expectation(
            subject_ref=subject_ref, expected_type=expected_type, expected_source=expected_source,
            owner_id=owner_id, originating_timezone=originating_timezone,
            deadline_utc=deadline_utc, appointment_local=appointment_local,
            expectation_id=expectation_id, actor_id="freight-domain", correlation_id=subject_ref)
        return not result.coalesced

    def discharge(self, expectation_id: str, *, observation_id: str) -> bool:
        """A BOUND observation about the subject discharges what was owed. M8 accepts a late arrival
        and marks it late; it refuses an observation bound to another subject."""
        expectation = self._m8.get(expectation_id)
        if expectation is None or not expectation.is_owed:
            return False
        self._m8.discharge(expectation_id, observation_id=observation_id,
                           actor_id="freight-domain")
        return True

    def amend_deadline(self, expectation_id: str, *, deadline_utc: str) -> bool:
        """EX-5 — the thing is still owed, by a DIFFERENT time: an appointment was moved. M8
        re-versions the deadline, retains the prior one in `deadline_history`, and re-arms its
        timer. Only a RAISED expectation is amended; one already judged is not un-judged."""
        expectation = self._m8.get(expectation_id)
        if expectation is None or expectation.state is not ExState.RAISED \
                or expectation.deadline_utc == deadline_utc:
            return False
        self._m8.amend_deadline(expectation_id, new_deadline_utc=deadline_utc,
                                actor_id="freight-domain", actor_kind="system")
        return True

    def cancel_expectation(self, expectation_id: str, *, reason: str) -> bool:
        """EX-6 — the REASON for an expectation disappeared: what it was waiting for is no longer
        what is owed. The row is retained as CANCELLED with the reason. M8 has no such exit from
        INDETERMINATE, and none is invented here: that one stays a named human's."""
        expectation = self._m8.get(expectation_id)
        if expectation is None or expectation.state not in (ExState.RAISED, ExState.OVERDUE):
            return False
        self._m8.cancel(expectation_id, reason=reason, actor_id="freight-domain",
                        actor_kind="system")
        return True

    def evaluate_due(self, *, owner_id: str) -> list[tuple[str, str]]:
        """Evaluate every RAISED expectation whose deadline has passed on this foundation's clock.

        The verdict is M8's and comes ONLY from persisted coverage: OVERDUE over a demonstrably
        healthy window, INDETERMINATE when we were blind. Each verdict is then handed to M9 through
        its own registered consumer, which raises exactly one owned Exception and keeps the honesty
        split in the question it asks the human. Returns `(expectation_id, state)` per evaluation."""
        now = self.now()
        rows = self._conn.execute(
            "SELECT expectation_id FROM expectations WHERE tenant = ? AND state = 'RAISED' "
            "AND deadline_utc <= ? ORDER BY deadline_utc, expectation_id",
            (self._tenant, now)).fetchall()
        evaluated: list[tuple[str, str]] = []
        for row in rows:
            result = self._m8.evaluate_deadline(row["expectation_id"], owner_id=owner_id,
                                                actor_id="freight-domain-clock")
            if result is None:
                continue
            evaluated.append((row["expectation_id"], result.to_state.value))
            for event_id in result.event_ids:
                envelope = self._conn.execute(
                    "SELECT envelope_json FROM event_outbox WHERE tenant = ? AND event_id = ?",
                    (self._tenant, event_id)).fetchone()
                if envelope is not None:
                    self._m9.consume_source_escalation(
                        EventEnvelope.from_json(envelope["envelope_json"]))
        return evaluated

    # ------------------------------------------------------------------ exception (M9)

    def raise_exception(self, *, exception_id: str, type: str, severity: str, source_ref: str,
                        source_kind: str, owner_id: str, summary: str, entity_ref: str | None,
                        specific_question: str | None = None, exposure: str | None = None) -> bool:
        """Something a human must decide. One accountable owner at creation; a re-raise of the same
        cause coalesces. No age threshold is armed: the threshold is a per-brokerage constant nobody
        has supplied, and an unvalidated number compiled in here would be a freight rule nobody chose.
        """
        if self._m9.get(exception_id) is not None:
            return False
        result = self._m9.raise_exception(
            type=type, severity=severity, source_ref=source_ref, source_kind=source_kind,
            owner_id=owner_id, summary=summary, entity_ref=entity_ref,
            specific_question=specific_question, exposure=exposure, exception_id=exception_id,
            actor_id="freight-domain", correlation_id=entity_ref or source_ref,
            schedule_timer=False)
        return not result.coalesced

    def resolve_exception_by_human(self, exception_id: str, *, human_id: str,
                                   correlation_id: str | None = None) -> bool:
        """EC-3 / EC-6 — a recorded, ACTIVE human of this tenant explicitly resolves ONE Exception.
        M9 is the only thing that closes one, and it does so through its own transition: it refuses
        a machine, a model or anyone it has not recorded in that seat, records her as the decider,
        and retains the row and every event before it. Nothing here writes M9's storage. Returns
        False when there is no such open Exception for this tenant (nothing is closed)."""
        exception = self._m9.get(exception_id)
        if exception is None or not exception.is_open:
            return False
        self._m9.resolve_by_human(exception_id, decision_human_id=human_id, actor_kind="human",
                                  correlation_id=correlation_id or exception.entity_ref
                                  or exception.source_ref)
        return True

    # ------------------------------------------------------------------ work item (M1)

    def ensure_work_item(self, *, work_item_id: str, type: str, owner_id: str,
                         entity_ref: str) -> bool:
        """One accountable human per unit of work. Returns True when the Work Item was created."""
        if self._m1.get(work_item_id) is not None:
            return False
        self._m1.create(work_item_id=work_item_id, type=type, owner_id=owner_id,
                        actor_type="system", actor_id="freight-domain", entity_ref=entity_ref,
                        correlation_id=entity_ref)
        return True

    # ------------------------------------------------------------------ reads (tenant-scoped)

    def _rows(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        return [dict(r) for r in self._conn.execute(sql, (self._tenant, *params)).fetchall()]

    def observations(self) -> list[dict[str, Any]]:
        """Every Observation of this tenant, in arrival order. `parsed` is the decoded parse output."""
        rows = self._rows(
            "SELECT * FROM observations WHERE tenant = ? ORDER BY received_at, observation_id")
        for row in rows:
            row["parsed"] = json.loads(row["parsed_value"]) if row["parsed_value"] else None
        return rows

    def observation(self, observation_id: str) -> dict[str, Any] | None:
        rows = self._rows("SELECT * FROM observations WHERE tenant = ? AND observation_id = ?",
                          (observation_id,))
        if not rows:
            return None
        row = rows[0]
        row["parsed"] = json.loads(row["parsed_value"]) if row["parsed_value"] else None
        return row

    def observation_by_external(self, source_system: str, external_id: str) -> dict[str, Any] | None:
        rows = self._rows(
            "SELECT observation_id FROM observations WHERE tenant = ? AND source_system = ? "
            "AND external_id = ? ORDER BY received_at, observation_id",
            (source_system, external_id))
        return self.observation(rows[0]["observation_id"]) if rows else None

    def confirmation_counts(self) -> dict[str, int]:
        """How many identical re-deliveries M5 confirmed, per observation. Read from M5's own
        `ObservationConfirmed` events — the machine's record of a duplicate, not a tally kept beside
        it."""
        rows = self._conn.execute(
            "SELECT aggregate_id, COUNT(*) AS n FROM event_outbox WHERE tenant = ? "
            "AND aggregate_type = 'observation' AND event_name = 'ObservationConfirmed' "
            "GROUP BY aggregate_id", (self._tenant,)).fetchall()
        return {r["aggregate_id"]: int(r["n"]) for r in rows}

    def binding_claims(self) -> list[dict[str, Any]]:
        return self._rows(
            "SELECT * FROM identity_binding_claims WHERE tenant = ? "
            "ORDER BY created_at, binding_claim_id")

    def conflicts(self) -> list[dict[str, Any]]:
        rows = self._rows("SELECT * FROM conflicts WHERE tenant = ? ORDER BY created_at, conflict_id")
        for row in rows:
            row["parties"] = self._rows(
                "SELECT party_ref, party_kind, provenance_class, stated_value, attach_seq "
                "FROM conflict_parties WHERE tenant = ? AND conflict_id = ? "
                "ORDER BY attach_seq, party_id", (row["conflict_id"],))
        return rows

    def expectations(self) -> list[dict[str, Any]]:
        return self._rows(
            "SELECT * FROM expectations WHERE tenant = ? ORDER BY created_at, expectation_id")

    def exceptions(self) -> list[dict[str, Any]]:
        return self._rows(
            "SELECT * FROM exceptions WHERE tenant = ? ORDER BY created_at, type, source_ref")

    def work_items(self) -> list[dict[str, Any]]:
        return self._rows("SELECT * FROM work_items WHERE tenant = ? ORDER BY work_item_id")

    def evidence_rows(self) -> list[dict[str, Any]]:
        return self._rows("SELECT * FROM evidence WHERE tenant = ? ORDER BY created_at, evidence_id")

    def effect_surface_counts(self) -> dict[str, int]:
        """Row counts, for THIS tenant, on every ledger that would record an external effect or a
        minted authority. The freight spine must leave all of them at zero."""
        return {
            table: int(self._conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE tenant = ?", (self._tenant,)).fetchone()[0])
            for table in EFFECT_SURFACE_TABLES
        }
