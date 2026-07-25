"""Tests for follow-up drafts behind send gates."""

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from generate_realistic_corpus import generate  # noqa: E402
from freight_recon.follow_up import FollowUpType, SendGateStatus, build_follow_up_draft, record_follow_up_draft  # noqa: E402
from freight_recon.reconciliation import FreightLoadForReconciliation  # noqa: E402
from freight_recon.review import build_review_payload  # noqa: E402
from freight_recon.review_actions import ReviewDecision  # noqa: E402
from freight_recon.workflow import WorkflowStore, process_load_packet  # noqa: E402


def _payload_fixture(tmp_path, load_id):
    corpus = tmp_path / "corpus"
    generate(corpus, 8, seed=42)
    raw = json.loads((corpus / "ground_truth" / "loads_and_scenarios.json").read_text())
    loads = [FreightLoadForReconciliation.from_mapping(item) for item in raw.values()]
    store = WorkflowStore(tmp_path / "workflow.sqlite3", tenant="tenant-fixture-a")
    seen: set[tuple[str, str]] = set()
    selected = None
    payload = None
    for load in loads:
        run = process_load_packet(
            store,
            load,
            primary_document_path=corpus / load.documents["carrier_invoice"],
            seen_invoice_keys=seen,
        )
        if load.load_id == load_id:
            selected = load
            payload = build_review_payload(run, load)
    assert selected is not None
    assert payload is not None
    return store, selected, payload


def test_expected_amount_approval_creates_dispute_draft(tmp_path):
    store, load, payload = _payload_fixture(tmp_path, "LD-560003")

    draft = build_follow_up_draft(payload, load, ReviewDecision.APPROVE_EXPECTED_AMOUNT)

    assert draft.draft_type == FollowUpType.DISPUTE
    assert draft.send_gate_status == SendGateStatus.PENDING_APPROVAL
    assert draft.tone == "short and direct"
    assert "Our records show $3334.50" in draft.body
    assert "invoice totals $3634.50" in draft.body
    assert any("rate_confirmation" in url for url in draft.evidence_urls)
    assert any("carrier_invoice" in url for url in draft.evidence_urls)
    store.close()


def test_request_backup_creates_backup_draft_and_audit_is_idempotent(tmp_path):
    store, load, payload = _payload_fixture(tmp_path, "LD-560008")

    draft = build_follow_up_draft(payload, load, ReviewDecision.REQUEST_BACKUP)
    record_follow_up_draft(store, draft)
    record_follow_up_draft(store, draft)

    assert draft.draft_type == FollowUpType.REQUEST_BACKUP
    assert "Please send the missing backup" in draft.body
    events = [
        event
        for event in store.audit_events(payload.run_id)
        if event["event_type"] == "follow_up_draft_created"
    ]
    assert len(events) == 1
    store.close()


def test_non_follow_up_action_is_rejected(tmp_path):
    _, load, payload = _payload_fixture(tmp_path, "LD-560003")

    with pytest.raises(ValueError):
        build_follow_up_draft(payload, load, ReviewDecision.APPROVE_FULL_AMOUNT)
