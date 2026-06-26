"""Mailbox-to-workflow orchestration.

This is the first operational spine for "the agent sits in the inbox": local inbound
``.eml`` files are preserved and packetized, then linked to the durable reconciliation
state machine, review payloads, and signed delivery messages.

Email remains inbound-only here. Human approval surfaces through the delivery layer, and
money/TMS actions still require the existing workflow gates.
"""

from __future__ import annotations

import email
import hashlib
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from pydantic import BaseModel, Field

from .delivery import (
    DeliveryChannel,
    DeliveryMessage,
    DeliverySigner,
    build_delivery_message,
    record_delivery_message,
    redact_delivery_message,
)
from .ingestion import AttachmentTextExtractor
from .mailbox_intake import MailboxMessageRecord, MailboxPacketRun, MailboxPollResult, run_mailbox_intake
from .extraction_bridge import reconciliation_from_extraction
from .reconciliation import (
    FreightLoadForReconciliation,
    ReconciliationOutcome,
    ReconciliationResult,
    reconcile_load,
)
from .review import (
    AgingMetadata,
    DogfoodClientProfile,
    EvidenceLink,
    FoundMoney,
    ReviewAction,
    ReviewActionOption,
    ReviewField,
    ReviewPayload,
    ReviewRoute,
    ReviewSeverity,
    RoutingDecision,
    build_review_payload,
    record_review_payload,
    review_load_for_run,
)
from .workflow import TERMINAL_STATES, WorkflowRun, WorkflowState, WorkflowStore


class MailboxWorkflowPacketResult(BaseModel):
    load_id: str
    workflow_run_id: int | None = None
    workflow_state: WorkflowState | None = None
    outcome: str | None = None
    packet_needs_human: bool = False
    packet_flags: list[str] = Field(default_factory=list)
    missing_required: list[str] = Field(default_factory=list)
    extraneous_attachments: int = 0
    review_created: bool = False
    delivery_created: bool = False
    skipped_reason: str | None = None


class MailboxWorkflowResult(BaseModel):
    mailbox: MailboxPollResult
    packet_results: list[MailboxWorkflowPacketResult] = Field(default_factory=list)
    review_payloads: list[ReviewPayload] = Field(default_factory=list)
    delivery_messages: list[DeliveryMessage] = Field(default_factory=list)

    @property
    def workflow_runs(self) -> int:
        return sum(1 for item in self.packet_results if item.workflow_run_id is not None)

    @property
    def reviews_created(self) -> int:
        return sum(1 for item in self.packet_results if item.review_created)

    @property
    def deliveries_created(self) -> int:
        return sum(1 for item in self.packet_results if item.delivery_created)


def run_mailbox_workflow(
    *,
    inbox_dir: str | Path,
    preserve_dir: str | Path,
    mailbox_state_path: str | Path,
    workflow_db_path: str | Path,
    loads: list[FreightLoadForReconciliation],
    signer: DeliverySigner | None = None,
    client: DogfoodClientProfile | None = None,
    actor: str = "Rasheed",
    channel: DeliveryChannel = DeliveryChannel.LOCAL,
    age_hours: int = 0,
    record_audit: bool = True,
    redact_tokens: bool = True,
    extractor: Callable[[str | Path], Any] | None = None,
    confidence_threshold: float = 0.85,
    attachment_text_extractor: AttachmentTextExtractor | None = None,
) -> MailboxWorkflowResult:
    """Run the controlled mailbox intake through workflow, review, and delivery.

    The packet workflow idempotency key is load/invoice scoped rather than content-hash scoped.
    That lets trickle-in emails update the same operational packet without creating a new money
    run every time a missing POD arrives.
    """

    mailbox = run_mailbox_intake(
        inbox_dir=inbox_dir,
        preserve_dir=preserve_dir,
        state_path=mailbox_state_path,
        loads=loads,
        attachment_text_extractor=attachment_text_extractor,
    )
    load_by_id = {load.load_id: load for load in loads}
    store = WorkflowStore(workflow_db_path)
    seen_invoice_keys = _seen_invoice_keys_from_store(store)
    packet_results: list[MailboxWorkflowPacketResult] = []
    review_payloads: list[ReviewPayload] = []
    delivery_messages: list[DeliveryMessage] = []
    client_profile = client or DogfoodClientProfile()

    try:
        for packet_run in mailbox.packet_runs:
            load = load_by_id.get(packet_run.load_id)
            if load is None:
                packet_results.append(
                    MailboxWorkflowPacketResult(
                        load_id=packet_run.load_id,
                        packet_needs_human=True,
                        packet_flags=list(packet_run.packet.flags),
                        missing_required=list(packet_run.packet.missing_required),
                        extraneous_attachments=packet_run.packet.extraneous_attachments,
                        skipped_reason="load not found in source-of-truth corpus",
                    )
                )
                continue

            run = _receive_or_refresh_packet(store, packet_run, load)
            if run.state == WorkflowState.RECEIVED:
                extraction_payload, result = _mailbox_extraction_payload_and_result(
                    packet_run=packet_run,
                    load=load,
                    preserve_dir=Path(preserve_dir),
                    seen_invoice_keys=seen_invoice_keys,
                    extractor=extractor,
                    confidence_threshold=confidence_threshold,
                )
                run = store.mark_extracted(run.id, extraction_payload)
                result = _apply_packet_review_flags(result, packet_run)
                run = store.mark_reconciled(run.id, result)
            elif run.state in {WorkflowState.NEEDS_REVIEW, WorkflowState.REQUESTED_BACKUP}:
                store.add_audit_event(
                    run.id,
                    "mailbox_packet_refreshed",
                    actor="system",
                    payload=_mailbox_packet_payload(packet_run, load),
                )
                extraction_payload, result = _mailbox_extraction_payload_and_result(
                    packet_run=packet_run,
                    load=load,
                    preserve_dir=Path(preserve_dir),
                    seen_invoice_keys=_seen_invoice_keys_from_store(store, exclude_run_id=run.id),
                    extractor=extractor,
                    confidence_threshold=confidence_threshold,
                )
                if extraction_payload["source"] == "vision_extraction":
                    store.add_audit_event(
                        run.id,
                        "extraction_recorded",
                        actor="system",
                        payload=extraction_payload,
                    )
                result = _apply_packet_review_flags(result, packet_run)
                run = store.refresh_reconciliation(run.id, result)
            elif run.state not in TERMINAL_STATES:
                store.add_audit_event(
                    run.id,
                    "mailbox_packet_refreshed",
                    actor="system",
                    payload=_mailbox_packet_payload(packet_run, load),
                )

            review_load = review_load_for_run(store, run, load)
            payload = build_review_payload(run, review_load, client=client_profile, age_hours=age_hours)
            if payload is not None:
                payload = _with_mailbox_packet_evidence(payload, packet_run)
            message = None
            if payload is not None:
                if record_audit:
                    record_review_payload(store, payload)
                review_payloads.append(payload)
                message = build_delivery_message(payload, signer, channel=channel, actor=actor)
                if record_audit:
                    record_delivery_message(store, message)
                delivery_messages.append(redact_delivery_message(message) if redact_tokens else message)

            packet_results.append(
                MailboxWorkflowPacketResult(
                    load_id=packet_run.load_id,
                    workflow_run_id=run.id,
                    workflow_state=run.state,
                    outcome=run.outcome,
                    packet_needs_human=packet_run.packet.needs_human,
                    packet_flags=list(packet_run.packet.flags),
                    missing_required=list(packet_run.packet.missing_required),
                    extraneous_attachments=packet_run.packet.extraneous_attachments,
                    review_created=payload is not None,
                    delivery_created=message is not None,
                )
            )
        for record in mailbox.unlinked_messages:
            run = _process_unlinked_message(store, record)
            payload = _build_unlinked_review_payload(
                run,
                record,
                client=client_profile,
                age_hours=age_hours,
            )
            message = None
            if payload is not None:
                if record_audit:
                    record_review_payload(store, payload)
                review_payloads.append(payload)
                message = build_delivery_message(payload, signer, channel=channel, actor=actor)
                if record_audit:
                    record_delivery_message(store, message)
                delivery_messages.append(redact_delivery_message(message) if redact_tokens else message)

            packet_results.append(
                MailboxWorkflowPacketResult(
                    load_id="UNLINKED",
                    workflow_run_id=run.id,
                    workflow_state=run.state,
                    outcome=run.outcome,
                    packet_needs_human=True,
                    packet_flags=["unlinked_message"],
                    review_created=payload is not None,
                    delivery_created=message is not None,
                    skipped_reason="inbound email could not be linked to a known load",
                )
            )
    finally:
        store.close()

    return MailboxWorkflowResult(
        mailbox=mailbox,
        packet_results=packet_results,
        review_payloads=review_payloads,
        delivery_messages=delivery_messages,
    )


def _receive_or_refresh_packet(
    store: WorkflowStore,
    packet_run: MailboxPacketRun,
    load: FreightLoadForReconciliation,
) -> WorkflowRun:
    packet_key = _packet_workflow_key(load)
    return store.receive_document(load.load_id, packet_key, payload=_mailbox_packet_payload(packet_run, load))


def _packet_workflow_key(load: FreightLoadForReconciliation) -> str:
    return f"mailbox_packet:{load.load_id}:{load.invoice_number}".lower()


def _mailbox_packet_payload(
    packet_run: MailboxPacketRun,
    load: FreightLoadForReconciliation,
) -> dict:
    packet = packet_run.packet
    return {
        "source": "mailbox_intake",
        "load_id": load.load_id,
        "invoice_number": load.invoice_number,
        "carrier": load.carrier,
        "source_message_count": packet_run.source_message_count,
        "packet_load_id": packet.packet_load_id,
        "link_confidence": packet.link_confidence,
        "delivered_doc_types": packet.delivered_doc_types,
        "missing_required": packet.missing_required,
        "extraneous_attachments": packet.extraneous_attachments,
        "needs_human": packet.needs_human,
        "flags": packet.flags,
        "attachments": [
            {
                "filename": attachment.filename,
                "sha256": attachment.sha256,
                "doc_type": attachment.classification.doc_type,
                "classification_confidence": attachment.classification.confidence,
                "linked_load_id": attachment.linked_load_id,
                "belongs_to_packet": attachment.belongs_to_packet,
                "flags": attachment.flags,
            }
            for attachment in packet.attachments
        ],
    }


def _mailbox_extraction_payload_and_result(
    *,
    packet_run: MailboxPacketRun,
    load: FreightLoadForReconciliation,
    preserve_dir: Path,
    seen_invoice_keys: set[tuple[str, str]] | None,
    extractor: Callable[[str | Path], Any] | None,
    confidence_threshold: float,
) -> tuple[dict, ReconciliationResult]:
    base_payload = {
        "invoice_number": load.invoice_number,
        "carrier": load.carrier,
        "source": "mailbox_packet_ground_truth",
        "packet_load_id": packet_run.packet.packet_load_id,
        "source_message_count": packet_run.source_message_count,
        "delivered_doc_types": packet_run.packet.delivered_doc_types,
        "mailbox_flags": packet_run.packet.flags,
    }
    if extractor is None:
        return base_payload, reconcile_load(load, seen_invoice_keys=seen_invoice_keys)

    invoice_path, invoice_issue = _materialize_carrier_invoice_attachment(packet_run, preserve_dir)
    if invoice_path is None:
        # Missing/ambiguous invoice remains a packet-review problem; do not synthesize an extraction.
        result = reconcile_load(load, seen_invoice_keys=seen_invoice_keys)
        if invoice_issue:
            result = result.model_copy(
                update={
                    "outcome": ReconciliationOutcome.NEEDS_REVIEW,
                    "reasons": [*result.reasons, invoice_issue],
                    "needs_human_review": True,
                }
            )
        return {
            **base_payload,
            "source": "mailbox_packet_no_extractable_invoice",
            "extractor_requested": True,
            "invoice_selection_issue": invoice_issue,
        }, result

    extraction_payload, result = reconciliation_from_extraction(
        load,
        _call_extractor(extractor, invoice_path),
        seen_invoice_keys=seen_invoice_keys,
        confidence_threshold=confidence_threshold,
    )
    extraction_payload.update(
        {
            "mailbox_invoice_attachment": str(invoice_path),
            "packet_load_id": packet_run.packet.packet_load_id,
            "source_message_count": packet_run.source_message_count,
            "delivered_doc_types": packet_run.packet.delivered_doc_types,
            "mailbox_flags": packet_run.packet.flags,
        }
    )
    return extraction_payload, result


def _materialize_carrier_invoice_attachment(
    packet_run: MailboxPacketRun,
    preserve_dir: Path,
) -> tuple[Path | None, str | None]:
    candidates = [
        attachment
        for attachment in packet_run.packet.attachments
        if attachment.belongs_to_packet and attachment.classification.doc_type == "carrier_invoice"
    ]
    if not candidates:
        return None, "no linked carrier invoice attachment"
    if len(candidates) > 1:
        return None, f"multiple linked carrier invoice attachments: {len(candidates)}"
    candidate = candidates[0]

    messages_dir = preserve_dir / "messages"
    output_dir = preserve_dir / "extracted_attachments"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{candidate.sha256[:16]}_{_safe_filename(candidate.filename)}"
    if output_path.exists():
        return output_path, None

    for eml_path in sorted(messages_dir.glob("*.eml")):
        mime = email.message_from_bytes(eml_path.read_bytes())
        for part in mime.walk():
            if part.get_content_disposition() != "attachment":
                continue
            payload = part.get_payload(decode=True) or b""
            if hashlib.sha256(payload).hexdigest() != candidate.sha256:
                continue
            output_path.write_bytes(payload)
            return output_path, None
    return None, "linked carrier invoice attachment was not found in preserved messages"


def _safe_filename(filename: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in filename)
    return cleaned or "attachment.pdf"


def _call_extractor(extractor: Callable[[str | Path], Any], path: str | Path) -> Any:
    try:
        return extractor(path)
    except Exception as exc:  # noqa: BLE001 - keep mailbox runs reviewable on render/provider failure
        return SimpleNamespace(extraction=None, model=None, error=f"{type(exc).__name__}: {exc}")


def _process_unlinked_message(store: WorkflowStore, record: MailboxMessageRecord) -> WorkflowRun:
    run = store.receive_document(
        "UNLINKED",
        f"mailbox_unlinked:{record.sha256}",
        payload={
            "source": "mailbox_intake",
            "reason": "inbound email could not be linked to a known load",
            "message": record.model_dump(mode="json"),
        },
    )
    if run.state == WorkflowState.RECEIVED:
        run = store.mark_extracted(
            run.id,
            {
                "source": "mailbox_unlinked_message",
                "subject": record.subject,
                "from_addr": record.from_addr,
                "attachment_names": record.attachment_names,
            },
        )
        result = ReconciliationResult(
            load_id="UNLINKED",
            invoice_number="UNKNOWN",
            carrier=record.from_addr or "UNKNOWN",
            outcome=ReconciliationOutcome.NEEDS_REVIEW,
            reasons=[
                "inbound email could not be linked to a known load",
                f"subject: {record.subject or '(no subject)'}",
            ],
            needs_human_review=True,
        )
        return store.mark_reconciled(run.id, result)
    return run


def _with_mailbox_packet_evidence(
    payload: ReviewPayload,
    packet_run: MailboxPacketRun,
) -> ReviewPayload:
    packet = packet_run.packet
    source_documents = {
        f"received_{index}_{attachment.classification.doc_type}": attachment.filename
        for index, attachment in enumerate(packet.attachments, start=1)
    }
    evidence_links = _packet_evidence_links(payload.client, packet_run)
    audit_context = {
        **payload.audit_context,
        "mailbox_packet_load_id": packet.packet_load_id,
        "mailbox_source_message_count": packet_run.source_message_count,
        "mailbox_delivered_doc_types": packet.delivered_doc_types,
        "mailbox_missing_required": packet.missing_required,
        "mailbox_extraneous_attachments": packet.extraneous_attachments,
        "mailbox_flags": packet.flags,
    }
    return payload.model_copy(
        update={
            "source_documents": source_documents,
            "evidence_links": evidence_links or payload.evidence_links,
            "audit_context": audit_context,
        }
    )


def _packet_evidence_links(
    client: DogfoodClientProfile,
    packet_run: MailboxPacketRun,
) -> list[EvidenceLink]:
    links: list[EvidenceLink] = []
    for index, attachment in enumerate(packet_run.packet.attachments, start=1):
        doc_type = attachment.classification.doc_type
        status = "received"
        if attachment.flags:
            status = ",".join(attachment.flags)
        elif not attachment.belongs_to_packet:
            status = "not in packet"
        note = (
            f"{status}; link={attachment.linked_load_id or 'unlinked'}; "
            f"confidence={attachment.classification.confidence:.2f}"
        )
        links.append(
            EvidenceLink(
                label=f"Received {doc_type}: {attachment.filename}",
                document_type=doc_type,
                path=f"mailbox://{attachment.sha256}/{attachment.filename}",
                url=f"{client.evidence_base_url}/{packet_run.load_id}/mailbox/{attachment.sha256[:12]}",
                note=note,
            )
        )
    return links


def _build_unlinked_review_payload(
    run: WorkflowRun,
    record: MailboxMessageRecord,
    *,
    client: DogfoodClientProfile,
    age_hours: int,
) -> ReviewPayload | None:
    if run.state != WorkflowState.NEEDS_REVIEW:
        return None
    routing = RoutingDecision(
        route=ReviewRoute.CHANNEL_POST,
        ping=False,
        reason="inbound email could not be linked to a load",
    )
    evidence = [
        EvidenceLink(
            label=f"Inbound email: {record.subject or '(no subject)'}",
            document_type="email",
            path=record.preserved_path,
            url=f"{client.evidence_base_url}/unlinked/{record.sha256[:12]}",
            note=f"from {record.from_addr or 'unknown sender'}; attachments={record.attachment_count}",
        )
    ]
    evidence.extend(
        EvidenceLink(
            label=f"Attachment: {name}",
            document_type="unknown",
            path=f"mailbox://{record.sha256}/{name}",
            url=f"{client.evidence_base_url}/unlinked/{record.sha256[:12]}/{index}",
            note="unlinked inbound attachment",
        )
        for index, name in enumerate(record.attachment_names, start=1)
    )
    return ReviewPayload(
        run_id=run.id,
        client=client,
        load_id="UNLINKED",
        invoice_number="UNKNOWN",
        carrier=record.from_addr or "UNKNOWN",
        outcome=ReconciliationOutcome.NEEDS_REVIEW,
        state=run.state,
        severity=ReviewSeverity.WARNING,
        title="Review unlinked inbound freight email",
        summary="An inbound email arrived but Neyma could not link it to a known load.",
        reasons=[
            "inbound email could not be linked to a known load",
            f"subject: {record.subject or '(no subject)'}",
        ],
        fields=[
            ReviewField(label="sender", invoice_value=record.from_addr, expected_value=None, status="unlinked"),
            ReviewField(label="attachments", invoice_value=str(record.attachment_count), expected_value=None, status="review"),
        ],
        actions=[ReviewAction.EDIT],
        action_options=[
            ReviewActionOption(
                code=ReviewAction.EDIT,
                label="Open unlinked email",
                consequence="Review the preserved inbound email and assign it to the right load.",
            )
        ],
        source_documents={"preserved_email": record.preserved_path},
        evidence_links=evidence,
        packet_detail_url=f"{client.packet_base_url}/{run.id}",
        routing=routing,
        aging=AgingMetadata(
            age_hours=age_hours,
            is_overdue=age_hours >= 48,
            next_escalation="daily digest" if age_hours < 48 else "reping owner/operator",
        ),
        found_money=FoundMoney(),
        audit_context={
            "requires_human": True,
            "no_autonomous_tms_write": True,
            "workflow_state": run.state.value,
            "mailbox_unlinked": True,
            "message_id": record.message_id,
            "thread_key": record.thread_key,
            "attachment_names": record.attachment_names,
            "dogfood_company": client.company_name,
            "operator_role": client.operator_role,
        },
    )


def _apply_packet_review_flags(
    result: ReconciliationResult,
    packet_run: MailboxPacketRun,
) -> ReconciliationResult:
    packet = packet_run.packet
    if not packet.needs_human:
        return result

    packet_reasons: list[str] = []
    for missing in packet.missing_required:
        packet_reasons.append(f"mailbox packet missing required {missing}")
    if packet.extraneous_attachments:
        packet_reasons.append(f"mailbox packet has {packet.extraneous_attachments} extraneous attachment(s)")
    for flag in packet.flags:
        if flag not in {"missing_required", "extraneous_attachment"}:
            packet_reasons.append(f"mailbox packet flag: {flag}")
    if not packet_reasons:
        packet_reasons.append("mailbox packet needs human review")

    if result.needs_human_review:
        return result.model_copy(update={"reasons": result.reasons + packet_reasons})

    return ReconciliationResult(
        load_id=result.load_id,
        invoice_number=result.invoice_number,
        carrier=result.carrier,
        outcome=ReconciliationOutcome.NEEDS_REVIEW,
        reasons=packet_reasons,
        variance_amount=Decimal("0.00"),
        needs_human_review=True,
    )


def _seen_invoice_keys_from_store(
    store: WorkflowStore,
    *,
    exclude_run_id: int | None = None,
) -> set[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    for run in store.list_runs():
        if exclude_run_id is not None and run.id == exclude_run_id:
            continue
        if run.carrier and run.invoice_number:
            seen.add((run.carrier.strip().lower(), run.invoice_number.strip().lower()))
    return seen
