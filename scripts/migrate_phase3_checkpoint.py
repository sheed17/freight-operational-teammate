#!/usr/bin/env python3
"""Apply the Phase-3 checkpoint schema to an existing Phase-2 canonical database.

Create-only, idempotent, resumable: adds checkpoint_witnesses, brakes, platform_brake, their
indexes and append-only triggers, and replaces the ledger's strict one-row-per-effect index with
the live-hold form (see src/freight_recon/migrations/phase3_checkpoint.py for why). Moves no
data. Fresh databases never need this — WorkflowStore builds them canonical-with-P3 directly.

Refuses a database that is not Phase-2 canonical first: this migration extends the canonical
shape, it does not repair a legacy one. Run migrations/phase2_tenant_first first if refused.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from freight_recon.migrations.phase3_checkpoint import (  # noqa: E402
    create_phase3_schema,
    phase3_readiness_problems,
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
              f"application; this migration only extends an existing Phase-2 database.")
        return 2

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        # Phase-2 canonicality first, judged by the one readiness oracle - minus the Phase-3
        # problems this migration exists to fix.
        from freight_recon.schema import schema_readiness_problems  # noqa: E402

        pre_p3 = set(phase3_readiness_problems(conn))
        other_problems = [p for p in schema_readiness_problems(conn) if p not in pre_p3]
        # Foreign-key enforcement is per-connection, not a database property: this read-only
        # report connection never enabled the pragma, so that finding is about US, not the file.
        other_problems = [p for p in other_problems if "PRAGMA foreign_keys is OFF" not in p]
        if other_problems:
            print("REFUSED: this database is not Phase-2 canonical. Phase 3 extends the "
                  "canonical shape; it does not repair a legacy one. Problems:")
            for p in other_problems:
                print(f"  - {p}")
            print("Run scripts/migrate_phase2_tenant_first.py first.")
            return 2

        problems = sorted(pre_p3)
        if not problems:
            print("ALREADY CANONICAL: the Phase-3 checkpoint schema is fully present. No-op.")
            return 0
        print("Phase-3 structure missing:")
        for p in problems:
            print(f"  - {p}")
        if not args.apply:
            print("\nDRY RUN ONLY. Re-run with --apply to create the missing structure.")
            return 0

        from freight_recon.migrations.phase3_checkpoint import stamp_phase3_version  # noqa: E402
        from freight_recon.workflow import utc_now  # noqa: E402

        performed = create_phase3_schema(conn, now=utc_now())
        for step in performed:
            print(f"  applied: {step}")
        remaining = phase3_readiness_problems(conn)
        if remaining:
            print("MIGRATION INCOMPLETE - remaining problems (safe to re-run):")
            for p in remaining:
                print(f"  - {p}")
            return 1
        # The completion marker LAST, only now that readiness was verified above.
        stamp_phase3_version(conn, now=utc_now())
        print("MIGRATION COMPLETE: the database now carries the Phase-3 checkpoint schema.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
