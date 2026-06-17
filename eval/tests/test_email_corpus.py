"""Tests for the synthetic inbound-email corpus (Stage 2 ingestion proving ground)."""

import email as email_lib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from generate_realistic_corpus import generate  # noqa: E402
from freight_recon.email_corpus import REQUIRED_DOC_TYPES, build_email_corpus  # noqa: E402
from freight_recon.reconciliation import FreightLoadForReconciliation  # noqa: E402


def _loads(tmp_path):
    corpus = tmp_path / "corpus"
    generate(corpus, 12, seed=42)
    raw = json.loads((corpus / "ground_truth" / "loads_and_scenarios.json").read_text())
    loads = [FreightLoadForReconciliation.from_mapping(item) for item in raw.values()]
    return corpus, loads


def test_email_corpus_emits_packet_per_load_with_hidden_truth(tmp_path):
    corpus, loads = _loads(tmp_path)
    out = tmp_path / "email_packets"

    result = build_email_corpus(loads, corpus_dir=corpus, output_dir=out, seed=42)

    assert len(result.packets) == len(loads)
    truth = json.loads((out / "ground_truth" / "email_packets.json").read_text())
    assert len(truth) == len(loads)
    for packet in result.packets:
        assert packet.required_doc_types == REQUIRED_DOC_TYPES
        for email_truth in packet.emails:
            assert Path(email_truth.eml_path).exists()


def test_missing_pod_scenario_flags_missing_document(tmp_path):
    corpus, loads = _loads(tmp_path)
    result = build_email_corpus(loads, corpus_dir=corpus, output_dir=tmp_path / "ep", seed=42)

    missing_pod = [p for p in result.packets if p.scenario == "missing_pod"]
    assert missing_pod, "expected at least one missing_pod packet"
    for packet in missing_pod:
        assert "pod" in packet.missing_doc_types
        delivered_types = {a.doc_type for e in packet.emails for a in e.attachments if not a.is_noise}
        assert "pod" not in delivered_types


def test_noise_attachments_link_to_a_different_load(tmp_path):
    corpus, loads = _loads(tmp_path)
    result = build_email_corpus(loads, corpus_dir=corpus, output_dir=tmp_path / "ep", seed=42)

    noisy = [p for p in result.packets if p.has_noise]
    assert noisy, "expected at least one packet with noise"
    for packet in noisy:
        noise = [a for e in packet.emails for a in e.attachments if a.is_noise]
        assert noise
        for attachment in noise:
            # The whole point: a noise attachment's true linked load is NOT this packet's load.
            assert attachment.links_to_load != packet.load_id


def test_trickle_scenario_splits_across_multiple_emails(tmp_path):
    corpus, loads = _loads(tmp_path)
    result = build_email_corpus(loads, corpus_dir=corpus, output_dir=tmp_path / "ep", seed=42)

    trickle = [p for p in result.packets if p.scenario == "trickle_pod_later"]
    assert trickle, "expected a trickle packet"
    # At least one trickle packet that actually had a POD should arrive as two emails.
    assert any(len(p.emails) >= 2 for p in trickle if "pod" not in p.missing_doc_types)


def test_eml_files_are_valid_mime_with_pdf_attachments(tmp_path):
    corpus, loads = _loads(tmp_path)
    result = build_email_corpus(loads, corpus_dir=corpus, output_dir=tmp_path / "ep", seed=42)

    packet = next(p for p in result.packets if p.emails and p.emails[0].attachments)
    mime = email_lib.message_from_string(Path(packet.emails[0].eml_path).read_text())
    assert mime.is_multipart()
    pdf_parts = [part for part in mime.walk() if part.get_content_type() == "application/pdf"]
    assert pdf_parts, "expected at least one PDF attachment"
    assert any(part.get_filename() for part in pdf_parts)
