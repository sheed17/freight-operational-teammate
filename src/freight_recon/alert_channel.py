"""Resilient critical alerts: reach the owner even when Slack is the thing that's down.

Neyma's alerts (loop went stale, a write failed, the bot can't post) are today circular — they all go
*through* Slack, so the one failure mode that most needs an alert (Slack itself dead, token revoked,
API erroring) is exactly the one that silently swallows it. This adds a fail-over: try Slack first, and
if that fails, fall back to email so a human still hears about it.

Pure and injectable: the Slack poster and email sender are passed in (fakes in tests). The function
never raises — an alert path that throws is worse than one that degrades, so every failure is captured
into the returned result for the caller to log.
"""

from __future__ import annotations

from dataclasses import dataclass

from .email_adapter import EmailMessageModel


@dataclass
class AlertResult:
    delivered: bool
    channel: str  # "slack" | "email" | "none"
    detail: str


def send_critical_alert(
    text: str,
    *,
    slack_poster=None,
    email_sender=None,
    email_to: str | None = None,
    email_from: str = "neyma@localhost",
    subject: str = "[Neyma] Alert",
) -> AlertResult:
    """Deliver a critical alert, Slack first then email. Returns which channel actually carried it.

    ``slack_poster(text) -> result`` is anything with a truthy ``.ok`` on success (e.g.
    ``SlackPostResult``); ``email_sender.send(EmailMessageModel) -> result`` likewise. Either may be
    ``None`` (that channel is simply unavailable). The fallback fires only when Slack does NOT succeed.
    """
    # 1) Primary: Slack.
    if slack_poster is not None:
        try:
            result = slack_poster(text)
            if getattr(result, "ok", bool(result)):
                return AlertResult(True, "slack", "posted to Slack")
            slack_detail = f"slack failed: {getattr(result, 'error', 'unknown')}"
        except Exception as exc:  # noqa: BLE001 - a throwing poster must not break the alert path
            slack_detail = f"slack raised: {type(exc).__name__}: {str(exc)[:140]}"
    else:
        slack_detail = "no slack poster"

    # 2) Fallback: email — the whole point is that this path does not depend on Slack.
    if email_sender is not None and email_to:
        email = EmailMessageModel(
            run_id=0, to=email_to, sender=email_from, subject=subject,
            text_body=text, html_body=f"<pre>{_escape(text)}</pre>",
        )
        try:
            sent = email_sender.send(email)
            if getattr(sent, "ok", False):
                return AlertResult(True, "email", f"{slack_detail}; fell back to email")
            return AlertResult(False, "none", f"{slack_detail}; email failed: {getattr(sent, 'error', 'unknown')}")
        except Exception as exc:  # noqa: BLE001
            return AlertResult(False, "none", f"{slack_detail}; email raised: {type(exc).__name__}")

    return AlertResult(False, "none", f"{slack_detail}; no email fallback configured")


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
