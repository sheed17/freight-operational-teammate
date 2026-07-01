"""Tests for in-thread reactivity: an owner's thread reply resumes an escalated operation, gated."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.slack_delegate import CommandIntent, CommandKind  # noqa: E402
from freight_recon.thread_reply import (  # noqa: E402
    find_resumable_operation,
    handle_thread_reply,
    intent_from_resumable,
)
from freight_recon.workflow import WorkflowStore  # noqa: E402


def _escalate(store, *, thread_ts, summary="Record the payable to TQL for LD-1",
              params=None, amount="2700.00", status="ESCALATED"):
    store.add_security_event("slack_operation_applied", actor="U_OWNER", payload={
        "thread_ts": thread_ts, "status": status, "summary": summary,
        "params": params or {"lane": "record_payable", "carrier": "TQL", "load_ref": "LD-1"},
        "approved_amount": amount,
    })


def test_find_resumable_finds_latest_escalation_in_thread(tmp_path):
    store = WorkflowStore(tmp_path / "w.sqlite3")
    try:
        _escalate(store, thread_ts="T1", amount="2700.00")
        _escalate(store, thread_ts="T2", amount="999.00", status="DONE")  # not escalated
        assert find_resumable_operation(store, "T1")["approved_amount"] == "2700.00"
        assert find_resumable_operation(store, "T2") is None  # DONE, nothing to resume
        assert find_resumable_operation(store, "nope") is None
        assert find_resumable_operation(store, None) is None
    finally:
        store.close()


def test_intent_from_resumable_adds_guidance_keeps_amount():
    intent = intent_from_resumable(
        {"summary": "Record payable", "params": {"lane": "record_payable", "carrier": "TQL"},
         "approved_amount": "2700.00"},
        "I'm logged in now, proceed",
    )
    assert intent.kind == CommandKind.OPERATE
    assert intent.params["operator_guidance"] == "I'm logged in now, proceed"
    assert intent.params["approved_amount"] == "2700.00"  # amount carried, never from the reply
    assert intent.params["lane"] == "record_payable"


def test_handle_thread_reply_resumes_when_authorized(tmp_path):
    store = WorkflowStore(tmp_path / "w.sqlite3")
    try:
        _escalate(store, thread_ts="T1")
        seen = {}

        def run_operation(intent):
            seen["intent"] = intent
            return "RAN"

        out = handle_thread_reply(store, thread_ts="T1", reply_text="it's Acme Corp",
                                  authorized=True, run_operation=run_operation)
        assert out == "RAN"
        assert seen["intent"].params["operator_guidance"] == "it's Acme Corp"
    finally:
        store.close()


def test_handle_thread_reply_ignores_unauthorized_or_empty_or_untied(tmp_path):
    store = WorkflowStore(tmp_path / "w.sqlite3")
    try:
        _escalate(store, thread_ts="T1")
        ran = []
        run = lambda intent: ran.append(1)
        # unauthorized -> ignored
        assert handle_thread_reply(store, thread_ts="T1", reply_text="hi", authorized=False, run_operation=run) is None
        # empty reply -> ignored
        assert handle_thread_reply(store, thread_ts="T1", reply_text="   ", authorized=True, run_operation=run) is None
        # reply in a thread with no escalation -> ignored
        assert handle_thread_reply(store, thread_ts="OTHER", reply_text="hi", authorized=True, run_operation=run) is None
        assert ran == []  # never executed in any of these cases
    finally:
        store.close()


def test_lane_goal_includes_operator_guidance():
    from freight_recon.operation_router import freight_lanes

    lanes = {l.name: l for l in freight_lanes()}
    intent = CommandIntent(CommandKind.OPERATE, "Record payable",
                           {"lane": "record_payable", "carrier": "TQL", "operator_guidance": "I'm logged in, proceed"})
    goal = lanes["record_payable"].build_goal(intent)
    assert "I'm logged in, proceed" in goal and "guidance" in goal.lower()
