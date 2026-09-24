"""R-replay-authority — replay confers no human/detector AUTHORITY ACT: it cannot activate a policy or
rule, nor release/narrow a brake.

Routed obligation (Product Driver, by identity):
  risk key            : restart_recovery:d2fa074bf6
  R-replay-authority(P1): "Replay could confer human or detector authority (activate a policy/rule,
                          release/narrow a brake) rather than remaining inert."

Product principle: an unmeasured risk is not a covered risk, and a guard speaks only for the
obligation it was written to answer. R8 (restart_recovery:a37eee130a) measured replay's authority
inertness via the module closure and the brake ROW COUNT. R-replay-authority sharpens the SAME theme
onto the specific authority ACTS — policy/rule ACTIVATION and brake RELEASE/NARROW — under a distinct
risk key, adding two dimensions R8 did not: replay's NO-WRITE-SURFACE (an act it cannot persist) and
a SEEDED ACTIVE brake whose release/narrow state a replay pass must leave untouched. This module
measures exactly that, and nothing broader. It is a VERIFICATION GAP, not a product defect: on this
tree the replay closure reaches no act module, replay has no write surface, and a replay pass leaves a
seeded ACTIVE brake ACTIVE.

Authority (not invented here):
  - CLAUDE.md §4 rules 9/10/11 — events cannot grant execution authority; replay cannot mint witnesses
    or grants; replay cannot call adapters.
  - ADR-010 (policy/rule activation requires a named ACTIVE human); ADR-011 (a brake release/narrow
    requires a human + decision_ref; a detector may only engage/widen).
  - platform-safety-acceptance.md AC-SAFE-019; the M-27 no-write-surface / structural-inertness
    precedent in test_p5_replay_and_audit.py (replay() takes no connection and writes nothing).
  - CLAUDE.md §6.

The corpus GC-1 CONTAINS the authority-act events whose live production performs the acts
(PolicyEvaluated, BrakeEngaged, BrakeReleased), so "replay performed no act" is a measurement over a
corpus that could have. Three dimensions, all RED-able: (A) the replay/audit import closure reaches no
policy/rule/brake act module; (B) replay() takes no connection and its source contains no write SQL,
so an act cannot be persisted; (C) a SEEDED ACTIVE brake is still ACTIVE, same scope and version,
after a replay pass — replay did not release or narrow it.

Changes no product runtime, no mutant, no acceptance requirement; imports the R8 file read-only.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "eval" / "fixtures"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from phase5_kit import make_store  # noqa: E402
from freight_recon.brake import BrakeStore  # noqa: E402
from freight_recon.event_replay import load_corpus, replay  # noqa: E402
# Reuse R8's import-closure walk and its authority-module set READ-ONLY (importing does not modify that
# file; only files changed in answer to THIS correction are bound to R-replay-authority's risk key).
from test_p8_r8_replay_inert_authority import (  # noqa: E402
    AUTHORITY_MODULES as ACT_MODULES, _reached_by, _replay_import_closure,
)

GC1 = load_corpus(FIXTURES / "gc1-corpus.json")
TENANT = "tenant-alpha"

# Events whose LIVE production performs an authority act — their presence makes "replay performed no
# act" a real measurement (CLAUDE.md §6).
ACT_DRIVING_EVENTS = frozenset({"PolicyEvaluated", "BrakeEngaged", "BrakeReleased"})


def require_population(items, what: str):
    assert items, f"no {what} to assert over — this guard would measure nothing"
    return items


def _replay_write_surface_markers() -> list[str]:
    """replay() must take NO connection and its source must contain NO write SQL — so even a computed
    activation/release could not be persisted. Returns the write-surface markers found (empty ==
    inert). This is the act-PERSISTENCE backstop the M-27 no-write-surface node establishes."""
    markers: list[str] = []
    params = set(inspect.signature(replay).parameters)
    if params & {"conn", "connection", "store", "db", "cursor"}:
        markers.append(f"replay accepts a connection parameter: {sorted(params)}")
    source = inspect.getsource(replay)
    for token in ("commit(", "INSERT", "UPDATE", "DELETE", "execute("):
        if token in source:
            markers.append(f"replay source contains write token {token!r}")
    return markers


def _seeded_brake_after_replay(tmp_path) -> dict:
    """Seed a REAL ACTIVE brake, capture its (state, scope, brake_version), run a replay pass, and
    re-read it. Replay must leave it ACTIVE, same scope and version — never released or narrowed."""
    store = make_store(tmp_path)
    brakes = BrakeStore(store.conn)
    engaged = brakes.engage(tenant=TENANT, actor="detector:seed", actor_kind="DETECTOR",
                            reason="seed an ACTIVE brake for the replay-inertness measurement")

    def snapshot():
        row = store.conn.execute(
            "SELECT state, scope, brake_version FROM brakes WHERE tenant = ? AND brake_id = ?",
            (TENANT, engaged.brake_id)).fetchone()
        return (row["state"], row["scope"], row["brake_version"])

    before = snapshot()
    result = replay(GC1)
    after = snapshot()
    store.close()
    return {"events_folded": result.events_folded, "before": before, "after": after}


def _authority_act_violations(reached_act_modules: set[str], write_markers: list[str],
                              brake_before, brake_after) -> list[str]:
    """The R-replay-authority decision. Any act module in the replay closure, any replay write surface,
    or any release/narrow of the seeded ACTIVE brake is replay conferring an authority act."""
    violations: list[str] = []
    if reached_act_modules:
        violations.append(
            f"the replay/audit import closure reaches authority-act modules {sorted(reached_act_modules)} "
            f"— replay CAN reach an activate()/release()/narrow() path")
    if write_markers:
        violations.append("replay has a write surface, so a computed act could be persisted: "
                          + "; ".join(write_markers))
    if brake_after != brake_before:
        violations.append(
            f"replay released or narrowed a seeded ACTIVE brake ({brake_before} -> {brake_after})")
    return violations


# --------------------------------------------------------------------------- the guard
def test_rreplayauthority_replay_confers_no_policy_rule_or_brake_authority(tmp_path):
    """THE GUARD (R-replay-authority). Replay performs no authority act: (A) its import closure reaches
    no policy/rule/brake act module; (B) replay() takes no connection and writes nothing, so an act
    cannot be persisted; (C) a SEEDED ACTIVE brake is still ACTIVE — same scope and version — after a
    replay pass over a corpus that CONTAINS authority-act events (PolicyEvaluated/BrakeEngaged/
    BrakeReleased). FAILS ("R-REPLAY-AUTHORITY VIOLATED") if replay could confer an authority act."""
    closure = _replay_import_closure()
    assert {"event_replay", "event_audit"} <= closure, "the closure walk inspected nothing (vacuous)"
    reached = closure & ACT_MODULES
    write_markers = _replay_write_surface_markers()

    names = {e.event_name for e in GC1}
    require_population(ACT_DRIVING_EVENTS & names, "authority-act events in the corpus")
    assert ACT_DRIVING_EVENTS <= names, (
        f"the corpus is missing authority-act events {sorted(ACT_DRIVING_EVENTS - names)}; "
        f"'replay performed no act' would be under-populated")

    delta = _seeded_brake_after_replay(tmp_path)
    assert delta["events_folded"] > 0, "replay folded nothing — the behavioural assertion would be vacuous"
    assert delta["before"][0] == "ACTIVE", f"the seed did not produce an ACTIVE brake: {delta['before']}"

    violations = _authority_act_violations(reached, write_markers, delta["before"], delta["after"])
    assert not violations, (
        "R-REPLAY-AUTHORITY VIOLATED — replay confers a human/detector authority act (it must remain "
        "inert):\n  - " + "\n  - ".join(violations))


# --------------------------------------------------------------------------- the RED control
def test_rreplayauthority_control_catches_replay_that_confers_an_act(tmp_path, monkeypatch):
    """THE CONTROL — proves the guard is not vacuous by reintroducing R-replay-authority's forbidden
    behaviour.

    Facet A — the decision discriminates (a reached act module, a replay write surface, or a
      released/narrowed seeded brake is a violation; none is not).
    Facet B — the closure WALK is non-vacuous: a synthetic module importing policy/brake is detected.
    Facet C — seen RED: with the closure made to reach an act module, with replay reported to have a
      write surface, and with the seeded brake reported RELEASED, THE GUARD's own assertion path
      raises."""
    g = sys.modules[__name__]
    active = ("ACTIVE", "tenant", "tenant:1")

    # Facet A — the decision discriminates on every dimension.
    assert _authority_act_violations({"brake"}, [], active, active)
    assert _authority_act_violations(set(), ["replay source contains write token 'UPDATE'"], active, active)
    assert _authority_act_violations(set(), [], active, ("RELEASED", "tenant", "tenant:2"))
    assert _authority_act_violations(set(), [], active, active) == []

    # Facet B — the walk can SEE an act import (built at runtime; no literal a self-scan could count).
    poison = _two_act_imports()
    assert ACT_MODULES & set(_reached_by(poison)), "the closure walk cannot see an authority-act import"

    # Facet C.1 — the guard fails when the closure reaches an act module.
    monkeypatch.setattr(g, "_replay_import_closure",
                        lambda: {"event_replay", "event_audit", "policy", "brake"})
    with pytest.raises(AssertionError, match="R-REPLAY-AUTHORITY VIOLATED"):
        g.test_rreplayauthority_replay_confers_no_policy_rule_or_brake_authority(tmp_path / "red-closure")
    monkeypatch.undo()

    # Facet C.2 — the guard fails when replay is reported to have a write surface.
    monkeypatch.setattr(g, "_replay_write_surface_markers",
                        lambda: ["replay accepts a connection parameter: ['conn', 'events']"])
    with pytest.raises(AssertionError, match="R-REPLAY-AUTHORITY VIOLATED"):
        g.test_rreplayauthority_replay_confers_no_policy_rule_or_brake_authority(tmp_path / "red-write")
    monkeypatch.undo()

    # Facet C.3 — the guard fails when a replay pass releases the seeded ACTIVE brake.
    monkeypatch.setattr(g, "_seeded_brake_after_replay",
                        lambda _tp: {"events_folded": 21, "before": ("ACTIVE", "tenant", "tenant:1"),
                                     "after": ("RELEASED", "tenant", "tenant:2")})
    with pytest.raises(AssertionError, match="R-REPLAY-AUTHORITY VIOLATED"):
        g.test_rreplayauthority_replay_confers_no_policy_rule_or_brake_authority(tmp_path / "red-brake")


def _two_act_imports():
    """A synthetic module importing two authority-act modules — built at runtime so this file carries
    no literal a self-scan could mistake for a real import."""
    import ast
    return ast.parse("from freight_recon.policy import M11Machine\nimport freight_recon.brake\n")
