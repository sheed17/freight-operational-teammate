"""Tests for workflow state, audit, and idempotency V0."""

from dataclasses import asdict
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from generate_realistic_corpus import generate  # noqa: E402
from freight_recon.reconciliation import FreightLoadForReconciliation  # noqa: E402
from freight_recon.workflow import (  # noqa: E402
    WorkflowError,
    WorkflowState,
    WorkflowStore,
    process_load_packet,
    sha256_file,
)
from freight_recon.workflow_direction import WorkflowDirection  # noqa: E402


def _generated_corpus(tmp_path, count=9, seed=42):
    corpus = tmp_path / "corpus"
    generate(corpus, count, seed)
    import json

    raw = json.loads((corpus / "ground_truth" / "loads_and_scenarios.json").read_text())
    loads = [FreightLoadForReconciliation.from_mapping(item) for item in raw.values()]
    return corpus, loads


def test_workflow_routes_generated_loads_to_done_or_review(tmp_path):
    corpus, loads = _generated_corpus(tmp_path, count=9)
    store = WorkflowStore(tmp_path / "workflow.sqlite3")
    seen: set[tuple[str, str]] = set()

    for load in loads:
        process_load_packet(store, load, primary_document_path=corpus / load.documents["carrier_invoice"], seen_invoice_keys=seen)

    runs = store.list_runs()
    assert len(runs) == 9
    states = {run.load_id: run.state for run in runs}
    assert states["LD-560001"] == WorkflowState.DONE
    assert states["LD-560003"] == WorkflowState.NEEDS_REVIEW
    assert states["LD-560007"] == WorkflowState.NEEDS_REVIEW
    assert len(store.audit_events()) >= 9 * 4
    store.close()


def test_workflow_idempotency_uses_document_hash(tmp_path):
    corpus, loads = _generated_corpus(tmp_path, count=1)
    load = loads[0]
    doc = corpus / load.documents["carrier_invoice"]
    store = WorkflowStore(tmp_path / "workflow.sqlite3")

    run1 = store.receive_document(load.load_id, sha256_file(doc), {"primary_document": str(doc)})
    run2 = store.receive_document(load.load_id, sha256_file(doc), {"primary_document": str(doc)})

    assert run1.id == run2.id
    assert len(store.list_runs()) == 1
    assert any(event["event_type"] == "duplicate_received" for event in store.audit_events(run1.id))
    store.close()


def test_workflow_idempotency_is_scoped_by_ap_ar_direction(tmp_path):
    corpus, loads = _generated_corpus(tmp_path, count=4)
    source = next(load for load in loads if load.load_id == "LD-560003")
    ap_load = source.model_copy(update={"workflow_direction": WorkflowDirection.CARRIER_PAYABLE})
    ar_load = source.model_copy(update={"workflow_direction": WorkflowDirection.CUSTOMER_INVOICE})
    doc = corpus / source.documents["carrier_invoice"]
    store = WorkflowStore(tmp_path / "workflow.sqlite3")

    ap_run = process_load_packet(store, ap_load, primary_document_path=doc)
    ar_run = process_load_packet(store, ar_load, primary_document_path=doc)

    assert ap_run.id != ar_run.id
    assert ap_run.workflow_direction == WorkflowDirection.CARRIER_PAYABLE
    assert ar_run.workflow_direction == WorkflowDirection.CUSTOMER_INVOICE
    assert store.get_run(ap_run.id).document_hash.startswith("CARRIER_PAYABLE:")
    assert store.get_run(ar_run.id).document_hash.startswith("CUSTOMER_INVOICE:")
    store.close()


def test_workflow_blocks_invalid_state_transition(tmp_path):
    corpus, loads = _generated_corpus(tmp_path, count=1)
    load = loads[0]
    doc = corpus / load.documents["carrier_invoice"]
    store = WorkflowStore(tmp_path / "workflow.sqlite3")
    run = store.receive_document(load.load_id, sha256_file(doc), {"primary_document": str(doc)})

    with pytest.raises(WorkflowError):
        store.transition(run.id, WorkflowState.ENTERING)
    store.close()


def test_process_load_packet_is_retry_safe_for_terminal_run(tmp_path):
    corpus, loads = _generated_corpus(tmp_path, count=1)
    load = loads[0]
    store = WorkflowStore(tmp_path / "workflow.sqlite3")
    seen: set[tuple[str, str]] = set()
    doc = corpus / load.documents["carrier_invoice"]

    first = process_load_packet(store, load, primary_document_path=doc, seen_invoice_keys=seen)
    second = process_load_packet(store, load, primary_document_path=doc, seen_invoice_keys=seen)

    assert first.id == second.id
    assert second.state == WorkflowState.DONE
    assert len(store.list_runs()) == 1
    store.close()
