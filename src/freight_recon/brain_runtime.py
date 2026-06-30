"""Runtime wiring that connects the Operator Brain to the gated money path.

The Brain module stays pure (it never imports the money path); this is where the consequential
FILL_AND_SUBMIT step is wired to ``enter_approved_payable`` — so a Brain plan can actually execute a
write, but ONLY through the full Safety Spine (approved-amount binding, deterministic verify-by-readback,
fail-closed). The Brain decides nothing about money here; it just hands off, and a write only counts as
ok when the gated path reaches a verified DONE.
"""

from __future__ import annotations

from typing import Callable

from freight_recon.operator_brain import FlowStep, StepAction, StepResult


def build_gated_submit(
    *,
    store,
    run_id: int,
    build_ledger: Callable[[dict], object],
    enter_fn: Callable | None = None,
    approved_amount_fn: Callable | None = None,
    on_status=None,
    ops_control=None,
) -> Callable[[dict], StepResult]:
    """Return a ``gated_submit(context) -> StepResult`` for the executor's FILL_AND_SUBMIT handler.

    ``build_ledger(context)`` constructs the ledger from what the Brain discovered/resolved (e.g. a
    DiscoveredInvoiceLedger from context['form'] + customer, or a MultiStepInvoiceLedger). The amount is
    NOT taken from the Brain — it is read from the human approval (``approved_amount_fn``) and bound by
    ``enter_approved_payable``; the step is ok only on a verified DONE.
    """
    from freight_recon.tms_write import approved_amount_for_run, enter_approved_payable

    _enter = enter_fn or enter_approved_payable
    _approved = approved_amount_fn or approved_amount_for_run

    def gated_submit(context: dict) -> StepResult:
        step = FlowStep(StepAction.FILL_AND_SUBMIT)
        approved = _approved(store, run_id)
        if not approved:
            return StepResult(step, ok=False, detail="refused: no human-approved amount recorded for this run")
        try:
            ledger = build_ledger(context)
        except Exception as exc:  # noqa: BLE001 - a wiring failure must fail the step closed, not raise
            return StepResult(step, ok=False, detail=f"could not build ledger: {str(exc)[:140]}")
        outcome = _enter(store, ledger, run_id, amount=approved, on_status=on_status, ops_control=ops_control)
        ok = bool(getattr(outcome, "verified", False))
        detail = getattr(outcome, "note", "") or f"final_state={getattr(outcome, 'final_state', '?')}"
        return StepResult(step, ok=ok, detail=detail)

    return gated_submit
