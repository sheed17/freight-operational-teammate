"""Human review payloads for supervised freight workflow decisions.

This module is channel-agnostic on purpose. Slack renders these typed payloads for human review;
the workflow core should not know about channel-specific blocks/buttons.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .extraction_bridge import apply_extracted_invoice
from .reconciliation import FreightLoadForReconciliation, ReconciliationOutcome
from .workflow import WorkflowRun, WorkflowState, WorkflowStore


def review_load_for_run(
    store: WorkflowStore, run: WorkflowRun, source_load: FreightLoadForReconciliation
) -> FreightLoadForReconciliation:
    """Return the load the review card should render from.

    On the real-extraction path the run carries the extracted invoice side (what the carrier
    *actually billed*); overlay it onto the source-of-truth load so the Slack card fields, variance
    dollars, and exact-amount money buttons reflect the real read. On the ground-truth path (no
    extraction event) the source load is returned unchanged.
    """
    for event in reversed(store.audit_events(run.id)):
        if event["event_type"] == "extraction_recorded" and event["payload"].get("source") == "vision_extraction":
            extracted = event["payload"].get("extracted_invoice")
            if extracted:
                return apply_extracted_invoice(source_load, extracted)
            break
    return source_load


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


class ReviewRoute(str, Enum):
    IMMEDIATE_PING = "IMMEDIATE_PING"
    CHANNEL_POST = "CHANNEL_POST"
    DIGEST_ONLY = "DIGEST_ONLY"


class ReviewField(BaseModel):
    label: str
    invoice_value: str | None = None
    expected_value: str | None = None
    status: str


class EvidenceLink(BaseModel):
    label: str
    document_type: str
    path: str
    url: str
    note: str | None = None


class ReviewActionOption(BaseModel):
    code: ReviewAction
    label: str
    amount: str | None = None
    requires_send_gate: bool = False
    creates_follow_up_draft: bool = False
    consequence: str


class AgingMetadata(BaseModel):
    age_hours: int = 0
    is_overdue: bool = False
    next_escalation: str | None = None


class RoutingDecision(BaseModel):
    route: ReviewRoute
    ping: bool = False
    reason: str


class FoundMoney(BaseModel):
    flagged_amount: str = "0.00"
    confirmed_recovered: str = "0.00"
    currency: str = "USD"


class DogfoodClientProfile(BaseModel):
    company_name: str = "Neyma Test Freight LLC"
    operator_name: str = "Rasheed"
    operator_role: str = "owner/operator"
    follow_up_tone: str = "short and direct"
    packet_base_url: str = "http://localhost:8000/packets"
    evidence_base_url: str = "http://localhost:8000/evidence"
    critical_variance_threshold: Decimal = Decimal("100.00")
    medium_variance_threshold: Decimal = Decimal("25.00")


class ReviewPayload(BaseModel):
    run_id: int
    client: DogfoodClientProfile = Field(default_factory=DogfoodClientProfile)
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
    action_options: list[ReviewActionOption] = Field(default_factory=list)
    source_documents: dict[str, str] = Field(default_factory=dict)
    evidence_links: list[EvidenceLink] = Field(default_factory=list)
    packet_detail_url: str
    routing: RoutingDecision
    aging: AgingMetadata = Field(default_factory=AgingMetadata)
    found_money: FoundMoney = Field(default_factory=FoundMoney)
    audit_context: dict[str, Any] = Field(default_factory=dict)


def build_review_payload(
    run: WorkflowRun,
    load: FreightLoadForReconciliation,
    *,
    client: DogfoodClientProfile | None = None,
    age_hours: int = 0,
) -> ReviewPayload | None:
    """Build a human-review card from a workflow run and load context.

    Returns ``None`` for runs that do not require human review.
    """
    if run.state != WorkflowState.NEEDS_REVIEW:
        return None
    if not run.outcome:
        return None

    client = client or DogfoodClientProfile()
    outcome = ReconciliationOutcome(run.outcome)
    reasons = _split_reason(run.reason)
    fields = _fields_for_outcome(outcome, load, reasons)
    flagged_amount = _flagged_amount(outcome, load)
    routing = _routing_for(outcome, reasons, flagged_amount, client)
    return ReviewPayload(
        run_id=run.id,
        client=client,
        load_id=run.load_id,
        invoice_number=run.invoice_number or load.invoice_number,
        carrier=run.carrier or load.carrier,
        outcome=outcome,
        state=run.state,
        severity=_severity_for(outcome, reasons, flagged_amount, client),
        title=_title_for(outcome, load),
        summary=_summary_for(outcome, load, reasons),
        reasons=reasons,
        fields=fields,
        actions=_actions_for(outcome, reasons),
        action_options=_action_options_for(outcome, load, reasons, flagged_amount),
        source_documents=load.documents,
        evidence_links=_evidence_links_for(load, client),
        packet_detail_url=f"{client.packet_base_url}/{run.id}",
        routing=routing,
        aging=_aging_for(age_hours, routing),
        found_money=FoundMoney(flagged_amount=_money(flagged_amount)),
        audit_context={
            "requires_human": True,
            "no_autonomous_tms_write": True,
            "workflow_state": run.state.value,
            "dogfood_company": client.company_name,
            "operator_role": client.operator_role,
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
    """Render a compact plain-text review message for CLI/local artifacts."""
    lines = [
        payload.title,
        f"Load: {payload.load_id}",
        f"Carrier: {payload.carrier}",
        f"Invoice: {payload.invoice_number}",
        f"Outcome: {payload.outcome.value}",
        f"Severity: {payload.severity.value}",
        f"Route: {payload.routing.route.value}",
        f"Packet: {payload.packet_detail_url}",
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
    if payload.evidence_links:
        lines.append("")
        lines.append("Evidence:")
        lines.extend(f"- {link.label}: {link.url}" for link in payload.evidence_links)
    lines.append("")
    if payload.action_options:
        lines.append("Actions:")
        lines.extend(f"- {option.label}" for option in payload.action_options)
    else:
        lines.append("Actions: " + ", ".join(action.value for action in payload.actions))
    return "\n".join(lines)


def _split_reason(reason: str | None) -> list[str]:
    if not reason:
        return []
    return [part.strip() for part in reason.split(";") if part.strip()]


def _severity_for(
    outcome: ReconciliationOutcome,
    reasons: list[str],
    flagged_amount: Decimal,
    client: DogfoodClientProfile,
) -> ReviewSeverity:
    if outcome == ReconciliationOutcome.DUPLICATE:
        return ReviewSeverity.CRITICAL
    if outcome == ReconciliationOutcome.VARIANCE and flagged_amount >= client.critical_variance_threshold:
        return ReviewSeverity.CRITICAL
    if outcome == ReconciliationOutcome.VARIANCE:
        return ReviewSeverity.WARNING
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


def _action_options_for(
    outcome: ReconciliationOutcome,
    load: FreightLoadForReconciliation,
    reasons: list[str],
    flagged_amount: Decimal,
) -> list[ReviewActionOption]:
    expected_total = _expected_total(load)
    invoice_total = _invoice_total(load)
    if outcome == ReconciliationOutcome.DUPLICATE:
        return [
            ReviewActionOption(
                code=ReviewAction.MARK_DUPLICATE,
                label="Mark duplicate",
                consequence="Closes this packet as duplicate and prevents payable entry.",
            ),
            ReviewActionOption(
                code=ReviewAction.DISPUTE,
                label="Dispute duplicate invoice",
                requires_send_gate=True,
                creates_follow_up_draft=True,
                consequence="Creates a short carrier dispute draft behind a send gate.",
            ),
        ]

    if outcome == ReconciliationOutcome.VARIANCE:
        dispute_label = f"Approve ${_money(expected_total)} and dispute ${_money(flagged_amount)} variance"
        if any("detention" in reason.lower() for reason in reasons):
            dispute_label = f"Approve ${_money(expected_total)} and dispute ${_money(flagged_amount)} detention"
        return [
            ReviewActionOption(
                code=ReviewAction.APPROVE,
                label=dispute_label,
                amount=_money(expected_total),
                requires_send_gate=True,
                creates_follow_up_draft=True,
                consequence="Approves expected payable amount and drafts a carrier dispute.",
            ),
            ReviewActionOption(
                code=ReviewAction.APPROVE,
                label=f"Approve full ${_money(invoice_total)}",
                amount=_money(invoice_total),
                consequence="Approves the carrier invoice as billed.",
            ),
            ReviewActionOption(
                code=ReviewAction.EDIT,
                label="Edit fields",
                consequence="Opens the packet detail page for correction before decision.",
            ),
        ]

    options = [
        ReviewActionOption(
            code=ReviewAction.EDIT,
            label="Edit packet",
            consequence="Opens the packet detail page for correction before decision.",
        )
    ]
    if any("missing backup" in reason.lower() or "missing pod" in reason.lower() for reason in reasons):
        options.append(
            ReviewActionOption(
                code=ReviewAction.REQUEST_BACKUP,
                label="Request backup from carrier",
                requires_send_gate=True,
                creates_follow_up_draft=True,
                consequence="Creates a short backup-request email behind a send gate.",
            )
        )
    options.append(
        ReviewActionOption(
            code=ReviewAction.APPROVE,
            label=f"Approve ${_money(invoice_total)} anyway",
            amount=_money(invoice_total),
            consequence="Approves the invoice despite missing evidence.",
        )
    )
    return options


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


def _evidence_links_for(load: FreightLoadForReconciliation, client: DogfoodClientProfile) -> list[EvidenceLink]:
    labels = {
        "carrier_invoice": "Carrier invoice",
        "rate_confirmation": "Rate confirmation",
        "pod": "POD",
        "bol": "BOL",
        "lumper_receipt": "Lumper receipt",
        "fuel_receipt": "Fuel receipt",
        "manifest": "Manifest",
    }
    links: list[EvidenceLink] = []
    for doc_type, path in sorted(load.documents.items()):
        clean_type = doc_type.removesuffix("_dirty")
        label = labels.get(clean_type, clean_type.replace("_", " ").title())
        links.append(
            EvidenceLink(
                label=label,
                document_type=doc_type,
                path=path,
                url=f"{client.evidence_base_url}/{load.load_id}/{doc_type}",
                note="dirty scan" if doc_type.endswith("_dirty") else None,
            )
        )
    return links


def _routing_for(
    outcome: ReconciliationOutcome,
    reasons: list[str],
    flagged_amount: Decimal,
    client: DogfoodClientProfile,
) -> RoutingDecision:
    if outcome == ReconciliationOutcome.DUPLICATE:
        return RoutingDecision(route=ReviewRoute.IMMEDIATE_PING, ping=True, reason="duplicate invoice")
    if outcome == ReconciliationOutcome.VARIANCE:
        if flagged_amount >= client.critical_variance_threshold:
            return RoutingDecision(
                route=ReviewRoute.IMMEDIATE_PING,
                ping=True,
                reason=f"variance at or above ${_money(client.critical_variance_threshold)}",
            )
        if flagged_amount >= client.medium_variance_threshold:
            return RoutingDecision(route=ReviewRoute.CHANNEL_POST, reason="medium money variance")
        return RoutingDecision(route=ReviewRoute.DIGEST_ONLY, reason="low money variance")
    if any("missing pod" in reason.lower() for reason in reasons):
        return RoutingDecision(route=ReviewRoute.IMMEDIATE_PING, ping=True, reason="missing POD")
    if any("missing" in reason.lower() for reason in reasons):
        return RoutingDecision(route=ReviewRoute.CHANNEL_POST, reason="missing packet evidence")
    return RoutingDecision(route=ReviewRoute.DIGEST_ONLY, reason="low severity review")


def _aging_for(age_hours: int, routing: RoutingDecision) -> AgingMetadata:
    if age_hours >= 72 and routing.ping:
        return AgingMetadata(age_hours=age_hours, is_overdue=True, next_escalation="direct re-ping now")
    if age_hours >= 48:
        return AgingMetadata(age_hours=age_hours, is_overdue=True, next_escalation="re-surface in daily summary")
    if age_hours >= 24:
        return AgingMetadata(age_hours=age_hours, is_overdue=False, next_escalation="daily digest reminder")
    return AgingMetadata(age_hours=age_hours)


def _invoice_total(load: FreightLoadForReconciliation) -> Decimal:
    return load.invoice_linehaul + load.invoice_fuel + sum(line.amount for line in load.invoice_accessorials)


def _expected_total(load: FreightLoadForReconciliation) -> Decimal:
    return load.rate_linehaul + load.rate_fuel + sum(line.amount for line in load.rate_accessorials)


def _flagged_amount(outcome: ReconciliationOutcome, load: FreightLoadForReconciliation) -> Decimal:
    if outcome != ReconciliationOutcome.VARIANCE:
        return Decimal("0.00")
    delta = _invoice_total(load) - _expected_total(load)
    return abs(delta)


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _payload_key(payload: ReviewPayload) -> str:
    action_content = {
        "run_id": payload.run_id,
        "state": payload.state.value,
        "outcome": payload.outcome.value,
        "reasons": payload.reasons,
        "summary": payload.summary,
        "flagged_amount": payload.found_money.flagged_amount,
        "packet_detail_url": payload.packet_detail_url,
        "fields": [field.model_dump(mode="json") for field in payload.fields],
        "action_options": [option.model_dump(mode="json") for option in payload.action_options],
    }
    digest = hashlib.sha256(
        json.dumps(action_content, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"{payload.run_id}:{digest}"
