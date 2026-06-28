"""Tests for the AP/AR direction vocabulary — the foundation of the AP vs AR split."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.workflow_direction import (  # noqa: E402
    WorkflowDirection,
    approval_action_label,
    approved_amount_meaning,
    execution_verb,
    is_payable,
    is_receivable,
)

AP = WorkflowDirection.CARRIER_PAYABLE
AR = WorkflowDirection.CUSTOMER_INVOICE


def test_direction_predicates_are_exclusive():
    assert is_payable(AP) and not is_receivable(AP)
    assert is_receivable(AR) and not is_payable(AR)


def test_approval_copy_never_blurs_ap_and_ar():
    ap = approval_action_label(AP, "3334.50")
    ar = approval_action_label(AR, "3334.50")
    assert ap == "Approve $3,334.50 carrier payable"
    assert ar == "Create customer invoice for $3,334.50"
    # The two directions must be unmistakably different copy for the same amount.
    assert ap != ar
    assert "payable" in ap and "payable" not in ar
    assert "customer invoice" in ar and "customer invoice" not in ap


def test_ar_copy_can_name_the_tms():
    assert approval_action_label(AR, "3334.50", tms_name="TruckingOffice") == (
        "Create customer invoice in TruckingOffice for $3,334.50"
    )


def test_approved_amount_meaning_distinct_per_direction():
    assert "PAY" in approved_amount_meaning(AP)
    assert "BILL" in approved_amount_meaning(AR)
    assert approved_amount_meaning(AP) != approved_amount_meaning(AR)


def test_execution_verb_distinct_per_direction():
    assert execution_verb(AP) == "Enter carrier payable in TMS"
    assert execution_verb(AR) == "Create customer invoice in TMS"


def test_money_formatting_has_thousands_separator():
    assert approval_action_label(AP, "4172") == "Approve $4,172.00 carrier payable"
