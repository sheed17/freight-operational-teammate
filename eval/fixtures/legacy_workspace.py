"""Deterministic builder for the pre-Phase-2 legacy workspace database.

THE HERMETICITY CORRECTION (U-HANDOFF-1B, H-2). The Phase-2 qualification suites used to copy
`data/active_workspace/neyma_workflow.sqlite3` - the founder's live, gitignored, developer-local
workspace. On a clean clone that file does not exist, so 46 tests failed and the recorded green
was a false green: the suite proved the migration against a database only one machine possessed.

This module replaces that dependency. It builds a byte-deterministic database with the SAME
STRUCTURAL SHAPE the live workspace had - the exact legacy DDL and the exact population profile -
from committed code alone:

    workflow_runs    18 rows   (15 NEEDS_REVIEW + 3 DONE)
    audit_events    102 rows   (4 per run + 2 extra per NEEDS_REVIEW run: 18*4 + 15*2)
    security_events   0 rows
    sqlite_sequence  workflow_runs=18, audit_events=102

No founder data is copied. Every value is synthesized deterministically (fixed timestamps,
sha256-derived document hashes), so repeated builds are identical, test order cannot matter, and
no home-directory or checkout-local state is read. The migration tests exercise exactly the same
code paths they always did - real SQLite, the real legacy DDL, the real migration - against
inputs any clean clone can reproduce.

The population constants are exported so tests assert against THE BUILDER, not against a magic
number whose provenance nobody can check.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

# The canonical fixture population. 18/15/3/102 mirror the structural profile of the workspace
# the original qualification ran against, so the qualification story is continuous - but the
# numbers are now DEFINED here, derivable and guarded, not inherited from a file nobody else has.
LEGACY_RUNS = 18
LEGACY_NEEDS_REVIEW = 15
LEGACY_DONE = 3
EVENTS_PER_RUN = 4          # document_received, extraction_recorded, reconciliation_completed, route_after_reconciliation
EXTRA_REVIEW_EVENTS = 2     # review_payload_created, delivery_message_created
LEGACY_AUDIT_EVENTS = LEGACY_RUNS * EVENTS_PER_RUN + LEGACY_NEEDS_REVIEW * EXTRA_REVIEW_EVENTS

assert LEGACY_NEEDS_REVIEW + LEGACY_DONE == LEGACY_RUNS
assert LEGACY_AUDIT_EVENTS == 102  # the derivation above must keep producing the qualified profile

_BASE_TS = "2026-06-25T04:13:{:02d}.000000+00:00"

LEGACY_DDL = """
CREATE TABLE workflow_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    load_id TEXT NOT NULL,
    document_hash TEXT NOT NULL UNIQUE,
    state TEXT NOT NULL,
    invoice_number TEXT,
    carrier TEXT,
    outcome TEXT,
    reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    from_state TEXT,
    to_state TEXT,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES workflow_runs(id)
);
CREATE TABLE security_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _doc_hash(i: int) -> str:
    return hashlib.sha256(f"legacy-fixture-doc-{i}".encode()).hexdigest()


def build_legacy_workspace(path: str | Path) -> Path:
    """Create the deterministic legacy workspace database at `path` and return it."""
    path = Path(path)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    try:
        conn.executescript(LEGACY_DDL)
        for i in range(1, LEGACY_RUNS + 1):
            state = "DONE" if i <= LEGACY_DONE else "NEEDS_REVIEW"
            ts = _BASE_TS.format(i % 60)
            conn.execute(
                "INSERT INTO workflow_runs (load_id, document_hash, state, invoice_number, "
                "carrier, outcome, reason, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    f"LD-56{i:04d}",
                    _doc_hash(i),
                    state,
                    f"INV-2026{i:03d}",
                    f"Fixture Carrier {i:02d} LLC",
                    "clean" if state == "DONE" else None,
                    None if state == "DONE" else "variance_review",
                    ts,
                    ts,
                ),
            )
            base_events = [
                "document_received",
                "extraction_recorded",
                "reconciliation_completed",
                "route_after_reconciliation",
            ]
            if state == "NEEDS_REVIEW":
                base_events += ["review_payload_created", "delivery_message_created"]
            for k, ev in enumerate(base_events):
                conn.execute(
                    "INSERT INTO audit_events (run_id, event_type, actor, from_state, to_state, "
                    "payload_json, created_at) VALUES (?,?,?,?,?,?,?)",
                    (i, ev, "system", None, None,
                     f'{{"fixture": true, "load_id": "LD-56{i:04d}", "step": {k}}}', ts),
                )
        conn.commit()
    finally:
        conn.close()
    return path


def legacy_workspace_copy(tmp_dir: str | Path, name: str = "legacy_workspace.sqlite3") -> str:
    """Drop-in replacement for the old shutil.copy(REAL, ...) helpers: build into a temp dir."""
    return str(build_legacy_workspace(Path(tmp_dir) / name))
