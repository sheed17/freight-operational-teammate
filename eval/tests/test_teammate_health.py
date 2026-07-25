"""Tests for turning the loop heartbeat into a Slack-native 'what is Neyma doing?' answer."""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.teammate_health import (  # noqa: E402
    HealthSnapshot,
    read_loop_health,
    read_pilot_readiness,
    render_health,
    render_pilot_readiness,
    watchdog_decision,
)

NOW = datetime(2026, 6, 27, 12, 0, 0, tzinfo=timezone.utc)


def _write(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_not_started_when_no_heartbeat(tmp_path):
    h = read_loop_health(tmp_path / "missing.json", now=NOW)
    assert h.status == "NOT_STARTED" and h.healthy is False
    assert ":white_circle:" in render_health(h)


def test_healthy_when_recent_idle(tmp_path):
    p = _write(
        tmp_path / "s.json",
        {
            "state": "IDLE",
            "iteration": 3,
            "finished_at": (NOW - timedelta(minutes=2)).isoformat(),
            "consecutive_failures": 0,
            "next_run_at": (NOW + timedelta(minutes=3)).isoformat(),
        },
    )
    h = read_loop_health(p, now=NOW)
    assert h.status == "OK" and h.healthy is True
    assert ":large_green_circle:" in render_health(h)


def test_error_when_consecutive_failures(tmp_path):
    p = _write(
        tmp_path / "s.json",
        {"state": "ERROR", "iteration": 5, "finished_at": (NOW - timedelta(minutes=1)).isoformat(), "consecutive_failures": 3},
    )
    h = read_loop_health(p, now=NOW)
    assert h.status == "ERROR" and h.healthy is False and h.consecutive_failures == 3
    assert ":red_circle:" in render_health(h)


def test_stale_when_no_recent_cycle(tmp_path):
    p = _write(
        tmp_path / "s.json",
        {"state": "IDLE", "iteration": 9, "finished_at": (NOW - timedelta(minutes=30)).isoformat(), "consecutive_failures": 0},
    )
    h = read_loop_health(p, now=NOW, stale_after_seconds=900)
    assert h.status == "STALE" and h.healthy is False
    assert ":large_yellow_circle:" in render_health(h)


def _snap(status: str) -> HealthSnapshot:
    return HealthSnapshot(status=status, healthy=status == "OK", detail=f"detail for {status}")


def test_watchdog_fires_once_on_stale_then_recovers():
    # Loop hangs/dies -> heartbeat goes STALE -> watchdog alerts once.
    msg, alerted = watchdog_decision(_snap("STALE"), already_alerted=False)
    assert msg and "watchdog" in msg.lower() and alerted is True
    # Still stale -> no repeat alert (not spammy).
    msg2, alerted2 = watchdog_decision(_snap("STALE"), already_alerted=True)
    assert msg2 is None and alerted2 is True
    # Heartbeat resumes -> one recovery message, state cleared.
    msg3, alerted3 = watchdog_decision(_snap("OK"), already_alerted=True)
    assert msg3 and "again" in msg3.lower() and alerted3 is False


def test_watchdog_ignores_error_and_boot_states():
    # ERROR is the loop's own alert job; NOT_STARTED/UNREADABLE are transient at boot. Don't alert.
    for status in ("ERROR", "NOT_STARTED", "UNREADABLE", "OK"):
        msg, alerted = watchdog_decision(_snap(status), already_alerted=False)
        assert msg is None and alerted is False


def test_pilot_readiness_go_when_core_local_signals_are_green(tmp_path):
    _write(
        tmp_path / "teammate_status.json",
        {"state": "IDLE", "iteration": 2, "finished_at": (NOW - timedelta(minutes=1)).isoformat()},
    )
    _write(
        tmp_path / "teammate_supervisor.json",
        {"degraded": False, "children": {"callback": {"pid": os.getpid(), "running": True}, "loop": {"pid": os.getpid(), "running": True}}},
    )
    import sqlite3

    conn = sqlite3.connect(tmp_path / "workflow.sqlite3")
    conn.execute("CREATE TABLE ok (id INTEGER)")
    conn.close()

    readiness = read_pilot_readiness(tmp_path, now=NOW)
    assert readiness.status == "GO" and readiness.healthy is True
    assert "Pilot readiness" in render_pilot_readiness(readiness)


def test_pilot_readiness_no_go_when_supervisor_is_degraded(tmp_path):
    _write(
        tmp_path / "teammate_status.json",
        {"state": "IDLE", "iteration": 2, "finished_at": (NOW - timedelta(minutes=1)).isoformat()},
    )
    _write(
        tmp_path / "teammate_supervisor.json",
        {
            "degraded": True,
            "children": {"callback": {"pid": os.getpid(), "running": True}},
            "events": [{"event": "child_dropped_after_crash_loop", "child": "loop"}],
        },
    )
    import sqlite3

    conn = sqlite3.connect(tmp_path / "workflow.sqlite3")
    conn.execute("CREATE TABLE ok (id INTEGER)")
    conn.close()

    readiness = read_pilot_readiness(tmp_path, now=NOW)
    assert readiness.status == "NO_GO" and readiness.healthy is False
    assert "loop dropped" in render_pilot_readiness(readiness)


def test_pilot_readiness_no_go_when_supervisor_pid_is_stale(tmp_path):
    _write(
        tmp_path / "teammate_status.json",
        {"state": "IDLE", "iteration": 2, "finished_at": (NOW - timedelta(minutes=1)).isoformat()},
    )
    _write(
        tmp_path / "teammate_supervisor.json",
        {"degraded": False, "children": {"callback": {"pid": 99999999, "running": True}}},
    )
    import sqlite3

    conn = sqlite3.connect(tmp_path / "workflow.sqlite3")
    conn.execute("CREATE TABLE ok (id INTEGER)")
    conn.close()

    readiness = read_pilot_readiness(tmp_path, now=NOW)
    assert readiness.status == "NO_GO"
    assert "callback dropped" in render_pilot_readiness(readiness)


def test_pilot_readiness_degraded_when_browser_lock_is_stale(tmp_path):
    _write(
        tmp_path / "teammate_status.json",
        {"state": "IDLE", "iteration": 2, "finished_at": (NOW - timedelta(minutes=1)).isoformat()},
    )
    _write(
        tmp_path / "teammate_supervisor.json",
        {"degraded": False, "children": {"callback": {"pid": os.getpid(), "running": True}}},
    )
    import sqlite3

    conn = sqlite3.connect(tmp_path / "workflow.sqlite3")
    conn.execute("CREATE TABLE ok (id INTEGER)")
    conn.close()
    lock = tmp_path / "browser.busy"
    lock.write_text("write", encoding="utf-8")
    old = (NOW - timedelta(hours=2)).timestamp()
    os.utime(lock, (old, old))

    readiness = read_pilot_readiness(tmp_path, now=NOW, lock_stale_after_seconds=1800)
    assert readiness.status == "DEGRADED"
    assert "Browser lock is STALE" in render_pilot_readiness(readiness)


def test_pilot_readiness_includes_browser_session_when_configured(tmp_path, monkeypatch):
    _write(
        tmp_path / "teammate_status.json",
        {"state": "IDLE", "iteration": 2, "finished_at": (NOW - timedelta(minutes=1)).isoformat()},
    )
    _write(
        tmp_path / "teammate_supervisor.json",
        {"degraded": False, "children": {"callback": {"pid": os.getpid(), "running": True}, "loop": {"pid": os.getpid(), "running": True}}},
    )
    import sqlite3

    conn = sqlite3.connect(tmp_path / "workflow.sqlite3")
    conn.execute("CREATE TABLE ok (id INTEGER)")
    conn.close()

    def fake_read_browser_session_health(*, cdp_url, url_filter=None):
        from freight_recon.browser_session_health import BrowserSessionHealth

        return BrowserSessionHealth(
            status="SESSION_EXPIRED",
            healthy=False,
            detail="TMS browser session appears to be on a login/session-expired page; human re-auth is required.",
            cdp_url=cdp_url,
            url_filter=url_filter,
            active_url="https://secure.truckingoffice.com/login",
            tabs_seen=1,
            matching_tabs=1,
        )

    import freight_recon.browser_session_health as bsh

    monkeypatch.setattr(bsh, "read_browser_session_health", fake_read_browser_session_health)
    readiness = read_pilot_readiness(tmp_path, now=NOW, cdp_url="http://localhost:9222", url_filter="secure.truckingoffice.com")
    rendered = render_pilot_readiness(readiness)
    assert readiness.status == "NO_GO"
    assert "human re-auth is required" in rendered
