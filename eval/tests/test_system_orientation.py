"""Tests for system orientation: explore a TMS, learn the layout, store it as recallable SYSTEM facts.

Two surfaces are covered here (P4 EP-8):
  * `orient_observed` - OBSERVATION ONLY, what `scripts/orient_tms.py` uses. The tests below prove
    it works when handed an object that has NOTHING but `observe()`, and prove structurally (AST)
    that it contains no click or navigate call at all.
  * `orient_system` / `orient_record_actions` - the RETAINED click-driven deep walk, for the
    authorized actuator-capable caller behind the effect boundary.
"""

import ast
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon import system_orientation  # noqa: E402
from freight_recon.system_orientation import orient_observed, orient_system  # noqa: E402


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


# --------------------------------------------------------------- EP-8: the observation-only surface


class _ObserveOnly:
    """A `ReadOnlyCdpObserver`-shaped stand-in: it has `observe()` and NOTHING else.

    No `click`, no `navigate`. Any traversal attempt raises AttributeError rather than being
    quietly swallowed, which is the point — this is the shape `scripts/orient_tms.py` holds.
    """

    def __init__(self, screen=None):
        self.calls = 0
        self._screen = screen if screen is not None else {
            "url": "https://x.transporters.io/dashboard",
            "headings": ["Dashboard"],
            "actions": ["New Order"],
            "nav": [{"text": "Orders", "url": "/o"}, {"text": "Finance", "url": "/f"},
                    {"text": "Settings", "url": "/s"}, {"text": "Orders", "url": "/o2"}],
        }

    def observe(self):
        self.calls += 1
        return self._screen


def test_observed_orientation_learns_the_layout_from_one_observation():
    obs = _ObserveOnly()
    facts = orient_observed(obs, _summarizer)
    # It learned the operational sections, dropped the "Settings" chrome and the duplicate "Orders".
    assert "Main navigation sections: Orders, Finance." in facts
    assert any("click-driven" in f for f in facts)
    assert obs.calls == 1, "observation-only orientation must not re-observe per section"


def test_observed_orientation_never_touches_a_traversal_method():
    """The behavioural half of EP-8: handed a surface with no click/navigate, it still works.

    If `orient_observed` ever reached for a traversal method, this raises AttributeError instead of
    passing — there is no try/except in that path to absorb it.
    """
    facts = orient_observed(_ObserveOnly(), _summarizer)
    assert facts, "it must still produce facts from observation alone"


def test_observed_orientation_contains_no_click_or_navigate_call_structurally():
    """The structural half: a docstring promising read-only is not evidence (that WAS EP-8's defect).

    Walk the AST of `orient_observed` and every helper it calls, and prove no forbidden traversal
    primitive is invoked anywhere in that closure.
    """
    forbidden = {"click", "click_row_action", "navigate", "evaluate", "command",
                 "type", "select", "upload_file", "set_file_input"}
    source = inspect.getsource(orient_observed)
    for helper in ("_operational_nav", "_layout_facts", "_summarize_section", "_orient_prompt"):
        source += "\n" + inspect.getsource(getattr(system_orientation, helper))
    called = {n.func.attr for n in ast.walk(ast.parse(source))
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not (called & forbidden), (
        f"the observation-only orientation path invokes {sorted(called & forbidden)} — EP-8 requires "
        "it reach the browser through an API that cannot actuate"
    )


def test_observed_orientation_survives_a_screen_with_nothing_on_it():
    facts = orient_observed(_ObserveOnly({"url": "x", "nav": [], "headings": []}), lambda p: "")
    assert facts == []
