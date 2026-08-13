"""Phase 5 — the durable event transport: the transactional OUTBOX and the dedup INBOX.

WHY THIS SCHEMA EXISTS

I10 says a consequential action is never taken and unrecorded. Until there is a table, that is a
slogan. ADR-008 §2.5 and M-23 turn it into a database guarantee:

    UPDATE machine_state (version++)  +  INSERT INTO event_outbox   -- ONE transaction. Both, or
                                                                    -- neither.

A relay then publishes from the outbox at-least-once and marks rows published. That "at-least-once"
is not a weakness to be apologised for; it is the only honest posture, because there is no instant
at which "published" and "recorded as published" are the same event. The system is therefore built
so that a second delivery costs nothing: M-24's inbox, keyed `(consumer_id, tenant, event_id)`,
with processing and inbox-insert in ONE commit, makes redelivery a no-op rather than a second
effect.

    The outbox alone cannot satisfy `AC-RACE-006`, and the inbox alone cannot satisfy it either.
    "The relay re-sends the identical event_id ⇒ INBOX NO-OP" is one sentence spanning both halves.
    That is why they are one schema.

WHAT EACH TABLE IS FOR

  event_outbox           the durable emission record. Written in the producing transition's OWN
                         commit; immutable except for its delivery bookkeeping; never deleted.
  event_inbox            the consumption record. `(tenant, consumer_id, event_id)` is the dedup
                         identity of events/registry.md §4 field 20. Fully append-only.
  inbox_aggregate_cursor per (consumer, aggregate) high-water mark. It is what makes STRICT
                         per-aggregate ordering (§8: F2, F3, F4, F11, F13) a mechanism rather than
                         a hope: a version gap parks instead of applying out of order.
  pending_references     M-26 parking. An event naming an aggregate that does not exist YET is
                         neither dropped nor failed; it is parked with its arrival order and a TTL,
                         drained in that order when the referent appears, and on TTL expiry becomes
                         a loud, owned problem instead of a log line.

TENANT SPELLING — DELIBERATE, AND NOT A DEVIATION

The event registry names the envelope field `tenant_id`. This repository has exactly ONE physical
tenant column, `tenant` (migrations/phase2_tenant_first.py, schema.py TENANT_COLUMN), and the whole
Phase-2 tenant-first oracle — nullability, no DEFAULT, tenant-FIRST primary keys, cross-tenant
foreign keys — is written against that name. A second spelling would buy literal fidelity to one
document and cost enforcement by every guard the repository already owns. So the envelope field
stays `tenant_id` in the event and the column stays `tenant` in the database, and these tables are
validated by the same oracle as every other tenant-owned table.

For the same reason `event_inbox`'s primary key is `(tenant, consumer_id, event_id)` rather than the
registry's written order `(consumer_id, tenant_id, event_id)`. The UNIQUENESS DOMAIN is identical —
a primary key is a set, not a sequence — but tenant-first is [C-1] and is checked structurally, and
a key whose first column is `consumer_id` would be reported unready by `schema_readiness_problems`.

WHAT IS DELIBERATELY *NOT* HERE

No `commit_key` column, on any table. The Commit Key is the identity of one logical EXTERNAL EFFECT
(ADR-009) and lives in exactly one ledger, `effect_grants`. An outbox row is the record of a FACT,
not a reservation of an effect, and merging the two identities is forbidden (CLAIMED rule 8). A
second table carrying `commit_key` + `state` would be a second effect authority, and
`schema.py::_second_ledger_problems` would say so.

No event-name whitelist. The canonical 105 (`events/registry.md` §3) and their per-contract payloads
are U5.3's; a `CHECK (event_name IN (...))` here would be this unit minting that registry by the
back door, and it would be wrong the first time a contract was added.
"""

from __future__ import annotations

import sqlite3

MIGRATION_ID = "phase5_event_transport"
P5_SCHEMA_VERSION = "phase5-event-transport-1"

# Tenant-owned, every one of them. There is no platform-scoped event: [C-1] makes tenant the FIRST
# partition dimension of every store, stream and inbox, and an event without a tenant is an event
# nobody owns.
P5_TENANT_TABLES: tuple[str, ...] = (
    "event_outbox",
    "event_inbox",
    "inbox_aggregate_cursor",
    "pending_references",
)

# Nothing here is tenant-exempt. Recorded explicitly rather than omitted, so that a future addition
# has to state its exemption and defend it, exactly as P3 had to defend `platform_brake`.
P5_EXEMPT_TABLES: tuple[str, ...] = ()

# The two outbox delivery states. There is no 'FAILED': a publish that failed is a publish that has
# not happened yet, and the relay retries it. A terminal failure state would be a place for an
# event to die quietly, which is the one thing I10 forbids.
DELIVERY_STATES: tuple[str, ...] = ("PENDING", "PUBLISHED")

# What the inbox records about an event it has finished with. Both are terminal and both mean
# "never process this event again for this consumer".
INBOX_OUTCOMES: tuple[str, ...] = ("APPLIED", "STALE_NOOP")

# Why an event is parked (M-26, events/registry.md §8).
PARK_REASONS: tuple[str, ...] = ("MISSING_AGGREGATE", "VERSION_GAP")

# The lifecycle of a parked row. DRAINED and EXPIRED are terminal; neither deletes the row, because
# "we parked this and then it went away" must remain answerable.
PARK_STATES: tuple[str, ...] = ("PARKED", "DRAINED", "EXPIRED")

# The aggregate types whose events require STRICT per-aggregate ordering (events/registry.md §8:
# F2 Pipeline, F3 External Effect/Grant, F4 Approval, F11 Policy, F13 Brake — "their
# version-monotonic transitions depend on it"). Keyed on `aggregate_type` rather than on event name
# because the ordering key IS `(tenant_id, aggregate_id, aggregate_version)` and the aggregate is
# what it orders; keying on the event name would require this unit to own the 105-name registry,
# which is U5.3's.
STRICT_ORDER_AGGREGATE_TYPES: tuple[str, ...] = (
    "pipeline_instance",   # F2
    "effect_grant",        # F3
    "approval",            # F4
    "policy",              # F11
    "brake",               # F13
)

_STRICT_SQL_LIST = ",".join(f"'{t}'" for t in STRICT_ORDER_AGGREGATE_TYPES)

# The exact text the strict-version-ownership trigger aborts with. Named here, and matched by
# `event_outbox.py` when it classifies a `sqlite3.IntegrityError`, so the two cannot drift: SQLite
# reports a trigger RAISE(ABORT) and a UNIQUE violation through the SAME exception type, and
# reporting "this event is already emitted" for an ordering violation would send the reader
# looking for a duplicate that does not exist.
STRICT_ORDER_ABORT = (
    "two DIFFERENT transitions claim one (tenant, aggregate, version) in a family that requires "
    "strict per-aggregate ordering [events/registry.md sec 8]"
)


P5_TARGET_SCHEMA: dict[str, str] = {
    # THE TRANSACTIONAL OUTBOX (ADR-008 §2.5, M-23, entities/17-audit-event.md §15).
    #
    # Written by `event_outbox.TransactionalOutbox.emit` INSIDE the producing transition's open
    # transaction — the module refuses to write outside one, so "the event was written in its own
    # commit" is not reachable through the supported API.
    #
    # Immutable except for the five delivery-bookkeeping columns; the triggers below enforce that,
    # so the immutability of the envelope survives an admin with a connection (S8: append-only, no
    # UPDATE/DELETE of history).
    "event_outbox": """
        CREATE TABLE event_outbox (
            tenant TEXT NOT NULL,
            event_id TEXT NOT NULL,
            event_name TEXT NOT NULL,
            event_version INTEGER NOT NULL,
            envelope_schema_version INTEGER NOT NULL,
            aggregate_type TEXT NOT NULL,
            aggregate_id TEXT NOT NULL,
            aggregate_version INTEGER NOT NULL,
            producer_transition_id TEXT NOT NULL,
            correlation_id TEXT NOT NULL,
            -- NULL only for a root ingress event (events/registry.md sec 1). Nullable by design.
            causation_id TEXT,
            -- sec 4 field 20's dedup key BEYOND event_id: transition-natural for internal events,
            -- source-natural for externally-observed ones. UNIQUE per tenant below, which is what
            -- makes a re-run of the same transition a refusal rather than a second event.
            idempotency_identity TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            -- The canonical ev_v1 serialization of the WHOLE envelope, and its digest. Storing the
            -- canonical bytes rather than a re-serialization means a redelivery is byte-identical
            -- by construction and tampering is detectable without a second source of truth.
            envelope_json TEXT NOT NULL,
            envelope_digest TEXT NOT NULL,
            -- Per-tenant monotonic arrival order. The relay claims and publishes in this order, so
            -- within one aggregate the publication order IS the version order.
            sequence INTEGER NOT NULL,
            delivery_state TEXT NOT NULL CHECK (delivery_state IN ('PENDING','PUBLISHED')),
            published_at TEXT,
            publish_attempts INTEGER NOT NULL DEFAULT 0,
            -- The relay lease. Two relays cannot claim the same row; a crashed relay's lease
            -- expires and the row is re-claimed, which is precisely AC-RACE-006/007's recovery.
            leased_by TEXT,
            lease_expires_at TEXT,
            PRIMARY KEY (tenant, event_id),
            UNIQUE (tenant, idempotency_identity),
            UNIQUE (tenant, sequence),
            CHECK (event_version >= 1),
            CHECK (envelope_schema_version >= 1),
            CHECK (aggregate_version >= 1),
            CHECK (recorded_at >= occurred_at),
            CHECK (delivery_state != 'PUBLISHED' OR published_at IS NOT NULL),
            CHECK (delivery_state != 'PENDING' OR published_at IS NULL)
        )""",
    # THE DEDUP INBOX (ADR-008 sec 2.6, M-24, events/registry.md sec 4).
    #
    # One row per (tenant, consumer, event). The row and the consumer's own state change are
    # written in ONE commit, so a duplicate delivery finds the row present and does nothing, and a
    # consumer crash before the commit leaves no row and is simply reprocessed.
    #
    # Fully append-only: there is no legitimate reason to revise the record of a consumption, and
    # an UPDATE would be exactly how a redelivery becomes a second effect.
    "event_inbox": """
        CREATE TABLE event_inbox (
            tenant TEXT NOT NULL,
            consumer_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            event_name TEXT NOT NULL,
            aggregate_type TEXT NOT NULL,
            aggregate_id TEXT NOT NULL,
            aggregate_version INTEGER NOT NULL,
            envelope_digest TEXT NOT NULL,
            outcome TEXT NOT NULL CHECK (outcome IN ('APPLIED','STALE_NOOP')),
            consumed_at TEXT NOT NULL,
            PRIMARY KEY (tenant, consumer_id, event_id),
            CHECK (aggregate_version >= 1)
        )""",
    # THE PER-AGGREGATE HIGH-WATER MARK.
    #
    # Ordering is per-aggregate and there is NO global order (sec 8), so the cursor is per
    # aggregate too. For a STRICT aggregate type a version gap parks; for an order-tolerant one the
    # cursor still advances (it is what makes a late duplicate detectable) but a gap does not block.
    "inbox_aggregate_cursor": """
        CREATE TABLE inbox_aggregate_cursor (
            tenant TEXT NOT NULL,
            consumer_id TEXT NOT NULL,
            aggregate_type TEXT NOT NULL,
            aggregate_id TEXT NOT NULL,
            applied_version INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (tenant, consumer_id, aggregate_type, aggregate_id),
            CHECK (applied_version >= 0)
        )""",
    # M-26 PARKING. Neither dropped nor failed.
    #
    # One row per parked event, carrying the FIRST reference that blocked it. A retry re-evaluates
    # every reference from the stored envelope, so recording one blocker loses nothing and keeps
    # the drain key single-valued.
    #
    # `arrival_sequence` is what "drained in arrival order" is measured by, and it is per
    # (tenant, consumer) monotonic rather than per referent: two events parked against the same
    # missing aggregate must be replayed in the order they arrived, not in id order.
    "pending_references": """
        CREATE TABLE pending_references (
            tenant TEXT NOT NULL,
            consumer_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            referenced_type TEXT NOT NULL,
            referenced_id TEXT NOT NULL,
            park_reason TEXT NOT NULL CHECK (park_reason IN ('MISSING_AGGREGATE','VERSION_GAP')),
            park_state TEXT NOT NULL CHECK (park_state IN ('PARKED','DRAINED','EXPIRED')),
            arrival_sequence INTEGER NOT NULL,
            parked_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_attempt_at TEXT,
            resolved_at TEXT,
            -- The human who inherits this when the TTL expires (I1). Nullable while the reference
            -- may still resolve on its own; required to be named by the expiry path, which returns
            -- it rather than logging it.
            accountable_owner_id TEXT,
            envelope_json TEXT NOT NULL,
            PRIMARY KEY (tenant, consumer_id, event_id),
            UNIQUE (tenant, consumer_id, arrival_sequence),
            CHECK (expires_at > parked_at),
            CHECK (park_state = 'PARKED' OR resolved_at IS NOT NULL)
        )""",
}


P5_INDEXES: dict[str, str] = {
    # The relay's claim scan: pending rows for one tenant, in arrival order.
    "ix_event_outbox_pending":
        "CREATE INDEX ix_event_outbox_pending "
        "ON event_outbox (tenant, sequence) WHERE delivery_state = 'PENDING'",
    # Per-aggregate order lookups for every family, strict or not. Also the lookup the strict
    # version-ownership trigger below uses, so it is not merely a convenience.
    "ix_event_outbox_aggregate":
        "CREATE INDEX ix_event_outbox_aggregate "
        "ON event_outbox (tenant, aggregate_type, aggregate_id, aggregate_version)",
    # The drain scan: everything still parked against one referent, in arrival order.
    "ix_pending_references_drain":
        "CREATE INDEX ix_pending_references_drain "
        "ON pending_references (tenant, consumer_id, referenced_type, referenced_id, "
        "arrival_sequence) WHERE park_state = 'PARKED'",
    # The TTL sweep.
    "ix_pending_references_expiry":
        "CREATE INDEX ix_pending_references_expiry "
        "ON pending_references (tenant, expires_at) WHERE park_state = 'PARKED'",
}

# Nothing from an earlier phase is replaced by P5. Declared so the readiness oracle's shape matches
# P3's and a future replacement has somewhere to go.
P5_REPLACED_INDEXES: tuple[str, ...] = ()


# The columns an outbox row is ALLOWED to change after it is written. Everything else is history.
OUTBOX_MUTABLE_COLUMNS: tuple[str, ...] = (
    "delivery_state", "published_at", "publish_attempts", "leased_by", "lease_expires_at",
)
_OUTBOX_IMMUTABLE = (
    "tenant", "event_id", "event_name", "event_version", "envelope_schema_version",
    "aggregate_type", "aggregate_id", "aggregate_version", "producer_transition_id",
    "correlation_id", "causation_id", "idempotency_identity", "occurred_at", "recorded_at",
    "envelope_json", "envelope_digest", "sequence",
)

PARK_MUTABLE_COLUMNS: tuple[str, ...] = (
    "park_state", "attempts", "last_attempt_at", "resolved_at", "accountable_owner_id",
)
_PARK_IMMUTABLE = (
    "tenant", "consumer_id", "event_id", "referenced_type", "referenced_id", "park_reason",
    "arrival_sequence", "parked_at", "expires_at", "envelope_json",
)

# [S8] and [C-8]: history is append-only, and that is enforced by the DATABASE rather than by
# convention. `UPDATE OF <cols>` fires when a column is NAMED in the SET list, even if the value
# is unchanged - which is the semantics we want: an immutable column may not appear in an UPDATE
# at all, so there is no "it was the same value anyway" defence.
P5_TRIGGERS: dict[str, str] = {
    # ### STRICT PER-AGGREGATE VERSION OWNERSHIP (events/registry.md sec 8), and why this is a
    # TRIGGER rather than the UNIQUE index it looks like it should be.
    #
    # The invariant the strict families actually need is that their transitions are
    # VERSION-MONOTONIC: no two DIFFERENT transitions may produce the same
    # (tenant, aggregate, version). It is NOT "one event per version" - EF-2 emits `GrantClaimed`
    # AND `EffectAttempted` in one commit on one `effect_grant` at one version
    # (state-machines/03-external-effect-grant.machine.md), and sec 11.4 says "the transition and
    # the EVENTS it emits", plural. A UNIQUE index over (tenant, aggregate_type, aggregate_id,
    # aggregate_version) would have looked exactly right and would have made EF-2 uninsertable.
    #
    # "At most one distinct producer_transition_id per group" is not expressible as a unique index
    # over any column set, so it is expressed directly. The complementary half - one transition may
    # not emit the same contract twice at one version - is already the UNIQUE
    # (tenant, idempotency_identity) constraint on the table.
    "trg_event_outbox_strict_version_owner": f"""
        CREATE TRIGGER trg_event_outbox_strict_version_owner
        BEFORE INSERT ON event_outbox
        WHEN NEW.aggregate_type IN ({_STRICT_SQL_LIST})
         AND EXISTS (SELECT 1 FROM event_outbox
                      WHERE tenant = NEW.tenant
                        AND aggregate_type = NEW.aggregate_type
                        AND aggregate_id = NEW.aggregate_id
                        AND aggregate_version = NEW.aggregate_version
                        AND producer_transition_id <> NEW.producer_transition_id)
        BEGIN SELECT RAISE(ABORT, '{STRICT_ORDER_ABORT}'); END""",
    "trg_event_outbox_envelope_immutable": f"""
        CREATE TRIGGER trg_event_outbox_envelope_immutable
        BEFORE UPDATE OF {", ".join(_OUTBOX_IMMUTABLE)} ON event_outbox
        BEGIN SELECT RAISE(ABORT,
            'event_outbox envelope columns are immutable [S8]: only delivery bookkeeping may change'
        ); END""",
    "trg_event_outbox_no_delete": """
        CREATE TRIGGER trg_event_outbox_no_delete
        BEFORE DELETE ON event_outbox
        BEGIN SELECT RAISE(ABORT,
            'event_outbox is append-only [S8]: an emitted event is never deleted'
        ); END""",
    "trg_event_inbox_append_only_update": """
        CREATE TRIGGER trg_event_inbox_append_only_update
        BEFORE UPDATE ON event_inbox
        BEGIN SELECT RAISE(ABORT,
            'event_inbox is append-only [M-24]: revising a consumption record is how a redelivery becomes a second effect'
        ); END""",
    "trg_event_inbox_append_only_delete": """
        CREATE TRIGGER trg_event_inbox_append_only_delete
        BEFORE DELETE ON event_inbox
        BEGIN SELECT RAISE(ABORT,
            'event_inbox is append-only [M-24]: deleting a row re-arms a duplicate delivery'
        ); END""",
    "trg_pending_references_immutable": f"""
        CREATE TRIGGER trg_pending_references_immutable
        BEFORE UPDATE OF {", ".join(_PARK_IMMUTABLE)} ON pending_references
        BEGIN SELECT RAISE(ABORT,
            'pending_references identity, arrival order, TTL and envelope are immutable [M-26]'
        ); END""",
    "trg_pending_references_no_delete": """
        CREATE TRIGGER trg_pending_references_no_delete
        BEFORE DELETE ON pending_references
        BEGIN SELECT RAISE(ABORT,
            'pending_references is append-only [M-26]: a parked event is drained or expired, never dropped'
        ); END""",
}


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


def _indexes(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name IS NOT NULL").fetchall()}


def _triggers(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()}


def create_phase5_schema(conn: sqlite3.Connection, *, now: str) -> list[str]:
    """Create whatever P5 event-transport structure is missing. Idempotent; returns what it did.

    Callable on a fresh canonical database (where `create_canonical_schema` drives it) and on an
    already-migrated Phase-3 database. Either way the resulting structure is byte-identical,
    because there is only one text.
    """
    performed: list[str] = []
    present = _tables(conn)
    for name in (*P5_TENANT_TABLES, *P5_EXEMPT_TABLES):
        if name not in present:
            conn.execute(P5_TARGET_SCHEMA[name])
            performed.append(f"create-table:{name}")
    existing = _indexes(conn)
    for name, ddl in P5_INDEXES.items():
        if name not in existing:
            conn.execute(ddl)
            performed.append(f"create-index:{name}")
    for stale in P5_REPLACED_INDEXES:
        if stale in _indexes(conn):
            conn.execute(f"DROP INDEX {stale}")
            performed.append(f"drop-index:{stale}")
    existing_triggers = _triggers(conn)
    for name, ddl in P5_TRIGGERS.items():
        if name not in existing_triggers:
            conn.execute(ddl)
            performed.append(f"create-trigger:{name}")
    # NO VERSION STAMP HERE, for the reason phase3_checkpoint states: the completion marker is
    # written LAST and only where readiness has been PROVEN. A stamp written by the builder would
    # appear on a half-migrated database the moment a later step failed.
    conn.commit()
    return performed


def stamp_phase5_version(conn: sqlite3.Connection, *, now: str) -> None:
    """Record the P5 event-transport marker — callable ONLY once readiness holds."""
    problems = phase5_readiness_problems(conn)
    if problems:
        raise RuntimeError(
            f"refusing to stamp {P5_SCHEMA_VERSION} on a database that is NOT ready: "
            + "; ".join(problems)
        )
    if "schema_migrations" in _tables(conn):
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration, step, applied_at, detail) "
            "VALUES (?,?,?,?)",
            (MIGRATION_ID, f"version:{P5_SCHEMA_VERSION}", now,
             "transactional outbox + dedup inbox + per-aggregate cursor + M-26 parking; "
             "readiness proven"),
        )
        conn.commit()


def phase5_readiness_problems(conn: sqlite3.Connection) -> list[str]:
    """Every reason this database cannot carry the durable event transport. Empty == ready.

    Structural, like the P2 and P3 oracles it extends. The append-only triggers are verified
    PRESENT because an immutable table whose triggers were dropped is an ordinary mutable table
    wearing a solemn comment.
    """
    problems: list[str] = []
    present = _tables(conn)
    for table in (*P5_TENANT_TABLES, *P5_EXEMPT_TABLES):
        if table not in present:
            problems.append(
                f"required Phase-5 table {table!r} is missing: run the "
                f"{MIGRATION_ID} migration"
            )
    if not any(t in present for t in P5_TENANT_TABLES):
        return problems

    live_triggers = _triggers(conn)
    missing_triggers = sorted(t for t in P5_TRIGGERS if t not in live_triggers)
    if missing_triggers and all(t in present for t in P5_TENANT_TABLES):
        problems.append(
            f"event-transport append-only triggers missing: {missing_triggers}. Without them the "
            f"outbox envelope is editable and an inbox row is deletable, which re-arms every "
            f"duplicate delivery [S8, M-24]."
        )
    live_indexes = _indexes(conn)
    for name in P5_INDEXES:
        if name not in live_indexes:
            problems.append(f"required Phase-5 index {name!r} is missing")
    for stale in P5_REPLACED_INDEXES:
        if stale in live_indexes:
            problems.append(f"replaced index {stale!r} is still present")
    return problems
