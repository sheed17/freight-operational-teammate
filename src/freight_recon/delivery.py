"""Channel-neutral delivery adapter with signed action intake.

This module renders typed :class:`~freight_recon.review.ReviewPayload` cards into
channel-neutral deliverable messages (Slack now; other headless UIs later) and accepts human actions
back through signed, expiring, single-use action tokens.

Design rules for this slice:

- It stays channel-neutral. Slack/Teams transports should only render
  :class:`DeliveryMessage` and post back :class:`SignedActionToken` strings. The workflow core
  must not learn about channel-specific blocks/buttons.
- Action intake never mutates workflow state directly. It verifies the signature, then calls the
  existing :func:`~freight_recon.review_actions.apply_review_action`, which enforces the workflow
  state machine. An action can never bypass workflow state.
- Every consequential step audits: message delivered, action received, action applied, action
  rejected, duplicate ignored.
- No autonomous send. Follow-up drafts created on action stay behind the existing send gate.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field

from .follow_up import build_follow_up_draft, record_follow_up_draft
from .reconciliation import FreightLoadForReconciliation
from .review import (
    AgingMetadata,
    EvidenceLink,
    FoundMoney,
    ReviewAction,
    ReviewActionOption,
    ReviewPayload,
    ReviewRoute,
    ReviewSeverity,
)
from .review_actions import (
    ReviewActionRequest,
    ReviewDecision,
    apply_review_action,
)
from .workflow import WorkflowError, WorkflowRun, WorkflowState, WorkflowStore
from .workflow_direction import WorkflowDirection

# Local dogfood signing secret. This is NOT a production secret and NOT a customer credential;
# the token only carries a run id, decision, and amount. Real channels must inject a per-deployment
# secret via ``NEYMA_DELIVERY_SECRET``. We never store customer TMS passwords here.
_LOCAL_DEV_SECRET = b"neyma-local-dogfood-delivery-secret-v0"

DEFAULT_TOKEN_TTL_SECONDS = 3600

class DeliveryError(RuntimeError):
    """Base error for the delivery adapter."""


class DeliverySignatureError(DeliveryError):
    """Raised when an action token signature is missing, malformed, or tampered."""


class DeliveryExpiredError(DeliveryError):
    """Raised when an action token is past its expiry."""


class DeliverySecretError(DeliveryError):
    """Raised when no production action-token secret is configured."""


class DeliveryChannel(str, Enum):
    LOCAL = "LOCAL"
    SLACK = "SLACK"
    TEAMS = "TEAMS"
    EMAIL = "EMAIL"


class DeliveryActionStatus(str, Enum):
    APPLIED = "APPLIED"
    DUPLICATE_IGNORED = "DUPLICATE_IGNORED"


class SignedAction(BaseModel):
    """Verified claims carried by an action token."""

    run_id: int
    decision: ReviewDecision
    actor: str = "Rasheed"
    amount: Decimal | None = None
    note: str | None = None
    action_id: str
    issued_at: float
    expires_at: float


class DeliveryActionButton(BaseModel):
    """A channel-neutral button: a human-readable label plus a signed, single-use token."""

    code: ReviewAction
    decision: ReviewDecision
    label: str
    amount: str | None = None
    amount_kind: str | None = None
    requires_send_gate: bool = False
    creates_follow_up_draft: bool = False
    consequence: str
    signed_token: str = ""


class DeliveryMessage(BaseModel):
    """A channel-neutral review message ready to render into Slack/Teams/CLI."""

    run_id: int
    workflow_direction: WorkflowDirection = WorkflowDirection.CARRIER_PAYABLE
    channel: DeliveryChannel = DeliveryChannel.LOCAL
    load_id: str
    carrier: str
    invoice_number: str
    title: str
    severity: ReviewSeverity
    route: ReviewRoute
    ping: bool = False
    summary: str
    reasons: list[str] = Field(default_factory=list)
    evidence_links: list[EvidenceLink] = Field(default_factory=list)
    packet_detail_url: str
    aging: AgingMetadata = Field(default_factory=AgingMetadata)
    found_money: FoundMoney = Field(default_factory=FoundMoney)
    actions: list[DeliveryActionButton] = Field(default_factory=list)
    status_banner: str = "Awaiting review"
    history: list[str] = Field(default_factory=list)


class DeliveryActionOutcome(BaseModel):
    """Result of submitting one signed action token."""

    run_id: int
    action_id: str
    status: DeliveryActionStatus
    decision: ReviewDecision
    from_state: WorkflowState
    to_state: WorkflowState
    actor: str
    mutation_text: str
    follow_up_created: bool = False
    message: DeliveryMessage


class DeliverySigner:
    """Issues and verifies HMAC-signed, expiring, single-use action tokens."""

    def __init__(self, secret: bytes | str, *, default_ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS) -> None:
        self.secret = secret.encode("utf-8") if isinstance(secret, str) else secret
        self.default_ttl_seconds = default_ttl_seconds

    @classmethod
    def from_env(
        cls,
        *,
        default_ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS,
        allow_local_dev: bool = False,
    ) -> "DeliverySigner":
        secret = os.environ.get("NEYMA_DELIVERY_SECRET")
        if secret:
            return cls(secret.encode("utf-8"), default_ttl_seconds=default_ttl_seconds)
        if allow_local_dev or os.environ.get("NEYMA_ALLOW_LOCAL_DELIVERY_SECRET") == "1":
            return cls(_LOCAL_DEV_SECRET, default_ttl_seconds=default_ttl_seconds)
        raise DeliverySecretError(
            "NEYMA_DELIVERY_SECRET is not set; pass allow_local_dev=True only for local dogfood"
        )

    def issue(
        self,
        run_id: int,
        decision: ReviewDecision,
        *,
        actor: str = "Rasheed",
        amount: str | Decimal | None = None,
        note: str | None = None,
        action_id: str | None = None,
        issued_at: datetime | None = None,
        ttl_seconds: int | None = None,
    ) -> str:
        issued = issued_at or datetime.now(timezone.utc)
        ttl = self.default_ttl_seconds if ttl_seconds is None else ttl_seconds
        claims = {
            "run_id": run_id,
            "decision": ReviewDecision(decision).value,
            "actor": actor,
            "amount": _amount_str(amount),
            "note": note,
            "action_id": action_id or uuid.uuid4().hex,
            "issued_at": issued.timestamp(),
            "expires_at": issued.timestamp() + ttl,
        }
        return self._encode(claims)

    def parse_signed(self, token: str) -> SignedAction:
        """Verify the signature and return the claims without checking expiry.

        Raises :class:`DeliverySignatureError` for missing/malformed/tampered tokens. A successful
        return means the claims are signed by this secret and can be trusted (e.g. for attributing
        an audit event to the claimed run id).
        """
        return SignedAction.model_validate(self._decode(token))

    def verify(self, token: str, *, now: datetime | None = None) -> SignedAction:
        action = self.parse_signed(token)
        current = (now or datetime.now(timezone.utc)).timestamp()
        if current > action.expires_at:
            raise DeliveryExpiredError(
                f"action token expired at {action.expires_at} (now {current})"
            )
        return action

    def _encode(self, claims: dict) -> str:
        body = base64.urlsafe_b64encode(
            json.dumps(claims, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        signature = self._sign(body)
        return f"{body.decode('ascii')}.{signature}"

    def _decode(self, token: str) -> dict:
        if not token or token.count(".") != 1:
            raise DeliverySignatureError("malformed action token")
        body_part, signature = token.split(".", 1)
        body = body_part.encode("ascii")
        expected = self._sign(body)
        if not hmac.compare_digest(expected, signature):
            raise DeliverySignatureError("action token signature mismatch")
        try:
            return json.loads(base64.urlsafe_b64decode(body).decode("utf-8"))
        except (ValueError, json.JSONDecodeError) as exc:  # pragma: no cover - defensive
            raise DeliverySignatureError("action token payload is not valid JSON") from exc

    def _sign(self, body: bytes) -> str:
        return hmac.new(self.secret, body, hashlib.sha256).hexdigest()


def build_delivery_message(
    payload: ReviewPayload,
    signer: DeliverySigner | None = None,
    *,
    channel: DeliveryChannel = DeliveryChannel.LOCAL,
    actor: str = "Rasheed",
    issued_at: datetime | None = None,
    ttl_seconds: int | None = None,
) -> DeliveryMessage:
    """Render a review payload into a channel-neutral message with signed action buttons.

    When ``signer`` is omitted the buttons carry no token (useful for rebuilding a message to
    mutate after the action round-trip, where the tokens are already spent).
    """
    buttons = [
        _button_for_option(payload.run_id, option, signer, actor=actor, issued_at=issued_at, ttl_seconds=ttl_seconds)
        for option in payload.action_options
    ]
    return DeliveryMessage(
        run_id=payload.run_id,
        workflow_direction=payload.workflow_direction,
        channel=channel,
        load_id=payload.load_id,
        carrier=payload.carrier,
        invoice_number=payload.invoice_number,
        title=payload.title,
        severity=payload.severity,
        route=payload.routing.route,
        ping=payload.routing.ping,
        summary=payload.summary,
        reasons=list(payload.reasons),
        evidence_links=list(payload.evidence_links),
        packet_detail_url=payload.packet_detail_url,
        aging=payload.aging,
        found_money=payload.found_money,
        actions=buttons,
    )


def record_delivery_message(store: WorkflowStore, message: DeliveryMessage) -> None:
    """Audit that a delivery message was created for a human-facing channel (idempotent)."""
    message_key = _message_key(message)
    for event in store.audit_events(message.run_id):
        if (
            event["event_type"] == "delivery_message_created"
            and event["payload"].get("message_key") == message_key
        ):
            return
    data = {"message_key": message_key, "message": redact_delivery_message(message).model_dump(mode="json")}
    store.add_audit_event(
        message.run_id,
        "delivery_message_created",
        actor="system",
        payload=data,
    )


def render_delivery_message(message: DeliveryMessage) -> str:
    """Render a compact plain-text view for CLI/local artifacts."""
    lines = [
        message.title,
        f"State: {message.status_banner}",
        f"Workflow: {message.workflow_direction.value}",
        f"Load: {message.load_id}",
        f"Carrier: {message.carrier}",
        f"Invoice: {message.invoice_number}",
        f"Severity: {message.severity.value}",
        f"Route: {message.route.value}{' (ping)' if message.ping else ''}",
        f"Flagged: ${message.found_money.flagged_amount}",
        f"Packet: {message.packet_detail_url}",
        "",
        message.summary,
    ]
    if message.aging.age_hours:
        overdue = " overdue" if message.aging.is_overdue else ""
        lines.append(f"Aging: {message.aging.age_hours}h{overdue}")
    if message.evidence_links:
        lines.append("")
        lines.append("Evidence:")
        lines.extend(f"- {link.label}: {link.url}" for link in message.evidence_links)
    if message.actions:
        lines.append("")
        lines.append("Actions:")
        lines.extend(f"- {button.label}" for button in message.actions)
    if message.history:
        lines.append("")
        lines.append("History:")
        lines.extend(f"- {entry}" for entry in message.history)
    return "\n".join(lines)


def submit_signed_action(
    store: WorkflowStore,
    token: str,
    *,
    signer: DeliverySigner,
    follow_up_loads: dict[str, FreightLoadForReconciliation] | None = None,
    now: datetime | None = None,
) -> DeliveryActionOutcome:
    """Verify and apply one signed action token from a delivery channel.

    Raises :class:`DeliverySignatureError` for tampered/malformed tokens,
    :class:`DeliveryExpiredError` for expired tokens, and propagates
    :class:`~freight_recon.workflow.WorkflowError` when the action is not valid for the run's
    current workflow state. Duplicate submissions of an already-applied ``action_id`` are
    idempotent. Every rejection (bad signature, expiry, wrong state) is audited.
    """
    now = now or datetime.now(timezone.utc)

    # 1) Signature first: a bad/tampered signature means the claims (including run_id) are
    #    untrusted, so the rejection is recorded against the system sentinel with only a fingerprint.
    try:
        action = signer.parse_signed(token)
    except DeliverySignatureError as exc:
        store.add_security_event(
            "delivery_action_rejected",
            actor="system",
            payload={
                "failure": "signature",
                "reason": str(exc),
                "token_fingerprint": _token_fingerprint(token),
            },
        )
        raise

    # 2) Expiry: the signature is valid, so the claimed run id is trusted enough to attribute.
    if now.timestamp() > action.expires_at:
        store.add_audit_event(
            action.run_id,
            "delivery_action_rejected",
            actor=action.actor,
            payload={
                "action_id": action.action_id,
                "decision": action.decision.value,
                "failure": "expired",
                "expires_at": action.expires_at,
            },
        )
        raise DeliveryExpiredError(
            f"action token expired at {action.expires_at} (now {now.timestamp()})"
        )

    prior = _prior_application(store, action.run_id, action.action_id)
    if prior is not None:
        return _duplicate_outcome(store, action, prior, now=now)

    store.add_audit_event(
        action.run_id,
        "delivery_action_received",
        actor=action.actor,
        payload={
            "action_id": action.action_id,
            "decision": action.decision.value,
            "amount": _amount_str(action.amount),
        },
    )

    request = ReviewActionRequest(
        run_id=action.run_id,
        decision=action.decision,
        actor=action.actor,
        amount=action.amount,
        note=action.note,
    )
    try:
        result = apply_review_action(store, request)
    except WorkflowError as exc:
        store.add_audit_event(
            action.run_id,
            "delivery_action_rejected",
            actor=action.actor,
            payload={
                "action_id": action.action_id,
                "decision": action.decision.value,
                "failure": "workflow_state",
                "reason": str(exc),
            },
        )
        raise

    follow_up_created = _maybe_create_follow_up(store, action, result, follow_up_loads)

    base_message = _current_message(store, action.run_id)
    mutated = _mutate_message(base_message, result.mutation_text, now=now)

    store.add_audit_event(
        action.run_id,
        "delivery_action_applied",
        actor=action.actor,
        payload={
            "action_id": action.action_id,
            "decision": action.decision.value,
            "from_state": result.from_state.value,
            "to_state": result.to_state.value,
            "mutation_text": result.mutation_text,
            "follow_up_created": follow_up_created,
            "message": redact_delivery_message(mutated).model_dump(mode="json"),
        },
    )

    return DeliveryActionOutcome(
        run_id=action.run_id,
        action_id=action.action_id,
        status=DeliveryActionStatus.APPLIED,
        decision=action.decision,
        from_state=result.from_state,
        to_state=result.to_state,
        actor=action.actor,
        mutation_text=result.mutation_text,
        follow_up_created=follow_up_created,
        message=mutated,
    )


def _button_for_option(
    run_id: int,
    option: ReviewActionOption,
    signer: DeliverySigner | None,
    *,
    actor: str,
    issued_at: datetime | None,
    ttl_seconds: int | None,
) -> DeliveryActionButton:
    decision = _decision_for_option(option)
    token = ""
    if signer is not None:
        token = signer.issue(
            run_id,
            decision,
            actor=actor,
            amount=option.amount,
            issued_at=issued_at,
            ttl_seconds=ttl_seconds,
        )
    return DeliveryActionButton(
        code=option.code,
        decision=decision,
        label=option.label,
        amount=option.amount,
        amount_kind=option.amount_kind,
        requires_send_gate=option.requires_send_gate,
        creates_follow_up_draft=option.creates_follow_up_draft,
        consequence=option.consequence,
        signed_token=token,
    )


def redact_delivery_message(message: DeliveryMessage) -> DeliveryMessage:
    """Return a copy safe for audit logs, local artifacts, and default CLI output."""
    redacted_actions = []
    for button in message.actions:
        token = button.signed_token
        safe_token = f"redacted:{_token_fingerprint(token)}" if token else ""
        redacted_actions.append(button.model_copy(update={"signed_token": safe_token}))
    return message.model_copy(update={"actions": redacted_actions})


def _decision_for_option(option: ReviewActionOption) -> ReviewDecision:
    if option.code == ReviewAction.MARK_DUPLICATE:
        return ReviewDecision.MARK_DUPLICATE
    if option.code == ReviewAction.DISPUTE:
        return ReviewDecision.DISPUTE
    if option.code == ReviewAction.REQUEST_BACKUP:
        return ReviewDecision.REQUEST_BACKUP
    if option.code == ReviewAction.EDIT:
        return ReviewDecision.EDIT_FIELDS
    # APPROVE splits into expected-amount (drafts a dispute) vs full-amount as billed.
    if option.amount_kind == "EXPECTED":
        return ReviewDecision.APPROVE_EXPECTED_AMOUNT
    if option.amount_kind == "FULL":
        return ReviewDecision.APPROVE_FULL_AMOUNT
    if option.creates_follow_up_draft:
        return ReviewDecision.APPROVE_EXPECTED_AMOUNT
    return ReviewDecision.APPROVE_FULL_AMOUNT


def _maybe_create_follow_up(
    store: WorkflowStore,
    action: SignedAction,
    result,
    follow_up_loads: dict[str, FreightLoadForReconciliation] | None,
) -> bool:
    if not result.draft_follow_up_required or follow_up_loads is None:
        return False
    payload = _latest_review_payload(store, action.run_id)
    if payload is None:
        return False
    load = follow_up_loads.get(payload.load_id)
    if load is None:
        return False
    draft = build_follow_up_draft(payload, load, action.decision)
    record_follow_up_draft(store, draft)
    return True


def _mutate_message(message: DeliveryMessage, mutation_text: str, *, now: datetime) -> DeliveryMessage:
    banner = f"{mutation_text} at {now.strftime('%Y-%m-%d %H:%M UTC')}"
    return message.model_copy(
        update={"status_banner": banner, "history": [*message.history, banner]}
    )


def _prior_application(store: WorkflowStore, run_id: int, action_id: str) -> dict | None:
    for event in store.audit_events(run_id):
        if (
            event["event_type"] == "delivery_action_applied"
            and event["payload"].get("action_id") == action_id
        ):
            return event["payload"]
    return None


def _duplicate_outcome(
    store: WorkflowStore,
    action: SignedAction,
    prior: dict,
    *,
    now: datetime,
) -> DeliveryActionOutcome:
    store.add_audit_event(
        action.run_id,
        "delivery_action_duplicate",
        actor=action.actor,
        payload={"action_id": action.action_id, "decision": action.decision.value},
    )
    message = DeliveryMessage.model_validate(prior["message"])
    return DeliveryActionOutcome(
        run_id=action.run_id,
        action_id=action.action_id,
        status=DeliveryActionStatus.DUPLICATE_IGNORED,
        decision=action.decision,
        from_state=WorkflowState(prior["from_state"]),
        to_state=WorkflowState(prior["to_state"]),
        actor=action.actor,
        mutation_text=prior["mutation_text"],
        follow_up_created=bool(prior.get("follow_up_created")),
        message=message,
    )


def _current_message(store: WorkflowStore, run_id: int) -> DeliveryMessage:
    events = store.audit_events(run_id)
    for event in reversed(events):
        if event["event_type"] in {"delivery_action_applied", "delivery_message_created"}:
            return DeliveryMessage.model_validate(event["payload"]["message"])
    payload = _latest_review_payload(store, run_id)
    if payload is not None:
        return build_delivery_message(payload)
    raise DeliveryError(f"no delivered message or review payload to mutate for run {run_id}")


def _latest_review_payload(store: WorkflowStore, run_id: int) -> ReviewPayload | None:
    for event in reversed(store.audit_events(run_id)):
        if event["event_type"] == "review_payload_created":
            return ReviewPayload.model_validate(event["payload"])
    return None


def _token_fingerprint(token: str) -> str:
    """Short, non-reversible fingerprint of a token for audit without storing its (untrusted) claims."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


def _amount_str(amount: str | Decimal | None) -> str | None:
    if amount is None:
        return None
    return f"{Decimal(amount):.2f}"


def _message_key(message: DeliveryMessage) -> str:
    return f"{message.run_id}:{message.channel.value}:{message.severity.value}:{len(message.actions)}"
