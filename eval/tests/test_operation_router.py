"""Tests for the request->agent->result bridge (Version B): bounded lanes, gates, refusal, receipts."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.operation_router import (  # noqa: E402
    OperationLane,
    OperationRouter,
    freight_lanes,
)
from freight_recon.operator_agent import OperatorAgent  # noqa: E402
from freight_recon.slack_delegate import CommandIntent, CommandKind  # noqa: E402


class FakeActuator:
    def __init__(self):
        self.calls = []

    def observe(self):
        return {"url": "https://tms.test/x", "interactive": [], "errors": []}

    def navigate(self, url): self.calls.append(("navigate", url)); return True
    def click(self, target): self.calls.append(("click", target)); return True
    def type(self, target, value): self.calls.append(("type", target, value)); return True
    def select(self, target, option): self.calls.append(("select", target, option)); return True
    def read(self, target): self.calls.append(("read", target)); return "INV-4912"


def _scripted_llm(actions):
    seq = list(actions)

    def complete(_prompt):
        return json.dumps(seq.pop(0)) if seq else json.dumps({"action": "DONE", "why": "finished"})

    return complete


def _operate(summary, params=None):
    return CommandIntent(kind=CommandKind.OPERATE, summary=summary, params=params or {})


def _agent_factory(llm, actuator=None):
    act = actuator or FakeActuator()

    def build_agent(*, approved_amount=None, approve=None):
        return OperatorAgent(actuator=act, complete=llm, approved_amount=approved_amount, approve=approve)

    build_agent.actuator = act
    return build_agent


def test_known_lane_drives_agent_to_done():
    llm = _scripted_llm([
        {"action": "NAVIGATE", "target": "https://tms.test/invoices/new"},
        {"action": "TYPE", "target": "Total Charge", "value": "0"},
        {"action": "CLICK", "target": "Save invoice"},
        {"action": "READ", "target": "invoice number"},
        {"action": "DONE", "why": "invoice INV-4912 created"},
    ])
    build_agent = _agent_factory(llm)
    router = OperationRouter(
        lanes=freight_lanes(), build_agent=build_agent,
        approved_amount_for=lambda _i: "2850.00",
    )
    res = router.run(_operate("invoice today's delivered load for Acme"), approve=lambda a: True)
    assert res.status == "DONE" and res.lane == "raise_invoice"
    # Money fence: the approved amount reached the form, not a model-chosen number.
    assert ("type", "Total Charge", "2850.00") in build_agent.actuator.calls
    assert "✅ Done" in res.to_slack()


def test_unknown_request_is_refused_not_improvised():
    # The core Version-B boundary: a request with no known lane must NOT free-form a goal.
    build_agent = _agent_factory(_scripted_llm([]))
    router = OperationRouter(lanes=freight_lanes(), build_agent=build_agent, approved_amount_for=lambda _i: "1")
    res = router.run(_operate("reorganize the whole accounting system however you see fit"))
    assert res.status == "REFUSED" and res.lane is None
    assert build_agent.actuator.calls == []  # the agent never ran
    assert "won't improvise" in res.to_slack()


def test_money_lane_without_approved_amount_escalates_at_the_door():
    build_agent = _agent_factory(_scripted_llm([]))
    router = OperationRouter(lanes=freight_lanes(), build_agent=build_agent, approved_amount_for=lambda _i: None)
    res = router.run(_operate("invoice the delivered load for Acme"))
    assert res.status == "ESCALATED" and res.lane == "raise_invoice"
    assert "no human-approved amount" in res.note
    assert build_agent.actuator.calls == []  # never drove without an approved amount


def test_agent_escalation_propagates_as_result():
    llm = _scripted_llm([{"action": "ESCALATE", "target": "cannot find the customer field"}])
    build_agent = _agent_factory(llm)
    router = OperationRouter(lanes=freight_lanes(), build_agent=build_agent, approved_amount_for=lambda _i: "100.00")
    res = router.run(_operate("invoice the load for Acme"), approve=lambda a: True)
    assert res.status == "ESCALATED" and res.lane == "raise_invoice"
    assert "✋ I need you" in res.to_slack()


def test_payable_lane_matches_and_binds_amount():
    llm = _scripted_llm([{"action": "DONE", "why": "payable recorded"}])
    build_agent = _agent_factory(llm)
    router = OperationRouter(lanes=freight_lanes(), build_agent=build_agent, approved_amount_for=lambda _i: "1200.00")
    res = router.run(_operate("record the carrier payable for load LD-5001"), approve=lambda a: True)
    assert res.status == "DONE" and res.lane == "record_payable"


def test_explicit_lane_param_overrides_keyword_matching():
    llm = _scripted_llm([{"action": "DONE", "why": "ok"}])
    build_agent = _agent_factory(llm)
    router = OperationRouter(lanes=freight_lanes(), build_agent=build_agent, approved_amount_for=lambda _i: "5.00")
    res = router.run(CommandIntent(CommandKind.OPERATE, "handle this", {"lane": "raise_invoice"}),
                     approve=lambda a: True)
    assert res.lane == "raise_invoice"


def test_non_money_lane_runs_without_an_amount():
    lane = OperationLane("status_check", ("check status",), lambda i: "check the load status", requires_amount=False)
    llm = _scripted_llm([{"action": "DONE", "why": "checked"}])
    build_agent = _agent_factory(llm)
    router = OperationRouter(lanes=[lane], build_agent=build_agent, approved_amount_for=lambda _i: None)
    res = router.run(_operate("check status of LD-5001"))
    assert res.status == "DONE" and res.lane == "status_check"
