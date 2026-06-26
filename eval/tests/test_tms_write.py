"""Tests for the gated TMS write path (Stage 7) against the mock TMS ledger."""

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from generate_realistic_corpus import generate  # noqa: E402
from freight_recon.reconciliation import FreightLoadForReconciliation  # noqa: E402
from freight_recon.review import build_review_payload, record_review_payload  # noqa: E402
from freight_recon.review_actions import ReviewActionRequest, ReviewDecision, apply_review_action  # noqa: E402
from freight_recon.tms_write import (  # noqa: E402
    ChargeLine,
    MockTmsWriteLedger,
    PayableWriteStatus,
    TmsWriteAdapter,
    TmsWriteError,
    enter_approved_payable,
)
from freight_recon.workflow import WorkflowError, WorkflowState, WorkflowStore, process_load_packet  # noqa: E402

_AMOUNT = "3634.50"  # LD-560003 full invoice amount


def _approved_run(tmp_path):
    corpus = tmp_path / "corpus"
    generate(corpus, 8, seed=42)
    raw = json.loads((corpus / "ground_truth" / "loads_and_scenarios.json").read_text())
    loads = [FreightLoadForReconciliation.from_mapping(item) for item in raw.values()]
    store = WorkflowStore(tmp_path / "wf.sqlite3")
    seen: set[tuple[str, str]] = set()
    for load in loads:
        process_load_packet(store, load, primary_document_path=corpus / load.documents["carrier_invoice"], seen_invoice_keys=seen)
    run = next(r for r in store.list_runs() if r.load_id == "LD-560003")
    load = next(load for load in loads if load.load_id == "LD-560003")
    payload = build_review_payload(run, load, age_hours=0)
    record_review_payload(store, payload)
    apply_review_action(store, ReviewActionRequest(run_id=run.id, decision=ReviewDecision.APPROVE_FULL_AMOUNT, amount=_AMOUNT))
    return store, run.id


def _ledger(tmp_path, fail_modes=frozenset()):
    return MockTmsWriteLedger(tmp_path / "ledger.json", fail_modes=fail_modes)


def test_tms_writes_pause_holds_approved_run(tmp_path):
    from freight_recon.ops_control import OpsControl, TmsWritesPausedError

    store, run_id = _approved_run(tmp_path)
    ops = OpsControl(tmp_path / "ops.json")
    ops.pause_tms_writes(actor="Rasheed", reason="something looks off")
    with pytest.raises(TmsWritesPausedError):
        enter_approved_payable(store, _ledger(tmp_path), run_id, amount=_AMOUNT, ops_control=ops)
    assert store.get_run(run_id).state == WorkflowState.APPROVED  # held in place, not failed
    assert _ledger(tmp_path).get_payable("LD-560003") is None  # nothing entered
    # resuming lets the same run proceed to DONE
    ops.resume_tms_writes(actor="Rasheed")
    outcome = enter_approved_payable(store, _ledger(tmp_path), run_id, amount=_AMOUNT, ops_control=ops)
    assert outcome.final_state == WorkflowState.DONE
    store.close()


def test_execution_status_updates_emitted_in_order_to_done(tmp_path):
    # The gated write emits channel-neutral status so a transport (Slack thread) can narrate it.
    store, run_id = _approved_run(tmp_path)
    updates: list = []
    enter_approved_payable(store, _ledger(tmp_path), run_id, amount=_AMOUNT, on_status=updates.append)
    assert [u.phase.value for u in updates] == ["ENTERING", "ENTERED", "VERIFIED", "DONE"]
    assert next(u for u in updates if u.phase.value == "ENTERED").external_ref  # carries the PV ref
    assert updates[-1].amount == _AMOUNT and updates[-1].load_id == "LD-560003"


def test_execution_status_emits_failed_on_readback_mismatch(tmp_path):
    store, run_id = _approved_run(tmp_path)
    updates: list = []
    enter_approved_payable(
        store, _ledger(tmp_path, fail_modes=frozenset({"readback_mismatch"})), run_id, amount=_AMOUNT, on_status=updates.append
    )
    # A mismatch must surface as a FAILED status, never VERIFIED/DONE.
    phases = [u.phase.value for u in updates]
    assert phases[-1] == "FAILED"
    assert "VERIFIED" not in phases and "DONE" not in phases


def test_status_sink_failure_never_breaks_the_money_path(tmp_path):
    store, run_id = _approved_run(tmp_path)

    def _boom(_update):
        raise RuntimeError("slack down")

    # A failing status sink must not break or alter the gated write.
    outcome = enter_approved_payable(store, _ledger(tmp_path), run_id, amount=_AMOUNT, on_status=_boom)
    assert outcome.final_state == WorkflowState.DONE and outcome.verified is True
    store.close()


def test_entry_refused_when_no_human_approval_recorded(tmp_path):
    # APPROVED via a direct transition with no review_approved_* event → binding fails closed.
    corpus = tmp_path / "corpus"
    generate(corpus, 8, seed=42)
    raw = json.loads((corpus / "ground_truth" / "loads_and_scenarios.json").read_text())
    loads = [FreightLoadForReconciliation.from_mapping(item) for item in raw.values()]
    store = WorkflowStore(tmp_path / "wf.sqlite3")
    seen: set[tuple[str, str]] = set()
    for load in loads:
        process_load_packet(store, load, primary_document_path=corpus / load.documents["carrier_invoice"], seen_invoice_keys=seen)
    run = next(r for r in store.list_runs() if r.load_id == "LD-560003")
    store.transition(run.id, WorkflowState.APPROVED, actor="system", event_type="forced_approve_no_amount")
    with pytest.raises(WorkflowError, match="no human-approved amount recorded"):
        enter_approved_payable(store, _ledger(tmp_path), run.id, amount=_AMOUNT)
    assert _ledger(tmp_path).get_payable("LD-560003") is None
    store.close()


def test_entry_amount_must_match_human_approved_amount(tmp_path):
    # The run was approved at _AMOUNT; trying to enter anything else is refused before any write.
    store, run_id = _approved_run(tmp_path)
    ledger = _ledger(tmp_path)
    with pytest.raises(WorkflowError, match="does not match the human-approved amount"):
        enter_approved_payable(store, ledger, run_id, amount="9999.00")
    assert ledger.get_payable("LD-560003") is None  # nothing entered
    assert store.get_run(run_id).state == WorkflowState.APPROVED  # state untouched
    store.close()


def test_happy_path_enters_and_verifies_to_done(tmp_path):
    store, run_id = _approved_run(tmp_path)
    ledger = _ledger(tmp_path)

    outcome = enter_approved_payable(store, ledger, run_id, amount=_AMOUNT, charges=[ChargeLine(name="total", amount=_AMOUNT)])

    assert outcome.final_state == WorkflowState.DONE
    assert outcome.write_status == PayableWriteStatus.WRITTEN
    assert outcome.verified is True
    assert outcome.external_ref
    assert ledger.get_payable("LD-560003")["amount"] == _AMOUNT
    events = {e["event_type"] for e in store.audit_events(run_id)}
    assert {"tms_write_prepared", "tms_write_submitted", "tms_write_verified"} <= events
    store.close()


def test_confirm_before_submit_is_required(tmp_path):
    store, run_id = _approved_run(tmp_path)
    ledger = _ledger(tmp_path)
    store.transition(run_id, WorkflowState.READY_FOR_ENTRY, actor="Rasheed", event_type="route_to_entry")
    run = store.get_run(run_id)
    adapter = TmsWriteAdapter(store, ledger)
    from freight_recon.tool_permissions import ToolContext

    prepared = adapter.prepare(
        run,
        amount=_AMOUNT,
        charges=[],
        context=ToolContext(workflow_state=WorkflowState.READY_FOR_ENTRY, approval_granted=True, tms_write_enabled=True),
    )
    store.transition(run_id, WorkflowState.ENTERING, actor="Rasheed", event_type="begin_entry")
    with pytest.raises(TmsWriteError):
        adapter.submit(
            prepared,
            context=ToolContext(workflow_state=WorkflowState.ENTERING, approval_granted=True, tms_write_enabled=True),
            confirmed=False,
        )
    assert ledger.get_payable("LD-560003") is None  # nothing written
    store.close()


def test_write_disabled_blocks_prepare(tmp_path):
    store, run_id = _approved_run(tmp_path)
    ledger = _ledger(tmp_path)
    with pytest.raises(TmsWriteError):
        enter_approved_payable(store, ledger, run_id, amount=_AMOUNT, tms_write_enabled=False)
    assert ledger.get_payable("LD-560003") is None
    store.close()


def test_requires_approved_state(tmp_path):
    store, run_id = _approved_run(tmp_path)
    ledger = _ledger(tmp_path)
    # Drive it to DONE first, then a second entry attempt must reject on state.
    enter_approved_payable(store, ledger, run_id, amount=_AMOUNT)
    with pytest.raises(WorkflowError):
        enter_approved_payable(store, ledger, run_id, amount=_AMOUNT)
    store.close()


def test_idempotent_resubmit_does_not_double_enter(tmp_path):
    store, run_id = _approved_run(tmp_path)
    ledger = _ledger(tmp_path)
    from freight_recon.tms_write import idempotency_key

    key = idempotency_key(run_id, "LD-560003", _AMOUNT)
    first = ledger.write_payable(run_id=run_id, load_id="LD-560003", carrier="X", amount=_AMOUNT, charges=[], key=key)
    second = ledger.write_payable(run_id=run_id, load_id="LD-560003", carrier="X", amount=_AMOUNT, charges=[], key=key)
    assert first.status == PayableWriteStatus.WRITTEN
    assert second.status == PayableWriteStatus.IDEMPOTENT_REPLAY
    assert second.external_ref == first.external_ref
    store.close()


def test_duplicate_payable_is_blocked_and_routes_to_failed(tmp_path):
    store, run_id = _approved_run(tmp_path)
    ledger = _ledger(tmp_path, fail_modes=frozenset({"duplicate"}))
    outcome = enter_approved_payable(store, ledger, run_id, amount=_AMOUNT)
    assert outcome.write_status == PayableWriteStatus.DUPLICATE_BLOCKED
    assert outcome.final_state == WorkflowState.FAILED
    assert outcome.verified is False
    store.close()


def test_session_expired_routes_to_waiting_for_session(tmp_path):
    store, run_id = _approved_run(tmp_path)
    ledger = _ledger(tmp_path, fail_modes=frozenset({"session_expired"}))
    outcome = enter_approved_payable(store, ledger, run_id, amount=_AMOUNT)
    assert outcome.write_status == PayableWriteStatus.SESSION_EXPIRED
    assert outcome.final_state == WorkflowState.WAITING_FOR_SESSION
    assert ledger.get_payable("LD-560003") is None
    store.close()


def test_readback_mismatch_blocks_done(tmp_path):
    store, run_id = _approved_run(tmp_path)
    ledger = _ledger(tmp_path, fail_modes=frozenset({"readback_mismatch"}))
    outcome = enter_approved_payable(store, ledger, run_id, amount=_AMOUNT)
    # The amount was written, but readback does not match what we intended → never DONE.
    assert outcome.write_status == PayableWriteStatus.WRITTEN
    assert outcome.verified is False
    assert outcome.final_state == WorkflowState.FAILED
    store.close()
