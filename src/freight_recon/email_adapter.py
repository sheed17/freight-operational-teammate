"""Local/dev email-link transport for the channel-neutral delivery adapter.

Renders a :class:`~freight_recon.delivery.DeliveryMessage` into a multipart (plain-text + HTML)
review artifact whose action buttons are **signed action links**, and accepts a clicked link back
into the signed action intake. As with the Slack transport, all business logic stays in
``delivery.submit_signed_action`` and the workflow state machine.

The signed Neyma token in each link is the credential: it is HMAC-signed, expiring, and single-use,
so a leaked link cannot be replayed after it is used or after it expires. Product user review goes
to Slack only; these artifacts are written to a local outbox for tests/dogfood and are not used as
a live user-notification channel.
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage as MimeMessage
from email.utils import formatdate
from html import escape
from pathlib import Path
import re
from typing import Protocol
from urllib.parse import parse_qs, urlencode, urlsplit

from pydantic import BaseModel, Field

from .delivery import (
    DeliveryActionOutcome,
    DeliveryMessage,
    DeliverySigner,
    submit_signed_action,
)
from .reconciliation import FreightLoadForReconciliation
from .workflow import WorkflowStore

DEFAULT_ACTION_BASE_URL = "http://localhost:8000/email/action"
DEFAULT_FROM_ADDRESS = "neyma@neyma-test-freight.test"


class EmailError(RuntimeError):
    """Base error for the email transport."""


class EmailAction(BaseModel):
    label: str
    decision: str
    url: str


class EmailMessageModel(BaseModel):
    run_id: int
    to: str
    sender: str = DEFAULT_FROM_ADDRESS
    subject: str
    text_body: str
    html_body: str
    actions: list[EmailAction] = Field(default_factory=list)


class EmailOutboxRecord(BaseModel):
    run_id: int
    to: str
    subject: str
    path: str | None = None
    sent: bool = False
    note: str


def build_email_message(
    message: DeliveryMessage,
    *,
    to: str,
    action_base_url: str = DEFAULT_ACTION_BASE_URL,
    sender: str = DEFAULT_FROM_ADDRESS,
) -> EmailMessageModel:
    """Render a delivery message into a local/dev review email artifact with signed action links."""
    actions = [
        EmailAction(
            label=button.label,
            decision=button.decision.value,
            url=_action_link(action_base_url, message.run_id, button.signed_token),
        )
        for button in message.actions
    ]
    return EmailMessageModel(
        run_id=message.run_id,
        to=to,
        sender=sender,
        subject=f"[Neyma] {message.title}",
        text_body=_text_body(message, actions),
        html_body=_html_body(message, actions),
        actions=actions,
    )


def build_mime(email: EmailMessageModel) -> MimeMessage:
    """Build a MIME ``multipart/alternative`` message (text + HTML) from the email model."""
    mime = MimeMessage()
    mime["Subject"] = email.subject
    mime["From"] = email.sender
    mime["To"] = email.to
    mime["Date"] = formatdate(localtime=True)
    mime["X-Neyma-Run-Id"] = str(email.run_id)
    mime.set_content(email.text_body)
    mime.add_alternative(email.html_body, subtype="html")
    return mime


def render_email_mime(email: EmailMessageModel) -> str:
    """Render an :class:`EmailMessageModel` into a MIME ``multipart/alternative`` string."""
    return build_mime(email).as_string()


class EmailSendResult(BaseModel):
    ok: bool
    error: str | None = None


class EmailSender(Protocol):
    """Minimal send interface so the dispatcher can inject a fake in tests."""

    def send(self, email: EmailMessageModel) -> EmailSendResult:
        ...


class SmtpEmailSender:
    """Send email over SMTP with STARTTLS. Credentials are passed in, never stored.

    This class is intentionally injectable. It should be used by a carrier-facing follow-up send
    gate, not for human review cards.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int = 587,
        username: str | None = None,
        password: str | None = None,
        starttls: bool = True,
        timeout: int = 15,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.starttls = starttls
        self.timeout = timeout

    def send(self, email: EmailMessageModel) -> EmailSendResult:
        mime = build_mime(email)
        try:
            with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as server:
                if self.starttls:
                    server.starttls()
                if self.username:
                    server.login(self.username, self.password or "")
                server.send_message(mime)
        except Exception as exc:  # noqa: BLE001 - transport errors are recorded, not raised
            # Bound + categorize: the note lands in an audit sink, so never store unbounded text.
            return EmailSendResult(ok=False, error=f"{type(exc).__name__}: {str(exc)[:160]}")
        return EmailSendResult(ok=True)


def parse_email_action_token(link: str) -> str:
    """Extract the signed action token from a clicked email action link or its query string."""
    query = urlsplit(link).query or link
    fields = parse_qs(query)
    token = fields.get("token")
    if not token or not token[0]:
        raise EmailError("email action link has no token")
    return token[0]


class EmailOutbox:
    """A gated local outbox. Writes ``.eml`` files; never sends over real SMTP in this slice."""

    def __init__(self, outbox_dir: str | Path, *, outbound_enabled: bool = False) -> None:
        self.outbox_dir = Path(outbox_dir)
        self.outbound_enabled = outbound_enabled

    def deliver(self, email: EmailMessageModel) -> EmailOutboxRecord:
        self.outbox_dir.mkdir(parents=True, exist_ok=True)
        path = self.outbox_dir / f"review_{email.run_id}_{_safe_recipient_slug(email.to)}.eml"
        path.write_text(render_email_mime(email), encoding="utf-8")
        # No real SMTP transport exists yet, so `outbound_enabled` never causes a send: every
        # path writes the .eml and returns sent=False. The flag only records intent for when a
        # gated SMTP transport is added later behind the tool-permission registry.
        note = (
            "outbound intent set, but no SMTP transport is wired; written to local outbox only (not sent)"
            if self.outbound_enabled
            else "outbound disabled; written to local outbox only (not sent)"
        )
        return EmailOutboxRecord(run_id=email.run_id, to=email.to, subject=email.subject, path=str(path), sent=False, note=note)


class EmailDeliveryAdapter:
    """Bind the email transport to the signed action intake."""

    def __init__(
        self,
        store: WorkflowStore,
        *,
        signer: DeliverySigner | None = None,
        action_base_url: str = DEFAULT_ACTION_BASE_URL,
        sender: str = DEFAULT_FROM_ADDRESS,
    ) -> None:
        self.store = store
        self.signer = signer or DeliverySigner.from_env()
        self.action_base_url = action_base_url
        self.sender = sender

    def build(self, message: DeliveryMessage, *, to: str) -> EmailMessageModel:
        return build_email_message(message, to=to, action_base_url=self.action_base_url, sender=self.sender)

    def handle_action_link(
        self,
        link: str,
        *,
        follow_up_loads: dict[str, FreightLoadForReconciliation] | None = None,
    ) -> DeliveryActionOutcome:
        """Apply the signed action carried by a clicked email link.

        The token is the credential — it is verified, expiry-checked, and idempotent inside
        ``submit_signed_action``. Propagates delivery/workflow errors from that intake.
        """
        token = parse_email_action_token(link)
        return submit_signed_action(self.store, token, signer=self.signer, follow_up_loads=follow_up_loads)


def _action_link(action_base_url: str, run_id: int, token: str) -> str:
    return f"{action_base_url}?{urlencode({'run': run_id, 'token': token})}"


def _safe_recipient_slug(recipient: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", recipient).strip("_").lower()
    return slug[:80] or "recipient"


def _text_body(message: DeliveryMessage, actions: list[EmailAction]) -> str:
    lines = [
        message.title,
        "",
        f"Load: {message.load_id}",
        f"Carrier: {message.carrier}",
        f"Invoice: {message.invoice_number}",
        f"Severity: {message.severity.value}  Route: {message.route.value}",
        f"Flagged: ${message.found_money.flagged_amount}",
        f"Packet: {message.packet_detail_url}",
        "",
        message.summary,
    ]
    if message.evidence_links:
        lines.append("")
        lines.append("Evidence:")
        lines.extend(f"- {link.label}: {link.url}" for link in message.evidence_links)
    if actions:
        lines.append("")
        lines.append("Actions (click to apply):")
        lines.extend(f"- {action.label}: {action.url}" for action in actions)
    lines.append("")
    lines.append(f"Status: {message.status_banner}")
    return "\n".join(lines)


def _html_body(message: DeliveryMessage, actions: list[EmailAction]) -> str:
    evidence = "".join(
        f'<li><a href="{escape(link.url)}">{escape(link.label)}</a></li>' for link in message.evidence_links
    )
    buttons = "".join(
        f'<a href="{escape(action.url)}" '
        'style="display:inline-block;margin:4px 8px 4px 0;padding:10px 14px;'
        'background:#172033;color:#ffffff;text-decoration:none;border-radius:6px;font-weight:700;">'
        f"{escape(action.label)}</a>"
        for action in actions
    )
    return f"""<!doctype html>
<html><body style="font-family:Inter,Arial,sans-serif;color:#172033;">
  <h2 style="margin:0 0 8px;">{escape(message.title)}</h2>
  <p style="color:#596780;margin:0 0 16px;">Severity {escape(message.severity.value)} ·
     Route {escape(message.route.value)} · Flagged ${escape(message.found_money.flagged_amount)}</p>
  <table style="border-collapse:collapse;margin-bottom:12px;">
    <tr><td style="padding:2px 12px 2px 0;color:#596780;">Load</td><td><strong>{escape(message.load_id)}</strong></td></tr>
    <tr><td style="padding:2px 12px 2px 0;color:#596780;">Carrier</td><td>{escape(message.carrier)}</td></tr>
    <tr><td style="padding:2px 12px 2px 0;color:#596780;">Invoice</td><td>{escape(message.invoice_number)}</td></tr>
  </table>
  <p>{escape(message.summary)}</p>
  <p><a href="{escape(message.packet_detail_url)}">Open packet detail</a></p>
  {f'<p><strong>Evidence</strong></p><ul>{evidence}</ul>' if evidence else ''}
  <p><strong>Actions</strong></p>
  <p>{buttons}</p>
  <p style="color:#596780;font-size:13px;">{escape(message.status_banner)}</p>
</body></html>
"""
