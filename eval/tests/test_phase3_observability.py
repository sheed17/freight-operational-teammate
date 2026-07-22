"""P3 observability, proved with a REAL observer (finding F-F).

The reviewer's objection, restated so it cannot be lost: the kernel HAD an observer parameter and
called it, and that was being treated as evidence that the unit's observability requirements were
met. Plumbing is not behaviour. P3's `rebaseline_contract.observability_requirements` names four
things — *every checkpoint step outcome*, *every refusal with the refusing step named*, *brake
state*, *claim CAS contention* — and each is asserted here against the events an actual observer
actually received, never against the existence of the hook.

The observer used throughout is `Recorder`: a plain list-appending callable attached at kernel
construction. Nothing here inspects kernel internals to decide what "should" have been emitted;
every assertion reads the recorded stream.

The fifth property is the one that makes observability safe rather than merely present:
**an observer that fails may not change what happened.** Observability describes control flow and
may never participate in it, so a raising observer must leave the checkpoint's outcome, the
witness row and the grant row byte-identical to a run with a silent observer.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from phase3_kit import (
    T_A,
    assert_outcome_a,
    assert_outcome_b,
    green_scenario,
    make_kernel,
    make_store,
    params_for,
)

from freight_recon.checkpoint import (
    CHECKPOINT_STEPS,
    claim_grant_cas,
    run_checkpoint,
)


class Recorder:
    """A real observer. Records every event it is handed, in order."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    def __call__(self, event: dict) -> None:
        self.events.append(event)

    def kinds(self) -> list[str]:
        return [e["kind"] for e in self.events]

    def of(self, kind: str) -> list[dict]:
        return [e for e in self.events if e["kind"] == kind]

    def steps(self) -> list[int]:
        return [e["step"] for e in self.of("CheckpointStep")]


def _observed_scenario(tmp_path, *, observer, name="obs", **kwargs):
    """green_scenario, rebuilt so the kernel carries a REAL observer from construction.

    `name` selects a DISTINCT subdirectory: green_scenario always names its database `p3.db`, so
    two scenarios under one tmp_path would silently share a store and the second checkpoint would
    be refused COMMIT_KEY_HELD by the first one's grant.
    """
    store, kernel, clock, effect, facts, versions, approval, world, inputs, request = (
        green_scenario(tmp_path / name, **kwargs))
    kernel._observer = observer          # the constructor slot; attached before anything runs
    return store, kernel, clock, effect, world, inputs, request


# ============================================================ every step outcome is emitted


def test_a_passing_checkpoint_emits_the_outcome_of_all_seven_steps_in_canonical_order(tmp_path):
    """Requirement 1: *every checkpoint step outcome*. All seven, in order, plus the pass event."""
    rec = Recorder()
    store, kernel, _clock, effect, _world, inputs, request = _observed_scenario(tmp_path, observer=rec)

    outcome = run_checkpoint(kernel, request, inputs)
    assert outcome.authorized, getattr(outcome, "detail", "")

    assert rec.steps() == [1, 2, 3, 4, 5, 6, 7], (
        f"the seven step outcomes were not all emitted in canonical order: {rec.steps()}"
    )
    for event in rec.of("CheckpointStep"):
        assert event["outcome"] == "PASS"
        assert event["step_name"] == CHECKPOINT_STEPS[event["step"] - 1], (
            f"step {event['step']} emitted under the name {event['step_name']!r}"
        )
    assert "CheckpointPassed" in rec.kinds(), "the passing checkpoint itself was not observable"


@pytest.mark.parametrize("failing_step", list(range(1, 8)))
def test_a_refused_checkpoint_emits_every_step_up_to_and_including_the_failure(
    tmp_path, failing_step
):
    """The ladder stays observable on the refusal path: PASS for each earlier step, then the
    refusal naming the failing one — and NOTHING after it, because nothing after it ran."""
    from test_phase3_step_order import FAULTS

    rec = Recorder()
    store, kernel, clock, effect, world, inputs, request = _observed_scenario(
        tmp_path, observer=rec, name=f"refuse{failing_step}")
    sc = {"clock": clock, "world": world, "kernel": kernel}
    inputs = FAULTS[failing_step](sc, inputs)

    outcome = run_checkpoint(kernel, request, inputs)
    assert not outcome.authorized and outcome.step == failing_step

    assert rec.steps() == list(range(1, failing_step)), (
        f"expected PASS events for steps 1..{failing_step - 1}; got {rec.steps()}"
    )
    failed = rec.of("CheckpointFailed")
    assert len(failed) == 1, f"exactly one refusal event expected, got {len(failed)}"
    assert failed[0]["step"] == failing_step
    assert failed[0]["step_name"] == CHECKPOINT_STEPS[failing_step - 1]
    assert "CheckpointPassed" not in rec.kinds()


# ============================================================ every refusal names its step


def test_every_refusal_identifies_the_failing_step_in_the_event_and_in_the_audit_record(tmp_path):
    """Requirement 2. A refusal that does not say WHICH check stopped it is an operational dead
    end, so it is asserted in BOTH surfaces: the observer stream and the durable security event
    (which is written after the rollback precisely so it survives)."""
    from test_phase3_step_order import FAULTS

    seen = 0
    for failing_step in range(1, 8):
        rec = Recorder()
        store, kernel, clock, effect, world, inputs, request = _observed_scenario(
            tmp_path, observer=rec, name=f"named{failing_step}")
        inputs = FAULTS[failing_step]({"clock": clock, "world": world, "kernel": kernel}, inputs)
        outcome = run_checkpoint(kernel, request, inputs)
        assert not outcome.authorized

        event = rec.of("CheckpointFailed")[0]
        assert event["step"] == failing_step and event["step_name"]
        assert event["reason"], "a refusal event with no reason"
        assert event["detail"], "a refusal event with no operator-readable detail"

        rows = store.conn.execute(
            "SELECT * FROM security_events WHERE tenant = ? ORDER BY id DESC LIMIT 1",
            (store.tenant,)).fetchall()
        assert rows, "the refusal was not durably recorded as a security event"
        assert str(failing_step) in rows[0]["payload_json"], (
            f"the durable record does not name the failing step: {rows[0]['payload_json'][:200]}"
        )
        assert_outcome_b(store, effect.key())
        seen += 1
    assert seen == 7, "the refusal ladder was not walked - this guard would prove nothing"


# ============================================================ brake state and version


def test_the_platform_and_tenant_brake_state_and_version_are_observable_at_step_7(tmp_path):
    """Requirement 3, in the form 16-brake.md point 7 requires: `brake_version` is per scope
    OWNER, so both owners must be observable, not just the composite token."""
    rec = Recorder()
    store, kernel, _clock, effect, _world, inputs, request = _observed_scenario(
        tmp_path, observer=rec, name="brakeobs")

    outcome = run_checkpoint(kernel, request, inputs)
    assert outcome.authorized

    step7 = rec.of("CheckpointStep")[-1]
    assert step7["step"] == 7 and step7["step_name"] == "brake_admission"
    assert step7["platform_brake_state"] == "RELEASED"
    assert step7["platform_brake_version"] == 0
    assert step7["tenant_active_brakes"] == []
    token = step7["brake_version"]
    assert "global:0" in token and "tenant:0" in token, f"composite token not observable: {token}"
    assert token == store.conn.execute(
        "SELECT brake_version FROM effect_grants WHERE tenant = ? AND commit_key = ?",
        (store.tenant, effect.key())).fetchone()[0], (
        "the observed brake token is not the one bound into the grant"
    )


def test_an_engaged_brake_is_observable_with_the_brake_that_denied_admission(tmp_path):
    """A refusal at step 7 must identify WHICH brake stopped it — the operator needs to know
    which one to consider releasing, and by whom it was engaged."""
    rec = Recorder()
    store, kernel, _clock, effect, _world, inputs, request = _observed_scenario(
        tmp_path, observer=rec, name="brakeon")
    status = kernel.brakes.engage(tenant=store.tenant, actor="owner:rasheed", actor_kind="HUMAN",
                                  reason="carrier portal returning garbage", action_class=None)

    outcome = run_checkpoint(kernel, request, inputs)
    assert not outcome.authorized and outcome.step == 7

    event = rec.of("CheckpointFailed")[0]
    assert event["reason"] == "BRAKE_ENGAGED"
    assert status.brake_id in event["detail"], "the refusal does not name the engaged brake"
    assert "owner:rasheed" in event["detail"], "the refusal does not name who engaged it"
    assert "carrier portal returning garbage" in event["detail"], "the reason is not observable"


def test_the_tenant_brake_version_moves_observably_after_an_engagement(tmp_path):
    """The version is the concurrency mechanism (16-brake.md point 19). If it were unobservable,
    a claim refused for BRAKE_CHANGED would be undiagnosable."""
    rec = Recorder()
    store, kernel, _clock, effect, _world, inputs, request = _observed_scenario(
        tmp_path, observer=rec, name="brakever")
    engaged = kernel.brakes.engage(tenant=store.tenant, actor="owner:rasheed", actor_kind="HUMAN",
                                   reason="incident", action_class="some_other_class")

    outcome = run_checkpoint(kernel, request, inputs)
    assert outcome.authorized, "an action-class brake on ANOTHER class must not deny this one"

    step7 = rec.of("CheckpointStep")[-1]
    assert step7["tenant_active_brakes"] == [engaged.brake_id], (
        f"an ACTIVE tenant brake was not observable at step 7: {step7}"
    )
    assert f"tenant:{engaged.brake_version}" in step7["brake_version"]


# ============================================================ claim CAS contention


def test_claim_cas_contention_is_observable(tmp_path):
    """Requirement 4. The second claimant of one grant does NOTHING, and the reason it did nothing
    must be visible — otherwise a silently-lost race looks identical to a silently-lost effect."""
    rec = Recorder()
    store, kernel, _clock, effect, _world, inputs, request = _observed_scenario(
        tmp_path, observer=rec, name="cascontend")

    outcome = run_checkpoint(kernel, request, inputs)
    assert outcome.authorized

    first = claim_grant_cas(kernel, outcome.handle, params_for(effect))
    second = claim_grant_cas(kernel, outcome.handle, params_for(effect))
    assert first.claimed and not second.claimed

    claimed = rec.of("GrantClaimed")
    assert len(claimed) == 1 and claimed[0]["grant_id"] == outcome.handle.grant_id
    assert claimed[0]["transition"] == ("GRANTED", "CLAIMED")

    refused = rec.of("ClaimRefused")
    assert len(refused) == 1, f"the losing claim was not observable: {rec.kinds()}"
    assert refused[0]["cause"] == "ALREADY_CLAIMED", (
        f"contention was observed under an uninformative cause: {refused[0]['cause']!r}"
    )
    assert refused[0]["grant_id"] == outcome.handle.grant_id
    assert_outcome_a(store, effect.key())


def test_a_brake_engaged_between_mint_and_claim_is_observable_as_brake_changed(tmp_path):
    """The contention that matters most operationally: the capability died between mint and claim
    because a human pulled the brake. `BRAKE_CHANGED`, not a generic failure."""
    rec = Recorder()
    store, kernel, _clock, effect, _world, inputs, request = _observed_scenario(
        tmp_path, observer=rec, name="brakerace")
    outcome = run_checkpoint(kernel, request, inputs)
    assert outcome.authorized

    kernel.brakes.engage(tenant=store.tenant, actor="owner:rasheed", actor_kind="HUMAN",
                         reason="stop everything", action_class=None)
    claim = claim_grant_cas(kernel, outcome.handle, params_for(effect))
    assert not claim.claimed

    causes = [e["cause"] for e in rec.of("ClaimRefused")]
    assert causes == ["BRAKE_CHANGED"], f"the brake race was not observable: {causes}"


def test_a_sev0_claim_refusal_is_observable_as_a_security_event(tmp_path):
    """A confused-deputy attempt is a Sev-0, and must reach BOTH the observer and the durable
    security log — an attack visible only in a returned value is an attack nobody reviews."""
    rec = Recorder()
    store, kernel, _clock, effect, _world, inputs, request = _observed_scenario(
        tmp_path, observer=rec, name="deputy")
    outcome = run_checkpoint(kernel, request, inputs)
    assert outcome.authorized

    wrong = replace(params_for(effect), target_resource_id="load:9999")
    claim = claim_grant_cas(kernel, outcome.handle, wrong)
    assert not claim.claimed and claim.cause == "CONFUSED_DEPUTY"

    sev0 = rec.of("Sev0")
    assert sev0 and sev0[0]["event_type"] == "ConfusedDeputyRefused"
    assert "mismatches" in sev0[0], "the Sev-0 event does not say WHAT was confused"
    rows = store.conn.execute(
        "SELECT event_type FROM security_events WHERE tenant = ?", (store.tenant,)).fetchall()
    assert "ConfusedDeputyRefused" in [r["event_type"] for r in rows]


# ============================================================ observer failure is contained


class Exploding:
    """An observer that fails on every event. The pathological case, not a rare one: an
    observability sink is exactly the sort of dependency that goes down during an incident."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, event: dict) -> None:
        self.calls += 1
        raise RuntimeError("the observability sink is down")


def _state_snapshot(store, commit_key):
    def rows(table):
        return [dict(r) for r in store.conn.execute(
            f"SELECT * FROM {table} WHERE tenant = ? AND commit_key = ? ORDER BY rowid",
            (store.tenant, commit_key)).fetchall()]
    return rows("effect_grants"), rows("checkpoint_witnesses")


def test_an_exploding_observer_does_not_change_a_passing_checkpoint(tmp_path):
    """Requirement 5, the passing side: identical outcome and identical rows, modulo the ids the
    kernel generates fresh per run."""
    silent_store, silent_kernel, _c, silent_effect, _w, silent_inputs, silent_request = (
        _observed_scenario(tmp_path, observer=Recorder(), name="silent.db"))
    silent = run_checkpoint(silent_kernel, silent_request, silent_inputs)
    assert silent.authorized

    boom = Exploding()
    store, kernel, _clock, effect, _world, inputs, request = _observed_scenario(
        tmp_path, observer=boom, name="boom.db")
    outcome = run_checkpoint(kernel, request, inputs)

    assert outcome.authorized, "an exploding observer refused a valid checkpoint"
    assert boom.calls >= 8, f"the observer was not actually exercised ({boom.calls} calls)"

    claim = claim_grant_cas(kernel, outcome.handle, params_for(effect))
    assert claim.claimed, "an exploding observer broke the claim CAS"
    assert_outcome_a(store, effect.key())
    claim_grant_cas(silent_kernel, silent.handle, params_for(silent_effect))

    grants, witnesses = _state_snapshot(store, effect.key())
    s_grants, s_witnesses = _state_snapshot(silent_store, silent_effect.key())
    assert len(grants) == len(s_grants) == 1 and len(witnesses) == len(s_witnesses) == 1
    volatile = {"grant_id", "checkpoint_id", "handle_digest", "claimed_at",
                "issued_at", "created_at", "expires_at", "id"}
    for key in set(s_grants[0]) - volatile:
        assert grants[0][key] == s_grants[0][key], f"grant column {key!r} diverged under failure"
    for key in set(s_witnesses[0]) - volatile:
        assert witnesses[0][key] == s_witnesses[0][key], f"witness column {key!r} diverged"


def test_an_exploding_observer_does_not_change_a_refused_checkpoint(tmp_path):
    """The refusal side: the rollback, the durable security event and the returned refusal must
    all be exactly what a silent observer would have produced."""
    boom = Exploding()
    store, kernel, _clock, effect, world, inputs, request = _observed_scenario(
        tmp_path, observer=boom, name="boomrefuse.db")
    world["projection"] = {"status": "IN_TRANSIT"}

    outcome = run_checkpoint(kernel, request, inputs)
    assert not outcome.authorized
    assert outcome.step == 3 and outcome.reason == "PROJECTED_STATE_STALE"
    assert boom.calls >= 3, f"the observer was not actually exercised ({boom.calls} calls)"
    assert_outcome_b(store, effect.key())
    rows = store.conn.execute(
        "SELECT event_type FROM security_events WHERE tenant = ?", (store.tenant,)).fetchall()
    assert "CheckpointRefused" in [r["event_type"] for r in rows], (
        "the durable refusal record was lost when the observer failed"
    )


def test_the_default_kernel_has_a_silent_observer_and_still_runs(tmp_path):
    """No observer at all is a supported configuration — observability is never load-bearing."""
    store = make_store(tmp_path, T_A, name="noobs.db")
    kernel, _clock = make_kernel(store)
    assert kernel._observer is not None, "the kernel must always have a callable observer slot"
    kernel.observe({"kind": "smoke"})   # must not raise
