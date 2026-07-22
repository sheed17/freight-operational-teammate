"""The canonical seven-step ORDER, defended against multi-fault inputs (finding F-D).

WHY THIS FILE EXISTS. The 105-case matrix perturbs the green scenario ONE fault at a time, so it
proves each step refuses what it owns. It cannot prove ORDER: a kernel that ran the seven checks
in any sequence would pass all 105 cases, because with one fault present only one step can fail.
Order is only observable when SEVERAL steps would fail at once — and that is precisely the state
a broken system is in.

WHY ORDER IS A SAFETY PROPERTY, NOT A PREFERENCE. SD-7 fixes the sequence and requires the FIRST
failing step to be the one reported. The ladder runs from "this was never authorized" (step 1)
through "the world moved underneath the decision" (steps 2-5) to "policy forbids it" (step 6) and
"a human has stopped us" (step 7). Reporting the later fault sends the operator to the wrong
remedy: told BRAKE_ENGAGED for a request that also has no valid approval, the honest response is
to release the brake — which would then let through something that was never authorized at all.
The reviewed dual-fault case (policy/gate failure + an ACTIVE brake) is exactly that shape, and
step 6 must win over step 7.

HOW EACH CASE IS BUILT. Every case constructs a scenario in which the EARLIER step's fault and
EVERY later step's fault are simultaneously present, then asserts three things:
  * the reported step is the earliest one;
  * the later fault is genuinely present (proved by removing the earlier fault and watching the
    later step fail) — without this the test could pass because the later fault never existed;
  * the universal oracle still holds: outcome (b), no witness, no live grant.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from phase3_kit import (
    T_B,
    assert_outcome_b,
    green_scenario,
    perturbed_facts,
)

from freight_recon.checkpoint import (
    CHECKPOINT_STEPS,
    Caps,
    CheckpointInputs,
    GateDecision,
    GateEntry,
    GateRegistry,
    NativeClaim,
    ProvenanceClass,
    run_checkpoint,
)


def _with(inputs: CheckpointInputs, **changes) -> CheckpointInputs:
    """A modified copy of CheckpointInputs. It is a slots class with a validating __init__, not a
    dataclass — deliberately, since the reader-type refusal must run on every construction — so
    the copy goes back through that same validation rather than around it."""
    fields = {
        "material_facts_reader": inputs.material_facts_reader,
        "projection_assertion": inputs.projection_assertion,
        "projected_state_reader": inputs.projected_state_reader,
        "entity_version_reader": inputs.entity_version_reader,
        "native_claims": inputs.native_claims,
        "approval": inputs.approval,
        "proposed_entity_versions": inputs.proposed_entity_versions,
        "runs_today": inputs.runs_today,
    }
    fields.update(changes)
    return CheckpointInputs(**fields)


# ------------------------------------------------------------------ fault injectors
#
# One injector per step. Each returns a NEW CheckpointInputs (and may mutate `world`, the live
# source every reader reads through), introducing exactly the fault that step owns. Composing
# injectors is what produces a multi-fault input.


def _fault_1(scenario, inputs):
    """Step 1 — approval validity: the approval is EXPIRED."""
    return _with(inputs, approval=replace(inputs.approval, expires_at=scenario["clock"].now))


def _fault_2(scenario, inputs):
    """Step 2 — material facts: the approved amount drifted."""
    scenario["world"]["facts"] = perturbed_facts(
        scenario["world"]["facts"], "counterparty", _value="Someone Else Entirely")
    return inputs


def _fault_3(scenario, inputs):
    """Step 3 — projected state: the live projection no longer matches the assertion."""
    scenario["world"]["projection"] = {"status": "IN_TRANSIT"}
    return inputs


def _fault_4(scenario, inputs):
    """Step 4 — native state: a retracted native claim."""
    return _with(inputs, native_claims=(
        NativeClaim(claim_id="nc-1", status="RETRACTED", conflicting=False,
                    provenance=ProvenanceClass.SYSTEM_IMPORTED),))


def _fault_5(scenario, inputs):
    """Step 5 — entity-version concurrency: the pinned entity moved."""
    scenario["world"]["versions"] = {k: v + 1 for k, v in scenario["world"]["versions"].items()}
    return inputs


def _fault_6(scenario, inputs):
    """Step 6 — policy evaluation: the approval cites a policy version that no longer exists."""
    return _with(inputs, approval=replace(inputs.approval, policy_version="pv0-retired"))


def _fault_7(scenario, inputs):
    """Step 7 — brake admission: a tenant-wide brake is ACTIVE."""
    scenario["kernel"].brakes.engage(
        tenant=scenario["kernel"].store.tenant, actor="owner:rasheed", actor_kind="HUMAN",
        reason="incident: dual-fault ordering case", action_class=None)
    return inputs


FAULTS = {1: _fault_1, 2: _fault_2, 3: _fault_3, 4: _fault_4,
          5: _fault_5, 6: _fault_6, 7: _fault_7}


def _scenario(tmp_path, *, name="order.db"):
    store, kernel, clock, effect, facts, versions, approval, world, inputs, request = (
        green_scenario(tmp_path))
    return {"store": store, "kernel": kernel, "clock": clock, "effect": effect,
            "world": world, "inputs": inputs, "request": request}


def _run_with(tmp_path, steps, *, name):
    """Build a fresh scenario, inject every fault in `steps`, run the checkpoint."""
    sc = _scenario(tmp_path / name)
    inputs = sc["inputs"]
    for step in sorted(steps):
        inputs = FAULTS[step](sc, inputs)
    return sc, run_checkpoint(sc["kernel"], sc["request"], inputs)


# ------------------------------------------------------------------ the reviewed dual-fault case


def test_policy_failure_and_an_active_brake_report_step_6_not_step_7(tmp_path):
    """THE REVIEWED CASE, named explicitly: step 6 must win over step 7.

    Both faults are present at once — the approval was granted under a retired policy version AND
    a tenant-wide brake is ACTIVE. The kernel must report `policy_evaluation`, not
    `brake_admission`.
    """
    sc, outcome = _run_with(tmp_path, {6, 7}, name="dual67")
    assert not outcome.authorized
    assert outcome.step == 6, (
        f"the earliest canonical failing step is 6 (policy_evaluation); the kernel reported "
        f"step {outcome.step} ({outcome.step_name}). Order is not being honoured."
    )
    assert outcome.step_name == "policy_evaluation"
    assert outcome.reason == "POLICY_VERSION_DRIFT"
    assert_outcome_b(sc["store"], sc["effect"].key())


def test_the_brake_fault_in_that_case_is_real_and_would_fail_on_its_own(tmp_path):
    """The dual-fault case proves nothing unless the LATER fault genuinely exists.

    Remove the policy fault, keep the brake, and step 7 must fail — so the test above really did
    choose between two live faults rather than observing one.
    """
    sc, outcome = _run_with(tmp_path, {7}, name="brakeonly")
    assert not outcome.authorized
    assert outcome.step == 7 and outcome.step_name == "brake_admission"
    assert outcome.reason == "BRAKE_ENGAGED"


def test_the_policy_fault_in_that_case_is_real_and_would_fail_on_its_own(tmp_path):
    """The mirror check: the earlier fault is real too, not an artefact of ordering."""
    sc, outcome = _run_with(tmp_path, {6}, name="policyonly")
    assert not outcome.authorized
    assert outcome.step == 6 and outcome.reason == "POLICY_VERSION_DRIFT"


# ------------------------------------------------------------------ every adjacent pair


@pytest.mark.parametrize("earlier,later", [(n, n + 1) for n in range(1, 7)])
def test_every_adjacent_pair_reports_the_earlier_step(tmp_path, earlier, later):
    """All six adjacent pairs. A single transposition anywhere in the ladder fails one of these."""
    sc, outcome = _run_with(tmp_path, {earlier, later}, name=f"pair{earlier}{later}")
    assert not outcome.authorized
    assert outcome.step == earlier, (
        f"steps {earlier} and {later} both fail; the kernel reported step {outcome.step} "
        f"({outcome.step_name}) instead of {earlier} ({CHECKPOINT_STEPS[earlier - 1]})"
    )
    assert_outcome_b(sc["store"], sc["effect"].key())


@pytest.mark.parametrize("later", list(range(2, 8)))
def test_the_later_fault_of_every_pair_is_independently_real(tmp_path, later):
    """Proves the population of `later` faults is genuine — the anti-vacuity half of the pairs."""
    sc, outcome = _run_with(tmp_path, {later}, name=f"solo{later}")
    assert not outcome.authorized
    assert outcome.step == later, (
        f"the injector for step {later} did not actually make step {later} fail (got step "
        f"{outcome.step}); every pair test using it would have proved nothing"
    )


# ------------------------------------------------------------------ the whole ladder at once


@pytest.mark.parametrize("first", list(range(1, 8)))
def test_all_remaining_faults_at_once_still_report_the_earliest(tmp_path, first):
    """Steps `first`..7 ALL fail simultaneously. Only step `first` may be reported.

    This is the strongest ordering statement available: with a suffix of the ladder entirely
    broken, any reordering within that suffix changes the answer.
    """
    steps = set(range(first, 8))
    sc, outcome = _run_with(tmp_path, steps, name=f"suffix{first}")
    assert not outcome.authorized
    assert outcome.step == first, (
        f"steps {sorted(steps)} all fail; the earliest is {first} "
        f"({CHECKPOINT_STEPS[first - 1]}) but the kernel reported step {outcome.step} "
        f"({outcome.step_name})"
    )
    assert_outcome_b(sc["store"], sc["effect"].key())


def test_the_reported_step_name_always_matches_the_canonical_index(tmp_path):
    """`step` and `step_name` may never disagree — a swap that renumbered one and not the other
    would otherwise be invisible to every assertion above."""
    seen = 0
    for first in range(1, 8):
        _sc, outcome = _run_with(tmp_path, set(range(first, 8)), name=f"names{first}")
        assert not outcome.authorized
        assert outcome.step_name == CHECKPOINT_STEPS[outcome.step - 1], (
            f"step {outcome.step} reported as {outcome.step_name!r}; canonical name is "
            f"{CHECKPOINT_STEPS[outcome.step - 1]!r}"
        )
        seen += 1
    assert seen == 7, "the ladder was not walked - this guard would prove nothing"


# ------------------------------------------------------------------ order across the two prefixes


def test_the_tenant_check_precedes_every_step(tmp_path):
    """A cross-tenant request is refused at step 1 even with the whole ladder broken behind it.

    The kernel never crosses a tenant, and it must not need to evaluate anything else to know it.
    """
    sc = _scenario(tmp_path / "xtenant")
    inputs = sc["inputs"]
    for step in (2, 3, 4, 5, 6, 7):
        inputs = FAULTS[step](sc, inputs)
    request = replace(sc["request"], effect=replace(sc["request"].effect, tenant=T_B))
    outcome = run_checkpoint(sc["kernel"], request, inputs)
    assert not outcome.authorized
    assert outcome.step == 1 and outcome.reason == "TENANT_MISMATCH"


def test_a_forbidden_action_class_reports_step_6_not_the_brake(tmp_path):
    """FORBIDDEN is a step-6 verdict. With a brake also ACTIVE, step 6 still wins.

    Distinct from the policy-drift case above: this one has no approval path at all, so it also
    proves the ordering holds for the gate-ladder branch of step 6 rather than only its
    version-drift branch.
    """
    store, kernel, clock, effect, facts, versions, approval, world, inputs, request = (
        green_scenario(tmp_path, action_class="forbidden_op"))
    kernel.brakes.engage(tenant=store.tenant, actor="owner:rasheed", actor_kind="HUMAN",
                         reason="incident", action_class=None)
    outcome = run_checkpoint(kernel, request, inputs)
    assert not outcome.authorized
    assert outcome.step == 6 and outcome.reason == "FORBIDDEN_ACTION_CLASS", (
        f"reported step {outcome.step} ({outcome.reason}); FORBIDDEN is step 6 and must be "
        "reported ahead of an ACTIVE brake"
    )
    assert_outcome_b(store, effect.key())


def test_a_cap_breach_reports_step_6_not_the_brake(tmp_path):
    """The autonomous branch of step 6, against an ACTIVE brake. Same ordering rule."""
    registry = GateRegistry(
        {"file_document": GateEntry(gate=GateDecision.AUTONOMOUS_WITHIN_CAPS,
                                    caps=Caps(max_per_day=1))},
        policy_version="pv1",
    )
    store, kernel, clock, effect, facts, versions, approval, world, inputs, request = (
        green_scenario(tmp_path, action_class="file_document", registry=registry))
    inputs = _with(inputs, approval=None, proposed_entity_versions=dict(versions), runs_today=5)
    kernel.brakes.engage(tenant=store.tenant, actor="owner:rasheed", actor_kind="HUMAN",
                         reason="incident", action_class=None)
    outcome = run_checkpoint(kernel, request, inputs)
    assert not outcome.authorized
    assert outcome.step == 6 and outcome.reason == "CAP_EXCEEDED"
    assert_outcome_b(store, effect.key())
