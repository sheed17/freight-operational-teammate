"""Verify supervised design-partner pilot package safety and completeness."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from freight_recon.design_partner_package import verify_design_partner_package  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-config", default=str(ROOT / "configs" / "clients" / "design_partner_template.yaml"))
    parser.add_argument(
        "--pilot-ledger",
        default=str(ROOT / "data" / "active_workspace" / "pilot_session" / "pilot_session_ledger.json"),
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = verify_design_partner_package(
        client_config_path=Path(args.client_config),
        pilot_ledger_path=Path(args.pilot_ledger),
    )
    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        print(f"ready: {str(result.ready).lower()}")
        for check in result.checks:
            status = "PASS" if check.ok else "FAIL"
            print(f"{status} {check.name}: {check.detail}")
    return 0 if result.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
