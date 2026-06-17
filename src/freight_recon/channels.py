"""Repeatable, multi-tenant channel integration for delivery transports.

This is the layer that makes onboarding a customer's Slack/email seamless and repeatable: each
customer carries a ``delivery:`` block in ``configs/clients/<customer>.yaml`` that names *which*
channels are on, how to route by severity, and — crucially — the **environment variable names** that
hold the secrets. Secrets never live in the repo or the config; only their names do.

Onboarding a customer becomes a runbook, not a code change:

1. Add/extend the customer's client config ``delivery:`` block.
2. Set the named environment variables (signing secret, action-token secret, etc.).
3. Run ``verify_delivery_config`` (or ``scripts/verify_channels.py``) — it confirms the config is
   well-formed and every named secret resolves, without sending anything.
4. Build live adapters with ``build_channel_adapters`` once outbound is enabled and gated.

The transports themselves (``slack_adapter`` / ``email_adapter``) are unchanged; this module only
wires per-customer configuration and secret resolution into them.
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Mapping

import yaml
from pydantic import BaseModel, Field

from .delivery import DeliverySigner
from .email_adapter import DEFAULT_ACTION_BASE_URL, DEFAULT_FROM_ADDRESS, EmailDeliveryAdapter
from .review import ReviewRoute
from .slack_adapter import SlackDeliveryAdapter
from .workflow import WorkflowStore


class ChannelType(str, Enum):
    DELIVERY = "delivery"
    SLACK = "slack"
    EMAIL = "email"


class ChannelConfigError(RuntimeError):
    """Raised when a delivery channel config is invalid or a required secret is unresolved."""


class SlackChannelConfig(BaseModel):
    enabled: bool = True
    outbound_enabled: bool = False
    signing_secret_env: str
    bot_token_env: str | None = None
    default_channel_id: str | None = None
    # ReviewRoute value -> Slack channel id, so severity routing maps to real channels per customer.
    routing: dict[str, str] = Field(default_factory=dict)


class EmailChannelConfig(BaseModel):
    enabled: bool = True
    sender: str | None = None
    from_env: str | None = None
    to: list[str] = Field(default_factory=list)
    action_base_url: str = DEFAULT_ACTION_BASE_URL
    outbound_enabled: bool = False
    outbox_dir: str | None = None
    # SMTP transport (live send). Credentials are referenced by env-var NAME only; never stored.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user_env: str | None = None
    smtp_password_env: str | None = None
    smtp_starttls: bool = True


class DeliveryConfig(BaseModel):
    default_channel: ChannelType = ChannelType.SLACK
    # Env var holding the HMAC secret used to sign action tokens for this customer.
    action_token_secret_env: str
    slack: SlackChannelConfig | None = None
    email: EmailChannelConfig | None = None


class ChannelCheck(BaseModel):
    channel: ChannelType
    enabled: bool
    ok: bool
    missing_secrets: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


def load_delivery_config(client_config_path: str | Path) -> DeliveryConfig | None:
    """Load the ``delivery:`` block from a client config YAML, or ``None`` if absent."""
    data = yaml.safe_load(Path(client_config_path).read_text(encoding="utf-8")) or {}
    block = data.get("delivery")
    if not block:
        return None
    return DeliveryConfig.model_validate(block)


def verify_delivery_config(
    config: DeliveryConfig,
    *,
    env: Mapping[str, str] | None = None,
) -> list[ChannelCheck]:
    """Preflight a customer's delivery config without sending anything.

    Returns one :class:`ChannelCheck` per configured channel plus a synthetic check for the shared
    action-token secret, reporting whether every named environment variable resolves.
    """
    env = os.environ if env is None else env
    checks: list[ChannelCheck] = []

    token_present = bool(env.get(config.action_token_secret_env))
    checks.append(
        ChannelCheck(
            channel=ChannelType.DELIVERY,
            enabled=True,
            ok=token_present,
            missing_secrets=[] if token_present else [config.action_token_secret_env],
            issues=[] if token_present else ["action-token signing secret is not set"],
        )
    )

    if config.slack is not None:
        checks.append(_check_slack(config.slack, env))
    if config.email is not None:
        checks.append(_check_email(config.email, env))
    return checks


def build_signer(config: DeliveryConfig, *, env: Mapping[str, str] | None = None) -> DeliverySigner:
    """Build the action-token signer for a customer from the env-named secret (fail closed)."""
    env = os.environ if env is None else env
    secret = env.get(config.action_token_secret_env)
    if not secret:
        raise ChannelConfigError(
            f"action-token secret env var is not set: {config.action_token_secret_env}"
        )
    return DeliverySigner(secret)


def build_channel_adapters(
    store: WorkflowStore,
    config: DeliveryConfig,
    *,
    env: Mapping[str, str] | None = None,
) -> dict[ChannelType, object]:
    """Build live transport adapters for every enabled channel whose secrets resolve.

    Skips channels that are disabled or missing a required secret (use ``verify_delivery_config``
    first to surface those). Returns a mapping of channel type to its adapter.
    """
    env = os.environ if env is None else env
    signer = build_signer(config, env=env)
    adapters: dict[ChannelType, object] = {}

    if config.slack is not None and config.slack.enabled:
        signing_secret = env.get(config.slack.signing_secret_env)
        if signing_secret:
            adapters[ChannelType.SLACK] = SlackDeliveryAdapter(
                store, signer=signer, signing_secret=signing_secret
            )

    if config.email is not None and config.email.enabled:
        adapters[ChannelType.EMAIL] = EmailDeliveryAdapter(
            store,
            signer=signer,
            action_base_url=config.email.action_base_url,
            sender=_email_sender(config.email, env),
        )
    return adapters


def slack_channel_for_route(slack: SlackChannelConfig, route: ReviewRoute) -> str | None:
    """Resolve the Slack channel id for a routing decision, falling back to the default channel."""
    return slack.routing.get(route.value) or slack.default_channel_id


def email_recipients(email: EmailChannelConfig) -> list[str]:
    return list(email.to)


def email_sender(email: EmailChannelConfig, env: Mapping[str, str]) -> str:
    return _email_sender(email, env)


def _check_slack(slack: SlackChannelConfig, env: Mapping[str, str]) -> ChannelCheck:
    if not slack.enabled:
        return ChannelCheck(channel=ChannelType.SLACK, enabled=False, ok=True)
    missing = [name for name in (slack.signing_secret_env, slack.bot_token_env) if name and not env.get(name)]
    issues = []
    if not slack.default_channel_id and not slack.routing:
        issues.append("no default_channel_id or routing configured")
    return ChannelCheck(
        channel=ChannelType.SLACK,
        enabled=True,
        ok=not missing and not issues,
        missing_secrets=missing,
        issues=issues,
    )


def _check_email(email: EmailChannelConfig, env: Mapping[str, str]) -> ChannelCheck:
    if not email.enabled:
        return ChannelCheck(channel=ChannelType.EMAIL, enabled=False, ok=True)
    missing = [email.from_env] if email.from_env and not env.get(email.from_env) else []
    issues = []
    if not email.to:
        issues.append("no recipients configured")
    if not _email_sender(email, env):
        issues.append("no sender address (set `sender` or `from_env`)")
    return ChannelCheck(
        channel=ChannelType.EMAIL,
        enabled=True,
        ok=not missing and not issues,
        missing_secrets=missing,
        issues=issues,
    )


def _email_sender(email: EmailChannelConfig, env: Mapping[str, str]) -> str:
    if email.from_env:
        return env.get(email.from_env, "")
    return email.sender or DEFAULT_FROM_ADDRESS
