"""U0.3 - the null-gate startup check (AC-CKPT-6-missing). NOT YET EXECUTABLE.

FINDING P0-F1: the frozen PR sequence lists U0.3 as a Phase-0 unit with AC-CKPT-6-missing as its
completion oracle. It is not achievable at Phase 0, and this file records why rather than faking it.

The case asserts that an action class with a NULL policy gate causes the system to FAIL TO START.

### THE GROUND FOR DEFERRING IT WAS CORRECTED AT P3 (independent-review finding F-G, adjudicating
the implementer-raised F-2). The original ground - "typed policy and action classes do not exist
until P8" - is SUPERSEDED and must not be repeated anywhere. P3 legitimately contains the MINIMAL
STRUCTURAL contract checkpoint step 5 (`policy_evaluation`) cannot be written without: the
`GateDecision` vocabulary and a fail-closed `GateRegistry` lookup. A step that evaluates policy
needs a typed gate to evaluate; a gate expressible as an absence is not a gate.

The case is nonetheless STILL DEFERRED, on the ground that actually holds: it is about STARTUP
over a REGISTERED PRODUCTION POPULATION, and that population is still EMPTY. P3 ships dark - no
production module constructs a `GateRegistry` or registers an action class. Running the probe
today would still enumerate ZERO gates and report green: the M-9 false-green pattern, and the
same error as PL-6 (a gate enabled before the thing it gates exists). The roadmap already names
the rule: a gate with nothing behind it is theatre.

WHAT P8 STILL OWNS, and what therefore still gates this case: rule authoring, compilation,
versioning, activation, precedence and conflict resolution, richer action-class descriptors, the
autonomy runtime, and the expectation/exception/compensation systems. Startup-time registration
arrives with those.

Also still true, and still the reason a "safe default" is not a substitute: `lane_graduation`'s
`is_autonomous()` returns a FAIL-SAFE DEFAULT when no graduation exists. A default says "nobody
decided, so we picked the safe answer"; the canonical rule says "nobody decided, so REFUSE TO
START". The first is safe today and silently wrong tomorrow.

So the honest outcome remains NOT_YET_EXECUTABLE, adjudicated in the baseline manifest, green at
P8 - and the probes below PROVE both halves (the vocabulary exists and is confined; the production
registration population is empty) rather than asserting either.
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase0 import gate_scan, manifest
from phase0.evaluation import EmptyPopulationError, Evaluation


def test_the_typed_gate_population_is_now_non_empty_and_confined_to_the_checkpoint_kernel():
    """REPLACES `test_the_canonical_gate_population_is_provably_empty_today` (P3).

    The original proved the population was EMPTY, which was the truth from P0 until P3 and the
    reason AC-CKPT-6-missing could not be executed without reporting a false green. P3 ended that
    condition: checkpoint step 5 is `policy_evaluation`, so the kernel had to carry a typed gate
    ladder (ADR-010 §3.1 amendment A3) with a fail-closed `GateRegistry`. Asserting emptiness now
    would be asserting something false, so the probe is replaced rather than deleted or relaxed.

    What it defends NOW is the property that actually still protects the system: the gate
    vocabulary exists in the checkpoint kernel and NOWHERE ELSE. A gate decision appearing in a
    workflow, an adapter or a callback would mean policy had leaked out of the boundary that
    evaluates it - the thing this probe existed to notice.

    ### ADJUDICATED at P3 (finding F-G / F-2): the manifest's stale ground - "typed policy and
    action classes do not exist until P8" - has been CORRECTED in
    phase-0-baseline-manifest.yaml. P3 may hold the minimal structural gate contract; P8 still
    owns rule authoring, compilation, versioning, activation, precedence/conflict resolution,
    richer action-class descriptors, the autonomy runtime and the expectation/exception/
    compensation systems. AC-CKPT-6-missing REMAINS DEFERRED and REMAINS UNGREEN, on the ground
    that actually holds - the production registration population is still zero, proved by
    `test_the_production_gate_registration_population_is_still_empty` below. This test still
    neither runs AC-CKPT-6-missing nor claims it green.
    """
    import freight_recon

    src = Path(freight_recon.__file__).parent
    ev = Evaluation(name="policy.typed_action_class_gates")
    # Match the gate decisions as WHOLE TOKENS, not as fragments of other identifiers.
    # `FORBIDDEN_TENANTS` (U2.6A's sentinel list) contains "FORBIDDEN" and is not a policy gate;
    # a substring scan counted it and reported that typed policy had arrived. Same class of bug as
    # the report guard that tripped over the word "DELETED" inside a docstring.
    #
    # ### AND MATCH THEM IN EXECUTABLE SOURCE ONLY (P6/M10). Whole-token matching removed one half
    # of that defect and left the other: raw text still cannot tell `if gate is FORBIDDEN:` apart
    # from a docstring that says "this machine mints NO gate decision". M10's `compensation.py`
    # says exactly that, in five comments and docstrings, and `phase6_compensations.py` explains a
    # column in one SQL `--` comment — six occurrences, ZERO executable — and this guard scored all
    # six as policy escaping the kernel. It was reading the module's account of the boundary and
    # calling it a breach of the boundary.
    #
    # `test_only_the_checkpoint_kernel_may_MINT_a_gate_decision` below had already reached this
    # conclusion and gone AST-based for it: prose is not runtime. `gate_scan.executable_source`
    # applies the same correction here — Python comments, docstrings and whole-line SQL comments
    # are blanked (geometry preserved, so line numbers stay true) and everything the interpreter
    # and SQLite actually execute is retained, DDL `CHECK` literals and error messages included.
    #
    # ### THIS NARROWS WHAT IS READ; IT WIDENS NOTHING. The KERNEL set below is untouched,
    # `compensation.py` is NOT in it, and a module that starts genuinely naming a gate in code
    # still leaks. `test_the_executable_source_scan_still_catches_a_gate_that_escapes_in_code`
    # proves that on a synthesised offender rather than asserting it.
    for path in sorted(src.rglob("*.py")):
        ev.sources_inspected.append(str(path))
        text = path.read_text(encoding="utf-8")
        for _line, token in gate_scan.gate_token_sites(text):
            ev.candidates.append(f"{path.name}:{token}")
            ev.accepted.append(f"{path.name}:{token}")

    assert ev.sources_inspected, "the probe inspected nothing - it cannot conclude anything"

    # The kernel modules that may legitimately carry the gate vocabulary. This is a POLICY
    # BOUNDARY, not a discovery problem, so it is stated - but it is stated defensively: each
    # member must still exist on disk, or a rename would empty the allowlist and the confinement
    # assertion below would pass over nothing (the vacuous-guard failure this file is named for).
    #
    # ### `pipeline_instance.py` JOINED THIS SET AT P6-CP-2, AND IT IS A WIDENING WITH A NARROWING
    # ATTACHED. `02-pipeline-instance.machine.md` §14 makes the gate vocabulary M2's business by
    # canon: PL-2 WRITES `gate_decision` and refuses NULL (F-20/GR-8); PL-3 rejects on `FORBIDDEN`;
    # PL-6 routes to a human on the two human gates; PL-7a admits autonomously only on
    # `AUTONOMOUS_WITHIN_CAPS`. A machine that could not NAME a gate decision could not route on
    # one, and the alternative — M2 inventing its own vocabulary — is the leak this guard exists to
    # catch, arriving by the door marked "compliant".
    #
    # So CARRYING a decision is now permitted here and MINTING one is asserted impossible below.
    # That is the property that was always meant: policy is DECIDED at the boundary that owns it.
    # `phase6_pipeline_instances.py` is deliberately NOT in this set — its `gate_decision` CHECK
    # derives its four literals from P3's `checkpoint_witnesses` DDL at import time rather than
    # restating them, so no gate token appears in that file at all and this guard still proves it.
    #
    # FIXED-SPECIFICATION: this is a POLICY BOUNDARY the architecture states, not a population to be
    # discovered — ADR-010 puts gate evaluation at the checkpoint kernel, and §14 gives machine M2
    # the right to route on the decision the kernel returns. Discovering it would mean asking the
    # code which modules currently touch gates, which is the question, not the answer. Each member
    # is verified to EXIST below, so a rename cannot empty the set and make the confinement vacuous.
    # Stated in ONE place — `phase0.gate_scan.GATE_RUNTIME_MODULES`, with the reasoning above
    # recorded beside it — because the ADR-010 authority guard needs the same boundary and a
    # boundary written down twice is a boundary that will eventually be written down differently.
    # `require_gate_runtime_modules` verifies every member still exists, so a rename cannot empty
    # the allowlist and make the confinement assertion below pass over nothing.
    KERNEL = gate_scan.require_gate_runtime_modules(src)

    try:
        ev.require_population()  # raises when nothing was inspected or nothing evaluated
    except EmptyPopulationError as exc:  # the P0 condition, which P3 ended
        raise AssertionError(
            "the typed gate population is empty again: P3's checkpoint kernel defines the "
            "ADR-010 gate ladder, so an empty population means the kernel was removed or "
            f"renamed out from under checkpoint step 5 ({exc})"
        ) from exc
    assert ev.accepted, "the gate population is empty - P3's kernel no longer declares the ladder"

    leaked = sorted({hit for hit in ev.accepted if hit.split(":", 1)[0] not in KERNEL})
    assert not leaked, (
        "a typed gate decision escaped the checkpoint kernel: policy must be evaluated at the "
        f"boundary that owns it, never carried by a workflow, adapter or callback: {leaked}"
    )


def test_the_executable_source_scan_still_catches_a_gate_that_escapes_in_code():
    """### THE NARROWING ABOVE, PAID FOR. A guard never seen to fail is a decoration (CLAUDE.md §6).

    `test_..._confined_to_the_checkpoint_kernel` now reads executable source instead of raw text.
    That is only defensible if the four ways a downstream machine could really take policy into its
    own hands STILL turn it red. Each mutant below is the actual defect in one line of code, run
    through the exact scanner the guard uses, and each must be FOUND. The prose forms — the ones
    that made M10 fail on a43feae — must be found by NEITHER.

    This is a scanner-level control and it runs in milliseconds. The whole-file version — which
    edits `compensation.py` on disk, re-runs this guard against the mutated tree and restores the
    original from memory — is the "M10 mints its own gate decision" case of
    `scripts/mutate_phase6_compensation.py`.
    """
    ESCAPES = {
        "decides HUMAN_APPROVAL_REQUIRED itself":
            'def gate(self):\n    return "HUMAN_APPROVAL_REQUIRED"\n',
        "decides FORBIDDEN itself":
            'def gate(self, comp):\n    if comp.amount_minor > 100:\n        return FORBIDDEN\n',
        "routes on a gate it named rather than one the kernel returned":
            'def go(self, d):\n    if d == "AUTONOMOUS_WITHIN_CAPS":\n        return self._skip()\n',
        "persists its own gate vocabulary as a CHECK":
            'DDL = """CREATE TABLE c (g TEXT CHECK (g IN (\'FORBIDDEN\')))"""\n',
    }
    for label, source in ESCAPES.items():
        assert gate_scan.gate_token_sites(source), (
            f"the executable-source scan did NOT catch a module that {label}. The confinement "
            "guard has been narrowed into a decoration - it would pass over a real escape."
        )

    PROSE = {
        "a docstring disclaiming the boundary":
            '"""This machine mints NO gate decision: FORBIDDEN is checkpoint.py\'s to decide."""\n',
        "a comment explaining the default":
            '# Its gate is unregistered, so the checkpoint resolves it to HUMAN_APPROVAL_REQUIRED.\n',
        "an SQL comment annotating a column":
            'DDL = """CREATE TABLE c (\n    -- ALWAYS HUMAN_APPROVAL_REQUIRED, bound to the commit key\n'
            '    approval_id TEXT\n)"""\n',
        "a function docstring naming the rule it obeys":
            'def refuse(self):\n    """COMPENSATION IS FORBIDDEN ON AN UNKNOWN OUTCOME (M-33)."""\n'
            '    return None\n',
    }
    for label, source in PROSE.items():
        assert not gate_scan.gate_token_sites(source), (
            f"the scan still fires on {label} - it is reading the module's ACCOUNT of the "
            f"boundary and calling it a breach: {gate_scan.gate_token_sites(source)}"
        )

    # ...and the discrimination is not an artefact of these snippets: M10's two real modules carry
    # the vocabulary in prose and NOWHERE in code, which is the population this control stands over.
    import freight_recon

    src = Path(freight_recon.__file__).parent
    m10 = [src / "compensation.py", src / "migrations" / "phase6_compensations.py"]
    prose_hits = 0
    for path in m10:
        assert path.exists(), f"{path.name} is gone - this control now proves nothing"
        raw = path.read_text(encoding="utf-8")
        prose_hits += sum(
            len(re.findall(rf"(?<![A-Za-z0-9_]){tok}(?![A-Za-z0-9_])", raw))
            for tok in gate_scan.GATE_TOKENS
        )
        assert not gate_scan.gate_token_sites(raw), (
            f"{path.name} names a gate decision in EXECUTABLE code. M10 carries, persists and "
            "routes nothing about gates - if that changed, this is a real product-boundary defect "
            f"and not a guard problem: {gate_scan.gate_token_sites(raw)}"
        )
    assert prose_hits >= 6, (
        f"M10's prose population collapsed to {prose_hits} occurrences - this control would pass "
        "vacuously, proving only that a scan found nothing in a file containing nothing"
    )


def test_only_the_checkpoint_kernel_may_MINT_a_gate_decision():
    """The narrowing that pays for `pipeline_instance.py` joining the allowlist above.

    ### CARRYING A GATE DECISION AND DECIDING ONE ARE DIFFERENT ACTS, AND ONLY THE SECOND IS THE
    LEAK. Machine M2 must name the four decisions to route on them (§14 PL-2/PL-3/PL-6/PL-7a), so
    the token scan above can no longer distinguish "policy escaped" from "the pipeline read the
    kernel's answer". This asserts the sharper thing directly: a gate decision comes into existence
    only by constructing a `GateEntry` or a `GateRegistry`, and outside the kernel nothing may.

    AST-based, not a substring sweep — `GateEntry` inside a docstring or an error message is prose,
    and a guard that fires on its own explanatory text is one people learn to suppress.
    """
    import ast

    import freight_recon

    src = Path(freight_recon.__file__).parent
    MINTS = {"GateEntry", "GateRegistry"}
    KERNEL = {"checkpoint.py"}
    inspected: list[str] = []
    offenders: list[str] = []
    kernel_mints: list[str] = []
    for path in sorted(src.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover — a file that does not parse is reported, not skipped
            offenders.append(f"{path.name}:UNPARSEABLE")
            continue
        inspected.append(path.name)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = (func.id if isinstance(func, ast.Name)
                    else func.attr if isinstance(func, ast.Attribute) else None)
            if name in MINTS:
                (kernel_mints if path.name in KERNEL else offenders).append(f"{path.name}:{name}")

    assert inspected, "the probe parsed nothing - it cannot conclude anything"
    # ### THE POSITIVE CONTROL. A confinement assertion over a population that contains no mint at
    # all passes vacuously and proves nothing (CLAUDE.md §9). The kernel's own `_DEFAULT` gate entry
    # is a real construction, so the scanner is demonstrated to FIND one before it is believed about
    # finding none elsewhere.
    assert kernel_mints, (
        "the AST scan found no GateEntry/GateRegistry construction anywhere, including inside "
        "checkpoint.py, which declares the fail-closed default. The scanner is not seeing "
        "constructions, so its silence about other modules is meaningless."
    )
    assert not offenders, (
        "a module outside the checkpoint kernel MINTS a gate decision: constructing a GateEntry or "
        f"a GateRegistry IS deciding policy, and ADR-010 puts that at one boundary: {sorted(offenders)}"
    )


def test_the_current_model_is_a_fail_safe_default_not_a_not_null_gate():
    """The distinction that makes U0.3 impossible at Phase 0."""
    from freight_recon.lane_graduation import LaneGraduation

    grad = LaneGraduation(Path("/tmp/phase0-nonexistent-graduation.json"))
    assert grad.is_autonomous("tenant_a", "raise_invoice") is False, (
        "absent an explicit graduation the lane must be supervised (fail-safe). If this changed, the "
        "current model got MORE dangerous, not less."
    )
    source = Path(LaneGraduation.__module__.replace(".", "/"))
    assert "is_autonomous" in LaneGraduation.__dict__


def test_ac_ckpt_6_missing_is_deferred_by_dependency_not_waived():
    """ERRATA 4: the requirement is PRESERVED; only its phase semantics were corrected."""
    failures = manifest.expected_failures()
    assert failures["AC-CKPT-6-missing"] == "DEFERRED_BY_DEPENDENCY - REQUIRED AT PHASE 8"
    entry = next(f for f in manifest.load()["expected_acceptance_failures"]
                 if f["case"] == "AC-CKPT-6-missing")
    assert entry["green_at_phase"] == "P8"
    assert entry["accountable_unit"] == "U8.1"
    assert "P0-F1" in entry["reason"]
    assert "ZERO gates" in entry["reason"]


def test_it_is_not_marked_passed_and_not_silently_skipped():
    """The two dishonest options are both closed: it is neither green nor invisible."""
    assert "PASSED" not in manifest.expected_failures()["AC-CKPT-6-missing"]
    assert "AC-CKPT-6-missing" in manifest.expected_failures()


def test_the_production_gate_registration_population_is_still_empty():
    """THE DEFERRAL'S CORRECTED GROUND, proved mechanically (finding F-G).

    AC-CKPT-6-missing is a STARTUP assertion over REGISTERED action classes. The vocabulary now
    exists (the probe above), so the only honest reason the case stays deferred is that nothing in
    production registers anything for it to check. That is a claim about the tree, and a claim
    about the tree must be measured, not believed - otherwise the deferral survives on habit long
    after it stopped being true, which is precisely the defect F-G reported.

    "Production" = every module under src/ that is not the kernel that DEFINES the contract and
    not a migration that only names the vocabulary in DDL. If any of them ever constructs a
    GateRegistry, the population is no longer empty, this guard fails, and the deferral must be
    re-adjudicated rather than quietly inherited.
    """
    import re as _re

    import freight_recon

    src = Path(freight_recon.__file__).parent
    # The kernel DEFINES GateRegistry; phase3_checkpoint carries the DDL vocabulary. Stated as a
    # boundary, and verified to still exist so a rename cannot empty it silently.
    DEFINING = {"checkpoint.py", "phase3_checkpoint.py"}
    for name in sorted(DEFINING):
        assert any(p.name == name for p in src.rglob("*.py")), (
            f"the defining-module allowlist names {name!r}, which no longer exists"
        )

    inspected, constructions = [], []
    for path in sorted(src.rglob("*.py")):
        inspected.append(str(path))
        if path.name in DEFINING:
            continue
        text = path.read_text(encoding="utf-8")
        for m in _re.finditer(r"(?<![A-Za-z0-9_])GateRegistry\s*\(", text):
            line = text[: m.start()].count("\n") + 1
            constructions.append(f"{path.relative_to(src)}:{line}")

    assert inspected, "the probe inspected nothing - it cannot conclude anything"
    assert not constructions, (
        "a production module now REGISTERS typed gates: " + ", ".join(constructions) + ". The "
        "AC-CKPT-6-missing deferral rested on the production registration population being zero. "
        "It is not zero any more - re-adjudicate the case instead of inheriting the deferral."
    )


def test_the_manifest_no_longer_claims_typed_policy_cannot_exist_before_p8():
    """The stale rationale itself, guarded (finding F-G).

    The manifest is an ACCEPTANCE_ORACLE. A false 'why' inside a correct 'what' is exactly how a
    stale premise outlives the fact that retired it, so the retired sentence must not come back
    as a live claim - and the replacement must name what P8 still owns.
    """
    entry = next(f for f in manifest.load()["expected_acceptance_failures"]
                 if f["case"] == "AC-CKPT-6-missing")
    reason = " ".join(str(entry["reason"]).split())
    assert not re.search(
        r"Typed policy and\s+action classes do not exist until P8;", reason, re.I), (
        "the manifest still asserts that typed policy cannot exist before P8. P3's checkpoint "
        "step 5 requires the typed gate contract, so that claim is false and stale."
    )
    assert "SUPERSEDED GROUND" in reason and "CORRECTED" in reason, (
        "the manifest replaced the stale ground without disarming it in place"
    )
    for owned in ("rule authoring", "compilation", "versioning", "activation",
                  "precedence", "autonomy runtime", "compensation"):
        assert owned in reason.lower(), f"the corrected rationale does not record P8 ownership of {owned}"
    # and the case is still NOT green
    assert entry["green_at_phase"] == "P8" and "PASSED" not in entry["status"]
