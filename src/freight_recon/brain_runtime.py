"""Runtime wiring that connects the Operator Brain to the gated money path.

The Brain module stays pure (it never imports the money path); this is where the consequential
FILL_AND_SUBMIT step is wired to an INJECTED effect executor — so a Brain plan can actually execute
a write, but ONLY through the full Safety Spine (approved-amount binding, deterministic
verify-by-readback, fail-closed). The Brain decides nothing about money here; it just hands off, and
a write only counts as ok when the gated path reaches a verified DONE.

### P4 ADAPTER CONTAINMENT. This module NO LONGER imports the effect-capable write path
(``tms_write``): its ``brain_runtime -> tms_write`` edge is cut. The effect executor
(``enter_fn``) and the approved-amount reader (``approved_amount_fn``) are INJECTED by the caller,
which is expected to supply a boundary-routed executor — one that flows through
``effect_boundary.execute_effect`` so a write without a claimed grant and a fresh witness refuses.
Ships dark: until a subsequent phase (P12) wires the approval→grant-mint and hands in such an
executor, brain_runtime holds no path to an ungated write. A missing executor fails CLOSED — the
old behaviour of silently reaching for the ungated ``enter_approved_payable`` default is gone.
"""

from __future__ import annotations

from typing import Callable

from freight_recon.operator_brain import FlowStep, StepAction, StepResult


def build_gated_submit(
    *,
    store,
    run_id: int,
    build_ledger: Callable[[dict], object],
    enter_fn: Callable,
    approved_amount_fn: Callable,
    on_status=None,
    ops_control=None,
) -> Callable[[dict], StepResult]:
    """Return a ``gated_submit(context) -> StepResult`` for the executor's FILL_AND_SUBMIT handler.

    ``build_ledger(context)`` constructs the ledger from what the Brain discovered/resolved (e.g. a
    DiscoveredInvoiceLedger from context['form'] + customer, or a MultiStepInvoiceLedger). The amount is
    NOT taken from the Brain — it is read from the human approval (``approved_amount_fn``) and bound by
    the injected ``enter_fn``; the step is ok only on a verified DONE.

    ``enter_fn`` and ``approved_amount_fn`` are REQUIRED and injected: this module must not import the
    effect-capable write path directly (P4 containment). Passing None fails CLOSED rather than
    reaching for an ungated default.
    """
    if enter_fn is None or approved_amount_fn is None:
        raise ValueError(
            "build_gated_submit requires an injected boundary-routed enter_fn and approved_amount_fn: "
            "brain_runtime does not import the effect path (P4 adapter containment). A missing "
            "executor fails closed rather than reaching for the ungated tms_write write path."
        )

    _enter = enter_fn
    _approved = approved_amount_fn

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
