"""Tests for the inbound->Slack-button->live-browser bridge: the Approve button decodes to the exact
gated operation and actually drives the OperationRouter."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.action_callback import _verify_operation_approval_value  # noqa: E402
from freight_recon.delivery import DeliverySigner  # noqa: E402
from freight_recon.inbox_brain import InboxAssessment, ThreadState  # noqa: E402
from freight_recon.operation_proposal import (  # noqa: E402
    APPROVE_ACTION_ID,
    build_operation_proposal_message,
    proposal_from_assessment,
)
from freight_recon.operation_router import OperationRouter, freight_lanes  # noqa: E402
from freight_recon.operator_agent import OperatorAgent  # noqa: E402
from freight_recon.slack_delegate import CommandIntent, CommandKind  # noqa: E402

_SIGNER = DeliverySigner(b"bridge-secret")


def _button_value(message):
    return message["blocks"][1]["elements"][0]["value"]


class _FakeActuator:
    def __init__(self): self.calls = []
    def observe(self): return {"url": "x", "interactive": [], "errors": []}
    def navigate(self, u): return True
    def click(self, t): self.calls.append(("click", t)); return True
    def type(self, t, v): self.calls.append(("type", t, v)); return True
    def select(self, t, o): return True
    def read(self, t): return "INV-1"


def test_proposal_button_decodes_to_the_exact_gated_operation():
    intent = CommandIntent(CommandKind.OPERATE, "Invoice Acme for LD-9", {"lane": "raise_invoice", "customer": "Acme"})
    msg = build_operation_proposal_message(intent, _SIGNER, approved_amount="2850.00",
                                           channel_id="C_OPS", thread_ts="1.1")
    assert msg["blocks"][1]["elements"][0]["action_id"] == APPROVE_ACTION_ID
    approval = _verify_operation_approval_value(_button_value(msg), _SIGNER)
    assert approval is not None
    assert approval.intent.params["lane"] == "raise_invoice"
    assert approval.approved_amount == "2850.00"
    assert approval.expected_channel_id == "C_OPS" and approval.expected_thread_ts == "1.1"


def test_tapping_the_button_drives_the_router_money_fenced():
    # Simulate the full bridge: emit button -> decode (the "tap") -> run the router with the bound amount.
    intent = CommandIntent(CommandKind.OPERATE, "Invoice Acme", {"lane": "raise_invoice", "customer": "Acme"})
    msg = build_operation_proposal_message(intent, _SIGNER, approved_amount="2850.00", channel_id="C")
    approval = _verify_operation_approval_value(_button_value(msg), _SIGNER)

    actuator = _FakeActuator()
    seq = [{"action": "TYPE", "target": "Total Charge", "value": "9999"},
           {"action": "READ", "target": "invoice"},  # money run confirms before DONE
           {"action": "DONE", "why": "ok"}]
    def complete(_p):
        return json.dumps(seq.pop(0)) if seq else json.dumps({"action": "DONE", "why": "done"})

    def build_agent(*, approved_amount=None, approve=None, prepare_only=False):
        return OperatorAgent(actuator=actuator, complete=complete, approved_amount=approved_amount,
                             approve=approve, prepare_only=prepare_only)

    router = OperationRouter(lanes=freight_lanes(), build_agent=build_agent,
                             approved_amount_for=lambda i: i.params.get("approved_amount"))
    # The callback injects the signed amount into params before running; mirror that.
    intent2 = approval.intent
    intent2.params["approved_amount"] = approval.approved_amount
    res = router.run(intent2, approve=lambda a: True)
    assert res.status == "DONE" and res.lane == "raise_invoice"
    # Money fence: the bound $2,850 reached the form, never the model's 9999.
    assert ("type", "Total Charge", "2850.00") in actuator.calls


def test_proposal_from_ready_to_bill_assessment():
    a = InboxAssessment(ThreadState.READY_TO_BILL, actionable=True, suggested_lane="raise_invoice",
                        suggested_action="LD-9 is ready to invoice Acme", load_ref="LD-9",
                        confidence=0.8, rationale="complete")
    msg = proposal_from_assessment(a, _SIGNER, channel_id="C_OPS", approved_amount="2850.00",
                                   params={"customer": "Acme"})
    assert msg is not None
    approval = _verify_operation_approval_value(_button_value(msg), _SIGNER)
    assert approval.intent.params["lane"] == "raise_invoice"
    assert approval.intent.params["customer"] == "Acme" and approval.intent.params["load_ref"] == "LD-9"


def test_auto_emit_only_for_clean_matches_with_a_deterministic_amount():
    from types import SimpleNamespace

    from freight_recon.operation_proposal import proposals_for_clean_matches

    loads = {
        "LD-1": SimpleNamespace(load_id="LD-1", carrier="TQL"),
        "LD-2": SimpleNamespace(load_id="LD-2", carrier="Echo"),
        "LD-3": SimpleNamespace(load_id="LD-3", carrier="Coyote"),
    }
    packet_results = [
        SimpleNamespace(load_id="LD-1", outcome="MATCHED"),    # clean -> button
        SimpleNamespace(load_id="LD-2", outcome="VARIANCE"),   # overbilled -> NO button (human review)
        SimpleNamespace(load_id="LD-3", outcome="MATCHED"),    # clean but amount resolver returns None
    ]
    amounts = {"LD-1": "2700.00", "LD-3": None}
    proposals = proposals_for_clean_matches(
        packet_results, loads, signer=_SIGNER, channel_id="C_OPS",
        amount_for_load=lambda load: amounts.get(load.load_id),
    )
    assert len(proposals) == 1  # only the clean match with a known amount
    approval = _verify_operation_approval_value(_button_value(proposals[0]), _SIGNER)
    assert approval.intent.params["lane"] == "record_payable"
    assert approval.intent.params["carrier"] == "TQL" and approval.approved_amount == "2700.00"


def test_proposals_for_ready_to_bill_makes_an_ar_invoice_button_per_delivered_load():
    from types import SimpleNamespace

    from freight_recon.operation_proposal import proposals_for_ready_to_bill

    loads = [
        SimpleNamespace(load_id="LD-1", customer="Coyote Logistics", delivery_date="2026-06-20"),  # delivered -> button
        SimpleNamespace(load_id="LD-2", customer="Echo", delivery_date=None),                      # not delivered -> none
        SimpleNamespace(load_id="LD-3", customer="TQL", delivery_date="2026-06-21"),               # delivered, amount None
    ]
    amounts = {"LD-1": "2450.00", "LD-3": None}
    proposals = proposals_for_ready_to_bill(
        loads, signer=_SIGNER, channel_id="C_OPS",
        amount_for_load=lambda load: amounts.get(load.load_id),
    )
    assert len(proposals) == 1  # only the delivered load with a known agreed amount
    approval = _verify_operation_approval_value(_button_value(proposals[0]), _SIGNER)
    assert approval.intent.params["lane"] == "raise_invoice"          # AR lane, not AP
    assert approval.intent.params["customer"] == "Coyote Logistics"   # bill the CUSTOMER
    assert approval.approved_amount == "2450.00"


def test_ready_to_bill_from_loads_table_extracts_non_invoiced_loads():
    from freight_recon.operation_proposal import ready_to_bill_from_loads_table

    obs = {"tables": [{
        "headers": ["Load #", "Trip #", "Status", "Customer", "Total"],
        "rows": [
            {"cells": ["Load #", "Trip #", "Status", "Customer", "Total"]},           # header echoed as a row
            {"cells": ["100", "1000", "Invoiced", "Coyote Logistics", "$2,000.00"]},  # already billed -> skip
            {"cells": ["101", "1001", "Dispatched", "Acme Foods", "$3,450.50"]},      # ready to bill
            {"cells": ["102", "1002", "Delivered", "Echo Global", "$1,200.00"]},      # ready to bill
        ],
    }]}
    ready = ready_to_bill_from_loads_table(obs)
    assert {r["load_ref"] for r in ready} == {"101", "102"}      # invoiced + header row excluded
    r101 = next(r for r in ready if r["load_ref"] == "101")
    assert r101["customer"] == "Acme Foods" and r101["amount"] == "3450.50"  # $ and comma stripped


def test_proposals_from_tms_loads_builds_ar_buttons_from_a_loads_table():
    from freight_recon.operation_proposal import proposals_from_tms_loads

    obs = {"tables": [{
        "headers": ["Load #", "Status", "Customer", "Total"],
        "rows": [
            {"cells": ["100", "Invoiced", "Coyote", "$2,000.00"]},        # already billed -> no button
            {"cells": ["101", "Dispatched", "Acme Foods", "$3,450.50"]},  # ready to bill -> button
        ],
    }]}
    proposals = proposals_from_tms_loads(obs, signer=_SIGNER, channel_id="C")
    assert len(proposals) == 1
    approval = _verify_operation_approval_value(_button_value(proposals[0]), _SIGNER)
    assert approval.intent.params["lane"] == "raise_invoice"
    assert approval.intent.params["customer"] == "Acme Foods"
    assert approval.intent.params["load_ref"] == "101"
    assert approval.approved_amount == "3450.50"        # the load's Total, deterministic


def test_no_button_for_non_lane_or_amountless_assessments():
    # Missing-backup has no bounded lane -> chase a doc, not an Approve-and-run button.
    chase = InboxAssessment(ThreadState.MISSING_BACKUP, actionable=True, suggested_lane=None,
                            suggested_action="missing POD", load_ref="LD-1", confidence=0.9, rationale="")
    assert proposal_from_assessment(chase, _SIGNER, channel_id="C", approved_amount="100") is None

    # A money lane with no human-approvable figure -> never post a run button.
    ready = InboxAssessment(ThreadState.READY_TO_BILL, actionable=True, suggested_lane="raise_invoice",
                            suggested_action="ready", load_ref="LD-2", confidence=0.8, rationale="")
    assert proposal_from_assessment(ready, _SIGNER, channel_id="C", approved_amount=None) is None
