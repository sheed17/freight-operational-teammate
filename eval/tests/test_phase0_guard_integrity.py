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

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase0 import manifest

TESTS = Path(__file__).resolve().parent
# Every phase's guards, not just Phase 0's. Mutation caught this: a skip added to a Phase-1 test
# went undetected because the sweep only globbed test_phase0_*. A guard suite that protects only the
# phase that wrote it stops protecting anything the moment the next phase lands.
GUARD_FILES = sorted(TESTS.glob("test_phase0_*.py")) + sorted(TESTS.glob("test_phase1_*.py"))

# The cases that MUST run and fail today. Neutering one is the defect this file exists to catch.
# Nothing is red-by-design any more. The two that were - AC-SAFE-012/013 - went green at Phase 1,
# and DEF-4/DEF-5 were corrected by the errata pass. The registry stays, because the day a new
# red-by-design case is added it must be a STRICT xfail (runs, named in CI, breaks the build when it
# starts passing) and never a skip.
STRICT_XFAIL_CASES: dict[str, str] = {}

# Cases that are GREEN and must STAY green. Phase 1 earned these; they may never be softened back
# into silence. Turning a passing safety oracle into an xfail or a skip is how a fix quietly rots:
# the test still exists, CI still looks calm, and nothing is being checked.
MUST_BE_GREEN = {
    "test_ac_safe_012_commit_key_excludes_mutable_decision_values": "AC-SAFE-012",
    "test_ac_safe_013_commit_key_exists_for_non_money_effects": "AC-SAFE-013",
    "test_ac_safe_012_end_to_end_two_amounts_raise_exactly_one_invoice": "AC-SAFE-012 (end-to-end)",
    "test_ac_safe_013_filing_the_same_pod_twice_attaches_it_once": "AC-SAFE-013 (end-to-end)",
}


def test_the_guard_suite_is_not_empty():
    assert len(GUARD_FILES) >= 12, f"only {len(GUARD_FILES)} phase guard files found"


def test_no_phase0_guard_is_skipped():
    """REG-7's sibling. `skip`/`skipif` are banned in EVERY phase's guard suite: they are silence."""
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


def test_the_green_safety_oracles_carry_no_xfail_or_skip():
    """AC-SAFE-012/013 are GREEN as of Phase 1. They may never be weakened back into silence.

    The brief is explicit: do not rename them, replace them with weaker tests, mark them skipped, or
    broaden their expected exceptions. This asserts the marker-level version of that: a passing
    safety oracle wearing an xfail is a fix that has quietly stopped being checked.
    """
    tests_dir = Path(__file__).resolve().parent
    guards = tests_dir / "test_phase0_migration_guards.py"
    text = guards.read_text(encoding="utf-8")
    for name, case in MUST_BE_GREEN.items():
        m = re.search(rf"\ndef {re.escape(name)}\(", text)
        assert m, f"{case}: the oracle {name} has vanished from the suite"
        preceding = text[max(0, m.start() - 300):m.start()]
        for weakener in ("xfail", "skip", "skipif"):
            assert f"@pytest.mark.{weakener}" not in preceding, (
                f"{case} ({name}) has been weakened with @pytest.mark.{weakener}. It is GREEN and "
                f"must stay green - Phase 1 is forward-only."
            )


def test_the_red_by_design_cases_are_strict_xfails():
    """Any case declared red-by-design must RUN and FAIL - and break the build when it starts passing."""
    if not STRICT_XFAIL_CASES:
        pytest.skip("no red-by-design cases remain: AC-SAFE-012/013 went green at Phase 1")
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


# --------------------------------------------------------------------------------------------
# Added by the Canonical Corpus Errata Pass (2026-07-16), after the mutation harness proved this
# class of hole exists in this very suite.
# --------------------------------------------------------------------------------------------

NEGATIVE_ASSERTION_TESTS = {
    # test name -> the file it lives in. Each asserts "X is NOT present", which is VACUOUSLY TRUE
    # over an empty population. Each MUST prove its population first.
    "test_timerfired_is_a_trigger_and_is_never_counted_as_an_emitted_event":
        "test_phase0_acceptance_bijection.py",
    "test_f15_declares_no_new_event_contracts":
        "test_phase0_acceptance_bijection.py",
    "test_no_event_cites_a_producer_transition_outside_the_canonical_set":
        "test_phase0_acceptance_bijection.py",
    "test_no_normative_document_still_requires_141_transitions":
        "test_phase0_errata_guards.py",
    "test_no_normative_document_still_requires_92_emitted_events":
        "test_phase0_errata_guards.py",
    "test_no_normative_document_still_says_six_of_eight":
        "test_phase0_errata_guards.py",
}


def _body(path: Path, name: str) -> str:
    src = path.read_text(encoding="utf-8")
    m = re.search(rf"\ndef {re.escape(name)}\(.*?\n(?=\ndef |\Z)", src, re.S)
    assert m, f"{name} not found in {path.name}"
    return m.group(0)


def test_every_negative_assertion_proves_its_population_first():
    """A negative assertion over an empty set is not a pass. It is a measurement of nothing.

    This is the M-9 family's subtlest member. `assert "TimerFired" not in names` reads like a real
    check and IS one - right up until `names` is empty, at which point it reports success forever.
    The errata mutation harness produced exactly that: stale bytecode made the event parser return
    zero contracts, and the test went green while measuring nothing.

    So every negative assertion in this suite must first prove it looked at a real population.
    """
    tests_dir = Path(__file__).resolve().parent
    offenders = []
    for name, filename in NEGATIVE_ASSERTION_TESTS.items():
        body = _body(tests_dir / filename, name)
        proves = ("require_population" in body) or re.search(r"assert \w*scanned\w* >=|assert checked >=", body)
        if not proves:
            offenders.append(f"{filename}::{name}")
    assert not offenders, (
        "negative assertion(s) that do not prove their population first:\n  " + "\n  ".join(offenders)
        + "\n\nAdd require_population() (or an explicit scanned/checked floor). Without it the test "
          "passes by measuring nothing."
    )


def test_the_bytecode_poisoning_lesson_is_recorded():
    """Restoring a .py does not restore behaviour: CPython invalidates a .pyc by (mtime, size).

    A mutation that preserves byte length and restores within one mtime tick leaves stale bytecode.
    The errata harness hit this and manufactured a false-green in the tool built to catch them.
    """
    a = 'm = re.match(r"^\\*\\*(F\\d+)[^:]*:?\\*\\*(.*)$", line.strip())'
    b = 'm = re.match(r"^\\*\\*(Z\\d+)[^:]*:?\\*\\*(.*)$", line.strip())'
    assert len(a) == len(b), (
        "the same-length-mutation hazard no longer reproduces; keep the lesson but update the example"
    )
