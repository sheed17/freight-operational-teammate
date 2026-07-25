"""Tests for the Slack transport over the signed delivery action intake."""

import hashlib
import hmac
import json
from pathlib import Path
from urllib.parse import urlencode
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from generate_realistic_corpus import generate  # noqa: E402
from freight_recon.delivery import (  # noqa: E402
    DeliveryActionStatus,
    DeliverySigner,
    build_delivery_message,
    record_delivery_message,
)
from freight_recon.reconciliation import FreightLoadForReconciliation  # noqa: E402
from freight_recon.review import build_review_payload, record_review_payload  # noqa: E402
from freight_recon.review_actions import ReviewDecision  # noqa: E402
from freight_recon.slack_adapter import (  # noqa: E402
    SlackDeliveryAdapter,
    SlackError,
    SlackSignatureError,
    render_slack_message,
    verify_slack_signature,
)
from freight_recon.workflow import WorkflowStore, process_load_packet  # noqa: E402

_SLACK_SECRET = b"slack-signing-secret"


def _delivered(tmp_path, load_id):
    signer = DeliverySigner(b"delivery-secret")
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


def _slack_body(message, decision):
    button = next(b for b in message.actions if b.decision == decision)
    payload = {
        "type": "block_actions",
        "user": {"id": "U123", "username": "rasheed"},
        "response_url": "https://hooks.slack.test/abc",
        "actions": [{"action_id": "act_0", "value": button.signed_token}],
    }
    return urlencode({"payload": json.dumps(payload)})


def _sign(body, timestamp):
    base = f"v0:{timestamp}:{body}".encode("utf-8")
    return "v0=" + hmac.new(_SLACK_SECRET, base, hashlib.sha256).hexdigest()


def test_render_slack_message_has_buttons_with_tokens(tmp_path):
    store, _, message, _ = _delivered(tmp_path, "LD-560003")
    rendered = render_slack_message(message)

    assert rendered["blocks"][0]["type"] == "header"
    actions = next(b for b in rendered["blocks"] if b["type"] == "actions")
    assert actions["elements"], "expected action buttons"
    for element, button in zip(actions["elements"], message.actions):
        assert element["value"] == button.signed_token
        if "style" in element:
            assert element["style"] in {"primary", "danger"}
    store.close()


def test_valid_slack_signature_accepted(tmp_path):
    store, _, message, _ = _delivered(tmp_path, "LD-560003")
    body = _slack_body(message, ReviewDecision.APPROVE_FULL_AMOUNT)
    verify_slack_signature(_SLACK_SECRET, timestamp="1000", body=body, signature=_sign(body, "1000"), now=1000)
    store.close()


def test_bad_slack_signature_rejected(tmp_path):
    store, _, message, _ = _delivered(tmp_path, "LD-560003")
    body = _slack_body(message, ReviewDecision.APPROVE_FULL_AMOUNT)
    with pytest.raises(SlackSignatureError):
        verify_slack_signature(_SLACK_SECRET, timestamp="1000", body=body, signature="v0=deadbeef", now=1000)
    store.close()


def test_stale_slack_timestamp_rejected(tmp_path):
    store, _, message, _ = _delivered(tmp_path, "LD-560003")
    body = _slack_body(message, ReviewDecision.APPROVE_FULL_AMOUNT)
    signature = _sign(body, "1000")
    # 10 minutes later is outside Slack's 5-minute replay window.
    with pytest.raises(SlackSignatureError):
        verify_slack_signature(_SLACK_SECRET, timestamp="1000", body=body, signature=signature, now=1600)
    store.close()


def test_handle_interaction_applies_and_updates_message(tmp_path):
    store, signer, message, loads = _delivered(tmp_path, "LD-560008")
    adapter = SlackDeliveryAdapter(store, signer=signer, signing_secret=_SLACK_SECRET)
    body = _slack_body(message, ReviewDecision.REQUEST_BACKUP)
    signature = _sign(body, "2000")

    outcome, update = adapter.handle_interaction(
        body=body,
        timestamp="2000",
        signature=signature,
        follow_up_loads=loads,
        now=2000,
    )

    assert outcome.status == DeliveryActionStatus.APPLIED
    assert update["replace_original"] is True
    banner = next(
        b for b in update["blocks"] if b["type"] == "context" and "Backup requested by Rasheed" in b["elements"][0]["text"]
    )
    assert banner is not None
    events = [e["event_type"] for e in store.audit_events(message.run_id)]
    assert "slack_interaction_received" in events
    assert "delivery_action_applied" in events
    store.close()


def test_handle_interaction_rejects_forged_slack_request(tmp_path):
    store, signer, message, loads = _delivered(tmp_path, "LD-560008")
    adapter = SlackDeliveryAdapter(store, signer=signer, signing_secret=_SLACK_SECRET)
    body = _slack_body(message, ReviewDecision.REQUEST_BACKUP)

    with pytest.raises(SlackSignatureError):
        adapter.handle_interaction(body=body, timestamp="2000", signature="v0=bad", follow_up_loads=loads, now=2000)
    # A forged Slack request must not transition the run.
    run = next(r for r in store.list_runs() if r.id == message.run_id)
    assert run.state.value == "NEEDS_REVIEW"
    store.close()


def test_adapter_requires_non_empty_signing_secret(tmp_path):
    store, signer, _, _ = _delivered(tmp_path, "LD-560008")
    with pytest.raises(SlackError, match="signing secret"):
        SlackDeliveryAdapter(store, signer=signer, signing_secret="")
    store.close()
