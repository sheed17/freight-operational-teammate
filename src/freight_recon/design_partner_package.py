"""Verification for supervised design-partner pilot readiness package."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from .channels import load_delivery_config, verify_delivery_config


class PackageCheck(BaseModel):
    name: str
    ok: bool
    detail: str


class PackageVerification(BaseModel):
    ready: bool
    checks: list[PackageCheck] = Field(default_factory=list)


def verify_design_partner_package(
    *,
    client_config_path: str | Path,
    pilot_ledger_path: str | Path,
) -> PackageVerification:
    checks: list[PackageCheck] = []
    client_config_path = Path(client_config_path)
    pilot_ledger_path = Path(pilot_ledger_path)
    data = yaml.safe_load(client_config_path.read_text(encoding="utf-8")) or {}

    checks.append(_check(bool(data.get("client_id")), "client_id_present", "client_id is set"))
    checks.append(_check(bool(data.get("company_name")), "company_name_present", "company_name is set"))
    checks.extend(_safety_checks(data))
    checks.extend(_delivery_checks(client_config_path))
    checks.extend(_pilot_ledger_checks(pilot_ledger_path))

    return PackageVerification(ready=all(check.ok for check in checks), checks=checks)


def _safety_checks(data: dict[str, Any]) -> list[PackageCheck]:
    tms = data.get("tms") or {}
    pilot = data.get("pilot") or {}
    delivery = data.get("delivery") or {}
    slack = delivery.get("slack") or {}
    email = delivery.get("email") or {}
    return [
        _check(tms.get("live_write_enabled") is False, "tms_live_write_disabled", "TMS live write is false"),
        _check(tms.get("tms_write_enabled") is False, "tms_write_disabled", "TMS write feature gate is false"),
        _check(
            tms.get("session_policy") == "human_established_session_only",
            "human_session_only",
            "TMS session policy is human-established only",
        ),
        _check(
            tms.get("browser_automation_allowed_against") == "customer_system_read_only_after_screen_map",
            "customer_system_read_only_mapping",
            "browser automation is read-only until customer-specific screen map exists",
        ),
        _check(
            _is_customer_specific_screen_map(tms.get("screen_map_path")),
            "customer_specific_screen_map_path",
            "screen_map_path is customer-specific and not the AscendTMS reference catalog",
        ),
        _check(pilot.get("supervised") is True, "pilot_supervised", "pilot is supervised"),
        _check(
            pilot.get("autonomous_tms_write_enabled") is False,
            "autonomous_tms_write_disabled",
            "autonomous TMS write disabled",
        ),
        _check(pilot.get("live_sends_enabled") is False, "pilot_live_sends_disabled", "pilot live sends disabled"),
        _check(slack.get("outbound_enabled") is False, "slack_outbound_disabled", "Slack outbound disabled"),
        _check(email.get("outbound_enabled") is False, "email_outbound_disabled", "email outbound disabled"),
    ]


def _delivery_checks(client_config_path: Path) -> list[PackageCheck]:
    try:
        config = load_delivery_config(client_config_path)
    except Exception as exc:  # noqa: BLE001 - report as failed package check
        return [_check(False, "delivery_config_parses", f"delivery config parse failed: {exc}")]
    if config is None:
        return [_check(False, "delivery_config_present", "delivery block is missing")]
    checks = [_check(True, "delivery_config_parses", "delivery block parses")]
    env_names = [config.action_token_secret_env]
    if config.slack is not None:
        env_names.append(config.slack.signing_secret_env)
        if config.slack.bot_token_env:
            env_names.append(config.slack.bot_token_env)
    if config.email is not None and config.email.from_env:
        env_names.append(config.email.from_env)
    bad_names = [name for name in env_names if not _looks_like_env_var_name(name)]
    checks.append(
        _check(
            not bad_names,
            "delivery_secret_env_names_shape",
            "delivery secret fields use env-var names, not literal secret values",
        )
    )
    # Empty env is intentional for templates: this confirms missing secret values are not committed.
    preflight = verify_delivery_config(config, env={})
    missing = sorted({name for check in preflight for name in check.missing_secrets})
    checks.append(
        _check(
            bool(missing),
            "delivery_secrets_not_committed",
            "delivery secrets are referenced by env var and not present in empty env",
        )
    )
    return checks


def _pilot_ledger_checks(pilot_ledger_path: Path) -> list[PackageCheck]:
    if not pilot_ledger_path.exists():
        return [_check(False, "internal_pilot_ledger_exists", f"missing {pilot_ledger_path}")]
    try:
        ledger = json.loads(pilot_ledger_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [_check(False, "internal_pilot_ledger_json", f"ledger is not valid JSON: {exc}")]
    return [
        _check(True, "internal_pilot_ledger_exists", "internal pilot ledger exists"),
        _check(
            ledger.get("ready_for_design_partner") is True,
            "internal_pilot_green",
            "internal pilot ledger ready_for_design_partner is true",
        ),
        _check(int(ledger.get("days_completed") or 0) >= 7, "internal_pilot_week_complete", "at least 7 days completed"),
        _check(not ledger.get("blockers"), "internal_pilot_no_blockers", "internal pilot has no blockers"),
    ]


def _check(ok: bool, name: str, detail: str) -> PackageCheck:
    return PackageCheck(name=name, ok=ok, detail=detail)


def _looks_like_env_var_name(value: str | None) -> bool:
    if not value:
        return False
    return bool(re.fullmatch(r"[A-Z][A-Z0-9_<>]*", value))


def _is_customer_specific_screen_map(value: str | None) -> bool:
    if not value:
        return False
    lowered = value.lower()
    return (
        lowered.startswith("configs/tms/")
        and lowered.endswith("_screen_map.json")
        and "ascendtms" not in lowered
        and "reference" not in lowered
    )
