"""Tests for the email transport over the signed delivery action intake."""

import email as email_lib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from generate_realistic_corpus import generate  # noqa: E402
from freight_recon.delivery import (  # noqa: E402
    DeliveryActionStatus,
    DeliveryExpiredError,
    DeliverySigner,
    build_delivery_message,
    record_delivery_message,
)
from freight_recon.email_adapter import (  # noqa: E402
    EmailDeliveryAdapter,
    EmailOutbox,
    build_email_message,
    parse_email_action_token,
    render_email_mime,
)
from freight_recon.reconciliation import FreightLoadForReconciliation  # noqa: E402
from freight_recon.review import build_review_payload, record_review_payload  # noqa: E402
from freight_recon.review_actions import ReviewDecision  # noqa: E402
from freight_recon.workflow import WorkflowStore, process_load_packet  # noqa: E402


def _delivered(tmp_path, load_id, *, signer=None):
    signer = signer or DeliverySigner(b"delivery-secret")
    corpus = tmp_path / "corpus"
    generate(corpus, 8, seed=42)
    raw = json.loads((corpus / "ground_truth" / "loads_and_scenarios.json").read_text())
    loads = [FreightLoadForReconciliation.from_mapping(item) for item in raw.values()]
    load_by_id = {load.load_id: load for load in loads}
    store = WorkflowStore(tmp_path / "workflow.sqlite3", tenant="tenant-fixture-a")
    seen: set[tuple[str, str]] = set()
    selected = None
    for load in loads:
        run = process_load_packet(
            store,
            load,
            primary_document_path=corpus / load.documents["carrier_invoice"],
            seen_invoice_keys=seen,
        )
        payload = build_review_payload(run, load, age_hours=48)
        if payload is not None:
            record_review_payload(store, payload)
            if load.load_id == load_id:
                selected = payload
    assert selected is not None
    message = build_delivery_message(selected, signer, actor="Rasheed")
    record_delivery_message(store, message)
    return store, signer, message, load_by_id


def _link_for(email_msg, decision):
    return next(a.url for a in email_msg.actions if a.decision == decision.value)


def test_build_email_has_signed_action_links_and_both_parts(tmp_path):
    store, _, message, _ = _delivered(tmp_path, "LD-560003")
    email_msg = build_email_message(message, to="rasheed@neyma-test-freight.test")

    assert email_msg.actions, "expected action links"
    for action, button in zip(email_msg.actions, message.actions):
        # The token is URL-encoded in the link (base64 padding becomes %3D); parse to compare.
        assert parse_email_action_token(action.url) == button.signed_token

    mime = email_lib.message_from_string(render_email_mime(email_msg))
    assert mime.is_multipart()
    subtypes = {part.get_content_subtype() for part in mime.walk()}
    assert {"plain", "html"} <= subtypes
    store.close()


def test_parse_email_action_token_roundtrips(tmp_path):
    store, _, message, _ = _delivered(tmp_path, "LD-560003")
    email_msg = build_email_message(message, to="rasheed@neyma-test-freight.test")
    link = _link_for(email_msg, ReviewDecision.APPROVE_FULL_AMOUNT)
    button = next(b for b in message.actions if b.decision == ReviewDecision.APPROVE_FULL_AMOUNT)
    assert parse_email_action_token(link) == button.signed_token
    store.close()


def test_handle_action_link_applies_and_mutates(tmp_path):
    store, signer, message, loads = _delivered(tmp_path, "LD-560008")
    adapter = EmailDeliveryAdapter(store, signer=signer)
    email_msg = adapter.build(message, to="rasheed@neyma-test-freight.test")
    link = _link_for(email_msg, ReviewDecision.REQUEST_BACKUP)

    outcome = adapter.handle_action_link(link, follow_up_loads=loads)

    assert outcome.status == DeliveryActionStatus.APPLIED
    assert "Backup requested by Rasheed" in outcome.message.status_banner
    assert outcome.follow_up_created is True
    store.close()


def test_expired_email_link_is_rejected(tmp_path):
    from datetime import datetime, timezone

    store, signer, message, _ = _delivered(tmp_path, "LD-560003")
    adapter = EmailDeliveryAdapter(store, signer=signer)
    # Issue a token in the past with a short TTL, then build a link from it by hand.
    token = signer.issue(
        message.run_id,
        ReviewDecision.APPROVE_FULL_AMOUNT,
        amount="3634.50",
        issued_at=datetime(2026, 6, 15, 9, 0, tzinfo=timezone.utc),
        ttl_seconds=60,
    )
    link = f"http://localhost:8000/email/action?run={message.run_id}&token={token}"
    # submit_signed_action uses real "now", which is well past the 60s TTL.
    with pytest.raises(DeliveryExpiredError):
        adapter.handle_action_link(link)
    store.close()


def test_outbox_writes_eml_and_marks_not_sent(tmp_path):
    store, _, message, _ = _delivered(tmp_path, "LD-560003")
    email_msg = build_email_message(message, to="rasheed@neyma-test-freight.test")
    outbox = EmailOutbox(tmp_path / "outbox", outbound_enabled=False)

    record = outbox.deliver(email_msg)

    assert record.sent is False
    assert Path(record.path).exists()
    assert "outbound disabled" in record.note
    store.close()
