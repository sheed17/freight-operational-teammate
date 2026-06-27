"""Tests for the continuous Gmail -> Slack loop wrapper."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_gmail_loop_writes_status_and_forwards_args(tmp_path):
    script = ROOT / "scripts" / "run_gmail_to_slack_loop.py"
    workspace = tmp_path / "loop"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--workspace",
            str(workspace),
            "--iterations",
            "1",
            "--interval-seconds",
            "1",
            "--stop-on-error",
            "--",
            "--text",
        ],
        text=True,
        capture_output=True,
        check=False,
        env={},
    )

    assert result.returncode != 0
    status = json.loads((workspace / "teammate_status.json").read_text(encoding="utf-8"))
    assert status["state"] == "ERROR"
    assert status["iteration"] == 1
    assert "--text" in status["command"]
    assert "--" not in status["command"]


def test_gmail_loop_redacts_inline_and_separate_credentials(tmp_path):
    script = ROOT / "scripts" / "run_gmail_to_slack_loop.py"
    workspace = tmp_path / "loop"

    subprocess.run(
        [
            sys.executable,
            str(script),
            "--workspace",
            str(workspace),
            "--iterations",
            "1",
            "--interval-seconds",
            "1",
            "--stop-on-error",
            "--username=person@example.com",
            "--password",
            "super-secret",
        ],
        text=True,
        capture_output=True,
        check=False,
        env={},
    )

    raw = (workspace / "teammate_status.json").read_text(encoding="utf-8")
    assert "person@example.com" not in raw
    assert "super-secret" not in raw
    status = json.loads(raw)
    assert "--username=REDACTED" in status["command"]
    assert "REDACTED" in status["command"]  # the separate --password value is redacted too


def _loop_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    import run_gmail_to_slack_loop as loop

    return loop


def test_loop_alert_fires_once_on_threshold_and_recovery():
    loop = _loop_module()
    # first failure at the threshold -> alert
    first = loop._loop_alert(1, 0, 1, iteration=3, returncode=1)
    assert first and "alert" in first.lower()
    # further failures -> no repeat alert (not spammy)
    assert loop._loop_alert(2, 1, 1, iteration=4, returncode=1) is None
    # recovery after having alerted -> recovered message
    recovered = loop._loop_alert(0, 2, 1, iteration=5, returncode=0)
    assert recovered and "recovered" in recovered.lower()
    # steady healthy state -> nothing
    assert loop._loop_alert(0, 0, 1, iteration=6, returncode=0) is None


def test_build_alert_poster_is_none_without_config():
    loop = _loop_module()
    assert loop._build_alert_poster(None) is None


def test_scrub_redacts_secret_shaped_output():
    loop = _loop_module()
    assert "hunter2" not in loop._scrub("IMAP error: password=hunter2 rejected")
    assert "[redacted]" in loop._scrub("authorization: Bearer abc123xyz")
    assert loop._scrub("normal line with no secrets") == "normal line with no secrets"


def test_new_work_nudge_fires_only_on_newly_dispatched_cards():
    loop = _loop_module()
    # A new card was actually dispatched this cycle -> volunteer it.
    nudge = loop._new_work_nudge({"sent": 3, "review_payloads": 7, "new_messages": 5})
    assert nudge and "3 new item" in nudge
    # The spam case: BODY.PEEK re-reads the same UNSEEN mail so reviews are re-derived (7), but the
    # dispatch layer re-sent nothing (sent=0). Must stay quiet instead of nudging every interval.
    assert loop._new_work_nudge({"sent": 0, "review_payloads": 7, "new_messages": 0}) is None
    assert loop._new_work_nudge({"review_payloads": 0, "new_messages": 4}) is None  # nothing to do -> quiet
    assert loop._new_work_nudge(None) is None


def test_cycle_summary_parses_report(tmp_path):
    loop = _loop_module()
    (tmp_path / "gmail_to_slack_report.json").write_text(
        json.dumps({"workflow": {"new_messages": 4, "packet_runs": 2, "review_payloads": 3}, "dispatch": {"sent": 3}})
    )
    assert loop._cycle_summary(tmp_path) == {"new_messages": 4, "packet_runs": 2, "review_payloads": 3, "sent": 3}
    assert loop._cycle_summary(tmp_path / "missing") is None


def test_should_post_digest_once_per_day_after_hour():
    from datetime import datetime, timezone

    loop = _loop_module()
    now = datetime.now(timezone.utc)
    local_hour = now.astimezone().hour
    today = now.astimezone().date().isoformat()
    assert loop._should_post_digest(now, None, None) is False  # disabled
    assert loop._should_post_digest(now, None, local_hour) is True  # at/after hour, not posted today
    assert loop._should_post_digest(now, today, local_hour) is False  # already posted today
    if local_hour < 23:
        assert loop._should_post_digest(now, None, local_hour + 1) is False  # before the hour
