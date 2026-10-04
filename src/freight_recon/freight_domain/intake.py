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

### NO EFFECT AND NO ADAPTER. Intake reads records it is handed and writes canonical rows. It sends
nothing and reaches no outside system of its own.

### A MODEL ONLY THROUGH THE INTERPRETER, AND ONLY WHEN ROUTED. Intake is handed an optional
`FreightInterpreter`. With none (the deterministic harness) it asks no model anything and a message
asserts only what its record already structured. With one, a record whose content is unstructured
language is READ once, at parse; the reading is grounded and normalized by `interpretation.py` and
stored on the Observation, so the projection and every replay read the stored reading and never
call a model again. A record nothing exact could place may be given model-PROPOSED candidate loads,
which the linker routes to a human and never binds.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..inference.contracts import CandidateOption
from .detectors import (
    AmendExpectation,
    CancelExpectation,
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
    ExternalEntityMappings,
    ExternalReference,
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
from .interpretation import FAILED, READ, ContentReading, FreightInterpreter
from .model import entity_id, entity_ref
from .projection import (
    LOAD,
    FreightProjection,
    LoadView,
    Projector,
    exception_key,
    split_ref,
)

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

#: How a model's stated support for a candidate orders the human's queue (M6 `confidence`, whose one
#: legitimate use is sorting that queue). It is an ordering key. No guard anywhere reads it.
CANDIDATE_QUEUE_ORDER: dict[str, float] = {"CLEAR": 0.9, "PARTIAL": 0.6, "WEAK": 0.3}


class ModelInferenceConfirmed(RuntimeError):
    """The linker returned something other than AMBIGUOUS for a model-proposed candidate. That is a
    broken invariant, not an input problem: intake stops rather than bind on it."""


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
    conflicts_resolved: int = 0
    expectations_raised: int = 0
    expectations_discharged: int = 0
    expectations_amended: int = 0
    expectations_cancelled: int = 0
    exceptions_raised: int = 0
    exceptions_resolved: int = 0
    settle_passes: int = 0
    writes_after_settle: int = 0
    model_readings: int = 0
    model_reading_failures: int = 0
    model_candidate_requests: int = 0
    model_candidates_refused: int = 0
    model_inferred_ambiguities: int = 0

    def as_document(self) -> dict[str, int]:
        return dict(self.__dict__)


@dataclass
class _Resolution:
    """The candidate loads a record's references resolve to, and how they were reached."""

    exact: list[tuple[str, str]] = field(default_factory=list)   # (entity_ref, mapping_id)
    weak: list[str] = field(default_factory=list)
    ambiguity: str | None = None


class FreightIntake:
    """Intake for ONE brokerage. It owns the foundation, the mapping store and the projector for
    that tenant, all bound at construction."""

    def __init__(self, conn: sqlite3.Connection, setup: TenantSetup, *,
                 interpreter: FreightInterpreter | None = None,
                 clock: HistoryClock | None = None) -> None:
        self.setup = setup
        self.clock = clock or HistoryClock()
        self.foundation = FreightFoundation(conn, tenant=setup.tenant, clock=self.clock)
        self.mappings = ExternalEntityMappings(conn, tenant=setup.tenant, clock=self.clock)
        self.projector = Projector(self.foundation, self.mappings, setup)
        self.interpreter = interpreter
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
        # A record that is unstructured language is READ here, once, and the grounded reading is
        # stored with the parse. Everything after this line is the same whether a model, a fixture
        # or nobody supplied the structure.
        reading = self._read_content(record, parsed, observation_id, as_of)
        self.foundation.mark_parsed(observation_id, parsed)

        if record.kind == "document":
            self._retain_document(observation_id, parsed["payload"],
                                  spans=reading.spans if reading is not None else ())
        if record.kind == "tms_load":
            outcome = self._intake_tms_load(record, observation_id, parsed)
        elif record.kind == "human_assertion":
            outcome = self._intake_human_assertion(record, observation_id, parsed)
        else:
            outcome = self._bind(record.label, observation_id, record.references(), record=record)
        if reading is not None and reading.status == FAILED:
            self._reading_failed(observation_id, outcome, record, reading)
        self._correlate(observation_id, outcome.load_id)
        self._retry_unbound()
        self._settle()
        return outcome

    # ------------------------------------------------------------------ model interpretation

    def _read_content(self, record: InboundRecord, parsed: dict[str, Any], observation_id: str,
                      as_of: str) -> ContentReading | None:
        """Hand the record to the interpreter, which decides whether a model is needed at all. A
        usable reading becomes the record's `asserts` or `extracted` block; a failed one leaves the
        record asserting nothing."""
        if self.interpreter is None:
            return None
        reading = self.interpreter.read(record, parsed, observation_id=observation_id,
                                        as_of_utc=as_of, interpreted_at=self.foundation.now())
        if reading.record is not None:
            parsed["interpretation"] = reading.record
        if reading.status == READ:
            self.stats.model_readings += 1
            if reading.asserts is not None:
                parsed["payload"]["asserts"] = reading.asserts
            if reading.extracted is not None:
                parsed["payload"]["extracted"] = reading.extracted
        elif reading.status == FAILED:
            self.stats.model_reading_failures += 1
        return reading

    def _reading_failed(self, observation_id: str, outcome: RecordOutcome, record: InboundRecord,
                        reading: ContentReading) -> None:
        """The record's language could not be read into supported structure. It is still observed,
        parsed and bound by its exact references — and a named human is told to read it."""
        what = "document" if record.kind == "document" else "message"
        self._raise_exception(RaiseException(
            exception_id=stable_id("exc", self.tenant, observation_id, "interpretation"),
            type="interpretation_unavailable", severity="SEV2", source_ref=observation_id,
            source_kind="observation", owner_id=self.setup.intake_owner,
            entity_ref=entity_ref(LOAD, outcome.load_id) if outcome.load_id else "",
            summary=(f"An inbound {what} could not be read automatically "
                     f"({(reading.failure or 'unknown').split(':', 1)[0]}). Nothing was "
                     f"extracted from it and nothing was assumed."),
            specific_question=f"What does this {what} say that the load needs?"))

    def _correlate(self, observation_id: str, load_id: str | None) -> None:
        if self.interpreter is not None and load_id:
            self.interpreter.ledger.correlate(observation_id, entity_ref(LOAD, load_id))

    def _candidate_options(self) -> tuple[CandidateOption, ...]:
        """This brokerage's loads, newest first, described for a model. The ids are this tenant's
        own canonical load refs — there is no other tenant's load in this intake to offer."""
        views = sorted(self.projector.project().loads.values(),
                       key=lambda v: (v.observations[0]["received_at"] if v.observations else "",
                                      v.load_id), reverse=True)
        return tuple(CandidateOption(candidate_id=v.ref, summary=describe_load(v)) for v in views)

    def _propose_candidates(self, label: str, observation_id: str, record: InboundRecord,
                            *, bound_exactly: bool,
                            deterministic_candidates: int) -> RecordOutcome | None:
        """Ask for model-proposed candidate loads — only reached for a message or document, and the
        interpreter only calls a model when exact resolution produced nothing. Returns the held
        outcome when candidates were recorded, else None."""
        if self.interpreter is None or record.kind not in ("message", "document"):
            return None
        payload = record.payload
        text = (f"{payload.get('subject', '')}\n{payload.get('body', '')}".strip()
                if record.kind == "message" else str(payload.get("content", "")))
        needs_options = not bound_exactly and not deterministic_candidates
        reading = self.interpreter.propose(
            observation_id=observation_id, kind=record.kind, text=text,
            options=self._candidate_options() if needs_options else (),
            bound_exactly=bound_exactly, deterministic_candidates=deterministic_candidates,
            at=self.foundation.now())
        if not reading.route.model_needed:
            return None
        self.stats.model_candidate_requests += 1
        self.stats.model_candidates_refused += len(reading.refused)
        if reading.status != READ or not reading.candidates:
            return None
        source = f"model:{self.interpreter.gateway.provider}/{self.interpreter.gateway.model}"
        proposed = [(c["candidate_id"], source) for c in reading.candidates]
        # The linker decides, not intake: a model inference is AMBIGUOUS at any stated support.
        decision = self.foundation.decide_link(observation_id, exact=(), weak=(),
                                               model_candidates=proposed)
        if decision.status == "CONFIRMED" or not decision.candidates:
            raise ModelInferenceConfirmed(
                "the linker did not route a model-proposed candidate to a human. A model "
                "inference never confirms a binding (GR-8).")
        self.foundation.bind_model_candidates(
            observation_id, owner_id=self.setup.intake_owner,
            candidates=[(c["candidate_id"], CANDIDATE_QUEUE_ORDER[c["support"]])
                        for c in reading.candidates])
        self.stats.model_inferred_ambiguities += 1
        self.stats.ambiguous_bindings += 1
        return RecordOutcome(
            label, AMBIGUOUS_BINDING, observation_id=observation_id,
            candidate_load_ids=tuple(split_ref(c)[1] for c in decision.candidates),
            ambiguity=decision.reason, detail="candidate loads proposed by a model; none bound")

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

    def _retain_document(self, observation_id: str, payload: dict[str, Any], *,
                         spans: Any = ()) -> None:
        """Retain the artifact content-addressed and point its extracted values at a span. Done at
        intake whether or not the document binds: the bytes are evidence either way."""
        evidence_id = self.foundation.retain_document(
            observation_id=observation_id, content=payload["content"].encode("utf-8"),
            media_type=payload["media_type"])
        self.foundation.attach_span(evidence_id, locator="page:1",
                                    extracted_text=payload["doc_type"])
        if spans:
            self.foundation.attach_field_spans(evidence_id, spans)
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
            elif resolved.status != UNMAPPED:
                raise MalformedHistory(f"unknown mapping resolution status {resolved.status!r}")
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
              references: Iterable[ExternalReference], *, late: bool = False,
              record: InboundRecord | None = None) -> RecordOutcome:
        """DETERMINISTIC FIRST. Exact, tenant-scoped resolution runs and its answer stands. Only when
        it produced nothing at all is a model asked for candidates, and those go to a human."""
        resolution = self._resolve(references)
        decision = self.foundation.decide_link(
            observation_id, exact=resolution.exact, weak=resolution.weak)
        confirmed = decision.status == "CONFIRMED" and decision.entity_ref is not None
        if record is not None:
            held = self._propose_candidates(
                label, observation_id, record, bound_exactly=confirmed,
                deterministic_candidates=len(decision.candidates))
            if held is not None:
                return held
        if confirmed and decision.entity_ref is not None:
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
                observation["observation_id"], exact=resolution.exact, weak=resolution.weak)
            if decision.status == "CONFIRMED" and decision.entity_ref is not None:
                self.foundation.bind_exact(observation["observation_id"], decision.entity_ref)
                self.stats.exact_bindings += 1
                self.stats.late_bindings += 1
                self._correlate(observation["observation_id"],
                                split_ref(decision.entity_ref)[1])

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
        elif act == "attribute_carrier_invoice":
            detail = self._attribute_invoice(observation_id, load_ref, payload)
        elif act == "confirm_appointment":
            detail = self._confirm_appointment(observation_id, load_ref, payload,
                                               human_id=human_id, decision_ref=decision_ref)
        elif act == "resolve_exception":
            detail = self._resolve_exception(observation_id, load_ref, payload, human_id=human_id)
        return RecordOutcome(record.label, BOUND, observation_id=observation_id,
                             load_id=split_ref(load_ref)[1], detail=detail)

    def _resolve_exception(self, observation_id: str, load_ref: str, payload: dict[str, Any], *,
                           human_id: str) -> str:
        """A recorded human closes ONE Exception, by name, on the load her act names. It is the only
        way this spine closes an Exception, and M9 does the closing: the row moves to RESOLVED with
        her as the decider and is retained.

        The Exception must be OPEN and attached to THAT load, in this brokerage: a key that is open
        on another load, or on nothing, closes nothing and is put back to a named human. Resolving
        an Exception decides only that: an invoice that is still unplaced is still unplaced."""
        view = self.projector.project().loads[split_ref(load_ref)[1]]
        named = [x for x in view.open_exceptions() if exception_key(x) == payload["exception"]]
        if len(named) == 1 and self.foundation.resolve_exception_by_human(
                named[0]["exception_id"], human_id=human_id, correlation_id=load_ref):
            self.stats.exceptions_resolved += 1
            return "resolve_exception"
        if any(exception_key(x) == payload["exception"] for x in view.exceptions):
            # It is this load's, and a human already closed it: saying so again changes nothing
            # and is nobody's new question.
            return "already resolved"
        self._raise_exception(RaiseException(
            exception_id=stable_id("exc", self.tenant, observation_id, "no_exception"),
            type="assertion_target_missing", severity="SEV2", source_ref=observation_id,
            source_kind="observation", owner_id=self.setup.intake_owner, entity_ref=load_ref,
            summary=f"A human resolved Exception {payload['exception']!r}, and this load has no "
                    f"open Exception by that name. Nothing was closed.",
            specific_question="Which Exception, on which load, did you mean to close?"))
        return "resolution could not be applied"

    def _attribute_invoice(self, observation_id: str, load_ref: str,
                           payload: dict[str, Any]) -> str:
        """A human placed an invoice on a movement. The act is already a bound, OWNER_ASSERTED
        Observation and the projection applies it; all intake does is tell a named human when what
        she said cannot be applied — an invoice Neyma never received, or a movement this load does
        not have. It is never silently ignored."""
        target = self.foundation.observation_by_external(
            payload["target"]["source_system"], payload["target"]["external_id"])
        view = self.projector.project().loads[split_ref(load_ref)[1]]
        placed = target is not None and any(
            target["observation_id"] in (p.origin_observation_id, *p.duplicate_observation_ids)
            for p in view.payables.values())
        if placed and payload["movement_key"] in view.movements:
            return "attribute_carrier_invoice"
        problem = ("names a movement this load does not have" if placed
                   else "names no carrier invoice Neyma holds on this load")
        self._raise_exception(RaiseException(
            exception_id=stable_id("exc", self.tenant, observation_id, "attribution_unusable"),
            type="invoice_attribution_unusable", severity="SEV2", source_ref=observation_id,
            source_kind="observation", owner_id=self.setup.intake_owner, entity_ref=load_ref,
            summary=f"A human attributed a carrier invoice to movement "
                    f"{payload['movement_key']!r}, and the attribution {problem}. Nothing was "
                    f"placed.",
            specific_question="Which invoice, and which movement of this load, did you mean?"))
        return "attribution could not be applied"

    def _confirm_appointment(self, observation_id: str, load_ref: str, payload: dict[str, Any], *,
                             human_id: str, decision_ref: str) -> str:
        """A human stated the appointment at a stop. If that window was in dispute, her act is the
        decision M7 was waiting for: the Conflict is resolved BY HER, citing this act, and every
        party's statement is retained."""
        view = self.projector.project().loads[split_ref(load_ref)[1]]
        appointment = view.appointments.get(payload["stop_key"])
        if appointment is None:
            self._raise_exception(RaiseException(
                exception_id=stable_id("exc", self.tenant, observation_id, "no_stop"),
                type="assertion_target_missing", severity="SEV2", source_ref=observation_id,
                source_kind="observation", owner_id=self.setup.intake_owner, entity_ref=load_ref,
                summary=f"A human confirmed an appointment at stop {payload['stop_key']!r}, which "
                        f"this load does not have. Nothing was recorded against a stop.",
                specific_question="Which stop of this load did you mean?"))
            return "stop not found"
        resolved = self.foundation.resolve_conflict_by_human(
            entity_ref=appointment.ref, field="window", human_id=human_id,
            decision_ref=decision_ref)
        if resolved is not None:
            self.stats.conflicts_resolved += 1
        return "confirm_appointment"

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
        if isinstance(intent, AmendExpectation):
            wrote = self.foundation.amend_deadline(intent.expectation_id,
                                                   deadline_utc=intent.deadline_utc)
            self.stats.expectations_amended += int(wrote)
            if wrote:
                # The moved deadline may itself already have passed.
                self.foundation.evaluate_due(owner_id=self.setup.load_owner)
            return wrote
        if isinstance(intent, CancelExpectation):
            wrote = self.foundation.cancel_expectation(intent.expectation_id,
                                                       reason=intent.reason)
            self.stats.expectations_cancelled += int(wrote)
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


def describe_load(view: LoadView) -> str:
    """One load, described for a model choosing between candidates: its outside names, parties,
    stops and reported status. Operational context only — no rate, charge or amount is included."""
    names = [f"{m.external_id} ({m.external_id_kind})" for m in view.mappings
             if m.state == "ACTIVE" and m.neyma_entity_type == LOAD]
    parts = ["references: " + ("; ".join(dict.fromkeys(names)) or "none")]
    if view.customer is not None and view.customer.value("legal_name"):
        parts.append(f"customer: {view.customer.value('legal_name')}")
    carriers = [str(c.value("legal_name")) for c in view.carriers.values()
                if c.value("legal_name")]
    if carriers:
        parts.append("carrier: " + "; ".join(carriers))
    drivers = [str(d.value("name")) for d in view.drivers.values() if d.value("name")]
    if drivers:
        parts.append("driver: " + "; ".join(drivers))
    stops = sorted(view.stops.values(), key=lambda s: (s.value("sequence") or 0, s.stop_key))
    if stops:
        parts.append("stops: " + "; ".join(
            f"{s.value('stop_type')} {s.value('facility_name')}" for s in stops))
    if view.load.value("reported_status"):
        parts.append(f"status: {view.load.value('reported_status')}")
    return " | ".join(parts)


def intake_for(conn: sqlite3.Connection, setup: TenantSetup, *,
               clock_factory: Callable[[], HistoryClock] = HistoryClock) -> FreightIntake:
    return FreightIntake(conn, setup, clock=clock_factory())
