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

import json
import sqlite3
from dataclasses import dataclass, field
from typing import Any

MIGRATION_ID = "phase2_tenant_first"

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


class MigrationRefused(RuntimeError):
    """The migration will not proceed. It says why, and it changes nothing."""


@dataclass
class Report:
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


def migrate(db: str, *, assert_tenant: str | None = None, dry_run: bool = True) -> Report:
    """Apply the Phase-2 migration. Resumable, idempotent, and destructive of nothing unvalidated.

    `assert_tenant` is a HUMAN ASSERTION - an owner stating that this workspace's untenanted history
    belongs to one tenant. It is not a derivation and it is not a default: absent it, ambiguous rows
    are quarantined intact. There is deliberately no fallback value, because a sentinel tenant is an
    inference that merges two tenants' history the first time a database is shared.
    """
    rep = inspect(db)
    rep.dry_run = dry_run
    rep.tenant_assertion = assert_tenant

    if rep.already_applied:
        rep.findings.append({"note": "already applied - rerun is a no-op"})
        return rep
    if dry_run:
        return rep

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        conn.commit()
        conn.execute("PRAGMA foreign_keys = OFF")   # rebuilds; re-enabled and checked at step 6
        present = _tables(conn)

        # ---- STEP 1: introduce structures (bookkeeping + quarantine first, so steps 2-3 can record)
        for t in ("schema_migrations", "migration_quarantine", "effect_grants"):
            if t not in present:
                conn.execute(TARGET_SCHEMA[t])
        conn.commit()
        done = _applied(conn)

        # ---- STEPS 2-4: rebuild each table tenant-first, backfilling or quarantining every row
        for table in TENANT_FIRST_TABLES:
            step = f"rebuild:{table}"
            if step in done or table not in present:
                continue
            target = "effect_grants" if table == "operation_commit_claims" else table
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
            if f"index:{name}" in _applied(conn):
                continue
            table = ddl.split(" ON ")[1].split(" ")[0]
            if table not in _tables(conn):
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
