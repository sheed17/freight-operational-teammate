"""The guard-integrity meta-guard: a safety guard may not be silently disarmed.

This file used to carry a hand-maintained RETAIN/UPDATE/REPLACE/REMOVE_AS_SUPERSEDED
classification for every guard module, plus prose justifications for each. That was repository
bookkeeping: the classification told nobody whether the code was safe, and it had to be edited
every time a file was added or removed. It went in the 2026-08 engineering-process simplification.

What survives is the part that protects runtime safety: guards are DISCOVERED, and a discovered
guard may not be skipped, xfailed or emptied. A disabled guard is silence, and silence is not a
pass. Phase-1 guards get the extra check because Phase 1 is forward-only - the amount left the
Commit Key, and no later change may relax the tests that hold it out.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parents[1]

GUARD_PREFIXES = ("test_phase0_", "test_phase1_", "test_u26a_", "test_u26bc_", "test_phase2_",
                  "test_phase3_", "test_phase5_", "test_phase6_", "test_p4_", "test_p5_",
                  "test_p6_")


def guard_files() -> list[str]:
    """DISCOVERED, never listed: phase-prefixed modules UNION every control-guard module the
    central inventory discovers by what it references. A new guard enters automatically."""
    sys.path.insert(0, str(ROOT / "eval"))
    from control import inventory as _inv
    names = {p.name for p in TESTS.glob("test_*.py") if p.name.startswith(GUARD_PREFIXES)}
    names |= {f.rsplit("/", 1)[-1] for f in _inv.control_guard_modules()}
    assert len(names) >= 20, "guard-file discovery collapsed"
    return sorted(names)


def _tests_in(name: str) -> list[ast.FunctionDef]:
    tree = ast.parse((TESTS / name).read_text(encoding="utf-8"))
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]


def test_the_guard_population_is_discovered_and_nonempty():
    found = guard_files()
    assert found, "no guard files discovered - every test below would pass over an empty set"
    missing = [f for f in found if not (TESTS / f).exists()]
    assert not missing, f"discovery named files that do not exist: {missing}"


def test_no_discovered_guard_is_skipped_or_xfailed():
    """Originally this only failed when EVERY test in a file was disabled - so skipping one
    load-bearing guard passed. Mutation caught it. Any disabled guard now fails."""
    offenders = []
    for name in guard_files():
        for n in _tests_in(name):
            if any("mark.skip" in ast.unparse(d) or "mark.xfail" in ast.unparse(d)
                   for d in n.decorator_list):
                offenders.append(f"{name}::{n.name}")
    assert not offenders, f"disabled guard(s) - silence is not a pass: {offenders}"


def test_no_discovered_guard_file_has_been_emptied_of_assertions():
    """Deleting the bodies is the other way to keep a green file that proves nothing."""
    offenders = []
    for name in guard_files():
        tests = _tests_in(name)
        if not tests:
            continue
        for n in tests:
            if not any(isinstance(x, (ast.Assert, ast.Raise, ast.Call)) for x in ast.walk(n)):
                offenders.append(f"{name}::{n.name}")
    assert not offenders, f"guard test(s) with no assertion and no call: {offenders}"


def test_the_phase_1_commit_key_guards_are_present_and_never_downgraded():
    """Phase 1 is forward-only: this is the defect that raised two invoices."""
    phase1 = [f for f in guard_files() if f.startswith("test_phase1_")]
    assert len(phase1) >= 3, f"the Phase-1 guard set shrank to {phase1}"
    for name in phase1:
        assert _tests_in(name), f"{name} has no tests left"
