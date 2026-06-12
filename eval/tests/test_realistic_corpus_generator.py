"""Regression tests for the realistic freight corpus generator."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from generate_realistic_corpus import build_loads, carrier_invoice_truth  # noqa: E402


def test_variance_scenarios_separate_rate_and_invoice_values():
    loads = build_loads(9, seed=11)
    fuel = next(load for load in loads if load.scenario == "fuel_mismatch")
    linehaul = next(load for load in loads if load.scenario == "linehaul_mismatch")

    assert fuel.rate_fuel != fuel.invoice_fuel
    assert fuel.rate_linehaul == fuel.invoice_linehaul
    assert "fuel surcharge" in fuel.variance_reasons[0]

    assert linehaul.rate_linehaul != linehaul.invoice_linehaul
    assert linehaul.rate_fuel == linehaul.invoice_fuel
    assert "linehaul" in linehaul.variance_reasons[0]


def test_carrier_invoice_truth_uses_invoice_claimed_amounts():
    load = next(load for load in build_loads(9, seed=11) if load.scenario == "linehaul_mismatch")
    truth = carrier_invoice_truth(load)

    assert truth["linehaul_amount"] == float(load.invoice_linehaul)
    assert truth["linehaul_amount"] != float(load.rate_linehaul)
    assert truth["total_amount"] == float(load.invoice_total)


def test_generator_contains_document_and_data_entry_scenarios():
    scenarios = {load.scenario for load in build_loads(18, seed=42)}

    assert "clean_match" in scenarios
    assert "unauthorized_detention" in scenarios
    assert "fuel_mismatch" in scenarios
    assert "linehaul_mismatch" in scenarios
    assert "missing_lumper_backup" in scenarios
    assert "duplicate_invoice" in scenarios
    assert "missing_pod" in scenarios


def test_duplicate_scenario_reuses_carrier_and_invoice_number():
    loads = build_loads(9, seed=42)
    previous_by_id = {load.load_id: load for load in loads}
    duplicate = next(load for load in loads if load.scenario == "duplicate_invoice")
    source_id = duplicate.variance_reasons[0].split()[-1]
    source = previous_by_id[source_id]

    assert duplicate.invoice_number == source.invoice_number
    assert duplicate.carrier == source.carrier
