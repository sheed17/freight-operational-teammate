"""Tests for the Inbox Brain: thread-state assessment, lane suggestion, injection-safe integration."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.brain_operator import BrainOperator, DecisionKind, Trigger, TriggerSource  # noqa: E402
from freight_recon.inbox_brain import (  # noqa: E402
    InboxItem,
    ThreadState,
    assess_inbox_item,
    build_inbox_classifier,
)
def _item(**kw):
    return InboxItem(**kw)


def test_missing_pod_is_chased_not_billed():
    a = assess_inbox_item(_item(load_ref="LD-1", subject="Invoice 900 – Load LD-1",
                                doc_types=["carrier_invoice"],
                                delivered_doc_types=["rate_confirmation", "carrier_invoice"]))
    assert a.thread_state == ThreadState.MISSING_BACKUP
    assert "pod" in a.suggested_action.lower() and a.suggested_lane is None and a.actionable


def test_fully_documented_load_is_ready_to_bill_and_suggests_invoice_lane():
    a = assess_inbox_item(_item(load_ref="LD-2", subject="POD attached – Load LD-2",
                                doc_types=["pod"],
                                delivered_doc_types=["rate_confirmation", "carrier_invoice", "pod"]))
    # carrier_invoice is not in THIS email, backup is complete -> ready to bill the customer.
    assert a.thread_state == ThreadState.READY_TO_BILL
    assert a.suggested_lane == "raise_invoice" and a.actionable


def test_new_carrier_invoice_goes_to_reconcile_not_a_write_lane():
    a = assess_inbox_item(_item(load_ref="LD-3", subject="Carrier invoice – Load LD-3",
                                doc_types=["carrier_invoice"],
                                delivered_doc_types=["rate_confirmation", "carrier_invoice", "pod"]))
    assert a.thread_state == ThreadState.NEW_CARRIER_INVOICE and a.suggested_lane is None


def test_dispute_reply_is_flagged_for_human():
    a = assess_inbox_item(_item(load_ref="LD-4", subject="Re: short pay on LD-4",
                                body="We are disputing the $250 detention deduction.",
                                delivered_doc_types=["rate_confirmation", "carrier_invoice", "pod"]))
    assert a.thread_state == ThreadState.DISPUTE_REPLY and a.suggested_lane is None and a.actionable


def test_ambiguous_item_uses_model_only_to_assess():
    # No docs, neutral subject -> deterministic core is unsure; model elevates it.
    def fake_llm(_p):
        return '{"thread_state": "INFORMATIONAL", "action": "fyi only", "confidence": 0.7}'

    a = assess_inbox_item(_item(load_ref="LD-5", subject="quick question",
                                required_doc_types=[]), complete=fake_llm)
    assert a.thread_state == ThreadState.INFORMATIONAL and not a.actionable


def test_measured_accuracy_on_labelled_synthetic_set():
    # A small labelled corpus mirroring the email_corpus scenarios; the deterministic core must hit it.
    cases = [
        (_item(load_ref="A", delivered_doc_types=["rate_confirmation", "carrier_invoice"]),
         ThreadState.MISSING_BACKUP),  # missing_pod
        (_item(load_ref="B", doc_types=["pod"],
               delivered_doc_types=["rate_confirmation", "carrier_invoice", "pod"]),
         ThreadState.READY_TO_BILL),   # complete
        (_item(load_ref="C", doc_types=["carrier_invoice"],
               delivered_doc_types=["rate_confirmation", "carrier_invoice", "pod"]),
         ThreadState.NEW_CARRIER_INVOICE),
        (_item(load_ref="D", subject="short pay dispute",
               delivered_doc_types=["rate_confirmation", "carrier_invoice", "pod"]),
         ThreadState.DISPUTE_REPLY),
        (_item(load_ref="E", delivered_doc_types=["rate_confirmation"]),
         ThreadState.MISSING_BACKUP),  # missing carrier_invoice + pod
        (_item(load_ref="F", doc_types=["rate_confirmation"],
               delivered_doc_types=["rate_confirmation", "carrier_invoice", "pod"]),
         ThreadState.READY_TO_BILL),
    ]
    correct = sum(1 for item, label in cases if assess_inbox_item(item).thread_state == label)
    assert correct / len(cases) >= 0.9  # measured accuracy on the labelled set


def test_inbox_classifier_is_injection_safe_in_brain_operator():
    # Inbound work can only ever PROPOSE — never execute — even when actionable.
    classify = build_inbox_classifier()
    brain = BrainOperator(
        allowed_users=("U1",), allowed_channel="C1",
        interpret=lambda _t: None,
        classify=classify,
        plan_capability=lambda summary: (None, f"plan: {summary}"),
        on_query=lambda i: "q", on_control=lambda i: "c",
    )
    trigger = Trigger(
        source=TriggerSource.INBOUND_DOC,
        text="POD attached",
        payload={"load_ref": "LD-9", "doc_types": ["pod"],
                 "delivered_doc_types": ["rate_confirmation", "carrier_invoice", "pod"]},
    )
    decision = brain.dispatch(trigger)
    # Actionable, but never auto-executed: it surfaces as a proposal (or escalation), not an action.
    assert decision.kind in (DecisionKind.PROPOSE, DecisionKind.ESCALATE)


def test_assess_packet_bridges_mailbox_doc_state():
    from freight_recon.inbox_brain import assess_packet

    # Missing POD -> chase it.
    a = assess_packet("LD-7", missing=["pod"])
    assert a.thread_state == ThreadState.MISSING_BACKUP
    # Complete packet (carrier invoice present) -> reconcile, not improvise.
    b = assess_packet("LD-8", missing=[])
    assert b.thread_state == ThreadState.NEW_CARRIER_INVOICE


def test_unactionable_inbound_is_ignored():
    classify = build_inbox_classifier()
    brain = BrainOperator(
        allowed_users=("U1",), allowed_channel="C1",
        interpret=lambda _t: None, classify=classify,
        plan_capability=lambda s: (None, s), on_query=lambda i: "q", on_control=lambda i: "c",
    )
    trigger = Trigger(source=TriggerSource.INBOUND_DOC, text="newsletter",
                      payload={"required_doc_types": [], "subject": "weekly news"})
    assert brain.dispatch(trigger).kind == DecisionKind.IGNORE
