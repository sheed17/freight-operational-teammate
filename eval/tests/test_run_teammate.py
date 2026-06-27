"""Tests for the one-command teammate launcher: all processes share one correctly-wired workspace."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from run_teammate import build_process_commands  # noqa: E402


def _val_after(cmd: list[str], flag: str) -> str:
    return cmd[cmd.index(flag) + 1]


def test_all_processes_share_one_workspace_db_and_heartbeat():
    cmds = build_process_commands(workspace="/tmp/ws", client_config="cfg.yaml", daily_digest_hour=7)
    callback, loop, site = cmds["callback"], cmds["loop"], cmds["site"]

    # The callback's DB + heartbeat are derived from the SAME workspace the loop drives — so the
    # Slack `status` surface cannot read a different file than the loop writes (mismatch impossible).
    assert _val_after(callback, "--db") == "/tmp/ws/workflow.sqlite3"
    assert _val_after(callback, "--status-file") == "/tmp/ws/teammate_status.json"
    assert _val_after(callback, "--workspace") == "/tmp/ws"
    assert _val_after(loop, "--workspace") == "/tmp/ws"
    assert "/tmp/ws/site" in site

    # Always-on defaults: auto-enter approved payables (mock) + forward the digest hour.
    assert "--auto-enter-approved-mock-tms" in callback
    assert _val_after(loop, "--daily-digest-hour") == "7"


def test_no_auto_enter_omits_the_mock_tms_flag():
    cmds = build_process_commands(workspace="/tmp/ws", client_config="c", auto_enter_mock_tms=False)
    assert "--auto-enter-approved-mock-tms" not in cmds["callback"]
