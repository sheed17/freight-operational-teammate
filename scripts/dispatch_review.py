"""Dispatch review payloads through configured Slack/email channels."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from freight_recon.channels import build_signer, load_delivery_config  # noqa: E402
from freight_recon.delivery import build_delivery_message, record_delivery_message  # noqa: E402
from freight_recon.delivery_dispatch import DispatchMode, dispatch_delivery_message  # noqa: E402
from freight_recon.review import ReviewPayload  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402
from run_review import DEFAULT_OUTPUT as DEFAULT_REVIEW_PAYLOADS  # noqa: E402
from run_workflow import DEFAULT_DB  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLIENT_CONFIG = ROOT / "configs" / "clients" / "neyma_test_freight.yaml"
DEFAULT_ATTEMPTS = ROOT / "data" / "active_workspace" / "delivery_dispatch_attempts.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payloads", default=str(DEFAULT_REVIEW_PAYLOADS))
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--client-config", default=str(DEFAULT_CLIENT_CONFIG))
    parser.add_argument("--mode", choices=[mode.value for mode in DispatchMode], default=DispatchMode.DRY_RUN.value)
    parser.add_argument("--run-id", type=int, help="Dispatch only this run id")
    parser.add_argument("--out", default=str(DEFAULT_ATTEMPTS))
    parser.add_argument("--email-outbox-dir", default=None)
    parser.add_argument("--text", action="store_true")
    parser.add_argument(
        "--allow-local-dev-secret",
        action="store_true",
        help="Use the fixed local dogfood signing secret when the configured secret is missing",
    )
    args = parser.parse_args()

    config = load_delivery_config(args.client_config)
    if config is None:
        raise SystemExit(f"No delivery config found: {args.client_config}")
    mode = DispatchMode(args.mode)
    signer = build_signer(config) if os.environ.get(config.action_token_secret_env) else None
    if signer is None and not args.allow_local_dev_secret:
        raise SystemExit(
            f"Missing action-token secret: {config.action_token_secret_env}. "
            "For local dogfood only, rerun with --allow-local-dev-secret."
        )
    if signer is None:
        from freight_recon.delivery import DeliverySigner  # noqa: PLC0415

        signer = DeliverySigner.from_env(allow_local_dev=True)

    raw = json.loads(Path(args.payloads).read_text(encoding="utf-8"))
    payloads = [ReviewPayload.model_validate(item) for item in raw]
    if args.run_id is not None:
        payloads = [payload for payload in payloads if payload.run_id == args.run_id]

    attempts = []
    store = WorkflowStore(args.db)
    try:
        for payload in payloads:
            message = build_delivery_message(payload, signer, actor="Rasheed")
            record_delivery_message(store, message)
            attempts.extend(
                dispatch_delivery_message(
                    store,
                    message,
                    config,
                    env=os.environ,
                    mode=mode,
                    email_outbox_dir=args.email_outbox_dir,
                )
            )
    finally:
        store.close()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps([attempt.model_dump(mode="json") for attempt in attempts], indent=2), encoding="utf-8")
    if args.text:
        for attempt in attempts:
            print(f"[{attempt.status.value}] {attempt.channel.value} {attempt.destination or '-'} — {attempt.note}")
    print(json.dumps([attempt.model_dump(mode="json") for attempt in attempts], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
