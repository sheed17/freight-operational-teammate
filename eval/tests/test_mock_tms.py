"""Tests for the local mock TMS surface."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from generate_realistic_corpus import generate  # noqa: E402
from freight_recon.mock_tms import build_mock_tms_site  # noqa: E402
from freight_recon.workflow import WorkflowStore, process_load_packet  # noqa: E402
from run_workflow import load_synthetic_loads  # noqa: E402


def test_mock_tms_site_writes_source_of_truth_surface(tmp_path):
    corpus = tmp_path / "corpus"
    generate(corpus, loads_count=8, seed=42)
    loads = load_synthetic_loads(corpus)
    store = WorkflowStore(tmp_path / "workflow.sqlite3", tenant="tenant-fixture-a")
    try:
        seen: set[tuple[str, str]] = set()
        for load in loads:
            process_load_packet(
                store,
                load,
                primary_document_path=corpus / load.documents["carrier_invoice"],
                seen_invoice_keys=seen,
            )

        site = build_mock_tms_site(
            output_dir=tmp_path / "site" / "tms",
            corpus_dir=corpus,
            loads=loads,
            store=store,
        )
    finally:
        store.close()

    assert len(site.records) == 8
    assert (tmp_path / "site" / "tms" / "index.html").exists()
    assert (tmp_path / "site" / "tms" / "data.json").exists()
    assert (tmp_path / "site" / "tms" / "loads" / "LD-560003.html").exists()

    variance = next(record for record in site.records if record.load_id == "LD-560003")
    assert variance.payable_status == "NEEDS_REVIEW"
    assert variance.rate_total == "3334.50"
    assert variance.invoice_total == "3634.50"
    assert variance.workflow_run_id is not None
    assert variance.packet_detail_url == f"../../packets/{variance.workflow_run_id}/"
    assert any(charge.name == "detention" and charge.authorized is False for charge in variance.charges)


def test_mock_tms_record_has_realistic_broker_fields(tmp_path):
    corpus = tmp_path / "corpus"
    generate(corpus, loads_count=8, seed=42)
    loads = load_synthetic_loads(corpus)
    store = WorkflowStore(tmp_path / "workflow.sqlite3", tenant="tenant-fixture-a")
    try:
        seen: set[tuple[str, str]] = set()
        for load in loads:
            process_load_packet(
                store,
                load,
                primary_document_path=corpus / load.documents["carrier_invoice"],
                seen_invoice_keys=seen,
            )
        site = build_mock_tms_site(
            output_dir=tmp_path / "site" / "tms",
            corpus_dir=corpus,
            loads=loads,
            store=store,
        )
    finally:
        store.close()

    variance = next(record for record in site.records if record.load_id == "LD-560003")
    # Carrier authority identifiers a real broker TMS carries.
    assert variance.carrier_mc and variance.carrier_dot and variance.carrier_scac
    assert len(variance.carrier_scac) == 4
    # Settlement / AP voucher concepts.
    assert variance.settlement_number == "STL-560003"
    assert variance.settlement_status == "ON_HOLD"  # NEEDS_REVIEW maps to an AP hold
    assert variance.payment_terms
    # Required-document checklist driven by what is actually on file.
    names = {doc.name for doc in variance.required_documents}
    assert {"Rate confirmation", "BOL", "POD"} <= names
    # Detention carries authorization terms (free time then per-hour).
    detention = next(c for c in variance.charges if c.name == "detention")
    assert detention.terms and "free" in detention.terms

    # A clean matched/auto-cleared load settles as PAID.
    paid = next((r for r in site.records if r.payable_status == "AUTO_CLEARED"), None)
    if paid is not None:
        assert paid.settlement_status == "PAID"

    # The enriched fields are serialized to the machine-readable surface too.
    import json as _json

    data = _json.loads((tmp_path / "site" / "tms" / "data.json").read_text())
    sample = next(item for item in data if item["load_id"] == "LD-560003")
    assert sample["settlement_status"] == "ON_HOLD"
    assert sample["carrier_scac"]
