"""Shared fixtures for the P6 M1 battery. Small, explicit, and derived where derivation is possible.

The one rule this kit follows: a fixture never asserts anything and never hides a decision the test
is about. `a_human` records an authority because ownership must come from a recorded authority — if
a test could get an owner without one, the test would not be testing ownership.
"""

from __future__ import annotations

import hashlib
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from freight_recon.event_contracts import CONTRACTS  # noqa: E402
from freight_recon.event_envelope import EventEnvelope, format_instant  # noqa: E402
from freight_recon.event_outbox import TransactionalOutbox  # noqa: E402
from freight_recon.work_item import (  # noqa: E402
    AGE_THRESHOLD_TIMER_KIND,
    AGGREGATE_TYPE,
    WorkItemMachine,
    record_human_authority,
)
from freight_recon.workflow import WorkflowStore  # noqa: E402

T_A = "tenant-alpha"
T_B = "tenant-beta"

EPOCH = datetime(2026, 8, 14, 9, 0, 0, tzinfo=timezone.utc)


class Clock:
    """A controllable clock: `advance` is the only way time passes in this battery."""

    def __init__(self, start: datetime = EPOCH) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: Any) -> datetime:
        self.now = self.now + timedelta(**kwargs)
        return self.now


def deterministic_event_id(seed: str) -> str:
    """A reproducible, genuinely v4-shaped UUID. Same seed, same id, every run and every machine."""
    digest = bytearray(hashlib.sha256(seed.encode("utf-8")).digest()[:16])
    digest[6] = (digest[6] & 0x0F) | 0x40
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(digest)))


def minimal_payload(event_name: str) -> dict[str, Any]:
    """A payload that SATISFIES `event_name`'s contract — every required fact, and nothing more.

    Derived from the contract rather than written per event, exactly as `phase5_kit` derives its
    fixtures and for the same reason: a hand-written body drifts from the specification silently,
    and this battery caught itself doing it — an `ApprovalGranted` fixture omitted `granted_by` and
    was refused by the real contract gate, which is the gate working.
    """
    contract = CONTRACTS[event_name]
    payload: dict[str, Any] = {}
    for spec in contract.fields:
        if not spec.required:
            continue
        if spec.fixed is not None:
            payload[spec.name] = (True if spec.fixed == "true" else
                                  False if spec.fixed == "false" else spec.fixed)
        elif spec.enum:
            payload[spec.name] = spec.enum[0]
        elif spec.listed:
            payload[spec.name] = [f"{spec.name}-1"]
        else:
            payload[spec.name] = f"{spec.name}-value"
    for group in contract.one_of:
        if group.required and not any(member in payload for member in group.members):
            payload[group.members[0]] = f"{group.members[0]}-value"
    return payload


def make_store(tmp_path: Path, tenant: str = T_A, name: str = "p6.db") -> WorkflowStore:
    return WorkflowStore(tmp_path / name, tenant=tenant)


def machine(store: WorkflowStore, *, tenant: str = T_A, clock: Clock | None = None
            ) -> WorkItemMachine:
    return WorkItemMachine(store.conn, tenant=tenant, clock=clock)


def a_human(
    store: WorkflowStore,
    human_id: str = "dispatcher-dana",
    *,
    tenant: str = T_A,
    role: str = "AUTHORIZED_HUMAN",
    recorded_by: str = "founder-sam",
    clock: Clock | None = None,
) -> str:
    record_human_authority(
        store.conn, tenant=tenant, human_id=human_id, display_name=human_id.title(),
        authority_role=role, recorded_by=recorded_by,
        now=(clock or Clock())(),
    )
    return human_id


def an_item(
    m: WorkItemMachine,
    *,
    work_item_id: str = "wi-4471-billing",
    owner_id: str = "dispatcher-dana",
    type: str = "delivered_load_closure",
    actor_type: str = "system",
    actor_id: str = "work-service",
    **kwargs: Any,
):
    return m.create(
        work_item_id=work_item_id, type=type, owner_id=owner_id,
        actor_type=actor_type, actor_id=actor_id, **kwargs,
    )


def a_human_decision(
    store: WorkflowStore,
    *,
    tenant: str = T_A,
    actor_id: str = "dispatcher-dana",
    actor_type: str = "human",
    event_name: str = "HumanDecided",
    seed: str = "decision-1",
    clock: Clock | None = None,
    aggregate_id: str | None = None,
    aggregate_version: int = 1,
    producer_transition_id: str = "WI-9",
    aggregate_type: str = AGGREGATE_TYPE,
    payload: dict[str, Any] | None = None,
) -> str:
    """Commit ONE canonical human-decision event and return its `event_id`.

    This is what a `decision_ref` of kind `AUDIT_EVENT` resolves against — the canonical event log,
    which `entities/17-audit-event.md` (points 8/15/17) makes the Audit Event itself. The fixture
    emits it through the REAL outbox for the same reason the P5 kit builds envelopes from contracts:
    a decision that never passed the contract gate would prove the resolver accepts things the
    producer would refuse.
    """
    now = format_instant((clock or Clock())())
    # ### THE AGGREGATE VARIES WITH THE SEED, AND THAT IS NOT COSMETIC. §4's transition-natural
    # identity is `(tenant, aggregate_type, aggregate_id, aggregate_version, transition, name)` and
    # the outbox enforces it UNIQUE. A fixture that pinned one aggregate id would make the SECOND
    # decision in a test collide with the first — reported as `DuplicateEmission`, which looks like
    # a machine defect and is actually the fixture minting one fact twice.
    # ER-13: a CONSEQUENTIAL contract must pin its decision context. Supplied from the contract's own
    # flag rather than per event, so the fixture cannot drift from `_check_consequential_pins`.
    pins: dict[str, Any] = {}
    if CONTRACTS[event_name].consequential:
        pins = {
            "entity_versions": {f"{aggregate_type}:{aggregate_id or seed}": aggregate_version},
            "policy_version": "pol-v1",
            "brake_version": "brk-v1",
        }
    envelope = EventEnvelope(
        event_id=deterministic_event_id(seed), event_name=event_name, event_version=1,
        occurred_at=now, recorded_at=now, tenant_id=tenant, aggregate_type=aggregate_type,
        aggregate_id=aggregate_id or f"wi-decision-{seed}", aggregate_version=aggregate_version,
        causation_id=None,
        correlation_id=f"corr-{seed}", producer_component="test",
        producer_transition_id=producer_transition_id, actor_type=actor_type, actor_id=actor_id,
        trace_id=f"trace-{seed}",
        payload=payload if payload is not None else minimal_payload(event_name),
        **pins,
    )
    conn = store.conn
    conn.execute("BEGIN IMMEDIATE")
    try:
        TransactionalOutbox(conn, tenant=tenant, clock=clock or Clock()).emit(envelope)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return envelope.event_id


def a_fired_age_timer(
    store: WorkflowStore,
    *,
    work_item_id: str,
    tenant: str = T_A,
    timer_id: str = "timer-age-1",
    kind: str = AGE_THRESHOLD_TIMER_KIND,
    state: str = "FIRED",
    aggregate_type: str = AGGREGATE_TYPE,
    clock: Clock | None = None,
) -> str:
    """A durable timer row in its post-fire state — the evidence WI-10's guard demands.

    Written directly rather than through `DurableTimers.schedule` + a relay pass, because the
    property under test is that WI-10 REFUSES without a real fired row; how the row got there is
    P5's certified business and not this unit's.
    """
    now = format_instant((clock or Clock())())
    conn = store.conn
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "INSERT INTO durable_timers (tenant, timer_id, aggregate_type, aggregate_id, "
            " timer_kind, fire_at, state, scheduled_at, fired_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (tenant, timer_id, aggregate_type, work_item_id, kind, now, state, now,
             now if state == "FIRED" else None),
        )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return timer_id


def outbox_events(store: WorkflowStore, *, tenant: str = T_A) -> list[dict[str, Any]]:
    return [
        {"event_id": r["event_id"], "event_name": r["event_name"],
         "aggregate_id": r["aggregate_id"], "aggregate_version": int(r["aggregate_version"]),
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


def state_digest(store: WorkflowStore, *, tenant: str = T_A) -> str:
    """A byte-level fingerprint of everything this tenant's M1 surface holds.

    ### THIS IS WHAT MAKES "NO-OP" A MEASUREMENT RATHER THAN A CLAIM. A redelivery case asserts the
    digest is byte-identical across the second delivery; without it, "nothing happened" is the
    absence of an assertion.
    """
    parts: list[str] = []
    for table, order in (
        ("work_items", "work_item_id"),
        ("tenant_humans", "human_id"),
        ("event_outbox", "sequence"),
        ("event_inbox", "event_id"),
        ("security_events", "id"),
    ):
        for row in store.conn.execute(
            f"SELECT * FROM {table} WHERE tenant = ? ORDER BY {order}", (tenant,)
        ).fetchall():
            parts.append(f"{table}|" + "|".join(f"{k}={row[k]!r}" for k in row.keys()))
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
