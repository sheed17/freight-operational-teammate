"""Tests for the owner-onboarding readiness gate."""

import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.owner_onboarding import evaluate_owner_onboarding, render_owner_onboarding  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CLIENT_CONFIG = ROOT / "configs" / "clients" / "rasheed_first_design_partner.yaml"


def _env() -> dict[str, str]:
    return {
        "NEYMA_IMAP_USERNAME": "u",
        "NEYMA_IMAP_PASSWORD": "p",
        "OPENAI_API_KEY": "k",
        "NEYMA_DELIVERY_SECRET_RASHEED_FIRST": "delivery-secret",
        "NEYMA_SLACK_SIGNING_SECRET_RASHEED_FIRST": "slack-secret",
        "NEYMA_SLACK_BOT_TOKEN_RASHEED_FIRST": "xoxb-token",
    }


def test_owner_onboarding_dry_preflight_ready_when_config_and_owner_controls_are_present(tmp_path):
    readiness = evaluate_owner_onboarding(
        workspace=tmp_path,
        client_config=CLIENT_CONFIG,
        env=_env(),
        allowed_slack_users=("U_OWNER",),
        allowed_slack_channel="C0BB8KG21J8",
        operation_url_filter="truckingoffice",
    )
    assert readiness.ready is True
    rendered = render_owner_onboarding(readiness)
    assert "Owner onboarding dry preflight: READY" in rendered
    assert "live use still requires --require-running" in rendered
    assert "runtime_credentials" in rendered


def test_owner_onboarding_requires_owner_slack_allowlist_and_tms_filter(tmp_path):
    readiness = evaluate_owner_onboarding(
        workspace=tmp_path,
        client_config=CLIENT_CONFIG,
        env=_env(),
        allowed_slack_users=(),
        allowed_slack_channel=None,
        operation_url_filter=None,
    )
    assert readiness.ready is False
    rendered = render_owner_onboarding(readiness)
    assert "slack_owner_allowlist" in rendered
    assert "tms_url_filter" in rendered


def test_owner_onboarding_running_gate_uses_runtime_readiness(tmp_path):
    (tmp_path / "teammate_status.json").write_text(
        json.dumps({"state": "IDLE", "iteration": 2, "consecutive_failures": 0}),
        encoding="utf-8",
    )
    (tmp_path / "teammate_supervisor.json").write_text(
        json.dumps({"degraded": False, "children": {"callback": {"pid": os.getpid(), "running": True}, "loop": {"pid": os.getpid(), "running": True}}}),
        encoding="utf-8",
    )
    conn = sqlite3.connect(tmp_path / "workflow.sqlite3")
    conn.execute("CREATE TABLE ok (id INTEGER)")
    conn.close()

    readiness = evaluate_owner_onboarding(
        workspace=tmp_path,
        client_config=CLIENT_CONFIG,
        env=_env(),
        allowed_slack_users=("U_OWNER",),
        allowed_slack_channel="C0BB8KG21J8",
        operation_url_filter="truckingoffice",
        require_running=True,
        cdp_url=None,
    )
    assert readiness.ready is True


def test_owner_onboarding_callback_probe_must_return_status_readiness(tmp_path):
    def probe(text, secret, url, user, channel):
        assert text == "status"
        assert secret == b"slack-secret"
        assert user == "U_OWNER"
        assert channel == "C0BB8KG21J8"
        return 200, ":large_green_circle: *Pilot readiness:* GO"

    readiness = evaluate_owner_onboarding(
        workspace=tmp_path,
        client_config=CLIENT_CONFIG,
        env=_env(),
        allowed_slack_users=("U_OWNER",),
        allowed_slack_channel="C0BB8KG21J8",
        operation_url_filter="truckingoffice",
        callback_url="https://neyma.ngrok-free.dev/slack/commands",
        require_public_ingress=True,
        probe=probe,
    )
    assert readiness.ready is True


def test_owner_onboarding_callback_probe_fails_if_callback_does_not_answer_status(tmp_path):
    readiness = evaluate_owner_onboarding(
        workspace=tmp_path,
        client_config=CLIENT_CONFIG,
        env=_env(),
        allowed_slack_users=("U_OWNER",),
        allowed_slack_channel="C0BB8KG21J8",
        operation_url_filter="truckingoffice",
        callback_url="http://127.0.0.1:8001/slack/commands",
        probe=lambda *_args: (200, "Commands:"),
    )
    assert readiness.ready is False
    assert "slack_callback_probe" in render_owner_onboarding(readiness)


def test_owner_onboarding_public_ingress_requirement_rejects_localhost_callback(tmp_path):
    readiness = evaluate_owner_onboarding(
        workspace=tmp_path,
        client_config=CLIENT_CONFIG,
        env=_env(),
        allowed_slack_users=("U_OWNER",),
        allowed_slack_channel="C0BB8KG21J8",
        operation_url_filter="truckingoffice",
        callback_url="http://127.0.0.1:8001/slack/commands",
        require_public_ingress=True,
        probe=lambda *_args: (200, ":large_green_circle: *Pilot readiness:* GO"),
    )
    assert readiness.ready is False
    assert "owner-ready Slack ingress must be public HTTPS" in render_owner_onboarding(readiness)
