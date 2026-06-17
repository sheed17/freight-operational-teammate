"""Tests for workflow-state controlled tool permissions."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.tool_permissions import (  # noqa: E402
    ToolContext,
    evaluate_tool_permission,
    record_tool_permission_decision,
)
from freight_recon.workflow import WorkflowState, WorkflowStore  # noqa: E402


def test_read_tms_load_allowed_during_review_without_approval():
    decision = evaluate_tool_permission(
        "read_tms_load",
        ToolContext(workflow_state=WorkflowState.NEEDS_REVIEW),
    )

    assert decision.allowed is True
    assert decision.reason == "allowed"


def test_send_follow_up_requires_outbound_enabled_and_explicit_approval():
    no_outbound = evaluate_tool_permission(
        "send_carrier_follow_up",
        ToolContext(workflow_state=WorkflowState.DISPUTED, approval_granted=True),
    )
    no_approval = evaluate_tool_permission(
        "send_carrier_follow_up",
        ToolContext(workflow_state=WorkflowState.DISPUTED, outbound_enabled=True),
    )
    allowed = evaluate_tool_permission(
        "send_carrier_follow_up",
        ToolContext(
            workflow_state=WorkflowState.DISPUTED,
            approval_granted=True,
            outbound_enabled=True,
        ),
    )

    assert no_outbound.allowed is False
    assert no_outbound.reason == "outbound messages are disabled"
    assert no_approval.allowed is False
    assert no_approval.reason == "explicit human approval is required"
    assert allowed.allowed is True


def test_tms_submit_blocked_without_write_enablement_and_right_state():
    wrong_state = evaluate_tool_permission(
        "submit_tms_payable",
        ToolContext(
            workflow_state=WorkflowState.NEEDS_REVIEW,
            approval_granted=True,
            tms_write_enabled=True,
        ),
    )
    write_disabled = evaluate_tool_permission(
        "submit_tms_payable",
        ToolContext(workflow_state=WorkflowState.ENTERING, approval_granted=True),
    )
    allowed = evaluate_tool_permission(
        "submit_tms_payable",
        ToolContext(
            workflow_state=WorkflowState.ENTERING,
            approval_granted=True,
            tms_write_enabled=True,
        ),
    )

    assert wrong_state.allowed is False
    assert "NEEDS_REVIEW" in wrong_state.reason
    assert write_disabled.allowed is False
    assert write_disabled.reason == "TMS write tools are disabled"
    assert allowed.allowed is True


def test_unknown_tool_is_blocked():
    decision = evaluate_tool_permission(
        "delete_everything",
        ToolContext(workflow_state=WorkflowState.NEEDS_REVIEW),
    )

    assert decision.allowed is False
    assert decision.reason == "unknown tool"


def test_tool_permission_decisions_are_audited(tmp_path):
    store = WorkflowStore(tmp_path / "workflow.sqlite3")
    try:
        run = store.receive_document("LD-560003", "hash-1", payload={"source": "test"})
        context = ToolContext(workflow_state=run.state, actor="test")
        decision = evaluate_tool_permission("read_tms_load", context)

        record_tool_permission_decision(store, run.id, decision=decision, context=context)

        events = store.audit_events(run.id)
        assert any(event["event_type"] == "tool_permission_blocked" for event in events)
        assert events[-1]["payload"]["tool_name"] == "read_tms_load"
    finally:
        store.close()
