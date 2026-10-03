"""The Neyma task contracts for model interpretation: what may be asked, and the shape of the answer.

### FOUR TASKS, AND NO GENERAL-PURPOSE CALL. A caller cannot send a prompt. It can ask for one of four
readings, each with a typed request and a strict typed output:

    interpret_message          one freight message      -> MessageInterpretation
    interpret_document_text    one document's text      -> DocumentTextInterpretation
    extract_commitments        one freight message      -> CommitmentExtraction
    propose_entity_candidates  text + supplied load ids -> CandidateProposal

### EVIDENCE FIRST. Every reported item carries `evidence_text`: a verbatim quote from the supplied
content. The application checks that the quote is really there and discards any item whose quote is
not. Confidence is not a field on any extracted fact: it ranks nothing here and authorizes nothing
anywhere.

### THE OUTPUT VOCABULARY HAS NO AUTHORITY IN IT. There is no field in which a model can approve an
accessorial, name a payee, authorize a payment, qualify a carrier, resolve a conflict or bind a
record to a load. `asserts_prior_approval` records that the SENDER claimed an approval; that is a
fraud signal on the charge, never an approval. `provenance` is not a field either: the runtime assigns
it from how a value was obtained (R-P1).

### EVERY REQUEST CARRIES A ROUTE. A `Route` is the routing boundary's statement that language
interpretation is genuinely required and why. The gateway refuses a request whose route says a model
is not needed, so a model call is never a casual default.

The output models are written for strict structured outputs: every field is required, optionality is
an explicit `| None`, and no field carries a default.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Generic, Literal, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict

#: Bumped whenever an output model changes shape. Part of every recording key.
SCHEMA_VERSION = "p9-interpretation-1"


class Task(str, enum.Enum):
    INTERPRET_MESSAGE = "interpret_message"
    INTERPRET_DOCUMENT_TEXT = "interpret_document_text"
    EXTRACT_COMMITMENTS = "extract_commitments"
    PROPOSE_ENTITY_CANDIDATES = "propose_entity_candidates"


class Status(str, enum.Enum):
    OK = "OK"
    SCHEMA_FAILURE = "SCHEMA_FAILURE"          # the reply did not satisfy the typed contract
    PROVIDER_FAILURE = "PROVIDER_FAILURE"      # transport, rate limit, rejection, refusal
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"      # the run's call or token budget is spent; not called
    REPLAY_MISS = "REPLAY_MISS"                # replay-only, and this reading was never recorded


class RoutingViolation(RuntimeError):
    """A model call was requested without a route that says a model is needed. A programming error:
    it is raised, never swallowed into a failed result."""


@dataclass(frozen=True)
class Route:
    """The routing boundary's decision for one piece of work."""

    task: Task
    model_needed: bool
    reason: str


# --------------------------------------------------------------------------- requests

@dataclass(frozen=True)
class MessageRequest:
    """One message as it was captured. `source_id` is the evidence identity every extracted fact
    points back to. `sent_local` is the sender-side wall clock the capture recorded, in `timezone`."""

    route: Route
    source_id: str
    channel: str
    sender_role: str
    sent_local: str
    timezone: str
    subject: str
    body: str
    correlation_id: str | None = None


@dataclass(frozen=True)
class DocumentTextRequest:
    route: Route
    source_id: str
    declared_doc_type: str
    text: str
    correlation_id: str | None = None


@dataclass(frozen=True)
class CandidateOption:
    """One canonical entity the model may choose. `summary` is freight context and carries no money."""

    candidate_id: str
    summary: str


@dataclass(frozen=True)
class CandidateRequest:
    route: Route
    source_id: str
    text: str
    options: tuple[CandidateOption, ...]
    correlation_id: str | None = None


# --------------------------------------------------------------------------- output vocabulary

class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


StopRole = Literal["PICKUP", "DELIVERY", "UNSPECIFIED"]
ChargeType = Literal["DETENTION", "LUMPER", "LAYOVER", "TONU", "REDELIVERY", "DRIVER_ASSIST",
                     "STORAGE", "OTHER"]
DocType = Literal["POD", "BOL", "RATE_CON", "CARRIER_INVOICE", "LUMPER_RECEIPT", "SCALE_TICKET",
                  "COI", "CUSTOMER_INVOICE", "OTHER"]
ReferenceKind = Literal["LOAD_NUMBER", "PO_NUMBER", "PRO_NUMBER", "BOL_NUMBER", "INVOICE_NUMBER",
                        "RATE_CON_NUMBER", "OTHER"]


class StatusObservation(_Strict):
    """Something the sender says HAS happened or IS true of the truck. Not a plan, not an ETA."""

    status: Literal["ARRIVED", "LOADED", "IN_TRANSIT", "DELIVERED"]
    stop: StopRole
    in_quoted_text: bool
    evidence_text: str


class Commitment(_Strict):
    """A promise to the brokerage to communicate or to send something later."""

    actor: Literal["SENDER", "DRIVER", "CARRIER", "CUSTOMER", "FACILITY", "OTHER"]
    promised_action: Literal["STATUS_UPDATE", "SEND_DOCUMENT", "CALL_BACK", "OTHER"]
    time_kind: Literal["RELATIVE_MINUTES", "CLOCK_TIME", "NONE"]
    relative_minutes: int | None
    clock_time_24h: str | None
    day_offset: int | None
    time_text: str | None
    in_quoted_text: bool
    evidence_text: str


class AppointmentObservation(_Strict):
    """An appointment time at a pickup or delivery facility, as the sender states it."""

    stop: StopRole
    appointment_status: Literal["REQUESTED", "CONFIRMED", "RESCHEDULED", "CANCELLED",
                                "UNSPECIFIED"]
    day_offset: int | None
    start_time_24h: str | None
    end_time_24h: str | None
    in_quoted_text: bool
    evidence_text: str


class AccessorialMention(_Strict):
    """A charge beyond the linehaul that the message mentions. A MENTION: it authorizes nothing."""

    charge_type: ChargeType
    charge_label: str
    amount_text: str | None
    currency_code: str | None
    asserts_prior_approval: bool
    approver_named: str | None
    in_quoted_text: bool
    evidence_text: str


class RateMention(_Strict):
    amount_text: str
    currency_code: str | None
    in_quoted_text: bool
    evidence_text: str


class DelayMention(_Strict):
    stop: StopRole
    reason_text: str | None
    in_quoted_text: bool
    evidence_text: str


class DocumentMention(_Strict):
    doc_type: DocType
    presence: Literal["ATTACHED", "PROMISED", "REQUESTED", "MENTIONED"]
    in_quoted_text: bool
    evidence_text: str


class ReferenceMention(_Strict):
    """An identifier exactly as written. It is a candidate reference, never a resolved identity."""

    kind: ReferenceKind
    value: str
    role: Literal["SUBJECT", "CORRECTED_FROM", "CORRECTED_TO", "OTHER"]
    in_quoted_text: bool
    evidence_text: str


class Correction(_Strict):
    """The sender says an earlier statement was wrong."""

    corrects: Literal["LOAD_REFERENCE", "APPOINTMENT", "STATUS", "AMOUNT", "OTHER"]
    evidence_text: str


class MessageInterpretation(_Strict):
    category: Literal["STATUS_UPDATE", "APPOINTMENT", "DOCUMENT_DELIVERY", "ACCESSORIAL_OR_BILLING",
                      "RATE", "CORRECTION", "REQUEST", "OTHER"]
    response_requested: bool
    statuses: list[StatusObservation]
    commitments: list[Commitment]
    appointments: list[AppointmentObservation]
    accessorials: list[AccessorialMention]
    rates: list[RateMention]
    delays: list[DelayMention]
    documents: list[DocumentMention]
    references: list[ReferenceMention]
    corrections: list[Correction]


class CommitmentExtraction(_Strict):
    commitments: list[Commitment]


class ChargeLine(_Strict):
    line_kind: Literal["LINEHAUL", "FUEL", "ACCESSORIAL", "TOTAL"]
    charge_type: ChargeType | None
    amount_text: str
    evidence_text: str


class DocumentTextInterpretation(_Strict):
    doc_type: DocType
    document_number: str | None
    document_number_evidence_text: str | None
    carrier_mc: str | None
    carrier_mc_evidence_text: str | None
    currency_code: str | None
    currency_evidence_text: str | None
    references: list[ReferenceMention]
    charges: list[ChargeLine]


class ProposedCandidate(_Strict):
    """`candidate_id` must be one of the ids the request supplied. Anything else is refused by the
    application. `support` orders a human's queue and confirms nothing."""

    candidate_id: str
    support: Literal["CLEAR", "PARTIAL", "WEAK"]
    evidence_text: str
    reason: str


class CandidateProposal(_Strict):
    candidates: list[ProposedCandidate]


OUTPUT_MODELS: dict[Task, type[BaseModel]] = {
    Task.INTERPRET_MESSAGE: MessageInterpretation,
    Task.INTERPRET_DOCUMENT_TEXT: DocumentTextInterpretation,
    Task.EXTRACT_COMMITMENTS: CommitmentExtraction,
    Task.PROPOSE_ENTITY_CANDIDATES: CandidateProposal,
}


# --------------------------------------------------------------------------- results

@dataclass(frozen=True)
class Usage:
    """Token counts as the provider reported them. The durable source of truth for cost."""

    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(self.input_tokens + other.input_tokens,
                     self.cached_input_tokens + other.cached_input_tokens,
                     self.output_tokens + other.output_tokens,
                     self.reasoning_tokens + other.reasoning_tokens)


T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class InferenceResult(Generic[T]):
    """One reading, or the reason there is none. `output` is None unless `status` is OK. `detail` is
    a short failure code and never contains request content or a credential."""

    task: Task
    status: Status
    output: T | None
    provider: str
    model: str
    interpreted_at: str
    usage: Usage
    attempts: int
    latency_ms: int
    request_digest: str
    served_from: str                 # live | replay | scripted
    detail: str = ""
    debug: str = ""                  # redacted provider message; returned, never logged

    @property
    def ok(self) -> bool:
        return self.status is Status.OK and self.output is not None


class InferenceGateway(Protocol):
    """What freight logic depends on. One provider implements it for production; another could be
    added behind it without a freight module changing."""

    provider: str
    model: str

    def interpret_message(
            self, request: MessageRequest) -> InferenceResult[MessageInterpretation]: ...

    def interpret_document_text(
            self, request: DocumentTextRequest) -> InferenceResult[DocumentTextInterpretation]: ...

    def extract_commitments(
            self, request: MessageRequest) -> InferenceResult[CommitmentExtraction]: ...

    def propose_entity_candidates(
            self, request: CandidateRequest) -> InferenceResult[CandidateProposal]: ...
