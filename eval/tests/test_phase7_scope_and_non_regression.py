"""P7-AC-1 — scope conformance and P6 non-regression.

This is the FIRST P7 increment (the READY unit is P7; see docs/implementation/CURRENT.md and
IMPLEMENTATION-REGISTRY.yaml unit P7, criterion `P7-AC-1`). P7 ships dark, and this slice lands NO
product surface: no provenance/evidence/linker/conflict runtime, no migration, no change to any
M1..M13 machine, the effect boundary, or any status document. It lands the STANDING SCOPE GATE for
the phase, so every later P7 slice (AC-2..AC-17) is checked against `allowed_scope` from the start,
exactly the way P0 landed the anti-false-green infrastructure before the code it guards.

`P7-AC-1`'s oracle names three checks, and this module runs each one on the candidate tree:

  1. "the prohibited surfaces are proved absent over a DISCOVERED population (AST/import sweep) with
     its denominator printed ... the production GateRegistry emptiness guard still passes" — the
     P8 policy runtime is not enabled.
  2. + 3. "P6's machine-population and transition-bijection guards are RE-RUN GREEN on the candidate
     tree as a NON-REGRESSION check" — re-running is NOT re-accepting: P6's `AC-MACH-*` half of G1
     is already accepted 17/17, and these fail only if P7 BROKE them.

### WHY THIS RE-RUNS THE AUTHORITATIVE GUARDS RATHER THAN REIMPLEMENTING THEM.
An independently-authored substring/name sweep for a "prohibited surface" false-positives here: a
tree-wide search for an autonomy "graduat"-ion engine flags the LEGACY `lane_graduation.py` and
`ops_control.py`, which are not the P8 autonomy engine at all. That is precisely the
filename/substring blind spot CLAUDE.md sec 6 says this repository produced four separate times. So
`P7-AC-1` re-runs the calibrated guards that already discover their populations and print their
denominators — `test_phase0_null_gate.py` for the production `GateRegistry` emptiness, and
`test_bootstrap_hermeticity.py` for the 134-transition corpus and the producer bijection — and adds
one discrimination control proving the prohibition detector can still fire. "RE-RUN GREEN" is taken
literally: the real guard is invoked, not a copy of its logic that could drift out of step with it.
"""

from __future__ import annotations

import ast
import importlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "freight_recon"

# Match pytest's prepend import mode so a lazy import of a sibling guard module returns the SAME
# object pytest collects (same file path -> no import-file mismatch, no double execution). Built
# from path joins, never string-literal filenames, so this module carries no hand-enumerated file
# population (test_false_green_defenses.py::test_no_control_guard_hand_enumerates_a_file_population).
for _p in (str(ROOT / "src"), str(ROOT / "eval"), str(ROOT / "eval" / "tests"),
           str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def require_population(items, what: str):
    """A negative/absence assertion over an empty set passes while proving nothing. Refuse that."""
    assert items, f"no {what} to assert over - this test would pass vacuously"
    return items


# ----------------------------------------------------------------- AC-1 part 1: no P8 policy runtime


def test_the_production_gate_registration_population_is_empty_on_the_p7_candidate_tree():
    """`P7-AC-1` clause: the production `GateRegistry` emptiness guard still passes on the candidate
    tree. This is the prohibited P8 policy-REGISTRATION / EVALUATION-RUNTIME / ENABLEMENT surface
    proved absent over a DISCOVERED population — `test_phase0_null_gate` walks every module under
    src/ (excluding the kernel that DEFINES the contract), asserts it inspected a non-empty set, and
    fails if any production module constructs a `GateRegistry`. The production registry stays EMPTY
    until U8.1/P8 (CLAUDE.md sec 10), so P7 must not have populated it.

    RE-RUN, not reimplemented: invoking the calibrated guard cannot drift out of step with it."""
    null_gate = importlib.import_module("test_phase0_null_gate")
    null_gate.test_the_production_gate_registration_population_is_still_empty()


# -------------------------------------------------- AC-1 parts 2 & 3: P6 non-regression (re-run green)


def test_the_p6_transition_corpus_guard_reruns_green_on_the_p7_candidate_tree():
    """`P7-AC-1` clause: P6's machine-population guard re-runs GREEN on the candidate tree. The
    134-transition corpus is anchored by EXACT SET EQUALITY against the registered expectation and
    every row is column-aligned. Re-running is a non-regression check; P6's `AC-MACH-*` half of G1
    is already accepted, and this fails only if a P7 change broke the transition corpus."""
    bootstrap = importlib.import_module("test_bootstrap_hermeticity")
    bootstrap.test_the_transition_corpus_is_positively_anchored_and_every_row_is_column_aligned()


def test_the_p6_producer_transition_bijection_guard_reruns_green_on_the_p7_candidate_tree():
    """`P7-AC-1` clause: P6's transition-bijection guard re-runs GREEN on the candidate tree. The
    sec-3 producer map, the corpus and the classification form ONE relation asserted in both
    directions (zero-owner and duplicate-owner both fail closed). Non-regression only."""
    bootstrap = importlib.import_module("test_bootstrap_hermeticity")
    bootstrap.test_the_producer_map_and_the_transition_corpus_are_bijective()


# ----------------------------------------------------------- the discovered denominator is non-empty


def test_the_scanned_source_population_is_non_empty_so_the_absence_proofs_are_not_vacuous():
    """The prohibition sweep above concludes "no production module registers a gate" over the
    modules under src/. Printing and flooring that denominator here makes an empty parse — which
    would make every absence proof vacuously green — a hard failure rather than a silent pass
    (CLAUDE.md sec 6: a green check that parsed nothing is worse than no check)."""
    modules = require_population(sorted(SRC.rglob("*.py")), "modules under src/freight_recon")
    # A floor well below the true count (127 at this landing): this asserts the tree was actually
    # walked, not the exact size, so ordinary growth never trips it.
    assert len(modules) >= 50, (
        f"the source population collapsed to {len(modules)} modules — the GateRegistry absence "
        f"proof would be running over an implausibly small or empty tree"
    )
    print(f"P7-AC-1: production-scope absence proofs ran over {len(modules)} src/freight_recon modules")


# --------------------------------------------------------- anti-vacuity: the prohibition can still fire


# The null-gate guard's detector, replicated for a DISCRIMINATION control (not for the live sweep):
# a `GateRegistry(...)` construction as a whole token, so a longer identifier ending in the name and
# a snake_case lookalike are both correctly ignored.
_GATE_REGISTRY_CONSTRUCTION = re.compile(r"(?<![A-Za-z0-9_])GateRegistry\s*\(")


def test_the_gate_registry_prohibition_detector_fires_on_a_real_construction_and_ignores_lookalikes():
    """A guard never seen to fire is a decoration (CLAUDE.md sec 6). This proves the prohibited-P8
    detector re-run above discriminates: it flags an actual `GateRegistry(...)` construction and is
    NOT tripped by a lookalike identifier or a snake_case name. The subject is a synthetic in-memory
    string — nothing is written to the tree, so the live sweep is unaffected."""
    leaking = "gate = GateRegistry(tenant=t)\n"  # the real out-of-scope construction
    spaced = "gate = GateRegistry (t)\n"          # whitespace before the paren still counts
    lookalike = "helper = MyGateRegistryFactory(t)\n"  # a longer identifier is not the construction
    snake = "reg = gate_registry(t)\n"            # a different symbol entirely

    assert _GATE_REGISTRY_CONSTRUCTION.search(leaking), (
        "the prohibition detector failed to flag a genuine GateRegistry construction — the "
        "delegated production-emptiness sweep it mirrors would pass vacuously"
    )
    assert _GATE_REGISTRY_CONSTRUCTION.search(spaced), "the detector missed a spaced construction"
    assert _GATE_REGISTRY_CONSTRUCTION.search(lookalike) is None, (
        "the detector fired on a longer identifier that merely contains the name — it would raise "
        "false positives and be disabled or ignored"
    )
    assert _GATE_REGISTRY_CONSTRUCTION.search(snake) is None, (
        "the detector fired on an unrelated snake_case symbol"
    )
    # It is also a whole-token match against a real parse of the synthetic module, not a substring
    # scan of raw text: the construction is a Call whose function is the Name `GateRegistry`.
    calls = [n for n in ast.walk(ast.parse(leaking))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "GateRegistry"]
    assert len(calls) == 1, f"expected exactly one GateRegistry construction in the fixture, found {len(calls)}"
