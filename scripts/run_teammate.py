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
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKSPACE = ROOT / "data" / "active_workspace" / "gmail_to_slack_service"


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
    python: str = sys.executable,
) -> dict[str, list[str]]:
    """Build the three child commands, all sharing one workspace, DB, and heartbeat file.

    The callback's --db/--status-file are derived from the SAME workspace the loop drives, so the
    `status` surface is provably wired to the loop's real DB and heartbeat.
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
    return {"site": site, "callback": callback, "loop": loop}


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
    args = parser.parse_args()

    workspace = Path(args.workspace)
    (workspace / "site").mkdir(parents=True, exist_ok=True)
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
    )

    procs: dict[str, subprocess.Popen] = {}
    print("Starting Neyma teammate (one workspace, correctly wired):")
    print(f"  workspace: {workspace}")
    for name, cmd in commands.items():
        procs[name] = subprocess.Popen(cmd)
        print(f"  started {name} (pid {procs[name].pid})")
    print(f"\nSlack: point your app's Request URLs at https://<stable-host>/slack/actions and /slack/commands")
    print(f"       (tunnel/forward to 127.0.0.1:{args.callback_port}). Type `status` in Slack to check health.")
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
