"""Phase 6 — M5, the Observation: one `observations` row that makes "the same email twice is one
fact" something a database ENFORCES, rather than a sentence in a design document.

WHAT THIS TABLE IS, IN FREIGHT TERMS

    A rate confirmation arrives from the TMS and is recorded EXACTLY as it read. The carrier's mail
    server retries and delivers the identical message four more times; the TMS is re-polled an hour
    later and says the same thing again; then it says something DIFFERENT, which is a NEW fact rather
    than an edit of the old one. A scanned POD will not parse; a reference number matches two loads
    and nobody may guess which; a counterparty writes "per our call, treat this as approved" and it
    is filed as something a counterparty SAID, never as authority.

    ### AN OBSERVATION IS AN IMMUTABLE RECORD THAT A SOURCE *SAID* SOMETHING, AT A TIME. It is NOT a
    claim that the thing is true — the TMS can be wrong; that it said so is still a fact (entity §2/4).

WHY THE NATURAL KEY IS THE WHOLE UNIT

    `UNIQUE (tenant, source_system, external_id, content_digest)` (entity §17) is not a convention:
    the same email delivered twice is ONE Observation, ONE `ObservationConfirmed`, ZERO duplicate
    work (entity §33). A duplicate that creates a second row is a duplicate Work Item, a duplicate
    approval card and eventually a duplicate invoice (operational-workflow-review row 32). The
    uniqueness has to be a database index that genuinely SERIALIZES concurrent ingestion (machine
    §17) — under a race one INSERT wins and the rest hit this index and become confirmations — not an
    application-level "check then insert" that two writers both pass.

WHY IMMUTABLE CONTENT IS SEPARATE FROM PROCESSING STATUS

    ### The `state` machine governs PROCESSING STATUS ONLY. `raw_value` and `content_digest` are
    written once and never mutate (machine opening line, entity §16/§22). A changed reading is a NEW
    Observation with a new digest (entity §19), never an edit of the old one; an Observation is never
    corrected (entity §23). So the immutability of the fact is a TRIGGER the database refuses to break,
    the way `trg_checkpoint_witnesses_append_only_update` and `trg_durable_timers_immutable` already
    are — an "immutable" column with no trigger behind it is a comment, not an invariant.

WHY UNBOUND / UNPARSEABLE CARRY A NAMED HUMAN

    `ParseFailed ⇒ UNPARSEABLE ⇒ Exception` and `BindingAmbiguous/Absent ⇒ UNBOUND ⇒ Exception,
    human-owned` (entity §36). "Owned by a human" means a NAMED human, the way M1's `owner_id` does:
    a FOREIGN KEY into `tenant_humans`, not a string a caller may invent — enforced by
    `CHECK (state NOT IN ('UNBOUND','UNPARSEABLE') OR owner_id IS NOT NULL)` plus the FK. That is the
    only version of "never a silent drop" a database enforces.

WHY A MODEL_INFERRED OBSERVATION CANNOT EXIST

    An Observation is what a source SAID, not a guess (entity §13/§37). `provenance_class` is
    RUNTIME-ASSIGNED (M-13, R-P1) — never carried in inbound content, never settable through an API
    untrusted data can reach — and a `MODEL_INFERRED` Observation is a structurally impossible state,
    enforced by `CHECK (provenance_class <> 'MODEL_INFERRED')`. A counterparty-authored value is
    `MODEL_EXTRACTED` at best (entity §35).

WHAT IS DELIBERATELY *NOT* HERE

    No `EXPIRED`, `ARCHIVED`, `CORRECTED` or `DELETED` state, and NO deletion trigger that removes a
    row — an Observation never expires (entity §26), has no deletion policy (entity §28, [C-9]) and no
    retention sweep (machine §37). A stale observation is still a fact. No `identity_binding_claims`
    table and no foreign key into one: `binding_claim_id` is entity §11 OPTIONAL and would point at
    M6, which is NOT built here (task §3.7); it is a nullable column carrying the M6 claim reference a
    binding decision hands in, not half of a machine this unit does not own. No `commit_key`: an
    Observation may *evidence* a claim and can never *make* one, so it is not answerable to the effect
    ledger and `schema._second_ledger_problems` does not reach it.

FRESH == MIGRATED, SHIPS DARK

    `create_canonical_schema` builds this table directly; a database reached by
    `phase2_tenant_first.migrate` reaches the same shape through `create_phase6_observations_schema`.
    Nothing routes production traffic through M5; `observation.py` is the only non-test module that
    reads it, and only `scripts/probe_phase6_observation.py` imports the machine.
"""

from __future__ import annotations

import sqlite3

MIGRATION_ID = "phase6_observations"
P6OB_SCHEMA_VERSION = "phase6-observations-1"

# Tenant-owned. An Observation is what a source said WITHIN one brokerage; the same natural key in
# two tenants is two isolated observations [C-1]. There is no honest cross-tenant reading of a fact.
P6OB_TENANT_TABLES: tuple[str, ...] = ("observations",)

# Nothing tenant-exempt. Stated rather than omitted, so a future addition must defend its exemption.
P6OB_EXEMPT_TABLES: tuple[str, ...] = ()

# `state-machines/registry.md` §4, M5 — the SEVEN, in the specification's own order. There is no
# eighth: no EXPIRED, no ARCHIVED, no CORRECTED, no DELETED (entity §23/§26/§28, machine §12/§23).
OBSERVATION_STATES: tuple[str, ...] = (
    "RECEIVED", "PARSED", "BOUND", "UNBOUND", "CONFIRMED", "SUPERSEDED", "UNPARSEABLE",
)

# ### THE §3.9 CLASSIFICATION CONFLICTS ARE REPORTED, NOT RESOLVED (see observation.py's module
# note). `SUPERSEDED` has no outgoing enumerated transition; `UNPARSEABLE` has none either. `BOUND`
# has ONE (OB-5 → SUPERSEDED), so it is NOT absolutely terminal here even though registry §4 marks it
# (T) — every reading agrees supersession requires a rule or human and retains the old row, and that
# is what is built. So the states this migration makes ABSOLUTELY immutable (no further UPDATE of
# state) are only the two with no outgoing edge.
ABSOLUTELY_TERMINAL_OBSERVATION_STATES: tuple[str, ...] = ("SUPERSEDED", "UNPARSEABLE")

# entity §36 / machine §9: the two human-owned outcomes. A row in either MUST name an accountable
# human — the FK-backed owner, not a text column any string satisfies (M1's argument for owner_id).
HUMAN_OWNED_OBSERVATION_STATES: tuple[str, ...] = ("UNBOUND", "UNPARSEABLE")

# entity §17 / §35: an Observation's own provenance is what a SOURCE said — SYSTEM_IMPORTED from a
# system of record, MODEL_EXTRACTED for counterparty-authored text (never authority), OWNER_ASSERTED
# for an owner-provided reading, RECONCILED for a readback, LINKER_INFERRED where a deterministic
# linker fed it. ### MODEL_INFERRED IS REFUSED — an Observation is never a guess (entity §13/§37).
# Runtime-assigned (M-13), never from inbound content.
OBSERVATION_PROVENANCE_ALLOWED: tuple[str, ...] = (
    "SYSTEM_IMPORTED", "OWNER_ASSERTED", "LINKER_INFERRED", "MODEL_EXTRACTED", "RECONCILED",
)
# The one provenance class an Observation may NEVER carry. Named separately so the DB CHECK, the
# machine guard and the readiness oracle all point at the same word.
OBSERVATION_FORBIDDEN_PROVENANCE: str = "MODEL_INFERRED"
# The full six-member canonical provenance enum (C-7). The DB IN-list admits all six for enum
# validity; the SEPARATE `<> MODEL_INFERRED` CHECK is the SOLE forbidder — so "a MODEL_INFERRED
# observation cannot exist" is ONE guard a mutation can flip, not a rule split across two clauses.
_OBSERVATION_PROVENANCE_ENUM: tuple[str, ...] = (
    *OBSERVATION_PROVENANCE_ALLOWED, OBSERVATION_FORBIDDEN_PROVENANCE,
)

# The deterministic binding methods that may move PARSED/UNBOUND → BOUND (machine OB-3/OB-4,
# spec §12.5). A binding offered on anything else — a confidence score, a model guess — is NOT
# deterministic and fails closed to UNBOUND (GR-8). V4's fail-closed default is exact ID match only.
DETERMINISTIC_MATCH_METHODS: tuple[str, ...] = ("EXACT_ID", "RULE", "RECONCILE", "HUMAN")

_STATES_SQL = ",".join(f"'{s}'" for s in OBSERVATION_STATES)
_HUMAN_OWNED_SQL = ",".join(f"'{s}'" for s in HUMAN_OWNED_OBSERVATION_STATES)
_PROV_SQL = ",".join(f"'{p}'" for p in _OBSERVATION_PROVENANCE_ENUM)

# The one referent the readiness oracle checks by name (the named-human owner). Derived from the DDL
# too by the generic loop; naming it here is the unit stating what it is FOR.
P6OB_REQUIRED_REFERENTS: tuple[str, ...] = ("tenant_humans",)

# The exact abort texts, worded WITHOUT apostrophes: they are interpolated into single-quoted SQL
# literals inside RAISE(ABORT, ...); an apostrophe would terminate the literal. Named here and
# matched by `observation.py` when it classifies an IntegrityError — SQLite reports a trigger
# RAISE(ABORT) and a CHECK/UNIQUE violation through the same exception type.
RAW_VALUE_ABORT = (
    "raw_value is immutable [entity 07-observation sec 16/22, C-8]: a wrong reading is superseded by "
    "a NEW observation, never edited in place. You cannot cancel that the world spoke; you can only "
    "record that it later spoke differently"
)
DIGEST_ABORT = (
    "content_digest is immutable [entity 07-observation sec 10/19]: it is half the natural key that "
    "makes THIS observation this observation. A row whose digest can be rewritten has no identity, "
    "and the same email twice would stop being one fact"
)
IDENTITY_ABORT = (
    "the identity of an observation is immutable: the tenant, the observation id, the source system, "
    "the external id it came from and when it was received are what make it THIS fact, and editing "
    "them would retarget a recorded fact onto a different source"
)
VERSION_ABORT = (
    "observations.version advances by exactly one per processing-status transition [GR-3]: a state "
    "change that does not advance it silently overwrites another transition. OCC on processing "
    "status is the concurrency guard, and a version that stands still is a lost update"
)
DELETE_ABORT = (
    "observations is never deleted [entity 07-observation sec 28, C-9]: retention is permanent so the "
    "source can be rebuilt years later. A stale or superseded observation is still historical truth, "
    "and deleting the row is how that truth disappears"
)


P6OB_TARGET_SCHEMA: dict[str, str] = {
    # THE OBSERVATION (`entities/07-observation.md`, spec §12.5, machine M5).
    #
    # Every column on its OWN line and every FOREIGN KEY / CHECK on its OWN line, and every
    # multi-condition CHECK on ONE physical line: `schema._canonical_columns` parses this DDL line by
    # line, reads only the first token of a line as a column, and skips a line that STARTS with
    # PRIMARY KEY / FOREIGN KEY / UNIQUE / CHECK. A wrapped clause reads as a column called
    # `REFERENCES` or `AND` — the blind spot `phase6_pipeline_instances` documents.
    "observations": """
        CREATE TABLE observations (
            tenant TEXT NOT NULL,
            observation_id TEXT NOT NULL,
            -- The natural key (entity sec 9/17). source_system + external_id name WHERE the fact came
            -- from; content_digest is a RUNTIME hash of raw_value (never taken from inbound content),
            -- so identical content collides on the UNIQUE index below and becomes a confirmation.
            source_system TEXT NOT NULL,
            external_id TEXT NOT NULL,
            content_digest TEXT NOT NULL,
            -- ### THE FACT ITSELF, EXACTLY AS OBSERVED (entity sec 10/14). Immutable — the trigger
            -- below refuses any UPDATE of it. A changed reading is a NEW observation, never an edit.
            raw_value TEXT NOT NULL,
            -- as_of is the source observation time; a confirmation UPDATES as_of AND NOTHING ELSE.
            as_of TEXT NOT NULL,
            received_at TEXT NOT NULL,
            -- ### THE SEVEN CANONICAL STATES, ENUMERATED INLINE ON THE COLUMN (registry sec 4, M5).
            -- One physical line so the readiness parser still reads `state` as a NOT NULL column and
            -- so DDL introspection finds the vocabulary ON the column: there is no eighth state, no
            -- EXPIRED and no DELETED. Interpolated from OBSERVATION_STATES, the single source of truth.
            state TEXT NOT NULL CHECK (state IN (%(states)s)),
            version INTEGER NOT NULL,
            -- ### PROVENANCE IS RUNTIME-ASSIGNED (M-13, R-P1), NEVER SET FROM CONTENT. A MODEL_INFERRED
            -- observation is a structurally impossible state (entity sec 37) — forbidden by a CHECK,
            -- not merely by the Python. The allowed set is interpolated from OBSERVATION_PROVENANCE_
            -- ALLOWED, which omits MODEL_INFERRED; the explicit <> CHECK below is the word the mutation
            -- battery flips and the readiness oracle greps for.
            provenance_class TEXT NOT NULL,
            -- Processing outputs, set once on their transition. parsed_value on OB-2; bound_entity_ref
            -- and binding_claim_id and match_method on OB-3/OB-4. binding_claim_id carries the M6 claim
            -- reference a binding decision hands in and has NO foreign key: M6 (identity_binding_claims)
            -- is NOT built here (task sec 3.7), and a FK into a table that does not exist would be half
            -- of a machine this unit does not own.
            parsed_value TEXT,
            bound_entity_ref TEXT,
            binding_claim_id TEXT,
            match_method TEXT,
            -- ### THE NAMED HUMAN who owns an UNBOUND / UNPARSEABLE exception (entity sec 36, machine
            -- sec 9). A FK into the tenant's recorded humans: "human-owned" is decoration while this is
            -- a text column any string satisfies (M1's argument for owner_id). The CHECK below makes an
            -- UNBOUND/UNPARSEABLE row with no owner a structurally impossible state.
            owner_id TEXT,
            unparse_reason TEXT,
            -- Supersession links (entity sec 18, self-FK). The old observation was true when made and
            -- is RETAINED; superseded_by points at the newer one, supersedes back at the older.
            supersedes TEXT,
            superseded_by TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            PRIMARY KEY (tenant, observation_id),
            -- The owner is a recorded human of THIS tenant; the supersession links are self-FKs into
            -- observations. Each on its OWN line so the readiness parser skips it as a non-column.
            FOREIGN KEY (tenant, owner_id) REFERENCES tenant_humans (tenant, human_id),
            FOREIGN KEY (tenant, supersedes) REFERENCES observations (tenant, observation_id),
            FOREIGN KEY (tenant, superseded_by) REFERENCES observations (tenant, observation_id),
            -- The state-vocabulary CHECK lives INLINE on the column above (declared once).
            CHECK (version >= 1),
            -- entity sec 36 / machine sec 9: an UNBOUND or UNPARSEABLE observation names a human, or
            -- it is a silent drop wearing a status. On ONE line: a wrapped continuation would read as
            -- a column called OR.
            CHECK (state NOT IN (%(human_owned)s) OR owner_id IS NOT NULL),
            -- entity sec 13/37: a MODEL_INFERRED observation cannot exist. An observation is what a
            -- source said, not a guess.
            CHECK (provenance_class <> '%(forbidden_prov)s'),
            CHECK (provenance_class IN (%(prov)s)),
            CHECK (trim(observation_id) <> ''),
            CHECK (trim(source_system) <> ''),
            CHECK (trim(external_id) <> ''),
            CHECK (trim(content_digest) <> ''),
            CHECK (trim(raw_value) <> ''),
            CHECK (trim(as_of) <> ''),
            CHECK (trim(state) <> '')
        )""" % {
            "states": _STATES_SQL, "human_owned": _HUMAN_OWNED_SQL, "prov": _PROV_SQL,
            "forbidden_prov": OBSERVATION_FORBIDDEN_PROVENANCE,
        },
}


P6OB_INDEXES: dict[str, str] = {
    # ### THE NATURAL KEY — A UNIQUE INDEX THAT GENUINELY SERIALIZES CONCURRENT INGESTION (entity
    # sec 17, machine sec 17). Under a race, one INSERT of a given (tenant, source, external_id,
    # content_digest) wins and every other hits THIS index and becomes a confirmation. Drop the
    # UNIQUE, or drop content_digest from it, and the same email twice becomes two rows — a duplicate
    # Work Item, a duplicate approval card, eventually a duplicate invoice.
    "ix_observations_natural_key":
        "CREATE UNIQUE INDEX ix_observations_natural_key "
        "ON observations (tenant, source_system, external_id, content_digest)",
    # The operator surface: the UNBOUND / UNPARSEABLE exceptions a human owns, by age. Never a sweep
    # that ages them out (machine sec 37) — a read for the person accountable, not a timer.
    "ix_observations_tenant_state":
        "CREATE INDEX ix_observations_tenant_state "
        "ON observations (tenant, state, received_at)",
}

# Nothing from an earlier phase is replaced. Declared so a future replacement has somewhere to go.
P6OB_REPLACED_INDEXES: tuple[str, ...] = ()


P6OB_TRIGGERS: dict[str, str] = {
    # ### raw_value NEVER MUTATES (entity sec 16/22, C-8). This makes the sentence true against a
    # connection, not only against the Python. A wrong reading is superseded, never edited.
    "trg_observations_raw_value_immutable": f"""
        CREATE TRIGGER trg_observations_raw_value_immutable
        BEFORE UPDATE OF raw_value ON observations
        BEGIN SELECT RAISE(ABORT, '{RAW_VALUE_ABORT}'); END""",
    # ### content_digest NEVER MUTATES (entity sec 10/19). It is half the natural key; a row whose
    # digest can be rewritten has no identity, and the same email twice would stop being one fact.
    "trg_observations_content_digest_immutable": f"""
        CREATE TRIGGER trg_observations_content_digest_immutable
        BEFORE UPDATE OF content_digest ON observations
        BEGIN SELECT RAISE(ABORT, '{DIGEST_ABORT}'); END""",
    # ### THE REST OF THE IDENTITY IS IMMUTABLE TOO. Editing the source_system or external_id would
    # retarget a recorded fact onto a different source; editing received_at would rewrite when it was
    # recorded. All the shape of change an audit cannot detect afterwards, because the row is then
    # internally consistent.
    "trg_observations_identity_immutable": f"""
        CREATE TRIGGER trg_observations_identity_immutable
        BEFORE UPDATE OF tenant, observation_id, source_system, external_id, received_at
        ON observations
        BEGIN SELECT RAISE(ABORT, '{IDENTITY_ABORT}'); END""",
    # ### OCC ON PROCESSING STATUS (GR-3, machine sec 17). A processing-status transition advances
    # version by exactly one; a state change that leaves version standing is two transitions claiming
    # one version. A confirmation (as_of updated, state unchanged) does not trip this — its WHEN is
    # false because the state did not change.
    "trg_observations_version_advances_on_state_change": f"""
        CREATE TRIGGER trg_observations_version_advances_on_state_change
        BEFORE UPDATE ON observations
        WHEN NEW.state <> OLD.state AND NEW.version <> OLD.version + 1
        BEGIN SELECT RAISE(ABORT, '{VERSION_ABORT}'); END""",
    # ### NO DELETION, EVER (entity sec 28, C-9). No expiry, no retention sweep, no tidy-away. A
    # superseded observation is retained; a stale one is still a fact.
    "trg_observations_no_delete": f"""
        CREATE TRIGGER trg_observations_no_delete
        BEFORE DELETE ON observations
        BEGIN SELECT RAISE(ABORT, '{DELETE_ABORT}'); END""",
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


def create_phase6_observations_schema(conn: sqlite3.Connection, *, now: str) -> list[str]:
    """Create whatever M5 structure is missing. Idempotent; returns what it did.

    Callable on a fresh canonical database and on an already-migrated one. Either way the resulting
    structure is byte-identical, because there is only one text — the discipline every other phase
    uses, and the reason a fresh database is never briefly unsafe. Built AFTER M1 (`tenant_humans`
    FK), which is why `schema.py` orders it after the Work Item.
    """
    performed: list[str] = []
    present = _tables(conn)
    for name in (*P6OB_TENANT_TABLES, *P6OB_EXEMPT_TABLES):
        if name not in present:
            conn.execute(P6OB_TARGET_SCHEMA[name])
            performed.append(f"create-table:{name}")
    existing = _indexes(conn)
    for name, ddl in P6OB_INDEXES.items():
        if name not in existing:
            conn.execute(ddl)
            performed.append(f"create-index:{name}")
    for stale in P6OB_REPLACED_INDEXES:
        if stale in _indexes(conn):
            conn.execute(f"DROP INDEX {stale}")
            performed.append(f"drop-index:{stale}")
    existing_triggers = _triggers(conn)
    for name, ddl in P6OB_TRIGGERS.items():
        if name not in existing_triggers:
            conn.execute(ddl)
            performed.append(f"create-trigger:{name}")
    # NO VERSION STAMP HERE — marker-last. A stamp written by the builder appears on a half-migrated
    # database the moment a later step fails, which is how a missing trigger goes unnoticed.
    conn.commit()
    return performed


def stamp_phase6_observations_version(conn: sqlite3.Connection, *, now: str) -> None:
    """Record the M5 marker — callable ONLY once readiness holds. Marker-last, like every phase."""
    problems = phase6_observations_readiness_problems(conn)
    if problems:
        raise RuntimeError(
            f"refusing to stamp {P6OB_SCHEMA_VERSION} on a database that is NOT ready: "
            + "; ".join(problems)
        )
    if "schema_migrations" in _tables(conn):
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration, step, applied_at, detail) "
            "VALUES (?,?,?,?)",
            (MIGRATION_ID, f"version:{P6OB_SCHEMA_VERSION}", now,
             "the Observation: one immutable fact per natural key, tenant-first, raw_value and "
             "content_digest immutable by trigger, UNBOUND/UNPARSEABLE owned by a recorded human; "
             "readiness proven"),
        )
        conn.commit()


def phase6_observations_readiness_problems(conn: sqlite3.Connection) -> list[str]:
    """Every reason this database cannot carry immutable observed facts. Empty == ready.

    Structural, like the P2/P3/P5/M1/M2/M3/M4 oracles it extends. The natural-key UNIQUE index and
    the immutability triggers are verified PRESENT because an `observations` table without them is an
    ordinary table with an aspirational comment: the same email twice would insert twice, raw_value
    would be editable, and a MODEL_INFERRED guess could be filed as a fact.
    """
    problems: list[str] = []
    present = _tables(conn)
    for table in (*P6OB_TENANT_TABLES, *P6OB_EXEMPT_TABLES):
        if table not in present:
            problems.append(
                f"required Phase-6 table {table!r} is missing: run the {MIGRATION_ID} migration"
            )
    if not all(t in present for t in P6OB_TENANT_TABLES):
        return problems

    live_triggers = _triggers(conn)
    missing_triggers = sorted(t for t in P6OB_TRIGGERS if t not in live_triggers)
    if missing_triggers:
        problems.append(
            f"Observation invariant triggers missing: {missing_triggers}. Without them raw_value or "
            f"content_digest could be rewritten, a processing-status transition could stand the "
            f"version still, and the immutable fact could be deleted [entity sec 16/19/28, GR-3, C-9]."
        )
    live_indexes = _indexes(conn)
    for name in P6OB_INDEXES:
        if name not in live_indexes:
            problems.append(f"required Phase-6 index {name!r} is missing")
    for stale in P6OB_REPLACED_INDEXES:
        if stale in live_indexes:
            problems.append(f"replaced index {stale!r} is still present")

    # ### THE NATURAL KEY, READ OUT OF THE LIVE DATABASE RATHER THAN ASSUMED FROM ITS NAME. An index
    # called `..._natural_key` that is not UNIQUE, or that has dropped content_digest, is the
    # one-observation-per-fact defence switched off with the sign left up.
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name = ?",
        ("ix_observations_natural_key",),
    ).fetchone()
    if row is not None:
        sql = " ".join((row[0] or "").split()).upper()
        if "UNIQUE" not in sql:
            problems.append(
                "ix_observations_natural_key is not UNIQUE: the same email delivered twice would "
                "insert as two rows, and 'one fact per natural key' (entity sec 17) would be a "
                "convention, not a constraint."
            )
        for column in ("TENANT", "SOURCE_SYSTEM", "EXTERNAL_ID", "CONTENT_DIGEST"):
            if column not in sql:
                problems.append(
                    f"ix_observations_natural_key does not cover {column!r}: the natural key is "
                    f"(tenant, source_system, external_id, content_digest), and dropping a member "
                    f"widens or narrows what counts as 'the same fact'."
                )

    # ### THE CHECKS AND THE STATE VOCABULARY, READ OUT OF THE observations DDL. A CHECK the migration
    # intended but a live database does not carry is the invariant switched off.
    ddl_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='observations'").fetchone()
    ddl = " ".join((ddl_row[0] if ddl_row else "" or "").split()).upper()
    expected_states = ("STATE IN (" + ",".join(f"'{s}'" for s in OBSERVATION_STATES) + ")").upper()
    if expected_states not in ddl.replace(", ", ","):
        problems.append(
            "observations does not enumerate the seven canonical states inline on the state column "
            "(registry sec 4, M5): without it an eighth state — an EXPIRED or a DELETED — would be "
            "writable, and entity sec 26/28 say neither exists."
        )
    human_owned_check = (
        "STATE NOT IN (" + ",".join(f"'{s}'" for s in HUMAN_OWNED_OBSERVATION_STATES)
        + ") OR OWNER_ID IS NOT NULL").upper()
    if human_owned_check not in ddl.replace(", ", ","):
        problems.append(
            "observations does not CHECK that an UNBOUND or UNPARSEABLE observation names an owner: "
            "entity sec 36 makes 'never a silent drop' a human-owned exception, and a database "
            "enforces it with a CHECK plus the tenant_humans FK."
        )
    if f"PROVENANCE_CLASS <> '{OBSERVATION_FORBIDDEN_PROVENANCE}'" not in ddl:
        problems.append(
            "observations does not CHECK that provenance_class is never MODEL_INFERRED: entity sec "
            "13/37 names a MODEL_INFERRED observation a structurally impossible state — a source said "
            "it, it was never a guess."
        )

    for table in P6OB_TENANT_TABLES:
        referents = _referents(conn, table)
        for referent in P6OB_REQUIRED_REFERENTS:
            if referent not in referents:
                problems.append(
                    f"{table} declares no foreign key into {referent!r}: 'owned by an authenticated "
                    f"recorded human' is decoration while owner_id is a free-text column (entity "
                    f"sec 18, M1's argument for owner_id)."
                )
    return problems
