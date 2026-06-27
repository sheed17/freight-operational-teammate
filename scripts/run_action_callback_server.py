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
from freight_recon.delivery_dispatch import slack_thread_status_poster  # noqa: E402
from freight_recon.ops_control import OpsControl  # noqa: E402
from freight_recon.post_approval_execution import (  # noqa: E402
    MockTmsAutoEntryConfig,
    maybe_execute_mock_tms_after_approval,
)
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
    parser.add_argument(
        "--auto-enter-approved-mock-tms",
        action="store_true",
        help="After an APPROVE_* Slack action, enter the approved payable into the mock TMS ledger.",
    )
    parser.add_argument(
        "--mock-tms-ledger",
        default=None,
        help="Mock TMS payable ledger path for --auto-enter-approved-mock-tms; defaults to workspace/browser_tms_payable_ledger.json",
    )
    parser.add_argument(
        "--status-file",
        default=None,
        help="Loop heartbeat the Slack `status` command reads; defaults to <workspace>/teammate_status.json",
    )
    args = parser.parse_args()

    workspace = Path(args.workspace)
    db_path = Path(args.db) if args.db else workspace / "neyma_workflow.sqlite3"
    corpus = Path(args.corpus) if args.corpus else workspace / "synthetic_corpus"
    status_file = Path(args.status_file) if args.status_file else workspace / "teammate_status.json"

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

    post_action_executor = None
    if args.auto_enter_approved_mock_tms:
        ledger_path = Path(args.mock_tms_ledger) if args.mock_tms_ledger else workspace / "browser_tms_payable_ledger.json"
        auto_entry_config = MockTmsAutoEntryConfig(enabled=True, ledger_path=str(ledger_path))
        ops_control = OpsControl(Path(db_path).parent / "ops_control.json")

        def _executor(store, outcome):
            on_status = None
            if args.client_config:
                delivery_config = load_delivery_config(args.client_config)
                if delivery_config is not None:
                    on_status = slack_thread_status_poster(store, delivery_config, env=os.environ)
            maybe_execute_mock_tms_after_approval(
                store,
                outcome,
                config=auto_entry_config,
                on_status=on_status,
                ops_control=ops_control,
            )

        post_action_executor = _executor

    # Preflight: a health/status surface wired to the wrong files reports confident falsehoods, which
    # is worse than no surface. Warn loudly if the Slack `status` command will read a DB/heartbeat the
    # loop is not actually writing (the loop and this server must share one --workspace).
    if not db_path.exists():
        print(f"WARNING: workflow DB not found at {db_path}")
        print("         -> Slack `status` counts and button actions will be wrong until it exists.")
        print("         -> point --db at the loop's DB (<loop --workspace>/workflow.sqlite3).")
    if not status_file.exists():
        print(f"WARNING: loop heartbeat not found at {status_file}")
        print("         -> Slack `status` will report NOT_STARTED until the loop writes it.")
        print("         -> point --status-file at <loop --workspace>/teammate_status.json.")

    server = run_callback_server(
        host=args.host,
        port=args.port,
        db_path=str(db_path),
        signer=signer,
        follow_up_loads=follow_up_loads,
        slack_signing_secret=slack_signing_secret,
        post_action_executor=post_action_executor,
        status_file=str(status_file),
    )
    print(f"Neyma action callback server listening on http://{args.host}:{args.port}")
    print("Email actions: /email/action?token=<signed-token>")
    print("JSON actions: POST /actions/signed {'token': '<signed-token>'}")
    if slack_signing_secret:
        print("Slack interactivity: POST /slack/actions (Slack-signed)")
    if post_action_executor is not None:
        print("Post-approval execution: mock TMS auto-entry enabled")
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
