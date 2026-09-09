"""### CRASHING A TRANSITION ON PURPOSE, SO "CRASH RECOVERY REACHES THE CANONICAL STATE" IS MEASURED.

`foundational-machine-acceptance.md`'s mandatory assertion 8 requires that a crash at a transition
leaves the machine at its canonical state. Four machines — M5, M11, M12, M13 — had no such case, and
the reason is that a crash is hard to stage honestly: monkeypatching a method proves the mock raises,
and killing a connection proves SQLite rolls back. Neither says anything about the MACHINE.

### SO THE CRASH IS STAGED THROUGH THE REAL WRITE PATH. Every P6 transition runs

        BEGIN IMMEDIATE  ->  UPDATE the aggregate row  ->  emit to `event_outbox`  ->  COMMIT

inside one transaction (GR-2: the row and its event, or neither). `event_outbox` carries
`UNIQUE (tenant, idempotency_identity)`, and §4's identity is transition-natural and therefore
PREDICTABLE:

        tn_v1|<tenant>|<aggregate_type>|<aggregate_id>|<version>|<transition>|<event>

Planting a row on that key makes the emission — the SECOND half of the transaction, after the row has
already been written — fail. The interruption therefore lands exactly where a crash is dangerous: the
row is updated in the open transaction and the event is not yet durable. What the tests then assert is
what a crash must never be able to break:

  * the aggregate row did NOT move and its version did NOT advance (the UPDATE went back);
  * no event was recorded;
  * a FRESH machine over the same database reads the canonical pre-crash state; and
  * the transition still completes exactly once on retry.

A machine that committed its row before its event, or swallowed the emission failure, or left the
version advanced, fails these. `scripts/mutate_phase6_ac5_evidence.py` injects exactly those defects
and shows each test going red."""

from __future__ import annotations

import sqlite3
import uuid
from typing import Any


def transition_natural_identity(
    tenant: str, aggregate_type: str, aggregate_id: str, aggregate_version: int,
    transition_id: str, event_name: str,
) -> str:
    """§4's identity, reproduced here so a test can plant a collision on the event a transition is
    ABOUT to emit. Kept in step with `EventEnvelope.transition_natural_identity` by
    `test_the_planted_identity_matches_the_envelopes_own`."""
    return "|".join((
        "tn_v1", tenant, aggregate_type, aggregate_id, str(aggregate_version),
        transition_id, event_name,
    ))


def outbox_count(conn: sqlite3.Connection, tenant: str) -> int:
    return int(conn.execute(
        "SELECT COUNT(*) FROM event_outbox WHERE tenant = ?", (tenant,)).fetchone()[0])


def next_emission_version(
    conn: sqlite3.Connection, tenant: str, aggregate_type: str, aggregate_id: str,
) -> int:
    """The `aggregate_version` the NEXT emission on this aggregate will carry.

    ### THIS IS THE EVENT STREAM'S OWN COUNTER, NOT THE ROW'S `version` COLUMN, AND THEY ARE NOT THE
    SAME NUMBER. A transition that emits two contracts (M11's PO-6 emits `PolicyRevoked` AND
    `PolicyVersionChanged`) advances the stream twice and the row once, so deriving the identity from
    the row would plant the collision on the wrong key and the crash would never be staged. Read from
    the stream, so a transition that grows a second event still stages correctly."""
    row = conn.execute(
        "SELECT MAX(aggregate_version) FROM event_outbox "
        "WHERE tenant = ? AND aggregate_type = ? AND aggregate_id = ?",
        (tenant, aggregate_type, aggregate_id)).fetchone()
    return int(row[0] or 0) + 1


def plant_colliding_emission(
    conn: sqlite3.Connection, tenant: str, *, aggregate_type: str, aggregate_id: str,
    transition_id: str, event_name: str, aggregate_version: int | None = None,
) -> str:
    """Occupy the outbox identity the next transition will emit on, so its emission raises.

    The planted row is a copy of an existing envelope with a fresh `event_id`, a sequence far past the
    real ones and the target identity — it is scaffolding for the failure, never something a test
    asserts about. Returns the identity it occupied."""
    if aggregate_version is None:
        aggregate_version = next_emission_version(conn, tenant, aggregate_type, aggregate_id)
    identity = transition_natural_identity(
        tenant, aggregate_type, aggregate_id, aggregate_version, transition_id, event_name)
    template = conn.execute(
        "SELECT * FROM event_outbox WHERE tenant = ? ORDER BY sequence LIMIT 1", (tenant,)).fetchone()
    if template is None:
        raise AssertionError(
            f"no event has been emitted for tenant {tenant!r} yet, so there is no envelope to copy. "
            f"Drive the machine to the state under test before staging the crash.")
    row: dict[str, Any] = dict(template)
    row["event_id"] = str(uuid.uuid4())
    row["idempotency_identity"] = identity
    row["sequence"] = 10_000 + int(row["sequence"] or 0)
    conn.execute(
        f"INSERT INTO event_outbox ({','.join(row)}) VALUES ({','.join('?' * len(row))})",
        tuple(row.values()))
    conn.commit()
    return identity
