"""Tests for Rasheed as the first supervised design partner run."""

from pathlib import Path
import subprocess
import sys

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.first_design_partner import verify_first_partner_slack  # noqa: E402
from run_first_design_partner import run_first_design_partner  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]


def test_first_design_partner_local_outbox_proves_operator_loop(tmp_path):
    report = run_first_design_partner(
        workspace=tmp_path / "first_partner",
        loads_count=8,
        seed=42,
        age_hours=48,
        dispatch_mode="LOCAL_OUTBOX",
    )

    assert report["ready"] is True
    assert report["email_ingestion_simulated"] is True
    assert report["carrier_sends_enabled"] is False
    assert report["real_tms_write_enabled"] is False
    assert report["slack_live_posting_enabled"] is False
    assert report["pilot"]["email_ingestion"]["packet_link_accuracy"] == 1.0
    assert report["pilot"]["local_callback_action_applied"] is True
    assert report["pilot"]["tms_readback_verified"] is True
    assert report["pilot"]["mock_tms_write_verified"] is True
    assert report["dispatch"]["statuses"] == {"OUTBOXED": 12}
    assert report["dispatch"]["channels"] == {"slack": 6, "email": 6}
    assert Path(report["artifacts"]["operator_report"]).exists()
    assert Path(report["artifacts"]["dispatch_attempts"]).exists()


def test_live_slack_mode_requires_real_delivery_secret(tmp_path, monkeypatch):
    monkeypatch.delenv("NEYMA_DELIVERY_SECRET_RASHEED_FIRST", raising=False)
    monkeypatch.delenv("NEYMA_SLACK_SIGNING_SECRET_RASHEED_FIRST", raising=False)
    monkeypatch.delenv("NEYMA_SLACK_BOT_TOKEN_RASHEED_FIRST", raising=False)

    with pytest.raises(SystemExit, match="Missing action-token secret"):
        run_first_design_partner(
            workspace=tmp_path / "first_partner",
            loads_count=8,
            seed=42,
            age_hours=48,
            dispatch_mode="LIVE_SLACK",
        )


def test_live_slack_mode_requires_signing_secret_and_bot_token(tmp_path, monkeypatch):
    monkeypatch.setenv("NEYMA_DELIVERY_SECRET_RASHEED_FIRST", "delivery-secret")
    monkeypatch.delenv("NEYMA_SLACK_SIGNING_SECRET_RASHEED_FIRST", raising=False)
    monkeypatch.delenv("NEYMA_SLACK_BOT_TOKEN_RASHEED_FIRST", raising=False)

    with pytest.raises(SystemExit, match="NEYMA_SLACK_SIGNING_SECRET_RASHEED_FIRST"):
        run_first_design_partner(
            workspace=tmp_path / "first_partner",
            loads_count=8,
            seed=42,
            age_hours=48,
            dispatch_mode="LIVE_SLACK",
        )


def test_cli_local_outbox_smoke(tmp_path):
    result = subprocess.run(
        [
            str(ROOT / ".venv" / "bin" / "python"),
            str(ROOT / "scripts" / "run_first_design_partner.py"),
            "--workspace",
            str(tmp_path / "cli_partner"),
            "--loads",
            "8",
            "--seed",
            "42",
            "--age-hours",
            "48",
            "--dispatch-mode",
            "LOCAL_OUTBOX",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert '"ready": true' in result.stdout
    assert '"real_tms_write_enabled": false' in result.stdout


def test_first_partner_slack_preflight_blocks_placeholders_and_missing_env():
    result = verify_first_partner_slack(ROOT / "configs" / "clients" / "rasheed_first_design_partner.yaml", env={})

    assert result.ready is False
    failed = {check.name for check in result.checks if not check.ok}
    assert "action_token_secret_present" in failed
    assert "slack_signing_secret_present" in failed
    assert "slack_bot_token_present" in failed
    assert "slack_channel_ids_replaced" in failed
    assert "email_outbound_disabled" not in failed
    assert "real_tms_write_disabled" not in failed


def test_first_partner_slack_preflight_ready_with_env_and_real_channel_ids(tmp_path):
    raw = yaml.safe_load((ROOT / "configs" / "clients" / "rasheed_first_design_partner.yaml").read_text())
    raw["delivery"]["slack"]["default_channel_id"] = "C0123REVIEW"
    raw["delivery"]["slack"]["routing"] = {
        "IMMEDIATE_PING": "C0123REVIEW",
        "CHANNEL_POST": "C0123REVIEW",
        "DIGEST_ONLY": "C0456DIGEST",
    }
    config = tmp_path / "rasheed_first.yaml"
    config.write_text(yaml.safe_dump(raw), encoding="utf-8")
    env = {
        "NEYMA_DELIVERY_SECRET_RASHEED_FIRST": "delivery-secret",
        "NEYMA_SLACK_SIGNING_SECRET_RASHEED_FIRST": "signing-secret",
        "NEYMA_SLACK_BOT_TOKEN_RASHEED_FIRST": "xoxb-test-token",
    }

    result = verify_first_partner_slack(config, env=env)

    assert result.ready is True
    checks = {check.name: check.ok for check in result.checks}
    assert checks["slack_delivery_preflight_ok"] is True
    assert checks["slack_channel_ids_replaced"] is True
