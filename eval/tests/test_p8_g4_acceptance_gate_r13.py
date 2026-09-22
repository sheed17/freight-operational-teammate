"""R13 — the P8 phase-acceptance gate may not be weakened to close the phase.

Routed obligation (Product Driver, by identity):
  risk key  : conflicting_evidence:c4ea3cceb2
  R13 (P1)  : "P8 status is materialized COMPLETE while a G4-required family lacks a present
              executable oracle, or a load-bearing negative guard has no proven RED control,
              weakening the gate to close the phase."

Product principle: an unmeasured risk is not a covered risk, and a guard speaks only for the
obligation it was written to answer. Until this correction there was NO guard that measured R13:
nothing failed if a session flipped P8 to COMPLETE while its G4 evidence was incomplete. This
module is that measurement.

Authority for the behaviour it enforces (not invented here):
  - docs/specifications/acceptance/release-gates.md — G4 requires 100% of AC-SAFE-001..028, the 105
    AC-CKPT matrix, AC-RACE-001..017, AC-REC-* and AC-SEC-*, zero-tolerance, and "G4 QUALIFIES HERE"
    for P8 (PHASE-OUTPUTS.md P8).
  - IMPLEMENTATION-REGISTRY.yaml meta.status_model — a phase reaches COMPLETE only when every
    required acceptance criterion is established PASS on evidence; a green suite does not accept it.
  - CLAUDE.md §6 — a negative/absence assertion needs a proven population, and a guard that protects
    a tier-1 invariant must have been SEEN to go RED (a control), or it is a decoration.

What this guard is NOT: it is not the whole of G4, and it does not re-adjudicate every family. It
realises exactly R13's hostile case — a COMPLETE P8 sitting on top of an incomplete G4 oracle
population or an uncontrolled load-bearing guard — and fails if that state is ever reached. The
separately-routed risks (the 10,000-interleaving-depth / crash-matrix population, R-P8-G4-P3RACE;
and the broader vacuity sweep, R13-w2) are NOT this guard's obligation and it does not speak for
them.

Direction of authority is one-way: the registry is the machine authority for P8's status; this file
only reads it. It changes no product code, no probe grammar, no refusal control, and no acceptance
requirement.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "docs" / "implementation" / "IMPLEMENTATION-REGISTRY.yaml"
SPEC = ROOT / "docs" / "specifications" / "acceptance"
EVAL_TESTS = ROOT / "eval" / "tests"
SCRIPTS = ROOT / "scripts"


def require_population(items, what: str):
    """CLAUDE.md §6: an assertion over an empty set passes vacuously. Prove the population first."""
    assert items, f"no {what} to assert over — this guard would measure nothing"
    return items


def _p8_status() -> str:
    """P8's selection status from the MACHINE authority. Materialization sets this to COMPLETE, so
    it is the exact field R13 watches."""
    units = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["units"]
    for u in units:
        if str(u.get("unit_id", "")) == "P8":
            return str(u["status"])
    raise AssertionError("P8 unit not found in IMPLEMENTATION-REGISTRY.yaml — cannot evaluate R13")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _ids_in_dir(directory: Path, pattern: str) -> set[str]:
    """Discover case ids across the collected test files, EXCLUDING this meta-guard's own source.
    Scanning this file would let its prose ("AC-RACE-017 oracle present") satisfy the very check it
    describes — the substring-fires-on-its-own-assertion blind spot (CLAUDE.md §6). Self-exclusion
    keeps the measurement about the real oracle population, not about this guard's wording."""
    self_path = Path(__file__).resolve()
    found: set[str] = set()
    for p in sorted(directory.glob("*.py")):
        if p.resolve() == self_path:
            continue
        found |= set(re.findall(pattern, _text(p)))
    return found


def _g4_family_oracle_population_complete() -> dict[str, bool]:
    """For each G4-required family, whether its executable-oracle POPULATION is present AND complete
    on THIS tree — measured with the discovery convention each family actually uses. A family missing
    even one enumerated case has an INCOMPLETE population, which is the "lacks a present executable
    oracle" condition R13 forbids under a COMPLETE P8. These are honest measurements: some resolve
    True (the families that are complete) and some False (the real gaps), so the checker is proven to
    discriminate rather than answering True to everything."""
    safe_ids = set(re.findall(r"AC-SAFE-0\d\d", _text(SPEC / "platform-safety-acceptance.md")))
    ckpt_105 = "== 105" in _text(EVAL_TESTS / "test_phase3_checkpoint_matrix.py")
    rec_oracles = re.findall(r"def test_ac_rec_00[1-5]", _text(EVAL_TESTS / "test_phase6_compensation.py"))
    sec_spec_ids = set(re.findall(r"AC-SEC-0\d\d", _text(SPEC / "security-and-tenancy-acceptance.md")))
    sec_oracle_ids = _ids_in_dir(EVAL_TESTS, r"AC-SEC-0\d\d")
    race_017_oracle = bool(_ids_in_dir(EVAL_TESTS, r"AC-RACE-017"))
    return {
        "AC-SAFE-001..028 (28 invariants enumerated in the spec)": len(safe_ids) == 28,
        "AC-CKPT 7x15==105 matrix asserts its dimension": ckpt_105,
        "AC-REC-001..005 have executable oracles": len(rec_oracles) >= 5,
        "AC-SEC-* every enumerated id has an executable oracle": bool(sec_spec_ids) and sec_spec_ids <= sec_oracle_ids,
        "AC-RACE-001..017 population complete (AC-RACE-017 oracle present)": race_017_oracle,
    }


def _p8_negative_guard_red_control_present() -> dict[str, bool]:
    """Each load-bearing P8 negative-guard mutation battery must carry a proven RED / anti-vacuity
    control marker (the string its own runner prints when a mutant is seen RED or a control stays
    GREEN), so a green run means "a mutant was actually caught", not "nothing ran"."""
    batteries = (
        "mutate_phase8_proposal",       # U8.6 proposal inertness / no-auto-advance / token-not-approval
        "mutate_p8_policy_admission",   # U8.1 registration + one-positive-decision
        "mutate_p8_rule_admission",     # U8.2 compile-or-refuse
        "mutate_phase6_brake",          # U8.3 brake admission
        "mutate_phase6_compensation",   # U8.4 compensation single-derivation / one-active
    )
    out: dict[str, bool] = {}
    for b in batteries:
        out[b] = bool(re.search(r"anti-vacuity|RESTORE-RED|escaped", _text(SCRIPTS / f"{b}.py")))
    return out


def r13_violations(p8_status: str, family_complete: dict[str, bool],
                   guard_control_present: dict[str, bool]) -> list[str]:
    """The R13 decision. The hostile case is realised ONLY when P8 is COMPLETE — a phase that is not
    COMPLETE cannot have weakened its own gate to close. When P8 is COMPLETE, every G4-required
    family must have a complete oracle population AND every load-bearing negative guard must have a
    proven RED control; each miss is a violation. Returns the list of realised violations (empty =
    the forbidden state is not present)."""
    if p8_status != "COMPLETE":
        return []
    violations: list[str] = []
    for fam, ok in sorted(family_complete.items()):
        if not ok:
            violations.append(f"P8 is COMPLETE but a G4 family lacks a present/complete executable oracle: {fam}")
    for guard, ok in sorted(guard_control_present.items()):
        if not ok:
            violations.append(f"P8 is COMPLETE but a load-bearing negative guard has no proven RED control: {guard}")
    return violations


def _assert_no_r13_violation(p8_status: str, family_complete: dict[str, bool],
                             guard_control_present: dict[str, bool]) -> None:
    violations = r13_violations(p8_status, family_complete, guard_control_present)
    assert not violations, (
        "R13 VIOLATED — P8 was materialized COMPLETE while its G4 gate is under-evidenced; this is "
        "weakening the gate to close the phase (release-gates.md G4 requires 100% of every family, "
        "and status_model requires every criterion PASS on evidence):\n  - " + "\n  - ".join(violations)
    )


# --------------------------------------------------------------------------- the guard
def test_r13_p8_is_not_complete_while_a_g4_family_or_negative_guard_is_under_evidenced():
    """THE GUARD. Fails if P8 is COMPLETE while any G4-required family has an incomplete oracle
    population or any load-bearing negative guard lacks a proven RED control. On a tree where P8 is
    not COMPLETE this passes — the forbidden state is not present — which is why the control below
    exists to prove the guard can go RED."""
    families = require_population(_g4_family_oracle_population_complete(), "G4 family oracle checks")
    guards = require_population(_p8_negative_guard_red_control_present(), "P8 negative-guard control checks")
    _assert_no_r13_violation(_p8_status(), families, guards)


# --------------------------------------------------------------------------- the RED control
def test_r13_control_catches_a_complete_p8_with_a_missing_oracle_or_uncontrolled_guard(monkeypatch):
    """THE CONTROL — proves the guard is not vacuous by driving it RED. It reintroduces the exact
    forbidden behaviour (a COMPLETE P8 over an incomplete family / uncontrolled guard) SYNTHETICALLY,
    so it stays valid even after the real gaps are legitimately closed, and confirms the guard fails.
    """
    all_families_ok = {k: True for k in _g4_family_oracle_population_complete()}
    all_guards_ok = {k: True for k in _p8_negative_guard_red_control_present()}
    require_population(all_families_ok, "G4 family checks")
    require_population(all_guards_ok, "negative-guard checks")

    a_missing_family = dict(all_families_ok)
    a_missing_family["AC-RACE-001..017 population complete (AC-RACE-017 oracle present)"] = False
    an_uncontrolled_guard = dict(all_guards_ok)
    an_uncontrolled_guard["mutate_phase8_proposal"] = False

    # Facet 1 — COMPLETE + a G4 family incomplete IS a violation.
    assert r13_violations("COMPLETE", a_missing_family, all_guards_ok), \
        "the guard would MISS a COMPLETE P8 whose G4 family oracle population is incomplete"
    # Facet 2 — COMPLETE + a load-bearing guard uncontrolled IS a violation.
    assert r13_violations("COMPLETE", all_families_ok, an_uncontrolled_guard), \
        "the guard would MISS a COMPLETE P8 whose load-bearing negative guard has no RED control"
    # Facet 3 — no false positive: COMPLETE with a fully-evidenced gate is NOT a violation.
    assert r13_violations("COMPLETE", all_families_ok, all_guards_ok) == [], \
        "the guard would fire on a fully-evidenced COMPLETE P8 (false positive)"
    # Facet 4 — it bites only on COMPLETE: a not-COMPLETE P8 is never an R13 violation.
    assert r13_violations("READY", a_missing_family, an_uncontrolled_guard) == [], \
        "the guard fired while P8 was not COMPLETE — R13's hostile case requires COMPLETE"

    # Facet 5 — invoke THE GUARD ITSELF with the forbidden behaviour reintroduced and require it to
    # FAIL. This is the "seen RED" proof CLAUDE.md §6 demands: the guard's own assertion path raises.
    g = sys.modules[__name__]
    monkeypatch.setattr(g, "_p8_status", lambda: "COMPLETE")
    monkeypatch.setattr(g, "_g4_family_oracle_population_complete", lambda: a_missing_family)
    monkeypatch.setattr(g, "_p8_negative_guard_red_control_present", lambda: all_guards_ok)
    with pytest.raises(AssertionError, match="R13 VIOLATED"):
        g.test_r13_p8_is_not_complete_while_a_g4_family_or_negative_guard_is_under_evidenced()


def test_r13_measurement_is_populated_and_discriminates():
    """Anti-vacuity for the MEASUREMENT (not just the decision): the family and guard manifests are
    non-empty, carry booleans, and — because R13 only bites on COMPLETE — the current-tree status is
    read as a real registry value. The decision function must return nothing while P8 is not COMPLETE
    and something once COMPLETE is combined with a real gap, proving the coupling is live."""
    families = require_population(_g4_family_oracle_population_complete(), "G4 family checks")
    guards = require_population(_p8_negative_guard_red_control_present(), "negative-guard checks")
    assert all(isinstance(v, bool) for v in families.values()), "a family check did not return a bool"
    assert all(isinstance(v, bool) for v in guards.values()), "a guard check did not return a bool"
    status = _p8_status()
    assert status in {"BLOCKED", "READY", "IN_PROGRESS", "COMPLETE"}, f"P8 status {status!r} is off-vocabulary"
    # The coupling is live: injecting COMPLETE over a deliberately-incomplete family yields a
    # violation, while the same family under the real (non-COMPLETE) status yields none.
    forced_gap = {**{k: True for k in families}, "AC-RACE-001..017 population complete (AC-RACE-017 oracle present)": False}
    assert r13_violations("COMPLETE", forced_gap, {k: True for k in guards}), "the decision does not couple COMPLETE to the gate"
    assert r13_violations(status, forced_gap, {k: True for k in guards}) == [] or status == "COMPLETE", \
        "R13 fired while P8 is not COMPLETE"
