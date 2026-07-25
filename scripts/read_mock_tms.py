"""Read a load/payable from the generated mock TMS through the bounded adapter."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from freight_recon.tms_adapter import MockTmsReadAdapter  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TMS = ROOT / "data" / "active_workspace" / "site" / "tms"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("load_id")
    parser.add_argument("--root", default=str(DEFAULT_TMS))
    parser.add_argument("--payable", action="store_true", help="Read carrier payable queue row")
    args = parser.parse_args()

    adapter = MockTmsReadAdapter(args.root)
    result = adapter.read_payable(args.load_id) if args.payable else adapter.read_load(args.load_id)
    print(json.dumps(result.model_dump(mode="json"), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
