"""Human review action intake for supervised workflow decisions."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field

from .review import ReviewAction, ReviewPayload
from .workflow import WorkflowError, WorkflowRun, WorkflowState, WorkflowStore
from .workflow_direction import approval_object, is_payable


class ReviewDecision(str, Enum):
    APPROVE_EXPECTED_AMOUNT = "APPROVE_EXPECTED_AMOUNT"
    APPROVE_FULL_AMOUNT = "APPROVE_FULL_AMOUNT"
    EDIT_FIELDS = "EDIT_FIELDS"
    DISPUTE = "DISPUTE"
    REQUEST_BACKUP = "REQUEST_BACKUP"
    MARK_DUPLICATE = "MARK_DUPLICATE"


class ReviewActionRequest(BaseModel):
    run_id: int
    decision: ReviewDecision
    actor: str = "Rasheed"
    amount: Decimal | None = None
    note: str | None = None
    corrections: list["ReviewCorrection"] = Field(default_factory=list)


class ReviewCorrection(BaseModel):
    field: str
    before: str | None = None
    after: str
    source: str = "human_review"


class ReviewActionResult(BaseModel):
    run_id: int
    decision: ReviewDecision
    from_state: WorkflowState
    to_state: WorkflowState
    actor: str
    mutation_text: str
    draft_follow_up_required: bool = False
    amount: str | None = None


def apply_review_action(store: WorkflowStore, request: ReviewActionRequest) -> ReviewActionResult:
    """Apply one human review action to a workflow run.

    This is the local dogfood action intake. Slack/Teams adapters should call this after
    signature verification instead of mutating workflow state directly.
    """
    run = store.get_run(request.run_id)
    if run is None:
        raise WorkflowError(f"workflow run not found: {request.run_id}")
    if run.state != WorkflowState.NEEDS_REVIEW:
        raise WorkflowError(f"review action requires NEEDS_REVIEW state, got {run.state.value}")

    if request.decision == ReviewDecision.EDIT_FIELDS:
        store.add_audit_event(
            run.id,
            "review_edit_requested",
            actor=request.actor,
            payload=_payload(request, run.workflow_direction),
        )
        if request.corrections:
            store.add_audit_event(
                run.id,
                "review_corrections_recorded",
                actor=request.actor,
                payload={
                    "corrections": [correction.model_dump(mode="json") for correction in request.corrections],
                    "eval_candidate": True,
                },
            )
        return _result(run, run, request, "Edit requested by {actor}")

    if request.decision == ReviewDecision.APPROVE_EXPECTED_AMOUNT:
        _validate_money_action(store, run.id, request)
        updated = store.transition(
            run.id,
            WorkflowState.APPROVED,
            actor=request.actor,
            event_type="review_approved_expected_amount",
            payload=_payload(request, run.workflow_direction),
        )
        return _result(
            run,
            updated,
            request,
            "Approved expected {object} {amount} by {actor}",
            draft_follow_up_required=is_payable(updated.workflow_direction),
        )

    if request.decision == ReviewDecision.APPROVE_FULL_AMOUNT:
        _validate_money_action(store, run.id, request)
        updated = store.transition(
            run.id,
            WorkflowState.APPROVED,
            actor=request.actor,
            event_type="review_approved_full_amount",
            payload=_payload(request, run.workflow_direction),
        )
        return _result(run, updated, request, "Approved full {object} {amount} by {actor}")

    if request.decision == ReviewDecision.DISPUTE:
        draft_follow_up_required = _draft_follow_up_required(store, run.id, request)
        updated = store.transition(
            run.id,
            WorkflowState.DISPUTED,
            actor=request.actor,
            event_type="review_disputed",
            payload=_payload(request, run.workflow_direction),
        )
        return _result(
            run,
            updated,
            request,
            "Disputed by {actor}",
            draft_follow_up_required=draft_follow_up_required,
        )

    if request.decision == ReviewDecision.REQUEST_BACKUP:
        draft_follow_up_required = _draft_follow_up_required(store, run.id, request)
        updated = store.transition(
            run.id,
            WorkflowState.REQUESTED_BACKUP,
            actor=request.actor,
            event_type="review_backup_requested",
            payload=_payload(request, run.workflow_direction),
        )
        return _result(
            run,
            updated,
            request,
            "Backup requested by {actor}",
            draft_follow_up_required=draft_follow_up_required,
        )

    if request.decision == ReviewDecision.MARK_DUPLICATE:
        updated = store.transition(
            run.id,
            WorkflowState.DISPUTED,
            actor=request.actor,
            event_type="review_marked_duplicate",
            payload=_payload(request, run.workflow_direction),
        )
        return _result(run, updated, request, "Marked duplicate by {actor}")

    raise WorkflowError(f"unsupported review decision: {request.decision.value}")


def _payload(request: ReviewActionRequest, direction) -> dict:
    return {
        "decision": request.decision.value,
        "actor": request.actor,
        "amount": str(request.amount) if request.amount is not None else None,
        "workflow_direction": direction.value,
        "note": request.note,
        "corrections": [correction.model_dump(mode="json") for correction in request.corrections],
    }


def _result(
    original: WorkflowRun,
    updated: WorkflowRun,
    request: ReviewActionRequest,
    template: str,
    *,
    draft_follow_up_required: bool = False,
) -> ReviewActionResult:
    amount = f"${request.amount:.2f}" if request.amount is not None else ""
    object_name = approval_object(updated.workflow_direction)
    return ReviewActionResult(
        run_id=original.id,
        decision=request.decision,
        from_state=original.state,
        to_state=updated.state,
        actor=request.actor,
        mutation_text=template.format(actor=request.actor, amount=amount, object=object_name).strip(),
        draft_follow_up_required=draft_follow_up_required,
        amount=f"{request.amount:.2f}" if request.amount is not None else None,
    )


def _validate_money_action(store: WorkflowStore, run_id: int, request: ReviewActionRequest) -> None:
    if request.amount is None:
        raise WorkflowError(f"{request.decision.value} requires an explicit amount")
    run = store.get_run(run_id)
    if run is None:
        raise WorkflowError(f"workflow run not found: {run_id}")
    payload = _latest_review_payload(store, run_id)
    if payload is None:
        raise WorkflowError("money approval requires a recorded review payload")
    if payload.workflow_direction != run.workflow_direction:
        raise WorkflowError(
            "money approval requires a review payload for the current workflow direction"
        )
    expected = {
        option.amount
        for option in payload.action_options
        if _decision_for_option(option) == request.decision and option.amount is not None
    }
    amount = f"{request.amount:.2f}"
    if amount not in expected:
        raise WorkflowError(
            f"{request.decision.value} amount {amount} does not match current review options"
        )


def _draft_follow_up_required(store: WorkflowStore, run_id: int, request: ReviewActionRequest) -> bool:
    payload = _latest_review_payload(store, run_id)
    if payload is None:
        return False
    for option in payload.action_options:
        if _decision_for_option(option) != request.decision:
            continue
        if option.amount is not None and request.amount is not None and f"{request.amount:.2f}" != option.amount:
            continue
        if option.amount is not None and request.amount is None:
            continue
        return option.creates_follow_up_draft
    return False


def _latest_review_payload(store: WorkflowStore, run_id: int) -> ReviewPayload | None:
    for event in reversed(store.audit_events(run_id)):
        if event["event_type"] == "review_payload_created":
            return ReviewPayload.model_validate(event["payload"])
    return None


def _decision_for_option(option) -> ReviewDecision:
    if option.code == ReviewAction.MARK_DUPLICATE:
        return ReviewDecision.MARK_DUPLICATE
    if option.code == ReviewAction.DISPUTE:
        return ReviewDecision.DISPUTE
    if option.code == ReviewAction.REQUEST_BACKUP:
        return ReviewDecision.REQUEST_BACKUP
    if option.code == ReviewAction.EDIT:
        return ReviewDecision.EDIT_FIELDS
    if option.amount_kind == "EXPECTED":
        return ReviewDecision.APPROVE_EXPECTED_AMOUNT
    if option.amount_kind == "FULL":
        return ReviewDecision.APPROVE_FULL_AMOUNT
    if option.creates_follow_up_draft:
        return ReviewDecision.APPROVE_EXPECTED_AMOUNT
    return ReviewDecision.APPROVE_FULL_AMOUNT
