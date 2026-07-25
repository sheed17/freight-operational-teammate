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


# ----- brick 3: real-tool handlers (wired to discovery + injected gated write) -----

_FORM_DOM = {
    "url": "https://t.test/orders/new", "action": "/o", "submits": ["Save"],
    "fields": [
        {"selector": "[name=amt]", "name": "amt", "id": "", "tag": "input", "type": "text",
         "label": "Total Charge", "required": False, "options": []},
        {"selector": "[name=cust]", "name": "cust", "id": "", "tag": "input", "type": "text",
         "label": "Customer", "required": True, "options": []},
    ],
}


class ToolSession:
    def __init__(self, dom):
        self.dom = dom
        self.nav = []

    def navigate(self, url):
        self.nav.append(url)

    def evaluate(self, expression):
        return self.dom


def _writable_mapping(_prompt):
    return json.dumps({"fields": {"amount": "[name=amt]", "bill_to": "[name=cust]"}, "submit_label": "Save"})


def test_build_tool_handlers_drives_full_flow_into_the_gated_write():
    from freight_recon.operator_brain import build_tool_handlers
    s = ToolSession(_FORM_DOM)
    captured = {}

    def gated_submit(ctx):
        captured["form"] = ctx.get("form")
        captured["customer_id"] = ctx.get("customer_id")
        return StepResult(FlowStep(StepAction.FILL_AND_SUBMIT), ok=True, detail="gated write verified")

    handlers = build_tool_handlers(
        session=s, complete=_writable_mapping, resolve_customer=lambda n: "C1", gated_submit=gated_submit,
    )
    plan = FlowPlan(goal="invoice", steps=[
        FlowStep(StepAction.NAVIGATE, "https://t.test/orders/new"),
        FlowStep(StepAction.DISCOVER_FORM, "https://t.test/orders/new"),
        FlowStep(StepAction.RESOLVE_CUSTOMER, "Acme Brokerage"),
        FlowStep(StepAction.FILL_AND_SUBMIT, "https://t.test/orders/new"),
        FlowStep(StepAction.READBACK_VERIFY),
    ])
    res = FlowExecutor(handlers=handlers).run(plan, {})
    assert res.completed
    # The gated write was reached only AFTER discovery + customer resolution populated the context.
    assert captured["customer_id"] == "C1"
    assert captured["form"] is not None and captured["form"].is_writable()
    assert "https://t.test/orders/new" in s.nav


def test_fill_and_submit_fails_closed_without_form_or_customer():
    from freight_recon.operator_brain import build_tool_handlers
    handlers = build_tool_handlers(
        session=ToolSession(_FORM_DOM), complete=_writable_mapping, resolve_customer=lambda n: "C1",
        gated_submit=lambda ctx: StepResult(FlowStep(StepAction.FILL_AND_SUBMIT), ok=True, detail="should not run"),
    )
    no_form = handlers[StepAction.FILL_AND_SUBMIT](FlowStep(StepAction.FILL_AND_SUBMIT), {})
    assert not no_form.ok and "no discovered form" in no_form.detail
    no_cust = handlers[StepAction.FILL_AND_SUBMIT](FlowStep(StepAction.FILL_AND_SUBMIT), {"form": object()})
    assert not no_cust.ok and "no resolved customer" in no_cust.detail


def test_resolve_and_discover_fail_closed():
    from freight_recon.operator_brain import build_tool_handlers
    # resolver returns nothing -> fail closed
    h = build_tool_handlers(session=ToolSession(_FORM_DOM), complete=_writable_mapping,
                            resolve_customer=lambda n: None,
                            gated_submit=lambda ctx: StepResult(FlowStep(StepAction.FILL_AND_SUBMIT), ok=True))
    r = h[StepAction.RESOLVE_CUSTOMER](FlowStep(StepAction.RESOLVE_CUSTOMER, "Ghost LLC"), {})
    assert not r.ok and "no customer resolved" in r.detail

    # a form with no amount field -> model maps amount null -> not writable -> step fails
    dom_no_amount = {"url": "u", "action": "/o", "submits": ["Save"],
                     "fields": [{"selector": "[name=cust]", "name": "cust", "id": "", "tag": "input",
                                 "type": "text", "label": "Customer", "required": True, "options": []}]}
    h2 = build_tool_handlers(session=ToolSession(dom_no_amount),
                             complete=lambda _p: json.dumps({"fields": {"amount": None, "bill_to": "[name=cust]"}}),
                             resolve_customer=lambda n: "C1",
                             gated_submit=lambda ctx: StepResult(FlowStep(StepAction.FILL_AND_SUBMIT), ok=True))
    ctx = {}
    rd = h2[StepAction.DISCOVER_FORM](FlowStep(StepAction.DISCOVER_FORM, "u"), ctx)
    assert not rd.ok and "not writable" in rd.detail
