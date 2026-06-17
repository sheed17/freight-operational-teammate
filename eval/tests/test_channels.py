"""Tests for the repeatable multi-tenant channel integration layer."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.channels import (  # noqa: E402
    ChannelConfigError,
    ChannelType,
    build_channel_adapters,
    build_signer,
    load_delivery_config,
    slack_channel_for_route,
    verify_delivery_config,
)
from freight_recon.email_adapter import EmailDeliveryAdapter  # noqa: E402
from freight_recon.review import ReviewRoute  # noqa: E402
from freight_recon.slack_adapter import SlackDeliveryAdapter  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402

_CONFIG_YAML = """
client_id: acme_freight
delivery:
  default_channel: slack
  action_token_secret_env: NEYMA_DELIVERY_SECRET_ACME
  slack:
    enabled: true
    signing_secret_env: NEYMA_SLACK_SIGNING_SECRET_ACME
    bot_token_env: NEYMA_SLACK_BOT_TOKEN_ACME
    default_channel_id: C0DEFAULT
    routing:
      IMMEDIATE_PING: C0PINGS
      DIGEST_ONLY: C0DIGEST
  email:
    enabled: true
    sender: neyma@acme-freight.test
    to:
      - controller@acme-freight.test
    action_base_url: https://app.neyma.example/email/action
    outbound_enabled: false
"""

_FULL_ENV = {
    "NEYMA_DELIVERY_SECRET_ACME": "acme-action-secret",
    "NEYMA_SLACK_SIGNING_SECRET_ACME": "acme-slack-secret",
    "NEYMA_SLACK_BOT_TOKEN_ACME": "xoxb-acme",
}


def _config(tmp_path):
    path = tmp_path / "acme_freight.yaml"
    path.write_text(_CONFIG_YAML, encoding="utf-8")
    return load_delivery_config(path)


def test_load_delivery_config_parses_channels(tmp_path):
    config = _config(tmp_path)
    assert config is not None
    assert config.default_channel == ChannelType.SLACK
    assert config.slack.signing_secret_env == "NEYMA_SLACK_SIGNING_SECRET_ACME"
    assert config.email.to == ["controller@acme-freight.test"]
    assert config.email.outbound_enabled is False


def test_load_delivery_config_absent_returns_none(tmp_path):
    path = tmp_path / "no_delivery.yaml"
    path.write_text("client_id: bare\n", encoding="utf-8")
    assert load_delivery_config(path) is None


def test_verify_reports_missing_secrets_when_env_empty(tmp_path):
    config = _config(tmp_path)
    checks = verify_delivery_config(config, env={})
    assert not all(check.ok for check in checks)
    flat_missing = {name for check in checks for name in check.missing_secrets}
    assert "NEYMA_DELIVERY_SECRET_ACME" in flat_missing
    assert "NEYMA_SLACK_SIGNING_SECRET_ACME" in flat_missing


def test_verify_passes_when_secrets_resolve(tmp_path):
    config = _config(tmp_path)
    checks = verify_delivery_config(config, env=_FULL_ENV)
    assert all(check.ok for check in checks), [c.model_dump() for c in checks if not c.ok]


def test_build_signer_fails_closed_without_secret(tmp_path):
    config = _config(tmp_path)
    with pytest.raises(ChannelConfigError):
        build_signer(config, env={})


def test_build_channel_adapters_builds_enabled_channels(tmp_path):
    config = _config(tmp_path)
    store = WorkflowStore(tmp_path / "wf.sqlite3")
    try:
        adapters = build_channel_adapters(store, config, env=_FULL_ENV)
        assert isinstance(adapters[ChannelType.SLACK], SlackDeliveryAdapter)
        assert isinstance(adapters[ChannelType.EMAIL], EmailDeliveryAdapter)
        # The Slack adapter carries the resolved per-customer signing secret.
        assert adapters[ChannelType.SLACK].signing_secret == b"acme-slack-secret"
    finally:
        store.close()


def test_build_channel_adapters_skips_slack_without_signing_secret(tmp_path):
    config = _config(tmp_path)
    store = WorkflowStore(tmp_path / "wf.sqlite3")
    env = {"NEYMA_DELIVERY_SECRET_ACME": "acme-action-secret"}  # action secret only
    try:
        adapters = build_channel_adapters(store, config, env=env)
        assert ChannelType.SLACK not in adapters
        assert ChannelType.EMAIL in adapters  # email needs no resolvable secret here
    finally:
        store.close()


def test_slack_channel_routing_and_fallback(tmp_path):
    config = _config(tmp_path)
    assert slack_channel_for_route(config.slack, ReviewRoute.IMMEDIATE_PING) == "C0PINGS"
    assert slack_channel_for_route(config.slack, ReviewRoute.DIGEST_ONLY) == "C0DIGEST"
    # CHANNEL_POST is not in routing -> falls back to the default channel.
    assert slack_channel_for_route(config.slack, ReviewRoute.CHANNEL_POST) == "C0DEFAULT"


def test_dogfood_client_config_has_valid_delivery_block():
    root = Path(__file__).resolve().parents[2]
    config = load_delivery_config(root / "configs" / "clients" / "neyma_test_freight.yaml")
    assert config is not None
    # Structure is valid; secrets are intentionally unset in dev, so it reports as not-yet-ready.
    checks = verify_delivery_config(config, env={})
    assert any(check.missing_secrets for check in checks)
