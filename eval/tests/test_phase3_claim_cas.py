"""Phase 3 — the claim CAS: GRANTED -> CLAIMED, atomically, once, revalidating everything.

Machine M3 EF-2/EF-2f/EF-2r/EF-2x and ADR-004 §3.3–§3.7, executed adversarially: replayed
handles, forged handles, confused deputies, racing claimers on separate connections, brakes and
policy changes between mint and claim, expiry, and the legacy rows that must never be claimable.
"""

from __future__ import annotations

import hashlib
import sys
import threading
from datetime import timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from phase3_kit import (  # noqa: E402
    Clock,
    T_A,
    T_B,
    assert_no_partial_state,
    assert_outcome_a,
    default_registry,
    green_scenario,
    make_kernel,
    make_store,
    params_for,
)

from freight_recon.brake import BrakeStore  # noqa: E402
from freight_recon.checkpoint import (  # noqa: E402
    GRANTED_TO_CLAIMED,
    ClaimParams,
    EffectGrantHandle,
    GateRegistry,
    claim_grant_cas,
    expire_unclaimed,
    revoke_unclaimed,
    run_checkpoint,
)


def _authorized(tmp_path, **kwargs):
    store, kernel, clock, effect, facts, versions, approval, world, inputs, request = (
        green_scenario(tmp_path, **kwargs))
    outcome = run_checkpoint(kernel, request, inputs)
    assert outcome.authorized, f"green scenario refused: {outcome}"
    return store, kernel, clock, effect, outcome


def test_the_cas_transition_is_named_and_single_use(tmp_path):
    assert GRANTED_TO_CLAIMED == ("GRANTED", "CLAIMED")
    store, kernel, clock, effect, outcome = _authorized(tmp_path)
    first = claim_grant_cas(kernel, outcome.handle, params_for(effect))
    assert first.claimed is True and first.transition == GRANTED_TO_CLAIMED
    assert_outcome_a(store, effect.key())
    second = claim_grant_cas(kernel, outcome.handle, params_for(effect))
    assert second.claimed is False and second.cause == "ALREADY_CLAIMED"
    rows = store.conn.execute(
        "SELECT COUNT(*) FROM effect_grants WHERE state = 'CLAIMED'").fetchone()[0]
    assert rows == 1, "a replayed claim produced a second CLAIMED row"
    store.close()


def test_a_forged_handle_with_a_bad_signature_is_refused_without_a_ledger_hit(tmp_path):
    store, kernel, clock, effect, outcome = _authorized(tmp_path)
    forged = EffectGrantHandle(
        tenant=T_A, grant_id=outcome.handle.grant_id, token=outcome.handle.token,
        signature="0" * 64)
    result = claim_grant_cas(kernel, forged, params_for(effect))
    assert result.claimed is False and result.cause == "INVALID_HANDLE_SIGNATURE"
    grant = store.conn.execute("SELECT state FROM effect_grants WHERE grant_id = ?",
                               (outcome.handle.grant_id,)).fetchone()
    assert grant["state"] == "GRANTED"
    store.close()


def test_a_well_formed_handle_naming_no_row_is_a_sev0(tmp_path):
    """ADR-004 §3.7 step 2: a correctly-signed handle naming no ledger row means someone is
    minting handles. Refused AND recorded as a security event."""
    store, kernel, clock, effect, outcome = _authorized(tmp_path)
    ghost_token = "ab" * 32
    ghost = EffectGrantHandle(
        tenant=T_A, grant_id="grant-that-never-existed", token=ghost_token,
        signature=kernel.sign(ghost_token))
    result = claim_grant_cas(kernel, ghost, params_for(effect))
    assert result.claimed is False and result.cause == "NO_SUCH_GRANT"
    events = [e["event_type"] for e in store.security_events()]
    assert "WellFormedHandleNamesNoRow" in events
    store.close()


def test_a_swapped_token_on_a_real_grant_is_a_digest_mismatch_sev0(tmp_path):
    store, kernel, clock, effect, outcome = _authorized(tmp_path)
    other_token = "cd" * 32
    swapped = EffectGrantHandle(
        tenant=T_A, grant_id=outcome.handle.grant_id, token=other_token,
        signature=kernel.sign(other_token))
    result = claim_grant_cas(kernel, swapped, params_for(effect))
    assert result.claimed is False and result.cause == "HANDLE_DIGEST_MISMATCH"
    assert "HandleDigestMismatch" in [e["event_type"] for e in store.security_events()]
    store.close()


def test_the_confused_deputy_is_refused_with_a_sev0_naming_the_mismatch(tmp_path):
    """A valid grant for load:4471 presented with parameters for load:4472: refused, Sev-0,
    nothing claimed (ADR-004 §3.7 step 4 — the attack the confusion check exists for)."""
    store, kernel, clock, effect, outcome = _authorized(tmp_path)
    wrong = ClaimParams(
        tenant=T_A, action_class="raise_invoice", target_system="tms:truckingoffice",
        target_resource_id="load:4472", target_operation="create_invoice")
    result = claim_grant_cas(kernel, outcome.handle, wrong)
    assert result.claimed is False and result.cause == "CONFUSED_DEPUTY"
    grant = store.conn.execute("SELECT state FROM effect_grants WHERE grant_id = ?",
                               (outcome.handle.grant_id,)).fetchone()
    assert grant["state"] == "GRANTED", "a confused-deputy attempt must not consume the grant"
    sev0 = [e for e in store.security_events() if e["event_type"] == "ConfusedDeputyRefused"]
    assert len(sev0) == 1
    assert sev0[0]["payload"]["mismatches"]["target_resource_id"]["caller"] == "load:4472"
    store.close()


def test_an_expired_grant_cannot_be_claimed_and_lazy_expiry_records_it(tmp_path):
    store, kernel, clock, effect, outcome = _authorized(tmp_path)
    clock.advance(seconds=61)  # both witness window and grant TTL elapse
    result = claim_grant_cas(kernel, outcome.handle, params_for(effect))
    assert result.claimed is False
    assert result.cause in ("EXPIRED", "STALE_WITNESS")  # witness staleness is checked first
    expired = expire_unclaimed(kernel)
    assert expired == 1
    grant = store.conn.execute("SELECT state FROM effect_grants WHERE grant_id = ?",
                               (outcome.handle.grant_id,)).fetchone()
    assert grant["state"] == "EXPIRED_UNCLAIMED"
    store.close()


def test_expiry_frees_the_commit_key_for_a_safe_re_checkpoint(tmp_path):
    """The crash-after-commit matrix case: witness+grant exist, the process dies before the
    claim, the grant expires unclaimed => NOTHING HAPPENED, and a re-checkpoint of the same
    logical effect mints fresh (ADR-004 §7)."""
    store, kernel, clock, effect, facts, versions, approval, world, inputs, request = (
        green_scenario(tmp_path))
    first = run_checkpoint(kernel, request, inputs)
    assert first.authorized
    clock.advance(seconds=61)
    assert expire_unclaimed(kernel) == 1
    # The approval is still GRANTED (it survives a provably-failed attempt) but it has TTL 1h:
    # still valid. The re-checkpoint re-runs all seven checks and mints a NEW grant.
    second = run_checkpoint(kernel, request, inputs)
    assert second.authorized, f"re-checkpoint after expiry refused: {second}"
    assert second.handle.grant_id != first.handle.grant_id
    claim = claim_grant_cas(kernel, second.handle, params_for(effect))
    assert claim.claimed is True
    states = [r["state"] for r in store.conn.execute(
        "SELECT state FROM effect_grants WHERE commit_key = ? ORDER BY created_at",
        (effect.key(),)).fetchall()]
    assert sorted(states) == ["CLAIMED", "EXPIRED_UNCLAIMED"]
    store.close()


def test_expiry_never_touches_a_claimed_row(tmp_path):
    store, kernel, clock, effect, outcome = _authorized(tmp_path)
    assert claim_grant_cas(kernel, outcome.handle, params_for(effect)).claimed
    clock.advance(seconds=3600)
    assert expire_unclaimed(kernel) == 0
    grant = store.conn.execute("SELECT state FROM effect_grants WHERE grant_id = ?",
                               (outcome.handle.grant_id,)).fetchone()
    assert grant["state"] == "CLAIMED", (
        "expiry reached a CLAIMED row: 'the world may have changed' was converted into "
        "'pretend it did not'")
    store.close()


def test_revocation_kills_an_unclaimed_grant_and_stays_distinct_from_expiry(tmp_path):
    store, kernel, clock, effect, outcome = _authorized(tmp_path)
    assert revoke_unclaimed(kernel, grant_id=outcome.handle.grant_id,
                            cause="brake engaged", actor="owner:rasheed") is True
    grant = store.conn.execute("SELECT state FROM effect_grants WHERE grant_id = ?",
                               (outcome.handle.grant_id,)).fetchone()
    assert grant["state"] == "REVOKED"
    result = claim_grant_cas(kernel, outcome.handle, params_for(effect))
    assert result.claimed is False and result.cause == "ALREADY_REVOKED"
    store.close()


def test_revoking_a_claimed_grant_does_nothing(tmp_path):
    store, kernel, clock, effect, outcome = _authorized(tmp_path)
    assert claim_grant_cas(kernel, outcome.handle, params_for(effect)).claimed
    assert revoke_unclaimed(kernel, grant_id=outcome.handle.grant_id,
                            cause="too late", actor="owner:rasheed") is False
    grant = store.conn.execute("SELECT state FROM effect_grants WHERE grant_id = ?",
                               (outcome.handle.grant_id,)).fetchone()
    assert grant["state"] == "CLAIMED", "revocation reached a claimed grant (ADR-004 §3.6)"
    store.close()


def test_brake_between_mint_and_claim_makes_the_cas_match_zero_rows(tmp_path):
    store, kernel, clock, effect, outcome = _authorized(tmp_path)
    BrakeStore(store.conn).engage(
        tenant=T_A, actor="detector:orphan-effects", actor_kind="DETECTOR",
        reason="orphan EffectAttempted observed")
    result = claim_grant_cas(kernel, outcome.handle, params_for(effect))
    assert result.claimed is False and result.cause == "BRAKE_CHANGED"
    grant = store.conn.execute("SELECT state FROM effect_grants WHERE grant_id = ?",
                               (outcome.handle.grant_id,)).fetchone()
    assert grant["state"] == "GRANTED"
    store.close()


def test_platform_brake_between_mint_and_claim_also_refuses(tmp_path):
    store, kernel, clock, effect, outcome = _authorized(tmp_path)
    BrakeStore(store.conn).engage_platform(
        actor="detector:tenant-isolation", actor_kind="DETECTOR",
        reason="cross-tenant signal — global stop")
    result = claim_grant_cas(kernel, outcome.handle, params_for(effect))
    assert result.claimed is False and result.cause == "BRAKE_CHANGED"
    store.close()


def test_brake_engage_and_release_both_invalidate_in_flight_grants(tmp_path):
    """ADR-011 §6: RELEASE MUST NOT REACTIVATE STALE GRANTS. Engage bumps the version; release
    bumps it again — a grant minted before either event stays dead after both."""
    store, kernel, clock, effect, outcome = _authorized(tmp_path)
    brakes = BrakeStore(store.conn)
    status = brakes.engage(tenant=T_A, actor="owner:rasheed", actor_kind="HUMAN", reason="incident")
    brakes.release(tenant=T_A, brake_id=status.brake_id, actor="owner:rasheed",
                   actor_kind="HUMAN", decision_ref="decision:incident-42-closed")
    result = claim_grant_cas(kernel, outcome.handle, params_for(effect))
    assert result.claimed is False and result.cause == "BRAKE_CHANGED", (
        "a release must not resurrect a grant minted before the incident")
    store.close()


def test_policy_version_change_between_mint_and_claim_refuses(tmp_path):
    store, kernel, clock, effect, outcome = _authorized(tmp_path)
    kernel.gates = default_registry(policy_version="pv2")  # the owner tightened policy
    result = claim_grant_cas(kernel, outcome.handle, params_for(effect))
    assert result.claimed is False and result.cause == "POLICY_CHANGED"
    grant = store.conn.execute("SELECT state FROM effect_grants WHERE grant_id = ?",
                               (outcome.handle.grant_id,)).fetchone()
    assert grant["state"] == "GRANTED"
    store.close()


def test_a_legacy_phase2_reservation_is_not_a_claimable_capability(tmp_path):
    """The P2 path writes GRANTED rows with NO checkpoint binding. Under the two-key rule they
    are reservations, not capabilities: a handle over one must refuse with GrantWithoutWitness."""
    store, kernel, clock, effect, outcome = _authorized(tmp_path)
    assert store.claim_operation_commit(
        commit_key="legacy-ck-1", target_system="tms:truckingoffice", lane="record_payable",
        load_ref="load:legacy", party="Carrier X", payload={})
    row = store.conn.execute(
        "SELECT grant_id FROM effect_grants WHERE commit_key = 'legacy-ck-1'").fetchone()
    token = "ef" * 32
    # forge the digest onto the legacy row so only the witness check separates them
    store.conn.execute("UPDATE effect_grants SET handle_digest = ? WHERE grant_id = ?",
                       (hashlib.sha256(token.encode()).hexdigest(), row["grant_id"]))
    store.conn.commit()
    handle = EffectGrantHandle(tenant=T_A, grant_id=row["grant_id"], token=token,
                               signature=kernel.sign(token))
    result = claim_grant_cas(kernel, handle, ClaimParams(
        tenant=T_A, action_class="record_payable", target_system="tms:truckingoffice",
        target_resource_id="load:legacy|Carrier X", target_operation="record_payable"))
    assert result.claimed is False and result.cause == "NO_WITNESS"
    assert "GrantWithoutWitness" in [e["event_type"] for e in store.security_events()]
    store.close()


def test_a_cross_tenant_handle_reads_as_absent_not_forbidden(tmp_path):
    """Tenant B presenting tenant A's perfectly valid handle learns nothing: the row is absent
    in B's partition, indistinguishable from never having existed."""
    store_a, kernel_a, clock, effect, outcome = _authorized(tmp_path)
    shared_key = b"k" * 32
    kernel_a2, _ = make_kernel(store_a, handle_key=shared_key)
    store_b = make_store(tmp_path, tenant=T_B, name="beta.db")
    kernel_b, _ = make_kernel(store_b, handle_key=shared_key)
    # re-sign A's token under the shared key so only tenancy separates the kernels
    handle = EffectGrantHandle(tenant=T_A, grant_id=outcome.handle.grant_id,
                               token=outcome.handle.token,
                               signature=kernel_b.sign(outcome.handle.token))
    result = claim_grant_cas(kernel_b, handle, params_for(effect))
    assert result.claimed is False and result.cause == "NO_SUCH_GRANT"
    grant = store_a.conn.execute("SELECT state FROM effect_grants WHERE grant_id = ?",
                                 (outcome.handle.grant_id,)).fetchone()
    assert grant["state"] == "GRANTED", "tenant B's probe must not consume tenant A's grant"
    store_a.close()
    store_b.close()


def test_n_racing_claimers_on_separate_connections_produce_exactly_one_claim(tmp_path):
    """AC-SAFE-014 at the CAS: eight claimers, eight real SQLite connections, one handle.
    Exactly one wins; the rest are refused; the ledger holds exactly one CLAIMED row."""
    shared_key = b"race" * 8
    store, kernel0, clock, effect, facts, versions, approval, world, inputs, request = (
        green_scenario(tmp_path))
    kernel, _ = make_kernel(store, handle_key=shared_key, clock=clock)
    outcome = run_checkpoint(kernel, request, inputs)
    assert outcome.authorized
    barrier = threading.Barrier(8)
    results: list = [None] * 8

    def contender(i: int) -> None:
        contender_store = make_store(tmp_path)  # same file, own connection
        contender_kernel, _ = make_kernel(contender_store, handle_key=shared_key, clock=clock)
        barrier.wait()
        results[i] = claim_grant_cas(contender_kernel, outcome.handle, params_for(effect))
        contender_store.close()

    threads = [threading.Thread(target=contender, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wins = [r for r in results if r is not None and r.claimed]
    losses = [r for r in results if r is not None and not r.claimed]
    assert len(wins) == 1, f"expected exactly one winner, got {len(wins)}"
    assert len(losses) == 7 and all(r.cause == "ALREADY_CLAIMED" for r in losses)
    claimed = store.conn.execute(
        "SELECT COUNT(*) FROM effect_grants WHERE state = 'CLAIMED'").fetchone()[0]
    assert claimed == 1
    assert_no_partial_state(store, effect.key())
    store.close()


def test_two_concurrent_checkpoints_for_one_effect_produce_exactly_one_grant(tmp_path):
    """The live-hold index at work across connections: two full checkpoints race for the same
    logical effect; the ledger admits one, the other lands on COMMIT_KEY_HELD => (b)."""
    from phase3_kit import (
        CheckpointInputs, CheckpointRequest, live_reader, make_approval, make_effect, make_facts,
    )
    results: list = [None, None]
    barrier = threading.Barrier(2)

    def racer(i: int) -> None:
        store_i = make_store(tmp_path)
        kernel_i, clock_i = make_kernel(store_i)
        effect = make_effect(resource="load:race")
        facts = make_facts(entity_ref="load:race")
        versions = {"load:race": 3}
        approval = make_approval(effect, facts, versions, clock_i)
        inputs = CheckpointInputs(
            material_facts_reader=live_reader(lambda: dict(facts)),
            projection_assertion={"status": "DELIVERED"},
            projected_state_reader=live_reader({"status": "DELIVERED"}),
            entity_version_reader=live_reader({"load:race": 3}),
            approval=approval)
        request = CheckpointRequest(effect=effect, actor="pipeline",
                                    accountable_owner="owner:rasheed",
                                    target_entity_ref="load:race")
        barrier.wait()
        results[i] = run_checkpoint(kernel_i, request, inputs)
        store_i.close()

    threads = [threading.Thread(target=racer, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    authorized = [r for r in results if r is not None and r.authorized]
    refused = [r for r in results if r is not None and not r.authorized]
    assert len(authorized) == 1, f"expected exactly one authorization, got {len(authorized)}"
    assert len(refused) == 1 and refused[0].reason == "COMMIT_KEY_HELD"
    checker = make_store(tmp_path)
    effect_key = make_effect(resource="load:race").key()
    grants = checker.conn.execute(
        "SELECT COUNT(*) FROM effect_grants WHERE commit_key = ?", (effect_key,)).fetchone()[0]
    witnesses = checker.conn.execute(
        "SELECT COUNT(*) FROM checkpoint_witnesses WHERE commit_key = ?",
        (effect_key,)).fetchone()[0]
    assert grants == 1 and witnesses == 1, "the loser left partial authorization state"
    checker.close()


# ============================================================ F-I: defense-in-depth predicates
#
# The claim CAS revalidates FIVE things inside the UPDATE's own WHERE clause:
#
#     WHERE tenant = ? AND grant_id = ? AND state = 'GRANTED'
#       AND expires_at > ? AND brake_version = ? AND policy_version = ?
#
# Three of them (state, brake_version, policy_version) are load-bearing on their own and each has
# a case above that fails if it is removed. The other two — `tenant` and `expires_at` — are
# DEFENSE IN DEPTH: under today's invariants an earlier control already refuses every input that
# would reach them. The independent review's F-I asked that this be recorded rather than
# discovered, and that the predicates be tested where a test can still distinguish them, so that
# removing the MASKING control later cannot silently weaken the CAS as a side effect.
#
# WHAT MASKS WHAT, precisely:
#
#   `expires_at > ?` is masked by TWO controls:
#       (1) the witness freshness check earlier in claim_grant_cas returns STALE_WITNESS first,
#           and it always fires first because CheckpointKernel.__init__ REFUSES
#           witness_window > grant_ttl - so witness_expires <= grant_expires, always;
#       (2) expire_unclaimed() flips a lapsed row to EXPIRED_UNCLAIMED, after which the
#           `state = 'GRANTED'` predicate refuses it.
#     A test CAN still distinguish it: tamper the ledger row's expires_at directly, leaving the
#     witness fresh. That models clock skew, a shortened TTL, and direct row tampering - and it is
#     exactly the state the predicate exists for.
#
#   `tenant = ?` is masked by the SELECT above it, which already loads the row by
#       (tenant, grant_id), plus the confused-deputy comparison of row["tenant"] against
#       params.tenant.
#     A test CAN still distinguish it: two tenants holding the SAME grant_id. Without the
#     predicate the UPDATE would reach the other tenant's row - and the damage would be silent,
#     because rowcount != 1 makes THIS claim refuse while the OTHER tenant's grant has already
#     been transitioned to CLAIMED underneath it.


def test_the_cas_expires_at_predicate_refuses_a_lapsed_grant_with_a_still_fresh_witness(tmp_path):
    """`expires_at > ?`, isolated from both of its masking controls.

    The row's expiry is moved into the past directly, so the witness is still fresh (no
    STALE_WITNESS) and the state is still GRANTED (no ALREADY_ refusal). Only the CAS's own
    expires_at predicate can refuse this, and it must.
    """
    store, kernel, clock, effect, outcome = _authorized(tmp_path)
    grant_id = outcome.handle.grant_id

    witness_expiry, grant_expiry = store.conn.execute(
        "SELECT w.expires_at, g.expires_at FROM checkpoint_witnesses w "
        "JOIN effect_grants g ON g.tenant = w.tenant AND g.grant_id = w.grant_id "
        "WHERE w.tenant = ? AND w.grant_id = ?", (store.tenant, grant_id)).fetchone()
    assert witness_expiry <= grant_expiry, (
        "the masking invariant is already broken: the witness outlives its grant"
    )

    lapsed = (clock.now - timedelta(seconds=1)).isoformat()
    store.conn.execute("UPDATE effect_grants SET expires_at = ? WHERE tenant = ? AND grant_id = ?",
                       (lapsed, store.tenant, grant_id))
    store.conn.commit()
    assert store.conn.execute(
        "SELECT state FROM effect_grants WHERE tenant = ? AND grant_id = ?",
        (store.tenant, grant_id)).fetchone()["state"] == "GRANTED", "setup changed the state"

    result = claim_grant_cas(kernel, outcome.handle, params_for(effect))
    assert result.claimed is False, (
        "a grant whose expiry has passed was CLAIMED - the CAS expires_at predicate did not fire"
    )
    assert result.cause == "EXPIRED", f"refused, but not as EXPIRED: {result.cause}"
    assert store.conn.execute(
        "SELECT state FROM effect_grants WHERE tenant = ? AND grant_id = ?",
        (store.tenant, grant_id)).fetchone()["state"] == "GRANTED"


def test_the_masking_invariant_behind_the_expires_at_predicate_is_still_enforced(tmp_path):
    """The masking control itself, guarded: `witness_window <= grant_ttl`.

    If this constructor refusal is ever removed, a witness could outlive its grant, the
    STALE_WITNESS check would stop masking, and the expires_at predicate would become the only
    thing standing between a lapsed grant and a claim. Losing the refusal is therefore a change
    that must be seen, not inferred - so it is asserted here beside the predicate it masks.
    """
    from freight_recon.checkpoint import CheckpointError, CheckpointKernel

    store = make_store(tmp_path, T_A, name="masking.db")
    with pytest.raises(CheckpointError, match="witness freshness window may not exceed"):
        CheckpointKernel(store, default_registry(),
                         witness_window=timedelta(seconds=120), grant_ttl=timedelta(seconds=60))
    # equal windows are legal, and are the boundary at which the masking is exact
    CheckpointKernel(store, default_registry(),
                     witness_window=timedelta(seconds=60), grant_ttl=timedelta(seconds=60))
    store.close()


def test_the_cas_tenant_predicate_protects_another_tenants_identically_named_grant(tmp_path):
    """`tenant = ?`, isolated: two tenants, ONE shared grant_id, both live and claimable.

    Without the predicate the UPDATE matches both rows: this claim would refuse (rowcount 2) while
    tenant B's grant was silently transitioned to CLAIMED - a capability consumed in a tenant that
    never asked for anything. The assertion that matters is therefore on tenant B's row.
    """
    shared_key = b"tenantpred" * 4
    store_a, kernel_a, clock_a, effect_a, _f, _v, _ap, _w, inputs_a, request_a = green_scenario(
        tmp_path)
    kernel_a, _ = make_kernel(store_a, clock=clock_a, handle_key=shared_key)
    out_a = run_checkpoint(kernel_a, request_a, inputs_a)
    assert out_a.authorized

    store_b, kernel_b, clock_b, effect_b, _f2, _v2, _ap2, _w2, inputs_b, request_b = (
        green_scenario(tmp_path / "b", tenant=T_B))
    kernel_b, _ = make_kernel(store_b, clock=clock_b, handle_key=shared_key)
    out_b = run_checkpoint(kernel_b, request_b, inputs_b)
    assert out_b.authorized

    # Force the collision the predicate exists for: the same grant_id in both tenants, with
    # identical brake and policy versions so nothing else can discriminate the rows.
    # checkpoint_witnesses is append-only by trigger, so the collision is built on the LEDGER
    # side only: tenant B keeps its own witness binding and additionally owns a row named
    # `shared_id`, under a distinct commit_key so the live-hold index still admits it.
    shared_id = out_a.handle.grant_id
    store_b.conn.execute(
        "INSERT INTO effect_grants (tenant, grant_id, commit_key, action_class, target_system, "
        "target_resource_id, target_operation, state, approved_amount, material_facts_json, "
        "policy_version, brake_version, expires_at, handle_digest, payload_json, issued_at, "
        "created_at) SELECT tenant, ?, commit_key || ':b2', action_class, target_system, "
        "target_resource_id, target_operation, 'GRANTED', approved_amount, material_facts_json, "
        "policy_version, brake_version, expires_at, handle_digest, payload_json, issued_at, "
        "created_at FROM effect_grants WHERE tenant = ? AND grant_id = ?",
        (shared_id, T_B, out_b.handle.grant_id))
    store_b.conn.commit()

    before = store_b.conn.execute(
        "SELECT state FROM effect_grants WHERE tenant = ? AND grant_id = ?",
        (T_B, shared_id)).fetchone()
    assert before is not None and before["state"] == "GRANTED", "the collision was not created"

    result = claim_grant_cas(kernel_a, out_a.handle, params_for(effect_a))
    assert result.claimed is True, f"tenant A's own legitimate claim was refused: {result.cause}"

    after = store_b.conn.execute(
        "SELECT state FROM effect_grants WHERE tenant = ? AND grant_id = ?",
        (T_B, shared_id)).fetchone()["state"]
    assert after == "GRANTED", (
        "tenant A's claim transitioned a row belonging to tenant B - the CAS tenant predicate "
        "did not fire, and the ONLY visible symptom would have been in another tenant's ledger"
    )
    store_a.close()
    store_b.close()


def test_the_cas_where_clause_still_carries_all_five_predicates(tmp_path):
    """The structural backstop, and the reason it is written as an exact set.

    CLAUDE.md section 11 forbids the claim CAS's WHERE clause from ever losing a predicate. Three
    are behaviourally proven above and two are defense-in-depth, so a source-level exact-set check
    is what makes the removal of a MASKED predicate visible at all. Membership, not a count: a
    same-count substitution must fail.
    """
    import inspect
    import re

    from freight_recon import checkpoint as ckpt

    # ### THE ANCHOR IS DISCOVERED, NOT NAMED. The first version of this guard read
    # `inspect.getsource(ckpt.claim_grant_cas)`, which silently stopped covering anything the day
    # the CAS body moved into a locked entry point so machine M2 could co-commit its own row with
    # it — the statement was still there, still correct, and this test reported that it "could not
    # be located". A guard anchored on one symbol is a guard that a refactor can aim at. So the
    # module is swept for the function that CONTAINS the statement, exactly one must, and its
    # absence is a failure rather than a miss.
    # The statement is identified by WHAT IT DOES — the GRANTED -> CLAIMED write — not by the name
    # of the function it happens to sit in. `expire_unclaimed` and `revoke_unclaimed` also UPDATE
    # this table, and neither is the CAS.
    CLAIM_WRITE = re.compile(r"UPDATE effect_grants\s+SET state = 'CLAIMED'", re.S)
    owners = {
        name: inspect.getsource(fn)
        for name, fn in vars(ckpt).items()
        if inspect.isfunction(fn) and getattr(fn, "__module__", None) == ckpt.__name__
        and CLAIM_WRITE.search(inspect.getsource(fn))
    }
    assert owners, (
        "no function in the checkpoint kernel performs the GRANTED -> CLAIMED write: the claim CAS "
        "has been removed, renamed out of the module, or generated at runtime. Any of the three "
        "means this guard is protecting nothing."
    )
    assert len(owners) == 1, (
        f"the claim CAS statement appears in {sorted(owners)}. Exactly one function may perform the "
        f"GRANTED -> CLAIMED transition (ADR-004 §3.5): two copies is two places for a predicate to "
        f"be dropped from, and this guard would only ever check one of them."
    )
    source = next(iter(owners.values()))
    m = re.search(r"UPDATE effect_grants.*?\"\"\"", source, re.S)
    assert m, "the claim CAS UPDATE statement could not be located in the source"
    where = m.group(0)
    required = {
        "tenant = ?": "cross-tenant protection (defense in depth, F-I)",
        "grant_id = ?": "the grant this handle names",
        "state = 'GRANTED'": "single-use: only an unclaimed grant is claimable",
        "expires_at > ?": "the grant TTL (defense in depth, F-I)",
        "brake_version = ?": "a brake event between mint and claim voids the grant",
        "policy_version = ?": "a policy change between mint and claim voids the grant",
    }
    missing = sorted(p for p in required if p not in where)
    assert not missing, (
        "the claim CAS lost WHERE-clause predicates, which CLAUDE.md section 11 forbids: "
        + ", ".join(f"{p} ({required[p]})" for p in missing)
    )
    tail = where.split("WHERE", 1)[1].rstrip().removesuffix('"""').strip()
    conditions = {c.strip() for c in re.split(r"\bAND\b", tail) if c.strip()}
    unexpected = sorted(c for c in conditions if c not in required)
    assert not unexpected, (
        f"the claim CAS gained unrecognised WHERE conditions: {unexpected}. A new predicate may "
        "be correct, but it must be adjudicated and recorded here, not absorbed silently."
    )
