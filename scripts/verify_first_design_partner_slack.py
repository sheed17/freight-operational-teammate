"""Preflight Rasheed first-design-partner real Slack setup without posting."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - optional local/runtime convenience
    pass

from freight_recon.first_design_partner import verify_first_partner_slack  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLIENT_CONFIG = ROOT / "configs" / "clients" / "rasheed_first_design_partner.yaml"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-config", default=str(DEFAULT_CLIENT_CONFIG))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = verify_first_partner_slack(args.client_config)
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
