"""Bounded TMS write path against the mock TMS (Stage 7).

This is the execution layer: operate the TMS the way a human would, but wrapped in the engine's
hard safety spine. Deterministic Python still owns the money; this module only *enters* a payable
that a human already approved, and only after passing every gate:

- **Workflow-state + permission gating.** Each step (prepare / submit / verify) is checked against
  the tool permission registry. Prepare and submit require explicit human approval and the
  `tms_write_enabled` feature flag; they only run in the correct workflow state.
- **Confirm-before-submit.** `prepare` writes nothing — it returns exactly what *will* be written
  (the diff + an idempotency key) for a human to confirm. `submit` refuses to run without that
  confirmation.
- **Per-action idempotency.** A re-submitted entry (crash/retry/double-click) does not double-enter;
  the ledger replays the existing record by idempotency key.
- **Verify-by-readback.** A run only reaches `DONE` after the entry is read back from the TMS and
  matches what we intended. A readback mismatch routes to `FAILED`, never to done.
- **Action trace + audit.** Every step records an audit event, the Asteroid-style "what the agent
  did" trail.

The mock ledger simulates real failure modes (duplicate-payable warning, session expiration,
readback mismatch) so the safety path is exercised before any real TMS is involved. No credentials
are stored; a real adapter would operate a human-established session behind this same interface.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, Field

from .ops_control import OpsControl, TmsWritesPausedError
from .tool_permissions import (
    ToolContext,
    ToolPermissionDecision,
    evaluate_tool_permission,
    record_tool_permission_decision,
)
from .workflow import WorkflowError, WorkflowRun, WorkflowState, WorkflowStore
from .workflow_direction import WorkflowDirection


class TmsWriteError(RuntimeError):
    """Raised when a TMS write step is not permitted or cannot be safely completed."""


class PayableWriteStatus(str, Enum):
    WRITTEN = "WRITTEN"
    IDEMPOTENT_REPLAY = "IDEMPOTENT_REPLAY"
    DUPLICATE_BLOCKED = "DUPLICATE_BLOCKED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    ADAPTER_FAILED = "ADAPTER_FAILED"


class ChargeLine(BaseModel):
    name: str
    amount: str


class PreparedPayableEntry(BaseModel):
    run_id: int
    load_id: str
    carrier: str
    amount: str
    charge_lines: list[ChargeLine] = Field(default_factory=list)
    idempotency_key: str
    confirm_required: bool = True
    summary: str


class PayableWriteResult(BaseModel):
    run_id: int
    load_id: str
    idempotency_key: str
    status: PayableWriteStatus
    external_ref: str | None = None
    note: str


class ReadbackVerification(BaseModel):
    run_id: int
    load_id: str
    match: bool
    expected_amount: str
    expected_idempotency_key: str | None = None
    found_amount: str | None = None
    found_idempotency_key: str | None = None
    identity_match: bool = False
    note: str


def idempotency_key(run_id: int, load_id: str, amount: str) -> str:
    return hashlib.sha256(f"{run_id}:{load_id}:{amount}".encode("utf-8")).hexdigest()[:24]


# The audit events the review/Slack intake records when a human approves an amount for a run.
_APPROVAL_EVENT_TYPES = ("review_approved_expected_amount", "review_approved_full_amount")


def approved_amount_for_run(
    store: WorkflowStore,
    run_id: int,
    *,
    workflow_direction: WorkflowDirection | str | None = None,
) -> str | None:
    """The amount a human approved for this run (from the latest review/Slack approval), or ``None``.

    This is the authoritative figure a TMS write must enter — the approval is the source of truth,
    not an amount handed to the executor afterward.
    """
    for event in reversed(store.audit_events(run_id)):
        if event["event_type"] in _APPROVAL_EVENT_TYPES:
            if workflow_direction is not None:
                expected_direction = WorkflowDirection(workflow_direction).value
                if event["payload"].get("workflow_direction") != expected_direction:
                    continue
            amount = event["payload"].get("amount")
            return str(amount) if amount is not None else None
    return None


class MockTmsWriteLedger:
    """A JSON-backed payable ledger standing in for the TMS accounting system.

    ``fail_modes`` injects real-world failure surfaces for tests: ``"session_expired"``,
    ``"duplicate"`` (a payable already exists for the load under a different key), and
    ``"readback_mismatch"`` (the TMS saves a different amount than submitted).
    """

    def __init__(self, path: str | Path, *, fail_modes: frozenset[str] = frozenset()) -> None:
        self.path = Path(path)
        self.fail_modes = fail_modes
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("{}", encoding="utf-8")

    def _read(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def get_payable(self, load_id: str) -> dict | None:
        return self._read().get(load_id)

    def write_payable(
        self,
        *,
        run_id: int,
        load_id: str,
        carrier: str,
        amount: str,
        charges: list[ChargeLine],
        key: str,
    ) -> PayableWriteResult:
        if "session_expired" in self.fail_modes:
            return PayableWriteResult(
                run_id=run_id,
                load_id=load_id,
                idempotency_key=key,
                status=PayableWriteStatus.SESSION_EXPIRED,
                note="TMS session expired before write; no payable entered",
            )

        ledger = self._read()
        existing = ledger.get(load_id)
        if existing and existing.get("idempotency_key") == key:
            return PayableWriteResult(
                run_id=run_id,
                load_id=load_id,
                idempotency_key=key,
                status=PayableWriteStatus.IDEMPOTENT_REPLAY,
                external_ref=existing.get("external_ref"),
                note="payable already entered with this idempotency key; not re-entered",
            )
        if existing or "duplicate" in self.fail_modes:
            return PayableWriteResult(
                run_id=run_id,
                load_id=load_id,
                idempotency_key=key,
                status=PayableWriteStatus.DUPLICATE_BLOCKED,
                external_ref=existing.get("external_ref") if existing else None,
                note="a payable already exists for this load; duplicate entry blocked",
            )

        # A misbehaving TMS that saves the wrong amount — caught later by verify-by-readback.
        saved_amount = amount
        if "readback_mismatch" in self.fail_modes:
            saved_amount = f"{Decimal(amount) - Decimal('0.01'):.2f}"

        external_ref = f"PV-{key[:8].upper()}"
        ledger[load_id] = {
            "run_id": run_id,
            "carrier": carrier,
            "amount": saved_amount,
            "charges": [c.model_dump(mode="json") for c in charges],
            "idempotency_key": key,
            "external_ref": external_ref,
        }
        self._write(ledger)
        return PayableWriteResult(
            run_id=run_id,
            load_id=load_id,
            idempotency_key=key,
            status=PayableWriteStatus.WRITTEN,
            external_ref=external_ref,
            note="payable entered",
        )


class TmsWriteAdapter:
    """Permission-gated, audited write operations against a mock TMS ledger."""

    def __init__(self, store: WorkflowStore, ledger: MockTmsWriteLedger) -> None:
        self.store = store
        self.ledger = ledger

    def prepare(
        self,
        run: WorkflowRun,
        *,
        amount: str,
        charges: list[ChargeLine],
        context: ToolContext,
    ) -> PreparedPayableEntry:
        self._gate("prepare_tms_payable_entry", run.id, context)
        key = idempotency_key(run.id, run.load_id, amount)
        prepared = PreparedPayableEntry(
            run_id=run.id,
            load_id=run.load_id,
            carrier=run.carrier or "",
            amount=amount,
            charge_lines=charges,
            idempotency_key=key,
            summary=f"Enter payable ${amount} for {run.load_id} ({run.carrier or 'carrier'})",
        )
        self.store.add_audit_event(
            run.id,
            "tms_write_prepared",
            actor=context.actor,
            payload={"action": "prepare", **prepared.model_dump(mode="json")},
        )
        return prepared

    def submit(
        self,
        prepared: PreparedPayableEntry,
        *,
        context: ToolContext,
        confirmed: bool,
    ) -> PayableWriteResult:
        self._gate("submit_tms_payable", prepared.run_id, context)
        if not confirmed:
            raise TmsWriteError("submit refused: confirm-before-submit not satisfied")
        result = self.ledger.write_payable(
            run_id=prepared.run_id,
            load_id=prepared.load_id,
            carrier=prepared.carrier,
            amount=prepared.amount,
            charges=prepared.charge_lines,
            key=prepared.idempotency_key,
        )
        self.store.add_audit_event(
            prepared.run_id,
            "tms_write_submitted",
            actor=context.actor,
            payload={"action": "submit", **result.model_dump(mode="json")},
        )
        return result

    def verify(
        self,
        run: WorkflowRun,
        *,
        expected_amount: str,
        expected_idempotency_key: str | None = None,
        context: ToolContext,
    ) -> ReadbackVerification:
        self._gate("verify_tms_payable", run.id, context)
        record = self.ledger.get_payable(run.load_id)
        found = record.get("amount") if record else None
        found_key = record.get("idempotency_key") if record else None
        amount_match = found is not None and Decimal(found) == Decimal(expected_amount)
        identity_match = expected_idempotency_key is not None and found_key == expected_idempotency_key
        match = amount_match and identity_match
        verification = ReadbackVerification(
            run_id=run.id,
            load_id=run.load_id,
            match=match,
            expected_amount=expected_amount,
            expected_idempotency_key=expected_idempotency_key,
            found_amount=found,
            found_idempotency_key=found_key,
            identity_match=identity_match,
            note=(
                "readback matches intended amount and idempotency key"
                if match
                else "readback does not match intended amount and idempotency key"
            ),
        )
        self.store.add_audit_event(
            run.id,
            "tms_write_verified",
            actor=context.actor,
            payload={"action": "verify", **verification.model_dump(mode="json")},
        )
        return verification

    def _gate(self, tool_name: str, run_id: int, context: ToolContext) -> ToolPermissionDecision:
        decision = evaluate_tool_permission(tool_name, context)
        record_tool_permission_decision(self.store, run_id, decision=decision, context=context)
        if not decision.allowed:
            raise TmsWriteError(f"{tool_name} blocked: {decision.reason}")
        return decision


class PayableEntryOutcome(BaseModel):
    run_id: int
    load_id: str
    final_state: WorkflowState
    write_status: PayableWriteStatus
    verified: bool
    external_ref: str | None = None
    trace: list[str] = Field(default_factory=list)
    note: str


class ExecutionPhase(str, Enum):
    """Coarse phases of a TMS write, for human-facing status updates (e.g. a Slack thread)."""

    ENTERING = "ENTERING"
    ENTERED = "ENTERED"
    VERIFIED = "VERIFIED"
    DONE = "DONE"
    FAILED = "FAILED"
    WAITING_FOR_SESSION = "WAITING_FOR_SESSION"


class ExecutionStatusUpdate(BaseModel):
    """A channel-neutral status update emitted as the gated write progresses.

    Transports (a Slack thread, etc.) render this so a human watches the payable land in the same
    place they approved it. Best-effort: the gated spine stays authoritative and never depends on a
    status sink succeeding.
    """

    run_id: int
    load_id: str
    phase: ExecutionPhase
    message: str
    external_ref: str | None = None
    amount: str | None = None


def enter_approved_payable(
    store: WorkflowStore,
    ledger: MockTmsWriteLedger,
    run_id: int,
    *,
    amount: str,
    charges: list[ChargeLine] | None = None,
    actor: str = "Rasheed",
    tms_write_enabled: bool = True,
    on_status: Callable[[ExecutionStatusUpdate], None] | None = None,
    ops_control: OpsControl | None = None,
) -> PayableEntryOutcome:
    """Drive an APPROVED run through the gated write path to DONE, FAILED, or WAITING_FOR_SESSION.

    Sequence: APPROVED → READY_FOR_ENTRY → prepare → ENTERING → submit → verify →
    (match) ENTERED → DONE, (mismatch/duplicate) FAILED, (session expired) WAITING_FOR_SESSION.
    Only a verified readback reaches DONE; nothing here decides money.
    """
    run = store.get_run(run_id)
    if run is None:
        raise WorkflowError(f"workflow run not found: {run_id}")
    if run.state != WorkflowState.APPROVED:
        raise WorkflowError(f"payable entry requires APPROVED state, got {run.state.value}")
    if run.workflow_direction != WorkflowDirection.CARRIER_PAYABLE:
        raise WorkflowError(
            f"payable entry requires CARRIER_PAYABLE workflow direction, got {run.workflow_direction.value}"
        )

    # Owner's brake: if TMS writes are paused, hold this APPROVED run in place (do not fail it).
    # It will execute on a later attempt once an owner resumes from Slack.
    if ops_control is not None and ops_control.is_tms_writes_paused():
        paused = ops_control.status()
        store.add_audit_event(
            run_id, "tms_write_paused_hold", actor=actor,
            payload={"paused_by": paused.get("paused_by"), "reason": paused.get("reason")},
        )
        raise TmsWritesPausedError(
            f"TMS writes are paused by {paused.get('paused_by')}"
            + (f" ({paused.get('reason')})" if paused.get("reason") else "")
            + "; run held in APPROVED until resumed"
        )

    # Bind the entry to the human approval: the amount entered must be the amount approved in Slack
    # for THIS run (recorded on the APPROVED transition), never just a caller-supplied figure.
    # Deterministic Python owns the money; the caller's `amount` is only an assertion that must match.
    approved = approved_amount_for_run(
        store,
        run_id,
        workflow_direction=WorkflowDirection.CARRIER_PAYABLE,
    )
    if approved is None:
        # Fail closed: the binding is the last line of defense for real money, so a run with no
        # recorded human approval must never reach the writer on a caller-supplied amount.
        raise WorkflowError(
            f"refusing TMS entry for run {run_id}: no human-approved amount recorded for this run"
        )
    if Decimal(approved) != Decimal(amount):
        raise WorkflowError(
            f"refusing TMS entry for run {run_id}: requested amount {amount} does not match the "
            f"human-approved amount {approved}"
        )

    charges = charges or []
    adapter = TmsWriteAdapter(store, ledger)
    trace: list[str] = []
    load_id = run.load_id

    def _emit(phase: ExecutionPhase, message: str, *, external_ref: str | None = None, amount: str | None = None) -> None:
        # Best-effort human-facing status; a sink failure must never break or alter the money path.
        if on_status is None:
            return
        try:
            on_status(
                ExecutionStatusUpdate(
                    run_id=run_id, load_id=load_id, phase=phase, message=message, external_ref=external_ref, amount=amount
                )
            )
        except Exception:  # noqa: BLE001 - status posting is advisory only
            pass

    run = store.transition(run_id, WorkflowState.READY_FOR_ENTRY, actor=actor, event_type="route_to_entry")
    trace.append("APPROVED→READY_FOR_ENTRY")

    prepare_ctx = ToolContext(
        workflow_state=WorkflowState.READY_FOR_ENTRY, actor=actor, approval_granted=True, tms_write_enabled=tms_write_enabled
    )
    prepared = adapter.prepare(run, amount=amount, charges=charges, context=prepare_ctx)
    trace.append(f"prepared idempotency_key={prepared.idempotency_key}")

    run = store.transition(run_id, WorkflowState.ENTERING, actor=actor, event_type="begin_entry")
    trace.append("READY_FOR_ENTRY→ENTERING")
    _emit(ExecutionPhase.ENTERING, f"Entering payable in TMS for {load_id} (${amount})…", amount=amount)

    submit_ctx = ToolContext(
        workflow_state=WorkflowState.ENTERING, actor=actor, approval_granted=True, tms_write_enabled=tms_write_enabled
    )
    try:
        result = adapter.submit(prepared, context=submit_ctx, confirmed=True)
    except Exception as exc:  # noqa: BLE001 - adapter failures must fail closed through workflow state
        trace.append("submit:ADAPTER_FAILED")
        recovery = _recover_after_submit_exception(
            store,
            adapter,
            run,
            prepared=prepared,
            amount=amount,
            actor=actor,
            error=exc,
        )
        if recovery is not None:
            result, verification = recovery
            trace.append("recover_readback:match=True")
            _emit(
                ExecutionPhase.VERIFIED,
                f"TMS adapter failed after submit, but readback verified ${amount}.",
                external_ref=result.external_ref,
                amount=amount,
            )
            store.transition(run_id, WorkflowState.ENTERED, actor=actor, event_type="entry_recovered_after_adapter_failure")
            store.transition(run_id, WorkflowState.DONE, actor=actor, event_type="entry_done")
            trace.extend(["ENTERING→ENTERED", "ENTERED→DONE"])
            _emit(
                ExecutionPhase.DONE,
                f"Marked DONE — {load_id} payable complete after recovered readback.",
                external_ref=result.external_ref,
                amount=amount,
            )
            return _outcome(
                run,
                WorkflowState.DONE,
                result,
                verified=verification.match,
                trace=trace,
                note="TMS adapter failed after submit, but deterministic readback recovered the payable",
            )

        store.add_audit_event(
            run_id,
            "tms_write_adapter_failed",
            actor=actor,
            payload={
                "adapter_error_type": type(exc).__name__,
                "adapter_error": str(exc)[:500],
                "idempotency_key": prepared.idempotency_key,
                "possible_write_unverified": True,
            },
        )
        store.transition(run_id, WorkflowState.FAILED, actor=actor, event_type="entry_adapter_failed")
        trace.append("ENTERING→FAILED")
        _emit(
            ExecutionPhase.FAILED,
            "TMS entry failed and readback could not verify whether the write landed — routed to review.",
        )
        failed = PayableWriteResult(
            run_id=run_id,
            load_id=load_id,
            idempotency_key=prepared.idempotency_key,
            status=PayableWriteStatus.ADAPTER_FAILED,
            note=f"TMS adapter failed and readback could not verify write state: {type(exc).__name__}",
        )
        return _outcome(
            run,
            WorkflowState.FAILED,
            failed,
            verified=False,
            trace=trace,
            note="TMS adapter failed; possible write unverified and routed to review",
        )
    trace.append(f"submit:{result.status.value}")

    if result.status == PayableWriteStatus.SESSION_EXPIRED:
        store.transition(run_id, WorkflowState.WAITING_FOR_SESSION, actor=actor, event_type="entry_session_expired")
        trace.append("ENTERING→WAITING_FOR_SESSION")
        _emit(ExecutionPhase.WAITING_FOR_SESSION, "Session expired — waiting for a fresh login before entering.")
        return _outcome(run, WorkflowState.WAITING_FOR_SESSION, result, verified=False, trace=trace,
                        note="session expired; awaiting a fresh human-established session")
    if result.status == PayableWriteStatus.DUPLICATE_BLOCKED:
        store.transition(run_id, WorkflowState.FAILED, actor=actor, event_type="entry_duplicate_blocked")
        trace.append("ENTERING→FAILED")
        _emit(ExecutionPhase.FAILED, "Duplicate payable blocked — routed to review.")
        return _outcome(run, WorkflowState.FAILED, result, verified=False, trace=trace,
                        note="duplicate payable blocked; routed to review")

    _emit(ExecutionPhase.ENTERED, f"Payable entered: {result.external_ref}", external_ref=result.external_ref)

    verify_ctx = ToolContext(workflow_state=WorkflowState.ENTERING, actor=actor)
    verification = adapter.verify(
        run,
        expected_amount=amount,
        expected_idempotency_key=prepared.idempotency_key,
        context=verify_ctx,
    )
    trace.append(f"verify:match={verification.match}")

    if not verification.match:
        store.transition(run_id, WorkflowState.FAILED, actor=actor, event_type="entry_readback_mismatch")
        trace.append("ENTERING→FAILED")
        _emit(ExecutionPhase.FAILED, "Readback mismatch — payable not confirmed, routed to review.")
        return _outcome(run, WorkflowState.FAILED, result, verified=False, trace=trace,
                        note="readback mismatch; payable not confirmed, routed to review")

    _emit(ExecutionPhase.VERIFIED, f"Readback verified ${amount}.", external_ref=result.external_ref, amount=amount)
    store.transition(run_id, WorkflowState.ENTERED, actor=actor, event_type="entry_confirmed")
    store.transition(run_id, WorkflowState.DONE, actor=actor, event_type="entry_done")
    trace.extend(["ENTERING→ENTERED", "ENTERED→DONE"])
    _emit(ExecutionPhase.DONE, f"Marked DONE — {load_id} payable complete.", external_ref=result.external_ref, amount=amount)
    return _outcome(run, WorkflowState.DONE, result, verified=True, trace=trace,
                    note="payable entered and verified by readback")


def _recover_after_submit_exception(
    store: WorkflowStore,
    adapter: TmsWriteAdapter,
    run: WorkflowRun,
    *,
    prepared: PreparedPayableEntry,
    amount: str,
    actor: str,
    error: Exception,
) -> tuple[PayableWriteResult, ReadbackVerification] | None:
    """Recover a possible post-click browser crash by reading the TMS before failing the run."""
    try:
        verification = adapter.verify(
            run,
            expected_amount=amount,
            expected_idempotency_key=prepared.idempotency_key,
            context=ToolContext(workflow_state=WorkflowState.ENTERING, actor=actor),
        )
        record = adapter.ledger.get_payable(run.load_id)
    except Exception as read_exc:  # noqa: BLE001 - recovery is best-effort and audited below
        store.add_audit_event(
            run.id,
            "tms_write_adapter_recovery_readback_failed",
            actor=actor,
            payload={
                "submit_error_type": type(error).__name__,
                "submit_error": str(error)[:500],
                "readback_error_type": type(read_exc).__name__,
                "readback_error": str(read_exc)[:500],
                "idempotency_key": prepared.idempotency_key,
                "possible_write_unverified": True,
            },
        )
        return None

    record_key = record.get("idempotency_key") if isinstance(record, dict) else None
    if verification.match:
        result = PayableWriteResult(
            run_id=run.id,
            load_id=run.load_id,
            idempotency_key=prepared.idempotency_key,
            status=PayableWriteStatus.ADAPTER_FAILED,
            external_ref=record.get("external_ref") if isinstance(record, dict) else None,
            note="adapter failed after submit, but readback matched amount and idempotency key",
        )
        store.add_audit_event(
            run.id,
            "tms_write_adapter_failure_recovered",
            actor=actor,
            payload={
                "submit_error_type": type(error).__name__,
                "submit_error": str(error)[:500],
                "idempotency_key": prepared.idempotency_key,
                "external_ref": result.external_ref,
                "verified": True,
            },
        )
        return result, verification

    store.add_audit_event(
        run.id,
        "tms_write_adapter_recovery_unverified",
        actor=actor,
        payload={
            "submit_error_type": type(error).__name__,
            "submit_error": str(error)[:500],
            "idempotency_key": prepared.idempotency_key,
            "readback_match": verification.match,
            "record_idempotency_key": record_key,
            "possible_write_unverified": True,
        },
    )
    return None


def _outcome(
    run: WorkflowRun,
    final_state: WorkflowState,
    result: PayableWriteResult,
    *,
    verified: bool,
    trace: list[str],
    note: str,
) -> PayableEntryOutcome:
    return PayableEntryOutcome(
        run_id=run.id,
        load_id=run.load_id,
        final_state=final_state,
        write_status=result.status,
        verified=verified,
        external_ref=result.external_ref,
        trace=trace,
        note=note,
    )
