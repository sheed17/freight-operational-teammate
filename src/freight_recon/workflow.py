"""Workflow state, audit, and idempotency for Neyma V0.

This is intentionally an explicit state machine backed by SQLite. LangGraph can become useful
later for long-running human waits and tool-rich branches; the current slice needs durable runs,
content-hash idempotency, safe transitions, and auditable decisions.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from types import SimpleNamespace
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from .extraction_bridge import reconciliation_from_extraction
from .reconciliation import (
    FreightLoadForReconciliation,
    ReconciliationResult,
    reconcile_load,
)
from .workflow_direction import WorkflowDirection


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
    workflow_direction: WorkflowDirection
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


from .schema import (
    SchemaNotReady,
    create_canonical_schema,
    enable_and_verify_foreign_keys,
    schema_readiness_problems,
)
from .tenant import require_tenant

# Internal, fixed. These names are interpolated into SQL for per-tenant id allocation, so they may
# never come from a caller: the tuple IS the allowlist.
_ID_ALLOCATED_TABLES = frozenset({"workflow_runs", "audit_events", "security_events"})


class WorkflowStore:
    """SQLite store for workflow runs and audit events. Bound to exactly one tenant, always."""

    def __init__(self, db_path: str | Path, *, tenant: str) -> None:
        """A store belongs to exactly ONE tenant, named at construction and never after.

        `tenant` is keyword-only and required: there is no positional slot to forget, no default to
        inherit, and no setter to change it later. A caller that cannot name its tenant is a caller
        that does not know whose data it is about to touch, and the safe answer to that is to stop.

        U2.6BC: the tenant bound here is now USED. All 22 affected methods scope their SQL by it,
        every one of the seven tenant-owned tables is tenant-first, and a database that cannot
        honour that is refused at construction rather than served unsafely.
        """
        # Validated at the boundary, so an invalid tenant cannot reach a query later disguised as a
        # valid one. `require_tenant` refuses None, blank, non-strings, and the sentinels.
        self._tenant = require_tenant(tenant, context=f"WorkflowStore({db_path})")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        # The callback now runs concurrent threads (background agent operations + Slack reads + the
        # loop), all sharing this on-disk store. WAL lets a reader and the writer proceed at once
        # instead of blocking each other, and an explicit busy timeout turns a transient lock into a
        # short wait rather than an OperationalError that would kill a background operation mid-write.
        try:
            self.conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError:
            # Another process/thread may be initializing the same store. The busy timeout still protects
            # normal transactions; this connection can proceed with the existing journal mode.
            pass
        self.conn.execute("PRAGMA busy_timeout=30000")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        # The tenant-consistent foreign keys are half of the cross-tenant relationship rule, and they
        # do nothing at all unless this pragma actually took. It is verified, not assumed.
        enable_and_verify_foreign_keys(self.conn)
        # Cached against SQLite's own DDL counter rather than a bare bool: `PRAGMA schema_version`
        # changes on every schema change, so a database altered under a live store is re-checked and
        # fails closed instead of coasting on a verdict that was true an hour ago.
        self._schema_ready_version: int | None = None
        self._migrate()
        # Fail HERE, not at the first query. A new binary must not open a legacy database at all:
        # its unscoped predecessor and this tenant-first schema cannot both be right.
        self._require_schema_ready()

    def close(self) -> None:
        self.conn.close()

    @property
    def tenant(self) -> str:
        """The one tenant this store belongs to. Read-only: there is no setter, deliberately.

        Rebinding an open store to another tenant would make every prior read and write ambiguous
        after the fact, which is worse than never having had a tenant at all.
        """
        return self._tenant

    def _migrate(self) -> None:
        """Create a FRESH database directly in the canonical tenant-first shape. Migrate nothing.

        Three cases, and only three:

        1. EMPTY database -> built canonical in one pass, from the single `TARGET_SCHEMA` text the
           migration itself uses. It never begins legacy, never needs legacy data to obtain
           `effect_grants`, and never needs a second startup to become correct. Every fixture and
           every test database gets the canonical shape for free, which is the point.
        2. ALREADY-CANONICAL database -> nothing to do.
        3. ANYTHING ELSE (pre-migration, half-migrated) -> we touch NOTHING and let
           `_require_schema_ready()` refuse with the full list of reasons.

        Case 3 is why this is not a `CREATE TABLE IF NOT EXISTS` sweep. Against a legacy database
        that sweep would happily add `effect_grants` beside the legacy tables and then die trying to
        index a `tenant` column that does not exist - having already mutated a database this binary
        must not write to. Business operations do not migrate schemas here; a human runs
        `migrations/phase2_tenant_first.py`, which is staged, auditable and resumable.
        """
        present = {
            r[0]
            for r in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if not {t for t in present if not t.startswith("sqlite_")}:
            create_canonical_schema(self.conn)
            return
        if not schema_readiness_problems(self.conn):
            return
        # Deliberately no `else`. An existing non-canonical database is the migration's business.

    def _require_schema_ready(self) -> None:
        """The ONE readiness contract. Every affected method calls it before tenant-owned SQL.

        There is no per-method interpretation, no legacy fallback, no "try the new query and then the
        old one", and no compatibility mode. A missing tenant column is not a reason to run the query
        that ignores tenants - that query IS the defect this phase removes.
        """
        version = self.conn.execute("PRAGMA schema_version").fetchone()[0]
        if version == self._schema_ready_version:
            return
        problems = schema_readiness_problems(self.conn)
        if problems:
            self._schema_ready_version = None
            raise SchemaNotReady(
                f"the Phase-2 tenant-first migration is required or incomplete for {self.db_path}; "
                f"refusing to run tenant-owned SQL against it:\n  - " + "\n  - ".join(problems)
            )
        self._schema_ready_version = version

    @contextmanager
    def _write_txn(self):
        """One serialized write. BEGIN IMMEDIATE takes the write lock before the read.

        Per-tenant row ids are allocated as MAX(id)+1 within the tenant, so the read that chooses the
        id and the write that uses it must be one atomic step or two concurrent ingests pick the same
        id and one loses. IMMEDIATE (not DEFERRED) is what makes that true.
        """
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self.conn.rollback()
            raise
        else:
            self.conn.commit()

    def _next_id(self, table: str) -> int:
        """The next row id WITHIN this tenant. Ids are per-tenant and deliberately collide across
        tenants - that collision is the thing the tests reuse to prove isolation is real."""
        if table not in _ID_ALLOCATED_TABLES:
            raise WorkflowError(f"id allocation is not defined for {table!r}")
        row = self.conn.execute(
            f"SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM {table} WHERE tenant = ?",
            (self._tenant,),
        ).fetchone()
        return int(row["next_id"])

    def receive_document(
        self,
        load_id: str,
        document_hash: str,
        payload: dict[str, Any],
        *,
        workflow_direction: WorkflowDirection | str = WorkflowDirection.CARRIER_PAYABLE,
    ) -> WorkflowRun:
        """Receive a document for THIS tenant. Identical bytes in another tenant are not our business.

        THE LIVE CROSS-TENANT DEFECT CLOSED. `document_hash` was globally UNIQUE and the dedup
        lookup was global, so when two tenants filed the same bytes the second tenant's document was
        silently called a duplicate of the first tenant's - and returned the first tenant's run.
        Deduplication now happens strictly WITHIN the bound tenant, there is no global hash preflight
        of any kind, and the uniqueness that enforces it is `(tenant, document_hash)`.
        """
        self._require_schema_ready()
        direction = WorkflowDirection(workflow_direction)
        scoped_document_hash = _direction_scoped_document_hash(document_hash, direction)

        # The duplicate check and the insert are ONE serialized step: two concurrent deliveries of
        # the same bytes must converge on one run, deterministically, not race for an id.
        duplicate_id: int | None = None
        run_id: int | None = None
        with self._write_txn():
            row = self.conn.execute(
                "SELECT id FROM workflow_runs WHERE tenant = ? AND document_hash = ?",
                (self._tenant, scoped_document_hash),
            ).fetchone()
            if row is not None:
                duplicate_id = int(row["id"])
            else:
                now = utc_now()
                run_id = self._next_id("workflow_runs")
                self.conn.execute(
                    """
                    INSERT INTO workflow_runs (
                        tenant, id, load_id, document_hash, state, workflow_direction,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self._tenant,
                        run_id,
                        load_id,
                        scoped_document_hash,
                        WorkflowState.RECEIVED.value,
                        direction.value,
                        now,
                        now,
                    ),
                )

        if duplicate_id is not None:
            existing = self.get_run(duplicate_id)
            assert existing is not None
            self.add_audit_event(
                existing.id,
                "duplicate_received",
                actor="system",
                payload={
                    "load_id": load_id,
                    "document_hash": scoped_document_hash,
                    "source_document_hash": document_hash,
                    "workflow_direction": direction.value,
                },
            )
            return existing

        run = self.get_run(run_id)
        assert run is not None
        self.add_audit_event(run.id, "document_received", actor="system", payload=payload)
        return run

    def get_run(self, run_id: int) -> WorkflowRun | None:
        """This tenant's run by id. Another tenant's run with the same id is ABSENT, not forbidden.

        Run ids are per-tenant and collide by construction, so a bare id is not an identity. The
        answer for another tenant's row is `None` - identical to a row that never existed - because
        distinguishing the two would disclose that it does.
        """
        self._require_schema_ready()
        row = self.conn.execute(
            "SELECT * FROM workflow_runs WHERE tenant = ? AND id = ?", (self._tenant, run_id)
        ).fetchone()
        return self._row_to_run(row) if row else None

    def get_run_by_hash(self, document_hash: str) -> WorkflowRun | None:
        """The read half of the document-hash defect, closed.

        Tenant A's row can never satisfy tenant B's lookup, and the absence of a row here says
        nothing whatsoever about whether another tenant holds those bytes.
        """
        self._require_schema_ready()
        row = self.conn.execute(
            "SELECT * FROM workflow_runs WHERE tenant = ? AND document_hash = ?",
            (self._tenant, document_hash),
        ).fetchone()
        return self._row_to_run(row) if row else None

    def list_runs(self) -> list[WorkflowRun]:
        """This tenant's runs. Pagination and ordering happen INSIDE the tenant partition."""
        self._require_schema_ready()
        rows = self.conn.execute(
            "SELECT * FROM workflow_runs WHERE tenant = ? ORDER BY id", (self._tenant,)
        ).fetchall()
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
        self._require_schema_ready()
        run = self.get_run(run_id)
        if run is None:
            raise WorkflowError(f"workflow run not found: {run_id}")
        if to_state not in ALLOWED_TRANSITIONS[run.state]:
            raise WorkflowError(f"invalid transition: {run.state.value} -> {to_state.value}")

        cur = self.conn.execute(
            "UPDATE workflow_runs SET state = ?, updated_at = ? "
            "WHERE tenant = ? AND id = ? AND state = ?",
            (to_state.value, utc_now(), self._tenant, run_id, run.state.value),
        )
        if cur.rowcount != 1:
            self.conn.rollback()
            raise WorkflowError(
                f"workflow run {run_id} changed while transitioning from {run.state.value}"
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
        self._require_schema_ready()
        run = self.transition(
            run_id,
            WorkflowState.EXTRACTED,
            event_type="extraction_recorded",
            payload=extraction_payload,
        )
        invoice_number = extraction_payload.get("invoice_number")
        carrier = extraction_payload.get("carrier")
        cur = self.conn.execute(
            """
            UPDATE workflow_runs
            SET invoice_number = COALESCE(?, invoice_number),
                carrier = COALESCE(?, carrier),
                updated_at = ?
            WHERE tenant = ? AND id = ?
            """,
            (invoice_number, carrier, utc_now(), self._tenant, run_id),
        )
        self._require_one_row(cur.rowcount, "mark_extracted", run_id)
        self.conn.commit()
        updated = self.get_run(run_id)
        assert updated is not None
        return updated

    def mark_reconciled(self, run_id: int, result: ReconciliationResult) -> WorkflowRun:
        self._require_schema_ready()
        self.transition(
            run_id,
            WorkflowState.RECONCILED,
            event_type="reconciliation_completed",
            payload=result.model_dump(mode="json"),
        )
        cur = self.conn.execute(
            """
            UPDATE workflow_runs
            SET workflow_direction = ?, invoice_number = ?, carrier = ?, outcome = ?, reason = ?, updated_at = ?
            WHERE tenant = ? AND id = ?
            """,
            (
                result.workflow_direction.value,
                result.invoice_number,
                result.carrier,
                result.outcome.value,
                "; ".join(result.reasons),
                utc_now(),
                self._tenant,
                run_id,
            ),
        )
        self._require_one_row(cur.rowcount, "mark_reconciled", run_id)
        self.conn.commit()
        next_state = self.review_state_for_result(result)
        return self.transition(
            run_id,
            next_state,
            event_type="route_after_reconciliation",
            payload={
                "outcome": result.outcome.value,
                "workflow_direction": result.workflow_direction.value,
                "reasons": result.reasons,
            },
        )

    def refresh_reconciliation(self, run_id: int, result: ReconciliationResult) -> WorkflowRun:
        """Update a review run after new packet evidence arrives.

        This is for inbox trickle-in cases: a missing POD or backup can arrive after the initial
        review card. If deterministic reconciliation is now clean, the run can close to ``DONE``;
        otherwise the run remains in human review with updated outcome/reasons and an audit event.
        """
        self._require_schema_ready()
        run = self.get_run(run_id)
        if run is None:
            raise WorkflowError(f"workflow run not found: {run_id}")
        if run.state not in {WorkflowState.NEEDS_REVIEW, WorkflowState.REQUESTED_BACKUP}:
            raise WorkflowError(
                "reconciliation refresh requires NEEDS_REVIEW or REQUESTED_BACKUP, "
                f"got {run.state.value}"
            )

        cur = self.conn.execute(
            """
            UPDATE workflow_runs
            SET workflow_direction = ?, invoice_number = ?, carrier = ?, outcome = ?, reason = ?, updated_at = ?
            WHERE tenant = ? AND id = ?
            """,
            (
                result.workflow_direction.value,
                result.invoice_number,
                result.carrier,
                result.outcome.value,
                "; ".join(result.reasons),
                utc_now(),
                self._tenant,
                run_id,
            ),
        )
        self._require_one_row(cur.rowcount, "refresh_reconciliation", run_id)
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
                payload={
                    "outcome": result.outcome.value,
                    "workflow_direction": result.workflow_direction.value,
                    "reasons": result.reasons,
                },
            )
        if run.state == WorkflowState.REQUESTED_BACKUP and next_state == WorkflowState.NEEDS_REVIEW:
            return self.transition(
                run_id,
                WorkflowState.NEEDS_REVIEW,
                event_type="route_after_reconciliation_refresh",
                payload={
                    "outcome": result.outcome.value,
                    "workflow_direction": result.workflow_direction.value,
                    "reasons": result.reasons,
                },
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
        """Attach evidence to THIS tenant's run.

        The tenant travels in the foreign key itself - `(tenant, run_id) -> workflow_runs(tenant, id)`
        - so an audit row cannot be spelled against another tenant's run even when the numeric ids
        match, which after per-tenant id allocation they routinely do.
        """
        self._require_schema_ready()
        with self._write_txn():
            self.conn.execute(
                """
                INSERT INTO audit_events (
                    tenant, id, run_id, event_type, actor, from_state, to_state, payload_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self._tenant,
                    self._next_id("audit_events"),
                    run_id,
                    event_type,
                    actor,
                    from_state.value if from_state else None,
                    to_state.value if to_state else None,
                    json.dumps(payload, sort_keys=True),
                    utc_now(),
                ),
            )

    def add_security_event(
        self,
        event_type: str,
        *,
        actor: str,
        payload: dict[str, Any],
    ) -> None:
        """Record an audit event that cannot safely be tied to a trusted workflow run.

        It still belongs to a tenant. Security events were pooled across tenants, which made one
        tenant's forged-token attempt readable as another's.
        """
        self._require_schema_ready()
        with self._write_txn():
            self.conn.execute(
                """
                INSERT INTO security_events (
                    tenant, id, event_type, actor, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    self._tenant,
                    self._next_id("security_events"),
                    event_type,
                    actor,
                    json.dumps(payload, sort_keys=True),
                    utc_now(),
                ),
            )

    def claim_operation_action(
        self,
        action_id: str,
        *,
        actor: str,
        payload: dict[str, Any],
    ) -> bool:
        """Atomically claim an operation approval action id.

        Returns ``False`` if another request already claimed the same action. This is separate from
        audit logging so threaded Slack retries/double-clicks cannot both run the router before an
        audit event is written.

        The claim is single-use WITHIN this tenant. It was single-use globally, so one tenant's
        action id consumed another tenant's claim and the second tenant's operator watched their
        own button do nothing.
        """
        self._require_schema_ready()
        try:
            self.conn.execute(
                """
                INSERT INTO operation_action_claims (
                    tenant, action_id, actor, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (self._tenant, action_id, actor, json.dumps(payload, sort_keys=True), utc_now()),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False

    def claim_delivery_action(
        self,
        action_id: str,
        *,
        run_id: int,
        actor: str,
        payload: dict[str, Any],
    ) -> bool:
        """Atomically claim a signed review action token before applying it, within this tenant.

        The `(tenant, run_id)` foreign key means a claim cannot be attached to another tenant's run:
        a token that names a run id this tenant does not own is refused by the database, not merely
        by the caller's good intentions.
        """
        self._require_schema_ready()
        try:
            self.conn.execute(
                """
                INSERT INTO delivery_action_claims (
                    tenant, action_id, run_id, actor, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    self._tenant,
                    action_id,
                    run_id,
                    actor,
                    json.dumps(payload, sort_keys=True),
                    utc_now(),
                ),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Either the claim is already taken in this tenant, or the run belongs to another tenant
            # and the tenant-consistent FK refused it. Both are "no", and neither may be
            # distinguished for the caller - the difference is another tenant's business.
            self.conn.rollback()
            return False

    def operation_commit_claim(
        self,
        *,
        commit_key: str,
    ) -> dict[str, Any] | None:
        """This tenant's reservation for a Commit Key, read from the ONE canonical ledger.

        Tenant A could observe tenant B's effect reservation - and, worse, act on its status. The
        same Commit Key in another tenant is a different effect and reads as absent here.
        """
        self._require_schema_ready()
        row = self.conn.execute(
            "SELECT * FROM effect_grants WHERE tenant = ? AND commit_key = ?",
            (self._tenant, commit_key),
        ).fetchone()
        return self._grant_to_claim(row) if row is not None else None

    def legacy_commit_rows(
        self,
        *,
        lane: str,
        load_ref: str,
        party: str,
        canonical_commit_key: str,
    ) -> list[dict[str, Any]]:
        """Pre-Phase-1 reservations for this SAME logical effect, found by their stored columns.

        THE COMPATIBILITY BRIDGE. Scope: exactly the rows written by the deleted amount-keyed
        algorithm, i.e. rows whose descriptive columns identify this logical effect but whose
        `commit_key` is not the canonical one. Deterministic: a plain indexed lookup on stored
        columns, with no recomputation of the old key and no guessing.

        Why it must exist: the old key mixed the amount in, so a historically-committed invoice
        computes a DIFFERENT key today. Without this lookup the canonical claim would succeed, and we
        would cheerfully raise a second invoice for an effect that already happened - the migration
        itself becoming the double-commit.

        What it may NOT do: authorize anything. It only ever BLOCKS. It returns rows; the caller
        escalates. It never infers success, never merges rows, and never converts a legacy row into a
        canonical reservation - two legacy rows for one logical effect are evidence of a historical
        double-commit and belong to a human, not to an algorithm.

        Removal: Phase 2 (U2.4), when the ledger backfill adjudicates these rows explicitly.
        Deletion condition: zero legacy rows remain, proven by the backfill's dry-run report.

        U2.6BC: the `tenant` PARAMETER is gone. It was the store's most dangerous remaining argument
        - a caller could ask "what history exists for tenant X?" of a store bound to tenant Y and
        receive it, so cross-tenant history could be returned as THIS tenant's compatibility
        evidence and escalate (or fail to escalate) an effect on another tenant's past.
        """
        self._require_schema_ready()
        rows = self.conn.execute(
            """
            SELECT * FROM effect_grants
            WHERE tenant = ? AND lane = ? AND load_ref = ? AND party = ? AND commit_key != ?
            """,
            (self._tenant, lane, load_ref, party, canonical_commit_key),
        ).fetchall()
        return [self._grant_to_claim(r) for r in rows]

    def claim_operation_commit(
        self,
        *,
        commit_key: str,
        target_system: str,
        lane: str,
        load_ref: str,
        party: str,
        approved_amount: str = "",
        payload: dict[str, Any],
    ) -> bool:
        """Atomically reserve/record this logical external effect, by its canonical Commit Key.

        The reservation happens before the browser agent can click a committing button. A crash after
        reservation fails closed and blocks a blind retry instead of risking a double-write.

        The caller supplies the Commit Key; this store no longer derives one. That is the Phase-1
        correction: the key identifies the logical EFFECT, and `approved_amount` is stored here only
        as a MATERIAL FACT of the decision - a column, never a key. Two approvals at different
        amounts for one invoice now converge on ONE reservation instead of raising two invoices.
        `approved_amount` is "" for non-money effects, which are now reserved too.

        U2.6BC: the `tenant` PARAMETER is gone and the row is written to the ONE canonical ledger.
        The reservation belongs to the store's tenant - full stop. Previously a caller named the
        tenant, so a store bound to tenant Y could reserve an effect "for" tenant X, and the global
        `commit_key` PRIMARY KEY meant tenant A's Commit Key BLOCKED tenant B's legitimate invoice:
        the same load reference at two brokerages, and the second one silently never raised. The
        uniqueness is now `(tenant, commit_key)`, so the same Commit Key in two tenants is two
        effects, and a duplicate within one tenant is still exactly one.

        What this deliberately is NOT: the Phase-3 claim CAS. The row is written `GRANTED`. Nothing
        here transitions it to `CLAIMED`, and no second effect namespace is created to hold it.
        """
        self._require_schema_ready()
        now = utc_now()
        try:
            self.conn.execute(
                """
                INSERT INTO effect_grants (
                    tenant, grant_id, commit_key, action_class, target_system, target_resource_id,
                    target_operation, state, approved_amount, material_facts_json,
                    lane, load_ref, party, payload_json, issued_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self._tenant,
                    commit_key,
                    commit_key,
                    lane,
                    target_system,
                    f"{load_ref}|{party}",
                    lane,
                    "GRANTED",
                    approved_amount,
                    # Material Facts stay SEPARATE from identity, by construction. The amount is
                    # preserved so drift stays auditable; it may never key a row again.
                    json.dumps({"approved_amount": approved_amount}, sort_keys=True),
                    lane,
                    load_ref,
                    party,
                    json.dumps(payload, sort_keys=True),
                    now,
                    now,
                ),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False

    def update_operation_commit_payload(
        self,
        *,
        commit_key: str,
        payload: dict[str, Any],
    ) -> None:
        """Update the payload of a reservation THIS tenant holds.

        Strict on row count: a caller only updates a reservation it just claimed, so zero rows means
        the reservation vanished or belongs to another tenant. Both are anomalies, and silently
        updating nothing would let the caller believe it had recorded an outcome it did not.
        """
        self._require_schema_ready()
        cur = self.conn.execute(
            """
            UPDATE effect_grants
            SET payload_json = ?
            WHERE tenant = ? AND commit_key = ?
            """,
            (json.dumps(payload, sort_keys=True), self._tenant, commit_key),
        )
        if cur.rowcount != 1:
            self.conn.rollback()
            raise WorkflowError(
                f"expected exactly one reservation to update for commit_key {commit_key!r} in "
                f"tenant {self._tenant!r}, {cur.rowcount} row(s) matched"
            )
        self.conn.commit()

    def release_operation_commit(self, *, commit_key: str) -> None:
        """Release a reservation THIS tenant holds. Tenant A could release tenant B's reservation.

        Row-count posture, deliberately asymmetric with the update above and worth stating: release
        is IDEMPOTENT by design - it is called on failure paths that may already have released - so
        zero rows is a legitimate outcome. More than one row is not, and cannot be: `(tenant,
        commit_key)` is unique. If that ever fires, the uniqueness this phase installed is gone.
        """
        self._require_schema_ready()
        cur = self.conn.execute(
            "DELETE FROM effect_grants WHERE tenant = ? AND commit_key = ?",
            (self._tenant, commit_key),
        )
        if cur.rowcount > 1:
            self.conn.rollback()
            raise WorkflowError(
                f"{cur.rowcount} reservations matched commit_key {commit_key!r} in tenant "
                f"{self._tenant!r}; (tenant, commit_key) is supposed to be unique"
            )
        self.conn.commit()

    def claim_autonomous_run(
        self,
        tenant: str,
        lane: str,
        *,
        cap: int,
        day: str | None = None,
    ) -> tuple[bool, int]:
        """Atomically reserve one autonomous run within the daily cap."""
        if cap < 1:
            return False, 0
        run_day = day or datetime.now(timezone.utc).date().isoformat()
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            row = self.conn.execute(
                """
                SELECT runs FROM autonomous_run_counters
                WHERE tenant = ? AND lane = ? AND day = ?
                """,
                (tenant, lane, run_day),
            ).fetchone()
            current = int(row["runs"]) if row else 0
            if current >= cap:
                self.conn.rollback()
                return False, current
            updated = current + 1
            self.conn.execute(
                """
                INSERT INTO autonomous_run_counters (tenant, lane, day, runs, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(tenant, lane, day)
                DO UPDATE SET runs = excluded.runs, updated_at = excluded.updated_at
                """,
                (tenant, lane, run_day, updated, utc_now()),
            )
            self.conn.commit()
            return True, updated
        except Exception:
            self.conn.rollback()
            raise

    def autonomous_runs_today(self, tenant: str, lane: str, *, day: str | None = None) -> int:
        run_day = day or datetime.now(timezone.utc).date().isoformat()
        row = self.conn.execute(
            """
            SELECT runs FROM autonomous_run_counters
            WHERE tenant = ? AND lane = ? AND day = ?
            """,
            (tenant, lane, run_day),
        ).fetchone()
        return int(row["runs"]) if row else 0

    def record_operation_token_amount(
        self,
        *,
        token_fingerprint: str,
        action_id: str,
        approved_amount: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Bind an APPROVED AMOUNT to a token fingerprint, within this tenant.

        This column is what an operator agreed to pay. It was bound in a GLOBAL namespace, so two
        tenants whose tokens fingerprinted alike shared one approved amount - and the conflict
        target silently OVERWROTE it. The conflict target is now `(tenant, token_fingerprint)`.
        """
        self._require_schema_ready()
        normalized_amount = normalize_money_amount(approved_amount)
        self.conn.execute(
            """
            INSERT INTO operation_token_amounts (
                tenant, token_fingerprint, action_id, approved_amount, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(tenant, token_fingerprint)
            DO UPDATE SET approved_amount = excluded.approved_amount,
                          action_id = excluded.action_id,
                          payload_json = excluded.payload_json
            """,
            (
                self._tenant,
                token_fingerprint,
                action_id,
                normalized_amount,
                json.dumps(payload or {}, sort_keys=True),
                utc_now(),
            ),
        )
        self.conn.commit()

    def operation_token_amount(self, token_fingerprint: str | None) -> str | None:
        """This tenant's approved amount for a fingerprint. Never another tenant's figure."""
        self._require_schema_ready()
        if not token_fingerprint:
            return None
        row = self.conn.execute(
            "SELECT approved_amount FROM operation_token_amounts "
            "WHERE tenant = ? AND token_fingerprint = ?",
            (self._tenant, token_fingerprint),
        ).fetchone()
        return str(row["approved_amount"]) if row else None

    def audit_events(self, run_id: int | None = None) -> list[dict[str, Any]]:
        """This tenant's audit history. Both branches are scoped - the `None` branch especially.

        The unfiltered branch is the one that leaked: it returned EVERY tenant's history, and it is
        the branch a support tool reaches for.
        """
        self._require_schema_ready()
        if run_id is None:
            rows = self.conn.execute(
                "SELECT * FROM audit_events WHERE tenant = ? ORDER BY id", (self._tenant,)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM audit_events WHERE tenant = ? AND run_id = ? ORDER BY id",
                (self._tenant, run_id),
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
        """This tenant's security events. They were pooled across every tenant in the database."""
        self._require_schema_ready()
        rows = self.conn.execute(
            "SELECT * FROM security_events WHERE tenant = ? ORDER BY id", (self._tenant,)
        ).fetchall()
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

    def _require_one_row(self, rowcount: int, operation: str, run_id: int) -> None:
        """Row-count behaviour is deterministic, and zero is never silently fine.

        Zero rows now means one of exactly two things, and neither is survivable: the run does not
        exist, or it belongs to another tenant. Before the tenant predicate a cross-tenant write
        matched and succeeded; the danger of leaving this unchecked is that the same write now
        matches nothing and reports success just as cheerfully.
        """
        if rowcount != 1:
            self.conn.rollback()
            raise WorkflowError(
                f"{operation}: expected exactly one row for run {run_id} in tenant "
                f"{self._tenant!r}, {rowcount} matched"
            )

    @staticmethod
    def _grant_to_claim(row: sqlite3.Row) -> dict[str, Any]:
        """One canonical ledger row, in the reservation shape its callers already speak.

        The ledger is the ONE table; this is a projection of it, not a second namespace. `tenant`
        comes from the ROW (which the tenant predicate has already constrained to ours) rather than
        from `self`, so a projection can never assert an ownership the row does not carry.
        """
        return {
            "commit_key": row["commit_key"],
            "tenant": row["tenant"],
            "lane": row["lane"],
            "load_ref": row["load_ref"],
            "party": row["party"],
            "approved_amount": row["approved_amount"],
            "payload": json.loads(row["payload_json"]),
            "created_at": row["created_at"],
        }

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
            workflow_direction=WorkflowDirection(row["workflow_direction"]),
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
    seen_invoice_keys: set[tuple[str, str, str]] | None = None,
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
        payload={
            "primary_document": str(primary_document_path),
            "load_id": load.load_id,
            "workflow_direction": load.workflow_direction.value,
        },
        workflow_direction=load.workflow_direction,
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

    extraction_payload, result = reconciliation_from_extraction(
        load,
        _call_extractor(extractor, primary_document_path),
        seen_invoice_keys=seen_invoice_keys,
        confidence_threshold=confidence_threshold,
    )
    run = store.mark_extracted(run.id, extraction_payload)
    return store.mark_reconciled(run.id, result)


def _call_extractor(extractor: Callable[[str | Path], Any], path: str | Path) -> Any:
    try:
        return extractor(path)
    except Exception as exc:  # noqa: BLE001 - provider/render failures become reviewable outcomes
        return SimpleNamespace(extraction=None, model=None, error=f"{type(exc).__name__}: {exc}")


def _direction_scoped_document_hash(document_hash: str, direction: WorkflowDirection) -> str:
    """Scope workflow idempotency by money direction.

    AP and AR may legitimately use the same source PDF/load evidence, but they authorize different
    financial objects. Persisting the scoped key prevents a carrier-payable run from swallowing a
    customer-invoice run for the same document.
    """
    prefix = f"{direction.value}:"
    return document_hash if document_hash.startswith(prefix) else f"{prefix}{document_hash}"


# `operation_commit_key(tenant, lane, load_ref, party, approved_amount)` was DELETED in Phase 1.
#
# It put the approved amount INTO the identity of the effect, so approving GBP 2,850 and then
# GBP 3,100 for one invoice produced two keys, two reservations, and two invoices. It is deleted
# rather than deprecated: leaving it importable would leave a second key namespace with independent
# claim authority, and the whole point is that exactly one identity algorithm exists.
#
# The canonical replacement is `freight_recon.commit_key.commit_key(LogicalEffect(...))`, whose
# signature cannot accept an amount. Phase 1 is FORWARD-ONLY: restoring this function fails the suite.


def normalize_money_amount(amount: str) -> str:
    raw = str(amount or "").strip().replace("$", "").replace(",", "")
    if raw.startswith("(") and raw.endswith(")"):
        raw = "-" + raw[1:-1]
    try:
        return f"{Decimal(raw).quantize(Decimal('0.01'))}"
    except (InvalidOperation, ValueError):
        return str(amount or "").strip()
