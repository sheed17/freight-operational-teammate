"""Managed browser/session health checks for the production browser bridge.

The pilot browser model is human-established session + Neyma-managed supervision. This module gives
that model an explicit health contract: is CDP reachable, is a TMS tab present, and does the current
page look logged in enough to operate? It does not store credentials or try to bypass MFA.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from urllib.parse import urlparse
from typing import Callable


Fetcher = Callable[[str, float], bytes]


@dataclass
class BrowserSessionHealth:
    status: str  # OK | NO_CDP | NO_TMS_TAB | SESSION_EXPIRED | UNREADABLE
    healthy: bool
    detail: str
    cdp_url: str
    url_filter: str | None = None
    active_url: str | None = None
    tabs_seen: int = 0
    matching_tabs: int = 0
    evidence: dict = field(default_factory=dict)


_LOGIN_HINTS = (
    "login", "log in", "sign in", "signin", "session expired", "session has expired",
    "session timed out", "please authenticate",
)
_LOGIN_PATH_RE = re.compile(r"/(login|signin|sign_in|sessions/new|auth)\b", re.I)


def read_browser_session_health(
    *,
    cdp_url: str = "http://localhost:9222",
    url_filter: str | None = None,
    fetcher: Fetcher | None = None,
    timeout: float = 2.0,
) -> BrowserSessionHealth:
    """Read Chrome's CDP tab list and classify the operator session.

    ``url_filter`` is the same domain/subdomain pin used by the operation router. With a filter, at
    least one matching tab must be present. A login-looking URL/title is treated as re-auth required.
    """
    base = cdp_url.rstrip("/")
    fetch = fetcher or _fetch
    try:
        raw = fetch(f"{base}/json", timeout)
        tabs = json.loads(raw.decode("utf-8"))
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        return BrowserSessionHealth(
            status="NO_CDP",
            healthy=False,
            detail=f"Browser CDP is not reachable at {base}: {type(exc).__name__}.",
            cdp_url=base,
            url_filter=url_filter,
        )
    if not isinstance(tabs, list):
        return BrowserSessionHealth(
            status="UNREADABLE",
            healthy=False,
            detail="Browser CDP returned an unreadable tab list.",
            cdp_url=base,
            url_filter=url_filter,
        )
    pages = [t for t in tabs if isinstance(t, dict) and t.get("type") == "page"]
    if url_filter:
        matches = [t for t in pages if url_matches_filter(str(t.get("url") or ""), url_filter)]
    else:
        matches = pages
    if not matches:
        return BrowserSessionHealth(
            status="NO_TMS_TAB",
            healthy=False,
            detail=(
                f"No browser tab matches the TMS filter {url_filter!r}."
                if url_filter else "No browser page tab is available for Neyma."
            ),
            cdp_url=base,
            url_filter=url_filter,
            tabs_seen=len(pages),
        )
    tab = matches[0]
    active_url = str(tab.get("url") or "")
    title = str(tab.get("title") or "")
    hay = f"{active_url} {title}".lower()
    if _LOGIN_PATH_RE.search(active_url) or any(hint in hay for hint in _LOGIN_HINTS):
        return BrowserSessionHealth(
            status="SESSION_EXPIRED",
            healthy=False,
            detail="TMS browser session appears to be on a login/session-expired page; human re-auth is required.",
            cdp_url=base,
            url_filter=url_filter,
            active_url=active_url,
            tabs_seen=len(pages),
            matching_tabs=len(matches),
            evidence={"title": title},
        )
    return BrowserSessionHealth(
        status="OK",
        healthy=True,
        detail=f"Browser session is reachable with a matching TMS tab: {active_url or title}.",
        cdp_url=base,
        url_filter=url_filter,
        active_url=active_url,
        tabs_seen=len(pages),
        matching_tabs=len(matches),
        evidence={"title": title},
    )


def render_browser_session_health(snapshot: BrowserSessionHealth) -> str:
    emoji = {
        "OK": ":large_green_circle:",
        "NO_CDP": ":red_circle:",
        "NO_TMS_TAB": ":large_yellow_circle:",
        "SESSION_EXPIRED": ":red_circle:",
        "UNREADABLE": ":red_circle:",
    }.get(snapshot.status, ":grey_question:")
    return f"{emoji} Browser session: {snapshot.detail}"


def url_matches_filter(url: str, url_filter: str | None) -> bool:
    """Return True when ``url`` is on the configured TMS host/domain allowlist.

    This intentionally mirrors the CDP navigation guard: match a full dot-label ("truckingoffice" in
    "secure.truckingoffice.com") or a full-domain suffix, never a raw substring.
    """
    if not url_filter:
        return True
    u = (url or "").strip()
    if not u:
        return False
    parsed = urlparse(u if "://" in u else "https://" + u)
    host = (parsed.netloc or parsed.path).lower().split(":")[0]
    if not host:
        return False
    parsed_filter = urlparse(url_filter if "://" in url_filter else "https://" + url_filter)
    needle = (parsed_filter.netloc or parsed_filter.path).lower().split(":")[0]
    if not needle:
        return False
    return needle in host.split(".") or host == needle or host.endswith("." + needle)


def _fetch(url: str, timeout: float) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read()
