"""Tests for the click->mock-money hook: every swallow/hold/skip/fail branch is audited, never silent."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from generate_realistic_corpus import generate  # noqa: E402
from freight_recon.action_callback import handle_signed_action_callback  # noqa: E402
from freight_recon.delivery import DeliverySigner, build_delivery_message, record_delivery_message  # noqa: E402
from freight_recon.ops_control import OpsControl  # noqa: E402
import freight_recon.post_approval_execution as pae  # noqa: E402
from freight_recon.post_approval_execution import MockTmsAutoEntryConfig, maybe_execute_mock_tms_after_approval  # noqa: E402
from freight_recon.reconciliation import FreightLoadForReconciliation  # noqa: E402
from freight_recon.review import build_review_payload, record_review_payload  # noqa: E402
from freight_recon.review_actions import ReviewDecision  # noqa: E402
from freight_recon.workflow import WorkflowState, WorkflowStore, process_load_packet  # noqa: E402


def _approved_outcome(tmp_path):
    """Apply a real APPROVE_EXPECTED click and capture the resulting APPLIED/APPROVED outcome."""
    signer = DeliverySigner(b"callback-secret")
    corpus = tmp_path / "corpus"
    generate(corpus, 8, seed=42)
    raw = json.loads((corpus / "ground_truth" / "loads_and_scenarios.json").read_text())
    loads = [FreightLoadForReconciliation.from_mapping(item) for item in raw.values()]
    store = WorkflowStore(tmp_path / "workflow.sqlite3")
    seen: set[tuple[str, str]] = set()
    selected = None
    for load in loads:
        run = process_load_packet(store, load, primary_document_path=corpus / load.documents["carrier_invoice"], seen_invoice_keys=seen)
        payload = build_review_payload(run, load, age_hours=48)
        if payload is not None:
            record_review_payload(store, payload)
            if load.load_id == "LD-560003":
                selected = payload
    assert selected is not None
    message = build_delivery_message(selected, signer, actor="Rasheed")
    record_delivery_message(store, message)
    token = next(b.signed_token for b in message.actions if b.decision == ReviewDecision.APPROVE_EXPECTED_AMOUNT)

    captured: dict = {}
    handle_signed_action_callback(
        store, token, signer=signer, follow_up_loads={load.load_id: load for load in loads},
        post_action_executor=lambda _s, outcome: captured.setdefault("outcome", outcome),
    )
    return store, captured["outcome"]


def _has_event(store, run_id, event_type) -> bool:
    return any(e["event_type"] == event_type for e in store.audit_events(run_id))


def test_enabled_executes_to_done_and_audits(tmp_path):
    store, outcome = _approved_outcome(tmp_path)
    result = maybe_execute_mock_tms_after_approval(
        store, outcome, config=MockTmsAutoEntryConfig(enabled=True, ledger_path=str(tmp_path / "l.json"))
    )
    assert result is not None and result.final_state == WorkflowState.DONE
    assert _has_event(store, outcome.run_id, "post_approval_execution_completed")
    store.close()


def test_disabled_skips_and_audits(tmp_path):
    store, outcome = _approved_outcome(tmp_path)
    result = maybe_execute_mock_tms_after_approval(
        store, outcome, config=MockTmsAutoEntryConfig(enabled=False, ledger_path=str(tmp_path / "l.json"))
    )
    assert result is None
    assert _has_event(store, outcome.run_id, "post_approval_execution_skipped")
    store.close()


def test_pause_brake_holds_without_entering_and_audits(tmp_path):
    store, outcome = _approved_outcome(tmp_path)
    ops = OpsControl(tmp_path / "ops.json")
    ops.pause_tms_writes(actor="Rasheed", reason="something looks off")
    ledger_path = tmp_path / "l.json"
    result = maybe_execute_mock_tms_after_approval(
        store, outcome, config=MockTmsAutoEntryConfig(enabled=True, ledger_path=str(ledger_path)), ops_control=ops
    )
    assert result is None
    assert _has_event(store, outcome.run_id, "post_approval_execution_held")
    from freight_recon.tms_write import MockTmsWriteLedger

    assert MockTmsWriteLedger(ledger_path).get_payable("LD-560003") is None  # the brake stopped the write
    store.close()


def test_missing_approved_amount_fails_closed_and_audits(tmp_path, monkeypatch):
    store, outcome = _approved_outcome(tmp_path)
    monkeypatch.setattr(pae, "approved_amount_for_run", lambda *a, **k: None)
    result = maybe_execute_mock_tms_after_approval(
        store, outcome, config=MockTmsAutoEntryConfig(enabled=True, ledger_path=str(tmp_path / "l.json"))
    )
    assert result is None
    assert _has_event(store, outcome.run_id, "post_approval_execution_failed")
    store.close()


def test_inner_execution_error_is_audited_and_swallowed(tmp_path, monkeypatch):
    store, outcome = _approved_outcome(tmp_path)

    def _boom(*_a, **_k):
        raise RuntimeError("tms exploded mid-write")

    monkeypatch.setattr(pae, "enter_approved_payable", _boom)
    result = maybe_execute_mock_tms_after_approval(
        store, outcome, config=MockTmsAutoEntryConfig(enabled=True, ledger_path=str(tmp_path / "l.json"))
    )
    assert result is None  # swallowed, so the Slack callback still acks cleanly
    assert _has_event(store, outcome.run_id, "post_approval_execution_failed")
    store.close()
