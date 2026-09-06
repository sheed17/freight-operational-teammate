"""Phase 6 — M13, the Brake: hardening the ONE landed brake substrate P3 created.

WHAT THIS MIGRATION IS. It does NOT create a brake table — P3 already did, in
`phase3_checkpoint.py`: the tenant-owned `brakes` table, the tenant-exempt one-row
`platform_brake` table, the `ix_brakes_one_active_per_scope` partial unique index, and the seeded
`platform_brake` row. M13 COMPLETES, HARDENS and CANONICALIZES that one authority. It adds only
what the M13 canon requires beyond P3 and could not live on the P3 tables:

  1. `brakes.released_by` gains a tenant-consistent FOREIGN KEY into `tenant_humans` (M1) — entity
     16-brake.md point 18: the releaser is a real recorded human of the tenant, enforced by the
     database, so "a releaser who is not a recorded human" and "a releaser from another tenant" are
     both structurally refused. This is why `brakes` must be REBUILT: SQLite cannot ALTER a foreign
     key onto an existing table.
  2. `brakes.released_by_kind` — the explicit belt to the FK's braces (point 16: "released_by is
     never a detector id"); a detector is never in `tenant_humans`, so the FK already forbids it,
     and this CHECK states it in the row as well.
  3. `signal_count` on BOTH tables — entity point 33 / machine §19: a flapping detector is ONE
     ACTIVE brake and a RISING signal count. Before M13 the rising count had nowhere to live.
  4. Append-only DELETE triggers on BOTH tables — entity point 28 `[C-9]`: a brake row is never
     deleted; the incident record is retained permanently. (UPDATE is legal — engage/widen/narrow/
     release mutate the row; only DELETE is refused.)

WHY THE PLATFORM ROW DOES NOT GAIN AN FK. Amendment A1 / SD-12: the `platform_brake` row belongs
to no tenant. It therefore cannot foreign-key into the tenant-first `tenant_humans` without
pretending it is one tenant's data — the exact defect A1 exists to forbid. So a PLATFORM release's
"recorded human" is enforced by the API (a truthful authenticated human with a decision_ref), not
by an FK. This gap is `M13-AQ-5` (the corpus does not answer cross-platform human identity), built
fail-closed and recorded, not resolved.

FRESH == MIGRATED. The hardened DDL is `P6BR_TARGET_SCHEMA`, merged LAST into `schema._ALL_TARGET_
SCHEMA` (after P3's), so a fresh canonical database is built directly in the hardened shape and
never rebuilds. A pre-M13 (P3-shaped) database gets `signal_count`/`released_by_kind` by
`ALTER TABLE ADD COLUMN` and the FK by the canonical SQLite table rebuild — and the result is
byte-for-byte the same structure, because there is only one text. Marker-last, like every phase.
"""

from __future__ import annotations

import sqlite3

from .phase3_checkpoint import P3_INDEXES as _P3_INDEXES

MIGRATION_ID = "phase6_brakes"
P6BR_SCHEMA_VERSION = "phase6-brakes-1"

# `brakes` is tenant-owned [C-1]; `platform_brake` is the ONE defended tenant-exempt table (SD-12,
# amendment A1). Declared EXPLICITLY, so a future addition to either set has to argue for itself —
# exactly as P3 recorded `P3_EXEMPT_TABLES = ("platform_brake",)`.
P6BR_TENANT_TABLES: tuple[str, ...] = ("brakes",)
P6BR_EXEMPT_TABLES: tuple[str, ...] = ("platform_brake",)

# The referent M13 adds to `brakes`. Read back out of the live DB by the readiness oracle.
P6BR_BRAKE_REFERENTS: tuple[str, ...] = ("tenant_humans",)

# Columns M13 adds beyond the P3 shape. Detection of their absence is what decides ALTER vs no-op.
# `brakes` is REBUILT (for the FK), so its new columns land in the DDL's positions. `platform_brake`
# is only ALTERed (no FK), and `ALTER TABLE ADD COLUMN` APPENDS — so on the platform row the new
# columns must be the LAST columns of the fresh DDL too, in this exact order, or a migrated database
# and a fresh one would disagree on column order (the "upgraded == fresh" oracle).
_BRAKE_NEW_COLUMNS: tuple[tuple[str, str], ...] = (
    ("signal_count", "INTEGER NOT NULL DEFAULT 1"),
    ("released_by_kind", "TEXT"),
)
_PLATFORM_NEW_COLUMNS: tuple[tuple[str, str], ...] = (
    ("released_by_kind", "TEXT"),
    ("signal_count", "INTEGER NOT NULL DEFAULT 0"),
)

# Abort texts. Interpolated into single-quoted RAISE(ABORT, '...') SQL literals, so worded WITHOUT
# apostrophes (an apostrophe would terminate the literal and the trigger would fail to compile —
# the defect phase6_work_items.py records having hit).
BRAKE_DELETE_ABORT = (
    "a brake row is never deleted [16-brake.md point 28, C-9]: the engage/widen/narrow/release "
    "history IS the incident timeline and its retention is permanent"
)
PLATFORM_BRAKE_DELETE_ABORT = (
    "the platform brake row is never deleted [SD-12, C-9]: an absent platform row reads as "
    "unreadable and REFUSES admission, which is not the same fact as a released brake"
)


# THE HARDENED BRAKE TABLE. Every P3 column and constraint is preserved verbatim; M13 adds
# signal_count, released_by_kind, their CHECKs, and the tenant-consistent released_by FK. One text:
# a fresh database is built from this, and the migrated path rebuilds to exactly this.
P6BR_TARGET_SCHEMA: dict[str, str] = {
    "brakes": """
        CREATE TABLE brakes (
            tenant TEXT NOT NULL,
            brake_id TEXT NOT NULL,
            scope TEXT NOT NULL,
            state TEXT NOT NULL CHECK (state IN ('ACTIVE','RELEASED')),
            actor TEXT NOT NULL,
            actor_kind TEXT NOT NULL CHECK (actor_kind IN ('HUMAN','DETECTOR')),
            engaged_reason TEXT NOT NULL,
            engaged_at TEXT NOT NULL,
            brake_version INTEGER NOT NULL,
            signal_count INTEGER NOT NULL DEFAULT 1,
            released_by TEXT,
            released_by_kind TEXT,
            release_decision_ref TEXT,
            released_at TEXT,
            PRIMARY KEY (tenant, brake_id),
            CHECK (state != 'RELEASED' OR (released_by IS NOT NULL AND release_decision_ref IS NOT NULL)),
            CHECK (released_by_kind IS NULL OR released_by_kind = 'HUMAN'),
            CHECK (signal_count >= 1),
            FOREIGN KEY (tenant, released_by) REFERENCES tenant_humans (tenant, human_id)
        )""",
    # THE PLATFORM BRAKE — ONE row (SD-12), id constrained to 1, NO tenant column (amendment A1).
    # M13 adds only signal_count; the seed and the id CHECK are P3's and preserved. A released
    # platform row carries released_by/release_decision_ref set by the API (no FK: the row belongs
    # to no tenant, so it cannot reference tenant_humans — M13-AQ-5, built fail-closed).
    "platform_brake": """
        CREATE TABLE platform_brake (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            state TEXT NOT NULL CHECK (state IN ('ACTIVE','RELEASED')),
            brake_version INTEGER NOT NULL,
            actor TEXT,
            actor_kind TEXT CHECK (actor_kind IS NULL OR actor_kind IN ('HUMAN','DETECTOR')),
            engaged_reason TEXT,
            engaged_at TEXT,
            released_by TEXT,
            release_decision_ref TEXT,
            released_at TEXT,
            released_by_kind TEXT,
            signal_count INTEGER NOT NULL DEFAULT 0
        )""",
}

# The one active-per-scope partial unique index is P3's; M13 recreates it verbatim after a rebuild
# (pulled from P3_INDEXES so a rebuild can never silently drop or redefine it).
P6BR_INDEXES: dict[str, str] = {
    "ix_brakes_one_active_per_scope": _P3_INDEXES["ix_brakes_one_active_per_scope"],
}
_BRAKES_INDEX_DDLS: tuple[str, ...] = tuple(
    ddl for ddl in _P3_INDEXES.values() if " ON brakes " in ddl
)

P6BR_REPLACED_INDEXES: tuple[str, ...] = ()

P6BR_TRIGGERS: dict[str, str] = {
    "trg_brakes_no_delete": f"""
        CREATE TRIGGER trg_brakes_no_delete
        BEFORE DELETE ON brakes
        BEGIN SELECT RAISE(ABORT, '{BRAKE_DELETE_ABORT}'); END""",
    "trg_platform_brake_no_delete": f"""
        CREATE TRIGGER trg_platform_brake_no_delete
        BEFORE DELETE ON platform_brake
        BEGIN SELECT RAISE(ABORT, '{PLATFORM_BRAKE_DELETE_ABORT}'); END""",
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


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _referents(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[2] for r in conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()}


def _rebuild_brakes_with_foreign_key(conn: sqlite3.Connection) -> list[str]:
    """Add the tenant-consistent `released_by` FK the only way SQLite allows: rebuild `brakes`.

    The canonical 12-step ALTER (SQLite docs, "Making Other Kinds Of Table Schema Changes"): FKs
    OFF outside a transaction, copy every existing column into a new table built from the hardened
    DDL, drop the old, rename, recreate the one active-per-scope index, verify no FK violation, FKs
    back ON. Any pre-M13 released rows whose `released_by` is not a recorded human of the tenant
    would surface HERE, as an honest foreign_key_check violation that abandons the rebuild — those
    releases predate the invariant M13 makes structural, and silently keeping them would be the
    thing the invariant exists to stop.

    Only the migrated path reaches this; a fresh database is already M13-shaped and never rebuilds.
    """
    performed: list[str] = []
    existing = _columns(conn, "brakes")
    new_cols = {c for c, _ in _BRAKE_NEW_COLUMNS}
    carried = [c for c in existing if c not in new_cols]
    carried_sql = ", ".join(carried)
    new_ddl = P6BR_TARGET_SCHEMA["brakes"].replace(
        "CREATE TABLE brakes", "CREATE TABLE _p6br_brakes_new", 1)

    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(new_ddl)
        conn.execute(
            f"INSERT INTO _p6br_brakes_new ({carried_sql}) SELECT {carried_sql} FROM brakes")
        conn.execute("DROP TABLE brakes")
        conn.execute("ALTER TABLE _p6br_brakes_new RENAME TO brakes")
        for ddl in _BRAKES_INDEX_DDLS:
            conn.execute(ddl)
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(
                f"rebuilding brakes introduced {len(violations)} foreign-key violation(s): "
                f"{violations}. A pre-M13 release by an unrecorded human cannot be carried forward; "
                f"the rebuild is abandoned and the brakes table is unchanged."
            )
        conn.commit()
        performed.append("rebuild-table:brakes(+fk tenant_humans)")
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
    return performed


def create_phase6_brakes_schema(conn: sqlite3.Connection, *, now: str) -> list[str]:
    """Harden the P3 brake substrate to the M13 shape. Idempotent; returns what it did.

    On a fresh canonical database the hardened DDL already built both tables, so this adds nothing
    but the DELETE triggers (which are M13's) and returns those (or `[]` on a second run). On a
    P3-shaped database it ALTERs in the new columns, rebuilds `brakes` for the FK, and adds the
    triggers. Either way the resulting structure is byte-identical to the fresh one.
    """
    performed: list[str] = []
    if "brakes" not in _tables(conn):
        # A database without the P3 brake table is broken; the P3/generic oracle reports it, and
        # M13 does not create P3's tables.
        return performed

    if "platform_brake" in _tables(conn):
        pcols = _columns(conn, "platform_brake")
        for col, decl in _PLATFORM_NEW_COLUMNS:
            if col not in pcols:
                conn.execute(f"ALTER TABLE platform_brake ADD COLUMN {col} {decl}")
                performed.append(f"add-column:platform_brake.{col}")

    bcols = _columns(conn, "brakes")
    for col, decl in _BRAKE_NEW_COLUMNS:
        if col not in bcols:
            conn.execute(f"ALTER TABLE brakes ADD COLUMN {col} {decl}")
            performed.append(f"add-column:brakes.{col}")

    if any(ref not in _referents(conn, "brakes") for ref in P6BR_BRAKE_REFERENTS):
        performed.extend(_rebuild_brakes_with_foreign_key(conn))

    existing_triggers = _triggers(conn)
    for name, ddl in P6BR_TRIGGERS.items():
        if name not in existing_triggers:
            conn.execute(ddl)
            performed.append(f"create-trigger:{name}")

    # NO VERSION STAMP HERE — marker-last, only where readiness is PROVEN (stamp_* below).
    conn.commit()
    return performed


def stamp_phase6_brakes_version(conn: sqlite3.Connection, *, now: str) -> None:
    """Record the M13 marker — callable ONLY once readiness holds. Marker-last, like every phase."""
    problems = phase6_brakes_readiness_problems(conn)
    if problems:
        raise RuntimeError(
            f"refusing to stamp {P6BR_SCHEMA_VERSION} on a database that is NOT ready: "
            + "; ".join(problems)
        )
    if "schema_migrations" in _tables(conn):
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration, step, applied_at, detail) "
            "VALUES (?,?,?,?)",
            (MIGRATION_ID, f"version:{P6BR_SCHEMA_VERSION}", now,
             "M13 Brake: released_by FK into tenant_humans, released_by_kind, signal_count on both "
             "tables, append-only DELETE triggers; readiness proven"),
        )
        conn.commit()


def phase6_brakes_readiness_problems(conn: sqlite3.Connection) -> list[str]:
    """Every reason this database cannot serve the M13 brake lifecycle. Empty == ready.

    Structural, like the P3/P5/P6 oracles it extends. Nothing is trusted because a name looks
    familiar: the FK is read back with `PRAGMA foreign_key_list`, the columns with `PRAGMA
    table_info`, the DELETE triggers by name, and the one active-per-scope index by name — because
    a brake whose delete trigger was dropped is an ordinary table wearing a solemn comment.
    """
    problems: list[str] = []
    present = _tables(conn)
    for table in (*P6BR_TENANT_TABLES, *P6BR_EXEMPT_TABLES):
        if table not in present:
            problems.append(
                f"required brake table {table!r} is missing: run the phase3_checkpoint migration "
                f"(M13 hardens P3's tables; it does not create them)"
            )
    if "brakes" not in present:
        return problems

    bcols = set(_columns(conn, "brakes"))
    for col, _ in _BRAKE_NEW_COLUMNS:
        if col not in bcols:
            problems.append(
                f"brakes.{col} is missing: run the {MIGRATION_ID} migration (the M13 delta over P3)"
            )
    if "platform_brake" in present:
        pcols = set(_columns(conn, "platform_brake"))
        for col, _ in _PLATFORM_NEW_COLUMNS:
            if col not in pcols:
                problems.append(f"platform_brake.{col} is missing: run the {MIGRATION_ID} migration")

    if any(ref not in _referents(conn, "brakes") for ref in P6BR_BRAKE_REFERENTS):
        problems.append(
            "brakes declares no foreign key into tenant_humans: `released_by` would be any "
            "non-empty string, and 'a releaser is a recorded human of the tenant' would be "
            "documentation rather than a database constraint [16-brake.md point 18]."
        )

    live_indexes = _indexes(conn)
    for name in P6BR_INDEXES:
        if name not in live_indexes:
            problems.append(
                f"required brake index {name!r} is missing: without it a second ACTIVE brake per "
                f"(tenant, scope) is insertable, which is a momentary release window during an incident."
            )

    live_triggers = _triggers(conn)
    missing_triggers = sorted(t for t in P6BR_TRIGGERS if t not in live_triggers)
    if missing_triggers:
        problems.append(
            f"brake append-only DELETE triggers missing: {missing_triggers}. Without them the "
            f"incident record is deletable and [C-9] is a comment."
        )
    return problems
