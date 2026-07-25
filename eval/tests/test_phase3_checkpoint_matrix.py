"""Phase 3 — THE 105-CASE CHECKPOINT MERGE-GATING MATRIX (platform-safety-acceptance.md Part B).

7 steps × 15 conditions, every case landing on the universal oracle:

    (a) ONE immutable Checkpoint Witness AND ONE claimed Effect Grant (all seven passed,
        atomically), or
    (b) NO authorization capability whatsoever — no witness, no live grant, no claim, no call.
    NO PARTIAL AUTHORIZATION STATE MAY EXIST.

Where the specification anchors a cell to a specific behaviour (the F-01 drift diff at step 2,
the structural cache refusal at step 3, the SD-3 oracle at step 5, fails-to-start at step 6,
"cannot read the brake never means off" at step 7, model-granted approval ⇒ Sev-0), the cell
asserts that exact behaviour, not merely (b). Refusals are additionally run twice and must name
the SAME first failing step both times (SD-7 determinism).

Crash cells raise a BaseException (`SimulatedProcessDeath`) through the REAL code path — a
simulated kill, not a caught error — and assert the transaction left nothing behind.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
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
    assert_nothing_happened,
    assert_outcome_a,
    assert_outcome_b,
    default_registry,
    live_reader,
    make_approval,
    make_effect,
    make_facts,
    make_kernel,
    make_store,
    params_for,
)

import freight_recon.checkpoint as cp  # noqa: E402
from freight_recon.brake import BrakeStore  # noqa: E402
from freight_recon.checkpoint import (  # noqa: E402
    ApprovalRecord,
    AuthoritativeSourceReader,
    Caps,
    CheckpointError,
    CheckpointInputs,
    CheckpointPassed,
    CheckpointRequest,
    EvidenceCondition,
    GateDecision,
    GateEntry,
    GateRegistry,
    NativeClaim,
    NotALiveReader,
    ProvenanceClass,
    ProvenancedFact,
    claim_grant_cas,
    expire_unclaimed,
    mint_grant,
    run_checkpoint,
)
from freight_recon.fingerprint import Money  # noqa: E402

STEPS = (1, 2, 3, 4, 5, 6, 7)
CONDITIONS = (
    "valid", "missing_input", "stale_input", "conflicting_input", "wrong_tenant",
    "wrong_target", "wrong_actor", "changed_version", "changed_policy", "changed_brake",
    "crash_before_txn", "crash_during_txn", "crash_after_commit", "replay",
    "concurrent_competing_claim",
)


class SimulatedProcessDeath(BaseException):
    """A kill signal, not an application error: it must tear through every except-Exception."""


class _Scenario:
    """One matrix cell: a fully-built green scenario plus the cell's perturbation knobs."""

    def __init__(self, tmp_path: Path, *, action_class: str = "raise_invoice") -> None:
        self.store = make_store(tmp_path)
        self.kernel, self.clock = make_kernel(self.store)
        self.action_class = action_class
        self.resource = "load:4471"
        self.effect = make_effect(action_class=action_class, resource=self.resource)
        self.facts = make_facts(entity_ref=self.resource)
        self.versions = {self.resource: 17}
        self.approval: ApprovalRecord | None = make_approval(
            self.effect, self.facts, self.versions, self.clock)
        self.world_facts = dict(self.facts)
        self.world_projection = {"status": "DELIVERED"}
        self.world_versions = dict(self.versions)
        self.native_claims: tuple[NativeClaim, ...] = (
            NativeClaim(claim_id="claim-pod", status="ACTIVE", conflicting=False,
                        provenance=ProvenanceClass.MODEL_EXTRACTED),)
        self.material_reader = live_reader(lambda: dict(self.world_facts))
        self.projected_reader = live_reader(lambda: dict(self.world_projection))
        self.version_reader = live_reader(lambda: dict(self.world_versions))
        self.projection_assertion = {"status": "DELIVERED"}
        self.runs_today = 0
        self.request = CheckpointRequest(
            effect=self.effect, actor="pipeline", accountable_owner="owner:rasheed",
            target_entity_ref=self.resource)

    def inputs(self) -> CheckpointInputs:
        return CheckpointInputs(
            material_facts_reader=self.material_reader,
            projection_assertion=self.projection_assertion,
            projected_state_reader=self.projected_reader,
            entity_version_reader=self.version_reader,
            native_claims=self.native_claims,
            approval=self.approval,
            runs_today=self.runs_today,
        )

    def close(self) -> None:
        self.store.close()


def _dying_reader(source: str = "tms") -> AuthoritativeSourceReader:
    def die() -> dict:
        raise SimulatedProcessDeath()
    return AuthoritativeSourceReader(die, source=source)


class _DyingDatetime(datetime):
    def astimezone(self, tz=None):  # noqa: D401
        raise SimulatedProcessDeath()


class _DyingBrakes:
    def admission_denied(self, **kwargs):
        raise SimulatedProcessDeath()

    def version_token(self, **kwargs):
        raise SimulatedProcessDeath()


class _AmountBomb(str):
    """Serializes innocently at step 2 (it is a str), detonates when step 6's cap evaluation
    reaches for `amount_minor` — a crash placed exactly inside the policy step."""

    @property
    def amount_minor(self):
        raise SimulatedProcessDeath()


class _ProjectionCache:
    """The thing step 3 must be structurally unable to accept."""

    def __init__(self) -> None:
        self.data = {"status": "DELIVERED", "cached_at": "an hour ago"}

    def read(self) -> dict:
        return dict(self.data)


def _expect_refusal(s: _Scenario, *, step: int | None = None, reason: str | None = None,
                    sev0: str | None = None) -> None:
    """Run the refusal twice: same first-failing step both times (SD-7), outcome (b), no
    partial state, and the anchored Sev-0 recorded when named."""
    first = run_checkpoint(s.kernel, s.request, s.inputs())
    assert first.authorized is False, f"expected refusal, got authorization: {first}"
    second = run_checkpoint(s.kernel, s.request, s.inputs())
    assert second.authorized is False
    assert (first.step, first.reason) == (second.step, second.reason), (
        f"SD-7 broken: {first.step}/{first.reason} then {second.step}/{second.reason}")
    if step is not None:
        assert first.step == step, f"expected step {step}, got {first.step} ({first.reason})"
    if reason is not None:
        assert first.reason == reason, f"expected {reason}, got {first.reason}"
    assert_outcome_b(s.store, s.effect.key())
    assert_no_partial_state(s.store, s.effect.key())
    if sev0 is not None:
        events = [e["event_type"] for e in s.store.security_events()]
        assert sev0 in events, f"anchored Sev-0 {sev0!r} not recorded; saw {events}"


def _expect_green(s: _Scenario) -> None:
    outcome = run_checkpoint(s.kernel, s.request, s.inputs())
    assert outcome.authorized, f"the green cell refused: {outcome}"
    claim = claim_grant_cas(s.kernel, outcome.handle, params_for(s.effect))
    assert claim.claimed is True, f"the green cell's claim refused: {claim}"
    assert_outcome_a(s.store, s.effect.key())
    assert_no_partial_state(s.store, s.effect.key())


def _expect_crash(s: _Scenario) -> None:
    with pytest.raises(SimulatedProcessDeath):
        run_checkpoint(s.kernel, s.request, s.inputs())
    assert_outcome_b(s.store, s.effect.key())
    assert_no_partial_state(s.store, s.effect.key())
    # the store survives the death and a later attempt is not poisoned by a stuck transaction
    s.store.conn.execute("SELECT 1").fetchone()


# ------------------------------------------------------------------ per-step perturbations
# Each returns after mutating the scenario; the runner decides green/refusal/crash flow.

def _perturb(s: _Scenario, step: int, condition: str):
    """Apply the cell's perturbation. Returns the expected-refusal kwargs, 'green', 'crash',
    'construction', or a special flow marker."""
    K = s.kernel

    if condition == "valid":
        if step == 4:
            pass  # the green scenario already carries an ACTIVE native claim
        if step == 6 and s.action_class == "raise_invoice":
            pass  # human gate satisfied by the approval
        return "green"

    if condition == "crash_before_txn":
        # the process dies before BEGIN: the clock is the first thing the checkpoint touches
        def dead_clock() -> datetime:
            raise SimulatedProcessDeath()
        K._clock = dead_clock
        return "crash"

    if condition == "crash_during_txn":
        if step == 1:
            assert s.approval is not None
            s.approval = replace(
                s.approval,
                expires_at=_DyingDatetime(2026, 7, 21, 13, 0, 0, tzinfo=timezone.utc))
        elif step == 2:
            s.material_reader = _dying_reader()
        elif step == 3:
            s.projected_reader = _dying_reader()
        elif step == 4:
            return "crash-at-step4"      # dies at the step-4/5 boundary via _sd3_pin_set
        elif step == 5:
            s.version_reader = _dying_reader()
        elif step == 6:
            return "crash-at-step6"      # autonomous amount cap over a bomb value
        elif step == 7:
            K.brakes = _DyingBrakes()
        return "crash"

    if condition == "crash_after_commit":
        return "crash-after-commit"

    if condition == "replay":
        return "replay"

    if condition == "concurrent_competing_claim":
        return "concurrent"

    if condition == "wrong_tenant":
        if step == 1:
            assert s.approval is not None
            s.approval = replace(s.approval, tenant=T_B)
            return {"step": 1, "reason": "WRONG_TENANT_APPROVAL",
                    "sev0": "CrossTenantApprovalPresented"}
        # every other step: the effect itself names the wrong tenant — refused before anything
        s.effect = make_effect(tenant=T_B, action_class=s.action_class, resource=s.resource)
        s.request = CheckpointRequest(
            effect=s.effect, actor="pipeline", accountable_owner="owner:rasheed",
            target_entity_ref=s.resource)
        return {"reason": "TENANT_MISMATCH"}

    if condition == "changed_brake":
        # a brake engagement is the perturbation wherever it lands in the step's timeline:
        # before the checkpoint for steps 1-6 (step 7 refuses), between mint and claim for 7.
        if step == 7:
            return "brake-between-mint-and-claim"
        BrakeStore(s.store.conn).engage(
            tenant=T_A, actor="owner:rasheed", actor_kind="HUMAN", reason=f"cell {step}")
        return {"step": 7, "reason": "BRAKE_ENGAGED"}

    if condition == "changed_policy":
        K.gates = default_registry(policy_version="pv2")
        # an approval composed under pv1 drifts at step 2 (policy_version is material, §3.11);
        # the diff deterministically names the policy.
        return {"step": 2, "reason": "VOID_ON_DRIFT"}

    # ---- step-targeted conditions ----
    if step == 1:
        if condition == "missing_input":
            s.approval = None
            return {"step": 1, "reason": "MISSING_APPROVAL"}
        if condition == "stale_input":
            s.clock.advance(hours=2)   # past the approval TTL
            return {"step": 1, "reason": "APPROVAL_EXPIRED"}
        if condition == "conflicting_input":
            assert s.approval is not None
            s.approval = replace(s.approval, state="REVOKED")
            return {"step": 1, "reason": "APPROVAL_REVOKED"}
        if condition == "wrong_target":
            other = make_effect(resource="load:9999")
            s.approval = make_approval(other, s.facts, s.versions, s.clock)
            return {"step": 2, "reason": "VOID_ON_DRIFT"}   # F-22 scope creep drifts
        if condition == "wrong_actor":
            assert s.approval is not None
            s.approval = replace(s.approval, actor_kind="MODEL")
            return {"step": 1, "reason": "NONHUMAN_APPROVAL",
                    "sev0": "NonHumanApprovalPresented"}
        if condition == "changed_version":
            assert s.approval is not None
            s.approval = replace(s.approval, fingerprint_version="fp_v9")
            return {"step": 2, "reason": "UNFINGERPRINTABLE_FACTS"}

    if step == 2:
        if condition == "missing_input":
            s.material_reader = live_reader(
                lambda: (_ for _ in ()).throw(cp.SourceUnreadable("tms is down")))
            return {"step": 2, "reason": "SOURCE_UNREADABLE"}
        if condition == "stale_input":
            # THE F-01 CASE: approve GBP 2,850; the TMS moves to GBP 3,100; resume.
            s.world_facts["amount"] = replace(
                s.world_facts["amount"], _value=Money(310000, "GBP"))
            return {"step": 2, "reason": "VOID_ON_DRIFT", "f01": True}
        if condition == "conflicting_input":
            s.world_facts["counterparty"] = replace(
                s.world_facts["counterparty"], _value="Different Carrier LLC")
            return {"step": 2, "reason": "VOID_ON_DRIFT"}
        if condition == "wrong_target":
            # the amount now depends on a DIFFERENT entity than the one the decision pinned:
            # the value is unchanged (no fingerprint drift) but the SD-3 set gains load:4472,
            # which the approval never pinned — step 5 is the wall.
            s.world_facts["amount"] = replace(s.world_facts["amount"], entity_ref="load:4472")
            return {"step": 5, "reason": "UNPINNED_MATERIAL_ENTITY"}
        if condition == "wrong_actor":
            # the same number, believed for a different reason: provenance drift (§3.3)
            s.world_facts["amount"] = replace(
                s.world_facts["amount"], provenance=ProvenanceClass.MODEL_EXTRACTED)
            return {"step": 2, "reason": "VOID_ON_DRIFT"}
        if condition == "changed_version":
            assert s.approval is not None
            s.approval = replace(s.approval, fingerprint_version="fp_v0")
            return {"step": 2, "reason": "UNFINGERPRINTABLE_FACTS"}

    if step == 3:
        if condition == "missing_input":
            s.projected_reader = live_reader(
                lambda: (_ for _ in ()).throw(cp.SourceUnreadable("source gone")))
            return {"step": 3, "reason": "PROJECTION_SOURCE_UNREADABLE"}
        if condition == "stale_input":
            return "cache-construction-failure"   # the anchored structural case
        if condition == "conflicting_input":
            s.world_projection["status"] = "IN_TRANSIT"
            return {"step": 3, "reason": "PROJECTED_STATE_STALE"}
        if condition == "wrong_target":
            s.projection_assertion = {"status": "DELIVERED", "load": "load:4471"}
            s.world_projection = {"status": "DELIVERED", "load": "load:4472"}
            return {"step": 3, "reason": "PROJECTED_STATE_STALE"}
        if condition == "wrong_actor":
            s.projected_reader = live_reader(lambda: "not-a-mapping")
            return {"step": 3, "reason": "MALFORMED_PROJECTION"}
        if condition == "changed_version":
            s.world_projection["version"] = "moved"
            return {"step": 3, "reason": "PROJECTED_STATE_STALE"}

    if step == 4:
        if condition == "missing_input":
            s.native_claims = (replace(s.native_claims[0], status="RETRACTED"),)
            return {"step": 4, "reason": "CLAIM_RETRACTED"}
        if condition == "stale_input":
            s.native_claims = (replace(s.native_claims[0], status="SUPERSEDED"),)
            return {"step": 4, "reason": "CLAIM_SUPERSEDED"}
        if condition == "conflicting_input":
            s.native_claims = (replace(s.native_claims[0], conflicting=True),)
            return {"step": 4, "reason": "CLAIM_CONFLICTING"}
        if condition == "wrong_target":
            s.native_claims = (
                s.native_claims[0],
                NativeClaim(claim_id="claim-other-load", status="RETRACTED", conflicting=False,
                            provenance=ProvenanceClass.MODEL_EXTRACTED))
            return {"step": 4, "reason": "CLAIM_RETRACTED"}
        if condition == "wrong_actor":
            # a MODEL_INFERRED material fact — approved over the same guess, so the fingerprint
            # matches and step 4 is the wall (AC-SAFE-015).
            inferred = {
                name: replace(f, provenance=ProvenanceClass.MODEL_INFERRED)
                for name, f in s.facts.items()}
            s.world_facts = dict(inferred)
            s.approval = make_approval(s.effect, inferred, s.versions, s.clock)
            return {"step": 4, "reason": "MODEL_INFERRED_MATERIAL_FACT"}
        if condition == "changed_version":
            degraded = {
                name: (replace(f, evidence_condition=EvidenceCondition.STALE)
                       if name == "amount" else f)
                for name, f in s.facts.items()}
            s.world_facts = dict(degraded)
            s.approval = make_approval(s.effect, degraded, s.versions, s.clock)
            return {"step": 4, "reason": "EVIDENCE_NOT_CONSISTENT"}

    if step == 5:
        if condition == "missing_input":
            # THE SD-3 ORACLE: an entity referenced by a material fact is NOT pinned. The
            # approval is COMPOSED with the empty pin map (so its own payload is internally
            # consistent and step 2 passes) — the violation is the missing pin, and step 5 is
            # the step that must catch it.
            s.approval = make_approval(s.effect, s.facts, {}, s.clock)
            return {"step": 5, "reason": "UNPINNED_MATERIAL_ENTITY"}
        if condition == "stale_input":
            s.version_reader = live_reader(
                lambda: (_ for _ in ()).throw(cp.SourceUnreadable("version store down")))
            return {"step": 5, "reason": "ENTITY_VERSIONS_UNREADABLE"}
        if condition == "conflicting_input" or condition == "changed_version":
            # the anchored case: an entity in the SD-3 set mutates concurrently
            s.world_versions[s.resource] = 18
            return {"step": 5, "reason": "ENTITY_VERSION_DRIFT"}
        if condition == "wrong_target":
            s.world_versions = {"load:9999": 17}
            return {"step": 5, "reason": "ENTITY_VERSION_UNREADABLE"}
        if condition == "wrong_actor":
            s.world_versions = {}
            return {"step": 5, "reason": "ENTITY_VERSION_UNREADABLE"}

    if step == 6:
        if condition == "missing_input":
            return "null-gate-fails-to-start"     # the anchored STRUCTURAL case
        if condition == "stale_input":
            s.effect = make_effect(action_class="forbidden_op", resource=s.resource)
            s.request = CheckpointRequest(
                effect=s.effect, actor="pipeline", accountable_owner="owner:rasheed",
                target_entity_ref=s.resource)
            s.approval = make_approval(s.effect, s.facts, s.versions, s.clock)
            return {"step": 6, "reason": "FORBIDDEN_ACTION_CLASS"}
        if condition == "conflicting_input":
            return "caps-exceeded"
        if condition == "wrong_target":
            s.effect = make_effect(action_class="forbidden_op", resource=s.resource)
            s.request = CheckpointRequest(
                effect=s.effect, actor="pipeline", accountable_owner="owner:rasheed",
                target_entity_ref=s.resource)
            s.approval = make_approval(s.effect, s.facts, s.versions, s.clock)
            return {"step": 6, "reason": "FORBIDDEN_ACTION_CLASS"}
        if condition == "wrong_actor":
            assert s.approval is not None
            s.kernel.gates = GateRegistry(
                {"raise_invoice": GateEntry(gate=GateDecision.HUMAN_APPROVAL_REQUIRED,
                                            required_authority="manager")},
                policy_version="pv1")
            return {"step": 1, "reason": "WRONG_AUTHORITY"}
        if condition == "changed_version":
            s.kernel.gates = default_registry(policy_version="pv3")
            return {"step": 2, "reason": "VOID_ON_DRIFT"}

    if step == 7:
        if condition == "missing_input":
            s.store.conn.execute("DELETE FROM platform_brake")
            s.store.conn.commit()
            return {"step": 7, "reason": "BRAKE_UNREADABLE"}
        if condition == "stale_input":
            BrakeStore(s.store.conn).engage(
                tenant=T_A, actor="owner:rasheed", actor_kind="HUMAN", reason="stop everything")
            return {"step": 7, "reason": "BRAKE_ENGAGED"}
        if condition == "conflicting_input":
            BrakeStore(s.store.conn).engage(
                tenant=T_A, action_class=s.action_class, actor="detector:d1",
                actor_kind="DETECTOR", reason="scoped stop")
            return {"step": 7, "reason": "BRAKE_ENGAGED"}
        if condition == "wrong_target":
            BrakeStore(s.store.conn).engage(
                tenant=T_A, action_class="file_document", actor="detector:d1",
                actor_kind="DETECTOR", reason="other class stopped")
            return "green"   # a brake on ANOTHER action class must not stop this one
        if condition == "wrong_actor":
            return "model-cannot-brake"
        if condition == "changed_version":
            BrakeStore(s.store.conn).engage_platform(
                actor="detector:iso", actor_kind="DETECTOR", reason="global")
            return {"step": 7, "reason": "BRAKE_ENGAGED"}

    raise AssertionError(f"no perturbation defined for step {step} condition {condition}")


@pytest.mark.parametrize("step", STEPS)
@pytest.mark.parametrize("condition", CONDITIONS)
def test_ac_ckpt_matrix(step: int, condition: str, tmp_path):
    s = _Scenario(tmp_path)
    try:
        plan = _perturb(s, step, condition)

        if plan == "green":
            _expect_green(s)
            return
        if plan == "crash":
            _expect_crash(s)
            return
        if plan == "crash-at-step4":
            original = cp._sd3_pin_set

            def die(*args, **kwargs):
                raise SimulatedProcessDeath()
            cp._sd3_pin_set = die
            try:
                _expect_crash(s)
            finally:
                cp._sd3_pin_set = original
            return
        if plan == "crash-at-step6":
            s.kernel.gates = GateRegistry(
                {"wire_out": GateEntry(gate=GateDecision.AUTONOMOUS_WITHIN_CAPS,
                                       caps=Caps(max_amount_minor=500000))},
                policy_version="pv1")
            s.effect = make_effect(action_class="wire_out", resource=s.resource)
            bomb = ProvenancedFact(
                field="amount", provenance=ProvenanceClass.SYSTEM_IMPORTED,
                evidence_condition=EvidenceCondition.CONSISTENT, entity_ref=s.resource,
                _value=_AmountBomb("285000|GBP"))
            s.world_facts = {"amount": bomb}
            s.approval = None
            s.request = CheckpointRequest(
                effect=s.effect, actor="pipeline", accountable_owner="owner:rasheed",
                target_entity_ref=s.resource)
            inputs = CheckpointInputs(
                material_facts_reader=live_reader(lambda: dict(s.world_facts)),
                projection_assertion=s.projection_assertion,
                projected_state_reader=s.projected_reader,
                entity_version_reader=s.version_reader,
                proposed_entity_versions={s.resource: 17},
                approval=None)
            with pytest.raises(SimulatedProcessDeath):
                run_checkpoint(s.kernel, s.request, inputs)
            assert_outcome_b(s.store, s.effect.key())
            return
        if plan == "crash-after-commit":
            outcome = run_checkpoint(s.kernel, s.request, s.inputs())
            assert outcome.authorized
            # the process dies here: the claim is never made. Time passes; the grant expires.
            s.clock.advance(seconds=61)
            assert expire_unclaimed(s.kernel) == 1
            assert_nothing_happened(s.store, s.effect.key())
            # and the re-checkpoint is SAFE: a fresh witness + grant mint cleanly
            retry = run_checkpoint(s.kernel, s.request, s.inputs())
            assert retry.authorized, f"re-checkpoint after expiry refused: {retry}"
            claim = claim_grant_cas(s.kernel, retry.handle, params_for(s.effect))
            assert claim.claimed is True
            assert_outcome_a(s.store, s.effect.key(), allow_dead_history=True)
            return
        if plan == "replay":
            # a green history exists; replaying it constructs no witness and claims nothing
            outcome = run_checkpoint(s.kernel, s.request, s.inputs())
            assert outcome.authorized
            claimed = claim_grant_cas(s.kernel, outcome.handle, params_for(s.effect))
            assert claimed.claimed
            witness_rows_before = s.store.conn.execute(
                "SELECT COUNT(*) FROM checkpoint_witnesses").fetchone()[0]
            row = s.store.conn.execute("SELECT * FROM checkpoint_witnesses").fetchone()
            ghost = object.__new__(CheckpointPassed)
            object.__setattr__(ghost, "checkpoint_id", row["checkpoint_id"])
            object.__setattr__(ghost, "tenant", row["tenant"])
            object.__setattr__(ghost, "commit_key", row["commit_key"])
            object.__setattr__(ghost, "_consumed", False)
            with pytest.raises(CheckpointError):
                mint_grant(
                    s.kernel, witness=ghost, request=s.request,
                    gate_entry=s.kernel.gates.gate_for(s.action_class), approval=None,
                    material_facts_fingerprint=row["material_facts_fingerprint"],
                    approval_fingerprint=None, entity_versions={},
                    brake_token=row["brake_version"], projected_observations=(),
                    native_claims=(), now=s.clock.now)
            assert s.store.conn.execute(
                "SELECT COUNT(*) FROM checkpoint_witnesses").fetchone()[0] == witness_rows_before
            replay_claim = claim_grant_cas(s.kernel, outcome.handle, params_for(s.effect))
            assert replay_claim.claimed is False
            return
        if plan == "concurrent":
            outcome = run_checkpoint(s.kernel, s.request, s.inputs())
            assert outcome.authorized
            first = claim_grant_cas(s.kernel, outcome.handle, params_for(s.effect))
            second = claim_grant_cas(s.kernel, outcome.handle, params_for(s.effect))
            assert first.claimed is True and second.claimed is False
            assert_outcome_a(s.store, s.effect.key())
            return
        if plan == "cache-construction-failure":
            cache = _ProjectionCache()
            with pytest.raises(NotALiveReader):
                CheckpointInputs(
                    material_facts_reader=s.material_reader,
                    projection_assertion=s.projection_assertion,
                    projected_state_reader=cache,           # type: ignore[arg-type]
                    entity_version_reader=s.version_reader,
                    approval=s.approval)
            with pytest.raises(NotALiveReader):
                type("CachedReader", (AuthoritativeSourceReader,), {})  # final: no subclass route
            assert_outcome_b(s.store, s.effect.key())
            return
        if plan == "null-gate-fails-to-start":
            with pytest.raises(CheckpointError, match="fails to start"):
                GateRegistry({"raise_invoice": None}, policy_version="pv1")  # type: ignore[dict-item]
            with pytest.raises(CheckpointError):
                GateEntry(gate=None)  # type: ignore[arg-type]
            assert_outcome_b(s.store, s.effect.key())
            return
        if plan == "caps-exceeded":
            s.kernel.gates = default_registry()
            s.effect = make_effect(action_class="file_document", resource=s.resource,
                                   occurrence_key="digest-abc")
            s.approval = None
            s.request = CheckpointRequest(
                effect=s.effect, actor="pipeline", accountable_owner="owner:rasheed",
                target_entity_ref=s.resource)
            s.runs_today = 20    # the cap
            def modified_inputs():
                return CheckpointInputs(
                    material_facts_reader=s.material_reader,
                    projection_assertion=s.projection_assertion,
                    projected_state_reader=s.projected_reader,
                    entity_version_reader=s.version_reader,
                    proposed_entity_versions=dict(s.versions),
                    approval=None, runs_today=s.runs_today)
            outcome = run_checkpoint(s.kernel, s.request, modified_inputs())
            assert outcome.authorized is False
            assert outcome.step == 6 and outcome.reason == "CAP_EXCEEDED"
            assert_outcome_b(s.store, s.effect.key())
            return
        if plan == "model-cannot-brake":
            from freight_recon.brake import BrakeError
            with pytest.raises(BrakeError, match="model"):
                BrakeStore(s.store.conn).engage(
                    tenant=T_A, actor="agent:sneaky", actor_kind="MODEL", reason="let me")
            _expect_green(s)   # a model's failed brake attempt changes nothing
            return
        if plan == "brake-between-mint-and-claim":
            outcome = run_checkpoint(s.kernel, s.request, s.inputs())
            assert outcome.authorized
            BrakeStore(s.store.conn).engage(
                tenant=T_A, actor="owner:rasheed", actor_kind="HUMAN", reason="mid-flight")
            refused = claim_grant_cas(s.kernel, outcome.handle, params_for(s.effect))
            assert refused.claimed is False and refused.cause == "BRAKE_CHANGED"
            s.clock.advance(seconds=61)
            expire_unclaimed(s.kernel)
            assert_nothing_happened(s.store, s.effect.key())   # nothing happened, provably
            return

        # a plain refusal cell
        assert isinstance(plan, dict), f"unhandled plan {plan!r}"
        f01 = plan.pop("f01", False)
        _expect_refusal(s, **plan)
        if f01:
            outcome = run_checkpoint(s.kernel, s.request, s.inputs())
            named = [d for d in outcome.drift if "amount" in d.field]
            assert named and named[0].approved == "285000|GBP" and named[0].current == "310000|GBP", (
                f"THE F-01 CASE must name the amount, old and new: {outcome.drift}")
    finally:
        s.close()


def test_the_matrix_is_exactly_seven_by_fifteen():
    assert len(STEPS) == 7 and len(CONDITIONS) == 15
    assert len(STEPS) * len(CONDITIONS) == 105, "the merge-gating matrix is 105 cases, exactly"
