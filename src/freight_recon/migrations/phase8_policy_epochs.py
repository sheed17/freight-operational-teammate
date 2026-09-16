"""### THE TENANT POLICY EPOCH — the scalar a checkpoint pins and the claim CAS revalidates.

### WHY THIS TABLE EXISTS, AND WHY IT IS NOT A COLUMN ON `policies`.

U8.1 made `current_policy_version()` load-bearing: it is bound into every witness and every Effect
Grant, and the claim CAS re-reads it FRESH so that a policy change between checkpoint and claim makes
the claim match ZERO rows. Until this migration that scalar was `MAX(policy_version)` over the
tenant's `policies` rows IN ANY STATE — and `policy_version` is allocated at PO-1, when a DRAFT row is
inserted.

### THE CONSEQUENCE, MEASURED: zero policies -> 0; ONE DRAFT that is never submitted, never approved
### and never activated -> 1; a second -> 2.

So a dispatcher opening a policy draft at 4pm silently voided every in-flight Effect Grant and every
outstanding human approval for the whole brokerage — including drafts later REJECTED, whose number
stayed spent. ADR-010 sec 8's worked example is about a policy the owner actually CHANGED. A draft is
not a change; it is a sentence someone is still writing.

### THE DECISION (founder-adjudicated at U8.1): THE EPOCH ADVANCES WHEN A POLICY TAKES EFFECT OR IS
### WITHDRAWN, AND AT NO OTHER TIME.

    PO-1 draft inserted     -> epoch unchanged
    draft rejected          -> epoch unchanged
    submitted for approval  -> epoch unchanged
    PO-4 ACTIVATED          -> epoch += 1   (voids in-flight authority, every scope)
    PO-6 REVOKED            -> epoch += 1   (voids in-flight authority, every scope)
    PO-7 EXPIRED            -> epoch += 1   (voids in-flight authority, every scope)

PO-7 is included because expiry IS withdrawal: the policy that decided no longer governs, so the
decision is no longer REPRODUCIBLE, which ADR-010 sec 9.1 makes an unclaimable condition in its own
right. PO-5 (SUPERSEDED) is deliberately NOT a separate advance — supersession happens inside PO-4's
transaction, and bumping twice for one change would be noise, not safety.

### WHY AN APPEND-ONLY TABLE, AND NOT A DERIVATION FROM `policies`.

The epoch MUST be monotonic non-decreasing. If it could ever decrease, a grant minted at epoch 5
would become claimable again after the value returned to 5 — a stale grant resurrected, which is the
exact failure the CAS predicate exists to prevent. No derivation over `policies` is both monotonic
AND advances on withdrawal:

  * `MAX(policy_version) WHERE state IN ('ACTIVE', ...)` is NOT monotonic — a row LEAVING the counted
    set drops the MAX.
  * `MAX(policy_version) WHERE activated_by IS NOT NULL` IS monotonic (a row only ever GAINS
    `activated_by`), but it does NOT advance on revocation: the revoked row was already counted. That
    is UNDER-VOIDING — the one direction M11's own docstring says is not available.
  * `policies` carries no column recording a NEW number at withdrawal (`revoked_reason` and
    `revoked_direction` are text), so there is nothing to take a MAX over.

An append-only table is monotonic BY CONSTRUCTION: rows are only ever inserted, `epoch` is allocated
as MAX+1 within the tenant, and UPDATE and DELETE are refused by trigger. The value can only rise.

### IT IS NOT AN EVENT LOG, AND THE EPOCH IS NEVER DERIVED FROM ONE. CLAUDE.md sec 4 rule 9 —
events cannot grant execution authority — so counting `PolicyVersionChanged` envelopes in the outbox
to produce the scalar the claim CAS trusts is forbidden, however convenient. This is durable state
written in the SAME transaction as the transition that caused it.

### TENANT-FIRST, LIKE EVERYTHING ELSE. `tenant` is the first column and the first PK member, so a
cross-tenant epoch read cannot be spelled. One brokerage's policy activity never moves another's.

### SHIPS DARK. Nothing in production binds a policy authority, so nothing in production reads this
table yet; M11 writes it, and `policy_admission.py` is the one module that will read it through M11.
It enables no external effect and grants no autonomy.
"""

from __future__ import annotations

import sqlite3

MIGRATION_ID = "phase8_policy_epochs"
P8PE_SCHEMA_VERSION = "phase8-policy-epochs-1"

# Tenant-owned. A brokerage's policy epoch is its own; there is no global policy clock [C-1].
P8PE_TENANT_TABLES: tuple[str, ...] = ("policy_epochs",)

# Nothing tenant-exempt. Stated rather than omitted, so a future addition must defend its exemption.
P8PE_EXEMPT_TABLES: tuple[str, ...] = ()

# The one referent the readiness oracle checks by name: an epoch is always caused by a policy.
P8PE_REQUIRED_REFERENTS: tuple[str, ...] = ("policies",)

#: The reasons an epoch may advance. A CHECK, not a comment — an epoch row that names no cause is an
#: epoch nobody can defend later, and 'DRAFTED' is deliberately NOT a member.
P8PE_ADVANCE_REASONS: tuple[str, ...] = ("ACTIVATED", "REVOKED", "EXPIRED")

# The exact abort texts, WITHOUT apostrophes: they are interpolated into single-quoted SQL literals
# inside RAISE(ABORT, ...); an apostrophe would terminate the literal. Named here and matched by
# `policy.py` when it classifies an IntegrityError.
EPOCH_IMMUTABLE_ABORT = (
    "a policy epoch is immutable [ADR-010 sec 7.4/9.1]: it is the scalar every witness and every "
    "Effect Grant was bound to, and the claim CAS revalidates it. Editing one retroactively changes "
    "what authority an already-judged effect was granted under. A new change is a NEW epoch"
)
EPOCH_DELETE_ABORT = (
    "a policy epoch is never deleted [ADR-010 sec 7.4/9.1]: the epoch sequence must be monotonic, "
    "and removing a row can lower the tenant MAX — which would make a stale Effect Grant claimable "
    "again. Authority is narrowed by adding an epoch, never by removing one"
)


P8PE_TARGET_SCHEMA: dict[str, str] = {
    # Every column on its OWN line and every FOREIGN KEY / CHECK / PRIMARY KEY on its OWN physical
    # line, and every multi-condition CHECK on ONE physical line: `schema._canonical_columns` parses
    # this DDL line by line, reads only the first token of a line as a column, and skips a line that
    # STARTS with PRIMARY KEY / FOREIGN KEY / UNIQUE / CHECK. A wrapped clause would read as a
    # phantom column called `REFERENCES` or `AND`.
    "policy_epochs": """
        CREATE TABLE policy_epochs (
            tenant TEXT NOT NULL,
            -- Allocated as MAX(epoch)+1 WITHIN THE TENANT, in the same transaction as the transition
            -- that caused it. Monotonic because this table is append-only, not because anyone is careful.
            epoch INTEGER NOT NULL,
            -- WHY authority moved. 'DRAFTED' is not a member: drafting is not a change.
            reason TEXT NOT NULL CHECK (reason IN ('ACTIVATED','REVOKED','EXPIRED')),
            -- WHICH policy moved, and at which of its own row versions. Both are retained because an
            -- effect judged under this epoch must stay explicable years later.
            policy_id TEXT NOT NULL,
            policy_version INTEGER NOT NULL,
            transition_id TEXT NOT NULL,
            -- The authenticated human, where the transition had one. NEVER a model, never automation.
            advanced_by TEXT,
            occurred_at TEXT NOT NULL,
            PRIMARY KEY (tenant, epoch),
            FOREIGN KEY (tenant, policy_id) REFERENCES policies (tenant, policy_id),
            CHECK (epoch >= 1)
        )""",
}

P8PE_INDEXES: dict[str, str] = {
    # Tenant-first, and the read the claim CAS path makes: the tenant MAX. The PK already orders
    # (tenant, epoch), and this index makes the per-policy audit read cheap without a table scan.
    "idx_policy_epochs_tenant_policy": (
        "CREATE INDEX idx_policy_epochs_tenant_policy "
        "ON policy_epochs (tenant, policy_id, epoch)"
    ),
}

P8PE_REPLACED_INDEXES: tuple[str, ...] = ()

P8PE_TRIGGERS: dict[str, str] = {
    "trg_policy_epochs_immutable": f"""
        CREATE TRIGGER trg_policy_epochs_immutable
        BEFORE UPDATE ON policy_epochs
        BEGIN SELECT RAISE(ABORT, '{EPOCH_IMMUTABLE_ABORT}'); END""",
    "trg_policy_epochs_no_delete": f"""
        CREATE TRIGGER trg_policy_epochs_no_delete
        BEFORE DELETE ON policy_epochs
        BEGIN SELECT RAISE(ABORT, '{EPOCH_DELETE_ABORT}'); END""",
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


def _referents(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[2] for r in conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()}


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def create_phase8_policy_epochs_schema(conn: sqlite3.Connection, *, now: str) -> list[str]:
    """Create whatever policy-epoch structure is missing. Idempotent; returns what it did.

    Callable on a fresh canonical database and on an already-migrated one. Either way the resulting
    structure is byte-identical, because there is only one text. Built AFTER M11 (`policies`, the
    `policy_id` FK referent), which is why `schema.py` orders it after the Policy.
    """
    performed: list[str] = []
    present = _tables(conn)
    for name in (*P8PE_TENANT_TABLES, *P8PE_EXEMPT_TABLES):
        if name not in present:
            conn.execute(P8PE_TARGET_SCHEMA[name])
            performed.append(f"create-table:{name}")
    existing = _indexes(conn)
    for name, ddl in P8PE_INDEXES.items():
        if name not in existing:
            conn.execute(ddl)
            performed.append(f"create-index:{name}")
    for stale in P8PE_REPLACED_INDEXES:
        if stale in _indexes(conn):
            conn.execute(f"DROP INDEX {stale}")
            performed.append(f"drop-index:{stale}")
    existing_triggers = _triggers(conn)
    for name, ddl in P8PE_TRIGGERS.items():
        if name not in existing_triggers:
            conn.execute(ddl)
            performed.append(f"create-trigger:{name}")
    # NO VERSION STAMP HERE — marker-last. A stamp written by the builder appears on a half-migrated
    # database the moment a later step fails, which is how a missing trigger goes unnoticed.
    conn.commit()
    return performed


def stamp_phase8_policy_epochs_version(conn: sqlite3.Connection, *, now: str) -> None:
    """Record the policy-epoch marker — callable ONLY once readiness holds. Marker-last, like every phase."""
    problems = phase8_policy_epochs_readiness_problems(conn)
    if problems:
        raise RuntimeError(
            f"refusing to stamp {P8PE_SCHEMA_VERSION} on a database that is NOT ready: "
            + "; ".join(problems)
        )
    if "schema_migrations" in _tables(conn):
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration, step, applied_at, detail) "
            "VALUES (?,?,?,?)",
            (MIGRATION_ID, f"version:{P8PE_SCHEMA_VERSION}", now,
             "Policy epoch: the tenant-monotonic scalar bound into every witness and grant and "
             "revalidated by the claim CAS, advanced ONLY when a policy takes effect or is "
             "withdrawn (ACTIVATED/REVOKED/EXPIRED) and never by drafting; append-only, tenant-first, "
             "immutable and undeletable by trigger; readiness proven"),
        )
        conn.commit()


def phase8_policy_epochs_readiness_problems(conn: sqlite3.Connection) -> list[str]:
    """Every reason this database cannot carry a trustworthy policy epoch. Empty == ready.

    Structural, like the P2/P3/P5/P6/P7 oracles it extends. The immutability and no-delete triggers
    are verified PRESENT because a `policy_epochs` table without them is an ordinary table with an
    aspirational comment: an epoch could be edited to change what an already-judged effect was
    authorised under, or DELETED — which lowers the tenant MAX and makes a stale Effect Grant
    claimable again.
    """
    problems: list[str] = []
    present = _tables(conn)
    for table in (*P8PE_TENANT_TABLES, *P8PE_EXEMPT_TABLES):
        if table not in present:
            problems.append(
                f"required Phase-8 table {table!r} is missing: run the {MIGRATION_ID} migration"
            )
    if not all(t in present for t in P8PE_TENANT_TABLES):
        return problems

    live_triggers = _triggers(conn)
    missing_triggers = sorted(t for t in P8PE_TRIGGERS if t not in live_triggers)
    if missing_triggers:
        problems.append(
            f"policy-epoch invariant triggers missing: {missing_triggers}. Without them an epoch "
            f"could be rewritten or deleted, and a deletion lowers the tenant MAX — which makes a "
            f"stale Effect Grant claimable again [ADR-010 sec 7.4/9.1]."
        )
    live_indexes = _indexes(conn)
    for name in P8PE_INDEXES:
        if name not in live_indexes:
            problems.append(f"required Phase-8 index {name!r} is missing")

    cols = _columns(conn, "policy_epochs")
    for required in ("tenant", "epoch", "reason", "policy_id", "policy_version", "transition_id",
                     "occurred_at"):
        if required not in cols:
            problems.append(f"policy_epochs is missing the {required!r} column")

    referents = _referents(conn, "policy_epochs")
    for referent in P8PE_REQUIRED_REFERENTS:
        if referent not in referents:
            problems.append(
                f"policy_epochs does not reference {referent!r}: an epoch with no policy behind it "
                f"cannot be explained to the broker whose effect it voided"
            )
    return problems
