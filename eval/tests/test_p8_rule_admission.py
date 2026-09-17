"""U8.2 — THE STANDING-RULE ADMISSION LAYER: the acceptance battery for compile-or-refuse Rules
composed into the U8.1 policy decision (ADR-010 §6 and §8 layer 6, `AC-WF10-005`).

Every test here could have failed before U8.2 existed. The battery measures three things and never
narration:

  * the COMPOSITION — a tenant's ALREADY-ACTIVE M12 rules become REAL `rules_evaluated` /
    `rules_matched` / `rules_rejected` in the `PolicyDecision`, a DENY rule blocks the action end to
    end at checkpoint step 6, and a scope with NO active rules leaves the decision BYTE-IDENTICAL to
    U8.1 (the rule fields are only non-decorative when a rule really acted);
  * the NARROWING-ONLY precedence — a rule may tighten a PERMIT into a DENY, but a rule that would
    LOOSEN a DENY is refused and recorded, and the layer names no gate member so it can never
    broaden the gate the tenant posture set;
  * the FAIL-CLOSED and HONEST-REFUSAL guarantees the machine already lands (M12) — a candidate over
    an unmodelled or MODEL_INFERRED field REFUSES TO COMPILE and the owner is TOLD (never "noted the
    procedure"), activation needs a named same-tenant human, a rule mints no gate decision, and a
    rule-vs-rule clash fails closed through M7 and never auto-merges — exercised here through the
    U8.2 lens to prove the integration preserves them.

The layer SHIPS DARK: it is imported only by `policy_admission.py`, which binds nothing live, so the
production `GateRegistry` stays EMPTY and the governed route still refuses.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for entry in (str(ROOT / "src"), str(ROOT / "eval"), str(ROOT / "eval" / "tests")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from freight_recon.checkpoint import (  # noqa: E402
    EvidenceCondition,
    GateDecision,
    ProvenanceClass,
    ProvenancedFact,
)
from freight_recon.policy import M11Machine, PolicyEvaluationInputs  # noqa: E402
from freight_recon.policy_admission import PolicyAdmissionAuthority  # noqa: E402
from freight_recon.rule import (  # noqa: E402
    DishonestReply,
    IllegalTransition,
    M12Machine,
    PRECEDENCE_LAYER,
    RuleEngineUnavailable,
    RuleWillNotCompile,
    assert_reply_is_honest,
    assert_within_precedence,
    compile_candidate,
    honest_refusal,
    reply_claims_enforcement,
)
from freight_recon.rule_admission import (  # noqa: E402
    SIGNAL_RULE_BROADENING_REFUSED,
    SIGNAL_RULE_DENIED,
    RuleAdmissionLayer,
)
from freight_recon.schema import (  # noqa: E402
    create_canonical_schema,
    enable_and_verify_foreign_keys,
)

TENANT = "acme-brokerage"
CLOCK = lambda: datetime(2026, 9, 3, 12, 0, 0, tzinfo=timezone.utc)  # noqa: E731
NOW = "2026-09-03T12:00:00Z"
_MODELLED = {"provenance_class": "SYSTEM_IMPORTED", "modelled": True}


# ------------------------------------------------------------------ helpers

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_canonical_schema(conn)
    enable_and_verify_foreign_keys(conn)
    return conn


def _human(conn, hid="po", *, role="POLICY_OWNER", state="ACTIVE", tenant=TENANT):
    offboarded = "2026-06-01T00:00:00Z" if state == "OFFBOARDED" else None
    conn.execute(
        "INSERT INTO tenant_humans (tenant, human_id, display_name, authority_role, state, "
        "recorded_at, recorded_by, recorded_by_kind, offboarded_at) VALUES (?,?,?,?,?,?,?, 'human', ?)",
        (tenant, hid, hid, role, state, "2026-01-01T00:00:00Z", "founder", offboarded))
    conn.commit()
    return hid


def _pod_deny_clauses():
    """A GATE_PRECONDITION guard: the POD must be CONSISTENT and non-inferred. Absent ⇒ the DENY
    rule fires (this is "never bill without a POD" — ADR-010 §6.1)."""
    return [
        {"field": "pod", "attr": "evidence_condition", "op": "==", "literal": "consistent", **_MODELLED},
        {"field": "pod", "attr": "provenance_class", "op": "in",
         "literal": ["SYSTEM_IMPORTED", "OWNER_ASSERTED", "MODEL_EXTRACTED"], **_MODELLED},
    ]


def _activate_rule(conn, rid, *, scope="action_class:raise_invoice", kind="GATE_PRECONDITION",
                   effect="DENY", clauses=None, owner="po", combine="AND", tenant=TENANT):
    """Activate a rule through M12's REAL lifecycle (no shortcut): propose → compile → confirm →
    activate, each by an authenticated human. Returns the rule_id."""
    m = M12Machine(conn, tenant=tenant, clock=CLOCK)
    m.propose(scope=scope, kind=kind, effect=effect, source_instruction=f"instruction {rid}",
              authored_by=owner, clauses=clauses if clauses is not None else _pod_deny_clauses(),
              combine=combine, rule_id=rid)
    m.compile(rid)
    m.confirm(rid, confirmed_by=owner)
    m.activate(rid, activated_by=owner)
    return rid


def _fact(field, *, value="x", provenance=ProvenanceClass.SYSTEM_IMPORTED,
          evidence=EvidenceCondition.CONSISTENT):
    return ProvenancedFact(field=field, provenance=provenance, evidence_condition=evidence, _value=value)


def _layer(conn, *, tenant=TENANT) -> RuleAdmissionLayer:
    return RuleAdmissionLayer(conn, tenant=tenant, clock=CLOCK)


# ==================================================================================================
# THE COMPOSITION — active rules are REAL evidence, narrowing only.
# ==================================================================================================

def test_no_active_rule_leaves_the_contribution_empty_and_decision_unchanged():
    """### THE POSITIVE CONTROL FOR BYTE-IDENTITY. With no active rule the layer folds in nothing:
    the base decision is returned unchanged and every rule field is empty, so a scope with no rules
    is BYTE-IDENTICAL to U8.1 (M-9: this is why the non-empty cases below prove something)."""
    conn = _conn()
    _human(conn)
    c = _layer(conn).compose(action_class="raise_invoice", base_decision="PERMIT", material_facts={})
    assert c.decision == "PERMIT"
    assert c.rules_evaluated == () and c.rules_matched == () and c.rules_rejected == ()
    assert c.security_signals == () and c.reason_suffix == ""
    assert not c.acted


def test_an_active_DENY_rule_with_no_POD_is_REAL_evidence_and_denies():
    """### "NEVER BILL WITHOUT A POD" — the canonical OUTCOME A. An ACTIVE GATE_PRECONDITION rule
    whose guarding POD clauses do NOT hold turns the decision into DENY, and the rule_id is REAL
    evidence in `rules_evaluated` AND `rules_matched` — not a decorative field."""
    conn = _conn()
    _human(conn)
    _activate_rule(conn, "r-pod")
    # No POD fact at all → the guard cannot hold → the rule fires.
    c = _layer(conn).compose(action_class="raise_invoice", base_decision="PERMIT", material_facts={})
    assert c.decision == "DENY", "the standing rule did not deny a bill with no POD"
    assert c.rules_evaluated == ("r-pod",)
    assert c.rules_matched == ("r-pod",), "the denying rule is not attributable in rules_matched"
    assert SIGNAL_RULE_DENIED in c.security_signals
    assert "r-pod" in c.reason_suffix


def test_an_active_rule_whose_guard_HOLDS_is_evaluated_but_does_not_act():
    """A rule that is satisfied does NOT act: it is EVALUATED (real evidence it was considered) but
    NOT MATCHED, and it neither denies nor loosens. Here the guarded counterparty is present, so the
    rule permits."""
    conn = _conn()
    _human(conn)
    _activate_rule(conn, "r-cp", clauses=[
        {"field": "counterparty", "attr": "value", "op": "==", "literal": "Acme Logistics", **_MODELLED}])
    facts = {"counterparty": _fact("counterparty", value="Acme Logistics")}
    c = _layer(conn).compose(action_class="raise_invoice", base_decision="PERMIT", material_facts=facts)
    assert c.decision == "PERMIT"
    assert c.rules_evaluated == ("r-cp",)
    assert c.rules_matched == (), "a satisfied rule must not be reported as having acted"


def test_the_full_admission_decision_carries_real_rule_ids(monkeypatch):
    """### THROUGH THE WHOLE U8.1 PATH: `PolicyAdmissionAuthority.resolve` returns a `PolicyDecision`
    whose rule fields carry the ACTIVE rule id when it acts. This is the field that ADR-010 §5.3
    asks for and that U8.1 left decorative — now it is deterministic evidence."""
    conn = _conn()
    _human(conn)
    _activate_policy(conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED,
                     policy_id="p-ok")
    _activate_rule(conn, "r-pod")
    d = PolicyAdmissionAuthority(conn, tenant=TENANT, clock=CLOCK).resolve(
        PolicyEvaluationInputs(tenant=TENANT, action_class="raise_invoice", now=NOW))
    assert d.decision == "DENY", "the standing rule did not deny through the admission layer"
    assert "r-pod" in d.rules_evaluated and "r-pod" in d.rules_matched
    assert SIGNAL_RULE_DENIED in d.security_signals
    assert d.escalation_required is True


def test_identical_inputs_and_active_rules_produce_a_BYTE_IDENTICAL_decision():
    """### DETERMINISM WITH RULES IN PLAY (ADR-010 §5.3 / §10). Given the same inputs and the same
    active rules, the decision is byte-identical — no clock, randomness, model call or unordered
    iteration enters the rule fold."""
    conn = _conn()
    _human(conn)
    _activate_policy(conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED,
                     policy_id="p-ok")
    _activate_rule(conn, "r-a")
    _activate_rule(conn, "r-b", clauses=[
        {"field": "counterparty", "attr": "value", "op": "==", "literal": "Acme Logistics", **_MODELLED}])
    inputs = PolicyEvaluationInputs(tenant=TENANT, action_class="raise_invoice", now=NOW)
    first = PolicyAdmissionAuthority(conn, tenant=TENANT, clock=CLOCK).resolve(inputs).to_bytes()
    again = PolicyAdmissionAuthority(conn, tenant=TENANT, clock=CLOCK).resolve(inputs).to_bytes()
    assert first == again


def test_a_MODEL_INFERRED_fact_at_evaluation_FAILS_CLOSED_no_decision():
    """### A GUESS CANNOT BECOME A GATE BY BEING PASSED THROUGH THE RULE LAYER (ADR-010 §5.1/§11).
    A rule compiled over a SYSTEM_IMPORTED field is handed a fact that is MODEL_INFERRED at runtime;
    reading its value RAISES, and the layer FAILS CLOSED — no decision is produced, at ANY
    confidence. There is no allow-on-rule-error path."""
    conn = _conn()
    _human(conn)
    _activate_rule(conn, "r-amt", clauses=[
        {"field": "amount", "attr": "value", "op": "==", "literal": 1, **_MODELLED}])
    inferred = {"amount": _fact("amount", value=1, provenance=ProvenanceClass.MODEL_INFERRED)}
    with pytest.raises(RuleEngineUnavailable):
        _layer(conn).compose(action_class="raise_invoice", base_decision="PERMIT",
                             material_facts=inferred)


def test_a_rule_that_would_LOOSEN_a_DENY_is_REFUSED_and_attributable():
    """### THE NEVER-LOOSEN GUARD (ADR-010 §7/§8). A layer-6 standing rule may only ever NARROW. A
    PERMIT-effect rule whose application would loosen a running DENY into a PERMIT is REFUSED, the
    decision STAYS DENY, and the offending rule is named in `rules_rejected` — a rule that could
    loosen authority would be worse than no rule at all."""
    conn = _conn()
    _human(conn)
    # A PERMIT-effect rule with no guard: evaluate_rule returns PERMIT unconditionally.
    _activate_rule(conn, "r-loosen", effect="PERMIT", clauses=[])
    c = _layer(conn).compose(action_class="raise_invoice", base_decision="DENY", material_facts={})
    assert c.decision == "DENY", "a PERMIT rule loosened a DENY — a layer-6 rule broadened authority"
    assert c.rules_matched == (), "a refused loosening rule must not be reported as having acted"
    assert any(rid == "r-loosen" for rid, _why in c.rules_rejected), (
        f"the refusal is not attributable to the offending rule: {c.rules_rejected}")
    assert SIGNAL_RULE_BROADENING_REFUSED in c.security_signals


def test_a_REQUIRE_HUMAN_APPROVAL_rule_is_matched_evidence_and_never_loosens():
    """### A REQUIRE_HUMAN_APPROVAL RULE IS RECORDED AS MATCHED AND CHANGES NO DECISION IN THIS SLICE.

    Its requirement — a human — is already carried by the effective gate, because nothing graduates:
    every checkpoint-evaluated action class is at or below HUMAN_APPROVAL_REQUIRED (a tenant may only
    narrow the product ceiling). So the rule is real evidence it was considered, and it NEVER loosens
    a PERMIT into anything broader. ### P14 DEBT (`U8.2-D1`): when autonomy graduation lands and an
    effective gate can be AUTONOMOUS_WITHIN_CAPS, this branch must be made a real gate-narrowing so a
    firing REQUIRE_HUMAN_APPROVAL rule cannot be matched-but-unenforced. Safe now; tracked for P14."""
    conn = _conn()
    _human(conn)
    _activate_rule(conn, "r-req", effect="REQUIRE_HUMAN_APPROVAL", clauses=[
        {"field": "counterparty", "attr": "value", "op": "==", "literal": "NEVER-MATCHES", **_MODELLED}])
    facts = {"counterparty": _fact("counterparty", value="Acme Logistics")}
    c = _layer(conn).compose(action_class="raise_invoice", base_decision="PERMIT", material_facts=facts)
    # the guard clause does not hold ⇒ the rule ACTS (REQUIRE_HUMAN_APPROVAL) ⇒ matched evidence...
    assert c.rules_matched == ("r-req",)
    # ...and it NEVER loosens: the decision stays PERMIT (the human gate already requires approval).
    assert c.decision == "PERMIT"
    assert SIGNAL_RULE_BROADENING_REFUSED not in c.security_signals


def test_a_non_gate_effect_rule_FAILS_CLOSED_at_the_checkpoint():
    """### A GATE_PRECONDITION RULE DECIDES PERMIT/DENY/REQUIRE_HUMAN_APPROVAL ONLY. A rule whose
    abstract effect is BIND or RESOLVE (an IDENTITY / CONFLICT_RESOLUTION effect) is not a gate
    decision; if one is ACTIVE on a checkpoint-evaluated scope it FAILS CLOSED — no decision — rather
    than being silently ignored (which would let the action proceed unjudged)."""
    conn = _conn()
    _human(conn)
    _activate_rule(conn, "r-bind", kind="CONSTRAINT", effect="BIND", clauses=[])
    with pytest.raises(RuleEngineUnavailable):
        _layer(conn).compose(action_class="raise_invoice", base_decision="PERMIT", material_facts={})


def test_stacked_rules_are_conjunctive_any_DENY_denies_never_auto_merged():
    """### FAIL-CLOSED CONJUNCTION, NEVER AN AUTO-MERGE. Two ACTIVE GATE_PRECONDITION rules stack on
    one multi-admitting action_class scope; the most restrictive wins. One permits and one denies ⇒
    the decision is DENY, and the layer picks no 'winner' that loosens."""
    conn = _conn()
    _human(conn)
    _activate_rule(conn, "r-permits", clauses=[
        {"field": "counterparty", "attr": "value", "op": "==", "literal": "Acme Logistics", **_MODELLED}])
    _activate_rule(conn, "r-denies")   # POD guard, no POD ⇒ denies
    facts = {"counterparty": _fact("counterparty", value="Acme Logistics")}
    c = _layer(conn).compose(action_class="raise_invoice", base_decision="PERMIT", material_facts=facts)
    assert c.decision == "DENY"
    assert set(c.rules_evaluated) == {"r-permits", "r-denies"}
    assert c.rules_matched == ("r-denies",)


# ==================================================================================================
# END TO END — the standing rule reaches the checkpoint's step 6.
# ==================================================================================================

def _wired_with_rule(tmp_path, *, rule_effect="DENY", rule_clauses=None, activate_rule=True,
                     action_class="raise_invoice"):
    from phase3_kit import make_store  # noqa: E402
    from freight_recon.checkpoint import CheckpointKernel, GateRegistry  # noqa: E402
    from phase3_kit import Clock  # noqa: E402

    store = make_store(tmp_path, TENANT, name="p8u2.db")
    create_canonical_schema(store.conn)
    enable_and_verify_foreign_keys(store.conn)
    store.conn.row_factory = sqlite3.Row
    _human(store.conn)
    _activate_policy(store.conn, scope=action_class, gate=GateDecision.HUMAN_APPROVAL_REQUIRED,
                     policy_id="p-ok")
    if activate_rule:
        _activate_rule(store.conn, "r-pod", scope=f"action_class:{action_class}",
                       effect=rule_effect, clauses=rule_clauses)
    authority = PolicyAdmissionAuthority(store.conn, tenant=TENANT, clock=CLOCK)
    clock = Clock()
    kernel = CheckpointKernel(store, GateRegistry({}, policy_version="pv1"), clock=clock,
                              policy_authority=authority)
    return store, kernel, clock, authority


def _scenario(authority, clock, *, action_class="raise_invoice", resource="load:4471",
              extra_facts=None):
    from phase3_kit import (  # noqa: E402
        CheckpointInputs, CheckpointRequest, make_approval, make_effect, make_facts, live_reader,
    )
    effect = make_effect(tenant=TENANT, action_class=action_class, resource=resource)
    facts = make_facts(entity_ref=resource)
    if extra_facts:
        facts.update(extra_facts)
    versions = {resource: 17}
    approval = make_approval(effect, facts, versions, clock,
                             policy_version=authority.current_policy_version())
    world = {"facts": dict(facts), "projection": {"status": "DELIVERED"}, "versions": dict(versions)}
    inputs = CheckpointInputs(
        material_facts_reader=live_reader(lambda: dict(world["facts"])),
        projection_assertion={"status": "DELIVERED"},
        projected_state_reader=live_reader(lambda: dict(world["projection"])),
        entity_version_reader=live_reader(lambda: dict(world["versions"])),
        approval=approval)
    request = CheckpointRequest(effect=effect, actor="pipeline",
                               accountable_owner="owner:rasheed", target_entity_ref=resource)
    return effect, inputs, request


def _rows(store, table, commit_key):
    return store.conn.execute(
        f"SELECT * FROM {table} WHERE tenant = ? AND commit_key = ?",
        (store.tenant, commit_key)).fetchall()


def test_e2e_an_active_DENY_rule_refuses_at_step_6_with_no_witness(tmp_path):
    """### END TO END: a standing rule blocks a real effect. With "never bill without a POD" ACTIVE
    and no POD in the facts, the checkpoint refuses at STEP 6 — no witness row, no grant row — and
    the refusal names the rule that did it (real, attributable evidence)."""
    from phase3_kit import run_checkpoint  # noqa: E402
    store, kernel, clock, authority = _wired_with_rule(tmp_path)
    effect, inputs, request = _scenario(authority, clock)

    outcome = run_checkpoint(kernel, request, inputs)
    assert not outcome.authorized, "a standing DENY rule did not block the effect"
    assert outcome.step == 6 and outcome.reason == "POLICY_DENIED", (
        f"step={outcome.step} reason={outcome.reason!r}")
    assert "r-pod" in outcome.detail, "the refusal is not attributable to the rule"
    assert _rows(store, "checkpoint_witnesses", effect.key()) == []
    assert _rows(store, "effect_grants", effect.key()) == []


def test_e2e_a_satisfied_rule_lets_the_checkpoint_pass_and_binds_the_witness(tmp_path):
    """### THE HAPPY PATH WITH A RULE IN PLAY: a rule whose guard HOLDS does not block. A POD that is
    consistent and system-imported satisfies "never bill without a POD", so the checkpoint mints one
    witness and one claimable grant — the rule was evaluated and permitted."""
    from phase3_kit import run_checkpoint, claim_grant_cas, params_for  # noqa: E402
    pod = _fact("pod", value="POD-1", provenance=ProvenanceClass.SYSTEM_IMPORTED,
                evidence=EvidenceCondition.CONSISTENT)
    store, kernel, clock, authority = _wired_with_rule(tmp_path)
    effect, inputs, request = _scenario(authority, clock, extra_facts={"pod": pod})

    outcome = run_checkpoint(kernel, request, inputs)
    assert outcome.authorized, f"a satisfied standing rule wrongly blocked the effect: {outcome}"
    assert len(_rows(store, "checkpoint_witnesses", effect.key())) == 1
    claim = claim_grant_cas(kernel, outcome.handle, params_for(effect))
    assert claim.claimed, f"the claim refused on the satisfied-rule path: {claim.cause}"


def test_e2e_no_active_rule_is_exactly_the_u81_green_path(tmp_path):
    """With NO active rule the checkpoint behaves EXACTLY as U8.1: the tenant policy permits and one
    witness + one grant are minted. The rule layer added nothing where there was nothing to add."""
    from phase3_kit import run_checkpoint  # noqa: E402
    store, kernel, clock, authority = _wired_with_rule(tmp_path, activate_rule=False)
    effect, inputs, request = _scenario(authority, clock)
    outcome = run_checkpoint(kernel, request, inputs)
    assert outcome.authorized, f"the U8.1 green path regressed with the rule layer present: {outcome}"
    assert len(_rows(store, "checkpoint_witnesses", effect.key())) == 1
    assert len(_rows(store, "effect_grants", effect.key())) == 1


# ==================================================================================================
# OUTCOME B — an owner's sentence either COMPILES or is HONESTLY REFUSED (ADR-010 §6, AC-WF10-005).
# ==================================================================================================

def test_a_candidate_on_an_UNMODELLED_field_refuses_to_compile_outcome_B():
    """### "DO NOT USE CARRIER X FOR PRODUCE" — the important OUTCOME B. `commodity` is not a
    modelled field, so the candidate CANNOT compile; the refusal NAMES what is missing, and it is a
    feature request surfaced by an honest refusal, not a silent failure."""
    with pytest.raises(RuleWillNotCompile) as exc:
        compile_candidate(
            {"kind": "GATE_PRECONDITION", "effect": "DENY", "combine": "AND", "clauses": [
                {"field": "commodity", "attr": "value", "op": "==", "literal": "produce",
                 "provenance_class": "SYSTEM_IMPORTED", "modelled": False}]},
            scope="book_carrier")
    assert "commodity" in exc.value.missing


def test_a_candidate_on_a_MODEL_INFERRED_field_refuses_to_compile_at_any_confidence():
    """### A RULE MAY NEVER BRANCH ON A GUESS (ADR-010 §5.1). A referenced field declared
    MODEL_INFERRED FAILS TO COMPILE — there is no confidence to raise, so it fails at confidence
    1.0 too."""
    with pytest.raises(RuleWillNotCompile) as exc:
        compile_candidate(
            {"kind": "GATE_PRECONDITION", "effect": "DENY", "combine": "AND", "clauses": [
                {"field": "margin", "attr": "value", "op": "<", "literal": 12,
                 "provenance_class": "MODEL_INFERRED", "modelled": True}]},
            scope="raise_invoice")
    assert "margin" in exc.value.missing


def test_an_uncompilable_instruction_never_claims_a_rule_was_installed_L_C():
    """### THE L-C GUARD, ON THE LITERAL REPLY TEXT. An uncompilable instruction's reply MUST be the
    honest refusal and MUST NOT claim enforcement — "noted the procedure" with no ACTIVE rule_id is
    the exact defect ADR-010 §6 exists to remove. The same claiming sentence is honest ONLY when a
    real ACTIVE rule_id backs it."""
    refusal = honest_refusal("commodity", why="commodity as a field on the load")
    assert not reply_claims_enforcement(refusal), "the honest refusal must not read as enforcement"
    assert_reply_is_honest(refusal, active_rule_id=None)   # honest: no false claim

    with pytest.raises(DishonestReply):
        assert_reply_is_honest("📋 Noted the procedure for raise_invoice", active_rule_id=None)
    # ...and the SAME claim is honest when a real ACTIVE rule backs it.
    assert_reply_is_honest("The rule is now active.", active_rule_id="rule-real")


# ==================================================================================================
# AUTHORIZATION, PRECEDENCE, CONFLICT, SHIP-DARK — the invariants the integration must preserve.
# ==================================================================================================

def test_activation_requires_a_named_same_tenant_ACTIVE_human():
    """### ACTIVATION NEEDS AN AUTHENTICATED HUMAN OF THIS TENANT. A model, a counterparty, an
    offboarded human and a wrong-tenant human each activate NOTHING. There is no admin/superuser
    backdoor; the activator is FK-bound into `tenant_humans`."""
    conn = _conn()
    _human(conn, "po")
    _human(conn, "gone", state="OFFBOARDED")
    m = M12Machine(conn, tenant=TENANT, clock=CLOCK)
    m.propose(scope="action_class:raise_invoice", kind="GATE_PRECONDITION", effect="DENY",
              source_instruction="never bill without a POD", authored_by="po",
              clauses=_pod_deny_clauses(), rule_id="r1")
    m.compile("r1")
    m.confirm("r1", confirmed_by="po")
    # a MODEL activation is refused and recorded (F14), not honoured.
    with pytest.raises(IllegalTransition):
        m.activate("r1", activated_by="po", actor_kind="model")
    # an offboarded human cannot activate.
    with pytest.raises(Exception):
        m.activate("r1", activated_by="gone")
    # a wrong-tenant human cannot activate.
    with pytest.raises(Exception):
        m.activate("r1", activated_by="stranger")
    assert m.get("r1").state.value == "CONFIRMED", "an unauthorized activation moved the rule to ACTIVE"
    # the rule never became a real evidence source for the admission layer.
    assert _layer(conn).active_rules("raise_invoice") == ()


def test_a_MODEL_activation_records_the_F14_tripwire_and_activates_nothing():
    """A model activation attempt emits the already-registered F14
    `UnauthorizedPolicyActivationAttempted` (reused, not a second contract) and the rule stays
    CONFIRMED — the model proposes; it never activates."""
    conn = _conn()
    _human(conn, "po")
    m = M12Machine(conn, tenant=TENANT, clock=CLOCK)
    m.propose(scope="action_class:raise_invoice", kind="GATE_PRECONDITION", effect="DENY",
              source_instruction="x", authored_by="po", clauses=_pod_deny_clauses(), rule_id="r1")
    m.compile("r1")
    m.confirm("r1", confirmed_by="po")
    with pytest.raises(IllegalTransition):
        m.activate("r1", activated_by="po", actor_kind="model")
    rows = conn.execute(
        "SELECT event_type FROM security_events WHERE tenant = ? AND "
        "event_type = 'UnauthorizedPolicyActivationAttempted'", (TENANT,)).fetchall()
    assert rows, "a model activation attempt did not record the F14 tripwire"


def test_at_most_one_active_rule_survives_per_single_admitting_scope():
    """### CONFLICT CANNOT BOTH-PERSIST on a single-admitting scope. The `subject_type` form admits
    exactly ONE ACTIVE rule per (tenant, scope, kind): activating a second SUPERSEDES the first in
    the same transaction, and a raw second ACTIVE insert is refused by the partial unique index."""
    conn = _conn()
    _human(conn)
    _activate_rule(conn, "id-a", scope="subject_type:carrier_invoice", kind="IDENTITY",
                   effect="BIND", clauses=[])
    _activate_rule(conn, "id-b", scope="subject_type:carrier_invoice", kind="IDENTITY",
                   effect="BIND", clauses=[])
    active = conn.execute(
        "SELECT rule_id FROM rules WHERE tenant = ? AND scope = 'subject_type:carrier_invoice' "
        "AND kind = 'IDENTITY' AND state = 'ACTIVE'", (TENANT,)).fetchall()
    assert len(active) == 1, f"two active rules coexist on a single-admitting scope: {active}"
    # ...and a raw second ACTIVE row is refused by the DB, not by convention.
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO rules (tenant, rule_id, rule_version, scope, kind, compiled_predicate, "
            "test_vectors, state, version, source_instruction, authored_by, activated_by, "
            "change_direction, created_at, updated_at) VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (TENANT, "id-c", 999, "subject_type:carrier_invoice", "IDENTITY",
             '{"status":"COMPILED"}', "[]", "ACTIVE", 1, "i", "po", "po", "narrow", "t", "t"))


def test_a_rule_never_overrides_a_higher_precedence_layer():
    """### A STANDING RULE IS PRECEDENCE LAYER 6 (ADR-010 §8) AND OVERRIDES NOTHING ABOVE IT — not a
    Constraint (1), a Permanent Truth (2), the Brake (3), the Product Policy ceiling (4) or the
    Tenant Policy (5). Placing a rule at any of those layers is refused; its own layer or below is
    accepted."""
    for layer in range(1, PRECEDENCE_LAYER):
        with pytest.raises(IllegalTransition):
            assert_within_precedence(layer)
    assert_within_precedence(PRECEDENCE_LAYER)


def test_a_rule_vs_rule_conflict_routes_through_M7_and_the_rule_never_activates():
    """### TWO CONFLICTING RULES FAIL CLOSED THROUGH M7 — NEVER AUTO-MERGED. RU-3 CALLS M7's landed
    `raise_conflict` (RULE_VS_RULE); the newer rule STAYS COMPILED and blocked on the conflict, so it
    NEVER becomes ACTIVE and NEVER reaches the admission layer. Neyma picks no winner."""
    from freight_recon.rule import RaisedConflict  # noqa: E402
    conn = _conn()
    _human(conn)
    _activate_rule(conn, "r-active")                     # an ACTIVE rule on the scope
    m = M12Machine(conn, tenant=TENANT, clock=CLOCK)
    m.propose(scope="action_class:raise_invoice", kind="GATE_PRECONDITION", effect="DENY",
              source_instruction="a competing rule", authored_by="po",
              clauses=_pod_deny_clauses(), rule_id="r-new")
    m.compile("r-new")
    result = m.detect_conflict("r-new", against_rule_id="r-active", owner_id="po")
    assert isinstance(result.conflict, RaisedConflict) and result.conflict.kind == "RULE_VS_RULE"
    assert m.get("r-new").state.value == "COMPILED", "a conflicted rule left COMPILED/blocked"
    # a real M7 conflicts row exists, minted by M7 (not M12).
    assert conn.execute(
        "SELECT COUNT(*) FROM conflicts WHERE tenant = ? AND kind = 'RULE_VS_RULE'",
        (TENANT,)).fetchone()[0] == 1
    # ...and only the original, unconflicted rule is ever ACTIVE evidence for admission.
    assert tuple(r.rule_id for r in _layer(conn).active_rules("raise_invoice")) == ("r-active",)


def test_the_admission_layer_mints_no_gate_decision_and_names_no_gate_token():
    """### THE RULE ADMISSION LAYER IS NOT A GATE AUTHORITY. It constructs no `GateEntry`/`GateRegistry`,
    calls no `register_gate`, and names NO gate-decision member token in executable code — so
    `checkpoint.py` stays the SOLE minter and the R-07 gate-runtime allowlist is unchanged by U8.2."""
    from phase0 import gate_scan  # noqa: E402
    src = (ROOT / "src" / "freight_recon" / "rule_admission.py").read_text(encoding="utf-8")
    assert gate_scan.gate_token_sites(src) == [], "rule_admission.py carries gate vocabulary"
    assert gate_scan.gate_registration_sites(src, label="rule_admission.py") == [], (
        "rule_admission.py registers a gate — the checkpoint is the sole gate authority")
    assert "rule_admission.py" not in gate_scan.GATE_RUNTIME_MODULES


def test_the_production_gate_registry_is_STILL_empty_after_u82():
    """### SHIPS DARK. U8.2 binds nothing live: the production `GateRegistry` population stays EMPTY,
    exactly as after U8.1 — composing standing rules registered not one action class. Proven by an
    AST sweep of the WHOLE production tree (including the new `rule_admission.py`) for any real gate
    registration site, mirroring the U8.1 empty-registry proof so U8.2's module is in the population."""
    from phase0 import gate_scan  # noqa: E402
    sites: list[str] = []
    swept = 0
    for root in ("src", "scripts"):
        for path in sorted((ROOT / root).rglob("*.py")):
            swept += 1
            sites += gate_scan.gate_registration_sites(
                path.read_text(encoding="utf-8"), label=str(path.relative_to(ROOT)))
    assert swept > 100, f"the sweep walked only {swept} modules — it saw a corner (M-9)"
    assert sites == [], f"U8.2 populated the kernel registry after all: {sites}"


# ------------------------------------------------------------------ M11 policy activation helper

def _activate_policy(conn, *, scope, gate, policy_id, owner="po", tenant=TENANT):
    """Activate a tenant policy through M11's real seven-transition path, so the admission layer has a
    real base posture to narrow. Mirrors the U8.1 battery's helper."""
    m = M11Machine(conn, tenant=tenant, clock=CLOCK, product_ceiling=gate)
    aid, diff = f"appr-{policy_id}", f"DIFF-{policy_id}"
    cols = dict(
        tenant=tenant, approval_id=aid, commit_key=f"ck-{aid}", action_class="change_policy",
        state="GRANTED", version=1, material_facts_fingerprint=diff, canonical_payload=b"{}",
        fingerprint_version="fp_v1", entity_versions_json='{"policy:%s": 1}' % policy_id,
        policy_version="1", brake_version="bv1", gate_decision="HUMAN_APPROVAL_REQUIRED",
        required_signatures=1, rendered_facts="{}", requested_at="2026-01-01T00:00:00Z",
        expires_at="2027-01-01T00:00:00Z", frozen=0, granted_by=owner,
        created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
    conn.execute(f"INSERT INTO approvals ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                 tuple(cols.values()))
    conn.commit()
    m.propose_draft(scope=scope, scope_kind="action_class", gate_decision=gate, caps={},
                    predicate={"clauses": []}, authored_by=owner, policy_id=policy_id)
    m.submit(policy_id, actor_id=owner)
    m.approve(policy_id, approval_id=aid, diff_fingerprint=diff, approved_by=owner)
    m.activate(policy_id, activated_by=owner)
    return policy_id
