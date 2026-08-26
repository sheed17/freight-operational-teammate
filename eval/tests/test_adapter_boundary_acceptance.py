"""AC-ADPT-* and the Effect / Effect-Grant outcome machine (M3 EF-3..EF-5) at the P4 effect
boundary. Built from the FROZEN contract (adapter-boundary-acceptance.md, ADR-004 §3.7/§7/§8,
03-external-effect-grant.machine.md), NOT from the implementation.

The negative oracle throughout is the adapter's own call log: a refusal that "does nothing" must
leave ZERO writes, and a verified success must leave EXACTLY ONE. `require_population` guards every
negative assertion so none passes vacuously.
"""

from __future__ import annotations

import copy
import json
import pickle
import sys
import threading
from datetime import timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for entry in (str(ROOT / "src"), str(ROOT / "eval")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from freight_recon import effect_boundary as eb  # noqa: E402
from freight_recon.checkpoint import (  # noqa: E402
    ClaimParams,
    expire_unclaimed,
    revoke_unclaimed,
)
from phase3_kit import make_kernel, make_store, params_for  # noqa: E402
from phase4_kit import (  # noqa: E402
    OP_ID,
    FakeTmsAdapter,
    T_A,
    T_B,
    mint_only,
)


def require_population(items, what):
    assert items, f"no {what} to assert over — this test would pass vacuously"
    return items


def security_events(store, event_type):
    return store.conn.execute(
        "SELECT * FROM security_events WHERE tenant = ? AND event_type = ?",
        (store.tenant, event_type)).fetchall()


def grant_state(store, grant_id):
    row = store.conn.execute(
        "SELECT state FROM effect_grants WHERE tenant = ? AND grant_id = ?",
        (store.tenant, grant_id)).fetchone()
    return row["state"] if row else None


# ================================================================ the happy path


def test_valid_claimed_grant_reaches_exactly_one_adapter_call_and_verifies(tmp_path):
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path)
    adapter = FakeTmsAdapter(approved=fp, mode="ok", readback="match")
    result = eb.execute_effect(kernel, handle, params_for(effect), adapter.operation())
    assert result.state == "VERIFIED"
    assert result.verification_outcome is eb.VerificationOutcome.VERIFIED_SUCCESS
    assert len(adapter.writes) == 1, f"expected exactly one adapter write, got {adapter.writes}"
    assert grant_state(store, handle.grant_id) == "VERIFIED"
    # EffectAttempted was recorded BEFORE the call (ADR-004 §3.7 step 6).
    require_population(security_events(store, "EffectAttempted"), "EffectAttempted records")


# ================================================================ claim-refusal cases (adapter does NOTHING)


def _assert_did_nothing(store, adapter, result, cause_contains=""):
    assert result.claimed is False, f"claim should have been refused, got {result}"
    assert adapter.writes == [], f"a refused claim touched the world: {adapter.writes}"
    if cause_contains:
        assert cause_contains in result.cause, f"cause {result.cause!r} lacks {cause_contains!r}"


def test_missing_grant_refuses_and_touches_nothing(tmp_path):
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path)
    adapter = FakeTmsAdapter(approved=fp)
    # A well-formed handle naming no ledger row: forge a fresh grant_id, keep the signature valid.
    from freight_recon.checkpoint import EffectGrantHandle
    forged = EffectGrantHandle(tenant=T_A, grant_id="no-such-grant",
                               token=handle.token, signature=kernel.sign(handle.token))
    result = eb.execute_effect(kernel, forged, params_for(effect), adapter.operation())
    _assert_did_nothing(store, adapter, result, "NO_SUCH_GRANT")
    require_population(security_events(store, "WellFormedHandleNamesNoRow"), "Sev-0 mint alarms")


def test_already_claimed_grant_yields_no_second_effect(tmp_path):
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path)
    first = FakeTmsAdapter(approved=fp)
    r1 = eb.execute_effect(kernel, handle, params_for(effect), first.operation())
    assert r1.state == "VERIFIED" and len(first.writes) == 1
    # A second execute on the same single-use grant claims nothing.
    second = FakeTmsAdapter(approved=fp)
    r2 = eb.execute_effect(kernel, handle, params_for(effect), second.operation())
    _assert_did_nothing(store, second, r2, "ALREADY_")


def test_expired_grant_refuses(tmp_path):
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path)
    expire_unclaimed(kernel, now=clock.now + timedelta(seconds=120))
    adapter = FakeTmsAdapter(approved=fp)
    result = eb.execute_effect(kernel, handle, params_for(effect), adapter.operation(),
                               now=clock.now + timedelta(seconds=121))
    _assert_did_nothing(store, adapter, result)


def test_revoked_grant_refuses(tmp_path):
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path)
    assert revoke_unclaimed(kernel, grant_id=handle.grant_id, cause="brake", actor="ops:sam")
    adapter = FakeTmsAdapter(approved=fp)
    result = eb.execute_effect(kernel, handle, params_for(effect), adapter.operation())
    _assert_did_nothing(store, adapter, result, "ALREADY_REVOKED")


def test_stale_witness_refuses(tmp_path):
    # A witness that is stale while the grant is still fresh: window < ttl isolates exactly this.
    store = make_store(tmp_path)
    kernel, clock = make_kernel(store, witness_window=timedelta(seconds=20),
                                grant_ttl=timedelta(seconds=90))
    from freight_recon.checkpoint import run_checkpoint
    from phase3_kit import green_scenario
    s2, k2, c2, effect, facts, versions, approval, world, inputs, request = green_scenario(tmp_path)
    # Rebuild on the shared store/kernel so windows apply.
    outcome = run_checkpoint(kernel, request, inputs)
    from freight_recon.checkpoint import CheckpointAuthorized
    assert isinstance(outcome, CheckpointAuthorized)
    from phase4_kit import approved_fingerprint
    fp = approved_fingerprint(store, effect.key())
    adapter = FakeTmsAdapter(approved=fp)
    result = eb.execute_effect(kernel, outcome.handle, params_for(effect), adapter.operation(),
                               now=clock.now + timedelta(seconds=40))  # >20 window, <90 ttl
    _assert_did_nothing(store, adapter, result, "STALE_WITNESS")


def test_brake_engaged_after_checkpoint_refuses_the_claim(tmp_path):
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path)
    kernel.brakes.engage(tenant=T_A, action_class=effect.action_class,
                         actor="ops:sam", actor_kind="HUMAN", reason="pause raises")
    adapter = FakeTmsAdapter(approved=fp)
    result = eb.execute_effect(kernel, handle, params_for(effect), adapter.operation())
    _assert_did_nothing(store, adapter, result, "BRAKE_CHANGED")


def test_policy_version_drift_after_checkpoint_refuses(tmp_path):
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path)
    # A new kernel over the SAME store with a bumped policy version — the CAS revalidates it. It
    # must share the minting kernel's HMAC key, or the handle would fail the signature filter first.
    from phase3_kit import default_registry
    kernel2, _ = make_kernel(store, registry=default_registry(policy_version="pv2"), clock=clock,
                             handle_key=kernel._handle_key)
    adapter = FakeTmsAdapter(approved=fp)
    result = eb.execute_effect(kernel2, handle, params_for(effect), adapter.operation())
    _assert_did_nothing(store, adapter, result, "POLICY_CHANGED")


def test_wrong_tenant_params_are_refused_before_any_claim(tmp_path):
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path)
    adapter = FakeTmsAdapter(approved=fp)
    wrong = ClaimParams(tenant=T_B, action_class=effect.action_class,
                        target_system=effect.target_system,
                        target_resource_id=effect.target_resource_id,
                        target_operation=effect.target_operation)
    with pytest.raises(eb.BoundaryError):
        eb.execute_effect(kernel, handle, wrong, adapter.operation())
    assert adapter.writes == []


def test_confused_deputy_params_refuse_and_sev0(tmp_path):
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path)
    adapter = FakeTmsAdapter(approved=fp)
    # Same tenant, DIFFERENT target resource than the grant was minted for.
    confused = ClaimParams(tenant=T_A, action_class=effect.action_class,
                          target_system=effect.target_system,
                          target_resource_id="load:9999",  # the grant is for load:4471
                          target_operation=effect.target_operation)
    result = eb.execute_effect(kernel, handle, confused, adapter.operation())
    _assert_did_nothing(store, adapter, result, "CONFUSED_DEPUTY")
    require_population(security_events(store, "ConfusedDeputyRefused"), "confused-deputy alarms")


# ================================================================ the outcome machine (EF-3..EF-5)


def test_ef3f_preflight_rejection_is_failed_with_proof(tmp_path):
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path)
    adapter = FakeTmsAdapter(approved=fp, mode="preflight_reject")
    result = eb.execute_effect(kernel, handle, params_for(effect), adapter.operation())
    assert result.state == "FAILED"
    assert result.failure_proof, "FAILED without proof is illegal (GR-5)"
    assert result.touched_world is False
    assert grant_state(store, handle.grant_id) == "FAILED"
    assert adapter.writes == [], "a pre-flight rejection did not touch the world"


def test_ef3u_ambiguous_attempt_is_unknown_never_failed(tmp_path):
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path)
    adapter = FakeTmsAdapter(approved=fp, mode="unknown")
    result = eb.execute_effect(kernel, handle, params_for(effect), adapter.operation())
    assert result.state == "UNKNOWN_OUTCOME", "an ambiguous attempt must NOT become FAILED"
    assert result.unknown_reason is eb.UnknownReason.UNKNOWN_OUTCOME
    assert result.exposure, "the human is escalated WITH the dollar exposure (ADR-004 §3.9)"
    assert grant_state(store, handle.grant_id) == "UNKNOWN_OUTCOME"


def test_f4_generic_post_attempt_exception_leaves_unknown_never_claimed(tmp_path):
    """F4: a generic, unclassified exception from `perform` AFTER the attempt was recorded must move
    the grant OUT of CLAIMED into UNKNOWN_OUTCOME. A grant left CLAIMED behind an EffectAttempted is
    the exact defect — it is a claimed-or-later state, so the detective sweep would never reconcile
    the possibly-committed effect. The exception still propagates (it is unexpected, not swallowed)."""
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path)
    adapter = FakeTmsAdapter(approved=fp, mode="raise_generic")
    with pytest.raises(RuntimeError):
        eb.execute_effect(kernel, handle, params_for(effect), adapter.operation())
    assert grant_state(store, handle.grant_id) == "UNKNOWN_OUTCOME", (
        "a generic post-attempt exception must not leave the grant CLAIMED"
    )
    # The attempt was durably recorded BEFORE the call, so the ambiguity is not lost.
    require_population(security_events(store, "EffectAttempted"), "EffectAttempted record")
    # The DURABLE outcome envelope (what the detective sweep and the escalated human read) records
    # the reason as a post-attempt adapter exception, not a normal ambiguous outcome.
    row = store.conn.execute(
        "SELECT payload_json, unknown_reason FROM effect_grants WHERE tenant = ? AND grant_id = ?",
        (store.tenant, handle.grant_id)).fetchone()
    assert row["unknown_reason"] == eb.UnknownReason.UNKNOWN_OUTCOME.value
    unknown_entries = require_population(
        [e for e in json.loads(row["payload_json"]).get("outcome_log", [])
         if e.get("state") == "UNKNOWN_OUTCOME"],
        "UNKNOWN_OUTCOME outcome-log entry")
    assert any("post-attempt adapter exception" in str(e.get("unknown_detail", ""))
               for e in unknown_entries), "the envelope must name the post-attempt exception cause"


def test_f4_generic_exception_is_never_laundered_into_failed(tmp_path):
    """AC-ADPT-015 / GR-5: only AdapterPreflightRejected (with proof) reaches FAILED. A generic
    exception carries NO proof of non-occurrence, so it must NEVER become FAILED."""
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path)
    adapter = FakeTmsAdapter(approved=fp, mode="raise_generic")
    with pytest.raises(RuntimeError):
        eb.execute_effect(kernel, handle, params_for(effect), adapter.operation())
    assert grant_state(store, handle.grant_id) != "FAILED"
    assert grant_state(store, handle.grant_id) == "UNKNOWN_OUTCOME"


def test_f4_unknown_after_generic_exception_is_not_an_orphan_and_needs_a_human(tmp_path):
    """The UNKNOWN_OUTCOME left by a generic failure has a real claimed grant, so the detective sweep
    does NOT misfire it as an orphan; and, like any UNKNOWN_OUTCOME, it never auto-resolves or
    retries — only a human (or later deterministic proof) moves it (EF-5, GR-6)."""
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path)
    adapter = FakeTmsAdapter(approved=fp, mode="raise_generic")
    with pytest.raises(RuntimeError):
        eb.execute_effect(kernel, handle, params_for(effect), adapter.operation())
    # There IS an EffectAttempted to reconcile, and its grant is claimed-or-later => NOT an orphan.
    require_population(security_events(store, "EffectAttempted"), "EffectAttempted record")
    assert eb.detect_orphan_effect_attempts(kernel) == [], (
        "a genuine UNKNOWN_OUTCOME is not an orphan — it has a real claimed grant"
    )
    # It resolves only under a named human decision.
    assert eb.resolve_unknown_outcome(kernel, handle.grant_id, to="FAILED",
                                      decision_ref="ticket-77", established_by="owner:rasheed")
    assert grant_state(store, handle.grant_id) == "FAILED"


def test_ef4_verified_success_on_healthy_matching_readback(tmp_path):
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path)
    adapter = FakeTmsAdapter(approved=fp, readback="match")
    result = eb.execute_effect(kernel, handle, params_for(effect), adapter.operation())
    assert result.state == "VERIFIED"
    assert ("readback", effect.target_resource_id) in adapter.calls


def test_ef4c_conflicting_readback_is_unknown_not_failed(tmp_path):
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path)
    adapter = FakeTmsAdapter(approved=fp, readback="conflict")
    result = eb.execute_effect(kernel, handle, params_for(effect), adapter.operation())
    assert result.state == "UNKNOWN_OUTCOME"
    assert result.unknown_reason is eb.UnknownReason.OBSERVATION_CONFLICTING
    assert grant_state(store, handle.grant_id) == "UNKNOWN_OUTCOME"


def test_ef4u_blind_readback_is_unavailable_never_verified_failure(tmp_path):
    """AC-ADPT-012: a logged-out page that 'loads fine' is OBSERVATION_UNAVAILABLE, never a
    verified failure. The effect may have happened."""
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path)
    adapter = FakeTmsAdapter(approved=fp, readback="blind")
    result = eb.execute_effect(kernel, handle, params_for(effect), adapter.operation())
    assert result.state == "UNKNOWN_OUTCOME"
    assert result.unknown_reason is eb.UnknownReason.OBSERVATION_UNAVAILABLE
    assert result.verification_outcome is eb.VerificationOutcome.OBSERVATION_UNAVAILABLE


def test_ef5_unknown_resolves_only_by_human_or_proof(tmp_path):
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path)
    adapter = FakeTmsAdapter(approved=fp, mode="unknown")
    eb.execute_effect(kernel, handle, params_for(effect), adapter.operation())
    # No decision reference => refused.
    with pytest.raises(eb.BoundaryError):
        eb.resolve_unknown_outcome(kernel, handle.grant_id, to="VERIFIED",
                                   decision_ref="", established_by="owner:rasheed")
    # A human establishes reality.
    assert eb.resolve_unknown_outcome(kernel, handle.grant_id, to="VERIFIED",
                                      decision_ref="ticket-42", established_by="owner:rasheed")
    assert grant_state(store, handle.grant_id) == "VERIFIED"


def test_ef5x_no_timer_moves_unknown(tmp_path):
    """UNKNOWN_OUTCOME never auto-resolves and is never retried (EF-5x illegal, GR-6)."""
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path)
    adapter = FakeTmsAdapter(approved=fp, mode="unknown")
    eb.execute_effect(kernel, handle, params_for(effect), adapter.operation())
    # An expiry sweep must NOT touch UNKNOWN_OUTCOME (only GRANTED expires).
    expire_unclaimed(kernel, now=clock.now + timedelta(hours=48))
    assert grant_state(store, handle.grant_id) == "UNKNOWN_OUTCOME"
    # And a re-execute cannot re-claim it (single-use, terminal-for-the-capability).
    retry = FakeTmsAdapter(approved=fp)
    r = eb.execute_effect(kernel, handle, params_for(effect), retry.operation())
    assert r.claimed is False and retry.writes == []


def test_unsafe_retry_after_ambiguity_is_impossible(tmp_path):
    """A retry NEVER re-uses a grant. The same handle after UNKNOWN_OUTCOME claims nothing."""
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path)
    a1 = FakeTmsAdapter(approved=fp, mode="unknown")
    eb.execute_effect(kernel, handle, params_for(effect), a1.operation())
    a2 = FakeTmsAdapter(approved=fp, mode="ok")
    r2 = eb.execute_effect(kernel, handle, params_for(effect), a2.operation())
    assert r2.claimed is False, "UNKNOWN_OUTCOME was retried as though nothing happened"
    assert a2.writes == []


# ================================================================ the execution capability


def test_forged_capability_is_refused(tmp_path):
    forged = object.__new__(eb.ExecutionCapability)
    with pytest.raises(eb.OrphanEffectDetected):
        eb.consume_capability(forged, op_id=OP_ID)


def test_capability_cannot_be_pickled_or_copied(tmp_path):
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path)
    cap = eb._mint_capability(tenant=T_A, grant_id="g", commit_key="c", op_id=OP_ID)
    with pytest.raises(eb.BoundaryError):
        pickle.dumps(cap)
    with pytest.raises(eb.BoundaryError):
        copy.copy(cap)
    with pytest.raises(eb.BoundaryError):
        copy.deepcopy(cap)


def test_capability_is_single_use(tmp_path):
    cap = eb._mint_capability(tenant=T_A, grant_id="g", commit_key="c", op_id=OP_ID)
    eb.consume_capability(cap, op_id=OP_ID)
    with pytest.raises(eb.OrphanEffectDetected):
        eb.consume_capability(cap, op_id=OP_ID)  # a second use is a replay


def test_capability_is_scoped_to_its_operation(tmp_path):
    cap = eb._mint_capability(tenant=T_A, grant_id="g", commit_key="c", op_id=OP_ID)
    with pytest.raises(eb.OrphanEffectDetected):
        eb.consume_capability(cap, op_id="A4.other_operation")


def test_direct_adapter_invocation_without_capability_is_orphan(tmp_path):
    """Calling an adapter's effect function directly (no boundary, no grant) fails closed."""
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path)
    adapter = FakeTmsAdapter(approved=fp)
    with pytest.raises(eb.OrphanEffectDetected):
        adapter.perform(None, params_for(effect))  # type: ignore[arg-type]
    assert adapter.writes == []


# ================================================================ orphan detection (ADR-004 §4.5)


def test_orphan_detector_is_not_vacuous_and_auto_engages_the_brake(tmp_path):
    """Inject a synthetic EffectAttempted with no grant. The detector must find it, record the
    Sev-0, and engage the brake. The happy path never produces one, so this injection is the only
    honest proof the detector works."""
    store = make_store(tmp_path)
    kernel, clock = make_kernel(store)
    # Synthetic orphan: an EffectAttempted whose grant does not exist.
    eb.record_effect_attempted(kernel, grant_id="ghost-grant",
                               params=ClaimParams(tenant=T_A, action_class="raise_invoice",
                                                   target_system="tms:truckingoffice",
                                                   target_resource_id="load:4471",
                                                   target_operation="create_invoice"))
    orphans = eb.detect_orphan_effect_attempts(kernel)
    assert [o.grant_id for o in orphans] == ["ghost-grant"], "the detector missed the orphan"
    require_population(security_events(store, "OrphanAdapterInvocation"), "Sev-0 orphan records")
    assert kernel.brakes.admission_denied(tenant=T_A, action_class="raise_invoice") is not None, \
        "an orphan effect must auto-engage the brake"


def test_orphan_detector_passes_a_healthy_ledger(tmp_path):
    """A verified effect leaves an EffectAttempted WITH a claimed-or-later grant — not an orphan."""
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path)
    adapter = FakeTmsAdapter(approved=fp)
    eb.execute_effect(kernel, handle, params_for(effect), adapter.operation())
    orphans = eb.detect_orphan_effect_attempts(kernel)
    assert orphans == [], f"a healthy verified effect was misread as an orphan: {orphans}"


def test_detective_sweep_finds_orphans_brakes_and_surfaces_unknowns(tmp_path):
    """The authorized detective loop's per-cycle reconciliation (`run_detective_sweep`) IS the
    runtime home of the orphan detector. In one pass it must: find an injected orphan, record the
    Sev-0 and auto-engage the brake, AND surface a genuine UNKNOWN_OUTCOME grant awaiting a human."""
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path)
    # A real UNKNOWN_OUTCOME enters the human-owned queue (a generic mid-attempt failure — F4).
    unknown_adapter = FakeTmsAdapter(approved=fp, mode="raise_generic")
    with pytest.raises(RuntimeError):
        eb.execute_effect(kernel, handle, params_for(effect), unknown_adapter.operation())
    # Inject a synthetic ORPHAN: an EffectAttempted whose grant does not exist.
    eb.record_effect_attempted(
        kernel, grant_id="orphan-ghost",
        params=ClaimParams(tenant=store.tenant, action_class="raise_invoice",
                           target_system="tms", target_resource_id="load:99",
                           target_operation="create_invoice"))

    result = eb.run_detective_sweep(kernel)

    assert result.tenant == store.tenant
    assert any(o.grant_id == "orphan-ghost" for o in result.orphans), "the sweep missed the orphan"
    require_population(security_events(store, "OrphanAdapterInvocation"), "Sev-0 orphan records")
    assert kernel.brakes.admission_denied(tenant=store.tenant, action_class="raise_invoice") is not None, \
        "the sweep must auto-engage the brake for an orphan's action class"
    assert handle.grant_id in result.unknown_outcomes, (
        "the genuine UNKNOWN_OUTCOME grant must be surfaced for human resolution, not lost"
    )


def test_detective_sweep_is_clean_on_a_healthy_ledger(tmp_path):
    """No orphans, no unknowns: a verified effect leaves nothing for the sweep to escalate. Guards
    against a sweep that reports phantom work (which would train operators to ignore it)."""
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path)
    adapter = FakeTmsAdapter(approved=fp)  # ok + matching readback => VERIFIED
    eb.execute_effect(kernel, handle, params_for(effect), adapter.operation())
    result = eb.run_detective_sweep(kernel)
    assert result.orphans == ()
    assert result.unknown_outcomes == (), "a VERIFIED effect is not an unknown outcome"


# ================================================================ AC-ADPT structural assertions


def test_ac_adpt_000_registry_declares_class_and_mode_for_every_op(tmp_path):
    ops = {
        "A4.create_invoice": eb.AdapterOperation(
            op_id="A4.create_invoice", adapter="A4",
            operation_class=eb.OperationClass.CONSEQUENTIAL_EFFECT,
            verification_mode=eb.VerificationMode.READBACK_VERIFIABLE,
            perform=lambda cap, p: eb.AttemptResult()),
        "A4.read_load": eb.AdapterOperation(
            op_id="A4.read_load", adapter="A4",
            operation_class=eb.OperationClass.CONSEQUENTIAL_FRESHNESS_READ,
            verification_mode=eb.VerificationMode.READBACK_VERIFIABLE),
    }
    reg = eb.AdapterOperationRegistry(ops)
    require_population(reg.op_ids(), "registered operations")
    for op_id in reg.op_ids():
        op = reg.get(op_id)
        assert isinstance(op.operation_class, eb.OperationClass)
        assert isinstance(op.verification_mode, eb.VerificationMode)


def test_ac_adpt_002_a_read_never_routes_through_the_effect_boundary(tmp_path):
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path)
    read_op = eb.AdapterOperation(
        op_id="A4.read_load", adapter="A4",
        operation_class=eb.OperationClass.CONSEQUENTIAL_FRESHNESS_READ,
        verification_mode=eb.VerificationMode.READBACK_VERIFIABLE)
    with pytest.raises(eb.BoundaryError):
        eb.execute_effect(kernel, handle, params_for(effect), read_op)


def test_ac_adpt_007_unverifiable_op_cannot_be_autonomous(tmp_path):
    op = eb.AdapterOperation(
        op_id="A3.transcribe_call", adapter="A3",
        operation_class=eb.OperationClass.CONSEQUENTIAL_EFFECT,
        verification_mode=eb.VerificationMode.UNVERIFIABLE,
        perform=lambda cap, p: eb.AttemptResult())
    with pytest.raises(eb.BoundaryError):
        eb.AdapterOperationRegistry({op.op_id: op},
                                    autonomous_op_ids=frozenset({"A3.transcribe_call"}))


def test_ac_adpt_015_adapter_never_converts_unknown_to_failed(tmp_path):
    """The adapter returns structured evidence; the machine decides. There is no adapter path that
    reaches FAILED — only a proven pre-flight non-occurrence does, and that is the boundary's call."""
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path)
    # Ambiguous outcome -> UNKNOWN, never FAILED.
    adapter = FakeTmsAdapter(approved=fp, mode="unknown")
    r = eb.execute_effect(kernel, handle, params_for(effect), adapter.operation())
    assert r.state == "UNKNOWN_OUTCOME" and r.state != "FAILED"


def test_ac_adpt_016_cross_tenant_is_contained_and_globally_braked(tmp_path):
    """Another tenant's grant, presented under this boundary, is refused before any effect, and the
    orphan/cross-tenant path escalates. Here we prove containment: T_B cannot claim on a T_A boundary."""
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path, tenant=T_A)
    # A boundary bound to T_B cannot even be handed T_A params without the tenant guard firing.
    store_b = make_store(tmp_path, tenant=T_B, name="beta.db")
    kernel_b, _ = make_kernel(store_b)
    adapter = FakeTmsAdapter(approved=fp)
    with pytest.raises(eb.BoundaryError):
        eb.execute_effect(kernel_b, handle, params_for(effect), adapter.operation())
    assert adapter.writes == []
    # Contained AND escalated: CrossTenantAccessAttempted recorded + GLOBAL brake engaged.
    require_population(security_events(store_b, "CrossTenantAccessAttempted"), "cross-tenant alarms")
    assert kernel_b.brakes.platform_status().state == "ACTIVE", \
        "a cross-tenant effect attempt must engage the GLOBAL brake"


# ================================================================ observability & rollback resilience


def test_observer_failure_never_alters_control_flow(tmp_path):
    def boom(event):
        raise RuntimeError("observer down")

    store = make_store(tmp_path)
    kernel, clock = make_kernel(store, observer=boom)
    from freight_recon.checkpoint import CheckpointAuthorized, run_checkpoint
    from phase3_kit import green_scenario
    s2, k2, c2, effect, facts, versions, approval, world, inputs, request = green_scenario(tmp_path)
    outcome = run_checkpoint(kernel, request, inputs)
    assert isinstance(outcome, CheckpointAuthorized)
    from phase4_kit import approved_fingerprint
    fp = approved_fingerprint(store, effect.key())
    adapter = FakeTmsAdapter(approved=fp)
    result = eb.execute_effect(kernel, outcome.handle, params_for(effect), adapter.operation())
    assert result.state == "VERIFIED", "a raising observer changed the outcome"


def test_illegal_transition_rolls_back_with_no_partial_state(tmp_path):
    store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path)
    # Transitioning a GRANTED (unclaimed) grant straight to ATTEMPTED is illegal — no CLAIMED row.
    with pytest.raises(eb.BoundaryError):
        eb._transition_from_claimed(kernel, handle.grant_id, to="ATTEMPTED", now=clock.now)
    assert grant_state(store, handle.grant_id) == "GRANTED", "an illegal transition mutated state"


# ================================================================ concurrency: one winner


# The race is run REPEATEDLY, not once. The defect this guards — two threads sharing ONE SQLite
# connection, so `BEGIN IMMEDIATE` opened the CONNECTION's transaction rather than the caller's —
# lost the race for roughly one attempt in forty. A single-shot race is a guard that almost never
# fires (CLAUDE.md §6), which is exactly how it reached CI as an intermittent red rather than being
# caught here. At ~25ms per race this costs a few seconds and it can actually fail.
CONCURRENT_RACES = 120


def test_concurrent_execute_yields_exactly_one_effect(tmp_path):
    """Two threads race the same grant through the boundary. The claim CAS is the sole
    serialization point: exactly one touches the world — never two, and never ZERO.

    ADR-004 §8: *"two concurrent pipelines, same commit key ⇒ exactly ONE claims"*. Zero writers is
    not a pass merely because two writers were prevented — a valid fresh grant with two live
    contenders owes the broker its one invoice, and a winner that dies between the claim CAS and the
    adapter leaves a CLAIMED grant with nothing behind it. The loser may take a clean claim refusal
    or a serialization error; what it may never take is a trip to the outside world.
    """
    for race in range(CONCURRENT_RACES):
        store, kernel, clock, effect, handle, fp, request = mint_only(tmp_path / f"race{race}")
        adapters = [FakeTmsAdapter(approved=fp), FakeTmsAdapter(approved=fp)]
        results: dict[int, str] = {}
        barrier = threading.Barrier(2)

        def run(index, a):
            barrier.wait()
            try:
                outcome = eb.execute_effect(kernel, handle, params_for(effect), a.operation())
                results[index] = (f"returned claimed={outcome.claimed} state={outcome.state} "
                                  f"cause={outcome.cause}")
            except BaseException as exc:  # noqa: BLE001 — SQLite may serialize with a lock error
                results[index] = f"raised {type(exc).__name__}: {exc}"

        threads = [threading.Thread(target=run, args=(i, a)) for i, a in enumerate(adapters)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # Report what BOTH racers did. The assertion used to print only the total, so the CI red
        # read "saw 0" and said nothing about which thread died or why; the whole diagnosis had to
        # be rebuilt from scratch. A concurrency assertion that cannot name the losing thread's
        # exception is a guard that reports the symptom and withholds the evidence.
        story = " | ".join(f"thread {i}: {len(a.writes)} write(s), {results.get(i, 'no result')}"
                           for i, a in enumerate(adapters))
        total_writes = sum(len(a.writes) for a in adapters)
        assert total_writes == 1, (
            f"exactly one thread must touch the world, saw {total_writes} "
            f"(race {race + 1} of {CONCURRENT_RACES}) — {story}")
        store.close()
