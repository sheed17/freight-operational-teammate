"""Deterministic invoice reconciliation.

The LLM reads documents; this module makes money/workflow decisions with plain Python.
It compares invoice-claimed values against rate-confirmed values and packet evidence, then
returns a structured outcome with human-readable reasons.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .workflow_direction import WorkflowDirection

MONEY = Decimal("0.01")


class ReconciliationOutcome(str, Enum):
    MATCHED = "MATCHED"
    VARIANCE = "VARIANCE"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    DUPLICATE = "DUPLICATE"
    FAILED = "FAILED"


class ChargeLine(BaseModel):
    name: str
    amount: Decimal
    authorized: bool = True
    backup_document: str | None = None

    @property
    def key(self) -> str:
        return normalize_charge_name(self.name)


class FreightLoadForReconciliation(BaseModel):
    workflow_direction: WorkflowDirection = WorkflowDirection.CARRIER_PAYABLE
    load_id: str
    pro_number: str | None = None
    bol_number: str | None = None
    manifest_number: str | None = None
    invoice_number: str
    carrier: str
    carrier_mc: str | None = None
    customer: str | None = None
    shipper: str | None = None
    consignee: str | None = None
    origin: str | None = None
    destination: str | None = None
    equipment: str | None = None
    commodity: str | None = None
    pickup_date: str | None = None
    delivery_date: str | None = None
    rate_linehaul: Decimal
    rate_fuel: Decimal
    invoice_linehaul: Decimal
    invoice_fuel: Decimal
    rate_accessorials: list[ChargeLine] = Field(default_factory=list)
    invoice_accessorials: list[ChargeLine] = Field(default_factory=list)
    scenario: str | None = None
    expected_outcome: str | None = None
    variance_reasons: list[str] = Field(default_factory=list)
    documents: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "FreightLoadForReconciliation":
        return cls.model_validate(raw)


class ReconciliationResult(BaseModel):
    workflow_direction: WorkflowDirection = WorkflowDirection.CARRIER_PAYABLE
    load_id: str
    invoice_number: str
    carrier: str
    outcome: ReconciliationOutcome
    reasons: list[str] = Field(default_factory=list)
    variance_amount: Decimal = Decimal("0.00")
    needs_human_review: bool = False


def money(value: Decimal | str | int | float) -> Decimal:
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def normalize_charge_name(name: str) -> str:
    return " ".join(name.strip().lower().replace("_", " ").replace("-", " ").split())


def _amount_delta(invoice_value: Decimal, rate_value: Decimal) -> Decimal:
    return money(invoice_value - rate_value)


def _accessorial_map(lines: list[ChargeLine]) -> dict[str, ChargeLine]:
    return {line.key: line for line in lines}


def reconcile_load(
    load: FreightLoadForReconciliation,
    *,
    workflow_direction: WorkflowDirection | str | None = None,
    seen_invoice_keys: set[tuple[str, str, str]] | None = None,
    tolerance: Decimal = Decimal("0.00"),
) -> ReconciliationResult:
    """Classify a single load's invoice against rate-confirmed values and packet evidence."""
    direction = WorkflowDirection(workflow_direction or load.workflow_direction)
    tolerance = money(tolerance)
    reasons: list[str] = []
    review_reasons: list[str] = []
    variance_amount = Decimal("0.00")

    invoice_key = (
        direction.value,
        load.carrier.strip().lower(),
        load.invoice_number.strip().lower(),
    )
    if seen_invoice_keys is not None:
        if invoice_key in seen_invoice_keys:
            return ReconciliationResult(
                workflow_direction=direction,
                load_id=load.load_id,
                invoice_number=load.invoice_number,
                carrier=load.carrier,
                outcome=ReconciliationOutcome.DUPLICATE,
                reasons=[_duplicate_reason(load, direction)],
                needs_human_review=True,
            )
        seen_invoice_keys.add(invoice_key)

    linehaul_delta = _amount_delta(load.invoice_linehaul, load.rate_linehaul)
    if abs(linehaul_delta) > tolerance:
        variance_amount += linehaul_delta
        reasons.append(
            f"linehaul mismatch: invoice {load.invoice_linehaul} vs rate {load.rate_linehaul}"
        )

    fuel_delta = _amount_delta(load.invoice_fuel, load.rate_fuel)
    if abs(fuel_delta) > tolerance:
        variance_amount += fuel_delta
        reasons.append(f"fuel mismatch: invoice {load.invoice_fuel} vs rate {load.rate_fuel}")

    rate_accessorials = _accessorial_map(load.rate_accessorials)
    invoice_accessorials = _accessorial_map(load.invoice_accessorials)

    for name, invoice_charge in invoice_accessorials.items():
        rate_charge = rate_accessorials.get(name)
        if rate_charge is None:
            variance_amount += money(invoice_charge.amount)
            reasons.append(
                f"unauthorized accessorial: {invoice_charge.name} {invoice_charge.amount} not on rate confirmation"
            )
            continue

        delta = _amount_delta(invoice_charge.amount, rate_charge.amount)
        if abs(delta) > tolerance:
            variance_amount += delta
            reasons.append(
                f"accessorial mismatch: {invoice_charge.name} invoice {invoice_charge.amount} "
                f"vs rate {rate_charge.amount}"
            )

        if _requires_backup(invoice_charge) and not _has_backup(load.documents, invoice_charge):
            review_reasons.append(f"missing backup for {invoice_charge.name} charge {invoice_charge.amount}")

    for name, rate_charge in rate_accessorials.items():
        if name not in invoice_accessorials:
            review_reasons.append(f"authorized {rate_charge.name} charge missing from invoice")

    if "pod" not in load.documents and "pod_dirty" not in load.documents:
        review_reasons.append("missing POD from document packet")

    if reasons:
        return ReconciliationResult(
            workflow_direction=direction,
            load_id=load.load_id,
            invoice_number=load.invoice_number,
            carrier=load.carrier,
            outcome=ReconciliationOutcome.VARIANCE,
            reasons=reasons + review_reasons,
            variance_amount=money(variance_amount),
            needs_human_review=True,
        )

    if review_reasons:
        return ReconciliationResult(
            workflow_direction=direction,
            load_id=load.load_id,
            invoice_number=load.invoice_number,
            carrier=load.carrier,
            outcome=ReconciliationOutcome.NEEDS_REVIEW,
            reasons=review_reasons,
            needs_human_review=True,
        )

    return ReconciliationResult(
        workflow_direction=direction,
        load_id=load.load_id,
        invoice_number=load.invoice_number,
        carrier=load.carrier,
        outcome=ReconciliationOutcome.MATCHED,
        reasons=["invoice matches rate confirmation and required packet evidence"],
        needs_human_review=False,
    )


def reconcile_many(loads: list[FreightLoadForReconciliation]) -> list[ReconciliationResult]:
    seen_invoice_keys: set[tuple[str, str, str]] = set()
    return [reconcile_load(load, seen_invoice_keys=seen_invoice_keys) for load in loads]


def _duplicate_reason(load: FreightLoadForReconciliation, direction: WorkflowDirection) -> str:
    if direction == WorkflowDirection.CUSTOMER_INVOICE:
        customer = load.customer or "customer"
        return f"duplicate customer invoice number {load.invoice_number} for {customer}"
    return f"duplicate carrier invoice number {load.invoice_number} for carrier {load.carrier}"


def _requires_backup(charge: ChargeLine) -> bool:
    return charge.key in {"lumper", "detention", "layover", "stop off", "stopoff"}


def _has_backup(documents: dict[str, str], charge: ChargeLine) -> bool:
    if charge.backup_document and charge.backup_document in documents:
        return True
    if charge.key == "lumper":
        return "lumper_receipt" in documents or "lumper_receipt_dirty" in documents
    if charge.key == "detention":
        return "detention_backup" in documents or "detention_backup_dirty" in documents
    if charge.key in {"stop off", "stopoff"}:
        return "rate_confirmation" in documents or "rate_confirmation_dirty" in documents
    return False
