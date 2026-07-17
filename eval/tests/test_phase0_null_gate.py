"""U0.3 - the null-gate startup check (AC-CKPT-6-missing). NOT YET EXECUTABLE.

FINDING P0-F1: the frozen PR sequence lists U0.3 as a Phase-0 unit with AC-CKPT-6-missing as its
completion oracle. It is not achievable at Phase 0, and this file records why rather than faking it.

The case asserts that an action class with a NULL policy gate causes the system to FAIL TO START.
That requires typed policy and action classes - which land at P8 (U8.1). Today the repository has
`lane_graduation`, whose `is_autonomous()` returns a FAIL-SAFE DEFAULT when no graduation exists.

A default and a NOT-NULL gate are not the same thing, and the difference is the whole point:
  - a default says "nobody decided, so we picked the safe answer";
  - the canonical rule says "nobody decided, so REFUSE TO START".
The first is safe today and silently wrong tomorrow; the second is why AC-CKPT-6-missing exists.

Implementing the check now would enumerate ZERO gates and report green - the exact false-green
pattern of M-9, and the same error as PL-6 (a gate enabled before the thing it gates exists). The
roadmap already names the rule: a gate with nothing behind it is theatre.

So the honest Phase-0 outcome is NOT_YET_EXECUTABLE, adjudicated in the baseline manifest, green at
P8. The probe below proves the population really is empty rather than asserting it.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase0 import manifest
from phase0.evaluation import EmptyPopulationError, Evaluation


def test_the_canonical_gate_population_is_provably_empty_today():
    """Do not take my word for it: try to enumerate typed policy gates and prove there are none."""
    import freight_recon

    src = Path(freight_recon.__file__).parent
    ev = Evaluation(name="policy.typed_action_class_gates")
    # Match the gate decisions as WHOLE TOKENS, not as fragments of other identifiers.
    # `FORBIDDEN_TENANTS` (U2.6A's sentinel list) contains "FORBIDDEN" and is not a policy gate;
    # a substring scan counted it and reported that typed policy had arrived. Same class of bug as
    # the report guard that tripped over the word "DELETED" inside a docstring.
    import re as _re

    gate_tokens = ("HUMAN_APPROVAL_REQUIRED", "AUTONOMOUS_WITHIN_CAPS",
                   "PERMANENT_HUMAN_ASSERTION_REQUIRED", "FORBIDDEN")
    for path in sorted(src.rglob("*.py")):
        ev.sources_inspected.append(str(path))
        text = path.read_text(encoding="utf-8")
        for token in gate_tokens:
            if _re.search(rf"(?<![A-Za-z0-9_]){token}(?![A-Za-z0-9_])", text):
                ev.candidates.append(f"{path.name}:{token}")
                ev.accepted.append(f"{path.name}:{token}")

    assert ev.sources_inspected, "the probe inspected nothing - it cannot conclude anything"
    with pytest.raises(EmptyPopulationError):
        ev.require_population()


def test_the_current_model_is_a_fail_safe_default_not_a_not_null_gate():
    """The distinction that makes U0.3 impossible at Phase 0."""
    from freight_recon.lane_graduation import LaneGraduation

    grad = LaneGraduation(Path("/tmp/phase0-nonexistent-graduation.json"))
    assert grad.is_autonomous("tenant_a", "raise_invoice") is False, (
        "absent an explicit graduation the lane must be supervised (fail-safe). If this changed, the "
        "current model got MORE dangerous, not less."
    )
    source = Path(LaneGraduation.__module__.replace(".", "/"))
    assert "is_autonomous" in LaneGraduation.__dict__


def test_ac_ckpt_6_missing_is_deferred_by_dependency_not_waived():
    """ERRATA 4: the requirement is PRESERVED; only its phase semantics were corrected."""
    failures = manifest.expected_failures()
    assert failures["AC-CKPT-6-missing"] == "DEFERRED_BY_DEPENDENCY - REQUIRED AT PHASE 8"
    entry = next(f for f in manifest.load()["expected_acceptance_failures"]
                 if f["case"] == "AC-CKPT-6-missing")
    assert entry["green_at_phase"] == "P8"
    assert entry["accountable_unit"] == "U8.1"
    assert "P0-F1" in entry["reason"]
    assert "ZERO gates" in entry["reason"]


def test_it_is_not_marked_passed_and_not_silently_skipped():
    """The two dishonest options are both closed: it is neither green nor invisible."""
    assert "PASSED" not in manifest.expected_failures()["AC-CKPT-6-missing"]
    assert "AC-CKPT-6-missing" in manifest.expected_failures()
