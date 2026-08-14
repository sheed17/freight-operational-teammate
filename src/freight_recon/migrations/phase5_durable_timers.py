"""The durable-timer schema (P5, ADR-016 §2 "durable timers and scheduler", M-36).

    ### M-36. A timeout MUST be a **durable timer emitting `TimerFired`** — never a background
    sweep, never a scan for "things that look old".
    **Mech:** `durable_timers` + a relay. · **Test:** `test_no_component_scans_for_staleness`.

WHY A TABLE AND NOT A SWEEP — THE DISTINCTION THIS SCHEMA EXISTS TO MAKE STRUCTURAL

A sweep asks the business tables a question: *"which work items LOOK old?"* Every answer it gives
depends on the shape of the query, the indexes that happen to exist, and whoever last edited the
predicate. It silently misses rows a slightly different `WHERE` would have caught, and nothing
fails when it does — the work simply never ages.

A durable timer is the opposite: the deadline is written down, **once, by the transition that
created the obligation**, in the same commit. A row exists or it does not. Firing is a lookup on an
explicit schedule (`state='SCHEDULED' AND fire_at <= now`), not an interrogation of business state,
and a missed fire is a row still sitting there rather than an absence nobody can see.

That is why `fire_at` is written by the scheduler and is **immutable** afterwards: a deadline that
can be edited is a deadline that can be quietly pushed out, which is how an obligation stops ageing
without anyone deciding that it should.

WHAT THE ROW CARRIES, AND WHAT IT DELIBERATELY DOES NOT

It carries WHEN and WHAT-IT-IS-ABOUT: the tenant, the aggregate, the fire time, and a `timer_kind`
the scheduling machine chose. ### **IT CARRIES NO DECISION.** `TimerFired` is a *trigger*, not a
canonical event — the corpus errata is explicit that it is excluded from the 105 — so a fired timer
does not say what happened. The MACHINE decides, by its own guard, and P6 owns those machines.
Encoding "an overdue expectation becomes `ExpectationOverdue`" here would put a transition table in
a migration file.

That separation is load-bearing for safety, not only tidiness: GR-6 forbids any timer transition
from moving an `UNKNOWN_OUTCOME`, and several states name **any** `TimerFired` as an ILLEGAL
transition. A timer service that decided outcomes could violate those; one that only says *"the
time you asked for has arrived"* cannot.
"""

from __future__ import annotations

import sqlite3

MIGRATION_ID = "phase5_durable_timers"
TIMERS_SCHEMA_VERSION = "p5-timers-1"

# Tenant-first, like every canonical table [C-1]. There is no tenant-exempt timer: "whose deadline
# is this" has no honest answer other than a tenant.
TIMER_TABLES: tuple[str, ...] = ("durable_timers",)

# The three states a timer can be in. ### FIRED AND CANCELLED ARE BOTH TERMINAL, and they are
# different facts: FIRED means the deadline arrived and was delivered; CANCELLED means the
# obligation ended before its deadline. Collapsing them would make "did this expectation ever come
# due?" unanswerable from history.
TIMER_STATES: tuple[str, ...] = ("SCHEDULED", "FIRED", "CANCELLED")

# The exact text the immutability trigger aborts with, matched by `event_timers` when it classifies
# a `sqlite3.IntegrityError` — the same discipline the outbox uses, because SQLite reports a
# trigger RAISE(ABORT) and a UNIQUE violation through one exception type.
# No apostrophe: this text is interpolated into a SQLite RAISE(ABORT) string literal, and a stray
# quote makes the trigger DDL a syntax error rather than a guard.
TIMER_IMMUTABLE_ABORT = (
    "a durable timer schedule is immutable once written: tenant, timer_id, aggregate, fire_at "
    "and timer_kind may never be updated [M-36]"
)

TIMER_TARGET_SCHEMA: dict[str, str] = {
    "durable_timers": """
        CREATE TABLE durable_timers (
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
        )""",
}

TIMER_INDEXES: dict[str, str] = {
    # THE DUE LOOKUP. Tenant-first, then state, then time — so firing is an index seek over an
    # explicit schedule. This index is what makes the no-sweep property affordable as well as
    # correct: without it the relay would degrade into the table scan M-36 forbids in spirit.
    "ix_durable_timers_due":
        "CREATE INDEX ix_durable_timers_due ON durable_timers (tenant, state, fire_at)",
    # Cancellation and re-scheduling both address a timer through its aggregate.
    "ix_durable_timers_aggregate":
        "CREATE INDEX ix_durable_timers_aggregate "
        "ON durable_timers (tenant, aggregate_type, aggregate_id, state)",
}

TIMER_TRIGGERS: dict[str, str] = {
    # ### THE SCHEDULE IS IMMUTABLE. Delivery bookkeeping (state, fired_at, cancelled_at,
    # cancel_reason, fire_attempts, leased_by, lease_expires_at) may move; the DEADLINE and its
    # subject may not. Enforced by the database rather than by convention, so it survives an admin
    # with a connection — the same reason the outbox's envelope columns are trigger-protected.
    "trg_durable_timers_immutable": f"""
        CREATE TRIGGER trg_durable_timers_immutable
        BEFORE UPDATE ON durable_timers
        FOR EACH ROW WHEN (
               NEW.tenant         IS NOT OLD.tenant
            OR NEW.timer_id       IS NOT OLD.timer_id
            OR NEW.aggregate_type IS NOT OLD.aggregate_type
            OR NEW.aggregate_id   IS NOT OLD.aggregate_id
            OR NEW.fire_at        IS NOT OLD.fire_at
            OR NEW.timer_kind     IS NOT OLD.timer_kind
            OR NEW.scheduled_at   IS NOT OLD.scheduled_at
            OR NEW.payload_json   IS NOT OLD.payload_json
        )
        BEGIN SELECT RAISE(ABORT, '{TIMER_IMMUTABLE_ABORT}'); END
    """,
    # ### A TERMINAL TIMER IS TERMINAL. A FIRED or CANCELLED timer may never return to SCHEDULED:
    # re-arming a delivered deadline would fire it twice, and re-arming a cancelled one would
    # resurrect an obligation someone decided was over.
    "trg_durable_timers_terminal": """
        CREATE TRIGGER trg_durable_timers_terminal
        BEFORE UPDATE ON durable_timers
        FOR EACH ROW WHEN OLD.state IN ('FIRED','CANCELLED') AND NEW.state = 'SCHEDULED'
        BEGIN SELECT RAISE(ABORT,
            'a FIRED or CANCELLED durable timer may never return to SCHEDULED'); END
    """,
    # History is append-only (S8). A timer row records that a deadline existed; deleting it would
    # erase the evidence that an obligation was ever owed.
    "trg_durable_timers_no_delete": """
        CREATE TRIGGER trg_durable_timers_no_delete
        BEFORE DELETE ON durable_timers
        BEGIN SELECT RAISE(ABORT,
            'durable_timers is append-only: a timer records that a deadline existed'); END
    """,
}


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


def _indexes(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'").fetchall()}


def _triggers(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()}


def create_timer_schema(conn: sqlite3.Connection, *, now: str) -> list[str]:
    """Create whatever durable-timer structure is missing. Idempotent; returns what it did."""
    performed: list[str] = []
    present = _tables(conn)
    for name in TIMER_TABLES:
        if name not in present:
            conn.execute(TIMER_TARGET_SCHEMA[name])
            performed.append(f"create-table:{name}")
    existing = _indexes(conn)
    for name, ddl in TIMER_INDEXES.items():
        if name not in existing:
            conn.execute(ddl)
            performed.append(f"create-index:{name}")
    existing_triggers = _triggers(conn)
    for name, ddl in TIMER_TRIGGERS.items():
        if name not in existing_triggers:
            conn.execute(ddl)
            performed.append(f"create-trigger:{name}")
    # No version stamp here — the completion marker is written LAST and only where readiness has
    # been PROVEN, exactly as the P3 and P5-transport migrations do. A stamp written by the builder
    # would appear on a half-migrated database the moment a later step failed.
    conn.commit()
    return performed


def timer_readiness_problems(conn: sqlite3.Connection) -> list[str]:
    """Every reason this database cannot carry durable timers. Empty == ready.

    Structural, and it checks the TRIGGERS rather than trusting that the table exists: the
    immutability of a deadline is the property that makes a timer a timer, and a table without its
    triggers is a table that merely looks like one.
    """
    problems: list[str] = []
    present = _tables(conn)
    for name in TIMER_TABLES:
        if name not in present:
            problems.append(f"missing table: {name}")
    if problems:
        return problems
    columns = {r[1] for r in conn.execute("PRAGMA table_info(durable_timers)").fetchall()}
    if "tenant" not in columns:
        problems.append("durable_timers is not tenant-first: no tenant column")
    primary = [r[1] for r in conn.execute("PRAGMA table_info(durable_timers)").fetchall() if r[5]]
    if primary[:1] != ["tenant"]:
        problems.append(f"durable_timers primary key must start with tenant [C-1]; got {primary}")
    existing_indexes, existing_triggers = _indexes(conn), _triggers(conn)
    for name in TIMER_INDEXES:
        if name not in existing_indexes:
            problems.append(f"missing index: {name}")
    for name in TIMER_TRIGGERS:
        if name not in existing_triggers:
            problems.append(f"missing trigger: {name}")
    return problems


def stamp_timer_version(conn: sqlite3.Connection, *, now: str) -> None:
    """Record the durable-timer marker — callable ONLY once readiness holds."""
    problems = timer_readiness_problems(conn)
    if problems:
        raise RuntimeError(
            f"refusing to stamp {TIMERS_SCHEMA_VERSION} on a database that is NOT ready: "
            + "; ".join(problems)
        )
    if "schema_migrations" in _tables(conn):
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration, step, applied_at, detail) "
            "VALUES (?,?,?,?)",
            (MIGRATION_ID, f"version:{TIMERS_SCHEMA_VERSION}", now,
             "durable timers: explicit schedule, immutable deadline, terminal states, "
             "append-only; readiness proven"),
        )
        conn.commit()
