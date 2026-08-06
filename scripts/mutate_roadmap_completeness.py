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
SWITCH_GUARD = "eval/tests/test_switch_consistency.py"
DOCS_GUARD = "eval/tests/test_docs_control_system.py"

REGISTRY = "docs/implementation/IMPLEMENTATION-REGISTRY.yaml"
TRACE = "docs/implementation/CAPABILITY-TRACEABILITY.yaml"
PHASE_OUTPUTS = "docs/implementation/PHASE-OUTPUTS.md"
SURFACE = "docs/implementation/IMPLEMENTATION-SURFACE.yaml"
CAP_MAP = "docs/product/FREIGHT-CAPABILITY-MAP.md"
CURRENT = "docs/implementation/CURRENT.md"
LEGACY = "docs/implementation/LEGACY-DISPOSITION.md"
SUPERVISOR = ".claude/agents/principal-architect-supervisor.md"
CLAUDE_MD = "CLAUDE.md"
README_MD = "README.md"
ARCH = "ARCHITECTURE.md"

# The R-07 status node, named once so the cross-cell and <details> cases below cannot drift from it.
R07_NODE = "test_r07_is_never_represented_as_contained_anywhere_live"

# A `<details>` block carrying a live OPEN claim, built once so every marker case differs from the
# others in EXACTLY the one property it attacks.
_HIDDEN = "R-07 remains OPEN and is NOT CONTAINED."
_ANCHOR = "## Documents required before proceeding"

# (id, file, old, new, the test that must catch it, what real defect this is [, expect [, guard]])
#
# `expect` is "CAUGHT" (default) or "GREEN". GREEN cases are not decoration: a battery in which
# every mutation fails the guard cannot distinguish a parser that reads rows correctly from one
# that fires on anything nearby, and the row-aware parser's whole risk is over-association. A GREEN
# case asserts a NEGATIVE invariant - that association does NOT cross a row or a table - and it is
# a battery defect if it fails, exactly as a MISS is.
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

    # ---------------------------------------------------------------------------------------
    # M22-M39 ADDED at the R-01/R-02 remediation.
    #
    # M12-M21 above all put the risk id and the polarity token in the SAME CELL, which is the
    # predecessor parser's own field of view. A battery drawn from the instrument's field of view
    # measures that field of view, not the corpus - RC-01, recurring. It reported 21/21 CAUGHT
    # while never testing the construction the corpus actually uses for its canonical status rows.
    #
    # M22-M25 are the three live rows that ESCAPED, mutated VERBATIM in their real cross-cell form,
    # plus the introduced ARCHITECTURE.md row. M26-M29 are the remaining authorized column
    # arrangements. M30-M31 are the negative bound. M32-M39 are the <details> classification.
    # ---------------------------------------------------------------------------------------
    ("M22", CURRENT,
     "| **R-07** | Ungated live-write paths | ### **CONTAINED** — recorded in",
     "| **R-07** | Ungated live-write paths | ### **OPEN — NOT CONTAINED** — recorded in",
     R07_NODE,
     "R-01, VERBATIM: the designated STATUS AUTHORITY's canonical R-07 row, with the risk id left "
     "in cell 1 and only the STATUS CELL flipped. The predecessor parsed this row as two discarded "
     "fragments and stayed green with the status authority reading OPEN. Compare M3, which flips "
     "the same row in the SAME-CELL form the old parser could see"),
    ("M23", CLAUDE_MD,
     "| **R-07** | ### **CONTAINED.** The containment MECHANISM is built",
     "| **R-07** | ### **OPEN — NOT CONTAINED.** The containment MECHANISM is built",
     R07_NODE,
     "R-01, VERBATIM: the OPERATING GUIDE's canonical R-07 row, subject in cell 1, status in cell 2"),
    ("M24", README_MD,
     "| **R-07 — ungated live-write paths** | ### **CONTAINED** — the mechanism is built",
     "| **R-07 — ungated live-write paths** | ### **OPEN — NOT CONTAINED** — the mechanism is built",
     "test_10_r07_is_recorded_open_and_never_contained",
     "R-01, VERBATIM: the PUBLIC LANDING DOCUMENT's canonical R-07 row - the third live cross-cell "
     "row, which the targeted review did not name and the adjudication found by sweeping. "
     "DELIBERATELY POINTED AT THE UNIFIED GUARD: README.md is NOT in the discovered "
     "live_authority_documents() population, so the roadmap guard's R-07 node genuinely cannot "
     "see it - it is reached only through the UNION with the four landing documents. Pointing this "
     "case at the roadmap node would have scored a MISS that says nothing about the parser and "
     "everything about which corpus each guard asserts over",
     "CAUGHT", DOCS_GUARD),
    ("M25", ARCH,
     "| **P5** | 🔄 **READY *(selected)* — NOT STARTED, NOT COMPLETE** |",
     "| **R-07** | ### **OPEN — NOT CONTAINED** |\n"
     "| **P5** | 🔄 **READY *(selected)* — NOT STARTED, NOT COMPLETE** |",
     R07_NODE,
     "R-01: a NEW cross-cell row introduced into ARCHITECTURE.md - the adjudication's own "
     "reproduction, which left all 222 guard tests green on the rejected candidate"),
    ("M26", LEGACY,
     "| **Current risk** | ### **R-07 — CONTAINED (recorded at P4).**",
     "| ### **OPEN — NOT CONTAINED** | ### **R-07** — (recorded at P4).",
     R07_NODE,
     "R-01 column arrangement: the STATUS in a LEADING cell and the SUBJECT in a later one - "
     "association must not depend on the subject coming first"),
    ("M27", LEGACY,
     "| **Current risk** | ### **R-07 — CONTAINED (recorded at P4).**",
     "| **Current risk** | severity | high | ### **R-07** | note | ### **OPEN — NOT CONTAINED** |",
     R07_NODE,
     "R-01 column arrangement: extra DESCRIPTIVE COLUMNS before, between and after the subject and "
     "status cells"),
    ("M28", LEGACY,
     "| **Current risk** | ### **R-07 — CONTAINED (recorded at P4).**",
     r"| **Current risk** | ### **R-07 \| OPEN — NOT CONTAINED (recorded at P4).**",
     R07_NODE,
     "R-01 escaping: an ESCAPED PIPE is cell CONTENT, not a delimiter. A parser that split on it "
     "would break this claim into two invisible fragments"),
    ("M29", LEGACY,
     "| **Current risk** | ### **R-07 — CONTAINED (recorded at P4).**",
     "| **Current risk** | `R-07` | `OPEN — NOT CONTAINED` |",
     R07_NODE,
     "R-01: INLINE CODE subject and status cells - backticks are normalized away, and a code span "
     "is not an exemption"),
    ("M30", LEGACY,
     "| **Current risk** | ### **R-07 — CONTAINED (recorded at P4).**",
     "| **Current risk** | ### **R-07 — CONTAINED (recorded at P4).**\n"
     "| **Unrelated residual** | ### **OPEN — NOT CONTAINED** |",
     R07_NODE,
     "R-01 NEGATIVE BOUND: a polarity token in a DIFFERENT ROW must NOT attach to the R-07 row. "
     "The guard must stay GREEN - a row-aware parser that joined rows would manufacture a false "
     "failure here, which is the unrelated-identifier failure CLAUDE.md sec 9 names",
     "GREEN"),
    ("M31", LEGACY,
     "| **Current risk** | ### **R-07 — CONTAINED (recorded at P4).**",
     "| **Current risk** | ### **R-07 — CONTAINED (recorded at P4).**\n\n"
     "| **Unrelated** | ### **OPEN — NOT CONTAINED** |\n",
     R07_NODE,
     "R-01 NEGATIVE BOUND: a polarity token in a DIFFERENT TABLE must NOT attach to the R-07 row. "
     "The guard must stay GREEN",
     "GREEN"),
    ("M32", CURRENT,
     _ANCHOR,
     f"<details>\n<summary>Notes</summary>\n\n{_HIDDEN}\n\n</details>\n\n{_ANCHOR}",
     R07_NODE,
     "R-02: a live OPEN claim inside an UNLABELLED <details> block. CURRENT.md records an incident "
     "in which a FALSE TRANSITION CLAIM was planted in exactly this way, and states that a false "
     "claim placed there is MORE dangerous than one in live text. The predecessor stripped every "
     "block unconditionally, so this left the whole guard set green"),
    ("M33", CURRENT,
     _ANCHOR,
     f"<details>\n<summary>⛔ HISTORICAL — SUPERSEDED</summary>\n\n{_HIDDEN}\n\n</details>\n\n{_ANCHOR}",
     R07_NODE,
     "R-02 DISCRIMINATOR: the SAME hidden claim in a block that DOES self-label. It must be parsed, "
     "exempt and excluded from live counts, and the guard must stay GREEN - otherwise the fix is "
     "just 'fail on every <details>', which would break the corpus's legitimate historical blocks",
     "GREEN"),
    # M34 RETARGETED at the fourth candidate (S-03). Its fixture wrote the marker with a BLANK LINE
    # before `<details>`, and a blank line already broke the prose run - so the case passed on a
    # tree where the ADJACENT arrangement it is named for escaped completely. A battery case that
    # cannot fail on the defect it describes is a fixture, not evidence. It now attacks the exact
    # no-blank-line form; the blank-line form it used to test is kept as M41, so neither is lost.
    ("M34", CURRENT,
     _ANCHOR,
     f"⛔ HISTORICAL — the superseded notes below.\n<details>\n<summary>Notes</summary>\n"
     f"{_HIDDEN}\n</details>\n\n{_ANCHOR}",
     R07_NODE,
     "S-03: the historical marker MOVED OUTSIDE the block, written ADJACENT to the opener with no "
     "blank line. Proximity is not attachment, and deleting one blank line must not make it "
     "attachment - this is the exact escape the reviewer reproduced"),
    ("M35", CURRENT,
     _ANCHOR,
     f"<details>\n<summary>Design note</summary>\n\n{_HIDDEN}\n\n</details>\n\n{_ANCHOR}",
     R07_NODE,
     "R-02: the historical marker REMOVED from a block that carries a live claim - the minimal "
     "edit that turns a legitimate quarantine into a hiding place"),
    ("M36", CURRENT,
     _ANCHOR,
     f"<details>\n<summary>⛔ HISTORICAL — SUPERSEDED</summary>\n\n{_HIDDEN}\n\n{_ANCHOR}",
     R07_NODE,
     "R-02: a MALFORMED block - the closing </details> deleted. It must FAIL CLOSED. Under the "
     "predecessor's non-greedy regex an unterminated block swallowed the document tail; a live "
     "claim may never disappear because the HTML did not parse"),
    ("M37", CURRENT,
     _ANCHOR,
     f"<details>\n<summary>⛔ HISTORICAL — SUPERSEDED</summary>\n\nsuperseded programs\n\n"
     f"<details>\n<summary>Notes</summary>\n\n{_HIDDEN}\n\n</details>\n</details>\n\n{_ANCHOR}",
     R07_NODE,
     "R-02 NESTING: an UNLABELLED block nested inside a labelled one. A block never inherits its "
     "parent's label - each block is labelled or it is READ"),
    ("M38", CURRENT,
     _ANCHOR,
     f"<details>\n<summary>Notes</summary>\n\n| **R-07** | ### **OPEN — NOT CONTAINED** |\n\n"
     f"</details>\n\n{_ANCHOR}",
     R07_NODE,
     "R-01 x R-02 COMPOSED: a CROSS-CELL status row hidden inside an UNLABELLED <details> block - "
     "the two blind spots stacked, which escaped the rejected candidate twice over"),
    ("M39", REGISTRY,
     "    status: READY\n    execution_state: NOT_STARTED\n    checkpoint_state: NO_CHECKPOINT\n"
     "    dependencies: [P4]",
     "    status: BLOCKED\n    execution_state: NOT_STARTED\n    checkpoint_state: NO_CHECKPOINT\n"
     "    dependencies: [P4]",
     "test_the_selected_ready_unit_construction_is_present_singular_and_matches_the_registry",
     "ZERO READY rows: the selector goes silent. Silence must not read as compliance - the "
     "one-READY-unit invariant is violated by zero just as it is by two",
     "CAUGHT", SWITCH_GUARD),
    ("M40", REGISTRY,
     "  - unit_id: P6\n    name: Foundational entities and state machines\n    status: BLOCKED",
     "  - unit_id: P6\n    name: Foundational entities and state machines\n    status: READY",
     "test_the_selected_ready_unit_construction_is_present_singular_and_matches_the_registry",
     "DUPLICATE READY rows: two units held READY at once, so the repository carries two live "
     "selection claims and no single next unit",
     "CAUGHT", SWITCH_GUARD),

    # ---------------------------------------------------------------------------------------
    # M41-M58 ADDED at the FOURTH candidate: the S-01 / S-02 / S-03 boundary defects.
    #
    # M22-M40 all measured the parser's ASSOCIATION behaviour, which was correct. None of them
    # measured its EXEMPTION SCOPE, so three laundering paths sat behind a 40/40 battery: a
    # conditional or historical word in ANY preceding cell exempted a separate status cell, and a
    # marker written adjacent to a `<details>` opener exempted the whole block. RC-01 again - a
    # battery drawn from the instrument's field of view measures that field of view.
    #
    # Two of these defects fire ACCIDENTALLY: `if`, `when`, `before`, `after` and `while` are
    # ordinary words in an evidence or notes column, so M48 and M50 below are not adversarial
    # constructions at all.
    #
    # Each family carries its own must-stay-GREEN negative (M52, M58, M44). Without them, a
    # "remediation" that deleted the exemption rules outright would score full marks here.
    # ---------------------------------------------------------------------------------------

    # ---- S-03: a structural tag is a unit boundary -----------------------------------------
    ("M41", CURRENT,
     _ANCHOR,
     f"⛔ HISTORICAL — the superseded notes below.\n\n<details>\n<summary>Notes</summary>\n\n"
     f"{_HIDDEN}\n\n</details>\n\n{_ANCHOR}",
     R07_NODE,
     "S-03 TWIN of M34: the SAME external marker with a BLANK LINE before the opener. This is what "
     "M34 used to test. Both arrangements must classify IDENTICALLY - that they diverged is the "
     "defect signature, and keeping both is what proves the boundary is structural, not whitespace",
     ),
    ("M42", CURRENT,
     _ANCHOR,
     f"<details>\n<summary>⛔ HISTORICAL — SUPERSEDED</summary>\n{_HIDDEN}\n\n{_ANCHOR}",
     R07_NODE,
     "S-03 TWIN of M36: an UNTERMINATED block written with NO BLANK LINES. M36 passed only because "
     "its fixture had them. The module promises an unterminated <details> grants no exemption at "
     "all; in this arrangement that promise was void and nothing was measuring it"),
    ("M43", CURRENT,
     _ANCHOR,
     f"<details>\n<summary>⛔ HISTORICAL — SUPERSEDED</summary>\nsuperseded programs\n"
     f"<details>\n<summary>Notes</summary>\n{_HIDDEN}\n</details>\n</details>\n\n{_ANCHOR}",
     R07_NODE,
     "S-03 TWIN of M37: an UNLABELLED block NESTED inside a labelled one, written with NO BLANK "
     "LINES. M37 passed only because its fixture had them. The module promises a block never "
     "inherits its parent's label; in this arrangement the child inherited"),
    ("M44", CURRENT,
     _ANCHOR,
     f"<details>\n<summary>Notes</summary>\nintro\n"
     f"<details>\n<summary>⛔ HISTORICAL — SUPERSEDED</summary>\n{_HIDDEN}\n"
     f"</details>\n</details>\n\n{_ANCHOR}",
     R07_NODE,
     "S-03 NEGATIVE BOUND: a LABELLED block nested inside a LIVE one, with no blank lines. It must "
     "be judged by its OWN attached marker and stay exempt. No inheritance means none in EITHER "
     "direction, and a fix that broke this would just be 'fail on every <details>'",
     "GREEN"),
    ("M45", CURRENT,
     _ANCHOR,
     f"<details>\n<summary>⛔ HISTORICAL — SUPERSEDED\n{_HIDDEN}\n</details>\n\n{_ANCHOR}",
     R07_NODE,
     "S-03: a MALFORMED <summary> - never closed - with no blank lines. `_build_block` correctly "
     "reads NO marker from it, but without a closing tag there is no boundary either, so the void "
     "label's text ran on into the body and was granted as marked-historical from behind the "
     "classifier's back"),
    ("M46", CURRENT,
     _ANCHOR,
     f"if the containment gate reopens this applies.\n<details>\n<summary>Notes</summary>\n"
     f"{_HIDDEN}\n</details>\n\n{_ANCHOR}",
     R07_NODE,
     "S-03 CONDITIONAL TWIN: the same adjacency escape reaching the HYPOTHETICAL rule instead of "
     "the historical one. The prose-boundary correction is what closes it, and a details-only case "
     "would not demonstrate that"),

    # ---- S-01: the conditional window is the status token's own cell -----------------------
    ("M47", CURRENT,
     _ANCHOR,
     f"| Conditional | if X happens | **R-07** | ### **OPEN — NOT CONTAINED** |\n\n{_ANCHOR}",
     R07_NODE,
     "S-01: `if` in an unrelated LEADING cell exempted a separate canonical status cell. The "
     "adjudication's exact reproduction"),
    ("M48", CURRENT,
     _ANCHOR,
     f"| **R-07** | recorded when the gate ran | ### **OPEN — NOT CONTAINED** |\n\n{_ANCHOR}",
     R07_NODE,
     "S-01 ACCIDENTAL: `when` in an EVIDENCE cell. No adversary is present - this is ordinary "
     "English in an ordinary column, which is what raises S-01 from an evasion vector to a latent "
     "silent-failure mode of the control"),
    ("M49", CURRENT,
     _ANCHOR,
     f"| **R-07** | reviewed before the cutover | ### **OPEN — NOT CONTAINED** |\n\n{_ANCHOR}",
     R07_NODE,
     "S-01: `before` in a cell BETWEEN the subject and the status"),
    ("M50", CURRENT,
     _ANCHOR,
     f"| **R-07** | ### **OPEN — NOT CONTAINED** | re-read after P5 |\n\n{_ANCHOR}",
     R07_NODE,
     "S-01 / R-03 PRESERVED: a conditional AFTER the status cell. A trailing qualifier qualifies an "
     "assertion; it does not turn it into a hypothetical. This was already correct and must STAY "
     "correct - it is the ordering half of the rule, which the cell-locality fix must not disturb"),
    ("M51", CURRENT,
     _ANCHOR,
     f"| **R-07** | held while P4 ran | ### **OPEN — NOT CONTAINED** |\n\n{_ANCHOR}",
     R07_NODE,
     "S-01: `while` in a DESCRIPTION cell"),
    ("M52", CURRENT,
     _ANCHOR,
     f"| **R-07** | ### **may not be recorded OPEN until the gate asserts empty** |\n\n{_ANCHOR}",
     R07_NODE,
     "S-01 NEGATIVE BOUND: a conditional that genuinely GOVERNS its own claim, in the SAME cell as "
     "the polarity token. It must stay exempt. Without this case, deleting the conditional rule "
     "outright would score full marks on M47-M51",
     "GREEN"),

    # ---- S-02: the marker window is the subject's own cell ---------------------------------
    ("M53", CURRENT,
     _ANCHOR,
     f"| Historical example | unrelated text | **R-07** | ### **OPEN — NOT CONTAINED** |\n\n{_ANCHOR}",
     R07_NODE,
     "S-02: a HISTORICAL token in an unrelated LEADING cell exempted a separate live status cell. "
     "The adjudication's exact reproduction"),
    ("M54", CURRENT,
     _ANCHOR,
     f"| nothing here is SUPERSEDED | **R-07** | ### **OPEN — NOT CONTAINED** |\n\n{_ANCHOR}",
     R07_NODE,
     "S-02: R-03's own authority sentence in its ROW-SHAPED form. R-03 closed this for sentences "
     "and the R-01 widening re-opened it for rows"),
    ("M55", CURRENT,
     _ANCHOR,
     "| Historical status | Risk | State |\n| --- | --- | --- |\n"
     f"| current | **R-07** | ### **OPEN — NOT CONTAINED** |\n\n{_ANCHOR}",
     R07_NODE,
     "S-02: the marker in a column HEADING. A heading NAMES a column; it does not qualify the "
     "values beneath it. If it did, the entire corpus would become exemptible by naming a column "
     "'Historical status'"),
    ("M56", CURRENT,
     _ANCHOR,
     "| ⛔ HISTORICAL | old note | superseded |\n"
     f"| current | **R-07** | ### **OPEN — NOT CONTAINED** |\n\n{_ANCHOR}",
     R07_NODE,
     "S-02: the marker in a NEIGHBOURING ROW. Two rows are two records, and this is also the "
     "overcorrection bound - it must be caught for the RIGHT reason, because nothing crosses a row"),
    ("M57", CURRENT,
     _ANCHOR,
     f"| **R-07** | ### **OPEN — NOT CONTAINED** | see the SUPERSEDED note |\n\n{_ANCHOR}",
     R07_NODE,
     "S-02 / R-03 PRESERVED: a marker AFTER the status in an unrelated NOTES cell. Already correct "
     "by ordering, and it must stay correct once the window is also narrowed by cell"),
    ("M58", CURRENT,
     _ANCHOR,
     f"| (HISTORICAL — this row states the state at P0) **R-07** stayed OPEN at P0 | evidence |"
     f"\n\n{_ANCHOR}",
     R07_NODE,
     "S-02 NEGATIVE BOUND: a marker attached to its ACTUAL claim - in the subject's OWN cell, "
     "before the risk id. This is the exact form PHASE-OUTPUTS.md and pr-sequence.md use, and it "
     "must stay exempt. Without it, deleting the marker rule would score full marks on M53-M57",
     "GREEN"),
]


def purge_pycache() -> None:
    for d in ROOT.rglob("__pycache__"):
        shutil.rmtree(d, ignore_errors=True)


def run_guard(node: str, guard: str) -> tuple[int, str]:
    """Run ONE guard node. `--tb=line` prints the failure's EXCEPTION TYPE, which is what lets the
    battery tell 'the guard asserted' apart from 'the parser crashed'. A mutation that kills the
    guard with a TypeError is not evidence the invariant is enforced."""
    purge_pycache()
    proc = subprocess.run(
        [str(ROOT / ".venv/bin/python"), "-m", "pytest", "-c", str(ROOT / "pytest-canonical.ini"),
         f"{guard}::{node}", "-q", "--no-header", "-p", "no:cacheprovider", "--tb=line"],
        cwd=ROOT, capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def unpack(case: tuple):
    """(id, file, old, new, node, what[, expect[, guard]])."""
    cid, rel, old, new, node, what = case[:6]
    expect = case[6] if len(case) > 6 else "CAUGHT"
    guard = case[7] if len(case) > 7 else GUARD
    return cid, rel, old, new, node, what, expect, guard


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()

    originals = {rel: (ROOT / rel).read_text(encoding="utf-8")
                 for rel in {c[1] for c in CASES}}
    guards = sorted({unpack(c)[7] for c in CASES})

    print("baseline: every guard used must be GREEN before any mutation")
    for guard in guards:
        purge_pycache()
        base = subprocess.run(
            [str(ROOT / ".venv/bin/python"), "-m", "pytest", "-c", str(ROOT / "pytest-canonical.ini"),
             guard, "-q", "--no-header", "-p", "no:cacheprovider"],
            cwd=ROOT, capture_output=True, text=True)
        if base.returncode != 0:
            print(f"REFUSED: {guard} is not green before mutation:\n" + base.stdout[-2000:])
            return 2
        print(f"  baseline GREEN  {guard}")
    print()

    ok = bad = 0
    try:
        for case in CASES:
            cid, rel, old, new, node, what, expect, guard = unpack(case)
            path = ROOT / rel
            text = originals[rel]
            # POSITIVE PRECONDITION. A case whose anchor is absent proves nothing, and a battery
            # that scores it as a pass is worse than no battery. It is a BATTERY DEFECT, reported
            # as such, never a skip.
            if text.count(old) < 1:
                print(f"{cid}: SKIP-INVALID - anchor not found in {rel} (the mutation would prove "
                      "nothing); fix the battery, do not ignore this")
                bad += 1
                continue
            mutated = text.replace(old, new, 1)
            if mutated == text:
                print(f"{cid}: SKIP-INVALID - the mutation changed nothing in {rel}")
                bad += 1
                continue
            path.write_text(mutated, encoding="utf-8")
            rc, out = run_guard(node, guard)
            path.write_text(text, encoding="utf-8")
            assert path.read_text(encoding="utf-8") == text, f"{cid}: {rel} not restored byte-for-byte"

            if expect == "GREEN":
                if rc == 0:
                    ok += 1
                    print(f"{cid}: REFUSED (stayed green, as required)  {node}\n        ({what})")
                else:
                    bad += 1
                    print(f"{cid}: *** FALSE POSITIVE *** {node} FAILED on a mutation that must "
                          f"NOT associate: {what}")
                continue

            if rc == 0:
                bad += 1
                print(f"{cid}: *** MISS *** {node} stayed green under: {what}")
            elif "AssertionError" not in out:
                # The node failed, but not by ASSERTING. An unrelated exception is not evidence
                # that the invariant is enforced - it is evidence the guard broke.
                bad += 1
                print(f"{cid}: *** WRONG REASON *** {node} failed without an AssertionError "
                      f"(an unrelated exception is not a catch):\n{out[-600:]}")
            else:
                ok += 1
                print(f"{cid}: CAUGHT  {node}\n        ({what})")
    finally:
        for rel, text in originals.items():
            (ROOT / rel).write_text(text, encoding="utf-8")
        purge_pycache()

    caught = sum(1 for c in CASES if unpack(c)[6] == "CAUGHT")
    refused = len(CASES) - caught
    print(f"\nbattery: {ok}/{len(CASES)} correct "
          f"({caught} must-be-CAUGHT, {refused} must-stay-GREEN), {bad} defective")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
