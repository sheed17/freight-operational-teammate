"""Tests for mailbox intake feeding workflow, review, and signed delivery artifacts."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from decimal import Decimal
from email.message import EmailMessage
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from generate_realistic_corpus import generate  # noqa: E402
from freight_recon.delivery import DeliverySigner  # noqa: E402
from freight_recon.email_corpus import build_email_corpus  # noqa: E402
from freight_recon.mailbox_workflow import run_mailbox_workflow  # noqa: E402
from freight_recon.reconciliation import FreightLoadForReconciliation  # noqa: E402
from freight_recon.review import ReviewAction  # noqa: E402
from freight_recon.review_actions import ReviewActionRequest, ReviewDecision, apply_review_action  # noqa: E402
from freight_recon.workflow import WorkflowState, WorkflowStore  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def _c(value, confidence=0.99):
    return SimpleNamespace(value=value, confidence=confidence)


def _fake_obj(load, *, linehaul=None, fuel=None, load_or_pro=None, linehaul_conf=0.99, total=None):
    linehaul_value = load.rate_linehaul if linehaul is None else linehaul
    fuel_value = load.rate_fuel if fuel is None else fuel
    consistent_total = Decimal(str(linehaul_value)) + Decimal(str(fuel_value))
    return SimpleNamespace(
        invoice_number=_c(load.invoice_number),
        carrier_name=_c(load.carrier),
        load_or_pro=_c(load_or_pro if load_or_pro is not None else load.load_id),
        linehaul_amount=_c(linehaul_value, linehaul_conf),
        fuel_surcharge=_c(fuel_value),
        total_amount=_c(consistent_total if total is None else total),
        invoice_date=_c("2026-05-05"),
        accessorials=[],
    )


def _extractor_for(obj, calls=None, *, model="gpt-4o", error=None):
    def extractor(path):
        if calls is not None:
            calls.append(Path(path))
        return SimpleNamespace(extraction=obj, model=model, error=error)

    return extractor


def _email_corpus(tmp_path, count=12):
    corpus = tmp_path / "corpus"
    generate(corpus, count, seed=42)
    raw = json.loads((corpus / "ground_truth" / "loads_and_scenarios.json").read_text())
    loads = [FreightLoadForReconciliation.from_mapping(item) for item in raw.values()]
    email_out = tmp_path / "email_packets"
    result = build_email_corpus(loads, corpus_dir=corpus, output_dir=email_out, seed=42)
    return corpus, loads, result


def _copy_packet_emails(packet, inbox: Path) -> None:
    inbox.mkdir(parents=True, exist_ok=True)
    for email in packet.emails:
        source = Path(email.eml_path)
        shutil.copy2(source, inbox / source.name)


def _exception_packet(loads, email_corpus):
    by_id = {load.load_id: load for load in loads}
    return next(
        packet
        for packet in email_corpus.packets
        if packet.emails and by_id[packet.load_id].expected_outcome != "MATCHED"
    )


def test_mailbox_workflow_creates_review_and_signed_delivery_for_exception(tmp_path):
    _, loads, email_corpus = _email_corpus(tmp_path)
    packet = _exception_packet(loads, email_corpus)
    load = next(load for load in loads if load.load_id == packet.load_id)
    assert load.expected_outcome != "MATCHED"
    inbox = tmp_path / "inbox"
    _copy_packet_emails(packet, inbox)

    result = run_mailbox_workflow(
        inbox_dir=inbox,
        preserve_dir=tmp_path / "mailbox",
        mailbox_state_path=tmp_path / "mailbox" / "mailbox_state.json",
        workflow_db_path=tmp_path / "workflow.sqlite3",
        loads=loads,
        signer=DeliverySigner(b"test-secret"),
        age_hours=48,
    )

    assert len(result.mailbox.new_messages) == len(packet.emails)
    assert result.workflow_runs == 1
    assert result.reviews_created == 1
    assert result.deliveries_created == 1
    workflow_result = result.packet_results[0]
    assert workflow_result.workflow_state == WorkflowState.NEEDS_REVIEW
    message = result.delivery_messages[0]
    assert message.actions
    assert all(action.signed_token.startswith("redacted:") for action in message.actions)
    assert all(link.path.startswith("mailbox://") for link in message.evidence_links)
    assert any("Received" in link.label for link in message.evidence_links)
    assert result.review_payloads[0].audit_context["mailbox_delivered_doc_types"]

    store = WorkflowStore(tmp_path / "workflow.sqlite3")
    try:
        events = [event["event_type"] for event in store.audit_events(workflow_result.workflow_run_id)]
    finally:
        store.close()
    assert "document_received" in events
    assert "review_payload_created" in events
    assert "delivery_message_created" in events


def test_mailbox_workflow_real_extraction_uses_preserved_carrier_invoice_attachment(tmp_path):
    _, loads, email_corpus = _email_corpus(tmp_path)
    packet = next(p for p in email_corpus.packets if p.scenario == "single_email_complete")
    load = next(load for load in loads if load.load_id == packet.load_id)
    billed_linehaul = load.rate_linehaul + 500
    calls: list[Path] = []
    inbox = tmp_path / "inbox"
    _copy_packet_emails(packet, inbox)

    result = run_mailbox_workflow(
        inbox_dir=inbox,
        preserve_dir=tmp_path / "mailbox",
        mailbox_state_path=tmp_path / "mailbox" / "mailbox_state.json",
        workflow_db_path=tmp_path / "workflow.sqlite3",
        loads=loads,
        signer=DeliverySigner(b"test-secret"),
        extractor=_extractor_for(_fake_obj(load, linehaul=billed_linehaul), calls),
    )

    assert calls and calls[0].exists()
    assert calls[0].parent.name == "extracted_attachments"
    workflow_result = next(item for item in result.packet_results if item.load_id == packet.load_id)
    assert workflow_result.workflow_state == WorkflowState.NEEDS_REVIEW
    payload = next(item for item in result.review_payloads if item.load_id == packet.load_id)
    linehaul = next(field for field in payload.fields if field.label == "linehaul")
    assert linehaul.invoice_value == f"{billed_linehaul:.2f}"
    store = WorkflowStore(tmp_path / "workflow.sqlite3")
    try:
        extracted = next(
            event for event in store.audit_events(workflow_result.workflow_run_id)
            if event["event_type"] == "extraction_recorded"
        )
    finally:
        store.close()
    assert extracted["payload"]["source"] == "vision_extraction"
    assert extracted["payload"]["extracted_invoice"]["invoice_linehaul"] == str(billed_linehaul)


def test_mailbox_workflow_real_extraction_low_confidence_forces_review(tmp_path):
    _, loads, email_corpus = _email_corpus(tmp_path)
    packet = next(p for p in email_corpus.packets if p.scenario == "single_email_complete")
    load = next(load for load in loads if load.load_id == packet.load_id)
    inbox = tmp_path / "inbox"
    _copy_packet_emails(packet, inbox)

    result = run_mailbox_workflow(
        inbox_dir=inbox,
        preserve_dir=tmp_path / "mailbox",
        mailbox_state_path=tmp_path / "mailbox" / "mailbox_state.json",
        workflow_db_path=tmp_path / "workflow.sqlite3",
        loads=loads,
        signer=DeliverySigner(b"test-secret"),
        extractor=_extractor_for(_fake_obj(load, linehaul_conf=0.4)),
    )

    workflow_result = next(item for item in result.packet_results if item.load_id == packet.load_id)
    assert workflow_result.workflow_state == WorkflowState.NEEDS_REVIEW
    store = WorkflowStore(tmp_path / "workflow.sqlite3")
    try:
        run = store.get_run(workflow_result.workflow_run_id)
    finally:
        store.close()
    assert run is not None
    assert "low-confidence extraction" in (run.reason or "")


def test_mailbox_workflow_real_extraction_total_mismatch_forces_review(tmp_path):
    _, loads, email_corpus = _email_corpus(tmp_path)
    packet = next(p for p in email_corpus.packets if p.scenario == "single_email_complete")
    load = next(load for load in loads if load.load_id == packet.load_id)
    inbox = tmp_path / "inbox"
    _copy_packet_emails(packet, inbox)

    result = run_mailbox_workflow(
        inbox_dir=inbox,
        preserve_dir=tmp_path / "mailbox",
        mailbox_state_path=tmp_path / "mailbox" / "mailbox_state.json",
        workflow_db_path=tmp_path / "workflow.sqlite3",
        loads=loads,
        signer=DeliverySigner(b"test-secret"),
        extractor=_extractor_for(_fake_obj(load, total=load.rate_linehaul + load.rate_fuel + 125)),
    )

    workflow_result = next(item for item in result.packet_results if item.load_id == packet.load_id)
    assert workflow_result.workflow_state == WorkflowState.NEEDS_REVIEW
    store = WorkflowStore(tmp_path / "workflow.sqlite3")
    try:
        run = store.get_run(workflow_result.workflow_run_id)
    finally:
        store.close()
    assert run is not None
    assert "does not equal its line items" in (run.reason or "")


def test_mailbox_workflow_real_extraction_exception_routes_to_review_not_crash(tmp_path):
    _, loads, email_corpus = _email_corpus(tmp_path)
    packet = next(p for p in email_corpus.packets if p.scenario == "single_email_complete")
    inbox = tmp_path / "inbox"
    _copy_packet_emails(packet, inbox)

    def raises(_path):
        raise RuntimeError("render failed")

    result = run_mailbox_workflow(
        inbox_dir=inbox,
        preserve_dir=tmp_path / "mailbox",
        mailbox_state_path=tmp_path / "mailbox" / "mailbox_state.json",
        workflow_db_path=tmp_path / "workflow.sqlite3",
        loads=loads,
        signer=DeliverySigner(b"test-secret"),
        extractor=raises,
    )

    workflow_result = next(item for item in result.packet_results if item.load_id == packet.load_id)
    assert workflow_result.workflow_state == WorkflowState.NEEDS_REVIEW
    store = WorkflowStore(tmp_path / "workflow.sqlite3")
    try:
        run = store.get_run(workflow_result.workflow_run_id)
    finally:
        store.close()
    assert run is not None
    assert "render failed" in (run.reason or "")


def test_mailbox_workflow_multiple_carrier_invoices_force_review_without_extracting(tmp_path):
    corpus, loads, _ = _email_corpus(tmp_path)
    load = loads[0]
    invoice_pdf = corpus / load.documents["carrier_invoice"]
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    message = EmailMessage()
    message["Message-ID"] = "<multi-invoice@example.test>"
    message["From"] = "billing@carrier.test"
    message["To"] = "billing@neyma-test-freight.test"
    message["Subject"] = f"Invoices for {load.load_id} {load.invoice_number}"
    message.set_content("Please process these invoices.")
    payload = invoice_pdf.read_bytes()
    message.add_attachment(
        payload,
        maintype="application",
        subtype="pdf",
        filename=f"{load.load_id}_{load.invoice_number}_carrier_invoice_a.pdf",
    )
    message.add_attachment(
        payload,
        maintype="application",
        subtype="pdf",
        filename=f"{load.load_id}_{load.invoice_number}_carrier_invoice_b.pdf",
    )
    (inbox / "multi_invoice.eml").write_bytes(message.as_bytes())
    calls: list[Path] = []

    result = run_mailbox_workflow(
        inbox_dir=inbox,
        preserve_dir=tmp_path / "mailbox",
        mailbox_state_path=tmp_path / "mailbox" / "mailbox_state.json",
        workflow_db_path=tmp_path / "workflow.sqlite3",
        loads=loads,
        signer=DeliverySigner(b"test-secret"),
        extractor=_extractor_for(_fake_obj(load), calls),
    )

    workflow_result = next(item for item in result.packet_results if item.load_id == load.load_id)
    assert calls == []
    assert workflow_result.workflow_state == WorkflowState.NEEDS_REVIEW
    store = WorkflowStore(tmp_path / "workflow.sqlite3")
    try:
        run = store.get_run(workflow_result.workflow_run_id)
    finally:
        store.close()
    assert run is not None
    assert "multiple linked carrier invoice attachments" in (run.reason or "")


def test_mailbox_workflow_surfaces_unlinked_inbound_email_for_review(tmp_path):
    _, loads, _ = _email_corpus(tmp_path)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    message = EmailMessage()
    message["Message-ID"] = "<unlinked@example.test>"
    message["From"] = "billing@unknown-carrier.test"
    message["To"] = "billing@neyma-test-freight.test"
    message["Subject"] = "Invoice docs attached"
    message.set_content("Please process these docs.")
    message.add_attachment(
        b"not a real pdf but enough for mailbox metadata",
        maintype="application",
        subtype="pdf",
        filename="invoice.pdf",
    )
    (inbox / "unlinked.eml").write_bytes(message.as_bytes())

    result = run_mailbox_workflow(
        inbox_dir=inbox,
        preserve_dir=tmp_path / "mailbox",
        mailbox_state_path=tmp_path / "mailbox" / "mailbox_state.json",
        workflow_db_path=tmp_path / "workflow.sqlite3",
        loads=loads,
        signer=DeliverySigner(b"test-secret"),
    )

    assert len(result.mailbox.unlinked_messages) == 1
    assert result.workflow_runs == 1
    assert result.reviews_created == 1
    workflow_result = result.packet_results[0]
    assert workflow_result.load_id == "UNLINKED"
    assert workflow_result.workflow_state == WorkflowState.NEEDS_REVIEW
    assert workflow_result.outcome == "NEEDS_REVIEW"
    payload = result.review_payloads[0]
    assert payload.title == "Review unlinked inbound freight email"
    assert payload.audit_context["mailbox_unlinked"] is True
    assert any(link.document_type == "email" for link in payload.evidence_links)
    assert result.delivery_messages[0].actions[0].signed_token.startswith("redacted:")


def test_mailbox_workflow_is_idempotent_on_repeat_poll(tmp_path):
    _, loads, email_corpus = _email_corpus(tmp_path)
    packet = _exception_packet(loads, email_corpus)
    inbox = tmp_path / "inbox"
    _copy_packet_emails(packet, inbox)
    kwargs = {
        "inbox_dir": inbox,
        "preserve_dir": tmp_path / "mailbox",
        "mailbox_state_path": tmp_path / "mailbox" / "mailbox_state.json",
        "workflow_db_path": tmp_path / "workflow.sqlite3",
        "loads": loads,
        "signer": DeliverySigner(b"test-secret"),
    }

    first = run_mailbox_workflow(**kwargs)
    second = run_mailbox_workflow(**kwargs)

    assert len(first.mailbox.new_messages) == len(packet.emails)
    assert len(second.mailbox.new_messages) == 0
    assert len(second.mailbox.duplicates) == len(packet.emails)
    assert first.packet_results[0].workflow_run_id == second.packet_results[0].workflow_run_id

    store = WorkflowStore(tmp_path / "workflow.sqlite3")
    try:
        runs = store.list_runs()
        run_id = first.packet_results[0].workflow_run_id
        review_events = [
            event for event in store.audit_events(run_id)
            if event["event_type"] == "review_payload_created"
        ]
        delivery_events = [
            event for event in store.audit_events(run_id)
            if event["event_type"] == "delivery_message_created"
        ]
    finally:
        store.close()
    assert len(runs) == 1
    assert len(review_events) == 1
    assert len(delivery_events) == 1


def test_mailbox_workflow_packet_flags_force_human_review_for_math_clean_packet(tmp_path):
    _, loads, email_corpus = _email_corpus(tmp_path)
    packet = next(p for p in email_corpus.packets if p.scenario == "trickle_pod_later" and len(p.emails) >= 2)
    load = next(load for load in loads if load.load_id == packet.load_id)
    assert load.expected_outcome == "MATCHED"
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    first_email = Path(packet.emails[0].eml_path)
    shutil.copy2(first_email, inbox / first_email.name)

    result = run_mailbox_workflow(
        inbox_dir=inbox,
        preserve_dir=tmp_path / "mailbox",
        mailbox_state_path=tmp_path / "mailbox" / "mailbox_state.json",
        workflow_db_path=tmp_path / "workflow.sqlite3",
        loads=loads,
        signer=DeliverySigner(b"test-secret"),
    )

    workflow_result = result.packet_results[0]
    assert workflow_result.packet_needs_human is True
    assert "pod" in workflow_result.missing_required
    assert workflow_result.workflow_state == WorkflowState.NEEDS_REVIEW
    assert workflow_result.outcome == "NEEDS_REVIEW"
    assert result.reviews_created == 1
    assert "missing required pod" in result.review_payloads[0].summary.lower() or any(
        "missing required pod" in reason for reason in result.review_payloads[0].reasons
    )
    payload = result.review_payloads[0]
    assert ReviewAction.APPROVE not in payload.actions
    assert all(option.code != ReviewAction.APPROVE for option in payload.action_options)
    assert any(option.code == ReviewAction.REQUEST_BACKUP for option in payload.action_options)


def test_mailbox_workflow_trickle_email_refreshes_same_run_when_packet_resolves(tmp_path):
    _, loads, email_corpus = _email_corpus(tmp_path)
    packet = next(p for p in email_corpus.packets if p.scenario == "trickle_pod_later" and len(p.emails) >= 2)
    load = next(load for load in loads if load.load_id == packet.load_id)
    assert load.expected_outcome == "MATCHED"
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    first_email = Path(packet.emails[0].eml_path)
    shutil.copy2(first_email, inbox / first_email.name)
    kwargs = {
        "inbox_dir": inbox,
        "preserve_dir": tmp_path / "mailbox",
        "mailbox_state_path": tmp_path / "mailbox" / "mailbox_state.json",
        "workflow_db_path": tmp_path / "workflow.sqlite3",
        "loads": loads,
        "signer": DeliverySigner(b"test-secret"),
    }

    first = run_mailbox_workflow(**kwargs)
    first_run_id = first.packet_results[0].workflow_run_id
    assert first.packet_results[0].workflow_state == WorkflowState.NEEDS_REVIEW

    second_email = Path(packet.emails[1].eml_path)
    shutil.copy2(second_email, inbox / second_email.name)
    second = run_mailbox_workflow(**kwargs)

    assert second.packet_results[0].workflow_run_id == first_run_id
    assert second.packet_results[0].workflow_state == WorkflowState.DONE
    assert second.packet_results[0].outcome == "MATCHED"
    assert second.reviews_created == 0
    store = WorkflowStore(tmp_path / "workflow.sqlite3")
    try:
        assert len(store.list_runs()) == 1
        events = [event["event_type"] for event in store.audit_events(first_run_id)]
    finally:
        store.close()
    assert "mailbox_packet_refreshed" in events
    assert "reconciliation_refreshed" in events
    assert "route_after_reconciliation_refresh" in events


def test_mailbox_workflow_real_extraction_trickle_refreshes_same_run_when_packet_resolves(tmp_path):
    _, loads, email_corpus = _email_corpus(tmp_path)
    packet = next(p for p in email_corpus.packets if p.scenario == "trickle_pod_later" and len(p.emails) >= 2)
    load = next(load for load in loads if load.load_id == packet.load_id)
    assert load.expected_outcome == "MATCHED"
    calls: list[Path] = []
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    first_email = Path(packet.emails[0].eml_path)
    shutil.copy2(first_email, inbox / first_email.name)
    kwargs = {
        "inbox_dir": inbox,
        "preserve_dir": tmp_path / "mailbox",
        "mailbox_state_path": tmp_path / "mailbox" / "mailbox_state.json",
        "workflow_db_path": tmp_path / "workflow.sqlite3",
        "loads": loads,
        "signer": DeliverySigner(b"test-secret"),
        "extractor": _extractor_for(_fake_obj(load), calls),
    }

    first = run_mailbox_workflow(**kwargs)
    first_run_id = first.packet_results[0].workflow_run_id
    assert first.packet_results[0].workflow_state == WorkflowState.NEEDS_REVIEW
    assert first.packet_results[0].outcome == "NEEDS_REVIEW"

    second_email = Path(packet.emails[1].eml_path)
    shutil.copy2(second_email, inbox / second_email.name)
    second = run_mailbox_workflow(**kwargs)

    assert second.packet_results[0].workflow_run_id == first_run_id
    assert second.packet_results[0].workflow_state == WorkflowState.DONE
    assert second.packet_results[0].outcome == "MATCHED"
    assert len(calls) >= 2
    store = WorkflowStore(tmp_path / "workflow.sqlite3")
    try:
        events = [event["event_type"] for event in store.audit_events(first_run_id)]
    finally:
        store.close()
    assert "mailbox_packet_refreshed" in events
    assert "extraction_recorded" in events
    assert "reconciliation_refreshed" in events


def test_mailbox_workflow_requested_backup_consumes_arriving_backup(tmp_path):
    _, loads, email_corpus = _email_corpus(tmp_path)
    packet = next(p for p in email_corpus.packets if p.scenario == "trickle_pod_later" and len(p.emails) >= 2)
    load = next(load for load in loads if load.load_id == packet.load_id)
    assert load.expected_outcome == "MATCHED"
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    first_email = Path(packet.emails[0].eml_path)
    shutil.copy2(first_email, inbox / first_email.name)
    kwargs = {
        "inbox_dir": inbox,
        "preserve_dir": tmp_path / "mailbox",
        "mailbox_state_path": tmp_path / "mailbox" / "mailbox_state.json",
        "workflow_db_path": tmp_path / "workflow.sqlite3",
        "loads": loads,
        "signer": DeliverySigner(b"test-secret"),
    }

    first = run_mailbox_workflow(**kwargs)
    run_id = first.packet_results[0].workflow_run_id
    store = WorkflowStore(tmp_path / "workflow.sqlite3")
    try:
        action = apply_review_action(
            store,
            ReviewActionRequest(run_id=run_id, decision=ReviewDecision.REQUEST_BACKUP),
        )
        assert action.to_state == WorkflowState.REQUESTED_BACKUP
    finally:
        store.close()

    second_email = Path(packet.emails[1].eml_path)
    shutil.copy2(second_email, inbox / second_email.name)
    second = run_mailbox_workflow(**kwargs)

    assert second.packet_results[0].workflow_run_id == run_id
    assert second.packet_results[0].workflow_state == WorkflowState.DONE
    assert second.packet_results[0].outcome == "MATCHED"
    store = WorkflowStore(tmp_path / "workflow.sqlite3")
    try:
        events = [event["event_type"] for event in store.audit_events(run_id)]
    finally:
        store.close()
    assert "review_backup_requested" in events
    assert "reconciliation_refreshed" in events
    assert "route_after_reconciliation_refresh" in events


def test_mailbox_workflow_duplicate_outcome_survives_repeat_poll(tmp_path):
    _, loads, email_corpus = _email_corpus(tmp_path)
    duplicate_load = next(load for load in loads if load.expected_outcome == "DUPLICATE")
    original_load = next(
        load
        for load in loads
        if load.load_id != duplicate_load.load_id
        and load.carrier == duplicate_load.carrier
        and load.invoice_number == duplicate_load.invoice_number
    )
    by_packet = {packet.load_id: packet for packet in email_corpus.packets if packet.emails}
    inbox = tmp_path / "inbox"
    _copy_packet_emails(by_packet[original_load.load_id], inbox)
    _copy_packet_emails(by_packet[duplicate_load.load_id], inbox)
    kwargs = {
        "inbox_dir": inbox,
        "preserve_dir": tmp_path / "mailbox",
        "mailbox_state_path": tmp_path / "mailbox" / "mailbox_state.json",
        "workflow_db_path": tmp_path / "workflow.sqlite3",
        "loads": loads,
        "signer": DeliverySigner(b"test-secret"),
    }

    first = run_mailbox_workflow(**kwargs)
    second = run_mailbox_workflow(**kwargs)

    first_duplicate = next(item for item in first.packet_results if item.load_id == duplicate_load.load_id)
    second_duplicate = next(item for item in second.packet_results if item.load_id == duplicate_load.load_id)
    assert first_duplicate.workflow_run_id == second_duplicate.workflow_run_id
    assert first_duplicate.workflow_state == WorkflowState.NEEDS_REVIEW
    assert first_duplicate.outcome == "DUPLICATE"
    assert second_duplicate.workflow_state == WorkflowState.NEEDS_REVIEW
    assert second_duplicate.outcome == "DUPLICATE"


def test_mailbox_workflow_cli_smoke(tmp_path):
    corpus, loads, email_corpus = _email_corpus(tmp_path, count=12)
    packet = _exception_packet(loads, email_corpus)
    inbox = tmp_path / "inbox"
    _copy_packet_emails(packet, inbox)

    result = subprocess.run(
        [
            str(ROOT / ".venv" / "bin" / "python"),
            str(ROOT / "scripts" / "run_mailbox_workflow.py"),
            "--corpus",
            str(corpus),
            "--inbox",
            str(inbox),
            "--preserve-dir",
            str(tmp_path / "mailbox"),
            "--mailbox-state",
            str(tmp_path / "mailbox" / "mailbox_state.json"),
            "--db",
            str(tmp_path / "workflow.sqlite3"),
            "--out",
            str(tmp_path / "mailbox" / "workflow_report.json"),
            "--text",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Mailbox Workflow" in result.stdout
    assert "Delivery messages: 1" in result.stdout
    assert (tmp_path / "mailbox" / "workflow_report.json").exists()
