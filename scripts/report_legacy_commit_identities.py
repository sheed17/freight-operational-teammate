#!/usr/bin/env python3
"""U1.5 — the historical Commit Key backfill, REPORT-ONLY. It writes nothing, ever.

Phase 1 changed how a logical effect is identified. Every reservation written before it carries a
key derived from the DELETED amount-keyed algorithm, so the same logical effect now computes a
different key. This report finds those rows and classifies them. It does not fix them: the ledger
backfill that adjudicates them is Phase 2 (U2.4).

The classification rule that matters:

    DO NOT INFER SUCCESS. No report and no migration may manufacture a verified outcome.

  RESOLVED_COMMITTED    - the row proves the effect happened. Its reservation is preserved so the
                          canonical path refuses to repeat it.
  UNRESOLVED            - RESERVED / NEEDS_VERIFICATION: a prior run reserved and never confirmed.
                          Nobody knows whether the TMS was written. It gets an owner, not a guess.
  MANUAL_REVIEW_REQUIRED - two or more legacy rows for ONE logical effect. Under the old algorithm
                          different amounts made different keys, so this IS evidence of a historical
                          double-commit. Do not merge them. Do not pick one. A human settles it.

Usage:  python scripts/report_legacy_commit_identities.py --db path/to/workflow.sqlite3
"""

import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from freight_recon.workflow import WorkflowStore  # noqa: E402

COMMITTED_STATUSES = {"COMMITTED", "DONE", "VERIFIED"}
UNRESOLVED_STATUSES = {"RESERVED", "NEEDS_VERIFICATION", ""}


def classify(rows: list[dict]) -> str:
    if len(rows) > 1:
        return "MANUAL_REVIEW_REQUIRED"
    status = str((rows[0].get("payload") or {}).get("status", "")).upper()
    if status in COMMITTED_STATUSES:
        return "RESOLVED_COMMITTED"
    if status in UNRESOLVED_STATUSES:
        return "UNRESOLVED"
    return "MANUAL_REVIEW_REQUIRED"


def report(db: str) -> dict:
    store = WorkflowStore(db)
    try:
        rows = [
            {
                "commit_key": r["commit_key"], "tenant": r["tenant"], "lane": r["lane"],
                "load_ref": r["load_ref"], "party": r["party"],
                "approved_amount": r["approved_amount"],
                "payload": json.loads(r["payload_json"]), "created_at": r["created_at"],
            }
            for r in store.conn.execute("SELECT * FROM operation_commit_claims").fetchall()
        ]
    finally:
        store.close()

    groups = collections.defaultdict(list)
    for r in rows:
        groups[(r["tenant"], r["lane"], r["load_ref"], r["party"])].append(r)

    findings = [
        {
            "logical_effect": dict(zip(("tenant", "lane", "load_ref", "party"), k)),
            "legacy_rows": len(v),
            "disposition": classify(v),
            "amounts": [r["approved_amount"] for r in v],
            "commit_keys": [r["commit_key"] for r in v],
        }
        for k, v in sorted(groups.items())
    ]
    counts = collections.Counter(f["disposition"] for f in findings)
    return {
        "database": db,
        "total_rows": len(rows),
        "logical_effects": len(findings),
        "dispositions": dict(counts),
        "findings": findings,
        "write_performed": False,   # always. This script has no write path.
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    args = ap.parse_args()
    out = report(args.db)
    print(json.dumps(out, indent=2, sort_keys=True))
    if out["dispositions"].get("MANUAL_REVIEW_REQUIRED"):
        print(
            f"\n*** {out['dispositions']['MANUAL_REVIEW_REQUIRED']} logical effect(s) have MULTIPLE "
            f"legacy reservations. Under the old amount-keyed identity that means the same effect "
            f"was committed more than once. This is evidence, not noise: check the TMS before "
            f"Phase 2's backfill runs. Do NOT merge these rows.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
