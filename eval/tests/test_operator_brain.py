"""Tests for the Operator Brain planning core: deterministic observe + injectable planning."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.operator_brain import (  # noqa: E402
    FlowExecutor,
    FlowPlan,
    FlowStep,
    StepAction,
    StepResult,
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


# ----- FlowExecutor (brick 2): drive the plan through tool handlers, gates enforced -----

def _ok_handler(label):
    def h(step, ctx):
        ctx.setdefault("ran", []).append(step.action.value)
        return StepResult(step, ok=True, detail=label)
    return h


def _plan(*actions):
    return FlowPlan(goal="g", steps=[FlowStep(action=a, target="/x") for a in actions])


def test_executor_runs_all_steps_and_completes():
    ctx = {}
    handlers = {a: _ok_handler("ok") for a in StepAction}
    res = FlowExecutor(handlers=handlers).run(
        _plan(StepAction.NAVIGATE, StepAction.DISCOVER_FORM, StepAction.FILL_AND_SUBMIT, StepAction.READBACK_VERIFY),
        ctx,
    )
    assert res.completed and not res.escalated
    assert ctx["ran"] == ["NAVIGATE", "DISCOVER_FORM", "FILL_AND_SUBMIT", "READBACK_VERIFY"]


def test_executor_halts_fail_closed_when_consequential_handler_missing():
    # No handler wired for FILL_AND_SUBMIT -> must halt, never skip/improvise the write.
    handlers = {StepAction.NAVIGATE: _ok_handler("ok")}
    res = FlowExecutor(handlers=handlers).run(_plan(StepAction.NAVIGATE, StepAction.FILL_AND_SUBMIT))
    assert not res.completed
    assert "no handler" in res.note and "FILL_AND_SUBMIT" in res.note


def test_executor_escalate_halts_and_surfaces_to_human():
    handlers = {a: _ok_handler("ok") for a in StepAction}
    plan = FlowPlan(goal="g", steps=[
        FlowStep(action=StepAction.NAVIGATE, target="/x"),
        FlowStep(action=StepAction.ESCALATE, target="cannot find invoice screen"),
        FlowStep(action=StepAction.FILL_AND_SUBMIT, target="/x"),  # must NOT run after escalate
    ])
    ctx = {}
    res = FlowExecutor(handlers=handlers).run(plan, ctx)
    assert res.escalated and not res.completed
    assert res.note == "cannot find invoice screen"
    assert "FILL_AND_SUBMIT" not in ctx.get("ran", [])  # nothing consequential ran past the escalate


def test_executor_halts_on_step_failure_without_replanner():
    def failing(step, ctx):
        return StepResult(step, ok=False, detail="form not found")
    handlers = {a: _ok_handler("ok") for a in StepAction}
    handlers[StepAction.DISCOVER_FORM] = failing
    res = FlowExecutor(handlers=handlers).run(_plan(StepAction.NAVIGATE, StepAction.DISCOVER_FORM, StepAction.FILL_AND_SUBMIT))
    assert not res.completed and not res.escalated
    assert "halted at DISCOVER_FORM" in res.note


def test_executor_replans_once_on_failure_then_succeeds():
    calls = {"discover": 0}

    def flaky_discover(step, ctx):
        calls["discover"] += 1
        return StepResult(step, ok=calls["discover"] > 1, detail="ok" if calls["discover"] > 1 else "transient")
    handlers = {a: _ok_handler("ok") for a in StepAction}
    handlers[StepAction.DISCOVER_FORM] = flaky_discover

    # Re-planner returns a fresh plan (here, the same shape) — the executor restarts from it.
    replan = lambda goal, obs, err: _plan(StepAction.DISCOVER_FORM, StepAction.FILL_AND_SUBMIT)
    res = FlowExecutor(handlers=handlers, replan_fn=replan, max_replans=1).run(
        _plan(StepAction.DISCOVER_FORM, StepAction.FILL_AND_SUBMIT)
    )
    assert res.completed and res.replans == 1
