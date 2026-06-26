"""Tests for posting TMS execution status as threaded replies under the Slack review card."""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.delivery_dispatch import (  # noqa: E402
    SlackPostResult,
    latest_slack_card_target,
    slack_thread_status_poster,
)
from freight_recon.tms_write import ExecutionPhase, ExecutionStatusUpdate  # noqa: E402


class _FakePoster:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.calls: list[dict] = []

    def post_message(self, *, channel: str, payload: dict) -> SlackPostResult:
        self.calls.append({"channel": channel, **payload})
        return SlackPostResult(ok=self.ok, channel=channel, ts="999.0001", error=None if self.ok else "rate_limited")


class _FakeStore:
    def __init__(self, events: list[dict]) -> None:
        self._events = events
        self.added: list[dict] = []

    def audit_events(self, run_id: int) -> list[dict]:
        return self._events

    def add_audit_event(self, run_id: int, event_type: str, *, actor: str, payload: dict) -> None:
        self.added.append({"event_type": event_type, "payload": payload})


def _sent(external_id: str, destination: str, status: str = "SENT") -> dict:
    return {
        "event_type": "delivery_dispatch_attempted",
        "payload": {"channel": "slack", "status": status, "external_id": external_id, "destination": destination},
    }


def test_status_posts_threaded_reply_under_the_card():
    store = _FakeStore([_sent("111.2222", "C123")])
    poster = _FakePoster()
    on_status = slack_thread_status_poster(store, SimpleNamespace(slack=None), env={}, poster=poster)

    on_status(
        ExecutionStatusUpdate(
            run_id=1, load_id="LD-1", phase=ExecutionPhase.ENTERED, message="Payable entered: PV-X", external_ref="PV-X"
        )
    )

    assert len(poster.calls) == 1
    call = poster.calls[0]
    assert call["channel"] == "C123"
    assert call["thread_ts"] == "111.2222"  # reply lands under the approved card, not a new message
    assert "PV-X" in call["text"]
    assert store.added[-1]["event_type"] == "execution_status_posted"
    assert store.added[-1]["payload"]["ok"] is True


def test_status_skipped_and_audited_when_no_card_target():
    store = _FakeStore([])  # the card was never sent (e.g. dry run)
    on_status = slack_thread_status_poster(store, SimpleNamespace(slack=None), env={}, poster=_FakePoster())
    on_status(ExecutionStatusUpdate(run_id=1, load_id="LD-1", phase=ExecutionPhase.DONE, message="done"))
    assert store.added[-1]["event_type"] == "execution_status_post_skipped"


def test_latest_slack_card_target_picks_most_recent_sent():
    store = _FakeStore(
        [
            _sent("1.0", "C1"),
            _sent("", "C1", status="BLOCKED"),
            _sent("2.0", "C2"),
        ]
    )
    assert latest_slack_card_target(store, 1) == ("C2", "2.0")
