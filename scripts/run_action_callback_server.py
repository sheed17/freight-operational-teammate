"""Run the local Neyma signed-action callback server for dogfood testing."""

from __future__ import annotations

import argparse
import ipaddress
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from freight_recon.action_callback import run_callback_server  # noqa: E402
from freight_recon.channels import build_signer, load_delivery_config  # noqa: E402
from freight_recon.cdp_actuator import CdpActuator  # noqa: E402
from freight_recon.cdp_session import CdpBrowserSession  # noqa: E402
from freight_recon.delivery import DeliverySigner  # noqa: E402
from freight_recon.delivery_dispatch import SlackApiPoster, slack_thread_status_poster  # noqa: E402
from freight_recon.operation_router import OperationRouter, freight_lanes  # noqa: E402
from freight_recon.operator_agent import OperatorAgent  # noqa: E402
from freight_recon.ops_control import OpsControl  # noqa: E402
from freight_recon.post_approval_execution import (  # noqa: E402
    MockTmsAutoEntryConfig,
    maybe_execute_mock_tms_after_approval,
)
from freight_recon.screen_discovery import openai_completer  # noqa: E402
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
    parser.add_argument(
        "--watchdog-interval-seconds",
        type=int,
        default=120,
        help="How often the callback server checks the loop heartbeat and proactively alerts Slack if "
        "the loop has gone STALE (hung/died). 0 disables. Requires --client-config for the Slack post.",
    )
    parser.add_argument(
        "--enable-operation-router",
        action="store_true",
        help="Enable Slack operation approvals -> OperationRouter. Requires --client-config and owner/channel allowlist.",
    )
    parser.add_argument("--operation-cdp-url", default=os.getenv("NEYMA_OPERATION_CDP_URL", "http://localhost:9222"))
    parser.add_argument("--operation-url-filter", default=os.getenv("NEYMA_OPERATION_URL_FILTER", ""))
    parser.add_argument("--operation-model", default=os.getenv("NEYMA_OPERATION_MODEL", "gpt-5.5"))
    parser.add_argument("--operation-max-steps", type=int, default=int(os.getenv("NEYMA_OPERATION_MAX_STEPS", "40")))
    parser.add_argument(
        "--allowed-slack-user",
        action="append",
        default=[],
        help="Slack user id allowed to approve operation-router runs. Can be repeated; defaults to NEYMA_ALLOWED_SLACK_USERS csv.",
    )
    parser.add_argument(
        "--allowed-slack-channel",
        default=os.getenv("NEYMA_ALLOWED_SLACK_CHANNEL"),
        help="Slack channel id allowed for operation-router approvals.",
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

    operation_router = None
    operation_result_poster = None
    allowed_slack_users = tuple(
        args.allowed_slack_user
        or [u.strip() for u in os.getenv("NEYMA_ALLOWED_SLACK_USERS", "").split(",") if u.strip()]
    )
    if args.enable_operation_router:
        if not args.client_config:
            parser.error("--enable-operation-router requires --client-config")
        if not slack_signing_secret:
            parser.error("--enable-operation-router requires a Slack signing secret from --client-config")
        if not allowed_slack_users or not args.allowed_slack_channel:
            parser.error("--enable-operation-router requires --allowed-slack-user and --allowed-slack-channel")
        operation_router = _build_live_operation_router(
            cdp_url=args.operation_cdp_url,
            url_filter=args.operation_url_filter or None,
            model=args.operation_model,
            max_steps=args.operation_max_steps,
            workspace=workspace,
            db_path=db_path,
        )
        operation_result_poster = _build_operation_result_poster(args.client_config)

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

    # Liveness watchdog: the loop alerts on its own *failures*, but a loop that hangs or dies simply
    # stops heart-beating and would go unnoticed. This independent thread (the callback is always up)
    # watches the same heartbeat and proactively pings Slack when it goes STALE / recovers.
    watchdog_poster = _build_digest_poster(args.client_config) if args.watchdog_interval_seconds > 0 else None
    if args.watchdog_interval_seconds > 0 and watchdog_poster is None:
        print("NOTE: heartbeat watchdog idle — needs --client-config with a Slack channel to post alerts.")
    elif watchdog_poster is not None:
        _start_heartbeat_watchdog(status_file, watchdog_poster, args.watchdog_interval_seconds)
        print(f"Liveness watchdog: alerting Slack if the loop heartbeat goes stale (every {args.watchdog_interval_seconds}s)")

    server = run_callback_server(
        host=args.host,
        port=args.port,
        db_path=str(db_path),
        signer=signer,
        follow_up_loads=follow_up_loads,
        slack_signing_secret=slack_signing_secret,
        post_action_executor=post_action_executor,
        status_file=str(status_file),
        operation_router=operation_router,
        operation_result_poster=operation_result_poster,
        allowed_slack_users=allowed_slack_users,
        allowed_slack_channel=args.allowed_slack_channel,
        # Natural-language routing for /neyma (cheap model — it only picks which read/operate, never money).
        nl_completer=openai_completer(model=os.getenv("NEYMA_NL_MODEL", "gpt-5.4")) if operation_router else None,
    )
    print(f"Neyma action callback server listening on http://{args.host}:{args.port}")
    print("Email actions: /email/action?token=<signed-token>")
    print("JSON actions: POST /actions/signed {'token': '<signed-token>'}")
    if slack_signing_secret:
        print("Slack interactivity: POST /slack/actions (Slack-signed)")
    if post_action_executor is not None:
        print("Post-approval execution: mock TMS auto-entry enabled")
    if operation_router is not None:
        print("Operation router approvals: enabled for allowed Slack user/channel only")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Neyma action callback server")
    finally:
        server.server_close()
    return 0


def _build_digest_poster(client_config: str | None):
    """Return callable(text)->None that posts to the client's Slack digest channel, or None.

    Best-effort: any failure to build or post is swallowed so watchdog alerting never crashes the
    callback server. Mirrors the loop's alert poster so both surfaces speak to the same channel.
    """
    if not client_config:
        return None
    try:
        from freight_recon.channels import slack_channel_for_route
        from freight_recon.delivery_dispatch import post_text_to_slack
        from freight_recon.review import ReviewRoute

        config = load_delivery_config(client_config)
        if config is None or config.slack is None:
            return None
        channel = slack_channel_for_route(config.slack, ReviewRoute.DIGEST_ONLY)
    except Exception:  # noqa: BLE001 - alerting must never block the server
        return None

    def _post(text: str) -> None:
        try:
            post_text_to_slack(text, channel=channel, config=config, env=os.environ)
        except Exception:  # noqa: BLE001
            pass

    return _post


def _build_live_operation_router(
    *,
    cdp_url: str,
    url_filter: str | None,
    model: str,
    max_steps: int,
    workspace: "Path | None" = None,
    db_path: "Path | None" = None,
) -> OperationRouter:
    """Build the real browser-agent router for Slack-approved operation runs.

    Supervised lanes PREPARE (fill + stop before Save; the human commits); a graduated lane runs
    unattended. The graduation policy is persisted per workspace so `/neyma graduate <lane>` sticks.
    """
    completer = openai_completer(model=model)

    from freight_recon.agent_memory import AgentMemory
    from freight_recon.lane_graduation import LaneGraduation
    from freight_recon.workflow import WorkflowStore

    mem_path = (Path(workspace) / "agent_memory.json") if workspace else Path("agent_memory.json")
    memory = AgentMemory(mem_path)  # recall learned facts + crystallize what works, per client

    def _build_agent(*, approved_amount=None, approve=None, prepare_only=False):
        session = CdpBrowserSession(cdp_url=cdp_url, url_filter=url_filter)
        session.__enter__()
        actuator = CdpActuator(session)

        class _ClosingOperatorAgent(OperatorAgent):
            def run(self, goal):
                try:
                    return super().run(goal)
                finally:
                    session.__exit__(None, None, None)

        return _ClosingOperatorAgent(
            actuator=actuator,
            complete=completer,
            approved_amount=approved_amount,
            approve=approve,
            max_steps=max_steps,
            prepare_only=prepare_only,
            memory=memory,
        )

    grad_path = (Path(workspace) / "lane_graduation.json") if workspace else Path("lane_graduation.json")
    return OperationRouter(
        lanes=freight_lanes(),
        build_agent=_build_agent,
        approved_amount_for=lambda intent: intent.params.get("approved_amount"),
        graduation=LaneGraduation(grad_path),
        commit_store=WorkflowStore(db_path) if db_path is not None else None,
    )


def _build_operation_result_poster(client_config: str | None):
    if not client_config:
        return None
    config = load_delivery_config(client_config)
    if config is None or config.slack is None:
        return None
    token = os.environ.get(config.slack.bot_token_env or "")
    if not token:
        return None
    poster = SlackApiPoster(token)

    def _post(receipt: dict) -> None:
        channel = receipt.get("channel_id") or _default_slack_channel(config)
        if not channel:
            return
        payload = {"text": receipt.get("text", "Neyma operation finished.")}
        if receipt.get("thread_ts"):
            payload["thread_ts"] = receipt["thread_ts"]
        poster.post_message(channel=channel, payload=payload)

    return _post


def _default_slack_channel(config) -> str | None:
    if config.slack is None:
        return None
    return config.slack.default_channel_id


def _start_heartbeat_watchdog(status_file: Path, poster, interval_seconds: int) -> threading.Thread:
    """Start a daemon thread that classifies the loop heartbeat each interval and posts a fire-once
    Slack alert when it goes STALE (loop hung/died) and a recovery when it heart-beats again."""
    from freight_recon.teammate_health import read_loop_health, watchdog_decision

    def _run() -> None:
        already_alerted = False
        while True:
            time.sleep(max(interval_seconds, 1))
            try:
                snapshot = read_loop_health(status_file)
                message, already_alerted = watchdog_decision(snapshot, already_alerted=already_alerted)
                if message:
                    poster(message)
            except Exception:  # noqa: BLE001 - the watchdog must never take down the server
                continue

    thread = threading.Thread(target=_run, name="neyma-heartbeat-watchdog", daemon=True)
    thread.start()
    return thread


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
