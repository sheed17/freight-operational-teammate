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

from freight_recon.migrations.phase2_tenant_first import (  # noqa: E402
    AssertionIncomplete,
    MigrationRefused,
    OwnerAssertion,
    migrate,
)
from freight_recon.tenant import InvalidTenant, MissingTenant  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True)
    ap.add_argument("--apply", action="store_true", help="write. Without this nothing is changed.")
    # An owner assertion is five things or it is nothing. `--assert-tenant` alone is deliberately
    # NOT accepted any more: a tenant with no actor, scope, basis or evidence is a guess with a flag.
    ap.add_argument("--assert-tenant", default=None,
                    help="Tenant these historical rows belong to. Requires --actor, --scope, "
                         "--basis and --evidence: alone it does not authorise anything.")
    ap.add_argument("--actor", default=None,
                    help="WHO is asserting this. A person or an authorized operator - never "
                         "'system', never inferred from the OS user or git.")
    ap.add_argument("--scope", default=None,
                    help="Exactly what this assertion covers (database + row population).")
    ap.add_argument("--basis", default=None,
                    help="WHY the actor believes it. A specific statement a reader could check "
                         "in a year - not 'confirmed'.")
    ap.add_argument("--evidence", default=None,
                    help="Where the basis can be verified: ticket, signed message, onboarding record.")
    args = ap.parse_args()
    assertion = None
    partial = [f for f, v in (("--assert-tenant", args.assert_tenant), ("--actor", args.actor),
                              ("--scope", args.scope), ("--basis", args.basis),
                              ("--evidence", args.evidence)) if v]
    if partial:
        try:
            # Built and validated BEFORE the database is opened: an incomplete assertion must cost
            # nothing, not even a file handle.
            assertion = OwnerAssertion(
                actor_id=args.actor or "", tenant=args.assert_tenant or "",
                scope=args.scope or "", operational_basis=args.basis or "",
                evidence_reference=args.evidence or "",
            )
        except (AssertionIncomplete, InvalidTenant, MissingTenant) as exc:
            print(f"MIGRATION REFUSED — incomplete owner assertion: {exc}", file=sys.stderr)
            print(f"  supplied: {', '.join(partial)}", file=sys.stderr)
            return 2
        print(f"OWNER ASSERTION\n  actor    : {assertion.actor_id}\n  tenant   : {assertion.tenant}\n"
              f"  scope    : {assertion.scope}\n  basis    : {assertion.operational_basis}\n"
              f"  evidence : {assertion.evidence_reference}\n"
              f"  tables   : {', '.join(assertion.affected_tables)}\n"
              f"  mode     : {'APPLY' if args.apply else 'DRY RUN (nothing is written)'}",
              file=sys.stderr)
    try:
        rep = migrate(args.db, assertion=assertion, dry_run=not args.apply)
    except (AssertionIncomplete, InvalidTenant, MissingTenant) as exc:
        # A rejected owner assertion is an operator error, not a crash. It gets the same clean
        # refusal as any other, because a traceback invites someone to "work around" it.
        print(f"MIGRATION REFUSED — invalid owner assertion: {exc}", file=sys.stderr)
        return 2
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
