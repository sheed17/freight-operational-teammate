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

