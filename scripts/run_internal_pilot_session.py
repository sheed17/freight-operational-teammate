"""Run a multi-day internal Neyma dogfood pilot session."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from freight_recon.pilot_session import render_pilot_session, run_pilot_session  # noqa: E402
from run_dogfood_pilot import DEFAULT_WORKSPACE, run_pilot  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=str(DEFAULT_WORKSPACE / "pilot_session"))
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--loads-per-day", type=int, default=18)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--age-hours", type=int, default=48)
    parser.add_argument("--text", action="store_true")
    args = parser.parse_args()

    ledger = run_pilot_session(
        session_workspace=Path(args.workspace),
        run_pilot=run_pilot,
        days=args.days,
        loads_per_day=args.loads_per_day,
        seed=args.seed,
        age_hours=args.age_hours,
    )
    print(ledger.model_dump_json(indent=2))
    if args.text:
        print()
        print(render_pilot_session(ledger))
    return 0 if ledger.ready_for_design_partner else 1


if __name__ == "__main__":
    raise SystemExit(main())
