"""R8-w2 — replay of the event log is STRUCTURALLY INERT: it durably mints NO pipeline, grant, claim,
effect, work item, compensation or witness, and it confers no authority.

Routed obligation (Product Driver, by identity):
  risk key   : restart_recovery:215759fe12
  R8-w2 (P1) : "Replay of the event log could confer human/detector authority or durably mint
               pipelines, grants, claims or effects, instead of being structurally inert."

Product principle: an unmeasured risk is not a covered risk, and a guard speaks only for the
obligation it was written to answer. R8 (restart_recovery:a37eee130a, guarded in
test_p8_r8_replay_inert_authority.py) measured the AUTHORITY-conferral disjunct (replay cannot reach
policy/rule/brake nor mutate brake state). R8-w2 sharpens the SECOND disjunct under a distinct risk
key: replay must durably MINT NONE of the execution artifacts — pipelines, grants, claims (CLAIMED
grants), effects, work items, compensations, checkpoint witnesses. This module measures exactly that
mint-inertness, and nothing broader. It is a VERIFICATION GAP, not a product defect: on this tree the
replay closure reaches no minting module and replaying the corpus mints nothing durable.

Authority (not invented here):
  - CLAUDE.md §4 rules 9/10/11 — events cannot grant execution authority; replay cannot mint
    witnesses or grants; replay cannot call adapters.
  - platform-safety-acceptance.md AC-SAFE-019 — replay cannot create a witness, grant, adapter call
    or effect.
  - event-and-replay-acceptance.md AC-EVT-007 — replay GC-1 ⇒ 0 witnesses, 0 grants, 0 adapter calls;
    the M-27 structural-inertness precedent in test_p5_replay_and_audit.py.
  - CLAUDE.md §6.

The corpus GC-1 CONTAINS exactly the events whose LIVE production durably mints (GrantClaimed,
EffectGranted, EffectAttempted, PipelineStarted, WorkItemCreated, CheckpointPassed,
CompensationRequired), so "replay minted nothing durable" is a measurement over a corpus that could
have, not a vacuous pass. Two dimensions, both realised here and both RED-able:
  (A) STRUCTURAL — the replay/audit import CLOSURE cannot reach any module that mints a durable
      artifact; a module it cannot import is one whose mint path it cannot call.
  (B) BEHAVIOURAL — replaying the corpus leaves every durable mint surface byte-for-byte unchanged
      and the replay result reports zero witnesses/grants/adapter-calls/consumer-emissions.

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
# answer to THIS correction are bound to R8-w2's risk key).
from test_p8_r8_replay_inert_authority import _reached_by, _replay_import_closure  # noqa: E402

GC1 = load_corpus(FIXTURES / "gc1-corpus.json")

# The modules that durably MINT an execution artifact: a grant/claim/witness (checkpoint,
# effect_boundary), a pipeline (pipeline_instance), an external effect (external_effect and the
# write/route surfaces), a work item (work_item), a compensation (compensation). Replay reaching ANY
# of these could durably mint the artifact R8-w2 forbids.
MINT_MODULES = {
    "effect_boundary", "checkpoint", "pipeline_instance", "external_effect", "compensation",
    "work_item", "governed_write_route", "operation_router",
}

# The durable tables a mint would land in. Replay must leave every one unchanged.
DURABLE_TABLES = ("pipeline_instances", "effect_grants", "checkpoint_witnesses", "compensations",
                  "event_outbox")

# Events whose LIVE production durably mints — their presence in the corpus makes the "minted nothing"
# assertion a real measurement (CLAUDE.md §6), not a vacuous pass over an inert corpus.
MINT_DRIVING_EVENTS = frozenset({
    "GrantClaimed", "EffectGranted", "EffectAttempted", "PipelineStarted", "WorkItemCreated",
    "CheckpointPassed", "CompensationRequired",
})


def require_population(items, what: str):
    assert items, f"no {what} to assert over — this guard would measure nothing"
    return items


def _replay_durable_mint_delta(tmp_path) -> dict:
    """Replay the corpus against REAL tables and report every durable-mint surface before/after, the
    CLAIMED-grant (claim) count before/after, and the mint counts the replay itself reports."""
    store = make_store(tmp_path)

    def counts():
        base = {t: store.conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in DURABLE_TABLES}
        base["effect_grants[CLAIMED]"] = store.conn.execute(
            "SELECT COUNT(*) FROM effect_grants WHERE state = 'CLAIMED'").fetchone()[0]
        return base

    before = counts()
    result = replay(GC1)
    after = counts()
    store.close()
    return {
        "events_folded": result.events_folded,
        "before": before,
        "after": after,
        "witnesses_minted": result.witnesses_minted,
        "grants_minted": result.grants_minted,
        "adapter_calls": result.adapter_calls,
        "consumer_emissions": result.consumer_emissions,
    }


def _durable_mint_violations(reached_mint_modules: set[str], delta: dict) -> list[str]:
    """The R8-w2 decision. Any mint module in the replay closure, any durable-table growth, or any
    minted witness/grant/adapter-call/emission is replay durably minting — the forbidden state."""
    violations: list[str] = []
    if reached_mint_modules:
        violations.append(
            f"the replay/audit import closure reaches minting modules {sorted(reached_mint_modules)} — "
            f"replay CAN reach a mint path")
    for surface, before in delta["before"].items():
        if delta["after"][surface] != before:
            violations.append(
                f"replay durably minted into {surface} ({before} -> {delta['after'][surface]})")
    reported = (delta["witnesses_minted"], delta["grants_minted"],
                delta["adapter_calls"], delta["consumer_emissions"])
    if reported != (0, 0, 0, 0):
        violations.append(
            f"replay reported minting (witnesses,grants,adapter_calls,consumer_emissions)={reported}")
    return violations


# --------------------------------------------------------------------------- the guard
def test_r8w2_replay_durably_mints_no_pipeline_grant_claim_or_effect(tmp_path):
    """THE GUARD (R8-w2). Replay is structurally inert w.r.t. durable mints: its import closure
    reaches NONE of the minting modules, and replaying a corpus that CONTAINS the events whose live
    production mints (GrantClaimed/EffectGranted/EffectAttempted/PipelineStarted/WorkItemCreated/
    CheckpointPassed/CompensationRequired) leaves every durable table unchanged and mints zero
    witnesses/grants/claims/effects. FAILS ("R8-w2 VIOLATED") if replay durably mints anything."""
    closure = _replay_import_closure()
    assert {"event_replay", "event_audit"} <= closure, "the closure walk inspected nothing (vacuous)"
    reached = closure & MINT_MODULES

    # Proven behavioural population: the corpus carries the mint-driving events, so "replay minted
    # nothing durable" is a measurement over a corpus that could have (CLAUDE.md §6).
    names = {e.event_name for e in GC1}
    present = require_population(MINT_DRIVING_EVENTS & names, "mint-driving events in the corpus")
    assert MINT_DRIVING_EVENTS <= names, (
        f"the corpus is missing mint-driving events {sorted(MINT_DRIVING_EVENTS - names)}; "
        f"'replay minted nothing' would be under-populated (present: {sorted(present)})")

    delta = _replay_durable_mint_delta(tmp_path)
    assert delta["events_folded"] > 0, "replay folded nothing — the behavioural assertions would be vacuous"

    violations = _durable_mint_violations(reached, delta)
    assert not violations, (
        "R8-w2 VIOLATED — replay durably mints an execution artifact (it must be structurally "
        "inert):\n  - " + "\n  - ".join(violations))


# --------------------------------------------------------------------------- the RED control
def test_r8w2_control_catches_replay_that_mints_a_durable_artifact(tmp_path, monkeypatch):
    """THE CONTROL — proves the guard is not vacuous by reintroducing R8-w2's forbidden behaviour.

    Facet A — the decision discriminates (a reached mint module, a grown durable table, a minted
      CLAIMED grant, or a nonzero reported mint is a violation; none is not).
    Facet B — the closure WALK is non-vacuous: a synthetic module importing effect_boundary/checkpoint
      is detected, so a green guard means the closure genuinely reaches no minting module.
    Facet C — seen RED: with the closure made to reach a mint module, and separately with replay made
      to grow a durable table (mint a CLAIMED grant), THE GUARD's own assertion path raises."""
    g = sys.modules[__name__]

    clean_before = {t: 0 for t in DURABLE_TABLES}
    clean_before["effect_grants[CLAIMED]"] = 0
    clean = {"events_folded": 22, "before": clean_before, "after": dict(clean_before),
             "witnesses_minted": 0, "grants_minted": 0, "adapter_calls": 0, "consumer_emissions": 0}

    # Facet A — the decision discriminates on every dimension.
    assert _durable_mint_violations({"checkpoint"}, clean)
    assert _durable_mint_violations(set(), {**clean, "after": {**clean_before, "effect_grants": 1}})
    assert _durable_mint_violations(set(), {**clean, "after": {**clean_before, "effect_grants[CLAIMED]": 1}})
    assert _durable_mint_violations(set(), {**clean, "grants_minted": 1})
    assert _durable_mint_violations(set(), clean) == []

    # Facet B — the walk can SEE a mint import (built at runtime; no literal a self-scan could count).
    poison = ast_parse_two_imports()
    assert MINT_MODULES & set(_reached_by(poison)), "the closure walk cannot see a minting import"

    # Facet C.1 — the guard fails when the closure reaches a mint module.
    monkeypatch.setattr(g, "_replay_import_closure",
                        lambda: {"event_replay", "event_audit", "checkpoint", "effect_boundary"})
    with pytest.raises(AssertionError, match="R8-w2 VIOLATED"):
        g.test_r8w2_replay_durably_mints_no_pipeline_grant_claim_or_effect(tmp_path / "red-closure")
    monkeypatch.undo()

    # Facet C.2 — the guard fails when replay durably mints a CLAIMED grant (a claim).
    minted_before = {t: 0 for t in DURABLE_TABLES}
    minted_before["effect_grants[CLAIMED]"] = 0
    minted_after = dict(minted_before)
    minted_after["effect_grants"] = 1
    minted_after["effect_grants[CLAIMED]"] = 1
    monkeypatch.setattr(g, "_replay_durable_mint_delta",
                        lambda _tp: {"events_folded": 22, "before": minted_before, "after": minted_after,
                                     "witnesses_minted": 0, "grants_minted": 1,
                                     "adapter_calls": 0, "consumer_emissions": 0})
    with pytest.raises(AssertionError, match="R8-w2 VIOLATED"):
        g.test_r8w2_replay_durably_mints_no_pipeline_grant_claim_or_effect(tmp_path / "red-mint")


def ast_parse_two_imports():
    """A synthetic module that imports two minting modules — built at runtime so this file carries no
    literal a scan could mistake for a real import."""
    import ast
    return ast.parse("from freight_recon.checkpoint import mint\nimport freight_recon.effect_boundary\n")
