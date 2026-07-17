"""U0.2 - THE TWO MIGRATION GUARDS. AC-SAFE-012 and AC-SAFE-013. RED BY DESIGN.

These are the reason Phase 0 exists before Phase 1. They RUN and they FAIL against the current
baseline, by design, and they are the plan's first green (U1.2 / U1.3).

    A guard that does not fail today is not a guard.

They are `strict` xfails, not skips. The difference matters: a skip is silence, and silence is what
let the defect live this long. A strict xfail RUNS the assertion, reports the failure by name in CI,
and - the important part - FAILS THE BUILD if it ever starts passing. So the day Phase 1 lands, this
file breaks and forces the baseline manifest to be updated deliberately. The ratchet only turns
forward.

THE DEFECT (operation_router.py::_commit_identity):
  (A) `approved_amount` is IN the commit identity. The Commit Key must identify the EFFECT, never
      the content of the decision. With the amount in the key, approving £2,850 and then £3,100 for
      the same logical invoice yields two different keys, two reservations, and TWO INVOICES.
  (B) `if not amount: return None`. A non-money effect - filing a POD - gets no commit identity at
      all, so its single-commitment cannot be enforced or proven.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freight_recon.operation_router import _commit_identity
from freight_recon.slack_delegate import CommandIntent, CommandKind
from phase0 import manifest


def _intent(**params) -> CommandIntent:
    """OPERATE is the consequential kind - the one that can reach an external effect."""
    return CommandIntent(kind=CommandKind.OPERATE, params=params)


def test_the_defect_surface_still_exists_where_the_plan_says_it_does():
    """If this fails, the plan's line references are stale and U1.2 targets the wrong code."""
    source = (Path(__file__).resolve().parents[2] / "src" / "freight_recon" / "operation_router.py").read_text()
    assert "def _commit_identity(" in source
    assert "approved_amount" in source, "the amount is no longer in _commit_identity - update DEF-1"
    assert "if not amount:" in source, "the non-money early return is gone - update DEF-2"


@pytest.mark.xfail(strict=True, reason="AC-SAFE-012: the amount is IN the commit identity (DEF-1). Green at U1.2.")
def test_ac_safe_012_commit_key_excludes_mutable_decision_values():
    """AC-SAFE-012 (FINANCIAL_CORRECTNESS, MIGRATION_GUARD).

    The frozen oracle: two proposals at £2,850 and £3,100 must yield an IDENTICAL commit key, so
    that exactly ONE invoice is ever raised. Today they yield different identities, because the
    amount is part of the identity. That is the double-pay defect, stated as a test.
    """
    intent = _intent(load_ref="LD-560010", carrier="ACME CARRIER")
    first = _commit_identity("tenant_a", "raise_invoice", intent, "2850.00")
    second = _commit_identity("tenant_a", "raise_invoice", intent, "3100.00")

    assert first is not None and second is not None
    assert first == second, (
        "AC-SAFE-012 VIOLATED: changing the approved amount changed the identity of the effect.\n"
        f"  £2,850 -> {first}\n"
        f"  £3,100 -> {second}\n"
        "The Commit Key identifies the EFFECT. The amount belongs in the Material-Facts Fingerprint."
    )


@pytest.mark.xfail(strict=True, reason="AC-SAFE-013: non-money effects get NO commit identity (DEF-2). Green at U1.3.")
def test_ac_safe_013_commit_key_exists_for_non_money_effects():
    """AC-SAFE-013 (DATA_INTEGRITY, MIGRATION_GUARD).

    The frozen oracle: filing the same POD twice produces ONE attachment. That requires the non-money
    effect to HAVE a commit key. Today `_commit_identity` returns None the moment there is no amount,
    so nothing can enforce single-commitment for it.
    """
    intent = _intent(load_ref="LD-560010", carrier="ACME CARRIER", document="POD")
    identity = _commit_identity("tenant_a", "file_document", intent, None)

    assert identity is not None, (
        "AC-SAFE-013 VIOLATED: a non-money effect (filing a POD) received NO commit identity.\n"
        "EVERY consequential effect has a Commit Key. Without one, filing the same POD twice cannot "
        "be prevented and cannot be proven to have been prevented."
    )


def test_the_amount_is_currently_part_of_the_identity_which_is_the_defect():
    """A POSITIVE assertion of the defect, so its removal cannot pass unnoticed.

    The xfails above prove the guards fail. This proves WHY, and will break loudly at U1.2 - which is
    the point: the fix must be a deliberate, visible change, not a quiet one.
    """
    intent = _intent(load_ref="LD-560010", carrier="ACME CARRIER")
    identity = _commit_identity("tenant_a", "raise_invoice", intent, "2850.00")
    assert identity is not None
    assert "approved_amount" in identity, "DEF-1 appears fixed - flip AC-SAFE-012 and update the manifest"
    assert identity["approved_amount"] == "2850.00"


def test_both_guards_are_registered_as_expected_failures_with_an_owner():
    failures = manifest.expected_failures()
    assert failures["AC-SAFE-012"] == "RED_BY_DESIGN"
    assert failures["AC-SAFE-013"] == "RED_BY_DESIGN"
    by_case = {f["case"]: f for f in manifest.load()["expected_acceptance_failures"]}
    assert by_case["AC-SAFE-012"]["green_at_phase"] == "P1"
    assert by_case["AC-SAFE-012"]["accountable_unit"] == "U1.2"
    assert by_case["AC-SAFE-013"]["accountable_unit"] == "U1.3"


def test_the_test_that_encodes_the_defect_is_recorded_for_inversion():
    """DEF-3 / U1.4: a test currently asserts the defect and will fight the fix."""
    lane_test = Path(__file__).resolve().parents[1] / "tests" / "test_lane_graduation.py"
    assert lane_test.exists()
    defects = {d["id"]: d for d in manifest.load()["expected_current_defects"]}
    assert defects["DEF-3"]["accountable_unit"] == "U1.4"
