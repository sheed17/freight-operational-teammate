"""Tests for the one-command teammate launcher: all processes share one correctly-wired workspace."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from run_teammate import build_process_commands, preflight_credentials  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CLIENT_CONFIG = str(ROOT / "configs" / "clients" / "rasheed_first_design_partner.yaml")


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


def _full_env() -> dict[str, str]:
    return {
        "NEYMA_IMAP_USERNAME": "u",
        "NEYMA_IMAP_PASSWORD": "p",
        "OPENAI_API_KEY": "k",
        "NEYMA_DELIVERY_SECRET_RASHEED_FIRST": "s",
        "NEYMA_SLACK_SIGNING_SECRET_RASHEED_FIRST": "ss",
        "NEYMA_SLACK_BOT_TOKEN_RASHEED_FIRST": "bt",
    }


def test_preflight_passes_when_all_secrets_present():
    assert preflight_credentials(client_config=CLIENT_CONFIG, env=_full_env()) == []


def test_preflight_flags_each_missing_secret():
    # No env at all -> mail creds, OpenAI key, and all of the client's Slack/action secrets are flagged.
    problems = preflight_credentials(client_config=CLIENT_CONFIG, env={})
    blob = " ".join(problems).lower()
    assert "imap username" in blob and "imap app password" in blob
    assert "openai_api_key" in blob
    assert "neyma_delivery_secret_rasheed_first" in blob
    assert "neyma_slack_signing_secret_rasheed_first" in blob
    assert "neyma_slack_bot_token_rasheed_first" in blob


def test_preflight_accepts_smtp_creds_as_mail_fallback():
    env = _full_env()
    del env["NEYMA_IMAP_USERNAME"]
    del env["NEYMA_IMAP_PASSWORD"]
    env["NEYMA_SMTP_USERNAME"] = "u"
    env["NEYMA_SMTP_PASSWORD"] = "p"
    assert preflight_credentials(client_config=CLIENT_CONFIG, env=env) == []
