"""Tests for Stage 2 inbound email ingestion (parse → classify → link → assemble)."""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from generate_realistic_corpus import generate  # noqa: E402
from freight_recon.email_corpus import build_email_corpus  # noqa: E402
from freight_recon.ingestion import (  # noqa: E402
    LoadIndex,
    ParsedAttachment,
    ParsedEmail,
    classify_attachment,
    ingest_emails,
    ingest_eml_paths,
    link_attachment,
    parse_eml,
)
from freight_recon.reconciliation import FreightLoadForReconciliation  # noqa: E402


def _corpus(tmp_path, count=12):
    corpus = tmp_path / "corpus"
    generate(corpus, count, seed=42)
    raw = json.loads((corpus / "ground_truth" / "loads_and_scenarios.json").read_text())
    loads = [FreightLoadForReconciliation.from_mapping(item) for item in raw.values()]
    email_out = tmp_path / "email_packets"
    result = build_email_corpus(loads, corpus_dir=corpus, output_dir=email_out, seed=42)
    return loads, result


def test_classify_attachment_recognizes_core_doc_types():
    assert classify_attachment("001_LD-560001_carrier_invoice.pdf").doc_type == "carrier_invoice"
    assert classify_attachment("001_LD-560001_rate_confirmation.pdf").doc_type == "rate_confirmation"
    assert classify_attachment("001_LD-560001_pod.pdf").doc_type == "pod"
    assert classify_attachment("001_LD-560001_bol.pdf").doc_type == "bol"
    unknown = classify_attachment("scan_0007.pdf")
    assert unknown.doc_type == "unknown"
    assert unknown.confidence < 0.5


def test_link_attachment_links_to_known_load(tmp_path):
    loads, _ = _corpus(tmp_path, count=8)
    index = LoadIndex(loads)
    load_id, conf, _ = link_attachment("001_LD-560003_carrier_invoice.pdf", "", index)
    assert load_id == "LD-560003"
    assert conf >= 0.9
    # An identifier that matches no known load does not link.
    none_id, none_conf, _ = link_attachment("random_LD-999999.pdf", "", index)
    assert none_id is None and none_conf == 0.0


def test_link_attachment_links_via_bol_number(tmp_path):
    loads, _ = _corpus(tmp_path, count=8)
    load = next(l for l in loads if l.bol_number)
    index = LoadIndex(loads)
    # A document whose only identifier is the BOL number must still link.
    load_id, conf, reason = link_attachment(f"signed_{load.bol_number}.pdf", "", index)
    assert load_id == load.load_id
    assert "BOL" in reason and conf >= 0.85


def test_generic_filename_under_packet_subject_is_not_attributed(tmp_path):
    """The contamination path: a generic-named foreign doc under a packet-load subject must NOT
    be treated as belonging just because the subject names the load."""
    loads, _ = _corpus(tmp_path, count=8)
    load = loads[0]
    emails = [
        ParsedEmail(
            subject=f"Invoice {load.invoice_number} / Load {load.load_id}",
            attachments=[
                ParsedAttachment(
                    filename=f"001_{load.load_id}_carrier_invoice.pdf",
                    content_type="application/pdf",
                    sha256="a" * 64,
                    size_bytes=100,
                ),
                ParsedAttachment(
                    filename="scan_0007.pdf",  # no identifier of its own
                    content_type="application/pdf",
                    sha256="b" * 64,
                    size_bytes=100,
                ),
            ],
        )
    ]
    ingested = ingest_emails(emails, loads)

    assert ingested.packet_load_id == load.load_id  # anchored by the real invoice's filename
    generic = next(a for a in ingested.attachments if a.filename == "scan_0007.pdf")
    assert generic.belongs_to_packet is False
    assert "linked_by_subject_only" in generic.flags
    assert ingested.needs_human is True


def test_parse_eml_extracts_pdf_attachments(tmp_path):
    _, result = _corpus(tmp_path, count=8)
    packet = next(p for p in result.packets if p.emails and p.emails[0].attachments)
    parsed = parse_eml(packet.emails[0].eml_path)
    assert parsed.attachments
    assert all(a.sha256 and a.size_bytes > 0 for a in parsed.attachments)
    assert parsed.date_header
    assert parsed.email_timestamp
    assert parsed.thread_key == parsed.message_id


def test_parse_eml_preserves_reply_thread_metadata():
    raw = "\n".join(
        [
            "Message-ID: <reply-2@carrier.test>",
            "From: carrier@example.test",
            "To: billing@neyma.test",
            "Subject: Re: Invoice INV-2026001 / Load LD-560001",
            "Date: Tue, 16 Jun 2026 14:05:00 -0500",
            "In-Reply-To: <root-1@carrier.test>",
            "References: <root-1@carrier.test> <middle-1@carrier.test>",
            "MIME-Version: 1.0",
            "Content-Type: text/plain; charset=utf-8",
            "",
            "POD attached.",
        ]
    )
    parsed = parse_eml(raw)

    assert parsed.email_timestamp == "2026-06-16T14:05:00-05:00"
    assert parsed.in_reply_to == "<root-1@carrier.test>"
    assert parsed.references == ["<root-1@carrier.test>", "<middle-1@carrier.test>"]
    assert parsed.thread_key == "<root-1@carrier.test>"


def test_complete_packet_links_and_has_no_missing(tmp_path):
    loads, result = _corpus(tmp_path, count=12)
    complete = next(p for p in result.packets if p.scenario == "single_email_complete")
    ingested = ingest_eml_paths([e.eml_path for e in complete.emails], loads)

    assert ingested.packet_load_id == complete.load_id
    assert ingested.missing_required == []
    assert ingested.extraneous_attachments == 0
    assert ingested.needs_human is False


def test_missing_pod_packet_flags_missing_and_needs_human(tmp_path):
    loads, result = _corpus(tmp_path, count=12)
    missing = next(p for p in result.packets if p.scenario == "missing_pod")
    ingested = ingest_eml_paths([e.eml_path for e in missing.emails], loads)

    assert "pod" in ingested.missing_required
    assert "missing_documents" in ingested.flags
    assert ingested.needs_human is True


def test_noise_attachment_does_not_belong_to_packet(tmp_path):
    loads, result = _corpus(tmp_path, count=12)
    noisy = next(p for p in result.packets if p.has_noise)
    ingested = ingest_eml_paths([e.eml_path for e in noisy.emails], loads)

    not_belonging = [a for a in ingested.attachments if not a.belongs_to_packet]
    assert not_belonging, "expected at least one rejected attachment"
    assert ingested.extraneous_attachments >= 1
    assert "extraneous_attachment" in ingested.flags
    assert ingested.needs_human is True


def test_ingestion_links_every_packet_and_rejects_all_noise(tmp_path):
    """End-to-end: across the whole corpus, packets link correctly and noise is always rejected."""
    loads, result = _corpus(tmp_path, count=12)
    link_ok = 0
    noise_total = noise_rejected = 0
    for packet in result.packets:
        ingested = ingest_eml_paths([e.eml_path for e in packet.emails], loads)
        link_ok += int(ingested.packet_load_id == packet.load_id)
        truth_by_name = {a.filename: a for e in packet.emails for a in e.attachments}
        for assessment in ingested.attachments:
            t = truth_by_name.get(assessment.filename)
            if t and t.is_noise:
                noise_total += 1
                noise_rejected += int(not assessment.belongs_to_packet)

    assert link_ok == len(result.packets)  # deterministic identifiers → every packet links
    assert noise_total >= 1
    assert noise_rejected == noise_total  # the linker rejects every noise attachment
