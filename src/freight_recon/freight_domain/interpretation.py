"""P9 deep-end 2 — model-backed freight interpretation: a model READS, and this module decides what
the reading may bear.

    raw message / document text
        -> route      (is language interpretation genuinely required? usually it is not)
        -> read       (one typed model reading, through the InferenceGateway)
        -> ground     (every item's evidence quote must really be in the content, or it is dropped)
        -> normalize  (deterministic arithmetic: a deadline, a calendar date, integer minor units)
        -> the SAME structures the freight spine already consumes: a message's `asserts`, a
           document's `extracted` block

Nothing downstream of this module knows a model was involved, and nothing downstream moved: identity,
binding, Conflicts, Expectations, reconciliation and the projection are the P9 spine's, unchanged.

### WHAT A READING MAY BECOME, AND WHAT IT MAY NOT.
  * It becomes a CLAIM with a quoted evidence span: a status a driver reported, a promise to follow
    up, an appointment someone stated, a charge someone mentioned, a rate someone quoted.
  * It never becomes an authorization, a binding, a resolution or an amount anyone is paid. There is
    no code path here that constructs one. "Detention is included per approval from Mike" is recorded
    as the sender's claim that an approval exists — a fraud signal on the charge — and nothing else.
  * A candidate load the model proposes is a `MODEL_INFER` candidate for a human. It can never
    confirm (GR-8), at any stated support, and an id the model was not handed is refused outright.

### THE MODEL DOES NO ARITHMETIC AND PICKS NO IDENTITY. A promise's deadline is the captured send time
plus the duration the model read, computed here. An appointment's date is the send date plus a day
offset, computed here. Money is the digits the model quoted, parsed to integer minor units here, and
refused if those digits are not in the evidence. Which load a record belongs to is the External
Entity Mapping's exact answer first; a model is asked only when that answer is "nothing".

### A FAILED READING CORRUPTS NOTHING. A timeout, a refusal, a malformed reply or an exhausted budget
leaves the record exactly as an uninterpreted record: observed, parsed, bound by its exact
references, asserting nothing — and a named human is told it needs reading.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

from ..inference.contracts import (
    SCHEMA_VERSION,
    CandidateOption,
    CandidateProposal,
    CandidateRequest,
    Commitment,
    DocumentTextInterpretation,
    DocumentTextRequest,
    InferenceGateway,
    InferenceResult,
    MessageInterpretation,
    MessageRequest,
    Route,
    Task,
)
from ..inference.ledger import InferenceLedger, RoutingRecord
from ..inference.prompts import PROMPT_VERSION
from ..inference.recording import content_digest
from .foundation import format_instant
from .history import InboundRecord, utc_datetime

INTERPRETER_VERSION = "p9-interpreter-1"

#: Document types whose TEXT carries fields the spine needs. A POD or a BOL is used or refused on its
#: signature, pages and legibility — envelope facts, decided without reading a word.
TEXT_BEARING_DOC_TYPES: tuple[str, ...] = ("RATE_CON", "CARRIER_INVOICE")

READ = "READ"
FAILED = "FAILED"
NOT_NEEDED = "NOT_NEEDED"
NOT_LANGUAGE = "not_language"

#: The most candidate loads handed to a model at once, most recently created first.
MAX_CANDIDATE_OPTIONS = 25
#: A promise or appointment further out than this was misread; it is dropped, not scheduled.
MAX_COMMITMENT_HORIZON = timedelta(days=14)
MAX_APPOINTMENT_DAY_OFFSET = 30

_STATUS_BY_STOP: dict[tuple[str, str], tuple[str, str | None]] = {
    ("ARRIVED", "PICKUP"): ("AT_PICKUP", "PICKUP"),
    ("ARRIVED", "DELIVERY"): ("AT_DELIVERY", "DELIVERY"),
    ("LOADED", "PICKUP"): ("LOADED", "PICKUP"),
    ("LOADED", "UNSPECIFIED"): ("LOADED", "PICKUP"),
    ("IN_TRANSIT", "PICKUP"): ("IN_TRANSIT", None),
    ("IN_TRANSIT", "DELIVERY"): ("IN_TRANSIT", None),
    ("IN_TRANSIT", "UNSPECIFIED"): ("IN_TRANSIT", None),
    ("DELIVERED", "DELIVERY"): ("DELIVERED", "DELIVERY"),
    ("DELIVERED", "UNSPECIFIED"): ("DELIVERED", "DELIVERY"),
}


# ================================================================================= routing

def route_content(record: InboundRecord) -> Route:
    """Whether reading this record's CONTENT needs a model. It needs one only when the record is
    language nobody has structured yet. Everything a system of record, a tracking feed, a portal or
    an authenticated human sends is already structured and never reaches a model."""
    payload = record.payload if isinstance(record.payload, Mapping) else {}
    if record.kind == "message":
        task = Task.INTERPRET_MESSAGE
        if "asserts" in payload:
            return Route(task, False, "pre_structured")
        if payload.get("direction") != "inbound":
            return Route(task, False, "not_an_inbound_message")
        if not str(payload.get("body") or "").strip():
            return Route(task, False, "empty_body")
        return Route(task, True, "inbound_free_text")
    if record.kind == "document":
        task = Task.INTERPRET_DOCUMENT_TEXT
        if payload.get("extracted"):
            return Route(task, False, "pre_structured")
        if str(payload.get("doc_type") or "").upper() not in TEXT_BEARING_DOC_TYPES:
            return Route(task, False, "document_type_needs_no_text_fields")
        if not payload.get("legible", True):
            return Route(task, False, "illegible")
        if not str(payload.get("content") or "").strip():
            return Route(task, False, "empty_text")
        return Route(task, True, "financial_document_text")
    return Route(Task.INTERPRET_MESSAGE, False, "structured_source")


def route_correlation(*, kind: str, bound_exactly: bool, deterministic_candidates: int,
                      options: int) -> Route:
    """Whether CORRELATING this record needs a model. Exact, tenant-scoped reference resolution
    always goes first, and whatever it produced stands: an exact bind, or a deterministic ambiguity a
    human owns. A model is asked only when exact resolution produced nothing at all."""
    task = Task.PROPOSE_ENTITY_CANDIDATES
    if bound_exactly:
        return Route(task, False, "exact_reference")
    if deterministic_candidates:
        return Route(task, False, "deterministic_candidates_stand")
    if kind not in ("message", "document"):
        return Route(task, False, "structured_source")
    if not options:
        return Route(task, False, "no_loads_to_propose")
    return Route(task, True, "no_reference_resolved")


# ================================================================================= grounding

@dataclass(frozen=True)
class Span:
    """Where a quote sits in the supplied content."""

    where: str                         # body | subject | text
    start: int
    end: int
    text: str

    def as_document(self) -> dict[str, Any]:
        return {"where": self.where, "start": self.start, "end": self.end, "text": self.text}


_FOLD = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-",
         "\u2014": "-"}


def _normalized(text: str) -> tuple[str, list[int]]:
    """`text` lower-cased with typographic quotes and dashes folded and whitespace runs collapsed,
    plus, for each normalized character, the index it came from."""
    out: list[str] = []
    index: list[int] = []
    pending_space = False
    for position, char in enumerate(text):
        char = _FOLD.get(char, char)
        if char.isspace():
            pending_space = bool(out)
            continue
        if pending_space:
            out.append(" ")
            index.append(position - 1)
            pending_space = False
        for piece in char.lower():
            out.append(piece)
            index.append(position)
    return "".join(out), index


def find_quote(quote: str, content: str) -> tuple[int, int] | None:
    """The span of `quote` in `content`, tolerant only of case, whitespace and typographic quotes. A
    paraphrase, an elision or an invented sentence is not found — and is therefore not evidence."""
    needle, _ = _normalized(quote.strip().strip("\"'"))
    if len(needle.replace(" ", "")) < 2:
        return None
    haystack, index = _normalized(content)
    at = haystack.find(needle)
    if at < 0:
        return None
    return index[at], index[at + len(needle) - 1] + 1


def ground(quote: str | None, *, body: str, subject: str = "") -> Span | None:
    """Locate an evidence quote in a message's body, then its subject."""
    if not quote:
        return None
    for where, content in (("body", body), ("subject", subject)):
        found = find_quote(quote, content)
        if found is not None:
            return Span(where, found[0], found[1], content[found[0]:found[1]])
    return None


def _contains(value: str, text: str) -> bool:
    needle, _ = _normalized(value)
    haystack, _ = _normalized(text)
    return bool(needle) and needle in haystack


_QUOTE_HEADER = re.compile(
    r"^\s*(-{2,}\s*(original|forwarded)\s+message\s*-{2,}|begin forwarded message:?"
    r"|on\s.{0,200}\bwrote:)\s*$", re.IGNORECASE)
_MAIL_HEADER = re.compile(r"^\s*(sent|date|to|subject):", re.IGNORECASE)
_INLINE_QUOTE = re.compile(r"(?<![-=<>])(?:^|\s)>\s")


def quoted_regions(body: str) -> list[tuple[int, int]]:
    """The character ranges of `body` that are quoted or forwarded material, by structure alone: a
    `>` quote marker, or everything after a reply / forward header. This is the deterministic half of
    "a quoted promise is not a new promise"; the model's own reading is the other half, and either
    one is enough to stop a second obligation being created."""
    regions: list[tuple[int, int]] = []
    lines = body.splitlines(keepends=True)
    offset = 0
    for number, line in enumerate(lines):
        stripped = line.strip()
        forwarded_header = (stripped.lower().startswith("from:")
                            and any(_MAIL_HEADER.match(later) for later in lines[number + 1:
                                                                                 number + 5]))
        if _QUOTE_HEADER.match(stripped) or forwarded_header:
            regions.append((offset, len(body)))
            break
        if line.lstrip().startswith(">"):
            regions.append((offset, offset + len(line)))
        else:
            marker = _INLINE_QUOTE.search(line)
            if marker is not None:
                regions.append((offset + marker.start(), offset + len(line)))
        offset += len(line)
    return regions


def _in_regions(span: Span, regions: Sequence[tuple[int, int]]) -> bool:
    return span.where == "body" and any(start < span.end and span.start < end
                                        for start, end in regions)


# ================================================================================= arithmetic

_AMOUNT = re.compile(r"^\$?\s*(\d{1,3}(?:,\d{3})+|\d+)(\.\d{1,2})?$")
_CLOCK = re.compile(r"^(\d{1,2}):(\d{2})$")
_ISO_CURRENCY = re.compile(r"^[A-Z]{3}$")


def parse_amount_minor(amount_text: str | None) -> int | None:
    """Integer minor units from an amount exactly as written, or None. Deliberately narrow: digits,
    optional thousands commas, optional cents, an optional leading `$`. "1.2k", "about 200" and
    "two fifty" are not parsed — an amount this cannot read exactly is not an amount it guesses."""
    if amount_text is None:
        return None
    match = _AMOUNT.match(amount_text.strip())
    if match is None:
        return None
    try:
        value = Decimal(match.group(1).replace(",", "") + (match.group(2) or ""))
    except InvalidOperation:
        return None
    minor = int(value * 100)
    return minor if 0 < minor < 10 ** 11 else None


def _clock(value: str | None) -> tuple[int, int] | None:
    match = _CLOCK.match((value or "").strip())
    if match is None:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    return (hour, minute) if hour < 24 and minute < 60 else None


def sent_local(as_of_utc: str, zone: str) -> datetime:
    return utc_datetime(as_of_utc).astimezone(ZoneInfo(zone))


def commitment_deadline(item: Commitment, *, as_of_utc: str, zone: str) -> str | None:
    """When a promise falls due, in UTC — computed here from the captured send time and the duration
    or clock time the model READ. None when no time was given, or when what was read does not
    describe a moment after the message was sent."""
    sent = utc_datetime(as_of_utc)
    if item.time_kind == "RELATIVE_MINUTES":
        if item.relative_minutes is None or item.relative_minutes <= 0:
            return None
        due = sent + timedelta(minutes=item.relative_minutes)
    elif item.time_kind == "CLOCK_TIME":
        clock = _clock(item.clock_time_24h)
        offset = item.day_offset or 0
        if clock is None or offset < 0:
            return None
        local_day = sent.astimezone(ZoneInfo(zone)).date() + timedelta(days=offset)
        due = datetime(local_day.year, local_day.month, local_day.day, clock[0], clock[1],
                       tzinfo=ZoneInfo(zone)).astimezone(timezone.utc)
    else:
        return None
    if due <= sent or due - sent > MAX_COMMITMENT_HORIZON:
        return None
    return format_instant(due)


# ================================================================================= conversion

@dataclass
class Converted:
    """What a reading became once grounded and normalized."""

    asserts: list[dict[str, Any]] = field(default_factory=list)
    mentions: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    dropped: list[dict[str, str]] = field(default_factory=list)

    def drop(self, item: str, reason: str) -> None:
        self.dropped.append({"item": item, "reason": reason})


def convert_message(output: MessageInterpretation, *, body: str, subject: str, as_of_utc: str,
                    zone: str) -> Converted:
    """A message reading as the spine's `asserts`. Every item must quote the message; a quoted or
    forwarded statement is not a new statement; and every number is computed or parsed here."""
    result = Converted(mentions={"documents": [], "references": [], "corrections": []})
    regions = quoted_regions(body)

    def supported(kind: str, item: Any) -> tuple[Span, bool] | None:
        span = ground(item.evidence_text, body=body, subject=subject)
        if span is None:
            result.drop(kind, "evidence_not_in_content")
            return None
        quoted = bool(getattr(item, "in_quoted_text", False)) or _in_regions(span, regions)
        return span, quoted

    for status in output.statuses:
        found = supported("status", status)
        if found is None:
            continue
        span, quoted = found
        if quoted:
            result.drop("status", "quoted_not_a_new_statement")
            continue
        mapped = _STATUS_BY_STOP.get((status.status, status.stop))
        if mapped is None:
            # "Checked in" with no word about WHERE. Which stop it is would be a guess.
            result.drop("status", "stop_not_stated")
            continue
        result.asserts.append({"type": "status", "status": mapped[0], "stop_key": None,
                               "stop_type": mapped[1], "movement_key": None,
                               "evidence": span.as_document()})

    for commitment in output.commitments:
        found = supported("commitment", commitment)
        if found is None:
            continue
        span, quoted = found
        due_by = commitment_deadline(commitment, as_of_utc=as_of_utc, zone=zone)
        if due_by is None:
            result.drop("commitment", "quoted_without_a_time" if quoted else "time_unresolved")
            continue
        # The deadline rests on the time WORDS: they must be quoted, and be in the message.
        if not commitment.time_text or not _contains(commitment.time_text,
                                                     body + "\n" + subject):
            result.drop("commitment", "time_words_not_in_content")
            continue
        result.asserts.append({
            "type": "commitment", "commitment_kind": commitment.promised_action.lower(),
            "due_by": due_by, "in_quoted_text": quoted, "actor": commitment.actor,
            "time_text": commitment.time_text, "evidence": span.as_document()})

    sent_day = sent_local(as_of_utc, zone).date()
    for appointment in output.appointments:
        found = supported("appointment", appointment)
        if found is None:
            continue
        span, quoted = found
        if quoted:
            result.drop("appointment", "quoted_not_a_new_statement")
            continue
        start = _clock(appointment.start_time_24h)
        end = _clock(appointment.end_time_24h) if appointment.end_time_24h else None
        offset = appointment.day_offset
        if appointment.stop == "UNSPECIFIED":
            result.drop("appointment", "stop_not_stated")
        elif start is None or (appointment.end_time_24h and end is None):
            result.drop("appointment", "time_not_stated")
        elif offset is None or not 0 <= offset <= MAX_APPOINTMENT_DAY_OFFSET:
            result.drop("appointment", "day_not_stated")
        else:
            day = (sent_day + timedelta(days=offset)).isoformat()
            result.asserts.append({
                "type": "appointment", "stop_key": None, "stop_type": appointment.stop,
                "local_date": day, "start_time": f"{start[0]:02d}:{start[1]:02d}",
                "end_time": f"{end[0]:02d}:{end[1]:02d}" if end else None,
                "claimed_status": appointment.appointment_status,
                "evidence": span.as_document()})

    for accessorial in output.accessorials:
        found = supported("accessorial_claim", accessorial)
        if found is None:
            continue
        span, quoted = found
        if quoted:
            result.drop("accessorial_claim", "quoted_not_a_new_statement")
            continue
        amount = _grounded_amount(accessorial.amount_text, body, subject)
        if accessorial.amount_text and amount is None:
            result.drop("accessorial_amount", "amount_not_readable_or_not_in_content")
        charge_type = (accessorial.charge_type if accessorial.charge_type != "OTHER"
                       else _label(accessorial.charge_label))
        result.asserts.append({
            "type": "accessorial_claim", "charge_type": charge_type, "amount_minor": amount,
            "currency": _grounded_currency(accessorial.currency_code, body, subject),
            "movement_key": None,
            "claims_authorization": bool(accessorial.asserts_prior_approval),
            "approver_named": accessorial.approver_named, "evidence": span.as_document()})

    for rate in output.rates:
        found = supported("rate", rate)
        if found is None:
            continue
        span, quoted = found
        amount = _grounded_amount(rate.amount_text, body, subject)
        if quoted:
            result.drop("rate", "quoted_not_a_new_statement")
        elif amount is None:
            result.drop("rate", "amount_not_readable_or_not_in_content")
        else:
            result.asserts.append({
                "type": "rate", "amount_minor": amount,
                "currency": _grounded_currency(rate.currency_code, body, subject),
                "movement_key": None, "evidence": span.as_document()})

    for delay in output.delays:
        found = supported("delay", delay)
        if found is None:
            continue
        span, quoted = found
        if quoted:
            result.drop("delay", "quoted_not_a_new_statement")
            continue
        result.asserts.append({
            "type": "delay", "reason": delay.reason_text or "", "stop_key": None,
            "stop_type": None if delay.stop == "UNSPECIFIED" else delay.stop,
            "evidence": span.as_document()})

    references: list[dict[str, Any]] = []
    for reference in output.references:
        found = supported("reference", reference)
        if found is None:
            continue
        span, quoted = found
        if not _contains(reference.value, body + "\n" + subject):
            result.drop("reference", "value_not_in_content")
            continue
        references.append({"kind": reference.kind, "value": reference.value.strip(),
                           "role": reference.role, "in_quoted_text": quoted,
                           "evidence": span.as_document()})
    result.mentions["references"] = references

    for document in output.documents:
        found = supported("document_mention", document)
        if found is None:
            continue
        span, quoted = found
        result.mentions["documents"].append({
            "doc_type": document.doc_type, "presence": document.presence,
            "in_quoted_text": quoted, "evidence": span.as_document()})

    for correction in output.corrections:
        span = ground(correction.evidence_text, body=body, subject=subject)
        if span is None:
            result.drop("correction", "evidence_not_in_content")
            continue
        if _in_regions(span, regions):
            result.drop("correction", "quoted_not_a_new_statement")
            continue
        result.mentions["corrections"].append({"corrects": correction.corrects,
                                               "evidence": span.as_document()})
        if correction.corrects == "LOAD_REFERENCE":
            fresh = [r for r in references if not r["in_quoted_text"]]
            stated = next((r["value"] for r in fresh if r["role"] == "CORRECTED_TO"), None)
            replaced = next((r["value"] for r in fresh if r["role"] == "CORRECTED_FROM"), None)
            result.asserts.append({"type": "reference_correction", "stated_reference": stated,
                                   "replaces": replaced, "evidence": span.as_document()})
    return result


def _grounded_amount(amount_text: str | None, body: str, subject: str) -> int | None:
    if not amount_text or not _contains(amount_text.strip().lstrip("$").strip(),
                                        body + "\n" + subject):
        return None
    return parse_amount_minor(amount_text)


def _grounded_currency(code: str | None, body: str, subject: str) -> str | None:
    """An ISO code the text itself states, or None. A `$` is not a currency."""
    text = (code or "").strip().upper()
    if not _ISO_CURRENCY.match(text):
        return None
    return text if re.search(rf"\b{text}\b", body + "\n" + subject) else None


def _label(text: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", (text or "OTHER").upper()).strip("_") or "OTHER"


@dataclass
class ConvertedDocument:
    extracted: dict[str, Any] | None = None
    spans: list[dict[str, Any]] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def convert_document(output: DocumentTextInterpretation, *, text: str,
                     declared_doc_type: str) -> ConvertedDocument:
    """A financial document's text as the spine's `extracted` block — or nothing at all.

    All or nothing: a rate confirmation or an invoice whose charges are only PARTLY supported by its
    own text is not partly extracted. One unsupported line makes the whole reading unusable, and a
    human is asked to read the document. Half a set of charges would reconcile to a wrong answer."""
    result = ConvertedDocument()
    number_key = "ratecon_number" if declared_doc_type == "RATE_CON" else "invoice_number"

    def need(value: str | None, evidence: str | None, what: str) -> str | None:
        found = find_quote(evidence or "", text) if evidence else None
        if not value or found is None or not _contains(value, text):
            result.problems.append(f"{what}_not_supported_by_text")
            return None
        result.spans.append({"field": what, "locator": f"char:{found[0]}-{found[1]}",
                             "text": text[found[0]:found[1]]})
        return value.strip()

    if output.doc_type != declared_doc_type:
        result.problems.append("doc_type_disagrees_with_declared_type")
    number = need(output.document_number, output.document_number_evidence_text, number_key)
    currency = need(output.currency_code, output.currency_evidence_text, "currency")
    if currency is not None and not _ISO_CURRENCY.match(currency):
        result.problems.append("currency_not_an_iso_code")
    carrier_mc = None
    if output.carrier_mc:
        carrier_mc = need(output.carrier_mc, output.carrier_mc_evidence_text, "carrier_mc")

    lines: dict[str, list[int]] = {"LINEHAUL": [], "FUEL": [], "TOTAL": []}
    accessorials: dict[str, int] = {}
    for index, charge in enumerate(output.charges):
        found = find_quote(charge.evidence_text, text)
        digits = charge.amount_text.strip().lstrip("$").strip()
        amount = parse_amount_minor(charge.amount_text)
        if found is None or amount is None or not _contains(digits, text[found[0]:found[1]]):
            result.problems.append(f"charge_line_{index}_not_supported_by_text")
            continue
        result.spans.append({"field": f"charge:{charge.line_kind}:{charge.charge_type or ''}",
                             "locator": f"char:{found[0]}-{found[1]}",
                             "text": text[found[0]:found[1]]})
        if charge.line_kind == "ACCESSORIAL":
            if charge.charge_type is None or charge.charge_type in accessorials:
                result.problems.append(f"charge_line_{index}_accessorial_type_unusable")
                continue
            accessorials[charge.charge_type] = amount
        else:
            lines[charge.line_kind].append(amount)
    if len(lines["LINEHAUL"]) != 1:
        result.problems.append("linehaul_not_stated_exactly_once")
    if len(lines["FUEL"]) > 1 or len(lines["TOTAL"]) > 1:
        result.problems.append("fuel_or_total_stated_more_than_once")
    if result.problems:
        return result

    extracted: dict[str, Any] = {
        number_key: number, "carrier_mc": carrier_mc, "movement_key": None, "status": None,
        "currency": currency, "linehaul_minor": lines["LINEHAUL"][0],
        "fuel_minor": lines["FUEL"][0] if lines["FUEL"] else 0,
        "accessorials": [{"charge_type": k, "amount_minor": v}
                         for k, v in sorted(accessorials.items())],
    }
    if lines["TOTAL"]:
        extracted["total_minor"] = lines["TOTAL"][0]
    result.extracted = extracted
    return result


def screen_candidates(proposal: CandidateProposal, *, options: Sequence[CandidateOption],
                      text: str) -> tuple[list[dict[str, Any]], list[str]]:
    """The model's proposed candidates, minus everything it was not entitled to say.

    A candidate survives only if its id is one this request SUPPLIED, exactly, and its evidence quote
    is in the record. An id the model made up, completed, copied out of the message text or carried
    over from anywhere else is REFUSED and reported. The survivors are candidates for a human: they
    are never a binding."""
    supplied = {o.candidate_id for o in options}
    accepted: dict[str, dict[str, Any]] = {}
    refused: list[str] = []
    for candidate in proposal.candidates:
        if candidate.candidate_id not in supplied:
            refused.append("candidate_id_not_supplied")
            continue
        found = find_quote(candidate.evidence_text, text)
        if found is None:
            refused.append("evidence_not_in_content")
            continue
        accepted.setdefault(candidate.candidate_id, {
            "candidate_id": candidate.candidate_id, "support": candidate.support,
            "evidence": {"where": "text", "start": found[0], "end": found[1],
                         "text": text[found[0]:found[1]]}})
    return list(accepted.values()), refused


# ================================================================================= the interpreter

@dataclass
class ContentReading:
    """What reading one record's content came to."""

    route: Route
    status: str                                     # NOT_NEEDED | READ | FAILED
    asserts: list[dict[str, Any]] | None = None
    extracted: dict[str, Any] | None = None
    spans: list[dict[str, Any]] = field(default_factory=list)
    record: dict[str, Any] | None = None            # stored on the Observation's parse output
    failure: str | None = None


@dataclass
class CandidateReading:
    route: Route
    status: str
    candidates: list[dict[str, Any]] = field(default_factory=list)
    refused: list[str] = field(default_factory=list)
    failure: str | None = None


class FreightInterpreter:
    """The freight spine's one way to a model. It routes, asks through the gateway, and hands back
    structures the spine already understands. It holds no tenant and writes nothing."""

    def __init__(self, gateway: InferenceGateway, ledger: InferenceLedger) -> None:
        self._gateway = gateway
        self.ledger = ledger

    @property
    def gateway(self) -> InferenceGateway:
        return self._gateway

    def _lineage(self, task: Task, result: InferenceResult[Any], *, interpreted_at: str,
                 status: str) -> dict[str, Any]:
        return {"task": task.value, "status": status, "provider": result.provider,
                "model": result.model, "schema_version": SCHEMA_VERSION,
                "prompt_version": PROMPT_VERSION, "interpreter_version": INTERPRETER_VERSION,
                "interpreted_at": interpreted_at, "request_digest": result.request_digest}

    def _routed_away(self, route: Route, *, subject_ref: str, at: str, text: str) -> None:
        # A record that was never language is not a task a model was spared; it is counted apart.
        task = NOT_LANGUAGE if route.reason == "structured_source" else route.task.value
        self.ledger.record_routing(RoutingRecord(
            at=at, task=task, model_needed=False, reason=route.reason,
            subject_ref=subject_ref, correlation_id=None, content_digest=content_digest(text)))

    def read(self, record: InboundRecord, parsed: Mapping[str, Any], *, observation_id: str,
             as_of_utc: str, interpreted_at: str) -> ContentReading:
        """Read one record's content, if and only if routing says a model is needed."""
        route = route_content(record)
        payload = parsed["payload"]
        if not route.model_needed:
            self._routed_away(route, subject_ref=observation_id, at=interpreted_at,
                              text=str(payload.get("body") or payload.get("content") or ""))
            return ContentReading(route=route, status=NOT_NEEDED)

        if record.kind == "message":
            zone = parsed["timezone"]
            result = self._gateway.interpret_message(MessageRequest(
                route=route, source_id=observation_id, channel=parsed["channel"],
                sender_role=payload["sender"]["role"],
                sent_local=sent_local(as_of_utc, zone).strftime("%Y-%m-%dT%H:%M"),
                timezone=zone, subject=payload["subject"], body=payload["body"]))
            if not result.ok or result.output is None:
                return self._failed(route, result, interpreted_at)
            converted = convert_message(result.output, body=payload["body"],
                                        subject=payload["subject"], as_of_utc=as_of_utc, zone=zone)
            stored = self._lineage(route.task, result, interpreted_at=interpreted_at, status=READ)
            stored.update({"category": result.output.category,
                           "response_requested": result.output.response_requested,
                           "mentions": converted.mentions, "dropped": converted.dropped})
            return ContentReading(route=route, status=READ, asserts=converted.asserts,
                                  record=stored)

        result = self._gateway.interpret_document_text(DocumentTextRequest(
            route=route, source_id=observation_id, declared_doc_type=payload["doc_type"],
            text=payload["content"]))
        if not result.ok or result.output is None:
            return self._failed(route, result, interpreted_at)
        document = convert_document(result.output, text=payload["content"],
                                    declared_doc_type=payload["doc_type"])
        if document.extracted is None:
            stored = self._lineage(route.task, result, interpreted_at=interpreted_at,
                                   status=FAILED)
            stored["failure"] = "unsupported_by_text:" + ",".join(document.problems)
            return ContentReading(route=route, status=FAILED, record=stored,
                                  failure=stored["failure"])
        stored = self._lineage(route.task, result, interpreted_at=interpreted_at, status=READ)
        stored["spans"] = document.spans
        return ContentReading(route=route, status=READ, extracted=document.extracted,
                              spans=document.spans, record=stored)

    def _failed(self, route: Route, result: InferenceResult[Any],
                interpreted_at: str) -> ContentReading:
        stored = self._lineage(route.task, result, interpreted_at=interpreted_at, status=FAILED)
        stored["failure"] = f"{result.status.value}:{result.detail}"
        return ContentReading(route=route, status=FAILED, record=stored,
                              failure=stored["failure"])

    def propose(self, *, observation_id: str, kind: str, text: str,
                options: Sequence[CandidateOption], bound_exactly: bool,
                deterministic_candidates: int, at: str) -> CandidateReading:
        """Candidate loads for a record that exact resolution could not place. Deterministic
        resolution has ALREADY run; this is asked only when it found nothing."""
        route = route_correlation(kind=kind, bound_exactly=bound_exactly,
                                  deterministic_candidates=deterministic_candidates,
                                  options=len(options))
        if not route.model_needed:
            self._routed_away(route, subject_ref=observation_id, at=at, text=text)
            return CandidateReading(route=route, status=NOT_NEEDED)
        supplied = tuple(options[:MAX_CANDIDATE_OPTIONS])
        result = self._gateway.propose_entity_candidates(CandidateRequest(
            route=route, source_id=observation_id, text=text, options=supplied))
        if not result.ok or result.output is None:
            return CandidateReading(route=route, status=FAILED,
                                    failure=f"{result.status.value}:{result.detail}")
        accepted, refused = screen_candidates(result.output, options=supplied, text=text)
        return CandidateReading(route=route, status=READ, candidates=accepted, refused=refused)
