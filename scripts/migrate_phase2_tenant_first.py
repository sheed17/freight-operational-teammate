#!/usr/bin/env python3
"""Phase-2 migration CLI: tenant-first persistence + the one canonical Effect Grant ledger.

    # look, change nothing (default)
    python scripts/migrate_phase2_tenant_first.py --db data/.../neyma_workflow.sqlite3

    # apply, quarantining any history whose tenant cannot be established
    python scripts/migrate_phase2_tenant_first.py --db ... --apply

    # apply, ASSERTING that this workspace's untenanted history belongs to one tenant.
    # This is an owner assertion, recorded as one. It is not a derivation and not a default.
    python scripts/migrate_phase2_tenant_first.py --db ... --apply --assert-tenant acme

There is no way to make the migration guess. Absent an assertion, ambiguous rows are quarantined
intact for a human to settle.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from freight_recon.migrations.phase2_tenant_first import MigrationRefused, migrate  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True)
    ap.add_argument("--apply", action="store_true", help="write. Without this nothing is changed.")
    ap.add_argument("--assert-tenant", default=None,
                    help="OWNER ASSERTION: this workspace's untenanted history belongs to this tenant.")
    args = ap.parse_args()
    try:
        rep = migrate(args.db, assert_tenant=args.assert_tenant, dry_run=not args.apply)
    except MigrationRefused as exc:
        print(f"MIGRATION REFUSED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(rep.as_dict(), indent=2, sort_keys=True))
    quarantined = sum(rep.rows_quarantined.values())
    if quarantined:
        print(
            f"\n*** {quarantined} row(s) QUARANTINED: their tenant could not be established without "
            f"guessing, and this migration does not guess. They are intact in `migration_quarantine`. "
            f"Re-run with --assert-tenant <tenant> to claim them, or settle them by hand.",
            file=sys.stderr,
        )
    if not args.apply:
        print("\n(dry run — nothing was written)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
