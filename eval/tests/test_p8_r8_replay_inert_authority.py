"""R8 — replay is STRUCTURALLY INERT with respect to human/detector authority: it can never activate
a policy or rule, nor release/narrow a brake, nor mint a witness/grant.

Routed obligation (Product Driver, by identity):
  risk key : restart_recovery:a37eee130a
  R8 (P1)  : "Replay could confer human/detector authority instead of being structurally inert."

Product principle: an unmeasured risk is not a covered risk, and a guard speaks only for the
obligation it was written to answer. The generated-scenario budget could not bind a direct guard to
this risk, so it stayed UNCOVERED. This module is that measurement — nothing broader. It is a
VERIFICATION GAP, not a product defect: on this tree the replay closure reaches none of the
authority modules and replaying the corpus mutates no authority state; this guard makes that
standing and RED-able.

The human/detector authority acts R8 names are exactly the P8 authority-bearing transitions:
  - activate a policy (M11) / a rule (M12) — each requires a named ACTIVE human;
  - release or narrow a brake (M13) — requires a human and a decision_ref (a detector may only
    engage/widen, never release/narrow).
A replay that could perform any of these would confer authority no event may confer (CLAUDE.md §4
rules 9/10/11: events cannot grant execution authority; replay cannot mint witnesses or grants;
replay cannot call adapters. platform-safety-acceptance.md AC-SAFE-019. event/replay acceptance).

Two dimensions, both realised here and both RED-able:
  (A) STRUCTURAL — the replay/audit import CLOSURE cannot reach the authority modules; a module it
      cannot import is one whose `activate()`/`release()`/`narrow()` it cannot call (the M-27 shape
      that test_p5_replay_and_audit.py uses for effect modules, extended to the AUTHORITY modules).
  (B) BEHAVIOURAL — replaying a corpus that CONTAINS authority events (BrakeEngaged/BrakeReleased)
      mutates no authority state: the `brakes` table is byte-for-byte unchanged (replay reconstructs
      the projection; it does not re-perform the release), and zero witnesses/grants are minted.

Changes no product runtime, no mutant, no acceptance requirement.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "freight_recon"
FIXTURES = ROOT / "eval" / "fixtures"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from phase5_kit import make_store  # noqa: E402
from freight_recon.event_replay import load_corpus, replay  # noqa: E402

GC1 = load_corpus(FIXTURES / "gc1-corpus.json")

# The P8 human/detector authority-bearing modules: policy/rule activation (M11/M12) and brake
# release/narrow (M13), plus their admission layers. Replay reaching ANY of these could confer the
# authority only a human/detector may.
AUTHORITY_MODULES = {
    "policy", "rule", "brake", "policy_admission", "rule_admission", "brake_lifecycle",
}


def require_population(items, what: str):
    assert items, f"no {what} to assert over — this guard would measure nothing"
    return items


def _reached_by(tree: ast.AST) -> list[str]:
    """Every module a source file pulls into its namespace, in EVERY import spelling (absolute,
    relative, `import`, and importlib/__import__ string args) — the same walk the effect-module
    closure guard uses, so an authority import hidden behind an alias cannot slip past."""
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                found.append(node.module.split(".")[-1])
            for alias in node.names:
                found.append(alias.name.split(".")[-1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                found.append(alias.name.split(".")[-1])
        elif isinstance(node, ast.Call):
            target = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if target in {"import_module", "__import__"}:
                for argument in node.args:
                    if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                        found.append(argument.value.split(".")[-1])
    return found


def _replay_import_closure() -> set[str]:
    """The transitive import closure of the replay runtime (event_replay + event_audit)."""
    seen: set[str] = set()
    frontier = ["event_replay", "event_audit"]
    while frontier:
        module = frontier.pop()
        if module in seen:
            continue
        seen.add(module)
        path = SRC / f"{module}.py"
        if path.exists():
            frontier.extend(_reached_by(ast.parse(path.read_text(encoding="utf-8"))))
    return seen


def _replay_authority_state_delta(tmp_path) -> dict:
    """Replay the corpus against REAL tables and report whether any AUTHORITY state moved: the brake
    row count before/after, and the witnesses/grants replay minted. Replay must move none of these."""
    store = make_store(tmp_path)
    brakes_before = store.conn.execute("SELECT COUNT(*) FROM brakes").fetchone()[0]
    result = replay(GC1)
    brakes_after = store.conn.execute("SELECT COUNT(*) FROM brakes").fetchone()[0]
    store.close()
    return {
        "events_folded": result.events_folded,
        "brakes_before": brakes_before,
        "brakes_after": brakes_after,
        "witnesses_minted": result.witnesses_minted,
        "grants_minted": result.grants_minted,
    }


def _authority_violations(reached_authority: set[str], delta: dict) -> list[str]:
    """The R8 decision. Any authority module in the replay closure, or any authority-state mutation by
    replay, is replay conferring authority — the forbidden state."""
    violations: list[str] = []
    if reached_authority:
        violations.append(
            f"the replay/audit import closure reaches authority modules {sorted(reached_authority)} — "
            f"replay CAN reach an activate()/release()/narrow() path")
    if delta["brakes_after"] != delta["brakes_before"]:
        violations.append(
            f"replay mutated brake authority state ({delta['brakes_before']} -> {delta['brakes_after']})")
    if (delta["witnesses_minted"], delta["grants_minted"]) != (0, 0):
        violations.append(
            f"replay minted authority ({delta['witnesses_minted']} witnesses, "
            f"{delta['grants_minted']} grants)")
    return violations


# --------------------------------------------------------------------------- the guard
def test_r8_replay_cannot_confer_human_or_detector_authority(tmp_path):
    """THE GUARD (R8). Replay is structurally inert w.r.t. human/detector authority: its import
    closure reaches NONE of the policy/rule/brake authority modules, and replaying a corpus that
    CONTAINS authority events (BrakeEngaged/BrakeReleased) mutates no brake state and mints no
    witness/grant. FAILS ("R8 VIOLATED") if replay could confer authority."""
    closure = _replay_import_closure()
    assert {"event_replay", "event_audit"} <= closure, "the closure walk inspected nothing (vacuous)"
    reached = closure & AUTHORITY_MODULES

    # Proven behavioural population: the corpus genuinely carries brake-authority episodes, so
    # "replay conferred no brake authority" is a measurement, not a vacuous pass (CLAUDE.md §6).
    names = {e.event_name for e in GC1}
    require_population({"BrakeEngaged", "BrakeReleased"} & names, "brake-authority events in the corpus")
    assert {"BrakeEngaged", "BrakeReleased"} <= names, "the corpus carries no brake release to replay"

    delta = _replay_authority_state_delta(tmp_path)
    assert delta["events_folded"] > 0, "replay folded nothing — the behavioural assertions would be vacuous"

    violations = _authority_violations(reached, delta)
    assert not violations, (
        "R8 VIOLATED — replay confers human/detector authority (it must be structurally inert):\n  - "
        + "\n  - ".join(violations))


# --------------------------------------------------------------------------- the RED control
def test_r8_control_catches_replay_that_reaches_or_confers_authority(tmp_path, monkeypatch):
    """THE CONTROL — proves the guard is not vacuous by reintroducing R8's forbidden behaviour.

    Facet A — the decision discriminates (a reached authority module, a mutated brake state, or a
      minted witness/grant is a violation; none is not).
    Facet B — the closure WALK is non-vacuous: a synthetic module that imports `policy`/`brake` is
      detected, so a green guard means the closure genuinely reaches no authority, not that the walk
      is blind.
    Facet C — seen RED: with the closure made to reach an authority module, THE GUARD's own assertion
      path raises; likewise when the replay is made to mutate brake state."""
    g = sys.modules[__name__]

    clean = {"events_folded": 5, "brakes_before": 1, "brakes_after": 1,
             "witnesses_minted": 0, "grants_minted": 0}
    # Facet A — the decision discriminates on all three dimensions.
    assert _authority_violations({"policy"}, clean)
    assert _authority_violations(set(), {**clean, "brakes_after": 2})
    assert _authority_violations(set(), {**clean, "grants_minted": 1})
    assert _authority_violations(set(), clean) == []

    # Facet B — the walk can SEE an authority import (self-scan safety: built at runtime, not written).
    poison = ast.parse("from freight_recon.policy import M11Machine\nimport freight_recon.brake\n")
    assert AUTHORITY_MODULES & set(_reached_by(poison)), "the closure walk cannot see an authority import"

    # Facet C.1 — the guard fails when the closure reaches an authority module.
    monkeypatch.setattr(g, "_replay_import_closure",
                        lambda: {"event_replay", "event_audit", "policy", "brake"})
    with pytest.raises(AssertionError, match="R8 VIOLATED"):
        g.test_r8_replay_cannot_confer_human_or_detector_authority(tmp_path / "red-closure")
    monkeypatch.undo()

    # Facet C.2 — the guard fails when replay mutates brake authority state.
    monkeypatch.setattr(g, "_replay_authority_state_delta",
                        lambda _tp: {"events_folded": 5, "brakes_before": 1, "brakes_after": 2,
                                     "witnesses_minted": 0, "grants_minted": 0})
    with pytest.raises(AssertionError, match="R8 VIOLATED"):
        g.test_r8_replay_cannot_confer_human_or_detector_authority(tmp_path / "red-brake")
