"""Tests for the shared-browser 'busy' signal — writer marks, reader defers, stale markers ignored."""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.browser_lock import BrowserLock  # noqa: E402


def test_mark_and_clear(tmp_path):
    lock = BrowserLock(tmp_path / "browser.busy")
    assert lock.is_busy() is False           # nothing marked
    lock.mark_busy(holder="agent")
    assert lock.is_busy() is True            # writer holds it
    lock.clear()
    assert lock.is_busy() is False           # released


def test_hold_context_manager_marks_then_clears(tmp_path):
    lock = BrowserLock(tmp_path / "browser.busy")
    with lock.hold(holder="operation"):
        assert lock.is_busy() is True        # busy during the write
    assert lock.is_busy() is False           # cleared after, even implicitly


def test_hold_clears_even_on_error(tmp_path):
    lock = BrowserLock(tmp_path / "browser.busy")
    try:
        with lock.hold():
            raise RuntimeError("write blew up")
    except RuntimeError:
        pass
    assert lock.is_busy() is False           # a crashed write must not wedge the reader


def test_stale_marker_is_ignored(tmp_path):
    p = tmp_path / "browser.busy"
    p.write_text(json.dumps({"at": time.time() - 999, "holder": "dead"}), encoding="utf-8")  # long expired
    assert BrowserLock(p, ttl_seconds=180).is_busy() is False  # TTL: a crashed writer can't block forever
