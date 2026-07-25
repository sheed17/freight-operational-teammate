"""Dispatch human review messages through configured customer channels.

This module is the production-shaped bridge between channel-neutral review messages and real
transports. It does not decide money or workflow state. It only routes, gates, renders, and audits
delivery attempts.

Product contract: Slack is the human review surface. Email artifacts here are local/dev review
fixtures only; carrier-facing follow-up email belongs to the follow-up/send-gate path, not this
user-review dispatcher.
"""

from __future__ import annotations

import json
import re
import urllib.request
from enum import Enum
from pathlib import Path
from typing import Mapping, Protocol

from pydantic import BaseModel, Field

from .channels import (
    ChannelType,
    DeliveryConfig,
    email_sender,
    email_recipients,
    slack_channel_for_route,
)
from .delivery import DeliveryMessage, redact_delivery_message
from .email_adapter import EmailOutbox, EmailSender, build_email_message
from .slack_adapter import render_slack_message
from .tool_permissions import ToolContext, evaluate_tool_permission, record_tool_permission_decision
from .workflow import WorkflowState, WorkflowStore


class DispatchMode(str, Enum):
    """How close to real outbound delivery this dispatch should get."""

    DRY_RUN = "DRY_RUN"
    LOCAL_OUTBOX = "LOCAL_OUTBOX"
    LIVE = "LIVE"


class DispatchStatus(str, Enum):
    DRY_RUN = "DRY_RUN"
    OUTBOXED = "OUTBOXED"
    SENT = "SENT"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class DispatchAttempt(BaseModel):
    run_id: int
    channel: ChannelType
    destination: str | None
    status: DispatchStatus
    note: str
    external_id: str | None = None
    payload: dict = Field(default_factory=dict)


class SlackPostResult(BaseModel):
    ok: bool
    channel: str | None = None
    ts: str | None = None
    error: str | None = None


class SlackPoster(Protocol):
    def post_message(self, *, channel: str, payload: dict) -> SlackPostResult:
        ...


class SlackApiPoster:
    """Minimal Slack Web API poster for the future live transport path."""

    def __init__(self, bot_token: str, *, timeout_seconds: int = 10) -> None:
        self.bot_token = bot_token
        self.timeout_seconds = timeout_seconds

    def post_message(self, *, channel: str, payload: dict) -> SlackPostResult:
        body = json.dumps({"channel": channel, **payload}).encode("utf-8")
        request = urllib.request.Request(
            "https://slack.com/api/chat.postMessage",
            data=body,
            headers={
                "Authorization": f"Bearer {self.bot_token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - transport errors are recorded, not raised
            # Bound and categorize the error: it lands in an audit note (a persistence sink), so
            # never store an unbounded, transport-controlled string.
            return SlackPostResult(ok=False, error=f"{type(exc).__name__}: {str(exc)[:160]}")
        return SlackPostResult(
            ok=bool(data.get("ok")),
            channel=data.get("channel"),
            ts=data.get("ts"),
            error=data.get("error"),
        )


def latest_slack_card_target(store: WorkflowStore, run_id: int) -> tuple[str, str] | None:
    """The (channel, ts) of the most recent Slack review card SENT for this run, from the audit trail.

    This is what lets execution status post as a threaded reply under the card the human approved.
    """
    for event in reversed(store.audit_events(run_id)):
        if event.get("event_type") != "delivery_dispatch_attempted":
            continue
        payload = event.get("payload", {})
        if (
            payload.get("channel") == ChannelType.SLACK.value
            and payload.get("status") == DispatchStatus.SENT.value
            and payload.get("external_id")
            and payload.get("destination")
        ):
            return payload["destination"], payload["external_id"]
    return None


_EXECUTION_PHASE_EMOJI = {
    "ENTERING": ":hourglass_flowing_sand:",
    "ENTERED": ":inbox_tray:",
    "VERIFIED": ":white_check_mark:",
    "DONE": ":checkered_flag:",
    "FAILED": ":rotating_light:",
    "WAITING_FOR_SESSION": ":lock:",
}


def slack_thread_status_poster(
    store: WorkflowStore,
    config: DeliveryConfig,
    *,
    env: Mapping[str, str],
    poster: SlackPoster | None = None,
    actor: str = "system",
):
    """Return an ``on_status`` callback that posts each TMS execution status as a threaded reply under
    the run's Slack review card, so the human watches the payable land where they approved it.

    Best-effort and audited: a missing card target, missing token, or transport error is recorded as
    an audit event, never raised — the gated write path stays authoritative.
    """
    resolved_poster = poster
    if resolved_poster is None and config.slack is not None:
        token = env.get(config.slack.bot_token_env or "")
        resolved_poster = SlackApiPoster(token) if token else None

    def _on_status(update) -> None:
        target = latest_slack_card_target(store, update.run_id)
        if target is None or resolved_poster is None:
            store.add_audit_event(
                update.run_id,
                "execution_status_post_skipped",
                actor=actor,
                payload={"phase": update.phase.value, "reason": "no_card_target" if target is None else "no_poster"},
            )
            return
        channel, ts = target
        emoji = _EXECUTION_PHASE_EMOJI.get(update.phase.value, ":information_source:")
        result = resolved_poster.post_message(channel=channel, payload={"thread_ts": ts, "text": f"{emoji} {update.message}"})
        store.add_audit_event(
            update.run_id,
            "execution_status_posted",
            actor=actor,
            payload={"phase": update.phase.value, "ok": result.ok, "thread_ts": ts, "error": result.error},
        )

    return _on_status


def post_text_to_slack(
    text: str,
    *,
    channel: str,
    config: DeliveryConfig,
    env: Mapping[str, str],
    poster: SlackPoster | None = None,
) -> SlackPostResult:
    """Post a plain-text message (e.g. the daily digest) to a Slack channel via the live poster."""
    resolved = poster
    if resolved is None and config.slack is not None:
        token = env.get(config.slack.bot_token_env or "")
        resolved = SlackApiPoster(token) if token else None
    if resolved is None:
        return SlackPostResult(ok=False, error="no_slack_token")
    if not channel:
        return SlackPostResult(ok=False, error="no_channel")
    return resolved.post_message(channel=channel, payload={"text": text})


def dispatch_delivery_message(
    store: WorkflowStore,
    message: DeliveryMessage,
    config: DeliveryConfig,
    *,
    env: Mapping[str, str] | None = None,
    mode: DispatchMode = DispatchMode.DRY_RUN,
    slack_poster: SlackPoster | None = None,
    email_outbox_dir: str | Path | None = None,
    email_transport: EmailSender | None = None,
    actor: str = "system",
) -> list[DispatchAttempt]:
    """Route one delivery message through enabled channels and audit every attempt."""
    attempts: list[DispatchAttempt] = []
    if config.slack is not None and config.slack.enabled:
        attempts.append(
            _dispatch_slack(
                store,
                message,
                config,
                env=env or {},
                mode=mode,
                poster=slack_poster,
                actor=actor,
            )
        )
    if config.email is not None and config.email.enabled:
        attempts.extend(
            _dispatch_email(
                store,
                message,
                config,
                env=env or {},
                mode=mode,
                email_outbox_dir=email_outbox_dir,
                email_transport=email_transport,
                actor=actor,
            )
        )
    return attempts


def _dispatch_slack(
    store: WorkflowStore,
    message: DeliveryMessage,
    config: DeliveryConfig,
    *,
    env: Mapping[str, str],
    mode: DispatchMode,
    poster: SlackPoster | None,
    actor: str,
) -> DispatchAttempt:
    assert config.slack is not None
    destination = slack_channel_for_route(config.slack, message.route)
    payload = render_slack_message(message)
    safe_payload = _redact_slack_payload(payload)
    if not destination:
        return _record_attempt(
            store,
            DispatchAttempt(
                run_id=message.run_id,
                channel=ChannelType.SLACK,
                destination=None,
                status=DispatchStatus.BLOCKED,
                note="no Slack channel configured for route",
                payload=safe_payload,
            ),
            actor=actor,
        )

    if mode == DispatchMode.DRY_RUN:
        return _record_attempt(
            store,
            DispatchAttempt(
                run_id=message.run_id,
                channel=ChannelType.SLACK,
                destination=destination,
                status=DispatchStatus.DRY_RUN,
                note="dry run only; no Slack API call made",
                payload=safe_payload,
            ),
            actor=actor,
        )
    if mode == DispatchMode.LOCAL_OUTBOX:
        return _record_attempt(
            store,
            DispatchAttempt(
                run_id=message.run_id,
                channel=ChannelType.SLACK,
                destination=destination,
                status=DispatchStatus.OUTBOXED,
                note="Slack payload rendered for local review only; no Slack API call made",
                payload=safe_payload,
            ),
            actor=actor,
        )

    decision = _evaluate_outbound_tool(
        store,
        message,
        "post_slack_review",
        outbound_enabled=getattr(config.slack, "outbound_enabled", False),
        actor=actor,
    )
    if not decision.allowed:
        return _record_attempt(
            store,
            DispatchAttempt(
                run_id=message.run_id,
                channel=ChannelType.SLACK,
                destination=destination,
                status=DispatchStatus.BLOCKED,
                note=decision.reason,
                payload=safe_payload,
            ),
            actor=actor,
        )
    token = env.get(config.slack.bot_token_env or "")
    if not token:
        return _record_attempt(
            store,
            DispatchAttempt(
                run_id=message.run_id,
                channel=ChannelType.SLACK,
                destination=destination,
                status=DispatchStatus.BLOCKED,
                note="Slack bot token is not configured",
                payload=safe_payload,
            ),
            actor=actor,
        )
    poster = poster or SlackApiPoster(token)
    result = poster.post_message(channel=destination, payload=payload)
    status = DispatchStatus.SENT if result.ok else DispatchStatus.FAILED
    return _record_attempt(
        store,
        DispatchAttempt(
            run_id=message.run_id,
            channel=ChannelType.SLACK,
            destination=destination,
            status=status,
            note="sent via Slack API" if result.ok else f"Slack API failed: {result.error}",
            external_id=result.ts,
            payload=safe_payload,
        ),
        actor=actor,
    )


def _dispatch_email(
    store: WorkflowStore,
    message: DeliveryMessage,
    config: DeliveryConfig,
    *,
    env: Mapping[str, str],
    mode: DispatchMode,
    email_outbox_dir: str | Path | None,
    email_transport: EmailSender | None,
    actor: str,
) -> list[DispatchAttempt]:
    assert config.email is not None
    attempts: list[DispatchAttempt] = []
    recipients = email_recipients(config.email)
    if not recipients:
        return [
            _record_attempt(
                store,
                DispatchAttempt(
                    run_id=message.run_id,
                    channel=ChannelType.EMAIL,
                    destination=None,
                    status=DispatchStatus.BLOCKED,
                    note="no email recipients configured",
                    payload=_redacted_message_payload(message),
                ),
                actor=actor,
            )
        ]

    for recipient in recipients:
        email = build_email_message(
            message,
            to=recipient,
            action_base_url=config.email.action_base_url,
            sender=email_sender(config.email, env),
        )
        safe_payload = {
            "subject": email.subject,
            "to": email.to,
            "sender": email.sender,
            "actions": [
                {"label": action.label, "decision": action.decision, "url": _redact_url(action.url)}
                for action in email.actions
            ],
        }
        if mode == DispatchMode.DRY_RUN:
            attempts.append(
                _record_attempt(
                    store,
                    DispatchAttempt(
                        run_id=message.run_id,
                        channel=ChannelType.EMAIL,
                        destination=recipient,
                        status=DispatchStatus.DRY_RUN,
                        note="dry run only; no email written or sent",
                        payload=safe_payload,
                    ),
                    actor=actor,
                )
            )
            continue
        if mode == DispatchMode.LOCAL_OUTBOX:
            outbox_dir = email_outbox_dir or config.email.outbox_dir or "data/active_workspace/email_outbox"
            record = EmailOutbox(outbox_dir, outbound_enabled=config.email.outbound_enabled).deliver(email)
            attempts.append(
                _record_attempt(
                    store,
                    DispatchAttempt(
                        run_id=message.run_id,
                        channel=ChannelType.EMAIL,
                        destination=recipient,
                        status=DispatchStatus.OUTBOXED,
                        note=record.note,
                        external_id=record.path,
                        payload=safe_payload,
                    ),
                    actor=actor,
                )
            )
            continue

        # LIVE review email is intentionally blocked. Slack is the human UI; email is inbound
        # intake plus carrier-facing follow-up. Keep the local outbox path for deterministic tests
        # and legacy artifacts, but never send user review cards over SMTP from this dispatcher.
        decision = _evaluate_outbound_tool(
            store,
            message,
            "send_review_email",
            outbound_enabled=config.email.outbound_enabled,
            actor=actor,
        )
        note = (
            "review email live send disabled by product contract; use Slack for human review"
            if decision.allowed
            else decision.reason
        )
        attempts.append(_email_attempt(store, message, recipient, DispatchStatus.BLOCKED, note, safe_payload, actor))
    return attempts


def _email_attempt(store, message, recipient, status, note, payload, actor) -> DispatchAttempt:
    return _record_attempt(
        store,
        DispatchAttempt(
            run_id=message.run_id,
            channel=ChannelType.EMAIL,
            destination=recipient,
            status=status,
            note=note,
            payload=payload,
        ),
        actor=actor,
    )


def _evaluate_outbound_tool(
    store: WorkflowStore,
    message: DeliveryMessage,
    tool_name: str,
    *,
    outbound_enabled: bool,
    actor: str,
):
    run = store.get_run(message.run_id)
    if run is None:
        context = ToolContext(workflow_state=WorkflowState.NEEDS_REVIEW, actor=actor)
    else:
        context = ToolContext(
            workflow_state=run.state,
            actor=actor,
            outbound_enabled=outbound_enabled,
        )
    decision = evaluate_tool_permission(tool_name, context)
    record_tool_permission_decision(store, message.run_id, decision=decision, context=context)
    return decision


def _record_attempt(store: WorkflowStore, attempt: DispatchAttempt, *, actor: str) -> DispatchAttempt:
    store.add_audit_event(
        attempt.run_id,
        "delivery_dispatch_attempted",
        actor=actor,
        payload=attempt.model_dump(mode="json"),
    )
    return attempt


def _redacted_message_payload(message: DeliveryMessage) -> dict:
    return redact_delivery_message(message).model_dump(mode="json")


# A Neyma action token is base64url(body) ("=" padding allowed) + "." + hex(hmac-sha256).
_TOKEN_SHAPE = re.compile(r"^[A-Za-z0-9_\-=]+\.[0-9a-f]{64}$")


def _redact_slack_payload(payload: dict) -> dict:
    """Redact action-button tokens before the payload reaches an audit/artifact sink.

    Belt: unconditionally redact every actions-block element ``value`` (where the current render
    places tokens). Suspenders: a value-based pass also redacts any token-shaped ``value`` elsewhere,
    so a future render that places a token outside an actions block is still covered.
    """
    safe = json.loads(json.dumps(payload))
    for block in safe.get("blocks", []):
        if block.get("type") == "actions":
            for element in block.get("elements", []):
                if element.get("value"):
                    element["value"] = "redacted"
    _redact_tokens_in_place(safe)
    return safe


def _redact_tokens_in_place(node: object) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "value" and isinstance(value, str) and _TOKEN_SHAPE.match(value):
                node[key] = "redacted"
            else:
                _redact_tokens_in_place(value)
    elif isinstance(node, list):
        for item in node:
            _redact_tokens_in_place(item)


def _redact_url(url: str) -> str:
    if "token=" not in url:
        return url
    prefix, _, _ = url.partition("token=")
    return f"{prefix}token=redacted"
