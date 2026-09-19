"""U8.5 — THE `lane` -> `action_class` migration (the PERSISTENCE half).

The code half of U8.5 renames the overloaded operational `lane` identifier to `action_class`
everywhere it meant WHAT consequential effect is attempted (raise_invoice / record_payable / ...).
This module is the DATA half: it migrates a pre-U8.5 database's persisted `lane` to the canonical
`action_class` deterministically, tenant-safely and idempotently, and it changes NO commit key, NO
grant/witness binding, NO approval identity, NO policy/brake version, NO cap result and NO gate.

### THE TWO PERSISTED SURFACES THAT CARRIED THE OPERATIONAL `lane`.

  * `autonomous_run_counters` — keyed `(tenant, lane, day)`. The identifier was mechanically
    determined to be an ACTION_CLASS: the WorkflowStore path is fed OperationRouter's `route.name`,
    the WHAT-effect, which is exactly the population `commit_key.OCCURRENCE_RULES` registers — NOT a
    policy scope distinct from it. So the column is RENAMED `lane` -> `action_class` (and the PK
    becomes `(tenant, action_class, day)`). SQLite's `RENAME COLUMN` preserves every row, the
    per-tenant counts and the composite PK, so a rename can never move a counter between tenants and
    the atomic daily-cap result is byte-identical before and after.

  * `effect_grants.lane` — a NON-AUTHORITATIVE legacy mirror, written byte-identical to the
    `action_class` column that already exists on that ledger. M3/P3 never read it, and after U8.5 the
    WorkflowStore legacy path reads `action_class` too. It is deliberately NOT dropped and NOT
    renamed: the effect ledger is the tier-1 effect boundary, and `action_class` is ALREADY the field
    there — dropping the mirror would be a schema rewrite of the ledger, not a mechanical rename, and
    would touch the M3 rebuild/backfill paths for no behavioural gain. The mirror is instead written
    `lane = action_class` byte-for-byte at the WorkflowStore write boundary, so it can never diverge
    into a second field that independently controls behaviour (the "no indefinite dual-authority"
    rule). That is a WRITE-path guarantee proven by a unit test, not a whole-table readiness scan —
    the M3/P3 checkpoint path also writes this ledger and leaves `lane` at its '' default, unused.

### IDEMPOTENT AND SAFE ON EITHER SHAPE. On a fresh canonical database `autonomous_run_counters` is
already `action_class`-shaped (phase2 builds it that way), so the rename is a no-op; on a pre-U8.5
database it performs exactly the one rename. Re-running finds nothing to do. It reads no tenant's data
on behalf of another: the counter rename is a whole-table DDL operation that touches no row.

### IT SHIPS DARK AND ENABLES NOTHING. It grants no autonomy, mints no gate, registers no policy,
and touches no live route. `autonomous_run_counters` is only ever written by the OperationRouter,
which is `None` in the deployed callback server; this migration only makes its column name honest.
"""

from __future__ import annotations

import sqlite3

MIGRATION_ID = "phase8_action_class"
P8AC_SCHEMA_VERSION = "phase8-action-class-1"

# The table whose `lane` identifier is a live authority key and is renamed to `action_class`.
P8AC_RENAMED_TABLE = "autonomous_run_counters"

# The ledger whose `lane` is a non-authoritative mirror of `action_class`, retained (not renamed,
# not dropped) and only invariant-checked.
P8AC_MIRROR_TABLE = "effect_grants"


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def migrate_phase8_action_class(conn: sqlite3.Connection, *, now: str) -> list[str]:
    """Rename the autonomous-run counter's `lane` column to `action_class`. Idempotent; returns work.

    Callable on a fresh canonical database (no-op — already `action_class`) and on a pre-U8.5 one
    (performs the one rename). It never drops or rewrites the effect ledger; the `effect_grants.lane`
    mirror is retained and kept equal to `action_class` at the WorkflowStore write boundary.
    """
    performed: list[str] = []
    present = _tables(conn)
    if P8AC_RENAMED_TABLE in present:
        cols = _columns(conn, P8AC_RENAMED_TABLE)
        if "lane" in cols and "action_class" not in cols:
            # A whole-table DDL rename: every row, the per-tenant counts and the composite PK
            # (tenant, lane, day) -> (tenant, action_class, day) are preserved by SQLite. No row
            # is read or moved across tenants.
            conn.execute(
                f"ALTER TABLE {P8AC_RENAMED_TABLE} RENAME COLUMN lane TO action_class")
            performed.append(f"rename-column:{P8AC_RENAMED_TABLE}.lane->action_class")
        elif "lane" in cols and "action_class" in cols:
            # Both present is an anomaly (a half-applied or hand-edited schema): refuse rather than
            # guess which one is authority. Fail closed — this is exactly the dual-field state U8.5
            # exists to remove.
            raise RuntimeError(
                f"{P8AC_RENAMED_TABLE} carries BOTH `lane` and `action_class`: U8.5 will not guess "
                f"which is authority. Reconcile the counter table by hand before migrating."
            )
    conn.commit()
    return performed


def phase8_action_class_readiness_problems(conn: sqlite3.Connection) -> list[str]:
    """Every reason this database has not completed the U8.5 persistence migration. Empty == ready.

    Structural, like the P2/P3/P5/P6/P7/P8-epoch oracles it sits beside. It proves two things:
    the counter table carries the canonical `action_class` column and NOT the legacy `lane`, and the
    effect ledger still carries its canonical `action_class` column. The `lane` mirror's non-divergence
    is a write-boundary guarantee (WorkflowStore writes lane = action_class) proven by a unit test, not
    a readiness row-scan — the M3/P3 checkpoint path writes the ledger too and leaves `lane` unused.
    """
    problems: list[str] = []
    present = _tables(conn)

    if P8AC_RENAMED_TABLE in present:
        cols = _columns(conn, P8AC_RENAMED_TABLE)
        if "action_class" not in cols:
            problems.append(
                f"{P8AC_RENAMED_TABLE} is missing the canonical `action_class` column: run the "
                f"{MIGRATION_ID} migration (it renames the legacy `lane` counter key)."
            )
        if "lane" in cols:
            problems.append(
                f"{P8AC_RENAMED_TABLE} still carries the legacy `lane` column: the U8.5 rename to "
                f"`action_class` did not complete, leaving the operational-control lane in a live "
                f"authority key."
            )

    if P8AC_MIRROR_TABLE in present:
        cols = _columns(conn, P8AC_MIRROR_TABLE)
        if "action_class" not in cols:
            problems.append(
                f"{P8AC_MIRROR_TABLE} is missing its canonical `action_class` column"
            )
        # The `lane` mirror's non-divergence is NOT asserted here as a readiness row-scan: the effect
        # ledger is also written by the M3/P3 checkpoint path, which populates `action_class` and
        # leaves `lane` at its '' default (it never uses the legacy mirror), so `action_class == lane`
        # is deliberately NOT a whole-table invariant. Non-divergence is guaranteed at the WRITE
        # boundary instead — the WorkflowStore legacy path writes `lane = action_class` byte-for-byte
        # — and proven by test_phase8_action_class_migration, not by perturbing P2/P3 readiness.
    return problems


def stamp_phase8_action_class_version(conn: sqlite3.Connection, *, now: str) -> None:
    """Record the U8.5 persistence marker — callable ONLY once readiness holds. Marker-last."""
    problems = phase8_action_class_readiness_problems(conn)
    if problems:
        raise RuntimeError(
            f"refusing to stamp {P8AC_SCHEMA_VERSION} on a database that is NOT ready: "
            + "; ".join(problems)
        )
    if "schema_migrations" in _tables(conn):
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration, step, applied_at, detail) "
            "VALUES (?,?,?,?)",
            (MIGRATION_ID, f"version:{P8AC_SCHEMA_VERSION}", now,
             "U8.5 lane->action_class persistence: autonomous_run_counters.lane renamed to "
             "action_class (tenant-first PK preserved, atomic-cap behaviour unchanged); "
             "effect_grants.lane retained as a non-authoritative mirror written = action_class at the "
             "write boundary; grants an autonomy of exactly nothing"),
        )
        conn.commit()
