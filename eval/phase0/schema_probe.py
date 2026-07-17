"""Tenant posture, recomputed from the real CREATE TABLE statements AND from a real database.

The canonical rule (AC-SEC-001) is not "a tenant column exists" — it is that tenant is FIRST in the
key. A `tenant` column alongside a `commit_key TEXT PRIMARY KEY` is not tenant isolation: the
uniqueness domain is still global, so one tenant's key can collide with another's.

U2.6BC — WHY THIS PROBE NOW HAS TWO LEGS

Phase 0 read source text, which was the right oracle while the answer was "red": you cannot ship a
tenant-first schema you have not written. It is the wrong oracle for "green". Source text says what
was TYPED; it cannot say what a database actually gets. A DDL string that never executes, or a
migration that half-runs, would leave the source reading canonical and the live schema global — the
probe would go green over exactly the defect it exists to catch.

So `tables()` still parses the source (it is what REG-1 needs: a new tenantless table is visible in
the text the moment it is written), and `live_tables()` builds a real store and reads
`sqlite_master` back. AC-SEC-001 requires BOTH, because either alone is a way to be wrong.
"""

from __future__ import annotations

import re
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .evaluation import Evaluation
from .sources import SRC, rel, require

TENANT_COLUMNS = ("tenant", "tenant_id")


@dataclass
class Table:
    name: str
    source: str
    columns: list[str]
    primary_key: list[str]
    has_tenant_column: bool
    tenant_first_in_key: bool

    @property
    def canonical(self) -> bool:
        return self.tenant_first_in_key


def _parse_primary_key(body: str, columns: list[tuple[str, str]]) -> list[str]:
    m = re.search(r"PRIMARY\s+KEY\s*\(([^)]*)\)", body, re.IGNORECASE)
    if m:
        return [c.strip() for c in m.group(1).split(",") if c.strip()]
    for name, coldef in columns:
        if re.search(r"\bPRIMARY\s+KEY\b", coldef, re.IGNORECASE):
            return [name]
    return []


def tables() -> tuple[list[Table], Evaluation]:
    ev = Evaluation(name="schema.tables")
    found: list[Table] = []
    for path in sorted(SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "CREATE TABLE" not in text:
            continue
        ev.sources_inspected.append(rel(path))
        # Terminated by `);` (an executescript) OR by `)"""` (a DDL string in TARGET_SCHEMA). The
        # canonical schema moved into the latter when the migration became its single source, and a
        # regex that only knew `);` silently parsed ZERO tables and reported no offenders — a green
        # that had inspected nothing. `require_population` is what caught it.
        for m in re.finditer(
            r'CREATE TABLE(?:\s+IF NOT EXISTS)?\s+(\w+)\s*\((.*?)\n\s*\)(?:;|""")',
            text,
            re.DOTALL | re.IGNORECASE,
        ):
            name, body = m.group(1), m.group(2)
            ev.candidates.append(name)
            columns: list[tuple[str, str]] = []
            for raw in body.split("\n"):
                line = raw.strip().rstrip(",")
                if not line or line.upper().startswith(("PRIMARY KEY", "UNIQUE", "FOREIGN KEY", "CHECK", "--")):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    columns.append((parts[0], line))
            if not columns:
                ev.unmatched.append(f"{path.name}: table {name} parsed with zero columns")
                continue
            colnames = [c for c, _ in columns]
            pk = _parse_primary_key(body, columns)
            has_tenant = any(c in TENANT_COLUMNS for c in colnames)
            tenant_first = bool(pk) and pk[0] in TENANT_COLUMNS
            t = Table(name, rel(path), colnames, pk, has_tenant, tenant_first)
            ev.parsed.append(name)
            if name in [x.name for x in found]:
                ev.duplicates.append(name)
            else:
                found.append(t)
                ev.accepted.append(name)
    require(SRC)
    return found, ev


def noncanonical_tables() -> list[Table]:
    ts, _ = tables()
    return [t for t in ts if not t.canonical]


def live_tables() -> tuple[list[Table], Evaluation]:
    """The posture of a REAL database, built the way production builds one.

    This is the leg that cannot be fooled by a DDL string nobody executes. It constructs an actual
    `WorkflowStore` on a throwaway path and reads the schema back out of `sqlite_master`, so what is
    reported is what a tenant's rows would really live in.
    """
    ev = Evaluation(name="schema.live_tables")
    from freight_recon.workflow import WorkflowStore

    found: list[Table] = []
    with tempfile.TemporaryDirectory() as tmp:
        store = WorkflowStore(Path(tmp) / "probe.sqlite3", tenant="schema-probe-tenant")
        try:
            ev.sources_inspected.append(f"live:{store.db_path.name}")
            names = [
                r[0]
                for r in store.conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
            ]
            for name in sorted(names):
                ev.candidates.append(name)
                info = store.conn.execute(f"PRAGMA table_info({name})").fetchall()
                colnames = [r[1] for r in info]
                pk_rows = sorted([r for r in info if r[5]], key=lambda r: r[5])
                pk = [r[1] for r in pk_rows]
                t = Table(
                    name,
                    "live",
                    colnames,
                    pk,
                    any(c in TENANT_COLUMNS for c in colnames),
                    bool(pk) and pk[0] in TENANT_COLUMNS,
                )
                ev.parsed.append(name)
                found.append(t)
                ev.accepted.append(name)
        finally:
            store.close()
    return found, ev
