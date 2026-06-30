"""Tests for ROI instrumentation: receipts + value digest from the same audit log the spine writes."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.roi_ledger import (  # noqa: E402
    MinutesPerTask,
    OperationReceipt,
    build_operation_receipts,
    build_value_digest,
    render_operation_receipt,
    render_value_digest,
)
from freight_recon.summary import DailySummary  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402


def _applied(store, *, lane, status, amount=None, note="", summary="", steps=None):
    store.add_security_event(
        "slack_operation_applied",
        actor="U_OWNER",
        payload={
            "lane": lane, "status": status, "approved_amount": amount,
            "note": note, "summary": summary, "steps": steps or [],
            "channel_id": "C_OPS", "thread_ts": "1.1",
        },
    )


def _daily(**kw):
    base = dict(
        processed=0, auto_cleared=0, needs_review=0, duplicates=0, missing_backup=0,
        potential_overbilling_flagged="0.00", confirmed_recovered="0.00",
    )
    base.update(kw)
    return DailySummary(**base)


def test_receipts_are_read_from_the_audit_log(tmp_path):
    store = WorkflowStore(tmp_path / "w.sqlite3")
    try:
        _applied(store, lane="raise_invoice", status="DONE", amount="2850.00",
                 note="invoice INV-4912 verified")
        _applied(store, lane="record_payable", status="ESCALATED", summary="customer not found")
        receipts = build_operation_receipts(store)
        assert [r.status for r in receipts] == ["DONE", "ESCALATED"]
        assert receipts[0].proof == "INV-4912" and receipts[0].amount == "2850.00"
    finally:
        store.close()


def test_value_digest_tallies_invoiced_and_payables_only_on_done(tmp_path):
    store = WorkflowStore(tmp_path / "w.sqlite3")
    try:
        _applied(store, lane="raise_invoice", status="DONE", amount="2850.00")
        _applied(store, lane="raise_invoice", status="DONE", amount="1150.00")
        _applied(store, lane="raise_invoice", status="FAILED", amount="9999.00")  # must NOT count
        _applied(store, lane="record_payable", status="DONE", amount="1200.00")
        _applied(store, lane="record_payable", status="ESCALATED")
        digest = build_value_digest(store)
        assert digest.invoices_raised == 2 and digest.invoiced_amount == "4000.00"
        assert digest.payables_recorded == 1 and digest.payables_amount == "1200.00"
        assert digest.operations_done == 3  # two invoices + one payable
        assert digest.operations_escalated == 1 and digest.operations_failed == 1
        # The FAILED $9,999 never entered any money total.
        assert "9999" not in digest.invoiced_amount
    finally:
        store.close()


def test_value_digest_folds_in_ap_reconciliation_numbers(tmp_path):
    store = WorkflowStore(tmp_path / "w.sqlite3")
    try:
        _applied(store, lane="raise_invoice", status="DONE", amount="2850.00")
        daily = _daily(auto_cleared=10, needs_review=3,
                       potential_overbilling_flagged="1310.00", confirmed_recovered="940.00")
        digest = build_value_digest(store, daily=daily)
        assert digest.overbilling_flagged == "1310.00" and digest.overbilling_recovered == "940.00"
        text = render_value_digest(digest)
        assert "Caught $1310.00" in text and "recovered $940.00" in text
        assert "Raised 1 customer invoice" in text and "$2850.00" in text
        assert "hrs of back-office saved (estimated)" in text
    finally:
        store.close()


def test_hours_saved_is_a_tunable_estimate(tmp_path):
    store = WorkflowStore(tmp_path / "w.sqlite3")
    try:
        _applied(store, lane="raise_invoice", status="DONE", amount="100.00")
        daily = _daily(auto_cleared=0, needs_review=0)
        # 1 invoice * 30 min = 30 min = 0.5 hr
        digest = build_value_digest(store, daily=daily, minutes=MinutesPerTask(invoice_raised=30))
        assert digest.hours_saved_estimate == "0.5"
    finally:
        store.close()


def test_render_receipt_shapes_per_status():
    done = render_operation_receipt(OperationReceipt(lane="raise_invoice", status="DONE",
                                                     amount="2850.00", proof="INV-4912"))
    assert done.startswith("✅ Done — customer invoice · $2850.00 — INV-4912 (verified)")

    esc = render_operation_receipt(OperationReceipt(lane="raise_invoice", status="ESCALATED",
                                                    summary="customer field missing"))
    assert esc.startswith("✋ I need you") and "customer field missing" in esc

    refused = render_operation_receipt(OperationReceipt(lane=None, status="REFUSED",
                                                        summary="no known lane"))
    assert refused.startswith("🚫 I won't improvise")

    failed = render_operation_receipt(OperationReceipt(lane="record_payable", status="FAILED",
                                                       amount="1200.00"))
    assert failed.startswith("⚠️ Couldn't finish — carrier payable · $1200.00")


def test_receipt_from_result_is_proof_carrying():
    from freight_recon.operation_router import OperationResult
    from freight_recon.roi_ledger import receipt_from_result

    result = OperationResult("DONE", "raise_invoice", "invoice INV-7001 verified",
                             [{"action": "READ", "observed": "INV-7001"}])
    receipt = receipt_from_result(result, amount="3200.00")
    assert receipt.proof == "INV-7001" and receipt.amount == "3200.00"
    assert render_operation_receipt(receipt).startswith("✅ Done — customer invoice · $3200.00 — INV-7001")


def test_empty_digest_is_honest_not_fake(tmp_path):
    store = WorkflowStore(tmp_path / "w.sqlite3")
    try:
        digest = build_value_digest(store)
        text = render_value_digest(digest)
        assert "Nothing consequential yet" in text
        assert digest.invoices_raised == 0 and digest.hours_saved_estimate == "0.0"
    finally:
        store.close()


def test_proof_extraction_falls_back_to_steps_then_none():
    # No id in the note, but a READ step confirms the invoice number.
    with_step = OperationReceipt(lane="raise_invoice", status="DONE")
    from freight_recon.roi_ledger import _extract_proof

    assert _extract_proof("done", [{"action": "READ", "observed": "Invoice #4912"}]) == "4912"
    assert _extract_proof("all good, saved it", []) is None
