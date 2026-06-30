"""ROI instrumentation: turn what Neyma DID into dollars and a receipt the owner trusts.

This is the product-side moat from the strategy work: a freight owner buys provable money, not
"AI." So every consequential thing the agent does leaves an auditable **receipt**, and the receipts
roll up into a **value digest** (caught $, recovered $, invoiced $, hours saved). It reads the same
event log the safety spine already writes — it invents no new source of truth:

- AP side (carrier-invoice reconciliation): overbilling *flagged* and *recovered* come from
  ``summary.DailySummary`` (recovered = only on a verified readback, never on a mere approval).
- Agent-operation side (the OperationRouter runs): invoices raised, payables recorded, and the
  outcome of each run come from the ``slack_operation_applied`` security events the callback writes.

Two render targets map to the owner's Slack UX:
- ``render_operation_receipt`` -> the proof-carrying receipt ("✅ Done — Invoice #4912 · $2,850,
  verified") shown right after a run.
- ``render_value_digest`` -> the periodic value digest ("this week: caught $1,310, recovered $940,
  invoiced $34,200 same-day, ~6 hrs saved").

Hours saved is an explicit, tunable ESTIMATE (minutes-per-task) and is always labelled as such — we
never dress an estimate up as a measured fact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from pydantic import BaseModel, Field

from .summary import DailySummary
from .workflow import WorkflowStore

APPLIED_EVENT = "slack_operation_applied"

# Which value bucket each known lane contributes to (mirrors operation_router.freight_lanes()).
_INVOICE_LANES = {"raise_invoice"}
_PAYABLE_LANES = {"record_payable"}


@dataclass(frozen=True)
class MinutesPerTask:
    """Tunable, honest estimate of the back-office minutes each handled task would have cost a human."""

    invoice_raised: int = 6
    payable_recorded: int = 6
    overbilling_reviewed: int = 8
    auto_cleared: int = 4


class OperationReceipt(BaseModel):
    """One agent-operation run, rendered as the owner sees it."""

    lane: str | None
    status: str  # DONE | ESCALATED | FAILED | REFUSED
    amount: str | None = None
    proof: str | None = None  # the verifiable artifact (invoice #, record id) parsed from the result
    summary: str = ""
    channel_id: str | None = None
    thread_ts: str | None = None
    created_at: str | None = None


class ValueDigest(BaseModel):
    """The owner-facing ROI roll-up for a period."""

    overbilling_flagged: str = "0.00"
    overbilling_recovered: str = "0.00"
    invoices_raised: int = 0
    invoiced_amount: str = "0.00"
    payables_recorded: int = 0
    payables_amount: str = "0.00"
    operations_done: int = 0
    operations_escalated: int = 0
    operations_failed: int = 0
    hours_saved_estimate: str = "0.0"
    recent_receipts: list[OperationReceipt] = Field(default_factory=list)


def build_operation_receipts(store: WorkflowStore) -> list[OperationReceipt]:
    """Read every applied agent operation out of the audit log, newest last (insertion order)."""
    receipts: list[OperationReceipt] = []
    for event in store.security_events():
        if event["event_type"] != APPLIED_EVENT:
            continue
        payload = event.get("payload") or {}
        receipts.append(
            OperationReceipt(
                lane=payload.get("lane"),
                status=str(payload.get("status", "")) or "UNKNOWN",
                amount=_amount_str(payload.get("approved_amount")),
                proof=_extract_proof(str(payload.get("note", "")), payload.get("steps") or []),
                summary=str(payload.get("summary", "")),
                channel_id=payload.get("channel_id"),
                thread_ts=payload.get("thread_ts"),
                created_at=event.get("created_at"),
            )
        )
    return receipts


def build_value_digest(
    store: WorkflowStore,
    *,
    daily: DailySummary | None = None,
    minutes: MinutesPerTask | None = None,
    recent: int = 5,
) -> ValueDigest:
    """Compose the AP reconciliation numbers (``daily``) with the agent-operation receipts into one
    ROI roll-up. ``daily`` is optional so the digest still works before the AP path has run."""
    minutes = minutes or MinutesPerTask()
    receipts = build_operation_receipts(store)

    invoiced = Decimal("0.00")
    payables = Decimal("0.00")
    invoices_raised = payables_recorded = done = escalated = failed = 0
    for r in receipts:
        if r.status == "DONE":
            done += 1
            if r.lane in _INVOICE_LANES:
                invoices_raised += 1
                invoiced += _to_decimal(r.amount)
            elif r.lane in _PAYABLE_LANES:
                payables_recorded += 1
                payables += _to_decimal(r.amount)
        elif r.status == "ESCALATED":
            escalated += 1
        elif r.status == "FAILED":
            failed += 1

    auto_cleared = daily.auto_cleared if daily else 0
    overbilling_reviewed = daily.needs_review if daily else 0
    saved_minutes = (
        invoices_raised * minutes.invoice_raised
        + payables_recorded * minutes.payable_recorded
        + overbilling_reviewed * minutes.overbilling_reviewed
        + auto_cleared * minutes.auto_cleared
    )

    return ValueDigest(
        overbilling_flagged=daily.potential_overbilling_flagged if daily else "0.00",
        overbilling_recovered=daily.confirmed_recovered if daily else "0.00",
        invoices_raised=invoices_raised,
        invoiced_amount=_money(invoiced),
        payables_recorded=payables_recorded,
        payables_amount=_money(payables),
        operations_done=done,
        operations_escalated=escalated,
        operations_failed=failed,
        hours_saved_estimate=f"{saved_minutes / 60:.1f}",
        recent_receipts=receipts[-recent:][::-1] if recent else [],
    )


def receipt_from_result(result, *, amount: str | None = None) -> OperationReceipt:
    """Build an owner receipt straight from an OperationRouter result (duck-typed: lane/status/note/
    steps), so the live Slack post can be proof-carrying without re-reading the audit log."""
    note = str(getattr(result, "note", "") or "")
    return OperationReceipt(
        lane=getattr(result, "lane", None),
        status=str(getattr(result, "status", "")) or "UNKNOWN",
        amount=_amount_str(amount),
        proof=_extract_proof(note, getattr(result, "steps", None) or []),
        summary=note,
    )


def render_operation_receipt(receipt: OperationReceipt) -> str:
    """Shape #3: the proof-carrying receipt shown right after a run. Proof, not a bare claim."""
    money = f" · ${receipt.amount}" if receipt.amount else ""
    what = _lane_label(receipt.lane)
    if receipt.status == "DONE":
        proof = f" — {receipt.proof}" if receipt.proof else ""
        verified = " (verified)" if receipt.proof else ""
        return f"✅ Done — {what}{money}{proof}{verified}"
    if receipt.status == "ESCALATED":
        return f"✋ I need you — {what}{money}: {receipt.summary or 'stopped and handed it to you'}"
    if receipt.status == "REFUSED":
        return f"🚫 I won't improvise — {receipt.summary or what}"
    return f"⚠️ Couldn't finish — {what}{money}: {receipt.summary or 'see the audit log'}"


def render_value_digest(digest: ValueDigest, *, period: str = "this week") -> str:
    """Shape #5: the periodic value digest — the single message that makes the ROI legible."""
    lines = [f"📊 Neyma {period}"]
    if _nonzero(digest.overbilling_flagged) or _nonzero(digest.overbilling_recovered):
        lines.append(
            f"• Caught ${digest.overbilling_flagged} in carrier overbilling "
            f"→ recovered ${digest.overbilling_recovered}"
        )
    if digest.invoices_raised:
        lines.append(
            f"• Raised {digest.invoices_raised} customer invoice"
            f"{'s' if digest.invoices_raised != 1 else ''} (${digest.invoiced_amount}) — same-day"
        )
    if digest.payables_recorded:
        lines.append(
            f"• Recorded {digest.payables_recorded} carrier payable"
            f"{'s' if digest.payables_recorded != 1 else ''} (${digest.payables_amount})"
        )
    if digest.operations_escalated or digest.operations_failed:
        lines.append(
            f"• {digest.operations_escalated} handed back to you · {digest.operations_failed} failed"
        )
    lines.append(f"• ~{digest.hours_saved_estimate} hrs of back-office saved (estimated)")
    if not (
        _nonzero(digest.overbilling_flagged)
        or digest.invoices_raised
        or digest.payables_recorded
    ):
        lines.append("Nothing consequential yet — I'll surface work as it lands.")
    return "\n".join(lines)


# --- helpers ---------------------------------------------------------------------------------

_PROOF_RE = re.compile(
    r"(?:invoice|inv|record)\s*#?\s*([A-Za-z]{1,4}-?\d{2,}|\d{2,})|#(\d{2,})", re.IGNORECASE
)


def _extract_proof(note: str, steps: list) -> str | None:
    """Best-effort pull of the verifiable artifact (an invoice/record id) from the run result.

    A receipt is only trustworthy if it points at something the owner can open and check, so we look
    for an id token in the agent's DONE note, then in any READ step it confirmed itself with.
    """
    for text in [note, *[_step_text(s) for s in steps]]:
        if not text:
            continue
        match = _PROOF_RE.search(text)
        if match:
            return (match.group(1) or f"#{match.group(2)}").strip()
    return None


def _step_text(step) -> str:
    if isinstance(step, dict):
        return " ".join(str(step.get(k, "")) for k in ("observed", "why", "value", "target"))
    return str(step or "")


def _lane_label(lane: str | None) -> str:
    if lane in _INVOICE_LANES:
        return "customer invoice"
    if lane in _PAYABLE_LANES:
        return "carrier payable"
    return lane or "operation"


def _amount_str(value) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _to_decimal(value) -> Decimal:
    try:
        return Decimal(str(value)) if value not in (None, "") else Decimal("0.00")
    except (ValueError, ArithmeticError):
        return Decimal("0.00")


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _nonzero(money_str: str) -> bool:
    return _to_decimal(money_str) != Decimal("0.00")
