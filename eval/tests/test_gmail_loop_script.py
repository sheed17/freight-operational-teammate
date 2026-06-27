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
