"""The P5 durable surface on PostgreSQL — the production transactional store (ADR-016).

    **PostgreSQL is the production transactional store.** SQLite remains for local development
    and deterministic testing only — it is **not** the assumed multi-tenant production database.
    ### **The persistence layer keeps a single schema/migration discipline across both.**
        — ADR-016 §1

WHAT "A SINGLE DISCIPLINE ACROSS BOTH" MEANS HERE, MECHANICALLY

Two dialects cannot share one DDL string: SQLite writes `RAISE(ABORT, '…')` inside a trigger body,
PostgreSQL needs a `plpgsql` function and `RAISE EXCEPTION`. So what is shared is not the text — it
is the **contract**: which tables exist, which columns they carry, which key is first, and which
invariants a trigger must enforce.

That contract is declared ONCE, below, and both renderings are checked against it. `postgres_p5.py`
does not get to decide that `event_outbox` has a different column set from the SQLite one;
`test_p5_postgres_persistence.py` compares the live PostgreSQL schema against the live SQLite
schema, column for column and key for key, and a divergence fails the build. That is the
`SQLite-vs-PostgreSQL behavioral divergence` hostile case the P5 contract names, made executable
rather than promised.

WHY THE TRIGGERS ARE THE POINT, NOT THE TABLES

Creating five tables in another database is not persistence work; it is typing. What makes the
event transport trustworthy is that its envelope columns are **immutable by trigger**, its history
is **append-only by trigger**, and a strict-ordering family cannot have two producer transitions
claim one version. Those properties survive an admin with a connection precisely because they are
not conventions.

### **A PostgreSQL port that dropped them would look identical in every schema listing and be a
different system.** So all eight are ported as `plpgsql` functions, and the gate proves each one
REFUSES on real PostgreSQL rather than asserting the trigger merely exists.

### NOR ARE THE CONSTRAINTS. The equivalence check originally compared column NAMES and primary
keys only, and mutation-proved blind: dropping `UNIQUE (tenant, idempotency_identity)` left the gate
PASSING. Widened to compare nullability, UNIQUE tuples and CHECK vocabulary, it immediately found
that this port had silently omitted **`UNIQUE (tenant, sequence)`**, six CHECK constraints on the
outbox, the inbox's outcome enum, the cursor's version floor, and the whole of the parking table's
constraint set. The missing `UNIQUE (tenant, sequence)` is the sharpest: it is precisely what makes
a duplicate-sequence allocation LOUD rather than silent.

### AND THE COLUMN SETS ARE NOT TRUSTED EITHER. The first version of this file was hand-written
against the DDL as remembered, and the equivalence gate immediately caught it: `event_inbox` had
gained a `detail` column SQLite does not have, and `pending_references` had lost `last_attempt_at`
and `resolved_at`. That is precisely the divergence the P5 contract names as a hostile case, found
by comparing LIVE CATALOG against LIVE CATALOG rather than text against text — which is the only
comparison that could have caught it.

WHAT THIS MODULE DELIBERATELY DOES NOT DO

It does not port the P2/P3 surface (the tenant-owned state tables and the checkpoint kernel's).
Those belong to the phases that own them, and ADR-016 assigns deployment and environments to P11.
It does not open connections, read configuration, or hold credentials — it takes a connection the
caller made. ### **AND IT IS NOT WIRED INTO ANY RUNTIME PATH.** `event_outbox`, `event_inbox` and
`event_timers` remain SQLite-coupled; making them dialect-agnostic is a refactor of certified code
and is recorded as owed work, not quietly claimed here.
"""

from __future__ import annotations

from typing import Any

MIGRATION_ID = "postgres_p5"
POSTGRES_P5_SCHEMA_VERSION = "pg-p5-1"

# ### THE SHARED CONTRACT. One declaration, two renderings. Each entry names the table, the
# tenant-first primary key, and the invariants its triggers must enforce — and the equivalence
# oracle compares BOTH live schemas against this, so neither dialect can drift alone.
P5_SURFACE: dict[str, dict[str, Any]] = {
    "event_outbox": {
        "primary_key": ("tenant", "event_id"),
        "invariants": ("envelope_immutable", "no_delete", "strict_version_owner"),
    },
    "event_inbox": {
        "primary_key": ("tenant", "consumer_id", "event_id"),
        "invariants": ("append_only_update", "append_only_delete"),
    },
    "inbox_aggregate_cursor": {
        "primary_key": ("tenant", "consumer_id", "aggregate_type", "aggregate_id"),
        "invariants": (),
    },
    "pending_references": {
        "primary_key": ("tenant", "consumer_id", "event_id"),
        "invariants": (),
    },
    "durable_timers": {
        "primary_key": ("tenant", "timer_id"),
        "invariants": ("schedule_immutable", "terminal", "no_delete"),
    },
}

# Every table's tenant column is FIRST in its primary key. Stated as its own constant because the
# P5 security requirement names it outright — "tenant-first keys preserved in PostgreSQL" — and a
# property named by the contract deserves an assertion of its own rather than an inference.
TENANT_FIRST: tuple[str, ...] = tuple(P5_SURFACE)

PG_TABLES: dict[str, str] = {
    "event_outbox": """
        CREATE TABLE IF NOT EXISTS event_outbox (
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
            causation_id TEXT,
            idempotency_identity TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            envelope_json TEXT NOT NULL,
            envelope_digest TEXT NOT NULL,
            sequence BIGINT NOT NULL,
            delivery_state TEXT NOT NULL DEFAULT 'PENDING',
            published_at TEXT,
            publish_attempts INTEGER NOT NULL DEFAULT 0,
            leased_by TEXT,
            lease_expires_at TEXT,
            PRIMARY KEY (tenant, event_id),
            UNIQUE (tenant, idempotency_identity),
            -- ### THE CONSTRAINT WHOSE ABSENCE MADE THE SEQUENCE CORRUPTION SILENT.
            -- SQLite carries UNIQUE (tenant, sequence) and this port did not. With it, the
            -- duplicate-sequence allocation that an unarmed advisory lock permits raises a UNIQUE
            -- violation instead of committing eight identical sequences; without it the database
            -- has no opinion. Defence in depth for exactly the defect this increment found, and it
            -- was missing from the very port that found it.
            UNIQUE (tenant, sequence),
            CHECK (delivery_state IN ('PENDING','PUBLISHED')),
            CHECK (event_version >= 1),
            CHECK (envelope_schema_version >= 1),
            CHECK (aggregate_version >= 1),
            CHECK (recorded_at >= occurred_at),
            CHECK (delivery_state != 'PUBLISHED' OR published_at IS NOT NULL),
            CHECK (delivery_state != 'PENDING' OR published_at IS NULL)
        )
    """,
    "event_inbox": """
        CREATE TABLE IF NOT EXISTS event_inbox (
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
        )
    """,
    "inbox_aggregate_cursor": """
        CREATE TABLE IF NOT EXISTS inbox_aggregate_cursor (
            tenant TEXT NOT NULL,
            consumer_id TEXT NOT NULL,
            aggregate_type TEXT NOT NULL,
            aggregate_id TEXT NOT NULL,
            applied_version INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (tenant, consumer_id, aggregate_type, aggregate_id),
            CHECK (applied_version >= 0)
        )
    """,
    "pending_references": """
        CREATE TABLE IF NOT EXISTS pending_references (
            tenant TEXT NOT NULL,
            consumer_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            referenced_type TEXT NOT NULL,
            referenced_id TEXT NOT NULL,
            park_reason TEXT NOT NULL CHECK (park_reason IN ('MISSING_AGGREGATE','VERSION_GAP')),
            park_state TEXT NOT NULL DEFAULT 'PARKED'
                CHECK (park_state IN ('PARKED','DRAINED','EXPIRED')),
            arrival_sequence BIGINT NOT NULL,
            parked_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_attempt_at TEXT,
            resolved_at TEXT,
            accountable_owner_id TEXT,
            envelope_json TEXT NOT NULL,
            PRIMARY KEY (tenant, consumer_id, event_id),
            UNIQUE (tenant, consumer_id, arrival_sequence),
            CHECK (expires_at > parked_at),
            CHECK (park_state = 'PARKED' OR resolved_at IS NOT NULL)
        )
    """,
    "durable_timers": """
        CREATE TABLE IF NOT EXISTS durable_timers (
            tenant TEXT NOT NULL,
            timer_id TEXT NOT NULL,
            aggregate_type TEXT NOT NULL,
            aggregate_id TEXT NOT NULL,
            timer_kind TEXT NOT NULL,
            fire_at TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'SCHEDULED',
            scheduled_at TEXT NOT NULL,
            fired_at TEXT,
            cancelled_at TEXT,
            cancel_reason TEXT,
            fire_attempts INTEGER NOT NULL DEFAULT 0,
            leased_by TEXT,
            lease_expires_at TEXT,
            correlation_id TEXT,
            causation_id TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}',
            PRIMARY KEY (tenant, timer_id),
            CHECK (state IN ('SCHEDULED','FIRED','CANCELLED'))
        )
    """,
}

PG_INDEXES: dict[str, str] = {
    "ix_event_outbox_pending":
        "CREATE INDEX IF NOT EXISTS ix_event_outbox_pending "
        "ON event_outbox (tenant, delivery_state, sequence)",
    "ix_event_outbox_aggregate":
        "CREATE INDEX IF NOT EXISTS ix_event_outbox_aggregate "
        "ON event_outbox (tenant, aggregate_type, aggregate_id, aggregate_version)",
    "ix_pending_references_drain":
        "CREATE INDEX IF NOT EXISTS ix_pending_references_drain "
        "ON pending_references (tenant, consumer_id, referenced_type, referenced_id, "
        "arrival_sequence)",
    "ix_durable_timers_due":
        "CREATE INDEX IF NOT EXISTS ix_durable_timers_due "
        "ON durable_timers (tenant, state, fire_at)",
    "ix_durable_timers_aggregate":
        "CREATE INDEX IF NOT EXISTS ix_durable_timers_aggregate "
        "ON durable_timers (tenant, aggregate_type, aggregate_id, state)",
}

# ### THE EIGHT INVARIANTS, AS plpgsql. Each mirrors a SQLite trigger one-for-one. A port that
# created the tables and skipped these would list identically in `information_schema` and be a
# different system: immutability would become a convention, and a convention is what the outbox
# was built to stop relying on.
PG_FUNCTIONS: dict[str, str] = {
    "fn_event_outbox_envelope_immutable": """
        CREATE OR REPLACE FUNCTION fn_event_outbox_envelope_immutable() RETURNS trigger AS $$
        BEGIN
            IF NEW.tenant IS DISTINCT FROM OLD.tenant
               OR NEW.event_id IS DISTINCT FROM OLD.event_id
               OR NEW.event_name IS DISTINCT FROM OLD.event_name
               OR NEW.aggregate_type IS DISTINCT FROM OLD.aggregate_type
               OR NEW.aggregate_id IS DISTINCT FROM OLD.aggregate_id
               OR NEW.aggregate_version IS DISTINCT FROM OLD.aggregate_version
               OR NEW.envelope_json IS DISTINCT FROM OLD.envelope_json
               OR NEW.envelope_digest IS DISTINCT FROM OLD.envelope_digest
               OR NEW.idempotency_identity IS DISTINCT FROM OLD.idempotency_identity THEN
                RAISE EXCEPTION 'the outbox envelope is immutable: only delivery bookkeeping may move';
            END IF;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql
    """,
    "fn_event_outbox_no_delete": """
        CREATE OR REPLACE FUNCTION fn_event_outbox_no_delete() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'event_outbox is append-only: a committed event is history';
        END; $$ LANGUAGE plpgsql
    """,
    "fn_event_outbox_strict_version_owner": """
        CREATE OR REPLACE FUNCTION fn_event_outbox_strict_version_owner() RETURNS trigger AS $$
        BEGIN
            IF NEW.aggregate_type IN ('pipeline_instance','effect_grant','approval','policy','brake')
               AND EXISTS (
                   SELECT 1 FROM event_outbox o
                    WHERE o.tenant = NEW.tenant
                      AND o.aggregate_type = NEW.aggregate_type
                      AND o.aggregate_id = NEW.aggregate_id
                      AND o.aggregate_version = NEW.aggregate_version
                      AND o.producer_transition_id <> NEW.producer_transition_id) THEN
                RAISE EXCEPTION 'two DIFFERENT transitions claim one (tenant, aggregate, version) in a family that requires strict per-aggregate ordering [events/registry.md sec 8]';
            END IF;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql
    """,
    "fn_event_inbox_append_only_update": """
        CREATE OR REPLACE FUNCTION fn_event_inbox_append_only_update() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'event_inbox is append-only: a consumption is a fact, never edited';
        END; $$ LANGUAGE plpgsql
    """,
    "fn_event_inbox_append_only_delete": """
        CREATE OR REPLACE FUNCTION fn_event_inbox_append_only_delete() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'event_inbox is append-only: deleting a consumption re-opens an effect';
        END; $$ LANGUAGE plpgsql
    """,
    "fn_durable_timers_immutable": """
        CREATE OR REPLACE FUNCTION fn_durable_timers_immutable() RETURNS trigger AS $$
        BEGIN
            IF NEW.tenant IS DISTINCT FROM OLD.tenant
               OR NEW.timer_id IS DISTINCT FROM OLD.timer_id
               OR NEW.aggregate_type IS DISTINCT FROM OLD.aggregate_type
               OR NEW.aggregate_id IS DISTINCT FROM OLD.aggregate_id
               OR NEW.fire_at IS DISTINCT FROM OLD.fire_at
               OR NEW.timer_kind IS DISTINCT FROM OLD.timer_kind
               OR NEW.scheduled_at IS DISTINCT FROM OLD.scheduled_at
               OR NEW.payload_json IS DISTINCT FROM OLD.payload_json THEN
                RAISE EXCEPTION 'a durable timer schedule is immutable once written: tenant, timer_id, aggregate, fire_at and timer_kind may never be updated [M-36]';
            END IF;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql
    """,
    "fn_durable_timers_terminal": """
        CREATE OR REPLACE FUNCTION fn_durable_timers_terminal() RETURNS trigger AS $$
        BEGIN
            IF OLD.state IN ('FIRED','CANCELLED') AND NEW.state = 'SCHEDULED' THEN
                RAISE EXCEPTION 'a FIRED or CANCELLED durable timer may never return to SCHEDULED';
            END IF;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql
    """,
    "fn_durable_timers_no_delete": """
        CREATE OR REPLACE FUNCTION fn_durable_timers_no_delete() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'durable_timers is append-only: a timer records that a deadline existed';
        END; $$ LANGUAGE plpgsql
    """,
}

PG_TRIGGERS: dict[str, str] = {
    "trg_event_outbox_envelope_immutable":
        "CREATE TRIGGER trg_event_outbox_envelope_immutable BEFORE UPDATE ON event_outbox "
        "FOR EACH ROW EXECUTE FUNCTION fn_event_outbox_envelope_immutable()",
    "trg_event_outbox_no_delete":
        "CREATE TRIGGER trg_event_outbox_no_delete BEFORE DELETE ON event_outbox "
        "FOR EACH ROW EXECUTE FUNCTION fn_event_outbox_no_delete()",
    "trg_event_outbox_strict_version_owner":
        "CREATE TRIGGER trg_event_outbox_strict_version_owner BEFORE INSERT ON event_outbox "
        "FOR EACH ROW EXECUTE FUNCTION fn_event_outbox_strict_version_owner()",
    "trg_event_inbox_append_only_update":
        "CREATE TRIGGER trg_event_inbox_append_only_update BEFORE UPDATE ON event_inbox "
        "FOR EACH ROW EXECUTE FUNCTION fn_event_inbox_append_only_update()",
    "trg_event_inbox_append_only_delete":
        "CREATE TRIGGER trg_event_inbox_append_only_delete BEFORE DELETE ON event_inbox "
        "FOR EACH ROW EXECUTE FUNCTION fn_event_inbox_append_only_delete()",
    "trg_durable_timers_immutable":
        "CREATE TRIGGER trg_durable_timers_immutable BEFORE UPDATE ON durable_timers "
        "FOR EACH ROW EXECUTE FUNCTION fn_durable_timers_immutable()",
    "trg_durable_timers_terminal":
        "CREATE TRIGGER trg_durable_timers_terminal BEFORE UPDATE ON durable_timers "
        "FOR EACH ROW EXECUTE FUNCTION fn_durable_timers_terminal()",
    "trg_durable_timers_no_delete":
        "CREATE TRIGGER trg_durable_timers_no_delete BEFORE DELETE ON durable_timers "
        "FOR EACH ROW EXECUTE FUNCTION fn_durable_timers_no_delete()",
}

MIGRATIONS_TABLE = """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        migration TEXT NOT NULL,
        step TEXT NOT NULL,
        applied_at TEXT NOT NULL,
        detail TEXT,
        PRIMARY KEY (migration, step)
    )
"""


def _existing(conn: Any, sql: str, params: tuple = ()) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return {r[0] for r in cur.fetchall()}


def pg_tables(conn: Any) -> set[str]:
    return _existing(conn, "SELECT table_name FROM information_schema.tables "
                           "WHERE table_schema = current_schema()")


def pg_triggers(conn: Any) -> set[str]:
    return _existing(conn, "SELECT trigger_name FROM information_schema.triggers "
                           "WHERE trigger_schema = current_schema()")


def pg_indexes(conn: Any) -> set[str]:
    return _existing(conn, "SELECT indexname FROM pg_indexes WHERE schemaname = current_schema()")


def pg_functions(conn: Any) -> set[str]:
    return _existing(conn, "SELECT routine_name FROM information_schema.routines "
                           "WHERE routine_schema = current_schema()")


def apply_postgres_p5(conn: Any, *, now: str) -> list[str]:
    """Create whatever P5 structure is missing on PostgreSQL. Idempotent; returns what it did.

    ### IDEMPOTENT BY CONSTRUCTION, WHICH IS THE `migration replayed twice` HOSTILE CASE. Every
    table and index uses `IF NOT EXISTS`; every function uses `CREATE OR REPLACE`; every trigger is
    created only when absent. A second run therefore performs NOTHING and reports an empty list —
    not "it worked again", but "there was nothing to do", which is the only answer that proves
    replay is safe.
    """
    performed: list[str] = []
    with conn.cursor() as cur:
        cur.execute(MIGRATIONS_TABLE)
    present = pg_tables(conn)
    for name, ddl in PG_TABLES.items():
        if name not in present:
            with conn.cursor() as cur:
                cur.execute(ddl)
            performed.append(f"create-table:{name}")
    existing_indexes = pg_indexes(conn)
    for name, ddl in PG_INDEXES.items():
        if name not in existing_indexes:
            with conn.cursor() as cur:
                cur.execute(ddl)
            performed.append(f"create-index:{name}")
    existing_functions = pg_functions(conn)
    for name, ddl in PG_FUNCTIONS.items():
        # CREATE OR REPLACE is safe to re-run, but it is only REPORTED as work when the function
        # was genuinely absent — so a replay's empty result is honest rather than filtered.
        with conn.cursor() as cur:
            cur.execute(ddl)
        if name not in existing_functions:
            performed.append(f"create-function:{name}")
    existing_triggers = pg_triggers(conn)
    for name, ddl in PG_TRIGGERS.items():
        if name not in existing_triggers:
            with conn.cursor() as cur:
                cur.execute(ddl)
            performed.append(f"create-trigger:{name}")
    conn.commit()
    return performed


def postgres_p5_readiness_problems(conn: Any) -> list[str]:
    """Every reason this PostgreSQL database cannot carry the P5 surface. Empty == ready.

    Checks the TRIGGERS and the tenant-first keys, not merely that the tables exist: a port whose
    invariants are missing looks identical in a schema listing and is a different system.
    """
    problems: list[str] = []
    present = pg_tables(conn)
    for name in P5_SURFACE:
        if name not in present:
            problems.append(f"missing table: {name}")
    if problems:
        return problems
    existing_indexes, existing_triggers = pg_indexes(conn), pg_triggers(conn)
    for name in PG_INDEXES:
        if name not in existing_indexes:
            problems.append(f"missing index: {name}")
    for name in PG_TRIGGERS:
        if name not in existing_triggers:
            problems.append(f"missing trigger: {name}")
    for table in TENANT_FIRST:
        key = primary_key_columns(conn, table)
        if key[:1] != ["tenant"]:
            problems.append(f"{table} primary key is not tenant-first [C-1]: {key}")
    return problems


def primary_key_columns(conn: Any, table: str) -> list[str]:
    """The primary-key columns of one table, IN ORDER — which is what "tenant-first" is about."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.attname
              FROM pg_index i
              JOIN pg_attribute a ON a.attrelid = i.indrelid
                                 AND a.attnum = ANY(i.indkey)
             WHERE i.indrelid = %s::regclass AND i.indisprimary
          ORDER BY array_position(i.indkey, a.attnum)
            """,
            (table,),
        )
        return [r[0] for r in cur.fetchall()]


def stamp_postgres_p5_version(conn: Any, *, now: str) -> None:
    """Record the marker — callable ONLY once readiness holds. Marker-last, as everywhere here."""
    problems = postgres_p5_readiness_problems(conn)
    if problems:
        raise RuntimeError(
            f"refusing to stamp {POSTGRES_P5_SCHEMA_VERSION} on a database that is NOT ready: "
            + "; ".join(problems)
        )
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO schema_migrations (migration, step, applied_at, detail) "
            "VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (MIGRATION_ID, f"version:{POSTGRES_P5_SCHEMA_VERSION}", now,
             "P5 durable surface on PostgreSQL: outbox, inbox, cursor, parking, timers; "
             "tenant-first keys and all eight invariants; readiness proven"),
        )
    conn.commit()


def migration_status(conn: Any) -> list[tuple[str, str, str]]:
    """`migration status` — the P5 contract's named observability requirement."""
    with conn.cursor() as cur:
        cur.execute("SELECT migration, step, applied_at FROM schema_migrations "
                    "ORDER BY migration, step")
        return [(r[0], r[1], r[2]) for r in cur.fetchall()]
