"""Tests for system orientation: explore a TMS, learn the layout, store it as recallable SYSTEM facts."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.system_orientation import orient_system  # noqa: E402


class _FakeActuator:
    """A tiny fake TMS: a home page with nav; each section observes to its own screen."""

    def __init__(self):
        self.clicked = []
        self._screen = "home"
        self.screens = {
            "home": {"url": "https://x.transporters.io/dashboard", "headings": ["Dashboard"],
                     "actions": [], "nav": [{"text": "Orders", "url": "/o"}, {"text": "Finance", "url": "/f"}]},
            "Orders": {"headings": ["Orders"], "actions": ["View Orders", "Add Order"], "nav": []},
            "Finance": {"headings": ["Finance"], "actions": ["Aged Debtors", "Invoices"], "nav": []},
        }

    def observe(self):
        return self.screens[self._screen]

    def click(self, target):
        self.clicked.append(target)
        if target in self.screens:
            self._screen = target
        return True


def _summarizer(prompt):
    # pretend to be the model: echo a one-liner naming the section from the prompt
    for name in ("Orders", "Finance"):
        if f"'{name}' area" in prompt:
            return f"{name}: this is the {name.lower()} area."
    return "section: unknown."


def test_orientation_learns_structure_and_each_section():
    act = _FakeActuator()
    facts = orient_system(act, _summarizer)
    joined = " ".join(facts)
    # structural facts
    assert "Main navigation sections: Orders, Finance." in facts
    assert any("click-driven" in f for f in facts)
    # it visited each section and learned a per-section fact
    assert "Orders" in act.clicked and "Finance" in act.clicked
    assert any("orders area" in f for f in facts) and any("finance area" in f for f in facts)


def test_orientation_is_read_only_and_never_crashes_on_a_bad_section():
    class _Flaky(_FakeActuator):
        def click(self, target):
            if target == "Finance":
                raise RuntimeError("won't open")
            return super().click(target)

    facts = orient_system(_Flaky(), _summarizer)  # must not raise
    assert any("Orders" in f for f in facts)  # good section still learned


def test_deep_orientation_learns_a_records_action_menus():
    # A record page whose "Billing" menu, when clicked, reveals "Raise invoice" — the deeper layer.
    from freight_recon.system_orientation import orient_record_actions

    class _RecordActuator:
        def __init__(self):
            self.state = "record"
            self.screens = {
                "record": {"headings": ["Order 1002"], "actions": ["Billing", "Transport", "Overview"]},
                "billing_open": {"headings": ["Order 1002"],
                                 "actions": ["Billing", "Transport", "Overview", "Raise invoice", "Record payment"]},
            }
        def navigate(self, url): self.state = "record"; return True
        def observe(self): return self.screens[self.state]
        def click(self, t):
            if t == "Billing": self.state = "billing_open"
            return True

    def menu_picker(prompt):
        return '{"menus": ["Billing"]}'  # model identifies Billing as the action menu

    facts = orient_record_actions(_RecordActuator(), menu_picker, record_url="https://x/orders/view/1002")
    joined = " ".join(facts)
    assert "action menus are: Billing" in joined
    assert "Billing' menu offers" in joined and "Raise invoice" in joined  # learned the invoice path!


def test_orientation_with_no_nav_returns_empty_gracefully():
    class _Empty:
        def observe(self): return {"url": "x", "nav": [], "actions": []}
        def click(self, t): return True
    assert orient_system(_Empty(), _summarizer) == []
