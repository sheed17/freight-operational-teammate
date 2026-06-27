"""Run the Gmail -> Slack teammate loop continuously.

This is the deployable local/VM shape of "the agent sits in the inbox": repeatedly pull matching
mail with BODY.PEEK (no read/delete/mark-seen), process packets, dispatch Slack review cards, and
write a small status file so the operator can see what Neyma is doing.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Belt-and-suspenders: the per-cycle runner never prints credentials, but the heartbeat captures
# subprocess output verbatim into a plaintext file the Slack status surface can read, so scrub any
# secret-shaped output before it lands.
_SECRET_RE = re.compile(r"(?i)(password|token|secret|cookie|authorization|api[_-]?key)\s*[:=]\s*\S+")


def _scrub(text: str) -> str:
    return _SECRET_RE.sub(r"\1=[redacted]", text or "")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
RUNNER = ROOT / "scripts" / "run_gmail_to_slack_dogfood.py"
DEFAULT_WORKSPACE = ROOT / "data" / "active_workspace" / "gmail_to_slack_service"


def _build_alert_poster(client_config: str | None):
    """Return a callable(text) that posts a loop alert to the configured digest channel, or None.

    Lets Neyma proactively tell Slack when polling is stuck/recovered instead of only writing JSON.
    Best-effort: any failure to post is swallowed so it never breaks the loop.
    """
    if not client_config:
        return None
    try:
        from freight_recon.channels import load_delivery_config, slack_channel_for_route
        from freight_recon.delivery_dispatch import post_text_to_slack
        from freight_recon.review import ReviewRoute

        config = load_delivery_config(client_config)
        if config is None or config.slack is None:
            return None
        channel = slack_channel_for_route(config.slack, ReviewRoute.DIGEST_ONLY)
    except Exception:  # noqa: BLE001 - alerting must never block polling
        return None

    def _post(text: str) -> None:
        try:
            post_text_to_slack(text, channel=channel, config=config, env=os.environ)
        except Exception:  # noqa: BLE001
            pass

    return _post


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=str(DEFAULT_WORKSPACE))
    parser.add_argument("--interval-seconds", type=int, default=300)
    parser.add_argument(
        "--iterations",
        type=int,
        default=0,
        help="Number of loop iterations to run. 0 means forever.",
    )
    parser.add_argument("--status-file", default=None, help="Defaults to <workspace>/teammate_status.json")
    parser.add_argument("--stop-on-error", action="store_true")
    parser.add_argument("--client-config", default=None, help="post Slack alerts/nudges/digest to the digest channel")
    parser.add_argument("--alert-after", type=int, default=1, help="post a Slack failure alert after this many consecutive failures")
    parser.add_argument("--daily-digest-hour", type=int, default=None, help="post the daily digest once/day at/after this local hour (0-23)")
    parser.add_argument(
        "--",
        dest="runner_args",
        nargs=argparse.REMAINDER,
        help="Arguments after -- are forwarded to run_gmail_to_slack_dogfood.py",
    )
    args, unknown = parser.parse_known_args()

    workspace = Path(args.workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    status_file = Path(args.status_file) if args.status_file else workspace / "teammate_status.json"
    forwarded = [value for value in [*unknown, *(args.runner_args or [])] if value != "--"]
    command = [sys.executable, str(RUNNER), "--workspace", str(workspace), *forwarded]

    alert_poster = _build_alert_poster(args.client_config)
    alert_after = max(args.alert_after, 1)
    prev_failures = 0

    iteration = 0
    consecutive_failures = 0
    while args.iterations == 0 or iteration < args.iterations:
        iteration += 1
        started = _now()
        _write_status(
            status_file,
            {
                "state": "RUNNING",
                "iteration": iteration,
                "started_at": started,
                "interval_seconds": args.interval_seconds,
                "command": _redact_command(command),
                "note": "Polling mailbox with BODY.PEEK; messages are not marked read by Neyma.",
            },
        )
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        finished = _now()
        if result.returncode == 0:
            consecutive_failures = 0
        else:
            consecutive_failures += 1
        state = "IDLE" if result.returncode == 0 else "ERROR"
        next_run_at = None
        if args.iterations == 0 or iteration < args.iterations:
            next_run_at = _ts(time.time() + max(args.interval_seconds, 1))
        _write_status(
            status_file,
            {
                "state": state,
                "iteration": iteration,
                "interval_seconds": args.interval_seconds,
                "started_at": started,
                "finished_at": finished,
                "returncode": result.returncode,
                "consecutive_failures": consecutive_failures,
                "next_run_at": next_run_at,
                "stdout_tail": _scrub(result.stdout[-4000:]),
                "stderr_tail": _scrub(result.stderr[-4000:]),
                "command": _redact_command(command),
            },
        )
        # Proactively tell Slack when polling breaks or recovers (not just the JSON heartbeat).
        if alert_poster is not None:
            message = _loop_alert(
                consecutive_failures, prev_failures, alert_after, iteration=iteration, returncode=result.returncode
            )
            if message:
                alert_poster(message)
        prev_failures = consecutive_failures

        # Volunteer good news: when a healthy cycle surfaced new review work, say so.
        if alert_poster is not None and result.returncode == 0:
            nudge = _new_work_nudge(_cycle_summary(workspace))
            if nudge:
                alert_poster(nudge)

        # Loop-driven daily digest (once/day at the configured hour) — operator owns no cron.
        if args.client_config and args.daily_digest_hour is not None:
            _maybe_post_daily_digest(workspace, args.client_config, args.daily_digest_hour)

        if result.returncode != 0 and args.stop_on_error:
            return result.returncode
        if args.iterations != 0 and iteration >= args.iterations:
            break
        time.sleep(max(args.interval_seconds, 1))
    return 0


def _loop_alert(consecutive_failures: int, prev_failures: int, alert_after: int, *, iteration: int, returncode: int) -> str | None:
    """Decide the proactive Slack alert (if any) for this loop cycle. Fires once when crossing the
    failure threshold, and once on recovery — never on every cycle."""
    if consecutive_failures == alert_after:
        return (
            f":red_circle: *Neyma alert:* Gmail polling failed (cycle {iteration}, exit {returncode}) — "
            f"{consecutive_failures} consecutive failure(s). Incoming mail will keep queuing; I'll keep retrying. "
            "Type `status` for details."
        )
    if prev_failures >= alert_after and consecutive_failures == 0:
        return f":large_green_circle: *Neyma recovered:* Gmail polling is back to normal (cycle {iteration})."
    return None


def _cycle_summary(workspace: Path) -> dict | None:
    """Read this cycle's counts from the runner report (new mail, packets, items needing review)."""
    report = workspace / "gmail_to_slack_report.json"
    if not report.exists():
        return None
    try:
        data = json.loads(report.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    workflow = data.get("workflow", {})
    return {
        "new_messages": int(workflow.get("new_messages") or 0),
        "packet_runs": int(workflow.get("packet_runs") or 0),
        "review_payloads": int(workflow.get("review_payloads") or 0),
        "sent": int(data.get("dispatch", {}).get("sent") or 0),
    }


def _new_work_nudge(summary: dict | None) -> str | None:
    """A compact 'Neyma brought you work' line — only when something needs the human this cycle, so
    the always-on loop volunteers good news, not only failures (and stays quiet on empty cycles)."""
    if not summary:
        return None
    needs = summary.get("review_payloads") or 0
    if needs <= 0:
        return None
    new_mail = summary.get("new_messages") or 0
    src = f" from {new_mail} new email(s)" if new_mail else ""
    return f":inbox_tray: *Neyma:* {needs} new item(s) need your review this cycle{src} — open Slack to approve/dispute."


def _should_post_digest(now: datetime, last_date_iso: str | None, hour: int | None) -> bool:
    """True at most once per day, on the first cycle at/after the configured local hour."""
    if hour is None:
        return False
    if now.astimezone().hour < hour:
        return False
    return now.astimezone().date().isoformat() != last_date_iso


def _maybe_post_daily_digest(workspace: Path, client_config: str, hour: int) -> None:
    """Post the daily digest once/day (operator owns no cron). Reuses the tested digest script."""
    marker = workspace / "last_digest.txt"
    last = marker.read_text(encoding="utf-8").strip() if marker.exists() else None
    if not _should_post_digest(datetime.now(timezone.utc), last, hour):
        return
    db = workspace / "workflow.sqlite3"
    payloads = workspace / "review_payloads.json"
    if not (db.exists() and payloads.exists()):
        return
    subprocess.run(
        [
            sys.executable, str(ROOT / "scripts" / "generate_daily_summary.py"),
            "--db", str(db), "--payloads", str(payloads),
            "--post-slack", "--client-config", client_config,
        ],
        text=True, capture_output=True, check=False,
    )
    marker.write_text(datetime.now(timezone.utc).astimezone().date().isoformat(), encoding="utf-8")


def _write_status(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _redact_command(command: list[str]) -> list[str]:
    redacted = []
    redact_next = False
    secret_flags = {"--password", "--username"}
    for value in command:
        if redact_next:
            redacted.append("REDACTED")
            redact_next = False
            continue
        if any(value.startswith(f"{flag}=") for flag in secret_flags):
            flag, _, _secret = value.partition("=")
            redacted.append(f"{flag}=REDACTED")
            continue
        redacted.append(value)
        if value in secret_flags:
            redact_next = True
    return redacted


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ts(value: float) -> str:
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
