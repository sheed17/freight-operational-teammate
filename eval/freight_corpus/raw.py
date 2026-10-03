"""The twenty hostile histories as RAW LANGUAGE, and the reading a careful reader would give them.

`to_raw` rewrites a history so that nothing a model is supposed to read has been read for it: every
message loses its `asserts`, and every rate confirmation and carrier invoice loses its `extracted`
block and carries its figures as document text instead. Everything else — the TMS rows, the tracking
pings, the portal, the human acts, the arrival order, and every labeled expected outcome — is
untouched. The same deterministic spine must reach the same labeled outcomes from the raw form.

`ORACLE_MESSAGES` is the reading of each message, written by hand. It is two things: the reply a
scripted gateway gives in tests (so the offline suite proves the spine reaches its outcomes from a
correct reading, at no cost), and nothing else — a LIVE run is scored against the histories' own
labeled outcomes and the fixtures' structured asserts, never against this table.

### THE ORACLE IS NOT EVIDENCE ABOUT A MODEL. A test that passes with the oracle says the application
is right GIVEN a correct reading. Whether a model produces one is what the live eval measures.

SYNTHETIC. Every company, person, number and sentence here is invented development input.
"""

from __future__ import annotations

import re
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from freight_recon.freight_domain.history import FreightHistory, InboundRecord  # noqa: E402
from freight_recon.inference.contracts import Task  # noqa: E402

from .histories import build_corpus  # noqa: E402
from .parties import CARRIERS  # noqa: E402
from .reading import (  # noqa: E402
    appointment,
    charge,
    delay,
    message,
    paper,
    pick,
    promise,
    rate,
    reference,
    status,
)

#: Records left exactly as authored. This one's hostility IS its structured payload — content trying
#: to declare its own provenance — and it is refused at observation, before anything is read.
KEEP_STRUCTURED: frozenset[tuple[str, str]] = frozenset({("C03", "email-declares-provenance")})

#: Bodies rewritten for the raw form, where the authored text does not itself say what its fixture
#: asserted. "at the dock, checked in" does not say WHICH dock; the fixture knew, a reader cannot.
BODY_OVERRIDES: dict[tuple[str, str], str] = {
    ("N01", "driver-arrived"): "at the shipper, checked in",
}

#: Where the RAW form legitimately ends differently. A bare number in a text can never resolve
#: exactly, so the deterministic harness leaves it UNBOUND; with a reader, the model may PROPOSE the
#: load it plainly names — which is recorded as a model-inferred ambiguity for a human, and binds
#: nothing.
EXPECTED_OVERRIDES: dict[str, dict[str, dict[str, Any]]] = {
    "N08": {"text-bare-number": {"disposition": "AMBIGUOUS", "candidates": ["LD-48410"],
                                 "ambiguity": "model_inferred"}},
}

_LABELS = {"DETENTION": "Detention", "LUMPER": "Lumper fee", "LAYOVER": "Layover",
           "TONU": "Truck ordered not used"}


def dollars(minor: int) -> str:
    return f"${minor // 100:,}.{minor % 100:02d}"


def document_text(doc_type: str, extracted: dict[str, Any], *, load: str, carrier_name: str,
                  note: str = "") -> tuple[str, dict[str, Any]]:
    """A rate confirmation or carrier invoice as text, and the reading of it. The reading quotes the
    exact line each value sits on."""
    invoice = doc_type == "CARRIER_INVOICE"
    number = extracted["invoice_number" if invoice else "ratecon_number"]
    title = "CARRIER INVOICE" if invoice else "CARRIER RATE CONFIRMATION"
    number_line = f"{'Invoice' if invoice else 'Rate confirmation'} number: {number}"
    mc_line = f"Carrier: {carrier_name} ({extracted['carrier_mc']})"
    load_line = f"Broker load number: {load}"
    currency_line = f"All amounts in {extracted['currency']}"
    lines = [title, number_line, mc_line, load_line, currency_line]
    charges: list[dict[str, Any]] = []

    def add(kind: str, label: str, minor: int, charge_type: str | None = None) -> None:
        line = f"{label}: {dollars(minor)}"
        lines.append(line)
        charges.append({"line_kind": kind, "charge_type": charge_type,
                        "amount_text": dollars(minor), "evidence_text": line})

    add("LINEHAUL", "Line haul", extracted["linehaul_minor"])
    if extracted.get("fuel_minor"):
        add("FUEL", "Fuel surcharge", extracted["fuel_minor"])
    for line in extracted.get("accessorials", ()):
        add("ACCESSORIAL", _LABELS.get(line["charge_type"]) or line["charge_type"].title(),
            line["amount_minor"], line["charge_type"])
    if extracted.get("total_minor") is not None:
        add("TOTAL", "Total due", extracted["total_minor"])
    if note:
        lines.append(note)
    reading = {
        "doc_type": doc_type, "document_number": number,
        "document_number_evidence_text": number_line,
        "carrier_mc": extracted["carrier_mc"], "carrier_mc_evidence_text": mc_line,
        "currency_code": extracted["currency"], "currency_evidence_text": currency_line,
        "references": [{"kind": "LOAD_NUMBER", "value": load, "role": "SUBJECT",
                        "in_quoted_text": False, "evidence_text": load_line}],
        "charges": charges,
    }
    return "\n".join(lines) + "\n", reading


def _raw_record(history_id: str, record: InboundRecord,
                documents: dict[str, dict[str, Any]]) -> InboundRecord:
    if (history_id, record.label.replace("-redelivered", "")) in KEEP_STRUCTURED:
        return record
    payload = dict(record.payload)
    if record.kind == "message":
        payload.pop("asserts", None)
        override = BODY_OVERRIDES.get((history_id, record.label))
        if override is not None:
            payload["body"] = override
        return replace(record, payload=payload)
    if record.kind == "document" and payload.get("extracted"):
        extracted = dict(payload["extracted"])
        content = str(payload["content"])
        load = re.search(r"\bload (\S+)", content)
        rendition = re.search(r"rendition (\w+)", content)
        carrier = next(c["name"] for c in CARRIERS.values() if c["mc"] == extracted["carrier_mc"])
        note = ""
        if rendition and rendition.group(1) != "a":
            note = f"Copy {rendition.group(1)} - resent"
        if "signed=False" in content:
            note = "Carrier signature: (not signed)"
        text, reading = document_text(payload["doc_type"], extracted,
                                      load=load.group(1) if load else "", carrier_name=carrier,
                                      note=note)
        documents[text] = reading
        payload.pop("extracted")
        payload["content"] = text
        return replace(record, payload=payload)
    return record


def to_raw(history: FreightHistory,
           documents: dict[str, dict[str, Any]] | None = None) -> FreightHistory:
    """`history` with its language un-read. `documents` collects text -> reading for each document."""
    documents = {} if documents is None else documents
    expected = dict(history.expected)
    overrides = EXPECTED_OVERRIDES.get(history.history_id)
    if overrides:
        expected["records"] = {**dict(expected.get("records") or {}), **overrides}
    return FreightHistory(
        history_id=history.history_id, title=history.title, tenant=history.tenant,
        hostile=history.hostile, expected=expected,
        records=tuple(_raw_record(history.history_id, r, documents) for r in history.records))


def build_raw_corpus() -> tuple[list[FreightHistory], dict[str, dict[str, Any]]]:
    """The twenty histories in raw form, and the reading of every document in them."""
    documents: dict[str, dict[str, Any]] = {}
    return [to_raw(history, documents) for history in build_corpus()], documents


# --------------------------------------------------------------------------- the readings

#: `(history_id, record label) -> reading`. The body each one reads is the raw record's own.
ORACLE_MESSAGES: dict[tuple[str, str], dict[str, Any]] = {
    ("N01", "driver-arrived"): message(
        category="STATUS_UPDATE",
        statuses=[status("ARRIVED", "PICKUP", "at the shipper, checked in")]),
    ("N01", "driver-loaded"): message(
        category="STATUS_UPDATE", statuses=[status("LOADED", "PICKUP", "loaded")]),
    ("N01", "carrier-promise"): message(
        category="STATUS_UPDATE",
        commitments=[promise("will update you by 8", clock="20:00", day=0, text="by 8")]),
    ("N01", "carrier-delay"): message(
        category="ACCESSORIAL_OR_BILLING",
        delays=[delay("shipper held him 3 hrs this afternoon",
                      reason="shipper held him 3 hrs this afternoon", stop="PICKUP")],
        accessorials=[charge("DETENTION", "we'll need detention 175", amount="175")]),
    ("N01", "driver-delivered"): message(
        category="STATUS_UPDATE", statuses=[status("DELIVERED", "DELIVERY", "delivered")]),
    ("N02", "carrier-promise"): message(
        category="STATUS_UPDATE",
        commitments=[promise("I will send the POD by 11 tomorrow", clock="11:00", day=1,
                             text="by 11 tomorrow", action="SEND_DOCUMENT")],
        documents=[paper("POD", "PROMISED", "I will send the POD by 11 tomorrow")]),
    ("N02", "carrier-pod-note"): message(
        category="DOCUMENT_DELIVERY", documents=[paper("POD", "ATTACHED", "POD attached")]),
    ("N02", "customer-forward"): message(
        category="OTHER",
        commitments=[promise("I will send the POD by 11 tomorrow", clock="11:00", day=1,
                             text="by 11 tomorrow", action="SEND_DOCUMENT", actor="CARRIER",
                             quoted=True)]),
    ("N05", "carrier-appointment"): message(
        category="APPOINTMENT",
        appointments=[appointment("DELIVERY", "we are set for 0900 delivery tomorrow", day=1,
                                  start="09:00")]),
    ("N06", "carrier-rate-talk"): message(
        category="RATE", rates=[rate("2150", "we are at 2150 all in")]),
    ("N08", "customer-po-only"): message(
        category="APPOINTMENT", response_requested=True,
        appointments=[appointment("DELIVERY", "push delivery on PO-8850 to Thursday", day=3,
                                  start=None, state="REQUESTED")],
        references=[reference("PO_NUMBER", "PO-8850", "PO-8850")]),
    ("N08", "text-bare-number"): message(
        category="STATUS_UPDATE", delays=[delay("running 2 hrs behind")],
        references=[reference("LOAD_NUMBER", "48410", "48410")]),
    ("N08", "customer-po-and-load"): message(
        category="OTHER",
        references=[reference("LOAD_NUMBER", "LD-48411", "the second truck, LD-48411")]),
    ("N09", "carrier-promise"): message(
        category="STATUS_UPDATE",
        commitments=[promise("I'll text you by 11 once he's checked in", clock="11:00", day=0,
                             text="by 11")]),
    ("N10", "carrier-old-number"): message(category="STATUS_UPDATE"),
    ("N10", "carrier-new-number"): message(
        category="STATUS_UPDATE", statuses=[status("LOADED", "PICKUP", "Loaded")]),
    ("N10", "carrier-stale-number"): message(category="STATUS_UPDATE"),
    ("N10", "customer-right-po"): message(
        category="REQUEST", response_requested=True,
        references=[reference("PO_NUMBER", "PO-4540", "PO-4540")]),
    ("N12", "carrier-lumper-claim"): message(
        category="ACCESSORIAL_OR_BILLING",
        accessorials=[charge("LUMPER", "lumper was 240 at the receiver", amount="240",
                             approved=True)]),
    ("N13", "driver-delivered"): message(
        category="STATUS_UPDATE", statuses=[status("DELIVERED", "DELIVERY", "delivered")]),
    ("C02", "carrier-rate-text"): message(
        category="RATE", response_requested=True,
        rates=[rate("1850", "We said 1850 all in")],
        documents=[paper("RATE_CON", "REQUESTED", "send the rate con when you can")]),
    ("C03", "carrier-says-approved"): message(
        category="ACCESSORIAL_OR_BILLING",
        accessorials=[charge("DETENTION", "you approved 200 detention on this load",
                             amount="200", approved=True)]),
}

#: Candidate proposals a careful reader would make for records nothing exact could place, keyed by the
#: text of the request. An unlisted request is answered "no candidate is supported".
ORACLE_CANDIDATES: dict[str, Any] = {
    "48410 running 2 hrs behind": pick("LD-48410 (load_ref)", evidence="48410"),
}


def oracle_responder(histories: list[FreightHistory],
                     documents: dict[str, dict[str, Any]]) -> Any:
    """A responder that reads the raw corpus correctly. Keyed by the text each request carries."""
    by_body: dict[str, dict[str, Any]] = {}
    for history in histories:
        for record in history.records:
            reading = ORACLE_MESSAGES.get((history.history_id, record.label))
            if reading is not None:
                by_body[str(record.payload["body"])] = reading

    def respond(task: Task, request: Any) -> Any:
        if task is Task.INTERPRET_MESSAGE:
            return by_body.get(request.body)
        if task is Task.INTERPRET_DOCUMENT_TEXT:
            return documents.get(request.text)
        if task is Task.PROPOSE_ENTITY_CANDIDATES:
            scripted = ORACLE_CANDIDATES.get(request.text)
            return scripted(request) if scripted is not None else {"candidates": []}
        return None
    return respond


def raw_message_labels(histories: list[FreightHistory]) -> list[tuple[str, str]]:
    """Every `(history_id, label)` whose content the raw corpus leaves for a reader."""
    out: list[tuple[str, str]] = []
    for history in histories:
        seen: set[str] = set()
        for record in history.records:
            if (record.kind == "message" and "asserts" not in record.payload
                    and record.external_id not in seen):
                seen.add(record.external_id)
                out.append((history.history_id, record.label))
    return out
