"""Turn Neyma's heartbeat into a human answer to "what is Neyma doing right now?".

The continuous loop writes a small ``teammate_status.json`` each cycle. An owner should never have to
open that file: this module reads it, decides whether the teammate is healthy / stale / failing, and
renders a Slack-friendly line. The same snapshot drives proactive alerts when polling gets stuck.
"""

from __future__ import annotations

import json
import os
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


@dataclass
class PilotReadinessSnapshot:
    status: str  # GO | DEGRADED | NO_GO
    healthy: bool
    checks: list[HealthSnapshot] = field(default_factory=list)


_EMOJI = {"OK": ":large_green_circle:", "STALE": ":large_yellow_circle:", "ERROR": ":red_circle:", "NOT_STARTED": ":white_circle:", "UNREADABLE": ":red_circle:"}
_READINESS_EMOJI = {"GO": ":large_green_circle:", "DEGRADED": ":large_yellow_circle:", "NO_GO": ":red_circle:"}


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


def read_supervisor_health(supervisor_file: str | Path) -> HealthSnapshot:
    """Classify the process-supervisor state written by ``scripts/run_teammate.py``."""
    path = Path(supervisor_file)
    if not path.exists():
        return HealthSnapshot(status="NOT_STARTED", healthy=False, detail="Process supervisor has not written state yet.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return HealthSnapshot(status="UNREADABLE", healthy=False, detail="Process supervisor state is unreadable.")
    children = data.get("children") or {}
    dropped = [
        name for name, child in children.items()
        if not (child or {}).get("running", False) or not _pid_alive((child or {}).get("pid"))
    ]
    events = data.get("events") or []
    dropped_events = [e for e in events if e.get("event") == "child_dropped_after_crash_loop"]
    if data.get("degraded") or dropped_events or dropped:
        names = ", ".join(e.get("child", "unknown") for e in dropped_events) or ", ".join(dropped) or "a child"
        return HealthSnapshot(
            status="ERROR",
            healthy=False,
            detail=f"Process supervisor is DEGRADED — {names} dropped after repeated crashes.",
            extra={"events": events, "children": children},
        )
    if not children:
        return HealthSnapshot(status="NOT_STARTED", healthy=False, detail="Process supervisor has no child processes recorded.")
    return HealthSnapshot(
        status="OK",
        healthy=True,
        detail=f"Process supervisor is healthy — {len(children)} child process(es) tracked.",
        extra={"events": events, "children": children},
    )


def read_browser_lock_health(lock_file: str | Path, *, now: datetime | None = None, stale_after_seconds: int = 1800) -> HealthSnapshot:
    """A stale browser lock means the reader may defer forever after a crashed write."""
    path = Path(lock_file)
    if not path.exists():
        return HealthSnapshot(status="OK", healthy=True, detail="Browser lock is clear.")
    now = now or datetime.now(timezone.utc)
    try:
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return HealthSnapshot(status="UNREADABLE", healthy=False, detail="Browser lock exists but cannot be read.")
    age = (now - modified).total_seconds()
    if age > stale_after_seconds:
        return HealthSnapshot(
            status="STALE",
            healthy=False,
            detail=f"Browser lock is STALE — held for {_ago(age)}. A write may have crashed mid-run.",
            age_seconds=age,
        )
    return HealthSnapshot(status="OK", healthy=True, detail=f"Browser lock is held briefly ({_ago(age)}).", age_seconds=age)


def _pid_alive(pid: object) -> bool:
    try:
        pid_int = int(pid)
    except (TypeError, ValueError):
        return False
    if pid_int <= 0:
        return False
    try:
        os.kill(pid_int, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def read_db_health(db_path: str | Path) -> HealthSnapshot:
    """Cheap DB availability check for the shared workflow store."""
    path = Path(db_path)
    if not path.exists():
        return HealthSnapshot(status="NOT_STARTED", healthy=False, detail="Workflow DB has not been created yet.")
    try:
        import sqlite3

        conn = sqlite3.connect(path)
        try:
            conn.execute("SELECT 1").fetchone()
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        return HealthSnapshot(status="ERROR", healthy=False, detail=f"Workflow DB is not readable: {type(exc).__name__}.")
    return HealthSnapshot(status="OK", healthy=True, detail="Workflow DB is readable.")


def read_pilot_readiness(
    workspace: str | Path,
    *,
    now: datetime | None = None,
    loop_stale_after_seconds: int = 900,
    lock_stale_after_seconds: int = 1800,
    db_path: str | Path | None = None,
    cdp_url: str | None = None,
    url_filter: str | None = None,
) -> PilotReadinessSnapshot:
    """Aggregate the local signals that decide whether the supervised pilot is healthy enough to trust."""
    ws = Path(workspace)
    checks = [
        read_loop_health(ws / "teammate_status.json", now=now, stale_after_seconds=loop_stale_after_seconds),
        read_supervisor_health(ws / "teammate_supervisor.json"),
        read_db_health(db_path or (ws / "workflow.sqlite3")),
        read_browser_lock_health(ws / "browser.busy", now=now, stale_after_seconds=lock_stale_after_seconds),
    ]
    if cdp_url:
        from .browser_session_health import read_browser_session_health

        browser = read_browser_session_health(cdp_url=cdp_url, url_filter=url_filter)
        checks.append(
            HealthSnapshot(
                status=browser.status,
                healthy=browser.healthy,
                detail=browser.detail,
                extra={
                    "cdp_url": browser.cdp_url,
                    "url_filter": browser.url_filter,
                    "active_url": browser.active_url,
                    "tabs_seen": browser.tabs_seen,
                    "matching_tabs": browser.matching_tabs,
                },
            )
        )
    if all(c.healthy for c in checks):
        return PilotReadinessSnapshot(status="GO", healthy=True, checks=checks)
    if any(c.status in ("ERROR", "UNREADABLE", "NO_CDP", "NO_TMS_TAB", "SESSION_EXPIRED") for c in checks):
        return PilotReadinessSnapshot(status="NO_GO", healthy=False, checks=checks)
    return PilotReadinessSnapshot(status="DEGRADED", healthy=False, checks=checks)


def watchdog_decision(snapshot: HealthSnapshot, *, already_alerted: bool) -> tuple[str | None, bool]:
    """Decide the proactive "the loop went dark" Slack alert from a heartbeat snapshot.

    The continuous loop already posts its own alert when a cycle *fails* (non-zero exit). The gap this
    closes is a loop that *hangs or dies* and simply stops heart-beating: its last heartbeat freezes,
    :func:`read_loop_health` classifies it STALE, but nothing tells the operator. This fires once on
    going STALE and once on recovery, so "Neyma went dark and didn't tell me" cannot happen silently.

    Returns ``(message_or_none, new_already_alerted)``. Only STALE triggers an alert — ERROR is the
    loop's own job, and NOT_STARTED/UNREADABLE are transient at boot and would cause false alarms.
    """
    if snapshot.status == "STALE" and not already_alerted:
        message = (
            f":large_yellow_circle: *Neyma watchdog:* {snapshot.detail} The poll loop may have hung or "
            "stopped. Incoming mail will keep queuing until it resumes — check the loop process."
        )
        return message, True
    if already_alerted and snapshot.status == "OK":
        return ":large_green_circle: *Neyma watchdog:* the poll loop is heart-beating normally again.", False
    return None, already_alerted


def render_health(snapshot: HealthSnapshot) -> str:
    emoji = _EMOJI.get(snapshot.status, ":grey_question:")
    lines = [f"{emoji} *Neyma — what I'm doing right now:* {snapshot.detail}"]
    if snapshot.iteration:
        lines.append(f"• poll cycles run: {snapshot.iteration}")
    if snapshot.status in ("ERROR", "STALE") and snapshot.next_run_at:
        lines.append(f"• will retry around: {snapshot.next_run_at}")
    return "\n".join(lines)


def render_pilot_readiness(snapshot: PilotReadinessSnapshot) -> str:
    emoji = _READINESS_EMOJI.get(snapshot.status, ":grey_question:")
    lines = [f"{emoji} *Pilot readiness:* {snapshot.status}"]
    for check in snapshot.checks:
        lines.append(f"• {_EMOJI.get(check.status, ':grey_question:')} {check.detail}")
    return "\n".join(lines)
