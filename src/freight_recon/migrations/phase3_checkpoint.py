"""Phase 3 — the checkpoint schema: witness table, brake tables, and the ledger's live-hold index.

WHAT THIS MIGRATION IS. Create-only and idempotent: it adds the two P3 tenant-owned tables
(`checkpoint_witnesses`, `brakes`), the platform brake row-table (`platform_brake`), their
indexes and append-only triggers, and it replaces the ledger's strict one-row-per-effect index
with the LIVE-HOLD partial index (below). It moves no data, infers no ownership, and never
rewrites an existing row. Running it twice is a no-op.

WHY THE INDEX CHANGES. Phase 2 shipped `UNIQUE (tenant, commit_key)` STRICT - one row per logical
effect, ever - and recorded its relaxation as a scheduled obligation ("when Pipeline Instance
lands (P6) the durable Layer-1 hold moves there"). Phase 3 cannot keep the strict form, because
the checkpoint matrix requires `crash after commit => the grant EXPIRES unclaimed => re-checkpoint
is safe` (platform-safety-acceptance.md, crash conditions): a safe re-checkpoint MINTS A NEW GRANT
under the SAME commit key (ADR-004 §3.8), which the strict index physically forbids once a dead
row exists. The replacement is stricter than the frozen P6 target in the only direction that is
safe to be stricter:

    UNIQUE (tenant, commit_key) WHERE state IN
        ('GRANTED','CLAIMED','ATTEMPTED','VERIFIED','UNKNOWN_OUTCOME')

  - at most ONE live-or-committed row per logical effect (GRANTED/CLAIMED/ATTEMPTED hold it,
    exactly as the strict index did);
  - a VERIFIED effect holds its key FOREVER (commit-once outlives the claim instant - the frozen
    model reaches this via Layer 1 + projected state; until P6 the ledger carries it alone);
  - UNKNOWN_OUTCOME holds the key indefinitely (ADR-009 §3.3: the stuck reservation is the point);
  - only PROVABLY-dead rows (EXPIRED_UNCLAIMED, REVOKED, FAILED-with-proof) free the key for the
    re-mint the crash semantics require.

`ix_effect_grants_commit_once` (the Layer-2 claim-instant exclusion) is untouched.

The P6 obligation stands: when Pipeline Instances arrive, the through-life hold moves to Layer 1
and this index relaxes again. Recorded here so the obligation survives the file that created it.
"""

from __future__ import annotations

import sqlite3

MIGRATION_ID = "phase3_checkpoint"
P3_SCHEMA_VERSION = "phase3-checkpoint-1"

# The P3 tenant-owned tables. Tenant-first [C-1], validated by the same readiness oracle that
# validates the Phase-2 seven.
P3_TENANT_TABLES: tuple[str, ...] = ("checkpoint_witnesses", "brakes")

# Deliberately NOT tenant-owned, adjudicated exactly like `schema_migrations`:
#   `platform_brake` is the ONE global admission brake (M13 §17, SD-12). A tenant column here
#   would make the platform stop a per-tenant fact, and "which tenant owns the platform brake"
#   is a question with no honest answer - the row exists BECAUSE it is nobody's tenant data.
P3_EXEMPT_TABLES: tuple[str, ...] = ("platform_brake",)

# The four canonical gate decisions (ADR-010 §3.1, amendment A3). Constrained structurally on the
# witness: a witness with a null or invented gate decision is not insertable (F-20).
GATE_DECISIONS: tuple[str, ...] = (
    "HUMAN_APPROVAL_REQUIRED",
    "AUTONOMOUS_WITHIN_CAPS",
    "PERMANENT_HUMAN_ASSERTION_REQUIRED",
    "FORBIDDEN",
)

BRAKE_STATES: tuple[str, ...] = ("ACTIVE", "RELEASED")

# Grant states that HOLD the commit key (live or committed). The complement - EXPIRED_UNCLAIMED,
# REVOKED, FAILED - is provably-dead: each asserts the world was NOT changed by this row.
LIVE_HOLD_STATES: tuple[str, ...] = (
    "GRANTED", "CLAIMED", "ATTEMPTED", "VERIFIED", "UNKNOWN_OUTCOME",
)

P3_TARGET_SCHEMA: dict[str, str] = {
    # THE CHECKPOINT WITNESS (entities/05-checkpoint-witness.md). Immutable record: written once
    # by the checkpoint function inside the checkpoint transaction, never updated, never deleted
    # (triggers below). No `state` column - the witness has NO lifecycle; VALID/STALE is a derived
    # predicate over expires_at and the bound versions, never a stored state.
    "checkpoint_witnesses": """
        CREATE TABLE checkpoint_witnesses (
            tenant TEXT NOT NULL,
            checkpoint_id TEXT NOT NULL,
            -- 1:1 to the grant it authorizes, enforced below. The FK is tenant-consistent so a
            -- witness can never vouch for another tenant's grant even when ids collide.
            grant_id TEXT NOT NULL,
            actor TEXT NOT NULL,
            accountable_owner TEXT NOT NULL,
            action_class TEXT NOT NULL,
            target_system TEXT NOT NULL,
            target_resource_id TEXT NOT NULL,
            target_operation TEXT NOT NULL,
            commit_key TEXT NOT NULL,
            material_facts_fingerprint TEXT NOT NULL,
            -- SD-3: the version of EVERY entity a material fact depends on, plus the target,
            -- plus every gate-precondition entity. Pinned exactly - never caller-chosen.
            entity_versions_json TEXT NOT NULL,
            -- Present iff the gate required a human (DB CHECK below).
            approval_id TEXT,
            approval_fingerprint TEXT,
            policy_version TEXT NOT NULL,
            gate_decision TEXT NOT NULL CHECK (gate_decision IN (
                'HUMAN_APPROVAL_REQUIRED','AUTONOMOUS_WITHIN_CAPS',
                'PERMANENT_HUMAN_ASSERTION_REQUIRED','FORBIDDEN')),
            autonomy_state TEXT NOT NULL,
            -- The composite brake token: BOTH the platform version and the tenant version at the
            -- instant the seven checks passed (M13 §17). The claim CAS re-derives and compares.
            brake_version TEXT NOT NULL,
            projected_observations_json TEXT NOT NULL,
            native_claims_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            PRIMARY KEY (tenant, checkpoint_id),
            UNIQUE (tenant, grant_id),
            CHECK (expires_at > created_at),
            -- A witness for a human-gated decision without its approval is structurally
            -- impossible, mirroring ADR-004 §3.2's CHECK on the grant.
            CHECK (approval_id IS NOT NULL OR gate_decision NOT IN (
                'HUMAN_APPROVAL_REQUIRED','PERMANENT_HUMAN_ASSERTION_REQUIRED')),
            FOREIGN KEY (tenant, grant_id) REFERENCES effect_grants (tenant, grant_id)
        )""",
    # THE TENANT BRAKE (M13, ADR-011). Two states. No TTL column exists, so no code path can
    # expire one. Engagement is a single row write. `brake_version` on each row is the tenant's
    # monotonic counter AT that event; the current tenant version is MAX over the tenant.
    "brakes": """
        CREATE TABLE brakes (
            tenant TEXT NOT NULL,
            brake_id TEXT NOT NULL,
            scope TEXT NOT NULL,
            state TEXT NOT NULL CHECK (state IN ('ACTIVE','RELEASED')),
            actor TEXT NOT NULL,
            actor_kind TEXT NOT NULL CHECK (actor_kind IN ('HUMAN','DETECTOR')),
            engaged_reason TEXT NOT NULL,
            engaged_at TEXT NOT NULL,
            brake_version INTEGER NOT NULL,
            released_by TEXT,
            release_decision_ref TEXT,
            released_at TEXT,
            PRIMARY KEY (tenant, brake_id),
            -- Release is a HUMAN act with a decision_ref, structurally: a released row without
            -- both is not insertable or updatable into existence.
            CHECK (state != 'RELEASED' OR (released_by IS NOT NULL AND release_decision_ref IS NOT NULL))
        )""",
    # THE PLATFORM BRAKE - ONE row (SD-12), id constrained to 1. Seeded RELEASED at version 0 so
    # "unreadable" and "released" are never the same observation: an absent row is a refusal.
    "platform_brake": """
        CREATE TABLE platform_brake (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            state TEXT NOT NULL CHECK (state IN ('ACTIVE','RELEASED')),
            brake_version INTEGER NOT NULL,
            actor TEXT,
            actor_kind TEXT CHECK (actor_kind IS NULL OR actor_kind IN ('HUMAN','DETECTOR')),
            engaged_reason TEXT,
            engaged_at TEXT,
            released_by TEXT,
            release_decision_ref TEXT,
            released_at TEXT
        )""",
}

P3_INDEXES: dict[str, str] = {
    # One ACTIVE brake per (tenant, scope): a flapping detector is one brake plus a rising signal
    # count, not a pile of rows (M13 §19).
    "ix_brakes_one_active_per_scope":
        "CREATE UNIQUE INDEX ix_brakes_one_active_per_scope "
        "ON brakes (tenant, scope) WHERE state = 'ACTIVE'",
    # THE LIVE-HOLD index replacing the Phase-2 strict form (module docstring).
    "ix_effect_grants_live_hold":
        "CREATE UNIQUE INDEX ix_effect_grants_live_hold "
        "ON effect_grants (tenant, commit_key) WHERE state IN "
        "('GRANTED','CLAIMED','ATTEMPTED','VERIFIED','UNKNOWN_OUTCOME')",
}

# The index the live-hold form REPLACES. Its presence beside the new one would re-forbid the
# re-mint the crash semantics require, so readiness treats it as a problem once P3 applies.
REPLACED_INDEXES: tuple[str, ...] = ("ix_effect_grants_tenant_commit_key",)

# [C-8]: the witness is an immutable record. UPDATE and DELETE are refused by the DATABASE, not
# by convention - an admin tool with a connection is exactly who these triggers exist for.
P3_TRIGGERS: dict[str, str] = {
    "trg_checkpoint_witnesses_append_only_update": """
        CREATE TRIGGER trg_checkpoint_witnesses_append_only_update
        BEFORE UPDATE ON checkpoint_witnesses
        BEGIN SELECT RAISE(ABORT, 'checkpoint_witnesses is append-only [C-8]: no UPDATE'); END""",
    "trg_checkpoint_witnesses_append_only_delete": """
        CREATE TRIGGER trg_checkpoint_witnesses_append_only_delete
        BEFORE DELETE ON checkpoint_witnesses
        BEGIN SELECT RAISE(ABORT, 'checkpoint_witnesses is append-only [C-8]: no DELETE'); END""",
}


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


def _indexes(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name IS NOT NULL").fetchall()}


def _triggers(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()}


def create_phase3_schema(conn: sqlite3.Connection, *, now: str) -> list[str]:
    """Create whatever P3 structure is missing. Idempotent; returns the steps it performed.

    Callable on a fresh canonical database (where create_canonical_schema drives it) and on a
    migrated Phase-2 database (where scripts/migrate_phase3_checkpoint.py drives it). Either way
    the resulting structure is byte-identical, because there is only one text.
    """
    performed: list[str] = []
    present = _tables(conn)
    for name in (*P3_TENANT_TABLES, *P3_EXEMPT_TABLES):
        if name not in present:
            conn.execute(P3_TARGET_SCHEMA[name])
            performed.append(f"create-table:{name}")
    # Seed the single platform brake row: RELEASED, version 0. INSERT OR IGNORE keeps reruns inert.
    conn.execute(
        "INSERT OR IGNORE INTO platform_brake (id, state, brake_version) VALUES (1, 'RELEASED', 0)"
    )
    existing = _indexes(conn)
    # Order matters: the replacement index must exist BEFORE the strict one is dropped, so no
    # instant exists in which the ledger is unconstrained. Both forms coexist harmlessly for the
    # moment between the two statements (the strict form implies the partial one).
    for name, ddl in P3_INDEXES.items():
        if name not in existing:
            conn.execute(ddl)
            performed.append(f"create-index:{name}")
    for stale in REPLACED_INDEXES:
        if stale in _indexes(conn):
            conn.execute(f"DROP INDEX {stale}")
            performed.append(f"drop-index:{stale}")
    existing_triggers = _triggers(conn)
    for name, ddl in P3_TRIGGERS.items():
        if name not in existing_triggers:
            conn.execute(ddl)
            performed.append(f"create-trigger:{name}")
    # DELIBERATELY NO VERSION STAMP HERE. The completion marker is written LAST, and only where
    # readiness has been PROVEN (ARCHITECTURE.md §26; the schedule-20 guard) — by
    # stamp_phase3_version below, from callers that have just verified it. A stamp written by
    # the structure-builder itself would appear on a half-migrated database the moment a later
    # step failed, which is exactly the marker-outranks-the-present defect.
    conn.commit()
    return performed


def stamp_phase3_version(conn: sqlite3.Connection, *, now: str) -> None:
    """Record the P3 completion marker — callable ONLY once readiness holds.

    Refuses to stamp a database whose Phase-3 structure is not proven: the marker records what
    structure already demonstrated, never the builder's intention.
    """
    problems = phase3_readiness_problems(conn)
    if problems:
        raise RuntimeError(
            "refusing to stamp phase3-checkpoint-1 on a database that is NOT ready: "
            + "; ".join(problems)
        )
    if "schema_migrations" in _tables(conn):
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration, step, applied_at, detail) "
            "VALUES (?,?,?,?)",
            (MIGRATION_ID, f"version:{P3_SCHEMA_VERSION}", now,
             "checkpoint witness + brake schema; ledger live-hold index; readiness proven"),
        )
        conn.commit()


def phase3_readiness_problems(conn: sqlite3.Connection) -> list[str]:
    """Every reason this database cannot serve the checkpoint kernel. Empty == ready.

    Structural, like the Phase-2 oracle it extends: nothing is trusted because a name looks
    familiar. The witness triggers are verified present because an append-only table whose
    triggers were dropped is an ordinary table wearing a solemn comment.
    """
    problems: list[str] = []
    present = _tables(conn)
    for table in (*P3_TENANT_TABLES, *P3_EXEMPT_TABLES):
        if table not in present:
            problems.append(
                f"required Phase-3 table {table!r} is missing: run the phase3_checkpoint migration"
            )
    if "checkpoint_witnesses" in present:
        missing_triggers = [t for t in P3_TRIGGERS if t not in _triggers(conn)]
        if missing_triggers:
            problems.append(
                f"checkpoint_witnesses append-only triggers missing: {missing_triggers}. Without "
                f"them the witness is an ordinary mutable table and [C-8] is a comment."
            )
    if "platform_brake" in present:
        rows = conn.execute("SELECT COUNT(*) FROM platform_brake").fetchone()[0]
        if rows != 1:
            problems.append(
                f"platform_brake must hold exactly ONE row (SD-12); found {rows}. An empty table "
                f"reads as 'cannot read the brake', which must refuse, not pass."
            )
    live_indexes = _indexes(conn)
    for name in P3_INDEXES:
        if name not in live_indexes:
            problems.append(f"required Phase-3 index {name!r} is missing")
    for stale in REPLACED_INDEXES:
        if stale in live_indexes:
            problems.append(
                f"replaced index {stale!r} is still present: the strict one-row-per-effect form "
                f"forbids the safe re-mint after EXPIRED_UNCLAIMED/REVOKED/FAILED that the "
                f"checkpoint crash semantics require."
            )
    return problems
