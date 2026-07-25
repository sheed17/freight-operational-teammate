"""Tests for bounded TMS read adapters."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from generate_realistic_corpus import generate  # noqa: E402
from freight_recon.mock_tms import build_mock_tms_site  # noqa: E402
from freight_recon.tms_adapter import MockTmsReadAdapter, TmsAdapterError  # noqa: E402
from freight_recon.tool_permissions import ToolContext  # noqa: E402
from freight_recon.workflow import WorkflowState, WorkflowStore, process_load_packet  # noqa: E402
from run_workflow import load_synthetic_loads  # noqa: E402


def _build_site(tmp_path: Path) -> Path:
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
        build_mock_tms_site(
            output_dir=tmp_path / "site" / "tms",
            corpus_dir=corpus,
            loads=loads,
            store=store,
        )
    finally:
        store.close()
    return tmp_path / "site" / "tms"


def _build_site_and_store(tmp_path: Path):
    corpus = tmp_path / "corpus"
    generate(corpus, loads_count=8, seed=42)
    loads = load_synthetic_loads(corpus)
    store = WorkflowStore(tmp_path / "workflow.sqlite3", tenant="tenant-fixture-a")
    seen: set[tuple[str, str]] = set()
    for load in loads:
        process_load_packet(
            store,
            load,
            primary_document_path=corpus / load.documents["carrier_invoice"],
            seen_invoice_keys=seen,
        )
    build_mock_tms_site(
        output_dir=tmp_path / "site" / "tms",
        corpus_dir=corpus,
        loads=loads,
        store=store,
    )
    return tmp_path / "site" / "tms", store


def test_mock_tms_read_adapter_reads_load_detail(tmp_path):
    adapter = MockTmsReadAdapter(_build_site(tmp_path))

    load = adapter.read_load("LD-560003")

    assert load.load_id == "LD-560003"
    assert load.pro_number == "PRO-9200411"
    assert load.invoice_number == "INV-2026003"
    assert load.carrier == "Summit Valley Trucking"
    assert load.rate_total == "3334.50"
    assert load.invoice_total == "3634.50"
    assert load.payable_status == "NEEDS_REVIEW"
    assert load.workflow_state == "NEEDS_REVIEW"
    assert any(charge.name == "detention" and charge.authorized is False for charge in load.charges)
    assert any(document.doc_type == "carrier_invoice" for document in load.documents)


def test_mock_tms_read_adapter_reads_payable_queue(tmp_path):
    adapter = MockTmsReadAdapter(_build_site(tmp_path))

    payable = adapter.read_payable("LD-560003")

    assert payable.invoice_number == "INV-2026003"
    assert payable.carrier == "Summit Valley Trucking"
    assert payable.expected_amount == "3334.50"
    assert payable.billed_amount == "3634.50"
    assert payable.payable_status == "NEEDS_REVIEW"


def test_mock_tms_read_adapter_blocks_invalid_load_ids(tmp_path):
    adapter = MockTmsReadAdapter(_build_site(tmp_path))

    with pytest.raises(TmsAdapterError):
        adapter.read_load("../LD-560003")


def test_mock_tms_read_adapter_fails_closed_on_missing_load(tmp_path):
    adapter = MockTmsReadAdapter(_build_site(tmp_path))

    with pytest.raises(TmsAdapterError):
        adapter.read_load("LD-999999")


def test_mock_tms_read_adapter_audits_permission_and_readback(tmp_path):
    site, store = _build_site_and_store(tmp_path)
    try:
        run = next(item for item in store.list_runs() if item.load_id == "LD-560003")
        adapter = MockTmsReadAdapter(
            site,
            store=store,
            run_id=run.id,
            tool_context=ToolContext(workflow_state=WorkflowState.NEEDS_REVIEW, actor="tester"),
        )

        adapter.read_load("LD-560003")
        adapter.read_payable("LD-560003")

        events = [event["event_type"] for event in store.audit_events(run.id)]
        assert events.count("tool_permission_allowed") >= 2
        assert "tms_load_read" in events
        assert "tms_payable_read" in events
    finally:
        store.close()
