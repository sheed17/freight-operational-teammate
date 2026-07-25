"""Shared builders and oracles for the Phase-3 checkpoint battery. NOT a test module.

Everything here is deliberately boring: fresh tenant-bound stores over tmp databases, a
controllable clock (the acceptance defaults forbid wall-clock dependence), one green scenario
that every hostile case perturbs, and the universal-oracle assertion the 105-case matrix names:

    (a) ONE immutable Checkpoint Witness AND ONE claimed Effect Grant, or
    (b) NO authorization capability whatsoever - no witness row, no grant row, no claim.
    NO PARTIAL AUTHORIZATION STATE MAY EXIST.
"""

from __future__ import annotations

import hashlib
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for entry in (str(ROOT / "src"), str(ROOT / "eval")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from freight_recon.checkpoint import (  # noqa: E402
    ApprovalRecord,
    AuthoritativeSourceReader,
    Caps,
    CheckpointInputs,
    CheckpointKernel,
    CheckpointRequest,
    ClaimParams,
    EvidenceCondition,
    GateDecision,
    GateEntry,
    GateRegistry,
    ProvenanceClass,
    ProvenancedFact,
    claim_grant_cas,
    material_fact_set,
    run_checkpoint,
)
from freight_recon.commit_key import LogicalEffect  # noqa: E402
from freight_recon.fingerprint import Money, canonical_payload  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402

T_A = "tenant-alpha"
T_B = "tenant-beta"

# One fixed instant; tests advance a mutable box, never the wall clock.
EPOCH = datetime(2026, 7, 21, 12, 0, 0, tzinfo=timezone.utc)


class Clock:
    """A controllable clock: `advance` is the only way time passes in this battery."""

    def __init__(self, start: datetime = EPOCH) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> datetime:
        self.now = self.now + timedelta(**kwargs)
        return self.now


def make_store(tmp_path: Path, tenant: str = T_A, name: str = "p3.db") -> WorkflowStore:
    return WorkflowStore(tmp_path / name, tenant=tenant)


def default_registry(policy_version: str = "pv1") -> GateRegistry:
    return GateRegistry(
        {
            "raise_invoice": GateEntry(gate=GateDecision.HUMAN_APPROVAL_REQUIRED),
            "file_document": GateEntry(
                gate=GateDecision.AUTONOMOUS_WITHIN_CAPS,
                caps=Caps(max_per_day=20, max_amount_minor=None),
            ),
            "assert_authorization": GateEntry(
                gate=GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED),
            "forbidden_op": GateEntry(gate=GateDecision.FORBIDDEN),
        },
        policy_version=policy_version,
    )


def make_kernel(
    store: WorkflowStore,
    *,
    clock: Clock | None = None,
    registry: GateRegistry | None = None,
    observer=None,
    handle_key: bytes | None = None,
    witness_window: timedelta = timedelta(seconds=60),
    grant_ttl: timedelta = timedelta(seconds=60),
) -> tuple[CheckpointKernel, Clock]:
    clk = clock or Clock()
    kernel = CheckpointKernel(
        store,
        registry or default_registry(),
        clock=clk,
        observer=observer,
        handle_key=handle_key,
        witness_window=witness_window,
        grant_ttl=grant_ttl,
    )
    return kernel, clk


def make_effect(
    *, tenant: str = T_A, action_class: str = "raise_invoice", resource: str = "load:4471",
    occurrence_key: str = "",
) -> LogicalEffect:
    return LogicalEffect(
        tenant=tenant, action_class=action_class, target_system="tms:truckingoffice",
        target_resource_id=resource, target_operation="create_invoice",
        occurrence_key=occurrence_key,
    )


def make_facts(
    *, amount_minor: int = 285000, entity_ref: str = "load:4471",
    provenance: ProvenanceClass = ProvenanceClass.SYSTEM_IMPORTED,
    evidence: EvidenceCondition = EvidenceCondition.CONSISTENT,
) -> dict[str, ProvenancedFact]:
    return {
        "amount": ProvenancedFact(
            field="amount", provenance=provenance, evidence_condition=evidence,
            entity_ref=entity_ref, _value=Money(amount_minor, "GBP")),
        "counterparty": ProvenancedFact(
            field="counterparty", provenance=ProvenanceClass.SYSTEM_IMPORTED,
            evidence_condition=EvidenceCondition.CONSISTENT, _value="Acme Logistics"),
    }


def make_approval(
    effect: LogicalEffect,
    facts: dict[str, ProvenancedFact],
    versions: dict[str, int],
    clock: Clock,
    *,
    policy_version: str = "pv1",
    tenant: str | None = None,
    actor_kind: str = "HUMAN",
    state: str = "GRANTED",
    authority: str = "owner",
    ttl: timedelta = timedelta(hours=1),
    fingerprint_version: str = "fp_v1",
) -> ApprovalRecord:
    """An approval whose payload was composed by the ONE canonical composer, at 'approval time'."""
    payload = canonical_payload(
        material_fact_set(
            effect=effect, commit_key=effect.key(), business_facts=facts,
            entity_versions=versions, policy_version=policy_version),
    )
    return ApprovalRecord(
        approval_id="ap-1", tenant=tenant or effect.tenant, actor_id="owner:rasheed",
        actor_kind=actor_kind, authority=authority, state=state,
        fingerprint=hashlib.sha256(payload).hexdigest(), canonical_payload=payload,
        fingerprint_version=fingerprint_version, entity_versions=dict(versions),
        policy_version=policy_version, granted_at=clock.now, expires_at=clock.now + ttl,
    )


def live_reader(value, *, source: str = "tms:truckingoffice") -> AuthoritativeSourceReader:
    """A live reader over a mutable box: `value` may be a dict (snapshotted per read) or a
    zero-arg callable (evaluated per read - mutate the box to model drift)."""
    if callable(value):
        return AuthoritativeSourceReader(value, source=source)
    return AuthoritativeSourceReader(lambda: dict(value), source=source)


def green_scenario(
    tmp_path: Path,
    *,
    tenant: str = T_A,
    action_class: str = "raise_invoice",
    resource: str = "load:4471",
    registry: GateRegistry | None = None,
):
    """The one green scenario every hostile case perturbs: a human-gated invoice at GBP 2,850,
    consistent evidence, fresh projection, pinned version 17, no brake."""
    store = make_store(tmp_path, tenant)
    kernel, clock = make_kernel(store, registry=registry)
    effect = make_effect(tenant=tenant, action_class=action_class, resource=resource)
    facts = make_facts(entity_ref=resource)
    versions = {resource: 17}
    approval = make_approval(effect, facts, versions, clock)
    world = {
        "facts": dict(facts),
        "projection": {"status": "DELIVERED"},
        "versions": dict(versions),
    }
    inputs = CheckpointInputs(
        material_facts_reader=live_reader(lambda: dict(world["facts"])),
        projection_assertion={"status": "DELIVERED"},
        projected_state_reader=live_reader(lambda: dict(world["projection"])),
        entity_version_reader=live_reader(lambda: dict(world["versions"])),
        approval=approval,
    )
    request = CheckpointRequest(
        effect=effect, actor="pipeline", accountable_owner="owner:rasheed",
        target_entity_ref=resource)
    return store, kernel, clock, effect, facts, versions, approval, world, inputs, request


def params_for(effect: LogicalEffect) -> ClaimParams:
    return ClaimParams(
        tenant=effect.tenant, action_class=effect.action_class,
        target_system=effect.target_system, target_resource_id=effect.target_resource_id,
        target_operation=effect.target_operation)


def checkpoint_and_claim(kernel, request, inputs, effect):
    outcome = run_checkpoint(kernel, request, inputs)
    if not outcome.authorized:
        return outcome, None
    claim = claim_grant_cas(kernel, outcome.handle, params_for(effect))
    return outcome, claim


# ------------------------------------------------------------------ the universal oracle


def witness_rows(store: WorkflowStore, commit_key: str) -> list:
    return store.conn.execute(
        "SELECT * FROM checkpoint_witnesses WHERE tenant = ? AND commit_key = ?",
        (store.tenant, commit_key)).fetchall()


def grant_rows(store: WorkflowStore, commit_key: str) -> list:
    return store.conn.execute(
        "SELECT * FROM effect_grants WHERE tenant = ? AND commit_key = ?",
        (store.tenant, commit_key)).fetchall()


def assert_outcome_a(store: WorkflowStore, commit_key: str, *, allow_dead_history: bool = False) -> None:
    """(a): exactly ONE claimed Effect Grant, checkpoint-bound 1:1 to its witness.

    `allow_dead_history` admits the retry shape: earlier attempts whose grants are provably dead
    (EXPIRED_UNCLAIMED / REVOKED / FAILED) remain as permanent evidence beside the one that
    committed — retention is permanent [C-9], and evidence of a refused past is not a second
    authorization."""
    witnesses = {w["checkpoint_id"]: w for w in witness_rows(store, commit_key)}
    grants = grant_rows(store, commit_key)
    claimed = [g for g in grants if g["state"] == "CLAIMED"]
    assert len(claimed) == 1, (
        f"outcome (a) requires exactly one CLAIMED grant, found {len(claimed)} "
        f"(states: {[g['state'] for g in grants]})")
    bound = witnesses.get(claimed[0]["checkpoint_id"])
    assert bound is not None, "the claimed grant has no witness (two-key rule broken at rest)"
    assert bound["grant_id"] == claimed[0]["grant_id"], "witness/grant 1:1 broken"
    if not allow_dead_history:
        assert len(grants) == 1, f"unexpected extra grant rows: {[g['state'] for g in grants]}"
        assert len(witnesses) == 1, f"unexpected extra witness rows: {len(witnesses)}"
    else:
        others = [g for g in grants if g["grant_id"] != claimed[0]["grant_id"]]
        dead = {"EXPIRED_UNCLAIMED", "REVOKED", "FAILED"}
        assert all(g["state"] in dead for g in others), (
            f"history rows must be provably dead: {[g['state'] for g in others]}")


def assert_outcome_b(store: WorkflowStore, commit_key: str, *, world_calls: list | None = None) -> None:
    """(b) for a checkpoint that never passed: NO witness row, no live grant row, no call."""
    witnesses = witness_rows(store, commit_key)
    assert witnesses == [], f"outcome (b) but {len(witnesses)} witness row(s) exist"
    live = [g for g in grant_rows(store, commit_key)
            if g["state"] in ("GRANTED", "CLAIMED", "ATTEMPTED", "VERIFIED", "UNKNOWN_OUTCOME")]
    assert live == [], f"outcome (b) but live grant rows exist: {[g['state'] for g in live]}"
    if world_calls is not None:
        assert world_calls == [], f"outcome (b) but the world was touched: {world_calls}"


def assert_nothing_happened(store: WorkflowStore, commit_key: str) -> None:
    """(b) for the post-mint deaths (crash after commit; brake between mint and claim): the
    witness persists as permanent evidence [C-9] and the grant row records a capability that
    died unclaimed — but NO claim exists, no capability survives, and every witness maps to a
    provably-dead grant. This is the matrix's own reading: 'the grant EXPIRES unclaimed => (b)
    — nothing happened; re-checkpoint is safe.'"""
    grants = {g["grant_id"]: g for g in grant_rows(store, commit_key)}
    live = [g for g in grants.values()
            if g["state"] in ("GRANTED", "CLAIMED", "ATTEMPTED", "VERIFIED", "UNKNOWN_OUTCOME")]
    assert live == [], f"nothing-happened but live/claimed rows exist: {[g['state'] for g in live]}"
    for w in witness_rows(store, commit_key):
        g = grants.get(w["grant_id"])
        assert g is not None, "a witness without its grant row"
        assert g["state"] in ("EXPIRED_UNCLAIMED", "REVOKED", "FAILED"), (
            f"the witnessed grant is not provably dead: {g['state']}")


def assert_no_partial_state(store: WorkflowStore, commit_key: str) -> None:
    """A witness without its grant, or a checkpoint-bound grant without its witness, is the
    partial authorization state the matrix forbids at every isolation level."""
    witnesses = witness_rows(store, commit_key)
    grants = {g["grant_id"]: g for g in grant_rows(store, commit_key)}
    for w in witnesses:
        assert w["grant_id"] in grants, "PARTIAL STATE: a witness row without its grant row"
    for g in grants.values():
        if g["checkpoint_id"]:
            assert any(w["checkpoint_id"] == g["checkpoint_id"] for w in witnesses), (
                "PARTIAL STATE: a checkpoint-bound grant without its witness")


def perturbed_facts(facts: dict, field_name: str, **changes) -> dict:
    """A copy of the fact set with one fact rebuilt (dataclasses.replace over frozen facts)."""
    out = dict(facts)
    out[field_name] = replace(out[field_name], **changes)
    return out
