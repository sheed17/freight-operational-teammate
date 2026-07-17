"""U0.13 - the guards guard themselves.

Found by the Phase-0 mutation harness: two ways to disarm this suite silently.

  1. Replace a MIGRATION_GUARD's `xfail(strict=True)` with `skip`. The suite stays green, CI reports
     nothing, and the guard that was supposed to fail today simply stops speaking. A skip is silence,
     and silence is what let the commit-key defect live this long.
  2. Let the manifest's two sections drift. DEF-2 (expected_current_defects) and AC-SAFE-013
     (expected_acceptance_failures) describe the SAME defect. Nothing made them agree, so one could
     be moved to a later phase while the other still claimed P1.

Neither mutation was detected until these tests existed. A guard that can be turned off without
anyone noticing is not a guard.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase0 import manifest

TESTS = Path(__file__).resolve().parent
GUARD_FILES = sorted(TESTS.glob("test_phase0_*.py"))

# The cases that MUST run and fail today. Neutering one is the defect this file exists to catch.
STRICT_XFAIL_CASES = {
    "test_ac_safe_012_commit_key_excludes_mutable_decision_values": "AC-SAFE-012",
    "test_ac_safe_013_commit_key_exists_for_non_money_effects": "AC-SAFE-013",
    "test_declared_transition_total_matches_the_enumeration": "DEF-4",
    "test_declared_emitted_event_total_matches_the_enumeration": "DEF-5",
}


def test_the_guard_suite_is_not_empty():
    assert len(GUARD_FILES) >= 9, f"only {len(GUARD_FILES)} Phase-0 guard files found"


def test_no_phase0_guard_is_skipped():
    """REG-7's sibling. `skip` and `skipif` are banned in the Phase-0 suite: they are silence."""
    offenders = []
    for path in GUARD_FILES:
        for i, line in enumerate(path.read_text(encoding="utf-8").split("\n"), start=1):
            if re.search(r"@pytest\.mark\.skip(if)?\b", line):
                offenders.append(f"{path.name}:{i}")
    assert not offenders, (
        f"Phase-0 guard(s) disarmed with skip: {offenders}\n"
        "A skipped guard reports nothing and fails nothing. Use xfail(strict=True) so the case RUNS, "
        "is named in CI, and BREAKS THE BUILD the day it starts passing."
    )


def test_the_red_by_design_cases_are_strict_xfails():
    """They must RUN and FAIL - and fail the build if they ever silently start passing."""
    found = {}
    for path in GUARD_FILES:
        text = path.read_text(encoding="utf-8")
        for name in STRICT_XFAIL_CASES:
            m = re.search(rf"(@pytest\.mark\.\w+\([^)]*\)\s*\n)?def {re.escape(name)}\(", text)
            if not m:
                continue
            block = text[max(0, m.start() - 400):m.end()]
            found[name] = block
    missing = set(STRICT_XFAIL_CASES) - set(found)
    assert not missing, f"red-by-design case(s) vanished from the suite: {sorted(missing)}"
    for name, block in found.items():
        assert "xfail" in block, f"{name} ({STRICT_XFAIL_CASES[name]}) is no longer an xfail"
        assert "strict=True" in block, (
            f"{name} ({STRICT_XFAIL_CASES[name]}) is a non-strict xfail. Non-strict means it can "
            f"start passing and nobody is told - so the fix would land unrecorded."
        )


def test_no_guard_swallows_its_own_assertion():
    """`except AssertionError: pass` is a guard that reports success no matter what."""
    offenders = []
    for path in GUARD_FILES:
        text = path.read_text(encoding="utf-8")
        if re.search(r"except\s+(AssertionError|Exception)\s*:\s*\n\s*pass", text):
            offenders.append(path.name)
    assert not offenders, f"guard(s) swallowing assertions: {offenders}"


def test_the_manifest_sections_agree_about_every_case():
    """Cross-section consistency: the same defect may not be at P1 here and P9 there."""
    defects = {d["id"]: d for d in manifest.load()["expected_current_defects"]}
    failures = {f["case"]: f for f in manifest.load()["expected_acceptance_failures"]}

    # A defect and its acceptance case must agree on the PHASE. They need not agree on the unit:
    # several defects can legitimately share one case (DEF-1 is the defect itself, fixed by U1.2;
    # DEF-3 is the test that encodes it, inverted by U1.4 - both are AC-SAFE-012).
    linked = [(d, defects[d]["acceptance"]) for d in defects if defects[d].get("acceptance")]
    checked = 0
    for def_id, case in linked:
        if case not in failures:
            continue
        d, f = defects[def_id], failures[case]
        checked += 1
        assert d["removed_by_phase"] == f["green_at_phase"], (
            f"{def_id} says the defect clears at {d['removed_by_phase']} but {case} says it goes "
            f"green at {f['green_at_phase']}. The manifest's two sections have drifted."
        )
    assert checked >= 3, f"only {checked} linked defect/case pairs were compared - too few to prove anything"

    # Where exactly ONE defect owns a case, the unit must match - otherwise nobody owns the fix.
    owners: dict[str, list[str]] = {}
    for def_id, case in linked:
        owners.setdefault(case, []).append(def_id)
    for case, ids in owners.items():
        if len(ids) != 1 or case not in failures:
            continue
        assert defects[ids[0]]["accountable_unit"] == failures[case]["accountable_unit"], (
            f"{ids[0]} and {case} name different accountable units: "
            f"{defects[ids[0]]['accountable_unit']} vs {failures[case]['accountable_unit']}"
        )


def test_every_expected_failure_has_a_test_that_actually_runs_it():
    """An 'expected failure' with no executing test is a claim, not a guard."""
    all_text = "\n".join(p.read_text(encoding="utf-8") for p in GUARD_FILES)
    for case in ("AC-SAFE-012", "AC-SAFE-013", "AC-SEC-001", "AC-CKPT-6-missing"):
        assert case in all_text, f"{case} is declared an expected failure but no guard mentions it"
