"""Phase 6 — the Work Item, and the recorded human authority that makes it ownable.

WHY THERE ARE TWO TABLES AND NOT ONE

`owner_id NOT NULL` is the mechanism the target spec names for M-35/I1 — *"Every Work Item and every
Exception MUST have an accountable human owner, at all times, from creation. Never null. Never 'the
system.'"* Taken alone it is a **non-empty string check**, and a non-empty string check is satisfied
by `owner_id='system'`, by `owner_id='the ops team'`, and by whatever the caller happened to have in
hand. That is ownership by documentation, which is the thing P6 exists to replace.

So ownership is a **foreign key into a record of authority**:

    work_items(tenant, owner_id)  ->  tenant_humans(tenant, human_id)

`tenant_humans` is not a user-management surface — administering users and roles is the web control
plane's, and ADR-017 assigns that to P11. It is the durable answer to the one question the entity
specification already asks and had nowhere to ask it: *`owner_id` FK → an authenticated user of the
tenant* (`entities/01-work-item.md` point 18). Without the referent, that line cannot be implemented;
with it, an owner Neyma never recorded is not a bad owner, it is an **unspellable** one.

The role set is §7's, copied from nowhere else and extended by nothing: **Policy Owner** (exactly one
named human per tenant, I1) and **Authorized human**. §7's other two rows — *Automated detector* and
*Agent / model* — are deliberately **absent from the CHECK**, because they are the two actors the
architecture spends the most words forbidding from owning anything. A detector may engage a brake and
never release one; a model may emit a `ProposedIntent` and nothing else (C-6, GR-7). Neither can be
written into this table, so neither can be written into `work_items.owner_id`.

WHY `recorded_by_kind` IS A ONE-VALUED CHECK

    recorded_by_kind TEXT NOT NULL CHECK (recorded_by_kind = 'human')

A column that can only hold one value looks like a mistake until you ask what it forbids. Authority
here is transitive: if a model could record a human's authority, the model would be choosing who may
own work, and rule 13 would be enforced against a roster the model wrote. The CHECK says the act of
recording an authority is itself a human act, in the database, where a refactor cannot talk it out of
being one. It is also the mutation this migration's battery aims at first.

WHAT IS DELIBERATELY *NOT* HERE

No `rules` table, and therefore no `decision_ref` FK to one. K-1 makes `decision_ref` polymorphic —
an `audit_events` row of a human-decision type, **or** an `ACTIVE` `rule_id`. The audit half is
resolvable today: the canonical Audit Event IS the event in the outbox
(`entities/17-audit-event.md` points 8/15/17 — identity `(tenant_id, event_id)`, written into the
transactional outbox). The rule half needs M12, which is a later P6 unit. So the rule half **fails
closed** rather than being stubbed open, and `work_item.py` says exactly that when it refuses.

No `commit_key` column on any table. The Commit Key is the identity of one external EFFECT and lives
in exactly one ledger (`effect_grants`, ADR-009, CLAUDE.md rule 8). A Work Item performs no effect at
all (`entities/01-work-item.md` point 38), so it has nothing to reserve.

No deletion of anything. A Work Item is never deleted (point 28) and an authority record is never
deleted either — offboarding is a STATE, because "this person used to be able to own work" is a fact
an audit has to be able to reach. Both are enforced by trigger, not by nobody having written the
DELETE yet.
"""

from __future__ import annotations

import sqlite3

MIGRATION_ID = "phase6_work_items"
P6_SCHEMA_VERSION = "phase6-work-items-1"

# Tenant-owned, both of them. A human's authority is authority WITHIN one brokerage; an obligation is
# owed BY one brokerage. Neither has an honest cross-tenant reading, so neither is exempt [C-1].
P6_TENANT_TABLES: tuple[str, ...] = (
    "tenant_humans",
    "work_items",
)

# Nothing here is tenant-exempt. Recorded explicitly rather than omitted, so a future addition has to
# state its exemption and defend it — exactly as P3 had to defend `platform_brake`.
P6_EXEMPT_TABLES: tuple[str, ...] = ()

# §7's two HUMAN roles. The other two rows of that table (Automated detector, Agent/model) are not
# roles a human holds and are structurally absent — see the module docstring.
AUTHORITY_ROLES: tuple[str, ...] = ("POLICY_OWNER", "AUTHORIZED_HUMAN")

# An authority record is never deleted; it is retired. `offboarded` is why point 36 of the entity
# spec ("a Work Item that loses its owner does not silently continue") has something to detect.
HUMAN_STATES: tuple[str, ...] = ("ACTIVE", "OFFBOARDED")

# `state ∈ {...}` from `entities/01-work-item.md` point 12 / spec §12.1. Terminal: CLOSED, CANCELLED.
WORK_ITEM_STATES: tuple[str, ...] = (
    "OPEN", "IN_PROGRESS", "BLOCKED", "AWAITING_HUMAN", "ESCALATED", "CLOSED", "CANCELLED",
)
TERMINAL_WORK_ITEM_STATES: tuple[str, ...] = ("CLOSED", "CANCELLED")

# K-1's two referent kinds. Stored so a `decision_ref` says WHICH namespace it is in — a polymorphic
# reference whose kind is inferred from the shape of the string is a reference that resolves
# differently on the day a rule id starts looking like a uuid.
DECISION_REF_KINDS: tuple[str, ...] = ("AUDIT_EVENT", "RULE")

# Identities that are not humans, spelled the way a caller in a hurry would spell them. `owner_id`
# cannot be one of these because a row for one cannot exist in `tenant_humans` — this CHECK is the
# belt to the role CHECK's braces, and it is what makes `owner_id='system'` refuse at INSERT rather
# than at review time. Lower-cased on both sides so `System` and `SYSTEM` are the same refusal.
NON_HUMAN_IDENTITIES: tuple[str, ...] = (
    "system", "neyma", "model", "agent", "detector", "bot", "automation", "none", "null",
    "unassigned", "unknown", "default", "nobody", "admin",
)
_NON_HUMAN_SQL_LIST = ",".join(f"'{i}'" for i in NON_HUMAN_IDENTITIES)

_STATES_SQL = ",".join(f"'{s}'" for s in WORK_ITEM_STATES)
_TERMINAL_SQL = ",".join(f"'{s}'" for s in TERMINAL_WORK_ITEM_STATES)
_ROLES_SQL = ",".join(f"'{r}'" for r in AUTHORITY_ROLES)
_HUMAN_STATES_SQL = ",".join(f"'{s}'" for s in HUMAN_STATES)
_REF_KINDS_SQL = ",".join(f"'{k}'" for k in DECISION_REF_KINDS)

# The exact abort texts. Named here and matched by `work_item.py` when it classifies a
# `sqlite3.IntegrityError`, for the reason `STRICT_ORDER_ABORT` exists in P5: SQLite reports a
# trigger RAISE(ABORT) and a CHECK/UNIQUE violation through the same exception type, and a message
# that guesses which one happened sends the reader hunting for the wrong defect.
OWNERLESS_ABORT = (
    "a Work Item may not be left ownerless [M-35, I1]: owner_id is never null, never blank and "
    "never a non-human identity"
)
TERMINAL_ABORT = (
    "a terminal Work Item does not transition [entities/01-work-item.md point 12]: CANCELLED is "
    "final, and CLOSED may only be reopened by WI-13 into IN_PROGRESS with phase_seq incremented"
)
# NOTE ON SPELLING: these strings are interpolated into single-quoted SQL literals inside
# `RAISE(ABORT, ...)`, so an apostrophe would terminate the literal and the trigger would fail to
# compile. Two of these sentences were first written with one and did exactly that. They are worded
# without apostrophes rather than escaped, because an escaped quote in a generated DDL string is a
# thing the next person has to notice.
VERSION_ABORT = (
    "work_items.version advances by exactly one per transition [GR-3]: a write that does not "
    "advance it silently overwrites another transition"
)
CLOSURE_ABORT = (
    "closure and cancellation require a resolvable decision_ref [I11, GR-14, K-1]: inactivity is "
    "not closure and a Work Item is never closed by silence"
)
AUTHORITY_IMMUTABLE_ABORT = (
    "the identity of a recorded authority and the act that recorded it are immutable: who was "
    "admitted, by whom, and when are facts an audit reads, not fields an operator edits"
)
AUTHORITY_DELETE_ABORT = (
    "tenant_humans is append-only: a human is OFFBOARDED, never deleted — deleting the record "
    "would strand every Work Item they own and erase the authority that admitted them"
)
WORK_ITEM_DELETE_ABORT = (
    "work_items is never deleted [entities/01-work-item.md point 28]: work does not disappear, it "
    "is closed or cancelled with a decision_ref"
)


P6_TARGET_SCHEMA: dict[str, str] = {
    # THE RECORD OF HUMAN AUTHORITY (§7 "Tenancy, Users, Roles & Authority"; M-8, M-9).
    #
    # This is the referent `entities/01-work-item.md` point 18 already required and had nowhere to
    # point at. It is NOT the control plane's user administration (ADR-017 → P11); it is the durable
    # fact that a named human was admitted to a tenant, by a named human, at a named time.
    "tenant_humans": """
        CREATE TABLE tenant_humans (
            tenant TEXT NOT NULL,
            human_id TEXT NOT NULL,
            display_name TEXT NOT NULL,
            authority_role TEXT NOT NULL,
            state TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            recorded_by TEXT NOT NULL,
            recorded_by_kind TEXT NOT NULL,
            offboarded_at TEXT,
            PRIMARY KEY (tenant, human_id),
            CHECK (authority_role IN (%(roles)s)),
            CHECK (state IN (%(human_states)s)),
            CHECK (trim(human_id) <> ''),
            CHECK (lower(trim(human_id)) NOT IN (%(non_human)s)),
            CHECK (trim(recorded_by) <> ''),
            CHECK (recorded_by_kind = 'human'),
            CHECK (state <> 'OFFBOARDED' OR offboarded_at IS NOT NULL),
            CHECK (state <> 'ACTIVE' OR offboarded_at IS NULL)
        )""" % {
        "roles": _ROLES_SQL, "human_states": _HUMAN_STATES_SQL, "non_human": _NON_HUMAN_SQL_LIST,
    },
    # THE WORK ITEM (`entities/01-work-item.md`, spec §12.1, machine M1).
    #
    # The unit of business responsibility and closure. It performs no external effect (point 38) and
    # carries no commit key — its Pipeline Instances do that, and they are a later unit.
    #
    # `owner_id` is NOT NULL *and* a foreign key, and the two do different jobs: NOT NULL forbids the
    # blank, the FK forbids the invented. Only both together make "an accountable human owner" a
    # thing the database can check.
    "work_items": """
        CREATE TABLE work_items (
            tenant TEXT NOT NULL,
            work_item_id TEXT NOT NULL,
            type TEXT NOT NULL,
            state TEXT NOT NULL,
            version INTEGER NOT NULL,
            owner_id TEXT NOT NULL,
            phase_seq INTEGER NOT NULL,
            entity_ref TEXT,
            reopens TEXT,
            prior_closure_ref TEXT,
            escalation_at TEXT,
            blocker_ref TEXT,
            exposure_amount_minor INTEGER,
            exposure_currency TEXT,
            exposure_observation_ref TEXT,
            closure_decision_ref TEXT,
            closure_decision_ref_kind TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (tenant, work_item_id),
            FOREIGN KEY (tenant, owner_id) REFERENCES tenant_humans(tenant, human_id),
            FOREIGN KEY (tenant, reopens) REFERENCES work_items(tenant, work_item_id),
            CHECK (state IN (%(states)s)),
            CHECK (version >= 1),
            CHECK (phase_seq >= 1),
            CHECK (trim(owner_id) <> ''),
            CHECK (trim(type) <> ''),
            CHECK (state NOT IN (%(terminal)s) OR closure_decision_ref IS NOT NULL),
            CHECK (state NOT IN (%(terminal)s) OR closure_decision_ref_kind IS NOT NULL),
            CHECK (closure_decision_ref_kind IS NULL OR closure_decision_ref_kind IN (%(ref_kinds)s)),
            CHECK (exposure_amount_minor IS NULL OR exposure_currency IS NOT NULL),
            CHECK (exposure_amount_minor IS NULL OR exposure_observation_ref IS NOT NULL)
        )""" % {
        "states": _STATES_SQL, "terminal": _TERMINAL_SQL, "ref_kinds": _REF_KINDS_SQL,
    },
}


P6_INDEXES: dict[str, str] = {
    # THE OWNERLESS-WORK DETECTOR'S INDEX, and the observability requirement's
    # ("ownerless-Work-Item detection at Sev-0, Work Item age"). Open work by owner is the query a
    # human asks when somebody leaves, and the query the offboarding refusal runs.
    "ix_work_items_tenant_owner_state":
        "CREATE INDEX ix_work_items_tenant_owner_state ON work_items (tenant, owner_id, state)",
    # Age. `AgeThresholdCrossed` (WI-10) is driven by a durable timer, never a sweep — this index is
    # for the human-facing "what is old and open", not for a polling loop.
    "ix_work_items_tenant_state_created":
        "CREATE INDEX ix_work_items_tenant_state_created ON work_items (tenant, state, created_at)",
    # Reopen lineage: "what reopened this" is answered without scanning.
    "ix_work_items_tenant_reopens":
        "CREATE INDEX ix_work_items_tenant_reopens ON work_items (tenant, reopens)",
}

# Nothing from an earlier phase is replaced by P6. Declared so the readiness oracle's shape matches
# P3's and P5's, and a future replacement has somewhere to go.
P6_REPLACED_INDEXES: tuple[str, ...] = ()

# The columns of a recorded authority that may change after it is written. Everything else is the
# record of an act, and an act is not editable.
HUMAN_MUTABLE_COLUMNS: tuple[str, ...] = ("display_name", "authority_role", "state", "offboarded_at")
_HUMAN_IMMUTABLE = ("tenant", "human_id", "recorded_at", "recorded_by", "recorded_by_kind")


P6_TRIGGERS: dict[str, str] = {
    # ### OWNERSHIP, DEFENDED WHERE A REFACTOR CANNOT REACH IT.
    #
    # `owner_id NOT NULL` plus the foreign key already forbid null and forbid an unrecorded human.
    # This trigger forbids the third shape — a blank or a non-human identity smuggled in by a write
    # that bypassed the machine — and it fires on UPDATE as well as INSERT, because the interesting
    # failure is not creating an ownerless item, it is a later transition quietly dropping the owner.
    "trg_work_items_owner_is_a_recorded_human_insert": f"""
        CREATE TRIGGER trg_work_items_owner_is_a_recorded_human_insert
        BEFORE INSERT ON work_items
        WHEN NEW.owner_id IS NULL OR trim(NEW.owner_id) = ''
          OR lower(trim(NEW.owner_id)) IN ({_NON_HUMAN_SQL_LIST})
        BEGIN SELECT RAISE(ABORT, '{OWNERLESS_ABORT}'); END""",
    "trg_work_items_owner_is_a_recorded_human_update": f"""
        CREATE TRIGGER trg_work_items_owner_is_a_recorded_human_update
        BEFORE UPDATE OF owner_id ON work_items
        WHEN NEW.owner_id IS NULL OR trim(NEW.owner_id) = ''
          OR lower(trim(NEW.owner_id)) IN ({_NON_HUMAN_SQL_LIST})
        BEGIN SELECT RAISE(ABORT, '{OWNERLESS_ABORT}'); END""",
    # ### AN OWNER MUST BE ACTIVE AT THE MOMENT THEY ARE GIVEN WORK.
    #
    # The foreign key proves the human is RECORDED; it says nothing about whether they still work
    # here. Assigning open work to an offboarded human is exactly the silent continuation point 36
    # forbids, and it is what a naive "the FK passed" implementation would allow.
    "trg_work_items_owner_is_active_insert": f"""
        CREATE TRIGGER trg_work_items_owner_is_active_insert
        BEFORE INSERT ON work_items
        WHEN (SELECT state FROM tenant_humans
               WHERE tenant = NEW.tenant AND human_id = NEW.owner_id) IS NOT 'ACTIVE'
        BEGIN SELECT RAISE(ABORT, '{OWNERLESS_ABORT}'); END""",
    "trg_work_items_owner_is_active_update": f"""
        CREATE TRIGGER trg_work_items_owner_is_active_update
        BEFORE UPDATE OF owner_id ON work_items
        WHEN (SELECT state FROM tenant_humans
               WHERE tenant = NEW.tenant AND human_id = NEW.owner_id) IS NOT 'ACTIVE'
        BEGIN SELECT RAISE(ABORT, '{OWNERLESS_ABORT}'); END""",
    # ### TERMINAL MEANS TERMINAL, EXCEPT FOR THE ONE DOOR WI-13 OPENS.
    #
    # `CANCELLED` + anything is illegal. `CLOSED` may go to `IN_PROGRESS` and ONLY with `phase_seq`
    # advanced — which is WI-13's "new phase" written as a constraint rather than as a convention the
    # transition layer is trusted to keep. Acceptance item 5 is this row.
    "trg_work_items_terminal_is_final": f"""
        CREATE TRIGGER trg_work_items_terminal_is_final
        BEFORE UPDATE ON work_items
        WHEN OLD.state IN ({_TERMINAL_SQL})
         AND NOT (OLD.state = 'CLOSED' AND NEW.state = 'IN_PROGRESS'
                  AND NEW.phase_seq = OLD.phase_seq + 1)
        BEGIN SELECT RAISE(ABORT, '{TERMINAL_ABORT}'); END""",
    # ### OCC IS NOT A CONVENTION.
    #
    # GR-3 says a transition writes `WHERE version = :expected` and zero rows is a lost update. That
    # protects concurrent writers from each other. This protects the counter itself: a write that
    # leaves `version` where it was, or jumps it, is not a transition — and a version that does not
    # advance is how two events claim one aggregate version downstream.
    "trg_work_items_version_advances_by_one": f"""
        CREATE TRIGGER trg_work_items_version_advances_by_one
        BEFORE UPDATE ON work_items
        WHEN NEW.version <> OLD.version + 1
        BEGIN SELECT RAISE(ABORT, '{VERSION_ABORT}'); END""",
    # ### CLOSURE IS AN EVENT, NEVER AN INFERENCE (I11).
    #
    # The table CHECK already refuses a terminal row with a null `decision_ref`. This refuses the
    # other direction on the way IN — a transition that moves to a terminal state must be carrying
    # the reference at the moment it moves, not acquiring one afterwards.
    "trg_work_items_closure_carries_a_decision": f"""
        CREATE TRIGGER trg_work_items_closure_carries_a_decision
        BEFORE UPDATE ON work_items
        WHEN NEW.state IN ({_TERMINAL_SQL})
         AND (NEW.closure_decision_ref IS NULL OR trim(NEW.closure_decision_ref) = ''
              OR NEW.closure_decision_ref_kind IS NULL)
        BEGIN SELECT RAISE(ABORT, '{CLOSURE_ABORT}'); END""",
    "trg_work_items_no_delete": f"""
        CREATE TRIGGER trg_work_items_no_delete
        BEFORE DELETE ON work_items
        BEGIN SELECT RAISE(ABORT, '{WORK_ITEM_DELETE_ABORT}'); END""",
    "trg_tenant_humans_identity_immutable": f"""
        CREATE TRIGGER trg_tenant_humans_identity_immutable
        BEFORE UPDATE OF {", ".join(_HUMAN_IMMUTABLE)} ON tenant_humans
        BEGIN SELECT RAISE(ABORT, '{AUTHORITY_IMMUTABLE_ABORT}'); END""",
    "trg_tenant_humans_no_delete": f"""
        CREATE TRIGGER trg_tenant_humans_no_delete
        BEFORE DELETE ON tenant_humans
        BEGIN SELECT RAISE(ABORT, '{AUTHORITY_DELETE_ABORT}'); END""",
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


def create_phase6_schema(conn: sqlite3.Connection, *, now: str) -> list[str]:
    """Create whatever P6 entity structure is missing. Idempotent; returns what it did.

    Callable on a fresh canonical database (where `create_canonical_schema` drives it) and on an
    already-migrated Phase-5 database. Either way the resulting structure is byte-identical, because
    there is only one text — the same discipline P3 and P5 use, and the reason a fresh database is
    never briefly unsafe.
    """
    performed: list[str] = []
    present = _tables(conn)
    for name in (*P6_TENANT_TABLES, *P6_EXEMPT_TABLES):
        if name not in present:
            conn.execute(P6_TARGET_SCHEMA[name])
            performed.append(f"create-table:{name}")
    existing = _indexes(conn)
    for name, ddl in P6_INDEXES.items():
        if name not in existing:
            conn.execute(ddl)
            performed.append(f"create-index:{name}")
    for stale in P6_REPLACED_INDEXES:
        if stale in _indexes(conn):
            conn.execute(f"DROP INDEX {stale}")
            performed.append(f"drop-index:{stale}")
    existing_triggers = _triggers(conn)
    for name, ddl in P6_TRIGGERS.items():
        if name not in existing_triggers:
            conn.execute(ddl)
            performed.append(f"create-trigger:{name}")
    # NO VERSION STAMP HERE — the marker is written LAST and only where readiness has been PROVEN.
    # A stamp written by the builder appears on a half-migrated database the moment a later step
    # fails, which is how a missing trigger goes unnoticed (phase3_checkpoint's rule, kept).
    conn.commit()
    return performed


def stamp_phase6_version(conn: sqlite3.Connection, *, now: str) -> None:
    """Record the P6 entity marker — callable ONLY once readiness holds."""
    problems = phase6_readiness_problems(conn)
    if problems:
        raise RuntimeError(
            f"refusing to stamp {P6_SCHEMA_VERSION} on a database that is NOT ready: "
            + "; ".join(problems)
        )
    if "schema_migrations" in _tables(conn):
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration, step, applied_at, detail) "
            "VALUES (?,?,?,?)",
            (MIGRATION_ID, f"version:{P6_SCHEMA_VERSION}", now,
             "recorded human authority + the Work Item, tenant-first, ownership by foreign key; "
             "readiness proven"),
        )
        conn.commit()


def phase6_readiness_problems(conn: sqlite3.Connection) -> list[str]:
    """Every reason this database cannot carry accountable Work Items. Empty == ready.

    Structural, like the P2, P3 and P5 oracles it extends. The triggers are verified PRESENT because
    a table whose ownership triggers were dropped is an ordinary table with an aspirational comment,
    and the foreign key is verified DECLARED because an `owner_id` with no referent is the
    non-empty-string check this whole migration exists to stop being.
    """
    problems: list[str] = []
    present = _tables(conn)
    for table in (*P6_TENANT_TABLES, *P6_EXEMPT_TABLES):
        if table not in present:
            problems.append(
                f"required Phase-6 table {table!r} is missing: run the {MIGRATION_ID} migration"
            )
    if not all(t in present for t in P6_TENANT_TABLES):
        return problems

    live_triggers = _triggers(conn)
    missing_triggers = sorted(t for t in P6_TRIGGERS if t not in live_triggers)
    if missing_triggers:
        problems.append(
            f"Phase-6 ownership/terminality triggers missing: {missing_triggers}. Without them a "
            f"Work Item can be left ownerless, a terminal item can transition, and the version "
            f"counter can stand still [M-35, I1, I11, GR-3]."
        )
    live_indexes = _indexes(conn)
    for name in P6_INDEXES:
        if name not in live_indexes:
            problems.append(f"required Phase-6 index {name!r} is missing")
    for stale in P6_REPLACED_INDEXES:
        if stale in live_indexes:
            problems.append(f"replaced index {stale!r} is still present")

    # THE OWNERSHIP FOREIGN KEY, READ OUT OF THE LIVE DATABASE. `schema.py`'s generic oracle checks
    # every canonical FK, but this one is the unit's whole point, so it is also checked here by name:
    # a P6 database without it does not have accountable ownership, it has a text column.
    owner_fk_declared = any(
        r[2] == "tenant_humans" and r[3] in ("tenant", "owner_id")
        for r in conn.execute("PRAGMA foreign_key_list(work_items)").fetchall()
    )
    if not owner_fk_declared:
        problems.append(
            "work_items declares no foreign key into tenant_humans: `owner_id` would be a "
            "non-empty string check, and 'an accountable human owner' would be documentation "
            "[entities/01-work-item.md point 18, M-35]."
        )
    return problems
