#!/usr/bin/env python3
"""Apply the Phase-5 event transport (outbox, inbox, cursor, parking) to an existing database.

Create-only, idempotent, resumable: adds `event_outbox`, `event_inbox`, `inbox_aggregate_cursor`
and `pending_references`, their indexes, and the append-only triggers that make the stored
envelope immutable and a consumption record undeletable. Moves no data and drops no index.

Fresh databases never need this — `WorkflowStore` builds them canonical-with-P5 directly. An
EXISTING database does need it, and deliberately is NOT auto-migrated: `WorkflowStore._migrate`
creates a canonical shape only for an empty database and otherwise touches nothing, so extending
a live schema stays an explicit act with a human behind it.

Refuses a database that is not already Phase-2/Phase-3 canonical: this migration extends the
canonical shape, it does not repair a legacy one. Run migrate_phase2_tenant_first.py and then
migrate_phase3_checkpoint.py first if refused.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from freight_recon.migrations.phase5_event_transport import (  # noqa: E402
    create_phase5_schema,
    phase5_readiness_problems,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", help="path to the SQLite database to migrate")
    parser.add_argument("--apply", action="store_true",
                        help="perform the migration (default: report only)")
    args = parser.parse_args()

    path = Path(args.database)
    if not path.exists():
        print(f"REFUSED: {path} does not exist. A fresh database is created canonical by the "
              f"application; this migration only extends an existing one.")
        return 2

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        from freight_recon.schema import schema_readiness_problems  # noqa: E402

        pre_p5 = set(phase5_readiness_problems(conn))
        other = [p for p in schema_readiness_problems(conn) if p not in pre_p5]
        # The composed oracle also reports the P5 tables as missing tenant-owned tables and the
        # strict-order index as a missing tenant-first constraint. Those ARE this migration's job,
        # so they must not be read as "the database is not canonical yet".
        p5_names = ("event_outbox", "event_inbox", "inbox_aggregate_cursor", "pending_references",
                    "ix_event_outbox_")
        other = [p for p in other if not any(name in p for name in p5_names)]
        # Foreign-key enforcement is per-connection, not a database property: this report
        # connection never enabled the pragma, so that finding is about US, not the file.
        other = [p for p in other if "PRAGMA foreign_keys is OFF" not in p]
        if other:
            print("REFUSED: this database is not canonical for the earlier phases. Phase 5 "
                  "extends the canonical shape; it does not repair a legacy one. Problems:")
            for p in other:
                print(f"  - {p}")
            print("Run scripts/migrate_phase2_tenant_first.py, then "
                  "scripts/migrate_phase3_checkpoint.py.")
            return 2

        problems = sorted(pre_p5)
        if not problems:
            print("ALREADY CANONICAL: the Phase-5 event transport is fully present. No-op.")
            return 0
        print("Phase-5 event-transport structure missing:")
        for p in problems:
            print(f"  - {p}")
        if not args.apply:
            print("\nDRY RUN ONLY. Re-run with --apply to create the missing structure.")
            return 0

        from freight_recon.migrations.phase5_event_transport import (  # noqa: E402
            stamp_phase5_version,
        )
        from freight_recon.workflow import utc_now  # noqa: E402

        for step in create_phase5_schema(conn, now=utc_now()):
            print(f"  applied: {step}")
        remaining = phase5_readiness_problems(conn)
        if remaining:
            print("MIGRATION INCOMPLETE - remaining problems (safe to re-run):")
            for p in remaining:
                print(f"  - {p}")
            return 1
        # The completion marker LAST, only now that readiness was verified above.
        stamp_phase5_version(conn, now=utc_now())
        print("MIGRATION COMPLETE: the database now carries the Phase-5 event transport.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
