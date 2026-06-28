"""Post-approval execution hook for turning Slack decisions into gated work.

The delivery callback applies the human decision. This module decides whether that decision should
advance into execution. V0 is deliberately mock-TMS only: it proves the always-on product loop
without letting a live customer TMS write happen through the callback path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from pydantic import BaseModel

from .delivery import DeliveryActionOutcome, DeliveryActionStatus
from .ops_control import OpsControl, TmsWritesPausedError
from .review_actions import ReviewDecision
from .tms_write import (
    ChargeLine,
    ExecutionStatusUpdate,
    MockTmsWriteLedger,
    PayableEntryOutcome,
    approved_amount_for_run,
    enter_approved_payable,
)
from .workflow import WorkflowState, WorkflowStore
from .workflow_direction import WorkflowDirection


class MockTmsAutoEntryConfig(BaseModel):
    """Config for the safe local/mock execution hook after a Slack approval."""

    enabled: bool = False
    ledger_path: str
    tms_write_enabled: bool = True
    actor: str = "Neyma"


def maybe_execute_mock_tms_after_approval(
    store: WorkflowStore,
    action: DeliveryActionOutcome,
    *,
    config: MockTmsAutoEntryConfig,
    on_status: Callable[[ExecutionStatusUpdate], None] | None = None,
    ops_control: OpsControl | None = None,
) -> PayableEntryOutcome | None:
    """Run mock-only TMS entry after an approved money action, if enabled and safe.

    Returns ``None`` when the action is not an approval or auto-entry is disabled. Any execution
    failure is audited and swallowed so the Slack callback still returns a normal action response;
    the workflow state and status thread remain the source of truth.
    """
    if action.status != DeliveryActionStatus.APPLIED:
        return None
    if action.decision not in {ReviewDecision.APPROVE_EXPECTED_AMOUNT, ReviewDecision.APPROVE_FULL_AMOUNT}:
        return None
    if action.to_state != WorkflowState.APPROVED:
        return None
    run = store.get_run(action.run_id)
    if run is None:
        return None
    if run.workflow_direction != WorkflowDirection.CARRIER_PAYABLE:
        store.add_audit_event(
            action.run_id,
            "post_approval_execution_skipped",
            actor=config.actor,
            payload={
                "reason": "non_payable_workflow_direction",
                "workflow_direction": run.workflow_direction.value,
                "decision": action.decision.value,
            },
        )
        return None

    if not config.enabled:
        store.add_audit_event(
            action.run_id,
            "post_approval_execution_skipped",
            actor=config.actor,
            payload={"reason": "mock_tms_auto_entry_disabled", "decision": action.decision.value},
        )
        return None

    amount = approved_amount_for_run(store, action.run_id)
    if amount is None:
        store.add_audit_event(
            action.run_id,
            "post_approval_execution_failed",
            actor=config.actor,
            payload={"reason": "missing_human_approved_amount", "decision": action.decision.value},
        )
        return None

    ledger = MockTmsWriteLedger(Path(config.ledger_path))
    try:
        outcome = enter_approved_payable(
            store,
            ledger,
            action.run_id,
            amount=amount,
            charges=[ChargeLine(name="approved_payable", amount=amount)],
            actor=config.actor,
            tms_write_enabled=config.tms_write_enabled,
            on_status=on_status,
            ops_control=ops_control,
        )
    except TmsWritesPausedError as exc:
        store.add_audit_event(
            action.run_id,
            "post_approval_execution_held",
            actor=config.actor,
            payload={"reason": "tms_writes_paused", "message": str(exc)[:500]},
        )
        return None
    except Exception as exc:  # noqa: BLE001 - execution errors must not break Slack callback ack
        store.add_audit_event(
            action.run_id,
            "post_approval_execution_failed",
            actor=config.actor,
            payload={"error_type": type(exc).__name__, "error": str(exc)[:500]},
        )
        return None

    store.add_audit_event(
        action.run_id,
        "post_approval_execution_completed",
        actor=config.actor,
        payload=outcome.model_dump(mode="json"),
    )
    return outcome
