"""Tests for the channel-neutral delivery adapter with signed action intake."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from generate_realistic_corpus import generate  # noqa: E402
from freight_recon.delivery import (  # noqa: E402
    DeliveryActionStatus,
    DeliveryExpiredError,
    DeliverySecretError,
    DeliverySignatureError,
    DeliverySigner,
    build_delivery_message,
    redact_delivery_message,
    record_delivery_message,
    render_delivery_message,
    submit_signed_action,
)
from freight_recon.reconciliation import FreightLoadForReconciliation  # noqa: E402
from freight_recon.review import build_review_payload, record_review_payload  # noqa: E402
from freight_recon.review_actions import ReviewDecision  # noqa: E402
from freight_recon.workflow import WorkflowError, WorkflowState, WorkflowStore, process_load_packet  # noqa: E402


def _delivered(tmp_path, load_id, *, signer=None, now=None):
    """Process the corpus, deliver a recorded message for ``load_id``, and return context."""
    signer = signer or DeliverySigner(b"test-secret")
    corpus = tmp_path / "corpus"
    generate(corpus, 8, seed=42)
    raw = json.loads((corpus / "ground_truth" / "loads_and_scenarios.json").read_text())
    loads = [FreightLoadForReconciliation.from_mapping(item) for item in raw.values()]
    load_by_id = {load.load_id: load for load in loads}
    store = WorkflowStore(tmp_path / "workflow.sqlite3", tenant="tenant-fixture-a")
    seen: set[tuple[str, str]] = set()
    selected_payload = None
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
                selected_payload = payload
    assert selected_payload is not None
    message = build_delivery_message(selected_payload, signer, actor="Rasheed", issued_at=now)
    record_delivery_message(store, message)
    return store, signer, selected_payload, message, load_by_id


def _token_for(message, decision):
    button = next(b for b in message.actions if b.decision == decision)
    return button.signed_token


def test_valid_signed_action_is_accepted_and_applies(tmp_path):
    store, signer, _, message, loads = _delivered(tmp_path, "LD-560003")
    token = _token_for(message, ReviewDecision.APPROVE_EXPECTED_AMOUNT)

    outcome = submit_signed_action(store, token, signer=signer, follow_up_loads=loads)

    assert outcome.status == DeliveryActionStatus.APPLIED
    assert outcome.from_state == WorkflowState.NEEDS_REVIEW
    assert outcome.to_state == WorkflowState.APPROVED
    assert outcome.follow_up_created is True
    events = [e["event_type"] for e in store.audit_events(outcome.run_id)]
    assert "delivery_action_received" in events
    assert "delivery_action_applied" in events
    assert "follow_up_draft_created" in events
    store.close()


def test_tampered_signature_is_rejected(tmp_path):
    store, signer, _, message, _ = _delivered(tmp_path, "LD-560003")
    token = _token_for(message, ReviewDecision.APPROVE_EXPECTED_AMOUNT)
    body, signature = token.split(".", 1)
    tampered = f"{body}.{'0' * len(signature)}"

    with pytest.raises(DeliverySignatureError):
        submit_signed_action(store, tampered, signer=signer)
    # A rejected-before-apply token must not transition the run.
    run = next(r for r in store.list_runs() if r.id == message.run_id)
    assert run.state == WorkflowState.NEEDS_REVIEW
    # The rejection is audited under the system sentinel (claims are untrusted), with a fingerprint.
    security = [
        e for e in store.security_events()
        if e["event_type"] == "delivery_action_rejected"
    ]
    assert security and security[-1]["payload"]["failure"] == "signature"
    assert "token_fingerprint" in security[-1]["payload"]
    store.close()


def test_from_env_requires_secret_unless_local_dev_is_explicit(monkeypatch):
    monkeypatch.delenv("NEYMA_DELIVERY_SECRET", raising=False)
    monkeypatch.delenv("NEYMA_ALLOW_LOCAL_DELIVERY_SECRET", raising=False)

    with pytest.raises(DeliverySecretError):
        DeliverySigner.from_env()

    assert isinstance(DeliverySigner.from_env(allow_local_dev=True), DeliverySigner)


def test_recorded_delivery_message_redacts_signed_tokens(tmp_path):
    store, _, _, message, _ = _delivered(tmp_path, "LD-560003")

    event = next(e for e in store.audit_events(message.run_id) if e["event_type"] == "delivery_message_created")
    recorded = event["payload"]["message"]
    assert recorded["actions"][0]["signed_token"].startswith("redacted:")
    assert recorded["actions"][0]["signed_token"] != message.actions[0].signed_token
    assert redact_delivery_message(message).actions[0].signed_token.startswith("redacted:")
    store.close()


def test_tampered_claims_are_rejected(tmp_path):
    """Re-encoding the claims body without the secret must fail signature verification."""
    import base64

    store, signer, payload, message, _ = _delivered(tmp_path, "LD-560003")
    token = _token_for(message, ReviewDecision.APPROVE_FULL_AMOUNT)
    body, _ = token.split(".", 1)
    claims = json.loads(base64.urlsafe_b64decode(body.encode("ascii")))
    claims["amount"] = "999999.00"
    forged_body = base64.urlsafe_b64encode(json.dumps(claims).encode("utf-8")).decode("ascii")
    forged = f"{forged_body}.{token.split('.', 1)[1]}"

    with pytest.raises(DeliverySignatureError):
        submit_signed_action(store, forged, signer=signer)
    store.close()


def test_expired_action_is_rejected(tmp_path):
    store, signer, _, message, _ = _delivered(tmp_path, "LD-560003")
    token = signer.issue(
        message.run_id,
        ReviewDecision.APPROVE_EXPECTED_AMOUNT,
        amount="3334.50",
        issued_at=datetime(2026, 6, 15, 9, 0, tzinfo=timezone.utc),
        ttl_seconds=60,
    )
    later = datetime(2026, 6, 15, 9, 5, tzinfo=timezone.utc)

    with pytest.raises(DeliveryExpiredError):
        submit_signed_action(store, token, signer=signer, now=later)
    run = next(r for r in store.list_runs() if r.id == message.run_id)
    assert run.state == WorkflowState.NEEDS_REVIEW
    # Expiry has a valid signature, so it is audited under the real run id.
    rejected = [
        e for e in store.audit_events(message.run_id)
        if e["event_type"] == "delivery_action_rejected"
    ]
    assert rejected and rejected[-1]["payload"]["failure"] == "expired"
    store.close()


def test_duplicate_action_is_idempotent(tmp_path):
    store, signer, _, message, loads = _delivered(tmp_path, "LD-560003")
    token = _token_for(message, ReviewDecision.APPROVE_EXPECTED_AMOUNT)

    first = submit_signed_action(store, token, signer=signer, follow_up_loads=loads)
    second = submit_signed_action(store, token, signer=signer, follow_up_loads=loads)

    assert first.status == DeliveryActionStatus.APPLIED
    assert second.status == DeliveryActionStatus.DUPLICATE_IGNORED
    assert second.to_state == first.to_state
    applied = [e for e in store.audit_events(message.run_id) if e["event_type"] == "delivery_action_applied"]
    assert len(applied) == 1
    assert any(e["event_type"] == "delivery_action_duplicate" for e in store.audit_events(message.run_id))
    store.close()


def test_action_cannot_bypass_workflow_state(tmp_path):
    """A second distinct action after the run leaves NEEDS_REVIEW must be rejected."""
    store, signer, _, message, loads = _delivered(tmp_path, "LD-560003")
    approve_expected = _token_for(message, ReviewDecision.APPROVE_EXPECTED_AMOUNT)
    approve_full = _token_for(message, ReviewDecision.APPROVE_FULL_AMOUNT)

    submit_signed_action(store, approve_expected, signer=signer, follow_up_loads=loads)
    with pytest.raises(WorkflowError):
        submit_signed_action(store, approve_full, signer=signer, follow_up_loads=loads)
    assert any(
        e["event_type"] == "delivery_action_rejected" for e in store.audit_events(message.run_id)
    )
    store.close()


def test_action_mutates_message_state_text(tmp_path):
    store, signer, _, message, loads = _delivered(tmp_path, "LD-560008")
    backup = _token_for(message, ReviewDecision.REQUEST_BACKUP)

    assert message.status_banner == "Awaiting review"
    outcome = submit_signed_action(store, backup, signer=signer, follow_up_loads=loads)

    assert "Backup requested by Rasheed" in outcome.message.status_banner
    assert any("Backup requested by Rasheed" in entry for entry in outcome.message.history)
    rendered = render_delivery_message(outcome.message)
    assert "Backup requested by Rasheed" in rendered
    store.close()
