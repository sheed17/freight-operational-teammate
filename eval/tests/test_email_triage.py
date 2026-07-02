"""Tests for the email-triage relevance gate: relevant? whose load? how to route? — fail closed."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.email_triage import (  # noqa: E402
    FREIGHT_OPS,
    NOISE,
    ROUTE_ASK,
    ROUTE_IGNORE,
    ROUTE_PROCESS,
    triage_email,
)
from freight_recon.ingestion import LoadIndex, ParsedAttachment, ParsedEmail  # noqa: E402
from freight_recon.reconciliation import FreightLoadForReconciliation  # noqa: E402


def _load(**kw) -> FreightLoadForReconciliation:
    base = dict(
        load_id="LD-560003",
        invoice_number="INV-9003",
        carrier="Redline Carriers",
        customer="Acme Foods",
        origin="Memphis, TN",
        destination="Dallas, TX",
        pickup_date="2026-06-20",
        delivery_date="2026-06-22",
        rate_linehaul="2000.00",
        rate_fuel="300.00",
        invoice_linehaul="2000.00",
        invoice_fuel="300.00",
    )
    base.update(kw)
    return FreightLoadForReconciliation.model_validate(base)


def _email(subject="", attachments=None, from_addr="ap@carrier.com") -> ParsedEmail:
    return ParsedEmail(from_addr=from_addr, subject=subject, attachments=attachments or [])


def _att(filename, text_hint="", content_type="application/pdf") -> ParsedAttachment:
    return ParsedAttachment(
        filename=filename, content_type=content_type, sha256="x" * 64, size_bytes=1, text_hint=text_hint
    )


def _fake_model(payload: dict):
    return lambda _prompt: json.dumps(payload)


# --------------------------------------------------------------------------- deterministic ID path


def test_identifier_in_subject_processes_without_a_model():
    loads = [_load()]
    d = triage_email(_email(subject="Invoice for LD-560003"), LoadIndex(loads))
    assert d.relevance == FREIGHT_OPS
    assert d.load_id == "LD-560003"
    assert d.link_method == "identifier"
    assert d.route == ROUTE_PROCESS
    assert d.used_model is False


def test_identifier_in_attachment_filename_processes():
    loads = [_load()]
    email = _email(subject="here you go", attachments=[_att("001_LD-560003_carrier_invoice.pdf")])
    d = triage_email(email, LoadIndex(loads))
    assert d.load_id == "LD-560003"
    assert d.category == "invoice"
    assert d.route == ROUTE_PROCESS


# --------------------------------------------------------------------------- no-model fallback


def test_no_model_freight_keywords_but_no_id_asks_a_human():
    loads = [_load()]
    # freight-looking (rate confirmation) but no known identifier and no model -> never auto-process
    d = triage_email(_email(subject="rate confirmation for next week"), LoadIndex(loads))
    assert d.relevance == FREIGHT_OPS
    assert d.load_id is None
    assert d.route == ROUTE_ASK
    assert "no_model" in d.flags


def test_no_model_no_freight_signal_is_ignored_as_noise():
    loads = [_load()]
    d = triage_email(_email(subject="50% off summer sale!!!", from_addr="deals@shop.com"), LoadIndex(loads))
    assert d.relevance == NOISE
    assert d.route == ROUTE_IGNORE


# --------------------------------------------------------------------------- model fuzzy path


def test_model_fuzzy_links_to_known_load_and_processes():
    loads = [_load()]
    # No clean id, but the carrier + lane match; the model links it to the known load with confidence.
    email = _email(subject="Our invoice for the Memphis to Dallas run last week", from_addr="billing@redline.com")
    model = _fake_model(
        {"relevance": "freight_ops", "category": "invoice", "load_id": "LD-560003",
         "confidence": 0.92, "reason": "carrier and lane match the known load"}
    )
    d = triage_email(email, LoadIndex(loads), loads, complete=model)
    assert d.route == ROUTE_PROCESS
    assert d.load_id == "LD-560003"
    assert d.link_method == "model_fuzzy"
    assert d.used_model is True


def test_model_noise_is_ignored():
    loads = [_load()]
    model = _fake_model({"relevance": "noise", "load_id": None, "confidence": 0.95, "reason": "newsletter"})
    d = triage_email(_email(subject="Logistics Weekly Newsletter"), LoadIndex(loads), loads, complete=model)
    assert d.relevance == NOISE
    assert d.route == ROUTE_IGNORE


def test_model_invented_load_id_is_discarded_and_asks():
    loads = [_load()]
    # The model returns a load id we never supplied — a hallucination / injection must not link.
    model = _fake_model(
        {"relevance": "freight_ops", "category": "invoice", "load_id": "LD-999999",
         "confidence": 0.99, "reason": "totally confident (but wrong)"}
    )
    d = triage_email(_email(subject="invoice attached"), LoadIndex(loads), loads, complete=model)
    assert d.load_id is None
    assert d.route == ROUTE_ASK
    assert "model_invented_load_id_discarded" in d.flags


def test_model_freight_but_low_confidence_asks_not_processes():
    loads = [_load()]
    model = _fake_model(
        {"relevance": "freight_ops", "category": "invoice", "load_id": "LD-560003",
         "confidence": 0.6, "reason": "maybe this load"}
    )
    d = triage_email(_email(subject="invoice"), LoadIndex(loads), loads, complete=model)
    assert d.route == ROUTE_ASK  # below process_min -> ask, never straight into the money pipeline


def test_model_freight_but_unlinked_asks():
    loads = [_load()]
    model = _fake_model(
        {"relevance": "freight_ops", "category": "dispute", "load_id": None,
         "confidence": 0.9, "reason": "a billing dispute but no load named"}
    )
    d = triage_email(_email(subject="short pay dispute"), LoadIndex(loads), loads, complete=model)
    assert d.route == ROUTE_ASK
    assert d.load_id is None
    assert "unlinked" in d.flags


def test_bad_model_json_falls_back_to_keywords():
    loads = [_load()]
    d = triage_email(
        _email(subject="carrier invoice enclosed"), LoadIndex(loads), loads,
        complete=lambda _p: "not json at all",
    )
    # falls back to the deterministic keyword path (freight signal -> ask)
    assert d.route == ROUTE_ASK
    assert d.used_model is False


def test_identifier_beats_model_no_call_needed():
    loads = [_load()]

    def exploding_model(_p):
        raise AssertionError("model must not be called when an identifier links")

    d = triage_email(_email(subject="LD-560003 invoice"), LoadIndex(loads), loads, complete=exploding_model)
    assert d.link_method == "identifier"
    assert d.route == ROUTE_PROCESS
