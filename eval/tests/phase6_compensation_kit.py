"""Shared builders for the P6 M10 battery — the Compensation. NOT a test module.

### THIS KIT DELIBERATELY DOES NOT IMPORT `compensation`. It composes the ALREADY-LANDED M2/M3/M4/P3
building blocks so a test or the probe can stand up a VERIFIED original effect, a GRANTED M4 approval,
and a real compensating M2 pipeline driven through the full checkpoint — and then call M10 itself. If it
imported `compensation`, it would appear on M10's ship-dark reach list, which must be exactly the test,
the probe and the mutation battery. It does not, so it does not.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
for entry in (str(ROOT / "src"), str(ROOT / "eval" / "tests")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from freight_recon.approval import ApprovalMachine  # noqa: E402
from freight_recon.commit_key import LogicalEffect  # noqa: E402
from freight_recon.event_envelope import format_instant  # noqa: E402
from freight_recon.pipeline_instance import PipelineMachine, PipelineState, Trigger as PT  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402

import phase3_kit as p3  # noqa: E402
import phase6_pipeline_kit as pk  # noqa: E402

# Re-export the pipeline kit's builders so a test reads one import.
Clock = pk.Clock
make_store = pk.make_store
a_human = pk.a_human
a_work_item = pk.a_work_item
a_human_decision = pk.a_human_decision
kernel_for = pk.kernel_for
T_A = pk.T_A
T_B = pk.T_B
OWNER = pk.OWNER

SYS = {"actor_type": "system", "actor_id": "execution-service"}


def a_world(resource: str = "invoice-560010", *, version: int = 17,
            amount_minor: int = 285000) -> dict[str, Any]:
    """The mutable box the compensating pipeline's live readers read."""
    return {
        "facts": dict(p3.make_facts(entity_ref=resource, amount_minor=amount_minor)),
        "projection": {"status": "DELIVERED"},
        "versions": {resource: version},
    }


def a_verified_original_effect(
    store: WorkflowStore, *, tenant: str = T_A, grant_id: str = "grant-560010",
    action_class: str = "raise_invoice", target_system: str = "tms:truckingoffice",
    resource: str = "invoice-560010", operation: str = "create_invoice", state: str = "VERIFIED",
    clock: Clock | None = None,
) -> str:
    """A landed M3 Effect Grant in a given state (VERIFIED by default) — the invoice that went out,
    WITH its checkpoint pins, so a real VERIFIED effect looks like one. Inserted directly (the probe and
    the mutation battery must never import M3), tenant-first."""
    now = format_instant((clock or Clock())())
    store.conn.execute(
        "INSERT INTO effect_grants (tenant, grant_id, commit_key, action_class, target_system, "
        "target_resource_id, target_operation, state, issued_at, created_at, entity_versions_json, "
        "policy_version, brake_version) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (tenant, grant_id, f"ck-orig-{grant_id}", action_class, target_system, resource, operation,
         state, "t", now, f'{{"{resource}": 17}}', "pv1", "brk-v1"))
    store.conn.commit()
    return grant_id


def an_original_effect_in(
    store: WorkflowStore, state: str, *, tenant: str = T_A, grant_id: str | None = None,
    clock: Clock | None = None,
) -> str:
    """A landed M3 Effect Grant in any of the eight states — the `--original-state` axis."""
    gid = grant_id or f"grant-{state.lower()}-{uuid.uuid4().hex[:6]}"
    return a_verified_original_effect(
        store, tenant=tenant, grant_id=gid, resource=f"invoice-{gid}", state=state, clock=clock)


def a_granted_m4_approval(
    store: WorkflowStore, effect: LogicalEffect, world: dict[str, Any], *, approval_id: str = "ap-cmp",
    tenant: str = T_A, granter: str = OWNER, clock: Clock | None = None,
) -> str:
    """A real M4 `approvals` row, GRANTED, bound to `effect`'s commit key — what CM-2 binds. `granter`
    must be an ACTIVE recorded human (M4's FK + CHECK). Money-affecting, so `HUMAN_APPROVAL_REQUIRED`."""
    clk = clock or Clock()
    am = ApprovalMachine(store.conn, tenant=tenant, clock=clk)
    am.request(
        approval_id=approval_id, effect=effect,
        material_facts_reader=p3.live_reader(lambda: dict(world["facts"])),
        entity_versions=dict(world["versions"]), policy_version="pv1",
        gate_decision="HUMAN_APPROVAL_REQUIRED", rendered_facts="credit note", brake_version="brk-v1")
    am.grant(approval_id, actor_id=granter, actor_kind="HUMAN", authority="owner")
    return approval_id


def drive_compensating_pipeline(
    store: WorkflowStore, effect: LogicalEffect, world: dict[str, Any], *, pipeline_instance_id: str,
    tenant: str = T_A, approval_id: str = "ap-cmp", granter: str = OWNER, target: str = "VERIFIED",
    clock: Clock | None = None,
) -> str | None:
    """Drive the M2 compensating pipeline for `effect` (already PROPOSED by CM-3) to `target` — one of
    VERIFIED, NEEDS_VERIFICATION or FAILED — through the FULL checkpoint, grant, claim and readback.

    The checkpoint's approval and PL-7b's binding are for `effect`'s own commit key, so this is a
    genuinely gated compensating write, not a fast path. Returns the pipeline's grant id."""
    clk = clock or Clock()
    m2 = PipelineMachine(store.conn, tenant=tenant, clock=clk)
    kernel = kernel_for(store, clk)
    human = {"actor_type": "human", "actor_id": granter}
    commit_key = effect.key()
    m2.apply(pipeline_instance_id, PT.POLICY_EVALUATED, **SYS, policy_version="pv1",
             gate_decision="HUMAN_APPROVAL_REQUIRED", policy_decision="PERMIT", rules_matched=["r-1"],
             reason="gate resolved", model_inferred_material_fact=False)
    m2.apply(pipeline_instance_id, PT.VALIDATION_COMPLETED, **SYS, validation_passed=True,
             money_fence_passed=True, document_fence_passed=True, material_fields_consistent=True,
             open_conflict=False)
    m2.apply(pipeline_instance_id, PT.GATE_ROUTED, **SYS, gate_decision="HUMAN_APPROVAL_REQUIRED")
    approval = p3.make_approval(effect, dict(world["facts"]), dict(world["versions"]), clk,
                                policy_version="pv1")
    m2.apply(pipeline_instance_id, PT.APPROVAL_GRANTED, **human, approval_id=approval_id,
             approval_commit_key=commit_key, approval_fingerprint=approval.fingerprint)
    inputs = p3.CheckpointInputs(
        material_facts_reader=p3.live_reader(lambda: dict(world["facts"])),
        projection_assertion={"status": "DELIVERED"},
        projected_state_reader=p3.live_reader(lambda: dict(world["projection"])),
        entity_version_reader=p3.live_reader(lambda: dict(world["versions"])),
        approval=approval)
    r8 = m2.apply(pipeline_instance_id, PT.CHECKPOINT_RUN, **SYS, kernel=kernel, checkpoint_inputs=inputs)
    m2.apply(pipeline_instance_id, PT.CLAIM_ATTEMPTED, **SYS, kernel=kernel, handle=r8.grant_handle)
    grant = m2.require(pipeline_instance_id).grant_id
    assert grant is not None  # a claimed pipeline has minted its grant
    if target == "FAILED":
        m2.apply(pipeline_instance_id, PT.ADAPTER_REJECTED_PRE_FLIGHT, **SYS,
                 failure_proof="TMS returned 422 before the credit note; nothing was written")
        return grant
    if target == "NEEDS_VERIFICATION":
        m2.apply(pipeline_instance_id, PT.ADAPTER_TIMED_OUT, **SYS, unknown_reason="UNKNOWN_OUTCOME",
                 unknown_outcome_ref="obs-cmp-1")
        return grant
    # VERIFIED — adapter returned, readback matched.
    m2.consume(
        pk.canonical_event(store, event_name="EffectExecuted", producer_transition_id="EF-3",
                           aggregate_type="effect_grant", aggregate_id=grant, aggregate_version=1,
                           seed=f"exec-{pipeline_instance_id}", clock=clk,
                           pipeline_instance_id=pipeline_instance_id, accountable_owner_id=granter,
                           tenant=tenant),
        pipeline_instance_id=pipeline_instance_id, trigger=PT.ADAPTER_RETURNED_SUCCESS)
    fingerprint = m2.require(pipeline_instance_id).material_facts_fingerprint
    m2.consume(
        pk.canonical_event(store, event_name="EffectVerified", producer_transition_id="EF-4",
                           aggregate_type="effect_grant", aggregate_id=grant, aggregate_version=2,
                           seed=f"ver-{pipeline_instance_id}", clock=clk,
                           pipeline_instance_id=pipeline_instance_id, accountable_owner_id=granter,
                           tenant=tenant, payload={"matched_fingerprint": fingerprint}),
        pipeline_instance_id=pipeline_instance_id, trigger=PT.READBACK_MATCHED,
        matched_fingerprint=fingerprint, health_signal="HEALTHY")
    return grant


assert PipelineState.VERIFIED  # the kit imports the enum it names; a rename must break here
