"""P9 — freight intake: one inbound record at a time, through the foundational machines.

    record -> Observation (M5) -> parse -> resolve references (External Entity Mapping)
           -> bind (M6, then M5) -> project -> detect -> Conflict / Expectation / Exception (M7/M8/M9)

### THE ONLY THING THAT CREATES A LOAD IS THE SYSTEM OF RECORD. A `tms_load` snapshot whose load number
this brokerage has never seen creates a Brokerage Load and its mappings. No email, text, document or
tracking ping ever creates one: those must RESOLVE to a load that exists, or they are held.

### THE BINDING IS EXACT OR IT IS A HUMAN'S. Every reference a record carries is resolved, exactly and
within this tenant. The load must be consistent with ALL of them: the candidates are intersected.
Exactly one survivor binds (EXACT_ID, `LINKER_INFERRED`). More than one — a PO that covers two loads —
is AMBIGUOUS. None — a POD carrying one load's number and another load's BOL — is AMBIGUOUS too, with
both loads named. Nothing resolves — the record is UNBOUND, and is retried when a later mapping makes
its reference resolvable. In every non-exact case a named human owns it and nothing is bound.

### A DUPLICATE DOES NOTHING. An identical record re-delivered is an M5 confirmation; intake stops
there. No second parse, bind, document, payable, expectation or timeline entry.

### NO EFFECT, NO MODEL, NO ADAPTER. Intake reads records it is handed and writes canonical rows. It
sends nothing, calls nothing outside the process, and asks no model anything.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .detectors import (
    DischargeExpectation,
    Intent,
    RaiseConflict,
    RaiseException,
    RaiseExpectation,
    detect,
)
from .entity_mapping import (
    AMBIGUOUS,
    EXACT,
    RETIRED_ONLY,
    UNMAPPED,
    CandidateGenerator,
    ExternalEntityMappings,
    ExternalReference,
    NoCandidates,
)
from .foundation import (
    FreightFoundation,
    ProvenanceFromContent,
    assign_at_runtime,
    stable_id,
)
from .history import (
    FreightHistory,
    InboundRecord,
    MalformedHistory,
    TenantSetup,
    UnparseableRecord,
    acquisition_for,
    parse_record,
    to_utc,
    utc_datetime,
)
from .model import entity_id, entity_ref
from .projection import LOAD, FreightProjection, Projector, split_ref

#: The most times intake re-projects after materializing intents. Each pass can only add rows the
#: machines accept; two passes settle every history in the corpus, and the bound is a guard against a
#: detector that never stops asking.
MAX_SETTLE_PASSES = 5

CREATED_LOAD = "CREATED_LOAD"
BOUND = "BOUND"
AMBIGUOUS_BINDING = "AMBIGUOUS"
UNBOUND = "UNBOUND"
DUPLICATE = "DUPLICATE"
UNPARSEABLE = "UNPARSEABLE"
REFUSED = "REFUSED"
CONTROL = "CONTROL"


class HistoryClock:
    """Time as the freight history tells it. The foundational machines stamp every row from this, so
    a deadline is evaluated against when a record ARRIVED rather than when a test happened to run."""

    def __init__(self) -> None:
        self._now: datetime | None = None

    def set(self, instant_utc: str) -> None:
        moment = utc_datetime(instant_utc)
        if self._now is not None and moment < self._now:
            raise MalformedHistory(
                f"a record arrived at {instant_utc}, before the previous one for this brokerage. "
                f"Records are processed in ARRIVAL order; a late-arriving record has an earlier "
                f"`as_of`, not an earlier `received_at`.")
        self._now = moment

    def __call__(self) -> datetime:
        if self._now is None:
            raise MalformedHistory("the history clock has not been set: no record has arrived yet")
        return self._now


@dataclass
class RecordOutcome:
    """What intake did with one record. The corpus asserts its labeled expectations against this."""

    label: str
    disposition: str
    observation_id: str | None = None
    load_id: str | None = None
    candidate_load_ids: tuple[str, ...] = ()
    ambiguity: str | None = None
    detail: str = ""


@dataclass
class IntakeStats:
    records_received: int = 0
    observations_created: int = 0
    duplicates_suppressed: int = 0
    unparseable: int = 0
    refused: int = 0
    loads_created: int = 0
    mappings_recorded: int = 0
    exact_bindings: int = 0
    ambiguous_bindings: int = 0
    unresolved_bindings: int = 0
    late_bindings: int = 0
    human_bindings: int = 0
    conflicts_raised: int = 0
    expectations_raised: int = 0
    expectations_discharged: int = 0
    exceptions_raised: int = 0
    settle_passes: int = 0
    writes_after_settle: int = 0

    def as_document(self) -> dict[str, int]:
        return dict(self.__dict__)


@dataclass
class _Resolution:
    """The candidate loads a record's references resolve to, and how they were reached."""

    exact: list[tuple[str, str]] = field(default_factory=list)   # (entity_ref, mapping_id)
    weak: list[str] = field(default_factory=list)
    model: list[tuple[str, str]] = field(default_factory=list)
    ambiguity: str | None = None


class FreightIntake:
    """Intake for ONE brokerage. It owns the foundation, the mapping store and the projector for
    that tenant, all bound at construction."""

    def __init__(self, conn: sqlite3.Connection, setup: TenantSetup, *,
                 candidate_generator: CandidateGenerator | None = None,
                 clock: HistoryClock | None = None) -> None:
        self.setup = setup
        self.clock = clock or HistoryClock()
        self.foundation = FreightFoundation(conn, tenant=setup.tenant, clock=self.clock)
        self.mappings = ExternalEntityMappings(conn, tenant=setup.tenant, clock=self.clock)
        self.projector = Projector(self.foundation, self.mappings, setup)
        self.candidates: CandidateGenerator = candidate_generator or NoCandidates()
        self.stats = IntakeStats()
        self._provisioned = False

    @property
    def tenant(self) -> str:
        return self.setup.tenant

    # ------------------------------------------------------------------ entry points

    def run(self, history: FreightHistory) -> list[RecordOutcome]:
        if history.tenant != self.tenant:
            raise MalformedHistory(
                f"history {history.history_id} belongs to {history.tenant!r} and was handed to the "
                f"intake of {self.tenant!r}. A brokerage's intake reads only its own freight.")
        return [self.ingest(record) for record in history.records]

    def projection(self) -> FreightProjection:
        """The canonical freight picture, rebuilt from durable records. A pure read."""
        return self.projector.project()

    def ingest(self, record: InboundRecord) -> RecordOutcome:
        self.stats.records_received += 1
        received_at = to_utc(record.received_at, what="received_at")
        self.clock.set(received_at)
        self._provision()
        # Deadlines that passed BEFORE this record arrived are evaluated first, so a late arrival is
        # recorded as late rather than quietly keeping a deadline it missed.
        self.foundation.evaluate_due(owner_id=self.setup.load_owner)

        if record.kind == "clock":
            self._settle()
            return RecordOutcome(record.label, CONTROL, detail="time passed; deadlines evaluated")
        if record.kind == "channel_coverage":
            payload = record.payload
            self.foundation.record_coverage(
                coverage_id=stable_id("cov", self.tenant, record.source_system,
                                      record.external_id),
                channel=str(payload["channel"]),
                window_start=to_utc(payload["window_start"], what="coverage window"),
                window_end=to_utc(payload["window_end"], what="coverage window"),
                health=str(payload["health"]), probe_source=record.source_system)
            return RecordOutcome(record.label, CONTROL, detail="channel coverage recorded")

        try:
            as_of = to_utc(record.as_of, what="as_of")
            observed = self.foundation.observe(
                source_system=record.source_system, external_id=record.external_id,
                content=record.content(), as_of=as_of, received_at=received_at,
                acquisition=acquisition_for(record.channel, record.kind))
        except ProvenanceFromContent as exc:
            # Content that names its own provenance is a counterparty trying to say how much it can
            # bear. It is not stored as a fact and it is not silently dropped: a human is told.
            self.stats.refused += 1
            source = f"{record.source_system}|{record.external_id}"
            self._raise_exception(RaiseException(
                exception_id=stable_id("exc", self.tenant, source, "content_provenance"),
                type="inbound_content_claimed_provenance", severity="SEV1", source_ref=source,
                source_kind="pending_reference", owner_id=self.setup.intake_owner,
                entity_ref="", summary=f"An inbound record tried to declare its own provenance "
                                       f"and was refused: {exc}",
                specific_question="Who sent this, and why does it assert its own authority?"))
            return RecordOutcome(record.label, REFUSED, detail="content supplied its own provenance")

        if observed.duplicate:
            self.stats.duplicates_suppressed += 1
            return RecordOutcome(record.label, DUPLICATE, observation_id=observed.observation_id,
                                 detail="identical content already observed; no downstream work")
        self.stats.observations_created += 1
        observation_id = observed.observation_id

        try:
            parsed = parse_record(record)
        except UnparseableRecord as exc:
            self.stats.unparseable += 1
            self.foundation.mark_unparseable(observation_id, owner_id=self.setup.intake_owner,
                                             reason=str(exc))
            return RecordOutcome(record.label, UNPARSEABLE, observation_id=observation_id,
                                 detail=str(exc))
        self.foundation.mark_parsed(observation_id, parsed)

        if record.kind == "document":
            self._retain_document(observation_id, parsed["payload"])
        if record.kind == "tms_load":
            outcome = self._intake_tms_load(record, observation_id, parsed)
        elif record.kind == "human_assertion":
            outcome = self._intake_human_assertion(record, observation_id, parsed)
        else:
            outcome = self._bind(record.label, observation_id, record.references())
        self._retry_unbound()
        self._settle()
        return outcome

    # ------------------------------------------------------------------ setup

    def _provision(self) -> None:
        if self._provisioned:
            return
        for human in self.setup.humans:
            self.foundation.provision_human(
                human_id=human["human_id"], display_name=human["display_name"],
                authority_role=human.get("authority_role", "AUTHORIZED_HUMAN"),
                recorded_by=self.setup.recorded_by)
        self._provisioned = True

    # ------------------------------------------------------------------ documents

    def _retain_document(self, observation_id: str, payload: dict[str, Any]) -> None:
        """Retain the artifact content-addressed and point its extracted values at a span. Done at
        intake whether or not the document binds: the bytes are evidence either way."""
        evidence_id = self.foundation.retain_document(
            observation_id=observation_id, content=payload["content"].encode("utf-8"),
            media_type=payload["media_type"])
        self.foundation.attach_span(evidence_id, locator="page:1",
                                    extracted_text=payload["doc_type"])
        if not payload["legible"]:
            self.foundation.mark_illegible(evidence_id)

    # ------------------------------------------------------------------ reference resolution

    def _resolve(self, references: Iterable[ExternalReference]) -> _Resolution:
        """Resolve every reference exactly and INTERSECT: the load must be consistent with all of
        them. References this tenant has never seen constrain nothing."""
        resolution = _Resolution()
        candidate_sets: list[dict[str, str]] = []
        for reference in references:
            resolved = self.mappings.resolve(reference, entity_type=LOAD)
            if resolved.status in (EXACT, AMBIGUOUS):
                candidate_sets.append({m.entity_ref: m.mapping_id for m in resolved.active})
                if resolved.status == AMBIGUOUS:
                    resolution.ambiguity = "one_reference_names_several_loads"
            elif resolved.status == RETIRED_ONLY:
                resolution.weak.extend(m.entity_ref for m in resolved.retired)
            elif resolved.status == UNMAPPED:
                resolution.model.extend(
                    (c.entity_ref, c.source)
                    for c in self.candidates.candidates(reference, tenant=self.tenant))
        if not candidate_sets:
            return resolution
        common = set(candidate_sets[0])
        for candidates in candidate_sets[1:]:
            common &= set(candidates)
        if common:
            merged = {ref: mid for candidates in candidate_sets for ref, mid in candidates.items()}
            resolution.exact = [(ref, merged[ref]) for ref in sorted(common)]
            if len(common) == 1:
                resolution.ambiguity = None
        else:
            # The references name DIFFERENT loads. Every one of them is offered to the linker, which
            # reports the disagreement; nothing is bound.
            merged = {ref: mid for candidates in candidate_sets for ref, mid in candidates.items()}
            resolution.exact = sorted(merged.items())
            resolution.ambiguity = "references_name_different_loads"
        return resolution

    def _bind(self, label: str, observation_id: str,
              references: Iterable[ExternalReference], *, late: bool = False) -> RecordOutcome:
        resolution = self._resolve(references)
        decision = self.foundation.decide_link(
            observation_id, exact=resolution.exact, weak=resolution.weak,
            model_candidates=resolution.model)
        if decision.status == "CONFIRMED" and decision.entity_ref is not None:
            self.foundation.bind_exact(observation_id, decision.entity_ref)
            self.stats.exact_bindings += 1
            if late:
                self.stats.late_bindings += 1
            return RecordOutcome(label, BOUND, observation_id=observation_id,
                                 load_id=split_ref(decision.entity_ref)[1])
        if decision.candidates:
            reason = decision.reason or "multiple"
            self.foundation.bind_ambiguous(observation_id, candidates=decision.candidates,
                                           owner_id=self.setup.intake_owner, reason=reason)
            if not late:
                self.stats.ambiguous_bindings += 1
            return RecordOutcome(
                label, AMBIGUOUS_BINDING, observation_id=observation_id,
                candidate_load_ids=tuple(split_ref(c)[1] for c in decision.candidates),
                ambiguity=resolution.ambiguity or reason)
        self.foundation.leave_unbound(observation_id, owner_id=self.setup.intake_owner)
        if not late:
            self.stats.unresolved_bindings += 1
        return RecordOutcome(label, UNBOUND, observation_id=observation_id,
                             detail="no reference resolved to a load this brokerage knows")

    def _retry_unbound(self) -> None:
        """A mapping may have just made an earlier record's reference resolvable — the TMS row that
        arrived after the POD it explains. Every UNBOUND record is re-resolved; one that now resolves
        exactly binds (OB-4), and nothing else changes."""
        for observation in self.foundation.observations():
            if observation["state"] != "UNBOUND" or observation["parsed"] is None:
                continue
            parsed = observation["parsed"]
            if parsed["kind"] in ("tms_load", "human_assertion"):
                continue
            references = [ExternalReference(r.get("system"), r["kind"], r["value"])
                          for r in parsed["refs"]]
            resolution = self._resolve(references)
            decision = self.foundation.decide_link(
                observation["observation_id"], exact=resolution.exact, weak=resolution.weak,
                model_candidates=resolution.model)
            if decision.status == "CONFIRMED" and decision.entity_ref is not None:
                self.foundation.bind_exact(observation["observation_id"], decision.entity_ref)
                self.stats.exact_bindings += 1
                self.stats.late_bindings += 1

    # ------------------------------------------------------------------ the system of record

    def _record_mapping(self, *, entity_type: str, ident: str, reference: ExternalReference,
                        provenance: str, observation_id: str) -> None:
        _, created = self.mappings.record(
            entity_type=entity_type, entity_id=ident, reference=reference,
            provenance_class=provenance, source_observation_id=observation_id)
        if created:
            self.stats.mappings_recorded += 1

    def _ensure_party(self, *, entity_type: str, reference: ExternalReference, provenance: str,
                      observation_id: str) -> str:
        resolved = self.mappings.resolve(reference, entity_type=entity_type)
        if resolved.active:
            return resolved.active[0].neyma_entity_id
        ident = entity_id(self.tenant, entity_type, observation_id, reference.value)
        self._record_mapping(entity_type=entity_type, ident=ident, reference=reference,
                             provenance=provenance, observation_id=observation_id)
        return ident

    def _intake_tms_load(self, record: InboundRecord, observation_id: str,
                         parsed: dict[str, Any]) -> RecordOutcome:
        payload = parsed["payload"]
        system = record.source_system
        provenance = assign_at_runtime(acquisition_for(record.channel, record.kind)).value
        load_reference = ExternalReference(system, "load_ref", payload["load_ref"])
        resolved = self.mappings.resolve(load_reference, entity_type=LOAD)
        created = False

        if resolved.status == EXACT:
            load_id = resolved.active[0].neyma_entity_id
        elif resolved.status == UNMAPPED:
            previous = payload.get("previous_load_ref")
            prior = (self.mappings.resolve(ExternalReference(system, "load_ref", str(previous)),
                                           entity_type=LOAD) if previous else None)
            if prior is not None and prior.status == EXACT:
                # The TMS RENUMBERED the load. The old number was true when made: it is retired as
                # SUPERSEDED and retained, and the new number names the same canonical load.
                load_id = prior.active[0].neyma_entity_id
                self.mappings.supersede(
                    prior.active[0].mapping_id, new_reference=load_reference,
                    provenance_class=provenance, source_observation_id=observation_id,
                    reason=f"the TMS renumbered {previous} to {payload['load_ref']}")
                self.stats.mappings_recorded += 1
            else:
                load_id = entity_id(self.tenant, LOAD, observation_id)
                self._record_mapping(entity_type=LOAD, ident=load_id, reference=load_reference,
                                     provenance=provenance, observation_id=observation_id)
                self.stats.loads_created += 1
                created = True
        else:
            # The load number names several loads, or only a retired mapping: a TMS row is not
            # allowed to pick. It is held for a human like any other record.
            return self._bind(record.label, observation_id, [load_reference])

        for reference in payload["references"]:
            target = str(reference.get("entity") or LOAD)
            external = ExternalReference(reference.get("system"), reference["kind"],
                                         reference["value"])
            self._record_mapping(entity_type=LOAD, ident=load_id, reference=external,
                                 provenance=provenance, observation_id=observation_id)
            if target.startswith("carrier_movement:"):
                # One outside row, two canonical entities: the PRO names the movement AND the load it
                # belongs to. Two mappings, neither collapsed into the other.
                movement_id = entity_id(self.tenant, "carrier_movement", load_id,
                                        target.split(":", 1)[1])
                self._record_mapping(entity_type="carrier_movement", ident=movement_id,
                                     reference=external, provenance=provenance,
                                     observation_id=observation_id)

        order = payload.get("order") or {}
        if order.get("tms_order_id"):
            self._ensure_party(
                entity_type="customer_order", provenance=provenance, observation_id=observation_id,
                reference=ExternalReference(system, "order_id", str(order["tms_order_id"])))
        customer = payload.get("customer") or {}
        if customer.get("tms_customer_id"):
            self._ensure_party(
                entity_type="customer", provenance=provenance, observation_id=observation_id,
                reference=ExternalReference(system, "customer_id", str(customer["tms_customer_id"])))
        for movement in payload.get("movements", ()):
            carrier = movement.get("carrier") or {}
            if carrier.get("mc_number"):
                self._ensure_party(
                    entity_type="carrier", provenance=provenance, observation_id=observation_id,
                    reference=ExternalReference("fmcsa", "mc_number", str(carrier["mc_number"])))

        load_ref = entity_ref(LOAD, load_id)
        self.foundation.bind_exact(observation_id, load_ref)
        self.stats.exact_bindings += 1
        # Every unit of work has one accountable human, from the moment the load exists.
        self.foundation.ensure_work_item(
            work_item_id=stable_id("wi", self.tenant, load_id), type="brokerage_load_operations",
            owner_id=self.setup.load_owner, entity_ref=load_ref)
        return RecordOutcome(record.label, CREATED_LOAD if created else BOUND,
                             observation_id=observation_id, load_id=load_id)

    # ------------------------------------------------------------------ authenticated human acts

    def _intake_human_assertion(self, record: InboundRecord, observation_id: str,
                                parsed: dict[str, Any]) -> RecordOutcome:
        payload = parsed["payload"]
        human_id = payload["human_id"]
        if not self.foundation.is_active_human(human_id):
            # An "authenticated human act" by nobody this brokerage has recorded. It asserts nothing.
            self.stats.refused += 1
            self.foundation.leave_unbound(observation_id, owner_id=self.setup.intake_owner)
            self._raise_exception(RaiseException(
                exception_id=stable_id("exc", self.tenant, observation_id, "unauthenticated"),
                type="unauthenticated_human_assertion", severity="SEV1",
                source_ref=observation_id, source_kind="observation",
                owner_id=self.setup.intake_owner, entity_ref="",
                summary=f"An assertion was made in the name of {human_id!r}, who is not a "
                        f"recorded active human of this brokerage. It was not applied.",
                specific_question="Who made this assertion, and through what session?"))
            return RecordOutcome(record.label, REFUSED, observation_id=observation_id,
                                 detail="the asserting human is not a recorded active human")

        resolution = self._resolve(record.references())
        decision = self.foundation.decide_link(observation_id, exact=resolution.exact,
                                               weak=resolution.weak)
        if decision.status != "CONFIRMED" or decision.entity_ref is None:
            # A human act that does not name exactly one load is held, not guessed at.
            return self._bind(record.label, observation_id, record.references())
        load_ref = decision.entity_ref
        decision_ref = f"observation:{observation_id}"
        self.foundation.bind_by_human(observation_id, entity_ref=load_ref, human_id=human_id,
                                      decision_ref=decision_ref)
        self.stats.human_bindings += 1

        act = payload["act"]
        detail = act
        if act in ("bind_observation", "correct_binding"):
            target = self.foundation.observation_by_external(
                payload["target"]["source_system"], payload["target"]["external_id"])
            if target is None:
                self._raise_exception(RaiseException(
                    exception_id=stable_id("exc", self.tenant, observation_id, "no_target"),
                    type="assertion_target_missing", severity="SEV2", source_ref=observation_id,
                    source_kind="observation", owner_id=self.setup.intake_owner,
                    entity_ref=load_ref,
                    summary="A human bound or corrected a record that Neyma has never received.",
                    specific_question="Which inbound record did you mean?"))
                detail = "target record not found"
            else:
                # IB-7 when the record was CONFIRMED elsewhere (the prior claim is retained as
                # CORRECTED), IB-2h when it was never bound.
                dependents = [e["expectation_id"] for e in self.foundation.expectations()
                              if e["discharge_observation_id"] == target["observation_id"]]
                self.foundation.correct_binding(
                    target["observation_id"], new_entity_ref=load_ref, human_id=human_id,
                    decision_ref=decision_ref, dependent_refs=dependents)
                self.stats.human_bindings += 1
        elif act == "correct_reference":
            wrong = ExternalReference(payload["wrong_reference"]["system"],
                                      payload["wrong_reference"]["kind"],
                                      payload["wrong_reference"]["value"])
            right_block = payload["right_reference"]
            right = (ExternalReference(right_block["system"], right_block["kind"],
                                       right_block["value"]) if right_block else None)
            load_id = split_ref(load_ref)[1]
            resolved = self.mappings.resolve(wrong, entity_type=LOAD)
            wrong_rows = [m for m in resolved.active if m.neyma_entity_id != load_id]
            for mapping in wrong_rows:
                # The reference was mapped to the WRONG load: that row is retained as CORRECTED and
                # a new OWNER_ASSERTED row puts the reference on the load the human named.
                self.mappings.correct(
                    mapping.mapping_id, new_reference=right or wrong, new_entity_type=LOAD,
                    new_entity_id=load_id, decision_ref=decision_ref, decision_human_id=human_id,
                    source_observation_id=observation_id,
                    reason=payload["note"] or "corrected by a human")
                self.stats.mappings_recorded += 1
            if not wrong_rows:
                own = [m for m in resolved.active if m.neyma_entity_id == load_id]
                for mapping in own:
                    # The reference is on the right load but is the wrong STRING.
                    self.mappings.correct(
                        mapping.mapping_id, new_reference=right, decision_ref=decision_ref,
                        decision_human_id=human_id, source_observation_id=observation_id,
                        reason=payload["note"] or "corrected by a human")
                    self.stats.mappings_recorded += 1
        return RecordOutcome(record.label, BOUND, observation_id=observation_id,
                             load_id=split_ref(load_ref)[1], detail=detail)

    # ------------------------------------------------------------------ detect and materialize

    def _settle(self) -> None:
        """Project, detect, hand the intents to the machines, and repeat until the picture owes
        nothing new. The final pass must write nothing: that is what makes the projection a fixed
        point, and replaying it inert."""
        for _ in range(MAX_SETTLE_PASSES):
            self.stats.settle_passes += 1
            projection = self.projector.project()
            wrote = False
            for view in projection.loads.values():
                for intent in detect(view, self.setup):
                    wrote = self._materialize(intent) or wrote
            if not wrote:
                return
        self.stats.writes_after_settle += 1

    def _materialize(self, intent: Intent) -> bool:
        if isinstance(intent, RaiseConflict):
            wrote = self.foundation.raise_conflict(
                conflict_id=intent.conflict_id, kind=intent.kind, entity_ref=intent.entity_ref,
                field=intent.field, parties=intent.parties, owner_id=intent.owner_id)
            self.stats.conflicts_raised += int(wrote)
            return wrote
        if isinstance(intent, RaiseExpectation):
            wrote = self.foundation.raise_expectation(
                expectation_id=intent.expectation_id, subject_ref=intent.subject_ref,
                expected_type=intent.expected_type, expected_source=intent.expected_source,
                owner_id=intent.owner_id, originating_timezone=intent.originating_timezone,
                deadline_utc=intent.deadline_utc, appointment_local=intent.appointment_local)
            self.stats.expectations_raised += int(wrote)
            if wrote:
                # A promise whose deadline had already passed when it arrived is evaluated now.
                self.foundation.evaluate_due(owner_id=self.setup.load_owner)
            return wrote
        if isinstance(intent, DischargeExpectation):
            bound = {o["observation_id"]: o for o in self.foundation.observations()}
            expectation = next((e for e in self.foundation.expectations()
                                if e["expectation_id"] == intent.expectation_id), None)
            if expectation is None:
                return False
            for observation_id in intent.observation_ids:
                row = bound.get(observation_id)
                # M8 discharges only on an observation M5 holds BOUND to this very subject.
                if row is None or row["state"] != "BOUND" \
                        or row["bound_entity_ref"] != expectation["subject_ref"]:
                    continue
                if self.foundation.discharge(intent.expectation_id, observation_id=observation_id):
                    self.stats.expectations_discharged += 1
                    return True
            return False
        return self._raise_exception(intent)

    def _raise_exception(self, intent: RaiseException) -> bool:
        wrote = self.foundation.raise_exception(
            exception_id=intent.exception_id, type=intent.type, severity=intent.severity,
            source_ref=intent.source_ref, source_kind=intent.source_kind,
            owner_id=intent.owner_id, summary=intent.summary,
            entity_ref=intent.entity_ref or None, specific_question=intent.specific_question)
        self.stats.exceptions_raised += int(wrote)
        return wrote


def intake_for(conn: sqlite3.Connection, setup: TenantSetup, *,
               clock_factory: Callable[[], HistoryClock] = HistoryClock) -> FreightIntake:
    return FreightIntake(conn, setup, clock=clock_factory())
