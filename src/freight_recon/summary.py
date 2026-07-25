"""Daily dogfood summary for Neyma review work."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from .review import ReviewPayload
from .workflow import WorkflowState, WorkflowStore


class SummaryException(BaseModel):
    run_id: int
    load_id: str
    invoice_number: str
    carrier: str
    reason: str
    flagged_amount: str
    age_hours: int
    packet_detail_url: str


class DailySummary(BaseModel):
    processed: int
    auto_cleared: int
    needs_review: int
    duplicates: int
    missing_backup: int
    potential_overbilling_flagged: str
    confirmed_recovered: str
    clean_matches_visible: bool = True
    oldest_largest_unresolved: list[SummaryException] = Field(default_factory=list)


def build_daily_summary(store: WorkflowStore, payloads: list[ReviewPayload]) -> DailySummary:
    runs = store.list_runs()
    run_by_id = {run.id: run for run in runs}
    payload_by_run = {payload.run_id: payload for payload in payloads}
    review_runs = [run for run in runs if run.outcome and run.outcome != "MATCHED"]
    unresolved = [
        payload
        for payload in payloads
        if run_by_id[payload.run_id].state == WorkflowState.NEEDS_REVIEW
    ]

    flagged = sum(Decimal(payload.found_money.flagged_amount) for payload in payloads)
    recovered = _confirmed_recovered(store, payload_by_run)

    return DailySummary(
        processed=len(runs),
        auto_cleared=sum(1 for run in runs if run.outcome == "MATCHED"),
        needs_review=len(review_runs),
        duplicates=sum(1 for run in runs if run.outcome == "DUPLICATE"),
        missing_backup=sum(
            1
            for run in review_runs
            if run.reason and ("missing backup" in run.reason.lower() or "missing pod" in run.reason.lower())
        ),
        potential_overbilling_flagged=_money(flagged),
        confirmed_recovered=_money(recovered),
        oldest_largest_unresolved=_top_unresolved(unresolved),
    )


def render_daily_summary(summary: DailySummary) -> str:
    lines = [
        "Neyma Daily Payables Summary",
        "",
        f"Processed: {summary.processed} invoice packets",
        f"Auto-cleared: {summary.auto_cleared}",
        f"Needs review: {summary.needs_review}",
        f"Duplicates: {summary.duplicates}",
        f"Missing backup: {summary.missing_backup}",
        f"Potential overbilling flagged: ${summary.potential_overbilling_flagged}",
        f"Month to date: ${summary.potential_overbilling_flagged} flagged · ${summary.confirmed_recovered} confirmed recovered",
    ]
    if summary.clean_matches_visible:
        lines.append(f"Clean matches: {summary.auto_cleared} - view")
    if summary.oldest_largest_unresolved:
        lines.append("")
        lines.append("Oldest/largest unresolved:")
        for item in summary.oldest_largest_unresolved:
            age = f"{item.age_hours}h old" if item.age_hours else "new"
            lines.append(
                f"- {item.invoice_number}: {item.reason}, ${item.flagged_amount} flagged, {age}"
            )
    return "\n".join(lines)


def _confirmed_recovered(store: WorkflowStore, payload_by_run: dict[int, ReviewPayload]) -> Decimal:
    """Money is *recovered* only once the payable is entered AND verified by readback (the run
    reaches DONE via ``entry_done``) — not merely approved. An approval the TMS never confirmed has
    recovered nothing yet, so crediting it at approval time would overstate the trust metric.
    """
    recovered_runs = {event["run_id"] for event in store.audit_events() if event["event_type"] == "entry_done"}
    total = Decimal("0.00")
    for run_id in recovered_runs:
        payload = payload_by_run.get(run_id)
        if payload is not None:
            total += Decimal(payload.found_money.flagged_amount)
    return total


def _top_unresolved(payloads: list[ReviewPayload]) -> list[SummaryException]:
    ordered = sorted(
        payloads,
        key=lambda payload: (payload.aging.age_hours, Decimal(payload.found_money.flagged_amount)),
        reverse=True,
    )
    return [
        SummaryException(
            run_id=payload.run_id,
            load_id=payload.load_id,
            invoice_number=payload.invoice_number,
            carrier=payload.carrier,
            reason=payload.reasons[0] if payload.reasons else payload.summary,
            flagged_amount=payload.found_money.flagged_amount,
            age_hours=payload.aging.age_hours,
            packet_detail_url=payload.packet_detail_url,
        )
        for payload in ordered[:5]
    ]


def _money(value: Decimal) -> str:
    return f"{value:.2f}"
