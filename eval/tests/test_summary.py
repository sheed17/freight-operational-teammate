"""Tests for daily dogfood summaries."""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from generate_realistic_corpus import generate  # noqa: E402
from freight_recon.reconciliation import FreightLoadForReconciliation  # noqa: E402
from freight_recon.review import build_review_payload, record_review_payload  # noqa: E402
from freight_recon.review_actions import ReviewActionRequest, ReviewDecision, apply_review_action  # noqa: E402
from freight_recon.summary import build_daily_summary, render_daily_summary  # noqa: E402
from freight_recon.workflow import WorkflowStore, process_load_packet  # noqa: E402


def _summary_fixture(tmp_path):
    corpus = tmp_path / "corpus"
    generate(corpus, 18, seed=42)
    raw = json.loads((corpus / "ground_truth" / "loads_and_scenarios.json").read_text())
    loads = [FreightLoadForReconciliation.from_mapping(item) for item in raw.values()]
    store = WorkflowStore(tmp_path / "workflow.sqlite3", tenant="tenant-fixture-a")
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
    return store, payloads


def test_daily_summary_counts_and_found_money(tmp_path):
    store, payloads = _summary_fixture(tmp_path)

    summary = build_daily_summary(store, payloads)

    assert summary.processed == 18
    assert summary.auto_cleared == 6
    assert summary.needs_review == 12
    assert summary.duplicates == 2
    assert summary.missing_backup == 4
    assert summary.potential_overbilling_flagged == "1250.00"
    assert summary.confirmed_recovered == "0.00"
    assert summary.oldest_largest_unresolved[0].flagged_amount == "300.00"
    store.close()


def test_confirmed_recovered_counts_only_at_verified_done(tmp_path):
    from freight_recon.tms_write import MockTmsWriteLedger, enter_approved_payable

    store, payloads = _summary_fixture(tmp_path)
    run_id = next(payload.run_id for payload in payloads if payload.load_id == "LD-560003")
    apply_review_action(
        store,
        ReviewActionRequest(run_id=run_id, decision=ReviewDecision.APPROVE_EXPECTED_AMOUNT, amount="3334.50"),
    )

    # Approval alone has recovered nothing yet — the TMS hasn't confirmed it.
    assert build_daily_summary(store, payloads).confirmed_recovered == "0.00"

    # Only once the payable is entered and verified by readback (run DONE) does it count.
    enter_approved_payable(store, MockTmsWriteLedger(tmp_path / "ledger.json"), run_id, amount="3334.50")
    summary = build_daily_summary(store, payloads)
    text = render_daily_summary(summary)
    assert summary.confirmed_recovered == "300.00"
    assert "$300.00 confirmed recovered" in text
    store.close()
