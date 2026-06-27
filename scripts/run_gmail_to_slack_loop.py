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
    parser.add_argument("--client-config", default=None, help="post Slack alerts to the digest channel when polling fails/recovers")
    parser.add_argument("--alert-after", type=int, default=1, help="post a Slack failure alert after this many consecutive failures")
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
