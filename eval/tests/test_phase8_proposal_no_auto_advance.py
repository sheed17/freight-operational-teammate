"""P8 / U8.6 — a proposal that reaches M2 PROPOSED does NOT auto-advance to POLICY_CHECKED or later.

Task mandate (U8.6): "proposal to M2 PROPOSED does not auto-advance POLICY_CHECKED or later", and
"Proposal construction may not evaluate or mint a gate". The proposal -> M2 seam
(`open_pipeline_for_proposal` -> `PipelineMachine.propose` / IntentProposed) must land the attempt in
PROPOSED and stop; advancing is a SEPARATE, explicit, policy-evaluated step that an authenticated
actor drives through policy/checkpoint/brake/grant/claim — never a side effect of proposing.

The guard below drives a mature proposal through the REAL seam to PROPOSED and FAILS (red) if it
reaches POLICY_CHECKED or any later state, or mints any witness/grant. Its positive sub-control shows
advancement IS possible via the explicit policy step (so PROPOSED-only is a deliberate stop, not an
inability to advance). The control beside it reintroduces the auto-advance in-process — the M9 defect
— and invokes THIS guard's own node, proving it goes red. It changes no product code.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from phase6_pipeline_kit import (  # noqa: E402
    OWNER,
    SYS,
    T_A,
    WORK_ITEM,
    a_human,
    a_work_item,
    ledger,
    machine,
    make_store,
    witnesses,
)

import freight_recon.pipeline_instance as pi  # noqa: E402  (for the control's in-process reintroduction)
from freight_recon.checkpoint import GateDecision  # noqa: E402
from freight_recon.pipeline_instance import (  # noqa: E402
    PipelineState,
    Trigger,
    open_pipeline_for_proposal,
)
from freight_recon.proposal import build_proposed_intent  # noqa: E402

# Every state that is POLICY_CHECKED or later — the seam must reach NONE of them by itself.
_ADVANCED_BEYOND_PROPOSED = frozenset(s for s in PipelineState if s is not PipelineState.PROPOSED)


def _mature():
    return build_proposed_intent(
        tenant=T_A, action_class="raise_invoice", target_system="tms:truckingoffice",
        target_resource_id="load:4471|acme", target_operation="create_invoice", occurrence_key="",
        work_item_id=WORK_ITEM, accountable_owner=OWNER)


def _seed(tmp_path: Path):
    store = make_store(tmp_path)
    a_human(store)
    a_work_item(store)
    return store, machine(store)


def test_a_proposal_reaching_m2_proposed_does_not_auto_advance(tmp_path):
    """THE GUARD. The seam lands the attempt in PROPOSED and advances NOTHING past policy; it mints
    no witness or grant. Fails (red) if it auto-advances to POLICY_CHECKED or later."""
    store, m = _seed(tmp_path)
    outcome = open_pipeline_for_proposal(
        m, _mature(), pipeline_instance_id="pl-1", proposal_ref="prop-A", **SYS)
    assert outcome.is_new_attempt
    inst = m.require("pl-1")
    assert inst.state is PipelineState.PROPOSED, f"the seam auto-advanced to {inst.state.value}"
    assert inst.state not in _ADVANCED_BEYOND_PROPOSED
    # R10, read off the persisted row: NONE of the policy / checkpoint / approval / grant / claim
    # stages was traversed by the seam. Each of these fields is set only when its stage runs, so all
    # being unset is direct evidence the attempt reached PROPOSED and no further.
    assert inst.policy_version is None and inst.gate_decision is None, \
        "the seam evaluated policy (a gate) instead of stopping at PROPOSED"
    assert inst.approval_id is None, "the seam bound an approval instead of stopping at PROPOSED"
    assert inst.checkpoint_id is None and inst.grant_id is None, \
        "the seam minted a checkpoint witness / grant instead of stopping at PROPOSED"
    assert inst.claimed_at is None, "the seam claimed a grant instead of stopping at PROPOSED"
    assert witnesses(store) == [] and ledger(store) == [], "the seam minted a witness/grant"

    # POSITIVE SUB-CONTROL: advancement IS possible — but only via a SEPARATE, explicit,
    # policy-evaluated PL-2 step the seam did NOT take. So PROPOSED-only is a deliberate stop.
    m.apply("pl-1", Trigger.POLICY_EVALUATED, **SYS, policy_version="pv1",
            gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_decision="PERMIT",
            rules_matched=["r-1"], reason="gate resolved", model_inferred_material_fact=False)
    assert m.require("pl-1").state is PipelineState.POLICY_CHECKED
    assert witnesses(store) == [] and ledger(store) == []   # even POLICY_CHECKED mints no witness/grant


def test_the_auto_advance_guard_catches_an_auto_advance(tmp_path, monkeypatch):
    """THE CONTROL, BOUND TO THE GUARD'S OWN NODE. Reintroduce the M9 defect in-process — a seam that
    auto-advances the new PROPOSED attempt past policy (drives PL-2 with a fabricated PERMIT) — and
    invoke the ACTUAL guard test above, proving it goes RED. If no AssertionError is raised, the
    guard could never have caught an auto-advance."""
    real = pi.open_pipeline_for_proposal

    def _auto_advancing(m, proposal, *, pipeline_instance_id, actor_type, actor_id, **kw):
        out = real(m, proposal, pipeline_instance_id=pipeline_instance_id,
                   actor_type=actor_type, actor_id=actor_id, **kw)
        if out.is_new_attempt:
            m.apply(pipeline_instance_id, pi.Trigger.POLICY_EVALUATED, actor_type=actor_type,
                    actor_id=actor_id, policy_version="pv-mutant",
                    gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_decision="PERMIT",
                    model_inferred_material_fact=False)
        return out

    # Patch the name the guard test resolves at call time, so its own call auto-advances.
    monkeypatch.setattr(sys.modules[__name__], "open_pipeline_for_proposal", _auto_advancing)
    with pytest.raises(AssertionError):
        test_a_proposal_reaching_m2_proposed_does_not_auto_advance(tmp_path)
