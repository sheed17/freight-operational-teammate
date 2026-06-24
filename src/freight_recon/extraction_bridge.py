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

import re
from typing import Any

from .reconciliation import ChargeLine, FreightLoadForReconciliation, money

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


def _norm(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", str(value or "")).upper()
