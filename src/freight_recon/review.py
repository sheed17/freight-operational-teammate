"""Human review payloads for supervised freight workflow decisions.

This module is channel-agnostic on purpose. Slack, Teams, and email adapters should render these
typed payloads later; the workflow core should not know about channel-specific blocks/buttons.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .reconciliation import FreightLoadForReconciliation, ReconciliationOutcome
from .workflow import WorkflowRun, WorkflowState, WorkflowStore


class ReviewSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class ReviewAction(str, Enum):
    APPROVE = "APPROVE"
    EDIT = "EDIT"
    DISPUTE = "DISPUTE"
    REQUEST_BACKUP = "REQUEST_BACKUP"
    MARK_DUPLICATE = "MARK_DUPLICATE"


class ReviewField(BaseModel):
    label: str
    invoice_value: str | None = None
    expected_value: str | None = None
    status: str


class ReviewPayload(BaseModel):
    run_id: int
    load_id: str
    invoice_number: str
    carrier: str
    outcome: ReconciliationOutcome
    state: WorkflowState
    severity: ReviewSeverity
    title: str
    summary: str
    reasons: list[str] = Field(default_factory=list)
    fields: list[ReviewField] = Field(default_factory=list)
    actions: list[ReviewAction] = Field(default_factory=list)
    source_documents: dict[str, str] = Field(default_factory=dict)
    audit_context: dict[str, Any] = Field(default_factory=dict)


def build_review_payload(run: WorkflowRun, load: FreightLoadForReconciliation) -> ReviewPayload | None:
    """Build a human-review card from a workflow run and load context.

    Returns ``None`` for runs that do not require human review.
    """
    if run.state != WorkflowState.NEEDS_REVIEW:
        return None
    if not run.outcome:
        return None

    outcome = ReconciliationOutcome(run.outcome)
    reasons = _split_reason(run.reason)
    fields = _fields_for_outcome(outcome, load, reasons)
    return ReviewPayload(
        run_id=run.id,
        load_id=run.load_id,
        invoice_number=run.invoice_number or load.invoice_number,
        carrier=run.carrier or load.carrier,
        outcome=outcome,
        state=run.state,
        severity=_severity_for(outcome, reasons),
        title=_title_for(outcome, load),
        summary=_summary_for(outcome, load, reasons),
        reasons=reasons,
        fields=fields,
        actions=_actions_for(outcome, reasons),
        source_documents=load.documents,
        audit_context={
            "requires_human": True,
            "no_autonomous_tms_write": True,
            "workflow_state": run.state.value,
        },
    )


def record_review_payload(store: WorkflowStore, payload: ReviewPayload) -> None:
    """Audit that a review payload was created for a human-facing channel."""
    payload_key = _payload_key(payload)
    for event in store.audit_events(payload.run_id):
        if (
            event["event_type"] == "review_payload_created"
            and event["payload"].get("payload_key") == payload_key
        ):
            return

    data = payload.model_dump(mode="json")
    data["payload_key"] = payload_key
    store.add_audit_event(
        payload.run_id,
        "review_payload_created",
        actor="system",
        payload=data,
    )


def render_text_review(payload: ReviewPayload) -> str:
    """Render a compact plain-text review message for CLI/email fallback."""
    lines = [
        payload.title,
        f"Load: {payload.load_id}",
        f"Carrier: {payload.carrier}",
        f"Invoice: {payload.invoice_number}",
        f"Outcome: {payload.outcome.value}",
        f"Severity: {payload.severity.value}",
        "",
        payload.summary,
    ]
    if payload.reasons:
        lines.append("")
        lines.append("Reasons:")
        lines.extend(f"- {reason}" for reason in payload.reasons)
    if payload.fields:
        lines.append("")
        lines.append("Review fields:")
        for field in payload.fields:
            expected = f" expected={field.expected_value}" if field.expected_value is not None else ""
            invoice = f" invoice={field.invoice_value}" if field.invoice_value is not None else ""
            lines.append(f"- {field.label}: {field.status}{invoice}{expected}")
    lines.append("")
    lines.append("Actions: " + ", ".join(action.value for action in payload.actions))
    return "\n".join(lines)


def _split_reason(reason: str | None) -> list[str]:
    if not reason:
        return []
    return [part.strip() for part in reason.split(";") if part.strip()]


def _severity_for(outcome: ReconciliationOutcome, reasons: list[str]) -> ReviewSeverity:
    if outcome in {ReconciliationOutcome.DUPLICATE, ReconciliationOutcome.VARIANCE}:
        return ReviewSeverity.CRITICAL
    if any("missing" in reason.lower() for reason in reasons):
        return ReviewSeverity.WARNING
    return ReviewSeverity.INFO


def _title_for(outcome: ReconciliationOutcome, load: FreightLoadForReconciliation) -> str:
    if outcome == ReconciliationOutcome.VARIANCE:
        return f"Review variance for {load.load_id}"
    if outcome == ReconciliationOutcome.DUPLICATE:
        return f"Review duplicate invoice for {load.load_id}"
    return f"Review invoice packet for {load.load_id}"


def _summary_for(
    outcome: ReconciliationOutcome,
    load: FreightLoadForReconciliation,
    reasons: list[str],
) -> str:
    if outcome == ReconciliationOutcome.VARIANCE:
        return "Invoice values do not match the rate/load record. Human approval is required."
    if outcome == ReconciliationOutcome.DUPLICATE:
        return "This carrier invoice number appears more than once. Do not enter payable until reviewed."
    if reasons:
        return "The packet is missing backup or evidence needed before approval."
    return f"Invoice {load.invoice_number} needs human review."


def _actions_for(outcome: ReconciliationOutcome, reasons: list[str]) -> list[ReviewAction]:
    actions = [ReviewAction.EDIT, ReviewAction.DISPUTE]
    if outcome == ReconciliationOutcome.DUPLICATE:
        return [ReviewAction.MARK_DUPLICATE, ReviewAction.DISPUTE]
    if any("missing backup" in reason.lower() or "missing pod" in reason.lower() for reason in reasons):
        actions.append(ReviewAction.REQUEST_BACKUP)
    actions.append(ReviewAction.APPROVE)
    return actions


def _fields_for_outcome(
    outcome: ReconciliationOutcome,
    load: FreightLoadForReconciliation,
    reasons: list[str],
) -> list[ReviewField]:
    fields = [
        ReviewField(
            label="linehaul",
            invoice_value=_money(load.invoice_linehaul),
            expected_value=_money(load.rate_linehaul),
            status="match" if load.invoice_linehaul == load.rate_linehaul else "variance",
        ),
        ReviewField(
            label="fuel",
            invoice_value=_money(load.invoice_fuel),
            expected_value=_money(load.rate_fuel),
            status="match" if load.invoice_fuel == load.rate_fuel else "variance",
        ),
    ]

    invoice_accessorials = {line.key: line for line in load.invoice_accessorials}
    rate_accessorials = {line.key: line for line in load.rate_accessorials}
    for key, invoice_line in invoice_accessorials.items():
        rate_line = rate_accessorials.get(key)
        fields.append(
            ReviewField(
                label=invoice_line.name,
                invoice_value=_money(invoice_line.amount),
                expected_value=_money(rate_line.amount) if rate_line else None,
                status="authorized" if rate_line else "unauthorized",
            )
        )

    if any("missing POD" in reason for reason in reasons):
        fields.append(ReviewField(label="POD", status="missing"))
    if outcome == ReconciliationOutcome.DUPLICATE:
        fields.append(ReviewField(label="invoice_number", invoice_value=load.invoice_number, status="duplicate"))
    return fields


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _payload_key(payload: ReviewPayload) -> str:
    return f"{payload.run_id}:{payload.state.value}:{payload.outcome.value}:{len(payload.reasons)}"
