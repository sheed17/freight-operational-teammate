"""Tests for the CDP actuator perception/action contract."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.cdp_actuator import CdpActuator, _OBSERVE_JS  # noqa: E402


class FakeSession:
    def __init__(self):
        self.expressions: list[str] = []

    def evaluate(self, expression: str):
        self.expressions.append(expression)
        if "querySelectorAll('a,button,input,select,textarea,[role=button]')" in expression:
            return 3
        return True


def test_observe_contract_includes_tables_rows_iframes_and_interactive_controls():
    assert "tables:tables" in _OBSERVE_JS
    assert "rows:rowLike" in _OBSERVE_JS
    assert "iframes:frames" in _OBSERVE_JS
    assert "interactive:interactive" in _OBSERVE_JS
    assert "body_text" in _OBSERVE_JS


def test_click_accepts_row_action_target_shape():
    session = FakeSession()
    actuator = CdpActuator(session, settle_seconds=0)

    assert actuator.click("Coyote Logistics -> Create Invoice") is True

    click_expression = session.expressions[0]
    assert "clickRowAction" in click_expression
    assert '"Coyote Logistics -> Create Invoice"' in click_expression


def test_click_row_action_passes_row_and_action_separately():
    session = FakeSession()
    actuator = CdpActuator(session, settle_seconds=0)

    assert actuator.click_row_action("Coyote Logistics", "Create Invoice") is True

    click_expression = session.expressions[0]
    assert '"Coyote Logistics","Create Invoice"' in click_expression



def test_navigation_domain_allowlist_guards_the_authenticated_browser():
    # P0: the agent drives a Chrome logged into the TMS; a mis-prompted NAVIGATE must not leave the
    # domain. host_allowed is the hard guard (no live connection needed to test it).
    from freight_recon.cdp_session import CdpBrowserSession

    s = CdpBrowserSession(url_filter="truckingoffice")
    assert s.host_allowed("https://secure.truckingoffice.com/loads") is True
    assert s.host_allowed("/invoices/new") is True                 # relative -> same (allowed) origin
    assert s.host_allowed("") is True                              # no-op
    assert s.host_allowed("https://www.google.com") is False       # off-domain
    assert s.host_allowed("https://evil-truckingoffice.com/x") is False   # not a real label match
    assert s.host_allowed("javascript:alert(1)") is False          # executable pseudo-URLs fail closed
    assert s.host_allowed("data:text/html,hi") is False
    assert s.host_allowed("file:///etc/passwd") is False
    assert s.host_allowed("about:blank") is True                   # harmless no-op/new blank page
    assert s.host_allowed("https://truckingoffice.com") is True

    # navigate() raises on an off-domain target; the actuator turns that into a soft failed action
    import pytest
    with pytest.raises(Exception):
        s.navigate("https://www.google.com")

    # no allowlist configured -> unrestricted (dev)
    assert CdpBrowserSession(url_filter=None).host_allowed("https://anywhere.example.com") is True
