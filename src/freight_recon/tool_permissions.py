"""Workflow-state controlled tool permission registry."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from .workflow import WorkflowState, WorkflowStore


class ToolRisk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ApprovalRequirement(str, Enum):
    NONE = "NONE"
    BEFORE_SEND = "BEFORE_SEND"
    EXPLICIT_HUMAN = "EXPLICIT_HUMAN"


class ToolPermission(BaseModel):
    name: str
    owning_adapter: str
    allowed_states: set[WorkflowState]
    risk: ToolRisk
    approval_required: ApprovalRequirement = ApprovalRequirement.NONE
    timeout_seconds: int = 30
    max_retries: int = 0
    audit_event: str
    requires_outbound_enabled: bool = False
    requires_tms_write_enabled: bool = False
    description: str


class ToolContext(BaseModel):
    workflow_state: WorkflowState
    actor: str = "system"
    approval_granted: bool = False
    outbound_enabled: bool = False
    tms_write_enabled: bool = False


class ToolPermissionDecision(BaseModel):
    tool_name: str
    allowed: bool
    reason: str
    risk: ToolRisk | None = None
    approval_required: ApprovalRequirement | None = None
    audit_event: str = "tool_permission_blocked"


TOOL_REGISTRY: dict[str, ToolPermission] = {
    "fetch_client_sop": ToolPermission(
        name="fetch_client_sop",
        owning_adapter="retrieval",
        allowed_states=set(WorkflowState),
        risk=ToolRisk.LOW,
        audit_event="tool_fetch_client_sop",
        description="Read client SOP/configuration context.",
    ),
    "search_prior_corrections": ToolPermission(
        name="search_prior_corrections",
        owning_adapter="retrieval",
        allowed_states={WorkflowState.NEEDS_REVIEW, WorkflowState.APPROVED, WorkflowState.DISPUTED},
        risk=ToolRisk.LOW,
        audit_event="tool_search_prior_corrections",
        description="Search prior human corrections for the same carrier or field.",
    ),
    "summarize_email_thread": ToolPermission(
        name="summarize_email_thread",
        owning_adapter="email",
        allowed_states={WorkflowState.RECEIVED, WorkflowState.EXTRACTED, WorkflowState.NEEDS_REVIEW},
        risk=ToolRisk.LOW,
        audit_event="tool_summarize_email_thread",
        description="Summarize an inbound email/PDF thread.",
    ),
    "draft_carrier_follow_up": ToolPermission(
        name="draft_carrier_follow_up",
        owning_adapter="email",
        allowed_states={WorkflowState.NEEDS_REVIEW, WorkflowState.APPROVED, WorkflowState.DISPUTED, WorkflowState.REQUESTED_BACKUP},
        risk=ToolRisk.MEDIUM,
        approval_required=ApprovalRequirement.BEFORE_SEND,
        audit_event="tool_draft_carrier_follow_up",
        description="Draft a carrier dispute, duplicate check, or missing-backup email.",
    ),
    "send_carrier_follow_up": ToolPermission(
        name="send_carrier_follow_up",
        owning_adapter="email",
        allowed_states={WorkflowState.DISPUTED, WorkflowState.REQUESTED_BACKUP},
        risk=ToolRisk.HIGH,
        approval_required=ApprovalRequirement.EXPLICIT_HUMAN,
        requires_outbound_enabled=True,
        audit_event="tool_send_carrier_follow_up",
        description="Send an approved carrier follow-up email.",
    ),
    "post_slack_review": ToolPermission(
        name="post_slack_review",
        owning_adapter="slack",
        allowed_states={WorkflowState.NEEDS_REVIEW},
        risk=ToolRisk.MEDIUM,
        requires_outbound_enabled=True,
        audit_event="tool_post_slack_review",
        description="Post a human review message to a configured Slack channel.",
    ),
    "send_review_email": ToolPermission(
        name="send_review_email",
        owning_adapter="email",
        allowed_states={WorkflowState.NEEDS_REVIEW},
        risk=ToolRisk.MEDIUM,
        requires_outbound_enabled=True,
        audit_event="tool_send_review_email",
        description="Send a human review email to configured recipients.",
    ),
    "read_tms_load": ToolPermission(
        name="read_tms_load",
        owning_adapter="tms_read",
        allowed_states={
            WorkflowState.NEEDS_REVIEW,
            WorkflowState.APPROVED,
            WorkflowState.READY_FOR_ENTRY,
            WorkflowState.ENTERING,
            WorkflowState.WAITING_FOR_SESSION,
        },
        risk=ToolRisk.LOW,
        audit_event="tool_read_tms_load",
        description="Read load/rate fields from the TMS.",
    ),
    "read_tms_payable": ToolPermission(
        name="read_tms_payable",
        owning_adapter="tms_read",
        allowed_states={
            WorkflowState.NEEDS_REVIEW,
            WorkflowState.APPROVED,
            WorkflowState.READY_FOR_ENTRY,
            WorkflowState.ENTERING,
            WorkflowState.WAITING_FOR_SESSION,
        },
        risk=ToolRisk.LOW,
        audit_event="tool_read_tms_payable",
        description="Read carrier payable fields from the TMS.",
    ),
    "prepare_tms_payable_entry": ToolPermission(
        name="prepare_tms_payable_entry",
        owning_adapter="tms_write",
        allowed_states={WorkflowState.READY_FOR_ENTRY},
        risk=ToolRisk.HIGH,
        approval_required=ApprovalRequirement.EXPLICIT_HUMAN,
        requires_tms_write_enabled=True,
        audit_event="tool_prepare_tms_payable_entry",
        description="Prepare an approved payable entry in confirm-before-submit mode.",
    ),
    "upload_tms_document": ToolPermission(
        name="upload_tms_document",
        owning_adapter="tms_write",
        allowed_states={WorkflowState.READY_FOR_ENTRY, WorkflowState.ENTERING},
        risk=ToolRisk.HIGH,
        approval_required=ApprovalRequirement.EXPLICIT_HUMAN,
        requires_tms_write_enabled=True,
        audit_event="tool_upload_tms_document",
        description="Upload an approved document into TMS.",
    ),
    "submit_tms_payable": ToolPermission(
        name="submit_tms_payable",
        owning_adapter="tms_write",
        allowed_states={WorkflowState.ENTERING},
        risk=ToolRisk.CRITICAL,
        approval_required=ApprovalRequirement.EXPLICIT_HUMAN,
        timeout_seconds=15,
        requires_tms_write_enabled=True,
        audit_event="tool_submit_tms_payable",
        description="Submit a payable entry after confirm-before-submit approval.",
    ),
    "verify_tms_payable": ToolPermission(
        name="verify_tms_payable",
        owning_adapter="tms_read",
        allowed_states={WorkflowState.ENTERING, WorkflowState.ENTERED},
        risk=ToolRisk.LOW,
        audit_event="tool_verify_tms_payable",
        description="Read back TMS payable data after entry.",
    ),
}


def get_tool_permission(tool_name: str) -> ToolPermission | None:
    return TOOL_REGISTRY.get(tool_name)


def evaluate_tool_permission(tool_name: str, context: ToolContext) -> ToolPermissionDecision:
    permission = get_tool_permission(tool_name)
    if permission is None:
        return ToolPermissionDecision(
            tool_name=tool_name,
            allowed=False,
            reason="unknown tool",
        )

    base = {
        "tool_name": tool_name,
        "risk": permission.risk,
        "approval_required": permission.approval_required,
    }
    if context.workflow_state not in permission.allowed_states:
        return ToolPermissionDecision(
            **base,
            allowed=False,
            reason=f"state {context.workflow_state.value} cannot use {tool_name}",
        )
    if permission.requires_outbound_enabled and not context.outbound_enabled:
        return ToolPermissionDecision(
            **base,
            allowed=False,
            reason="outbound messages are disabled",
        )
    if permission.requires_tms_write_enabled and not context.tms_write_enabled:
        return ToolPermissionDecision(
            **base,
            allowed=False,
            reason="TMS write tools are disabled",
        )
    if (
        permission.approval_required == ApprovalRequirement.EXPLICIT_HUMAN
        and not context.approval_granted
    ):
        return ToolPermissionDecision(
            **base,
            allowed=False,
            reason="explicit human approval is required",
        )

    return ToolPermissionDecision(
        **base,
        allowed=True,
        reason="allowed",
        audit_event=permission.audit_event,
    )


def record_tool_permission_decision(
    store: WorkflowStore,
    run_id: int,
    *,
    decision: ToolPermissionDecision,
    context: ToolContext,
) -> None:
    store.add_audit_event(
        run_id,
        "tool_permission_allowed" if decision.allowed else "tool_permission_blocked",
        actor=context.actor,
        payload={
            "tool_name": decision.tool_name,
            "allowed": decision.allowed,
            "reason": decision.reason,
            "risk": decision.risk.value if decision.risk else None,
            "approval_required": decision.approval_required.value if decision.approval_required else None,
            "workflow_state": context.workflow_state.value,
            "approval_granted": context.approval_granted,
            "outbound_enabled": context.outbound_enabled,
            "tms_write_enabled": context.tms_write_enabled,
        },
    )
