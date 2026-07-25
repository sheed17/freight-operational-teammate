"""Preflight checks for Rasheed as Neyma's first supervised design partner."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

import yaml
from pydantic import BaseModel, Field

from .channels import load_delivery_config, verify_delivery_config


class FirstPartnerCheck(BaseModel):
    name: str
    ok: bool
    detail: str


class FirstPartnerSlackPreflight(BaseModel):
    ready: bool
    checks: list[FirstPartnerCheck] = Field(default_factory=list)


def verify_first_partner_slack(
    client_config_path: str | Path,
    *,
    env: Mapping[str, str] | None = None,
) -> FirstPartnerSlackPreflight:
    """Verify real Slack can be connected before any LIVE_SLACK post is attempted."""
    env = os.environ if env is None else env
    client_config_path = Path(client_config_path)
    raw = yaml.safe_load(client_config_path.read_text(encoding="utf-8")) or {}
    checks: list[FirstPartnerCheck] = []
    config = load_delivery_config(client_config_path)
    if config is None:
        checks.append(_check("delivery_config_present", False, "delivery block is missing"))
        return FirstPartnerSlackPreflight(ready=False, checks=checks)
    checks.append(_check("delivery_config_present", True, "delivery block is present"))
    checks.extend(_base_safety_checks(raw))
    checks.extend(_channel_secret_checks(config, env))
    checks.extend(_slack_channel_checks(raw))
    return FirstPartnerSlackPreflight(ready=all(check.ok for check in checks), checks=checks)


def _base_safety_checks(raw: dict) -> list[FirstPartnerCheck]:
    tms = raw.get("tms") or {}
    pilot = raw.get("pilot") or {}
    delivery = raw.get("delivery") or {}
    email = delivery.get("email") or {}
    slack = delivery.get("slack") or {}
    return [
        _check("carrier_sends_disabled", pilot.get("carrier_email_send_mode") == "draft_only_send_gate", "carrier emails are draft-only"),
        _check("real_tms_write_disabled", tms.get("live_write_enabled") is False and tms.get("tms_write_enabled") is False, "real TMS writes disabled"),
        _check("email_outbound_disabled", email.get("outbound_enabled") is False, "email outbound disabled"),
        _check("slack_config_outbound_default_off", slack.get("outbound_enabled") is False, "Slack outbound disabled in config by default"),
    ]


def _channel_secret_checks(config, env: Mapping[str, str]) -> list[FirstPartnerCheck]:
    checks = [
        _check("action_token_secret_present", bool(env.get(config.action_token_secret_env)), config.action_token_secret_env),
    ]
    if config.slack is None:
        checks.append(_check("slack_config_present", False, "Slack config missing"))
        return checks
    checks.extend(
        [
            _check("slack_config_present", True, "Slack config present"),
            _check("slack_signing_secret_present", bool(env.get(config.slack.signing_secret_env)), config.slack.signing_secret_env),
            _check("slack_bot_token_present", bool(config.slack.bot_token_env and env.get(config.slack.bot_token_env)), config.slack.bot_token_env or "missing bot_token_env"),
        ]
    )
    delivery_checks = verify_delivery_config(config, env=env)
    slack_check = next((check for check in delivery_checks if check.channel.value == "slack"), None)
    checks.append(_check("slack_delivery_preflight_ok", bool(slack_check and slack_check.ok), "verify_delivery_config Slack check passes"))
    return checks


def _slack_channel_checks(raw: dict) -> list[FirstPartnerCheck]:
    slack = ((raw.get("delivery") or {}).get("slack") or {})
    ids = [slack.get("default_channel_id")] + list((slack.get("routing") or {}).values())
    replaced = [channel_id for channel_id in ids if channel_id and "REPLACE" not in channel_id]
    return [
        _check("slack_channel_ids_replaced", len(replaced) == len([i for i in ids if i]), "Slack channel IDs are configured"),
    ]


def _check(name: str, ok: bool, detail: str) -> FirstPartnerCheck:
    return FirstPartnerCheck(name=name, ok=ok, detail=detail)
