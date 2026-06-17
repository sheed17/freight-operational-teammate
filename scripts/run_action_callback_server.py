"""Run the local Neyma signed-action callback server for dogfood testing."""

from __future__ import annotations

import argparse
import ipaddress
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from freight_recon.action_callback import run_callback_server  # noqa: E402
from freight_recon.channels import build_signer, load_delivery_config  # noqa: E402
from freight_recon.delivery import DeliverySigner  # noqa: E402
from run_dogfood_pilot import DEFAULT_WORKSPACE  # noqa: E402
from run_workflow import load_synthetic_loads  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--workspace", default=str(DEFAULT_WORKSPACE))
    parser.add_argument("--db", default=None, help="Workflow SQLite DB path; defaults to workspace DB")
    parser.add_argument("--corpus", default=None, help="Synthetic corpus path; defaults to workspace corpus")
    parser.add_argument(
        "--client-config",
        default=None,
        help="Client config; when set, the action-token signer and Slack interactivity route "
        "(/slack/actions) use that customer's secrets, enabling live Slack button clicks",
    )
    parser.add_argument(
        "--allow-local-dev-secret",
        action="store_true",
        help="Use the fixed local dogfood signing secret when NEYMA_DELIVERY_SECRET is not set",
    )
    args = parser.parse_args()

    workspace = Path(args.workspace)
    db_path = Path(args.db) if args.db else workspace / "neyma_workflow.sqlite3"
    corpus = Path(args.corpus) if args.corpus else workspace / "synthetic_corpus"

    slack_signing_secret = None
    if args.client_config:
        # Wire the customer's real secrets: the signer must match the secret used to sign tokens at
        # dispatch, and the Slack route needs the Slack signing secret to verify button clicks.
        config = load_delivery_config(args.client_config)
        if config is None:
            parser.error(f"no delivery config found in {args.client_config}")
        signer = build_signer(config)
        if config.slack is not None:
            slack_signing_secret = os.environ.get(config.slack.signing_secret_env)
            if not slack_signing_secret:
                parser.error(f"Slack signing secret env var is not set: {config.slack.signing_secret_env}")
    else:
        local_dev_secret_enabled = (
            args.allow_local_dev_secret or os.environ.get("NEYMA_ALLOW_LOCAL_DELIVERY_SECRET") == "1"
        )
        if local_dev_secret_enabled and not _is_loopback_host(args.host):
            parser.error("the local dogfood delivery secret may only be used with a loopback host")
        signer = DeliverySigner.from_env(allow_local_dev=args.allow_local_dev_secret)

    follow_up_loads = None
    if corpus.exists():
        follow_up_loads = {load.load_id: load for load in load_synthetic_loads(corpus)}

    server = run_callback_server(
        host=args.host,
        port=args.port,
        db_path=str(db_path),
        signer=signer,
        follow_up_loads=follow_up_loads,
        slack_signing_secret=slack_signing_secret,
    )
    print(f"Neyma action callback server listening on http://{args.host}:{args.port}")
    print("Email actions: /email/action?token=<signed-token>")
    print("JSON actions: POST /actions/signed {'token': '<signed-token>'}")
    if slack_signing_secret:
        print("Slack interactivity: POST /slack/actions (Slack-signed)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Neyma action callback server")
    finally:
        server.server_close()
    return 0


def _is_loopback_host(host: str) -> bool:
    normalized = host.strip().lower()
    if normalized in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
