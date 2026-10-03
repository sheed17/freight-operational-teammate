"""P9 deep-end 2 — model-backed freight interpretation, tested with freight.

Every test here runs raw freight language through the REAL spine — the P6-P8 machines on a real
database, the External Entity Mapping, the projection, the detectors — with a scripted reader in the
model's seat. Nothing is mocked below the gateway and nothing leaves the process.

### WHAT THE SCRIPTED READER IS, AND IS NOT. It answers with a reading written by hand. A test that
passes with a CORRECT scripted reading proves the application reaches the right freight outcome GIVEN
a correct reading. A test that hands the spine a WRONG or hostile reading — an invented load id, a
quote that is not in the message, a promise that is really a quotation, an "approval" — proves what
the application refuses to do whatever a model says. Neither is evidence about a model: that is what
`scripts/run_freight_interpretation_eval.py` measures, live, on opt-in.

### THE CORPUS IS SYNTHETIC DEVELOPMENT INPUT. A passing test validates no freight rule.

### WHAT COULD FAIL, AND WOULD. `scripts/mutate_p9_interpretation.py` reintroduces the real defect
behind each behavioural claim and confirms the named test turns RED.
"""

from __future__ import annotations

import socket
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
for entry in (str(ROOT / "src"), str(ROOT / "eval")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from freight_corpus import raw_histories as scenarios_module  # noqa: E402
from freight_corpus.builders import (  # noqa: E402
    HistoryBuilder,
    charges,
    load_ref,
    movement,
    stop,
)
from freight_corpus.histories import build_corpus  # noqa: E402
from freight_corpus.interpretation_cases import (  # noqa: E402
    CORRELATION_CASES,
    FOREIGN_ID,
    LABELED_MESSAGES,
    REQUIRED_TAGS,
    coverage,
)
from freight_corpus.interpretation_eval import (  # noqa: E402
    calls_failed,
    message_agreement,
    run_correlation_cases,
    run_labeled_messages,
    run_stage,
)
from freight_corpus.parties import (  # noqa: E402
    CARRIERS,
    CEDAR,
    CUSTOMERS,
    NORTHLINE,
    NORTHLINE_OPS,
    NORTHLINE_SMS,
    SETUPS,
)
from freight_corpus.raw import (  # noqa: E402
    build_raw_corpus,
    document_text,
    oracle_responder,
    raw_message_labels,
)
from freight_corpus.raw_histories import (  # noqa: E402
    APPROVED_BY_MIKE,
    CHECK_IN,
    DOCUMENT_READINGS,
    FORWARD,
    POD_BARE,
    build_raw_histories,
    raw_history_responder,
)
from freight_corpus.reading import (  # noqa: E402
    appointment,
    candidates,
    charge,
    correction,
    message,
    paper,
    promise,
    rate,
    reference,
    status,
)
from freight_recon.freight_domain.corpus_run import (  # noqa: E402
    cross_tenant_violations,
    run_corpus,
    shared_reference_population,
)
from freight_recon.freight_domain.foundation import format_instant  # noqa: E402
from freight_recon.freight_domain.history import FreightHistory  # noqa: E402
from freight_recon.freight_domain.interpretation import (  # noqa: E402
    FreightInterpreter,
    amount_written,
    commitment_deadline,
    convert_document,
    convert_message,
    find_quote,
    parse_amount_minor,
    quoted_regions,
    route_content,
    route_correlation,
)
from freight_recon.inference.contracts import (  # noqa: E402
    Commitment,
    DocumentTextInterpretation,
    MessageInterpretation,
    Task,
)
from freight_recon.inference.gateway import (  # noqa: E402
    ProviderRejection,
    ReplayGateway,
    TransportFailure,
)
from freight_recon.inference.ledger import InferenceLedger  # noqa: E402
from freight_recon.inference.recording import RecordingStore  # noqa: E402
from freight_recon.inference.scripted import ScriptedGateway  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402

POD_NOTE_REQUEST = "POD\n" + POD_BARE
#: Readings gpt-6-luna actually gave, recorded by the opt-in live eval and committed.
LUNA_RECORDING = ROOT / "eval" / "freight_corpus" / "recordings" / "gpt-6-luna.effort-low.json"


class Run:
    """One pass of histories through the spine with a reader, and what it left behind."""

    def __init__(self, directory: Path, histories, *, responder=None, gateway=None,
                 recording: RecordingStore | None = None, name: str = "spine.db") -> None:
        self.store = WorkflowStore(directory / name, tenant=histories[0].tenant)
        self.conn: sqlite3.Connection = self.store.conn
        self.ledger = gateway.ledger if gateway is not None else InferenceLedger()
        self.gateway = gateway or ScriptedGateway(responder, ledger=self.ledger,
                                                  recording=recording)
        self.result = run_corpus(self.conn, SETUPS, histories,
                                 interpreter=FreightInterpreter(self.gateway, self.ledger))

    def view(self, tenant: str, load: str):
        return self.result.view(tenant, load)

    def observation(self, history_id: str, label: str) -> dict:
        outcome = self.result.outcome(history_id, label)
        tenant = self.result.history(history_id).history.tenant
        row = self.result.intakes[tenant].foundation.observation(outcome.observation_id)
        assert row is not None, f"{history_id}/{label} was not observed"
        return row

    def claims(self, observation_id: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT tenant, state, match_method, provenance_class, owner_id, ambiguous_reason, "
            "entity_ref, confidence FROM identity_binding_claims WHERE subject_ref = ? "
            "ORDER BY created_at, binding_claim_id", (observation_id,)).fetchall()

    def mismatches(self) -> list[str]:
        return [m for h in self.result.histories for m in h.mismatches]


def _scenario(history_id: str) -> FreightHistory:
    return next(h for h in build_raw_histories() if h.history_id == history_id)


def _truncate(history: FreightHistory, *, after: str) -> FreightHistory:
    labels = [r.label for r in history.records]
    assert after in labels, f"{history.history_id} has no record labeled {after!r}"
    return FreightHistory(history_id=history.history_id, title=history.title,
                          tenant=history.tenant, hostile=history.hostile,
                          records=history.records[: labels.index(after) + 1], expected={})


@pytest.fixture(scope="module")
def scenarios(tmp_path_factory):
    """The nine raw-language histories, read correctly, in ONE database for both brokerages."""
    run = Run(tmp_path_factory.mktemp("p9-scenarios"), build_raw_histories(),
              responder=raw_history_responder())
    yield run
    run.store.close()


@pytest.fixture(scope="module")
def raw_corpus(tmp_path_factory):
    """The twenty hostile histories in raw form, read correctly."""
    histories, documents = build_raw_corpus()
    run = Run(tmp_path_factory.mktemp("p9-raw-corpus"), histories,
              responder=oracle_responder(histories, documents))
    yield run, histories, documents
    run.store.close()


# ============================================================ the corpus, from raw language

def test_the_twenty_histories_reach_every_labeled_outcome_from_raw_language(raw_corpus, tmp_path):
    """The finish line. Every message has lost its structured `asserts` and every rate confirmation
    and invoice its `extracted` block. Read correctly, the UNCHANGED spine reaches every outcome the
    histories label — and the same canonical picture the deterministic harness reaches."""
    run, histories, documents = raw_corpus
    assert len(run.result.histories) == 20
    assert run.mismatches() == []
    metrics = run.result.report["metrics"]
    assert metrics["labeled_expectations_checked"] >= 262
    assert metrics["labeled_expectations_failed"] == 0

    messages = raw_message_labels(histories)
    assert len(messages) == 22 and len(documents) == 23, (len(messages), len(documents))
    assert len(run.gateway.invocations_of(Task.INTERPRET_MESSAGE)) == len(messages)
    # A re-delivered rate confirmation and a re-sent TMS row are duplicates: observed once, read once.
    assert len(run.gateway.invocations_of(Task.INTERPRET_DOCUMENT_TEXT)) == len(documents)
    assert metrics["duplicate_inputs_suppressed"] > 0
    assert metrics["model_readings"] == len(messages) + len(documents)
    assert metrics["model_reading_failures"] == 0 and metrics["external_effect_rows"] == 0
    assert metrics["wrong_cross_tenant_mappings"] == 0

    agreement = message_agreement(run.result, histories)
    assert agreement["messages"] == 22 and agreement["differences"] == []

    structured = WorkflowStore(tmp_path / "structured.db", tenant=NORTHLINE)
    try:
        baseline = run_corpus(structured.conn, SETUPS, build_corpus()).report["metrics"]
    finally:
        structured.close()
    same = ("canonical_loads_produced", "conflicts_raised", "conflicts_open",
            "expectations_raised", "expectations_discharged", "overdue_expectations",
            "indeterminate_expectations", "reconciliations_computed",
            "reconciliations_reconciled", "reconciliations_discrepant",
            "reconciliation_discrepancies", "unresolved_document_requirements",
            "duplicate_invoices_recognized", "duplicate_evidence_recognized",
            "loads_requiring_human_attention", "refused_records", "unparseable_records",
            "exact_external_mappings_resolved", "human_asserted_bindings")
    assert {k: metrics[k] for k in same} == {k: baseline[k] for k in same}
    assert all(baseline[k] > 0 for k in ("conflicts_raised", "expectations_raised",
                                         "reconciliations_discrepant")), "nothing was compared"


def test_a_record_someone_already_structured_never_reaches_a_model(tmp_path):
    """Routing, not habit. The structured corpus carries its `asserts` and `extracted` blocks, so no
    message and no document is read; a model is asked only about the two records exact resolution
    could not place at all."""
    def responder(task, request):
        return {"candidates": []} if task is Task.PROPOSE_ENTITY_CANDIDATES else None

    run = Run(tmp_path, build_corpus(), responder=responder)
    try:
        assert run.gateway.invocations_of(Task.INTERPRET_MESSAGE) == []
        assert run.gateway.invocations_of(Task.INTERPRET_DOCUMENT_TEXT) == []
        asked = run.gateway.invocations_of(Task.PROPOSE_ENTITY_CANDIDATES)
        assert len(asked) == 2, [r.text[:40] for r in asked]
        assert run.mismatches() == []
        reasons = run.ledger.summary()["routing"]["deterministic_reasons"]
        assert reasons["pre_structured"] > 40 and reasons["exact_reference"] > 40
        assert run.ledger.summary()["routing"]["deterministic_rate"] > 0.95
    finally:
        run.store.close()


def test_the_routing_boundary_sends_only_unstructured_language_to_a_model():
    histories, _ = build_raw_corpus()
    routes = {(r.kind, route_content(r).reason): route_content(r).model_needed
              for h in histories for r in h.records}
    assert routes[("message", "inbound_free_text")] is True
    assert routes[("document", "financial_document_text")] is True
    for settled in (("tms_load", "structured_source"), ("tracking_event", "structured_source"),
                    ("human_assertion", "structured_source"), ("appointment", "structured_source"),
                    ("document", "document_type_needs_no_text_fields"),
                    ("message", "pre_structured")):
        assert routes[settled] is False, settled
    assert route_correlation(kind="message", bound_exactly=True, deterministic_candidates=0,
                             options=9).model_needed is False
    assert route_correlation(kind="message", bound_exactly=False, deterministic_candidates=2,
                             options=9).model_needed is False
    assert route_correlation(kind="tracking_event", bound_exactly=False,
                             deterministic_candidates=0, options=9).model_needed is False
    assert route_correlation(kind="message", bound_exactly=False, deterministic_candidates=0,
                             options=0).model_needed is False
    assert route_correlation(kind="message", bound_exactly=False, deterministic_candidates=0,
                             options=9).model_needed is True


def test_all_nine_raw_histories_reach_their_labeled_outcomes(scenarios):
    assert len(scenarios.result.histories) == 9
    assert {h.history.tenant for h in scenarios.result.histories} == {NORTHLINE, CEDAR}
    for item in scenarios.result.histories:
        assert item.checks >= 3, f"{item.history.history_id} asserts only {item.checks} outcome(s)"
        assert item.mismatches == [], item.mismatches
    metrics = scenarios.result.report["metrics"]
    assert metrics["external_effect_rows"] == 0 and metrics["wrong_cross_tenant_mappings"] == 0
    for tenant, intake in scenarios.result.intakes.items():
        assert set(intake.foundation.effect_surface_counts().values()) == {0}, tenant


# ============================================================ evidence and lineage

def test_a_raw_carrier_message_becomes_a_supported_observation_with_evidence(scenarios):
    """"Checked in at the shipper 12:42" becomes a driver's AT_PICKUP claim at the right stop, a
    reading of an artifact (`MODEL_EXTRACTED`), pointing at the exact characters it was read from
    and naming the model that read them."""
    view = scenarios.view(NORTHLINE, "LD-51001")
    claims = [t for t in view.tracking if t.value("signal") == "driver_assertion"]
    assert len(claims) == 1
    fact = claims[0].field_of("status").facts[0]
    assert (fact.value, fact.provenance_class, claims[0].stop_key) == (
        "AT_PICKUP", "MODEL_EXTRACTED", "S1")
    assert fact.source_system == f"{NORTHLINE_SMS}#+1-555-0177", (
        "a claim's source is the party who made it")

    observation = scenarios.observation("R01", "driver-checkin")
    assert fact.observation_id == observation["observation_id"]
    parsed = observation["parsed"]
    item = next(a for a in parsed["payload"]["asserts"] if a["type"] == "status")
    span = item["evidence"]
    assert span["where"] == "body"
    assert parsed["payload"]["body"][span["start"]:span["end"]] == span["text"] == (
        "Checked in at the shipper 12:42")
    lineage = parsed["interpretation"]
    assert (lineage["task"], lineage["status"], lineage["provider"], lineage["model"]) == (
        "interpret_message", "READ", "scripted", "scripted-reader")
    assert lineage["interpreted_at"] == observation["received_at"]
    assert lineage["schema_version"] and lineage["prompt_version"] and lineage["request_digest"]
    for forbidden in ("provenance", "provenance_class", "confidence"):
        assert forbidden not in item and forbidden not in lineage, (
            f"a reading carries {forbidden!r}; the runtime assigns provenance, not the reader")


def test_an_item_whose_evidence_is_not_in_the_message_is_not_extracted():
    """Evidence first. A reported item must quote the content; a paraphrase, an elision or an
    invented sentence is dropped with a reason, and so is a number that is not really there."""
    body = "Driver is loaded. Lumper was 240 at the receiver."
    reading = MessageInterpretation.model_validate(message(
        statuses=[status("LOADED", "PICKUP", "Driver is loaded"),
                  status("DELIVERED", "DELIVERY", "the driver has delivered the freight")],
        commitments=[promise("I'll update you by 5", clock="17:00", day=0, text="by 5")],
        accessorials=[charge("LUMPER", "Lumper was 240 at the receiver", amount="2400"),
                      charge("DETENTION", "Lumper was 240 ... receiver", amount="240")]))
    converted = convert_message(reading, body=body, subject="",
                                as_of_utc="2026-06-01T17:00:00.000Z", zone="America/Chicago")
    kinds = [(a["type"], a.get("status"), a.get("amount_minor")) for a in converted.asserts]
    assert kinds == [("status", "LOADED", None), ("accessorial_claim", None, None)], kinds
    reasons = sorted((d["item"], d["reason"]) for d in converted.dropped)
    assert reasons == [("accessorial_amount", "amount_not_readable_or_not_in_content"),
                       ("accessorial_claim", "evidence_not_in_content"),
                       ("commitment", "evidence_not_in_content"),
                       ("status", "evidence_not_in_content")], reasons

    assert find_quote("LUMPER  was 240", body) == (18, 32)
    assert find_quote("lumper was two forty", body) is None
    assert [parse_amount_minor(t) for t in ("175", "$240.00", "1,850", "2150")] == [
        17500, 24000, 185000, 215000]
    assert [parse_amount_minor(t) for t in ("1.2k", "about 200", "two fifty", "", None, "0",
                                            "-50")] == [None] * 7


def test_a_document_reading_is_all_or_nothing(tmp_path):
    """One charge line the invoice text does not support makes the WHOLE reading unusable: no payable
    is created from the supported half, and a named human is asked to read the document."""
    history = _scenario("R06")
    text = next(t for t in DOCUMENT_READINGS if "IW-9107" in t)
    good = DOCUMENT_READINGS[text]
    bad = {**good, "charges": [*good["charges"][:-1],
                               {**good["charges"][-1], "evidence_text": "Total due: $9,999.00"}]}
    run = Run(tmp_path, [history],
              responder=raw_history_responder({(Task.INTERPRET_DOCUMENT_TEXT, text): bad}))
    try:
        view = run.view(NORTHLINE, "LD-51007")
        assert len(view.payables) == 0, "half an invoice became a payable"
        assert {str(d.value("doc_type")) for d in view.documents.values()} == {
            "RATE_CON", "POD", "CARRIER_INVOICE"}, "the artifact itself must still be retained"
        parsed = run.observation("R06", "carrier-invoice")["parsed"]
        assert parsed["payload"]["extracted"] == {}
        assert parsed["interpretation"]["status"] == "FAILED"
        assert "charge_line_2_not_supported_by_text" in parsed["interpretation"]["failure"]
        unavailable = [x for x in view.exceptions if x["type"] == "interpretation_unavailable"]
        assert len(unavailable) == 1 and unavailable[0]["owner_id"] == "priya.nair"
    finally:
        run.store.close()

    # The reading must also AGREE with what the record says the document is.
    wrong_type = DocumentTextInterpretation.model_validate({**good, "doc_type": "RATE_CON"})
    assert convert_document(wrong_type, text=text, declared_doc_type="CARRIER_INVOICE").problems
    assert convert_document(DocumentTextInterpretation.model_validate(good), text=text,
                            declared_doc_type="CARRIER_INVOICE").extracted["total_minor"] == 232500


def _billed_against_a_rate_con(invoice: dict) -> tuple[FreightHistory, dict[str, dict]]:
    """One load: a signed rate confirmation for $1,950.00, then a carrier invoice. Returns the
    history and each raw document's text with the correct reading of it."""
    h = HistoryBuilder("RX1", "an invoice billed against a signed rate confirmation", NORTHLINE,
                       day="2026-06-17", zone="America/Chicago", hostile=("raw_language",))
    load, carrier = "LD-59001", CARRIERS["ironwood"]
    papers: dict[str, dict] = {}

    def paper_(label: str, at: str, doc_type: str, block: dict, signed: bool | None) -> None:
        text, reading = document_text(doc_type, {"carrier_mc": carrier["mc"], **block},
                                      load=load, carrier_name=carrier["name"])
        papers[label] = {"text": text, "reading": reading}
        h.raw_document(label, at, doc_type, text, refs=(load_ref(load),), via=NORTHLINE_OPS,
                       signed=signed)

    h.tms("covered", h.t("07:30"), load=load, status="COVERED", version=1,
          customer=CUSTOMERS["prairie_ag"], po="PO-9901", bol="BOL-79001", sell=charges(248000),
          stops=(stop("S1", "PICKUP", 1, "Prairie Ag Decatur", "America/Chicago"),
                 stop("S2", "DELIVERY", 2, "Delta Crop Services", "America/Chicago")),
          movements=(movement("M1", carrier, pro="PRO-79001"),))
    paper_("rate-con", h.t("09:40"), "RATE_CON",
           {"ratecon_number": "RC-59001", **charges(195000)}, True)
    paper_("carrier-invoice", h.t("15:20", 1), "CARRIER_INVOICE",
           {"invoice_number": "IW-9901", **invoice}, None)
    h.clock("end", h.t("12:00", 2))
    return h.build({}), papers


def test_an_amount_that_keeps_only_part_of_a_written_number_is_not_that_number(tmp_path):
    """The model never chooses an amount — and "1,950.00" is not what an invoice that says
    "$11,950.00" states. Containment accepted it: that invoice, read with its leading digit dropped,
    matched the signed $1,950.00 rate confirmation and came out RECONCILED, $10,000 overbilled and
    clean. A number that keeps only some of a written number's digits is now refused; the document
    becomes one a named human is asked to read, and nothing reconciles on it."""
    written = [("2150", "we are at 2150 all in"), ("$2,150.00", "Line haul: $2,150.00"),
               ("2150", "Line haul: 2150.00"), ("175", "Detention was 175."),
               ("175", "detention 175, lumper 240")]
    partial = [("1,950.00", "Line haul: $11,950.00"), ("950.00", "Line haul: $1,950.00"),
               ("150", "we are at 2150 all in"), ("215", "we are at 2150 all in"),
               ("175", "detention 175.50 owed"), ("7700", "Load 7700412"), ("1", "$1,950.00"),
               ("50.00", "Fuel surcharge: $150.00"), (None, "175"), ("", "175")]
    assert [amount_written(a, t) for a, t in written] == [True] * len(written)
    assert [amount_written(a, t) for a, t in partial] == [False] * len(partial)

    # In a MESSAGE: a rate cut out of the rate, a "rate" cut out of the load number, and a detention
    # amount cut out of the rate. Only the number that is really written survives.
    body = "Load 7700412 delivered. We are at 2150 all in. Detention applies at the receiver."
    quote = "We are at 2150 all in"
    reading = MessageInterpretation.model_validate(message(
        rates=[rate("215", quote), rate("7700", quote), rate("2150", quote)],
        accessorials=[charge("DETENTION", "Detention applies at the receiver", amount="150")]))
    converted = convert_message(reading, body=body, subject="",
                                as_of_utc="2026-06-01T17:00:00.000Z", zone="America/Chicago")
    assert [(a["type"], a["amount_minor"]) for a in converted.asserts] == [
        ("accessorial_claim", None), ("rate", 215000)], converted.asserts
    assert sorted(d["item"] for d in converted.dropped) == ["accessorial_amount", "rate", "rate"]

    # On a DOCUMENT the amount must be whole ON THE LINE THAT WAS QUOTED. The same invoice also
    # bills a real $1,950.00 of detention two lines down: that does not support the linehaul.
    text, good = document_text(
        "CARRIER_INVOICE", {"carrier_mc": "MC-771203", "invoice_number": "IW-9902",
                            **charges(1195000, 0, {"DETENTION": 195000}, total=1390000)},
        load="LD-59002", carrier_name="Ironwood Hauling Inc")
    assert "Line haul: $11,950.00" in text and "Detention: $1,950.00" in text, text

    def read(first_line: dict) -> Any:
        reading = {**good, "charges": [{**good["charges"][0], **first_line}, *good["charges"][1:]]}
        return convert_document(DocumentTextInterpretation.model_validate(reading), text=text,
                                declared_doc_type="CARRIER_INVOICE")

    assert read({}).extracted["linehaul_minor"] == 1195000, "the honest reading must still be usable"
    dropped_digit = read({"amount_text": "$1,950.00"})
    assert dropped_digit.extracted is None
    assert "charge_line_0_not_supported_by_text" in dropped_digit.problems
    # A quote that stops mid-number does not hide the digit the reading left out.
    cut_quote = read({"amount_text": "1,950.00", "evidence_text": "1,950.00"})
    assert cut_quote.extracted is None, "an evidence quote cut out of a longer number was accepted"

    # THROUGH THE SPINE: $11,950.00 billed against a signed $1,950.00 rate confirmation.
    history, papers = _billed_against_a_rate_con(charges(1195000, total=1195000))
    invoice = papers["carrier-invoice"]
    misread = {**invoice["reading"], "charges": [
        {**line, "amount_text": line["amount_text"].replace("11,950.00", "1,950.00")}
        for line in invoice["reading"]["charges"]]}
    assert [line["amount_text"] for line in misread["charges"]] == ["$1,950.00", "$1,950.00"]

    def through_the_spine(name: str, invoice_reading: dict) -> Run:
        readings = {papers["rate-con"]["text"]: papers["rate-con"]["reading"],
                    invoice["text"]: invoice_reading}
        return Run(tmp_path, [history], name=name,
                   responder=lambda task, request: readings[request.text])

    honest = through_the_spine("honest.db", invoice["reading"])
    try:
        view = honest.view(NORTHLINE, "LD-59001")
        billed = next(iter(view.payables.values())).field_of("linehaul").facts[0]
        assert (billed.value.amount_minor, billed.provenance_class, billed.may_gate) == (
            1195000, "MODEL_EXTRACTED", True), "a document amount is a fact a gate may read"
        assert [(r.status, [d.code for d in r.discrepancies]) for r in view.reconciliations] == [
            ("DISCREPANT", ["LINEHAUL_MISMATCH"])]
    finally:
        honest.store.close()

    run = through_the_spine("misread.db", misread)
    try:
        view = run.view(NORTHLINE, "LD-59001")
        assert view.payables == {}, "an amount the invoice never states became a payable"
        assert "RECONCILED" not in {r.status for r in view.reconciliations}, (
            "an invoice overbilled by $10,000 reconciled clean against the rate confirmation")
        parsed = run.observation("RX1", "carrier-invoice")["parsed"]
        assert parsed["payload"]["extracted"] == {}
        assert parsed["interpretation"]["status"] == "FAILED"
        assert "charge_line_0_not_supported_by_text" in parsed["interpretation"]["failure"]
        unavailable = [x for x in view.exceptions if x["type"] == "interpretation_unavailable"]
        assert len(unavailable) == 1 and unavailable[0]["owner_id"] == "priya.nair"
        # The rate confirmation, read honestly in the same run, is untouched.
        assert next(iter(view.rate_confirmations.values())).value("linehaul").amount_minor == 195000
    finally:
        run.store.close()


def test_values_read_off_a_document_point_at_spans_of_the_retained_artifact(scenarios):
    text = next(t for t in DOCUMENT_READINGS if "IW-9107" in t)
    view = scenarios.view(NORTHLINE, "LD-51007")
    payable = next(iter(view.payables.values()))
    fact = payable.field_of("linehaul").facts[0]
    assert fact.provenance_class == "MODEL_EXTRACTED" and fact.evidence_id
    rows = scenarios.conn.execute(
        "SELECT locator, region, extracted_text FROM evidence_spans WHERE tenant = ? "
        "AND evidence_id = ? AND locator LIKE 'char:%'", (NORTHLINE, fact.evidence_id)).fetchall()
    assert len(rows) >= 6, f"only {len(rows)} field spans were retained for the invoice"
    for row in rows:
        start, end = (int(part) for part in row["locator"].split(":")[1].split("-"))
        assert text[start:end] == row["extracted_text"], row["locator"]
    regions = {row["region"] for row in rows}
    assert {"invoice_number", "currency", "charge:LINEHAUL:", "charge:TOTAL:",
            "charge:ACCESSORIAL:DETENTION"} <= regions, regions


# ============================================================ commitments and expectations

def test_a_raw_promise_becomes_an_existing_expectation_with_a_deterministic_deadline(scenarios):
    """"I'll update you in an hour", said at 12:44 and received at 12:47. The model read "an hour";
    the application computed 13:44 from the captured send time; M8 owns everything after that —
    including calling it OVERDUE only because the channel was demonstrably up."""
    view = scenarios.view(NORTHLINE, "LD-51001")
    promised = [e for e in view.expectations if e["expected_type"] == "counterparty_update"]
    assert len(promised) == 1
    expectation = promised[0]
    said_at = datetime(2026, 6, 1, 17, 44, tzinfo=timezone.utc)          # 12:44 in Chicago
    assert scenarios.observation("R01", "driver-checkin")["as_of"] == format_instant(said_at)
    assert expectation["deadline_utc"] == "2026-06-01T18:44:00.000Z", (
        "the deadline must run from when the promise was SAID, plus the hour that was read")
    assert expectation["deadline_utc"] != "2026-06-01T18:47:00.000Z", "it ran from RECEIPT"
    assert (expectation["state"], expectation["expected_source"], expectation["owner_id"]) == (
        "OVERDUE", NORTHLINE_SMS, "dana.ortiz")
    row = scenarios.conn.execute(
        "SELECT state, deadline_utc FROM expectations WHERE tenant = ? AND expectation_id = ?",
        (NORTHLINE, expectation["expectation_id"])).fetchone()
    assert tuple(row) == ("OVERDUE", "2026-06-01T18:44:00.000Z"), "it is not an M8 Expectation"
    unmet = [x for x in view.exceptions if x["type"] == "expectation_unmet"]
    assert len(unmet) == 1 and unmet[0]["owner_id"] == "dana.ortiz"


def test_a_deadline_is_arithmetic_on_what_was_read_never_a_date_the_model_chose():
    def item(**fields) -> Commitment:
        return Commitment.model_validate(promise("x", **fields))

    sent = "2026-06-01T23:05:00.000Z"                                    # 18:05 in Chicago
    zone = "America/Chicago"
    assert commitment_deadline(item(minutes=30), as_of_utc=sent, zone=zone) == (
        "2026-06-01T23:35:00.000Z")
    assert commitment_deadline(item(clock="20:00", day=0), as_of_utc=sent, zone=zone) == (
        "2026-06-02T01:00:00.000Z")
    assert commitment_deadline(item(clock="11:00", day=1), as_of_utc=sent, zone=zone) == (
        "2026-06-02T16:00:00.000Z")
    # A reading that does not describe a moment AFTER the message is not turned into a deadline.
    for misread in (item(clock="08:00", day=0), item(minutes=0), item(minutes=-10), item(),
                    item(clock="25:00", day=0), item(clock="8pm", day=0),
                    item(minutes=60 * 24 * 40)):
        assert commitment_deadline(misread, as_of_utc=sent, zone=zone) is None, misread
    # The spring-forward night: 09:00 the next morning is 14:00Z, not 15:00Z.
    assert commitment_deadline(item(clock="09:00", day=1), as_of_utc="2026-03-08T02:00:00.000Z",
                               zone=zone) == "2026-03-08T14:00:00.000Z"


def test_a_quoted_or_forwarded_promise_creates_no_second_obligation(scenarios, tmp_path):
    """The carrier promised an update by 5 and kept it. The customer then forwarded that email.
    The quoted promise is not a new one: one Expectation, discharged — and the same holds when the
    READER fails to notice it is a quotation, because the structure of the email says so too."""
    def assert_one_obligation(run: Run) -> None:
        view = run.view(NORTHLINE, "LD-51002")
        promised = [e for e in view.expectations if e["expected_type"] == "counterparty_update"]
        assert [e["state"] for e in promised] == ["DISCHARGED"], promised
        assert len([t for t in view.tracking if t.value("status") == "LOADED"]) == 1, (
            "the quoted status was applied a second time")
        assert not [x for x in view.exceptions if x["type"] == "expectation_unmet"]
        assert view.attention == []

    assert_one_obligation(scenarios)
    forwarded = scenarios.observation("R02", "customer-forward")["parsed"]
    quoted = [a for a in forwarded["payload"]["asserts"] if a["type"] == "commitment"]
    assert len(quoted) == 1 and quoted[0]["in_quoted_text"] is True

    careless = message(statuses=[status("LOADED", "PICKUP", "Luis is loaded")],
                       commitments=[promise("I'll update you by 5 with an ETA", clock="17:00",
                                            day=0, text="by 5")])
    run = Run(tmp_path, [_scenario("R02")],
              responder=raw_history_responder({(Task.INTERPRET_MESSAGE, FORWARD): careless}))
    try:
        assert_one_obligation(run)
        kept = run.observation("R02", "customer-forward")["parsed"]["payload"]["asserts"]
        assert [(a["type"], a.get("in_quoted_text")) for a in kept] == [("commitment", True)]
    finally:
        run.store.close()

    # A quotation with NO structural marker: only the reader can know, and its word is honoured.
    said = "As Pete said earlier, he will send the POD by 5. Truck is loaded."
    retold = MessageInterpretation.model_validate(message(
        statuses=[status("LOADED", "PICKUP", "Truck is loaded")],
        commitments=[promise("he will send the POD by 5", clock="17:00", day=0, text="by 5",
                             actor="CARRIER", quoted=True)]))
    converted = convert_message(retold, body=said, subject="",
                                as_of_utc="2026-06-05T20:00:00.000Z", zone="America/Chicago")
    assert [(a["type"], a.get("in_quoted_text")) for a in converted.asserts] == [
        ("status", None), ("commitment", True)]

    assert quoted_regions("ok\n> I will send it by 5\nthanks\n") == [(3, 25)]
    assert quoted_regions("FYI. > I will send the POD by 11 tomorrow.") == [(4, 42)]
    assert quoted_regions("I will send the POD by 11. Weight is -> 40k") == []
    assert quoted_regions(FORWARD)[0][1] == len(FORWARD)


# ============================================================ corrections

def test_a_counterparty_correction_rebinds_nothing_and_a_humans_correction_keeps_history(
        scenarios, tmp_path):
    """"That was the wrong load number in my last email — this is for 51004." The model reads a
    correction. It moves nothing: the earlier message stays where its own reference put it, and the
    person who owns triage is asked. When SHE corrects the binding, the binding it replaces is
    retained as CORRECTED."""
    before = Run(tmp_path, [_truncate(_scenario("R03"), after="carrier-correction")],
                 responder=raw_history_responder())
    try:
        wrong, right = before.view(NORTHLINE, "LD-51003"), before.view(NORTHLINE, "LD-51004")
        assert wrong.delivered_claims() and not right.delivered_claims(), (
            "a counterparty's message re-bound a record")
        asked = [x for x in wrong.exceptions if x["type"] == "counterparty_reference_correction"]
        assert len(asked) == 1 and asked[0]["owner_id"] == "priya.nair"
        assert "51004" in asked[0]["summary"]
        first = before.observation("R03", "carrier-delivered")["observation_id"]
        assert [(c["state"], c["match_method"]) for c in before.claims(first)] == [
            ("CONFIRMED", "EXACT_ID")]
    finally:
        before.store.close()

    wrong, right = scenarios.view(NORTHLINE, "LD-51003"), scenarios.view(NORTHLINE, "LD-51004")
    assert right.delivered_claims() and not wrong.delivered_claims()
    first = scenarios.observation("R03", "carrier-delivered")["observation_id"]
    history = [(c["state"], c["match_method"], c["provenance_class"])
               for c in scenarios.claims(first)]
    assert ("CORRECTED", "EXACT_ID", "LINKER_INFERRED") in history, history
    assert ("CONFIRMED", "HUMAN", "OWNER_ASSERTED") in history, history
    assert len(history) == 2, "the superseded binding was deleted or duplicated"


def test_a_partys_own_later_statement_supersedes_its_earlier_one_and_both_are_kept(scenarios):
    """The dispatcher said 0900, then "correction — 1000". His later statement is his current one;
    the earlier one is retained as history. It does not touch what the CUSTOMER said."""
    appointment_ = scenarios.view(NORTHLINE, "LD-51009").appointments["S2"]
    window = appointment_.field_of("window")
    starts = sorted(f.value["start_local"][-5:] for f in window.facts)
    assert starts == ["09:00", "10:00", "13:00"], starts
    latest = {source.split("#")[1]: fact.value["start_local"][-5:]
              for source, fact in window.latest_by_source().items()}
    assert latest == {"pete@ironwoodhauling.example": "10:00",
                      "npatel@greatlakesbev.example": "13:00"}, latest
    assert [f.value["start_local"][-5:] for f in window.stale_facts()] == ["09:00"]
    assert {f.provenance_class for f in window.facts} == {"MODEL_EXTRACTED"}


# ============================================================ correlation

def test_a_model_proposed_candidate_never_binds_however_clearly_it_is_supported(scenarios):
    """"POD attached for 51005." names no load exactly. The reader proposes LD-51005 with CLEAR
    support — and it is still not bound: one AMBIGUOUS, MODEL_INFERRED claim owned by a named human.
    Two candidates stay two candidates."""
    single = scenarios.result.outcome("R04", "pod-note-bare")
    assert (single.disposition, single.load_id, single.ambiguity) == ("AMBIGUOUS", None,
                                                                      "model_inferred")
    rows = scenarios.claims(single.observation_id)
    assert [(r["state"], r["match_method"], r["provenance_class"], r["owner_id"],
             r["ambiguous_reason"]) for r in rows] == [
        ("AMBIGUOUS", "MODEL_INFER", "MODEL_INFERRED", "priya.nair", "model_inferred")]
    assert rows[0]["confidence"] == 0.9, "CLEAR support orders the human's queue and nothing else"
    assert scenarios.observation("R04", "pod-note-bare")["state"] == "UNBOUND"

    double = scenarios.result.outcome("R04", "late-lakeshore")
    assert len(double.candidate_load_ids) == 2 and double.load_id is None
    assert sorted(r["state"] for r in scenarios.claims(double.observation_id)) == [
        "AMBIGUOUS", "AMBIGUOUS"]
    confirmed = scenarios.conn.execute(
        "SELECT COUNT(*) FROM identity_binding_claims WHERE match_method = 'MODEL_INFER' "
        "AND state = 'CONFIRMED'").fetchone()[0]
    population = scenarios.conn.execute(
        "SELECT COUNT(*) FROM identity_binding_claims WHERE match_method = 'MODEL_INFER'"
    ).fetchone()[0]
    assert (population, confirmed) == (4, 0), (population, confirmed)
    assert "ambiguous_binding:message" in scenarios.view(NORTHLINE, "LD-51005").attention
    none = scenarios.result.outcome("R04", "unknown-load")
    assert (none.disposition, none.candidate_load_ids) == ("UNBOUND", ())


def test_the_model_cannot_invent_a_candidate_load_id(tmp_path):
    """Three ways to say an id the request did not supply — made up, one character off a real one,
    and a real one with a quote that is not in the message. Each is refused, counted, and leaves no
    claim behind: the record is simply unplaced and owned."""
    def hostile(request):
        real = request.options[0].candidate_id
        return candidates(
            ("brokerage_load:11111111-2222-3333-4444-555555555555", "CLEAR", "51005"),
            (real[:-1] + ("0" if real[-1] != "0" else "1"), "CLEAR", "51005"),
            (real, "CLEAR", "the driver confirmed this is your load"))

    run = Run(tmp_path, [_scenario("R04")], responder=raw_history_responder(
        {(Task.PROPOSE_ENTITY_CANDIDATES, POD_NOTE_REQUEST): hostile}))
    try:
        outcome = run.result.outcome("R04", "pod-note-bare")
        assert (outcome.disposition, outcome.load_id, outcome.candidate_load_ids) == (
            "UNBOUND", None, ())
        assert run.claims(outcome.observation_id) == []
        intake = run.result.intakes[NORTHLINE]
        assert intake.stats.model_candidates_refused == 3
        assert run.observation("R04", "pod-note-bare")["owner_id"] == "priya.nair"
        # The other two records of this history were read honestly and behave as before.
        assert len(run.result.outcome("R04", "late-lakeshore").candidate_load_ids) == 2
    finally:
        run.store.close()


def test_the_same_load_number_at_two_brokerages_cannot_cross_bind(scenarios, tmp_path):
    """Northline and Cedar Ridge each have an LD-51005, with the same PO, BOL and PRO, and each gets
    "POD attached for 51005." A model is only ever handed the asking brokerage's own loads; and when
    a reader hands back the OTHER brokerage's canonical id anyway, it is refused."""
    north, cedar = scenarios.view(NORTHLINE, "LD-51005"), scenarios.view(CEDAR, "LD-51005")
    assert north.ref != cedar.ref
    own = {tenant: {v.ref for v in projection.loads.values()}
           for tenant, projection in scenarios.result.projections.items()}
    asked = scenarios.gateway.invocations_of(Task.PROPOSE_ENTITY_CANDIDATES)
    seen: dict[str, int] = {}
    for request in asked:
        offered = {o.candidate_id for o in request.options}
        owners = [tenant for tenant, refs in own.items() if offered and offered <= refs]
        assert len(owners) == 1, f"a candidate request mixed brokerages: {sorted(offered)}"
        seen[owners[0]] = seen.get(owners[0], 0) + 1
    assert seen == {NORTHLINE: 3, CEDAR: 1}, seen
    assert scenarios.result.outcome("R05", "pod-note-bare").candidate_load_ids == (cedar.load_id,)
    assert cross_tenant_violations(scenarios.conn) == []
    assert shared_reference_population(scenarios.conn) >= 4, "no reference is shared; nothing proved"

    remembered: dict[str, str] = {}

    def crossing(request):
        ids = [o.candidate_id for o in request.options if "LD-51005 (load_ref)" in o.summary]
        if "northline" not in remembered:
            remembered["northline"] = ids[0]
            return candidates((ids[0], "CLEAR", "51005"))
        return candidates((remembered["northline"], "CLEAR", "51005"))

    run = Run(tmp_path, [_scenario("R04"), _scenario("R05")], responder=raw_history_responder(
        {(Task.PROPOSE_ENTITY_CANDIDATES, POD_NOTE_REQUEST): crossing}))
    try:
        foreign = run.view(NORTHLINE, "LD-51005").ref
        assert remembered["northline"] == foreign
        outcome = run.result.outcome("R05", "pod-note-bare")
        assert (outcome.disposition, outcome.candidate_load_ids) == ("UNBOUND", ())
        assert run.result.intakes[CEDAR].stats.model_candidates_refused == 1
        leaked = run.conn.execute(
            "SELECT COUNT(*) FROM identity_binding_claims WHERE tenant = ? AND entity_ref = ?",
            (CEDAR, foreign)).fetchone()[0]
        assert leaked == 0 and cross_tenant_violations(run.conn) == []
    finally:
        run.store.close()


def test_an_exact_reference_binds_without_asking_a_model(scenarios):
    """Deterministic first. Every message and document that carried a reference the mapping table
    resolves exactly was bound by it; a model was asked about correlation only for the four records
    that carried no resolvable reference at all."""
    asked = scenarios.gateway.invocations_of(Task.PROPOSE_ENTITY_CANDIDATES)
    assert len(asked) == 4
    unplaced = {scenarios.result.outcome(h, label).observation_id
                for h, label in (("R04", "pod-note-bare"), ("R04", "late-lakeshore"),
                                 ("R04", "unknown-load"), ("R05", "pod-note-bare"))}
    assert {request.source_id for request in asked} == unplaced
    language = [(h.history.history_id, r.label) for h in scenarios.result.histories
                for r in h.history.records if r.kind in ("message", "document")]
    exact = [r for r in scenarios.ledger.routings if r.reason == "exact_reference"]
    assert len(language) == 21 and len(exact) == len(language) - len(unplaced), (
        len(language), len(exact))
    checkin = scenarios.result.outcome("R01", "driver-checkin")
    assert checkin.disposition == "BOUND" and checkin.observation_id not in unplaced
    assert [c["match_method"] for c in scenarios.claims(checkin.observation_id)] == ["EXACT_ID"]


# ============================================================ money and authority

def test_an_accessorial_statement_never_creates_an_authorization(scenarios):
    """"Invoice attached. Detention is included per approval from Mike." Mike is not a recorded
    human of this brokerage and a sentence is not an approval. The charge stays CLAIMED, the claim
    of approval is recorded as a fraud signal, and a named person is asked whether anyone approved
    it. The detention the invoice then bills is unresolved, not paid."""
    view = scenarios.view(NORTHLINE, "LD-51007")
    assert view.authorizations == []
    detention = view.accessorials["DETENTION"]
    assert detention.lifecycle_state == "CLAIMED" and detention.authorization_id is None
    assert detention.counterparty_asserted_authorization is True
    note = scenarios.observation("R06", "carrier-invoice-note")["parsed"]["payload"]["asserts"]
    assert [(a["type"], a["claims_authorization"], a["approver_named"], a["amount_minor"])
            for a in note] == [("accessorial_claim", True, "Mike", None)]
    types = sorted({x["type"] for x in view.exceptions})
    assert types == ["accessorial_authorization_unresolved", "counterparty_self_authorization"]
    result = view.reconciliations[0]
    line = next(d for d in result.discrepancies if d.line == "DETENTION")
    assert (result.status, line.code, line.authorization) == (
        "DISCREPANT", "ACCESSORIAL_NOT_ON_RATE_CONFIRMATION", "UNRESOLVED")
    assert scenarios.conn.execute(
        "SELECT COUNT(*) FROM approvals WHERE tenant = ?", (NORTHLINE,)).fetchone()[0] == 0
    assert APPROVED_BY_MIKE in scenarios_module.READINGS, "the scenario's message is gone"


def test_a_model_read_rate_mention_cannot_outrank_the_rate_confirmation(scenarios, raw_corpus):
    """The dispatcher wrote "2150 all in"; the rate confirmation says 1,950.00; the invoice bills
    2,150.00. The buy rate is the rate confirmation's. The conversational figure is retained as a
    guess no consequential read can use, and the invoice is DISCREPANT against the rate con."""
    corpus_run, _, _ = raw_corpus
    for run, load in ((scenarios, "LD-51007"), (corpus_run, "LD-48340")):
        view = run.view(NORTHLINE, load)
        movement = next(iter(view.movements.values()))
        said = movement.field_of("pre_ratecon_buy").facts
        assert [(f.value.amount_minor, f.provenance_class, f.may_gate) for f in said] == [
            (215000, "MODEL_INFERRED", False)], load
        assert movement.value("pre_ratecon_buy") is None and (
            movement.condition("pre_ratecon_buy") == "unknown"), load
        result = view.reconciliations[0]
        assert result.expected.amount_minor == 195000, load
        assert result.expected_basis.startswith("rate_confirmation:"), result.expected_basis
        assert "LINEHAUL_MISMATCH" in {d.code for d in result.discrepancies}, load
        ratecon = next(iter(view.rate_confirmations.values()))
        assert ratecon.field_of("linehaul").facts[0].provenance_class == "MODEL_EXTRACTED"
        assert "owed_to_carrier.linehaul" in {c["field"] for c in view.conflicts}, load


def test_an_amount_with_no_stated_currency_is_retained_as_a_guess(raw_corpus):
    """"we'll need detention 175" names no currency. The amount is read in the load's own currency
    and, because that currency was ASSUMED, the fact is weakened: it cannot dispute or gate. The
    invoice line, which states its currency, is the one a consequential read uses."""
    run, _, _ = raw_corpus
    amount = run.view(NORTHLINE, "LD-48219").accessorials["DETENTION"].field_of("amount")
    by_class = sorted((f.provenance_class, f.value.amount_minor, f.value.currency)
                      for f in amount.facts)
    assert by_class == [("MODEL_EXTRACTED", 17500, "USD"), ("MODEL_INFERRED", 17500, "USD")]
    assert [f.provenance_class for f in amount.gating_facts()] == ["MODEL_EXTRACTED"]


# ============================================================ conflicts

def test_conflicting_appointment_messages_raise_a_conflict_not_a_guessed_overwrite(scenarios):
    """The system of record says today 15:00-17:00. The carrier says the receiver pushed it to 10
    tomorrow. The customer says today at 3. Nobody's statement replaces anybody else's: the window
    is in conflict, it offers NO value, and a named human owns the decision."""
    view = scenarios.view(NORTHLINE, "LD-51008")
    window = view.appointments["S2"].field_of("window")
    assert view.appointments["S2"].condition("window") == "conflicting"
    assert view.appointments["S2"].value("window") is None, "a conflicting field offered a value"
    conflict = next(c for c in view.conflicts if c["field"] == "window")
    assert conflict["state"] in ("RAISED", "OPEN", "ESCALATED")
    assert conflict["owner_id"] == "dana.ortiz"
    stated = {p["stated_value"].split(" ")[0]: p["provenance_class"]
              for p in conflict["parties"]}
    assert stated == {"2026-06-21T15:00..2026-06-21T17:00": "SYSTEM_IMPORTED",
                      "2026-06-22T10:00..2026-06-22T10:00": "MODEL_EXTRACTED",
                      "2026-06-21T15:00..2026-06-21T15:00": "MODEL_EXTRACTED"}, stated
    assert len(window.facts) == 3 and len(window.latest_by_source()) == 3
    # The status is still the system of record's: a sentence did not confirm or cancel anything.
    assert {f.provenance_class for f in view.appointments["S2"].field_of("status").facts} == {
        "SYSTEM_IMPORTED"}

    # Two parties writing to ONE inbox, and no system appointment at all: still a Conflict.
    one_inbox = scenarios.view(NORTHLINE, "LD-51009")
    conflict = next(c for c in one_inbox.conflicts if c["field"] == "window")
    assert {p["provenance_class"] for p in conflict["parties"]} == {"MODEL_EXTRACTED"}
    assert len(conflict["parties"]) >= 2 and one_inbox.appointments["S2"].value("window") is None
    assert not [e for e in one_inbox.expectations if e["expected_type"].startswith("arrival")], (
        "an appointment nobody but a counterparty stated raised an arrival deadline")


def test_a_drivers_delivered_against_tracking_is_a_conflict_not_a_verdict(scenarios):
    view = scenarios.view(NORTHLINE, "LD-51010")
    assert view.delivered_claims()[0].field_of("status").facts[0].provenance_class == (
        "MODEL_EXTRACTED")
    conflict = next(c for c in view.conflicts if c["field"] == "tracking_status")
    assert sorted(p["stated_value"] for p in conflict["parties"]) == ["AT_DELIVERY", "DELIVERED"]
    assert view.invoice is not None and view.invoice.lifecycle_state == "NOT_ELIGIBLE"


# ============================================================ failure and replay

@pytest.mark.parametrize("failure", [
    TransportFailure("APITimeoutError"),
    ProviderRejection("AuthenticationError:401"),
    {"category": "STATUS_UPDATE", "statuses": "not a list"},
    "<<<not json>>>",
])
def test_a_failed_reading_routes_to_a_human_and_corrupts_nothing(tmp_path, failure):
    """A timeout, a rejection, a malformed reply. The message is still observed, parsed and bound by
    its exact reference; it asserts NOTHING; and the person who owns triage is told to read it. No
    status, no promise, no deadline and no effect row was conjured from a reading that failed."""
    run = Run(tmp_path, [_scenario("R01")], responder=raw_history_responder(
        {(Task.INTERPRET_MESSAGE, CHECK_IN): lambda request: failure}))
    try:
        outcome = run.result.outcome("R01", "driver-checkin")
        assert outcome.disposition == "BOUND"
        observation = run.observation("R01", "driver-checkin")
        assert observation["state"] == "BOUND"
        parsed = observation["parsed"]
        assert parsed["payload"]["asserts"] == [] and parsed["payload"]["body"] == CHECK_IN
        assert parsed["interpretation"]["status"] == "FAILED"
        view = run.view(NORTHLINE, "LD-51001")
        assert not [t for t in view.tracking if t.value("signal") == "driver_assertion"]
        assert not [e for e in view.expectations if e["expected_type"] == "counterparty_update"]
        assert view.commitments == [] and view.conflicts == []
        told = [x for x in view.exceptions if x["type"] == "interpretation_unavailable"]
        assert len(told) == 1 and told[0]["owner_id"] == "priya.nair"
        assert told[0]["entity_ref"] == view.ref and CHECK_IN not in told[0]["summary"]
        intake = run.result.intakes[NORTHLINE]
        assert intake.stats.model_reading_failures == 1 and intake.stats.model_readings == 0
        assert set(intake.foundation.effect_surface_counts().values()) == {0}
        assert len(view.messages) == 1, "the message itself must still be on the load"
        assert run.ledger.calls[-1].outcome in ("PROVIDER_FAILURE", "SCHEMA_FAILURE")
    finally:
        run.store.close()


def test_replaying_a_recorded_run_calls_nothing_and_reproduces_the_projection(tmp_path,
                                                                             monkeypatch):
    """Record the nine histories once; replay them with every socket call forbidden. The replayed
    run reaches the same canonical projection, byte for byte, and reports no live tokens."""
    path = tmp_path / "recording.json"
    first = Run(tmp_path, build_raw_histories(), responder=raw_history_responder(),
                recording=RecordingStore(path), name="recorded.db")
    digests = {t: p.digest() for t, p in first.result.projections.items()}
    recorded = len(first.gateway.invocations)
    first.store.close()
    # 24 readings, 24 recordings: the two brokerages' identical POD note was SENT at different
    # times, and when a message was sent is part of the question (a promise runs from it).
    assert recorded == 24 and len(RecordingStore(path)) == 24

    def no_network(*args, **kwargs):
        raise AssertionError("the replay path opened a socket")
    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    replay = ReplayGateway(provider="scripted", model="scripted-reader",
                           recording=RecordingStore(path), ledger=InferenceLedger())
    second = Run(tmp_path, build_raw_histories(), gateway=replay, name="replayed.db")
    try:
        assert {t: p.digest() for t, p in second.result.projections.items()} == digests
        assert second.mismatches() == []
        summary = second.ledger.summary()
        assert summary["served_from"] == {"replay": 24} and summary["failures"] == 0
        assert summary["live_tokens"] == {"input_tokens": 0, "cached_input_tokens": 0,
                                          "output_tokens": 0, "reasoning_tokens": 0}
        per_load = summary["calls_by_correlation"]
        assert per_load[second.view(NORTHLINE, "LD-51007").ref]["calls"] == 4
        assert per_load["uncorrelated"]["calls"] >= 4
    finally:
        second.store.close()


def test_the_projection_reads_a_stored_reading_and_never_asks_again(scenarios):
    """Replay is structurally inert: rebuilding the freight picture is a pure read of stored
    readings. Projecting again — as every later ingest does — makes no model call."""
    before = len(scenarios.gateway.invocations)
    digests = {t: i.projection().digest() for t, i in scenarios.result.intakes.items()}
    assert {t: i.projection().digest() for t, i in scenarios.result.intakes.items()} == digests
    assert len(scenarios.gateway.invocations) == before == 24


# ============================================================ the eval's own scorer

def test_the_labeled_eval_covers_what_it_claims_and_its_scorer_can_fail():
    """A scorer that cannot fail is a decoration. Every required category has a case; a correct
    reading scores full marks on a counted denominator; a wrong one fails the field it got wrong;
    and a call that failed is a failure, never an empty pass."""
    covered = coverage()
    assert set(covered) == set(REQUIRED_TAGS) and all(covered.values()), covered
    assert len(LABELED_MESSAGES) >= 20 and len(CORRELATION_CASES) >= 5
    by_id = {c.case_id: c for c in LABELED_MESSAGES}
    cases = [by_id["LM02"], by_id["LM05"], by_id["LM07"]]
    right = {
        by_id["LM02"].body: message(
            statuses=[status("ARRIVED", "UNSPECIFIED", "Driver checked in at 12:42")],
            commitments=[promise("I'll update you in an hour", minutes=60, text="in an hour")]),
        by_id["LM05"].body: message(
            documents=[paper("CARRIER_INVOICE", "ATTACHED", "Invoice attached")],
            accessorials=[charge("DETENTION", "Detention is included per approval from Mike",
                                 approved=True, approver="Mike")]),
        by_id["LM07"].body: message(
            references=[reference("LOAD_NUMBER", "48291", "this is for 48291",
                                  role="CORRECTED_TO")],
            corrections=[correction("LOAD_REFERENCE", "That was the wrong load number")]),
    }
    perfect = run_labeled_messages(ScriptedGateway(lambda t, r: right.get(r.body)), cases)
    assert (perfect["cases_fully_correct"], perfect["fields_checked"],
            perfect["fields_correct"], perfect["failed_calls"]) == (3, 26, 26, 0), perfect
    assert perfect["items_dropped_by_grounding"] == 1, "the unplaced arrival was not dropped"

    wrong = dict(right)
    wrong[by_id["LM02"].body] = message(
        statuses=[status("ARRIVED", "PICKUP", "Driver checked in at 12:42")],
        commitments=[promise("I'll update you in an hour", minutes=600, text="in an hour")])
    wrong[by_id["LM05"].body] = None
    scored = run_labeled_messages(
        ScriptedGateway(lambda t, r: wrong.get(r.body) or ProviderRejection("refused")), cases)
    assert (scored["cases_fully_correct"], scored["failed_calls"],
            scored["fields_checked"]) == (1, 1, 17), scored
    failed = next(r for r in scored["results"] if r["case"] == "LM02")["fields"]
    assert sorted(failed) == ["commitments", "statuses"], failed

    by_case = {c.case_id: c for c in CORRELATION_CASES}

    def proposer(task, request):
        case = next(c for c in CORRELATION_CASES if c.text == request.text)
        picked = [(i, "CLEAR", request.text.split("\n")[-1][:12]) for i in sorted(case.expect)]
        if case.case_id == "CC04":
            picked.append((FOREIGN_ID, "CLEAR", "LD-48219"))
        if case.case_id == "CC02":
            picked = picked[:1]                          # picks ONE of two equally plausible loads
        return candidates(*picked)

    correlation = run_correlation_cases(ScriptedGateway(proposer))
    assert correlation["cases"] == 6 and correlation["ids_refused"] == 1
    wrong_cases = [r["case"] for r in correlation["results"] if not r["ok"]]
    assert wrong_cases == ["CC02"], wrong_cases
    assert by_case["CC04"].expect == frozenset()
    trap = next(r for r in correlation["results"] if r["case"] == "CC04")
    assert trap["ok"] and FOREIGN_ID in trap["proposed"] and trap["observed"] == []
    unstated = appointment("DELIVERY", "x", day=None, start="09:00")
    assert unstated["day_offset"] is None


# ============================================================ what the model actually said

def test_the_recorded_luna_readings_replay_offline_and_reproduce_the_measured_result(monkeypatch):
    """The live eval's result, pinned. The readings gpt-6-luna gave on 2026-10-02 are committed;
    replaying them — every socket call forbidden — through TODAY's grounding, normalization and
    spine must reproduce the scores that were reported. So a change to the deterministic layer that
    would mishandle what a real model really says fails here, at no cost.

    A REPLAY_MISS means the question changed since it was last asked: a prompt, an output schema, a
    labeled case or a corpus message was edited. That is not a flake. Re-measure, and commit the new
    recording with the change:

        NEYMA_LIVE_INFERENCE=1 .venv/bin/python scripts/run_freight_interpretation_eval.py \\
            --live --stage all

    ### THIS IS A RECORD OF ONE MODEL ON A SYNTHETIC CORPUS, NOT EVIDENCE ABOUT CUSTOMERS, and the
    recording is a development optimization: nothing consequential reads it."""
    def no_network(*args, **kwargs):
        raise AssertionError("replaying the recorded readings opened a socket")
    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    assert LUNA_RECORDING.is_file(), f"{LUNA_RECORDING} is not committed"

    ledger = InferenceLedger()
    gateway = ReplayGateway(provider="openai", model="gpt-6-luna", reasoning_effort="low",
                            recording=RecordingStore(LUNA_RECORDING), ledger=ledger)
    labeled = run_stage("labeled", gateway, ledger)
    corpus = run_stage("corpus", gateway, ledger)
    nine = run_stage("scenarios", gateway, ledger)
    assert calls_failed(ledger) == {}, (
        f"{calls_failed(ledger)}: the committed recording no longer answers the questions the "
        f"code asks. Re-measure with the live eval and commit the new recording.")

    messages = labeled["messages"]
    assert (messages["cases"], messages["cases_fully_correct"], messages["fields_checked"],
            messages["fields_correct"], messages["failed_calls"]) == (24, 24, 209, 209, 0), {
        r["case"]: r["fields"] for r in messages["results"] if not r["passed"]}
    assert (labeled["correlation"]["cases_correct"], labeled["correlation"]["ids_refused"]) == (
        6, 0), labeled["correlation"]["results"]
    assert labeled["commitments_only_task"]["cases_correct"] == 4

    assert (corpus["histories"], corpus["labeled_outcomes_checked"],
            corpus["labeled_outcomes_failed"]) == (20, 264, 0), corpus["mismatches"]
    assert (corpus["model_readings"], corpus["model_reading_failures"],
            corpus["model_candidates_refused"], corpus["external_effect_rows"],
            corpus["wrong_cross_tenant_mappings"]) == (45, 0, 0, 0, 0)
    # Where the model's reading differs from a fixture's, it read MORE that is really there:
    # "loaded and rolling" is LOADED and IN_TRANSIT; the fixture structured only LOADED.
    agreement = corpus["message_agreement"]
    assert (agreement["messages"], agreement["messages_agreeing"]) == (22, 20)
    for row in agreement["differences"]:
        extra = [fact for fact in row["observed"] if fact not in row["expected"]]
        assert all(fact in row["observed"] for fact in row["expected"]), row
        assert extra == [("status", "IN_TRANSIT", None)], row

    assert (nine["histories"], nine["labeled_outcomes_checked"],
            nine["labeled_outcomes_failed"]) == (9, 88, 0), nine["mismatches"]
    assert (nine["model_reading_failures"], nine["model_candidates_refused"],
            nine["model_inferred_ambiguities"], nine["external_effect_rows"]) == (0, 0, 3, 0)

    summary = ledger.summary()
    assert summary["served_from"] == {"replay": 105} and summary["live_tokens"]["input_tokens"] == 0
    assert summary["tokens"]["input_tokens"] > 200_000, "the recorded token counts were lost"
    assert {call.model for call in ledger.calls} == {"gpt-6-luna"}
