"""The one schema contract: what canonical means, and the refusal of everything else.

WHY THIS FILE EXISTS SEPARATELY

Every affected `WorkflowStore` method must fail BEFORE it issues tenant-owned SQL against a database
that cannot honour it. If each method decided that for itself, twenty-two methods would hold
twenty-two opinions, and the first one to be lenient would be the hole. So there is exactly one
readiness contract, it is structural, and it has no lenient mode:

    no legacy SQL fallback. no "try the new query, then the old one". no silent compatibility mode.
    no unscoped read to "check first". no missing table read as "no record".

A missing tenant column is not a reason to fall back to the query that ignores tenants - that query
is the defect. It is a reason to stop.

WHAT CANONICAL MEANS IS NOT DEFINED HERE

It is defined ONCE, in `migrations/phase2_tenant_first.TARGET_SCHEMA`, and imported. A fresh
database and a migrated database therefore cannot drift into two different "canonical" shapes,
because there is only one text. `create_canonical_schema()` builds a new database directly in the
Phase-2 shape - it does not create the legacy schema and then migrate it, so a fresh database is
never briefly unsafe and never needs a second startup to become correct.
"""

from __future__ import annotations

import re
import sqlite3

from .migrations.phase2_tenant_first import (
    CANONICAL_TENANT_TABLES,
    TARGET_SCHEMA,
    GRANT_STATES,
    INDEXES,
    MIGRATION_ID,
    SCHEMA_VERSION,
    TARGET_SCHEMA,
    TENANT_EXEMPT_TABLES,
)

TENANT_COLUMN = "tenant"

# Indexes without which the tenant-first PROPERTY is not enforced by the database, only hoped for.
REQUIRED_INDEXES: tuple[str, ...] = (
    "ix_workflow_runs_tenant_document_hash",   # the doc-hash defect, closed structurally
    "ix_effect_grants_tenant_commit_key",      # one live reservation per (tenant, logical effect)
    "ix_effect_grants_commit_once",            # Layer-2 claim-instant exclusion
)

# Their presence proves a migration was never run, or died half-way. Either way: not ready.
LEGACY_TABLES: tuple[str, ...] = ("operation_commit_claims",)

# Every table a canonical database is allowed to contain. A new table must be added here
# deliberately, which is the point (REG-1).
CANONICAL_TABLES: tuple[str, ...] = (
    *CANONICAL_TENANT_TABLES,
    "autonomous_run_counters",
    *TENANT_EXEMPT_TABLES,
)


class SchemaNotReady(RuntimeError):
    """This database cannot answer tenant-owned SQL. The operation stops here.

    Deliberately NOT a `WorkflowError`. Three call sites already catch `WorkflowError` and turn it
    into an operator-facing outcome; if this inherited from it, "your database is unmigrated" would
    be delivered as a workflow decision and the caller would carry on. It is not a workflow
    condition. It is the absence of a database this code may speak to.
    """


class ForeignKeysNotEnforced(RuntimeError):
    """`PRAGMA foreign_keys=ON` was issued and did not take. The tenant-consistent FKs are inert."""


def enable_and_verify_foreign_keys(conn: sqlite3.Connection) -> None:
    """Turn foreign keys on and PROVE they are on. Issuing the pragma is not evidence.

    SQLite silently IGNORES `PRAGMA foreign_keys` inside a transaction. A build that issues it and
    assumes it worked gets tenant-consistent foreign keys that never fire - the constraint reads as
    present in the DDL, enforces nothing, and every cross-tenant test passes for the wrong reason.
    So we commit any open transaction first, then read the value back.
    """
    conn.commit()  # a pragma issued inside a transaction is a no-op, silently
    conn.execute("PRAGMA foreign_keys = ON")
    row = conn.execute("PRAGMA foreign_keys").fetchone()
    if not row or int(row[0]) != 1:
        raise ForeignKeysNotEnforced(
            "PRAGMA foreign_keys=ON did not take effect. The tenant-consistent foreign keys would "
            "be decorative and cross-tenant children would be insertable."
        )


def create_canonical_schema(conn: sqlite3.Connection) -> None:
    """Create a FRESH database directly in the tenant-first Phase-2 shape.

    Not the legacy schema plus a migration: a new database is canonical from its first statement.
    Idempotent - existing tables are left alone, so this is safe to call on every construction.
    """
    present = _tables(conn)
    for name in CANONICAL_TABLES:
        if name not in present:
            conn.execute(TARGET_SCHEMA[name])
    existing_indexes = _index_names(conn)
    for name, ddl in INDEXES.items():
        table = ddl.split(" ON ")[1].split(" ")[0]
        if name not in existing_indexes and table in _tables(conn):
            conn.execute(ddl)
    # Stamp the version so a future incompatible shape is REFUSED rather than half-spoken to.
    if "schema_migrations" in _tables(conn):
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration, step, applied_at, detail) "
            "VALUES (?,?,?,?)",
            (MIGRATION_ID, f"version:{SCHEMA_VERSION}", _now(), "fresh database created canonical"),
        )
    conn.commit()


def schema_readiness_problems(conn: sqlite3.Connection) -> list[str]:
    """Every reason this database cannot serve tenant-owned SQL. Empty list == ready.

    Deterministic and total: it reports ALL problems, not the first, so a partially migrated
    database cannot be fixed one surprise at a time.
    """
    problems: list[str] = []
    present = _tables(conn)

    for legacy in LEGACY_TABLES:
        if legacy in present:
            problems.append(
                f"legacy table {legacy!r} is still present: this database is pre-migration or the "
                f"migration did not finish. Run the phase2_tenant_first migration."
            )
    residue = sorted(t for t in present if t.startswith("_legacy_"))
    if residue:
        problems.append(
            f"migration residue {residue}: a previous migration run did not reach its cleanup step."
        )

    for table in CANONICAL_TENANT_TABLES:
        if table not in present:
            problems.append(f"required tenant-owned table {table!r} is missing")
            continue
        columns = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if TENANT_COLUMN not in columns:
            problems.append(f"{table!r} has no {TENANT_COLUMN!r} column")
            continue
        pk = _pk_columns(conn, table)
        if not pk or pk[0] != TENANT_COLUMN:
            # A tenant COLUMN is not tenant isolation. If tenant is not FIRST in the key the
            # uniqueness domain is still global, which is the defect wearing a column.
            problems.append(
                f"{table!r} is not tenant-first: primary key is {pk or '(none)'}, expected "
                f"{TENANT_COLUMN!r} first"
            )

    missing_indexes = [n for n in REQUIRED_INDEXES if n not in _index_names(conn)]
    if missing_indexes:
        problems.append(
            f"required tenant-first constraint(s) missing: {missing_indexes}. Without them the "
            f"database does not enforce tenant uniqueness, it only documents it."
        )

    if "workflow_runs" in present and _has_global_unique_document_hash(conn):
        problems.append(
            "workflow_runs still carries a GLOBAL unique index on document_hash alone: one tenant's "
            "document would block another tenant's identical bytes."
        )

    # Nullability, defaults and tenant-consistent foreign keys, per canonical table.
    for table in CANONICAL_TENANT_TABLES:
        if table in present:
            problems.extend(_column_problems(conn, table))
            problems.extend(_foreign_key_problems(conn, table))

    if "effect_grants" not in present:
        problems.append(
            "the canonical effect_grants ledger is missing: there is nowhere to record a logical "
            "effect's single commitment."
        )
    else:
        problems.extend(_ledger_problems(conn))
        problems.extend(_column_problems(conn, "effect_grants"))

    problems.extend(_second_ledger_problems(conn, present))
    problems.extend(_enforcement_problems(conn))
    problems.extend(_version_problems(conn, present))
    return problems


def _version_problems(conn: sqlite3.Connection, present: set[str]) -> list[str]:
    if "schema_migrations" not in present:
        return []
    stamped = {
        r[0].split(":", 1)[1]
        for r in conn.execute(
            "SELECT step FROM schema_migrations WHERE migration = ? AND step LIKE 'version:%'",
            (MIGRATION_ID,),
        ).fetchall()
    }
    # An unstamped-but-structurally-canonical database is ready: structure is the truth, the stamp is
    # bookkeeping. A stamp we do not recognise is NOT ready - that is a newer shape, and guessing at
    # a schema written by a binary we are not is precisely the mixed-version hazard.
    unknown = sorted(v for v in stamped if v != SCHEMA_VERSION)
    if unknown:
        return [
            f"database carries schema version(s) {unknown}, this binary speaks {SCHEMA_VERSION!r}. "
            f"Refusing: an older process may not write a newer tenant-first shape."
        ]
    return []


def _ledger_problems(conn: sqlite3.Connection) -> list[str]:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='effect_grants'"
    ).fetchone()
    if not row or not row[0]:
        return ["effect_grants exists but its DDL could not be read"]
    m = re.search(r"CHECK\s*\(\s*state\s+IN\s*\(([^)]*)\)", row[0], re.IGNORECASE | re.DOTALL)
    if not m:
        return [
            "effect_grants does not constrain `state` structurally: the eight canonical states would "
            "be a convention, and a ninth would be insertable."
        ]
    constrained = set(re.findall(r"'([A-Z_]+)'", m.group(1)))
    if constrained != set(GRANT_STATES):
        return [
            f"effect_grants constrains {sorted(constrained)}; the canonical states are "
            f"{sorted(GRANT_STATES)}. Missing: {sorted(set(GRANT_STATES) - constrained)}; "
            f"unexpected: {sorted(constrained - set(GRANT_STATES))}"
        ]
    return []


# --------------------------------------------------------------------------------------------
# Blocker 3: the invariants a database must actually ENFORCE, not merely declare in a name.
#
# Everything below reads structure out of the live database and compares it to what TARGET_SCHEMA
# says. Nothing is trusted because an index has a familiar name or a migration marker says done -
# a marker is a claim about the past, and the question this oracle answers is about the present.
# --------------------------------------------------------------------------------------------

def _canonical_fks() -> dict[str, list[tuple[tuple[str, ...], str, tuple[str, ...]]]]:
    """Parse the REQUIRED foreign keys out of TARGET_SCHEMA itself.

    Derived, never hand-maintained: a second list would drift from the schema the moment either
    moved, and a readiness oracle that disagrees with the thing it validates is worse than none.
    """
    out: dict[str, list[tuple[tuple[str, ...], str, tuple[str, ...]]]] = {}
    for table, ddl in TARGET_SCHEMA.items():
        fks = []
        for m in re.finditer(
            r"FOREIGN\s+KEY\s*\(([^)]*)\)\s*REFERENCES\s+(\w+)\s*\(([^)]*)\)", ddl, re.IGNORECASE
        ):
            child = tuple(c.strip() for c in m.group(1).split(",") if c.strip())
            parent_cols = tuple(c.strip() for c in m.group(3).split(",") if c.strip())
            fks.append((child, m.group(2), parent_cols))
        if fks:
            out[table] = fks
    return out


def _canonical_columns(table: str) -> dict[str, dict]:
    """Column contract (nullability + default) for one canonical table, from TARGET_SCHEMA."""
    ddl = TARGET_SCHEMA.get(table, "")
    spec: dict[str, dict] = {}
    body = ddl[ddl.find("(") + 1: ddl.rfind(")")] if "(" in ddl else ""
    for raw in body.split("\n"):
        line = raw.strip().rstrip(",")
        if not line or line.upper().startswith(("PRIMARY KEY", "FOREIGN KEY", "UNIQUE", "CHECK", "--")):
            continue
        # Strip the trailing comment FIRST. `gate_decision TEXT,  -- P8: ... NOT NULL at P8` is a
        # NULLABLE column whose comment says when it becomes required; reading the whole line makes
        # the oracle demand NOT NULL today and call every canonical database unready. A parser that
        # reads prose as schema will eventually read the wrong prose.
        definition = line.split("--", 1)[0].strip().rstrip(",")
        if not definition:
            continue
        parts = definition.split()
        if len(parts) < 2:
            continue
        upper = definition.upper()
        spec[parts[0]] = {
            "notnull": "NOT NULL" in upper,
            "has_default": " DEFAULT " in f" {upper} ",
        }
    return spec


def _column_problems(conn: sqlite3.Connection, table: str) -> list[str]:
    """Nullability and defaults on the tenant column and every other canonical NOT NULL column.

    A nullable tenant is a row whose owner is unknown, and a tenant DEFAULT is worse: it invents an
    owner silently. Both would satisfy a check that only asked whether the column exists.
    """
    problems: list[str] = []
    canonical = _canonical_columns(table)
    live = {r[1]: r for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    for name, spec in canonical.items():
        row = live.get(name)
        if row is None:
            problems.append(f"{table}.{name} is missing (canonical schema declares it)")
            continue
        notnull, default = bool(row[3]), row[4]
        if spec["notnull"] and not notnull:
            problems.append(
                f"{table}.{name} is NULLABLE; the canonical schema declares it NOT NULL"
                + (" — a nullable tenant is a row whose owner is unknown"
                   if name == TENANT_COLUMN else "")
            )
        if name == TENANT_COLUMN and default is not None:
            problems.append(
                f"{table}.{TENANT_COLUMN} carries DEFAULT {default!r}: a defaulted tenant invents an "
                f"owner nobody chose. Ownership is asserted, never defaulted."
            )
    return problems


def _foreign_key_problems(conn: sqlite3.Connection, table: str) -> list[str]:
    """The declared FKs must MATCH the canonical composite tenant-aware ones, in order.

    Column ORDER matters: (tenant, run_id) -> (tenant, id) and (run_id, tenant) -> (tenant, id) are
    different constraints, and only one of them says "a child may not reference another tenant's
    parent". A count of foreign keys would call both fine.
    """
    required = _canonical_fks().get(table, [])
    if not required:
        return []
    live = []
    for r in conn.execute(f"PRAGMA foreign_key_list({table})").fetchall():
        live.append((r[0], r[2], r[3], r[4], r[5], r[6]))   # id, parent, from, to, on_update, on_delete
    grouped: dict[int, dict] = {}
    for fid, parent, frm, to, on_update, on_delete in live:
        g = grouped.setdefault(fid, {"parent": parent, "from": [], "to": [],
                                     "on_update": on_update, "on_delete": on_delete})
        g["from"].append(frm)
        g["to"].append(to)
    declared = {
        (tuple(g["from"]), g["parent"], tuple(g["to"])) for g in grouped.values()
    }
    problems = []
    for child_cols, parent, parent_cols in required:
        if (child_cols, parent, parent_cols) not in declared:
            problems.append(
                f"{table} is missing its tenant-consistent foreign key "
                f"{child_cols} -> {parent}{parent_cols}. Declared: {sorted(declared) or 'none'}. "
                f"Without it a child may reference another tenant's parent."
            )
    return problems


def _enforcement_problems(conn: sqlite3.Connection) -> list[str]:
    """Declarations are not enforcement, and enforcement is not integrity.

    A database can declare every foreign key, have the pragma off, and hold orphans - all three are
    separate failures and each is reported separately.
    """
    problems: list[str] = []
    enabled = conn.execute("PRAGMA foreign_keys").fetchone()
    if not enabled or not enabled[0]:
        problems.append(
            "PRAGMA foreign_keys is OFF on this connection: every tenant-consistent foreign key is "
            "decoration. (It is silently ignored inside a transaction — enable it outside one.)"
        )
    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        # Observation, not repair: readiness never deletes an orphan to make itself pass.
        tables = sorted({str(v[0]) for v in violations})
        problems.append(
            f"foreign_key_check reports {len(violations)} existing violation(s) in {tables}: the "
            f"declarations are correct but the DATA already breaks them. Manual repair required — "
            f"readiness observes, it does not delete rows to make itself green."
        )
    return problems


def _second_ledger_problems(conn: sqlite3.Connection, present: set[str]) -> list[str]:
    """One ledger. A second table carrying commit_key + state is a second effect authority."""
    problems = []
    for table in sorted(present):
        if table in ("effect_grants",) or table.startswith("_legacy_"):
            continue
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if "commit_key" in cols and "state" in cols:
            problems.append(
                f"{table!r} carries both commit_key and state: a second effect ledger can reserve "
                f"the same logical effect independently of effect_grants."
            )
    return problems


def _has_global_unique_document_hash(conn: sqlite3.Connection) -> bool:
    """A UNIQUE index on document_hash ALONE - the live cross-tenant defect, structurally."""
    for idx in conn.execute("PRAGMA index_list(workflow_runs)").fetchall():
        name, unique = idx[1], idx[2]
        if not unique:
            continue
        cols = [r[2] for r in conn.execute(f"PRAGMA index_info({name})").fetchall()]
        if cols == ["document_hash"]:
            return True
    return False


def _pk_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = [r for r in conn.execute(f"PRAGMA table_info({table})").fetchall() if r[5]]
    rows.sort(key=lambda r: r[5])
    return [r[1] for r in rows]


def _index_names(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()}


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }


def _now() -> str:
    from .workflow import utc_now

    return utc_now()
