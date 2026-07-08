"""A minimal CDP (Chrome DevTools Protocol) browser session: navigate + evaluate.

This is the thin, real-browser realization of the :class:`BrowserSession` protocol the gated
TruckingOffice ledger drives. It attaches to a Chrome the human already logged into (so no credentials
are ever stored or typed by the agent) and exposes just two operations: navigate to a URL and evaluate
JavaScript in the page. Keeping the surface tiny keeps the money-path logic deterministic and testable
elsewhere; this file is the I/O seam.

Chrome 111+ rejects CDP websocket connections that carry a browser ``Origin`` header, so the client
connects with the origin suppressed (the connection is a local tool, not a web page).
"""

from __future__ import annotations

import json
import base64
import time
import urllib.error
import urllib.request
from pathlib import Path

import websocket  # websocket-client

from .browser_session_health import url_matches_filter


class CdpError(RuntimeError):
    pass


class CdpBrowserSession:
    def __init__(self, *, cdp_url: str = "http://localhost:9222", url_filter: str | None = None, timeout: int = 20) -> None:
        self.cdp_url = cdp_url.rstrip("/")
        self.url_filter = url_filter
        self.timeout = timeout
        self._ws = None
        self._id = 0

    def __enter__(self) -> "CdpBrowserSession":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def connect(self, *, attempts: int = 3) -> None:
        """Attach to a Chrome page tab, retrying transient timeouts (the socket occasionally times out
        on the first try when the browser is busy — a retry beats crashing the whole operation)."""
        last: Exception | None = None
        for i in range(max(1, attempts)):
            try:
                self._connect_once()
                return
            except (websocket.WebSocketException, OSError, urllib.error.URLError) as exc:
                last = exc
                self.close()
                time.sleep(0.6 * (i + 1))
        raise CdpError(f"could not connect to CDP at {self.cdp_url} after {attempts} tries: {last}")

    def _connect_once(self) -> None:
        tabs = json.load(urllib.request.urlopen(f"{self.cdp_url}/json", timeout=self.timeout))
        pages = [t for t in tabs if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
        if self.url_filter:
            pages = [t for t in pages if url_matches_filter(t.get("url") or "", self.url_filter)]
        if not pages:
            raise CdpError(f"no attachable page tab at {self.cdp_url}")
        self._ws = websocket.create_connection(
            pages[0]["webSocketDebuggerUrl"], timeout=self.timeout, max_size=None, suppress_origin=True
        )
        self._cmd("Page.enable")

    def close(self) -> None:
        if self._ws is not None:
            try:
                self._ws.close()
            finally:
                self._ws = None

    def _cmd(self, method: str, params: dict | None = None) -> dict:
        if self._ws is None:
            raise CdpError("session is not connected")
        self._id += 1
        mid = self._id
        self._ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self._ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise CdpError(f"{method} failed: {msg['error']}")
                return msg

    def command(self, method: str, params: dict | None = None) -> dict:
        """Public passthrough to a raw CDP command (e.g. the Input domain for real keyboard/mouse)."""
        return self._cmd(method, params)

    def host_allowed(self, url: str) -> bool:
        """Is this navigation target on the TMS domain allowlist? A relative/same-page target stays on
        the current (already-allowed) origin. With no ``url_filter`` configured, navigation is
        unrestricted (dev). This is the hard guard the browser-supervision protocol requires so a
        mis-prompted agent can't wander out of the authenticated TMS session."""
        if not self.url_filter:
            return True
        u = (url or "").strip()
        lowered = u.lower()
        if lowered.startswith(("javascript:", "data:", "file:", "vbscript:")):
            return False
        if not u or u[0] in "/?#" or lowered.startswith("about:blank"):
            return True  # relative / same-page / no-op navigation
        return url_matches_filter(u, self.url_filter)

    def navigate(self, url: str, *, settle_seconds: float = 3.0) -> None:
        if not self.host_allowed(url):
            # Refuse to drive the authenticated TMS browser off its domain (a confused/mis-prompted
            # NAVIGATE). Raised as CdpError; the actuator catches it into a soft failed-action so the
            # agent adapts/escalates rather than crashing.
            raise CdpError(f"navigation to {url!r} blocked — not on the TMS domain allowlist "
                           f"({self.url_filter!r})")
        self._cmd("Page.navigate", {"url": url})
        time.sleep(settle_seconds)  # let the page (and any XHR-rendered form) settle before reading

    def evaluate(self, expression: str):
        result = self._cmd("Runtime.evaluate", {"expression": expression, "returnByValue": True})
        return result.get("result", {}).get("result", {}).get("value")

    def capture_screenshot(self, path: str | Path, *, full_page: bool = False) -> str:
        """Capture a PNG screenshot to disk for audit/debug evidence.

        This is cheap browser observability. It does not call a vision model; callers decide separately
        whether a failure warrants expensive visual inference.
        """
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        result = self._cmd(
            "Page.captureScreenshot",
            {"format": "png", "captureBeyondViewport": bool(full_page)},
        )
        data = result.get("result", {}).get("data")
        if not data:
            raise CdpError("Page.captureScreenshot returned no data")
        target.write_bytes(base64.b64decode(data))
        return str(target)
