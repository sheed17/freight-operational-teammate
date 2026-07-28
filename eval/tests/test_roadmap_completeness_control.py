"""Roadmap-completeness control guards.

Three control-system defects, and the executable answer to each:

  1. CONTRADICTORY PHASE/STATUS AUTHORITY. One `status` field was answering three questions, so
     "P4 is the sole READY unit", "P4 has not begun" and "two P4 checkpoints landed" were all
     written as status claims about the same word. The registry now carries three orthogonal
     fields - status (selection), execution_state (execution), checkpoint_state (review ladder) -
     and these guards enforce their vocabulary, their mutual consistency, and the rule that a
     navigation document may RESTATE the registry but never contradict it.

  2. P13 TOO BROAD TO GUARANTEE W1-W11. P13 was one atomic unit whose scope read "additional
     operational loops" - satisfiable with any number of loops built, including one. It now
     decomposes into per-loop and cross-loop sub-units, and P13 cannot complete while any
     required sub-unit is incomplete. THE DECOMPOSITION DOES NOT BEGIN P13: these guards assert
     every sub-unit is still BLOCKED / NOT_STARTED / NO_CHECKPOINT.

  3. NO CAPABILITY-TO-IMPLEMENTATION TRACEABILITY. Nothing connected a promised freight
     capability to the unit that will build it and the evidence that will prove it. That is now
     CAPABILITY-TRACEABILITY.yaml, checked here against the product corpus, the registry and the
     source tree in both directions.

Discipline carried from the earlier phases (CLAUDE.md sec 9): DISCOVER populations, never
enumerate them; assert exact SETS, not counts; prove every negative assertion's population; and
make the completeness equivalence MECHANICAL - roadmap_completeness_report() is exercised against
synthetic finished and unfinished worlds, so it can never degenerate into a constant.
"""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "eval"))
from control import inventory as inv  # noqa: E402

IMPL = ROOT / "docs" / "implementation"
REGISTRY = IMPL / "IMPLEMENTATION-REGISTRY.yaml"
TRACE = IMPL / "CAPABILITY-TRACEABILITY.yaml"
CAPABILITY_MAP = ROOT / "docs" / "product" / "FREIGHT-CAPABILITY-MAP.md"
LEGACY = IMPL / "LEGACY-DISPOSITION.md"
BUILD_STATUS = IMPL / "BUILD-STATUS.yaml"
MANIFEST = IMPL / "phase-0-baseline-manifest.yaml"
AUTHORITY_MAP = ROOT / "docs" / "CANONICAL-DOCUMENTS.md"

SELECTION_STATES = {"BLOCKED", "READY", "IN_PROGRESS", "COMPLETE"}
EXECUTION_STATES = {"NOT_STARTED", "IN_PROGRESS", "COMPLETE"}
CHECKPOINT_STATES = {
    "NO_CHECKPOINT", "CHECKPOINT_IMPLEMENTED", "CHECKPOINT_INDEPENDENTLY_REVIEWED",
    "CHECKPOINT_ACCEPTED_FOR_CONTINUATION", "FINAL_ADJUDICATION_PENDING",
    "PHASE_ACCEPTANCE_COMPLETE",
}
REVIEWED_CHECKPOINT_STATES = {
    "CHECKPOINT_INDEPENDENTLY_REVIEWED", "CHECKPOINT_ACCEPTED_FOR_CONTINUATION",
}
IMPLEMENTATION_STATUSES = {
    "SPECIFIED", "PARTIALLY_IMPLEMENTED", "IMPLEMENTED", "LEGACY_IMPLEMENTATION_ONLY",
}
CLAIMS_CODE = {"IMPLEMENTED", "PARTIALLY_IMPLEMENTED", "LEGACY_IMPLEMENTATION_ONLY"}
EVIDENCE_STATUSES = {"NOT_COLLECTED", "IN_PROGRESS", "RECORDED"}

# The eleven canonical loops. FIXED-SPECIFICATION: this is the frozen loop id set of
# docs/specifications/workflows/registry.md, not a discovered file population - a twelfth loop is
# a product decision requiring an explicit change to PRODUCT.md sec 6 and the workflow registry.
LOOPS = tuple(f"W{i}" for i in range(1, 12))

# The three cross-cutting P13 obligations. FIXED-SPECIFICATION: named by the founder correction,
# not discovered - losing one is exactly the silent scope reduction this decomposition prevents.
CROSS_CUTTING_SUB_UNITS = ("P13-H1", "P13-O1", "P13-M1")


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def require_population(items, what: str):
    assert items, f"no {what} to assert over - this test would pass vacuously"
    return items


def registry() -> dict:
    return yaml.safe_load(read(REGISTRY))


def units() -> list[dict]:
    return registry()["units"]


def phase_units(us: list[dict] | None = None) -> list[dict]:
    return [u for u in (us if us is not None else units())
            if re.fullmatch(r"P\d+", u["unit_id"])]


def sub_units(us: list[dict] | None = None) -> list[dict]:
    p13 = next(u for u in (us if us is not None else units()) if u["unit_id"] == "P13")
    return p13["sub_units"]


def capabilities() -> list[dict]:
    return yaml.safe_load(read(TRACE))["capabilities"]


# ============================================================ 1. the three-field status model


def test_the_status_model_is_declared_with_all_three_vocabularies():
    """The model must be written down in the registry itself, not only in a guard. A vocabulary
    that lives only in test code is a vocabulary the next session cannot find."""
    model = registry()["meta"]["status_model"]
    for field, expected in (("status", SELECTION_STATES),
                            ("execution_state", EXECUTION_STATES),
                            ("checkpoint_state", CHECKPOINT_STATES)):
        block = model[field]
        assert block.get("question"), f"{field}: no question stated - what does it answer?"
        declared = {v.split()[0] if isinstance(v, str) else v for v in block["values"]}
        assert declared == expected, (
            f"{field} vocabulary drifted: extra={declared - expected}, missing={expected - declared}"
        )
    assert model["invariants"], "the status model declares no invariants"
    # The deliberate decision not to move P4 out of READY must stay explained, or a later session
    # will "fix" it and silently delete the repository's only next-unit selector.
    why = model["status"]["deliberately_unchanged"]
    assert re.search(r"single_ready_unit|ZERO READY", why), (
        "the reason P4 stays READY while executing is no longer recorded - without it, moving it "
        "looks like a tidy-up rather than the removal of the next-unit selector"
    )


def test_every_unit_carries_three_valid_and_mutually_consistent_states():
    problems = []
    for u in require_population(units(), "registry units"):
        uid, sel = u["unit_id"], u["status"]
        ex, ck = u.get("execution_state"), u.get("checkpoint_state")
        if ex not in EXECUTION_STATES:
            problems.append(f"{uid}: execution_state {ex!r} is not canonical")
            continue
        if ck not in CHECKPOINT_STATES:
            problems.append(f"{uid}: checkpoint_state {ck!r} is not canonical")
            continue
        landed = u.get("landed_checkpoints") or []
        if sel == "COMPLETE" and not (ex == "COMPLETE" and ck == "PHASE_ACCEPTANCE_COMPLETE"):
            problems.append(f"{uid}: COMPLETE but execution_state={ex}, checkpoint_state={ck}")
        if ex == "COMPLETE" and sel != "COMPLETE":
            problems.append(f"{uid}: execution_state COMPLETE while status={sel}")
        if sel == "BLOCKED" and (ex != "NOT_STARTED" or ck != "NO_CHECKPOINT"):
            problems.append(f"{uid}: BLOCKED but execution_state={ex}, checkpoint_state={ck} - "
                            "a blocked unit cannot have executed")
        if ex == "IN_PROGRESS":
            if sel not in {"READY", "IN_PROGRESS"}:
                problems.append(f"{uid}: executing while status={sel}")
            if not landed:
                problems.append(f"{uid}: execution_state IN_PROGRESS with no landed checkpoint - "
                                "a phase cannot claim execution with nothing to show")
        if ex == "NOT_STARTED" and landed:
            problems.append(f"{uid}: NOT_STARTED but records {len(landed)} landed checkpoint(s)")
    assert not problems, "unit state fields are inconsistent:\n  " + "\n  ".join(problems)


def test_at_most_one_unit_executes_and_it_is_the_derived_active_phase():
    executing = [u["unit_id"] for u in units() if u["execution_state"] == "IN_PROGRESS"]
    assert len(executing) <= 1, f"more than one unit is executing: {executing}"
    if not executing:
        return
    derived = yaml.safe_load(read(BUILD_STATUS))["derived"]["active_phase"]
    assert executing[0] == derived, (
        f"the executing unit {executing[0]} is not the mechanically derived active phase "
        f"{derived} - the founder progress snapshot and the registry disagree about what is "
        "being worked on"
    )


def test_the_selector_remains_mechanically_valid_while_a_phase_executes():
    """The whole reason P4 keeps status READY: the control system SELECTS on that field. If a
    later session moves an executing unit out of READY without providing a successor, the
    repository silently loses its ability to name the next approved unit."""
    us = units()
    ready = [u["unit_id"] for u in us if u["status"] == "READY"]
    assert len(ready) == 1, f"exactly one unit must be selectable, found {ready}"
    sys.path.insert(0, str(ROOT / "scripts"))
    import progress_status as ps  # noqa: E402
    assert ps.single_ready_unit(us) == ready[0], (
        "the mechanical selector disagrees with the registry's READY set"
    )
    selected = next(u for u in us if u["unit_id"] == ready[0])
    for dep in selected["dependencies"]:
        dep_unit = next(u for u in us if u["unit_id"] == dep)
        assert dep_unit["status"] == "COMPLETE", (
            f"{ready[0]} is selectable while dependency {dep} is {dep_unit['status']}"
        )


def test_a_claimed_independent_checkpoint_review_must_cite_a_report_that_exists():
    """A checkpoint may CLAIM independent review only with a report on disk. The P4 checkpoints
    are the live case: findings F1..F4 demonstrably came from a review, but that review's REPORT
    was never preserved - so the checkpoint records the gap instead of an accepted review, and a
    later adjudication cannot quietly inherit findings whose source it cannot read."""
    checked = 0
    problems = []
    for u in units():
        for cp in u.get("landed_checkpoints") or []:
            checked += 1
            report = cp.get("independent_review_report")
            state = cp["checkpoint_state"]
            if report:
                assert (ROOT / report).exists(), f"{cp['id']}: cited report {report} missing"
            elif state in REVIEWED_CHECKPOINT_STATES:
                # permitted ONLY when the absence is disclosed as a recorded gap in the checkpoint
                note = (cp.get("independent_review_note") or "").upper()
                if not re.search(r"NOT SELF-CERTIFIED|RECORDED GAP|NOT.{0,20}PRESERVED", note):
                    problems.append(
                        f"{cp['id']}: checkpoint_state {state} with no report and no disclosed gap"
                    )
            assert cp.get("implementer_evidence"), f"{cp['id']}: no implementer evidence recorded"
            assert (ROOT / cp["implementer_evidence"]).exists(), (
                f"{cp['id']}: implementer evidence {cp['implementer_evidence']} does not exist"
            )
    assert checked >= 1, "no landed checkpoints found - this guard proved nothing"
    assert not problems, "checkpoint review claims without evidence:\n  " + "\n  ".join(problems)


def test_an_executing_phase_is_never_described_as_not_begun():
    """The exact contradiction that triggered this correction: P4 carried landed checkpoint
    evidence in one paragraph and 'IT HAS NOT BEGUN' in another. Scoped to the phase that is
    actually executing, so it can never pin a stale moment."""
    executing = [u for u in units() if u["execution_state"] == "IN_PROGRESS"]
    if not executing:
        return
    unit = executing[0]
    n = re.fullmatch(r"P(\d+)", unit["unit_id"]).group(1)
    assert unit.get("landed_checkpoints"), f"{unit['unit_id']} executes with no landed evidence"
    docs = _live_authority_documents()
    rx = re.compile(rf"(?:P{n}\b|Phase\s+{n}\b)[^.\n|]{{0,60}}?"
                    r"(?:\bhas\s+not\s+begun\b|\bnot\s+yet\s+begun\b|\bNOT\s+begun\b|"
                    r"\*{0,3}NOT\s+STARTED)", re.I)
    offenders = []
    for rel in docs:
        text = _strip_historical(read(ROOT / rel))
        for m in rx.finditer(text):
            window = " ".join(m.group(0).split())
            if _EXEMPT.search(window):
                continue
            offenders.append(f"{rel}:{text[: m.start()].count(chr(10)) + 1}: {window[:90]!r}")
    assert not offenders, (
        f"{unit['unit_id']} has landed checkpoint evidence but is described as not begun:\n  "
        + "\n  ".join(offenders)
    )


_EXEMPT = re.compile(r"\brequire[sd]?\b|\bmay not\b|\buntil\b|\bonce\b|\bbefore\b|\bwhen\b|"
                     r"\bunless\b|\bwould\b|\bcannot\b|\bnever\b|\bif\b", re.I)


def _strip_historical(text: str) -> str:
    """Explicitly-labelled historical blocks may retain superseded claims IN PLACE."""
    return re.sub(r"<details>.*?</details>", "", text, flags=re.S)


def _live_authority_documents() -> list[str]:
    """DISCOVERED: current-authority documents plus the root control docs and agent lenses, minus
    the review family and everything the authority map classifies as historical.

    Two principled exclusions, both derived rather than hand-listed:

      * THE REGISTRY ITSELF. It is the authority these documents are being compared AGAINST, not
        a restatement of it. It also explains, in prose, the very contradiction this correction
        removed ('one file said "P4 is READY" while another said "P4 has not begun"') - and a
        guard that fires on the text explaining the defect is the substring-guard failure
        CLAUDE.md sec 9 names.
      * FROZEN ACCEPTANCE CONTRACTS (U-*-ACCEPTANCE.yaml). Their criteria record what an agent
        had to state AT ITS OWN MOMENT and are bound to an adjudicated result and an independent
        report. HANDOFF-04's "the agent states Phase 3 is NOT STARTED" was TRUE when adjudicated
        PASS; rewriting it would falsify closed history, which this correction may never do.
    """
    docs = list(inv.current_authority_documents())
    docs += inv.root_control_like_documents() + inv.agent_files() + inv.compatibility_agent_files()
    historical = set(inv.implementation_review_documents()) | set(inv.historical_documents())
    frozen = {d for d in docs if re.search(r"U-[\w-]+-ACCEPTANCE\.yaml$", d)}
    excluded = historical | frozen | {"docs/implementation/IMPLEMENTATION-REGISTRY.yaml"}
    out = sorted({d for d in docs if d not in excluded and (ROOT / d).exists()})
    assert len(out) >= 15, f"the live-authority scan population collapsed to {len(out)}"
    return out


def test_no_navigation_document_restates_a_phase_state_the_registry_does_not_hold():
    """The generalized replacement for spot-fixing individual sentences. Derived from the
    registry, so it protects every phase and cannot go stale: for each phase, the states it is
    NOT in become forbidden declarations across the discovered live-authority population.
    Requirement prose ("requires P4 COMPLETE", "may not begin", "until P5") is exempt - a
    document may state a precondition about a state a phase is not in."""
    docs = _live_authority_documents()
    forbidden = {
        "NOT_STARTED": [r"is\s+\*{0,3}(?:IN[ _]PROGRESS|COMPLETE)", r"\bhas\s+begun\b"],
        "IN_PROGRESS": [r"\*{0,3}NOT\s+STARTED", r"\bhas\s+not\s+begun\b", r"\bnot\s+yet\s+begun\b",
                        r"\bNOT\s+begun\b", r"\bhas\s+not\s+started\b", r"is\s+\*{0,3}COMPLETE"],
        "COMPLETE": [r"\*{0,3}NOT\s+STARTED", r"is\s+\*{0,3}NOT\s+COMPLETE",
                     r"is\s+\*{0,3}IN[ _]PROGRESS", r"is\s+\*{0,3}BLOCKED",
                     r"\bhas\s+not\s+begun\b"],
    }
    offenders = []
    for u in phase_units():
        n = re.fullmatch(r"P(\d+)", u["unit_id"]).group(1)
        alt = rf"(?:P{n}\b|Phase\s+{n}\b)"
        for pat in forbidden[u["execution_state"]]:
            rx = re.compile(rf"{alt}[^.\n|]{{0,60}}?{pat}", re.I)
            for rel in docs:
                text = _strip_historical(read(ROOT / rel))
                for m in rx.finditer(text):
                    window = " ".join(m.group(0).split())
                    if _EXEMPT.search(window):
                        continue
                    line = text[: m.start()].count("\n") + 1
                    offenders.append(
                        f"{rel}:{line}: {u['unit_id']} is {u['execution_state']} but the document "
                        f"says {window[:90]!r}"
                    )
    assert not offenders, (
        "navigation documents contradict the registry's execution_state:\n  "
        + "\n  ".join(offenders)
    )


def test_r07_is_never_represented_as_contained_anywhere_live():
    """R-07 is the one status the repository has always stated consistently. This guard keeps it
    that way from the traceability layer too: the manifest record, and no live-authority document
    may call it contained or closed."""
    manifest = read(MANIFEST)
    assert "status: OPEN - NOT CONTAINED" in manifest, "the R-07 manifest record changed"
    offenders = []
    for rel in _live_authority_documents():
        text = _strip_historical(read(ROOT / rel))
        for m in re.finditer(r"R-07[^.\n|]{0,60}?(?:\bis\s+\*{0,3}CONTAINED|\bnow\s+closed\b|"
                             r"\bis\s+\*{0,3}CLOSED\b)", text, re.I):
            window = " ".join(m.group(0).split())
            if _EXEMPT.search(window):
                continue
            offenders.append(f"{rel}:{text[: m.start()].count(chr(10)) + 1}: {window[:90]!r}")
    assert not offenders, "R-07 is represented as contained:\n  " + "\n  ".join(offenders)


def test_the_recorded_effect_violation_surface_is_the_mechanically_recomputed_one():
    """The four-versus-five drift: IMPLEMENTATION-SURFACE.yaml counted an edge (brain_runtime)
    that a P4 checkpoint had already cut. Any document stating a violation COUNT must state the
    number the probe actually computes."""
    sys.path.insert(0, str(ROOT / "eval"))
    from phase0 import import_probe
    live = import_probe.effect_adapter_import_violations()[0]
    recorded = yaml.safe_load(read(MANIFEST))["effect_adapter_import_gate"]["violation_edges"]
    assert len(live) == len(recorded), (
        f"the probe finds {len(live)} effect-capable violation edges but the manifest records "
        f"{len(recorded)} - the gate's exact set drifted"
    )
    # Any STATED count of effect-capable edges must equal the computed one. The first version of
    # this guard pinned the single stale phrase "five effect-capable import edges" and the
    # mutation battery caught it staying green when the drift returned as "five effect-capable
    # violation edges" - a same-defect substitution one word away. Parse the number instead.
    words = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
             "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}
    surface = read(IMPL / "IMPLEMENTATION-SURFACE.yaml")
    # `edges?` - the SINGULAR counts too. When the surface fell to one residual edge at P4/U4.10 the
    # honest sentence became "the ONE effect-capable violation edge", and a plural-only pattern
    # silently stopped checking anything: the guard would pass because it found NO claim, which is
    # precisely the drift it exists to catch. Accepting the singular strictly widens coverage.
    claims = re.findall(
        r"\b(\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+"
        r"effect-capable\s+\S+\s+edges?\b",
        re.sub(r"\s+", " ", surface), re.I,
    )
    assert claims, "IMPLEMENTATION-SURFACE.yaml states no effect-capable edge count to check"
    wrong = [c for c in claims
             if (int(c) if c.isdigit() else words[c.lower()]) != len(live)]
    assert not wrong, (
        f"IMPLEMENTATION-SURFACE.yaml claims {wrong} effect-capable edges; the probe computes "
        f"{len(live)} and the manifest records {len(recorded)}"
    )


# ============================================================ 2. the P13 decomposition


def test_every_loop_w1_to_w11_has_a_p13_sub_unit():
    """Exact SET, not a count - a same-count substitution must fail."""
    subs = require_population(sub_units(), "P13 sub-units")
    owned = set()
    for s in subs:
        owned |= set(re.findall(r"\bW\d+\b", s["owning_loop_or_surface"]))
    missing = [w for w in LOOPS if w not in owned]
    assert not missing, f"P13 decomposition does not own these loops: {missing}"
    # each loop must have its OWN dedicated sub-unit, not merely be mentioned by a sibling
    dedicated = {s["sub_unit_id"] for s in subs}
    absent = [f"P13-{w}" for w in LOOPS if f"P13-{w}" not in dedicated]
    assert not absent, f"loops with no dedicated P13 sub-unit: {absent}"
    # and the loop set itself must still be exactly eleven, in the canonical index
    specs = sorted(p.name for p in (ROOT / "docs" / "specifications" / "workflows").glob("W*.md"))
    assert len(specs) == 11, f"expected 11 workflow specs, found {len(specs)}: {specs}"


def test_the_cross_cutting_sub_units_are_present_and_are_not_loops():
    """The handoff, Operator-coordination and authority-migration obligations must each be their
    own unit - and none of them may be represented as a twelfth loop."""
    subs = {s["sub_unit_id"]: s for s in sub_units()}
    for required in CROSS_CUTTING_SUB_UNITS:
        assert required in subs, f"the P13 decomposition lost {required}"
    owner = subs["P13-O1"]["owning_loop_or_surface"]
    assert "SURFACE" in owner.upper(), (
        "P13-O1 must own a cross-cutting SURFACE - customer service and operational "
        "management/reporting are surfaces, never loops (OPERATIONAL-LOOPS.md sec 4-6)"
    )
    assert len(subs) == len(LOOPS) + len(CROSS_CUTTING_SUB_UNITS), (
        f"the P13 sub-unit population is {len(subs)} - expected the eleven loops plus H1, O1, M1"
    )


def test_every_p13_sub_unit_carries_the_full_obligation_contract():
    """A sub-unit that omits a field is a sub-unit whose obligation can be argued away later."""
    required_fields = [
        "owning_loop_or_surface", "operational_trigger", "durable_work_item", "closure_condition",
        "required_freight_entities", "required_evidence", "policy_and_approval_boundary",
        "allowed_effect_classes", "systems_and_adapters", "degraded_mode_behavior",
        "human_escalation_boundary", "design_partner_evidence_required",
        "historical_evaluation_requirement", "shadow_acceptance", "supervised_acceptance",
        "bounded_autonomy_eligibility", "rollback_or_compensation_requirement", "depends_on",
        "acceptance_contract", "status", "execution_state", "checkpoint_state",
    ]
    problems = []
    for s in require_population(sub_units(), "P13 sub-units"):
        for f in required_fields:
            if f not in s:
                problems.append(f"{s['sub_unit_id']}: missing {f}")
            elif f != "allowed_effect_classes" and not s[f]:
                # allowed_effect_classes may legitimately be EMPTY (a handoff performs no effect)
                problems.append(f"{s['sub_unit_id']}: {f} is empty")
    assert not problems, "P13 sub-units with incomplete contracts:\n  " + "\n  ".join(problems)


def test_every_p13_sub_unit_dependency_resolves():
    """A sub-unit may depend on a phase or a sibling sub-unit; it may not depend on a ghost."""
    us = units()
    known = {u["unit_id"] for u in us} | {s["sub_unit_id"] for s in sub_units(us)}
    problems = []
    for s in require_population(sub_units(us), "P13 sub-units"):
        deps = s["depends_on"]
        assert deps, f"{s['sub_unit_id']}: depends on nothing - what unblocks it?"
        for d in deps:
            if d not in known:
                problems.append(f"{s['sub_unit_id']} depends on unknown unit {d}")
    assert not problems, "unresolved sub-unit dependencies:\n  " + "\n  ".join(problems)


def test_every_p13_sub_unit_names_an_acceptance_contract_that_exists():
    """An implementation unit that references no acceptance contract fails the build - and a
    contract that names a file must name one that exists."""
    checked = 0
    problems = []
    for s in require_population(sub_units(), "P13 sub-units"):
        contract = s["acceptance_contract"]
        assert contract, f"{s['sub_unit_id']}: no acceptance contract"
        for cited in re.findall(r"docs/[\w./-]+\.md", contract):
            checked += 1
            if not (ROOT / cited).exists():
                problems.append(f"{s['sub_unit_id']} cites missing contract {cited}")
        assert re.search(r"\bG\d+\b", contract), (
            f"{s['sub_unit_id']}: acceptance contract names no release gate"
        )
    assert checked >= 11, f"only {checked} contract files verified - population too small"
    assert not problems, "acceptance contracts that do not exist:\n  " + "\n  ".join(problems)


def test_the_p13_decomposition_has_not_begun_p13():
    """Specifying an obligation is not discharging it. Every sub-unit must still be untouched, or
    this correction would itself have started the phase it was only allowed to describe."""
    started = []
    for s in require_population(sub_units(), "P13 sub-units"):
        if (s["status"], s["execution_state"], s["checkpoint_state"]) != (
                "BLOCKED", "NOT_STARTED", "NO_CHECKPOINT"):
            started.append(f"{s['sub_unit_id']}: {s['status']}/{s['execution_state']}/"
                           f"{s['checkpoint_state']}")
    assert not started, "P13 sub-units recorded as started:\n  " + "\n  ".join(started)
    p13 = next(u for u in units() if u["unit_id"] == "P13")
    assert p13["status"] == "BLOCKED", f"P13 is {p13['status']} - the decomposition may not start it"


def p13_completion_errors(us: list[dict]) -> list[str]:
    """P13 may be COMPLETE only when every required sub-unit is COMPLETE - including the three
    cross-cutting obligations, which no loop sub-unit can discharge on their behalf."""
    p13 = next(u for u in us if u["unit_id"] == "P13")
    if p13["status"] != "COMPLETE":
        return []
    errs = [f"P13 is COMPLETE while required sub-unit {s['sub_unit_id']} is {s['status']}"
            for s in p13["sub_units"]
            if s.get("required", True) and s["status"] != "COMPLETE"]
    present = {s["sub_unit_id"] for s in p13["sub_units"] if s["status"] == "COMPLETE"}
    for needed in tuple(f"P13-{w}" for w in LOOPS) + CROSS_CUTTING_SUB_UNITS:
        if needed not in present:
            errs.append(f"P13 is COMPLETE without a completed {needed}")
    return errs


def test_p13_cannot_be_complete_while_a_required_sub_unit_is_incomplete():
    """Proven by MUTATION rather than asserted. The predicate is exercised against a synthetic
    world where P13 is COMPLETE and one sub-unit is not: if it does not object there, it is a
    decoration."""
    assert p13_completion_errors(units()) == [], (
        "P13 is BLOCKED and no sub-unit has started, so the predicate must be quiet today"
    )
    mutant = copy.deepcopy(units())
    p13 = next(u for u in mutant if u["unit_id"] == "P13")
    p13["status"] = "COMPLETE"
    p13["execution_state"] = "COMPLETE"
    p13["checkpoint_state"] = "PHASE_ACCEPTANCE_COMPLETE"
    for s in p13["sub_units"]:
        s["status"] = "COMPLETE"
    assert p13_completion_errors(mutant) == [], "an all-complete P13 must be permitted"

    # a loop left unbuilt must veto completion
    p13["sub_units"][0]["status"] = "BLOCKED"
    errs = p13_completion_errors(mutant)
    assert any("P13-W1" in e for e in errs), (
        f"P13 completed with a required loop sub-unit incomplete (errors: {errs})"
    )

    # and demoting it to optional must NOT buy completion, because W1 is structurally required
    p13["sub_units"][0]["required"] = False
    errs = p13_completion_errors(mutant)
    assert any("P13-W1" in e for e in errs), (
        "a required loop was quietly demoted to optional and P13 completed anyway - the exact "
        "scope-reduction hole this decomposition exists to close"
    )
    p13["sub_units"][0].update(status="COMPLETE", required=True)

    # each cross-cutting obligation must veto independently
    for sid in CROSS_CUTTING_SUB_UNITS:
        target = next(s for s in p13["sub_units"] if s["sub_unit_id"] == sid)
        target["status"] = "BLOCKED"
        errs = p13_completion_errors(mutant)
        assert any(sid in e for e in errs), f"P13 completed without {sid}"
        target["status"] = "COMPLETE"

    # and a deleted sub-unit must be caught too - not merely an incomplete one
    p13["sub_units"] = [s for s in p13["sub_units"] if s["sub_unit_id"] != "P13-M1"]
    assert any("P13-M1" in e for e in p13_completion_errors(mutant)), (
        "P13 completed after the authority-migration sub-unit was deleted outright"
    )


def test_the_cross_loop_handoff_unit_states_atomicity_ownership_and_evidence():
    """A handoff sub-unit that does not demand atomicity, an accountable owner and the dedup
    evidence is a handoff that can silently drop an obligation."""
    h1 = next(s for s in sub_units() if s["sub_unit_id"] == "P13-H1")
    blob = " ".join(str(v) for v in h1.values())
    for label, pattern in (("atomicity", r"SAME COMMIT|atomic"),
                           ("ownership", r"owner|ownerless|responsibility gap"),
                           ("evidence", r"source event id|crash oracle|crash")):
        assert re.search(pattern, blob, re.I), f"P13-H1 states no {label} requirement"
    assert h1["allowed_effect_classes"] == [], (
        "a handoff must perform NO external effect - it creates an obligation, not an action"
    )
    cap = next(c for c in capabilities() if c["capability_id"] == "CAP-22")
    assert re.search(r"AC-FC-016", cap["supervised_acceptance_contract"]), (
        "the cross-loop handoff capability lost its zero-tolerance acceptance case AC-FC-016"
    )


def test_the_operator_is_never_a_second_workflow_source_of_truth():
    """The Operator proposes and coordinates; Pipeline Instances remain the durable orchestrator.
    A row that gave the Operator its own machine or its own effect classes would be a second
    orchestration system, which the architecture forbids outright."""
    cap = next(c for c in capabilities() if c["capability_id"] == "CAP-19")
    machine = cap["required_state_machine_or_pipeline"]
    assert "NONE OF ITS OWN" in machine.upper(), (
        "CAP-19 gives the Operator a workflow machine of its own - that is a second workflow "
        "source of truth"
    )
    assert re.search(r"Pipeline Instances remain", machine), (
        "CAP-19 no longer records that Pipeline Instances remain the durable orchestrator"
    )
    effects = " ".join(cap["allowed_effect_classes"])
    assert effects.startswith("none of its own"), (
        f"CAP-19 grants the Operator effect classes of its own: {effects!r}"
    )
    boundaries = cap["permanent_human_boundaries"]
    for forbidden in ("click", "write", "send", "move money", "grant itself authority"):
        assert forbidden in boundaries, (
            f"CAP-19 no longer records that the Operator cannot {forbidden}"
        )
    o1 = next(s for s in sub_units() if s["sub_unit_id"] == "P13-O1")
    assert "OPERATOR PROPOSES" in o1["policy_and_approval_boundary"].upper(), (
        "P13-O1 lost the proposer/coordinator boundary"
    )
    assert re.search(r"creates no parallel work object|no second workflow record",
                     o1["durable_work_item"], re.I), (
        "P13-O1 no longer states that the Operator creates no parallel work object"
    )


# ============================================================ 3. capability traceability


def test_the_eighteen_promised_capability_areas_are_all_covered():
    """Exact SET against the product map's own headings - if an area is dropped from either
    document, or renamed in one and not the other, this fails."""
    headings = re.findall(r"^## \d+\.\s+([^—\n]+?)\s+—", read(CAPABILITY_MAP), re.M)
    areas = [h.strip() for h in headings]
    assert len(areas) == 18, f"FREIGHT-CAPABILITY-MAP.md declares {len(areas)} areas, expected 18"
    traced = [c["capability_name"] for c in capabilities()[:18]]
    assert traced == areas, (
        "the traceability registry's first eighteen rows are not the eighteen promised capability "
        f"areas, in order: extra={set(traced) - set(areas)}, missing={set(areas) - set(traced)}"
    )


def test_every_capability_carries_the_full_traceability_contract():
    """Every field the founder correction requires, on every row."""
    required_fields = [
        "capability_id", "capability_name", "capability_area", "owning_loop_or_surface",
        "product_authority_reference", "workflow_spec_reference", "owning_phase",
        "owning_implementation_unit", "prerequisite_units", "required_entities", "required_events",
        "required_state_machine_or_pipeline", "required_evidence_types", "required_policy_classes",
        "required_adapters_or_channels", "allowed_effect_classes", "permanent_human_boundaries",
        "design_partner_evidence_status", "historical_evaluation_status",
        "shadow_acceptance_contract", "supervised_acceptance_contract", "bounded_autonomy_contract",
        "implementation_status", "source_implementation_reference", "test_or_eval_reference",
        "release_gate_reference", "unresolved_decisions", "current_truth_source",
    ]
    # these may legitimately be empty/null: an absent autonomy contract, an unimplemented
    # capability citing no source, a capability that performs no effect, a row with no open
    # decision. Their PRESENCE is required; their content is checked by the guards below.
    nullable = {"bounded_autonomy_contract", "source_implementation_reference",
                "allowed_effect_classes", "unresolved_decisions", "required_adapters_or_channels"}
    problems = []
    for c in require_population(capabilities(), "capability rows"):
        for f in required_fields:
            if f not in c:
                problems.append(f"{c.get('capability_id', '?')}: missing {f}")
            elif f not in nullable and not c[f]:
                problems.append(f"{c['capability_id']}: {f} is empty")
    assert not problems, "capability rows with incomplete contracts:\n  " + "\n  ".join(problems)


def test_every_capability_names_a_loop_or_surface_a_phase_and_an_implementation_unit():
    us = units()
    unit_ids = {u["unit_id"] for u in us} | {s["sub_unit_id"] for s in sub_units(us)}
    problems = []
    for c in require_population(capabilities(), "capability rows"):
        cid = c["capability_id"]
        if not c.get("owning_loop_or_surface"):
            problems.append(f"{cid}: no owning loop or surface")
        if c.get("owning_phase") not in unit_ids:
            problems.append(f"{cid}: owning phase {c.get('owning_phase')} is not a registry unit")
        if c.get("owning_implementation_unit") not in unit_ids:
            problems.append(
                f"{cid}: implementation unit {c.get('owning_implementation_unit')} does not exist"
            )
        for dep in c.get("prerequisite_units") or []:
            if dep not in unit_ids:
                problems.append(f"{cid}: prerequisite {dep} does not exist")
    assert not problems, "capability rows with broken ownership:\n  " + "\n  ".join(problems)


def test_every_capability_and_its_unit_reference_an_acceptance_contract():
    us = units()
    by_unit = {u["unit_id"]: u.get("acceptance_contract") for u in us}
    by_unit.update({s["sub_unit_id"]: s.get("acceptance_contract") for s in sub_units(us)})
    problems = []
    for c in require_population(capabilities(), "capability rows"):
        cid = c["capability_id"]
        if not c.get("shadow_acceptance_contract"):
            problems.append(f"{cid}: no shadow acceptance contract")
        if not c.get("supervised_acceptance_contract"):
            problems.append(f"{cid}: no supervised acceptance contract")
        if not c.get("release_gate_reference"):
            problems.append(f"{cid}: no release gate")
        if not by_unit.get(c["owning_implementation_unit"]):
            problems.append(
                f"{cid}: its implementation unit {c['owning_implementation_unit']} references no "
                "acceptance contract"
            )
    assert not problems, "missing acceptance references:\n  " + "\n  ".join(problems)


def test_a_capability_is_implemented_only_with_source_and_executable_evidence():
    """A claim of code is checked against the tree, in both directions."""
    checked = 0
    problems = []
    for c in require_population(capabilities(), "capability rows"):
        cid, status = c["capability_id"], c["implementation_status"]
        assert status in IMPLEMENTATION_STATUSES, f"{cid}: invalid status {status!r}"
        refs = c.get("source_implementation_reference")
        if status in CLAIMS_CODE:
            if not refs:
                problems.append(f"{cid} claims {status} with no source reference")
                continue
            for ref in refs:
                path = ROOT / ref["path"]
                if not path.exists():
                    problems.append(f"{cid}: source file {ref['path']} does not exist")
                elif not re.search(rf"\b{re.escape(ref['symbol'])}\b",
                                   path.read_text(encoding="utf-8")):
                    problems.append(
                        f"{cid}: symbol {ref['symbol']!r} absent from {ref['path']} - the "
                        "registry presents unwritten code as written"
                    )
                checked += 1
            cited = re.findall(r"(eval/[\w./-]+\.py)", c.get("test_or_eval_reference") or "")
            if not cited:
                problems.append(f"{cid} claims {status} with no executable evidence reference")
            for t in cited:
                if not (ROOT / t).exists():
                    problems.append(f"{cid}: cited test file {t} does not exist")
        elif refs:
            problems.append(f"{cid} is {status} yet cites source - one of the two is wrong")
    assert checked >= 4, f"only {checked} source citations verified - population too small"
    assert not problems, (
        "capability implementation claims without evidence:\n  " + "\n  ".join(problems)
    )


def test_no_legacy_module_is_silently_treated_as_target_authority():
    """A pre-reset module that happens to share a name with a canonical concept is the thing the
    capability REPLACES, never proof that it is built. Any row citing legacy source must name its
    disposition and say plainly that it is not the canonical capability."""
    legacy_text = read(LEGACY)
    checked = 0
    problems = []
    for c in capabilities():
        if c["implementation_status"] != "LEGACY_IMPLEMENTATION_ONLY":
            continue
        checked += 1
        disp = c.get("legacy_disposition_reference")
        if not disp:
            problems.append(f"{c['capability_id']}: legacy implementation with no disposition")
            continue
        if "LEGACY-DISPOSITION.md" not in disp:
            problems.append(f"{c['capability_id']}: disposition does not cite LEGACY-DISPOSITION.md")
        for ref in c.get("source_implementation_reference") or []:
            module = Path(ref["path"]).name
            if module not in legacy_text:
                problems.append(
                    f"{c['capability_id']}: cites legacy module {module} that carries no "
                    "disposition - an undispositioned legacy module is one nobody has agreed to "
                    "replace"
                )
            note = (ref.get("note") or "").upper()
            if "NOT THE CANONICAL" not in note and "NEVER THE CANONICAL" not in note:
                problems.append(
                    f"{c['capability_id']}: the {module} citation does not say it is NOT the "
                    "canonical capability - that is how a prototype becomes 'done'"
                )
    assert checked >= 1, "no legacy-implementation rows found - this guard proved nothing"
    assert not problems, "legacy treated as target authority:\n  " + "\n  ".join(problems)


def supervised_autonomy_errors(caps: list[dict]) -> list[str]:
    errs = []
    for c in caps:
        cid = c["capability_id"]
        effects = [e for e in (c.get("allowed_effect_classes") or [])
                   if not str(e).lower().startswith("none")]
        if effects and not c.get("supervised_acceptance_contract"):
            errs.append(f"{cid}: performs effects {effects[:2]} with no supervised contract")
        if c.get("bounded_autonomy_contract") and not c.get("release_gate_reference"):
            errs.append(f"{cid}: claims bounded autonomy with no release gate")
    return errs


def test_supervised_and_autonomous_claims_require_their_contracts():
    """Both proven against synthetic violations, so neither can pass vacuously."""
    assert supervised_autonomy_errors(capabilities()) == [], "live rows violate the contract rules"
    mutant = copy.deepcopy(capabilities())
    row = next(c for c in mutant if c["capability_id"] == "CAP-11")
    row["supervised_acceptance_contract"] = ""
    errs = supervised_autonomy_errors(mutant)
    assert any("supervised" in e for e in errs), (
        f"a capability with real effect classes was accepted with no supervised contract: {errs}"
    )
    row["supervised_acceptance_contract"] = "docs/specifications/acceptance/W8-acceptance.md (G8)"
    row["bounded_autonomy_contract"] = "invoice release becomes autonomous"
    row["release_gate_reference"] = None
    errs = supervised_autonomy_errors(mutant)
    assert any("autonomy" in e for e in errs), (
        f"an autonomy claim was accepted with no release gate: {errs}"
    )


def test_the_capability_map_and_the_registry_agree_on_what_is_built():
    """A navigation document may not claim capability beyond the machine-readable status. Parsed
    per SECTION, so a claim cannot hide behind a neighbouring paragraph."""
    text = read(CAPABILITY_MAP)
    sections = re.split(r"^## (\d+)\.", text, flags=re.M)[1:]
    pairs = list(zip(sections[0::2], sections[1::2]))
    assert len(pairs) == 18, f"parsed {len(pairs)} capability sections, expected 18"
    caps = {c["capability_id"]: c for c in capabilities()}
    offenders = []
    for num, body in pairs:
        cid = f"CAP-{int(num):02d}"
        status = caps[cid]["implementation_status"]
        m = re.search(r"\*\*Current state:\*\*\s*([A-Za-z_]+)", body)
        assert m, f"{cid}: the capability map states no current state"
        stated = m.group(1).upper()
        if status == "SPECIFIED" and stated != "SPECIFIED":
            offenders.append(f"{cid}: map says {stated}, traceability says {status}")
        if status != "SPECIFIED" and stated == "SPECIFIED":
            # the reverse direction: real partial code must not hide behind SPECIFIED either
            offenders.append(f"{cid}: map says SPECIFIED, traceability records {status}")
    assert not offenders, (
        "the capability map and the traceability registry disagree:\n  " + "\n  ".join(offenders)
    )


def test_evidence_and_gate_vocabularies_are_canonical():
    problems = []
    for c in require_population(capabilities(), "capability rows"):
        cid = c["capability_id"]
        for field in ("design_partner_evidence_status", "historical_evaluation_status"):
            if c[field] not in EVIDENCE_STATUSES:
                problems.append(f"{cid}: {field}={c[field]!r} is not canonical")
        gate = c.get("release_gate_reference")
        if gate and not re.fullmatch(r"G\d+", str(gate)):
            problems.append(f"{cid}: release gate {gate!r} is not a G0-G10 identifier")
    assert not problems, "non-canonical vocabulary:\n  " + "\n  ".join(problems)


def test_the_traceability_artifact_is_registered_as_canonical():
    """An unclassified load-bearing document is exactly the gap the authority map exists to
    close."""
    amap = read(AUTHORITY_MAP)
    assert TRACE.name in amap, "CAPABILITY-TRACEABILITY.yaml is not classified in the authority map"
    rows = [ln for ln in amap.split("\n")
            if ln.strip().startswith("|") and TRACE.name in ln.split("|")[1]]
    assert rows, f"{TRACE.name} is not a subject row in the authority map"
    assert any(re.search(r"IMPLEMENTATION_CONTROL|CANONICAL", r) for r in rows), (
        f"{TRACE.name} is registered without an authority level that may direct implementation"
    )


# ============================================================ 4. the completeness equivalence


def roadmap_completeness_report(us: list[dict] | None = None,
                                caps: list[dict] | None = None) -> dict:
    """THE EQUIVALENCE, COMPUTED.

        full_roadmap_complete
          <=> every required phase COMPLETE
          AND every required P13 sub-unit COMPLETE
          AND every mandatory capability at its required acceptance state
          AND no mandatory release gate left open

    A capability is at its required acceptance state only when it is IMPLEMENTED, its
    design-partner evidence is RECORDED and its historical evaluation is RECORDED - because a
    capability nobody has validated against a real freight operation is a capability that exists
    only in this repository.
    """
    us = us if us is not None else units()
    caps = caps if caps is not None else capabilities()
    incomplete_phases = [u["unit_id"] for u in phase_units(us) if u["status"] != "COMPLETE"]
    incomplete_sub_units = sorted(
        s["sub_unit_id"] for s in sub_units(us)
        if s.get("required", True) and s["status"] != "COMPLETE"
    )
    # Structural completeness of the decomposition counts too: a DELETED sub-unit is not a
    # completed one, and p13_completion_errors is the single predicate that knows this.
    structural = p13_completion_errors(us)
    unsatisfied = [c["capability_id"] for c in caps if not (
        c["implementation_status"] == "IMPLEMENTED"
        and c["design_partner_evidence_status"] == "RECORDED"
        and c["historical_evaluation_status"] == "RECORDED"
    )]
    by_id = {c["capability_id"]: c for c in caps}
    open_gates = sorted({str(by_id[cid].get("release_gate_reference")) for cid in unsatisfied
                         if by_id[cid].get("release_gate_reference")})
    return {
        "incomplete_phases": incomplete_phases,
        "incomplete_p13_sub_units": incomplete_sub_units,
        "p13_structural_errors": structural,
        "capabilities_without_required_acceptance": unsatisfied,
        "open_mandatory_release_gates": open_gates,
        "full_roadmap_complete": not (incomplete_phases or incomplete_sub_units or structural
                                      or unsatisfied or open_gates),
    }


def _finished_world() -> tuple[list[dict], list[dict]]:
    us = copy.deepcopy(units())
    for u in us:
        u["status"] = "COMPLETE"
        u["execution_state"] = "COMPLETE"
        u["checkpoint_state"] = "PHASE_ACCEPTANCE_COMPLETE"
        for s in u.get("sub_units") or []:
            s["status"] = "COMPLETE"
    caps = copy.deepcopy(capabilities())
    for c in caps:
        c["implementation_status"] = "IMPLEMENTED"
        c["design_partner_evidence_status"] = "RECORDED"
        c["historical_evaluation_status"] = "RECORDED"
    return us, caps


def _with(us: list[dict], unit_id: str, **fields) -> list[dict]:
    for u in us:
        if u["unit_id"] == unit_id:
            u.update(fields)
    return us


def _with_sub(us: list[dict], sub_id: str, **fields) -> list[dict]:
    for s in sub_units(us):
        if s["sub_unit_id"] == sub_id:
            s.update(fields)
    return us


def _with_cap(caps: list[dict], cap_id: str, **fields) -> list[dict]:
    for c in caps:
        if c["capability_id"] == cap_id:
            c.update(fields)
    return caps


def test_the_roadmap_cannot_be_complete_while_any_promised_capability_is_only_documented():
    """The founder question this whole correction exists to answer: CAN the complete roadmap be
    marked finished while any promised W1-W11 capability remains unimplemented? The answer must be
    mechanically NO - so the equivalence is exercised against a fully-finished synthetic world and
    then broken one conjunct at a time. A predicate that is merely always-False would pass a
    today-only assertion; it must also be able to say True, or it proves nothing."""
    live = roadmap_completeness_report()
    assert live["full_roadmap_complete"] is False, (
        "the roadmap reports COMPLETE - it is not: P4 is executing, P5-P14 have not begun, and "
        "no freight capability is implemented"
    )
    assert live["incomplete_phases"], "no incomplete phases found - the report parsed nothing"
    assert len(live["capabilities_without_required_acceptance"]) >= 18, (
        "fewer than the eighteen promised areas are unsatisfied - the capability corpus collapsed"
    )

    # a world where everything really is done -> True (so the predicate is not a constant)
    done_units, done_caps = _finished_world()
    assert roadmap_completeness_report(done_units, done_caps)["full_roadmap_complete"] is True, (
        "a genuinely finished program cannot be recognised - the predicate is a constant False, "
        "which proves nothing about the cases it is meant to catch"
    )

    # then break each conjunct independently; every one must veto completion
    for label, mutate in (
        ("an incomplete phase", lambda u, c: (_with(u, "P14", status="BLOCKED"), c)),
        ("an unbuilt loop", lambda u, c: (_with_sub(u, "P13-W9", status="BLOCKED"), c)),
        ("a missing cross-loop handoff unit",
         lambda u, c: (_with_sub(u, "P13-H1", status="BLOCKED"), c)),
        ("a missing authority migration unit",
         lambda u, c: (_with_sub(u, "P13-M1", status="BLOCKED"), c)),
        ("a missing Operator coordination unit",
         lambda u, c: (_with_sub(u, "P13-O1", status="BLOCKED"), c)),
        ("an unimplemented capability",
         lambda u, c: (u, _with_cap(c, "CAP-10", implementation_status="SPECIFIED"))),
        ("a capability with no design-partner evidence",
         lambda u, c: (u, _with_cap(c, "CAP-05", design_partner_evidence_status="NOT_COLLECTED"))),
        ("a capability never evaluated against history",
         lambda u, c: (u, _with_cap(c, "CAP-08", historical_evaluation_status="IN_PROGRESS"))),
    ):
        mu, mc = mutate(copy.deepcopy(done_units), copy.deepcopy(done_caps))
        assert roadmap_completeness_report(mu, mc)["full_roadmap_complete"] is False, (
            f"the roadmap was allowed to complete with {label}"
        )


def test_the_completeness_rule_is_written_down_where_a_human_will_find_it():
    """A mechanical rule nobody can read is a rule the next session will re-derive differently."""
    rule = yaml.safe_load(read(TRACE))["meta"]["completeness_rule"]
    for token in ("IF AND ONLY IF", "P13 sub-unit", "release gate"):
        assert token in rule, f"the completeness rule no longer states {token!r}"
    assert "roadmap_completeness_report" in rule, (
        "the completeness rule does not name the function that computes it - prose and mechanism "
        "must point at each other"
    )
