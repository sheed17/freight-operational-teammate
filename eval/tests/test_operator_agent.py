"""Tests for the embedded Operator Agent loop: autonomous driving, money-fenced and gated."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.operator_agent import LiveAction, LiveActionKind, OperatorAgent  # noqa: E402


class FakeActuator:
    def __init__(self):
        self.calls = []
        self.fail = set()  # action kinds to fail

    def observe(self):
        return {"url": "https://tms.test/x", "interactive": [{"kind": "input", "label": "Total Charge"}], "errors": []}

    def navigate(self, url): self.calls.append(("navigate", url)); return True
    def click(self, target): self.calls.append(("click", target)); return "click" not in self.fail
    def type(self, target, value): self.calls.append(("type", target, value)); return True
    def select(self, target, option): self.calls.append(("select", target, option)); return True
    def read(self, target): self.calls.append(("read", target)); return "read-value"


def _scripted_llm(actions):
    """Return a completer that emits the given action dicts in order, then DONE."""
    seq = list(actions)

    def complete(_prompt):
        if seq:
            return json.dumps(seq.pop(0))
        return json.dumps({"action": "DONE", "why": "finished"})

    return complete


def test_agent_drives_a_sequence_to_done():
    act = FakeActuator()
    llm = _scripted_llm([
        {"action": "NAVIGATE", "target": "https://tms.test/new"},
        {"action": "TYPE", "target": "Customer", "value": "Acme"},
        {"action": "CLICK", "target": "Continue"},
        {"action": "DONE", "why": "order created"},
    ])
    res = OperatorAgent(actuator=act, complete=llm, approve=lambda a: True).run("create an order")
    assert res.status == "DONE"
    assert ("navigate", "https://tms.test/new") in act.calls
    assert ("type", "Customer", "Acme") in act.calls


def test_money_fence_substitutes_approved_amount_for_the_models_number():
    act = FakeActuator()
    # The model tries to type its OWN amount (9999) into a money field.
    llm = _scripted_llm([{"action": "TYPE", "target": "Total Charge", "value": "9999.00"},
                         {"action": "DONE", "why": "done"}])
    OperatorAgent(actuator=act, complete=llm, approved_amount="2850.00", approve=lambda a: True).run("invoice")
    typed = [c for c in act.calls if c[0] == "type"]
    # The runtime substituted the approved amount; the model's 9999 never reached the form.
    assert typed == [("type", "Total Charge", "2850.00")]


def test_money_field_without_approved_amount_escalates():
    act = FakeActuator()
    llm = _scripted_llm([{"action": "TYPE", "target": "Amount", "value": "5"}])
    res = OperatorAgent(actuator=act, complete=llm, approved_amount=None).run("invoice")
    assert res.status == "ESCALATED" and "no approved amount" in res.note
    assert not [c for c in act.calls if c[0] == "type"]  # nothing typed into the money field


def test_consequential_action_requires_approval():
    act = FakeActuator()
    llm = _scripted_llm([{"action": "CLICK", "target": "Save invoice"}])
    # No approver -> the committing click must not run; agent escalates.
    res = OperatorAgent(actuator=act, complete=llm, approve=None).run("invoice")
    assert res.status == "ESCALATED" and "needs approval" in res.note
    assert ("click", "Save invoice") not in act.calls  # never committed without approval


def test_consequential_action_runs_when_approved():
    act = FakeActuator()
    llm = _scripted_llm([{"action": "CLICK", "target": "Submit"}, {"action": "DONE", "why": "ok"}])
    res = OperatorAgent(actuator=act, complete=llm, approve=lambda a: True).run("invoice")
    assert res.status == "DONE"
    assert ("click", "Submit") in act.calls


def test_escalate_and_max_steps_fail_closed():
    act = FakeActuator()
    esc = OperatorAgent(actuator=act, complete=_scripted_llm([{"action": "ESCALATE", "target": "cannot find screen"}])).run("x")
    assert esc.status == "ESCALATED" and "cannot find screen" in esc.note

    # a model that never says DONE -> bounded, fails closed
    loop_llm = lambda _p: json.dumps({"action": "READ", "target": "x"})
    res = OperatorAgent(actuator=act, complete=loop_llm, max_steps=3).run("x")
    assert res.status == "FAILED" and "within 3 steps" in res.note


def test_unknown_model_action_escalates():
    res = OperatorAgent(actuator=FakeActuator(), complete=lambda _p: json.dumps({"action": "DROP_TABLE"})).run("x")
    assert res.status == "ESCALATED"


def test_agent_escalates_when_stuck_repeating_instead_of_looping():
    # The real failure mode observed live: the model clicks "Close" forever. The loop guard must
    # stop it (escalate) rather than grind to max_steps.
    act = FakeActuator()
    res = OperatorAgent(
        actuator=act,
        complete=lambda _p: json.dumps({"action": "CLICK", "target": "Close", "why": "close modal"}),
        max_steps=20, stuck_after=3,
    ).run("find the invoices")
    assert res.status == "ESCALATED" and "stuck" in res.note
    # It stopped early, not after 20 identical clicks.
    assert len([c for c in act.calls if c == ("click", "Close")]) <= 3
