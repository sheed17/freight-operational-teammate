"""Slack transport for the channel-neutral delivery adapter.

This layer renders a :class:`~freight_recon.delivery.DeliveryMessage` into Slack Block Kit and
accepts Slack interactive button clicks back into the signed action intake. It is a thin
transport: all business logic stays in ``delivery.submit_signed_action`` and the workflow state
machine. Two independent HMAC layers protect the round trip:

1. Slack request signing (``X-Slack-Signature`` / ``v0=...``) proves the callback really came from
   Slack and is not replayed (timestamp freshness).
2. The Neyma action token (carried in each button's ``value``) proves the action is authentic,
   unexpired, single-use, and bound to a specific run/decision/amount.

No Slack credentials are stored here. The signing secret comes from the environment, and posting to
a real workspace stays behind an explicit transport that this module does not exercise in tests.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from urllib.parse import parse_qs

from pydantic import BaseModel

from .delivery import (
    DeliveryActionOutcome,
    DeliveryMessage,
    DeliverySigner,
    submit_signed_action,
)
from .reconciliation import FreightLoadForReconciliation
from .review import ReviewSeverity
from .workflow import WorkflowStore

# Slack signs the literal string ``v0:{timestamp}:{body}`` with the app signing secret.
_SLACK_SIGNATURE_VERSION = "v0"
_SLACK_MAX_SKEW_SECONDS = 60 * 5

_SEVERITY_EMOJI = {
    ReviewSeverity.CRITICAL: ":red_circle:",
    ReviewSeverity.WARNING: ":large_yellow_circle:",
    ReviewSeverity.INFO: ":large_blue_circle:",
}


class SlackError(RuntimeError):
    """Base error for the Slack transport."""


class SlackSignatureError(SlackError):
    """Raised when a Slack request signature is missing, stale, or invalid."""


class SlackInteraction(BaseModel):
    """The parsed, verified pieces of a Slack interactive button click."""

    token: str
    action_id: str
    slack_user: str | None = None
    response_url: str | None = None


def render_slack_message(message: DeliveryMessage) -> dict:
    """Render a delivery message into a Slack ``chat.postMessage``-shaped payload.

    Each action button carries its signed Neyma token in ``value`` so the interaction callback can
    feed it straight back into the signed action intake.
    """
    emoji = _SEVERITY_EMOJI.get(message.severity, "")
    header_text = f"{emoji} {message.title}".strip()
    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": _truncate(header_text, 150)}},
        {
            "type": "section",
            "fields": [
                _md_field("Load", message.load_id),
                _md_field("Carrier", message.carrier),
                _md_field("Invoice", message.invoice_number),
                _md_field("Flagged", f"${message.found_money.flagged_amount}"),
            ],
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        f"*Severity:* {message.severity.value}  ·  "
                        f"*Route:* {message.route.value}"
                        + ("  ·  :rotating_light: ping" if message.ping else "")
                        + (f"  ·  *Aging:* {message.aging.age_hours}h" if message.aging.age_hours else "")
                    ),
                }
            ],
        },
        {"type": "section", "text": {"type": "mrkdwn", "text": _truncate(message.summary, 3000)}},
    ]

    if message.evidence_links:
        evidence = " · ".join(f"<{link.url}|{link.label}>" for link in message.evidence_links[:8])
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Evidence:* {evidence}"}})
    blocks.append(
        {"type": "section", "text": {"type": "mrkdwn", "text": f"<{message.packet_detail_url}|Open packet detail>"}}
    )

    if message.actions:
        # Slack allows at most 5 elements per actions block.
        blocks.append(
            {
                "type": "actions",
                "block_id": f"neyma_review_{message.run_id}",
                "elements": [
                    _slack_button(button, index)
                    for index, button in enumerate(message.actions[:5])
                ],
            }
        )

    blocks.append(
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f":memo: {message.status_banner}"}],
        }
    )
    return {"text": message.title, "blocks": blocks}


def verify_slack_signature(
    signing_secret: bytes | str,
    *,
    timestamp: str,
    body: str,
    signature: str,
    now: float | None = None,
) -> None:
    """Verify a Slack request signature, raising :class:`SlackSignatureError` on any problem.

    Implements Slack's documented scheme: HMAC-SHA256 over ``v0:{timestamp}:{body}`` compared in
    constant time against the ``X-Slack-Signature`` header, plus a 5-minute replay window.
    """
    secret = signing_secret.encode("utf-8") if isinstance(signing_secret, str) else signing_secret
    if not timestamp or not signature:
        raise SlackSignatureError("missing Slack signature headers")
    try:
        ts = int(timestamp)
    except ValueError as exc:
        raise SlackSignatureError("invalid Slack timestamp") from exc
    current = time.time() if now is None else now
    if abs(current - ts) > _SLACK_MAX_SKEW_SECONDS:
        raise SlackSignatureError("Slack request timestamp outside the allowed window")

    basestring = f"{_SLACK_SIGNATURE_VERSION}:{timestamp}:{body}".encode("utf-8")
    expected = f"{_SLACK_SIGNATURE_VERSION}=" + hmac.new(secret, basestring, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise SlackSignatureError("Slack signature mismatch")


def parse_slack_interaction(body: str) -> SlackInteraction:
    """Parse a Slack interactive-message callback body into the token and metadata.

    Slack posts ``application/x-www-form-urlencoded`` with a single ``payload`` field holding JSON.
    Call :func:`verify_slack_signature` on the raw ``body`` before trusting this.
    """
    fields = parse_qs(body)
    raw = fields.get("payload")
    if not raw:
        raise SlackError("Slack interaction payload missing")
    try:
        data = json.loads(raw[0])
    except json.JSONDecodeError as exc:
        raise SlackError("Slack interaction payload is not valid JSON") from exc
    actions = data.get("actions") or []
    if not actions or not actions[0].get("value"):
        raise SlackError("Slack interaction has no actionable button value")
    return SlackInteraction(
        token=actions[0]["value"],
        action_id=actions[0].get("action_id", ""),
        slack_user=(data.get("user") or {}).get("username") or (data.get("user") or {}).get("id"),
        response_url=data.get("response_url"),
    )


class SlackDeliveryAdapter:
    """Bind Slack's transport to the signed action intake without leaking Slack into the core."""

    def __init__(
        self,
        store: WorkflowStore,
        *,
        signer: DeliverySigner | None = None,
        signing_secret: bytes | str | None = None,
    ) -> None:
        self.store = store
        self.signer = signer or DeliverySigner.from_env()
        secret = signing_secret if signing_secret is not None else os.environ.get("NEYMA_SLACK_SIGNING_SECRET", "")
        if not secret:
            raise SlackError("Slack signing secret is required")
        self.signing_secret = secret.encode("utf-8") if isinstance(secret, str) else secret

    def render(self, message: DeliveryMessage) -> dict:
        return render_slack_message(message)

    def handle_interaction(
        self,
        *,
        body: str,
        timestamp: str,
        signature: str,
        follow_up_loads: dict[str, FreightLoadForReconciliation] | None = None,
        now: float | None = None,
    ) -> tuple[DeliveryActionOutcome, dict]:
        """Verify a Slack button click and apply the carried signed action.

        Returns the :class:`DeliveryActionOutcome` and a Slack ``chat.update``-shaped payload that
        re-renders the (now mutated) message. Raises :class:`SlackSignatureError` for bad Slack
        signatures and propagates delivery/workflow errors from the signed action intake.
        """
        verify_slack_signature(
            self.signing_secret,
            timestamp=timestamp,
            body=body,
            signature=signature,
            now=now,
        )
        interaction = parse_slack_interaction(body)
        # Record who clicked in Slack for traceability. Only attempt this once the action token's
        # own signature checks out, so a forged button value falls through to the delivery layer's
        # canonical (sentinel-run) rejection audit rather than crashing here.
        if interaction.slack_user:
            try:
                run_id = self.signer.parse_signed(interaction.token).run_id
            except Exception:  # noqa: BLE001 - delivery layer re-validates and audits the rejection
                run_id = None
            if run_id is not None:
                self.store.add_audit_event(
                    run_id,
                    "slack_interaction_received",
                    actor=interaction.slack_user,
                    payload={"action_id": interaction.action_id},
                )
        outcome = submit_signed_action(
            self.store,
            interaction.token,
            signer=self.signer,
            follow_up_loads=follow_up_loads,
        )
        return outcome, {"replace_original": True, **render_slack_message(outcome.message)}


def _slack_button(button, index: int) -> dict:
    element = {
        "type": "button",
        "action_id": f"{button.decision.value.lower()}_{index}",
        "text": {"type": "plain_text", "text": _truncate(button.label, 75)},
        "value": button.signed_token,
    }
    # Slack only accepts "primary" or "danger"; a plain button must omit "style" entirely.
    if button.requires_send_gate:
        element["style"] = "primary"
    return element


def _md_field(label: str, value: str) -> dict:
    return {"type": "mrkdwn", "text": f"*{label}*\n{value}"}


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"
