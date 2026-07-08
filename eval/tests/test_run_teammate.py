"""Tests for the one-command teammate launcher: all processes share one correctly-wired workspace."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from run_teammate import build_process_commands, preflight_credentials, write_supervisor_state  # noqa: E402

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


def test_operation_router_flags_are_opt_in_for_callback():
    default_cmds = build_process_commands(workspace="/tmp/ws", client_config="c")
    assert "--enable-operation-router" not in default_cmds["callback"]

    cmds = build_process_commands(
        workspace="/tmp/ws",
        client_config="c",
        enable_operation_router=True,
        allowed_slack_users=("U_OWNER",),
        allowed_slack_channel="C_OPS",
        operation_url_filter="transporters",
    )
    callback = cmds["callback"]
    assert "--enable-operation-router" in callback
    assert _val_after(callback, "--allowed-slack-user") == "U_OWNER"
    assert _val_after(callback, "--allowed-slack-channel") == "C_OPS"
    assert _val_after(callback, "--operation-url-filter") == "transporters"


def test_gmail_loop_can_enable_real_inbox_triage():
    cmds = build_process_commands(
        workspace="/tmp/ws",
        client_config="c",
        enable_triage=True,
        triage_model="gpt-5.4",
    )
    loop = cmds["loop"]
    assert "--enable-triage" in loop
    assert _val_after(loop, "--triage-model") == "gpt-5.4"


def test_ngrok_supervised_forwards_fixed_domain_to_callback_port():
    cmds = build_process_commands(
        workspace="/tmp/ws", client_config="c", callback_port=8001,
        ngrok_domain="frigidly-sixteen-shifter.ngrok-free.dev", ngrok_bin="ngrok",
    )
    ngrok = cmds["ngrok"]
    # Modern --url=https://<domain> form, forwarding to 127.0.0.1 explicitly (a bare port lets ngrok
    # pick IPv6 [::1] while the callback binds IPv4 only -> ERR_NGROK_8012 connection refused).
    assert ngrok == [
        "ngrok", "http", "--url=https://frigidly-sixteen-shifter.ngrok-free.dev",
        "http://127.0.0.1:8001", "--log=stdout",
    ]


def test_ngrok_omitted_when_no_domain_or_no_binary():
    assert "ngrok" not in build_process_commands(workspace="/tmp/ws", client_config="c")
    assert "ngrok" not in build_process_commands(
        workspace="/tmp/ws", client_config="c", ngrok_domain="d.ngrok-free.dev", ngrok_bin=None
    )


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


def test_supervision_self_heals_with_backoff_then_gives_up_on_a_crash_loop():
    from run_teammate import supervision_decision

    # first crash after a calm period -> restart quickly, counter starts at 1
    assert supervision_decision(crashes=0, seconds_since_last_crash=9999) == (True, 2.0, 1)

    # rapid consecutive crashes -> exponential backoff, capped at 30s
    r, b, n = supervision_decision(crashes=1, seconds_since_last_crash=1); assert (r, b, n) == (True, 4.0, 2)
    r, b, n = supervision_decision(crashes=3, seconds_since_last_crash=1); assert (r, b, n) == (True, 16.0, 4)
    r, b, n = supervision_decision(crashes=4, seconds_since_last_crash=1); assert (r, b, n) == (True, 30.0, 5)  # 2^5=32 -> cap 30

    # too many rapid crashes -> give up (crash-loop guard), don't spin forever
    assert supervision_decision(crashes=5, seconds_since_last_crash=1) == (False, 0.0, 6)

    # a calm period resets the counter, so an occasional crash always self-heals
    assert supervision_decision(crashes=5, seconds_since_last_crash=9999) == (True, 2.0, 1)


def test_supervisor_state_records_degraded_child_drop(tmp_path):
    p = write_supervisor_state(
        tmp_path,
        children={"callback": 1234},
        degraded=True,
        events=[{"event": "child_dropped_after_crash_loop", "child": "loop"}],
    )
    blob = p.read_text(encoding="utf-8")
    assert "child_dropped_after_crash_loop" in blob
    assert '"degraded": true' in blob
