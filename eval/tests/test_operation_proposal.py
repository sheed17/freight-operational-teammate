"""Tests for the inbound->Slack-button->live-browser bridge: the Approve button decodes to the exact
gated operation and actually drives the OperationRouter."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

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


class _Result:
    ok = True


class _Poster:
    def __init__(self):
        self.messages = []

    def post_message(self, *, channel, payload):
        self.messages.append({"channel": channel, **payload})
        return _Result()


class _LoadsActuator:
    def __init__(self, observation):
        self._observation = observation
        self.session = self
        self.evaluated = []

    def evaluate(self, expression):
        self.evaluated.append(expression)

    def observe(self):
        return self._observation


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


def test_ready_to_bill_from_loads_table_extracts_delivered_not_invoiced_loads():
    from freight_recon.operation_proposal import ready_to_bill_from_loads_table

    obs = {"tables": [{
        "headers": ["Load #", "Trip #", "Status", "Customer", "Total"],
        "rows": [
            {"cells": ["Load #", "Trip #", "Status", "Customer", "Total"]},           # header echoed as a row
            {"cells": ["100", "1000", "Invoiced", "Coyote Logistics", "$2,000.00"]},  # already billed -> skip
            {"cells": ["101", "1001", "Dispatched", "Acme Foods", "$3,450.50"]},      # in transit -> NOT billable
            {"cells": ["102", "1002", "Delivered", "Echo Global", "$1,200.00"]},      # ready to bill
        ],
    }]}
    ready = ready_to_bill_from_loads_table(obs)
    assert {r["load_ref"] for r in ready} == {"102"}   # only delivered-and-not-invoiced; dispatched excluded
    r102 = next(r for r in ready if r["load_ref"] == "102")
    assert r102["customer"] == "Echo Global" and r102["amount"] == "1200.00"  # $ and comma stripped


def test_ready_to_bill_reads_amount_when_total_column_drifts():
    # Real TruckingOffice loads table: the amount renders under a column left of the 'Total' header,
    # whose cell holds the row's action links. The parser must find the money cell, not trust position.
    from freight_recon.operation_proposal import ready_to_bill_from_loads_table

    obs = {"tables": [{
        "headers": ["Load #", "Status", "Customer", "POD", "Total"],
        "rows": [
            {"cells": ["102", "Delivered", "Echo Global", "$1,200.00", "View Edit Copy"]},  # $ under BOL
        ],
    }]}
    ready = ready_to_bill_from_loads_table(obs)
    assert len(ready) == 1 and ready[0]["amount"] == "1200.00"  # money cell found despite the drift


def test_ready_to_bill_strips_truncation_ellipsis_from_customer():
    # TMS list views truncate long names ("Echo Global Logistics" -> "Echo Global L..."); the trailing
    # ellipsis must not reach the bill-to search step.
    from freight_recon.operation_proposal import ready_to_bill_from_loads_table

    obs = {"tables": [{
        "headers": ["Load #", "Status", "Customer", "Total"],
        "rows": [{"cells": ["101", "Delivered", "Echo Global L...", "$2,500.00"]}],
    }]}
    ready = ready_to_bill_from_loads_table(obs)
    assert ready[0]["customer"] == "Echo Global L"  # ellipsis stripped, clean search prefix


def test_proposals_from_tms_loads_builds_ar_buttons_from_a_loads_table():
    from freight_recon.operation_proposal import proposals_from_tms_loads

    obs = {"tables": [{
        "headers": ["Load #", "Status", "Customer", "Total"],
        "rows": [
            {"cells": ["100", "Invoiced", "Coyote", "$2,000.00"]},        # already billed -> no button
            {"cells": ["101", "Dispatched", "Zeta Co", "$9,999.00"]},     # in transit -> no button
            {"cells": ["102", "Delivered", "Acme Foods", "$3,450.50"]},   # ready to bill -> button
        ],
    }]}
    proposals = proposals_from_tms_loads(obs, signer=_SIGNER, channel_id="C")
    assert len(proposals) == 1
    approval = _verify_operation_approval_value(_button_value(proposals[0]), _SIGNER)
    assert approval.intent.params["lane"] == "raise_invoice"
    assert approval.intent.params["customer"] == "Acme Foods"
    assert approval.intent.params["load_ref"] == "102"
    assert approval.approved_amount == "3450.50"        # the load's Total, deterministic


def test_pod_gate_only_bills_delivered_loads_with_paperwork_attached():
    # Owner SOP: "always attach the POD before billing a customer." With require_pod, a delivered load
    # whose delivery-document column is empty gets NO money button; one with paperwork does.
    from freight_recon.operation_proposal import (
        loads_missing_pod, proposals_from_tms_loads, ready_to_bill_from_loads_table,
    )

    obs = {"tables": [{
        "headers": ["Load #", "Status", "Customer", "POD", "Total"],
        "rows": [
            {"cells": ["101", "Delivered", "Echo Global", "", "$2,500.00"]},          # no POD attached
            {"cells": ["102", "Delivered", "Acme Foods", "POD.pdf", "$3,450.50"]},     # POD attached
        ],
    }]}
    # reader records the tri-state paperwork signal
    by_ref = {r["load_ref"]: r for r in ready_to_bill_from_loads_table(obs)}
    assert by_ref["101"]["has_pod"] is False and by_ref["102"]["has_pod"] is True

    # require_pod: only the load with paperwork is billed
    gated = proposals_from_tms_loads(obs, signer=_SIGNER, channel_id="C", require_pod=True)
    assert len(gated) == 1
    assert _verify_operation_approval_value(_button_value(gated[0]), _SIGNER).intent.params["load_ref"] == "102"

    # the un-paperworked delivered load surfaces as an exception, never a money button
    missing = loads_missing_pod(obs)
    assert [m["load_ref"] for m in missing] == ["101"]

    # without the gate (default), both delivered loads bill as before — no behavior change
    assert len(proposals_from_tms_loads(obs, signer=_SIGNER, channel_id="C")) == 2


def test_pod_gate_is_noop_when_the_list_has_no_paperwork_column():
    # If the loads list can't show POD status, has_pod is unknown (None) — the gate can't fabricate a
    # signal. require_pod then bills nothing (fail-closed to the SOP); default still bills.
    from freight_recon.operation_proposal import (
        loads_missing_pod, proposals_from_tms_loads, ready_to_bill_from_loads_table,
    )

    obs = {"tables": [{
        "headers": ["Load #", "Status", "Customer", "Total"],
        "rows": [{"cells": ["102", "Delivered", "Acme Foods", "$3,450.50"]}],
    }]}
    assert ready_to_bill_from_loads_table(obs)[0]["has_pod"] is None
    assert loads_missing_pod(obs) == []                                   # unknown != proven-missing
    assert len(proposals_from_tms_loads(obs, signer=_SIGNER, channel_id="C")) == 1
    assert len(proposals_from_tms_loads(obs, signer=_SIGNER, channel_id="C", require_pod=True)) == 0


def test_pod_gate_treats_money_under_paperwork_header_as_unknown_not_attached():
    # Column drift can put the Total amount under a BOL/POD-looking header. A dollar value is not proof
    # of delivery paperwork; with require_pod, this must fail closed instead of creating a money button.
    from freight_recon.operation_proposal import proposals_from_tms_loads, ready_to_bill_from_loads_table

    obs = {"tables": [{
        "headers": ["Load #", "Status", "Customer", "BOL", "Total"],
        "rows": [{"cells": ["102", "Delivered", "Echo Global", "$1,200.00", "View Edit Copy"]}],
    }]}

    ready = ready_to_bill_from_loads_table(obs)
    assert ready[0]["amount"] == "1200.00"
    assert ready[0]["has_pod"] is None
    assert len(proposals_from_tms_loads(obs, signer=_SIGNER, channel_id="C", require_pod=True)) == 0


def test_bol_or_generic_docs_column_does_not_satisfy_pod_gate():
    from freight_recon.operation_proposal import proposals_from_tms_loads, ready_to_bill_from_loads_table

    obs = {"tables": [{
        "headers": ["Load #", "Status", "Customer", "BOL", "Total"],
        "rows": [{"cells": ["102", "Delivered", "Echo Global", "BOL.pdf", "$1,200.00"]}],
    }]}

    ready = ready_to_bill_from_loads_table(obs)
    assert ready[0]["has_pod"] is None
    assert len(proposals_from_tms_loads(obs, signer=_SIGNER, channel_id="C", require_pod=True)) == 0


def test_live_ar_cycle_requires_pod_and_posts_missing_pod_exception():
    from propose_ar_from_tms import _cycle

    obs = {"tables": [{
        "headers": ["Load #", "Status", "Customer", "POD", "Total"],
        "rows": [{"cells": ["101", "Delivered", "Echo Global", "", "$2,500.00"]}],
    }]}
    poster = _Poster()

    posted = _cycle(
        act=_LoadsActuator(obs),
        signer=_SIGNER,
        channel="C",
        loads_url="https://tms.test/loads",
        store=None,
        lock=None,
        live=True,
        poster=poster,
    )

    assert posted == 0
    assert len(poster.messages) == 1
    assert "Missing POD" in poster.messages[0]["text"]
    assert "Approve & run" not in json.dumps(poster.messages[0])


def test_live_ar_cycle_default_pod_gate_blocks_unknown_pod_status():
    from propose_ar_from_tms import _cycle

    obs = {"tables": [{
        "headers": ["Load #", "Status", "Customer", "Total"],
        "rows": [{"cells": ["101", "Delivered", "Echo Global", "$2,500.00"]}],
    }]}
    poster = _Poster()

    posted = _cycle(
        act=_LoadsActuator(obs),
        signer=_SIGNER,
        channel="C",
        loads_url="https://tms.test/loads",
        store=None,
        lock=None,
        live=True,
        poster=poster,
    )

    assert posted == 0
    assert len(poster.messages) == 1
    assert "POD status unknown" in poster.messages[0]["text"]
    assert "Approve & run" not in json.dumps(poster.messages[0])


def test_live_ar_cycle_can_disable_pod_gate_for_dev_only():
    from propose_ar_from_tms import _cycle

    obs = {"tables": [{
        "headers": ["Load #", "Status", "Customer", "Total"],
        "rows": [{"cells": ["101", "Delivered", "Echo Global", "$2,500.00"]}],
    }]}
    poster = _Poster()

    posted = _cycle(
        act=_LoadsActuator(obs),
        signer=_SIGNER,
        channel="C",
        loads_url="https://tms.test/loads",
        store=None,
        lock=None,
        live=True,
        poster=poster,
        require_pod=False,
    )

    assert posted == 1
    assert len(poster.messages) == 1
    assert "Approve & run" in json.dumps(poster.messages[0])


def test_detail_page_pod_classifier_counts_delivery_proof_not_rate_con():
    # When the loads list can't show POD, the load's FileSafe attachments resolve it. On TruckingOffice
    # a signed BOL is the delivery proof; a rate con is only the booking agreement and must NOT satisfy
    # the billing gate.
    from freight_recon.operation_proposal import pod_present_in_attachments, has_pod_from_detail

    assert pod_present_in_attachments(["Signed BOL - load 102.pdf"]) is True
    assert pod_present_in_attachments(["proof of delivery.pdf"]) is True
    assert pod_present_in_attachments(["POD_102.jpg", "Rate Confirmation.pdf"]) is True   # POD among others
    assert pod_present_in_attachments(["Rate Confirmation.pdf"]) is False                  # booking doc only
    assert pod_present_in_attachments(["ratecon.pdf"]) is False
    assert pod_present_in_attachments([]) is False                                          # nothing attached
    # tri-state: an unreadable detail page stays unknown (None), never a billing-greenlight False
    assert has_pod_from_detail([], page_readable=False) is None
    assert has_pod_from_detail(["POD.pdf"], page_readable=True) is True
    assert has_pod_from_detail(["Rate Con.pdf"], page_readable=True) is False


def test_no_button_for_non_lane_or_amountless_assessments():
    # Missing-backup has no bounded lane -> chase a doc, not an Approve-and-run button.
    chase = InboxAssessment(ThreadState.MISSING_BACKUP, actionable=True, suggested_lane=None,
                            suggested_action="missing POD", load_ref="LD-1", confidence=0.9, rationale="")
    assert proposal_from_assessment(chase, _SIGNER, channel_id="C", approved_amount="100") is None

    # A money lane with no human-approvable figure -> never post a run button.
    ready = InboxAssessment(ThreadState.READY_TO_BILL, actionable=True, suggested_lane="raise_invoice",
                            suggested_action="ready", load_ref="LD-2", confidence=0.8, rationale="")
    assert proposal_from_assessment(ready, _SIGNER, channel_id="C", approved_amount=None) is None
