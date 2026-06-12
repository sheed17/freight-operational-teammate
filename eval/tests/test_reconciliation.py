"""Tests for deterministic reconciliation over synthetic freight scenarios."""

from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from generate_realistic_corpus import generate  # noqa: E402
from freight_recon.reconciliation import (  # noqa: E402
    FreightLoadForReconciliation,
    ReconciliationOutcome,
    reconcile_many,
)


def _reconcile_generated(tmp_path, count=18, seed=42):
    corpus = tmp_path / "corpus"
    generate(corpus, count, seed)
    raw = json.loads((corpus / "ground_truth" / "loads_and_scenarios.json").read_text())
    loads = [FreightLoadForReconciliation.from_mapping(item) for item in raw.values()]
    return raw, reconcile_many(loads)


def test_reconciliation_matches_generated_expected_outcomes(tmp_path):
    generated, results = _reconcile_generated(tmp_path)
    by_id = {result.load_id: result for result in results}

    for load_id, load in generated.items():
        assert by_id[load_id].outcome.value == load["expected_outcome"]


def test_reconciliation_detects_money_variances_with_reasons(tmp_path):
    _, results = _reconcile_generated(tmp_path)
    by_id = {result.load_id: result for result in results}

    fuel = by_id["LD-560004"]
    assert fuel.outcome == ReconciliationOutcome.VARIANCE
    assert any("fuel mismatch" in reason for reason in fuel.reasons)
    assert fuel.variance_amount > 0

    linehaul = by_id["LD-560005"]
    assert linehaul.outcome == ReconciliationOutcome.VARIANCE
    assert any("linehaul mismatch" in reason for reason in linehaul.reasons)
    assert linehaul.variance_amount > 0


def test_reconciliation_detects_missing_packet_evidence(tmp_path):
    _, results = _reconcile_generated(tmp_path)
    by_id = {result.load_id: result for result in results}

    lumper = by_id["LD-560006"]
    assert lumper.outcome == ReconciliationOutcome.NEEDS_REVIEW
    assert any("missing backup" in reason for reason in lumper.reasons)

    pod = by_id["LD-560008"]
    assert pod.outcome == ReconciliationOutcome.NEEDS_REVIEW
    assert any("missing POD" in reason for reason in pod.reasons)


def test_reconciliation_detects_duplicate_invoices_before_other_issues(tmp_path):
    _, results = _reconcile_generated(tmp_path)
    by_id = {result.load_id: result for result in results}

    duplicate = by_id["LD-560007"]
    assert duplicate.outcome == ReconciliationOutcome.DUPLICATE
    assert any("duplicate invoice number" in reason for reason in duplicate.reasons)
