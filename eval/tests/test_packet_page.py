"""Tests for local packet detail page generation."""

import hashlib
import json
from email.message import EmailMessage
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from generate_realistic_corpus import generate  # noqa: E402
from freight_recon.packet_page import build_packet_site  # noqa: E402
from freight_recon.reconciliation import FreightLoadForReconciliation  # noqa: E402
from freight_recon.review import build_review_payload, record_review_payload  # noqa: E402
from freight_recon.review import (
    DogfoodClientProfile,
    EvidenceLink,
    FoundMoney,
    ReviewAction,
    ReviewActionOption,
    ReviewPayload,
    ReviewRoute,
    ReviewSeverity,
    RoutingDecision,
)  # noqa: E402
from freight_recon.reconciliation import ReconciliationOutcome, ReconciliationResult  # noqa: E402
from freight_recon.workflow import WorkflowState, WorkflowStore, process_load_packet  # noqa: E402


def _build_review_fixture(tmp_path, count=8):
    corpus = tmp_path / "corpus"
    generate(corpus, count, seed=42)
    raw = json.loads((corpus / "ground_truth" / "loads_and_scenarios.json").read_text())
    loads = [FreightLoadForReconciliation.from_mapping(item) for item in raw.values()]
    store = WorkflowStore(tmp_path / "workflow.sqlite3")
    seen: set[tuple[str, str]] = set()
    payloads = []
    for load in loads:
        run = process_load_packet(
            store,
            load,
            primary_document_path=corpus / load.documents["carrier_invoice"],
            seen_invoice_keys=seen,
        )
        payload = build_review_payload(run, load, age_hours=48)
        if payload:
            record_review_payload(store, payload)
            payloads.append(payload)
    return corpus, {load.load_id: load for load in loads}, store, payloads


def test_packet_page_renders_evidence_math_actions_and_audit(tmp_path):
    corpus, loads, store, payloads = _build_review_fixture(tmp_path)
    site = tmp_path / "site"

    pages = build_packet_site(
        output_dir=site,
        corpus_dir=corpus,
        store=store,
        loads=loads,
        payloads=payloads,
    )

    first = pages[0]
    html = first.path.read_text(encoding="utf-8")
    assert "Carrier Invoice" in html
    assert "Rate Confirmation" in html
    assert "Reconciliation Math" in html
    assert "Approve $3334.50 and dispute $300.00 detention" in html
    assert "review_payload_created" in html
    assert 'href="../../evidence/LD-560003/carrier_invoice.pdf"' in html
    assert 'href="/evidence/' not in html
    assert 'href="/packets/' not in html
    assert (site / "evidence" / "LD-560003" / "carrier_invoice.pdf").exists()
    assert (site / "evidence" / "LD-560003" / "rate_confirmation.pdf").exists()
    assert (site / "index.html").exists()
    assert (site / "favicon.ico").exists()
    store.close()


def test_packet_page_prefers_exact_mailbox_attachment_evidence(tmp_path):
    corpus, loads, store, payloads = _build_review_fixture(tmp_path)
    payload = payloads[0]
    attachment_bytes = b"%PDF-1.4\n% received mailbox invoice bytes\n"
    attachment_sha = hashlib.sha256(attachment_bytes).hexdigest()

    message = EmailMessage()
    message["From"] = "carrier@example.test"
    message["To"] = "ap@example.test"
    message["Subject"] = f"Invoice for {payload.load_id}"
    message.set_content("Attached.")
    message.add_attachment(
        attachment_bytes,
        maintype="application",
        subtype="pdf",
        filename="received invoice.pdf",
    )
    mailbox = tmp_path / "mailbox"
    messages = mailbox / "messages"
    messages.mkdir(parents=True)
    (messages / "received.eml").write_bytes(message.as_bytes())

    mailbox_payload = payload.model_copy(
        update={
            "evidence_links": [
                EvidenceLink(
                    label="Received carrier invoice: received invoice.pdf",
                    document_type="carrier_invoice",
                    path=f"mailbox://{attachment_sha}/received invoice.pdf",
                    url=f"http://localhost:8000/evidence/{payload.load_id}/mailbox/{attachment_sha[:12]}",
                    note="received from inbox",
                )
            ]
        }
    )
    site = tmp_path / "site"

    pages = build_packet_site(
        output_dir=site,
        corpus_dir=corpus,
        store=store,
        loads=loads,
        payloads=[mailbox_payload],
        mailbox_preserve_dir=mailbox,
    )

    received_pdf = (
        site
        / "evidence"
        / payload.load_id
        / "mailbox"
        / attachment_sha[:12]
        / "received_invoice.pdf"
    )
    html = pages[0].path.read_text(encoding="utf-8")
    assert received_pdf.read_bytes() == attachment_bytes
    assert f'iframe src="../../evidence/{payload.load_id}/mailbox/{attachment_sha[:12]}/received_invoice.pdf"' in html
    assert "Received in Mailbox" in html
    assert "Received: carrier invoice: received invoice.pdf" in html
    assert "received from inbox" in html
    store.close()


def test_packet_page_links_each_mailbox_evidence_item_by_exact_sha(tmp_path):
    corpus, loads, store, payloads = _build_review_fixture(tmp_path)
    payload = payloads[0]
    attachment_one = b"%PDF-1.4\n% first carrier invoice bytes\n"
    attachment_two = b"%PDF-1.4\n% second carrier invoice bytes\n"
    sha_one = hashlib.sha256(attachment_one).hexdigest()
    sha_two = hashlib.sha256(attachment_two).hexdigest()

    message = EmailMessage()
    message["From"] = "carrier@example.test"
    message["To"] = "ap@example.test"
    message["Subject"] = f"Corrected invoices for {payload.load_id}"
    message.set_content("Attached.")
    message.add_attachment(
        attachment_one,
        maintype="application",
        subtype="pdf",
        filename="invoice original.pdf",
    )
    message.add_attachment(
        attachment_two,
        maintype="application",
        subtype="pdf",
        filename="invoice corrected.pdf",
    )
    mailbox = tmp_path / "mailbox"
    messages = mailbox / "messages"
    messages.mkdir(parents=True)
    (messages / "received.eml").write_bytes(message.as_bytes())

    mailbox_payload = payload.model_copy(
        update={
            "evidence_links": [
                EvidenceLink(
                    label="Received carrier invoice: invoice original.pdf",
                    document_type="carrier_invoice",
                    path=f"mailbox://{sha_one}/invoice original.pdf",
                    url=f"http://localhost:8000/evidence/{payload.load_id}/mailbox/{sha_one[:12]}",
                    note="first invoice",
                ),
                EvidenceLink(
                    label="Received carrier invoice: invoice corrected.pdf",
                    document_type="carrier_invoice",
                    path=f"mailbox://{sha_two}/invoice corrected.pdf",
                    url=f"http://localhost:8000/evidence/{payload.load_id}/mailbox/{sha_two[:12]}",
                    note="corrected invoice",
                ),
            ]
        }
    )

    pages = build_packet_site(
        output_dir=tmp_path / "site",
        corpus_dir=corpus,
        store=store,
        loads=loads,
        payloads=[mailbox_payload],
        mailbox_preserve_dir=mailbox,
    )

    html = pages[0].path.read_text(encoding="utf-8")
    assert f'mailbox/{sha_one[:12]}/invoice_original.pdf' in html
    assert f'mailbox/{sha_two[:12]}/invoice_corrected.pdf' in html
    assert "first invoice" in html
    assert "corrected invoice" in html
    store.close()


def test_packet_page_handles_unlinked_review_payload(tmp_path):
    corpus, loads, store, _ = _build_review_fixture(tmp_path)
    run = store.receive_document(
        "UNLINKED",
        "mailbox_unlinked:test",
        payload={"source": "test", "reason": "unlinked"},
    )
    run = store.mark_extracted(run.id, {"source": "test", "carrier": "billing@carrier.test"})
    run = store.mark_reconciled(
        run.id,
        ReconciliationResult(
            load_id="UNLINKED",
            invoice_number="UNKNOWN",
            carrier="billing@carrier.test",
            outcome=ReconciliationOutcome.NEEDS_REVIEW,
            reasons=["inbound email could not be linked to a known load"],
            needs_human_review=True,
        ),
    )
    payload = ReviewPayload(
        run_id=run.id,
        client=DogfoodClientProfile(),
        load_id="UNLINKED",
        invoice_number="UNKNOWN",
        carrier="billing@carrier.test",
        outcome=ReconciliationOutcome.NEEDS_REVIEW,
        state=WorkflowState.NEEDS_REVIEW,
        severity=ReviewSeverity.WARNING,
        title="Review unlinked inbound freight email",
        summary="An inbound email arrived but Neyma could not link it to a known load.",
        reasons=["inbound email could not be linked to a known load"],
        actions=[ReviewAction.EDIT],
        action_options=[
            ReviewActionOption(
                code=ReviewAction.EDIT,
                label="Open unlinked email",
                consequence="Review preserved inbound email.",
            )
        ],
        evidence_links=[
            EvidenceLink(
                label="Inbound email",
                document_type="email",
                path="mailbox://abc/message.eml",
                url="http://localhost/evidence/unlinked",
            )
        ],
        packet_detail_url="http://localhost/packets/1",
        routing=RoutingDecision(route=ReviewRoute.CHANNEL_POST, reason="unlinked"),
        found_money=FoundMoney(),
    )

    pages = build_packet_site(
        output_dir=tmp_path / "site",
        corpus_dir=corpus,
        store=store,
        loads=loads,
        payloads=[payload],
    )

    html = pages[0].path.read_text(encoding="utf-8")
    assert "Review unlinked inbound freight email" in html
    assert "Received Evidence" in html
    assert "Workflow State" in html
    store.close()
