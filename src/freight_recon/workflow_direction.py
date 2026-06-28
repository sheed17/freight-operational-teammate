"""AP vs AR: the canonical direction of a freight back-office workflow.

This is the foundation of the AP/AR split (roadmap piece #1). Two workflows that must NEVER blur in
Slack copy or in which amount is bound:

- **CARRIER_PAYABLE (AP)** — we PAY a carrier. Reconcile the carrier's invoice against the rate
  confirmation to catch overbilling; the approved amount is what we will *pay out*.
- **CUSTOMER_INVOICE (AR)** — we BILL a broker/shipper. Construct our invoice (linehaul + accessorials
  we are owed); the approved amount is what we will *collect*.

The "approved amount" means a different thing in each direction, and the Safety Spine binds whichever
one applies — so the direction has to be explicit and travel with the run, not be inferred downstream.
Everything (reconciliation framing, review payload, Slack button copy, execution verb) threads off this.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum


class WorkflowDirection(str, Enum):
    CARRIER_PAYABLE = "CARRIER_PAYABLE"   # AP — Carrier Payables Teammate
    CUSTOMER_INVOICE = "CUSTOMER_INVOICE"  # AR — Customer Billing Teammate


def is_payable(direction: WorkflowDirection) -> bool:
    return direction == WorkflowDirection.CARRIER_PAYABLE


def is_receivable(direction: WorkflowDirection) -> bool:
    return direction == WorkflowDirection.CUSTOMER_INVOICE


def _money(amount) -> str:
    return f"${Decimal(str(amount)):,.2f}"


def approved_amount_meaning(direction: WorkflowDirection) -> str:
    """Plain-English meaning of the approved amount — distinct per direction so the human knows what
    they are authorizing (pay-out vs collect)."""
    return (
        "the amount we will PAY the carrier"
        if is_payable(direction)
        else "the amount we will BILL the customer"
    )


def approval_action_label(direction: WorkflowDirection, amount, *, tms_name: str | None = None) -> str:
    """The Slack approval button copy — states exactly what will happen, and never blurs AP and AR.

    AP -> 'Approve $3,334.50 carrier payable'
    AR -> 'Create customer invoice for $3,334.50' (optionally naming the TMS)
    """
    money = _money(amount)
    if is_payable(direction):
        return f"Approve {money} carrier payable"
    where = f" in {tms_name}" if tms_name else ""
    return f"Create customer invoice{where} for {money}"


def execution_verb(direction: WorkflowDirection) -> str:
    """How the gated executor narrates the action it is performing."""
    return "Enter carrier payable in TMS" if is_payable(direction) else "Create customer invoice in TMS"


def approval_object(direction: WorkflowDirection) -> str:
    """The concrete financial object a human just approved."""
    return "carrier payable" if is_payable(direction) else "customer invoice"
