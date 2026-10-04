"""P9 — Financial Reconciliation Result (domain entity #40): a DERIVED comparison of what we agreed to
pay a carrier against what the carrier billed.

### IT IS NEVER AUTHORITATIVE MONEY AND NEVER A SILENT ADJUSTMENT. The result is recomputed from the
Rate Confirmation and the Carrier Payable every time the projection is built. It changes no record.
A mismatch becomes a Conflict or an Exception that a named human owns; nothing here approves,
disputes, rounds away or "tolerates" a difference. There is no tolerance: a discrepancy threshold is
a per-brokerage rule nobody has supplied (NEEDS VALIDATION), and zero is the only value that needs no
permission.

### THE RATE CONFIRMATION IS THE ONLY EXPECTED BUY (V-14 — OPEN). Until a design partner says
otherwise, a number agreed in a text or sitting in a TMS field is a `MODEL_INFERRED` observation. This
module reads its expected side through `Field.current`, which offers only statements a consequential
gate may read, so a guess cannot stand in for an agreement — and when no rate confirmation is on file
the expected side is `absent`, not filled in from the conversation.

### AN ACCESSORIAL IS NOT ITS AUTHORIZATION (CD-5, V-15 — OPEN). A charge the rate confirmation does
not carry is compared against the brokerage's own recorded human authorizations and nothing else. A
carrier saying it was approved is not an authorization. Unmatched means UNRESOLVED and a human decides
— never auto-approved, never auto-disputed.

The legacy `reconciliation.py` (Decimal amounts, outcome classes that gate a button) is the first
implemented surface and stays under its recorded deletion condition in LEGACY-DISPOSITION.md S7. This
module does not call it and nothing calls both.
"""

from __future__ import annotations

from collections.abc import Sequence

from .foundation import EvidenceCondition
from .model import (
    AccessorialAuthorization,
    CarrierMovement,
    CarrierPayable,
    DirectedMoney,
    Discrepancy,
    Field,
    FinancialReconciliationResult,
    RateConfirmation,
    carrier_owed,
    entity_id,
)

CONSISTENT = EvidenceCondition.CONSISTENT.value
ABSENT = EvidenceCondition.ABSENT.value
CONFLICTING = EvidenceCondition.CONFLICTING.value

#: Discrepancy codes that mean "a human already decided this line" and therefore do not make the
#: result DISCREPANT.
NON_BLOCKING_AUTHORIZATIONS: tuple[str, ...] = ("AUTHORIZED",)

COMPARED_FIELDS: tuple[str, ...] = ("linehaul", "fuel", "accessorials")


def _side_condition(fields: Sequence[Field]) -> str:
    """The evidence condition of one side of the comparison: conflicting if ANY of its lines is, absent
    if nothing was said, consistent only when every line is."""
    conditions = [f.condition for f in fields]
    if CONFLICTING in conditions:
        return CONFLICTING
    if all(c == ABSENT for c in conditions):
        return ABSENT
    if all(c == CONSISTENT for c in conditions):
        return CONSISTENT
    return EvidenceCondition.UNKNOWN.value


def _accessorial_map(field: Field) -> dict[str, int]:
    return {line["charge_type"]: int(line["amount_minor"]) for line in (field.value or [])}


def _line_total(linehaul: DirectedMoney, fuel: DirectedMoney, accessorials: dict[str, int]) -> int:
    return linehaul.amount_minor + fuel.amount_minor + sum(accessorials.values())


def _authorization_for(charge_type: str, amount_minor: int,
                       authorizations: Sequence[AccessorialAuthorization],
                       denied: Sequence[str]) -> tuple[str, str]:
    """Is this billed accessorial covered by a recorded HUMAN authorization? Returns
    `(authorization, detail)`. The only thing that makes a line AUTHORIZED is a confirmed
    `AccessorialAuthorization` of the same charge type whose cap covers the amount."""
    if charge_type in denied:
        return "DENIED", "a recorded human denied this accessorial"
    matching = [a for a in authorizations
                if a.charge_type == charge_type and a.lifecycle_state == "CONFIRMED"
                and a.amount_cap.direction == "OUT"]
    if not matching:
        return "UNRESOLVED", ("no recorded human authorization exists for this accessorial; a "
                              "counterparty saying it was approved is not an authorization")
    covering = [a for a in matching if a.amount_cap.amount_minor >= amount_minor]
    if not covering:
        return "EXCEEDS_AUTHORIZATION", "the billed amount is above the authorized cap"
    return "AUTHORIZED", f"authorized by {covering[0].authorized_by} ({covering[0].decision_ref})"


def reconcile_movement(
    *, tenant: str, load_id: str, movement: CarrierMovement,
    rate_confirmation: RateConfirmation | None, payable: CarrierPayable | None,
    authorizations: Sequence[AccessorialAuthorization], denied_charge_types: Sequence[str],
) -> FinancialReconciliationResult | None:
    """Compare one movement's Rate Confirmation with its Carrier Payable. Returns None when there is
    neither — nothing has been agreed and nothing billed, so there is nothing to compare."""
    if rate_confirmation is None and payable is None:
        return None
    reconciliation_id = entity_id(tenant, "financial_reconciliation_result", movement.entity_id)
    sources: list[str] = []
    discrepancies: list[Discrepancy] = []

    expected_fields = ([rate_confirmation.field_of(n) for n in COMPARED_FIELDS]
                       if rate_confirmation is not None else [])
    actual_fields = ([payable.field_of(n) for n in COMPARED_FIELDS]
                     if payable is not None else [])
    expected_condition = _side_condition(expected_fields) if expected_fields else ABSENT
    actual_condition = _side_condition(actual_fields) if actual_fields else ABSENT
    for item in (*expected_fields, *actual_fields):
        sources.extend(f.observation_id for f in item.facts)

    expected_total: DirectedMoney | None = None
    actual_total: DirectedMoney | None = None
    rate_status = rate_confirmation.value("status") if rate_confirmation is not None else None
    expected_basis = "none: no rate confirmation is on file (V-14)"
    if rate_confirmation is not None:
        expected_basis = f"rate_confirmation:{rate_status or 'STATUS_UNKNOWN'}"

    if expected_condition == CONSISTENT and rate_confirmation is not None:
        e_line, e_fuel = rate_confirmation.value("linehaul"), rate_confirmation.value("fuel")
        e_acc = _accessorial_map(rate_confirmation.field_of("accessorials"))
        expected_total = carrier_owed(_line_total(e_line, e_fuel, e_acc), e_line.currency)
    if actual_condition == CONSISTENT and payable is not None:
        a_line, a_fuel = payable.value("linehaul"), payable.value("fuel")
        a_acc = _accessorial_map(payable.field_of("accessorials"))
        actual_total = carrier_owed(_line_total(a_line, a_fuel, a_acc), a_line.currency)
        stated = payable.value("total")
        if stated is not None and stated.amount_minor != actual_total.amount_minor:
            discrepancies.append(Discrepancy(
                code="INVOICE_ARITHMETIC", line="total", expected=actual_total, actual=stated,
                delta_minor=stated.amount_minor - actual_total.amount_minor, authorization="n/a",
                detail="the invoice's stated total is not the sum of its own lines"))

    comparable = (expected_condition == CONSISTENT and actual_condition == CONSISTENT
                  and rate_confirmation is not None and payable is not None)
    if comparable:
        assert rate_confirmation is not None and payable is not None
        currency = e_line.currency
        if a_line.currency != currency:
            discrepancies.append(Discrepancy(
                code="CURRENCY_MISMATCH", line="linehaul", expected=e_line, actual=a_line,
                delta_minor=None, authorization="n/a",
                detail="the invoice and the rate confirmation are in different currencies"))
        else:
            for code, line, exp, act in (("LINEHAUL_MISMATCH", "linehaul", e_line, a_line),
                                         ("FUEL_MISMATCH", "fuel", e_fuel, a_fuel)):
                if exp.amount_minor != act.amount_minor:
                    discrepancies.append(Discrepancy(
                        code=code, line=line, expected=exp, actual=act,
                        delta_minor=act.amount_minor - exp.amount_minor, authorization="n/a",
                        detail=f"billed {line} differs from the rate confirmation"))
            for charge_type in sorted(set(e_acc) | set(a_acc)):
                exp_minor, act_minor = e_acc.get(charge_type), a_acc.get(charge_type)
                if exp_minor is not None and act_minor is not None:
                    if exp_minor != act_minor:
                        discrepancies.append(Discrepancy(
                            code="ACCESSORIAL_AMOUNT_MISMATCH", line=charge_type,
                            expected=carrier_owed(exp_minor, currency),
                            actual=carrier_owed(act_minor, currency),
                            delta_minor=act_minor - exp_minor, authorization="n/a",
                            detail=f"billed {charge_type} differs from the rate confirmation"))
                elif act_minor is not None:
                    authorization, detail = _authorization_for(
                        charge_type, act_minor, authorizations, denied_charge_types)
                    discrepancies.append(Discrepancy(
                        code="ACCESSORIAL_NOT_ON_RATE_CONFIRMATION", line=charge_type,
                        expected=None, actual=carrier_owed(act_minor, currency),
                        delta_minor=act_minor, authorization=authorization, detail=detail))
                else:
                    assert exp_minor is not None
                    discrepancies.append(Discrepancy(
                        code="ACCESSORIAL_NOT_BILLED", line=charge_type,
                        expected=carrier_owed(exp_minor, currency), actual=None,
                        delta_minor=-exp_minor, authorization="n/a",
                        detail=f"the rate confirmation carries {charge_type}; the invoice does not"))
    elif payable is not None and actual_condition == CONSISTENT and expected_condition == ABSENT:
        discrepancies.append(Discrepancy(
            code="EXPECTED_BUY_UNESTABLISHED", line="total", expected=None, actual=actual_total,
            delta_minor=None, authorization="n/a",
            detail=("a carrier invoice is on file and no rate confirmation is: the rate "
                    "confirmation is the only authoritative buy rate (V-14), so there is nothing "
                    "this invoice can be reconciled against")))

    blocking = [d for d in discrepancies if d.authorization not in NON_BLOCKING_AUTHORIZATIONS]
    mismatches = [d for d in blocking if d.code != "EXPECTED_BUY_UNESTABLISHED"]
    if mismatches:
        status = "DISCREPANT"
    elif comparable and not blocking and rate_status == "SIGNED":
        status = "RECONCILED"
    else:
        # Not comparable, awaiting an invoice, a side is conflicting, or the rate confirmation is not
        # SIGNED. Whether an unsigned rate confirmation governs is NEEDS VALIDATION, so an unsigned
        # one never yields RECONCILED.
        status = "COMPUTED"
    return FinancialReconciliationResult(
        reconciliation_id=reconciliation_id, tenant_id=tenant, load_id=load_id,
        movement_id=movement.entity_id, status=status, expected=expected_total,
        expected_condition=expected_condition, expected_basis=expected_basis, actual=actual_total,
        actual_condition=actual_condition, discrepancies=tuple(discrepancies),
        source_observation_ids=tuple(dict.fromkeys(sources)),
        payable_id=payable.entity_id if payable is not None else None)


def blocking_discrepancies(result: FinancialReconciliationResult) -> list[Discrepancy]:
    return [d for d in result.discrepancies if d.authorization not in NON_BLOCKING_AUTHORIZATIONS]
