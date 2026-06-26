"""Tests for human-review payload generation."""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from generate_realistic_corpus import generate  # noqa: E402
from freight_recon.reconciliation import FreightLoadForReconciliation, ReconciliationOutcome  # noqa: E402
from freight_recon.review import (  # noqa: E402
    DogfoodClientProfile,
    ReviewAction,
    ReviewRoute,
    ReviewSeverity,
    build_review_payload,
    record_review_payload,
    render_text_review,
)
from freight_recon.workflow import WorkflowState, WorkflowStore, process_load_packet  # noqa: E402


def _run_generated_workflow(tmp_path, count=9):
    corpus = tmp_path / "corpus"
    generate(corpus, count, seed=42)
    raw = json.loads((corpus / "ground_truth" / "loads_and_scenarios.json").read_text())
    loads = [FreightLoadForReconciliation.from_mapping(item) for item in raw.values()]
    store = WorkflowStore(tmp_path / "workflow.sqlite3")
    seen: set[tuple[str, str]] = set()
    for load in loads:
        process_load_packet(
            store,
            load,
            primary_document_path=corpus / load.documents["carrier_invoice"],
            seen_invoice_keys=seen,
        )
    return corpus, loads, store


def test_review_payload_for_variance_has_human_actions(tmp_path):
    _, loads, store = _run_generated_workflow(tmp_path, count=5)
    load_by_id = {load.load_id: load for load in loads}
    run = next(run for run in store.list_runs() if run.load_id == "LD-560003")

    payload = build_review_payload(run, load_by_id[run.load_id])

    assert payload is not None
    assert payload.outcome == ReconciliationOutcome.VARIANCE
    assert payload.severity == ReviewSeverity.CRITICAL
    assert ReviewAction.APPROVE in payload.actions
    assert ReviewAction.DISPUTE in payload.actions
    assert any(field.status == "unauthorized" for field in payload.fields)
    assert payload.packet_detail_url.endswith(f"/{run.id}")
    assert any(link.document_type == "carrier_invoice" for link in payload.evidence_links)
    assert any(link.document_type == "rate_confirmation" for link in payload.evidence_links)
    assert payload.found_money.flagged_amount == "300.00"
    assert payload.routing.route == ReviewRoute.IMMEDIATE_PING
    assert any("Approve $3334.50 and dispute $300.00 detention" == option.label for option in payload.action_options)
    # A standalone dispute (hold the whole payable, pay nothing) is offered, distinct from the
    # approve-the-clean-part-and-dispute-the-delta option.
    standalone_dispute = [
        o for o in payload.action_options if o.code == ReviewAction.DISPUTE and "hold payment" in o.label.lower()
    ]
    assert len(standalone_dispute) == 1 and standalone_dispute[0].amount is None
    assert payload.audit_context["no_autonomous_tms_write"] is True
    store.close()


def test_review_payload_for_duplicate_blocks_approval_default(tmp_path):
    _, loads, store = _run_generated_workflow(tmp_path, count=7)
    load_by_id = {load.load_id: load for load in loads}
    run = next(run for run in store.list_runs() if run.load_id == "LD-560007")

    payload = build_review_payload(run, load_by_id[run.load_id])

    assert payload is not None
    assert payload.outcome == ReconciliationOutcome.DUPLICATE
    assert payload.actions == [ReviewAction.MARK_DUPLICATE, ReviewAction.DISPUTE]
    assert [option.label for option in payload.action_options] == [
        "Mark duplicate",
        "Dispute duplicate invoice",
    ]
    assert all(option.code != ReviewAction.APPROVE for option in payload.action_options)
    assert any(field.status == "duplicate" for field in payload.fields)
    store.close()


def test_matched_done_run_has_no_review_payload(tmp_path):
    _, loads, store = _run_generated_workflow(tmp_path, count=1)
    run = store.list_runs()[0]

    payload = build_review_payload(run, loads[0])

    assert run.state == WorkflowState.DONE
    assert payload is None
    store.close()


def test_text_review_renderer_is_channel_safe(tmp_path):
    _, loads, store = _run_generated_workflow(tmp_path, count=8)
    load_by_id = {load.load_id: load for load in loads}
    run = next(run for run in store.list_runs() if run.load_id == "LD-560008")
    payload = build_review_payload(run, load_by_id[run.load_id])
    assert payload is not None

    text = render_text_review(payload)

    assert "Load: LD-560008" in text
    assert "Actions:" in text
    assert "Request backup from carrier" in text
    assert "Packet:" in text
    assert "Evidence:" in text
    store.close()


def test_record_review_payload_is_idempotent(tmp_path):
    _, loads, store = _run_generated_workflow(tmp_path, count=8)
    load_by_id = {load.load_id: load for load in loads}
    run = next(run for run in store.list_runs() if run.load_id == "LD-560008")
    payload = build_review_payload(run, load_by_id[run.load_id])
    assert payload is not None

    record_review_payload(store, payload)
    record_review_payload(store, payload)

    events = [
        event
        for event in store.audit_events(run.id)
        if event["event_type"] == "review_payload_created"
    ]
    assert len(events) == 1
    store.close()


def test_record_review_payload_records_new_revision_when_action_amount_changes(tmp_path):
    _, loads, store = _run_generated_workflow(tmp_path, count=8)
    load_by_id = {load.load_id: load for load in loads}
    run = next(run for run in store.list_runs() if run.load_id == "LD-560003")
    payload = build_review_payload(run, load_by_id[run.load_id])
    assert payload is not None

    changed_options = list(payload.action_options)
    changed_options[0] = changed_options[0].model_copy(update={"amount": "3335.50"})
    changed_payload = payload.model_copy(update={"action_options": changed_options})

    record_review_payload(store, payload)
    record_review_payload(store, changed_payload)

    events = [
        event
        for event in store.audit_events(run.id)
        if event["event_type"] == "review_payload_created"
    ]
    assert len(events) == 2
    assert events[0]["payload"]["payload_key"] != events[1]["payload"]["payload_key"]
    store.close()


def test_missing_pod_routes_to_ping_and_aging_escalates(tmp_path):
    _, loads, store = _run_generated_workflow(tmp_path, count=8)
    load_by_id = {load.load_id: load for load in loads}
    run = next(run for run in store.list_runs() if run.load_id == "LD-560008")

    payload = build_review_payload(run, load_by_id[run.load_id], age_hours=72)

    assert payload is not None
    assert payload.routing.route == ReviewRoute.IMMEDIATE_PING
    assert payload.routing.ping is True
    assert payload.aging.is_overdue is True
    assert payload.aging.next_escalation == "direct re-ping now"
    store.close()


def test_dogfood_profile_can_tune_variance_routing(tmp_path):
    _, loads, store = _run_generated_workflow(tmp_path, count=4)
    load_by_id = {load.load_id: load for load in loads}
    run = next(run for run in store.list_runs() if run.load_id == "LD-560003")
    client = DogfoodClientProfile(critical_variance_threshold="500.00", medium_variance_threshold="25.00")

    payload = build_review_payload(run, load_by_id[run.load_id], client=client)

    assert payload is not None
    assert payload.severity == ReviewSeverity.WARNING
    assert payload.routing.route == ReviewRoute.CHANNEL_POST
    assert payload.client.company_name == "Neyma Test Freight LLC"
    assert payload.client.operator_role == "owner/operator"
    store.close()
