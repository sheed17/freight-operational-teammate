"""Tests for supervised design-partner deployment package verification."""

from pathlib import Path
import json
import sys

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.design_partner_package import verify_design_partner_package  # noqa: E402


def _ledger(path: Path, *, ready=True, days=7, blockers=None):
    path.write_text(
        json.dumps(
            {
                "ready_for_design_partner": ready,
                "days_completed": days,
                "blockers": blockers or [],
            }
        ),
        encoding="utf-8",
    )


def test_design_partner_template_is_safe_with_green_ledger(tmp_path):
    root = Path(__file__).resolve().parents[2]
    ledger = tmp_path / "pilot_session_ledger.json"
    _ledger(ledger)

    result = verify_design_partner_package(
        client_config_path=root / "configs" / "clients" / "design_partner_template.yaml",
        pilot_ledger_path=ledger,
    )

    assert result.ready is True
    checks = {check.name: check.ok for check in result.checks}
    assert checks["tms_live_write_disabled"] is True
    assert checks["pilot_live_sends_disabled"] is True
    assert checks["slack_outbound_disabled"] is True
    assert checks["email_outbound_disabled"] is True
    assert checks["delivery_secret_env_names_shape"] is True
    assert checks["delivery_secrets_not_committed"] is True
    assert checks["customer_system_read_only_mapping"] is True
    assert checks["customer_specific_screen_map_path"] is True
    assert checks["internal_pilot_week_complete"] is True


def test_package_blocks_if_live_write_enabled(tmp_path):
    root = Path(__file__).resolve().parents[2]
    template = yaml.safe_load((root / "configs" / "clients" / "design_partner_template.yaml").read_text())
    template["tms"]["live_write_enabled"] = True
    config = tmp_path / "partner.yaml"
    config.write_text(yaml.safe_dump(template), encoding="utf-8")
    ledger = tmp_path / "pilot_session_ledger.json"
    _ledger(ledger)

    result = verify_design_partner_package(client_config_path=config, pilot_ledger_path=ledger)

    assert result.ready is False
    failed = {check.name for check in result.checks if not check.ok}
    assert "tms_live_write_disabled" in failed


def test_package_blocks_without_green_internal_week(tmp_path):
    root = Path(__file__).resolve().parents[2]
    ledger = tmp_path / "pilot_session_ledger.json"
    _ledger(ledger, ready=False, days=3, blockers=["day_01:tokens_redacted"])

    result = verify_design_partner_package(
        client_config_path=root / "configs" / "clients" / "design_partner_template.yaml",
        pilot_ledger_path=ledger,
    )

    assert result.ready is False
    failed = {check.name for check in result.checks if not check.ok}
    assert "internal_pilot_green" in failed
    assert "internal_pilot_week_complete" in failed
    assert "internal_pilot_no_blockers" in failed


def test_package_blocks_literal_secret_in_env_field(tmp_path):
    root = Path(__file__).resolve().parents[2]
    template = yaml.safe_load((root / "configs" / "clients" / "design_partner_template.yaml").read_text())
    template["delivery"]["action_token_secret_env"] = "super-secret-token-value"
    config = tmp_path / "partner.yaml"
    config.write_text(yaml.safe_dump(template), encoding="utf-8")
    ledger = tmp_path / "pilot_session_ledger.json"
    _ledger(ledger)

    result = verify_design_partner_package(client_config_path=config, pilot_ledger_path=ledger)

    assert result.ready is False
    failed = {check.name for check in result.checks if not check.ok}
    assert "delivery_secret_env_names_shape" in failed


def test_package_blocks_reference_screen_map(tmp_path):
    root = Path(__file__).resolve().parents[2]
    template = yaml.safe_load((root / "configs" / "clients" / "design_partner_template.yaml").read_text())
    template["tms"]["screen_map_path"] = "configs/tms/ascendtms_screen_map.json"
    config = tmp_path / "partner.yaml"
    config.write_text(yaml.safe_dump(template), encoding="utf-8")
    ledger = tmp_path / "pilot_session_ledger.json"
    _ledger(ledger)

    result = verify_design_partner_package(client_config_path=config, pilot_ledger_path=ledger)

    assert result.ready is False
    failed = {check.name for check in result.checks if not check.ok}
    assert "customer_specific_screen_map_path" in failed


def test_package_blocks_non_read_only_browser_mapping_policy(tmp_path):
    root = Path(__file__).resolve().parents[2]
    template = yaml.safe_load((root / "configs" / "clients" / "design_partner_template.yaml").read_text())
    template["tms"]["browser_automation_allowed_against"] = "customer_system_write"
    config = tmp_path / "partner.yaml"
    config.write_text(yaml.safe_dump(template), encoding="utf-8")
    ledger = tmp_path / "pilot_session_ledger.json"
    _ledger(ledger)

    result = verify_design_partner_package(client_config_path=config, pilot_ledger_path=ledger)

    assert result.ready is False
    failed = {check.name for check in result.checks if not check.ok}
    assert "customer_system_read_only_mapping" in failed
