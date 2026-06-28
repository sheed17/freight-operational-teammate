"""Tests for the Operator Brain planning core: deterministic observe + injectable planning."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.operator_brain import (  # noqa: E402
    FlowPlan,
    StepAction,
    observe,
    plan_flow,
)


# What the deterministic _OBSERVE_JS would yield on a transporters.io-like dashboard.
_OBS = {
    "url": "https://example-tms.test/dashboard",
    "nav": [
        {"text": "Add Order", "href": "/orders/new"},
        {"text": "Non-Invoiced", "href": "/finance/uninvoiced"},
        {"text": "Invoices", "href": "/order/invoices"},
        {"text": "Add Customer", "href": "/customer/create"},
    ],
    "headings": ["Welcome to the TMS"],
    "has_form": False,
}


class FakeSession:
    def __init__(self, obs):
        self.obs = obs
        self.navigated = []

    def navigate(self, url):
        self.navigated.append(url)

    def evaluate(self, expression):
        return self.obs


def test_observe_reads_nav_and_state_deterministically():
    s = FakeSession(_OBS)
    obs = observe(s, "https://example-tms.test/dashboard")
    assert s.navigated == ["https://example-tms.test/dashboard"]
    assert obs.url.endswith("/dashboard")
    assert {n["href"] for n in obs.nav} >= {"/orders/new", "/order/invoices"}
    # The observation is serialized for the planner with nav + headings.
    assert "navigation" in obs.to_prompt_json() and "/orders/new" in obs.to_prompt_json()


def test_plan_flow_builds_typed_ordered_plan():
    obs = observe(FakeSession(_OBS), "u")

    # A fake Brain that reasoned the multi-step order->invoice flow this system requires.
    def fake_complete(prompt: str) -> str:
        assert "GOAL" in prompt and "/orders/new" in prompt  # it was shown the goal + the nav
        return json.dumps({
            "steps": [
                {"action": "NAVIGATE", "target": "/orders/new", "why": "create the order first"},
                {"action": "RESOLVE_CUSTOMER", "target": "Acme Brokerage", "why": "bill-to"},
                {"action": "DISCOVER_FORM", "target": "/orders/new", "why": "map the order form"},
                {"action": "FILL_AND_SUBMIT", "target": "/orders/new", "why": "submit the order/invoice"},
                {"action": "READBACK_VERIFY", "why": "confirm it landed"},
            ],
            "notes": ["invoicing here is order-driven"],
        })

    plan = plan_flow("Raise a customer invoice for Acme Brokerage", obs, complete=fake_complete)
    assert isinstance(plan, FlowPlan)
    assert [s.action for s in plan.steps][:2] == [StepAction.NAVIGATE, StepAction.RESOLVE_CUSTOMER]
    assert plan.is_actionable()


def test_consequential_steps_are_flagged_for_gating():
    obs = observe(FakeSession(_OBS), "u")
    plan = plan_flow(
        "invoice",
        obs,
        complete=lambda _p: json.dumps({"steps": [
            {"action": "NAVIGATE", "target": "/x"},
            {"action": "FILL_AND_SUBMIT", "target": "/x"},
        ]}),
    )
    cons = plan.consequential_steps()
    # Exactly the write step is consequential — the executor must route it through the gates/approval.
    assert len(cons) == 1 and cons[0].action == StepAction.FILL_AND_SUBMIT
    assert not [s for s in plan.steps if s.action == StepAction.NAVIGATE][0].is_consequential()


def test_plan_flow_ignores_unknown_actions_and_handles_fenced_json():
    obs = observe(FakeSession(_OBS), "u")

    def fenced(_p):
        return "```json\n" + json.dumps({"steps": [
            {"action": "NAVIGATE", "target": "/x"},
            {"action": "DELETE_EVERYTHING", "target": "/x"},  # outside the vocabulary -> dropped
            {"action": "ESCALATE", "target": "cannot find invoice screen"},
        ]}) + "\n```"

    plan = plan_flow("invoice", obs, complete=fenced)
    actions = [s.action for s in plan.steps]
    assert StepAction.NAVIGATE in actions and StepAction.ESCALATE in actions
    assert all(isinstance(a, StepAction) for a in actions)  # no untyped/unknown actions survived
    assert len(plan.steps) == 2  # the unknown action was filtered out


def test_escalate_only_plan_is_actionable():
    obs = observe(FakeSession(_OBS), "u")
    plan = plan_flow("impossible", obs, complete=lambda _p: json.dumps(
        {"steps": [{"action": "ESCALATE", "target": "no invoice capability on this plan"}]}))
    assert plan.is_actionable()  # escalation is a valid outcome
    assert not plan.consequential_steps()  # but nothing consequential runs
