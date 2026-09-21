"""P8 / U8.6 — Proposal construction REFUSES an unregistered action class and REFUSES (never invents)
a missing one.

Task mandate (U8.6, pressure-test list): "ambiguous or unregistered action_class refuses", and "A
model may not invent them to make the proposal executable." The registered action-class population is
the discovered `commit_key.OCCURRENCE_RULES` / `product_policy.ACTION_CLASS_POPULATION`; a proposal
may only name a member of it, and a request that names none is refused for clarification, not built
with an invented default.

Each guard below realises the forbidden state against the REAL construction seams
(`build_proposed_intent` and `proposed_intent_from_command_intent`) and FAILS (red) if an unregistered
class is accepted or a missing one is invented. Beside each guard is a control BOUND TO THE GUARD'S
OWN NODE: it reintroduces the forbidden state in-process (accept-all population / a default-inventing
wrapper — the M1/M10 mutant semantics) and invokes the actual guard test, proving it goes red. The
guards observe the existing fail-closed refusal; they do not create it, and no product code changes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import freight_recon.proposal as proposal_mod  # noqa: E402  (for the controls' in-process reintroductions)
from freight_recon.proposal import (  # noqa: E402
    AmbiguousProposal,
    UnregisteredActionClass,
    build_proposed_intent,
    proposed_intent_from_command_intent,
)
from freight_recon.slack_delegate import CommandIntent, CommandKind  # noqa: E402

_T = "tenant-ac"


def _operate(action_class: str) -> CommandIntent:
    return CommandIntent(kind=CommandKind.OPERATE, summary="op",
                         params={"action_class": action_class, "load_ref": "1", "customer": "acme"})


def _build_refuses(action_class: str) -> bool:
    try:
        build_proposed_intent(tenant=_T, action_class=action_class)
    except UnregisteredActionClass:
        return True
    return False


def _from_intent_refuses_unregistered(action_class: str) -> bool:
    try:
        proposed_intent_from_command_intent(_operate(action_class), tenant=_T, authenticated=True)
    except UnregisteredActionClass:
        return True
    return False


def _from_intent_refuses_missing() -> bool:
    intent = CommandIntent(kind=CommandKind.OPERATE, summary="op",
                           params={"load_ref": "1", "customer": "acme"})   # no action_class at all
    try:
        proposed_intent_from_command_intent(intent, tenant=_T, authenticated=True)
    except AmbiguousProposal:
        return True
    return False


# ------------------------------------------------------- unregistered action class is refused

def test_an_unregistered_action_class_is_refused_not_invented_at_construction():
    """THE GUARD. An unregistered action class is refused by BOTH construction seams. Fails (red) if
    one is accepted."""
    # POSITIVE CONTROL: a REGISTERED class is accepted (the refusal is specific, not blanket).
    assert build_proposed_intent(tenant=_T, action_class="raise_invoice").action_class == "raise_invoice"
    # ...and ONLY the unregistered class is refused, via each construction seam.
    assert _build_refuses("wire_money_to_nigeria"), \
        "an unregistered action_class was accepted by build_proposed_intent"
    assert _from_intent_refuses_unregistered("wire_money_to_nigeria"), \
        "an unregistered action_class was accepted by proposed_intent_from_command_intent"


def test_the_unregistered_guard_catches_an_unregistered_action_class_accepted(monkeypatch):
    """THE CONTROL, BOUND TO THE GUARD'S OWN NODE. Reintroduce acceptance — make the registered
    population contain everything — and invoke the ACTUAL guard test above, proving it goes RED."""
    class _AcceptAll:
        def __contains__(self, item) -> bool:  # noqa: ARG002
            return True

    monkeypatch.setattr(proposal_mod, "ACTION_CLASS_POPULATION", _AcceptAll())
    with pytest.raises(AssertionError):
        test_an_unregistered_action_class_is_refused_not_invented_at_construction()


# ------------------------------------------------------- missing action class is refused, not invented

def test_a_missing_action_class_is_refused_not_invented_at_construction():
    """THE GUARD. A request that names no action class is refused for clarification, never built with
    an invented default. Fails (red) if a missing action class is invented/accepted."""
    # POSITIVE CONTROL: a request that DOES name an action class is accepted.
    assert proposed_intent_from_command_intent(
        _operate("raise_invoice"), tenant=_T, authenticated=True).action_class == "raise_invoice"
    # ...and ONLY the missing-action-class request is refused (not defaulted to some class).
    assert _from_intent_refuses_missing(), \
        "a missing action_class was invented/accepted instead of refused for clarification"


def test_the_missing_guard_catches_a_missing_action_class_invented(monkeypatch):
    """THE CONTROL, BOUND TO THE GUARD'S OWN NODE. Reintroduce invention (the M10 defect) — a wrapper
    that defaults a missing action class to raise_invoice before the real seam — and invoke the
    ACTUAL guard test above, proving it goes RED."""
    real = proposal_mod.proposed_intent_from_command_intent

    def _inventing(intent, **kw):
        params = dict(intent.params or {})
        if not params.get("action_class"):
            params["action_class"] = "raise_invoice"   # M10: invent a default instead of refusing
            intent = CommandIntent(kind=intent.kind, summary=intent.summary, params=params)
        return real(intent, **kw)

    # Patch the name the guard/helpers resolve at call time, so a missing action class is invented.
    monkeypatch.setattr(sys.modules[__name__], "proposed_intent_from_command_intent", _inventing)
    with pytest.raises(AssertionError):
        test_a_missing_action_class_is_refused_not_invented_at_construction()
