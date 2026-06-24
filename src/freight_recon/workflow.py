"""Workflow state, audit, and idempotency for Neyma V0.

This is intentionally an explicit state machine backed by SQLite. LangGraph can become useful
later for long-running human waits and tool-rich branches; the current slice needs durable runs,
content-hash idempotency, safe transitions, and auditable decisions.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from .extraction_bridge import apply_extraction_to_load
from .reconciliation import (
    FreightLoadForReconciliation,
    ReconciliationOutcome,
    ReconciliationResult,
    reconcile_load,
)


class WorkflowState(str, Enum):
    RECEIVED = "RECEIVED"
    EXTRACTED = "EXTRACTED"
    RECONCILED = "RECONCILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    APPROVED = "APPROVED"
    DISPUTED = "DISPUTED"
    REQUESTED_BACKUP = "REQUESTED_BACKUP"
    READY_FOR_ENTRY = "READY_FOR_ENTRY"
    ENTERING = "ENTERING"
    ENTERED = "ENTERED"
    DONE = "DONE"
    FAILED = "FAILED"
    WAITING_FOR_SESSION = "WAITING_FOR_SESSION"


TERMINAL_STATES = {WorkflowState.DONE, WorkflowState.FAILED}

ALLOWED_TRANSITIONS: dict[WorkflowState, set[WorkflowState]] = {
    WorkflowState.RECEIVED: {WorkflowState.EXTRACTED, WorkflowState.FAILED},
    WorkflowState.EXTRACTED: {WorkflowState.RECONCILED, WorkflowState.FAILED},
    WorkflowState.RECONCILED: {
        WorkflowState.DONE,
        WorkflowState.NEEDS_REVIEW,
        WorkflowState.READY_FOR_ENTRY,
        WorkflowState.FAILED,
    },
    WorkflowState.NEEDS_REVIEW: {
        WorkflowState.APPROVED,
        WorkflowState.DISPUTED,
        WorkflowState.REQUESTED_BACKUP,
        WorkflowState.DONE,
        WorkflowState.FAILED,
    },
    WorkflowState.APPROVED: {WorkflowState.READY_FOR_ENTRY, WorkflowState.DONE},
    WorkflowState.DISPUTED: {WorkflowState.DONE},
    WorkflowState.REQUESTED_BACKUP: {WorkflowState.NEEDS_REVIEW, WorkflowState.DONE},
    WorkflowState.READY_FOR_ENTRY: {WorkflowState.ENTERING, WorkflowState.DONE},
    WorkflowState.ENTERING: {WorkflowState.ENTERED, WorkflowState.FAILED, WorkflowState.WAITING_FOR_SESSION},
    WorkflowState.ENTERED: {WorkflowState.DONE},
    WorkflowState.WAITING_FOR_SESSION: {WorkflowState.ENTERING, WorkflowState.FAILED},
    WorkflowState.DONE: set(),
    WorkflowState.FAILED: set(),
}


class WorkflowError(RuntimeError):
    """Raised for invalid workflow operations."""


@dataclass(frozen=True)
class WorkflowRun:
    id: int
    load_id: str
    document_hash: str
    state: WorkflowState
    invoice_number: str | None
    carrier: str | None
    outcome: str | None
    reason: str | None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class WorkflowStore:
    """SQLite store for workflow runs and audit events."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._migrate()

    def close(self) -> None:
        self.conn.close()

    def _migrate(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS workflow_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                load_id TEXT NOT NULL,
                document_hash TEXT NOT NULL UNIQUE,
                state TEXT NOT NULL,
                invoice_number TEXT,
                carrier TEXT,
                outcome TEXT,
                reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                from_state TEXT,
                to_state TEXT,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES workflow_runs(id)
            );

            CREATE TABLE IF NOT EXISTS security_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def receive_document(self, load_id: str, document_hash: str, payload: dict[str, Any]) -> WorkflowRun:
        existing = self.get_run_by_hash(document_hash)
        if existing:
            self.add_audit_event(
                existing.id,
                "duplicate_received",
                actor="system",
                payload={"load_id": load_id, "document_hash": document_hash},
            )
            return existing

        now = utc_now()
        cur = self.conn.execute(
            """
            INSERT INTO workflow_runs (
                load_id, document_hash, state, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (load_id, document_hash, WorkflowState.RECEIVED.value, now, now),
        )
        self.conn.commit()
        run = self.get_run(cur.lastrowid)
        assert run is not None
        self.add_audit_event(run.id, "document_received", actor="system", payload=payload)
        return run

    def get_run(self, run_id: int) -> WorkflowRun | None:
        row = self.conn.execute("SELECT * FROM workflow_runs WHERE id = ?", (run_id,)).fetchone()
        return self._row_to_run(row) if row else None

    def get_run_by_hash(self, document_hash: str) -> WorkflowRun | None:
        row = self.conn.execute(
            "SELECT * FROM workflow_runs WHERE document_hash = ?", (document_hash,)
        ).fetchone()
        return self._row_to_run(row) if row else None

    def list_runs(self) -> list[WorkflowRun]:
        rows = self.conn.execute("SELECT * FROM workflow_runs ORDER BY id").fetchall()
        return [self._row_to_run(row) for row in rows]

    def transition(
        self,
        run_id: int,
        to_state: WorkflowState,
        *,
        actor: str = "system",
        event_type: str = "state_transition",
        payload: dict[str, Any] | None = None,
    ) -> WorkflowRun:
        run = self.get_run(run_id)
        if run is None:
            raise WorkflowError(f"workflow run not found: {run_id}")
        if to_state not in ALLOWED_TRANSITIONS[run.state]:
            raise WorkflowError(f"invalid transition: {run.state.value} -> {to_state.value}")

        self.conn.execute(
            "UPDATE workflow_runs SET state = ?, updated_at = ? WHERE id = ?",
            (to_state.value, utc_now(), run_id),
        )
        self.conn.commit()
        self.add_audit_event(
            run_id,
            event_type,
            actor=actor,
            from_state=run.state,
            to_state=to_state,
            payload=payload or {},
        )
        updated = self.get_run(run_id)
        assert updated is not None
        return updated

    def mark_extracted(self, run_id: int, extraction_payload: dict[str, Any]) -> WorkflowRun:
        run = self.transition(
            run_id,
            WorkflowState.EXTRACTED,
            event_type="extraction_recorded",
            payload=extraction_payload,
        )
        invoice_number = extraction_payload.get("invoice_number")
        carrier = extraction_payload.get("carrier")
        self.conn.execute(
            """
            UPDATE workflow_runs
            SET invoice_number = COALESCE(?, invoice_number),
                carrier = COALESCE(?, carrier),
                updated_at = ?
            WHERE id = ?
            """,
            (invoice_number, carrier, utc_now(), run_id),
        )
        self.conn.commit()
        updated = self.get_run(run_id)
        assert updated is not None
        return updated

    def mark_reconciled(self, run_id: int, result: ReconciliationResult) -> WorkflowRun:
        self.transition(
            run_id,
            WorkflowState.RECONCILED,
            event_type="reconciliation_completed",
            payload=result.model_dump(mode="json"),
        )
        self.conn.execute(
            """
            UPDATE workflow_runs
            SET invoice_number = ?, carrier = ?, outcome = ?, reason = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                result.invoice_number,
                result.carrier,
                result.outcome.value,
                "; ".join(result.reasons),
                utc_now(),
                run_id,
            ),
        )
        self.conn.commit()
        next_state = self.review_state_for_result(result)
        return self.transition(
            run_id,
            next_state,
            event_type="route_after_reconciliation",
            payload={"outcome": result.outcome.value, "reasons": result.reasons},
        )

    def refresh_reconciliation(self, run_id: int, result: ReconciliationResult) -> WorkflowRun:
        """Update a review run after new packet evidence arrives.

        This is for inbox trickle-in cases: a missing POD or backup can arrive after the initial
        review card. If deterministic reconciliation is now clean, the run can close to ``DONE``;
        otherwise the run remains in human review with updated outcome/reasons and an audit event.
        """
        run = self.get_run(run_id)
        if run is None:
            raise WorkflowError(f"workflow run not found: {run_id}")
        if run.state not in {WorkflowState.NEEDS_REVIEW, WorkflowState.REQUESTED_BACKUP}:
            raise WorkflowError(
                "reconciliation refresh requires NEEDS_REVIEW or REQUESTED_BACKUP, "
                f"got {run.state.value}"
            )

        self.conn.execute(
            """
            UPDATE workflow_runs
            SET invoice_number = ?, carrier = ?, outcome = ?, reason = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                result.invoice_number,
                result.carrier,
                result.outcome.value,
                "; ".join(result.reasons),
                utc_now(),
                run_id,
            ),
        )
        self.conn.commit()
        self.add_audit_event(
            run_id,
            "reconciliation_refreshed",
            actor="system",
            payload=result.model_dump(mode="json"),
        )
        next_state = self.review_state_for_result(result)
        if next_state == WorkflowState.DONE:
            return self.transition(
                run_id,
                WorkflowState.DONE,
                event_type="route_after_reconciliation_refresh",
                payload={"outcome": result.outcome.value, "reasons": result.reasons},
            )
        if run.state == WorkflowState.REQUESTED_BACKUP and next_state == WorkflowState.NEEDS_REVIEW:
            return self.transition(
                run_id,
                WorkflowState.NEEDS_REVIEW,
                event_type="route_after_reconciliation_refresh",
                payload={"outcome": result.outcome.value, "reasons": result.reasons},
            )
        updated = self.get_run(run_id)
        assert updated is not None
        return updated

    def add_audit_event(
        self,
        run_id: int,
        event_type: str,
        *,
        actor: str,
        payload: dict[str, Any],
        from_state: WorkflowState | None = None,
        to_state: WorkflowState | None = None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO audit_events (
                run_id, event_type, actor, from_state, to_state, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                event_type,
                actor,
                from_state.value if from_state else None,
                to_state.value if to_state else None,
                json.dumps(payload, sort_keys=True),
                utc_now(),
            ),
        )
        self.conn.commit()

    def add_security_event(
        self,
        event_type: str,
        *,
        actor: str,
        payload: dict[str, Any],
    ) -> None:
        """Record an audit event that cannot safely be tied to a trusted workflow run."""
        self.conn.execute(
            """
            INSERT INTO security_events (
                event_type, actor, payload_json, created_at
            ) VALUES (?, ?, ?, ?)
            """,
            (event_type, actor, json.dumps(payload, sort_keys=True), utc_now()),
        )
        self.conn.commit()

    def audit_events(self, run_id: int | None = None) -> list[dict[str, Any]]:
        if run_id is None:
            rows = self.conn.execute("SELECT * FROM audit_events ORDER BY id").fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM audit_events WHERE run_id = ? ORDER BY id", (run_id,)
            ).fetchall()
        return [
            {
                "id": row["id"],
                "run_id": row["run_id"],
                "event_type": row["event_type"],
                "actor": row["actor"],
                "from_state": row["from_state"],
                "to_state": row["to_state"],
                "payload": json.loads(row["payload_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def security_events(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM security_events ORDER BY id").fetchall()
        return [
            {
                "id": row["id"],
                "run_id": None,
                "event_type": row["event_type"],
                "actor": row["actor"],
                "from_state": None,
                "to_state": None,
                "payload": json.loads(row["payload_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    @staticmethod
    def review_state_for_result(result: ReconciliationResult) -> WorkflowState:
        if result.outcome.value == "MATCHED":
            return WorkflowState.DONE
        if result.outcome.value in {"VARIANCE", "NEEDS_REVIEW", "DUPLICATE"}:
            return WorkflowState.NEEDS_REVIEW
        return WorkflowState.FAILED

    @staticmethod
    def _row_to_run(row: sqlite3.Row) -> WorkflowRun:
        return WorkflowRun(
            id=row["id"],
            load_id=row["load_id"],
            document_hash=row["document_hash"],
            state=WorkflowState(row["state"]),
            invoice_number=row["invoice_number"],
            carrier=row["carrier"],
            outcome=row["outcome"],
            reason=row["reason"],
        )


def process_load_packet(
    store: WorkflowStore,
    load: FreightLoadForReconciliation,
    *,
    primary_document_path: str | Path,
    seen_invoice_keys: set[tuple[str, str]] | None = None,
    extractor: Callable[[str | Path], Any] | None = None,
    confidence_threshold: float = 0.85,
) -> WorkflowRun:
    """Run one load packet through receive -> extract -> reconcile -> route.

    When ``extractor`` is ``None`` (the default), the invoice side is taken from the synthetic
    ground-truth ``load`` — fast, deterministic, no API (used by tests and the local dogfood spine).
    When an extractor is injected, the carrier-invoice PDF is read by real vision extraction and the
    *extracted* invoice side is reconciled against the source-of-truth rate side. Deterministic
    Python still owns the money decision; low-confidence required fields or a load-link mismatch
    force human review (they never auto-clear).
    """
    doc_hash = sha256_file(primary_document_path)
    run = store.receive_document(
        load.load_id,
        doc_hash,
        payload={"primary_document": str(primary_document_path), "load_id": load.load_id},
    )

    if run.state in TERMINAL_STATES or run.state == WorkflowState.NEEDS_REVIEW:
        return run

    if extractor is None:
        run = store.mark_extracted(
            run.id,
            {
                "invoice_number": load.invoice_number,
                "carrier": load.carrier,
                "source": "synthetic_ground_truth",
            },
        )
        result = reconcile_load(load, seen_invoice_keys=seen_invoice_keys)
        return store.mark_reconciled(run.id, result)

    extraction = extractor(primary_document_path)
    if getattr(extraction, "extraction", None) is None:
        # Extraction failed — route to a human, never guess, never crash.
        run = store.mark_extracted(
            run.id,
            {"source": "vision_extraction", "model": getattr(extraction, "model", None),
             "error": getattr(extraction, "error", "extraction returned no result")},
        )
        result = ReconciliationResult(
            load_id=load.load_id,
            invoice_number=load.invoice_number or "",
            carrier=load.carrier,
            outcome=ReconciliationOutcome.NEEDS_REVIEW,
            reasons=[f"extraction failed: {getattr(extraction, 'error', 'no result')}"],
            needs_human_review=True,
        )
        return store.mark_reconciled(run.id, result)

    recon_load, low_confidence, link_ok = apply_extraction_to_load(
        load, extraction.extraction, confidence_threshold=confidence_threshold
    )
    run = store.mark_extracted(
        run.id,
        {
            "invoice_number": recon_load.invoice_number,
            "carrier": recon_load.carrier,
            "source": "vision_extraction",
            "model": getattr(extraction, "model", None),
            "low_confidence_required": low_confidence,
            "link_ok": link_ok,
        },
    )
    result = reconcile_load(recon_load, seen_invoice_keys=seen_invoice_keys)
    if low_confidence or not link_ok:
        # The confidence gate: a low-confidence read or a wrong load link never auto-clears.
        reasons = list(result.reasons)
        if low_confidence:
            reasons.append(f"low-confidence extraction on required field(s): {', '.join(low_confidence)}")
        if not link_ok:
            reasons.append("extracted load/PRO does not match the linked load id")
        result = result.model_copy(
            update={
                "outcome": ReconciliationOutcome.NEEDS_REVIEW,
                "reasons": reasons,
                "needs_human_review": True,
            }
        )
    return store.mark_reconciled(run.id, result)
