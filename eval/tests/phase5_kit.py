"""Shared builders and oracles for the P5 event-transport battery. NOT a test module.

Boring on purpose, exactly like `phase3_kit`: fresh tenant-bound stores over tmp databases, a
controllable clock (nothing here may depend on the wall clock), one green envelope every hostile
case perturbs, and the two oracles the whole unit is judged against —

    ATOMICITY  a state change and its event are BOTH present or BOTH absent. Never one.
    NO-OP      a redelivered event leaves the consumer's state digest UNCHANGED and its handler
               uncalled a second time.

`deterministic_event_id` exists because §1 requires a UUID v4 and a test battery requires
reproducible ids. It derives one from a seed by setting the version and variant bits — a real v4
by shape, a fixture by provenance.
"""

from __future__ import annotations

import hashlib
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
for entry in (str(ROOT / "src"), str(ROOT / "eval")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from freight_recon.event_contracts import (  # noqa: E402
    CONTRACTS,
    CanonicalContract,
    contract_for,
)
from freight_recon.event_envelope import EventEnvelope, format_instant  # noqa: E402
from freight_recon.event_inbox import DedupInbox  # noqa: E402
from freight_recon.event_outbox import (  # noqa: E402
    OutboxRelay,
    TransactionalOutbox,
    transactional_emit,
)
from freight_recon.workflow import WorkflowStore  # noqa: E402

T_A = "tenant-alpha"
T_B = "tenant-beta"

EPOCH = datetime(2026, 8, 12, 9, 0, 0, tzinfo=timezone.utc)


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
    digest = hashlib.sha256(seed.encode("utf-8")).digest()[:16]
    raw = bytearray(digest)
    raw[6] = (raw[6] & 0x0F) | 0x40      # version 4
    raw[8] = (raw[8] & 0x3F) | 0x80      # RFC-4122 variant
    return str(uuid.UUID(bytes=bytes(raw)))


def make_store(tmp_path: Path, tenant: str = T_A, name: str = "p5.db") -> WorkflowStore:
    return WorkflowStore(tmp_path / name, tenant=tenant)


def canonical_payload(contract: CanonicalContract) -> dict[str, Any]:
    """A minimal payload that SATISFIES `contract` — every required fact, and nothing more.

    Derived from the contract rather than written per event, so this cannot drift from the
    specification and cannot quietly stop covering a field that was added to one. Optional fields
    are deliberately omitted: the minimal satisfying body is the one that proves the contract is
    satisfiable, and an over-full fixture would hide a field wrongly marked optional.
    """
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
        if group.required:
            payload[group.members[0]] = f"{group.members[0]}-value"
    return payload


# §5's pins, supplied at the ENVELOPE level for a consequential contract. `entity_versions` is
# written `type:id` because that is the form `DedupInbox.consume` derives its `requires` set from.
def _consequential_pins(aggregate_type: str, aggregate_id: str) -> dict[str, Any]:
    return {
        "entity_versions": {f"{aggregate_type}:{aggregate_id}": 1},
        "policy_version": "policy-v1",
        "brake_version": "brake-v1",
    }


def make_envelope(
    *,
    seed: str | None = None,
    tenant: str = T_A,
    event_name: str = "CheckpointPassed",
    aggregate_type: str | None = None,
    aggregate_id: str = "pi-4471",
    aggregate_version: int = 1,
    producer_transition_id: str | None = None,
    clock: Clock | None = None,
    **overrides: Any,
) -> EventEnvelope:
    """The green envelope: a genuinely CANONICAL event. Every hostile case perturbs this.

    ### THE ENVELOPE IS BUILT FROM ITS CONTRACT, NOT FROM CONSTANTS. `aggregate_type`,
    `producer_transition_id` and the payload all default to what
    `docs/specifications/events/registry.md` declares for `event_name`, so naming any of the 118
    contracts yields a valid event without the caller restating its contract. That matters for more
    than convenience: before U5.3 this fixture emitted a `CheckpointPassed` whose payload was
    `{"pipeline_instance_id": ...}` — a shape the specification never declared — and the whole
    transport battery was green against a fact that was not canonical. Deriving the fixture is what
    stops that being possible again.

    A caller may still override any of it, and hostile cases do exactly that.
    """
    contract = CONTRACTS.get(event_name)
    if aggregate_type is None:
        aggregate_type = (contract.aggregate_type if contract and contract.aggregate_type
                          else "pipeline_instance")
    if producer_transition_id is None:
        producer_transition_id = (contract.producers[0] if contract and contract.producers
                                  else "PL-8")

    now = format_instant((clock or Clock())())
    fields: dict[str, Any] = {
        "event_id": deterministic_event_id(
            seed or f"{tenant}|{aggregate_type}|{aggregate_id}|{aggregate_version}|{event_name}"
        ),
        "event_name": event_name,
        "event_version": 1,
        "occurred_at": now,
        "recorded_at": now,
        "tenant_id": tenant,
        "aggregate_type": aggregate_type,
        "aggregate_id": aggregate_id,
        "aggregate_version": aggregate_version,
        "causation_id": None,
        "correlation_id": "corr-4471",
        "producer_component": "m2-pipeline",
        "producer_transition_id": producer_transition_id,
        "actor_type": "system",
        "actor_id": "system",
        "trace_id": "trace-4471",
        "payload": canonical_payload(contract) if contract else {},
    }
    if contract is not None:
        if contract.consequential:
            fields.update(_consequential_pins(aggregate_type, aggregate_id))
        # ER-11/ER-12: a contract whose family file declares `actor_type=human` ONLY.
        # ER-10: and any contract whose own payload FIXES `provenance_class=OWNER_ASSERTED`
        # — `ClaimCorrected` does exactly that, so a system-actor version of it is not merely
        # untidy, it is the laundering ER-10 forbids. Both are read from the CONTRACT rather than
        # listed here, so a newly minted contract carrying either constraint is covered the day it
        # is minted. (An earlier version hardcoded three names and silently stopped covering
        # `ApprovalGranted` and `RuleActivated` when the derived set grew to six.)
        if (contract.human_only
                or fields["payload"].get("provenance_class") == "OWNER_ASSERTED"):
            fields["actor_type"] = "human"
            fields["actor_id"] = "ops-lead-1"
    fields.update(overrides)
    return EventEnvelope(**fields)


def a_contract_on(aggregate_type: str) -> str:
    """The name of a canonical contract that lives on `aggregate_type`.

    Discovered from the registry, never enumerated: a case parameterized over the strict-order
    aggregate types needs a REAL contract for each one, and hardcoding a name per type is how a
    parameterized case quietly stops covering a family whose contracts were renamed.
    """
    names = sorted(n for n, c in CONTRACTS.items() if c.aggregate_type == aggregate_type)
    if not names:
        raise AssertionError(
            f"no canonical contract declares aggregate_type={aggregate_type!r}; the case that "
            f"asked for one would otherwise have tested nothing"
        )
    return names[0]


def make_canonical_envelope(event_name: str, **overrides: Any) -> EventEnvelope:
    """`make_envelope` for a named contract, refusing a name the registry does not declare.

    `make_envelope` tolerates an unknown name on purpose — hostile cases need to build one. This
    wrapper is for the exhaustive sweeps, where a typo must fail rather than silently test nothing.
    """
    contract_for(event_name)
    return make_envelope(event_name=event_name, **overrides)


# --------------------------------------------------------------------------- the state change

# A real canonical row, not a scratch table: the platform brake's monotonic version is a genuine
# durable state change, and asserting "the state change and the event are both there, or neither"
# against a table the rest of the system already trusts is stronger than inventing one.
STATE_CHANGE_SQL = "UPDATE platform_brake SET brake_version = brake_version + 1 WHERE id = 1"


def brake_version(store: WorkflowStore) -> int:
    return int(store.conn.execute("SELECT brake_version FROM platform_brake WHERE id = 1")
               .fetchone()[0])


def emit_with_state_change(
    store: WorkflowStore, envelope: EventEnvelope, *, clock: Clock | None = None,
) -> None:
    """The M-23 shape: one transaction carrying a state change and the event it emitted."""
    with transactional_emit(store.conn, tenant=envelope.tenant_id, clock=clock) as session:
        session.execute(STATE_CHANGE_SQL)
        session.emit(envelope)


# ---------------------------------------------------------------------------------- factories

def make_outbox(store: WorkflowStore, *, tenant: str = T_A, clock: Clock | None = None):
    return TransactionalOutbox(store.conn, tenant=tenant, clock=clock)


class RecordingSink:
    """A publish sink that records every delivery, and can be told to crash.

    `crash_after_publish` is the AC-RACE-007 shape: the event REALLY LEFT (it is in `delivered`)
    and then the relay died before it could mark the row. `crash_before_publish` is AC-RACE-006:
    nothing left at all.
    """

    def __init__(self) -> None:
        self.delivered: list[EventEnvelope] = []
        self.crash_before_publish = False
        self.crash_after_publish = False

    def __call__(self, envelope: EventEnvelope) -> None:
        if self.crash_before_publish:
            raise RuntimeError("simulated relay crash BEFORE publish")
        self.delivered.append(envelope)
        if self.crash_after_publish:
            raise RuntimeError("simulated relay crash AFTER publish, before mark-published")

    @property
    def event_ids(self) -> list[str]:
        return [e.event_id for e in self.delivered]

    @property
    def digests(self) -> list[str]:
        return [e.digest() for e in self.delivered]


def make_relay(
    store: WorkflowStore,
    sink: RecordingSink,
    *,
    tenant: str = T_A,
    relay_id: str = "relay-1",
    clock: Clock | None = None,
    lease: timedelta = timedelta(seconds=30),
) -> OutboxRelay:
    return OutboxRelay(store.conn, tenant=tenant, publish=sink, relay_id=relay_id,
                       clock=clock or Clock(), lease=lease)


class RecordingHandler:
    """A consumer handler that writes durable state, so "did it happen twice" is a QUERY.

    It appends to `applied` (an in-process witness) AND increments the brake version (a durable
    one). The durable side is what the state-digest oracle reads: a duplicate that ran the handler
    twice would move the digest, and no amount of careful assertion-writing could hide it.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self.applied: list[EventEnvelope] = []

    def __call__(self, envelope: EventEnvelope) -> None:
        self.applied.append(envelope)
        self._conn.execute(STATE_CHANGE_SQL)

    @property
    def event_ids(self) -> list[str]:
        return [e.event_id for e in self.applied]


def agnostic_drain(handler):
    """Opt a consumption into the post-apply drain cascade — the honest way, for a handler that
    genuinely has no per-event semantics to get wrong.

    ### WHY THIS IS A NAMED HELPER AND NOT AN INLINE `lambda e: handler`. The cascade is opt-in
    (F-04) because replaying somebody else's parked event through the CURRENT invocation's handler
    lets event A be executed under event B's trigger and facts. `RecordingHandler` is immune to that
    by construction: it reads only the envelope it is handed and derives nothing from the event that
    seeded the drain, so "the handler for THAT envelope" and "this handler" are the same function.
    That is a property of THIS handler, not a property of handlers, and writing it down here keeps a
    future caller from copying the opt-in to a handler for which it is false — which is exactly how
    M1 acquired the defect.
    """
    return lambda envelope: handler


class FailingHandler:
    """A handler that raises after writing — the consumer-crash-mid-transaction shape."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self.calls = 0

    def __call__(self, envelope: EventEnvelope) -> None:
        self.calls += 1
        self._conn.execute(STATE_CHANGE_SQL)
        raise RuntimeError("simulated consumer crash inside the handler")


def make_inbox(
    store: WorkflowStore,
    *,
    tenant: str = T_A,
    consumer_id: str = "consumer-m2",
    clock: Clock | None = None,
    **kwargs: Any,
) -> DedupInbox:
    return DedupInbox(store.conn, tenant=tenant, consumer_id=consumer_id,
                      clock=clock or Clock(), **kwargs)


# ------------------------------------------------------------------------------------ oracles

def state_digest(store: WorkflowStore) -> str:
    """A digest over every row the transport and its consumers can touch.

    Deliberately WIDE and deliberately EXCLUDING the outbox's delivery bookkeeping: a redelivery
    legitimately moves `publish_attempts`, and a digest that moved with it could never answer
    "did the duplicate change anything that MATTERS".
    """
    parts: list[str] = []
    for sql in (
        "SELECT brake_version FROM platform_brake WHERE id = 1",
        "SELECT tenant, event_id, envelope_digest, sequence FROM event_outbox ORDER BY tenant, sequence",
        "SELECT tenant, consumer_id, event_id, outcome FROM event_inbox "
        " ORDER BY tenant, consumer_id, event_id",
        "SELECT tenant, consumer_id, aggregate_type, aggregate_id, applied_version "
        "  FROM inbox_aggregate_cursor ORDER BY tenant, consumer_id, aggregate_type, aggregate_id",
        "SELECT tenant, consumer_id, event_id, park_state, park_reason FROM pending_references "
        " ORDER BY tenant, consumer_id, arrival_sequence",
    ):
        for row in store.conn.execute(sql).fetchall():
            parts.append("|".join(str(v) for v in tuple(row)))
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def outbox_rows(store: WorkflowStore, tenant: str = T_A) -> list[sqlite3.Row]:
    return store.conn.execute(
        "SELECT * FROM event_outbox WHERE tenant = ? ORDER BY sequence", (tenant,)
    ).fetchall()


def inbox_rows(store: WorkflowStore, tenant: str = T_A) -> list[sqlite3.Row]:
    return store.conn.execute(
        "SELECT * FROM event_inbox WHERE tenant = ? ORDER BY event_id", (tenant,)
    ).fetchall()


def assert_atomic(store: WorkflowStore, *, expect_event: bool, baseline_version: int) -> None:
    """M-23's universal oracle: the state change and the event agree about whether they happened.

    Both, or neither. A run that produced one of them is the dual write, and there is no shape of
    it that this unit is allowed to pass.
    """
    rows = outbox_rows(store)
    moved = brake_version(store) != baseline_version
    if expect_event:
        assert rows, "the transaction committed but no outbox row exists — the event was lost"
        assert moved, "an outbox row exists but the state change did not commit"
    else:
        assert not rows, (
            f"the transaction rolled back but {len(rows)} outbox row(s) survive — an event now "
            f"asserts a transition that never happened"
        )
        assert not moved, (
            "the transaction rolled back but the state change survives — the action was taken and "
            "is unrecorded (I10)"
        )
