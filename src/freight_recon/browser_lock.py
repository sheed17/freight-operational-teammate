"""A cross-process 'browser busy' signal for the single shared Chrome (CDP) session.

Two processes drive the one logged-in browser: the operation agent (on a Slack tap — WRITING to the
TMS) and the AR-trigger (periodically READING /loads). They must not touch the same tab at once, or a
periodic read could navigate away mid-write. The write is always allowed (it's the human-approved
action); the READER defers. So this is not mutual exclusion — it's a one-way signal: the writer marks
the browser busy while it operates, and the reader skips a cycle if the browser is busy.

A TTL guards against a crashed writer wedging the reader forever (a stale marker is ignored).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path


class BrowserLock:
    def __init__(self, path: str | Path, *, ttl_seconds: float = 180.0) -> None:
        self.path = Path(path)
        self.ttl = ttl_seconds

    def is_busy(self) -> bool:
        """True if a writer marked the browser busy recently (within the TTL). Stale markers are ignored
        so a crashed writer can't block the reader forever."""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - missing/corrupt marker = not busy
            return False
        return (time.time() - float(data.get("at", 0))) < self.ttl

    def mark_busy(self, *, holder: str = "") -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps({"at": time.time(), "holder": holder}), encoding="utf-8")
        os.replace(tmp, self.path)  # atomic

    def clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def hold(self, *, holder: str = ""):
        """Context manager for the WRITER: marks busy on enter, clears on exit (even on error)."""
        return _Hold(self, holder)


class _Hold:
    def __init__(self, lock: BrowserLock, holder: str) -> None:
        self._lock = lock
        self._holder = holder

    def __enter__(self) -> "_Hold":
        self._lock.mark_busy(holder=self._holder)
        return self

    def __exit__(self, *_exc) -> None:
        self._lock.clear()
