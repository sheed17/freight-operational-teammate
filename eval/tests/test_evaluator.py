"""Regression tests for the eval harness's own scoring math.

These protect the numbers the Stage 1 gate is built on. If a refactor changes how a
field is scored, calibrated, or categorized, these break before the harness silently
reports wrong accuracy.
"""

import pytest

import evaluator as ev
from evaluator import (
    CORRECT,
    EXTRA,
    INCORRECT,
    MISSING,
    evaluate,
    normalize_date,
    parse_number,
    score_accessorials,
    score_scalar,
    string_match,
)


# ---------------------------------------------------------------------------
# Value normalization
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    (1150, 1150.0),
    (1150.0, 1150.0),
    ("1150", 1150.0),
    ("$1,150.00", 1150.0),
    ("  1,150.00 USD ", 1150.0),
    ("-50.5", -50.5),
    (None, None),
    ("", None),
    ("n/a", None),
])
def test_parse_number(raw, expected):
    assert parse_number(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("2024-03-15", "2024-03-15"),
    ("03/15/2024", "2024-03-15"),
    ("3/15/2024", "2024-03-15"),
    ("March 15, 2024", "2024-03-15"),
    ("Mar 15, 2024", "2024-03-15"),
    ("not a date", None),
    (None, None),
])
def test_normalize_date(raw, expected):
    assert normalize_date(raw) == expected


@pytest.mark.parametrize("a,b,expected", [
    ("Swift Transport LLC", "swift transport llc", "exact"),
    ("Swift Transport", "Swift Transport LLC", "near"),       # substring
    ("Midwest Freight Inc", "Midwest Freight", "near"),
    ("Acme Trucking", "Globex Logistics", "no"),
    ("", "x", "no"),
])
def test_string_match(a, b, expected):
    assert string_match(a, b) == expected


# ---------------------------------------------------------------------------
# Scalar scoring
# ---------------------------------------------------------------------------

def _field(value, conf=0.9, note=None):
    d = {"value": value, "confidence": conf}
    if note:
        d["extraction_note"] = note
    return d


def test_numeric_correct_within_tolerance():
    fs = score_scalar("f", "decimal", "linehaul_amount", _field(1150.005), 1150.00)
    assert fs.outcome == CORRECT


def test_numeric_incorrect_beyond_tolerance():
    fs = score_scalar("f", "decimal", "linehaul_amount", _field(1200.0), 1150.00)
    assert fs.outcome == INCORRECT
    assert fs.category == ev.WRONG_VALUE


def test_numeric_string_with_formatting_is_parsed():
    fs = score_scalar("f", "decimal", "total_amount", _field("$1,387.50"), 1387.50)
    assert fs.outcome == CORRECT


def test_date_matches_across_formats():
    fs = score_scalar("f", "date", "invoice_date", _field("03/15/2024"), "2024-03-15")
    assert fs.outcome == CORRECT


def test_identifier_requires_exact_match_truncation_is_wrong():
    # The spec's example: L-449 vs L-44982 is a real error, not a near-match.
    fs = score_scalar("f", "string", "load_or_pro_number", _field("L-449"), "L-44982")
    assert fs.outcome == INCORRECT


def test_identifier_exact_passes():
    fs = score_scalar("f", "string", "load_or_pro_number", _field("L-44982"), "L-44982")
    assert fs.outcome == CORRECT


def test_descriptive_string_near_match_is_correct():
    fs = score_scalar("f", "string", "carrier_name", _field("Midwest Freight"), "Midwest Freight Inc")
    assert fs.outcome == CORRECT


def test_missing_value_is_not_found():
    fs = score_scalar("f", "decimal", "fuel_surcharge", _field(None, 0.3), 87.5)
    assert fs.outcome == MISSING
    assert fs.category == ev.NOT_FOUND
    assert fs.asserted is False


def test_extra_value_when_truth_absent():
    fs = score_scalar("f", "decimal", "fuel_surcharge", _field(50.0), None)
    assert fs.outcome == EXTRA


def test_both_absent_is_correct():
    fs = score_scalar("f", "string", "carrier_name", _field(None), None)
    assert fs.outcome == CORRECT


def test_fuel_zero_is_present_and_matches():
    fs = score_scalar("f", "decimal", "fuel_surcharge", _field(0.0), 0.0)
    assert fs.outcome == CORRECT


def test_categorize_multipage_from_note():
    fs = score_scalar("f", "decimal", "linehaul_amount", _field(None, 0.2, "value was on the second page"), 1150.0)
    assert fs.category == ev.MULTI_PAGE_MISS


def test_categorize_format_error_for_unparseable_number():
    fs = score_scalar("f", "decimal", "total_amount", _field("see attached"), 1387.50)
    assert fs.outcome == INCORRECT
    assert fs.category == ev.FORMAT_ERROR


def test_categorize_label_variation_from_note():
    fs = score_scalar("f", "string", "carrier_name", _field("Wrong Co", 0.6, "label was non-standard"), "Right Co")
    assert fs.category == ev.LABEL_VARIATION


# ---------------------------------------------------------------------------
# Accessorials scoring
# ---------------------------------------------------------------------------

def test_accessorials_full_match_order_independent():
    extracted = [{"name": "lumper", "amount": 95.0, "confidence": 0.9},
                 {"name": "detention", "amount": 120.0, "confidence": 0.9}]
    truth = [{"name": "detention", "amount": 120.0},
             {"name": "lumper", "amount": 95.0}]
    fs, preds = score_accessorials("f", extracted, truth)
    assert fs.outcome == CORRECT
    assert all(p.correct for p in preds)


def test_accessorials_missed_item_is_incorrect():
    extracted = [{"name": "lumper", "amount": 95.0, "confidence": 0.85}]
    truth = [{"name": "lumper", "amount": 95.0}, {"name": "detention", "amount": 120.0}]
    fs, preds = score_accessorials("f", extracted, truth)
    assert fs.outcome == INCORRECT
    assert "found 1/2" in fs.note


def test_accessorials_extra_item_is_incorrect():
    extracted = [{"name": "lumper", "amount": 95.0, "confidence": 0.9},
                 {"name": "tonu", "amount": 200.0, "confidence": 0.7}]
    truth = [{"name": "lumper", "amount": 95.0}]
    fs, preds = score_accessorials("f", extracted, truth)
    assert fs.outcome == INCORRECT
    # the extra (wrong) item is an incorrect prediction for calibration
    assert any(not p.correct for p in preds)


def test_accessorials_both_empty_is_correct():
    fs, preds = score_accessorials("f", [], [])
    assert fs.outcome == CORRECT
    assert preds == []


def test_accessorials_truth_present_extracted_empty_is_missing():
    fs, _ = score_accessorials("f", [], [{"name": "detention", "amount": 120.0}])
    assert fs.outcome == MISSING


# ---------------------------------------------------------------------------
# End-to-end aggregation + the production gate (anchored to the committed fixtures)
# ---------------------------------------------------------------------------

def test_mock_v1_fails_gate_with_two_overconfidence_cases(results_from_mock, mock_v1, ground_truth, config):
    report = evaluate(results_from_mock(mock_v1), ground_truth, config)
    assert report.docs_processed == 3
    assert report.production_ready() is False
    # linehaul (002) and load_or_pro (003) are confidently wrong required fields.
    danger = report.dangerous_overconfidence()
    assert len(danger) == 2
    assert {d["field"] for d in danger} == {"linehaul_amount", "load_or_pro_number"}
    # required-field accuracy below the 90% gate for those two
    req = report.required_field_pass()
    assert req["linehaul_amount"] is False
    assert req["load_or_pro_number"] is False
    assert req["total_amount"] is True


def test_mock_v2_passes_gate(results_from_mock, mock_v2, ground_truth, config):
    report = evaluate(results_from_mock(mock_v2), ground_truth, config)
    assert report.production_ready() is True
    assert report.dangerous_overconfidence() == []
    assert report.overall_accuracy >= ev.GATE_OVERALL_ACCURACY


def test_failure_modes_recorded(results_from_mock, mock_v1, ground_truth, config):
    report = evaluate(results_from_mock(mock_v1), ground_truth, config)
    # fuel surcharge was returned null on 002 -> NOT_FOUND
    assert report.failure_modes.get(ev.NOT_FOUND, {}).get("fuel_surcharge") == 1


def test_extraction_failure_counts_fields_as_model_error(config, ground_truth):
    from extraction import ExtractionResult
    failed = ExtractionResult("invoice_001.pdf", "FAILED", error="boom")
    report = evaluate([failed], ground_truth, config)
    assert report.extraction_failures
    # every field becomes a MODEL_ERROR miss; none counted correct
    assert report.field_stats["total_amount"].missing == 1
    assert ev.MODEL_ERROR in report.failure_modes


def test_buckets_partition_all_asserted_predictions(results_from_mock, mock_v1, ground_truth, config):
    report = evaluate(results_from_mock(mock_v1), ground_truth, config)
    total_in_buckets = sum(b.n for b in report.buckets)
    # every bucket's correct count never exceeds its n
    assert all(b.correct <= b.n for b in report.buckets)
    assert total_in_buckets > 0
