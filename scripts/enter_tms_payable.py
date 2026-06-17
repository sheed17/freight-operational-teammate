"""Enter an APPROVED payable into the mock TMS through the gated write path (confirm + readback)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from freight_recon.tms_write import ChargeLine, MockTmsWriteLedger, enter_approved_payable  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402
from run_workflow import DEFAULT_DB  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = ROOT / "data" / "active_workspace" / "tms_payable_ledger.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id", type=int)
    parser.add_argument("--amount", required=True)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    parser.add_argument("--charge", action="append", default=[], help="name=amount (repeatable)")
    parser.add_argument(
        "--fail-mode",
        action="append",
        default=[],
        choices=["duplicate", "session_expired", "readback_mismatch"],
        help="inject a mock TMS failure mode for drills",
    )
    parser.add_argument("--no-write-enabled", action="store_true", help="simulate the TMS-write feature gate being off")
    args = parser.parse_args()

    charges = []
    for raw in args.charge:
        name, _, amount = raw.partition("=")
        charges.append(ChargeLine(name=name, amount=amount))

    store = WorkflowStore(args.db)
    ledger = MockTmsWriteLedger(args.ledger, fail_modes=frozenset(args.fail_mode))
    try:
        outcome = enter_approved_payable(
            store,
            ledger,
            args.run_id,
            amount=args.amount,
            charges=charges,
            tms_write_enabled=not args.no_write_enabled,
        )
    finally:
        store.close()
    print(json.dumps(outcome.model_dump(mode="json"), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
