"""Run the whole Neyma teammate as one supervised process group.

One command brings up the three local processes, all wired to ONE workspace — so the Slack `status`
surface can never read a different DB/heartbeat than the loop writes (the path-mismatch landmine is
removed by construction):
  - static packet site            (serves <WS>/site)
  - signed-action callback server (Slack clicks + `status` command + mock auto-execution)
  - continuous Gmail poll loop     (heartbeat + alerts + new-work nudge + daily digest)

If any child exits, the group is shut down. Stable ingress (the HTTPS tunnel/host forwarding to the
callback port) is a separate concern — see docs/DEPLOYMENT.md.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
DEFAULT_WORKSPACE = ROOT / "data" / "active_workspace" / "gmail_to_slack_service"


def preflight_credentials(*, client_config: str, env: Mapping[str, str]) -> list[str]:
    """Return human-readable problems for any credential the teammate needs but is missing.

    Empty list means good to go. This runs BEFORE the children are spawned so a missing secret fails
    loudly at launch instead of silently at first use — where today it would only surface as a poll
    cycle failure (mail), a refused Slack post (alerts), or an unverifiable button click (actions).
    """
    problems: list[str] = []
    if not (env.get("NEYMA_IMAP_USERNAME") or env.get("NEYMA_SMTP_USERNAME")):
        problems.append("IMAP username missing (set NEYMA_IMAP_USERNAME) — the loop cannot read mail.")
    if not (env.get("NEYMA_IMAP_PASSWORD") or env.get("NEYMA_SMTP_PASSWORD")):
        problems.append("IMAP app password missing (set NEYMA_IMAP_PASSWORD) — the loop cannot read mail.")
    if not env.get("OPENAI_API_KEY"):
        problems.append("OPENAI_API_KEY missing — invoice extraction and the browser agent cannot run.")

    try:
        from freight_recon.channels import load_delivery_config

        config = load_delivery_config(client_config)
    except Exception as exc:  # noqa: BLE001
        problems.append(f"could not load client config {client_config}: {exc}")
        return problems
    if config is None:
        problems.append(f"no delivery config found at {client_config}.")
        return problems

    if not env.get(config.action_token_secret_env):
        problems.append(
            f"action-token secret missing (set {config.action_token_secret_env}) — Slack action links "
            "cannot be signed or verified."
        )
    if config.slack is not None:
        if config.slack.signing_secret_env and not env.get(config.slack.signing_secret_env):
            problems.append(
                f"Slack signing secret missing (set {config.slack.signing_secret_env}) — inbound Slack "
                "clicks cannot be verified."
            )
        if config.slack.bot_token_env and not env.get(config.slack.bot_token_env):
            problems.append(
                f"Slack bot token missing (set {config.slack.bot_token_env}) — Neyma cannot post to Slack."
            )
    return problems


def build_process_commands(
    *,
    workspace: str | Path,
    client_config: str,
    site_port: int = 8000,
    callback_port: int = 8001,
    interval_seconds: int = 300,
    daily_digest_hour: int | None = None,
    mailbox: str = "Neyma-Test-Inbox",
    query: str = "UNSEEN",
    auto_enter_mock_tms: bool = True,
    enable_operation_router: bool = False,
    allowed_slack_users: tuple[str, ...] = (),
    allowed_slack_channel: str | None = None,
    operation_url_filter: str | None = None,
    propose_clean_payables: bool = False,
    enable_ar_trigger: bool = False,
    ar_interval_seconds: int = 300,
    ar_require_pod: bool = True,
    ar_autonomous: bool = False,
    tms_loads_url: str = "https://secure.truckingoffice.com/loads",
    ngrok_domain: str | None = None,
    ngrok_bin: str | None = "ngrok",
    python: str = sys.executable,
) -> dict[str, list[str]]:
    """Build the child commands, all sharing one workspace, DB, and heartbeat file.

    The callback's --db/--status-file are derived from the SAME workspace the loop drives, so the
    `status` surface is provably wired to the loop's real DB and heartbeat.

    When ``ngrok_domain`` and a resolvable ``ngrok_bin`` are given, the stable-ingress tunnel is
    supervised as a fourth child forwarding the fixed domain to the callback port — so Slack's
    Request URL can never silently point at a dead tunnel while the app itself is up (the exact
    desync that makes `/neyma` report "the app did not respond").
    """
    ws = Path(workspace)
    db = ws / "workflow.sqlite3"
    status_file = ws / "teammate_status.json"

    site = [python, "-m", "http.server", str(site_port), "--directory", str(ws / "site")]

    callback = [
        python, str(ROOT / "scripts" / "run_action_callback_server.py"),
        "--host", "127.0.0.1", "--port", str(callback_port),
        "--workspace", str(ws), "--db", str(db), "--status-file", str(status_file),
        "--client-config", client_config,
    ]
    if auto_enter_mock_tms:
        callback.append("--auto-enter-approved-mock-tms")
    if enable_operation_router:
        callback.append("--enable-operation-router")
        for user in allowed_slack_users:
            callback += ["--allowed-slack-user", user]
        if allowed_slack_channel:
            callback += ["--allowed-slack-channel", allowed_slack_channel]
        if operation_url_filter:
            callback += ["--operation-url-filter", operation_url_filter]

    loop = [
        python, str(ROOT / "scripts" / "run_gmail_to_slack_loop.py"),
        "--workspace", str(ws), "--interval-seconds", str(interval_seconds),
        "--client-config", client_config,
    ]
    if daily_digest_hour is not None:
        loop += ["--daily-digest-hour", str(daily_digest_hour)]
    loop += [
        "--", "--client-config", client_config, "--real-extraction", "--provider", "openai",
        "--mailbox", mailbox, "--query", query, "--dispatch-mode", "LIVE", "--enable-live-slack-outbound",
    ]
    if propose_clean_payables:
        loop.append("--propose-clean-payables")
    commands = {"site": site, "callback": callback, "loop": loop}

    if enable_ar_trigger:
        # The AR trigger: periodically read the TMS /loads and post 'Invoice [Approve & run]' buttons for
        # ready-to-bill loads. Shares the workspace DB (dedup) and the browser.busy marker (defers while a
        # write is in progress), and drives the SAME Chrome the operation agent uses.
        commands["ar_trigger"] = [
            python, str(ROOT / "scripts" / "propose_ar_from_tms.py"),
            "--client-config", client_config,
            "--url-filter", operation_url_filter or "truckingoffice",
            "--loads-url", tms_loads_url,
            "--db", str(db), "--lock-path", str(ws / "browser.busy"),
            "--interval-seconds", str(ar_interval_seconds),
        ]
        # POD gate is ON by default (owner SOP: never bill before POD is proven). On a TMS whose loads
        # list doesn't expose POD (e.g. TruckingOffice), every load reads as 'POD unknown' and is blocked
        # until detail-page POD verification exists — pass ar_require_pod=False to bill on delivery alone.
        if not ar_require_pod:
            commands["ar_trigger"].append("--no-require-pod")
        # Autonomy: graduated loads (within the owner's ceiling/allowlist/daily-cap) are invoiced
        # unattended by the trigger itself; ungraduated/over-cap loads still get a supervised button.
        if ar_autonomous:
            commands["ar_trigger"].append("--autonomous")

    if ngrok_domain and ngrok_bin:
        # ngrok reads NGROK_AUTHTOKEN from the environment, so no prior `ngrok config` is required.
        # Use the modern --url=https://<domain> form: the deprecated --domain flag on ngrok 3.39+
        # binds an HTTP-only edge, so Slack's HTTPS Request URL fails the TLS handshake and reports
        # "the app did not respond". --log=stdout keeps tunnel state in the supervised log.
        url = ngrok_domain if "://" in ngrok_domain else f"https://{ngrok_domain}"
        # Forward to 127.0.0.1 EXPLICITLY, not the bare port: ngrok resolves a bare port via
        # "localhost", which can pick IPv6 [::1] while the callback binds IPv4 127.0.0.1 only —
        # causing ERR_NGROK_8012 "connection refused" even though both processes are up.
        commands["ngrok"] = [
            ngrok_bin, "http", f"--url={url}", f"http://127.0.0.1:{callback_port}", "--log=stdout",
        ]
    return commands


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=str(DEFAULT_WORKSPACE))
    parser.add_argument("--client-config", required=True)
    parser.add_argument("--site-port", type=int, default=8000)
    parser.add_argument("--callback-port", type=int, default=8001)
    parser.add_argument("--interval-seconds", type=int, default=300)
    parser.add_argument("--daily-digest-hour", type=int, default=None)
    parser.add_argument("--mailbox", default="Neyma-Test-Inbox")
    parser.add_argument("--query", default="UNSEEN")
    parser.add_argument("--no-auto-enter", action="store_true", help="do not auto-enter approved payables into the mock TMS")
    parser.add_argument("--enable-operation-router", action="store_true", help="enable signed Slack operation approvals -> OperationRouter")
    parser.add_argument("--allowed-slack-user", action="append", default=[], help="Slack user id allowed to approve OperationRouter runs")
    parser.add_argument("--allowed-slack-channel", default=os.environ.get("NEYMA_ALLOWED_SLACK_CHANNEL"))
    parser.add_argument("--operation-url-filter", default=os.environ.get("NEYMA_OPERATION_URL_FILTER"))
    parser.add_argument("--propose-clean-payables", action="store_true", help="auto-post a 'Record payable [Approve & run]' button for each cleanly matched carrier invoice")
    parser.add_argument("--enable-ar-trigger", action="store_true", help="supervise the AR trigger: periodically read the live TMS /loads and post an 'Invoice [Approve & run]' button per ready-to-bill load")
    parser.add_argument("--ar-interval-seconds", type=int, default=300, help="how often the AR trigger reads the TMS /loads (defers while a write holds the browser)")
    parser.add_argument("--tms-loads-url", default="https://secure.truckingoffice.com/loads", help="the live TMS loads page the AR trigger reads")
    parser.add_argument("--ar-no-require-pod", action="store_true", help="dev/demo only: let the AR trigger bill delivered loads without proven POD (default requires POD per owner SOP)")
    parser.add_argument("--ar-autonomous", action="store_true", help="the AR trigger invoices GRADUATED loads unattended (money-fenced + within your ceiling/allowlist/daily-cap); ungraduated/over-cap loads still post a button")
    parser.add_argument("--skip-preflight", action="store_true", help="start even if the credential preflight finds problems (not recommended)")
    parser.add_argument("--ngrok-domain", default=os.environ.get("NGROK_STATIC_DOMAIN"), help="supervise an ngrok tunnel from this fixed domain to the callback port (defaults to $NGROK_STATIC_DOMAIN)")
    parser.add_argument("--no-ngrok", action="store_true", help="do not supervise ngrok (run stable ingress separately)")
    args = parser.parse_args()

    # Fail loud at launch, not silently at first use, when a required credential is missing.
    problems = preflight_credentials(client_config=args.client_config, env=os.environ)
    if problems:
        print("Credential preflight found problems:")
        for problem in problems:
            print(f"  - {problem}")
        if not args.skip_preflight:
            print("\nRefusing to start. Fix the .env entries above, or rerun with --skip-preflight to start anyway.")
            return 1
        print("\n--skip-preflight set: starting anyway (some functions will fail until fixed).")
    else:
        print("Credential preflight: all required secrets present.")

    workspace = Path(args.workspace)
    (workspace / "site").mkdir(parents=True, exist_ok=True)

    ngrok_domain = None if args.no_ngrok else args.ngrok_domain
    ngrok_bin = shutil.which("ngrok") if ngrok_domain else None
    if ngrok_domain and not ngrok_bin:
        print(f"NOTE: --ngrok-domain {ngrok_domain} given but the `ngrok` binary is not on PATH — "
              "ingress NOT supervised. Install ngrok or run the tunnel separately (see docs/DEPLOYMENT.md).")

    commands = build_process_commands(
        workspace=workspace,
        client_config=args.client_config,
        site_port=args.site_port,
        callback_port=args.callback_port,
        interval_seconds=args.interval_seconds,
        daily_digest_hour=args.daily_digest_hour,
        mailbox=args.mailbox,
        query=args.query,
        auto_enter_mock_tms=not args.no_auto_enter,
        enable_operation_router=args.enable_operation_router,
        allowed_slack_users=tuple(args.allowed_slack_user),
        allowed_slack_channel=args.allowed_slack_channel,
        operation_url_filter=args.operation_url_filter,
        propose_clean_payables=args.propose_clean_payables,
        enable_ar_trigger=args.enable_ar_trigger,
        ar_require_pod=not args.ar_no_require_pod,
        ar_autonomous=args.ar_autonomous,
        ar_interval_seconds=args.ar_interval_seconds,
        tms_loads_url=args.tms_loads_url,
        ngrok_domain=ngrok_domain,
        ngrok_bin=ngrok_bin,
    )

    procs: dict[str, subprocess.Popen] = {}
    print("Starting Neyma teammate (one workspace, correctly wired):")
    print(f"  workspace: {workspace}")
    for name, cmd in commands.items():
        procs[name] = subprocess.Popen(cmd)
        print(f"  started {name} (pid {procs[name].pid})")
    host = f"https://{ngrok_domain}" if (ngrok_domain and ngrok_bin) else "https://<stable-host>"
    print(f"\nSlack: point your app's Request URLs at {host}/slack/actions and {host}/slack/commands")
    if ngrok_domain and ngrok_bin:
        print(f"       (ingress supervised here -> 127.0.0.1:{args.callback_port}; fixed domain, set Slack once).")
    else:
        print(f"       (tunnel/forward to 127.0.0.1:{args.callback_port} yourself). Type `status` in Slack to check health.")
    print("Ctrl-C to stop the whole group.\n")

    try:
        while True:
            for name, proc in procs.items():
                rc = proc.poll()
                if rc is not None:
                    print(f"\n{name} exited (rc={rc}) — shutting down the group.")
                    raise KeyboardInterrupt
            time.sleep(2)
    except KeyboardInterrupt:
        print("Stopping Neyma teammate...")
    finally:
        for proc in procs.values():
            proc.terminate()
        for proc in procs.values():
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
