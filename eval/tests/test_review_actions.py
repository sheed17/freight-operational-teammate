"""Tests for local dogfood review action intake."""

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from generate_realistic_corpus import generate  # noqa: E402
from freight_recon.reconciliation import ChargeLine, FreightLoadForReconciliation  # noqa: E402
from freight_recon.review import build_review_payload, record_review_payload  # noqa: E402
from freight_recon.review_actions import (  # noqa: E402
    ReviewCorrection,
    ReviewActionRequest,
    ReviewDecision,
    apply_review_action,
)
from freight_recon.workflow import WorkflowError, WorkflowState, WorkflowStore, process_load_packet  # noqa: E402
from freight_recon.workflow_direction import WorkflowDirection  # noqa: E402


def _store_with_review_runs(tmp_path, count=8):
    corpus = tmp_path / "corpus"
    generate(corpus, count, seed=42)
    raw = json.loads((corpus / "ground_truth" / "loads_and_scenarios.json").read_text())
    loads = [FreightLoadForReconciliation.from_mapping(item) for item in raw.values()]
    store = WorkflowStore(tmp_path / "workflow.sqlite3", tenant="tenant-fixture-a")
    seen: set[tuple[str, str]] = set()
    for load in loads:
        run = process_load_packet(
            store,
            load,
            primary_document_path=corpus / load.documents["carrier_invoice"],
            seen_invoice_keys=seen,
        )
        payload = build_review_payload(run, load)
        if payload is not None:
            record_review_payload(store, payload)
    return store


def test_approve_expected_amount_advances_to_approved_and_audits(tmp_path):
    store = _store_with_review_runs(tmp_path)
    run = next(run for run in store.list_runs() if run.load_id == "LD-560003")

    result = apply_review_action(
        store,
        ReviewActionRequest(
            run_id=run.id,
            decision=ReviewDecision.APPROVE_EXPECTED_AMOUNT,
            amount="3334.50",
            note="approve expected, dispute detention",
        ),
    )

    assert result.from_state == WorkflowState.NEEDS_REVIEW
    assert result.to_state == WorkflowState.APPROVED
    assert result.mutation_text == "Approved expected carrier payable $3334.50 by Rasheed"
    assert result.draft_follow_up_required is True
    events = store.audit_events(run.id)
    assert any(event["event_type"] == "review_approved_expected_amount" for event in events)
    store.close()


def test_ar_expected_approval_records_customer_invoice_direction_without_follow_up(tmp_path):
    corpus = tmp_path / "corpus"
    generate(corpus, 5, seed=42)
    raw = json.loads((corpus / "ground_truth" / "loads_and_scenarios.json").read_text())
    load = FreightLoadForReconciliation.from_mapping(raw["LD-560003"]).model_copy(
        update={"workflow_direction": WorkflowDirection.CUSTOMER_INVOICE}
    )
    store = WorkflowStore(tmp_path / "workflow.sqlite3", tenant="tenant-fixture-a")
    run = process_load_packet(store, load, primary_document_path=corpus / load.documents["carrier_invoice"])
    payload = build_review_payload(run, load)
    assert payload is not None
    record_review_payload(store, payload)

    result = apply_review_action(
        store,
        ReviewActionRequest(
            run_id=run.id,
            decision=ReviewDecision.APPROVE_EXPECTED_AMOUNT,
            amount="3334.50",
        ),
    )

    assert result.to_state == WorkflowState.APPROVED
    assert result.mutation_text == "Approved expected customer invoice $3334.50 by Rasheed"
    assert result.draft_follow_up_required is False
    event = next(event for event in store.audit_events(run.id) if event["event_type"] == "review_approved_expected_amount")
    assert event["payload"]["workflow_direction"] == "CUSTOMER_INVOICE"
    store.close()


def test_ar_request_backup_does_not_create_carrier_follow_up_requirement(tmp_path):
    load = FreightLoadForReconciliation(
        workflow_direction=WorkflowDirection.CUSTOMER_INVOICE,
        load_id="LD-AR-BACKUP",
        invoice_number="AR-100",
        carrier="Test Carrier",
        customer="Test Broker",
        rate_linehaul="2000.00",
        rate_fuel="300.00",
        invoice_linehaul="2000.00",
        invoice_fuel="300.00",
        rate_accessorials=[ChargeLine(name="Detention", amount="150.00")],
        invoice_accessorials=[ChargeLine(name="Detention", amount="150.00")],
        documents={"carrier_invoice": "invoice.pdf", "rate_confirmation": "rate.pdf", "pod": "pod.pdf"},
    )
    invoice = tmp_path / "invoice.pdf"
    invoice.write_bytes(b"%PDF-1.4 fake")
    store = WorkflowStore(tmp_path / "workflow.sqlite3", tenant="tenant-fixture-a")
    run = process_load_packet(store, load, primary_document_path=invoice)
    payload = build_review_payload(run, load)
    assert payload is not None
    record_review_payload(store, payload)

    result = apply_review_action(
        store,
        ReviewActionRequest(run_id=run.id, decision=ReviewDecision.REQUEST_BACKUP),
    )

    assert result.to_state == WorkflowState.REQUESTED_BACKUP
    assert result.draft_follow_up_required is False
    event = next(event for event in store.audit_events(run.id) if event["event_type"] == "review_backup_requested")
    assert event["payload"]["workflow_direction"] == "CUSTOMER_INVOICE"
    store.close()


def test_dispute_advances_to_disputed_and_requires_follow_up(tmp_path):
    store = _store_with_review_runs(tmp_path)
    run = next(run for run in store.list_runs() if run.load_id == "LD-560004")

    result = apply_review_action(
        store,
        ReviewActionRequest(run_id=run.id, decision=ReviewDecision.DISPUTE, note="fuel over rate"),
    )

    assert result.to_state == WorkflowState.DISPUTED
    assert result.mutation_text == "Disputed by Rasheed"
    assert result.draft_follow_up_required is True
    assert any(event["event_type"] == "review_disputed" for event in store.audit_events(run.id))
    store.close()


def test_request_backup_advances_to_requested_backup(tmp_path):
    store = _store_with_review_runs(tmp_path)
    run = next(run for run in store.list_runs() if run.load_id == "LD-560008")

    result = apply_review_action(
        store,
        ReviewActionRequest(run_id=run.id, decision=ReviewDecision.REQUEST_BACKUP),
    )

    assert result.to_state == WorkflowState.REQUESTED_BACKUP
    assert result.draft_follow_up_required is True
    assert any(event["event_type"] == "review_backup_requested" for event in store.audit_events(run.id))
    store.close()


def test_edit_fields_stays_in_review_and_audits(tmp_path):
    store = _store_with_review_runs(tmp_path)
    run = next(run for run in store.list_runs() if run.load_id == "LD-560003")

    result = apply_review_action(
        store,
        ReviewActionRequest(run_id=run.id, decision=ReviewDecision.EDIT_FIELDS, note="fix amount"),
    )

    assert result.from_state == WorkflowState.NEEDS_REVIEW
    assert result.to_state == WorkflowState.NEEDS_REVIEW
    assert store.get_run(run.id).state == WorkflowState.NEEDS_REVIEW
    assert any(event["event_type"] == "review_edit_requested" for event in store.audit_events(run.id))
    store.close()


def test_edit_fields_records_typed_corrections(tmp_path):
    store = _store_with_review_runs(tmp_path)
    run = next(run for run in store.list_runs() if run.load_id == "LD-560003")

    apply_review_action(
        store,
        ReviewActionRequest(
            run_id=run.id,
            decision=ReviewDecision.EDIT_FIELDS,
            note="correct linehaul",
            corrections=[
                ReviewCorrection(field="linehaul_amount", before="3634.50", after="3334.50")
            ],
        ),
    )

    events = store.audit_events(run.id)
    correction_event = next(event for event in events if event["event_type"] == "review_corrections_recorded")
    assert correction_event["payload"]["eval_candidate"] is True
    assert correction_event["payload"]["corrections"][0]["field"] == "linehaul_amount"
    store.close()


def test_money_approval_requires_current_action_amount(tmp_path):
    store = _store_with_review_runs(tmp_path)
    run = next(run for run in store.list_runs() if run.load_id == "LD-560003")

    with pytest.raises(WorkflowError, match="does not match current review options"):
        apply_review_action(
            store,
            ReviewActionRequest(
                run_id=run.id,
                decision=ReviewDecision.APPROVE_EXPECTED_AMOUNT,
                amount="9999.99",
            ),
        )
    store.close()


def test_money_approval_rejects_stale_payload_from_other_direction(tmp_path):
    corpus = tmp_path / "corpus"
    generate(corpus, 5, seed=42)
    raw = json.loads((corpus / "ground_truth" / "loads_and_scenarios.json").read_text())
    load = FreightLoadForReconciliation.from_mapping(raw["LD-560003"]).model_copy(
        update={"workflow_direction": WorkflowDirection.CUSTOMER_INVOICE}
    )
    store = WorkflowStore(tmp_path / "workflow.sqlite3", tenant="tenant-fixture-a")
    run = process_load_packet(store, load, primary_document_path=corpus / load.documents["carrier_invoice"])
    payload = build_review_payload(run, load)
    assert payload is not None
    stale_ap_payload = payload.model_copy(update={"workflow_direction": WorkflowDirection.CARRIER_PAYABLE})
    record_review_payload(store, stale_ap_payload)

    with pytest.raises(WorkflowError, match="current workflow direction"):
        apply_review_action(
            store,
            ReviewActionRequest(
                run_id=run.id,
                decision=ReviewDecision.APPROVE_EXPECTED_AMOUNT,
                amount="3334.50",
            ),
        )
    store.close()


def test_money_approval_requires_amount(tmp_path):
    store = _store_with_review_runs(tmp_path)
    run = next(run for run in store.list_runs() if run.load_id == "LD-560003")

    with pytest.raises(WorkflowError, match="requires an explicit amount"):
        apply_review_action(
            store,
            ReviewActionRequest(run_id=run.id, decision=ReviewDecision.APPROVE_FULL_AMOUNT),
        )
    store.close()


def test_review_action_rejects_terminal_runs(tmp_path):
    store = _store_with_review_runs(tmp_path, count=1)
    run = store.list_runs()[0]
    assert run.state == WorkflowState.DONE

    with pytest.raises(WorkflowError):
        apply_review_action(
            store,
            ReviewActionRequest(run_id=run.id, decision=ReviewDecision.APPROVE_FULL_AMOUNT),
        )
    store.close()
