# P5 U5.7 + U5.8 — transactional outbox and dedup inbox: implementer evidence

**Checkpoint:** `P5-CP-1`. **Content commit:** the U5.7+U5.8 replacement candidate.
**Suite at the evidenced tree:** 2267 passed / 0 failed / 3 skipped.

## What landed

P5's first runtime capability. Before this, `IMPLEMENTATION-SURFACE.yaml` recorded outbox and inbox
as `SPECIFICATION_ONLY`. A state change and the events it emits now land in **one commit or
neither**; a relay publishes at-least-once under lease exclusivity; and a redelivered event is a
**no-op** rather than a second effect.

Built as one unit because `AC-RACE-006` spans both halves — *"outbox crash before publish | the relay
re-sends the identical `event_id` ⇒ **inbox no-op**"*. An outbox alone cannot satisfy it.

## Design

Four tenant-first tables in `src/freight_recon/migrations/phase5_event_transport.py`:

| table | key facts |
|---|---|
| `event_outbox` | per-tenant monotonic `sequence`; `UNIQUE(tenant, idempotency_identity)`; envelope columns immutable by trigger |
| `event_inbox` | PK `(tenant, consumer_id, event_id)`; append-only |
| `inbox_aggregate_cursor` | per-aggregate applied version |
| `pending_references` | parked events whose aggregate does not exist yet, with TTL |

Wired into `schema.py`'s single readiness oracle at six points, so the transport is validated by the
**same** tenant-first contract as every other table — no exemption.

**Atomicity is structural, not conventional.** `TransactionalOutbox` takes an existing
`sqlite3.Connection` and `emit` **refuses to run outside an open transaction**. There is no
`allow_autocommit` flag, and an AST guard asserts no parameter shaped like one exists. Verified by the
review on an `isolation_level=None` connection: refused; and with an explicit `BEGIN IMMEDIATE` on
that same connection, rollback leaves zero rows.

**Idempotency** is keyed `(tenant, consumer_id, event_id)`. The handler runs *inside* the inbox
transaction, so a handler exception rolls back its writes and the inbox row together. The same
`event_id` from a *different* `consumer_id` correctly does **not** dedup.

**Serialization.** `ev_v1` reuses `fingerprint.Money` and fp_v1's rules (NFC, bytewise-sorted keys,
floats forbidden) over a JSON tree, because fp_v1's flat form cannot represent
`ConflictRaised.parties[]`. The stored bytes *are* the canonical bytes, so a redelivery is
byte-identical by construction.

## The ordering defect found and fixed during the build

The first design enforced strict per-aggregate ordering with
`UNIQUE(tenant, aggregate_type, aggregate_id, aggregate_version)`. That reads correctly and **would
have made the canonical claim path uninsertable at P6**: `EF-2` legitimately emits `GrantClaimed`
*and* `EffectAttempted` on one `effect_grant` at one version.

Replaced by `trg_event_outbox_strict_version_owner`, which enforces the invariant that actually
holds — **no two DIFFERENT producer transitions may own one version** — and which no index can
express. The inbox carried the mirror bug: a cursor treating `version <= applied` as stale would have
silently discarded `EffectAttempted`. Both halves fixed; the independent review confirmed the fix is
complete, that the trigger is correctly tenant-scoped, and that gap-parking plus drain reassembles
1,2,3 in order regardless of arrival order.

## Scenarios exercised — 133 nodes in `eval/tests/test_phase5_event_transport.py`

Crash between state-write and event-write, and between event-write and commit: **neither survives**,
traced from the SQLite statement stream (exactly one BEGIN/COMMIT spanning both). Crash before
publish: identical `event_id` and digest re-sent; a dead relay's lease expires and a *different*
relay re-sends it. Crash after publish: duplicate delivery absorbed, state digest byte-identical.
Consumer crash before inbox commit: reprocessed to the same digest as a clean run; after: not
reprocessed, across a real restart. Two concurrent relays: 6 events, 6 deliveries, zero overlap.
Cross-tenant: rejected before the handler and before any write, digest unchanged,
`CrossTenantAccessAttempted` observed. Malformed: one node per required envelope field plus 12
field-level refusals. Dangling references: parked, drained in arrival order, TTL expiry returns the
accountable owner.

## Production stays dark

The relay has no default sink and refuses construction without an explicit `publish` callable; the
transport modules import no adapter or network client (asserted by AST over a **discovered** module
population, not a hand-typed list); consuming events yields 0 checkpoint witnesses and 0 effect
grants; `GateRegistry` is constructed nowhere in `src/`; the Phase-8 deferral is intact.

## Migration posture

Existing databases are **not** auto-migrated (`WorkflowStore` only builds empty ones).
`scripts/migrate_phase5_event_transport.py` handles them; exercised dry-run → apply → idempotent
rerun, and a migrated database's `sqlite_master` is byte-identical to a fresh one. A
partially-applied migration is reported by the readiness oracle and repaired by re-running. The
marker is written last. `phase2_tenant_first.migrate()` gained a STEP 10 for the same reason it has a
STEP 9.

## Deliberately not built

The 105 event contracts and upcasters (U5.3 — `event_name` is shape-validated only, no whitelist),
GC-1 (U5.4), the replay sandbox (U5.5), audit reconstruction (U5.6), and **PostgreSQL**. ADR-016's
production store does not exist; this is SQLite only, so P5's persistence half is untouched. TTL
expiry returns `ExpiredReference` objects rather than minting `ExceptionRaised`, because M9 is P6.

**No P5 acceptance criterion is scored by this checkpoint.** All 14 remain `PENDING`; `status` stays
`READY`; this is `CHECKPOINT_ACCEPTED_FOR_CONTINUATION`, not phase acceptance.
