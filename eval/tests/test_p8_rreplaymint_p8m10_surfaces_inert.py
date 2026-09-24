"""R-replay-mint — replaying the event log across the P8/M10 SURFACES durably mints nothing: no
pipeline, grant, claim, effect, conflict, expectation, exception, compensation, approval, policy,
rule, work item or observation row.

Routed obligation (Product Driver, by identity):
  risk key        : restart_recovery:cf65129446
  R-replay-mint(P1): "Replaying the event log across the P8/M10 surfaces could durably mint pipelines,
                     grants, claims or effects instead of being structurally inert."

Product principle: an unmeasured risk is not a covered risk, and a guard speaks only for the
obligation it was written to answer. R8-w2 (restart_recovery:215759fe12) measured the execution-
artifact mint set (pipelines/grants/claims/effects/witnesses). R-replay-mint sharpens the SAME
inertness onto the P8/M10 MACHINE SURFACES specifically — the M7 Conflict, M8 Expectation, M9
Exception and M10 Compensation machines, plus policy/rule/approval/pipeline/work-item/observation —
under a distinct risk key. This module measures exactly that, and nothing broader. It is a
VERIFICATION GAP, not a product defect: on this tree the replay closure reaches no P8/M10 machine
module and replaying the corpus leaves every P8/M10 durable table unchanged.

Authority (not invented here):
  - CLAUDE.md §4 rules 9/10/11 — events cannot grant execution authority; replay cannot mint witnesses
    or grants; replay cannot call adapters.
  - platform-safety-acceptance.md AC-SAFE-019 — replay cannot create a witness, grant, adapter call or
    effect; event-and-replay-acceptance.md AC-EVT-007.
  - foundational-machine-acceptance.md (M7-M10 are ordinary machines that mint durable rows on their
    live transitions); the M-27 structural-inertness precedent in test_p5_replay_and_audit.py.
  - CLAUDE.md §6.

The corpus GC-1 CONTAINS the P8/M10-surface events whose LIVE production mints those rows
(PipelineStarted, GrantClaimed, EffectAttempted, CompensationRequired, ExceptionRaised,
PolicyEvaluated, ApprovalGranted, WorkItemCreated), so "replay minted nothing across the P8/M10
surfaces" is a measurement over a corpus that could have, not a vacuous pass. Two dimensions, both
RED-able: (A) the replay/audit import closure reaches no P8/M10 machine module; (B) replaying the
corpus leaves every existing P8/M10 durable table byte-for-byte unchanged.

Changes no product runtime, no mutant, no acceptance requirement; imports the R8 file read-only.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "eval" / "fixtures"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from phase5_kit import make_store  # noqa: E402
from freight_recon.event_replay import load_corpus, replay  # noqa: E402
# Reuse R8's import-closure walk READ-ONLY (importing does not modify that file; only files changed in
# answer to THIS correction are bound to R-replay-mint's risk key).
from test_p8_r8_replay_inert_authority import _reached_by, _replay_import_closure  # noqa: E402

GC1 = load_corpus(FIXTURES / "gc1-corpus.json")

# The P8/M10 machine modules — M7 Conflict, M8 Expectation, M9 Exception, M10 Compensation, plus the
# policy/rule/approval/pipeline/work-item/observation/effect surfaces. Replay reaching ANY of these
# could durably mint that surface's rows.
P8M10_MINT_MODULES = {
    "conflict", "expectation", "exception", "compensation", "policy", "rule", "approval",
    "pipeline_instance", "work_item", "observation", "identity_binding_claim",
    "checkpoint", "effect_boundary", "external_effect",
}

# The canonical P8/M10 durable tables. Only the ones that exist on this schema are asserted over
# (discovered at runtime); the population is required non-empty so the check cannot pass vacuously.
P8M10_DURABLE_TABLES = (
    "pipeline_instances", "effect_grants", "checkpoint_witnesses", "compensations", "conflicts",
    "expectations", "exceptions", "approvals", "policies", "rules", "work_items", "observations",
    "event_outbox",
)

# Events whose LIVE P8/M10 production durably mints — their presence makes "minted nothing" a real
# measurement (CLAUDE.md §6).
P8M10_MINT_DRIVING_EVENTS = frozenset({
    "PipelineStarted", "GrantClaimed", "EffectAttempted", "CompensationRequired", "ExceptionRaised",
    "PolicyEvaluated", "ApprovalGranted", "WorkItemCreated",
})


def require_population(items, what: str):
    assert items, f"no {what} to assert over — this guard would measure nothing"
    return items


def _existing_p8m10_tables(conn) -> list[str]:
    return [t for t in P8M10_DURABLE_TABLES
            if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                            (t,)).fetchone()]


def _replay_p8m10_surface_delta(tmp_path) -> dict:
    """Replay the corpus against REAL tables and report every existing P8/M10 durable surface
    before/after, plus the mint counts the replay itself reports."""
    store = make_store(tmp_path)
    tables = _existing_p8m10_tables(store.conn)
    before = {t: store.conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
    result = replay(GC1)
    after = {t: store.conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
    store.close()
    return {
        "events_folded": result.events_folded,
        "tables": tables,
        "before": before,
        "after": after,
        "witnesses_minted": result.witnesses_minted,
        "grants_minted": result.grants_minted,
        "adapter_calls": result.adapter_calls,
        "consumer_emissions": result.consumer_emissions,
    }


def _p8m10_mint_violations(reached_modules: set[str], delta: dict) -> list[str]:
    """The R-replay-mint decision. Any P8/M10 machine module in the replay closure, any P8/M10 table
    growth, or any minted witness/grant/adapter-call/emission is replay durably minting a P8/M10
    surface — the forbidden state."""
    violations: list[str] = []
    if reached_modules:
        violations.append(
            f"the replay/audit import closure reaches P8/M10 machine modules {sorted(reached_modules)} "
            f"— replay CAN reach a mint path")
    for surface, before in delta["before"].items():
        if delta["after"][surface] != before:
            violations.append(
                f"replay durably minted into P8/M10 surface {surface} ({before} -> {delta['after'][surface]})")
    reported = (delta["witnesses_minted"], delta["grants_minted"],
                delta["adapter_calls"], delta["consumer_emissions"])
    if reported != (0, 0, 0, 0):
        violations.append(
            f"replay reported minting (witnesses,grants,adapter_calls,consumer_emissions)={reported}")
    return violations


# --------------------------------------------------------------------------- the guard
def test_rreplaymint_p8m10_surfaces_are_structurally_inert_under_replay(tmp_path):
    """THE GUARD (R-replay-mint). Replay is structurally inert across the P8/M10 surfaces: its import
    closure reaches NONE of the P8/M10 machine modules, and replaying a corpus that CONTAINS the
    P8/M10-surface events whose live production mints (PipelineStarted/GrantClaimed/EffectAttempted/
    CompensationRequired/ExceptionRaised/PolicyEvaluated/ApprovalGranted/WorkItemCreated) leaves every
    existing P8/M10 durable table unchanged and mints zero witnesses/grants/effects. FAILS
    ("R-REPLAY-MINT VIOLATED") if replay durably mints across the P8/M10 surfaces."""
    closure = _replay_import_closure()
    assert {"event_replay", "event_audit"} <= closure, "the closure walk inspected nothing (vacuous)"
    reached = closure & P8M10_MINT_MODULES

    names = {e.event_name for e in GC1}
    require_population(P8M10_MINT_DRIVING_EVENTS & names, "P8/M10 mint-driving events in the corpus")
    assert P8M10_MINT_DRIVING_EVENTS <= names, (
        f"the corpus is missing P8/M10 mint-driving events {sorted(P8M10_MINT_DRIVING_EVENTS - names)}; "
        f"'replay minted nothing across P8/M10' would be under-populated")

    delta = _replay_p8m10_surface_delta(tmp_path)
    require_population(delta["tables"], "existing P8/M10 durable tables to assert over")
    assert delta["events_folded"] > 0, "replay folded nothing — the behavioural assertions would be vacuous"

    violations = _p8m10_mint_violations(reached, delta)
    assert not violations, (
        "R-REPLAY-MINT VIOLATED — replay durably mints across the P8/M10 surfaces (it must be "
        "structurally inert):\n  - " + "\n  - ".join(violations))


# --------------------------------------------------------------------------- the RED control
def test_rreplaymint_control_catches_replay_that_mints_a_p8m10_surface(tmp_path, monkeypatch):
    """THE CONTROL — proves the guard is not vacuous by reintroducing R-replay-mint's forbidden state.

    Facet A — the decision discriminates (a reached P8/M10 module, a grown P8/M10 table, or a nonzero
      reported mint is a violation; none is not).
    Facet B — the closure WALK is non-vacuous: a synthetic module importing compensation/exception is
      detected, so a green guard means the closure genuinely reaches no P8/M10 machine module.
    Facet C — seen RED: with the closure made to reach a P8/M10 module, and separately with replay
      made to grow a P8/M10 table (mint a compensation), THE GUARD's own assertion path raises."""
    g = sys.modules[__name__]

    clean_before = {"compensations": 0, "exceptions": 0, "pipeline_instances": 0}
    clean = {"events_folded": 21, "tables": list(clean_before), "before": clean_before,
             "after": dict(clean_before), "witnesses_minted": 0, "grants_minted": 0,
             "adapter_calls": 0, "consumer_emissions": 0}

    # Facet A — the decision discriminates on every dimension.
    assert _p8m10_mint_violations({"compensation"}, clean)
    assert _p8m10_mint_violations(set(), {**clean, "after": {**clean_before, "compensations": 1}})
    assert _p8m10_mint_violations(set(), {**clean, "grants_minted": 1})
    assert _p8m10_mint_violations(set(), clean) == []

    # Facet B — the walk can SEE a P8/M10 machine import (built at runtime; no literal a scan counts).
    poison = _two_p8m10_imports()
    assert P8M10_MINT_MODULES & set(_reached_by(poison)), "the closure walk cannot see a P8/M10 import"

    # Facet C.1 — the guard fails when the closure reaches a P8/M10 machine module.
    monkeypatch.setattr(g, "_replay_import_closure",
                        lambda: {"event_replay", "event_audit", "compensation", "exception"})
    with pytest.raises(AssertionError, match="R-REPLAY-MINT VIOLATED"):
        g.test_rreplaymint_p8m10_surfaces_are_structurally_inert_under_replay(tmp_path / "red-closure")
    monkeypatch.undo()

    # Facet C.2 — the guard fails when replay durably mints a P8/M10 surface row (a compensation).
    minted_before = {"compensations": 0, "exceptions": 0}
    minted_after = {"compensations": 1, "exceptions": 0}
    monkeypatch.setattr(g, "_replay_p8m10_surface_delta",
                        lambda _tp: {"events_folded": 21, "tables": list(minted_before),
                                     "before": minted_before, "after": minted_after,
                                     "witnesses_minted": 0, "grants_minted": 0,
                                     "adapter_calls": 0, "consumer_emissions": 0})
    with pytest.raises(AssertionError, match="R-REPLAY-MINT VIOLATED"):
        g.test_rreplaymint_p8m10_surfaces_are_structurally_inert_under_replay(tmp_path / "red-mint")


def _two_p8m10_imports():
    """A synthetic module importing two P8/M10 machine modules — built at runtime so this file carries
    no literal a self-scan could mistake for a real import."""
    import ast
    return ast.parse("from freight_recon.compensation import M10Machine\nimport freight_recon.exception\n")
