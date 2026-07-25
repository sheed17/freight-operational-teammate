"""Tests for the resilient critical-alert channel: Slack first, email fallback when Slack is down."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.alert_channel import send_critical_alert  # noqa: E402


class _Res:
    def __init__(self, ok, error=None):
        self.ok = ok
        self.error = error


class _Slack:
    def __init__(self, ok, raises=False):
        self.ok = ok
        self.raises = raises
        self.calls = 0

    def __call__(self, text):
        self.calls += 1
        if self.raises:
            raise RuntimeError("slack api down")
        return _Res(self.ok, None if self.ok else "no_slack_token")


class _Email:
    def __init__(self, ok=True):
        self.ok = ok
        self.sent = []

    def send(self, email):
        self.sent.append(email)
        return _Res(self.ok)


def test_slack_ok_does_not_fall_back():
    slack, email = _Slack(ok=True), _Email()
    res = send_critical_alert("loop is stale", slack_poster=slack, email_sender=email, email_to="o@x.com")
    assert res.delivered and res.channel == "slack"
    assert email.sent == []  # email untouched when Slack works


def test_slack_failure_falls_back_to_email():
    slack, email = _Slack(ok=False), _Email(ok=True)
    res = send_critical_alert("loop is stale", slack_poster=slack, email_sender=email,
                              email_to="owner@x.com", subject="[Neyma] STALE")
    assert res.delivered and res.channel == "email"
    assert len(email.sent) == 1 and email.sent[0].to == "owner@x.com"
    assert email.sent[0].subject == "[Neyma] STALE" and "loop is stale" in email.sent[0].text_body


def test_slack_raising_still_falls_back():
    slack, email = _Slack(ok=True, raises=True), _Email(ok=True)
    res = send_critical_alert("write failed", slack_poster=slack, email_sender=email, email_to="o@x.com")
    assert res.delivered and res.channel == "email"


def test_no_fallback_configured_reports_undelivered_without_raising():
    res = send_critical_alert("x", slack_poster=_Slack(ok=False))
    assert not res.delivered and res.channel == "none" and "no email fallback" in res.detail


def test_both_down_is_captured_not_raised():
    res = send_critical_alert("x", slack_poster=_Slack(ok=False), email_sender=_Email(ok=False),
                              email_to="o@x.com")
    assert not res.delivered and res.channel == "none" and "email failed" in res.detail
