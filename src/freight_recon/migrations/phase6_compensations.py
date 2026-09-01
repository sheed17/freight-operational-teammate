"""Phase 6 — M10, the Compensation: one `compensations` row per external effect that should not have
happened, and the one machine in Neyma whose whole job is to prove that an UNDO gets NO privileged path.

WHAT THIS TABLE IS, IN FREIGHT TERMS

    A carrier's POD was bound to the wrong load. An invoice for GBP 2,850 went out to Acme on the
    strength of that binding. Weeks later a human corrects the binding, and Invoice #560010 is now known
    to rest on a fact that was wrong. The money left the building. Something has to credit it back.

    The tempting fix is a rollback: find the effect, call the TMS void endpoint, mark the row undone.
    ### THAT IS A SECOND, UNGATED WRITE ROUTE INTO A CUSTOMER'S ACCOUNTING SYSTEM, reached at the exact
    moment the system is already known to be wrong about something. So M10 does the opposite: the credit
    note is a NEW external effect — its own Pipeline Instance, its own policy, its own brake check, its
    own human approval, its own checkpoint witness, its own single-use Effect Grant, its own commit key
    and its own readback. The `compensations` row is only the OBLIGATION to do that, with a named human
    owner and the dollar amount at stake written on it from the moment it exists.

    ### A COMPENSATION IS THE UNDOING OF AN EXTERNAL EFFECT THAT SHOULD NOT HAVE HAPPENED.
    ### THE COMPENSATION IS ITSELF A SEPARATELY GATED EXTERNAL EFFECT. IT RECEIVES NO PRIVILEGED PATH.
    ### YOU CANNOT UNDO WHAT YOU CANNOT PROVE YOU DID.

    And when the original effect's outcome is UNKNOWN — the TMS timed out and nobody can say whether the
    invoice was issued — M10 REFUSES to compensate at all (M-33). "Cancel invoice #560010" against a
    system where no such invoice exists can CREATE a credit note out of nothing. A human resolves the
    unknown to `VERIFIED` or `FAILED` first. Only then may compensation be considered.

THE SIX CANONICAL STATES, AND NO SEVENTH (registry §4 / M10, entity §12, target spec §12.10)

    REQUIRED · APPROVED · EXECUTING · COMPLETED · COMPENSATION_FAILED · NOT_POSSIBLE. `COMPLETED` is the
    ONLY terminal state. `REQUIRED`, `COMPENSATION_FAILED` and `NOT_POSSIBLE` are non-terminal and
    human-owned. `APPROVED`/`EXECUTING` are recoverable. ### AN EXPOSURE NEVER EXPIRES (entity §26:
    NEVER) — there is no `CANCELLED`, no `EXPIRED`, no `RETRYING`, no `RESOLVED`, no `REVERSED`, no
    `UNDONE`, no seventh state. ### `COMPENSATION_FAILED` AND `NOT_POSSIBLE` ARE THE MOST DANGEROUS
    STATES THE SYSTEM CAN BE IN — reality and the projection are KNOWN to diverge — so they must be
    loud, owned by a named human, and CARRY THE EXPOSURE (entity §42, machine §38).

WHY AN OWNERLESS COMPENSATION IS STRUCTURALLY IMPOSSIBLE (entity §10/§16, machine §5, I1, AC-SAFE-028)

    `owner_id` is `NOT NULL` from creation and FOREIGN-KEY-backed into `tenant_humans` (M1's precedent).
    "A compensation has a human owner" is decoration while `owner_id` is a free-text column any string
    satisfies. The caller supplies the human; the machine never picks one; `system` is not a human; a
    model may never own one.

WHY THE EXPOSURE IS INTEGER MINOR UNITS + A CURRENCY, AND CARRIES ITS PROVENANCE (K-4, ### M10-AQ-13)

    `K-4` (`entities/00-conventions.md`) names Compensation among the operational records a money field
    is permitted on, and requires that the field CARRY THE REFERENCE it was read from — "a money field
    on an operational record MUST carry the `observation_id` (or effect/approval) it was read from; a
    money field MUST NOT be populated from a knowledge-base recall." Entity §10 lists `exposure` as
    required and names no such reference; §11's optional attributes are none of them. ### THE REFERENCE
    K-4 IS SATISFIED BY HERE IS `original_effect_id`: the exposure is the amount the ORIGINAL effect's
    VERIFIED readback established, and `original_effect_id` is already a required, NOT NULL, FK-backed
    attribute (entity §10/§18). No new reference is invented (the corpus supports none); no money value
    is persisted without provenance. The value is stored the canonical way — `exposure_amount_minor`
    (INTEGER) + `exposure_currency` (an ISO-4217 code) — matching M1's landed
    `exposure_amount_minor`/`exposure_currency` shape, so a float or a `Decimal` is refused at the
    `Money` construction the machine performs and a non-integer is refused by the DB `CHECK`. ### THE
    EXPOSURE COLUMNS ARE IMMUTABLE (the identity trigger), so a failing or impossible compensation can
    never zero, null or "settle" the number — those are exactly the states where the number is the
    whole point (entity §42).

WHY THE DATABASE STATES THE LIFECYCLE, NOT A COMMENT (entity §16)

    The six states are enumerated inline on the `state` column with a `CHECK`. ### A `CHECK` states that
    a transition to `EXECUTING` requires a bound `pipeline_instance_id` — this is the constraint that
    makes "execution is a gated attempt" a fact the database enforces rather than a sentence the machine
    prints (entity §16, verbatim). ### A `BEFORE DELETE` trigger refuses the delete outright (entity §28
    `[C-9]`, retention permanent): no sweep, no reaper, no scan, no TTL moves a Compensation.

WHY AT MOST ONE ACTIVE COMPENSATION PER INVALIDATED EFFECT (entity §17, machine §17/§19)

    `UNIQUE (tenant_id, original_effect_id) WHERE state != 'NOT_POSSIBLE'`, tenant-first, BUILT VERBATIM.
    ### IT LOOKS SURPRISING — `NOT_POSSIBLE` is non-terminal and human-owned, yet excluded — and the
    consequence is real: a second Compensation for the same original effect IS insertable while an
    earlier `NOT_POSSIBLE` row is still open and owned. ### THAT IS `M10-AQ-9`. It is preserved as the
    canonical predicate, not "improved" to close it. The executing pipeline uses its OWN commit-key
    uniqueness (Layer-1 reservation on `pipeline_instances`), so the compensating write is reserved
    exactly once WITHOUT a second effect ledger here.

WHAT THE FOREIGN KEYS POINT AT (entity §18)

    `owner_id` -> `tenant_humans` (M1); `original_effect_id` -> `effect_grants` (M3, the VERIFIED effect
    being undone AND the K-4 provenance of the exposure); `pipeline_instance_id` -> `pipeline_instances`
    (M2, the executing attempt); `approval_id` -> `approvals` (M4, the human authorisation). Every
    lookup is tenant-first, so every cross-tenant reference fails closed `[C-1]`.

WHAT IS DELIBERATELY *NOT* HERE (the seams this unit does not own)

    ### NO `invalidating_decision_ref` COLUMN (### M10-AQ-3): entity §10/§11 name none, and the
    invalidating correction's `decision_ref` is REQUIRED on the immutable `CompensationRequired` event
    rather than persisted as a row column. The row read alone cannot answer "which correction
    invalidated this effect?"; the event lineage can. No policy/rule table (M11/M12 are not built), no
    brake lifecycle (M13 is not built), no M9 `exceptions` row created here (M10 emits its F10 events and
    stops). `checkpoint.py` stays the sole gate minter and M3 the single effect authority.

FRESH == MIGRATED, SHIPS DARK

    `create_canonical_schema` builds this table directly; a migrated database reaches the SAME shape
    through `create_phase6_compensations_schema`. Nothing routes production traffic through M10;
    `compensation.py` is the only non-test module that reads it, and only
    `scripts/probe_phase6_compensation.py` imports the machine. NO oversight queue, dashboard, notifier
    or MTTR surface ships with M10.
"""

from __future__ import annotations

import sqlite3

MIGRATION_ID = "phase6_compensations"
P6CM_SCHEMA_VERSION = "phase6-compensations-1"

# Tenant-owned. A Compensation is owed WITHIN one brokerage; the same original effect in two tenants are
# two isolated Compensations [C-1]. Every query and every uniqueness constraint is tenant-first.
P6CM_TENANT_TABLES: tuple[str, ...] = ("compensations",)

# Nothing tenant-exempt. Stated rather than omitted, so a future addition must defend its exemption.
P6CM_EXEMPT_TABLES: tuple[str, ...] = ()

# `state-machines/registry.md` §4, M10 / target spec §12.10 — the SIX, in the registry's own order.
# There is no seventh: no CANCELLED (entity §25: N/A once REQUIRED, the exposure exists), no EXPIRED
# (entity §26: NEVER), no RETRYING (machine §20: a failed compensation is NOT auto-retried), no RESOLVED
# (that is M9's registered state name; a local synonym is forbidden), no REVERSED, no UNDONE, no
# ABANDONED, no bare FAILED (the state is COMPENSATION_FAILED — the longer name is not the same fact as a
# pipeline failing, and collapsing them loses the exposure).
COMPENSATION_STATES: tuple[str, ...] = (
    "REQUIRED", "APPROVED", "EXECUTING", "COMPLETED", "COMPENSATION_FAILED", "NOT_POSSIBLE",
)

# machine §8 — the one terminal state (no outgoing enumerated transition to a live state).
TERMINAL_COMPENSATION_STATES: tuple[str, ...] = ("COMPLETED",)

# machine §9, entity §12 — the THREE non-terminal human-owned states. Reality and the projection are
# KNOWN to diverge in two of them; every one names its human and carries its exposure.
HUMAN_OWNED_COMPENSATION_STATES: tuple[str, ...] = (
    "REQUIRED", "COMPENSATION_FAILED", "NOT_POSSIBLE",
)

# machine §10 — the two recoverable transient states.
RECOVERABLE_COMPENSATION_STATES: tuple[str, ...] = ("APPROVED", "EXECUTING")

_STATES_SQL = ",".join(f"'{s}'" for s in COMPENSATION_STATES)

# The exact abort texts, worded WITHOUT apostrophes: they are interpolated into single-quoted SQL
# literals inside RAISE(ABORT, ...). Matched by `compensation.py` when it classifies an IntegrityError.
VERSION_ABORT = (
    "compensations.version advances by exactly one per state transition [GR-3, C-10]: a state change "
    "that does not advance it silently overwrites another transition. OCC on the compensation version "
    "is the concurrency guard, and a version that stands still is a lost update"
)
IDENTITY_ABORT = (
    "the identity of a compensation is immutable [entity 13 sec 15/16, C-8]: the tenant, the id, the "
    "original effect it undoes, its own commit key, the human who owns it, THE EXPOSURE AT STAKE and "
    "its currency, the reason it exists and when it was raised are what make it THIS compensation. The "
    "state, the executing pipeline, the approval and the reality decision may advance; the identity and "
    "above all the exposure may NOT — zeroing or nulling the exposure on failure or impossibility is "
    "the exact forgetting these states exist to prevent [entity 13 sec 42]"
)
DELETE_ABORT = (
    "a compensation is never deleted [entity 13 sec 28/29, C-9]: retention is permanent, and an "
    "exposure NEVER expires and is never swept away by a reaper. A row that quietly stops being visible "
    "is the EXACT failure this entity exists to prevent — the money left the building and nobody is "
    "accountable for it. No sweep, no reaper, no scan, no TTL, no cancellation"
)


P6CM_TARGET_SCHEMA: dict[str, str] = {
    # THE COMPENSATION (`entities/13-compensation.md`, spec §12.10, machine M10).
    #
    # Every column on its OWN line and every FOREIGN KEY / CHECK / PRIMARY KEY on its OWN physical line,
    # and every multi-condition CHECK on ONE physical line: `schema._canonical_columns` parses this DDL
    # line by line, reads only the first token of a line as a column, and skips a line that STARTS with
    # PRIMARY KEY / FOREIGN KEY / UNIQUE / CHECK. A wrapped clause would read as a phantom column.
    "compensations": """
        CREATE TABLE compensations (
            tenant TEXT NOT NULL,
            compensation_id TEXT NOT NULL,
            -- ### THE VERIFIED EXTERNAL EFFECT BEING UNDONE (entity §10/§21, CM-1, M-33). FK-backed into
            -- effect_grants: a compensation may be created ONLY for a landed M3 Effect Grant, and CM-1
            -- reads its persisted state (VERIFIED) from that row — never a caller flag. This is ALSO the
            -- K-4 provenance of the exposure (### M10-AQ-13): the money is the amount the original
            -- effect's verified readback established.
            original_effect_id TEXT NOT NULL,
            -- ### THE COMPENSATING EFFECT'S OWN COMMIT KEY (entity §9/§17, ADR-009). Its OWN identity,
            -- resolved from CANONICAL_OCCURRENCE_SOURCES["adjust_invoice"] (entity Compensation, field
            -- compensation_id) — NEVER derived from the original effect's commit key. Stored so retries
            -- of the SAME compensation converge on one key; the executing pipeline enforces its
            -- uniqueness (Layer-1). Carried WITH a foreign key into effect_grants (original_effect_id)
            -- so this row is answerable to the ONE ledger and is not a second effect authority (rule 17).
            commit_key TEXT NOT NULL,
            -- ### THE SIX CANONICAL STATES, ENUMERATED INLINE (registry §4, M10). One physical line: no
            -- seventh state — no CANCELLED, no EXPIRED, no RETRYING, no RESOLVED, no REVERSED, no UNDONE.
            state TEXT NOT NULL CHECK (state IN (%(states)s)),
            version INTEGER NOT NULL,
            -- ### THE EXPOSURE — THE DOLLAR AMOUNT AT STAKE — IN CANONICAL MONEY (entity §10, K-4,
            -- ### M10-AQ-13). Integer minor units + an ISO-4217 code, both NOT NULL from creation. A
            -- float and a Decimal are refused at the Money construction the machine performs; the DB
            -- CHECK typeof='integer' refuses a non-integer minor-unit; length=3 refuses a malformed
            -- currency. The exposure is IMMUTABLE (identity trigger) and survives into COMPENSATION_FAILED
            -- and NOT_POSSIBLE — it may never be zeroed, nulled or settled (entity §42).
            exposure_amount_minor INTEGER NOT NULL,
            exposure_currency TEXT NOT NULL,
            -- ### THE NAMED HUMAN who owns the Compensation FROM CREATION (entity §10/§16, machine §5,
            -- I1, AC-SAFE-028). NOT NULL, and FK-backed into the tenant's recorded humans below: an
            -- ownerless Compensation is a STRUCTURALLY IMPOSSIBLE state, `system` is not a human, and a
            -- model actor may never be the owner. The caller supplies the human; the machine never picks.
            owner_id TEXT NOT NULL,
            -- ### THE CORRECTION THAT INVALIDATED THE ORIGINAL (entity §10). A human-readable reason.
            -- The invalidating correction's authenticated `decision_ref` is REQUIRED on the immutable
            -- CompensationRequired event (### M10-AQ-3), resolved through M1's resolver at CM-1 — it is
            -- NOT a column, because entity §10/§11 name none and inventing one without authority is the
            -- defect §5 exists to catch.
            reason TEXT NOT NULL,
            -- ### THE EXECUTING ATTEMPT (entity §11, CM-3). Set at CM-3 when a NEW M2 Pipeline Instance
            -- starts; NULL until then. The CHECK below makes EXECUTING require it. FK into
            -- pipeline_instances: the compensating write is a SEPARATE, fully-gated pipeline.
            pipeline_instance_id TEXT,
            -- ### THE HUMAN APPROVAL (entity §11, CM-2). Set at CM-2; NULL until then. FK into approvals
            -- (M4): money-affecting compensation is ALWAYS HUMAN_APPROVAL_REQUIRED, and the approval is
            -- bound to THIS compensation's own commit key. Consumed later, inside the executing
            -- pipeline's claim (AP-7) — not at CM-2 (### M10-AQ-6).
            approval_id TEXT,
            -- ### THE HUMAN-ESTABLISHED REALITY (entity §11, CM-5). Set when a human resolves a
            -- COMPENSATION_FAILED / NOT_POSSIBLE compensation to COMPLETED. Distinct from the
            -- invalidating decision_ref (that is CM-1's, on the event). Resolved through M1's resolver.
            reality_decision_ref TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            PRIMARY KEY (tenant, compensation_id),
            -- The owner is a recorded ACTIVE human of THIS tenant. Each FK on its OWN line so the
            -- readiness parser skips it as a non-column.
            FOREIGN KEY (tenant, owner_id) REFERENCES tenant_humans (tenant, human_id),
            -- The original effect, the executing pipeline and the approval are all rows of THIS tenant.
            FOREIGN KEY (tenant, original_effect_id) REFERENCES effect_grants (tenant, grant_id),
            FOREIGN KEY (tenant, pipeline_instance_id) REFERENCES pipeline_instances (tenant, pipeline_instance_id),
            FOREIGN KEY (tenant, approval_id) REFERENCES approvals (tenant, approval_id),
            CHECK (version >= 1),
            -- ### CHECK: a transition to EXECUTING requires a bound pipeline_instance_id (entity §16,
            -- verbatim). This is the constraint that makes "execution is a gated attempt" a fact the
            -- database STATES rather than a sentence the machine prints.
            CHECK (state <> 'EXECUTING' OR pipeline_instance_id IS NOT NULL),
            -- ### THE EXPOSURE IS INTEGER MINOR UNITS AND AN ISO-4217 CODE (K-4). A non-integer
            -- minor-unit (a float smuggled past Money) and a malformed currency are refused by the DB.
            CHECK (typeof(exposure_amount_minor) = 'integer'),
            CHECK (length(exposure_currency) = 3),
            CHECK (trim(compensation_id) <> ''),
            CHECK (trim(original_effect_id) <> ''),
            CHECK (trim(commit_key) <> ''),
            CHECK (trim(owner_id) <> ''),
            CHECK (trim(reason) <> ''),
            CHECK (trim(state) <> '')
        )""" % {"states": _STATES_SQL},
}


P6CM_INDEXES: dict[str, str] = {
    # ### ONE ACTIVE COMPENSATION PER INVALIDATED EFFECT — THE CANONICAL PARTIAL UNIQUE INDEX (entity
    # §17, machine §17/§19, verbatim). Tenant-first, partial on `state != 'NOT_POSSIBLE'`. ### BUILT
    # EXACTLY AS WRITTEN, NOT "IMPROVED" (### M10-AQ-9): NOT_POSSIBLE is excluded even though it is
    # non-terminal and human-owned, so a second compensation for the same original effect IS insertable
    # while an earlier NOT_POSSIBLE row is still open. That surprising consequence is the canonical
    # predicate's, and it is reported rather than silently changed. Drop the UNIQUE, or the WHERE, or the
    # tenant, and two active compensations fit one invalidated effect.
    "ix_compensations_one_active_per_effect":
        "CREATE UNIQUE INDEX ix_compensations_one_active_per_effect "
        "ON compensations (tenant, original_effect_id) WHERE state != 'NOT_POSSIBLE'",
    # The owner's queue: the compensations a named human owns, by state — what an ordering needs. M10
    # owes the row and the tenant-first index; it does NOT build the queue UI, dashboard or notifier.
    "ix_compensations_owner":
        "CREATE INDEX ix_compensations_owner ON compensations (tenant, owner_id, state)",
    # The compensating effect's commit-key lookup (convergence and audit), tenant-first.
    "ix_compensations_commit_key":
        "CREATE INDEX ix_compensations_commit_key ON compensations (tenant, commit_key, state)",
}

# Nothing from an earlier phase is replaced. Declared so a future replacement has somewhere to go.
P6CM_REPLACED_INDEXES: tuple[str, ...] = ()


P6CM_TRIGGERS: dict[str, str] = {
    # ### OCC ON THE COMPENSATION (GR-3, C-10, machine §17). Every M10 transition changes state, so
    # version must advance by exactly one on every write; a state change that leaves version standing is
    # two transitions claiming one version.
    "trg_compensations_version_advances_on_state_change": f"""
        CREATE TRIGGER trg_compensations_version_advances_on_state_change
        BEFORE UPDATE ON compensations
        WHEN NEW.state <> OLD.state AND NEW.version <> OLD.version + 1
        BEGIN SELECT RAISE(ABORT, '{VERSION_ABORT}'); END""",
    # ### THE IDENTITY OF THE COMPENSATION IS IMMUTABLE, AND SO IS THE EXPOSURE (entity §15/§16/§42).
    # The tenant, id, the original effect, the commit key, the owner, THE EXPOSURE and its currency, the
    # reason and created_at may not be edited — editing the exposure would let a failing compensation
    # zero the number that is the whole point of the loud states. The state, pipeline, approval and
    # reality-decision columns are DELIBERATELY ABSENT from this list because the transitions write them.
    "trg_compensations_identity_immutable": f"""
        CREATE TRIGGER trg_compensations_identity_immutable
        BEFORE UPDATE OF tenant, compensation_id, original_effect_id, commit_key, owner_id,
                         exposure_amount_minor, exposure_currency, reason, created_at
        ON compensations
        BEGIN SELECT RAISE(ABORT, '{IDENTITY_ABORT}'); END""",
    # ### NO DELETION, EVER, AND NO EXPIRY (entity §26/§28/§29, C-9). Retention is permanent; a
    # compensation is never outlived, swept, reaped or deleted. Deleting the row is exactly the
    # forgetting this entity exists to prevent — the money left the building and its accountability with
    # it.
    "trg_compensations_no_delete": f"""
        CREATE TRIGGER trg_compensations_no_delete
        BEFORE DELETE ON compensations
        BEGIN SELECT RAISE(ABORT, '{DELETE_ABORT}'); END""",
}

# The referents the readiness oracle checks by name. Derived from the DDL by the generic FK loop too;
# naming them here is the unit stating what they are FOR.
P6CM_COMPENSATION_REFERENTS: tuple[str, ...] = (
    "tenant_humans", "effect_grants", "pipeline_instances", "approvals",
)


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


def create_phase6_compensations_schema(conn: sqlite3.Connection, *, now: str) -> list[str]:
    """Create whatever M10 structure is missing. Idempotent; returns what it did.

    Callable on a fresh canonical database and on an already-migrated one. Either way the resulting
    structure is byte-identical, because there is only one text. Built LAST of the P6 units because
    `compensations` holds FKs into tenant_humans (M1), effect_grants (M3), pipeline_instances (M2) and
    approvals (M4), which is why `schema.py` orders it after them.
    """
    performed: list[str] = []
    present = _tables(conn)
    for name in (*P6CM_TENANT_TABLES, *P6CM_EXEMPT_TABLES):
        if name not in present:
            conn.execute(P6CM_TARGET_SCHEMA[name])
            performed.append(f"create-table:{name}")
    existing = _indexes(conn)
    for name, ddl in P6CM_INDEXES.items():
        if name not in existing:
            conn.execute(ddl)
            performed.append(f"create-index:{name}")
    for stale in P6CM_REPLACED_INDEXES:
        if stale in _indexes(conn):
            conn.execute(f"DROP INDEX {stale}")
            performed.append(f"drop-index:{stale}")
    existing_triggers = _triggers(conn)
    for name, ddl in P6CM_TRIGGERS.items():
        if name not in existing_triggers:
            conn.execute(ddl)
            performed.append(f"create-trigger:{name}")
    # NO VERSION STAMP HERE — marker-last, like every phase. A stamp on a half-migrated database is how
    # a missing trigger goes unnoticed.
    conn.commit()
    return performed


def stamp_phase6_compensations_version(conn: sqlite3.Connection, *, now: str) -> None:
    """Record the M10 marker — callable ONLY once readiness holds. Marker-last, like every phase."""
    problems = phase6_compensations_readiness_problems(conn)
    if problems:
        raise RuntimeError(
            f"refusing to stamp {P6CM_SCHEMA_VERSION} on a database that is NOT ready: "
            + "; ".join(problems)
        )
    if "schema_migrations" in _tables(conn):
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration, step, applied_at, detail) "
            "VALUES (?,?,?,?)",
            (MIGRATION_ID, f"version:{P6CM_SCHEMA_VERSION}", now,
             "the Compensation: one compensations row per external effect that should not have "
             "happened, tenant-first, six states, a named human owner and the exposure from creation "
             "(structurally impossible ownerless), the compensating effect's OWN commit key, EXECUTING "
             "requires a bound pipeline, exposure immutable and never zeroed, one active compensation "
             "per invalidated effect (NOT_POSSIBLE excluded, M10-AQ-9), no expiry and no deletion; "
             "readiness proven"),
        )
        conn.commit()


def phase6_compensations_readiness_problems(conn: sqlite3.Connection) -> list[str]:
    """Every reason this database cannot carry Compensations safely. Empty == ready.

    Structural, like the P2/P3/P5/M1..M9 oracles it extends. The six-state CHECK, the
    EXECUTING-requires-a-pipeline CHECK, the owner NOT NULL + FK, the exposure NOT NULL, the partial
    unique index, the no-delete/immutability triggers and the four foreign keys are verified PRESENT
    because a `compensations` table without them is an ordinary table with an aspirational comment: a
    compensation could execute with no gated attempt, an ownerless obligation could exist, a seventh
    state or a zeroed exposure could be written, and a compensation could be deleted.
    """
    problems: list[str] = []
    present = _tables(conn)
    for table in (*P6CM_TENANT_TABLES, *P6CM_EXEMPT_TABLES):
        if table not in present:
            problems.append(
                f"required Phase-6 table {table!r} is missing: run the {MIGRATION_ID} migration"
            )
    if not all(t in present for t in P6CM_TENANT_TABLES):
        return problems

    live_triggers = _triggers(conn)
    missing_triggers = sorted(t for t in P6CM_TRIGGERS if t not in live_triggers)
    if missing_triggers:
        problems.append(
            f"Compensation invariant triggers missing: {missing_triggers}. Without them a compensation "
            f"could be deleted (an exposure FORGOTTEN), a state transition could stand the version still "
            f"(a lost update), or the identity/owner/EXPOSURE could be edited in place "
            f"[entity §15/§26/§28/§42, GR-3, C-9]."
        )
    live_indexes = _indexes(conn)
    for name in P6CM_INDEXES:
        if name not in live_indexes:
            problems.append(f"required Phase-6 index {name!r} is missing")
    for stale in P6CM_REPLACED_INDEXES:
        if stale in live_indexes:
            problems.append(f"replaced index {stale!r} is still present")

    # ### THE CANONICAL PARTIAL UNIQUE INDEX, READ OUT OF THE LIVE DATABASE RATHER THAN ASSUMED FROM ITS
    # NAME (entity §17, ### M10-AQ-9). An index called `..._one_active_per_effect` that is not UNIQUE, or
    # that has lost its `WHERE state != 'NOT_POSSIBLE'` clause, is the one-active-compensation rule
    # switched off with the sign left up: two active compensations for one invalidated effect become
    # insertable.
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name = ?",
        ("ix_compensations_one_active_per_effect",),
    ).fetchone()
    if row is not None:
        sql = " ".join((row[0] or "").split()).upper().replace(", ", ",")
        if "UNIQUE" not in sql:
            problems.append(
                "ix_compensations_one_active_per_effect is not UNIQUE: two active compensations for one "
                "invalidated effect would be insertable, and the one-active rule (entity §17) would be a "
                "convention, not a constraint."
            )
        if "WHERESTATE!='NOT_POSSIBLE'" not in sql.replace(" ", ""):
            problems.append(
                "ix_compensations_one_active_per_effect has lost its `WHERE state != 'NOT_POSSIBLE'` "
                "clause: the partial index is the canonical predicate (### M10-AQ-9), verbatim — with "
                "the WHERE gone it would forbid the second compensation the corpus permits after a "
                "NOT_POSSIBLE, or (dropped entirely) permit two active ones."
            )
        for column in ("TENANT", "ORIGINAL_EFFECT_ID"):
            if column not in sql:
                problems.append(
                    f"ix_compensations_one_active_per_effect does not cover {column!r}: a dropped tenant "
                    f"is cross-tenant coalescing of one invalidated effect; a dropped member changes "
                    f"what counts as 'the same invalidated effect'."
                )

    # ### THE CHECKS AND THE VOCABULARY, READ OUT OF THE compensations DDL. A CHECK the migration
    # intended but a live database does not carry is the invariant switched off.
    ddl_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='compensations'").fetchone()
    ddl = " ".join((ddl_row[0] if ddl_row else "" or "").split()).upper()
    compact = ddl.replace(", ", ",")

    expected_states = ("STATE IN (" + ",".join(f"'{s}'" for s in COMPENSATION_STATES) + ")").upper()
    if expected_states not in compact:
        problems.append(
            "compensations does not enumerate the six canonical states inline on the state column "
            "(registry §4, M10): without it a seventh state — a CANCELLED, an EXPIRED, a RETRYING or a "
            "bare RESOLVED — would be writable, and entity §26 and machine §14 say none exists."
        )
    for clause, why in (
        ("STATE <> 'EXECUTING' OR PIPELINE_INSTANCE_ID IS NOT NULL",
         "a transition to EXECUTING requires a bound pipeline_instance_id (entity §16, verbatim): this "
         "is the constraint that makes 'execution is a gated attempt' a fact the database states rather "
         "than a sentence the machine prints"),
        ("TYPEOF(EXPOSURE_AMOUNT_MINOR) = 'INTEGER'",
         "the exposure is integer minor units (K-4, ### M10-AQ-13): a non-integer minor-unit (a float "
         "smuggled past Money) would be insertable, and 2850.00 and 2850.0 are the same money and "
         "different bytes"),
    ):
        if clause not in compact:
            problems.append(f"compensations does not CHECK: {clause.lower()} — {why}.")

    # ### owner_id AND exposure ARE NOT NULL FROM CREATION (entity §10/§16). An ownerless or exposure-
    # less compensation is structurally impossible: the columns are NOT NULL. Read the NOT NULL back
    # rather than trust it.
    info = {r[1]: r for r in conn.execute("PRAGMA table_info(compensations)").fetchall()}
    for col, why in (
        ("owner_id",
         "an ownerless Compensation would be insertable, and entity §16 names it a structurally "
         "impossible state — the owner is assigned at creation (I1, AC-SAFE-028)"),
        ("exposure_amount_minor",
         "a Compensation with no exposure would be insertable, and the exposure is the whole point of "
         "the loud states (entity §10/§42, K-4)"),
        ("exposure_currency",
         "an exposure with no currency is not money (K-4): the amount and the code are one fact"),
    ):
        r = info.get(col)
        if r is None or r[3] != 1:
            problems.append(f"compensations.{col} is not NOT NULL: {why}.")

    for referent in P6CM_COMPENSATION_REFERENTS:
        if referent not in _referents(conn, "compensations"):
            problems.append(
                f"compensations declares no foreign key into {referent!r}: the owner is a recorded "
                f"ACTIVE human of THIS tenant (M1), the original effect a VERIFIED grant of THIS tenant "
                f"(M3), the executing attempt a pipeline of THIS tenant (M2) and the approval an "
                f"authorisation of THIS tenant (M4) — 'a named X' is decoration while the column is free "
                f"text (entity §18, [C-1])."
            )
    return problems
