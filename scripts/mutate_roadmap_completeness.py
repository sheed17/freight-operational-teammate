#!/usr/bin/env python3
"""The roadmap-completeness mutation battery.

A guard never seen to fail is a decoration (CLAUDE.md sec 9). This battery reintroduces, one at a
time, each real defect that eval/tests/test_roadmap_completeness_control.py exists to catch, and
requires the guard to FAIL each time.

Doctrine, identical to scripts/mutate_phase3_guards.py and scripts/mutate_phase4_boundary.py:
originals are held **in memory**, `__pycache__` is purged around every mutation, restoration is
verified byte-for-byte, and `git checkout` / `restore` / `stash` / `clean` are NEVER used - using
one of them once destroyed unrecoverable uncommitted work in this repository.

Evidence infrastructure. Never imported by runtime, and it adjudicates nothing.

    .venv/bin/python scripts/mutate_roadmap_completeness.py
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD = "eval/tests/test_roadmap_completeness_control.py"

REGISTRY = "docs/implementation/IMPLEMENTATION-REGISTRY.yaml"
TRACE = "docs/implementation/CAPABILITY-TRACEABILITY.yaml"
PHASE_OUTPUTS = "docs/implementation/PHASE-OUTPUTS.md"
SURFACE = "docs/implementation/IMPLEMENTATION-SURFACE.yaml"
CAP_MAP = "docs/product/FREIGHT-CAPABILITY-MAP.md"
CURRENT = "docs/implementation/CURRENT.md"
LEGACY = "docs/implementation/LEGACY-DISPOSITION.md"
SUPERVISOR = ".claude/agents/principal-architect-supervisor.md"

# (id, file, old, new, the test that must catch it, what real defect this is)
CASES = [
    # M1/M3 RE-POINTED at the R-07 closure content commit. A mutation case is bound to the exact
    # text it reintroduces the defect INTO; when the document legitimately changes, the case must be
    # re-pointed or it SETUP-FAILs and proves nothing. P4 went COMPLETE and R-07 went CONTAINED, so
    # both originals below moved. The DEFECT each case reintroduces is unchanged - only its anchor.
    ("M1", PHASE_OUTPUTS,
     "## P4 — Adapter containment ✅ COMPLETE — ADJUDICATED",
     "## P4 — Adapter containment ⛔ NOT STARTED",
     "test_an_executing_phase_is_never_described_as_not_begun",
     "the original contradiction: a phase with landed checkpoints described as not started"),
    ("M2", PHASE_OUTPUTS,
     "## P3 — Checkpoint, Witness and claim CAS ✅ COMPLETE",
     "## P3 — Checkpoint, Witness and claim CAS ⛔ NOT STARTED",
     "test_no_navigation_document_restates_a_phase_state_the_registry_does_not_hold",
     "a navigation heading asserting a phase state the registry does not hold"),
    ("M3", CURRENT,
     "| **R-07** | Ungated live-write paths | ### **CONTAINED** — recorded in",
     "| **R-07** | Ungated live-write paths | ### **R-07 is OPEN — NOT CONTAINED** — recorded in",
     "test_r07_is_never_represented_as_contained_anywhere_live",
     "the R-07 status contradicted in live authority text: the manifest records CONTAINED while the "
     "status authority says OPEN. Before the containment record was written this case ran the other "
     "way (an EARLY containment claim); the guard protects AGREEMENT with the manifest, not a "
     "particular value, so the case follows it"),
    # M4 RE-POINTED at the replacement candidate, discharging half of CB-01. Its anchor was
    # `status: READY` + `execution_state: IN_PROGRESS`, a pairing no unit has held since P4 went
    # COMPLETE, so the case SKIP-INVALIDed and proved nothing. A SKIP-INVALID is a battery defect,
    # not a result. The DEFECT is unchanged - a unit with landed evidence claiming it never began.
    ("M4", REGISTRY,
     "    status: COMPLETE\n    execution_state: COMPLETE\n    checkpoint_state: PHASE_ACCEPTANCE_COMPLETE",
     "    status: COMPLETE\n    execution_state: NOT_STARTED\n    checkpoint_state: PHASE_ACCEPTANCE_COMPLETE",
     "test_every_unit_carries_three_valid_and_mutually_consistent_states",
     "a unit claiming NOT_STARTED while recording landed checkpoints"),
    ("M5", REGISTRY,
     "      - sub_unit_id: P13-W9",
     "      - sub_unit_id: P13-WX",
     "test_every_loop_w1_to_w11_has_a_p13_sub_unit",
     "a W-loop silently dropped from the P13 decomposition"),
    ("M6", REGISTRY,
     "      - sub_unit_id: P13-M1",
     "      - sub_unit_id: P13-MX",
     "test_the_cross_cutting_sub_units_are_present_and_are_not_loops",
     "the workflow-authority-migration obligation silently dropped"),
    ("M7", REGISTRY,
     "        status: BLOCKED\n        execution_state: NOT_STARTED\n        checkpoint_state: NO_CHECKPOINT",
     "        status: IN_PROGRESS\n        execution_state: IN_PROGRESS\n        checkpoint_state: CHECKPOINT_IMPLEMENTED",
     "test_the_p13_decomposition_has_not_begun_p13",
     "the decomposition quietly starting P13"),
    ("M8", TRACE,
     "    implementation_status: SPECIFIED\n    source_implementation_reference: null\n    test_or_eval_reference: \"docs/specifications/acceptance/W9-acceptance.md (specification-level)\"",
     "    implementation_status: IMPLEMENTED\n    source_implementation_reference: null\n    test_or_eval_reference: \"docs/specifications/acceptance/W9-acceptance.md (specification-level)\"",
     "test_a_capability_is_implemented_only_with_source_and_executable_evidence",
     "a capability marked IMPLEMENTED with no source and no executable evidence"),
    ("M9", TRACE,
     "      NONE OF ITS OWN. Pipeline Instances remain the durable workflow orchestrator; the Operator\n      proposes and coordinates and the spine disposes.",
     "      The Operator owns its own durable workflow machine and drives loops directly.",
     "test_the_operator_is_never_a_second_workflow_source_of_truth",
     "the Operator promoted into a second workflow source of truth"),
    ("M10", CAP_MAP,
     "## 12. Claims & cargo exceptions (OS&D)  — loop **W11**",
     "## 12. Claims and cargo exceptions REMOVED  — loop **W11**",
     "test_the_eighteen_promised_capability_areas_are_all_covered",
     "one of the eighteen promised capability areas renamed out of coverage"),
    # M11 RE-POINTED at the replacement candidate, discharging the other half of CB-01. Its anchor
    # ("as FOUR effect-capable violation edges") had not existed since the surface reached ZERO.
    ("M11", SURFACE,
     "is now ZERO effect-capable",
     "is now five effect-capable",
     "test_the_recorded_effect_violation_surface_is_the_mechanically_recomputed_one",
     "the four-versus-five drift returning"),

    # ---------------------------------------------------------------------------------------
    # M12-M21 ADDED at the replacement candidate: the F-01 defect set and the grammar the F-02
    # guard was blind to.
    #
    # M12-M16 reintroduce, VERBATIM, the five live false claims the targeted adjudication found in
    # the rejected candidate. Each one passed the previous guard while the suite reported green, so
    # each is a proven MISS being converted into a proven CATCH.
    #
    # M17-M21 are the grammar variants. The pattern these replace required a copula from the closed
    # set {is, stays, remains} to FOLLOW `R-07`; every case below puts the verb somewhere else, or
    # uses no verb at all, which is how the repository's own canonical status rows are written.
    # ---------------------------------------------------------------------------------------
    ("M12", LEGACY,
     "| **Current risk** | ### **R-07 — CONTAINED (recorded at P4).**",
     "| **Current risk** | ### **R-07 — OPEN, NOT CONTAINED.**",
     "test_r07_is_never_represented_as_contained_anywhere_live",
     "F-01 defect 3, VERBATIM: the copula-free em-dash table cell in the section titled THE R-07 "
     "SURFACE - the single most-read statement of R-07's status, and the form no previous guard "
     "could ever see"),
    ("M13", LEGACY,
     "**WRITE HALF CUT at U4.11 (P4) — the deferral below is DISCHARGED.**",
     "**Still present — DEFERRED (it keeps R-07 OPEN):**",
     "test_r07_is_never_represented_as_contained_anywhere_live",
     "F-01 defect 1, VERBATIM: the verb-precedes construction 'it keeps R-07 OPEN', asserting the "
     "write half this commit certifies as cut is still present"),
    ("M14", LEGACY,
     "agree both-sided; **zero** residuals remain.",
     "agree both-sided; (**not yet** — **four** residuals remain).",
     "test_the_recorded_effect_violation_surface_is_the_mechanically_recomputed_one",
     "F-01 defect 2, VERBATIM: the residual-count claim contradicting a violation surface the probe "
     "recomputes as EMPTY"),
    ("M15", SUPERVISOR,
     "2. **Safety boundaries intact** — verify R-07 against the machine record in",
     "2. **Safety boundaries intact** — R-07 still recorded OPEN unless the unit is P4 itself; in",
     "test_r07_is_never_represented_as_contained_anywhere_live",
     "F-01 defect 4, VERBATIM: an OPERATIVE adjudication criterion instructing a supervisor to "
     "require R-07 to be recorded OPEN - an agent obeying it would reject the correct repository "
     "state. The trailing 'unless' must NOT excuse it"),
    ("M16", SUPERVISOR,
     "production-reachable live-write paths (EP-1, EP-3, EP-6, EP-7, EP-9, EP-10) was **CUT at P4** —",
     "production-reachable live-write paths and an open R-07, and no unit is APPROVED otherwise —",
     "test_r07_is_never_represented_as_contained_anywhere_live",
     "F-01 defect 5, VERBATIM: 'an open R-07' asserted as a live property of the repository"),
    ("M17", LEGACY,
     "| **Current risk** | ### **R-07 — CONTAINED (recorded at P4).**",
     "| **Current risk** | ### **The remaining residual leaves R-07 open.**",
     "test_r07_is_never_represented_as_contained_anywhere_live",
     "grammar variant: 'leaves R-07 open' - verb precedes the risk id"),
    ("M18", LEGACY,
     "| **Current risk** | ### **R-07 — CONTAINED (recorded at P4).**",
     "| **Current risk** | ### **R-07 not contained.**",
     "test_r07_is_never_represented_as_contained_anywhere_live",
     "grammar variant: 'R-07 not contained' - no copula at all"),
    ("M19", LEGACY,
     "| **Current risk** | ### **R-07 — CONTAINED (recorded at P4).**",
     "| **Current risk** | ### **The boundary does not contain R-07.**",
     "test_r07_is_never_represented_as_contained_anywhere_live",
     "grammar variant: 'does not contain R-07' - the risk id is the OBJECT, not the subject"),
    ("M20", LEGACY,
     "| **Current risk** | ### **R-07 — CONTAINED (recorded at P4).**",
     "| **Current risk** | ### **Violation residuals keep R-07 open.**",
     "test_r07_is_never_represented_as_contained_anywhere_live",
     "grammar variant: 'violation residuals keep R-07 open'"),
    ("M21", LEGACY,
     "| **Current risk** | ### **R-07 — CONTAINED (recorded at P4).**",
     "| **Current risk** | ### **R-07: OPEN.**",
     "test_r07_is_never_represented_as_contained_anywhere_live",
     "grammar variant: 'R-07: OPEN' - a colon-introduced value, which a sentence splitter that "
     "treats ':' as a boundary would cut in half and lose"),
]


def purge_pycache() -> None:
    for d in ROOT.rglob("__pycache__"):
        shutil.rmtree(d, ignore_errors=True)


def run_guard(node: str) -> int:
    purge_pycache()
    return subprocess.run(
        [str(ROOT / ".venv/bin/python"), "-m", "pytest", "-c", str(ROOT / "pytest-canonical.ini"),
         f"{GUARD}::{node}", "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True,
    ).returncode


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()

    originals = {rel: (ROOT / rel).read_text(encoding="utf-8")
                 for rel in {c[1] for c in CASES}}

    print("baseline: the guard must be GREEN before any mutation")
    purge_pycache()
    base = subprocess.run(
        [str(ROOT / ".venv/bin/python"), "-m", "pytest", "-c", str(ROOT / "pytest-canonical.ini"),
         GUARD, "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True)
    if base.returncode != 0:
        print("REFUSED: the guard is not green before mutation:\n" + base.stdout[-2000:])
        return 2
    print("  baseline GREEN\n")

    caught = missed = 0
    try:
        for cid, rel, old, new, node, what in CASES:
            path = ROOT / rel
            text = originals[rel]
            if text.count(old) < 1:
                print(f"{cid}: SKIP-INVALID - anchor not found in {rel} (the mutation would prove "
                      "nothing); fix the battery, do not ignore this")
                missed += 1
                continue
            path.write_text(text.replace(old, new, 1), encoding="utf-8")
            rc = run_guard(node)
            path.write_text(text, encoding="utf-8")
            assert path.read_text(encoding="utf-8") == text, f"{cid}: {rel} not restored byte-for-byte"
            if rc != 0:
                caught += 1
                print(f"{cid}: CAUGHT  {node}\n        ({what})")
            else:
                missed += 1
                print(f"{cid}: *** MISS *** {node} stayed green under: {what}")
    finally:
        for rel, text in originals.items():
            (ROOT / rel).write_text(text, encoding="utf-8")
        purge_pycache()

    print(f"\nbattery: {caught}/{len(CASES)} caught, {missed} missed")
    return 0 if missed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
