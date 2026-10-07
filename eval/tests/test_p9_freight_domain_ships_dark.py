"""P9 deep-end 1 — the freight-domain spine ships dark, and the guards that say so can fail.

P9 is the first phase to IMPORT the P6-P8 foundational machines from production code. Every one of
those machines shipped with a guard asserting it had no production importer; each of those guards now
admits exactly one module, `freight_domain/foundation.py`, by exact path. That is only safe if the
admitted module is itself reached by nothing live. This file is where that is proved:

  1. the importer detector the replaced guards rely on fires on every import spelling — including
     the subpackage form three of the old guards could not see;
  2. inside `freight_domain/`, `foundation.py` is the ONLY module that imports a foundational machine;
  3. nothing outside `freight_domain/` imports it, and exactly two harness scripts run it — the
     deterministic corpus harness, and the opt-in interpretation eval that reaches it through the
     eval corpus package;
  4. its import closure reaches no effect-capable adapter and no effect/approval authority;
  5. it constructs no gate, mints no witness or grant, and imports no model SDK or network client —
     since deep-end 2 it may be HANDED an inference gateway, and it can build none itself;
  6. the production GateRegistry is still empty and the deployed governed route still refuses;
  7. the registry records P9 as in progress and not reviewed, with P10 still BLOCKED.

`scripts/mutate_p9_freight_domain.py` reintroduces the forbidden state behind each of these and
confirms the named guard turns RED.
"""

from __future__ import annotations

import ast
import importlib
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _entry in (str(ROOT / "src"), str(ROOT / "eval"), str(ROOT / "eval" / "tests"),
               str(ROOT / "scripts")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from dark_surface_kit import (  # noqa: E402
    P9_FOUNDATION,
    SCRIPTS,
    SRC,
    import_closure,
    imported_modules,
    importers_of,
)
from phase0 import import_probe  # noqa: E402

PACKAGE = SRC / "freight_domain"
REGISTRY = ROOT / "docs" / "implementation" / "IMPLEMENTATION-REGISTRY.yaml"

#: The foundational machines and surfaces of P6-P8. FIXED-SPECIFICATION: these are the fifteen
#: primitives of domain-entities/registry.md plus the P7 provenance surfaces and the P8 admission
#: layer — the things a freight module must reach through the composition module or not at all.
FOUNDATIONAL_MACHINES = frozenset({
    "work_item", "pipeline_instance", "external_effect", "approval", "observation",
    "identity_binding_claim", "conflict", "expectation", "exception", "compensation", "policy",
    "rule", "brake", "brake_lifecycle", "checkpoint", "evidence", "provenance", "linker", "lineage",
    "policy_admission", "rule_admission", "proposal",
})
#: What the composition module is entitled to import, exactly. `checkpoint` is the kernel's
#: vocabulary (`ProvenanceClass`, `EvidenceCondition`) reused by import — the one-authority reuse —
#: and nothing in the package constructs a gate from it (proved below).
FOUNDATION_IMPORTS = frozenset({
    "work_item", "observation", "identity_binding_claim", "conflict", "expectation", "exception",
    "evidence", "provenance", "linker", "checkpoint",
})
#: Modules that hold EFFECT or APPROVAL authority, or admit policy. FIXED-SPECIFICATION
#: (ARCHITECTURE.md): the freight spine reaches none of them. The effect-capable ADAPTERS are not
#: listed here — they are read from `phase0.import_probe`, the repository's own authority for them.
AUTHORITY_MODULES = frozenset({
    "effect_boundary", "external_effect", "approval", "compensation", "pipeline_instance",
    "governed_write_route", "governed_write_registry", "governed_approval", "policy_admission",
    "rule_admission", "operation_router", "operator_agent", "action_callback",
})
MODEL_AND_NETWORK_SDKS = frozenset({
    "openai", "anthropic", "instructor", "litellm", "requests", "httpx", "urllib", "aiohttp",
    "smtplib", "imaplib", "socket", "slack_sdk", "playwright", "browser_use", "subprocess",
})
FORBIDDEN_CONSTRUCTIONS = frozenset({
    "GateRegistry", "GateEntry", "BrakeStore", "CheckpointPassed", "ApprovalRecord",
    "LogicalEffect", "execute_effect",
})


def _package_files() -> list[Path]:
    files = sorted(PACKAGE.rglob("*.py"))
    assert len(files) >= 9, f"the freight_domain package has only {len(files)} modules on disk"
    return files


def _names_package(source: str, package: str) -> bool:
    """Whether `source` imports anything from the package `package`, by any spelling."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            if package in (node.module or "").split("."):
                return True
            if any(alias.name == package for alias in node.names):
                return True
        elif isinstance(node, ast.Import):
            if any(package in alias.name.split(".") for alias in node.names):
                return True
        elif isinstance(node, ast.Call):
            target = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if target in ("import_module", "__import__"):
                for argument in node.args:
                    if isinstance(argument, ast.Constant) and isinstance(argument.value, str) \
                            and package in argument.value.split("."):
                        return True
    return False


# ============================================================ 1. the detector can fire

def test_the_importer_detector_fires_on_every_spelling_and_not_on_lookalikes():
    """The ONE matcher every replaced ships-dark guard now relies on. If it missed a spelling, eleven
    guards would be decorations at once — so each spelling is proved here, positive and negative."""
    spellings = {
        "sibling relative": "from .expectation import M8Machine\n",
        "subpackage relative": "from ..expectation import M8Machine\n",
        "deep relative": "from ...freight_recon.expectation import M8Machine\n",
        "absolute": "from freight_recon.expectation import M8Machine\n",
        "bare relative module": "from . import expectation\n",
        "bare parent module": "from .. import expectation\n",
        "from package": "from freight_recon import expectation\n",
        "plain import": "import freight_recon.expectation\n",
        "aliased import": "import freight_recon.expectation as ex\n",
        "importlib": "import importlib\nm = importlib.import_module('freight_recon.expectation')\n",
        "dunder import": "m = __import__('freight_recon.expectation')\n",
        "inside a function": "def f():\n    from ..expectation import M8Machine\n    return M8Machine\n",
    }
    for name, source in spellings.items():
        assert "expectation" in imported_modules(source), f"the detector missed: {name}"
    lookalikes = {
        "the migration": "from .migrations.phase6_expectations import EXPECTATION_STATES\n",
        "a longer name": "from .expectation_helpers import thing\n",
        "an imported NAME": "from .foundation import expectation\n",
        "a string that is not an import": "x = 'from ..expectation import M8Machine'\n",
        "a comment": "# from ..expectation import M8Machine\nx = 1\n",
    }
    for name, source in lookalikes.items():
        assert "expectation" not in imported_modules(source), f"the detector fired on: {name}"
    # The three matchers this replaced, shown blind on the spelling P9 actually uses.
    subpackage = "from ..expectation import M8Machine\n"
    assert not ("import expectation" in subpackage or "from .expectation" in subpackage
                or "from freight_recon.expectation" in subpackage), (
        "the old M8 substring matcher would now see the subpackage spelling")
    node = next(n for n in ast.walk(ast.parse("from ..evidence import EvidenceStore\n"))
                if isinstance(n, ast.ImportFrom))
    assert node.module == "evidence" and not node.module.endswith(".evidence"), (
        "the old evidence/provenance `.endswith('.x')` matcher would now see a relative import")


# ============================================================ 2. one composition module

def test_foundation_is_the_only_freight_domain_module_that_imports_a_foundational_machine():
    """Inside the package, exactly one module touches the P6-P8 machines, and it touches exactly the
    ones freight uses. A second module importing M7 directly is a second place to raise a Conflict."""
    reached: dict[str, set[str]] = {}
    for path in _package_files():
        hits = imported_modules(path.read_text(encoding="utf-8")) & FOUNDATIONAL_MACHINES
        if hits:
            reached[path.relative_to(ROOT).as_posix()] = hits
    print(f"swept {len(_package_files())} freight_domain modules; machine importers: {sorted(reached)}")
    assert set(reached) == {P9_FOUNDATION}, (
        f"foundational machines are imported outside the composition module: "
        f"{ {k: sorted(v) for k, v in reached.items() if k != P9_FOUNDATION} }")
    assert reached[P9_FOUNDATION] == FOUNDATION_IMPORTS, (
        f"the composition module imports {sorted(reached[P9_FOUNDATION])}; the freight spine is "
        f"entitled to exactly {sorted(FOUNDATION_IMPORTS)}. A new dependency is decided HERE.")
    for stem in FOUNDATION_IMPORTS - {"checkpoint"}:
        assert P9_FOUNDATION in importers_of(stem, scripts=True), stem


# ============================================================ 3. nothing live reaches it

def test_nothing_outside_the_package_reaches_the_freight_domain_except_its_two_harnesses():
    """The spine has no production caller: no adapter, workflow, callback, route or operator script
    reaches it. Two harness scripts run it, each on a throwaway database.

    REACHES, not merely imports. The interpretation eval never names `freight_domain`: it imports
    the eval corpus package, which does. A guard that only looked for the direct import stayed green
    with that second harness on disk — so a module that imports `freight_corpus` is counted as
    reaching the spine, and no production module may import `freight_corpus` at all."""
    direct: list[str] = []
    reaching: list[str] = []
    production_corpus_importers: list[str] = []
    swept = 0
    for path in sorted(SRC.rglob("*.py")) + sorted(SCRIPTS.rglob("*.py")):
        if PACKAGE in path.parents:
            continue
        swept += 1
        source = path.read_text(encoding="utf-8")
        name = path.relative_to(ROOT).as_posix()
        names_spine = _names_package(source, "freight_domain")
        names_corpus = _names_package(source, "freight_corpus")
        if names_spine:
            direct.append(name)
        if names_spine or names_corpus:
            reaching.append(name)
        if names_corpus and SRC in path.parents:
            production_corpus_importers.append(name)
    print(f"swept {swept} modules outside freight_domain; direct: {direct}; reaching: {reaching}")
    assert swept > 150, f"the sweep inspected {swept} modules; it proves nothing"
    assert production_corpus_importers == [], (
        f"production code imports the eval corpus: {production_corpus_importers}")
    assert direct == ["scripts/run_freight_corpus.py"], (
        f"the freight-domain spine is imported from outside its package by {direct}. It ships "
        f"dark.")
    assert reaching == ["scripts/run_freight_corpus.py",
                        "scripts/run_freight_interpretation_eval.py"], (
        f"the freight-domain spine is reached from outside its package by {reaching}. It ships "
        f"dark: exactly two harness scripts may run it.")
    corpus_package = sorted((ROOT / "eval" / "freight_corpus").glob("*.py"))
    assert any(_names_package(p.read_text(encoding="utf-8"), "freight_domain")
               for p in corpus_package), "the eval corpus no longer reaches the spine: stale guard"

    harness = (SCRIPTS / "run_freight_corpus.py").read_text(encoding="utf-8")
    assert "tempfile.TemporaryDirectory" in harness and "WorkflowStore" in harness
    assert not (imported_modules(harness) & (import_probe.EFFECT_CAPABLE_ADAPTERS
                                            | MODEL_AND_NETWORK_SDKS))
    # The eval harness can reach a model — only through the inference gateway module, never an SDK
    # of its own — and it reaches no effect-capable adapter. That it will not spend without two
    # explicit switches is proved behaviourally in test_p9_inference_gateway.py.
    eval_harness = (SCRIPTS / "run_freight_interpretation_eval.py").read_text(encoding="utf-8")
    reached = imported_modules(eval_harness)
    assert not (reached & (import_probe.EFFECT_CAPABLE_ADAPTERS | MODEL_AND_NETWORK_SDKS)), (
        sorted(reached & (import_probe.EFFECT_CAPABLE_ADAPTERS | MODEL_AND_NETWORK_SDKS)))
    assert "openai_responses" in reached and "LIVE_ENV" in eval_harness


# ============================================================ 4. the import closure

def test_the_freight_domain_import_closure_reaches_nothing_effect_capable():
    """Structural, not counted-afterwards: a package that cannot REACH an effect-capable adapter or an
    effect/approval authority cannot use one, and no future edit can make it act without first
    turning this RED. The adapter set is the repository's own (`phase0.import_probe`)."""
    closure: set[str] = set()
    for path in _package_files():
        closure |= import_closure(path)
    adapters = set(import_probe.EFFECT_CAPABLE_ADAPTERS)
    assert len(adapters) >= 6, "the effect-capable adapter population collapsed"
    assert len(closure) > 30 and FOUNDATION_IMPORTS <= closure, (
        f"the closure walk reached only {len(closure)} modules; it inspected nothing")
    reached = sorted(closure & (adapters | AUTHORITY_MODULES))
    assert not reached, (
        f"the freight-domain import closure reaches {reached}. The spine performs no external "
        f"effect and holds no effect authority; a path to one makes that a discipline instead of a "
        f"structural fact. Closure: {sorted(closure)}")


# ============================================================ 5. no gate, no model, no network

def test_the_freight_domain_constructs_no_gate_and_imports_no_model_or_network_client():
    """It mints nothing, and it imports no model SDK and no network client. `checkpoint.py` stays the
    sole minter of a gate decision and a witness (CLAUDE.md sec 10). Since deep-end 2 the spine may
    be HANDED an inference gateway and read language through it; it cannot construct one, and
    whatever a model proposes about correlation is routed to a human by the deterministic linker."""
    constructions: list[str] = []
    third_party: list[str] = []
    for path in _package_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                if name in FORBIDDEN_CONSTRUCTIONS:
                    constructions.append(f"{path.name}: {name}()")
            if isinstance(node, ast.Import):
                third_party.extend(f"{path.name}: {a.name}" for a in node.names
                                   if a.name.split(".")[0] in MODEL_AND_NETWORK_SDKS)
            if isinstance(node, ast.ImportFrom) and not node.level:
                if (node.module or "").split(".")[0] in MODEL_AND_NETWORK_SDKS:
                    third_party.append(f"{path.name}: {node.module}")
    assert not constructions, f"the freight spine constructs authority: {constructions}"
    assert not third_party, f"the freight spine imports a model SDK or network client: {third_party}"


# ============================================================ 6. the kernel is still dark

def test_the_production_gate_registry_is_still_empty_and_the_governed_route_still_refuses():
    """RE-RUN of the calibrated guards, invoked rather than reimplemented so they cannot drift."""
    importlib.import_module(
        "test_phase0_null_gate").test_the_production_gate_registration_population_is_still_empty()
    route = importlib.import_module("test_p4_deployed_governed_route")
    with tempfile.TemporaryDirectory() as scratch:
        route.test_the_blocked_route_refuses_explicitly_rather_than_falling_through(Path(scratch))


# ============================================================ 7. recorded truthfully

def _unit_block(text: str, unit: str, following: str) -> str:
    start = text.index(f"\n  - unit_id: {unit}\n")
    return text[start:text.index(f"\n  - unit_id: {following}\n", start)]


def _field(block: str, name: str) -> str | None:
    match = re.search(rf"(?m)^    {re.escape(name)}:\s*(\S+)\s*$", block)
    return match.group(1) if match else None


def test_p9_is_recorded_in_progress_and_unreviewed_and_p10_is_still_blocked():
    """P9 is IN PROGRESS with four implemented, unreviewed checkpoints, each with evidence on disk.
    It is not COMPLETE, nothing is scored, its validation blockers stand, and P10 has not been
    unblocked. (Three checkpoints until P9-CP-4, the continuous load loop, landed by founder
    direction on 2026-10-06; two until P9-CP-3. The assertion below is exact, so recording a fifth
    — or dropping one — fails here. Building the loop accepted nothing and opened nothing: every
    other line of this test is unchanged.)"""
    text = REGISTRY.read_text(encoding="utf-8")
    p9, p10 = _unit_block(text, "P9", "P10"), _unit_block(text, "P10", "P11")
    assert (_field(p9, "status"), _field(p9, "execution_state"), _field(p9, "checkpoint_state")) == (
        "READY", "IN_PROGRESS", "CHECKPOINT_IMPLEMENTED")
    assert (_field(p10, "status"), _field(p10, "execution_state"),
            _field(p10, "checkpoint_state")) == ("BLOCKED", "NOT_STARTED", "NO_CHECKPOINT")
    assert "validation_blockers:" in p9 and "REQUIRE DESIGN-PARTNER VALIDATION" in p9
    assert "acceptance_criteria:" not in p9, "P9 acquired an acceptance block from its own build"
    assert not re.search(r"(?m)^\s*result:\s*PASS\b", p9), "a P9 criterion was scored PASS"
    assert "readiness_target: LOCALLY_IMPLEMENTED" in p9
    checkpoints = re.findall(r"(?m)^      - id: (P9-CP-\d+)\s*$", p9)
    assert checkpoints == ["P9-CP-1", "P9-CP-2", "P9-CP-3", "P9-CP-4"], checkpoints
    evidence = re.findall(r"(?m)^\s*implementer_evidence:\s*(\S+)\s*$", p9)
    assert len(evidence) == len(checkpoints), (
        f"P9 names {len(evidence)} evidence file(s) for {len(checkpoints)} landed checkpoint(s)")
    assert len(set(evidence)) == len(evidence), "two checkpoints cite the same evidence file"
    for path in evidence:
        assert (ROOT / path).is_file(), f"{path} is not on disk"
    reviews = re.findall(r"(?m)^\s*independent_review_report:\s*(\S+)\s*$", p9)
    assert reviews == ["null"] * len(checkpoints), (
        f"a P9 checkpoint claims an independent review report ({reviews}); none has been "
        f"performed")
    assert p9.count("checkpoint_state: CHECKPOINT_IMPLEMENTED") == 1 + len(checkpoints)
