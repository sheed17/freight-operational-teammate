"""Tests for local packet detail page generation."""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from generate_realistic_corpus import generate  # noqa: E402
from freight_recon.packet_page import build_packet_site  # noqa: E402
from freight_recon.reconciliation import FreightLoadForReconciliation  # noqa: E402
from freight_recon.review import build_review_payload, record_review_payload  # noqa: E402
from freight_recon.workflow import WorkflowStore, process_load_packet  # noqa: E402


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
    assert (site / "evidence" / "LD-560003" / "carrier_invoice.pdf").exists()
    assert (site / "evidence" / "LD-560003" / "rate_confirmation.pdf").exists()
    assert (site / "index.html").exists()
    assert (site / "favicon.ico").exists()
    store.close()
