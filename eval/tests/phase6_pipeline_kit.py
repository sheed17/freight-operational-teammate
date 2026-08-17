"""Shared builders for the P6 M2 battery — the Pipeline Instance. NOT a test module.

The rule this kit follows is `phase6_kit`'s: a fixture never asserts anything and never hides a
decision the test is about. It composes the ALREADY-CERTIFIED kits rather than re-deriving their
material — P3's kernel/approval/reader builders and P6's recorded-authority builder are imported,
because a battery that built its own approval fingerprint would be testing its own arithmetic.
"""

from __future__ import annotations

import hashlib
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
for entry in (str(ROOT / "src"), str(ROOT / "eval" / "tests")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from freight_recon.checkpoint import (  # noqa: E402
    Caps,
    CheckpointInputs,
    CheckpointKernel,
    GateDecision,
    GateEntry,
    GateRegistry,
)
from freight_recon.commit_key import LogicalEffect  # noqa: E402
from freight_recon.event_contracts import CONTRACTS  # noqa: E402
from freight_recon.event_envelope import EventEnvelope, format_instant  # noqa: E402
from freight_recon.event_outbox import TransactionalOutbox  # noqa: E402
from freight_recon.pipeline_instance import (  # noqa: E402
    AGGREGATE_TYPE,
    PipelineMachine,
    PipelineState,
    Trigger,
)
from freight_recon.work_item import WorkItemMachine, record_human_authority  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402

from phase3_kit import (  # noqa: E402
    Clock as _P3Clock,
    live_reader,
    make_approval,
    make_facts,
)

T_A = "tenant-alpha"
T_B = "tenant-beta"

EPOCH = datetime(2026, 8, 14, 9, 0, 0, tzinfo=timezone.utc)

# The freight narrative every case in this battery perturbs. Named here so the tests read like the
# operation they model rather than like fixtures: load 4471 delivered, POD in hand, invoice owed.
LOAD = "load:4471"
OWNER = "dispatcher-dana"
WORK_ITEM = "wi-4471-billing"
PIPELINE = "pl-4471-invoice-1"


class Clock(_P3Clock):
    """P3's controllable clock, starting at this battery's own epoch.

    Subclassed rather than re-declared: `make_approval` and `live_reader` take P3's Clock, and a
    second class with the same shape would work until the day one of them grew a method. `advance`
    is still the only way time passes here.
    """

    def __init__(self, start: datetime = EPOCH) -> None:
        super().__init__(start)


def deterministic_event_id(seed: str) -> str:
    """A reproducible, genuinely v4-shaped UUID. Same seed, same id, every run and every machine."""
    digest = bytearray(hashlib.sha256(seed.encode("utf-8")).digest()[:16])
    digest[6] = (digest[6] & 0x0F) | 0x40
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(digest)))


def make_store(tmp_path: Path, tenant: str = T_A, name: str = "p6m2.db") -> WorkflowStore:
    return WorkflowStore(tmp_path / name, tenant=tenant)


def registry(policy_version: str = "pv1") -> GateRegistry:
    """The gate ladder these cases route on. Built HERE, in a test, and never in production code:
    `CURRENT.md` keeps the production `GateRegistry` population EMPTY until U8.1/P8."""
    return GateRegistry(
        {
            "raise_invoice": GateEntry(gate=GateDecision.HUMAN_APPROVAL_REQUIRED),
            "file_document": GateEntry(
                gate=GateDecision.AUTONOMOUS_WITHIN_CAPS,
                caps=Caps(max_per_day=20, max_amount_minor=None)),
            "forbidden_op": GateEntry(gate=GateDecision.FORBIDDEN),
        },
        policy_version=policy_version,
    )


def kernel_for(
    store: WorkflowStore,
    clock: Clock,
    *,
    gates: GateRegistry | None = None,
    witness_window: timedelta = timedelta(seconds=60),
    grant_ttl: timedelta = timedelta(seconds=60),
    observer: Any = None,
) -> CheckpointKernel:
    return CheckpointKernel(
        store, gates or registry(), clock=clock, witness_window=witness_window,
        grant_ttl=grant_ttl, observer=observer,
    )


def an_effect(
    *, tenant: str = T_A, action_class: str = "raise_invoice", resource: str = LOAD,
    occurrence_key: str = "",
) -> LogicalEffect:
    return LogicalEffect(
        tenant=tenant, action_class=action_class, target_system="tms:truckingoffice",
        target_resource_id=resource, target_operation="create_invoice",
        occurrence_key=occurrence_key,
    )


def a_human(
    store: WorkflowStore, human_id: str = OWNER, *, tenant: str = T_A,
    role: str = "AUTHORIZED_HUMAN", recorded_by: str = "founder-sam", clock: Clock | None = None,
) -> str:
    record_human_authority(
        store.conn, tenant=tenant, human_id=human_id, display_name=human_id.title(),
        authority_role=role, recorded_by=recorded_by, now=(clock or Clock())(),
    )
    return human_id


def a_work_item(
    store: WorkflowStore, *, tenant: str = T_A, work_item_id: str = WORK_ITEM,
    owner_id: str = OWNER, clock: Clock | None = None,
):
    """The obligation the attempt serves: "get load 4471 billed"."""
    m1 = WorkItemMachine(store.conn, tenant=tenant, clock=clock)
    return m1.create(
        work_item_id=work_item_id, type="delivered_load_closure", owner_id=owner_id,
        actor_type="system", actor_id="work-service", entity_ref=LOAD,
    )


def machine(store: WorkflowStore, *, tenant: str = T_A, clock: Clock | None = None
            ) -> PipelineMachine:
    return PipelineMachine(store.conn, tenant=tenant, clock=clock)


def a_world(resource: str = LOAD, *, version: int = 17) -> dict[str, Any]:
    """The mutable box the live readers read. Mutating it IS how a case models drift."""
    return {
        "facts": dict(make_facts(entity_ref=resource)),
        "projection": {"status": "DELIVERED"},
        "versions": {resource: version},
    }


def checkpoint_inputs(
    effect: LogicalEffect,
    world: dict[str, Any],
    clock: Clock,
    *,
    approved: bool = True,
    policy_version: str = "pv1",
    **approval_overrides: Any,
) -> CheckpointInputs:
    """P3's typed inputs, composed from P3's own builders.

    `approved=False` is the autonomous path: no approval is bound, which the kernel accepts only
    when the gate does not require one.
    """
    approval = None
    if approved:
        approval = make_approval(
            effect, dict(world["facts"]), dict(world["versions"]), clock,
            policy_version=policy_version, **approval_overrides,
        )
    return CheckpointInputs(
        material_facts_reader=live_reader(lambda: dict(world["facts"])),
        projection_assertion={"status": "DELIVERED"},
        projected_state_reader=live_reader(lambda: dict(world["projection"])),
        entity_version_reader=live_reader(lambda: dict(world["versions"])),
        approval=approval,
    )


def approval_fingerprint(effect: LogicalEffect, world: dict[str, Any], clock: Clock,
                         *, policy_version: str = "pv1") -> str:
    """The fingerprint PL-7b must bind — recomputed by the canonical composer, never transcribed."""
    return make_approval(
        effect, dict(world["facts"]), dict(world["versions"]), clock,
        policy_version=policy_version,
    ).fingerprint


# --------------------------------------------------------------------------------- event fixtures

def canonical_event(
    store: WorkflowStore,
    *,
    event_name: str,
    producer_transition_id: str,
    aggregate_type: str,
    aggregate_id: str,
    aggregate_version: int,
    seed: str,
    tenant: str = T_A,
    actor_type: str = "system",
    actor_id: str = "execution-service",
    clock: Clock | None = None,
    payload: dict[str, Any] | None = None,
    work_item_id: str | None = WORK_ITEM,
    pipeline_instance_id: str | None = None,
    accountable_owner_id: str | None = None,
    emit: bool = False,
) -> EventEnvelope:
    """One CANONICAL envelope of the given contract — built from the contract, not hand-written.

    The consumed transitions of M2 are driven by events whose producers are M3 and M4, and those
    machines are later units. The battery therefore constructs the canonical envelope directly, as
    `phase5_kit` does: the point under test is that M2 consumes a real contract-valid event through
    the real dedup inbox, not how the producing machine will one day build it.

    `emit=True` additionally writes it to the outbox, which is what a `decision_ref` resolves
    against.
    """
    now = format_instant((clock or Clock())())
    contract = CONTRACTS[event_name]
    body: dict[str, Any] = dict(payload or {})
    for spec in contract.fields:
        if spec.required and spec.name not in body:
            body[spec.name] = (
                (True if spec.fixed == "true" else False if spec.fixed == "false" else spec.fixed)
                if spec.fixed is not None
                else spec.enum[0] if spec.enum
                else [f"{spec.name}-1"] if spec.listed
                else f"{spec.name}-value"
            )
    pins: dict[str, Any] = {}
    if contract.consequential and not contract.consequential_conditional:
        pins = {
            "entity_versions": {f"{aggregate_type}:{aggregate_id}": aggregate_version},
            "policy_version": "pv1",
            "brake_version": "brk-v1",
        }
    envelope = EventEnvelope(
        event_id=deterministic_event_id(seed), event_name=event_name,
        event_version=contract.current_version, occurred_at=now, recorded_at=now,
        tenant_id=tenant, aggregate_type=aggregate_type, aggregate_id=aggregate_id,
        aggregate_version=aggregate_version, causation_id=None, correlation_id=f"corr-{seed}",
        producer_component="test", producer_transition_id=producer_transition_id,
        actor_type=actor_type, actor_id=actor_id, trace_id=f"trace-{seed}", payload=body,
        work_item_id=work_item_id, pipeline_instance_id=pipeline_instance_id,
        accountable_owner_id=accountable_owner_id, **pins,
    )
    if emit:
        conn = store.conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            TransactionalOutbox(conn, tenant=tenant, clock=clock or Clock()).emit(envelope)
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    return envelope


def a_human_decision(
    store: WorkflowStore, *, tenant: str = T_A, actor_id: str = OWNER, seed: str = "reality-1",
    clock: Clock | None = None,
) -> str:
    """A committed `HumanDecided` — what a PL-15 `decision_ref` of kind AUDIT_EVENT resolves to."""
    envelope = canonical_event(
        store, event_name="HumanDecided", producer_transition_id="WI-9",
        aggregate_type="work_item", aggregate_id=f"wi-decision-{seed}", aggregate_version=1,
        seed=seed, tenant=tenant, actor_type="human", actor_id=actor_id, clock=clock,
        payload={"decision_ref": f"ref-{seed}"}, emit=True,
    )
    return envelope.event_id


# ------------------------------------------------------------------------------------- oracles

def outbox_events(store: WorkflowStore, *, tenant: str = T_A) -> list[dict[str, Any]]:
    return [
        {"event_id": r["event_id"], "event_name": r["event_name"],
         "aggregate_type": r["aggregate_type"], "aggregate_id": r["aggregate_id"],
         "aggregate_version": int(r["aggregate_version"]),
         "producer_transition_id": r["producer_transition_id"]}
        for r in store.conn.execute(
            "SELECT * FROM event_outbox WHERE tenant = ? ORDER BY sequence", (tenant,)).fetchall()
    ]


def security_rows(store: WorkflowStore, *, tenant: str = T_A) -> list[dict[str, Any]]:
    return [
        {"event_type": r["event_type"], "actor": r["actor"], "payload_json": r["payload_json"]}
        for r in store.conn.execute(
            "SELECT * FROM security_events WHERE tenant = ? ORDER BY id", (tenant,)).fetchall()
    ]


def ledger(store: WorkflowStore, *, tenant: str = T_A) -> list[dict[str, Any]]:
    return [
        {"grant_id": r["grant_id"], "state": r["state"], "commit_key": r["commit_key"]}
        for r in store.conn.execute(
            "SELECT * FROM effect_grants WHERE tenant = ? ORDER BY grant_id", (tenant,)).fetchall()
    ]


def witnesses(store: WorkflowStore, *, tenant: str = T_A) -> list[dict[str, Any]]:
    return [
        {"checkpoint_id": r["checkpoint_id"], "grant_id": r["grant_id"],
         "commit_key": r["commit_key"]}
        for r in store.conn.execute(
            "SELECT * FROM checkpoint_witnesses WHERE tenant = ? ORDER BY checkpoint_id",
            (tenant,)).fetchall()
    ]


def state_digest(store: WorkflowStore, *, tenant: str = T_A) -> str:
    """A byte-level fingerprint of everything this tenant's M1+M2+kernel surface holds.

    ### THIS IS WHAT MAKES "NO-OP" A MEASUREMENT RATHER THAN A CLAIM. Every redelivery case asserts
    the digest is byte-identical across the second delivery; without it, "nothing happened" is the
    absence of an assertion.
    """
    parts: list[str] = []
    for table, order in (
        ("pipeline_instances", "pipeline_instance_id"),
        ("work_items", "work_item_id"),
        ("tenant_humans", "human_id"),
        ("effect_grants", "grant_id"),
        ("checkpoint_witnesses", "checkpoint_id"),
        ("event_outbox", "sequence"),
        ("event_inbox", "event_id"),
        ("pending_references", "event_id"),
        ("security_events", "id"),
    ):
        for row in store.conn.execute(
            f"SELECT * FROM {table} WHERE tenant = ? ORDER BY {order}", (tenant,)
        ).fetchall():
            parts.append(f"{table}|" + "|".join(f"{k}={row[k]!r}" for k in row.keys()))
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------- the green narrative

SYS = {"actor_type": "system", "actor_id": "execution-service"}
HUMAN = {"actor_type": "human", "actor_id": OWNER}


def a_proposed_attempt(
    store: WorkflowStore,
    *,
    tenant: str = T_A,
    clock: Clock | None = None,
    pipeline_instance_id: str = PIPELINE,
    work_item_id: str = WORK_ITEM,
    effect: LogicalEffect | None = None,
    owner_id: str = OWNER,
    with_work_item: bool = True,
):
    """Load 4471 is delivered and billable; attempt #1 at raising the invoice has been proposed."""
    clk = clock or Clock()
    if with_work_item:
        a_human(store, owner_id, tenant=tenant, clock=clk)
        a_work_item(store, tenant=tenant, work_item_id=work_item_id, owner_id=owner_id, clock=clk)
    m = machine(store, tenant=tenant, clock=clk)
    outcome = m.propose(
        pipeline_instance_id=pipeline_instance_id, work_item_id=work_item_id,
        effect=effect or an_effect(tenant=tenant), proposal_ref="intent-1", **SYS,
    )
    return m, outcome


def advance_to_checkpoint(
    m: PipelineMachine,
    pipeline_instance_id: str = PIPELINE,
    *,
    gate: GateDecision = GateDecision.HUMAN_APPROVAL_REQUIRED,
    approval_id: str = "ap-1",
    fingerprint: str = "fp-approved",
    commit_key: str | None = None,
) -> None:
    """PL-2 → PL-4 → (PL-6 → PL-7b | PL-7a), leaving the attempt in CHECKPOINT."""
    m.apply(pipeline_instance_id, Trigger.POLICY_EVALUATED, **SYS,
            policy_version="pv1", gate_decision=gate, policy_decision="PERMIT",
            rules_matched=["r-1"], reason="gate resolved", model_inferred_material_fact=False)
    m.apply(pipeline_instance_id, Trigger.VALIDATION_COMPLETED, **SYS,
            validation_passed=True, money_fence_passed=True, document_fence_passed=True,
            material_fields_consistent=True, open_conflict=False)
    if gate is GateDecision.AUTONOMOUS_WITHIN_CAPS:
        m.apply(pipeline_instance_id, Trigger.GATE_ROUTED, **SYS,
                gate_decision=gate, caps_evaluated={"max_per_day": True},
                brake_version="brk-v1", policy_version="pv1")
        return
    m.apply(pipeline_instance_id, Trigger.GATE_ROUTED, **SYS, gate_decision=gate)
    key = commit_key or m.require(pipeline_instance_id).commit_key
    m.apply(pipeline_instance_id, Trigger.APPROVAL_GRANTED, **HUMAN,
            approval_id=approval_id, approval_commit_key=key, approval_fingerprint=fingerprint)


assert PipelineState.CHECKPOINT  # the kit imports the enum it names; a rename must break here
assert AGGREGATE_TYPE == "pipeline_instance"
