"""P7-AC-15 — ships dark, no enablement, and no second authority.

This is the DEDICATED battery that establishes `P7-AC-15`
(`ships_dark_no_enablement_and_no_second_authority`) as ONE coherent, pointable artifact. Until this
file the criterion's coverage was scattered across "AC-15 touch" fragments in the provenance /
evidence / identity suites, and two clauses of its oracle — the deployed governed route's
`ROUTE_NOT_CONFIGURED` refusal and the recorded readiness tier — were not established by any P7
artifact. A completion-claim audit flagged exactly that: `P7-AC-15` had no implementation evidence
pointed at in the candidate tree. This module is that evidence.

`P7-AC-15`'s oracle (IMPLEMENTATION-REGISTRY.yaml unit P7) names four things, and this module runs
each on the candidate tree:

  1. "An AST importer sweep over a DISCOVERED denominator — never a filename list — proving no
     production importer joins a P7 surface to a live path." -> one consolidated sweep over the four
     P7 surfaces (`provenance`, `evidence`, `linker`, `lineage`), denominator printed.
  2. "the production `GateRegistry` emptiness guard passes." -> RE-RUN of the calibrated
     `test_phase0_null_gate` guard (invoked, not reimplemented — it cannot drift out of step with it).
  3. "the deployed governed route still answers a recorded `ROUTE_NOT_CONFIGURED` refusal." -> RE-RUN
     of the calibrated `test_p4_deployed_governed_route` blocked-route guard.
  4. "the recorded readiness tier matches `readiness_target`" (= `LOCALLY_IMPLEMENTED`). -> a
     non-over-promotion check: the registry records P7 at `LOCALLY_IMPLEMENTED` and at no higher
     achieved tier, and this holds across BOTH the pre-acceptance and the accepted-but-still-dark
     lifecycle states. Phase acceptance legitimately moves `execution_state` NOT_STARTED ->
     COMPLETE and `checkpoint_state` NO_CHECKPOINT -> PHASE_ACCEPTANCE_COMPLETE (P0-P6 already show
     the accepted values) WITHOUT enabling anything or changing the readiness tier; darkness is the
     readiness tier plus the behavioural checks in clauses 1-3/5, never a lifecycle field. The
     earlier oracle pinned NOT_STARTED / NO_CHECKPOINT as if they proved darkness, so a legitimate
     acceptance transition would have made AC-15 fail while the product was still dark - the
     stale-oracle defect this correction removes. The BEHAVIOURAL proof of the tier is clauses 1-3
     and the no-second-authority scan below; a status line cannot prove itself, so this clause only
     pins that nothing promoted P7 past the tier those behaviours establish.

Plus the requirement's structural half — "`checkpoint.py` remains the SOLE minter of a gate decision
and of a Checkpoint Witness; P7 introduces no second effect authority and no second orchestration
system" — as an AST scan of the four P7 surfaces.

### NOTHING HERE IS SCORED. `P7-AC-15`'s result stays PENDING until phase closure scores it; this
module only makes the criterion pointable and establishes it on the candidate tree. Re-running the
calibrated guards (rather than copying their logic) follows the same discipline as
`test_phase7_scope_and_non_regression.py` for `P7-AC-1`.
"""

from __future__ import annotations

import ast
import importlib
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "freight_recon"
REGISTRY = ROOT / "docs" / "implementation" / "IMPLEMENTATION-REGISTRY.yaml"

# Match pytest's prepend import mode so a lazy import of a sibling guard returns the SAME object
# pytest collects. Built from path joins, never string-literal filenames, so this module carries no
# hand-enumerated file population.
for _p in (str(ROOT / "src"), str(ROOT / "eval"), str(ROOT / "eval" / "tests"),
           str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# The four P7 SURFACE modules that must ship dark: the provenance-safety core, the Evidence store, the
# deterministic linker and the lineage walker. The `phase7_evidence` MIGRATION is deliberately NOT in
# this set — `schema.py` legitimately builds the Evidence tables; it is the store and the logic
# modules that must have no production importer (entity 08-evidence, CLAUDE.md sec 10).
P7_SURFACE: tuple[str, ...] = ("provenance", "evidence", "linker", "lineage")


def require_population(items, what: str):
    """A negative/absence assertion over an empty set passes while proving nothing. Refuse that."""
    assert items, f"no {what} to assert over - this test would pass vacuously"
    return items


def _src_modules() -> list[Path]:
    return require_population(sorted(SRC.rglob("*.py")), "src/freight_recon modules")


# ----------------------------------------------------- clause 1: no production importer of a P7 surface


def test_no_production_module_imports_any_p7_surface():
    """`P7-AC-15` clause 1: over a DISCOVERED, printed denominator of every module under
    src/freight_recon, no production module imports any of the four P7 surfaces. A P7 module importing
    another P7 module (lineage->evidence/provenance, linker->provenance) is P7-INTERNAL composition,
    not a production wiring, so the surfaces themselves are excluded from the importer population.
    Importing the `phase7_evidence` MIGRATION is expected and is NOT a surface import."""
    importers: list[str] = []
    inspected = 0
    for path in _src_modules():
        if path.stem in P7_SURFACE:
            continue
        inspected += 1
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module and \
                    node.module.rsplit(".", 1)[-1] in P7_SURFACE:
                importers.append(f"{path.name} -> {node.module}")
            if isinstance(node, ast.ImportFrom) and not node.module:
                for alias in node.names:
                    if alias.name in P7_SURFACE:
                        importers.append(f"{path.name} -> .{alias.name}")
    print(f"P7-AC-15 clause 1: inspected {inspected} src modules for a production importer of {P7_SURFACE}")
    assert inspected > 0, "the ship-dark sweep inspected nothing"
    assert not importers, f"a P7 surface has production importer(s) — it is not dark: {importers}"


# ----------------------------------------------------- clause 2: the production GateRegistry is empty


def test_the_production_gate_registry_is_empty_on_the_candidate_tree():
    """`P7-AC-15` clause 2: the production `GateRegistry` stays EMPTY until U8.1/P8 (CLAUDE.md sec 10).
    RE-RUN of the calibrated guard — invoked, not reimplemented, so it cannot drift out of step."""
    null_gate = importlib.import_module("test_phase0_null_gate")
    null_gate.test_the_production_gate_registration_population_is_still_empty()


# --------------------------------------------- clause 3: the deployed governed route refuses (dark)


def test_the_deployed_governed_route_still_refuses_route_not_configured():
    """`P7-AC-15` clause 3: the deployed governed route answers a recorded `ROUTE_NOT_CONFIGURED`
    refusal — the capability ships dark and enabling it is a separate, founder-authorized decision
    (CLAUDE.md sec 10). RE-RUN of the calibrated P4 blocked-route guard on the candidate tree; it
    posts to the governed handler directly (no socket), so P7 must not have enabled the route."""
    route = importlib.import_module("test_p4_deployed_governed_route")
    with tempfile.TemporaryDirectory() as d:
        route.test_the_blocked_route_refuses_explicitly_rather_than_falling_through(Path(d))


# ------------------------------------------- clause 4: the recorded readiness tier is LOCALLY_IMPLEMENTED


def _p7_unit_block(text: str) -> str:
    start = text.index("\n  - unit_id: P7\n")
    end = text.index("\n  - unit_id: P8\n", start)
    block = text[start:end]
    assert "acceptance_criteria:" in block, "did not isolate the P7 unit block"
    return block


# The one readiness tier P7 is authorised to record, and the TWO legitimate values each phase
# lifecycle field passes through. FIXED-SPECIFICATION: these are the registry's canonical
# phase-lifecycle vocabulary and the single authorised tier (meta.status_model; rebaseline_contract
# .readiness_target) — the specification this clause enforces, not a discovered file population.
_AUTHORISED_READINESS_TARGET = "LOCALLY_IMPLEMENTED"
_HIGHER_READINESS_TIERS = ("DEPLOYED", "PILOT_READY", "ENABLED", "PRODUCTION_READY", "PRODUCTION")
_LEGIT_EXECUTION_STATES = ("NOT_STARTED", "COMPLETE")
_LEGIT_CHECKPOINT_STATES = ("NO_CHECKPOINT", "PHASE_ACCEPTANCE_COMPLETE")


def _unit_field(block: str, field: str) -> str | None:
    """Value of a unit-level scalar field (4-space indent) inside a registry unit block."""
    m = re.search(rf"(?m)^    {re.escape(field)}:\s*(\S+)\s*$", block)
    return m.group(1) if m else None


def _over_promotion_problems(block: str) -> list[str]:
    """`P7-AC-15` clause 4 as a PURE predicate, so its discrimination is provable on synthetic
    blocks. Returns the reasons a unit block would count as enabled / over-promoted past the
    authorised readiness tier; an empty list means "recorded dark as specified". The lifecycle
    fields are admitted at EITHER their pre-acceptance or their accepted value — both are dark,
    because acceptance enables nothing — but any OTHER value (a readiness tier that leaked into a
    lifecycle field, a live/graduated marker) is a defect."""
    problems: list[str] = []
    if f"readiness_target: {_AUTHORISED_READINESS_TARGET}" not in block:
        problems.append(f"readiness_target is not {_AUTHORISED_READINESS_TARGET}")
    for higher in _HIGHER_READINESS_TIERS:
        if f"readiness_target: {higher}" in block:
            problems.append(f"over-promoted past {_AUTHORISED_READINESS_TARGET}: {higher!r}")
    exec_state = _unit_field(block, "execution_state")
    if exec_state not in _LEGIT_EXECUTION_STATES:
        problems.append(f"execution_state {exec_state!r} is neither pre-acceptance nor accepted-dark")
    cp_state = _unit_field(block, "checkpoint_state")
    if cp_state not in _LEGIT_CHECKPOINT_STATES:
        problems.append(f"checkpoint_state {cp_state!r} is neither pre-acceptance nor accepted-dark")
    return problems


def test_the_recorded_p7_readiness_tier_is_locally_implemented_and_not_higher():
    """`P7-AC-15` clause 4: the recorded readiness tier matches `readiness_target` — P7 is at
    `LOCALLY_IMPLEMENTED` and at NO higher tier — across BOTH the pre-acceptance and the
    accepted-but-still-dark lifecycle states. Phase acceptance legitimately moves `execution_state`
    to COMPLETE and `checkpoint_state` to PHASE_ACCEPTANCE_COMPLETE without enabling anything, so
    this clause no longer treats NOT_STARTED / NO_CHECKPOINT as the evidence of darkness (the stale
    oracle this correction removes). It pins non-over-promotion; the BEHAVIOURAL proof of the tier
    is clauses 1-3 and clause 5. A status line cannot prove itself, so this asserts only that
    nothing promoted P7 past what those behaviours establish."""
    block = _p7_unit_block(REGISTRY.read_text(encoding="utf-8"))
    problems = _over_promotion_problems(block)
    assert not problems, "P7 is over-promoted / not recorded dark: " + "; ".join(problems)


def test_the_over_promotion_oracle_admits_an_accepted_but_dark_p7_and_catches_real_enablement():
    """Regression for the stale-oracle defect. Clause 4's predicate must stay GREEN when P7 is
    legitimately phase-accepted yet STILL DARK (execution `COMPLETE`, checkpoint
    `PHASE_ACCEPTANCE_COMPLETE`, `readiness_target` unchanged), and must go RED the moment the
    recorded readiness tier is promoted to a deployed/enabled tier — in EITHER lifecycle state.
    Synthetic in-memory blocks; nothing on the tree is touched. This proves the oracle discriminates
    enablement from an acceptance transition rather than passing on whatever it happens to read."""
    def block(exec_state: str, cp_state: str, tier: str) -> str:
        return (
            "\n  - unit_id: P7\n"
            "    status: READY\n"
            f"    execution_state: {exec_state}\n"
            f"    checkpoint_state: {cp_state}\n"
            "    rebaseline_contract:\n"
            f"      readiness_target: {tier}\n"
            "    acceptance_criteria:\n"
        )

    # pre-acceptance, dark — the state on the current tree — is green
    assert not _over_promotion_problems(
        block("NOT_STARTED", "NO_CHECKPOINT", _AUTHORISED_READINESS_TARGET))
    # accepted, STILL dark — the state a legitimate phase acceptance produces — MUST stay green
    assert not _over_promotion_problems(
        block("COMPLETE", "PHASE_ACCEPTANCE_COMPLETE", _AUTHORISED_READINESS_TARGET)), (
        "an accepted-but-dark P7 was wrongly flagged as enabled — the stale oracle regressed")
    # actual deployment / enablement (a promoted readiness tier) MUST fail, in either lifecycle state
    for exec_state, cp_state in (("NOT_STARTED", "NO_CHECKPOINT"),
                                 ("COMPLETE", "PHASE_ACCEPTANCE_COMPLETE")):
        for tier in _HIGHER_READINESS_TIERS:
            assert _over_promotion_problems(block(exec_state, cp_state, tier)), (
                f"the oracle failed to catch over-promotion to {tier} in "
                f"lifecycle ({exec_state}/{cp_state})")
    # a lifecycle field carrying a live/graduated marker is caught even at the authorised tier
    assert _over_promotion_problems(
        block("ENABLED", "NO_CHECKPOINT", _AUTHORISED_READINESS_TARGET)), \
        "an execution_state carrying an enablement marker was not caught"
    assert _over_promotion_problems(
        block("COMPLETE", "GRADUATED", _AUTHORISED_READINESS_TARGET)), \
        "a checkpoint_state carrying a graduation marker was not caught"


# ------------------------------------ clause 5 (structural): no second authority, checkpoint sole minter


def test_no_p7_surface_builds_a_second_authority_or_reaches_the_effect_transport():
    """`P7-AC-15` structural half: `checkpoint.py` stays the SOLE gate/witness minter and P7 builds no
    second effect authority and no second orchestration. AST over the four P7 surfaces: none
    CONSTRUCTS a `GateRegistry` or a second `BrakeStore`, and none reaches the event transport or the
    governed-write registry. Reusing the kernel's `ProvenanceClass` / `GateReadOfInferredFact` BY
    IMPORT is the ONE-authority reuse AC-2 requires and is not flagged."""
    forbidden_constructions = {"GateRegistry", "BrakeStore"}
    forbidden_import_tails = {"event_outbox", "event_contracts", "governed_write_registry"}
    problems: list[str] = []
    inspected: list[str] = []
    for stem in P7_SURFACE:
        path = SRC / f"{stem}.py"
        assert path.exists(), f"P7 surface module missing: {stem}.py"
        inspected.append(stem)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id in forbidden_constructions:
                problems.append(f"{stem}.py constructs {node.func.id}()")
            if isinstance(node, ast.ImportFrom) and node.module and \
                    node.module.rsplit(".", 1)[-1] in forbidden_import_tails:
                problems.append(f"{stem}.py imports {node.module}")
    print(f"P7-AC-15 clause 5: scanned {inspected} P7 surfaces for a second authority / effect transport")
    assert inspected, "no P7 surface inspected"
    assert not problems, f"a P7 surface builds a second authority or reaches the effect transport: {problems}"


# ----------------------------------------------------- anti-vacuity: populations non-empty, detector fires


def test_the_ship_dark_populations_are_non_empty_and_the_importer_detector_can_fire():
    """A negative/absence sweep over an empty set is vacuously green (CLAUDE.md sec 6). This floors the
    discovered denominators and proves the clause-1 importer detector DISCRIMINATES: it fires on a
    synthetic production import of a P7 surface. The subject is an in-memory string; nothing is
    written to the tree."""
    modules = require_population(_src_modules(), "src modules")
    assert len(modules) >= 50, f"src population collapsed to {len(modules)} — the sweep would be near-vacuous"
    missing = [s for s in P7_SURFACE if not (SRC / f"{s}.py").exists()]
    assert not missing, f"P7 surface module(s) missing — clause 1/5 would inspect nothing: {missing}"

    leaking = "from freight_recon.evidence import EvidenceStore\n"   # a real production wiring
    lookalike = "from freight_recon.evidence_helpers import thing\n"  # a different module
    hits = [n for n in ast.walk(ast.parse(leaking))
            if isinstance(n, ast.ImportFrom) and n.module and n.module.rsplit(".", 1)[-1] in P7_SURFACE]
    assert len(hits) == 1, "the importer detector failed to fire on a genuine P7-surface import"
    misses = [n for n in ast.walk(ast.parse(lookalike))
              if isinstance(n, ast.ImportFrom) and n.module and n.module.rsplit(".", 1)[-1] in P7_SURFACE]
    assert not misses, "the importer detector fired on a lookalike module name"
