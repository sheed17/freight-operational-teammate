"""Carrier follow-up draft generation behind a send gate."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from .reconciliation import FreightLoadForReconciliation
from .review import ReviewPayload
from .review_actions import ReviewDecision
from .workflow import WorkflowStore


class FollowUpType(str, Enum):
    DISPUTE = "DISPUTE"
    REQUEST_BACKUP = "REQUEST_BACKUP"
    DUPLICATE_CHECK = "DUPLICATE_CHECK"


class SendGateStatus(str, Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED_TO_SEND = "APPROVED_TO_SEND"
    CANCELLED = "CANCELLED"


class FollowUpDraft(BaseModel):
    run_id: int
    load_id: str
    invoice_number: str
    carrier: str
    draft_type: FollowUpType
    to: str
    subject: str
    body: str
    evidence_urls: list[str] = Field(default_factory=list)
    send_gate_status: SendGateStatus = SendGateStatus.PENDING_APPROVAL
    tone: str = "short and direct"


def build_follow_up_draft(
    payload: ReviewPayload,
    load: FreightLoadForReconciliation,
    decision: ReviewDecision,
) -> FollowUpDraft:
    """Create a carrier follow-up draft without sending it."""
    draft_type = _draft_type_for(decision)
    evidence_urls = _evidence_urls(payload, draft_type)
    subject = _subject_for(payload, draft_type)
    body = _body_for(payload, load, draft_type)
    return FollowUpDraft(
        run_id=payload.run_id,
        load_id=payload.load_id,
        invoice_number=payload.invoice_number,
        carrier=payload.carrier,
        draft_type=draft_type,
        to=_carrier_email(payload.carrier),
        subject=subject,
        body=body,
        evidence_urls=evidence_urls,
        tone=payload.client.follow_up_tone,
    )


def record_follow_up_draft(store: WorkflowStore, draft: FollowUpDraft) -> None:
    """Audit that a follow-up draft was prepared behind a send gate."""
    draft_key = f"{draft.run_id}:{draft.draft_type.value}:{draft.invoice_number}"
    for event in store.audit_events(draft.run_id):
        if (
            event["event_type"] == "follow_up_draft_created"
            and event["payload"].get("draft_key") == draft_key
        ):
            return
    data = draft.model_dump(mode="json")
    data["draft_key"] = draft_key
    store.add_audit_event(
        draft.run_id,
        "follow_up_draft_created",
        actor="system",
        payload=data,
    )


def _draft_type_for(decision: ReviewDecision) -> FollowUpType:
    if decision in {ReviewDecision.APPROVE_EXPECTED_AMOUNT, ReviewDecision.DISPUTE}:
        return FollowUpType.DISPUTE
    if decision == ReviewDecision.REQUEST_BACKUP:
        return FollowUpType.REQUEST_BACKUP
    if decision == ReviewDecision.MARK_DUPLICATE:
        return FollowUpType.DUPLICATE_CHECK
    raise ValueError(f"decision does not create a follow-up draft: {decision.value}")


def _subject_for(payload: ReviewPayload, draft_type: FollowUpType) -> str:
    if draft_type == FollowUpType.DISPUTE:
        return f"Invoice {payload.invoice_number} variance on load {payload.load_id}"
    if draft_type == FollowUpType.REQUEST_BACKUP:
        return f"Backup needed for invoice {payload.invoice_number}"
    return f"Duplicate invoice check for {payload.invoice_number}"


def _body_for(payload: ReviewPayload, load: FreightLoadForReconciliation, draft_type: FollowUpType) -> str:
    reasons = "; ".join(payload.reasons)
    if draft_type == FollowUpType.DISPUTE:
        expected = _expected_total(load)
        invoice = _invoice_total(load)
        return (
            f"Please review invoice {payload.invoice_number} for load {payload.load_id}.\n\n"
            f"Our records show ${expected}, but the invoice totals ${invoice}.\n\n"
            f"Reason: {reasons}\n\n"
            "Please send a revised invoice or backup for the variance."
        )
    if draft_type == FollowUpType.REQUEST_BACKUP:
        return (
            f"Please send the missing backup for invoice {payload.invoice_number} on load {payload.load_id}.\n\n"
            f"Reason: {reasons}"
        )
    return (
        f"We received invoice {payload.invoice_number} more than once for load {payload.load_id}.\n\n"
        "Please confirm which packet should be processed."
    )


def _evidence_urls(payload: ReviewPayload, draft_type: FollowUpType) -> list[str]:
    wanted = {"carrier_invoice", "rate_confirmation"}
    if draft_type == FollowUpType.REQUEST_BACKUP:
        wanted = {"carrier_invoice", "pod", "lumper_receipt", "rate_confirmation"}
    return [
        link.url
        for link in payload.evidence_links
        if link.document_type in wanted
    ]


def _carrier_email(carrier: str) -> str:
    slug = "".join(ch.lower() for ch in carrier if ch.isalnum())
    return f"billing+{slug}@example-carrier.test"


def _invoice_total(load: FreightLoadForReconciliation) -> str:
    total = load.invoice_linehaul + load.invoice_fuel + sum(line.amount for line in load.invoice_accessorials)
    return f"{total:.2f}"


def _expected_total(load: FreightLoadForReconciliation) -> str:
    total = load.rate_linehaul + load.rate_fuel + sum(line.amount for line in load.rate_accessorials)
    return f"{total:.2f}"
