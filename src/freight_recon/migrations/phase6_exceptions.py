"""Phase 6 — M9, the Exception: one `exceptions` row per thing that needs a human, one machine, five
states, and the one honesty rule that makes an obligation Neyma could not resolve reach a NAMED PERSON
rather than be quietly forgotten.

WHAT THIS TABLE IS, IN FREIGHT TERMS

    A TMS write times out and the outcome is UNKNOWN. Neyma does NOT log it and move on — it RAISES an
    Exception with a named human owner from the moment the row exists and a severity recorded beside it.
    An authenticated human ACKNOWLEDGES it, which proves they SAW it and proves nothing else, and it
    keeps ageing. Nobody acts, so a durable timer moves it to AGEING and then ESCALATED — louder, still
    owned, and never resolved by the clock. Someone tries to close it with the string "done" and the
    database refuses, because closure is an event with a `decision_ref` that RESOLVES to an authenticated
    human decision. A model tries to clear it and is refused at any confidence. The severity is
    reassessed and that is a FIELD change carrying the value it moved from, so a rebuild months later
    reproduces the severity that is LIVE rather than the one it was born with.

    ### AN EXCEPTION IS SOMETHING THAT NEEDS A HUMAN. IT REACHES A NAMED HUMAN OWNER FROM CREATION, AND
    ### IT IS NEVER CLOSED BY SILENCE. AN EXCEPTION CLOSED WITHOUT A DECISION IS NOT CLOSED — IT IS
    ### FORGOTTEN (F-30). It is NOT an error log, an alert, or an issue tracker row; it is NOT
    ### auto-closable and NOT outlivable (entity §4).

WHY AN OWNERLESS EXCEPTION IS STRUCTURALLY IMPOSSIBLE (entity §16/§37, I1, M-35, AC-SAFE-028)

    `owner_id` is `NOT NULL` from creation and FOREIGN-KEY-backed into `tenant_humans` (M1's precedent
    for a named ACTIVE human; M7's for the human behind a `decision_ref`). "An Exception has a human
    owner" is decoration while `owner_id` is a free-text column any string satisfies. A system-raised
    Exception STILL gets a named ACTIVE human at creation — the CALLER supplies the human; the machine
    never picks one, `system` is not a human, and a model actor may never be the owner (`[C-6]`, `ER-9`).

WHY CLOSURE REQUIRES A `decision_ref` THAT RESOLVES (entity §16/§22/§36, GR-14, K-1, I11, AC-MACH-903)

    `CHECK (state <> 'RESOLVED' OR decision_ref IS NOT NULL)` is the STRUCTURAL half — a RESOLVED row
    with no `decision_ref` is not insertable. But the CHECK is NOT "non-null"; it is "RESOLVES". The
    machine imports M1's landed `resolve_decision_ref` (### the ONE K-1 executor — never a second) and
    refuses a value that references nothing, a human-decision event type recorded by automation (ER-11),
    or an event that is not a human decision at all. A bare string fails; the string `done` fails. And
    `CHECK (state <> 'RESOLVED' OR decision_human_id IS NOT NULL)` names the ACTIVE human behind it.

WHY THERE IS NO SIXTH STATE, NO CANCELLED, NO EXPIRED, NO SUB_STATUS-AS-STATE

    Five states only (`OPEN, ACKNOWLEDGED, AGEING, ESCALATED, RESOLVED`), enumerated inline on the state
    column: no `CANCELLED` (### M9-AQ-2: a retracted cause is still an event, still a `decision_ref`,
    and reaches RESOLVED like every other closure — there is no CANCELLED state and no cancelled-event
    registered to hold it), no `EXPIRED` (entity §26: an exception NEVER expires — it ages/escalates), no
    `AUTO_CLOSED`, no `TIMED_OUT`, no `STALE`, no `SUPERSEDED`, no `REOPENED`. The brief's finer
    sub-states (triage / assigned / investigating / awaiting-external / awaiting-human /
    resolution-proposed) are a `sub_status` FIELD with a closed CHECK vocabulary DISJOINT from the state
    set, never lifecycle states (machine header). ### M9-AQ-2: a retracted cause is still an event with
    a `decision_ref` (entity §25) and reaches RESOLVED like every other closure — there is no cancelled
    state and no cancelled-event registered anywhere to hold it, and none is invented here.

WHY THE FREEZE IS CONDITIONAL AND RECORDED (### M9-AQ-5, entity §15/§38)

    ### NOT EVERY EXCEPTION FREEZES AN ENTITY — only those that make a material field non-`consistent`
    (entity §38). `freezes_entity` is stated by the caller and RECORDED; when it is set, `entity_ref`
    (the projected business entity, K-2) and `frozen_field` are required. The freeze is written in the
    SAME COMMIT as the raise and its event, so a persistence failure leaves nothing half-raised.
    `exception.py` projects a freezing open Exception into the checkpoint's EXISTING `NativeClaim
    (conflicting=…)` types WITHOUT importing the checkpoint — an Exception is an INPUT to the gate and
    never a gate. P3 stays the sole gate minter and M3 the single effect authority (CLAUDE.md rule 17).

WHY THE DEDUP INDEX IS BUILT, AND RECORDED AS A CHOICE (### entity §17, machine §17/§19, F9)

    Three canonical files call `UNIQUE (tenant, source_ref, type) WHERE state != 'RESOLVED'` OPTIONAL in
    those words. Machine §19 says "GR-4 + the dedup index", the closest thing to a requirement in the
    corpus. ### THIS BUILD BUILDS IT — tenant-first, partial on `state != 'RESOLVED'` — so a re-raise of
    the same cause is a database-serialized no-op rather than only an application short-circuit, and it
    records that CHOICE here rather than turning an explicitly optional constraint into a silent
    mandatory acceptance criterion. `GR-4`'s consumer-inbox idempotency is the MANDATORY half and is
    unconditional.

WHAT THE FOREIGN KEYS POINT AT (### M9-AQ-3, entity §18, task §3.9)

    `owner_id` / `acknowledged_by` / `decision_human_id` -> `tenant_humans` (M1). `source_ref` is
    POLYMORPHIC across eight-plus aggregate types with no one table to point at, so it follows M7's
    `conflict_parties` shape EXACTLY: `source_ref` is the single source of truth, `source_kind` is a
    closed CHECK discriminator, and per-kind MIRROR columns carry a real FK ONLY for the kinds whose
    table EXISTS today — `observation` (M5), `identity_binding_claim` (M6), `conflict` (M7),
    `expectation` (M8), `work_item` (M1), `pipeline_instance` (M2), `effect_grant` (M3), `approval`
    (M4). The kinds whose table does NOT exist — `compensation` (M10), `evidence` (P7), `rule` (M12),
    `policy` (M11), `pending_reference` (a composite-keyed park) — are carried as a constrained,
    NOT-NULL `source_ref` with the discriminator and NO FK, and that missing half is RECORDED. Nothing
    here builds `compensations`, `evidence`, `rules` or `policies` to give a FK somewhere to point.

WHAT IS DELIBERATELY *NOT* HERE (the seams this unit does not own)

    No `exceptions`-adjacent freeze table (### M9-AQ-5: the row IS the durable condition, projected into
    the checkpoint's existing types). No `compensations`/`policies`/`rules`/`evidence` table and no
    `CM-*`/`PO-*`/`RU-*`. No `rules` FK for a `decision_ref` of kind RULE — that half REFUSES today in
    M1's resolver (debt P6-D4, closes at M12). No brake engagement — a Sev-0 exception CARRIES `SEV0`;
    the brake is the source detector's act (F9 cross-cutting), not M9's.

FRESH == MIGRATED, SHIPS DARK

    `create_canonical_schema` builds this table directly; a database reached by
    `phase2_tenant_first.migrate` reaches the SAME shape through `create_phase6_exceptions_schema`.
    Nothing routes production traffic through M9; `exception.py` is the only non-test module that reads
    it, and only `scripts/probe_phase6_exception.py` imports the machine. NO oversight queue, UI,
    dashboard, notifier, pager or MTTR emitter ships with M9.
"""

from __future__ import annotations

import sqlite3

MIGRATION_ID = "phase6_exceptions"
P6XC_SCHEMA_VERSION = "phase6-exceptions-1"

# Tenant-owned. An Exception is owed WITHIN one brokerage; the same source_ref in two tenants are two
# isolated Exceptions [C-1]. Every query and every uniqueness constraint is tenant-first.
P6XC_TENANT_TABLES: tuple[str, ...] = ("exceptions",)

# Nothing tenant-exempt. Stated rather than omitted, so a future addition must defend its exemption.
P6XC_EXEMPT_TABLES: tuple[str, ...] = ()

# `state-machines/registry.md` §4, M9 / target spec §12.9 — the FIVE, in the registry's own order.
# There is no sixth: no CANCELLED (### M9-AQ-2), no EXPIRED (entity §26: NEVER), no AUTO_CLOSED, no
# TIMED_OUT, no STALE, no SUPERSEDED, no REOPENED.
EXCEPTION_STATES: tuple[str, ...] = (
    "OPEN", "ACKNOWLEDGED", "AGEING", "ESCALATED", "RESOLVED",
)

# machine §8 — the one terminal state (no outgoing enumerated transition to a live state).
TERMINAL_EXCEPTION_STATES: tuple[str, ...] = ("RESOLVED",)

# machine §9 — the FOUR non-terminal human-owned states. Every one names its human; getting louder
# (AGEING/ESCALATED) never means getting orphaned.
HUMAN_OWNED_EXCEPTION_STATES: tuple[str, ...] = (
    "OPEN", "ACKNOWLEDGED", "AGEING", "ESCALATED",
)

# entity §12, registry §4, F9 — the WHOLE severity vocabulary. A Sev-0 exception carries SEV0; the
# brake engagement at its source is not M9's (F9 cross-cutting). There is no fourth severity.
EXCEPTION_SEVERITIES: tuple[str, ...] = ("SEV0", "SEV1", "SEV2")

# The machine header's finer sub-states as a closed FIELD vocabulary — NOT lifecycle states. Spelled
# lowercase so a value can never be mistaken for a canonical state (the five are UPPERCASE) and the
# two vocabularies are DISJOINT. `awaiting_human` here is a sub_status VALUE, never M1's AWAITING_HUMAN
# lifecycle state (registry: no machine defines a local synonym); it appears in no transition guard
# that changes `state` and adds no transition row.
SUB_STATUSES: tuple[str, ...] = (
    "triage", "assigned", "investigating", "awaiting_external", "awaiting_human",
    "resolution_proposed",
)

# entity §13/§31 — the failure classification a PERMANENT-failure exception RECORDS. The vocabulary is
# M1's landed `FailureDisposition` (its `.value`s), SUPPLIED to EC-1 as an enumerated value and never
# INFERRED from a message (task §3.5.8, M-74: "a catch-all base class is NOT a classification"). A
# catch-all base class, an HTTP status, a vendor string and a model's opinion are none of these two.
FAILURE_CLASSIFICATIONS: tuple[str, ...] = ("transient", "permanent")

# `decision_ref`'s resolvable-kind discriminator (K-1), UPPERCASE to match M1's `DECISION_REF_KINDS`
# EXACTLY, because M9 IMPORTS and CALLS `work_item.resolve_decision_ref` (never a second resolver). A
# human decision resolves into an `audit_events` row (the canonical event log); a rule-basis decision
# would resolve into `rules` (M12, NOT built) and refuses today — debt P6-D4, not M9's to close.
DECISION_REF_KINDS: tuple[str, ...] = ("AUDIT_EVENT", "RULE")

# ### THE POLYMORPHIC SOURCE (### M9-AQ-3, entity §9/§18). `source_ref` is the single source of truth;
# `source_kind` is the closed discriminator; per-kind MIRROR columns carry a real FK ONLY for the kinds
# whose table EXISTS today (M7's `conflict_parties` shape, exact). kind -> (mirror_column, table, pk).
SOURCE_KIND_TABLE: dict[str, tuple[str, str, str]] = {
    "observation": ("source_observation_ref", "observations", "observation_id"),
    "identity_binding_claim": ("source_claim_ref", "identity_binding_claims", "binding_claim_id"),
    "conflict": ("source_conflict_ref", "conflicts", "conflict_id"),
    "expectation": ("source_expectation_ref", "expectations", "expectation_id"),
    "work_item": ("source_work_item_ref", "work_items", "work_item_id"),
    "pipeline_instance": ("source_pipeline_ref", "pipeline_instances", "pipeline_instance_id"),
    "effect_grant": ("source_grant_ref", "effect_grants", "grant_id"),
    "approval": ("source_approval_ref", "approvals", "approval_id"),
}

# The kinds whose table does NOT exist today — carried as a constrained discriminator with NO FK, and
# RECORDED here (### M9-AQ-3). `pending_reference` is keyed (tenant, consumer_id, event_id), not a
# single id, so it could not be FK-backed even if it were "a table this unit owns".
SOURCE_KINDS_WITHOUT_TABLE: tuple[str, ...] = (
    "compensation", "evidence", "rule", "policy", "pending_reference",
)

# The full closed vocabulary — the FK-backed kinds first, then the recorded-only kinds.
SOURCE_KINDS: tuple[str, ...] = (*SOURCE_KIND_TABLE.keys(), *SOURCE_KINDS_WITHOUT_TABLE)

# The referents the readiness oracle checks by name. Derived from the DDL by the generic FK loop too;
# naming them here is the unit stating what they are FOR.
P6XC_EXCEPTION_REFERENTS: tuple[str, ...] = (
    "tenant_humans", *(tbl for (_, tbl, _) in SOURCE_KIND_TABLE.values()),
)

_STATES_SQL = ",".join(f"'{s}'" for s in EXCEPTION_STATES)
_SEV_SQL = ",".join(f"'{s}'" for s in EXCEPTION_SEVERITIES)
_SUB_SQL = ",".join(f"'{s}'" for s in SUB_STATUSES)
_FAIL_SQL = ",".join(f"'{c}'" for c in FAILURE_CLASSIFICATIONS)
_SOURCE_KINDS_SQL = ",".join(f"'{k}'" for k in SOURCE_KINDS)
_DECISION_KINDS_SQL = ",".join(f"'{k}'" for k in DECISION_REF_KINDS)

# The per-kind MIRROR column declarations, foreign keys and consistency CHECKs — generated so the
# eight FK-backed kinds cannot drift out of step, each on its OWN physical line (the readiness parser
# reads only a line's first token as a column and skips a line starting with FOREIGN KEY / CHECK).
_MIRROR_COLUMN_SQL = "\n".join(
    f"            {col} TEXT," for (col, _, _) in SOURCE_KIND_TABLE.values())
_MIRROR_FK_SQL = "\n".join(
    f"            FOREIGN KEY (tenant, {col}) REFERENCES {tbl} (tenant, {pk}),"
    for (col, tbl, pk) in SOURCE_KIND_TABLE.values())
_MIRROR_CHECK_SQL = "\n".join(
    f"            CHECK (source_kind <> '{kind}' OR {col} = source_ref),\n"
    f"            CHECK (source_kind = '{kind}' OR {col} IS NULL),"
    for kind, (col, _, _) in SOURCE_KIND_TABLE.items())

# The exact abort texts, worded WITHOUT apostrophes: they are interpolated into single-quoted SQL
# literals inside RAISE(ABORT, ...). Matched by `exception.py` when it classifies an IntegrityError.
VERSION_ABORT = (
    "exceptions.version advances by exactly one per state transition [GR-3, C-10]: a state change "
    "that does not advance it silently overwrites another transition. OCC on the exception version is "
    "the concurrency guard, and a version that stands still is a lost update"
)
IDENTITY_ABORT = (
    "the identity of an exception is immutable [entity 12 sec 15/16, C-8]: the tenant, the id, the "
    "type, the source that raised it, the kind of that source, the entity it concerns, whether it "
    "freezes that entity and which field, the owner assigned at creation, and when it was raised are "
    "what make it THIS exception. Severity may be reassessed [EC-7]; the identity may not, or a "
    "permanent-failure exception on one load would quietly become one on another"
)
DELETE_ABORT = (
    "an exception is never deleted [entity 12 sec 28/29, C-9]: retention is permanent, and an "
    "exception NEVER expires and is never swept away by a reaper. A row that quietly stops being "
    "visible is the EXACT failure this entity exists to prevent — an exception closed without a "
    "decision is not closed, it is FORGOTTEN [F-30]. No sweep, no reaper, no scan, no TTL"
)


P6XC_TARGET_SCHEMA: dict[str, str] = {
    # THE EXCEPTION (`entities/12-exception.md`, spec §12.9, machine M9).
    #
    # Every column on its OWN line and every FOREIGN KEY / CHECK / PRIMARY KEY on its OWN physical
    # line, and every multi-condition CHECK on ONE physical line: `schema._canonical_columns` parses
    # this DDL line by line, reads only the first token of a line as a column, and skips a line that
    # STARTS with PRIMARY KEY / FOREIGN KEY / UNIQUE / CHECK. A wrapped clause would read as a phantom
    # column called `REFERENCES` or `OR` — the blind spot `phase6_pipeline_instances` documents and
    # this repository produced four times.
    "exceptions": """
        CREATE TABLE exceptions (
            tenant TEXT NOT NULL,
            exception_id TEXT NOT NULL,
            -- The exception TYPE — the category of what needs a human (an unknown outcome, an
            -- unparseable observation, an ambiguous binding…). Open by design (entity §21 ends its
            -- cause list with an ellipsis): freight/cause-domain vocabulary, not a closed machine enum,
            -- so NOT NULL and non-empty rather than CHECK-enumerated. Component of the dedup key.
            type TEXT NOT NULL,
            -- ### THE SEVERITY, ENUMERATED INLINE (entity §12, registry §4, F9). One physical line so
            -- the readiness parser reads `severity` as NOT NULL and finds the vocabulary ON the column:
            -- SEV0 | SEV1 | SEV2 and no fourth. EC-7 mutates it (with its own event); it never gates.
            severity TEXT NOT NULL CHECK (severity IN (%(sev)s)),
            -- ### THE FIVE CANONICAL STATES, ENUMERATED INLINE (registry §4, M9). One physical line:
            -- no sixth state — no CANCELLED, no EXPIRED, no AUTO_CLOSED, no TIMED_OUT, no bare
            -- SUPERSEDED. Interpolated from EXCEPTION_STATES, the single source of truth.
            state TEXT NOT NULL CHECK (state IN (%(states)s)),
            version INTEGER NOT NULL,
            -- ### THE NAMED HUMAN who owns the Exception FROM CREATION (entity §10/§16/§37, machine §5,
            -- I1). NOT NULL, and FK-backed into the tenant's recorded humans below: an ownerless
            -- Exception is a STRUCTURALLY IMPOSSIBLE state, `system` is not a human, and a model actor
            -- may never be the owner. The caller supplies the human; the machine never picks one.
            owner_id TEXT NOT NULL,
            -- ### THE MACHINE THAT RAISED IT (entity §9). `source_ref` is the single source of truth;
            -- `source_kind` is the closed discriminator; the MIRROR columns below carry the FK for the
            -- kinds whose table exists. `source_ref` is NOT NULL — an exception with no cause is a
            -- silent alert wearing a status.
            source_ref TEXT NOT NULL,
            source_kind TEXT NOT NULL CHECK (source_kind IN (%(source_kinds)s)),
%(mirror_columns)s
            -- ### THE PROJECTED BUSINESS ENTITY THIS EXCEPTION CONCERNS (K-2, entity §14). Distinct
            -- from source_ref (the machine row that raised it): a load/document/movement projection is
            -- freight domain (P9+) and carries NO FK. Required when the exception freezes it.
            entity_ref TEXT,
            frozen_field TEXT,
            -- ### THE CONDITIONAL FREEZE (### M9-AQ-5, entity §38). NOT every exception freezes an
            -- entity — only those that make a material field non-consistent. Stated by the caller and
            -- RECORDED; when set, entity_ref and frozen_field are required (CHECK below). 0 or 1.
            freezes_entity INTEGER NOT NULL,
            -- The finer sub-state as a FIELD, never a lifecycle state (machine header). Closed
            -- vocabulary DISJOINT from the five states. Set at raise under OPEN.
            sub_status TEXT,
            -- ### THE SUPPLIED FAILURE CLASSIFICATION (entity §13/§31, L-D, M-74). A PERMANENT
            -- (auth/config) failure records `permanent`; it is SUPPLIED as an enumerated value from
            -- M1's FailureDisposition, never inferred from a message. Nullable — most exceptions are
            -- not failure-derived.
            failure_classification TEXT,
            -- Optional money exposure (K-4: sourced from a verified/live read, never memory) and the
            -- specific question we need the human to answer (entity §11). Never gate inputs.
            exposure TEXT,
            specific_question TEXT,
            summary TEXT NOT NULL,
            -- Set on EC-2 (a human SAW it): the acknowledging ACTIVE human and when. Acknowledgement
            -- proves seen, not resolved; the obligation still ages (entity §31).
            acknowledged_at TEXT,
            acknowledged_by TEXT,
            -- Set on EC-4 / EC-5 (the durable ageing/escalation timers). Stamps only; they never
            -- resolve (machine §37).
            ageing_at TEXT,
            escalation_at TEXT,
            -- Set on EC-3 / EC-6 (RESOLVED). decision_ref is the resolving reference; decision_ref_kind
            -- is K-1's discriminator; decision_human_id is the FK-backed ACTIVE human behind it. There
            -- is no FK on decision_ref — a human decision resolves against the canonical event log
            -- (M1's resolver), and the rule half is M12 (not built).
            decision_ref TEXT,
            decision_ref_kind TEXT,
            decision_human_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            PRIMARY KEY (tenant, exception_id),
            -- The owner, the acknowledging human and the decision-human are recorded ACTIVE humans of
            -- THIS tenant. Each on its OWN line so the readiness parser skips it as a non-column.
            FOREIGN KEY (tenant, owner_id) REFERENCES tenant_humans (tenant, human_id),
            FOREIGN KEY (tenant, acknowledged_by) REFERENCES tenant_humans (tenant, human_id),
            FOREIGN KEY (tenant, decision_human_id) REFERENCES tenant_humans (tenant, human_id),
%(mirror_fks)s
            -- The severity / state / source_kind vocabulary CHECKs live INLINE on the columns above.
            CHECK (version >= 1),
            -- ### CLOSURE REQUIRES A decision_ref THAT RESOLVES (entity §16, GR-14, K-1, I11, F-30).
            -- This CHECK is the STRUCTURAL half — a RESOLVED row with no decision_ref is not
            -- insertable — and `exception.py` supplies the "RESOLVES" half by importing M1's resolver.
            -- Each on ONE physical line.
            CHECK (state <> 'RESOLVED' OR decision_ref IS NOT NULL),
            -- ### A RESOLVED EXCEPTION NAMES THE ACTIVE HUMAN BEHIND ITS decision_ref (K-1, entity
            -- §35): "an authenticated human" is decoration while decision_human_id is free text.
            CHECK (state <> 'RESOLVED' OR decision_human_id IS NOT NULL),
            CHECK (decision_ref_kind IS NULL OR decision_ref_kind IN (%(decision_kinds)s)),
            -- ### THE CONDITIONAL FREEZE IS RECORDED, NOT GUESSED (### M9-AQ-5, entity §38). A freezing
            -- exception names the entity and the field it froze; a non-freezing one names neither.
            CHECK (freezes_entity IN (0, 1)),
            CHECK (freezes_entity = 0 OR (entity_ref IS NOT NULL AND frozen_field IS NOT NULL)),
            -- ### sub_status IS A FIELD FROM A CLOSED VOCABULARY, NEVER A LIFECYCLE STATE (machine
            -- header). The vocabulary is DISJOINT from the five states, so it can never be a state.
            CHECK (sub_status IS NULL OR sub_status IN (%(sub_statuses)s)),
            CHECK (failure_classification IS NULL OR failure_classification IN (%(fail_class)s)),
            -- ### THE SOURCE MIRROR IS CONSISTENT WITH source_kind (### M9-AQ-3). A kind whose table
            -- exists sets its mirror = source_ref (and no other mirror); a kind with no table sets no
            -- mirror, and source_ref carries the token. Each on ONE physical line.
%(mirror_checks)s
            CHECK (trim(exception_id) <> ''),
            CHECK (trim(type) <> ''),
            CHECK (trim(owner_id) <> ''),
            CHECK (trim(source_ref) <> ''),
            CHECK (trim(summary) <> ''),
            CHECK (trim(state) <> '')
        )""" % {
            "sev": _SEV_SQL, "states": _STATES_SQL, "source_kinds": _SOURCE_KINDS_SQL,
            "decision_kinds": _DECISION_KINDS_SQL, "sub_statuses": _SUB_SQL, "fail_class": _FAIL_SQL,
            "mirror_columns": _MIRROR_COLUMN_SQL, "mirror_fks": _MIRROR_FK_SQL,
            "mirror_checks": _MIRROR_CHECK_SQL,
        },
}


P6XC_INDEXES: dict[str, str] = {
    # ### THE OPTIONAL OPEN-EXCEPTION DEDUP INDEX — A PARTIAL UNIQUE INDEX (entity §17, machine §17/§19,
    # F9). Three canonical files call this OPTIONAL in those words; THIS BUILD builds it (machine §19:
    # "GR-4 + the dedup index"), tenant-first and partial on `state != 'RESOLVED'`, so a re-raise of the
    # same (source_ref, type) cause is a database-serialized no-op. Drop the UNIQUE, or drop the WHERE,
    # or drop the tenant, and two open exceptions fit one cause. Recorded as a CHOICE, not smuggled in
    # as a mandatory acceptance criterion (task §3.5.9).
    "ix_exceptions_one_open_per_cause":
        "CREATE UNIQUE INDEX ix_exceptions_one_open_per_cause "
        "ON exceptions (tenant, source_ref, type) WHERE state != 'RESOLVED'",
    # The human's queue: the open exceptions a named human owns, ordered by severity and age — what an
    # ordering needs (entity §42). NEEDS_VERIFICATION-backed and Sev-0 exceptions are the highest
    # priority; mean-time-to-human-resolution is the metric that matters. M9 owes the row and the
    # tenant-first index; it does NOT build the queue.
    "ix_exceptions_owner_queue":
        "CREATE INDEX ix_exceptions_owner_queue "
        "ON exceptions (tenant, owner_id, state, severity, created_at)",
    # The source read across every state (open and resolved history), for the dedup lookup and audit.
    "ix_exceptions_source":
        "CREATE INDEX ix_exceptions_source ON exceptions (tenant, source_ref, type, state)",
}

# Nothing from an earlier phase is replaced. Declared so a future replacement has somewhere to go.
P6XC_REPLACED_INDEXES: tuple[str, ...] = ()


P6XC_TRIGGERS: dict[str, str] = {
    # ### OCC ON THE EXCEPTION (GR-3, C-10, machine §17). A state transition advances version by exactly
    # one; a state change that leaves version standing is two transitions claiming one version. (An EC-7
    # severity change does NOT change state, so it may advance version freely — this fires only on a
    # state change that fails to advance it.)
    "trg_exceptions_version_advances_on_state_change": f"""
        CREATE TRIGGER trg_exceptions_version_advances_on_state_change
        BEFORE UPDATE ON exceptions
        WHEN NEW.state <> OLD.state AND NEW.version <> OLD.version + 1
        BEGIN SELECT RAISE(ABORT, '{VERSION_ABORT}'); END""",
    # ### THE IDENTITY OF THE EXCEPTION IS IMMUTABLE, BUT SEVERITY IS NOT (entity §15/§16, EC-7). The
    # tenant, id, type, source and its kind, the entity it concerns, the freeze decision and field, the
    # owner and created_at may not be edited — editing them would retarget or relaunder a recorded
    # obligation in place. `severity` is DELIBERATELY ABSENT from this list because EC-7 reassesses it.
    "trg_exceptions_identity_immutable": f"""
        CREATE TRIGGER trg_exceptions_identity_immutable
        BEFORE UPDATE OF tenant, exception_id, type, source_ref, source_kind, entity_ref,
                         frozen_field, freezes_entity, owner_id, created_at
        ON exceptions
        BEGIN SELECT RAISE(ABORT, '{IDENTITY_ABORT}'); END""",
    # ### NO DELETION, EVER, AND NO EXPIRY (entity §26/§28/§29, C-9). Retention is permanent; an
    # exception ages and escalates but is NEVER outlived, swept, reaped or deleted. This is the
    # structural form of "an exception closed without a decision is FORGOTTEN" — deleting the row is
    # exactly the forgetting this entity exists to prevent one level up.
    "trg_exceptions_no_delete": f"""
        CREATE TRIGGER trg_exceptions_no_delete
        BEFORE DELETE ON exceptions
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


def create_phase6_exceptions_schema(conn: sqlite3.Connection, *, now: str) -> list[str]:
    """Create whatever M9 structure is missing. Idempotent; returns what it did.

    Callable on a fresh canonical database and on an already-migrated one. Either way the resulting
    structure is byte-identical, because there is only one text. Built LAST of the P6 units because
    `exceptions` holds FKs into every prior P6 machine's table (M1..M8) plus tenant_humans (M1), which
    is why `schema.py` orders it after them.
    """
    performed: list[str] = []
    present = _tables(conn)
    for name in (*P6XC_TENANT_TABLES, *P6XC_EXEMPT_TABLES):
        if name not in present:
            conn.execute(P6XC_TARGET_SCHEMA[name])
            performed.append(f"create-table:{name}")
    existing = _indexes(conn)
    for name, ddl in P6XC_INDEXES.items():
        if name not in existing:
            conn.execute(ddl)
            performed.append(f"create-index:{name}")
    for stale in P6XC_REPLACED_INDEXES:
        if stale in _indexes(conn):
            conn.execute(f"DROP INDEX {stale}")
            performed.append(f"drop-index:{stale}")
    existing_triggers = _triggers(conn)
    for name, ddl in P6XC_TRIGGERS.items():
        if name not in existing_triggers:
            conn.execute(ddl)
            performed.append(f"create-trigger:{name}")
    # NO VERSION STAMP HERE — marker-last, like every phase. A stamp on a half-migrated database is
    # how a missing trigger goes unnoticed.
    conn.commit()
    return performed


def stamp_phase6_exceptions_version(conn: sqlite3.Connection, *, now: str) -> None:
    """Record the M9 marker — callable ONLY once readiness holds. Marker-last, like every phase."""
    problems = phase6_exceptions_readiness_problems(conn)
    if problems:
        raise RuntimeError(
            f"refusing to stamp {P6XC_SCHEMA_VERSION} on a database that is NOT ready: "
            + "; ".join(problems)
        )
    if "schema_migrations" in _tables(conn):
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration, step, applied_at, detail) "
            "VALUES (?,?,?,?)",
            (MIGRATION_ID, f"version:{P6XC_SCHEMA_VERSION}", now,
             "the Exception: one exceptions row per thing that needs a human, tenant-first, five "
             "states, a named ACTIVE human owner from creation (structurally impossible ownerless), "
             "closure requires a decision_ref that RESOLVES (structural CHECK + M1's resolver), never "
             "closed by silence, no expiry and no deletion, ageing/escalation on durable timers, a "
             "conditional recorded freeze, the optional open-exception dedup index BUILT; readiness "
             "proven"),
        )
        conn.commit()


def phase6_exceptions_readiness_problems(conn: sqlite3.Connection) -> list[str]:
    """Every reason this database cannot carry Exceptions safely. Empty == ready.

    Structural, like the P2/P3/P5/M1..M8 oracles it extends. The RESOLVED-requires-decision_ref CHECK,
    the named-decision-human CHECK, the owner NOT NULL + FK, the closed vocabularies, the conditional
    freeze CHECK, the no-delete/immutability triggers and the source-mirror FKs are verified PRESENT
    because an `exceptions` table without them is an ordinary table with an aspirational comment: a
    RESOLVED row with no decision could exist, an ownerless obligation could exist, a sixth state or a
    fourth severity could be written, and a resolved exception could be deleted.
    """
    problems: list[str] = []
    present = _tables(conn)
    for table in (*P6XC_TENANT_TABLES, *P6XC_EXEMPT_TABLES):
        if table not in present:
            problems.append(
                f"required Phase-6 table {table!r} is missing: run the {MIGRATION_ID} migration"
            )
    if not all(t in present for t in P6XC_TENANT_TABLES):
        return problems

    live_triggers = _triggers(conn)
    missing_triggers = sorted(t for t in P6XC_TRIGGERS if t not in live_triggers)
    if missing_triggers:
        problems.append(
            f"Exception invariant triggers missing: {missing_triggers}. Without them an exception "
            f"could be deleted (a recorded obligation FORGOTTEN), a state transition could stand the "
            f"version still (a lost update), or the identity/owner/freeze could be edited in place "
            f"[entity §15/§26/§28, GR-3, C-9]."
        )
    live_indexes = _indexes(conn)
    for name in P6XC_INDEXES:
        if name not in live_indexes:
            problems.append(f"required Phase-6 index {name!r} is missing")
    for stale in P6XC_REPLACED_INDEXES:
        if stale in live_indexes:
            problems.append(f"replaced index {stale!r} is still present")

    # ### THE OPTIONAL-BUT-BUILT DEDUP INDEX, READ OUT OF THE LIVE DATABASE RATHER THAN ASSUMED FROM
    # ITS NAME. This build BUILT it; an index called `..._one_open_per_cause` that is not UNIQUE, or
    # that has lost its `WHERE state != 'RESOLVED'` clause, is the dedup this build chose switched off
    # with the sign left up: two open exceptions for one cause would become insertable.
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name = ?",
        ("ix_exceptions_one_open_per_cause",),
    ).fetchone()
    if row is not None:
        sql = " ".join((row[0] or "").split()).upper().replace(", ", ",")
        if "UNIQUE" not in sql:
            problems.append(
                "ix_exceptions_one_open_per_cause is not UNIQUE: two open exceptions for one "
                "(source_ref, type) cause would be insertable, and the dedup this build chose (machine "
                "§19) would be a convention, not a constraint."
            )
        if "WHERESTATE!='RESOLVED'" not in sql.replace(" ", ""):
            problems.append(
                "ix_exceptions_one_open_per_cause has lost its `WHERE state != 'RESOLVED'` clause: the "
                "partial index is what allows many resolved exceptions per cause in history while "
                "permitting at most one open (entity §17)."
            )
        for column in ("TENANT", "SOURCE_REF", "TYPE"):
            if column not in sql:
                problems.append(
                    f"ix_exceptions_one_open_per_cause does not cover {column!r}: a dropped tenant is "
                    f"cross-tenant coalescing of one cause; a dropped member changes what counts as "
                    f"'the same cause'."
                )

    # ### THE CHECKS AND THE VOCABULARIES, READ OUT OF THE exceptions DDL. A CHECK the migration
    # intended but a live database does not carry is the invariant switched off.
    ddl_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='exceptions'").fetchone()
    ddl = " ".join((ddl_row[0] if ddl_row else "" or "").split()).upper()
    compact = ddl.replace(", ", ",")

    expected_states = ("STATE IN (" + ",".join(f"'{s}'" for s in EXCEPTION_STATES) + ")").upper()
    if expected_states not in compact:
        problems.append(
            "exceptions does not enumerate the five canonical states inline on the state column "
            "(registry §4, M9): without it a sixth state — a CANCELLED, an EXPIRED or a bare "
            "SUPERSEDED — would be writable, and entity §26 and machine §14 say none exists."
        )
    expected_sev = ("SEVERITY IN (" + ",".join(f"'{s}'" for s in EXCEPTION_SEVERITIES) + ")").upper()
    if expected_sev not in compact:
        problems.append(
            "exceptions does not enumerate the severity vocabulary inline on the severity column "
            "(entity §12, registry §4): SEV0 | SEV1 | SEV2 and no fourth."
        )
    expected_kinds = ("SOURCE_KIND IN (" + ",".join(f"'{k}'" for k in SOURCE_KINDS) + ")").upper()
    if expected_kinds not in compact:
        problems.append(
            "exceptions does not enumerate the closed source-kind vocabulary inline on the source_kind "
            "column (### M9-AQ-3, entity §9): the source reference is polymorphic and its kind is what "
            "tells a reader which table (if any) it points at."
        )
    for clause, why in (
        ("STATE <> 'RESOLVED' OR DECISION_REF IS NOT NULL",
         "a RESOLVED exception must carry a decision_ref (entity §16, GR-14, F-30): an exception "
         "closed without a decision is not closed, it is FORGOTTEN — this is the structural half of "
         "the RESOLVES requirement `exception.py` completes with M1's resolver"),
        ("STATE <> 'RESOLVED' OR DECISION_HUMAN_ID IS NOT NULL",
         "a RESOLVED exception must name the ACTIVE human behind its decision_ref (K-1, entity §35): "
         "'an authenticated human' is decoration while decision_human_id is a free-text column"),
        ("FREEZES_ENTITY = 0 OR (ENTITY_REF IS NOT NULL AND FROZEN_FIELD IS NOT NULL)",
         "a freezing exception names the entity and the field it froze (### M9-AQ-5, entity §38): a "
         "freeze with no field to block is a freeze that blocks nothing"),
    ):
        if clause not in compact:
            problems.append(f"exceptions does not CHECK: {clause.lower()} — {why}.")

    # ### owner_id IS NOT NULL FROM CREATION (entity §37). An ownerless Exception is structurally
    # impossible: the column is NOT NULL and FK-backed. Read the NOT NULL back rather than trust it.
    owner_notnull = any(
        r[1] == "owner_id" and r[3] == 1
        for r in conn.execute("PRAGMA table_info(exceptions)").fetchall())
    if not owner_notnull:
        problems.append(
            "exceptions.owner_id is not NOT NULL: an ownerless Exception would be insertable, and "
            "entity §37 names it a structurally impossible state — the owner is assigned at creation "
            "(I1, AC-SAFE-028)."
        )

    for referent in P6XC_EXCEPTION_REFERENTS:
        if referent not in _referents(conn, "exceptions"):
            problems.append(
                f"exceptions declares no foreign key into {referent!r}: the owner, the acknowledging "
                f"human and the decision-human are recorded ACTIVE humans of THIS tenant (M1), and each "
                f"FK-backed source kind is a row of THIS tenant — 'a named X' is decoration while the "
                f"column is free text (entity §18, task §3.9, ### M9-AQ-3)."
            )
    return problems
