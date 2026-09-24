"""R-P8-G4-P3RACE — the P8 gate may not close on an unproven AC-CKPT / AC-RACE-breadth / crash-point
population.

Routed obligation (Product Driver, by identity):
  risk key         : conflicting_evidence:50b9a58648
  R-P8-G4-P3RACE(P1): "G4 also requires the AC-CKPT 105-case matrix, the AC-RACE
                      10,000-interleaving-per-race population beyond the brake race, and the required
                      crash-point matrices; the approved command set offers no P3 claim-CAS/checkpoint
                      mutation control and no crash-matrix driver, so their completeness cannot be
                      independently re-derived here beyond running the existing suite."

This is a distinct obligation from R13 (which measures the AC-SEC / AC-RACE-017 oracle presence and
the negative-guard RED controls) and R13-w2 (which measures the BRAKE race's 10,000-interleaving
depth and the negative-guard batteries' seen-RED standing). Neither reads the three completeness
populations this obligation names, coupled to a COMPLETE P8:

  (A) the AC-CKPT 105-case matrix is present and COMPLETE as a standing oracle -- exactly 7x15==105
      parametrized cells with per-cell anti-vacuity, not merely "some checkpoint cases".
  (B) the AC-RACE 10,000-interleaving population BEYOND the brake race -- the P3 claim-CAS /
      checkpoint races (AC-RACE-001/003/004) -- is established by a standing oracle at the declared
      depth. A claim-CAS race run at 2 or 8 threads is not the declared 10,000-interleaving
      population.
  (C) the required crash-point matrices exist as a standing oracle that ENUMERATES the crash points
      and asserts a coverage denominator -- not crash flags injected one test at a time with no
      proven population.

Authority (not invented here): release-gates.md G4 (the 105 AC-CKPT matrix; AC-RACE-001..017 at
10,000 interleavings per race; every crash point + crash matrices); recovery-and-compensation-
acceptance.md (AC-RACE schedules are EXACT and a non-deterministic run FAILS); platform-safety-
acceptance.md (the 7x15 checkpoint matrix); acceptance/registry.md (the ORACLE RULE; a negative
assertion needs a proven population); CLAUDE.md sec 6 (prove the population's denominator).

Scope: this guard realises R-P8-G4-P3RACE's hostile case and fails if it is realised (P8 COMPLETE
while one of the three populations is not established as a standing oracle). It does not speak for
R13 or R13-w2 (their own files). It reads the machine authority only; it changes no product code,
probe grammar, refusal control or acceptance requirement.

Hygiene (CLAUDE.md sec 6): every directory scan EXCLUDES this file and the sibling acceptance-gate
meta-guards (which name these populations as their SUBJECT, not by exercising them); the AC-CKPT
dimension and the declared race depth are computed, not written; and the only test-node-id tokens
in this file are its three real tests -- so neither the substring-self-reference blind spot nor a
phantom node id can occur.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "docs" / "implementation" / "IMPLEMENTATION-REGISTRY.yaml"
EVAL_TESTS = ROOT / "eval" / "tests"
CI_YML = ROOT / ".github" / "workflows" / "ci.yml"
_SELF = Path(__file__).name
_BRAKE_RACE_FILE = "test_phase3_brake.py"     # the brake race is R13-w2's subject, not "beyond" it
_CKPT_MATRIX_FILE = "test_phase3_checkpoint_matrix.py"


def require_population(items, what: str):
    assert items, f"no {what} to assert over -- this guard would measure nothing"
    return items


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _p8_status() -> str:
    units = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["units"]
    for u in units:
        if str(u.get("unit_id", "")) == "P8":
            return str(u["status"])
    raise AssertionError("P8 unit not found in IMPLEMENTATION-REGISTRY.yaml -- cannot evaluate R-P8-G4-P3RACE")


def _sibling_suite_files(exclude: tuple[str, ...] = ()) -> list[tuple[str, str]]:
    """(name, text) for every collected test file EXCEPT this one, the sibling acceptance-gate
    meta-guards, and any explicitly excluded name. Excluding the acceptance-gate meta-guards is
    essential: they name the AC-CKPT/AC-RACE populations and the race depth as their SUBJECT, so
    counting those mentions would let a population read as 'established' merely because a meta-guard
    describes it (the substring-self-reference blind spot, CLAUDE.md sec 6)."""
    out: list[tuple[str, str]] = []
    for p in sorted(EVAL_TESTS.glob("*.py")):
        if p.name == _SELF or "acceptance_gate" in p.name or p.name in exclude:
            continue
        out.append((p.name, _text(p)))
    return out


def _ac_ckpt_105_matrix_complete_standing() -> bool:
    """(A) The AC-CKPT matrix is present and complete: exactly 7x15 == the declared 105 cells,
    double-parametrized, with a per-cell anti-vacuity raise so no cell passes without a real
    perturbation. Reads the canonical matrix oracle file directly (not a scan)."""
    declared = 7 * 15  # steps x conditions (platform-safety-acceptance.md); computed, not written
    t = _text(EVAL_TESTS / _CKPT_MATRIX_FILE)
    if not t:
        return False
    dimension = re.search(r"len\(STEPS\)\s*\*\s*len\(CONDITIONS\)\s*==\s*(\d+)", t)
    dimension_ok = bool(dimension) and int(dimension.group(1)) == declared
    double_param = t.count("@pytest.mark.parametrize") >= 2
    per_cell_anti_vacuity = "no perturbation defined" in t
    return dimension_ok and double_param and per_cell_anti_vacuity


def _ac_race_beyond_brake_10k_standing() -> bool:
    """(B) A NON-brake race (the P3 claim-CAS / checkpoint races) is exercised at >= the declared
    10,000 interleavings by a standing oracle -- a collected test (brake test and meta-guards
    excluded) or a CI step. A claim-CAS race at 2/8 threads is not the declared population."""
    declared_depth = 10 ** 4  # 10,000 interleavings per race (release-gates.md G4 / AC-RACE-002)
    race_ctx = re.compile(r"interleav|run_race|racing|never both, never neither|claim.*cas|Barrier", re.I)
    for _name, t in _sibling_suite_files(exclude=(_BRAKE_RACE_FILE,)):
        if not race_ctx.search(t):
            continue
        depths = [int(n) for n in re.findall(r"range\(\s*(\d{4,})\s*\)", t)]
        depths += [int(n) for n in re.findall(r"repeat\s*=\s*(\d{4,})", t)]
        depths += [int(n) for n in re.findall(r"Barrier\(\s*(\d{4,})\s*\)", t)]
        if any(d >= declared_depth for d in depths):
            return True
    ci = _text(CI_YML)
    # a CI race step at >= the declared depth that is NOT the brake probe
    for line in ci.splitlines():
        if "probe_phase6_brake" in line:
            continue
        m = re.search(r"--repeat\s+(\d+)", line)
        if m and int(m.group(1)) >= declared_depth:
            return True
    return False


def _crash_point_matrix_denominator_standing() -> bool:
    """(C) A crash-point MATRIX exists as a standing oracle: a collected test ENUMERATES the crash
    points as a population and asserts a coverage denominator over them. Crash flags injected one
    test at a time, with no enumerated population, are not a matrix (CLAUDE.md sec 6: a negative
    assertion needs a proven denominator)."""
    # Require an ACTUAL enumerated population: a variable whose name contains crash + point/matrix,
    # ASSIGNED a collection literal ([ ( or {), plus a coverage denominator over it. A prose mention
    # or a parametrize arg named "crash_point" (test_phase6_conflict.py:619) followed by an unrelated
    # assert-len must NOT count -- that is the manifest/prose-mention pollution CLAUDE.md sec 6 names.
    pop_assign = re.compile(r"\w*crash\w*(?:point|matrix)\w*\s*[:=]\s*[\[\({]", re.I)
    denominator = re.compile(r"assert\s+len\(|require_population\(|== len\(")
    for _name, t in _sibling_suite_files():
        if pop_assign.search(t) and denominator.search(t):
            return True
    return False


def p3race_violations(p8_status: str, ac_ckpt_ok: bool, ac_race_beyond_brake_ok: bool,
                      crash_matrix_ok: bool) -> list[str]:
    """The R-P8-G4-P3RACE decision. The hostile case is realised ONLY when P8 is COMPLETE. When it
    is, all three G4 completeness populations must be established by a standing oracle; each miss
    weakens the gate to close the phase."""
    if p8_status != "COMPLETE":
        return []
    violations: list[str] = []
    if not ac_ckpt_ok:
        violations.append("P8 is COMPLETE but the AC-CKPT 105-case matrix is not established complete by a standing oracle")
    if not ac_race_beyond_brake_ok:
        violations.append("P8 is COMPLETE but the AC-RACE 10,000-interleaving population BEYOND the brake race "
                          "(the P3 claim-CAS/checkpoint races) is not established by any standing oracle")
    if not crash_matrix_ok:
        violations.append("P8 is COMPLETE but the required crash-point matrix (an enumerated crash-point "
                          "population with a coverage denominator) is not established by any standing oracle")
    return violations


def _assert_no_p3race_violation(p8_status: str, ac_ckpt_ok: bool, ac_race_beyond_brake_ok: bool,
                                crash_matrix_ok: bool) -> None:
    violations = p3race_violations(p8_status, ac_ckpt_ok, ac_race_beyond_brake_ok, crash_matrix_ok)
    assert not violations, (
        "R-P8-G4-P3RACE VIOLATED -- P8 was materialized COMPLETE while a G4 completeness population "
        "cannot be independently re-derived (release-gates.md G4 requires the 105 AC-CKPT matrix, "
        "AC-RACE at 10,000 interleavings per race, and crash-point matrices):\n  - " + "\n  - ".join(violations))


# --------------------------------------------------------------------------- the guard
def test_p3race_p8_is_not_complete_while_a_g4_completeness_population_is_unestablished():
    """THE GUARD. Fails if P8 is COMPLETE while the AC-CKPT 105 matrix, the AC-RACE beyond-brake
    10,000-interleaving population, or the crash-point matrix is not established by a standing
    oracle. On a tree where P8 is not COMPLETE this passes; the control below drives it RED."""
    _assert_no_p3race_violation(
        _p8_status(),
        _ac_ckpt_105_matrix_complete_standing(),
        _ac_race_beyond_brake_10k_standing(),
        _crash_point_matrix_denominator_standing(),
    )


# --------------------------------------------------------------------------- the RED control
def test_p3race_control_catches_a_complete_p8_with_an_unestablished_population(monkeypatch):
    """THE CONTROL -- drives the guard RED to prove it is not vacuous. It reintroduces R-P8-G4-P3RACE's
    forbidden behaviour SYNTHETICALLY (a COMPLETE P8 with the AC-CKPT matrix, the beyond-brake race
    population, or the crash-point matrix unestablished), so it stays valid after the real gaps are
    closed, and confirms the guard fails."""
    # Facet 1 -- COMPLETE + AC-CKPT matrix not complete IS a violation.
    assert p3race_violations("COMPLETE", False, True, True), "the guard would MISS an incomplete AC-CKPT matrix"
    # Facet 2 -- COMPLETE + beyond-brake race population absent IS a violation.
    assert p3race_violations("COMPLETE", True, False, True), "the guard would MISS an absent beyond-brake race population"
    # Facet 3 -- COMPLETE + crash-point matrix absent IS a violation.
    assert p3race_violations("COMPLETE", True, True, False), "the guard would MISS an absent crash-point matrix"
    # Facet 4 -- no false positive: COMPLETE with all three established is NOT a violation.
    assert p3race_violations("COMPLETE", True, True, True) == [], "the guard fired on a fully-established COMPLETE P8"
    # Facet 5 -- it bites only on COMPLETE.
    assert p3race_violations("READY", False, False, False) == [], "the guard fired while P8 was not COMPLETE"

    # Facet 6 -- invoke THE GUARD ITSELF with the forbidden behaviour reintroduced and require it to FAIL.
    g = sys.modules[__name__]
    monkeypatch.setattr(g, "_p8_status", lambda: "COMPLETE")
    monkeypatch.setattr(g, "_ac_race_beyond_brake_10k_standing", lambda: False)
    with pytest.raises(AssertionError, match="R-P8-G4-P3RACE VIOLATED"):
        g.test_p3race_p8_is_not_complete_while_a_g4_completeness_population_is_unestablished()


def test_p3race_measurement_is_populated_and_reads_all_three_populations():
    """Anti-vacuity for the MEASUREMENT: each of the three checks returns a bool, P8's status reads as
    a real registry value, and the decision couples a COMPLETE status to all three populations -- so
    the guard genuinely READS ac_ckpt, the beyond-brake ac_race population, and the crash matrix, and
    discriminates rather than answering the same thing to each."""
    ckpt = _ac_ckpt_105_matrix_complete_standing()
    race = _ac_race_beyond_brake_10k_standing()
    crash = _crash_point_matrix_denominator_standing()
    assert isinstance(ckpt, bool) and isinstance(race, bool) and isinstance(crash, bool), "a check did not return a bool"
    status = _p8_status()
    assert status in {"BLOCKED", "READY", "IN_PROGRESS", "COMPLETE"}, f"P8 status {status!r} is off-vocabulary"
    # The coupling is live on all three dimensions.
    assert p3race_violations("COMPLETE", False, True, True), "no coupling to the AC-CKPT dimension"
    assert p3race_violations("COMPLETE", True, False, True), "no coupling to the beyond-brake AC-RACE dimension"
    assert p3race_violations("COMPLETE", True, True, False), "no coupling to the crash-matrix dimension"
    assert p3race_violations(status, False, False, False) == [] or status == "COMPLETE", "fired while P8 is not COMPLETE"
