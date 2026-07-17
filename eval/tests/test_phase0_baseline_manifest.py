"""U0.12 - the baseline manifest's own integrity.

The manifest is the only place a Phase-0 allowance may live. Every allowance must carry a reason, a
removal phase, an accountable unit and a deletion condition - enforced here, not by review etiquette.

    No indefinite allowance. No wildcard allowance. No allowance justified only as "legacy".

An allowance without a deletion condition is an indefinite allowance wearing a temporary label.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase0 import manifest

FORBIDDEN_JUSTIFICATIONS = ("legacy", "historical", "for now", "tbd", "temporary")


def test_the_manifest_exists_and_parses():
    assert manifest.load()


@pytest.mark.parametrize("section", ["expected_current_defects", "expected_acceptance_failures",
                                     "expected_deprecated_terms"])
def test_every_allowance_names_a_reason_a_phase_a_unit_and_a_deletion_condition(section):
    entries = manifest.allowance_sections()[section]
    assert entries, f"{section} is empty - the probe would prove nothing"
    for e in entries:
        label = e.get("id") or e.get("case") or e.get("term")
        for field in ("reason", "removed_by_phase", "accountable_unit", "deletion_condition"):
            assert e.get(field), f"{section}/{label}: missing {field}"


def test_no_allowance_is_justified_only_as_legacy():
    for section, entries in manifest.allowance_sections().items():
        for e in entries:
            label = e.get("id") or e.get("case") or e.get("term")
            reason = str(e.get("reason", "")).strip().lower()
            assert len(reason) > 25, f"{section}/{label}: reason too thin to adjudicate: {reason!r}"
            assert reason not in FORBIDDEN_JUSTIFICATIONS, f"{section}/{label}: {reason!r} is not a reason"


def test_no_wildcard_allowance():
    """A wildcard would let anything through under a rule nobody could adjudicate."""
    raw = Path(manifest.MANIFEST if hasattr(manifest, "MANIFEST") else
               Path(__file__).resolve().parents[2] / "docs" / "implementation"
               / "phase-0-baseline-manifest.yaml").read_text(encoding="utf-8")
    for section in ("edges:", "tables_not_tenant_first:", "effect_capable_by_import:"):
        assert f"{section}\n    - '*'" not in raw
        assert f"{section}\n    - \"*\"" not in raw
    assert "\n    - '*'" not in raw and '\n    - "*"' not in raw


def test_r07_is_never_described_as_contained():
    """The single most important sentence in the manifest."""
    legacy = manifest.load()["expected_legacy_paths"]
    assert legacy["status"].startswith("OPEN")
    assert "NOT CONTAINED" in legacy["status"]
    assert legacy["containment_mechanism"].strip().startswith("NONE")
    assert "discipline, not a mechanism" in legacy["containment_mechanism"]
    assert "may never be read as containment" in legacy["containment_mechanism"]


def test_every_prohibited_regression_names_the_test_that_detects_it():
    """A rule with no detector is a wish."""
    regs = manifest.load()["prohibited_new_regressions"]
    assert len(regs) >= 8
    tests_dir = Path(__file__).resolve().parent
    for r in regs:
        detector = r["detected_by"]
        assert (tests_dir / f"{detector}.py").exists(), f"{r['id']}: no such detector {detector}"


def test_every_required_invariant_names_an_accountable_unit():
    for inv in manifest.load()["required_invariants"]:
        assert inv["rule"] and inv["reason"] and inv["accountable_unit"]


def test_the_test_count_ratchet_direction_is_recorded():
    """Tests may be added. A DROP is a hard failure - that is how a guard disappears unnoticed."""
    baseline = manifest.load()["baseline"]
    assert baseline["tests_passing_at_baseline"] == 677
    assert ">=" in baseline["test_count_rule"]
