"""P9 — the freight-domain projection: canonical entities as a deterministic fold over durable records.

### THE PROJECTION IS A PURE READ. `Projector.project()` reads Observations, Identity Binding Claims,
External Entity Mappings, Conflicts, Expectations, Exceptions, Work Items and Evidence for ONE tenant
and builds the canonical Brokerage Loads and everything that hangs off them. It writes nothing, calls
no machine transition and no adapter, and mints nothing. That is what makes replay structurally inert:
rebuilding the freight picture is re-running this function.

### WHICH LOAD AN ARTIFACT BELONGS TO IS M6's ANSWER, NOT M5's. The binding is read from the CONFIRMED
Identity Binding Claim for the observation. M5's `bound_entity_ref` column is not consulted: M5 has no
re-bind transition, so after a human corrects a binding (IB-7) that column still names the old load.

### WHAT A FACT CAN BEAR IS DERIVED FROM HOW ITS RECORD WAS ACQUIRED. The parse output records the
record's `Acquisition`, and every fact read from it takes its provenance from that. M5's
`provenance_class` column is not consulted either: OB-3 overwrites it with the BINDING's provenance, so
a driver's text bound by exact id reads `LINKER_INFERRED` on the row. A binding says where an artifact
belongs; it does not make what the artifact says any more true.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .entity_mapping import ExternalEntityMappings, ExternalReference
from .entity_mapping import Mapping as EntityMapping
from .financial import blocking_discrepancies, reconcile_movement
from .foundation import (
    Acquisition,
    EvidenceCondition,
    FreightFoundation,
    assign_at_runtime,
    facility_local_deadline,
    format_instant,
    stable_id,
)
from .history import CARRIER_SIDE_ROLES, TenantSetup
from .model import (
    ARRIVAL_STATUSES,
    OWNER_CONFIRMATION,
    POSITION_SIGNAL,
    STAGES_PAST_STOP,
    TRACKING_PROGRESSION,
    AccessorialAuthorization,
    AccessorialCharge,
    Appointment,
    BrokerageLoad,
    Carrier,
    CarrierContact,
    CarrierMovement,
    CarrierPayable,
    CommunicationMessage,
    CommunicationThread,
    Customer,
    CustomerContact,
    CustomerInvoice,
    CustomerOrder,
    DirectedMoney,
    Document,
    DocumentRequirement,
    Driver,
    Entity,
    Fact,
    FinancialReconciliationResult,
    Leg,
    OperationalTimelineEntry,
    Organization,
    RateConfirmation,
    Stop,
    TrackingEvent,
    carrier_owed,
    customer_owes,
    entity_id,
    entity_ref,
)

LOAD = BrokerageLoad.ENTITY_TYPE
MODEL_INFERRED = "MODEL_INFERRED"
#: The outside system a carrier's MC number is an id IN. An MC is trusted only within it, and only
#: for the brokerage whose mapping recorded it.
CARRIER_REGISTRY = "fmcsa"
#: The BENIGN ways one MC number is written: an optional `MC` prefix in any case, spaces and hyphens
#: around it, then the digits and nothing else. `MC-771203`, `MC 771203`, `mc771203` and `771203`.
_MC_BENIGN_FORM = re.compile(r"\s*(?:MC)?[\s-]*([0-9]+)\s*", re.IGNORECASE)
OPEN_CONFLICT_STATES = ("RAISED", "OPEN", "ESCALATED")
OWED_STATES = ("RAISED", "OVERDUE", "INDETERMINATE")
LATE_STATES = ("OVERDUE", "INDETERMINATE")
#: The appointment statuses that are a TIME a truck is held to: a CONFIRMED window, and the window
#: an appointment was RESCHEDULED to. A REQUESTED window is not a time anyone agreed to (CD-13) and
#: a CANCELLED appointment is no time at all.
TIMED_APPOINTMENT_STATUSES = ("CONFIRMED", "RESCHEDULED")


def split_ref(ref: str) -> tuple[str, str]:
    kind, _, ident = ref.partition(":")
    return kind, ident


def exception_key(exception: Mapping[str, Any]) -> str:
    """What makes an Exception THE SAME Exception on every run: its type and its cause. M9 allows one
    open row per `(source_ref, type)`, so this names an open Exception uniquely — and unlike the row's
    own id, which M9 mints at random when it raises one for a missed deadline, it is the same string
    when the history is replayed. It is also how a human names the Exception she is resolving."""
    return f"{exception['type']}@{exception['source_ref']}"


def canonical_mc_digits(value: object) -> str | None:
    """The digits of an MC number, when `value` is a BENIGN way of writing one; else None.

    Two spellings name one MC only when they differ in representation and in nothing else: the
    optional `MC` prefix, its case, and the spaces and hyphens around it. The DIGITS must then be
    identical, character for character. This is not a fuzzy match and must never become one: a
    shorter number, a longer one, a leading zero, one digit different, a separator inside the
    digits, another prefix or a trailing letter is a DIFFERENT identifier (or not an MC at all) —
    it returns None or different digits, and the invoice stays a named human's question."""
    match = _MC_BENIGN_FORM.fullmatch(str(value))
    return match.group(1) if match else None


@dataclass
class UnboundItem:
    """An inbound record Neyma did NOT attach to a load, and why."""

    observation_id: str
    kind: str | None
    state: str                         # UNBOUND | UNPARSEABLE
    reason: str                        # ambiguous | absent | unparseable
    owner_id: str | None
    candidate_load_ids: tuple[str, ...]
    references: tuple[str, ...]
    source_system: str
    as_of: str
    model_proposed: bool = False       # the candidates came from a model, not from a reference

    def as_document(self) -> dict[str, Any]:
        return {"observation_id": self.observation_id, "kind": self.kind, "state": self.state,
                "reason": self.reason, "owner_id": self.owner_id,
                "candidate_load_ids": list(self.candidate_load_ids),
                "references": list(self.references), "source_system": self.source_system,
                "as_of": self.as_of, "model_proposed": self.model_proposed}


@dataclass
class LoadView:
    """One Brokerage Load and every canonical record that hangs off it."""

    load: BrokerageLoad
    order: CustomerOrder | None = None
    customer: Customer | None = None
    movements: dict[str, CarrierMovement] = field(default_factory=dict)       # by movement_key
    legs: dict[str, Leg] = field(default_factory=dict)
    stops: dict[str, Stop] = field(default_factory=dict)                      # by stop_key
    appointments: dict[str, Appointment] = field(default_factory=dict)        # by stop_key
    carriers: dict[str, Carrier] = field(default_factory=dict)
    drivers: dict[str, Driver] = field(default_factory=dict)
    contacts: dict[str, Entity] = field(default_factory=dict)
    rate_confirmations: dict[str, RateConfirmation] = field(default_factory=dict)
    documents: dict[str, Document] = field(default_factory=dict)              # by evidence_id
    messages: list[CommunicationMessage] = field(default_factory=list)
    tracking: list[TrackingEvent] = field(default_factory=list)
    accessorials: dict[str, AccessorialCharge] = field(default_factory=dict)
    authorizations: list[AccessorialAuthorization] = field(default_factory=list)
    denied_charge_types: list[str] = field(default_factory=list)
    payables: dict[str, CarrierPayable] = field(default_factory=dict)
    requirements: list[DocumentRequirement] = field(default_factory=list)
    reconciliations: list[FinancialReconciliationResult] = field(default_factory=list)
    invoice: CustomerInvoice | None = None
    mappings: list[EntityMapping] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    expectations: list[dict[str, Any]] = field(default_factory=list)
    exceptions: list[dict[str, Any]] = field(default_factory=list)
    work_item: dict[str, Any] | None = None
    observations: list[dict[str, Any]] = field(default_factory=list)          # bound, arrival order
    commitments: list[dict[str, Any]] = field(default_factory=list)
    reference_corrections: list[dict[str, Any]] = field(default_factory=list)
    duplicate_evidence_arrivals: list[str] = field(default_factory=list)
    invoice_attributions: list[dict[str, Any]] = field(default_factory=list)   # human acts, in order
    binding_history: list[dict[str, Any]] = field(default_factory=list)
    ambiguous_candidates: list[UnboundItem] = field(default_factory=list)
    timeline: list[OperationalTimelineEntry] = field(default_factory=list)
    attention: list[str] = field(default_factory=list)       # open things a human must DECIDE
    housekeeping: list[str] = field(default_factory=list)    # open rows whose cause is already cured

    @property
    def load_id(self) -> str:
        return self.load.entity_id

    @property
    def ref(self) -> str:
        return self.load.ref

    def entities(self) -> list[Entity]:
        """Every field-bearing entity of this load, in a stable order."""
        out: list[Entity] = [self.load]
        for bag in (([self.order] if self.order else []), ([self.customer] if self.customer else []),
                    self.movements.values(), self.legs.values(), self.stops.values(),
                    self.appointments.values(), self.carriers.values(), self.drivers.values(),
                    self.contacts.values(), self.rate_confirmations.values(),
                    self.documents.values(), self.messages, self.tracking,
                    self.accessorials.values(), self.payables.values()):
            out.extend(bag)
        return out

    def entity_refs(self) -> set[str]:
        return {e.ref for e in self.entities()}

    def standing_tracking(self) -> list[TrackingEvent]:
        """Every movement claim that still STANDS. One a recorded human overruled stays in
        `tracking` as what its source SAID, and it is no longer evidence of where the truck has
        been: it reaches no stop, reports no delivery, starts no watch and puts the load at no
        stage. Neither does a bare claim that CONTRADICTS her decision and that she has not yet
        answered. Whatever CONCLUDES where the truck has been reads this, never `tracking`."""
        return [t for t in self.tracking if t.overruled_by is None and t.contests is None]

    def stops_a_claim_answers(self, claim: TrackingEvent) -> list[str]:
        """The stops this claim says the truck has been to, IF it stands: the stop it names, when
        what it reports happens at a stop; or, when it names none, the ONLY stop of a kind the
        reported stage is past. The rule `detectors.arrival_evidence` applies stop by stop, asked
        here of one claim."""
        status = claim.value("status")
        if claim.stop_key is not None:
            return [claim.stop_key] if claim.stop_key in self.stops \
                and status in ARRIVAL_STATUSES else []
        out: list[str] = []
        for stop_key, stop in self.stops.items():
            kind = stop.value("stop_type")
            if status in STAGES_PAST_STOP.get(kind, ()) and len(
                    [s for s in self.stops.values() if s.value("stop_type") == kind]) == 1:
                out.append(stop_key)
        return out

    def delivered_claims(self) -> list[TrackingEvent]:
        """Every source that has SAID this load delivered. A claim, from each of them (CD-15)."""
        return [t for t in self.standing_tracking() if t.value("status") == "DELIVERED"]

    def open_conflicts(self) -> list[dict[str, Any]]:
        return [c for c in self.conflicts if c["state"] in OPEN_CONFLICT_STATES]

    def owed_expectations(self) -> list[dict[str, Any]]:
        return [e for e in self.expectations if e["state"] in OWED_STATES]

    def late_expectations(self) -> list[dict[str, Any]]:
        return [e for e in self.expectations if e["state"] in LATE_STATES]

    # ------------------------------------------------------------------ the appointment that stands

    def arrival_deadline(self, stop_key: str) -> str | None:
        """The instant the truck is held to arrive at this stop by NOW: the end of the window of
        the appointment that stands there as a time, in the FACILITY's local time. None when no
        time stands — no appointment, a REQUESTED or CANCELLED one, or a window in dispute.

        ### THE CURRENT APPOINTMENT IS THE ONLY SOURCE OF THE CURRENT DEADLINE. Not a row M8 holds
        about a window the appointment has left, and not how healthy the tracking channel was when
        that window closed. Whatever asks what this stop is held to asks here."""
        appointment = self.appointments.get(stop_key)
        if appointment is None \
                or appointment.value("status") not in TIMED_APPOINTMENT_STATUSES:
            return None
        window = appointment.value("window")
        if window is None:
            return None
        return format_instant(facility_local_deadline(
            datetime.fromisoformat(window["end_local"]), window["timezone"]))

    def appointment_cancelled(self, stop_key: str) -> bool:
        """Whether the appointment at this stop was CANCELLED: the window it had no longer stands,
        and nothing has replaced it."""
        appointment = self.appointments.get(stop_key)
        return appointment is not None and appointment.value("status") == "CANCELLED"

    def superseded_expectations(self) -> list[dict[str, Any]]:
        """Arrival watches M8 still holds for a window the appointment has LEFT.

        A watch follows its appointment: M8 amends a RAISED one and cancels an OVERDUE one. One it
        has judged INDETERMINATE — the window closed while the tracking channel could not be shown
        to be up — it will do neither with, and nothing here makes it: that row stays exactly as M8
        ruled it, owned, with its Exception, until the truck arrives or it ages out.

        ### IT IS HISTORY ABOUT A WINDOW, NOT THE DEADLINE OF THE STOP. Once the appointment has
        moved on or been cancelled, such a row says what could not be verified about a time nobody
        holds any more. It does not time the appointment that stands, and it is not work."""
        out: list[dict[str, Any]] = []
        for expectation in self.expectations:
            kind, _, stop_key = expectation["expected_type"].partition(":")
            if kind != "arrival" or expectation["state"] != "INDETERMINATE":
                continue
            deadline = self.arrival_deadline(stop_key)
            if self.appointment_cancelled(stop_key) \
                    or (deadline is not None and expectation["deadline_utc"] != deadline):
                out.append(expectation)
        return out

    def operative_expectations(self) -> list[dict[str, Any]]:
        """What is owed NOW: every owed Expectation except a superseded arrival watch. This, never
        `owed_expectations`, is what current work, quiet and attention are read from."""
        superseded = {e["expectation_id"] for e in self.superseded_expectations()}
        return [e for e in self.owed_expectations() if e["expectation_id"] not in superseded]

    def open_exceptions(self) -> list[dict[str, Any]]:
        return [x for x in self.exceptions if x["state"] != "RESOLVED"]

    def as_document(self) -> dict[str, Any]:
        """The canonical, replay-stable shape of this load. Ids minted by a machine at random (an
        escalation's exception id, a correction's new claim id) are deliberately absent: they name
        the same fact differently on every run."""
        return {
            "load": self.load.as_document(),
            "order": self.order.as_document() if self.order else None,
            "customer": self.customer.as_document() if self.customer else None,
            "entities": [e.as_document() for e in self.entities()[1:]
                         if e is not self.order and e is not self.customer],
            "authorizations": [a.as_document() for a in self.authorizations],
            "denied_charge_types": sorted(self.denied_charge_types),
            "requirements": [r.as_document() for r in self.requirements],
            "reconciliations": [r.as_document() for r in self.reconciliations],
            "invoice": self.invoice.as_document() if self.invoice else None,
            "mappings": [{"external_system": m.external_system, "kind": m.external_id_kind,
                          "external_id": m.external_id, "state": m.state,
                          "provenance_class": m.provenance_class,
                          "entity": m.entity_ref} for m in self.mappings],
            "conflicts": [{"entity_ref": c["entity_ref"], "field": c["field"], "kind": c["kind"],
                           "state": c["state"], "owner_id": c["owner_id"],
                           "parties": [[p["party_ref"], p["provenance_class"], p["stated_value"]]
                                       for p in c["parties"]]} for c in self.conflicts],
            "expectations": [{"expected_type": e["expected_type"], "state": e["state"],
                              "deadline_utc": e["deadline_utc"],
                              "expected_source": e["expected_source"], "late": e["late"],
                              "coverage_gap": e["coverage_gap"], "owner_id": e["owner_id"]}
                             for e in self.expectations],
            "exceptions": sorted(
                ({"type": x["type"], "severity": x["severity"], "state": x["state"],
                  "owner_id": x["owner_id"], "source_kind": x["source_kind"]}
                 for x in self.exceptions), key=lambda d: json.dumps(d, sort_keys=True)),
            "work_item": ({"type": self.work_item["type"], "state": self.work_item["state"],
                           "owner_id": self.work_item["owner_id"]} if self.work_item else None),
            "attention": list(self.attention),
            "housekeeping": list(self.housekeeping),
            "timeline": [t.as_document() for t in self.timeline],
        }


@dataclass
class FreightProjection:
    """Everything Neyma canonically believes about one brokerage's freight, right now."""

    tenant: str
    organization: Organization
    loads: dict[str, LoadView] = field(default_factory=dict)
    threads: dict[str, CommunicationThread] = field(default_factory=dict)
    unbound: list[UnboundItem] = field(default_factory=list)
    mappings: list[EntityMapping] = field(default_factory=list)
    duplicate_confirmations: int = 0

    def load_for_ref(self, load_ref: str) -> LoadView | None:
        _, ident = split_ref(load_ref)
        return self.loads.get(ident)

    def view_by_load_ref(self, value: str) -> LoadView | None:
        """The load a brokerage's own load number CURRENTLY names (an ACTIVE mapping)."""
        for view in self.loads.values():
            for mapping in view.mappings:
                if (mapping.external_id_kind == "load_ref" and mapping.external_id == value
                        and mapping.state == "ACTIVE" and mapping.neyma_entity_type == LOAD):
                    return view
        return None

    def as_document(self) -> dict[str, Any]:
        return {
            "tenant": self.tenant,
            "organization": self.organization.as_document(),
            "loads": [self.loads[k].as_document() for k in sorted(self.loads)],
            "threads": [self.threads[k].as_document() for k in sorted(self.threads)],
            "unbound": [u.as_document() for u in self.unbound],
        }

    def digest(self) -> str:
        text = json.dumps(self.as_document(), sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Projector:
    """Builds the `FreightProjection` for one tenant from durable records. Reads only."""

    def __init__(self, foundation: FreightFoundation, mappings: ExternalEntityMappings,
                 setup: TenantSetup) -> None:
        if not (foundation.tenant == mappings.tenant == setup.tenant):
            raise ValueError(
                f"a projection is of ONE tenant: foundation={foundation.tenant!r}, "
                f"mappings={mappings.tenant!r}, setup={setup.tenant!r}")
        self._f = foundation
        self._m = mappings
        self._setup = setup
        self._tenant = foundation.tenant

    # ------------------------------------------------------------------ the fold

    def project(self) -> FreightProjection:
        tenant = self._tenant
        organization = Organization(tenant_id=tenant, entity_id=entity_id(tenant, "organization"),
                                    origin_observation_id="provisioned")
        projection = FreightProjection(tenant=tenant, organization=organization)
        all_mappings = self._m.all()
        projection.mappings = all_mappings

        for mapping in all_mappings:
            if mapping.neyma_entity_type != LOAD:
                continue
            view = projection.loads.get(mapping.neyma_entity_id)
            if view is None:
                view = LoadView(load=BrokerageLoad(
                    tenant_id=tenant, entity_id=mapping.neyma_entity_id,
                    origin_observation_id=mapping.source_observation_id))
                projection.loads[mapping.neyma_entity_id] = view
            view.mappings.append(mapping)

        observations = self._f.observations()
        by_id = {o["observation_id"]: o for o in observations}
        claims = self._f.binding_claims()
        confirmed = {c["subject_ref"]: c for c in claims if c["state"] == "CONFIRMED"}
        ambiguous: dict[str, list[dict[str, Any]]] = {}
        for claim in claims:
            if claim["state"] == "AMBIGUOUS":
                ambiguous.setdefault(claim["subject_ref"], []).append(claim)
        self._evidence_by_digest = {row["content_digest"]: row
                                    for row in self._f.evidence_rows()}
        projection.duplicate_confirmations = sum(self._f.confirmation_counts().values())

        bound: list[tuple[LoadView, dict[str, Any], dict[str, Any], dict[str, Any]]] = []
        for observation in observations:
            parsed = observation["parsed"]
            claim = confirmed.get(observation["observation_id"])
            if claim is not None and parsed is not None:
                kind, ident = split_ref(claim["entity_ref"])
                view = projection.loads.get(ident) if kind == LOAD else None
                if view is not None:
                    view.observations.append(observation)
                    bound.append((view, observation, parsed, claim))
                    continue
            if observation["state"] in ("UNBOUND", "UNPARSEABLE", "PARSED", "RECEIVED"):
                item = self._unbound_item(observation, ambiguous.get(observation["observation_id"]))
                projection.unbound.append(item)
                for load_id in item.candidate_load_ids:
                    candidate_view = projection.loads.get(load_id)
                    if candidate_view is not None:
                        candidate_view.ambiguous_candidates.append(item)

        # ### STRUCTURE FIRST, THEN EVERYTHING THAT HANGS OFF IT. A rate confirmation can arrive before
        # the TMS row that says which carrier is moving the load. Folding strictly in arrival order
        # would attribute that paper to a movement that does not exist yet and lose it. The system of
        # record's rows are applied first; every other record then lands, in arrival order, on a load
        # whose movements and stops are already there. What each record SAID, and when, is unchanged.
        for view, observation, parsed, claim in bound:
            if parsed["kind"] == "tms_load":
                self._apply(projection, view, observation, parsed, claim)
        for view, observation, parsed, claim in bound:
            if parsed["kind"] != "tms_load":
                self._apply(projection, view, observation, parsed, claim)

        for claim in claims:
            human_bound = claim["state"] == "CONFIRMED" and claim["match_method"] == "HUMAN"
            if human_bound or claim["state"] in ("CORRECTED", "REJECTED"):
                kind, ident = split_ref(claim["entity_ref"])
                view = projection.loads.get(ident) if kind == LOAD else None
                if view is not None:
                    view.binding_history.append({
                        "subject_ref": claim["subject_ref"], "state": claim["state"],
                        "match_method": claim["match_method"],
                        "provenance_class": claim["provenance_class"],
                        "decision_ref": claim["decision_ref"],
                        "corrected_from": claim["corrected_from"],
                        "updated_at": claim["updated_at"],
                        "source": by_id.get(claim["subject_ref"])})

        self._attach_foundation(projection)
        for view in projection.loads.values():
            self._derive(view)
        from .timeline import build_timeline  # local: timeline reads the finished view
        for view in projection.loads.values():
            view.timeline = build_timeline(view)
        return projection

    def _unbound_item(self, observation: Mapping[str, Any],
                      claims: list[dict[str, Any]] | None) -> UnboundItem:
        parsed = observation["parsed"]
        candidates = tuple(dict.fromkeys(
            split_ref(c["entity_ref"])[1] for c in (claims or ())
            if split_ref(c["entity_ref"])[0] == LOAD))
        if observation["state"] == "UNPARSEABLE":
            reason = "unparseable"
        elif candidates:
            reason = "ambiguous"
        else:
            reason = "absent"
        references = tuple(
            ExternalReference(r.get("system"), r["kind"], r["value"]).label()
            for r in (parsed or {}).get("refs", ()))
        return UnboundItem(
            observation_id=observation["observation_id"],
            kind=(parsed or {}).get("kind"), state=observation["state"], reason=reason,
            owner_id=observation["owner_id"], candidate_load_ids=candidates,
            references=references, source_system=observation["source_system"],
            as_of=observation["as_of"],
            model_proposed=any(c["match_method"] == "MODEL_INFER" for c in (claims or ())))

    # ------------------------------------------------------------------ facts

    def _fact(self, observation: Mapping[str, Any], parsed: Mapping[str, Any], value: Any, *,
              provenance: str | None = None, source: str | None = None,
              evidence_id: str | None = None, decision_ref: str | None = None) -> Fact:
        """A statement read from one record. Provenance comes from HOW the record was acquired
        (R-P1), unless the caller WEAKENS it — weakening is always legal, strengthening never."""
        assigned = assign_at_runtime(Acquisition(parsed["acquisition"])).value
        return Fact(
            value=value, provenance_class=provenance or assigned,
            observation_id=observation["observation_id"],
            source_system=source or observation["source_system"], as_of=observation["as_of"],
            originating_timezone=parsed["timezone"], received_at=observation["received_at"],
            evidence_id=evidence_id, decision_ref=decision_ref)

    # ------------------------------------------------------------------ appliers

    def _apply(self, projection: FreightProjection, view: LoadView,
               observation: Mapping[str, Any], parsed: Mapping[str, Any],
               claim: Mapping[str, Any]) -> None:
        kind = parsed["kind"]
        payload = parsed["payload"]
        if kind == "tms_load":
            self._apply_tms_load(view, observation, parsed, payload)
        elif kind == "tracking_event":
            self._add_tracking(view, observation, parsed, payload, index=0)
        elif kind == "appointment":
            self._observe_appointment(view, observation, parsed, payload)
        elif kind == "document":
            self._apply_document(view, observation, parsed, payload, claim)
        elif kind == "message":
            self._apply_message(projection, view, observation, parsed, payload)
        elif kind == "human_assertion":
            self._apply_human_assertion(view, observation, parsed, payload)

    def _resolve_entity(self, system: str, kind: str, value: str, entity_type: str) -> str | None:
        resolution = self._m.resolve(ExternalReference(system, kind, value), entity_type=entity_type)
        rows = resolution.active or resolution.retired
        return rows[0].neyma_entity_id if rows else None

    def _apply_tms_load(self, view: LoadView, observation: Mapping[str, Any],
                        parsed: Mapping[str, Any], payload: Mapping[str, Any]) -> None:
        tenant, load = self._tenant, view.load

        def fact(value: Any, **kw: Any) -> Fact:
            return self._fact(observation, parsed, value, **kw)

        load.observe("load_ref", fact(payload["load_ref"]))
        load.observe("reported_status", fact(payload["status"]))
        if "sell" in payload:
            sell = payload["sell"]
            total = sell["linehaul_minor"] + sell["fuel_minor"] + sum(
                a["amount_minor"] for a in sell["accessorials"])
            load.observe("sell", fact(customer_owes(total, sell["currency"])))

        system = observation["source_system"]
        order_block = payload.get("order") or {}
        if view.order is None:
            order_id = None
            if order_block.get("tms_order_id"):
                order_id = self._resolve_entity(system, "order_id",
                                                str(order_block["tms_order_id"]), "customer_order")
            # V-21 (OPEN): with no order id from the TMS the order is PROVISIONALLY one-per-load. The
            # FK is on the Load, so a later discovery that one order covers two loads re-points
            # `order_id` and adds nothing.
            order_id = order_id or entity_id(tenant, "customer_order", load.entity_id)
            view.order = CustomerOrder(tenant_id=tenant, entity_id=order_id,
                                       origin_observation_id=observation["observation_id"])
            load.order_id = order_id
        if order_block.get("customer_po"):
            view.order.observe("customer_po", fact(str(order_block["customer_po"])))
        if order_block.get("commodity"):
            view.order.observe("commodity", fact(str(order_block["commodity"])))

        customer_block = payload.get("customer") or {}
        if customer_block.get("tms_customer_id"):
            customer_id = self._resolve_entity(
                system, "customer_id", str(customer_block["tms_customer_id"]), "customer")
            if customer_id is not None:
                if view.customer is None:
                    view.customer = Customer(tenant_id=tenant, entity_id=customer_id,
                                             origin_observation_id=observation["observation_id"])
                    load.customer_id = customer_id
                    view.order.customer_id = customer_id
                if customer_block.get("legal_name"):
                    view.customer.observe("legal_name", fact(str(customer_block["legal_name"])))
                for contact in customer_block.get("contacts", ()):
                    self._contact(view, CustomerContact, customer_id, contact, fact,
                                  observation["observation_id"])

        for stop in payload.get("stops", ()):
            entity = view.stops.get(stop["stop_key"])
            if entity is None:
                entity = Stop(tenant_id=tenant,
                              entity_id=entity_id(tenant, "stop", load.entity_id, stop["stop_key"]),
                              origin_observation_id=observation["observation_id"],
                              load_id=load.entity_id, stop_key=stop["stop_key"])
                view.stops[stop["stop_key"]] = entity
            entity.observe("stop_type", fact(stop["stop_type"]))
            entity.observe("sequence", fact(stop["sequence"]))
            entity.observe("facility_name", fact(stop["facility_name"]))
            entity.observe("facility_timezone", fact(stop["facility_timezone"]))
            if "appointment" in stop:
                self._observe_appointment(
                    view, observation, parsed, {"stop_key": stop["stop_key"], **stop["appointment"]})

        for item in payload.get("movements", ()):
            key = item["movement_key"]
            movement = view.movements.get(key)
            if movement is None:
                movement = CarrierMovement(
                    tenant_id=tenant,
                    entity_id=entity_id(tenant, "carrier_movement", load.entity_id, key),
                    origin_observation_id=observation["observation_id"],
                    load_id=load.entity_id, movement_key=key)
                view.movements[key] = movement
            movement.observe("reported_status", fact(item["status"]))
            if item.get("carrier_pro"):
                movement.observe("carrier_pro", fact(str(item["carrier_pro"])))
            if "carrier_pay" in item:
                pay = item["carrier_pay"]
                total = pay["linehaul_minor"] + pay["fuel_minor"] + sum(
                    a["amount_minor"] for a in pay["accessorials"])
                # V-14: a buy figure that is not a rate confirmation is retained, WEAKENED to a guess.
                movement.observe("pre_ratecon_buy", fact(carrier_owed(total, pay["currency"]),
                                                         provenance=MODEL_INFERRED))
            carrier_block = item.get("carrier") or {}
            if carrier_block.get("mc_number"):
                carrier_id = self._resolve_entity("fmcsa", "mc_number",
                                                  str(carrier_block["mc_number"]), "carrier")
                if carrier_id is not None:
                    carrier = view.carriers.get(carrier_id)
                    if carrier is None:
                        carrier = Carrier(tenant_id=tenant, entity_id=carrier_id,
                                          origin_observation_id=observation["observation_id"])
                        view.carriers[carrier_id] = carrier
                    movement.carrier_id = carrier_id
                    carrier.observe("mc_number", fact(str(carrier_block["mc_number"])))
                    if carrier_block.get("legal_name"):
                        carrier.observe("legal_name", fact(str(carrier_block["legal_name"])))
                    if carrier_block.get("dot_number"):
                        carrier.observe("dot_number", fact(str(carrier_block["dot_number"])))
                    for contact in carrier_block.get("contacts", ()):
                        self._contact(view, CarrierContact, carrier_id, contact, fact,
                                      observation["observation_id"])
                    driver_block = item.get("driver") or {}
                    if driver_block.get("name") or driver_block.get("phone"):
                        seed = driver_block.get("phone") or driver_block.get("name")
                        driver_id = entity_id(tenant, "driver", carrier_id, seed)
                        driver = view.drivers.get(driver_id)
                        if driver is None:
                            driver = Driver(tenant_id=tenant, entity_id=driver_id,
                                            origin_observation_id=observation["observation_id"],
                                            carrier_id=carrier_id)
                            view.drivers[driver_id] = driver
                        movement.driver_id = driver_id
                        for name in ("name", "phone"):
                            if driver_block.get(name):
                                driver.observe(name, fact(str(driver_block[name])))
            for sequence, leg in enumerate(item.get("legs", ()), start=1):
                leg_id = entity_id(tenant, "leg", movement.entity_id, leg["leg_key"])
                entity = view.legs.get(leg_id)
                if entity is None:
                    entity = Leg(tenant_id=tenant, entity_id=leg_id,
                                 origin_observation_id=observation["observation_id"],
                                 movement_id=movement.entity_id, leg_key=leg["leg_key"])
                    view.legs[leg_id] = entity
                entity.observe("sequence", fact(sequence))
                for stop_key in leg["stop_keys"]:
                    if stop_key in view.stops:
                        view.stops[stop_key].leg_id = leg_id

        if payload["status"] in TRACKING_PROGRESSION:
            # The TMS status is ONE tracking source among several (domain family 07), and a claim.
            self._add_tracking(view, observation, parsed,
                               {"signal": "tms_status", "status": payload["status"],
                                "stop_key": None, "movement_key": None, "position": None},
                               index=0)

    def _contact(self, view: LoadView, cls: type, parent_id: str, contact: Mapping[str, Any],
                 fact: Any, observation_id: str) -> None:
        seed = contact.get("email") or contact.get("phone") or contact.get("name")
        if not seed:
            return
        contact_id = entity_id(self._tenant, cls.ENTITY_TYPE, parent_id, seed)
        entity = view.contacts.get(contact_id)
        if entity is None:
            parent_field = "customer_id" if cls is CustomerContact else "carrier_id"
            entity = cls(tenant_id=self._tenant, entity_id=contact_id,
                         origin_observation_id=observation_id, **{parent_field: parent_id})
            view.contacts[contact_id] = entity
        for name in ("name", "email", "phone", "role"):
            if contact.get(name):
                entity.observe(name, fact(str(contact[name])))

    def _observe_appointment(self, view: LoadView, observation: Mapping[str, Any],
                             parsed: Mapping[str, Any], payload: Mapping[str, Any], *,
                             source: str | None = None, decision_ref: str | None = None) -> None:
        stop = view.stops.get(payload["stop_key"])
        if stop is None:
            return
        appointment = view.appointments.get(payload["stop_key"])
        if appointment is None:
            appointment = Appointment(
                tenant_id=self._tenant,
                entity_id=entity_id(self._tenant, "appointment", stop.entity_id),
                origin_observation_id=observation["observation_id"], stop_id=stop.entity_id)
            view.appointments[payload["stop_key"]] = appointment
        window = {"start_local": payload["start_local"], "end_local": payload["end_local"],
                  "timezone": payload["timezone"]}
        appointment.observe("window", self._fact(observation, parsed, window, source=source,
                                                 decision_ref=decision_ref))
        if payload.get("status"):
            # A claim READ out of free text states a window and nothing more: a counterparty's
            # message can dispute an appointment time, but REQUESTED is not CONFIRMED (CD-13) and a
            # sentence does not make it so.
            appointment.observe("status", self._fact(observation, parsed, payload["status"],
                                                     source=source, decision_ref=decision_ref))

    def _attribute(self, view: LoadView, *, movement_key: str | None, carrier_mc: str | None,
                   ) -> tuple[CarrierMovement | None, str | None, str | None]:
        """Which movement a carrier-side record belongs to, HOW that is known, or WHY it is not:
        `(movement, basis, problem)`, exactly one of the last two set.

        By the movement key the record itself carries; else by the carrier's MC, resolved EXACTLY and
        within this brokerage through the External Entity Mapping, when exactly ONE movement of this
        load is that carrier's. Otherwise nothing is chosen: a load may be moved by several carriers,
        and attributing a carrier's paper to "the" movement would be the 1:1 assumption V-21 forbids.

        The MC is an IDENTITY looked up within this brokerage. It matches the string a mapping
        recorded, or — when both are BENIGN ways of writing an MC — a mapping whose digits are
        identical (`canonical_mc_digits`: "MC 771203" and "MC-771203" are one number; "MC-77120"
        and "MC-771204" are not, and are never matched). Every carrier either way finds is counted:
        if the brokerage's own records hold that number under two carriers, nothing is chosen. An
        MC that fits no recorded carrier is a named human's question, not a guess."""
        if movement_key and movement_key in view.movements:
            return view.movements[movement_key], "MOVEMENT_KEY", None
        if not carrier_mc:
            return None, None, "CARRIER_NOT_STATED"
        resolution = self._m.resolve(
            ExternalReference(CARRIER_REGISTRY, "mc_number", str(carrier_mc)),
            entity_type=Carrier.ENTITY_TYPE)
        exact = tuple(dict.fromkeys(m.neyma_entity_id for m in resolution.active))
        digits = canonical_mc_digits(carrier_mc)
        equivalent = tuple(dict.fromkeys(
            m.neyma_entity_id for m in self._m.active_of_kind(
                CARRIER_REGISTRY, "mc_number", entity_type=Carrier.ENTITY_TYPE)
            if canonical_mc_digits(m.external_id) == digits)) if digits is not None else ()
        carriers = tuple(dict.fromkeys((*exact, *equivalent)))
        if not carriers:
            return None, None, "CARRIER_UNRECOGNIZED"
        if len(carriers) > 1:
            return None, None, "CARRIER_AMBIGUOUS"
        matches = [m for m in view.movements.values() if m.carrier_id == carriers[0]]
        if len(matches) == 1:
            return matches[0], "CARRIER_MC_EXACT" if exact else "CARRIER_MC_EQUIVALENT", None
        return None, None, "CARRIER_AMBIGUOUS" if matches else "CARRIER_NOT_ON_LOAD"

    def _movement_for(self, view: LoadView, *, movement_key: str | None,
                      carrier_mc: str | None) -> CarrierMovement | None:
        return self._attribute(view, movement_key=movement_key, carrier_mc=carrier_mc)[0]

    def _add_tracking(self, view: LoadView, observation: Mapping[str, Any],
                      parsed: Mapping[str, Any], payload: Mapping[str, Any], *,
                      index: int, source: str | None = None) -> None:
        def fact(value: Any) -> Fact:
            return self._fact(observation, parsed, value, source=source)

        event = TrackingEvent(
            tenant_id=self._tenant,
            entity_id=entity_id(self._tenant, "tracking_event", observation["observation_id"],
                                payload["signal"], index),
            origin_observation_id=observation["observation_id"], load_id=view.load_id,
            stop_key=payload.get("stop_key"))
        movement = self._movement_for(view, movement_key=payload.get("movement_key"),
                                      carrier_mc=None)
        event.movement_id = movement.entity_id if movement else None
        event.observe("signal", fact(payload["signal"]))
        event.observe("status", fact(payload["status"]))
        if payload.get("position") is not None:
            event.observe("position", fact(payload["position"]))
        view.tracking.append(event)
        stop = view.stops.get(payload.get("stop_key") or "")
        if stop is not None:
            # Arrival and departure are CLAIMS, from whichever source made them (CD-15).
            if payload["status"] in ("AT_PICKUP", "AT_DELIVERY"):
                stop.observe("reported_arrival", fact(observation["as_of"]))
            elif payload["status"] in ("LOADED", "DELIVERED"):
                stop.observe("reported_departure", fact(observation["as_of"]))

    def _apply_document(self, view: LoadView, observation: Mapping[str, Any],
                        parsed: Mapping[str, Any], payload: Mapping[str, Any],
                        claim: Mapping[str, Any]) -> None:
        digest = hashlib.sha256(payload["content"].encode("utf-8")).hexdigest()
        evidence = self._evidence_by_digest.get(digest)
        if evidence is None:
            return
        evidence_id = evidence["evidence_id"]
        source = f"document:{evidence_id}"

        def fact(value: Any) -> Fact:
            return self._fact(observation, parsed, value, source=source, evidence_id=evidence_id)

        document = view.documents.get(evidence_id)
        if document is not None:
            # The same bytes arrived again under a different message. ONE Document; the second
            # arrival is recorded and creates no second canonical record.
            document.arrivals.append(observation["observation_id"])
            view.duplicate_evidence_arrivals.append(observation["observation_id"])
            return
        document = Document(
            tenant_id=self._tenant,
            entity_id=entity_id(self._tenant, "document", evidence_id, view.load_id),
            origin_observation_id=observation["observation_id"], evidence_id=evidence_id,
            load_id=view.load_id, binding_method=claim["match_method"],
            arrivals=[observation["observation_id"]])
        document.observe("doc_type", fact(payload["doc_type"]))
        document.observe("signed", fact(payload["signed"]))
        document.observe("pages", fact({"expected": payload["pages_expected"],
                                        "present": payload["pages_present"]}))
        if evidence["illegible"] or not payload["legible"]:
            document.lifecycle_state = "ILLEGIBLE"
        else:
            document.lifecycle_state = "BOUND"
        view.documents[evidence_id] = document

        extracted = payload.get("extracted") or {}
        if not extracted or document.lifecycle_state == "ILLEGIBLE":
            return
        movement, basis, problem = self._attribute(
            view, movement_key=extracted.get("movement_key"),
            carrier_mc=extracted.get("carrier_mc"))
        currency = extracted["currency"]
        lines = sorted(extracted["accessorials"], key=lambda a: a["charge_type"])
        if payload["doc_type"] == "RATE_CON":
            key = movement.entity_id if movement else f"load:{view.load_id}"
            ratecon = view.rate_confirmations.get(key)
            if ratecon is None:
                ratecon = RateConfirmation(
                    tenant_id=self._tenant,
                    entity_id=entity_id(self._tenant, "rate_confirmation", key),
                    origin_observation_id=observation["observation_id"],
                    movement_id=movement.entity_id if movement else None,
                    document_id=document.entity_id)
                view.rate_confirmations[key] = ratecon
            ratecon.observe("ratecon_number", fact(extracted["ratecon_number"]))
            ratecon.observe("status", fact(
                extracted.get("status") or ("SIGNED" if payload["signed"] else "SENT")))
            ratecon.observe("linehaul", fact(carrier_owed(extracted["linehaul_minor"], currency)))
            ratecon.observe("fuel", fact(carrier_owed(extracted["fuel_minor"], currency)))
            ratecon.observe("accessorials", fact(lines))
        elif payload["doc_type"] == "CARRIER_INVOICE":
            key = f"{extracted.get('carrier_mc') or '?'}|{extracted['invoice_number']}"
            payable = view.payables.get(key)
            new_values = (extracted["linehaul_minor"], extracted["fuel_minor"],
                          tuple((a["charge_type"], a["amount_minor"]) for a in lines))
            if payable is not None:
                first = (payable.field_of("linehaul").facts[0].value.amount_minor,
                         payable.field_of("fuel").facts[0].value.amount_minor,
                         tuple((a["charge_type"], a["amount_minor"])
                               for a in payable.field_of("accessorials").facts[0].value))
                if new_values == first:
                    # The same invoice number re-sent with the same charges: one payable. The
                    # duplicate is RECOGNIZED and suppressed (L-Payable DUPLICATE_SUPPRESSED).
                    payable.duplicate_observation_ids.append(observation["observation_id"])
                    return
            else:
                # An invoice that cannot be placed on a movement is still a payable someone is
                # asking for. It is created UNATTRIBUTED, with the reason, so that it is held and a
                # named human is asked — never quietly parked where no reconciliation looks.
                payable = CarrierPayable(
                    tenant_id=self._tenant,
                    entity_id=entity_id(self._tenant, "carrier_payable", key),
                    origin_observation_id=observation["observation_id"],
                    movement_id=movement.entity_id if movement else None, load_id=view.load_id,
                    document_id=document.entity_id, attribution_basis=basis,
                    attribution_problem=problem,
                    stated_carrier_mc=(str(extracted["carrier_mc"])
                                       if extracted.get("carrier_mc") else None),
                    stated_movement_key=extracted.get("movement_key"))
                view.payables[key] = payable
            payable.observe("invoice_number", fact(extracted["invoice_number"]))
            payable.observe("linehaul", fact(carrier_owed(extracted["linehaul_minor"], currency)))
            payable.observe("fuel", fact(carrier_owed(extracted["fuel_minor"], currency)))
            payable.observe("accessorials", fact(lines))
            if "total_minor" in extracted:
                payable.observe("total", fact(carrier_owed(extracted["total_minor"], currency)))
            for line in lines:
                self._accessorial(view, observation, parsed, movement=movement,
                                  charge_type=line["charge_type"],
                                  amount=carrier_owed(line["amount_minor"], currency),
                                  role="carrier", source=source, evidence_id=evidence_id,
                                  claims_authorization=False)

    def _accessorial(self, view: LoadView, observation: Mapping[str, Any],
                     parsed: Mapping[str, Any], *, movement: CarrierMovement | None,
                     charge_type: str, amount: DirectedMoney | None, role: str,
                     source: str | None, evidence_id: str | None, claims_authorization: bool,
                     amount_provenance: str | None = None) -> None:
        charge = view.accessorials.get(charge_type)
        if charge is None:
            charge = AccessorialCharge(
                tenant_id=self._tenant,
                entity_id=entity_id(self._tenant, "accessorial_charge", view.load_id, charge_type),
                origin_observation_id=observation["observation_id"], load_id=view.load_id,
                movement_id=movement.entity_id if movement else None)
            charge.observe("charge_type", self._fact(observation, parsed, charge_type,
                                                     source=source, evidence_id=evidence_id))
            view.accessorials[charge_type] = charge
        if amount is not None:
            charge.observe("amount", self._fact(observation, parsed, amount, source=source,
                                                evidence_id=evidence_id,
                                                provenance=amount_provenance))
        charge.observe("requesting_party_role", self._fact(observation, parsed, role,
                                                           source=source, evidence_id=evidence_id))
        charge.claim_observation_ids.append(observation["observation_id"])
        if claims_authorization:
            # CD-5 / ADR-003: a counterparty saying "you approved it" is a FRAUD SIGNAL on the charge.
            # It is recorded here and it is never an Accessorial Authorization.
            charge.counterparty_asserted_authorization = True

    def _apply_message(self, projection: FreightProjection, view: LoadView,
                       observation: Mapping[str, Any], parsed: Mapping[str, Any],
                       payload: Mapping[str, Any]) -> None:
        def fact(value: Any) -> Fact:
            return self._fact(observation, parsed, value)

        thread_id = entity_id(self._tenant, "communication_thread", parsed["channel"],
                              payload["thread_key"])
        thread = projection.threads.get(thread_id)
        if thread is None:
            thread = CommunicationThread(
                tenant_id=self._tenant, entity_id=thread_id,
                origin_observation_id=observation["observation_id"],
                thread_key=payload["thread_key"])
            thread.observe("channel", fact(parsed["channel"]))
            projection.threads[thread_id] = thread
        if payload["subject"]:
            thread.observe("subject", fact(payload["subject"]))
        message = CommunicationMessage(
            tenant_id=self._tenant,
            entity_id=entity_id(self._tenant, "communication_message",
                                observation["observation_id"]),
            origin_observation_id=observation["observation_id"], thread_id=thread_id,
            load_id=view.load_id,
            quoted_message_external_ids=tuple(payload["quoted_external_ids"]))
        message.observe("direction", fact(payload["direction"]))
        message.observe("sender_role", fact(payload["sender"]["role"]))
        message.observe("sender", fact(payload["sender"]["name"] or payload["sender"]["address"]))
        message.observe("subject", fact(payload["subject"]))
        message.observe("body", fact(payload["body"]))
        view.messages.append(message)
        thread.message_ids.append(message.entity_id)
        thread.load_ids.append(view.load_id)

        role = payload["sender"]["role"]
        # WHO SAID IT is the source of a claim made in a message, not which inbox it landed in. Two
        # parties writing to one inbox are two sources: neither's statement supersedes the other's.
        # The same party's later statement does supersede its own earlier one, and both are kept.
        speaker = claim_source(observation, payload)
        for index, item in enumerate(payload["asserts"]):
            kind = item["type"]
            if kind == "status":
                signal = "driver_assertion" if role == "driver" else "carrier_assertion"
                self._add_tracking(view, observation, parsed,
                                   {"signal": signal, "status": item["status"],
                                    "stop_key": resolve_stop_key(view, item),
                                    "movement_key": item.get("movement_key"), "position": None},
                                   index=index + 1, source=speaker)
            elif kind == "appointment":
                claim = resolve_appointment_claim(view, item)
                if claim is not None:
                    self._observe_appointment(view, observation, parsed, claim, source=speaker)
            elif kind == "accessorial_claim":
                movement = self._movement_for(view, movement_key=item.get("movement_key"),
                                              carrier_mc=None)
                money, weakened = resolve_claim_money(view, item)
                self._accessorial(
                    view, observation, parsed, movement=movement, charge_type=item["charge_type"],
                    amount=money, role=role, source=speaker, evidence_id=None,
                    claims_authorization=item["claims_authorization"],
                    amount_provenance=weakened)
            elif kind == "rate":
                movement = self._movement_for(view, movement_key=item.get("movement_key"),
                                              carrier_mc=None)
                if movement is None and len(view.movements) == 1:
                    movement = next(iter(view.movements.values()))
                money, _ = resolve_claim_money(view, item)
                if movement is not None and money is not None:
                    # V-14: a rate said in conversation is retained as a guess, never as the buy.
                    movement.observe("pre_ratecon_buy", self._fact(
                        observation, parsed, money, provenance=MODEL_INFERRED, source=speaker))
            elif kind == "reference_correction":
                view.reference_corrections.append({
                    "observation_id": observation["observation_id"], "index": index,
                    "stated_reference": item.get("stated_reference"),
                    "replaces": item.get("replaces"), "sender_role": role})
            elif kind == "commitment":
                view.commitments.append({
                    "observation_id": observation["observation_id"], "index": index,
                    "commitment_kind": item["commitment_kind"], "due_by": item["due_by"],
                    "in_quoted_text": item["in_quoted_text"], "sender_role": role,
                    "sender_identity": sender_identity(payload),
                    "channel": observation["source_system"], "timezone": parsed["timezone"],
                    "received_at": observation["received_at"], "as_of": observation["as_of"]})

    def _apply_human_assertion(self, view: LoadView, observation: Mapping[str, Any],
                               parsed: Mapping[str, Any], payload: Mapping[str, Any]) -> None:
        act = payload["act"]
        decision_ref = f"observation:{observation['observation_id']}"
        if act == "authorize_accessorial":
            assigned = assign_at_runtime(Acquisition(parsed["acquisition"])).value
            view.authorizations.append(AccessorialAuthorization(
                authorization_id=entity_id(self._tenant, "accessorial_authorization",
                                           observation["observation_id"]),
                tenant_id=self._tenant, load_id=view.load_id, charge_type=payload["charge_type"],
                amount_cap=DirectedMoney(
                    payload["amount_cap_minor"], payload["currency"], payload["direction"],
                    "owed_to_carrier" if payload["direction"] == "OUT" else "owed_by_customer"),
                authorized_by=payload["human_id"], decision_ref=decision_ref,
                provenance_class=assigned, observation_id=observation["observation_id"]))
        elif act == "deny_accessorial":
            view.denied_charge_types.append(payload["charge_type"])
        elif act == "confirm_appointment":
            # OWNER_ASSERTED, from how the record was acquired: it answers what was said before it,
            # and no machine statement overwrites it.
            self._observe_appointment(view, observation, parsed, {
                "stop_key": payload["stop_key"], "start_local": payload["start_local"],
                "end_local": payload["end_local"], "timezone": payload["timezone"],
                "status": "CONFIRMED"}, decision_ref=decision_ref)
        elif act == "confirm_movement_status":
            # OWNER_ASSERTED, from how the record was acquired. It is one more statement about
            # where the load is — hers — and `_apply_status_decisions` gives it its weight.
            self._add_tracking(view, observation, parsed, {
                "signal": OWNER_CONFIRMATION, "status": payload["status"],
                "stop_key": payload.get("stop_key")}, index=0)
        elif act == "attribute_carrier_invoice":
            target = self._f.observation_by_external(payload["target"]["source_system"],
                                                     payload["target"]["external_id"])
            if target is not None:
                # Applied in `_derive`, once every invoice is on the load: the human's act may
                # arrive before or after the paper it places.
                view.invoice_attributions.append({
                    "target_observation_id": target["observation_id"],
                    "movement_key": payload["movement_key"], "human_id": payload["human_id"],
                    "decision_ref": decision_ref,
                    "observation_id": observation["observation_id"],
                    "received_at": observation["received_at"]})

    # ------------------------------------------------------------------ foundation rows

    def _attach_foundation(self, projection: FreightProjection) -> None:
        refs_to_view: dict[str, LoadView] = {}
        for view in projection.loads.values():
            for ref in view.entity_refs():
                refs_to_view[ref] = view
        expectation_view: dict[str, LoadView] = {}
        for expectation in self._f.expectations():
            view = refs_to_view.get(expectation["subject_ref"])
            if view is not None:
                view.expectations.append(expectation)
                expectation_view[expectation["expectation_id"]] = view
        for conflict in self._f.conflicts():
            view = refs_to_view.get(conflict["entity_ref"])
            if view is None:
                continue
            view.conflicts.append(conflict)
            if conflict["state"] in OPEN_CONFLICT_STATES:
                for entity in view.entities():
                    if entity.ref == conflict["entity_ref"] and conflict["field"] in entity.FIELDS:
                        entity.field_of(conflict["field"]).conflict_id = conflict["conflict_id"]
        for exception in self._f.exceptions():
            view = refs_to_view.get(exception["entity_ref"] or "")
            if view is None and exception["source_kind"] == "expectation":
                view = expectation_view.get(exception["source_ref"])
            if view is not None:
                view.exceptions.append(exception)
        for work_item in self._f.work_items():
            view = refs_to_view.get(work_item["entity_ref"] or "")
            if view is not None:
                view.work_item = work_item

    # ------------------------------------------------------------------ derived state

    def _apply_invoice_attributions(self, view: LoadView) -> None:
        """A recorded human places an invoice on a movement of the load. Hers is the only word that
        can place paper Neyma could not, and the later of two such acts stands. It names a MOVEMENT;
        it approves nothing and makes nothing payable — the invoice is then reconciled like any
        other, and may well not match."""
        for attribution in view.invoice_attributions:
            payable = next(
                (p for p in view.payables.values()
                 if attribution["target_observation_id"]
                 in (p.origin_observation_id, *p.duplicate_observation_ids)), None)
            if payable is None:
                continue
            movement = view.movements.get(attribution["movement_key"])
            if movement is None:
                # She named a movement this load does not have. Nothing is placed; if nothing else
                # had placed it either, that is now WHY it is unplaced.
                if payable.movement_id is None:
                    payable.attribution_problem = "MOVEMENT_UNKNOWN"
                    payable.stated_movement_key = attribution["movement_key"]
                    payable.attributed_by = attribution["human_id"]
                continue
            payable.movement_id = movement.entity_id
            payable.attribution_basis = "HUMAN_ASSERTION"
            payable.attribution_problem = None
            payable.attributed_by = attribution["human_id"]
            payable.attribution_decision_ref = attribution["decision_ref"]

    def _apply_status_decisions(self, view: LoadView) -> None:
        """A recorded human's word on where the load IS settles what was said BEFORE it. Another
        source's earlier claim of a LATER stage than the one she confirmed is overruled: it stays
        on the record as what that source said, and it no longer counts as a claim that the stage
        was reached.

        ### HER DECISION DEFEATS THE CLAIM. SAYING IT AGAIN DOES NOT RESURRECT IT. What is said
        AFTER she decided, of a later stage than she confirmed, is one of three things:

          * a READING that the truck moved on - the tracking provider's own position puts it past
            where she said it was. That stands, and so does every claim made from then on: her
            decision was about a moment, and the truck has left it. Nobody is asked to approve a
            real delivery because the truck was in transit earlier.
          * a RESTATEMENT - the very source she overruled says the same thing again, having said
            nothing else in between: a re-sent row, a new version of it with no new freight fact,
            the same text typed twice. It is overruled by the same decision, and silently: it was
            answered when she answered the first one.
          * a bare claim that is NEW - another source, or the same one after it had said something
            different. It may well be true, and it is still only a word against hers. It is marked
            as contesting her decision, it does not stand, and the detectors put it in front of a
            recorded human as a new dispute.

        ### A RESTATEMENT IS DROPPED SILENTLY ONLY WHERE THE TRUCK IS STILL BEING ASKED ABOUT. It is
        safe to say nothing about a repeated "delivered" while the brokerage is still waiting for
        that truck at the stop the claim is about: the watch there is owed, it goes late, and the
        follow-up finds out. Where nothing is waiting - the truck is already at that stop by
        standing evidence, or this brokerage watches no arrivals at all - the repeat is the only
        thing that could move the load on, and dropping it unasked would leave a delivery report
        on a QUIET load. There it contests her decision like any other bare claim: a question,
        never silence.

        A claim is judged by the moment it is ABOUT (`as_of`), never by when it arrived: a copy of
        the overruled statement under a new record id is about the same moment, and is overruled
        with it. Only her LATEST decision governs (`P9-D60`)."""
        decisions = [t for t in view.tracking if t.value("signal") == OWNER_CONFIRMATION
                     and t.value("status") in TRACKING_PROGRESSION]
        if not decisions:
            return

        def said(event: TrackingEvent) -> Fact:
            return event.field_of("status").facts[0]

        latest = max(decisions, key=lambda t: (said(t).as_of, t.entity_id))
        decided_at = said(latest).as_of
        decision = latest.origin_observation_id
        rank = TRACKING_PROGRESSION.index(latest.value("status"))

        def beyond(event: TrackingEvent) -> bool:
            return TRACKING_PROGRESSION.index(event.value("status")) > rank

        for event in view.tracking:
            if event is latest or event.value("status") not in TRACKING_PROGRESSION:
                continue
            if said(event).as_of <= decided_at and beyond(event):
                event.overruled_by = decision

        claims = sorted((t for t in view.tracking if t.value("status") in TRACKING_PROGRESSION
                         and t.value("signal") != OWNER_CONFIRMATION),
                        key=lambda t: (said(t).as_of, t.entity_id))
        # The first reading, after her decision, that the truck is past where she said it was.
        moved_on_at = min((said(t).as_of for t in claims if t.value("signal") == POSITION_SIGNAL
                           and said(t).as_of > decided_at and beyond(t)), default=None)
        watching = self._setup.arrival_tracking_channel is not None

        def still_asked_about(event: TrackingEvent) -> bool:
            """Whether, at the moment this claim is about, the brokerage is still waiting for the
            truck at a stop the claim would answer: nothing standing has put it there yet."""
            moment = said(event).as_of
            been = {stop_key for t in view.tracking
                    if t is not event and t.overruled_by is None and t.contests is None
                    and said(t).as_of <= moment for stop_key in view.stops_a_claim_answers(t)}
            return watching and bool(set(view.stops_a_claim_answers(event)) - been)

        last_said: dict[tuple[str, str], TrackingEvent] = {}
        for event in claims:
            fact = said(event)
            source = (fact.source_system, event.value("signal"))
            previous, last_said[source] = last_said.get(source), event
            if fact.as_of <= decided_at or not beyond(event):
                continue
            if event.value("signal") == POSITION_SIGNAL:
                continue
            if moved_on_at is not None and moved_on_at <= fact.as_of:
                continue
            restated = (previous is not None and previous.overruled_by == decision
                        and previous.value("status") == event.value("status"))
            if restated and still_asked_about(event):
                event.overruled_by = decision
            else:
                event.contests = decision

    def _derive(self, view: LoadView) -> None:
        tenant = self._tenant
        self._apply_status_decisions(view)
        self._apply_invoice_attributions(view)

        # L-Access: a charge is AUTHORIZED only by a recorded human authorization that covers it.
        for charge_type, charge in view.accessorials.items():
            amount = charge.value("amount")
            covering = [a for a in view.authorizations
                        if a.charge_type == charge_type and amount is not None
                        and a.amount_cap.amount_minor >= amount.amount_minor]
            if charge_type in view.denied_charge_types:
                charge.lifecycle_state = "DENIED"
            elif charge.condition("amount") == EvidenceCondition.CONFLICTING.value:
                charge.lifecycle_state = "DISPUTED"
            elif covering:
                charge.lifecycle_state = "AUTHORIZED"
                charge.authorization_id = covering[0].authorization_id
            else:
                charge.lifecycle_state = "CLAIMED"

        # L-Payable: a second, DIFFERENT statement of the same invoice number is a dispute.
        for payable in view.payables.values():
            contested = any(payable.condition(n) == EvidenceCondition.CONFLICTING.value
                            for n in payable.CONTESTED)
            payable.lifecycle_state = "DISPUTED" if contested else "INVOICE_RECEIVED"

        # E40: one derived reconciliation per movement that has a rate confirmation or a payable.
        view.reconciliations = []
        for movement in view.movements.values():
            ratecon = view.rate_confirmations.get(movement.entity_id)
            payables = [p for p in view.payables.values() if p.movement_id == movement.entity_id]
            for payable in payables or [None]:
                result = reconcile_movement(
                    tenant=tenant, load_id=view.load_id, movement=movement,
                    rate_confirmation=ratecon, payable=payable,
                    authorizations=view.authorizations,
                    denied_charge_types=view.denied_charge_types)
                if result is not None:
                    view.reconciliations.append(result)
                    if payable is not None and result.status == "RECONCILED":
                        payable.lifecycle_state = "RECONCILED"
                    elif payable is not None and result.status == "DISCREPANT":
                        payable.lifecycle_state = "HELD"
        # An invoice no movement claims was compared against NOTHING above. It is HELD: it cannot
        # be RECONCILED, and "no discrepancy found" about it would be a statement nobody checked.
        for payable in view.payables.values():
            if payable.movement_id is None:
                payable.lifecycle_state = "HELD"

        self._derive_requirements(view)
        self._derive_invoice_eligibility(view)
        self._derive_attention(view)

    def qualifying_document(self, view: LoadView, doc_type: str) -> Document | None:
        """The document that satisfies a requirement, or None. It must be the right type, bound to
        this load by a CONFIRMED claim, legible, complete, on retained evidence, and — for a POD —
        SIGNED. An unsigned BOL is not a POD, and neither is a POD nobody can read."""
        for document in view.documents.values():
            if document.value("doc_type") != doc_type or document.lifecycle_state != "BOUND":
                continue
            pages = document.value("pages") or {}
            if pages.get("present", 0) < pages.get("expected", 1):
                continue
            if doc_type == "POD" and document.value("signed") is not True:
                continue
            if self._f.evidence_condition(document.evidence_id) != "consistent":
                continue
            return document
        return None

    def _derive_requirements(self, view: LoadView) -> None:
        tenant = self._tenant
        view.requirements = []
        delivered = bool(view.delivered_claims())
        if not self._setup.document_requirements:
            view.requirements.append(DocumentRequirement(
                requirement_id=entity_id(tenant, "document_requirement", view.load_id, "unknown"),
                tenant_id=tenant, load_id=view.load_id, gate="RAISE_INVOICE",
                required_doc_type="UNKNOWN", state="UNKNOWN",
                reason=("this brokerage has configured no document requirement; per-customer "
                        "requirement sets are NEEDS VALIDATION and are never assumed")))
            return
        for config in self._setup.document_requirements:
            expected_type = f"document:{config.required_doc_type}"
            related = [e for e in view.expectations if e["expected_type"] == expected_type]
            expectation_id = related[-1]["expectation_id"] if related else None
            document = self.qualifying_document(view, config.required_doc_type)
            if document is not None:
                state, reason = "SATISFIED", f"{config.required_doc_type} on file"
            elif delivered:
                state = "OUTSTANDING"
                reason = f"delivery has been reported and no usable {config.required_doc_type} is on file"
            else:
                state, reason = "PENDING", "delivery has not been reported"
            view.requirements.append(DocumentRequirement(
                requirement_id=entity_id(tenant, "document_requirement", view.load_id,
                                         config.gate, config.required_doc_type),
                tenant_id=tenant, load_id=view.load_id, gate=config.gate,
                required_doc_type=config.required_doc_type, state=state, reason=reason,
                satisfied_by_document_id=document.entity_id if document else None,
                expectation_id=expectation_id))

    def _derive_invoice_eligibility(self, view: LoadView) -> None:
        """The L-Invoice `ELIGIBLE` guard (CD-3, CD-8, GR-10), evaluated and explained. Nothing is
        issued: this build raises no invoice and performs no effect."""
        blockers: list[str] = []
        if not view.delivered_claims():
            blockers.append("delivery has not been reported by any source")
        if view.load.condition("sell") != EvidenceCondition.CONSISTENT.value:
            blockers.append(f"the sell rate is {view.load.condition('sell')}")
        for requirement in view.requirements:
            if requirement.state != "SATISFIED":
                blockers.append(f"document requirement {requirement.required_doc_type} is "
                                f"{requirement.state}: {requirement.reason}")
        billing_refs = {view.load.ref, *(d.ref for d in view.documents.values())}
        if view.customer:
            billing_refs.add(view.customer.ref)
        for conflict in view.open_conflicts():
            if conflict["entity_ref"] in billing_refs or conflict["field"] == "tracking_status":
                blockers.append(f"open conflict on {conflict['field']}")
        view.invoice = CustomerInvoice(
            tenant_id=self._tenant,
            entity_id=entity_id(self._tenant, "customer_invoice", view.load_id),
            origin_observation_id=view.load.origin_observation_id, load_id=view.load_id,
            lifecycle_state="NOT_ELIGIBLE" if blockers else "ELIGIBLE", blockers=tuple(blockers))

    def _derive_attention(self, view: LoadView) -> None:
        """Why a human must look at this load. Each line is one open, owned thing that needs a
        DECISION. An Exception raised for a missed deadline whose awaited thing has since arrived is
        still open in M9 — nothing closes an Exception but a human or a registered rule — but there
        is nothing left to decide about it, so it is listed as housekeeping, not as attention."""
        reasons: list[str] = []
        housekeeping: list[str] = []
        # A watch on a window the appointment has left is history, and so is its Exception.
        operative = view.operative_expectations()
        owed_ids = {e["expectation_id"] for e in operative}
        for conflict in view.open_conflicts():
            reasons.append(f"conflict:{conflict['entity_ref'].split(':')[0]}.{conflict['field']}")
        for expectation in operative:
            if expectation["state"] in LATE_STATES:
                reasons.append(
                    f"expectation:{expectation['expected_type']}:{expectation['state']}")
        for exception in view.open_exceptions():
            if exception["source_kind"] == "expectation":
                if exception["source_ref"] not in owed_ids:
                    housekeeping.append(f"cured_exception:{exception['type']}")
                continue                      # an owed one is already listed as the expectation
            reasons.append(f"exception:{exception['type']}")
        for item in view.ambiguous_candidates:
            reasons.append(f"ambiguous_binding:{item.kind}")
        for requirement in view.requirements:
            if requirement.state == "UNKNOWN":
                reasons.append("document_requirements_unknown")
            elif requirement.state == "OUTSTANDING" and not any(
                    e["expected_type"] == f"document:{requirement.required_doc_type}"
                    for e in view.owed_expectations()):
                # Owed, with no configured deadline to make it an Expectation: still a human's.
                reasons.append(f"document_outstanding:{requirement.required_doc_type}")
        for result in view.reconciliations:
            if result.status == "COMPUTED" and result.actual is not None:
                reasons.append("reconciliation_unresolved")
        for payable in view.payables.values():
            if payable.movement_id is None:
                # Read off the payable itself, not off the Exception raised for it: the invoice
                # needs a human whether or not that row has been written yet.
                reasons.append(f"invoice_unattributed:{payable.attribution_problem}")
        view.attention = sorted(set(reasons))
        view.housekeeping = sorted(set(housekeeping))


def claim_source(observation: Mapping[str, Any], payload: Mapping[str, Any]) -> str:
    """The source of a claim made in a message: the channel it arrived on AND the party who made it."""
    sender = payload["sender"]
    return (f"{observation['source_system']}#"
            f"{sender.get('address') or sender.get('name') or sender['role']}")


def sender_identity(payload: Mapping[str, Any]) -> str | None:
    """WHO sent a message, exactly: the address its own record carries. An IDENTITY, compared
    character for character and never tidied - not a description. Nothing is read from a name, a
    role or an organisation: two contacts at one customer, two docks, and two carriers' drivers are
    different senders. A record that carries no address has NO sender identity (None), and nothing
    is ever matched to None."""
    address = payload["sender"]["address"]
    return address if address.strip() else None


def resolve_stop_key(view: LoadView, item: Mapping[str, Any]) -> str | None:
    """Which stop a claim is about. A record that names the stop keeps it. A claim read from free
    text names only a KIND of stop ("at the shipper"), and that resolves only when the load has
    exactly one stop of that kind — a load with two pickups does not get one picked for it."""
    if item.get("stop_key"):
        return str(item["stop_key"])
    kind = item.get("stop_type")
    if not kind:
        return None
    matches = [key for key, stop in view.stops.items() if stop.value("stop_type") == kind]
    return matches[0] if len(matches) == 1 else None


def resolve_appointment_claim(view: LoadView, item: Mapping[str, Any]) -> dict[str, Any] | None:
    """An appointment claim as a facility-local window on one stop, or None when it cannot be placed.
    A claim read from free text carries a calendar date and a wall-clock time; the FACILITY's zone
    comes from the stop it resolves to, never from the sender. A time stated without an end is a
    window of exactly that instant — nothing is rounded out to a plausible window."""
    if "start_local" in item:
        return dict(item)
    stop_key = resolve_stop_key(view, item)
    stop = view.stops.get(stop_key or "")
    zone = stop.value("facility_timezone") if stop is not None else None
    if stop_key is None or not zone:
        return None
    day = item["local_date"]
    return {"stop_key": stop_key, "start_local": f"{day}T{item['start_time']}",
            "end_local": f"{day}T{item['end_time'] or item['start_time']}", "timezone": zone,
            "status": None}


def load_currency(view: LoadView) -> str | None:
    """The one currency the system of record carries this load's sell rate in, or None."""
    currencies = {f.value.currency for f in view.load.field_of("sell").facts
                  if isinstance(f.value, DirectedMoney)}
    return next(iter(currencies)) if len(currencies) == 1 else None


def resolve_claim_money(view: LoadView,
                        item: Mapping[str, Any]) -> tuple[DirectedMoney | None, str | None]:
    """An amount claimed in a message, as money owed to a carrier, and whether it must be WEAKENED.

    A claim that states its currency keeps it. One that does not ("detention 175") is read in the
    currency the system of record carries this load's sell rate in — and because that currency was
    ASSUMED, not read, the resulting fact is weakened to `MODEL_INFERRED`: retained, and unable to
    gate or dispute anything. Whether an unstated currency may be assumed at all is NEEDS VALIDATION
    (debt `P9-D12`). With no single load currency there is no amount."""
    if item.get("amount_minor") is None:
        return None, None
    if item.get("currency"):
        return carrier_owed(item["amount_minor"], item["currency"]), None
    assumed = load_currency(view)
    if assumed is None:
        return None, None
    return carrier_owed(item["amount_minor"], assumed), MODEL_INFERRED


_ATTRIBUTION_REASONS: dict[str, str] = {
    "CARRIER_NOT_STATED": "it prints no carrier MC and names no movement",
    "CARRIER_UNRECOGNIZED": "it prints carrier MC {mc!r}, which names no carrier this brokerage "
                            "has recorded (an MC is matched on its exact digits; a shorter, "
                            "longer or different number is never matched)",
    "CARRIER_NOT_ON_LOAD": "it prints carrier MC {mc!r}, a carrier this brokerage knows that "
                           "moves no movement of this load",
    "CARRIER_AMBIGUOUS": "it prints carrier MC {mc!r}, which fits more than one movement of this "
                         "load",
    "MOVEMENT_UNKNOWN": "{human} placed it on movement {key!r}, which this load does not have",
}


def movement_candidates(view: LoadView) -> list[dict[str, Any]]:
    """This load's movements and who moves each — what a human choosing a movement is shown."""
    out: list[dict[str, Any]] = []
    for key in sorted(view.movements):
        movement = view.movements[key]
        carrier = view.carriers.get(movement.carrier_id or "")
        out.append({"movement_key": key, "movement_id": movement.entity_id,
                    "carrier_name": carrier.value("legal_name") if carrier else None,
                    "carrier_mc": carrier.value("mc_number") if carrier else None})
    return out


def explain_unattributed_invoice(view: LoadView, payable: CarrierPayable) -> dict[str, Any]:
    """Everything a human needs to place an invoice Neyma could not: which document, what is missing
    or ambiguous, what evidence there is, and what would clear it. No amount appears here."""
    number = payable.value("invoice_number")
    document = next((d for d in view.documents.values()
                     if d.entity_id == payable.document_id), None)
    reason = _ATTRIBUTION_REASONS[payable.attribution_problem or "CARRIER_NOT_STATED"].format(
        mc=payable.stated_carrier_mc, key=payable.stated_movement_key,
        human=payable.attributed_by)
    candidates = movement_candidates(view)
    listed = "; ".join(
        f"{c['movement_key']} {c['carrier_name'] or 'carrier not recorded'} "
        f"({c['carrier_mc'] or 'no MC recorded'})" for c in candidates) or "none recorded"
    return {
        "invoice_number": number, "problem": payable.attribution_problem,
        "stated_carrier_mc": payable.stated_carrier_mc,
        "document_ref": document.ref if document else None,
        "evidence_id": document.evidence_id if document else None,
        "observation_id": payable.origin_observation_id, "candidates": candidates,
        "summary": (f"Carrier invoice {number} is bound to this load and bills no movement Neyma "
                    f"can name: {reason}. This load's movements: {listed}. It has not been "
                    f"reconciled and nothing is payable on it."),
        "question": (f"Which movement of this load does invoice {number} bill? Attribute it to "
                     f"that movement, or say it is not this load's."),
        "clears_when": ("a recorded human attributes the invoice to a movement of this load, or "
                        "the system of record names the carrier the invoice prints"),
    }


def commitment_expectation_id(tenant: str, load_ref: str, commitment: Mapping[str, Any]) -> str:
    return stable_id("exp", tenant, load_ref, "counterparty_update",
                     commitment["observation_id"], commitment["index"])


def counterparty_updates(view: LoadView) -> list[dict[str, Any]]:
    """Bound inbound records from the carrier's side of this load, in arrival order. NOT what
    answers a promise: a promise is answered only by its own sender's word (`sender_identity`)."""
    out: list[dict[str, Any]] = []
    for observation in view.observations:
        parsed = observation["parsed"]
        payload = parsed["payload"]
        if parsed["kind"] == "message" and payload["direction"] == "inbound" \
                and payload["sender"]["role"] in CARRIER_SIDE_ROLES:
            out.append(observation)
    return out


def load_entity_ref(load_id: str) -> str:
    return entity_ref(LOAD, load_id)
