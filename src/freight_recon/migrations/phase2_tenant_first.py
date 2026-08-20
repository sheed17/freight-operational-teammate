"""Phase 2 — tenant-first persistence + the one canonical Effect Grant ledger.

WHAT THIS FIXES
---------------
Seven of eight tables key their rows without tenant, so the uniqueness domain is global. The sharpest
case is live today: `workflow_runs.document_hash` is UNIQUE across the whole database, so two tenants
receiving the SAME document bytes collide, and the second tenant's document is silently treated as a
duplicate of the first tenant's. That is a cross-tenant leak, not a future risk.

THE HARD PART: TENANT OWNERSHIP OF HISTORY
------------------------------------------
Only `operation_commit_claims` carries a tenant. The other six tables have no tenant anywhere in the
row - not in a column, not in a parent, not in a payload. There is nothing to derive from.

    The frozen data-migration plan already settled this:
    "ownership cannot be inferred - a human assigns it."

So this migration NEVER guesses. A human may ASSERT that a workspace's rows belong to one tenant
(`--assert-tenant`), which is an owner assertion and is recorded as one. Absent that assertion, rows
are QUARANTINED with their reason. A default or sentinel tenant would be an inference wearing a
constant's clothes, and it would silently merge two tenants' history the first time this database is
shared - so there isn't one.

STAGED, in the order the plan requires:
    1. introduce structures        2. backfill deterministically   3. quarantine ambiguous rows
    4. validate the backfill       5. create constraints/indexes   6. verify compatibility
    7. enforce NOT NULL            8. drop obsolete constraints only after proof

Nothing destructive runs before validation, and `--dry-run` writes nothing at all.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from typing import Any

MIGRATION_ID = "phase2_tenant_first"

# The SAME boundary production uses. An asserted migration tenant is not a lesser kind of tenant
# identity that may be spelled loosely - it is the identity every migrated row will carry forever,
# and it is the one place where a bad value is written to 120 rows at once instead of one.
from ..tenant import require_tenant  # noqa: E402

# The exact seven. Enumerated, never counted: the plan once said "6 of 8" and Phase 2 executed
# literally would have left `operation_token_amounts` behind with AC-SEC-001 still red and the phase
# marked done. The guard compares this SET against the live schema.
TENANT_FIRST_TABLES: tuple[str, ...] = (
    "workflow_runs",
    "audit_events",
    "security_events",
    "operation_action_claims",
    "delivery_action_claims",
    "operation_commit_claims",     # becomes effect_grants (U2.5)
    "operation_token_amounts",
)
ALREADY_TENANT_FIRST: tuple[str, ...] = ("autonomous_run_counters",)

# The same seven tables under their CANONICAL RUNTIME names. `operation_commit_claims` is a legacy
# name: after U2.6BC the store speaks to `effect_grants` and nothing else. Both spellings are kept
# because they answer different questions - TENANT_FIRST_TABLES is "what does the migration read",
# CANONICAL_TENANT_TABLES is "what must exist for the store to run". A single tuple could not.
CANONICAL_TENANT_TABLES: tuple[str, ...] = (
    "workflow_runs",
    "audit_events",
    "security_events",
    "operation_action_claims",
    "delivery_action_claims",
    "effect_grants",
    "operation_token_amounts",
)

# Tables that are deliberately NOT tenant-owned, each adjudicated. This list is not an exemption
# hatch: it has exactly two members and both would be WRONG to tenant-key.
#   `migration_quarantine` holds rows whose tenant is, by definition, unknown - it is the table that
#   exists BECAUSE ownership could not be established. A tenant column here would force the exact
#   inference the phase refuses, at the one moment we have already proven we cannot make it.
#   `schema_migrations` records what ran against the DATABASE. A database is not a tenant.
TENANT_EXEMPT_TABLES: tuple[str, ...] = (
    "migration_quarantine",
    "schema_migrations",
    # Blocker 2's audit record: migration bookkeeping, not tenant-owned business data - but it must
    # exist in BOTH the fresh and migrated shapes, or "canonical" quietly means two things.
    "owner_assertions",
)

# Bumped when the canonical shape changes in a way an older binary cannot speak to. A database
# stamped with a version this code does not know is refused, not guessed at.
SCHEMA_VERSION = "phase2-tenant-first-1"

# The eight canonical Effect Grant states. From the frozen spec, not invented and not renamed.
# REVOKED stays DISTINCT from EXPIRED_UNCLAIMED: "revoked by brake/policy/approval" and "expired
# unclaimed" are different facts about why a capability died, and audit needs both.
GRANT_STATES: tuple[str, ...] = (
    "GRANTED", "CLAIMED", "ATTEMPTED", "VERIFIED",
    "FAILED", "EXPIRED_UNCLAIMED", "REVOKED", "UNKNOWN_OUTCOME",
)
TERMINAL_STATES: tuple[str, ...] = ("VERIFIED", "FAILED", "EXPIRED_UNCLAIMED", "REVOKED")

# Historical classification. Exactly one per row.
CLASS_EQUIVALENT = "PROVABLY_EQUIVALENT_LOGICAL_EFFECT"
CLASS_DISTINCT = "PROVABLY_DISTINCT_LOGICAL_EFFECT"
CLASS_NOT_EXECUTED = "PROVABLY_NOT_EXECUTED"
CLASS_VERIFIED = "VERIFIED_EXECUTED"
CLASS_UNKNOWN = "UNKNOWN_OUTCOME"
CLASS_AMBIGUOUS_TENANT = "AMBIGUOUS_TENANT"
CLASS_AMBIGUOUS_IDENTITY = "AMBIGUOUS_IDENTITY"
CLASS_DUPLICATE_LEGACY = "DUPLICATE_LEGACY_RESERVATION"
CLASS_TEST_ONLY = "TEST_ONLY"
CLASS_INVALID = "INVALID_LEGACY_STATE"
CLASS_MANUAL = "MANUAL_REVIEW_REQUIRED"


# Actor values that name nobody. Same reasoning as the tenant sentinels: each is a real habit, and
# each turns "who decided this?" into a question the audit trail cannot answer.
FORBIDDEN_ACTORS = frozenset({
    "system", "migration", "admin", "operator", "unknown", "default", "none", "null",
    "root", "user", "automation", "script", "bot", "ci", "n/a", "na", "-", "test",
})

# Phrases that look like a reason and carry none. The basis exists so a reader in a year can tell
# WHY these rows were assigned; "confirmed" tells them nothing.
GENERIC_BASIS = frozenset({
    "requested", "confirmed", "migration", "existing data", "assumed single tenant",
    "ok", "yes", "approved", "as discussed", "per request", "obvious", "same as before",
    "single tenant", "only tenant", "it's fine", "sure", "done", "n/a", "na", "-",
})

MIN_BASIS_WORDS = 4


# --------------------------------------------------------------------------------------------
# Blocker 5: every input database reaches EXACTLY ONE classified outcome.
#
# The point of naming them is that an operator can act on the answer. "It failed" is not an outcome
# - it does not say whether to retry, to supply an assertion, to repair a schema by hand, or to stop
# and call someone. Each value below carries a safe next action, and the migration must always land
# on exactly one of them rather than on a traceback.
# --------------------------------------------------------------------------------------------

CANONICAL_READY = "CANONICAL_READY"
DRY_RUN_ONLY = "DRY_RUN_ONLY"
OWNER_ASSERTION_REQUIRED = "OWNER_ASSERTION_REQUIRED"
QUARANTINED_PENDING_REVIEW = "QUARANTINED_PENDING_REVIEW"
CONFLICTING_OWNER_ASSERTION = "CONFLICTING_OWNER_ASSERTION"
PARTIAL_MIGRATION_DETECTED = "PARTIAL_MIGRATION_DETECTED"
MANUAL_SCHEMA_REPAIR_REQUIRED = "MANUAL_SCHEMA_REPAIR_REQUIRED"
UNSUPPORTED_SCHEMA_VERSION = "UNSUPPORTED_SCHEMA_VERSION"
MIGRATION_FAILED_RETRY_SAFE = "MIGRATION_FAILED_RETRY_SAFE"
MIGRATION_COMPLETE_RESTART_SAFE = "MIGRATION_COMPLETE_RESTART_SAFE"

MIGRATION_OUTCOMES: tuple[str, ...] = (
    CANONICAL_READY, DRY_RUN_ONLY, OWNER_ASSERTION_REQUIRED, QUARANTINED_PENDING_REVIEW,
    CONFLICTING_OWNER_ASSERTION, PARTIAL_MIGRATION_DETECTED, MANUAL_SCHEMA_REPAIR_REQUIRED,
    UNSUPPORTED_SCHEMA_VERSION, MIGRATION_FAILED_RETRY_SAFE, MIGRATION_COMPLETE_RESTART_SAFE,
)

# What an operator should DO. An outcome without a next action is a status nobody can act on.
NEXT_ACTION: dict[str, str] = {
    CANONICAL_READY: "none - the database is canonical and the application may run against it",
    DRY_RUN_ONLY: "review the report, then re-run with --apply and a complete owner assertion",
    OWNER_ASSERTION_REQUIRED: (
        "supply --actor/--assert-tenant/--scope/--basis/--evidence. Ownership of these rows cannot "
        "be inferred; a human must assert it"),
    QUARANTINED_PENDING_REVIEW: (
        "inspect migration_quarantine and settle each row by hand. Nothing was guessed"),
    CONFLICTING_OWNER_ASSERTION: (
        "resolve the disagreement by hand: two assertions claim different owners for these rows. "
        "Both claims are preserved and zero rows were reassigned"),
    PARTIAL_MIGRATION_DETECTED: "re-run the migration; it resumes from durable evidence",
    MANUAL_SCHEMA_REPAIR_REQUIRED: (
        "repair the schema by hand: it is malformed in a way migration must not silently rewrite"),
    UNSUPPORTED_SCHEMA_VERSION: (
        "deploy the matching application version: this database was written by a newer binary and "
        "must NOT be downgraded"),
    MIGRATION_FAILED_RETRY_SAFE: "re-run; no partial authority was created",
    MIGRATION_COMPLETE_RESTART_SAFE: "re-run to confirm; the completed work is durable",
}


class AssertionIncomplete(ValueError):
    """An owner assertion is missing something it cannot be honest without. Fail closed."""


@dataclass(frozen=True)
class OwnerAssertion:
    """An authorized human stating who owns historical rows that carry no ownership.

    Every field is required, because the assertion answers a question a machine cannot: these six
    tables have no tenant anywhere in them, so SOMEONE decided, and the record must say who, what
    they authorised, and on what basis. An assertion missing any of that is not a weaker assertion -
    it is a guess with paperwork.

    Frozen: the scope that was validated is the scope that gets applied, with no window in which it
    could widen between the check and the use.
    """

    actor_id: str
    tenant: str
    scope: str
    operational_basis: str
    evidence_reference: str
    affected_tables: tuple[str, ...] = TENANT_FIRST_TABLES

    def __post_init__(self) -> None:
        # The SAME production boundary (Blocker 1). No second, looser path for migrations.
        object.__setattr__(self, "tenant", require_tenant(
            self.tenant, context="migration owner assertion"))

        actor = str(self.actor_id or "").strip()
        if not actor:
            raise AssertionIncomplete(
                "an owner assertion needs an actor: WHO is asserting that these rows belong to this "
                "tenant. It is never inferred from the OS user, git, the environment, or the "
                "configured client - a machine that names the actor has named nobody."
            )
        if actor.lower() in FORBIDDEN_ACTORS:
            raise AssertionIncomplete(
                f"{self.actor_id!r} does not name a person or an authorized operator. An audit trail "
                f"whose actor is {actor.lower()!r} cannot answer 'who decided this?'."
            )
        object.__setattr__(self, "actor_id", actor)

        scope = str(self.scope or "").strip()
        if not scope:
            raise AssertionIncomplete(
                "an owner assertion needs an explicit bounded scope: which database and which rows "
                "it authorises. An unbounded assertion silently covers whatever is found later."
            )
        object.__setattr__(self, "scope", scope)

        basis = str(self.operational_basis or "").strip()
        if not basis:
            raise AssertionIncomplete(
                "an owner assertion needs an operational basis: WHY the actor believes these rows "
                "belong to this tenant."
            )
        if basis.lower() in GENERIC_BASIS or len(basis.split()) < MIN_BASIS_WORDS:
            raise AssertionIncomplete(
                f"{basis!r} is not an operational basis - it is an acknowledgement. State the "
                f"specific reason a reader could check in a year."
            )
        object.__setattr__(self, "operational_basis", basis)

        evidence = str(self.evidence_reference or "").strip()
        if not evidence:
            raise AssertionIncomplete(
                "an owner assertion needs an evidence reference: where the basis can be verified "
                "(a ticket, a signed message, an onboarding record, a file path)."
            )
        object.__setattr__(self, "evidence_reference", evidence)

        if not self.affected_tables:
            raise AssertionIncomplete("an owner assertion must name the tables it affects")

    def fingerprint(self) -> str:
        """Identity of WHAT was asserted. A rerun of the same claim matches; a changed tenant, scope,
        actor or basis does NOT - it must surface as a conflict, never a quiet reassignment."""
        raw = "|".join([
            self.actor_id.lower(), self.tenant.lower(), self.scope.lower(),
            self.operational_basis.lower(), self.evidence_reference.lower(),
            ",".join(sorted(self.affected_tables)),
        ])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


class MigrationRefused(RuntimeError):
    """The migration will not proceed. It says why, and it changes nothing."""


@dataclass
class Report:
    """What the migration saw, did, and what an operator should do next."""

    """What the migration saw and did. A dry run produces this and writes nothing."""

    dry_run: bool
    tenant_assertion: str | None = None
    tables_inspected: list[str] = field(default_factory=list)
    rows_inspected: dict[str, int] = field(default_factory=dict)
    rows_migrated: dict[str, int] = field(default_factory=dict)
    rows_quarantined: dict[str, int] = field(default_factory=dict)
    classifications: dict[str, int] = field(default_factory=dict)
    findings: list[dict] = field(default_factory=list)
    already_applied: bool = False
    validated: bool = False
    outcome: str = DRY_RUN_ONLY
    migration_run_id: str | None = None
    assertion_id: str | None = None
    source_schema_version: str | None = None
    target_schema_version: str | None = None
    database: str | None = None
    canonical_effect_rows: int = 0
    readiness_problems: list[str] = field(default_factory=list)

    @property
    def next_action(self) -> str:
        return NEXT_ACTION.get(self.outcome, "unclassified outcome - do not proceed")

    def as_dict(self) -> dict[str, Any]:
        return {
            "migration": MIGRATION_ID,
            "dry_run": self.dry_run,
            "tenant_assertion": self.tenant_assertion,
            "already_applied": self.already_applied,
            "validated": self.validated,
            "tables_inspected": self.tables_inspected,
            "rows_inspected": self.rows_inspected,
            "rows_migrated": self.rows_migrated,
            "rows_quarantined": self.rows_quarantined,
            "classifications": self.classifications,
            "findings": self.findings,
            "outcome": self.outcome,
            "next_action": self.next_action,
            "migration_run_id": self.migration_run_id,
            "assertion_id": self.assertion_id,
            "database": self.database,
            "source_schema_version": self.source_schema_version,
            "target_schema_version": self.target_schema_version,
            "canonical_effect_rows": self.canonical_effect_rows,
            "readiness_problems": self.readiness_problems,
        }


# ---------------------------------------------------------------------------------- the target schema
#
# `tenant` (not `tenant_id`) is the column name throughout: it is what the existing code already uses,
# and P2 is about the tenant-first PROPERTY, not vocabulary. The canonical spec spells it `tenant_id`;
# that rename belongs with P8's other renames, and is recorded as such rather than smuggled in here.

TARGET_SCHEMA: dict[str, str] = {
    "workflow_runs": """
        CREATE TABLE workflow_runs (
            tenant TEXT NOT NULL,
            id INTEGER NOT NULL,
            load_id TEXT NOT NULL,
            document_hash TEXT NOT NULL,
            state TEXT NOT NULL,
            workflow_direction TEXT NOT NULL DEFAULT 'CARRIER_PAYABLE',
            invoice_number TEXT,
            carrier TEXT,
            outcome TEXT,
            reason TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (tenant, id)
        )""",
    "audit_events": """
        CREATE TABLE audit_events (
            tenant TEXT NOT NULL,
            id INTEGER NOT NULL,
            run_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            actor TEXT NOT NULL,
            from_state TEXT,
            to_state TEXT,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (tenant, id),
            -- Tenant-consistent FK: a child may not reference a parent in another tenant. The tenant
            -- travels in the reference itself, so a cross-tenant row cannot be spelled.
            FOREIGN KEY (tenant, run_id) REFERENCES workflow_runs(tenant, id)
        )""",
    "security_events": """
        CREATE TABLE security_events (
            tenant TEXT NOT NULL,
            id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            actor TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (tenant, id)
        )""",
    "operation_action_claims": """
        CREATE TABLE operation_action_claims (
            tenant TEXT NOT NULL,
            action_id TEXT NOT NULL,
            actor TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (tenant, action_id)
        )""",
    "delivery_action_claims": """
        CREATE TABLE delivery_action_claims (
            tenant TEXT NOT NULL,
            action_id TEXT NOT NULL,
            run_id INTEGER NOT NULL,
            actor TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (tenant, action_id),
            FOREIGN KEY (tenant, run_id) REFERENCES workflow_runs(tenant, id)
        )""",
    "operation_token_amounts": """
        CREATE TABLE operation_token_amounts (
            tenant TEXT NOT NULL,
            token_fingerprint TEXT NOT NULL,
            action_id TEXT NOT NULL,
            approved_amount TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (tenant, token_fingerprint)
        )""",
    # U2.2 + U2.5: the ONE canonical ledger. `operation_commit_claims` becomes `effect_grants` - a
    # rename, not a second table, because two ledgers that can each reserve an effect is exactly the
    # hole this phase exists to close.
    "effect_grants": """
        CREATE TABLE effect_grants (
            tenant TEXT NOT NULL,
            grant_id TEXT NOT NULL,
            -- IDENTITY (Phase 1's canonical Commit Key). Nothing mutable may appear here.
            commit_key TEXT NOT NULL,
            action_class TEXT NOT NULL,
            target_system TEXT NOT NULL,
            target_resource_id TEXT NOT NULL,
            target_operation TEXT NOT NULL,
            -- THE EIGHT CANONICAL STATES. Constrained structurally, not by convention.
            state TEXT NOT NULL CHECK (state IN (
                'GRANTED','CLAIMED','ATTEMPTED','VERIFIED',
                'FAILED','EXPIRED_UNCLAIMED','REVOKED','UNKNOWN_OUTCOME')),
            -- MATERIAL FACTS: what the decision said. Separate from identity, by construction.
            -- The amount lives here so drift stays visible and auditable; it may never key a row.
            approved_amount TEXT NOT NULL DEFAULT '',
            material_facts_json TEXT NOT NULL DEFAULT '{}',
            -- Outcome aspect (03-external-effect.md). Set by Phase 3+, never inferred here.
            verification_outcome TEXT,
            unknown_reason TEXT,
            -- PHASE-3+ columns: present so the ledger is shaped for the checkpoint, NULL until the
            -- phase that can honestly populate them. Each is listed in RESERVED_COLUMNS with its
            -- phase; a guard fails if one is left unexplained.
            checkpoint_id TEXT,            -- P3: FK -> checkpoint_witnesses (table does not exist yet)
            material_facts_fingerprint TEXT,  -- P3
            entity_versions_json TEXT,     -- P3
            gate_decision TEXT,            -- P8: the 4-member registry; NOT NULL at P8
            policy_version TEXT,           -- P8
            brake_version TEXT,            -- P8
            pipeline_instance_id TEXT,     -- P6
            approval_id TEXT,
            expires_at TEXT,               -- P3 (TTL -> EXPIRED_UNCLAIMED)
            handle_digest TEXT,            -- P3
            claimed_at TEXT,
            -- legacy descriptive columns, carried so history stays attributable
            lane TEXT NOT NULL DEFAULT '',
            load_ref TEXT NOT NULL DEFAULT '',
            party TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL DEFAULT '{}',
            issued_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (tenant, grant_id)
        )""",
    # Already tenant-first before Phase 2, and carried here so ONE table in the tree owns the
    # canonical shape. A fresh database must not have to run a migration to obtain it.
    "autonomous_run_counters": """
        CREATE TABLE autonomous_run_counters (
            tenant TEXT NOT NULL,
            lane TEXT NOT NULL,
            day TEXT NOT NULL,
            runs INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (tenant, lane, day)
        )""",
    # THE OWNER ASSERTION. Append-only: a prior assertion is never rewritten, because rewriting one
    # to hide a failed attempt is precisely how an audit trail stops being evidence. A rerun that
    # disagrees is a CONFLICT, recorded beside the original, not a correction of it.
    "owner_assertions": """
        CREATE TABLE owner_assertions (
            assertion_id TEXT PRIMARY KEY,
            migration_run_id TEXT NOT NULL,
            migration TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            asserted_tenant TEXT NOT NULL,
            assertion_scope TEXT NOT NULL,
            affected_table_set TEXT NOT NULL,
            operational_basis TEXT NOT NULL,
            evidence_reference TEXT NOT NULL,
            source_schema_version TEXT,
            source_commit TEXT,
            asserted_at TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN
                ('PENDING','APPLIED','PARTIALLY_APPLIED','FAILED','DRY_RUN','CONFLICT')),
            rows_considered INTEGER NOT NULL DEFAULT 0,
            rows_assigned INTEGER NOT NULL DEFAULT 0,
            rows_quarantined INTEGER NOT NULL DEFAULT 0,
            conflicts_detected INTEGER NOT NULL DEFAULT 0,
            unresolved_rows INTEGER NOT NULL DEFAULT 0,
            completed_at TEXT
        )""",

    # Ambiguous history lives here, intact, until a human settles it. Not deleted, not guessed at.
    "migration_quarantine": """
        CREATE TABLE migration_quarantine (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            migration TEXT NOT NULL,
            source_table TEXT NOT NULL,
            classification TEXT NOT NULL,
            reason TEXT NOT NULL,
            row_json TEXT NOT NULL,
            quarantined_at TEXT NOT NULL
        )""",
    # The migration's own bookkeeping: what ran, so a rerun is a no-op rather than a duplicate.
    "schema_migrations": """
        CREATE TABLE schema_migrations (
            migration TEXT NOT NULL,
            step TEXT NOT NULL,
            applied_at TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (migration, step)
        )""",
}

# Columns the ledger carries but Phase 2 may not populate. Each names the phase that fills it, so a
# NULL here is a scheduled obligation rather than an oversight.
RESERVED_COLUMNS: dict[str, str] = {
    "checkpoint_id": "P3 - Checkpoint Witness does not exist yet (FK added with the table)",
    "material_facts_fingerprint": "P3 - the canonical fingerprint is checkpoint work",
    "entity_versions_json": "P3 - entity-version pinning is checkpoint step 5",
    "gate_decision": "P8 - typed Policy / Action Class gate registration; NOT NULL at P8",
    "policy_version": "P8 - policy runtime",
    "brake_version": "P8 - brake runtime",
    "pipeline_instance_id": "P6 - Pipeline Instance entity",
    "expires_at": "P3 - grant TTL drives GRANTED -> EXPIRED_UNCLAIMED",
    "handle_digest": "P3 - minted with the witness",
    "approval_id": "P3 - bound at checkpoint step 1",
    "claimed_at": "P3 - set by the claim CAS",
    "verification_outcome": "P3/P4 - the verification taxonomy",
    "unknown_reason": "P3/P4 - the verification taxonomy",
}

INDEXES: dict[str, str] = {
    # THE DOC-HASH FIX. Was `document_hash TEXT NOT NULL UNIQUE` - global across tenants, so two
    # tenants filing identical bytes collided and the second was called a duplicate of the first.
    "ix_workflow_runs_tenant_document_hash":
        "CREATE UNIQUE INDEX ix_workflow_runs_tenant_document_hash "
        "ON workflow_runs (tenant, document_hash)",
    # The P2 reservation hold: one live reservation per (tenant, logical effect). This is stricter
    # than the final model on purpose - it matches exactly what the code does today, where one row
    # holds the effect for its whole life. When Pipeline Instance lands (P6) the durable Layer-1
    # hold moves there and this relaxes to the partial index below. Recorded as a P6 obligation.
    "ix_effect_grants_tenant_commit_key":
        "CREATE UNIQUE INDEX ix_effect_grants_tenant_commit_key "
        "ON effect_grants (tenant, commit_key)",
    # LAYER 2 COMMIT-ONCE, exactly as frozen (spec section 16.1): the claim-instant exclusion.
    "ix_effect_grants_commit_once":
        "CREATE UNIQUE INDEX ix_effect_grants_commit_once "
        "ON effect_grants (tenant, commit_key) WHERE state = 'CLAIMED'",
    "ix_audit_events_tenant_run": "CREATE INDEX ix_audit_events_tenant_run ON audit_events (tenant, run_id)",
}


def _now() -> str:
    from ..workflow import utc_now
    return utc_now()


def _index_names(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name IS NOT NULL").fetchall()}


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


def _applied(conn: sqlite3.Connection) -> set[str]:
    if "schema_migrations" not in _tables(conn):
        return set()
    return {r[0] for r in conn.execute(
        "SELECT step FROM schema_migrations WHERE migration = ?", (MIGRATION_ID,)).fetchall()}


def _mark(conn: sqlite3.Connection, step: str, detail: str = "") -> None:
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations (migration, step, applied_at, detail) VALUES (?,?,?,?)",
        (MIGRATION_ID, step, _now(), detail),
    )


def _quarantine(conn: sqlite3.Connection, table: str, classification: str, reason: str, row: dict) -> None:
    conn.execute(
        "INSERT INTO migration_quarantine (migration, source_table, classification, reason, row_json,"
        " quarantined_at) VALUES (?,?,?,?,?,?)",
        (MIGRATION_ID, table, classification, reason, json.dumps(row, sort_keys=True, default=str), _now()),
    )


def _is_tenant_first(conn: sqlite3.Connection, table: str) -> bool:
    """Tenant FIRST in the primary key. A tenant COLUMN is not tenant isolation."""
    pk = [r for r in conn.execute(f"PRAGMA table_info({table})").fetchall() if r[5]]
    pk.sort(key=lambda r: r[5])
    return bool(pk) and pk[0][1] in ("tenant", "tenant_id")


def classify_legacy_grant(rows: list[dict]) -> str:
    """Classify the legacy reservations for ONE logical effect. Never infers success."""
    if len(rows) > 1:
        # Different amounts made different keys under the deleted algorithm, so two rows for one
        # logical effect is the fingerprint of a historical double-commit. Evidence, not noise.
        return CLASS_DUPLICATE_LEGACY
    status = str((rows[0].get("payload") or {}).get("status", "")).upper()
    if status in ("COMMITTED", "DONE", "VERIFIED"):
        return CLASS_VERIFIED
    if status in ("RESERVED", "NEEDS_VERIFICATION", ""):
        # A reservation that never confirmed. Nobody knows whether the TMS was written. A timeout is
        # not a failure and silence is not success: it is UNKNOWN, and it belongs to a human.
        return CLASS_UNKNOWN
    return CLASS_MANUAL


def _expected_steps(conn: sqlite3.Connection, present: set[str]) -> set[str]:
    steps = {f"rebuild:{t}" for t in TENANT_FIRST_TABLES if t in present or f"_legacy_{t}" in present}
    steps |= {f"index:{n}" for n in INDEXES}
    steps |= {"verify:foreign_keys", "verify:post_cleanup"}
    return steps


def _is_fully_applied(conn: sqlite3.Connection, present: set[str]) -> bool:
    if "schema_migrations" not in present:
        return False
    done = _applied(conn)
    if not done:
        return False
    # Every table this migration was ever going to rebuild is rebuilt, and every index it can create
    # for a table that exists has been created.
    for t in TENANT_FIRST_TABLES:
        if t in present and f"rebuild:{t}" not in done and not _is_tenant_first(conn, t):
            return False
    for name, ddl in INDEXES.items():
        table = ddl.split(" ON ")[1].split(" ")[0]
        if table in present and f"index:{name}" not in done:
            return False
    return "verify:post_cleanup" in done


def inspect(db: str) -> Report:
    """Read-only. What is here, what it would become, what cannot be decided by a machine."""
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        rep = Report(dry_run=True)
        rep.database = db
        rep.target_schema_version = SCHEMA_VERSION
        present = _tables(conn)
        # Idempotency is decided by what this migration RECORDED, not by whether some table happens
        # to exist. Keying it on `effect_grants` was wrong: that table is only created when there are
        # legacy claims to move, so a workspace without any reported itself unmigrated forever.
        rep.already_applied = _is_fully_applied(conn, present)
        for t in TENANT_FIRST_TABLES:
            if t not in present:
                continue
            rep.tables_inspected.append(t)
            n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            rep.rows_inspected[t] = n
            if not n:
                continue
            has_tenant = any(r[1] in ("tenant", "tenant_id")
                             for r in conn.execute(f"PRAGMA table_info({t})").fetchall())
            if not has_tenant:
                rep.classifications[CLASS_AMBIGUOUS_TENANT] = (
                    rep.classifications.get(CLASS_AMBIGUOUS_TENANT, 0) + n)
                rep.findings.append({
                    "table": t, "rows": n, "classification": CLASS_AMBIGUOUS_TENANT,
                    "reason": "no tenant column, no tenant-bearing parent, no tenant in payload - "
                              "there is nothing to derive from. A human must assert ownership.",
                })
        if "operation_commit_claims" in present:
            groups: dict[tuple, list[dict]] = {}
            for r in conn.execute("SELECT * FROM operation_commit_claims").fetchall():
                row = dict(r)
                row["payload"] = json.loads(row.get("payload_json") or "{}")
                groups.setdefault((row["tenant"], row["lane"], row["load_ref"], row["party"]), []).append(row)
            for key, rows in groups.items():
                c = classify_legacy_grant(rows)
                rep.classifications[c] = rep.classifications.get(c, 0) + len(rows)
                if c in (CLASS_DUPLICATE_LEGACY, CLASS_UNKNOWN, CLASS_MANUAL):
                    rep.findings.append({
                        "table": "operation_commit_claims",
                        "logical_effect": dict(zip(("tenant", "lane", "load_ref", "party"), key)),
                        "rows": len(rows), "classification": c,
                        "amounts": [r["approved_amount"] for r in rows],
                    })
        return rep
    finally:
        conn.close()


def _final_outcome(db: str, rep: "Report", *, already: bool) -> str:
    """Readiness decides the outcome. Reaching the last line of the migration does not.

    A migration that finished its steps but left a database the application cannot safely serve is
    not COMPLETE - it is PARTIAL, and saying so is the difference between an operator re-running it
    and an operator deploying on top of it.
    """
    from ..schema import schema_readiness_problems

    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        problems = schema_readiness_problems(conn)
    finally:
        conn.close()
    rep.readiness_problems = problems
    # Quarantine outranks a clean schema. A canonical structure holding rows whose owner nobody has
    # asserted is not "ready" - it is a database with unresolved history and a tidy shape, and
    # reporting READY there would invite exactly the deployment this phase exists to prevent.
    if sum(rep.rows_quarantined.values()):
        return QUARANTINED_PENDING_REVIEW
    if not problems:
        return MIGRATION_COMPLETE_RESTART_SAFE if already else CANONICAL_READY
    if any("schema version" in p for p in problems):
        return UNSUPPORTED_SCHEMA_VERSION
    if sum(rep.rows_quarantined.values()):
        return QUARANTINED_PENDING_REVIEW
    if any("foreign_key_check" in p or "manual repair" in p for p in problems):
        return MANUAL_SCHEMA_REPAIR_REQUIRED
    return PARTIAL_MIGRATION_DETECTED


def _record_assertion(conn: sqlite3.Connection, assertion: "OwnerAssertion", run_id: str,
                      *, status: str, considered: int = 0) -> str:
    """Persist the assertion BEFORE the assignment it authorises. Append-only.

    Ordering is the whole point. Assign-then-record leaves a window in which rows are owned by a
    tenant nobody is recorded as having chosen - and if the recording then fails, that window is
    permanent and invisible. So the authority exists first, as PENDING, and is completed afterwards.
    """
    assertion_id = f"{run_id}:{assertion.fingerprint()}"
    conn.execute(
        """
        INSERT INTO owner_assertions (
            assertion_id, migration_run_id, migration, actor_id, asserted_tenant, assertion_scope,
            affected_table_set, operational_basis, evidence_reference, source_schema_version,
            source_commit, asserted_at, status, rows_considered
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (assertion_id, run_id, MIGRATION_ID, assertion.actor_id, assertion.tenant,
         assertion.scope, ",".join(sorted(assertion.affected_tables)),
         assertion.operational_basis, assertion.evidence_reference,
         str(conn.execute("PRAGMA schema_version").fetchone()[0]), _source_commit(),
         _now(), status, considered),
    )
    return assertion_id


def _source_commit() -> str | None:
    import subprocess
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or None
    except Exception:
        return None


def _prior_assertions(conn: sqlite3.Connection) -> list[dict]:
    if "owner_assertions" not in _tables(conn):
        return []
    return [dict(r) for r in conn.execute(
        "SELECT * FROM owner_assertions WHERE status IN ('APPLIED','PARTIALLY_APPLIED')").fetchall()]


def _refuse_conflicting_assertion(db: str, assertion: "OwnerAssertion") -> None:
    """A prior APPLIED assertion naming a different tenant is a conflict, always - even when the rows
    are already migrated and nothing would change. Both claims are preserved; a human decides."""
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        for prior in _prior_assertions(conn):
            if prior["asserted_tenant"] != assertion.tenant:
                conn.execute(
                    "UPDATE owner_assertions SET conflicts_detected = conflicts_detected + 1 "
                    "WHERE assertion_id = ?", (prior["assertion_id"],))
                conn.commit()
                raise MigrationRefused(
                    f"CONFLICTING OWNER ASSERTION: {prior['actor_id']} already asserted these rows "
                    f"belong to {prior['asserted_tenant']!r}; this run asserts {assertion.tenant!r}. "
                    f"Both claims are preserved. Zero rows reassigned - a human resolves which is "
                    f"correct."
                )
    finally:
        conn.close()


def migrate(db: str, *, assertion: "OwnerAssertion | None" = None,
            assert_tenant: str | None = None, dry_run: bool = True) -> Report:
    """Apply the Phase-2 migration. Resumable, idempotent, and destructive of nothing unvalidated.

    `assert_tenant` is a HUMAN ASSERTION - an owner stating that this workspace's untenanted history
    belongs to one tenant. It is not a derivation and it is not a default: absent it, ambiguous rows
    are quarantined intact. There is deliberately no fallback value, because a sentinel tenant is an
    inference that merges two tenants' history the first time a database is shared.
    """
    # Validate BEFORE inspecting, before opening, before anything: an invalid assertion must cost
    # zero rows, zero ledger inserts, and zero quarantine entries under the bad value. `default` is
    # not ownership - it is missing ownership spelled so it compiles, and a migration is exactly
    # where that mistake becomes permanent for every historical row at once.
    if assertion is not None and assert_tenant is not None:
        raise AssertionIncomplete(
            "pass an OwnerAssertion or nothing. `assert_tenant` alone no longer authorises "
            "assignment (Blocker 2): a tenant with no actor, scope, basis or evidence is a guess."
        )
    if assert_tenant is not None:
        # Blocker 1's validation still runs first, so a sentinel is named as the real problem - but
        # a bare tenant no longer AUTHORISES anything.
        require_tenant(assert_tenant, context=f"migration owner assertion for {db}")
        raise AssertionIncomplete(
            "a bare tenant no longer authorises historical assignment. Supply an OwnerAssertion "
            "with actor_id, scope, operational_basis and evidence_reference: these six tables have "
            "no ownership in them, so the record must say WHO decided and on what basis."
        )
    assert_tenant = assertion.tenant if assertion else None
    rep = inspect(db)
    rep.dry_run = dry_run
    rep.tenant_assertion = assert_tenant

    rep.outcome = MIGRATION_COMPLETE_RESTART_SAFE if rep.already_applied else DRY_RUN_ONLY
    if rep.already_applied:
        # An applied migration is a no-op for the ROWS - but a DIFFERENT assertion arriving now is
        # still a conflicting claim about who owns them, and returning "already applied" would let
        # it pass unremarked. Check the claim first, then no-op.
        if assertion is not None:
            _refuse_conflicting_assertion(db, assertion)
        rep.findings.append({"note": "already applied - rerun is a no-op"})
        rep.outcome = _final_outcome(db, rep, already=True)
        return rep
    if dry_run:
        # A dry run that would need an assertion says so, so an operator learns it BEFORE apply.
        needs = rep.classifications.get(CLASS_AMBIGUOUS_TENANT, 0)
        rep.outcome = OWNER_ASSERTION_REQUIRED if (needs and assertion is None) else DRY_RUN_ONLY
        return rep

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        conn.commit()
        conn.execute("PRAGMA foreign_keys = OFF")   # rebuilds; re-enabled and checked at step 6
        present = _tables(conn)

        # ---- STEP 1: introduce structures (bookkeeping + quarantine first, so steps 2-3 can record)
        # Every canonical table, not merely the ones this legacy database happened to have. A
        # workspace that never recorded a delivery claim still needs `delivery_action_claims` to
        # exist afterwards: otherwise the migration reports success and the application meets
        # "no such table" at runtime instead of a clean readiness refusal. Found by the Blocker-3
        # oracle - the migrated shape was missing three canonical tables.
        for t in ("schema_migrations", "migration_quarantine", "owner_assertions"):
            if t not in present:
                conn.execute(TARGET_SCHEMA[t])
        conn.commit()
        done = _applied(conn)

        # ---- STEP 1b: the AUTHORITY, recorded BEFORE the assignment it authorises ----
        run_id = f"{MIGRATION_ID}:{_now()}"
        assertion_id = None
        if assertion is not None:
            for prior in _prior_assertions(conn):
                if prior["asserted_tenant"] != assertion.tenant:
                    conn.execute(
                        "UPDATE owner_assertions SET conflicts_detected = conflicts_detected + 1 "
                        "WHERE assertion_id = ?", (prior["assertion_id"],))
                    conn.commit()
                    rep.outcome = CONFLICTING_OWNER_ASSERTION
                    raise MigrationRefused(
                        f"CONFLICTING OWNER ASSERTION: {prior['actor_id']} already asserted these "
                        f"rows belong to {prior['asserted_tenant']!r}; this run asserts "
                        f"{assertion.tenant!r}. Both claims are preserved. Zero rows assigned."
                    )
                if prior["assertion_id"].endswith(assertion.fingerprint()):
                    rep.already_applied = True
                    rep.findings.append({"note": "identical assertion already applied - no-op",
                                         "assertion_id": prior["assertion_id"],
                                         "actor_id": prior["actor_id"]})
                    return rep
            considered = sum(rep.rows_inspected.values())
            assertion_id = _record_assertion(conn, assertion, run_id,
                                             status="PENDING", considered=considered)
            conn.commit()   # durable BEFORE any row moves
            rep.findings.append({"assertion_id": assertion_id, "actor_id": assertion.actor_id,
                                 "asserted_tenant": assertion.tenant, "status": "PENDING"})

        # ---- STEPS 2-4: rebuild each table tenant-first, backfilling or quarantining every row
        for table in TENANT_FIRST_TABLES:
            step = f"rebuild:{table}"
            if step in done or table not in present:
                continue
            target = "effect_grants" if table == "operation_commit_claims" else table
            if _is_tenant_first(conn, table):
                # ALREADY canonical: rebuilding it would drop the table and take its indexes with
                # it, leaving a database that documents its tenant constraints without enforcing
                # them. Re-migrating a canonical database must be a no-op, not a demotion.
                _mark(conn, step, "already tenant-first - no rebuild")
                continue
            rows = [dict(r) for r in conn.execute(f"SELECT * FROM {table}").fetchall()]
            has_tenant = any(r[1] in ("tenant", "tenant_id")
                             for r in conn.execute(f"PRAGMA table_info({table})").fetchall())

            conn.execute(f"ALTER TABLE {table} RENAME TO _legacy_{table}")
            if target not in _tables(conn):
                conn.execute(TARGET_SCHEMA[target])

            migrated = quarantined = 0
            for row in rows:
                tenant = row.get("tenant") if has_tenant else assert_tenant
                if not tenant:
                    # STEP 3: quarantine. Intact, classified, reversible by a human.
                    _quarantine(conn, table, CLASS_AMBIGUOUS_TENANT,
                                "no tenant could be established without inference; supply "
                                "--assert-tenant to claim this workspace's history", row)
                    quarantined += 1
                    continue
                if target == "effect_grants":
                    _insert_grant(conn, row, tenant)
                else:
                    cols = [c for c in row if c != "tenant"]
                    conn.execute(
                        f"INSERT INTO {target} (tenant, {', '.join(cols)}) "
                        f"VALUES (?{', ?' * len(cols)})",
                        (tenant, *[row[c] for c in cols]),
                    )
                migrated += 1
            rep.rows_migrated[table] = migrated
            rep.rows_quarantined[table] = quarantined
            _mark(conn, step, f"migrated={migrated} quarantined={quarantined}")
            conn.commit()

        # ---- STEP 3b: complete the assertion with what ACTUALLY happened ----
        if assertion_id is not None:
            assigned = sum(rep.rows_migrated.values())
            quarantined = sum(rep.rows_quarantined.values())
            status = "APPLIED" if quarantined == 0 else "PARTIALLY_APPLIED"
            conn.execute(
                "UPDATE owner_assertions SET status = ?, rows_assigned = ?, rows_quarantined = ?, "
                "unresolved_rows = ?, completed_at = ? WHERE assertion_id = ?",
                (status, assigned, quarantined, quarantined, _now(), assertion_id),
            )
            conn.commit()

        # ---- STEP 3c: create canonical tables this legacy database never had ----
        # AFTER the rebuild, deliberately. SQLite resolves a foreign key to whatever table holds the
        # name at CREATE time, so building `delivery_action_claims` while `workflow_runs` is still
        # renamed to `_legacy_workflow_runs` binds its FK to the legacy table - permanently, and
        # invisibly until PRAGMA foreign_key_check reports a mismatch. Both defects in this step were
        # found by the Blocker-3 oracle rather than by reading the code.
        # EVERY canonical table, from the same list fresh creation uses - not just the tenant-owned
        # ones. Two lists would mean "canonical" quietly means two different shapes, which is exactly
        # the drift the readiness oracle exists to make impossible.
        from ..schema import CANONICAL_TABLES  # single source of truth, imported not duplicated

        live = _tables(conn)
        for table in CANONICAL_TABLES:
            if table not in live and table in TARGET_SCHEMA:
                conn.execute(TARGET_SCHEMA[table])
                _mark(conn, f"create:{table}", "absent from the legacy database")
        conn.commit()

        # ---- STEP 4: validate the backfill BEFORE anything destructive or constraining
        for table in TENANT_FIRST_TABLES:
            target = "effect_grants" if table == "operation_commit_claims" else table
            if target not in _tables(conn):
                continue
            orphans = conn.execute(
                f"SELECT COUNT(*) FROM {target} WHERE tenant IS NULL OR TRIM(tenant) = ''"
            ).fetchone()[0]
            if orphans:
                raise MigrationRefused(
                    f"{target}: {orphans} row(s) carry no tenant after backfill. Refusing to add a "
                    f"tenant-first constraint over rows whose tenant is unknown."
                )
        rep.validated = True

        # ---- STEP 5: constraints/indexes, only now that the data is proven
        for name, ddl in INDEXES.items():
            # Deliberately NOT gated on the step marker. A marker records that this migration once
            # created the index; the rebuild above may since have dropped the table it sat on.
            # Liveness is checked below, against the database as it is now.
            table = ddl.split(" ON ")[1].split(" ")[0]
            if table not in _tables(conn):
                continue
            if name in _index_names(conn):
                # Already present RIGHT NOW - not "was present earlier". The rebuild drops a table
                # and its indexes with it, so an existence check cached from before the rebuild
                # would skip re-creating an index that no longer exists and leave the database
                # documenting a constraint it does not enforce.
                _mark(conn, f"index:{name}", "already present")
                continue
            try:
                conn.execute(ddl)
            except sqlite3.IntegrityError as exc:
                raise MigrationRefused(
                    f"{name}: the data violates the constraint this phase exists to add ({exc}). "
                    f"This is a real collision, not a migration bug - it must be adjudicated."
                ) from exc
            _mark(conn, f"index:{name}")
        conn.commit()

        # ---- STEP 6: verify compatibility (FKs back on, integrity proven)
        conn.commit()          # PRAGMA foreign_keys is silently IGNORED inside a transaction
        conn.execute("PRAGMA foreign_keys = ON")
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise MigrationRefused(f"foreign-key violations after migration: {violations[:5]}")
        _mark(conn, "verify:foreign_keys")

        # ---- STEP 8: drop the legacy tables ONLY now that every step above proved out.
        # FKs go OFF for the drops: SQLite rewrites a child's FK target when its parent is renamed,
        # so `_legacy_audit_events` now points at `_legacy_workflow_runs` and dropping the parent
        # first trips the constraint. The legacy tables are being removed together; their mutual
        # references are irrelevant. FKs come straight back on and are re-checked below.
        conn.commit()          # ditto - without this the pragma below does nothing
        conn.execute("PRAGMA foreign_keys = OFF")
        for table in TENANT_FIRST_TABLES:
            legacy = f"_legacy_{table}"
            if legacy in _tables(conn):
                conn.execute(f"DROP TABLE {legacy}")
                _mark(conn, f"drop:{legacy}")
        conn.commit()
        conn.execute("PRAGMA foreign_keys = ON")
        residual = conn.execute("PRAGMA foreign_key_check").fetchall()
        if residual:
            raise MigrationRefused(f"foreign-key violations after cleanup: {residual[:5]}")
        _mark(conn, "verify:post_cleanup")
        conn.commit()

        # ---- STEP 9 (P3): finish CANONICAL, not canonical-as-of-P2. "Canonical" is one shape,
        # defined by one text, and since Phase 3 that shape includes the checkpoint tables and
        # the ledger's live-hold index. A migration that stopped at the P2 shape would hand the
        # readiness oracle a database it must refuse - the exact fresh-vs-migrated drift the
        # single-TARGET_SCHEMA design exists to prevent. create_phase3_schema is create-only
        # and idempotent; on a database that somehow already carries P3 structure it is a no-op.
        from .phase3_checkpoint import create_phase3_schema

        for step in create_phase3_schema(conn, now=_now()):
            _mark(conn, f"phase3:{step}")
        conn.commit()

        # ---- STEP 10 (P5): the same argument, one phase later. Since P5 the canonical shape also
        # includes the durable event transport - outbox, inbox, per-aggregate cursor and M-26
        # parking - with its append-only triggers. Stopping at the P3 shape would leave a MIGRATED
        # database the readiness oracle refuses while a FRESH one passes, which is exactly the
        # fresh-vs-migrated drift this file's single-TARGET_SCHEMA design exists to prevent.
        # Create-only and idempotent, like its predecessor.
        from .phase5_event_transport import create_phase5_schema

        for step in create_phase5_schema(conn, now=_now()):
            _mark(conn, f"phase5:{step}")
        conn.commit()

        # ...and the durable timers (M-36), for the identical reason. A MIGRATED database without
        # `durable_timers` is one the readiness oracle refuses while a FRESH one passes - the
        # fresh-vs-migrated drift this file's single-TARGET_SCHEMA design exists to prevent, and
        # the exact 17-node failure adding the table produced before this step existed.
        # Create-only and idempotent, like its predecessors.
        from .phase5_durable_timers import create_timer_schema

        for step in create_timer_schema(conn, now=_now()):
            _mark(conn, f"timers:{step}")
        conn.commit()

        # ---- STEP 11 (P6): the entity layer — the recorded human authority and the Work Item.
        # The same argument, one phase later again, and it is not a formality: `work_items` carries
        # the foreign key that makes ownership structural, so a MIGRATED database without it is one
        # where `owner_id` would have been a text column while a FRESH database enforced a referent.
        # Create-only and idempotent, like its three predecessors.
        from .phase6_work_items import create_phase6_schema

        for step in create_phase6_schema(conn, now=_now()):
            _mark(conn, f"phase6:{step}")
        conn.commit()

        # ...and the Pipeline Instance, which must follow the Work Item because it holds a foreign
        # key into it (and two more into P3's witness and grant tables). A MIGRATED database without
        # it is one where two attempts at one logical effect would both insert while a FRESH one
        # refused the second — the fresh-vs-migrated drift, in the one place where its cost is a
        # duplicate invoice. Create-only and idempotent, like its four predecessors.
        from .phase6_pipeline_instances import create_phase6_pipeline_schema

        for step in create_phase6_pipeline_schema(conn, now=_now()):
            _mark(conn, f"phase6pi:{step}")
        conn.commit()

        # M3, the External Effect / Effect Grant. Adds the outcome columns and rebuilds the ledger to
        # carry its foreign keys into the witness and the Pipeline Instance — AFTER both of those
        # exist, because it references each. This is the migrated path's half of "fresh == migrated":
        # a fresh database is built M3-shaped directly, and this brings a P2-shaped ledger to the same
        # shape. Idempotent; a no-op on a ledger that already carries them.
        from .phase6_external_effects import create_phase6_external_effects_schema

        for step in create_phase6_external_effects_schema(conn, now=_now()):
            _mark(conn, f"phase6ef:{step}")
        conn.commit()

        # ---- THE COMPLETION MARKER COMES LAST, AND ONLY IF READINESS PASSES ----
        # A marker written before readiness is a claim about the past that outranks the present.
        # Structure decides; the marker only records what structure already proved.
        rep.outcome = _final_outcome(db, rep, already=False)
        rep.migration_run_id = run_id
        rep.assertion_id = assertion_id
        if "effect_grants" in _tables(conn):
            rep.canonical_effect_rows = conn.execute(
                "SELECT COUNT(*) FROM effect_grants").fetchone()[0]
        if rep.outcome in (CANONICAL_READY, MIGRATION_COMPLETE_RESTART_SAFE):
            _mark(conn, f"version:{SCHEMA_VERSION}", "readiness proven")
            # The P3 and P5 stamps under the SAME proven-readiness condition; each refuses
            # internally too, so neither marker can appear on a shape that did not prove itself.
            from .phase3_checkpoint import stamp_phase3_version
            from .phase5_event_transport import stamp_phase5_version
            from .phase6_external_effects import stamp_phase6_external_effects_version
            from .phase6_pipeline_instances import stamp_phase6_pipeline_version
            from .phase6_work_items import stamp_phase6_version

            stamp_phase3_version(conn, now=_now())
            stamp_phase5_version(conn, now=_now())
            stamp_phase6_version(conn, now=_now())
            stamp_phase6_pipeline_version(conn, now=_now())
            stamp_phase6_external_effects_version(conn, now=_now())
            conn.commit()
        return rep
    finally:
        conn.close()


def _insert_grant(conn: sqlite3.Connection, row: dict, tenant: str) -> None:
    """One legacy reservation -> one canonical ledger row.

    The legacy `commit_key` is carried unchanged as `grant_id`: it is the row's historical identity
    and deleting it would destroy the audit trail. It is NOT reused as a canonical Commit Key - that
    key was derived WITH the amount and is not a logical-effect identity. The canonical `commit_key`
    is left as the legacy value too, and the row is marked so the compatibility bridge still finds
    it; recomputing a canonical key here would be manufacturing identity for an effect whose
    occurrence nobody can now establish.
    """
    payload = json.loads(row.get("payload_json") or "{}")
    status = str(payload.get("status", "")).upper()
    # Never infer success. A reservation that never confirmed is UNKNOWN_OUTCOME - human-owned,
    # non-terminal - and a timeout is not a FAILED.
    state = "VERIFIED" if status in ("COMMITTED", "DONE", "VERIFIED") else "UNKNOWN_OUTCOME"
    unknown_reason = None if state == "VERIFIED" else "LEGACY_RESERVATION_NEVER_CONFIRMED"
    conn.execute(
        """
        INSERT INTO effect_grants (
            tenant, grant_id, commit_key, action_class, target_system, target_resource_id,
            target_operation, state, approved_amount, material_facts_json, unknown_reason,
            lane, load_ref, party, payload_json, issued_at, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            tenant, row["commit_key"], row["commit_key"], row.get("lane", ""), "legacy",
            f"{row.get('load_ref','')}|{row.get('party','')}", row.get("lane", ""), state,
            row.get("approved_amount", ""),
            json.dumps({"approved_amount": row.get("approved_amount", ""),
                        "legacy_amount_keyed_identity": True}, sort_keys=True),
            unknown_reason, row.get("lane", ""), row.get("load_ref", ""), row.get("party", ""),
            row.get("payload_json", "{}"), row.get("created_at", _now()), row.get("created_at", _now()),
        ),
    )
