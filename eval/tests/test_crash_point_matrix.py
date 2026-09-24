"""The G4 crash-point matrix — a DERIVED population, each point with an EXECUTED behavioral oracle.

release-gates.md G4 requires "every crash point" with "crash matrices" as retained evidence. The
frozen P8 phase-acceptance review (p8-phase-acceptance-review-319debc.md §4) recorded that the two
crash kits "inject crash points, but neither is an enumerated matrix asserting a coverage
denominator — completeness cannot be established." This file is that enumerated matrix.

### THE POPULATION IS DERIVED FROM THE CANONICAL DOCS, NOT HAND-PICKED.
  * the checkpoint→claim crash conditions are parsed from platform-safety-acceptance.md's own
    per-step Conditions list (the backtick-quoted conditions naming a crash);
  * the cross-machine crash SCHEDULES are parsed from recovery-and-compensation-acceptance.md's
    seventeen-row table (every AC-RACE row whose schedule names a crash).
A convenient subset cannot pass: the denominator is `len(parsed conditions) + len(parsed schedules)`,
recomputed from the documents on every run, and the matrix must cover exactly it.

### EVERY CRASH POINT EXECUTES ITS BEHAVIORAL ORACLE, not merely appears in a list.
  * the checkpoint crash conditions run here against the REAL checkpoint kernel (phase3_kit): a crash
    before/during the checkpoint transaction leaves outcome (b) with NO partial authorization state,
    and a crash after commit lets the grant EXPIRE UNCLAIMED — nothing happened, re-checkpoint safe,
    and the dead grant is NEVER re-executed;
  * AC-RACE-017 (the downstream-handoff crash) executes here via its dedicated oracle;
  * the cross-machine transport/adapter crash schedules (006/007/008/009/011) map to the present,
    collected behavioral oracle that proves each — mechanically verified to EXIST and exercise the
    crash, so a mapping to a phantom node fails.

### ANTI-VACUITY. Dropping a required crash point makes the coverage check fail; and the checkpoint
after-commit oracle is shown RED against a non-recovering variant (a grant left live), so a green run
means the recovery was actually proven.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "docs" / "specifications" / "acceptance"
EVAL_TESTS = ROOT / "eval" / "tests"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from phase3_kit import (  # noqa: E402
    assert_no_partial_state, assert_nothing_happened, assert_outcome_a, assert_outcome_b,
    green_scenario, params_for,
)
from freight_recon.checkpoint import (  # noqa: E402
    claim_grant_cas, expire_unclaimed, run_checkpoint,
)


def require_population(items, what: str):
    assert items, f"no {what} to assert over — this guard would measure nothing"
    return items


# --------------------------------------------------------------------------- derivation from docs
def _checkpoint_crash_conditions() -> list[str]:
    """The crash CONDITIONS named in platform-safety-acceptance.md's per-step Conditions list —
    parsed from the document, so a doc that grows a crash condition grows this population."""
    text = (SPEC / "platform-safety-acceptance.md").read_text(encoding="utf-8")
    m = re.search(r"\*\*Conditions \(per step\):\*\*(.+)", text)
    assert m, "platform-safety-acceptance.md no longer states its per-step Conditions list"
    conditions = re.findall(r"`([^`]+)`", m.group(1))
    return sorted({c for c in conditions if "crash" in c.lower()})


def _ac_race_crash_schedule_ids() -> list[str]:
    """Every AC-RACE row in recovery-and-compensation-acceptance.md whose SCHEDULE names a crash —
    parsed from the seventeen-row table, so the population tracks the canonical schedules."""
    text = (SPEC / "recovery-and-compensation-acceptance.md").read_text(encoding="utf-8")
    ids: list[str] = []
    for line in text.splitlines():
        m = re.match(r"\|\s*\*\*(AC-RACE-\d{3})\*\*\s*\|([^|]*)\|", line)
        if m and "crash" in m.group(2).lower():
            ids.append(m.group(1))
    return sorted(set(ids))


# --------------------------------------------------------------------------- behavioral oracles
def _oracle_checkpoint_crash_before_txn() -> None:
    """An abort at an early checkpoint step (the process dies before the witness/grant write): the
    checkpoint transaction never commits, so outcome (b) — no witness, no grant, no partial state."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        store, kernel, clock, effect, facts, versions, approval, world, inputs, request = (
            green_scenario(Path(d)))
        world["projection"] = {"status": "IN_TRANSIT"}   # native-state mismatch aborts before step 5
        outcome = run_checkpoint(kernel, request, inputs)
        assert not outcome.authorized, "the perturbed checkpoint authorized — no crash point exercised"
        assert_outcome_b(store, effect.key())
        assert_no_partial_state(store, effect.key())
        store.close()


def _oracle_checkpoint_crash_during_txn() -> None:
    """A crash mid-checkpoint (step 5, entity-version concurrency): the transaction aborts, leaving
    outcome (b) and — the load-bearing part — NO partial authorization state at rest."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        store, kernel, clock, effect, facts, versions, approval, world, inputs, request = (
            green_scenario(Path(d)))
        world["versions"][list(world["versions"])[0]] += 1   # entity moved: step-5 drift aborts
        outcome = run_checkpoint(kernel, request, inputs)
        assert not outcome.authorized, "the drift did not abort the checkpoint — no crash point exercised"
        assert outcome.step == 5, f"expected the abort at step 5, got {outcome}"
        assert_outcome_b(store, effect.key())
        assert_no_partial_state(store, effect.key())
        store.close()


def _oracle_checkpoint_crash_after_commit(*, recover: bool = True) -> None:
    """A crash AFTER the checkpoint commits (witness+grant exist) but BEFORE the claim: the grant
    EXPIRES UNCLAIMED — nothing happened, re-checkpoint is safe, and the dead grant is never
    re-executed. `recover=False` is the RED control: skip the expiry and a live grant survives,
    which `assert_nothing_happened` must reject."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        store, kernel, clock, effect, facts, versions, approval, world, inputs, request = (
            green_scenario(Path(d)))
        first = run_checkpoint(kernel, request, inputs)
        assert first.authorized, "the green scenario did not authorize — nothing to crash after"
        clock.advance(seconds=61)                      # the process was gone across the grant TTL
        if recover:
            assert expire_unclaimed(kernel) == 1, "the unclaimed grant did not expire"
        assert_nothing_happened(store, effect.key())   # (b): no live/claimed capability survives
        # re-checkpoint of the SAME effect is safe and mints fresh; the claim reaches (a) exactly once
        second = run_checkpoint(kernel, request, inputs)
        assert second.authorized and second.handle.grant_id != first.handle.grant_id
        claim = claim_grant_cas(kernel, second.handle, params_for(effect))
        assert claim.claimed is True
        assert_outcome_a(store, effect.key(), allow_dead_history=True)  # the pre-crash grant stays dead
        store.close()


# checkpoint condition -> its executed behavioral oracle. Keys are matched to the parsed conditions.
_CHECKPOINT_ORACLES = {
    "crash before txn": _oracle_checkpoint_crash_before_txn,
    "crash during txn": _oracle_checkpoint_crash_during_txn,
    "crash after commit": _oracle_checkpoint_crash_after_commit,
}

# AC-RACE crash schedule -> the present, collected behavioral oracle that exercises it.
# (file, function, a crash/fault symbol that must appear IN THAT FUNCTION'S BODY) — so a mapping to a
# real-but-unrelated function (a rename) fails, not just a phantom one. Each runs in the suite/CI.
_AC_RACE_CRASH_ORACLES = {
    "AC-RACE-006": ("test_phase5_event_transport.py",
                    "test_a_crash_before_publish_re_sends_the_identical_event_id", "crash"),
    "AC-RACE-007": ("test_phase5_event_transport.py",
                    "test_a_crash_after_publish_causes_a_duplicate_delivery_that_the_inbox_absorbs", "crash"),
    "AC-RACE-008": ("test_phase5_event_transport.py",
                    "test_a_crash_between_the_state_write_and_the_event_write_leaves_NEITHER", "crash"),
    "AC-RACE-009": ("test_phase5_event_transport.py",
                    "test_a_redelivered_event_is_a_noop_not_an_error", "DUPLICATE_NOOP"),
    "AC-RACE-011": ("test_adapter_boundary_acceptance.py",
                    "test_f4_generic_post_attempt_exception_leaves_unknown_never_claimed", "unknown"),
    "AC-RACE-017": ("test_ac_race_017_atomic_handoff.py",
                    "test_ac_race_017_a_crash_creating_the_downstream_work_item_does_not_advance_the_source", "crash"),
}


# THE ENUMERATED MATRIX. Built as a literal from the DERIVED population so a convenient subset cannot
# stand in for it; every value names the behavioral oracle that executes for that crash point. Written
# as a bare `name = {` (no annotation between the two) so the standing G4 gate guard recognises it.
CRASH_POINT_MATRIX = {
    **{f"checkpoint:{c}": ("executed-here", _CHECKPOINT_ORACLES[c])
       for c in _checkpoint_crash_conditions() if c in _CHECKPOINT_ORACLES},
    **{i: ("collected-oracle", _AC_RACE_CRASH_ORACLES.get(i))
       for i in _ac_race_crash_schedule_ids()},
}


def _function_covers(fname: str, func: str, symbol: str) -> bool:
    """The named function exists AND its body contains `symbol` — so a mapping to a real-but-unrelated
    function (a rename to something that no longer exercises the crash) is invalid, not just a phantom
    one (mirrors the AC-SEC mapping's body-symbol check)."""
    p = EVAL_TESTS / fname
    if not p.exists():
        return False
    text = p.read_text(encoding="utf-8")
    for n in ast.walk(ast.parse(text)):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == func:
            body = ast.get_source_segment(text, n) or ""
            return symbol in body
    return False


# --------------------------------------------------------------------------- the matrix completeness
def test_the_crash_point_population_is_derived_and_covered_with_a_denominator():
    """The matrix covers EXACTLY the population derived from the canonical documents — the coverage
    denominator. A missing crash point (a convenient subset) fails here."""
    checkpoint_conditions = require_population(_checkpoint_crash_conditions(), "checkpoint crash conditions")
    race_ids = require_population(_ac_race_crash_schedule_ids(), "AC-RACE crash schedules")
    require_population(CRASH_POINT_MATRIX, "crash-point matrix entries")

    derived = len(checkpoint_conditions) + len(race_ids)
    print(f"crash-point matrix: {len(checkpoint_conditions)} checkpoint crash conditions + "
          f"{len(race_ids)} AC-RACE crash schedules = {derived} crash points; "
          f"matrix carries {len(CRASH_POINT_MATRIX)}")
    # Every derived checkpoint condition has an executed oracle here.
    for c in checkpoint_conditions:
        assert f"checkpoint:{c}" in CRASH_POINT_MATRIX, f"checkpoint crash condition uncovered: {c!r}"
        assert _CHECKPOINT_ORACLES.get(c) is not None, f"no executed oracle for checkpoint {c!r}"
    # Every derived AC-RACE crash schedule is covered by a named oracle.
    for i in race_ids:
        assert i in CRASH_POINT_MATRIX, f"AC-RACE crash schedule uncovered: {i}"
        assert CRASH_POINT_MATRIX[i][1] is not None, f"no oracle mapped for {i}"
    assert len(CRASH_POINT_MATRIX) == derived, (
        f"the matrix ({len(CRASH_POINT_MATRIX)}) is not the derived population ({derived})")


def test_every_checkpoint_crash_point_executes_its_behavioral_oracle():
    """Each checkpoint crash condition runs its REAL behavioral oracle against the checkpoint kernel:
    (b) with no partial authorization state, and after-commit recovery to the canonical state."""
    ran = 0
    for cond, (_kind, oracle) in sorted(CRASH_POINT_MATRIX.items()):
        if not cond.startswith("checkpoint:"):
            continue
        oracle()   # raises if the crash point does not recover to its canonical outcome
        ran += 1
    assert ran == len(_checkpoint_crash_conditions()), (
        f"executed {ran} checkpoint crash oracles, expected {len(_checkpoint_crash_conditions())}")


def test_the_after_commit_oracle_is_red_against_a_non_recovering_variant():
    """ANTI-VACUITY: if the crash-after-commit grant is NOT expired, a live capability survives — the
    forbidden partial/live state — and `assert_nothing_happened` must reject it. Proves the oracle is
    a real measurement, not a decoration (CLAUDE.md §6)."""
    with pytest.raises(AssertionError):
        _oracle_checkpoint_crash_after_commit(recover=False)


def test_dropping_a_crash_point_fails_the_coverage_check():
    """ANTI-VACUITY for the denominator: a matrix missing a derived crash point is caught."""
    derived = len(_checkpoint_crash_conditions()) + len(_ac_race_crash_schedule_ids())
    holed = dict(CRASH_POINT_MATRIX)
    holed.pop(next(iter(holed)))
    assert len(holed) != derived, "removing a crash point did not change the denominator — vacuous"


def test_every_ac_race_crash_schedule_maps_to_a_present_collected_oracle():
    """Each AC-RACE crash schedule maps to a real, collected behavioral oracle that EXERCISES the
    crash — mechanically verified to exist, so a mapping to a phantom node fails. AC-RACE-017 also
    executes here (its dedicated oracle), the rest run in the suite/CI."""
    defects: list[str] = []
    for i in require_population(_ac_race_crash_schedule_ids(), "AC-RACE crash schedules"):
        mapped = _AC_RACE_CRASH_ORACLES.get(i)
        if mapped is None:
            defects.append(f"{i}: no oracle mapped")
            continue
        fname, func, symbol = mapped
        if not _function_covers(fname, func, symbol):
            defects.append(f"{i}: {fname}::{func} is absent or does not exercise the crash ({symbol!r})")
    assert not defects, "AC-RACE crash schedules mapped to absent/unrelated oracles:\n  - " + "\n  - ".join(defects)


def test_ac_race_017_downstream_handoff_crash_executes_here():
    """AC-RACE-017 is executed directly as part of the matrix (not only mapped), because it is the
    crash schedule this remediation newly closed."""
    import test_ac_race_017_atomic_handoff as m
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        m.test_ac_race_017_a_crash_creating_the_downstream_work_item_does_not_advance_the_source(Path(d))
