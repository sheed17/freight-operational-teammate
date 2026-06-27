"""Turn Neyma's heartbeat into a human answer to "what is Neyma doing right now?".

The continuous loop writes a small ``teammate_status.json`` each cycle. An owner should never have to
open that file: this module reads it, decides whether the teammate is healthy / stale / failing, and
renders a Slack-friendly line. The same snapshot drives proactive alerts when polling gets stuck.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class HealthSnapshot:
    status: str  # OK | STALE | ERROR | NOT_STARTED | UNREADABLE
    healthy: bool
    detail: str
    state: str | None = None
    iteration: int | None = None
    consecutive_failures: int = 0
    last_run_at: str | None = None
    age_seconds: float | None = None
    next_run_at: str | None = None
    extra: dict = field(default_factory=dict)


_EMOJI = {"OK": ":large_green_circle:", "STALE": ":large_yellow_circle:", "ERROR": ":red_circle:", "NOT_STARTED": ":white_circle:", "UNREADABLE": ":red_circle:"}


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _ago(age: float | None) -> str:
    if age is None:
        return "unknown time"
    age = max(age, 0)
    if age < 90:
        return f"{int(age)}s ago"
    if age < 5400:
        return f"{int(age // 60)}m ago"
    return f"{int(age // 3600)}h ago"


def read_loop_health(status_file: str | Path, *, now: datetime | None = None, stale_after_seconds: int = 900) -> HealthSnapshot:
    """Read the loop heartbeat and classify it. ``stale_after_seconds`` is the grace beyond which a
    quiet loop is treated as stuck (default 15m — well past the default 5m poll interval)."""
    path = Path(status_file)
    if not path.exists():
        return HealthSnapshot(status="NOT_STARTED", healthy=False, detail="Gmail polling has not started yet (no heartbeat).")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return HealthSnapshot(status="UNREADABLE", healthy=False, detail="Neyma's heartbeat file is unreadable.")

    now = now or datetime.now(timezone.utc)
    state = data.get("state")
    failures = int(data.get("consecutive_failures") or 0)
    last = data.get("finished_at") or data.get("started_at")
    last_dt = _parse_ts(last)
    age = (now - last_dt).total_seconds() if last_dt else None
    next_run = data.get("next_run_at")
    # Liveness must not go blind if the operator widens the poll interval: require quiet beyond the
    # larger of the caller's grace and ~3 poll intervals before calling a quiet loop stuck.
    interval = data.get("interval_seconds")
    if isinstance(interval, (int, float)) and interval > 0:
        stale_after_seconds = max(stale_after_seconds, int(3 * interval))
    common = dict(
        state=state,
        iteration=data.get("iteration"),
        consecutive_failures=failures,
        last_run_at=last,
        age_seconds=age,
        next_run_at=next_run,
    )

    if state == "ERROR" or failures > 0:
        return HealthSnapshot(
            status="ERROR", healthy=False,
            detail=f"Gmail polling is FAILING — {failures} consecutive failure(s), last attempt {_ago(age)}.",
            **common,
        )
    if age is not None and age > stale_after_seconds:
        return HealthSnapshot(
            status="STALE", healthy=False,
            detail=f"Gmail polling looks STUCK — no cycle in {_ago(age)}.",
            **common,
        )
    running = state == "RUNNING"
    detail = (
        f"Gmail polling is healthy — currently polling (cycle {data.get('iteration')})."
        if running
        else f"Gmail polling is healthy — idle, last cycle {_ago(age)}, next around {next_run or 'soon'}."
    )
    return HealthSnapshot(status="OK", healthy=True, detail=detail, **common)


def render_health(snapshot: HealthSnapshot) -> str:
    emoji = _EMOJI.get(snapshot.status, ":grey_question:")
    lines = [f"{emoji} *Neyma — what I'm doing right now:* {snapshot.detail}"]
    if snapshot.iteration:
        lines.append(f"• poll cycles run: {snapshot.iteration}")
    if snapshot.status in ("ERROR", "STALE") and snapshot.next_run_at:
        lines.append(f"• will retry around: {snapshot.next_run_at}")
    return "\n".join(lines)
