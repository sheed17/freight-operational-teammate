"""Tests for the activity timeline: curated, newest-first, owner-readable 'show your work'."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.activity_log import build_activity, render_activity  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402


def test_timeline_is_curated_newest_first_and_proof_bearing(tmp_path):
    store = WorkflowStore(tmp_path / "w.sqlite3")
    try:
        store.add_security_event("slack_operation_applied", actor="R",
                                 payload={"lane": "raise_invoice", "status": "DONE",
                                          "approved_amount": "2850.00", "invoice_number": "INV-4912"})
        store.add_security_event("slack_operation_rejected", actor="X",
                                 payload={"failure": "authorization"})
        # An internal/noise event that must NOT appear in the owner timeline.
        store.add_security_event("review_payloads", actor="system", payload={"count": 3})

        events = build_activity(store)
        summaries = [e.summary for e in events]
        assert any("Ran raise_invoice — DONE · $2850.00" in s for s in summaries)
        assert any("Rejected an approval (authorization)" in s for s in summaries)
        assert not any("review_payloads" in s for s in summaries)  # noise filtered out

        text = render_activity(events)
        assert "What Neyma did" in text and "INV-4912" in text
    finally:
        store.close()


def test_empty_timeline_is_honest(tmp_path):
    store = WorkflowStore(tmp_path / "w.sqlite3")
    try:
        assert "No activity" in render_activity(build_activity(store))
    finally:
        store.close()


def test_audit_command_renders_timeline(tmp_path):
    from freight_recon.ops_control import OpsControl, handle_ops_command

    oc = OpsControl(tmp_path / "ops.json")
    store = WorkflowStore(tmp_path / "w.sqlite3")
    try:
        store.add_security_event("slack_operation_applied", actor="R",
                                 payload={"lane": "record_payable", "status": "DONE"})
        out = handle_ops_command("audit", actor="R", ops_control=oc, store=store)
        assert "What Neyma did" in out and "record_payable" in out
    finally:
        store.close()
