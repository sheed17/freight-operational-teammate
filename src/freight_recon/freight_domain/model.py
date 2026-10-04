"""P9 — the canonical freight-domain model: entities, field-level provenance, money and time.

The names, relationships and lifecycle vocabularies here are those of
`docs/specifications/domain-entities/registry.md` and its family files. A name that is not in that
registry does not belong in this module.

### AUTHORITY IS FIELD-LEVEL, NEVER WHOLE-RECORD. An entity is a set of `Field`s, and a `Field` is the
append-only history of what each source said about one attribute. A Carrier Movement's linehaul can be
`SYSTEM_IMPORTED` from the TMS while its driver's phone is `MODEL_EXTRACTED` from a text message; no
one system is authoritative for the record.

### CONFLICTING IS NOT ABSENT IS NOT UNKNOWN (CD-20). A `Field` reports one of the kernel's five
evidence conditions and never flattens a disagreement into a value:

    absent        no source has said anything
    unknown       we know we could not observe it, or a rule we need has not been supplied
    consistent    every source's latest statement agrees
    conflicting   sources disagree, or an open Conflict freezes the field — NO value is offered
    stale         the only statement predates a later one from the same source

### A FACT IS APPENDED, NEVER REWRITTEN. A later statement from the same source supersedes the earlier
one and the earlier one is retained. A machine statement never overwrites an `OWNER_ASSERTED` one
(R-P3); if it disagrees, the field is conflicting and the owner's value is preserved.

### MONEY ALWAYS HAS A DIRECTION (CD-17). `DirectedMoney` is integer minor units, an ISO-4217 code, a
direction and a kind. A bare amount cannot be constructed.

### TIME KEEPS ITS TIMEZONE. Every fact carries a UTC instant and the originating IANA zone; an
appointment window is a facility-local wall-clock reading plus the facility's zone.

### THE CARDINALITIES ARE NOT COLLAPSED (V-21 — OPEN, NEEDS VALIDATION). Customer Order, Brokerage
Load, Carrier Movement, Leg and Stop are distinct entities with their own ids. Each child carries its
parent's id (Load.order_id, Movement.load_id, Leg.movement_id, Stop.leg_id, Appointment.stop_id), so a
1:N discovery later is additive. Nothing here assumes one movement per load.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, ClassVar

from ..fingerprint import Money
from .foundation import EvidenceCondition, as_class, may_gate_consequential_action

#: The namespace every canonical entity id is derived in. Ids are derived from the Observation that
#: caused the entity to exist — never from an outside reference, which is a name and not an identity.
ENTITY_NAMESPACE = uuid.UUID("6f1d2c4e-9a3b-4d57-8f21-0b7c5e9a1d33")

MONEY_DIRECTIONS: tuple[str, ...] = ("IN", "OUT", "QUOTED")
MONEY_KINDS: tuple[str, ...] = (
    "owed_to_customer", "owed_by_customer", "owed_to_carrier", "paid", "received",
    "quoted_uncommitted",
)


class DomainModelError(RuntimeError):
    """A structurally impossible domain state was requested. Fail closed."""


def entity_id(tenant: str, entity_type: str, *seed: object) -> str:
    """A deterministic, opaque, tenant-scoped canonical id."""
    return str(uuid.uuid5(ENTITY_NAMESPACE, "|".join([tenant, entity_type, *map(str, seed)])))


def entity_ref(entity_type: str, entity_id_: str) -> str:
    return f"{entity_type}:{entity_id_}"


@dataclass(frozen=True)
class DirectedMoney:
    """`amount_minor` + `currency` + `money_direction` + `money_kind`. Floats are refused by the
    kernel's `Money`, which this wraps rather than re-implements."""

    amount_minor: int
    currency: str
    direction: str
    kind: str

    def __post_init__(self) -> None:
        Money(self.amount_minor, self.currency)
        if self.direction not in MONEY_DIRECTIONS:
            raise DomainModelError(
                f"money_direction {self.direction!r} is not one of {list(MONEY_DIRECTIONS)} (CD-17)")
        if self.kind not in MONEY_KINDS:
            raise DomainModelError(
                f"money_kind {self.kind!r} is not one of {list(MONEY_KINDS)} (CD-17)")

    def as_document(self) -> dict[str, Any]:
        return {"amount_minor": self.amount_minor, "currency": self.currency,
                "money_direction": self.direction, "money_kind": self.kind}

    def display(self) -> str:
        sign = "-" if self.amount_minor < 0 else ""
        whole, cents = divmod(abs(self.amount_minor), 100)
        return f"{sign}{self.currency} {whole:,}.{cents:02d}"


def carrier_owed(amount_minor: int, currency: str) -> DirectedMoney:
    """What we owe a carrier: money OUT."""
    return DirectedMoney(amount_minor, currency, "OUT", "owed_to_carrier")


def customer_owes(amount_minor: int, currency: str) -> DirectedMoney:
    """What a customer owes us: money IN."""
    return DirectedMoney(amount_minor, currency, "IN", "owed_by_customer")


@dataclass(frozen=True)
class Fact:
    """One source's statement about one field, with how it came to be believed and where from."""

    value: Any
    provenance_class: str
    observation_id: str
    source_system: str
    as_of: str                       # UTC instant the statement is about
    originating_timezone: str
    received_at: str                 # UTC instant Neyma received it
    evidence_id: str | None = None
    decision_ref: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "provenance_class", as_class(self.provenance_class).value)

    @property
    def may_gate(self) -> bool:
        """Whether a consequential gate may READ this fact. `MODEL_INFERRED` never may."""
        return may_gate_consequential_action(self.provenance_class)

    def as_document(self) -> dict[str, Any]:
        value = self.value.as_document() if isinstance(self.value, DirectedMoney) else self.value
        return {"value": value, "provenance_class": self.provenance_class,
                "observation_id": self.observation_id, "source_system": self.source_system,
                "as_of": self.as_of, "originating_timezone": self.originating_timezone,
                "evidence_id": self.evidence_id, "decision_ref": self.decision_ref}


def _comparable(value: Any) -> Any:
    return value.as_document() if isinstance(value, DirectedMoney) else value


@dataclass
class Field:
    """The append-only history of one attribute, and its evidence condition."""

    name: str
    facts: list[Fact] = field(default_factory=list)
    unknown_reason: str | None = None
    conflict_id: str | None = None        # an OPEN M7 Conflict freezing this field
    # Whether two sources' mutually exclusive statements about this field are a DISPUTE. A field
    # that is not contested keeps each source's statement side by side: two honest clocks reporting
    # an arrival four minutes apart are not contradicting each other.
    contested: bool = False

    def add(self, fact: Fact) -> None:
        self.facts.append(fact)

    def mark_unknown(self, reason: str) -> None:
        self.unknown_reason = reason

    def latest_by_source(self) -> dict[str, Fact]:
        """Each source's latest statement. Within one source a later `as_of` supersedes; a late
        arrival carrying an EARLIER `as_of` is stale and does not regress the source's statement."""
        latest: dict[str, Fact] = {}
        for fact in self.facts:
            current = latest.get(fact.source_system)
            if current is None or (fact.as_of, fact.received_at) >= (current.as_of,
                                                                    current.received_at):
                latest[fact.source_system] = fact
        return latest

    def stale_facts(self) -> list[Fact]:
        latest = self.latest_by_source()
        return [f for f in self.facts if latest[f.source_system] is not f]

    def owner_fact(self) -> Fact | None:
        owned = [f for f in self.facts if f.provenance_class == "OWNER_ASSERTED"]
        return max(owned, key=lambda f: (f.as_of, f.received_at)) if owned else None

    def gating_facts(self) -> list[Fact]:
        """The latest statements a consequential read may use — a guess is not among them."""
        return [f for f in self.latest_by_source().values() if f.may_gate]

    def answered_by_owner(self, fact: Fact) -> bool:
        """Whether an owner's assertion already ANSWERED this statement.

        A recorded human decided the field knowing everything Neyma had then been told, so what was
        said before she decided no longer disputes her. Neither does a source that merely REPEATS,
        afterwards, what it had already said — a system of record nobody has updated yet is the same
        statement arriving again, not a new one. A source that says something NEW after she decided
        is a new dispute: her value is preserved and a human is asked again (R-P3)."""
        owner = self.owner_fact()
        if owner is None or fact is owner:
            return False
        if fact.received_at <= owner.received_at:
            return True
        earlier = [f for f in self.facts if f.source_system == fact.source_system
                   and f.received_at <= owner.received_at]
        if not earlier:
            return False
        prior = max(earlier, key=lambda f: (f.as_of, f.received_at))
        return repr(_comparable(prior.value)) == repr(_comparable(fact.value))

    def disagreement(self) -> list[Fact]:
        """The latest statements when they are mutually exclusive, else empty. Only a CONTESTED field
        can be in dispute, and only statements that may gate take part: a guess is retained as an
        observation and cannot dispute a fact. A statement an owner has already answered takes no
        part either — it is retained in the history, and it is settled."""
        if not self.contested:
            return []
        gating = [f for f in self.gating_facts() if not self.answered_by_owner(f)]
        distinct = {repr(_comparable(f.value)) for f in gating}
        return sorted(gating, key=lambda f: (f.as_of, f.source_system)) if len(distinct) > 1 else []

    @property
    def condition(self) -> str:
        if self.conflict_id is not None or self.disagreement():
            return EvidenceCondition.CONFLICTING.value
        if not self.facts:
            return (EvidenceCondition.UNKNOWN.value if self.unknown_reason
                    else EvidenceCondition.ABSENT.value)
        if not self.gating_facts():
            # Something was said, but only as a guess: nothing a consequential read may rest on.
            return EvidenceCondition.UNKNOWN.value
        return EvidenceCondition.CONSISTENT.value

    @property
    def current(self) -> Fact | None:
        """The believed statement, ONLY when the field is consistent. A conflicting field offers no
        value — except that an owner's assertion is preserved and never machine-overwritten."""
        owner = self.owner_fact()
        if owner is not None:
            return owner
        if self.condition != EvidenceCondition.CONSISTENT.value:
            return None
        return max(self.gating_facts(), key=lambda f: (f.as_of, f.received_at))

    @property
    def value(self) -> Any:
        current = self.current
        return current.value if current is not None else None

    def as_document(self) -> dict[str, Any]:
        current = self.current
        return {
            "condition": self.condition,
            "value": _comparable(current.value) if current is not None else None,
            "provenance_class": current.provenance_class if current is not None else None,
            "unknown_reason": self.unknown_reason,
            "conflict_id": self.conflict_id,
            "history": [f.as_document() for f in self.facts],
        }


@dataclass
class Entity:
    """A canonical domain entity: an opaque tenant-scoped id and a closed set of fields."""

    ENTITY_TYPE: ClassVar[str] = ""
    FIELDS: ClassVar[tuple[str, ...]] = ()
    #: The fields on which disagreeing sources are a Conflict a human must resolve.
    CONTESTED: ClassVar[tuple[str, ...]] = ()

    tenant_id: str
    entity_id: str
    origin_observation_id: str
    fields: dict[str, Field] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.tenant_id or "").strip():
            raise DomainModelError(
                f"a {self.ENTITY_TYPE} without a tenant_id cannot exist (CD-19): tenant is the first "
                f"component of every key.")
        for name in self.FIELDS:
            self.fields.setdefault(name, Field(name, contested=name in self.CONTESTED))

    @property
    def ref(self) -> str:
        return entity_ref(self.ENTITY_TYPE, self.entity_id)

    def field_of(self, name: str) -> Field:
        if name not in self.FIELDS:
            raise DomainModelError(
                f"{self.ENTITY_TYPE} has no field {name!r}; its canonical fields are "
                f"{list(self.FIELDS)}. A field the registry does not name is not added here.")
        return self.fields[name]

    def observe(self, name: str, fact: Fact) -> None:
        self.field_of(name).add(fact)

    def value(self, name: str) -> Any:
        return self.field_of(name).value

    def condition(self, name: str) -> str:
        return self.field_of(name).condition

    def links(self) -> dict[str, Any]:
        """The entity's relationship ids (each FK direction explicit). Overridden per entity."""
        return {}

    def as_document(self) -> dict[str, Any]:
        return {
            "entity_type": self.ENTITY_TYPE, "tenant_id": self.tenant_id,
            "entity_id": self.entity_id, "origin_observation_id": self.origin_observation_id,
            "links": self.links(),
            "fields": {name: self.fields[name].as_document() for name in self.FIELDS},
        }


# --------------------------------------------------------------------------- party (family 01)

@dataclass
class Organization(Entity):
    """E1 — the brokerage itself: the tenant boundary. Provisioned, not transitioned."""

    ENTITY_TYPE: ClassVar[str] = "organization"
    FIELDS: ClassVar[tuple[str, ...]] = ("legal_name",)


@dataclass
class Customer(Entity):
    """E2 — a party that owes us (money IN). A name match never confirms identity."""

    ENTITY_TYPE: ClassVar[str] = "customer"
    FIELDS: ClassVar[tuple[str, ...]] = ("legal_name",)


@dataclass
class CustomerContact(Entity):
    """E3 — a human at a Customer. Their assertion is a counterparty claim, never authority."""

    ENTITY_TYPE: ClassVar[str] = "customer_contact"
    FIELDS: ClassVar[tuple[str, ...]] = ("name", "email", "phone", "role")
    customer_id: str = ""

    def links(self) -> dict[str, Any]:
        return {"customer_id": self.customer_id}


@dataclass
class Carrier(Entity):
    """E5 — a party that moves freight and whom we pay (money OUT). Confirmed on MC or DOT."""

    ENTITY_TYPE: ClassVar[str] = "carrier"
    FIELDS: ClassVar[tuple[str, ...]] = ("legal_name", "mc_number", "dot_number")


@dataclass
class CarrierContact(Entity):
    """E6 — a dispatcher at a Carrier. "You approved the detention" from them is a fraud signal."""

    ENTITY_TYPE: ClassVar[str] = "carrier_contact"
    FIELDS: ClassVar[tuple[str, ...]] = ("name", "email", "phone", "role")
    carrier_id: str = ""

    def links(self) -> dict[str, Any]:
        return {"carrier_id": self.carrier_id}


@dataclass
class Driver(Entity):
    """E7 — the human executing a movement. A driver's "delivered" is a claim, not a delivery proof."""

    ENTITY_TYPE: ClassVar[str] = "driver"
    FIELDS: ClassVar[tuple[str, ...]] = ("name", "phone")
    carrier_id: str = ""

    def links(self) -> dict[str, Any]:
        return {"carrier_id": self.carrier_id}


# --------------------------------------------------------------------------- load family (03)

@dataclass
class CustomerOrder(Entity):
    """E10 — the customer's request, before it is a billable load. Not the Brokerage Load."""

    ENTITY_TYPE: ClassVar[str] = "customer_order"
    FIELDS: ClassVar[tuple[str, ...]] = ("customer_po", "commodity")
    customer_id: str | None = None

    def links(self) -> dict[str, Any]:
        return {"customer_id": self.customer_id}


@dataclass
class BrokerageLoad(Entity):
    """E11 — the commercial unit we are paid for. Not the Carrier Movement, not the TMS row."""

    ENTITY_TYPE: ClassVar[str] = "brokerage_load"
    FIELDS: ClassVar[tuple[str, ...]] = ("load_ref", "reported_status", "sell")
    CONTESTED: ClassVar[tuple[str, ...]] = ("sell",)
    order_id: str | None = None           # FK on Load: an order may convert to several loads
    customer_id: str | None = None

    def links(self) -> dict[str, Any]:
        return {"order_id": self.order_id, "customer_id": self.customer_id}


@dataclass
class CarrierMovement(Entity):
    """E12 — one carrier's physical execution of (part of) a load; what is settled with a carrier."""

    ENTITY_TYPE: ClassVar[str] = "carrier_movement"
    # `pre_ratecon_buy` holds every buy figure that is NOT a rate confirmation — a TMS carrier-pay
    # field, a number agreed in a text. V-14 (OPEN): until validated, the rate confirmation is the
    # only authoritative buy rate, so those figures are retained as MODEL_INFERRED observations and
    # can never be read by a consequential gate.
    FIELDS: ClassVar[tuple[str, ...]] = ("reported_status", "carrier_pro", "pre_ratecon_buy")
    load_id: str = ""                      # FK on Movement: a load may be moved by several
    movement_key: str = ""
    carrier_id: str | None = None
    driver_id: str | None = None

    def links(self) -> dict[str, Any]:
        return {"load_id": self.load_id, "carrier_id": self.carrier_id,
                "driver_id": self.driver_id, "movement_key": self.movement_key}


@dataclass
class Leg(Entity):
    """E13 — a segment of a Movement between Stops."""

    ENTITY_TYPE: ClassVar[str] = "leg"
    FIELDS: ClassVar[tuple[str, ...]] = ("sequence",)
    movement_id: str = ""
    leg_key: str = ""

    def links(self) -> dict[str, Any]:
        return {"movement_id": self.movement_id, "leg_key": self.leg_key}


@dataclass
class Stop(Entity):
    """E14 — one scheduled appearance at a facility. Arrival and departure are claims."""

    ENTITY_TYPE: ClassVar[str] = "stop"
    FIELDS: ClassVar[tuple[str, ...]] = (
        "stop_type", "sequence", "facility_name", "facility_timezone", "reported_arrival",
        "reported_departure",
    )
    load_id: str = ""
    leg_id: str | None = None
    stop_key: str = ""

    def links(self) -> dict[str, Any]:
        return {"load_id": self.load_id, "leg_id": self.leg_id, "stop_key": self.stop_key}


@dataclass
class Appointment(Entity):
    """E15 — a time window at a Stop's facility, in the FACILITY's local time. REQUESTED is not
    CONFIRMED (CD-13)."""

    ENTITY_TYPE: ClassVar[str] = "appointment"
    FIELDS: ClassVar[tuple[str, ...]] = ("window", "status")
    CONTESTED: ClassVar[tuple[str, ...]] = ("window",)
    stop_id: str = ""

    def links(self) -> dict[str, Any]:
        return {"stop_id": self.stop_id}


# --------------------------------------------------------------------------- commercial (04)

@dataclass
class RateConfirmation(Entity):
    """E21 — what we agreed to PAY the carrier: the buy, money OUT. Evidence of a payable, not an
    invoice, and not our customer rate."""

    ENTITY_TYPE: ClassVar[str] = "rate_confirmation"
    FIELDS: ClassVar[tuple[str, ...]] = ("ratecon_number", "status", "linehaul", "fuel",
                                         "accessorials", "total")
    CONTESTED: ClassVar[tuple[str, ...]] = ("linehaul", "fuel", "accessorials")
    movement_id: str | None = None
    document_id: str | None = None

    def links(self) -> dict[str, Any]:
        return {"movement_id": self.movement_id, "document_id": self.document_id}


# --------------------------------------------------------------------------- documents (05)

DOC_TYPES: tuple[str, ...] = (
    "POD", "BOL", "RATE_CON", "LUMPER_RECEIPT", "SCALE_TICKET", "COI", "CUSTOMER_INVOICE",
    "CARRIER_INVOICE",
)


@dataclass
class Document(Entity):
    """E22 — the domain wrapper over a foundational Evidence and its binding. The bytes are the
    Evidence; which load it belongs to is an Identity Binding Claim."""

    ENTITY_TYPE: ClassVar[str] = "document"
    FIELDS: ClassVar[tuple[str, ...]] = ("doc_type", "signed", "pages")
    evidence_id: str = ""
    load_id: str | None = None             # None while the binding is ambiguous or absent
    lifecycle_state: str = "RECEIVED"      # L-Doc
    binding_method: str | None = None
    arrivals: list[str] = field(default_factory=list)   # every observation that carried these bytes

    def links(self) -> dict[str, Any]:
        return {"evidence_id": self.evidence_id, "load_id": self.load_id,
                "lifecycle_state": self.lifecycle_state, "binding_method": self.binding_method,
                "arrivals": list(self.arrivals)}


@dataclass(frozen=True)
class DocumentRequirement:
    """E23 — a statement that a load requires document types before a consequential action. In the
    canonical model it is compiled from a Rule; per-customer requirement sets are NEEDS VALIDATION, so
    here it is tenant CONFIGURATION and its absence is `unknown`, never an assumed default."""

    requirement_id: str
    tenant_id: str
    load_id: str
    gate: str                              # the action class the requirement gates
    required_doc_type: str
    state: str                             # SATISFIED | OUTSTANDING | UNKNOWN
    reason: str
    satisfied_by_document_id: str | None = None
    expectation_id: str | None = None

    def as_document(self) -> dict[str, Any]:
        return dict(self.__dict__)


# --------------------------------------------------------------------------- communication (06)

@dataclass
class CommunicationThread(Entity):
    """E25 — a conversation grouping messages. NOT "one load's thread": binding is per message."""

    ENTITY_TYPE: ClassVar[str] = "communication_thread"
    FIELDS: ClassVar[tuple[str, ...]] = ("channel", "subject")
    thread_key: str = ""
    message_ids: list[str] = field(default_factory=list)
    load_ids: list[str] = field(default_factory=list)

    def links(self) -> dict[str, Any]:
        return {"thread_key": self.thread_key, "message_ids": list(self.message_ids),
                "load_ids": sorted(set(self.load_ids))}


@dataclass
class CommunicationMessage(Entity):
    """E26 — one immutable record that a party SAID something. What it asserts is a claim."""

    ENTITY_TYPE: ClassVar[str] = "communication_message"
    FIELDS: ClassVar[tuple[str, ...]] = ("direction", "sender_role", "sender", "subject", "body")
    thread_id: str = ""
    load_id: str | None = None
    quoted_message_external_ids: tuple[str, ...] = ()

    def links(self) -> dict[str, Any]:
        return {"thread_id": self.thread_id, "load_id": self.load_id,
                "quoted_message_external_ids": list(self.quoted_message_external_ids)}


# --------------------------------------------------------------------------- tracking (07)

TRACKING_SIGNALS: tuple[str, ...] = (
    "tracking_provider_position", "driver_assertion", "carrier_assertion", "tms_status",
)

#: The movement-status progression. Used ONLY to notice that one source reports an EARLIER stage at a
#: LATER instant than another source's later stage — a contradiction a human must look at. It ranks
#: nothing and resolves nothing.
TRACKING_PROGRESSION: tuple[str, ...] = (
    "AT_PICKUP", "LOADED", "IN_TRANSIT", "AT_DELIVERY", "DELIVERED",
)


@dataclass
class TrackingEvent(Entity):
    """E27 — an observed movement signal. Source-specific, and never proof of completion."""

    ENTITY_TYPE: ClassVar[str] = "tracking_event"
    FIELDS: ClassVar[tuple[str, ...]] = ("signal", "status", "position")
    load_id: str | None = None
    movement_id: str | None = None
    stop_key: str | None = None

    def links(self) -> dict[str, Any]:
        return {"load_id": self.load_id, "movement_id": self.movement_id,
                "stop_key": self.stop_key}


# --------------------------------------------------------------------------- accessorial (08)

@dataclass
class AccessorialCharge(Entity):
    """E28 — the ASK: a charge beyond the linehaul. Not the Authorization."""

    ENTITY_TYPE: ClassVar[str] = "accessorial_charge"
    FIELDS: ClassVar[tuple[str, ...]] = ("charge_type", "amount", "requesting_party_role")
    CONTESTED: ClassVar[tuple[str, ...]] = ("amount",)
    load_id: str = ""
    movement_id: str | None = None
    lifecycle_state: str = "CLAIMED"       # L-Access
    authorization_id: str | None = None
    counterparty_asserted_authorization: bool = False
    claim_observation_ids: list[str] = field(default_factory=list)

    def links(self) -> dict[str, Any]:
        return {"load_id": self.load_id, "movement_id": self.movement_id,
                "lifecycle_state": self.lifecycle_state,
                "authorization_id": self.authorization_id,
                "counterparty_asserted_authorization": self.counterparty_asserted_authorization,
                "claim_observation_ids": list(self.claim_observation_ids)}


@dataclass(frozen=True)
class AccessorialAuthorization:
    """E29 — the RIGHT to bill or pay an accessorial: who authorized it, how, with what scope.

    ### HUMAN-ONLY (CD-5, ADR-003). The only authorization this build can construct is the
    undocumented one, and it exists only as an `OWNER_ASSERTED` act of a recorded human carrying a
    `decision_ref`. A model cannot create it and a counterparty's claim that it exists is not it.
    Contractually pre-authorized accessorials are NEEDS VALIDATION and are not built."""

    authorization_id: str
    tenant_id: str
    load_id: str
    charge_type: str
    amount_cap: DirectedMoney
    authorized_by: str
    decision_ref: str
    provenance_class: str
    observation_id: str
    lifecycle_state: str = "CONFIRMED"     # L-AccessAuth
    authorization_source: str = "human_assertion"

    def __post_init__(self) -> None:
        if self.provenance_class != "OWNER_ASSERTED":
            raise DomainModelError(
                f"an Accessorial Authorization must be OWNER_ASSERTED; {self.provenance_class!r} "
                f"cannot create one (CD-5, ADR-003). A counterparty's claim that authorization "
                f"exists is a fraud signal, and a model states no facts.")
        if not str(self.authorized_by or "").strip() or not str(self.decision_ref or "").strip():
            raise DomainModelError(
                "an Accessorial Authorization names the human who authorized it and the decision "
                "record behind it. An authorization nobody can be pointed at is not one.")

    def as_document(self) -> dict[str, Any]:
        doc = dict(self.__dict__)
        doc["amount_cap"] = self.amount_cap.as_document()
        return doc


# --------------------------------------------------------------------------- financial (09)

#: What may place a carrier's invoice on a movement. A document's own movement key, an MC that
#: resolves EXACTLY through this brokerage's External Entity Mapping to the carrier of exactly one
#: movement of the load, or a recorded human's act. Nothing else — and never a model.
ATTRIBUTION_BASES: tuple[str, ...] = ("MOVEMENT_KEY", "CARRIER_MC_EXACT", "HUMAN_ASSERTION")

#: Why an invoice bound to a load could not be placed on one of its movements.
#:   CARRIER_NOT_STATED     the invoice prints no MC and names no movement
#:   CARRIER_UNRECOGNIZED   the MC as printed names no carrier this brokerage has recorded
#:   CARRIER_NOT_ON_LOAD    it names a recorded carrier that moves no movement of this load
#:   CARRIER_AMBIGUOUS      it fits more than one movement, or the MC names more than one carrier
#:   MOVEMENT_UNKNOWN       a human placed it on a movement this load does not have
ATTRIBUTION_PROBLEMS: tuple[str, ...] = (
    "CARRIER_NOT_STATED", "CARRIER_UNRECOGNIZED", "CARRIER_NOT_ON_LOAD", "CARRIER_AMBIGUOUS",
    "MOVEMENT_UNKNOWN",
)


@dataclass
class CustomerInvoice(Entity):
    """E30 — what WE bill the customer: money IN. This build never issues one; it evaluates the
    L-Invoice ELIGIBLE guard and reports why a load is or is not eligible."""

    ENTITY_TYPE: ClassVar[str] = "customer_invoice"
    FIELDS: ClassVar[tuple[str, ...]] = ("total",)
    load_id: str = ""
    lifecycle_state: str = "NOT_ELIGIBLE"
    blockers: tuple[str, ...] = ()

    def links(self) -> dict[str, Any]:
        return {"load_id": self.load_id, "lifecycle_state": self.lifecycle_state,
                "blockers": list(self.blockers)}


@dataclass
class CarrierPayable(Entity):
    """E32 — what WE owe a carrier: money OUT. Created from the carrier's invoice; the Rate
    Confirmation is the evidence of terms, not the payable."""

    ENTITY_TYPE: ClassVar[str] = "carrier_payable"
    FIELDS: ClassVar[tuple[str, ...]] = ("invoice_number", "linehaul", "fuel", "accessorials",
                                         "total")
    CONTESTED: ClassVar[tuple[str, ...]] = ("linehaul", "fuel", "accessorials")
    movement_id: str | None = None
    load_id: str | None = None
    document_id: str | None = None
    lifecycle_state: str = "INVOICE_RECEIVED"      # L-Payable
    duplicate_observation_ids: list[str] = field(default_factory=list)
    # WHICH movement this invoice bills, and how that is known. An invoice bound to a load is not
    # thereby attributed to a carrier: a load may be moved by several, and the paper may be nobody's
    # on this load at all. `attribution_basis` names what placed it; `attribution_problem` is why
    # nothing could. Exactly one of them is set.
    attribution_basis: str | None = None           # one of ATTRIBUTION_BASES
    attribution_problem: str | None = None         # one of ATTRIBUTION_PROBLEMS
    stated_carrier_mc: str | None = None           # the MC as the invoice PRINTS it, or None
    stated_movement_key: str | None = None
    attributed_by: str | None = None               # the human, when a human placed it
    attribution_decision_ref: str | None = None

    def links(self) -> dict[str, Any]:
        return {"movement_id": self.movement_id, "load_id": self.load_id,
                "document_id": self.document_id, "lifecycle_state": self.lifecycle_state,
                "duplicate_observation_ids": list(self.duplicate_observation_ids),
                "attribution_basis": self.attribution_basis,
                "attribution_problem": self.attribution_problem,
                "stated_carrier_mc": self.stated_carrier_mc,
                "attributed_by": self.attributed_by}


# --------------------------------------------------------------------------- derived (11)

@dataclass(frozen=True)
class Discrepancy:
    code: str
    line: str
    expected: DirectedMoney | None
    actual: DirectedMoney | None
    delta_minor: int | None
    authorization: str                      # n/a | UNRESOLVED | AUTHORIZED | EXCEEDS_AUTHORIZATION
    detail: str

    def as_document(self) -> dict[str, Any]:
        return {"code": self.code, "line": self.line,
                "expected": self.expected.as_document() if self.expected else None,
                "actual": self.actual.as_document() if self.actual else None,
                "delta_minor": self.delta_minor, "authorization": self.authorization,
                "detail": self.detail}


@dataclass(frozen=True)
class FinancialReconciliationResult:
    """E40 — a DERIVED comparison of expected against actual financials for a movement. Never
    authoritative money, and never a silent adjustment: a mismatch is a Conflict or an Exception a
    human owns."""

    reconciliation_id: str
    tenant_id: str
    load_id: str
    movement_id: str
    status: str                             # L-Recon: COMPUTED | RECONCILED | DISCREPANT
    expected: DirectedMoney | None
    expected_condition: str
    expected_basis: str
    actual: DirectedMoney | None
    actual_condition: str
    discrepancies: tuple[Discrepancy, ...]
    source_observation_ids: tuple[str, ...]  # CD-18: every source financial record pinned
    # WHICH invoice was compared. A movement can be billed twice, and a result that named only the
    # movement would let one invoice's verdict be read as another's.
    payable_id: str | None = None

    def as_document(self) -> dict[str, Any]:
        return {
            "reconciliation_id": self.reconciliation_id, "tenant_id": self.tenant_id,
            "load_id": self.load_id, "movement_id": self.movement_id,
            "payable_id": self.payable_id, "status": self.status,
            "expected": self.expected.as_document() if self.expected else None,
            "expected_condition": self.expected_condition, "expected_basis": self.expected_basis,
            "actual": self.actual.as_document() if self.actual else None,
            "actual_condition": self.actual_condition,
            "discrepancies": [d.as_document() for d in self.discrepancies],
            "source_observation_ids": list(self.source_observation_ids),
        }


@dataclass(frozen=True)
class OperationalTimelineEntry:
    """E39 — a derived, read-only "what happened, when, why" row. Never a source of truth: it is
    rebuilt from canonical records, and each entry pins the records it was derived from."""

    timeline_entry_id: str
    tenant_id: str
    load_id: str
    at: str                                  # UTC instant the entry is about
    originating_timezone: str
    kind: str
    summary: str
    provenance_class: str | None
    source_refs: tuple[str, ...]
    received_at: str | None = None
    flags: tuple[str, ...] = ()

    def as_document(self) -> dict[str, Any]:
        return {"timeline_entry_id": self.timeline_entry_id, "tenant_id": self.tenant_id,
                "load_id": self.load_id, "at": self.at,
                "originating_timezone": self.originating_timezone, "kind": self.kind,
                "summary": self.summary, "provenance_class": self.provenance_class,
                "source_refs": list(self.source_refs), "received_at": self.received_at,
                "flags": list(self.flags)}
