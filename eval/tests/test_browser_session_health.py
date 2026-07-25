"""Tests for CDP/TMS browser session health classification."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.browser_session_health import (  # noqa: E402
    read_browser_session_health,
    render_browser_session_health,
    url_matches_filter,
)


def _fetch_tabs(tabs):
    def fetch(url: str, timeout: float) -> bytes:
        assert url == "http://localhost:9222/json"
        assert timeout > 0
        return json.dumps(tabs).encode("utf-8")

    return fetch


def test_browser_session_health_ok_when_matching_logged_in_tms_tab():
    health = read_browser_session_health(
        url_filter="secure.truckingoffice.com",
        fetcher=_fetch_tabs([
            {"type": "page", "url": "https://secure.truckingoffice.com/loads", "title": "Loads"},
        ]),
    )
    assert health.status == "OK"
    assert health.healthy is True
    assert health.matching_tabs == 1
    assert "Browser session" in render_browser_session_health(health)


def test_browser_session_health_no_cdp_when_fetch_fails():
    def fetch(url: str, timeout: float) -> bytes:
        raise OSError("closed")

    health = read_browser_session_health(fetcher=fetch)
    assert health.status == "NO_CDP"
    assert health.healthy is False
    assert "not reachable" in health.detail


def test_browser_session_health_no_tms_tab_when_filter_does_not_match():
    health = read_browser_session_health(
        url_filter="secure.truckingoffice.com",
        fetcher=_fetch_tabs([
            {"type": "page", "url": "https://example.com", "title": "Example"},
        ]),
    )
    assert health.status == "NO_TMS_TAB"
    assert health.healthy is False
    assert health.tabs_seen == 1


def test_browser_session_health_uses_host_label_matching_not_substrings():
    assert url_matches_filter("https://secure.truckingoffice.com/loads", "truckingoffice") is True
    assert url_matches_filter("https://secure.truckingoffice.com/loads", "truckingoffice.com") is True
    assert url_matches_filter("https://evil-truckingoffice.com/loads", "truckingoffice") is False

    health = read_browser_session_health(
        url_filter="truckingoffice",
        fetcher=_fetch_tabs([
            {"type": "page", "url": "https://evil-truckingoffice.com/loads", "title": "Wrong tab"},
        ]),
    )
    assert health.status == "NO_TMS_TAB"


def test_browser_session_health_session_expired_when_login_page_visible():
    health = read_browser_session_health(
        url_filter="secure.truckingoffice.com",
        fetcher=_fetch_tabs([
            {"type": "page", "url": "https://secure.truckingoffice.com/login", "title": "Sign in"},
        ]),
    )
    assert health.status == "SESSION_EXPIRED"
    assert health.healthy is False
    assert "re-auth" in health.detail


def test_browser_session_health_unreadable_for_non_list_cdp_payload():
    health = read_browser_session_health(fetcher=_fetch_tabs({"bad": "shape"}))
    assert health.status == "UNREADABLE"
    assert health.healthy is False
