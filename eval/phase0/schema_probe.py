"""Tenant posture, recomputed from the real CREATE TABLE statements.

Phase 0 does NOT migrate the schema. It records the current posture and prevents it getting worse.

The canonical rule (AC-SEC-001) is not "a tenant column exists" — it is that tenant is FIRST in the
key. A `tenant` column alongside a `commit_key TEXT PRIMARY KEY` is not tenant isolation: the
uniqueness domain is still global, so one tenant's key can collide with another's.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

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
        for m in re.finditer(
            r"CREATE TABLE(?:\s+IF NOT EXISTS)?\s+(\w+)\s*\((.*?)\n\s*\);", text, re.DOTALL | re.IGNORECASE
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
