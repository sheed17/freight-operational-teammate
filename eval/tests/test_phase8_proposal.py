"""P8 / U8.6 — `CommandIntent` → Proposal, attacked by risk.

The unit's claim: natural-language / channel interpretation may produce an INERT structured proposal,
and a consequential OPERATE request reaches the canonical pipeline through exactly ONE such boundary
— never through a free-form `CommandIntent`, and never a second command object, reservation or
effect identity. Each section below is a way that claim could be wrong, and each costs a broker when
it is:

    a proposal grants authority        constructing/signing/serializing mints something         (§ A)
    an unregistered effect is proposed  a model invents a new kind of action                     (§ B)
    untrusted text becomes a command    email/doc content authenticates itself                   (§ C)
    a read/unknown proposes an effect   QUERY/UNKNOWN slip through the OPERATE boundary           (§ D)
    a float amount is proposed          money is not canonical minor units                       (§ E)
    a guess gates                       a MODEL_INFERRED fact is promoted/read by a gate          (§ F)
    a round trip loses/forges identity  serialize→deserialize drops action_class/provenance      (§ G)
    the amount forks identity           the commit key contains the amount (ADR-009)             (§ H)
    a proposal bypasses M2              it does not enter PipelineMachine.propose                 (§ I)
    a duplicate bills twice             redelivery/equivalence is not absorbed under Layer-1      (§ I)
    the token IS the authority          a signed button trusts free-form CommandIntent           (§ J)
    a caller splits one effect in two   an occurrence string enters identity (the P1 hatch)      (§ K)

### THIS IS THE IMPLEMENTING SESSION'S BATTERY, NOT AN INDEPENDENT REVIEW.
"""

from __future__ import annotations

import ast
import dataclasses
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
    T_B,
    WORK_ITEM,
    SYS,
    a_human,
    a_work_item,
    ledger,
    machine,
    make_store,
    state_digest,
    witnesses,
)

from freight_recon.action_callback import (  # noqa: E402
    build_slack_operation_approval_value,
    _verify_operation_approval_value,
)
from freight_recon.checkpoint import GateDecision, GateReadOfInferredFact, ProvenanceClass  # noqa: E402
from freight_recon.commit_key import (  # noqa: E402
    CanonicalOccurrence,
    LogicalEffect,
    UnidentifiableEffect,
    UnresolvedCanonicalOccurrence,
    occurrence_key_for,
)
from freight_recon.delivery import DeliverySigner  # noqa: E402
from freight_recon.fingerprint import Money, MoneyMustNotFloat  # noqa: E402
from freight_recon.pipeline_instance import (  # noqa: E402
    AuthorityRefused,
    PipelineError,
    PipelineState,
    Trigger,
    open_pipeline_for_proposal,
)
from freight_recon.slack_adapter import SlackError  # noqa: E402
from freight_recon.proposal import (  # noqa: E402
    OwnerlessProposal,
    ProposalError,
    ProposedFact,
    ProposedIntent,
    UnregisteredActionClass,
    build_proposed_intent,
    proposed_intent_from_command_intent,
)
from freight_recon.slack_delegate import CommandIntent, CommandKind  # noqa: E402


def _operate(action_class="raise_invoice", **params):
    params.setdefault("action_class", action_class)
    return CommandIntent(kind=CommandKind.OPERATE, summary=f"do {action_class}", params=params)


def _mature_proposal(*, tenant=T_A, work_item_id=WORK_ITEM, owner=OWNER, resource="load:4471|acme"):
    """A proposal complete enough to enter M2 as an attempt (a SINGLE class with a full target, so
    its occurrence derives canonically as "")."""
    return build_proposed_intent(
        tenant=tenant, action_class="raise_invoice", target_system="tms:truckingoffice",
        target_resource_id=resource, target_operation="create_invoice",
        work_item_id=work_item_id, accountable_owner=owner,
        facts=(ProposedFact.money("approved_amount", Money(285000, "USD"),
                                  provenance=ProvenanceClass.MODEL_EXTRACTED),),
        summary="Invoice Acme for load 4471",
    )


# --- fire-proofs (CLAUDE.md §5 rule 20 / §6) -----------------------------------------------------
# A guard that asserts an absence proves nothing until something is observed to make it FIRE. Each
# `..._catches_...` control in this file reintroduces exactly ONE forbidden state (via monkeypatch,
# which pytest auto-undoes) and asserts the paired guard goes RED. A guard's refusal is expressed as
# `pytest.raises`, so when the forbidden state is realised the guard surfaces pytest's `Failed`
# (a BaseException, NOT an Exception — this was learned the hard way), while a plain-assert guard
# surfaces AssertionError; `_guard_fires` treats EITHER as "the guard fired" and fails, bound, only
# when the guard PASSED though the defect was live. It invokes the real guard function, so the
# control cannot drift away from what it protects.
try:
    from _pytest.outcomes import Failed as _Failed  # pytest's "DID NOT RAISE ..." outcome  # noqa: E402
except Exception:  # pragma: no cover - pytest internals moved
    _Failed = AssertionError


def _guard_fires(guard, *args, binding):
    try:
        guard(*args)
    except (AssertionError, _Failed):
        return
    raise AssertionError(
        f"{binding}: the guard PASSED while the forbidden state was realised — a guard that cannot "
        f"fail is a decoration, not a guard")


# ============================================================ A. a proposal is INERT

def test_constructing_a_proposal_mints_nothing(tmp_path):
    """Constructing, serializing and deserializing a proposal creates ZERO pipeline rows, witnesses,
    grants, claims and security events — the whole point of `inert`. Proven against a real store."""
    store = make_store(tmp_path)
    a_human(store)
    a_work_item(store)
    before = state_digest(store)

    proposal = proposed_intent_from_command_intent(
        _operate(customer="Acme", load_ref="4471"), tenant=T_A, authenticated=True,
        target_system="tms:truckingoffice", work_item_id=WORK_ITEM, accountable_owner=OWNER,
        approved_money=Money(285000, "USD"),
    )
    wire = proposal.to_wire()
    round_tripped = ProposedIntent.from_wire(wire)
    _ = round_tripped.logical_effect().key()  # deriving identity is pure

    assert state_digest(store) == before, "constructing/serializing a proposal changed durable state"
    assert witnesses(store) == [] and ledger(store) == []
    assert store.conn.execute("SELECT COUNT(*) FROM pipeline_instances").fetchone()[0] == 0


# ============================================================ B. the action class must be REGISTERED
#
# ### THE UNREGISTERED / MISSING action_class REFUSALS MOVED TO A DEDICATED, DISCRIMINATING GUARD.
# `test_an_unregistered_action_class_is_refused_not_invented` and
# `test_a_missing_action_class_is_ambiguous_and_refused` were removed from here (CLAUDE.md §5 rule
# 20: a green absence-assertion with no adjacent control that can be seen to fire is a defect with a
# passing status). Their exact hostile cases are now measured by
# `test_phase8_action_class_registered.py`, where each refusal has a node-bound `..._catches_...`
# control observed to make the guard go RED when an unregistered/missing class is accepted/invented.
# The positive population check below is kept: it is an acceptance, not a non-discriminating absence.

def test_all_eight_registered_action_classes_are_proposable():
    from freight_recon.product_policy import ACTION_CLASS_POPULATION

    assert len(ACTION_CLASS_POPULATION) == 8
    for ac in ACTION_CLASS_POPULATION:
        p = build_proposed_intent(tenant=T_A, action_class=ac)
        assert p.action_class == ac


# ============================================================ C. the authentication / injection boundary
#
# ### THE UNAUTHENTICATED / CONTENT-DECLARED-PROVENANCE REFUSALS MOVED TO A DISCRIMINATING GUARD.
# `test_unauthenticated_content_cannot_become_a_command` and
# `test_content_may_not_declare_its_own_provenance` were removed from here (CLAUDE.md §5 rule 20: a
# green absence-assertion with no adjacent control observed to fire is a defect with a passing
# status). Their exact hostile cases are measured by
# `test_phase8_token_not_approval.py::test_untrusted_content_cannot_become_an_authenticated_command`
# (which refuses unauthenticated content AND content that declares its own provenance under either
# key), whose node-bound control `test_the_authentication_guard_catches_untrusted_content_accepted`
# is observed to make the guard go RED when the forbidden state is realised.


# ============================================================ D. only OPERATE proposes an effect

def test_an_operate_intent_does_produce_a_proposal():
    """POSITIVE CONTROL for the parametrized refusal below: OPERATE is the kind that DOES propose."""
    assert proposed_intent_from_command_intent(
        _operate("raise_invoice", load_ref="1", customer="x"), tenant=T_A, authenticated=True
    ).action_class == "raise_invoice"


@pytest.mark.parametrize("kind", [CommandKind.QUERY, CommandKind.CONTROL, CommandKind.UNKNOWN])
def test_non_operate_intents_do_not_produce_a_proposal(kind):
    # FIRE-PROOF: test_the_non_operate_guard_catches_a_read_intent_that_proposes reintroduces the
    # defect (interpretation builds a proposal for a non-OPERATE intent) and observes THIS go RED.
    intent = CommandIntent(kind=kind, summary="what's outstanding?",
                           params={"action_class": "raise_invoice"})
    with pytest.raises(ProposalError):
        proposed_intent_from_command_intent(intent, tenant=T_A, authenticated=True)


def test_the_non_operate_guard_catches_a_read_intent_that_proposes(monkeypatch):
    """CONTROL: if interpretation stopped restricting proposals to OPERATE (a QUERY/CONTROL/UNKNOWN
    silently built a proposal), the guard above must go RED. Reintroduce exactly that and observe it."""
    def _kindless(intent, **kw):                      # a builder that ignores the command kind
        return build_proposed_intent(tenant=kw.get("tenant") or T_A,
                                     action_class=intent.params["action_class"])
    monkeypatch.setattr(sys.modules[__name__], "proposed_intent_from_command_intent", _kindless)
    _guard_fires(test_non_operate_intents_do_not_produce_a_proposal, CommandKind.QUERY,
                 binding="non-OPERATE proposes")


# ============================================================ E. money is canonical minor units

def test_a_float_money_amount_is_refused():
    # FIRE-PROOF: test_the_float_money_guard_catches_a_float_accepted reintroduces the defect (a
    # binary float is parsed into money) and observes THIS guard go RED.
    # POSITIVE CONTROL: an exact decimal string / minor-unit int is accepted...
    assert ProposedFact.money_from_amount("2850.00") == Money(285000, "USD")
    assert ProposedFact(field="approved_amount", value="285000|USD",
                        provenance=ProvenanceClass.MODEL_EXTRACTED).value == "285000|USD"
    # ...and ONLY a binary float is refused.
    with pytest.raises(MoneyMustNotFloat):
        ProposedFact.money_from_amount(2850.00)           # a binary float
    with pytest.raises(MoneyMustNotFloat):
        ProposedFact(field="approved_amount", value=2850.0, provenance=ProvenanceClass.MODEL_EXTRACTED)


def test_the_float_money_guard_catches_a_float_accepted(monkeypatch):
    """CONTROL: if money parsing stopped refusing a binary float (parsing it as if it were exact),
    the guard above must go RED. Reintroduce exactly that and observe it fire."""
    monkeypatch.setattr(ProposedFact, "money_from_amount", staticmethod(
        lambda amount, currency="USD": Money(int(float(str(amount).replace(",", "")) * 100), currency)))
    _guard_fires(test_a_float_money_amount_is_refused, binding="float money accepted")


def test_a_money_fact_is_canonical_minor_units():
    money = ProposedFact.money_from_amount("2,850.00")
    assert money == Money(285000, "USD")
    fact = ProposedFact.money("approved_amount", money, provenance=ProvenanceClass.SYSTEM_IMPORTED)
    assert fact.value == "285000|USD"
    assert fact.provenance is ProvenanceClass.SYSTEM_IMPORTED


def test_sub_cent_precision_is_refused():
    # FIRE-PROOF: test_the_sub_cent_guard_catches_sub_cent_precision_accepted reintroduces the defect
    # (a sub-cent amount is rounded into money instead of refused) and observes THIS guard go RED.
    with pytest.raises(MoneyMustNotFloat):
        ProposedFact.money_from_amount("2850.001")


def test_the_sub_cent_guard_catches_sub_cent_precision_accepted(monkeypatch):
    """CONTROL: if money parsing rounded a sub-cent amount instead of refusing it, the guard above
    must go RED. Reintroduce exactly that and observe it fire."""
    monkeypatch.setattr(ProposedFact, "money_from_amount", staticmethod(
        lambda amount, currency="USD": Money(round(float(str(amount).replace(",", "")) * 100), currency)))
    _guard_fires(test_sub_cent_precision_is_refused, binding="sub-cent precision accepted")


# ============================================================ F. a MODEL_INFERRED fact never gates

def test_a_model_inferred_material_fact_is_carried_but_never_gate_readable():
    # FIRE-PROOF: test_the_model_inferred_guard_catches_a_promoted_inferred_fact reintroduces the
    # defect (a MODEL_INFERRED fact becomes gate-readable) and observes THIS guard go RED.
    # POSITIVE CONTROL: a non-inferred (MODEL_EXTRACTED) fact IS gate-readable — the quarantine is
    # specific to MODEL_INFERRED, not a blanket "nothing is readable".
    extracted = ProposedFact(field="approved_amount", value="285000|USD",
                             provenance=ProvenanceClass.MODEL_EXTRACTED)
    assert extracted.gate_readable is True
    assert extracted.read_for_gate() == "285000|USD"

    guess = ProposedFact(field="approved_amount", value="285000|USD",
                         provenance=ProvenanceClass.MODEL_INFERRED)
    assert guess.gate_readable is False
    with pytest.raises(GateReadOfInferredFact):
        guess.read_for_gate()
    proposal = build_proposed_intent(
        tenant=T_A, action_class="raise_invoice", facts=(guess,),
    )
    assert proposal.gate_readable_facts() == ()          # excluded from what a gate may read
    # ...and it stays MODEL_INFERRED across a serialization round trip: construction never promotes it.
    again = ProposedIntent.from_wire(proposal.to_wire())
    assert again.fact("approved_amount").provenance is ProvenanceClass.MODEL_INFERRED


def test_the_model_inferred_guard_catches_a_promoted_inferred_fact(monkeypatch):
    """CONTROL: if the proposal's gate-forbidden set were emptied (a MODEL_INFERRED guess becomes
    readable by a consequential gate), the guard above must go RED. Reintroduce exactly that and
    observe it fire. This is the proposal-level counterpart to the dedicated fact-level guard in
    test_phase8_model_inferred_not_promoted.py."""
    import freight_recon.proposal as prop_mod
    monkeypatch.setattr(prop_mod, "_GATE_FORBIDDEN", frozenset())
    _guard_fires(test_a_model_inferred_material_fact_is_carried_but_never_gate_readable,
                 binding="MODEL_INFERRED promoted to gate-readable")


def test_proposal_gate_readability_matches_the_kernel_for_every_provenance_class():
    """### S1 — THE MIRRORED RULE IS PINNED TO THE KERNEL, not merely claimed. For EVERY one of the
    six canonical classes, a ProposedFact's `gate_readable` must equal whether the kernel's OWN
    `ProvenancedFact.value` accessor permits the read. A divergence — the proposal adding/removing a
    class, or the kernel changing its forbidden set — fails HERE, so the module docstring's
    consistency claim cannot silently drift (CLAUDE.md §6)."""
    from freight_recon.checkpoint import EvidenceCondition, ProvenancedFact

    checked = 0
    for pc in ProvenanceClass:
        fact = ProposedFact(field="approved_amount", value="285000|USD", provenance=pc)
        kernel = ProvenancedFact(field="approved_amount", provenance=pc,
                                 evidence_condition=EvidenceCondition.CONSISTENT,
                                 entity_ref="load:1", _value="285000|USD")
        kernel_allows = True
        try:
            _ = kernel.value
        except GateReadOfInferredFact:
            kernel_allows = False
        assert fact.gate_readable is kernel_allows, (
            f"{pc.value}: proposal gate_readable={fact.gate_readable} but kernel allows={kernel_allows}")
        checked += 1
    assert checked == 6, f"expected the six canonical classes, checked {checked}"


# ============================================================ G. serialization preserves identity + provenance

def test_round_trip_preserves_proposal_data_and_re_derives_the_same_identity():
    """### RE-ADJUDICATED at the CI #52 correction. A round trip preserves the proposal's DATA — action
    class, target, the typed occurrence INPUTS, provenance — and so RE-DERIVES the same identity
    through the canonical authority. It does not carry an occurrence: the wire form has no field for
    one and refuses a form that declares one (§ K). What survives the wire is information, never
    identity authority."""
    p = _mature_proposal()
    again = ProposedIntent.from_wire(p.to_wire())
    assert again == p, "a round trip changed the proposal's data"
    assert again.action_class == "raise_invoice"
    assert again.target_resource_id == "load:4471|acme"
    assert again.logical_effect().key() == p.logical_effect().key()
    assert again.fact("approved_amount").provenance is ProvenanceClass.MODEL_EXTRACTED
    # the typed derivation inputs survive, and re-derive the same DERIVED occurrence
    for derived in (_targeted("update_status", target_status="DELIVERED"),
                    _targeted("file_document", document_digest=_DIGEST_A)):
        back = ProposedIntent.from_wire(derived.to_wire())
        assert back == derived
        assert back.logical_effect() == derived.logical_effect()


def test_a_tampered_wire_form_naming_an_unregistered_class_is_refused():
    # FIRE-PROOF: test_the_unregistered_wire_guard_catches_an_unregistered_class_accepted
    # reintroduces the defect (an unregistered action class survives deserialization) → THIS goes RED.
    wire = _mature_proposal().to_wire()
    # POSITIVE CONTROL: the UNtampered wire form round-trips fine...
    assert ProposedIntent.from_wire(wire).action_class == "raise_invoice"
    # ...and ONLY the tampered (unregistered action class) form is refused.
    wire["action_class"] = "wire_money_to_nigeria"
    with pytest.raises(UnregisteredActionClass):
        ProposedIntent.from_wire(wire)


def test_the_unregistered_wire_guard_catches_an_unregistered_class_accepted(monkeypatch):
    """CONTROL: if the registered-class population accepted everything (a tampered wire form naming
    an invented effect deserializes), the guard above must go RED. Reintroduce exactly that."""
    import freight_recon.proposal as prop_mod

    class _AcceptAllClasses:
        def __contains__(self, _item):
            return True

        def __iter__(self):
            return iter(("raise_invoice",))

        def __len__(self):
            return 8

    monkeypatch.setattr(prop_mod, "ACTION_CLASS_POPULATION", _AcceptAllClasses())
    _guard_fires(test_a_tampered_wire_form_naming_an_unregistered_class_is_refused,
                 binding="unregistered action class deserialized")


def test_a_tampered_wire_form_with_a_noncanonical_provenance_is_refused():
    # FIRE-PROOF: test_the_noncanonical_provenance_wire_guard_catches_a_bad_provenance_accepted
    # reintroduces the defect (a seventh, non-canonical provenance is coerced in) → THIS goes RED.
    wire = _mature_proposal().to_wire()
    # POSITIVE CONTROL: a canonical provenance round-trips fine...
    assert ProposedIntent.from_wire(wire).fact("approved_amount").provenance is ProvenanceClass.MODEL_EXTRACTED
    # ...and ONLY the non-canonical provenance is refused.
    wire["facts"][0]["provenance"] = "OWNER_SAID_SO_TRUST_ME"
    with pytest.raises(ProposalError):
        ProposedIntent.from_wire(wire)


def test_the_noncanonical_provenance_wire_guard_catches_a_bad_provenance_accepted(monkeypatch):
    """CONTROL: if provenance coercion invented a default for an unknown string instead of refusing
    it (a wire form asserting its own seventh class), the guard above must go RED. Reintroduce it."""
    import freight_recon.proposal as prop_mod
    monkeypatch.setattr(prop_mod, "_as_provenance",
                        lambda v: v if isinstance(v, ProvenanceClass) else ProvenanceClass.MODEL_EXTRACTED)
    _guard_fires(test_a_tampered_wire_form_with_a_noncanonical_provenance_is_refused,
                 binding="non-canonical provenance coerced")


# ============================================================ H. commit-key identity (ADR-009)

def test_the_commit_key_is_derived_and_carries_no_amount():
    p1 = _mature_proposal()
    # a DIFFERENT proposed amount is the SAME logical effect (the amount is a material fact, not identity)
    p2 = build_proposed_intent(
        tenant=T_A, action_class="raise_invoice", target_system="tms:truckingoffice",
        target_resource_id="load:4471|acme", target_operation="create_invoice",
        work_item_id=WORK_ITEM, accountable_owner=OWNER,
        facts=(ProposedFact("approved_amount", "310000|USD", ProvenanceClass.MODEL_EXTRACTED),),
    )
    assert p1.logical_effect().key() == p2.logical_effect().key()
    assert p1.logical_effect().key() == LogicalEffect(
        tenant=T_A, action_class="raise_invoice", target_system="tms:truckingoffice",
        target_resource_id="load:4471|acme", target_operation="create_invoice", occurrence_key="",
    ).key()


def test_an_immature_proposal_fails_closed_at_the_identity_boundary():
    """Unknown target ⇒ no identity ⇒ cannot enter M2. Refuse, never guess."""
    # FIRE-PROOF: test_the_immature_guard_catches_an_unidentified_effect_accepted reintroduces the
    # defect (identity derivation stops raising on an empty required field) and observes THIS go RED.
    # POSITIVE CONTROL: a MATURE proposal derives its identity fine...
    assert _mature_proposal().is_mature is True
    assert _mature_proposal().logical_effect().key()  # derives without raising
    # ...and ONLY an immature proposal (unknown target) fails closed.
    p = build_proposed_intent(tenant=T_A, action_class="raise_invoice")  # no target
    assert p.is_mature is False
    with pytest.raises(UnidentifiableEffect):
        p.logical_effect()


def test_the_immature_guard_catches_an_unidentified_effect_accepted(monkeypatch):
    """CONTROL: if effect-identity derivation stopped raising on an empty required field (an immature
    proposal is carried toward an attempt instead of failing closed), the guard above must go RED.
    Reintroduce exactly that — a `key()` that never refuses — and observe it fire."""
    from freight_recon import commit_key
    monkeypatch.setattr(commit_key.LogicalEffect, "key", lambda self: "forced-identity")
    _guard_fires(test_an_immature_proposal_fails_closed_at_the_identity_boundary,
                 binding="immature proposal accepted at identity boundary")


# ============================================================ I. the proposal → M2 boundary

def _seed(tmp_path, tenant=T_A):
    store = make_store(tmp_path, tenant)
    a_human(store, tenant=tenant)
    a_work_item(store, tenant=tenant)
    return store, machine(store, tenant=tenant)


def test_a_mature_proposal_opens_exactly_one_proposed_instance(tmp_path):
    store, m = _seed(tmp_path)
    outcome = open_pipeline_for_proposal(
        m, _mature_proposal(), pipeline_instance_id="pl-1", proposal_ref="prop-A", **SYS)
    assert outcome.is_new_attempt
    inst = m.require("pl-1")
    assert inst.state is PipelineState.PROPOSED
    assert inst.owner_id == OWNER
    assert inst.commit_key == _mature_proposal().logical_effect().key()
    # ### IT DOES NOT AUTO-ADVANCE, AND IT MINTS NOTHING.
    assert inst.state is PipelineState.PROPOSED
    assert witnesses(store) == [] and ledger(store) == []
    # POSITIVE CONTROL that PROPOSED-only is a DELIBERATE stop, not because advancement is impossible:
    # a SEPARATE, explicit, policy-evaluated PL-2 step (which the seam did NOT perform) DOES advance
    # it to POLICY_CHECKED. So "no auto-advance" is proven against a machine that CAN advance, and a
    # mutant that made the seam auto-advance past policy would break the PROPOSED assertion above.
    m.apply("pl-1", Trigger.POLICY_EVALUATED, **SYS, policy_version="pv1",
            gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_decision="PERMIT",
            rules_matched=["r-1"], reason="gate resolved", model_inferred_material_fact=False)
    assert m.require("pl-1").state is PipelineState.POLICY_CHECKED
    assert witnesses(store) == [] and ledger(store) == []   # even POLICY_CHECKED mints no witness/grant


def test_a_redelivered_equivalent_proposal_is_absorbed_as_one_attempt(tmp_path):
    store, m = _seed(tmp_path)
    open_pipeline_for_proposal(m, _mature_proposal(), pipeline_instance_id="pl-1",
                               proposal_ref="prop-A", **SYS)
    # a second, equivalent proposal for the SAME logical effect — one reservation winner, one absorbed
    dup = open_pipeline_for_proposal(m, _mature_proposal(), pipeline_instance_id="pl-2",
                                     proposal_ref="prop-B", **SYS)
    assert dup.absorbed is not None and dup.absorbed.holder.pipeline_instance_id == "pl-1"
    assert m.get("pl-2") is None, "the duplicate did not become a second attempt"
    # redelivering the SAME duplicate is idempotent — still one absorbed record, still one attempt
    again = open_pipeline_for_proposal(m, _mature_proposal(), pipeline_instance_id="pl-2",
                                       proposal_ref="prop-B", **SYS)
    assert again.absorbed is not None and again.absorbed.already_absorbed
    live = [r for r in m.attempts_for(_mature_proposal().logical_effect().key())]
    assert len(live) == 1


def test_a_proposal_with_no_work_item_cannot_become_an_attempt(tmp_path):
    store, m = _seed(tmp_path)
    # POSITIVE CONTROL: the SAME proposal WITH an accountable Work Item opens fine...
    owned = build_proposed_intent(
        tenant=T_A, action_class="raise_invoice", target_system="tms:truckingoffice",
        target_resource_id="load:4471|acme", target_operation="create_invoice",
        work_item_id=WORK_ITEM, accountable_owner=OWNER)
    assert open_pipeline_for_proposal(m, owned, pipeline_instance_id="pl-ok", **SYS).is_new_attempt
    # ...and ONLY the ownerless proposal is refused.
    ownerless = build_proposed_intent(
        tenant=T_A, action_class="raise_invoice", target_system="tms:truckingoffice",
        target_resource_id="load:4471|acme", target_operation="create_invoice",
        work_item_id=None)
    with pytest.raises(OwnerlessProposal):
        open_pipeline_for_proposal(m, ownerless, pipeline_instance_id="pl-1", **SYS)
    assert m.get("pl-1") is None


def test_a_model_may_not_open_a_pipeline_from_a_proposal(tmp_path):
    store, m = _seed(tmp_path)
    # POSITIVE CONTROL: a system actor CAN open a pipeline from the proposal...
    assert open_pipeline_for_proposal(m, _mature_proposal(), pipeline_instance_id="pl-ok",
                                      **SYS).is_new_attempt
    # ...and ONLY a model actor is refused (GR-7 / §40: agents emit inert proposals only).
    with pytest.raises(AuthorityRefused, match="model"):
        open_pipeline_for_proposal(m, _mature_proposal(), pipeline_instance_id="pl-1",
                                   actor_type="model", actor_id="extractor")


def test_a_cross_tenant_proposal_is_refused_without_leaking(tmp_path):
    """A proposal naming T_B cannot open an attempt on a T_A machine, and the refusal does not
    confirm anything about T_B."""
    store, m = _seed(tmp_path, tenant=T_A)
    foreign = build_proposed_intent(
        tenant=T_B, action_class="raise_invoice", target_system="tms:truckingoffice",
        target_resource_id="load:4471|acme", target_operation="create_invoice",
        work_item_id=WORK_ITEM, accountable_owner=OWNER)
    # POSITIVE CONTROL: the SAME-tenant proposal opens fine on the T_A machine.
    native = build_proposed_intent(
        tenant=T_A, action_class="raise_invoice", target_system="tms:truckingoffice",
        target_resource_id="load:4471|acme", target_operation="create_invoice",
        work_item_id=WORK_ITEM, accountable_owner=OWNER)
    assert open_pipeline_for_proposal(m, native, pipeline_instance_id="pl-ok", **SYS).is_new_attempt
    # ...and ONLY the cross-tenant (T_B) proposal is refused, without leaking anything about T_B.
    with pytest.raises(PipelineError):
        open_pipeline_for_proposal(m, foreign, pipeline_instance_id="pl-1", **SYS)
    assert m.get("pl-1") is None


# ============================================================ J. the signed token (no socket)

_SIGNER = DeliverySigner(b"u86-proposal-secret")


def _token(**params):
    params.setdefault("action_class", "raise_invoice")
    intent = CommandIntent(kind=CommandKind.OPERATE, summary="invoice Acme for LD-9", params=params)
    return build_slack_operation_approval_value(intent, _SIGNER, approved_amount="2850.00")


def test_a_signed_token_carries_the_inert_proposal_as_authority():
    """The signed button value is a SURFACE over a proposal: its authority is the `ProposedIntent`,
    with a REGISTERED action class and canonical minor-unit money; `.intent` is a derived view.
    Verifying a token returns DATA — it neither executes nor approves anything (generating/verifying
    a token is not approval; only the authenticated human tap at the callback is)."""
    approval = _verify_operation_approval_value(_token(customer="Acme", load_ref="LD-9"), _SIGNER)
    assert approval is not None
    proposal = approval.proposed_intent
    assert proposal.action_class == "raise_invoice"                    # registered
    assert proposal.fact("approved_amount").value == "285000|USD"      # canonical minor units
    assert approval.intent.params["action_class"] == "raise_invoice"   # derived, non-authoritative view
    # channel/thread/TTL and the single-use action_id survive the migration.
    assert approval.action_id and approval.expires_at > approval.issued_at


def test_a_tampered_token_is_refused():
    value = _token(customer="Acme", load_ref="LD-9")
    # POSITIVE CONTROL: the untampered token verifies...
    assert _verify_operation_approval_value(value, _SIGNER) is not None
    body, sig = value.split(".", 1)
    # A FORGED SIGNATURE over a valid body is refused ONLY by the HMAC check — this is what pins the
    # token's authority to its signature. You cannot fabricate an operation-approval token, so a
    # forged token is never "approval" (breaking the HMAC compare makes this assertion fail).
    forged_sig = sig[:-1] + ("a" if sig[-1] != "a" else "b")
    with pytest.raises(SlackError):
        _verify_operation_approval_value(body + "." + forged_sig, _SIGNER)
    # A tampered payload body is refused too (signature mismatch / invalid payload).
    tampered_body = body[:-1] + ("A" if body[-1] != "A" else "B")
    with pytest.raises(SlackError):
        _verify_operation_approval_value(tampered_body + "." + sig, _SIGNER)


# ============================================================ K. occurrence identity has ONE authority
#
# CI #52 found that U8.6 had re-opened the exact escape hatch P1 closed: `ProposedIntent.occurrence_key`
# was a free-form string any caller could set and the wire round-tripped, so varying it between retries
# minted a new logical effect every time — the amount defect under another field name. A proposal now
# holds NO occurrence of its own. `logical_effect()` derives it through the one canonical authority,
# `commit_key.occurrence_key_for`, from typed INPUTS (the document's SHA-256 content digest; the status
# the operation sets) or from a resolved `CanonicalOccurrence` handed in by a trusted resolver — never
# stored, serialized or deserialized. Each test is one way that could be wrong; mutants M11–M17 in
# `scripts/mutate_phase8_proposal.py` reintroduce each defect and are observed to turn these RED.

_DIGEST_A = "a" * 64
_DIGEST_B = "b" * 64
_PA_1 = CanonicalOccurrence(entity="Payment Application", occurrence_id="pa-1")
_PA_2 = CanonicalOccurrence(entity="Payment Application", occurrence_id="pa-2")


def _targeted(action_class, **kw):
    """A proposal with a complete target for `action_class`; occurrence inputs ride in `kw`."""
    return build_proposed_intent(
        tenant=T_A, action_class=action_class, target_system="tms:truckingoffice",
        target_resource_id="ld-9|acme", target_operation=action_class,
        work_item_id=WORK_ITEM, accountable_owner=OWNER, **kw)


def _key(proposal, **derive):
    return proposal.logical_effect(**derive).key()


def test_no_caller_path_can_hand_a_proposal_an_occurrence():
    """Construction has no occurrence parameter at all — not on the dataclass, not on the builder — so
    there is nothing for a CommandIntent, a model or an untyped caller to set."""
    assert "occurrence_key" not in {f.name for f in dataclasses.fields(ProposedIntent)}
    with pytest.raises(TypeError):
        build_proposed_intent(tenant=T_A, action_class="raise_invoice", occurrence_key="retry-2")
    with pytest.raises(TypeError):
        ProposedIntent(tenant=T_A, action_class="raise_invoice", occurrence_key="retry-2")


def test_a_wire_payload_cannot_declare_its_own_occurrence():
    wire = _mature_proposal().to_wire()
    # POSITIVE CONTROL: the untampered wire form deserializes and derives the ordinary key...
    assert _key(ProposedIntent.from_wire(wire)) == _key(_mature_proposal())
    assert "occurrence_key" not in wire, "the wire form still emits an occurrence discriminator"
    # ...and ONLY a form that DECLARES an occurrence — or any identity authority — is refused, loudly,
    # rather than half-accepted with the declaration silently dropped.
    declarations = ({"occurrence_key": "retry-2"}, {"occurrence_key": ""},
                    {"commit_key": "f" * 64},
                    {"resolved": {"entity": "Payment Application", "occurrence_id": "pa-1"}})
    for declared in declarations:
        with pytest.raises(ProposalError):
            ProposedIntent.from_wire({**wire, **declared})
    # a prop_v1 form (which carried a free-form occurrence string) is never reinterpreted as v2
    with pytest.raises(ProposalError):
        ProposedIntent.from_wire({**wire, "v": "prop_v1"})


@pytest.mark.parametrize("action_class, extra, derive", [
    ("raise_invoice", {}, {}),                                  # SINGLE
    ("update_status", {"status_value": "DELIVERED"}, {}),       # DERIVED_TARGET_STATUS
    ("record_payment", {}, {"resolved": _PA_1}),                # CANONICAL, resolved
])
def test_two_retries_cannot_vary_an_occurrence_string_into_two_commit_keys(action_class, extra, derive):
    """A retry is the SAME logical effect. Whatever occurrence string the CommandIntent's params, a
    model or a redelivered wire form's `material_params` carries, it reaches no identity."""
    keys, derived = set(), 0
    for attempt in ("attempt-1", "attempt-2", "", "2026-09-21T10:00:00Z"):
        p = proposed_intent_from_command_intent(
            _operate(action_class, load_ref="LD-9", customer="Acme", occurrence_key=attempt, **extra),
            tenant=T_A, authenticated=True, target_system="tms:truckingoffice",
            work_item_id=WORK_ITEM, accountable_owner=OWNER)
        keys.add(_key(p, **derive))
        wire = p.to_wire()
        wire["material_params"] = {**wire["material_params"], "occurrence_key": f"{attempt}-tampered"}
        keys.add(_key(ProposedIntent.from_wire(wire), **derive))
        derived += 2
    assert derived == 8
    assert len(keys) == 1, f"{derived} retries of ONE {action_class} minted {len(keys)} logical effects"


def test_single_action_class_identity_converges():
    """SINGLE: repetition is not legitimate. The occurrence is "" whatever typed inputs or resolved
    occurrence ride along, so every re-proposal of one invoice is ONE effect."""
    base = _targeted("raise_invoice")
    keys = {_key(base),
            _key(_targeted("raise_invoice", document_digest=_DIGEST_A)),
            _key(_targeted("raise_invoice", document_digest=_DIGEST_B)),
            _key(_targeted("raise_invoice", target_status="DELIVERED")),
            _key(_targeted("raise_invoice", target_status="PICKED_UP")),
            _key(base, resolved=_PA_1)}
    assert base.logical_effect().occurrence_key == ""
    assert keys == {LogicalEffect(
        tenant=T_A, action_class="raise_invoice", target_system="tms:truckingoffice",
        target_resource_id="ld-9|acme", target_operation="raise_invoice", occurrence_key="").key()}


def test_derived_occurrences_derive_deterministically_from_their_canonical_inputs():
    # update_status: the status being SET is the occurrence (normalised by the canonical rule)...
    assert _key(_targeted("update_status", target_status="DELIVERED")) == \
        _key(_targeted("update_status", target_status="  delivered "))
    assert _key(_targeted("update_status", target_status="DELIVERED")) != \
        _key(_targeted("update_status", target_status="PICKED_UP"))
    # ...file_document: the document's content digest is the occurrence.
    assert _key(_targeted("file_document", document_digest=_DIGEST_A)) == \
        _key(_targeted("file_document", document_digest=_DIGEST_A.upper()))
    assert _key(_targeted("file_document", document_digest=_DIGEST_A)) != \
        _key(_targeted("file_document", document_digest=_DIGEST_B))
    # The occurrence is exactly what the canonical authority returns — nothing proposal-local.
    assert _targeted("update_status", target_status="DELIVERED").logical_effect().occurrence_key == \
        occurrence_key_for("update_status", target_status="DELIVERED")
    assert _targeted("file_document", document_digest=_DIGEST_A).logical_effect().occurrence_key == \
        occurrence_key_for("file_document", document_digest=_DIGEST_A)
    # A missing input fails closed — never a default — so the proposal is not mature.
    for p in (_targeted("update_status"), _targeted("file_document")):
        assert p.is_mature is False
        with pytest.raises(UnidentifiableEffect):
            p.logical_effect()
    # A free-form string may not stand in for a content digest.
    with pytest.raises(ProposalError):
        _targeted("file_document", document_digest="retry-2")


def test_the_proposal_derives_the_same_identity_as_the_canonical_router(tmp_path):
    """### ONE REQUEST, ONE IDENTITY, TWO READERS. The proposal and the canonical router
    (`operation_router._logical_effect`) derive the SAME `LogicalEffect` from the same request —
    including a file_document whose digest is read from the ACTUAL file bytes. The commit-key semantics
    are preserved, not re-decided."""
    from freight_recon.commit_key import document_digest
    from freight_recon.operation_router import _logical_effect, freight_routes

    routes = {r.name: r for r in freight_routes()}
    doc = tmp_path / "pod.pdf"
    doc.write_bytes(b"%PDF-1.4 proof of delivery LD-9")
    cases = [
        ("raise_invoice", {}, {}, {}),
        ("record_payable", {}, {}, {}),
        ("update_status", {"status_value": "DELIVERED"}, {}, {}),
        ("file_document", {}, {"document_digest": document_digest(str(doc))},
         {"document_path": str(doc)}),
    ]
    checked = 0
    for action_class, extra, proposal_kw, router_kw in cases:
        intent = _operate(action_class, load_ref="LD-9", customer="Acme", **extra)
        proposal = proposed_intent_from_command_intent(
            intent, tenant=T_A, authenticated=True, target_system="tms:truckingoffice", **proposal_kw)
        router = _logical_effect(T_A, "tms:truckingoffice", routes[action_class], intent, **router_kw)
        assert proposal.logical_effect() == router, action_class
        assert proposal.logical_effect().key() == router.key(), action_class
        checked += 1
    assert checked == len(cases) == 4


@pytest.mark.parametrize("action_class", ["record_payment", "adjust_invoice", "check_call"])
def test_an_unresolved_canonical_occurrence_fails_closed(action_class, tmp_path):
    """CANONICAL_OCCURRENCE_REQUIRED: only a resolver can say WHICH occurrence this is. With none the
    proposal is immature, derivation raises exactly as `occurrence_key_for` does, and the M2 seam opens
    nothing. No occurrence is invented to make the proposal mature — not even from a CommandIntent that
    names one."""
    # POSITIVE CONTROL: the same target on a SINGLE class is mature and derives — the refusal is the
    # occurrence rule's, not a broken target.
    assert _targeted("raise_invoice").is_mature is True
    p = _targeted(action_class)
    assert p.is_mature is False
    with pytest.raises(UnresolvedCanonicalOccurrence):
        p.logical_effect()
    named = proposed_intent_from_command_intent(
        _operate(action_class, load_ref="LD-9", customer="Acme", occurrence_key="pa-1"),
        tenant=T_A, authenticated=True, target_system="tms:truckingoffice",
        work_item_id=WORK_ITEM, accountable_owner=OWNER)
    with pytest.raises(UnresolvedCanonicalOccurrence):
        named.logical_effect()
    store, m = _seed(tmp_path)
    with pytest.raises(UnresolvedCanonicalOccurrence):
        open_pipeline_for_proposal(m, p, pipeline_instance_id="pl-1", **SYS)
    assert m.get("pl-1") is None
    assert store.conn.execute("SELECT COUNT(*) FROM pipeline_instances").fetchone()[0] == 0


def test_a_correctly_resolved_canonical_occurrence_produces_the_ordinary_canonical_key():
    p = _targeted("record_payment")
    expected = LogicalEffect(
        tenant=T_A, action_class="record_payment", target_system="tms:truckingoffice",
        target_resource_id="ld-9|acme", target_operation="record_payment",
        occurrence_key=occurrence_key_for("record_payment", resolved=_PA_1)).key()
    assert _key(p, resolved=_PA_1) == expected
    # the same occurrence, however spelled, is one effect; two occurrences are two partial payments
    assert _key(p, resolved=CanonicalOccurrence("Payment Application", " PA-1 ")) == expected
    assert _key(p, resolved=_PA_2) != expected
    # a wrong-entity occurrence is refused by the canonical authority
    with pytest.raises(UnidentifiableEffect):
        p.logical_effect(resolved=CanonicalOccurrence("Compensation", "cm-1"))
    # derivation never stores the occurrence: the proposal and its wire form carry no trace of it
    assert p == _targeted("record_payment")
    assert "pa-1" not in repr(p.to_wire())


class _LookAlikeOccurrence:
    """Duck-types `CanonicalOccurrence` without being one — what an untyped caller could build."""

    entity = "Payment Application"
    occurrence_id = "pa-1"

    def key(self):
        return "payment application:pa-1"


def test_an_untyped_occurrence_stand_in_is_refused():
    """Only the canonical resolved type may carry occurrence identity: a raw string, a deserialized
    dict or a look-alike object is refused before it reaches the canonical authority."""
    p = _targeted("record_payment")
    # POSITIVE CONTROL: the canonical type derives.
    assert _key(p, resolved=_PA_1)
    for forged in ("payment application:pa-1",
                   {"entity": "Payment Application", "occurrence_id": "pa-1"},
                   _LookAlikeOccurrence()):
        with pytest.raises(ProposalError):
            p.logical_effect(resolved=forged)


def test_a_mutable_amount_never_changes_the_logical_key_under_any_occurrence_rule():
    cases = [("raise_invoice", {}, {}),
             ("update_status", {"target_status": "DELIVERED"}, {}),
             ("file_document", {"document_digest": _DIGEST_A}, {}),
             ("record_payment", {}, {"resolved": _PA_1})]
    for action_class, kw, derive in cases:
        keys = [_key(_targeted(action_class, **kw,
                               facts=(ProposedFact.money("approved_amount", Money(minor, "USD")),)),
                     **derive)
                for minor in (50000, 70000, 285000, 310000)]
        assert len(keys) == 4 and len(set(keys)) == 1, f"{action_class}: the amount forked identity"


# --- structural: one occurrence source, no second resolver ------------------------------------------

_RULE_TABLE_NAMES = frozenset({
    "OCCURRENCE_RULES", "CANONICAL_OCCURRENCE_SOURCES", "SINGLE", "DERIVED_DOCUMENT_DIGEST",
    "DERIVED_TARGET_STATUS", "CANONICAL_OCCURRENCE_REQUIRED",
})


def _occurrence_source_offenders(tree: ast.AST) -> tuple[list[str], int]:
    """(offenders, LogicalEffect constructions checked). Every `LogicalEffect(...)` must take its
    `occurrence_key=` from a local name bound ONLY by calls to `occurrence_key_for`, and the module
    must reference none of the rule tables a second resolver would dispatch on."""
    offenders: list[str] = []
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.ImportFrom):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.Name):
            names = [node.id]
        elif isinstance(node, ast.Attribute):
            names = [node.attr]
        offenders += [f"references rule table {n} (a second occurrence resolver)"
                      for n in names if n in _RULE_TABLE_NAMES]
    checked = 0
    for fn in (n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
        bound: dict[str, list[ast.AST]] = {}
        for n in ast.walk(fn):
            if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                for t in targets:
                    if isinstance(t, ast.Name):
                        bound.setdefault(t.id, []).append(n.value)
        for call in ast.walk(fn):
            if not (isinstance(call, ast.Call)
                    and getattr(call.func, "id", getattr(call.func, "attr", None)) == "LogicalEffect"):
                continue
            checked += 1
            kw = next((k for k in call.keywords if k.arg == "occurrence_key"), None)
            sources = bound.get(kw.value.id, []) if kw and isinstance(kw.value, ast.Name) else []
            if not sources or not all(isinstance(v, ast.Call)
                                      and getattr(v.func, "id", None) == "occurrence_key_for"
                                      for v in sources):
                offenders.append(f"{fn.name}:{call.lineno} LogicalEffect.occurrence_key does not "
                                 f"come solely from occurrence_key_for")
    return offenders, checked


def test_the_proposal_module_has_one_occurrence_source_and_no_second_resolver():
    """### STRUCTURAL, by AST, over the real module. The final `LogicalEffect` occurrence discriminator
    comes through `occurrence_key_for` and nothing else, and proposal.py dispatches on no rule table of
    its own. Paired with the positive control below, which proves the detector can go RED."""
    tree = ast.parse((ROOT / "src" / "freight_recon" / "proposal.py").read_text(encoding="utf-8"))
    offenders, checked = _occurrence_source_offenders(tree)
    assert checked >= 1, "no LogicalEffect construction found in proposal.py — the guard parsed nothing"
    assert not offenders, offenders


def test_the_occurrence_source_guard_fires_on_a_reintroduced_escape_hatch():
    """POSITIVE CONTROL: each shape of the escape hatch is flagged; the canonical shape is not."""
    hostile = [
        "def logical_effect(self):\n    return LogicalEffect(tenant=t, occurrence_key=self.occurrence_key)\n",
        "def logical_effect(self):\n    occ = self.material_params.get('o') or occurrence_key_for(a)\n"
        "    return LogicalEffect(occurrence_key=occ)\n",
        "def logical_effect(self):\n    occ = occurrence_key_for(a)\n    if x:\n        occ = raw\n"
        "    return LogicalEffect(occurrence_key=occ)\n",
        "def logical_effect(self):\n    return LogicalEffect(tenant=t)\n",
        "from .commit_key import OCCURRENCE_RULES\n",
    ]
    for src in hostile:
        assert _occurrence_source_offenders(ast.parse(src))[0], f"the guard is blind to:\n{src}"
    clean = ("def logical_effect(self):\n    occ = occurrence_key_for(a)\n"
             "    return LogicalEffect(occurrence_key=occ)\n")
    assert _occurrence_source_offenders(ast.parse(clean)) == ([], 1)


def test_every_registered_action_class_renders_a_signed_proposal_and_identity_still_fails_closed():
    """### A RENDERING SURFACE DERIVES NO IDENTITY (CI #52 correction). U8.6 first derived the occurrence
    AT CONSTRUCTION, so the production Slack proposal button could not even be rendered for
    file_document / record_payment / adjust_invoice / check_call — construction raised. A proposal is
    inert data: it renders for every registered action class, and identity is derived — and fails
    closed — only at `logical_effect()`, which is where the M2 seam asks for it."""
    from freight_recon.product_policy import ACTION_CLASS_POPULATION

    rendered = {}
    for action_class in sorted(ACTION_CLASS_POPULATION):
        approval = _verify_operation_approval_value(
            _token(action_class=action_class, customer="Acme", load_ref="LD-9"), _SIGNER)
        rendered[action_class] = approval.proposed_intent
    assert len(rendered) == 8, f"expected all eight registered classes to render, got {sorted(rendered)}"
    # The token's proposal is tenant-less (the tenant is bound when it matures), so it is immature.
    assert all(p.is_mature is False for p in rendered.values())
    # Bound to a tenant, the CANONICAL classes are still refused at the identity boundary...
    for action_class in ("record_payment", "adjust_invoice", "check_call"):
        bound = dataclasses.replace(rendered[action_class], tenant=T_A, target_system="tms:truckingoffice")
        with pytest.raises(UnresolvedCanonicalOccurrence):
            bound.logical_effect()
    # ...while a SINGLE class, bound the same way, derives its ordinary identity.
    assert dataclasses.replace(rendered["raise_invoice"], tenant=T_A,
                               target_system="tms:truckingoffice").logical_effect().occurrence_key == ""
