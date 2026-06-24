"""Tests for configured Slack delivery dispatch and local email artifacts."""

import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from generate_realistic_corpus import generate  # noqa: E402
from freight_recon.channels import DeliveryConfig  # noqa: E402
from freight_recon.delivery import DeliverySigner, build_delivery_message, record_delivery_message  # noqa: E402
from freight_recon.delivery_dispatch import (  # noqa: E402
    DispatchMode,
    DispatchStatus,
    SlackPostResult,
    dispatch_delivery_message,
)
from freight_recon.reconciliation import FreightLoadForReconciliation  # noqa: E402
from freight_recon.review import build_review_payload, record_review_payload  # noqa: E402
from freight_recon.workflow import WorkflowStore, process_load_packet  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


class FakeSlackPoster:
    def __init__(self) -> None:
        self.calls = []

    def post_message(self, *, channel: str, payload: dict) -> SlackPostResult:
        self.calls.append({"channel": channel, "payload": payload})
        return SlackPostResult(ok=True, channel=channel, ts="1718500000.000100")


def _config(
    *,
    slack_outbound=False,
    email_outbound=False,
    recipients=None,
    sender="neyma@test.example",
    from_env=None,
) -> DeliveryConfig:
    email_block = {
        "enabled": True,
        "to": recipients or ["controller@test.example"],
        "action_base_url": "https://neyma.test/email/action",
        "outbound_enabled": email_outbound,
    }
    if sender is not None:
        email_block["sender"] = sender
    if from_env is not None:
        email_block["from_env"] = from_env
    return DeliveryConfig.model_validate(
        {
            "default_channel": "slack",
            "action_token_secret_env": "NEYMA_DELIVERY_SECRET_TEST",
            "slack": {
                "enabled": True,
                "outbound_enabled": slack_outbound,
                "signing_secret_env": "NEYMA_SLACK_SIGNING_SECRET_TEST",
                "bot_token_env": "NEYMA_SLACK_BOT_TOKEN_TEST",
                "default_channel_id": "C0REVIEW",
                "routing": {"IMMEDIATE_PING": "C0PINGS", "CHANNEL_POST": "C0REVIEW"},
            },
            "email": email_block,
        }
    )


def _message(tmp_path):
    corpus = tmp_path / "corpus"
    generate(corpus, 8, seed=42)
    raw = json.loads((corpus / "ground_truth" / "loads_and_scenarios.json").read_text())
    loads = [FreightLoadForReconciliation.from_mapping(item) for item in raw.values()]
    load = next(item for item in loads if item.load_id == "LD-560003")
    store = WorkflowStore(tmp_path / "workflow.sqlite3")
    run = process_load_packet(
        store,
        load,
        primary_document_path=corpus / load.documents["carrier_invoice"],
        seen_invoice_keys=set(),
    )
    payload = build_review_payload(run, load, age_hours=48)
    assert payload is not None
    record_review_payload(store, payload)
    message = build_delivery_message(payload, DeliverySigner(b"dispatch-secret"), actor="Rasheed")
    record_delivery_message(store, message)
    return store, message


def test_dispatch_dry_run_routes_and_redacts_tokens(tmp_path):
    store, message = _message(tmp_path)
    try:
        attempts = dispatch_delivery_message(store, message, _config(), mode=DispatchMode.DRY_RUN)

        assert [attempt.channel.value for attempt in attempts] == ["slack", "email"]
        assert all(attempt.status == DispatchStatus.DRY_RUN for attempt in attempts)
        audit = [e for e in store.audit_events(message.run_id) if e["event_type"] == "delivery_dispatch_attempted"]
        assert len(audit) == 2
        serialized = json.dumps([event["payload"] for event in audit])
        assert message.actions[0].signed_token not in serialized
        assert "token=redacted" in serialized
        assert '"value": "redacted"' in serialized
    finally:
        store.close()


def test_live_slack_blocks_when_outbound_disabled(tmp_path):
    store, message = _message(tmp_path)
    poster = FakeSlackPoster()
    try:
        attempts = dispatch_delivery_message(
            store,
            message,
            _config(slack_outbound=False),
            env={"NEYMA_SLACK_BOT_TOKEN_TEST": "xoxb-test"},
            mode=DispatchMode.LIVE,
            slack_poster=poster,
        )
        slack = next(attempt for attempt in attempts if attempt.channel.value == "slack")
        assert slack.status == DispatchStatus.BLOCKED
        assert slack.note == "outbound messages are disabled"
        assert poster.calls == []
    finally:
        store.close()


def test_live_slack_posts_when_gated_and_configured(tmp_path):
    store, message = _message(tmp_path)
    poster = FakeSlackPoster()
    try:
        attempts = dispatch_delivery_message(
            store,
            message,
            _config(slack_outbound=True),
            env={"NEYMA_SLACK_BOT_TOKEN_TEST": "xoxb-test"},
            mode=DispatchMode.LIVE,
            slack_poster=poster,
        )
        slack = next(attempt for attempt in attempts if attempt.channel.value == "slack")
        assert slack.status == DispatchStatus.SENT
        assert slack.external_id == "1718500000.000100"
        assert poster.calls[0]["channel"] == "C0PINGS"
        # The real outbound payload must keep tokens for clickable Slack buttons.
        assert poster.calls[0]["payload"]["blocks"][-2]["elements"][0]["value"] == message.actions[0].signed_token
    finally:
        store.close()


def test_local_email_outbox_writes_explicit_artifact(tmp_path):
    store, message = _message(tmp_path)
    outbox = tmp_path / "outbox"
    try:
        attempts = dispatch_delivery_message(
            store,
            message,
            _config(),
            mode=DispatchMode.LOCAL_OUTBOX,
            email_outbox_dir=outbox,
        )
        email = next(attempt for attempt in attempts if attempt.channel.value == "email")
        assert email.status == DispatchStatus.OUTBOXED
        assert Path(email.external_id).exists()
        eml = Path(email.external_id).read_text(encoding="utf-8")
        assert "https://neyma.test/email/action" in eml
        assert "token" in eml
    finally:
        store.close()


def test_email_dispatch_uses_from_env_sender(tmp_path):
    store, message = _message(tmp_path)
    try:
        attempts = dispatch_delivery_message(
            store,
            message,
            _config(sender=None, from_env="NEYMA_FROM_ADDRESS"),
            env={"NEYMA_FROM_ADDRESS": "ops@customer.example"},
            mode=DispatchMode.DRY_RUN,
        )
        email = next(attempt for attempt in attempts if attempt.channel.value == "email")
        assert email.payload["sender"] == "ops@customer.example"
    finally:
        store.close()


def test_local_email_outbox_writes_one_artifact_per_recipient(tmp_path):
    store, message = _message(tmp_path)
    outbox = tmp_path / "outbox"
    recipients = ["ap@test.example", "controller@test.example"]
    try:
        attempts = dispatch_delivery_message(
            store,
            message,
            _config(recipients=recipients),
            mode=DispatchMode.LOCAL_OUTBOX,
            email_outbox_dir=outbox,
        )
        email_attempts = [attempt for attempt in attempts if attempt.channel.value == "email"]
        paths = [Path(attempt.external_id) for attempt in email_attempts]
        assert len(paths) == 2
        assert len(set(paths)) == 2
        assert all(path.exists() for path in paths)
    finally:
        store.close()


def test_dispatch_cli_requires_secret_or_explicit_local_flag():
    blocked = subprocess.run(
        [
            str(ROOT / ".venv" / "bin" / "python"),
            str(ROOT / "scripts" / "dispatch_review.py"),
            "--mode",
            "DRY_RUN",
            "--out",
            str(ROOT / "data" / "active_workspace" / "test_should_not_write_dispatch.json"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert blocked.returncode != 0
    assert "Missing action-token secret" in blocked.stderr
    assert "--allow-local-dev-secret" in blocked.stderr


def test_live_review_email_blocked_even_when_gated(tmp_path):
    store, message = _message(tmp_path)
    try:
        attempts = dispatch_delivery_message(
            store, message, _config(email_outbound=True),
            mode=DispatchMode.LIVE, env={},
        )
        email = [a for a in attempts if a.channel.value == "email"]
        assert email and email[0].status == DispatchStatus.BLOCKED
        assert "use Slack for human review" in email[0].note
    finally:
        store.close()
