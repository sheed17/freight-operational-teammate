"""Preflight a customer's delivery channels: validate config and resolve named secrets (no send)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from freight_recon.channels import load_delivery_config, verify_delivery_config  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLIENT_CONFIG = ROOT / "configs" / "clients" / "neyma_test_freight.yaml"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-config", default=str(DEFAULT_CLIENT_CONFIG))
    args = parser.parse_args()

    config = load_delivery_config(args.client_config)
    if config is None:
        print(f"No `delivery:` block found in {args.client_config}")
        return 1

    checks = verify_delivery_config(config)
    payload = {
        "client_config": args.client_config,
        "default_channel": config.default_channel.value,
        "checks": [check.model_dump(mode="json") for check in checks],
        "ready": all(check.ok for check in checks),
    }
    print(json.dumps(payload, indent=2))
    for check in checks:
        status = "OK  " if check.ok else "MISS"
        detail = ""
        if check.missing_secrets:
            detail = f" missing env: {', '.join(check.missing_secrets)}"
        elif check.issues:
            detail = f" issues: {'; '.join(check.issues)}"
        print(f"[{status}] {check.channel.value}{detail}", file=sys.stderr)
    return 0 if payload["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
