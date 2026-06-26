"""Bridge real vision extraction into deterministic reconciliation inputs.

Extraction fills the **invoice side only** (what the carrier billed). The rate / source-of-truth
side of the load is left untouched, so reconciliation compares *what the carrier billed* against
*what we agreed* — which is the whole point. Deterministic Python still makes the money decision;
this module never decides money.

It also surfaces the two things a human must see before a low-quality read can move money:

- ``low_confidence_required`` — any required field (load/PRO, linehaul, total) the model was unsure
  about, so the caller can force human review even when the math happens to match.
- ``link_ok`` — whether the extracted load/PRO actually matches the load this packet is linked to;
  a mismatch means the invoice may belong to a different load and must be reviewed.

This is duck-typed on the extraction object (the validated ``Confident[...]`` model) so workflow code
stays decoupled from the LLM/render stack; the caller injects the extractor.
"""

from __future__ import annotations

from decimal import Decimal
import re
from typing import Any

from .reconciliation import (
    ChargeLine,
    FreightLoadForReconciliation,
    ReconciliationOutcome,
    ReconciliationResult,
    money,
    reconcile_load,
)

# The required fields whose low confidence must force human review (non-negotiable #4).
REQUIRED_CONFIDENCE_FIELDS = ("load_or_pro", "linehaul_amount", "total_amount")


def apply_extraction_to_load(
    source_load: FreightLoadForReconciliation,
    extraction_obj: Any,
    *,
    confidence_threshold: float = 0.85,
) -> tuple[FreightLoadForReconciliation, list[str], bool]:
    """Overlay a real extracted invoice onto the source-of-truth load.

    Returns ``(recon_load, low_confidence_required, link_ok)``. ``recon_load`` has the real extracted
    invoice side and the original rate side; the caller reconciles it and, if there are low-confidence
    required fields or a link mismatch, forces ``NEEDS_REVIEW``.
    """
    obj = extraction_obj
    invoice_accessorials = [
        ChargeLine(name=str(item.name), amount=money(item.amount))
        for item in (getattr(obj, "accessorials", None) or [])
    ]
    recon_load = source_load.model_copy(
        update={
            "invoice_number": str(obj.invoice_number.value),
            "carrier": str(obj.carrier_name.value),
            "invoice_linehaul": money(obj.linehaul_amount.value),
            "invoice_fuel": money(obj.fuel_surcharge.value),
            "invoice_accessorials": invoice_accessorials,
        }
    )

    low_confidence_required = sorted(
        name
        for name in REQUIRED_CONFIDENCE_FIELDS
        if getattr(obj, name).confidence < confidence_threshold
    )
    link_ok = _norm(obj.load_or_pro.value) == _norm(source_load.load_id)
    return recon_load, low_confidence_required, link_ok


def serialize_invoice_side(recon_load: FreightLoadForReconciliation, *, total_amount: Any) -> dict:
    """Serialize the extracted invoice side for durable audit, so the review card can render it.

    This is what the carrier actually billed (extracted), kept separate from the source-of-truth
    rate side. Persisted on the run; rehydrated by :func:`apply_extracted_invoice` for the Slack card
    and money buttons.
    """
    return {
        "invoice_number": recon_load.invoice_number,
        "carrier": recon_load.carrier,
        "invoice_linehaul": str(recon_load.invoice_linehaul),
        "invoice_fuel": str(recon_load.invoice_fuel),
        "invoice_accessorials": [
            {"name": charge.name, "amount": str(charge.amount)} for charge in recon_load.invoice_accessorials
        ],
        "stated_total": str(total_amount),
    }


def apply_extracted_invoice(
    source_load: FreightLoadForReconciliation, payload: dict
) -> FreightLoadForReconciliation:
    """Overlay a persisted extracted invoice side onto the source-of-truth load for the review card."""
    return source_load.model_copy(
        update={
            "invoice_number": payload.get("invoice_number") or source_load.invoice_number,
            "carrier": payload.get("carrier") or source_load.carrier,
            "invoice_linehaul": money(payload["invoice_linehaul"]),
            "invoice_fuel": money(payload["invoice_fuel"]),
            "invoice_accessorials": [
                ChargeLine(name=item["name"], amount=money(item["amount"]))
                for item in payload.get("invoice_accessorials", [])
            ],
        }
    )


def reconciliation_from_extraction(
    source_load: FreightLoadForReconciliation,
    extraction: Any,
    *,
    seen_invoice_keys: set[tuple[str, str]] | None = None,
    confidence_threshold: float = 0.85,
) -> tuple[dict, ReconciliationResult]:
    """Build an extraction audit payload and deterministic reconciliation result.

    Shared by the single-PDF workflow and mailbox workflow so real extraction is gated the same way
    everywhere: low confidence, load-link mismatch, and self-inconsistent stated totals always force
    human review.
    """
    if getattr(extraction, "extraction", None) is None:
        payload = {
            "source": "vision_extraction",
            "model": getattr(extraction, "model", None),
            "error": getattr(extraction, "error", "extraction returned no result"),
        }
        result = ReconciliationResult(
            load_id=source_load.load_id,
            invoice_number=source_load.invoice_number or "",
            carrier=source_load.carrier,
            outcome=ReconciliationOutcome.NEEDS_REVIEW,
            reasons=[f"extraction failed: {getattr(extraction, 'error', 'no result')}"],
            needs_human_review=True,
        )
        return payload, result

    try:
        recon_load, low_confidence, link_ok = apply_extraction_to_load(
            source_load, extraction.extraction, confidence_threshold=confidence_threshold
        )
    except Exception as exc:  # noqa: BLE001 - malformed/partial extraction must fail closed
        payload = {
            "source": "vision_extraction",
            "model": getattr(extraction, "model", None),
            "error": f"invalid extraction values: {type(exc).__name__}: {exc}",
        }
        result = ReconciliationResult(
            load_id=source_load.load_id,
            invoice_number=source_load.invoice_number or "",
            carrier=source_load.carrier,
            outcome=ReconciliationOutcome.NEEDS_REVIEW,
            reasons=[payload["error"]],
            needs_human_review=True,
        )
        return payload, result

    stated_total = _decimal_or(
        getattr(getattr(extraction.extraction, "total_amount", None), "value", None),
        recon_load.invoice_linehaul + recon_load.invoice_fuel
        + sum(charge.amount for charge in recon_load.invoice_accessorials),
    )
    payload = {
        "invoice_number": recon_load.invoice_number,
        "carrier": recon_load.carrier,
        "source": "vision_extraction",
        "model": getattr(extraction, "model", None),
        "low_confidence_required": low_confidence,
        "link_ok": link_ok,
        "extracted_invoice": serialize_invoice_side(recon_load, total_amount=stated_total),
    }
    result = reconcile_load(recon_load, seen_invoice_keys=seen_invoice_keys)

    line_item_total = recon_load.invoice_linehaul + recon_load.invoice_fuel + sum(
        charge.amount for charge in recon_load.invoice_accessorials
    )
    total_mismatch = abs(stated_total - line_item_total) > Decimal("0.01")
    if low_confidence or not link_ok or total_mismatch:
        reasons = list(result.reasons)
        if low_confidence:
            reasons.append(f"low-confidence extraction on required field(s): {', '.join(low_confidence)}")
        if not link_ok:
            reasons.append("extracted load/PRO does not match the linked load id")
        if total_mismatch:
            reasons.append(f"carrier invoice total ${stated_total} does not equal its line items ${line_item_total}")
        result = result.model_copy(
            update={
                "outcome": ReconciliationOutcome.NEEDS_REVIEW,
                "reasons": reasons,
                "needs_human_review": True,
            }
        )
    return payload, result


def _norm(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", str(value or "")).upper()


def _decimal_or(value: Any, fallback: Decimal) -> Decimal:
    if value is None:
        return Decimal(fallback)
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001 - invalid extracted totals fall back to line-item sum
        return Decimal(fallback)
