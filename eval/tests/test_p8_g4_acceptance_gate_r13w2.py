"""R13-w2 — the P8 gate may not close on a VACUOUS negative guard or an under-populated race oracle.

Routed obligation (Product Driver, by identity):
  risk key   : conflicting_evidence:ab49d00345
  R13-w2 (P1): "P8 status could be materialized COMPLETE while a load-bearing P8 negative guard
               (brake admission, policy/rule activation authority, compensation single-derivation)
               is vacuous -- passes green without any mutant/control ever seen RED -- or while a
               G4-required family (notably AC-RACE's declared 10,000-interleaving-per-race
               requirement) has no present executable oracle establishing a non-empty, complete
               population. Either weakens the gate purely to let the phase close."

This is a STRONGER, distinct obligation from R13 (conflicting_evidence:c4ea3cceb2, guarded in
test_p8_g4_acceptance_gate_r13.py). R13 required each load-bearing guard to DECLARE an anti-vacuity
marker and each G4 family to have a present oracle. R13-w2 sharpens two of those into what is
actually MEASURED here, coupled to a COMPLETE P8:

  (A) the AC-RACE race depth the gate DECLARES -- 10,000 interleavings per race
      (release-gates.md G4; recovery-and-compensation-acceptance.md AC-RACE-002) -- must be
      established as a NON-EMPTY, COMPLETE STANDING population: a collected test or a CI step that
      actually exercises a race at that depth. A probe that CAN reach the depth only by a hand-typed
      argument is not a standing population.

  (B) each named load-bearing negative-guard MUTATION battery must be EXERCISED by standing evidence
      (a CI run step or a collected test that invokes it), so a mutant is observed RED on every push.
      A battery runnable only by hand is "never seen RED" in the evidence a phase acceptance can
      re-derive -- the vacuity R13-w2 forbids.

Authority (not invented here): release-gates.md G4 (10,000 interleavings per race; 100% of every
family); IMPLEMENTATION-REGISTRY.yaml meta.status_model (COMPLETE only on evidence, never a green
suite); CLAUDE.md sec 6 (a guard protecting a tier-1 invariant must have been SEEN to go RED, and a
population must be proven, not assumed).

Scope: this guard realises R13-w2's hostile case and fails if it is realised. It does not speak for
R13 (its own file) or for the separately-routed R-P8-G4-P3RACE (the AC-CKPT / crash-matrix / P3
claim-CAS breadth). It reads the machine authority only; it changes no product code, probe grammar,
refusal control or acceptance requirement.

Hygiene note: every directory scan below EXCLUDES this file, and battery names and the race depth
are built from fragments / arithmetic, so this guard's own text can neither satisfy the check it
describes (the substring-self-reference blind spot, CLAUDE.md sec 6) nor plant a phantom test node
id for a node-id extractor. The only test node ids in this file are its three real tests.
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


def require_population(items, what: str):
    """CLAUDE.md sec 6: an assertion over an empty set passes vacuously. Prove the population first."""
    assert items, f"no {what} to assert over -- this guard would measure nothing"
    return items


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _p8_status() -> str:
    units = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["units"]
    for u in units:
        if str(u.get("unit_id", "")) == "P8":
            return str(u["status"])
    raise AssertionError("P8 unit not found in IMPLEMENTATION-REGISTRY.yaml -- cannot evaluate R13-w2")


def _sibling_suite_texts() -> list[str]:
    """The text of every collected test file EXCEPT this one AND the sibling ACCEPTANCE-GATE
    meta-guards. Self-exclusion stops this file's own strings from satisfying the checks it
    describes; excluding the acceptance-gate meta-guards is essential, because THEY enumerate the
    battery names and the race depth as their SUBJECT (not by exercising them) -- counting those
    mentions would let a battery read as 'exercised' merely because another meta-guard lists its
    name (the substring-self-reference blind spot, CLAUDE.md sec 6)."""
    out: list[str] = []
    for p in sorted(EVAL_TESTS.glob("*.py")):
        if p.name == _SELF or "acceptance_gate" in p.name:
            continue
        out.append(_text(p))
    return out


def _p8_negative_guard_batteries() -> list[str]:
    """The load-bearing P8 negative-guard mutation batteries R13-w2 names. Built from fragments so
    the full module name never appears literally in THIS file (self-scan safety)."""
    m = "mutate_"
    return [
        m + "phase8_proposal",      # U8.6 proposal inertness / token-not-approval / no-auto-advance
        m + "p8_policy_admission",  # U8.1 policy activation authority + one-positive-decision
        m + "p8_rule_admission",    # U8.2 rule activation authority (compile-or-refuse)
        m + "phase6_brake",         # U8.3 brake admission
        m + "phase6_compensation",  # U8.4 compensation single-derivation / one-active
    ]


# A battery is only "seen RED" if something EXECUTES it. A mere mention -- a manifest entry
# ("M10": "scripts/mutate_x.py") or a doc backtick -- is not execution. These are the idioms the
# real runners use: a CI `python scripts/mutate_x.py` step, a subprocess of the script, runpy, or
# loading it and calling its main(). Requiring an execution idiom is what makes this check stronger
# than R13's "declares a marker" and faithful to R13-w2's "ever seen RED".
_EXEC_IDIOM = re.compile(r"subprocess|runpy|run_path|spec_from_file_location|\.main\(\)")


def _negative_guard_seen_red_standing() -> dict[str, bool]:
    """(B) Each named battery is EXECUTED by standing evidence -- a CI run step OR a non-meta
    collected test that actually runs it (subprocess / runpy / main()) -- so its mutant is observed
    RED on every push. A battery only mentioned (manifest/doc) or runnable only by hand is 'never
    seen RED' in re-derivable evidence, which is the vacuity R13-w2 forbids under a COMPLETE P8."""
    ci = _text(CI_YML)
    siblings = [(t) for t in _sibling_suite_texts()]
    out: dict[str, bool] = {}
    for b in _p8_negative_guard_batteries():
        in_ci = (b + ".py") in ci                      # a CI `python scripts/<b>.py` run step
        run_by_test = any((b in t) and _EXEC_IDIOM.search(t) for t in siblings)
        out[b] = in_ci or run_by_test
    return out


def _ac_race_declared_depth_standing() -> bool:
    """(A) Is AC-RACE's declared race depth established as a STANDING, non-empty population -- a
    collected test (this file excluded) or a CI step that exercises a race at >= the declared depth?
    The depth is computed, not written, so this file carries no literal a self-scan could count."""
    declared_depth = 10 ** 4  # ten thousand interleavings per race (release-gates.md G4 / AC-RACE-002)
    # A CI step invoking a race/interleave probe with --repeat >= the declared depth.
    ci = _text(CI_YML)
    ci_hit = any(int(n) >= declared_depth for n in re.findall(r"--repeat\s+(\d+)", ci))
    # A collected test that exercises an interleaving/race at >= the declared depth (range(N) or
    # repeat=N), restricted to files that are actually about a race so a money literal cannot pose
    # as a depth.
    race_found = False
    for t in _sibling_suite_texts():
        if not re.search(r"interleav|never both, never neither|mint/claim race", t):
            continue
        depths = [int(n) for n in re.findall(r"range\(\s*(\d{4,})\s*\)", t)]
        depths += [int(n) for n in re.findall(r"repeat\s*=\s*(\d{4,})", t)]
        if any(d >= declared_depth for d in depths):
            race_found = True
            break
    return ci_hit or race_found


def r13w2_violations(p8_status: str, race_depth_standing: bool,
                     battery_seen_red: dict[str, bool]) -> list[str]:
    """The R13-w2 decision. The hostile case is realised ONLY when P8 is COMPLETE. When it is,
    AC-RACE's declared depth must be a standing population AND every load-bearing negative-guard
    battery must be seen RED in standing evidence; each miss weakens the gate to close the phase."""
    if p8_status != "COMPLETE":
        return []
    violations: list[str] = []
    if not race_depth_standing:
        violations.append(
            "P8 is COMPLETE but AC-RACE's declared 10,000-interleaving-per-race depth is not "
            "established by any standing oracle (no collected test or CI step exercises it)")
    for battery, ok in sorted(battery_seen_red.items()):
        if not ok:
            violations.append(
                "P8 is COMPLETE but a load-bearing negative-guard mutation battery is never seen "
                f"RED in standing evidence (runnable only by hand): {battery}")
    return violations


def _assert_no_r13w2_violation(p8_status: str, race_depth_standing: bool,
                               battery_seen_red: dict[str, bool]) -> None:
    violations = r13w2_violations(p8_status, race_depth_standing, battery_seen_red)
    assert not violations, (
        "R13-w2 VIOLATED -- P8 was materialized COMPLETE while its G4 gate rests on a vacuous "
        "negative guard or an under-populated race oracle; this weakens the gate to close the "
        "phase (release-gates.md G4 declares 10,000 interleavings per race and 100% of every "
        "family; status_model requires evidence, and CLAUDE.md sec 6 requires a guard to be seen "
        "RED):\n  - " + "\n  - ".join(violations))


# --------------------------------------------------------------------------- the guard
def test_r13w2_p8_is_not_complete_while_a_guard_is_vacuous_or_the_race_oracle_is_underpopulated():
    """THE GUARD. Fails if P8 is COMPLETE while AC-RACE's declared depth lacks a standing population
    or any load-bearing negative-guard battery is never seen RED in standing evidence. On a tree
    where P8 is not COMPLETE this passes -- the forbidden state is not present -- which is why the
    control below drives it RED."""
    batteries = require_population(_negative_guard_seen_red_standing(), "P8 negative-guard batteries")
    _assert_no_r13w2_violation(_p8_status(), _ac_race_declared_depth_standing(), batteries)


# --------------------------------------------------------------------------- the RED control
def test_r13w2_control_catches_a_complete_p8_with_a_vacuous_guard_or_underpopulated_race(monkeypatch):
    """THE CONTROL -- drives the guard RED to prove it is not vacuous. It reintroduces R13-w2's
    forbidden behaviour SYNTHETICALLY (a COMPLETE P8 whose race depth is not standing, or whose
    negative-guard battery is never seen RED), so it stays valid after the real gaps are closed, and
    confirms the guard fails."""
    all_batteries_ok = {k: True for k in _negative_guard_seen_red_standing()}
    require_population(all_batteries_ok, "negative-guard checks")
    a_vacuous_battery = dict(all_batteries_ok)
    a_vacuous_battery[next(iter(sorted(a_vacuous_battery)))] = False

    # Facet 1 -- COMPLETE + AC-RACE depth not standing IS a violation.
    assert r13w2_violations("COMPLETE", False, all_batteries_ok), \
        "the guard would MISS a COMPLETE P8 whose declared race depth has no standing population"
    # Facet 2 -- COMPLETE + a negative-guard battery never seen RED IS a violation.
    assert r13w2_violations("COMPLETE", True, a_vacuous_battery), \
        "the guard would MISS a COMPLETE P8 whose negative-guard battery is never seen RED"
    # Facet 3 -- no false positive: COMPLETE with both dimensions satisfied is NOT a violation.
    assert r13w2_violations("COMPLETE", True, all_batteries_ok) == [], \
        "the guard would fire on a fully-evidenced COMPLETE P8 (false positive)"
    # Facet 4 -- it bites only on COMPLETE.
    assert r13w2_violations("READY", False, a_vacuous_battery) == [], \
        "the guard fired while P8 was not COMPLETE -- R13-w2's hostile case requires COMPLETE"

    # Facet 5 -- invoke THE GUARD ITSELF with the forbidden behaviour reintroduced and require it to
    # FAIL (the "seen RED" proof CLAUDE.md sec 6 demands).
    g = sys.modules[__name__]
    monkeypatch.setattr(g, "_p8_status", lambda: "COMPLETE")
    monkeypatch.setattr(g, "_ac_race_declared_depth_standing", lambda: False)
    monkeypatch.setattr(g, "_negative_guard_seen_red_standing", lambda: a_vacuous_battery)
    with pytest.raises(AssertionError, match="R13-w2 VIOLATED"):
        g.test_r13w2_p8_is_not_complete_while_a_guard_is_vacuous_or_the_race_oracle_is_underpopulated()


def test_r13w2_measurement_is_populated_and_reads_both_race_depth_and_negative_guards():
    """Anti-vacuity for the MEASUREMENT: the battery manifest is non-empty and boolean, the AC-RACE
    depth check returns a bool, P8's status reads as a real registry value, and the decision couples
    a COMPLETE status to both dimensions. Proves the guard actually READS ac_race depth and the
    negative guards, and discriminates, rather than answering the same thing to everything."""
    batteries = require_population(_negative_guard_seen_red_standing(), "negative-guard checks")
    assert all(isinstance(v, bool) for v in batteries.values()), "a battery check did not return a bool"
    assert isinstance(_ac_race_declared_depth_standing(), bool), "the race-depth check did not return a bool"
    status = _p8_status()
    assert status in {"BLOCKED", "READY", "IN_PROGRESS", "COMPLETE"}, f"P8 status {status!r} is off-vocabulary"
    # The coupling is live on BOTH dimensions.
    assert r13w2_violations("COMPLETE", False, {k: True for k in batteries}), "no coupling to the race dimension"
    assert r13w2_violations("COMPLETE", True, {**{k: True for k in batteries},
                                               next(iter(sorted(batteries))): False}), "no coupling to the guard dimension"
    assert r13w2_violations(status, False, {k: False for k in batteries}) == [] or status == "COMPLETE", \
        "R13-w2 fired while P8 is not COMPLETE"
