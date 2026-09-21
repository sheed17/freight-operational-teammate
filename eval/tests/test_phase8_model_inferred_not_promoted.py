"""P8 / U8.6 — R8: a MODEL_INFERRED material fact is NEVER promoted by Proposal construction into a
fact readable by consequential gate evaluation.

This file exists to MEASURE one acceptance-blocking obligation and nothing else:

    [P1 conflicting_evidence] R8 — "A MODEL_INFERRED material fact (amount, counterparty) is
    promoted by Proposal construction into a fact readable by consequential gate evaluation."

The task requires U8.6 to PRESERVE the MODEL_INFERRED prohibition (ADR-002 §2.3 / AC-SAFE-015 /
GR-8): a model may propose text and structured fields, but a MODEL_INFERRED material fact remains
unreadable to consequential gate evaluation and CANNOT be promoted by Proposal construction.

The guard below realises the exact hostile case against the REAL proposal-construction seams
(`ProposedFact`, `build_proposed_intent`, `proposed_intent_from_command_intent`, and the
serialization round trip), for BOTH a model-inferred AMOUNT and a model-inferred COUNTERPARTY, and
FAILS (red) if any of them is promoted to gate-readable. The control beside it reintroduces the
forbidden promotion and proves the guard actually goes red — a guard never seen to fail is a
decoration (CLAUDE.md §6). It changes no product code and asserts an absence with an adjacent
positive control, so its green is discriminating.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from freight_recon.checkpoint import GateReadOfInferredFact, ProvenanceClass  # noqa: E402
from freight_recon.fingerprint import Money  # noqa: E402
from freight_recon.proposal import (  # noqa: E402
    ProposedFact,
    ProposedIntent,
    build_proposed_intent,
    proposed_intent_from_command_intent,
)
from freight_recon.slack_delegate import CommandIntent, CommandKind  # noqa: E402

_T = "tenant-r8"


def _refused_by_gate(fact: ProposedFact) -> bool:
    """Did reading this fact for a consequential gate REFUSE structurally? (Plain try/except, not
    pytest.raises, so the oracle's only failure mode is a clean AssertionError — which is what the
    control below monkeypatches into existence.)"""
    try:
        fact.read_for_gate()
    except GateReadOfInferredFact:
        return True
    return False


def _r8_oracle_model_inferred_is_never_gate_readable() -> None:
    """THE R8 ORACLE. A MODEL_INFERRED material fact carried through EVERY proposal-construction path
    is never gate-readable and is never promoted. Raises AssertionError (RED) the moment a promotion
    has happened. Both the guard and its control invoke this one oracle."""
    # 1. A MODEL_INFERRED AMOUNT built directly into a proposal.
    amount = ProposedFact(field="approved_amount", value="285000|USD",
                          provenance=ProvenanceClass.MODEL_INFERRED)
    assert amount.gate_readable is False, "R8: a MODEL_INFERRED amount became gate-readable"
    assert _refused_by_gate(amount), "R8: read_for_gate did not refuse a MODEL_INFERRED amount"

    # 2. A MODEL_INFERRED COUNTERPARTY (the risk names amount AND counterparty).
    counterparty = ProposedFact(field="counterparty", value="acme corp",
                                provenance=ProvenanceClass.MODEL_INFERRED)
    assert counterparty.gate_readable is False, "R8: a MODEL_INFERRED counterparty became gate-readable"
    assert _refused_by_gate(counterparty), "R8: read_for_gate did not refuse a MODEL_INFERRED counterparty"

    # 3. build_proposed_intent must EXCLUDE both from the gate-readable set — not promote either.
    proposal = build_proposed_intent(
        tenant=_T, action_class="raise_invoice", target_system="tms:truckingoffice",
        target_resource_id="load:4471|acme", target_operation="create_invoice",
        work_item_id="wi-1", accountable_owner="dana", facts=(amount, counterparty))
    assert proposal.gate_readable_facts() == (), \
        "R8: a MODEL_INFERRED fact reached the gate-readable set of a constructed proposal"

    # 4. The CommandIntent -> Proposal construction seam (the one the risk names) must NOT promote a
    #    model-inferred amount: whatever provenance the runtime assigns is carried, never strengthened.
    from_intent = proposed_intent_from_command_intent(
        CommandIntent(kind=CommandKind.OPERATE, summary="invoice acme for LD-9",
                      params={"action_class": "raise_invoice", "customer": "acme", "load_ref": "LD-9"}),
        tenant=_T, authenticated=True, approved_money=Money(285000, "USD"),
        amount_provenance=ProvenanceClass.MODEL_INFERRED)
    minted = from_intent.fact("approved_amount")
    assert minted is not None, "the constructed proposal carries no approved_amount fact"
    assert minted.provenance is ProvenanceClass.MODEL_INFERRED, \
        "R8: proposal construction PROMOTED the amount's provenance away from MODEL_INFERRED"
    assert minted.gate_readable is False, "R8: the model-inferred amount is gate-readable after construction"
    assert from_intent.gate_readable_facts() == (), \
        "R8: a MODEL_INFERRED amount reached the gate-readable set via CommandIntent construction"

    # 5. Serializing + deserializing (a step of Proposal construction) does not launder provenance.
    again = ProposedIntent.from_wire(from_intent.to_wire())
    round_tripped = again.fact("approved_amount")
    assert round_tripped is not None and round_tripped.provenance is ProvenanceClass.MODEL_INFERRED, \
        "R8: a serialization round trip promoted a MODEL_INFERRED amount"
    assert again.gate_readable_facts() == (), \
        "R8: a MODEL_INFERRED amount became gate-readable across a serialization round trip"


def test_model_inferred_material_fact_is_never_promoted_to_gate_readable_by_proposal_construction():
    """THE GUARD. Fails (red) if a MODEL_INFERRED amount or counterparty is promoted to gate-readable
    anywhere in proposal construction. This is the direct measurement of R8."""
    _r8_oracle_model_inferred_is_never_gate_readable()


def test_the_guard_catches_a_model_inferred_promotion(monkeypatch):
    """THE CONTROL. Reintroduce the forbidden behaviour — make MODEL_INFERRED facts report
    gate-readable (a promotion) — and prove the guard's own oracle goes RED. If this raises no
    AssertionError, the guard above is a decoration that could never have caught the defect."""
    monkeypatch.setattr(ProposedFact, "gate_readable", property(lambda self: True))
    with pytest.raises(AssertionError):
        _r8_oracle_model_inferred_is_never_gate_readable()
