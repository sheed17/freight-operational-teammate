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
        assert "hrs of back-office saved (conservative estimate)" in text
    finally:
        store.close()


def test_ar_invoice_never_inflates_the_carrier_overbilling_recovered_bucket(tmp_path):
    # Hard AP/AR guard (owner trust-eroder #2): an AR customer invoice is its own bucket and must
    # NEVER be counted as money "recovered" from carrier overbilling (an AP concept).
    store = WorkflowStore(tmp_path / "w.sqlite3")
    try:
        _applied(store, lane="raise_invoice", status="DONE", amount="9999.00")  # big AR invoice
        daily = _daily(potential_overbilling_flagged="100.00", confirmed_recovered="40.00")
        digest = build_value_digest(store, daily=daily)
        # Recovered stays the AP number; the $9,999 AR invoice lives only in the invoiced bucket.
        assert digest.overbilling_recovered == "40.00"
        assert digest.invoiced_amount == "9999.00"
        assert "9999" not in digest.overbilling_recovered and "9999" not in digest.overbilling_flagged
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
    # Verified (read back) shows "(verified)"; a prose-only id shows "(reported by agent)".
    done = render_operation_receipt(OperationReceipt(lane="raise_invoice", status="DONE",
                                                     amount="2850.00", proof="INV-4912", verified=True))
    assert done.startswith("✅ Done — customer invoice · $2850.00 — INV-4912 (verified)")
    reported = render_operation_receipt(OperationReceipt(lane="raise_invoice", status="DONE",
                                                         amount="2850.00", proof="INV-4912", verified=False))
    assert "INV-4912 (reported by agent)" in reported and "(verified)" not in reported

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
    assert receipt.proof == "INV-7001" and receipt.amount == "3200.00" and receipt.verified is True
    assert "INV-7001 (verified)" in render_operation_receipt(receipt)


def test_prose_only_id_is_reported_not_verified():
    from freight_recon.operation_router import OperationResult
    from freight_recon.roi_ledger import receipt_from_result

    # The agent's chatty note names an id, but it never READ it back -> reported, NOT verified.
    result = OperationResult("DONE", "raise_invoice", "all set, saved invoice INV-9 I think", [])
    receipt = receipt_from_result(result, amount="100.00")
    assert receipt.proof == "INV-9" and receipt.verified is False
    assert "(reported by agent)" in render_operation_receipt(receipt)


def test_empty_digest_is_honest_not_fake(tmp_path):
    store = WorkflowStore(tmp_path / "w.sqlite3")
    try:
        digest = build_value_digest(store)
        text = render_value_digest(digest)
        assert "Nothing consequential yet" in text
        assert digest.invoices_raised == 0 and digest.hours_saved_estimate == "0.0"
    finally:
        store.close()


def test_proof_extraction_distinguishes_readback_from_prose():
    from freight_recon.roi_ledger import _extract_proof

    # A READ step's observed value -> verified True.
    assert _extract_proof("done", [{"action": "READ", "observed": "Invoice #4912"}]) == ("4912", True)
    # Prose only -> proof but verified False.
    assert _extract_proof("saved invoice INV-5 ok", []) == ("INV-5", False)
    # Nothing -> none.
    assert _extract_proof("all good, saved it", []) == (None, False)


# --- run trace: the receipt shows the PATH (read -> clicked -> filled -> committed -> verified) ------

def test_build_run_trace_renders_owner_legible_actions_and_folds_bookkeeping():
    from freight_recon.roi_ledger import build_run_trace

    steps = [
        {"action": "CLICK", "target": "101", "ok": True},
        {"action": "TYPE", "target": "Amount", "value": "2500.00", "ok": True},
        {"action": "SELECT", "target": "Customer", "value": "Echo Global", "ok": True},
        {"action": "CLICK", "target": "Create Invoice", "committed": True, "ok": True},
        {"action": "READ", "target": "invoice", "observed": "Invoice #560010, $2,500.00", "ok": True},
        {"committed": True, "commit_key": "abc"},   # bookkeeping-only -> folded away
        {"screenshot": "/tmp/x.png"},               # bookkeeping-only -> folded away
    ]
    trace = build_run_trace(steps)
    assert trace == [
        "Clicked 101",
        "Filled Amount = 2500.00",
        "Selected Customer = Echo Global",
        "Committed: Create Invoice",
        "Read invoice → Invoice #560010, $2,500.00",
    ]


def test_failed_click_is_marked_in_the_trace():
    from freight_recon.roi_ledger import build_run_trace
    assert build_run_trace([{"action": "CLICK", "target": "Save", "ok": False}]) == ["Clicked Save (failed)"]


def test_receipt_from_result_carries_and_renders_the_trace():
    from types import SimpleNamespace
    from freight_recon.roi_ledger import receipt_from_result

    steps = [
        {"action": "CLICK", "target": "Create Invoice", "committed": True, "ok": True},
        {"action": "READ", "target": "invoice", "observed": "#560010", "ok": True},
    ]
    receipt = receipt_from_result(
        SimpleNamespace(lane="raise_invoice", status="DONE", note="Invoice #560010 saved", steps=steps),
        amount="2500.00",
    )
    assert receipt.trace == ["Committed: Create Invoice", "Read invoice → #560010"]
    rendered = render_operation_receipt(receipt)
    assert rendered.splitlines()[0].startswith("✅ Done")
    assert "   • Committed: Create Invoice" in rendered
    assert "   • Read invoice → #560010" in rendered
    # show_trace=False keeps the one-line headline for compact surfaces
    assert "\n" not in render_operation_receipt(receipt, show_trace=False)


def test_refused_receipt_has_no_trace_since_nothing_ran():
    r = OperationReceipt(lane=None, status="REFUSED", summary="unknown request",
                         trace=["should-not-render"])
    assert render_operation_receipt(r) == "🚫 I won't improvise — unknown request"
