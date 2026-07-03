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


def test_money_fence_substitutes_approved_amount_for_rate_and_line_haul_labels():
    act = FakeActuator()
    llm = _scripted_llm([
        {"action": "TYPE", "target": "Line Haul Rate", "value": "9999.00"},
        {"action": "DONE", "why": "done"},
    ])
    res = OperatorAgent(actuator=act, complete=llm, approved_amount="2850.00", approve=lambda a: True).run("invoice")

    assert res.status == "DONE"
    assert ("type", "Line Haul Rate", "2850.00") in act.calls
    assert ("type", "Line Haul Rate", "9999.00") not in act.calls


def test_money_fence_escalates_currency_shaped_write_to_nonmoney_field():
    act = FakeActuator()
    llm = _scripted_llm([
        {"action": "TYPE", "target": "Reference Code", "value": "9999.00"},  # cents -> looks like money
    ])
    res = OperatorAgent(actuator=act, complete=llm, approved_amount="2850.00", approve=lambda a: True).run("invoice")

    assert res.status == "ESCALATED"
    assert "monetary write" in res.note
    assert not [c for c in act.calls if c[0] == "type"]


def test_bare_integer_search_query_is_allowed_not_a_money_write():
    # LIVE-CAUGHT REGRESSION: the agent typed load number "100" into a search box to FIND the load.
    # A bare integer is not currency-shaped — the fence must let it through, not escalate.
    act = FakeActuator()
    llm = _scripted_llm([
        {"action": "TYPE", "target": "load_search_query", "value": "100"},
        {"action": "DONE", "why": "searched"},
    ])
    res = OperatorAgent(actuator=act, complete=llm, approved_amount="2000.00", approve=lambda a: True).run("find load")
    assert res.status == "DONE"
    assert ("type", "load_search_query", "100") in act.calls  # the search typed through, unfenced


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
    # A committed write must be read back before DONE (verify-before-done).
    llm = _scripted_llm([{"action": "CLICK", "target": "Submit"},
                         {"action": "READ", "target": "Invoice #"},
                         {"action": "DONE", "why": "ok"}])
    res = OperatorAgent(actuator=act, complete=llm, approve=lambda a: True).run("invoice")
    assert res.status == "DONE"
    assert ("click", "Submit") in act.calls
    assert ("read", "Invoice #") in act.calls


def test_failed_commit_click_retries_without_second_approval_then_reaches_done():
    class FlakySaveActuator(FakeActuator):
        def __init__(self):
            super().__init__()
            self.clicks = 0

        def click(self, target):
            self.calls.append(("click", target))
            self.clicks += 1
            return self.clicks > 1

    approvals = []
    act = FlakySaveActuator()
    llm = _scripted_llm([
        {"action": "CLICK", "target": "Save invoice"},
        {"action": "CLICK", "target": "Save invoice"},
        {"action": "READ", "target": "Invoice #"},
        {"action": "DONE", "why": "saved"},
    ])

    res = OperatorAgent(
        actuator=act,
        complete=llm,
        approve=lambda a: approvals.append(a) or True,
    ).run("invoice")

    assert res.status == "DONE"
    assert approvals and len(approvals) == 1
    assert act.calls.count(("click", "Save invoice")) == 2


def test_second_consequential_action_after_success_is_not_clicked():
    act = FakeActuator()
    llm = _scripted_llm([
        {"action": "CLICK", "target": "Save invoice"},
        {"action": "CLICK", "target": "Submit payable"},
    ])

    res = OperatorAgent(actuator=act, complete=llm, approve=lambda a: True).run("invoice")

    # Double-pay guard still holds (the second commit never clicks); and because nothing was read back
    # to confirm, it escalates for the human to verify rather than reporting a green DONE.
    assert res.status == "ESCALATED"
    assert "could not confirm" in res.note
    assert ("click", "Save invoice") in act.calls
    assert ("click", "Submit payable") not in act.calls


def test_money_fence_substitutes_a_nonnumeric_placeholder_in_a_money_field():
    # LIVE-CAUGHT REGRESSION: the model types the placeholder "approved amount" (not a number) into the
    # amount field, expecting the runtime to swap in the real figure. The fence must substitute — an
    # earlier value-only check let the literal string through, writing $0.00 to a live invoice.
    act = FakeActuator()
    llm = _scripted_llm([
        {"action": "TYPE", "target": "Invoice Amount", "value": "approved amount"},
        {"action": "DONE", "why": "done"},
    ])
    res = OperatorAgent(actuator=act, complete=llm, approved_amount="2850.00", approve=lambda a: True).run("invoice")
    assert res.status == "DONE"
    assert ("type", "Invoice Amount", "2850.00") in act.calls
    assert ("type", "Invoice Amount", "approved amount") not in act.calls


def test_form_opener_is_not_treated_as_the_commit():
    # LIVE-CAUGHT REGRESSION: "Create Invoice" only OPENS the entry modal, but it matched the commit
    # keyword "create" — burning the single-use approval and the commit-once guard, so the real Submit
    # was refused as "already committed" and the agent reported DONE having never saved.
    act = FakeActuator()
    llm = _scripted_llm([
        {"action": "CLICK", "target": "Create Invoice"},              # opener — must NOT be the commit
        {"action": "TYPE", "target": "Invoice Amount", "value": "x"},
        {"action": "CLICK", "target": "Submit"},                      # the real commit
        {"action": "READ", "target": "Invoice #"},                    # confirm it saved
        {"action": "DONE", "why": "saved"},
    ])
    res = OperatorAgent(actuator=act, complete=llm, approved_amount="2850.00", approve=lambda a: True).run("invoice")
    assert res.status == "DONE"
    assert ("click", "Create Invoice") in act.calls   # the opener ran
    assert ("click", "Submit") in act.calls           # the real commit ran (not blocked as "already committed")


def test_form_opener_runs_without_approval_but_real_commit_gates():
    # The opener must run even with no approver; only the true commit (Submit) escalates.
    act = FakeActuator()
    llm = _scripted_llm([
        {"action": "CLICK", "target": "Create Invoice"},
        {"action": "CLICK", "target": "Submit"},
    ])
    res = OperatorAgent(actuator=act, complete=llm, approved_amount="2850.00", approve=None).run("invoice")
    assert res.status == "ESCALATED" and "needs approval" in res.note
    assert ("click", "Create Invoice") in act.calls   # opener ran unauthenticated (it's not consequential)
    assert ("click", "Submit") not in act.calls       # the real commit was gated


def test_committed_write_without_readback_is_forced_to_confirm_before_done():
    # The agent commits then tries to declare DONE without reading anything back. The runtime forces a
    # confirm-read; once it reads the saved record, DONE is accepted.
    act = FakeActuator()
    llm = _scripted_llm([
        {"action": "CLICK", "target": "Submit"},          # commit
        {"action": "DONE", "why": "assumed saved"},        # premature — no readback yet
        {"action": "READ", "target": "Invoice #"},         # forced confirm-read
        {"action": "DONE", "why": "confirmed"},
    ])
    res = OperatorAgent(actuator=act, complete=llm, approve=lambda a: True).run("invoice")
    assert res.status == "DONE"
    assert ("read", "Invoice #") in act.calls   # it was made to read back before DONE was accepted


def test_committed_write_that_cannot_be_confirmed_escalates_not_done():
    # It commits, is asked to confirm, but never reads back (keeps declaring DONE). That is NOT a verified
    # success — it must surface for a human, never a green DONE. (This is the false-DONE the live run hit.)
    act = FakeActuator()
    llm = _scripted_llm([
        {"action": "CLICK", "target": "Submit"},
        {"action": "DONE", "why": "assumed saved"},
        {"action": "DONE", "why": "still assuming"},
    ])
    res = OperatorAgent(actuator=act, complete=llm, approve=lambda a: True).run("invoice")
    assert res.status == "ESCALATED"
    assert "could not confirm" in res.note


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
