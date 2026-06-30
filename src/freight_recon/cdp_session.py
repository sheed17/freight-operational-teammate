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
import time
import urllib.request

import websocket  # websocket-client


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

    def connect(self) -> None:
        tabs = json.load(urllib.request.urlopen(f"{self.cdp_url}/json", timeout=self.timeout))
        pages = [t for t in tabs if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
        if self.url_filter:
            pages = [t for t in pages if self.url_filter in (t.get("url") or "")] or pages
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

    def navigate(self, url: str, *, settle_seconds: float = 3.0) -> None:
        self._cmd("Page.navigate", {"url": url})
        time.sleep(settle_seconds)  # let the page (and any XHR-rendered form) settle before reading

    def evaluate(self, expression: str):
        result = self._cmd("Runtime.evaluate", {"expression": expression, "returnByValue": True})
        return result.get("result", {}).get("result", {}).get("value")
