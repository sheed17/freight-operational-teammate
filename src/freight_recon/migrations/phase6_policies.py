"""Phase 6 — M11, the Policy: one `policies` row per tenant posture, and the one machine in Neyma that
turns "what may Neyma do alone, for whom, up to what caps" from a sentence in a prompt into a VALUE the
owner can see, version and revoke.

WHAT THIS TABLE IS, IN FREIGHT TERMS

    An owner types "never bill without a POD." The old system replied "noted the procedure" and installed
    a sentence in an LLM prompt — the owner believed they installed a control; they installed a
    suggestion. Later an invoice goes out on a load with no proof of delivery and the honest answer to
    "I told you not to do that" is "you told a text box."

    ### A POLICY IS A VALUE THE OWNER CAN SEE, NOT A SENTENCE IN A PROMPT.
    ### A TENANT POLICY MAY ONLY EVER NARROW THE PRODUCT CEILING.
    ### AUTOMATION MAY ONLY EVER MOVE AUTHORITY IN THE SAFE DIRECTION.
    ### A GATE EXPRESSIBLE AS AN ABSENCE IS NOT A GATE.
    ### A POLICY MAY NEVER BRANCH ON A GUESS.

    M11 makes the difference real: a policy is a ROW — a `gate_decision` that cannot be null and is one of
    the four canonical members (ADR-010 §3.1), a `predicate` that cannot read a `MODEL_INFERRED` guess, a
    `policy_version` bound into every witness and grant, an `activated_by` that must be an authenticated
    human recorded in `tenant_humans`, and a lifecycle in which every version is retained forever because
    effects were judged under it.

THIS FILE CARRIES THE ADR-010 GATE VOCABULARY IN EXECUTABLE DDL — BY CANON, AND IT MINTS NOTHING

    A policy's whole content is a `gate_decision`, so the `gate_decision` CHECK enumerates the four
    canonical members (ADR-010 §3.1) as SQL literals. That makes this migration a CARRIER of the gate
    vocabulary, exactly as `pipeline_instance.py` carries it, which is why `policy.py` and this module join
    `eval/phase0/gate_scan.GATE_RUNTIME_MODULES` and cite ADR-010. ### IT CONSTRUCTS NO `GateEntry` AND NO
    gate registry, and it registers NO production action class: `checkpoint.py` stays the SOLE minter of a
    gate decision, and the production registration population stays EMPTY (R-07, AC-CKPT-6-missing, U8.1).

THE SEVEN CANONICAL STATES, AND NO EIGHTH (registry §4 / M11, entity §12, target spec §12.11, machine §7)

    DRAFT · PROPOSED · APPROVED · ACTIVE · SUPERSEDED · REVOKED · EXPIRED. Terminal: SUPERSEDED, REVOKED,
    EXPIRED. Non-terminal (all recoverable): DRAFT, PROPOSED, APPROVED, ACTIVE. Initial: DRAFT. ### THERE
    IS NO `NARROWED` (that is an ACTIVE policy with a tighter posture — a new version), NO `SUSPENDED`
    (that is REVOKED — revocation narrows and is immediate), NO `INVALID` (that is a DRAFT/PROPOSED that
    failed validation and never activated), and no `PENDING`, `ENABLED`, `DISABLED`, `CANCELLED`,
    `REJECTED`, `COMPILED`, `CONFIRMED`, `FAILED` or `ARCHIVED` — the last three are M12 Rule's states.

WHY THE DATABASE STATES THE INVARIANTS, NOT A COMMENT (entity §16)

    ### `CHECK (state <> 'ACTIVE' OR activated_by IS NOT NULL)` (entity §16, verbatim): an ACTIVE policy
    with no activator is structurally impossible, and `activated_by` is FK-backed into `tenant_humans`, so
    a model-activated or automation-activated policy is not insertable. ### `CHECK (gate_decision NOT
    NULL)` and the four-member enumeration (F-20): a gate expressible as an absence is not a gate. ### The
    direction of a policy's change is a PERSISTED, CHECKABLE column (`change_direction`), and `CHECK
    (expires_at IS NULL OR change_direction = 'narrow')` makes "only a NARROWING policy may carry an
    expiry" a fact the database enforces — a broadening policy carrying an expiry (automatic broadening
    with a delay) is refused at INSERT, not by review. ### A `BEFORE DELETE` trigger refuses the delete
    outright (entity §28/§29, [C-9], retention permanent): a wrong policy is SUPERSEDED by a new version,
    never edited in place, because effects were judged under the old one and it still has to explain them.

    ### THE CEILING INVARIANT IS DELIBERATELY *NOT* A ROW-LOCAL SQL `CHECK` (### M11-AQ-5). "A tenant
    policy's gate_decision may only NARROW the product ceiling" compares against Product Policy, which
    spec §20.2 enforces in CONFIG — it is not a column of this row, so no row-local constraint can
    reference it. It is enforced at the PO-2 transition guard and machine M11 §15's illegal transition,
    over a DECLARED TOTAL ORDER on the four canonical gate members (`policy.py`), stated the same way
    `01-work-item.md` ("enforced at the transition layer") and `15-rule.md` ("enforced at compile") name
    their own enforcement layer. Broadening is MECHANICALLY IMPOSSIBLE, not merely refused in review.

WHY THE VERSION NAMESPACE IS THE TENANT, NEVER THE SCOPE (entity §9/§17/§19, ### M11-AQ-6, [C-10])

    `UNIQUE (tenant, policy_version)` plus per-tenant monotonicity make a scope-local numbering
    structurally impossible: two scopes cannot each hold version 1. `scope` appears in the natural key
    because it names WHICH posture the row carries, not because it opens a second numbering. ### THE
    CONSEQUENCE IS DELIBERATE: a change in ANY scope advances the TENANT's `policy_version`, so
    `PolicyVersionChanged` voids in-flight approvals/witnesses/unclaimed grants in EVERY scope — a
    checkpoint pins and re-validates exactly ONE `policy_version` per decision, so over-voiding is the
    fail-closed direction and under-voiding is not available.

WHY AT MOST ONE ACTIVE POLICY PER SCOPE (entity §17, machine §17)

    `UNIQUE (tenant_id, scope) WHERE state = 'ACTIVE'`, tenant-first. One active policy per scope; the
    SAME scope may be ACTIVE in two brokerages without collision, and two tenants may both hold version 1.
    Plus OCC on the row `version`: a transition writes `WHERE version = :expected`; zero rows is a lost
    update that raises.

WHY EXACTLY ONE ACTIVE POLICY OWNER PER TENANT (### M11-AQ-7 / P6-D72 — CLOSED AT M11, TIER 1)

    Entity point 7 requires "exactly one named Policy Owner per tenant" (I1), point 18 requires
    `activated_by` to BE the Policy Owner or an authorised delegate, and PO-6's "broadening requires the
    Policy Owner" resolves through the same record. M1's landed `tenant_humans` carries
    `authority_role IN ('POLICY_OWNER','AUTHORIZED_HUMAN')` but NO constraint limiting a tenant to one
    ACTIVE `POLICY_OWNER` — two were insertable. This migration adds that constraint to the EXISTING
    tenant-authority record, ON `tenant_humans`, as a tenant-first PARTIAL UNIQUE INDEX. ### NO SECOND
    USER/ADMIN/SUPERUSER/AUTHORITY SYSTEM IS INVENTED (ADR-017's control plane is P11); the invariant
    sits on the one record of human authority the system already has. It is tenant-first, so it does NOT
    couple tenants: brokerage A and brokerage B may each name their own single Policy Owner.

WHAT THE FOREIGN KEYS POINT AT (entity §18)

    `authored_by` -> `tenant_humans` (the Policy Owner or a delegate who authored the draft);
    `activated_by` -> `tenant_humans` (the authenticated human who activated — NEVER a model, NEVER
    automation); `approval_id` -> `approvals` (M4, the governed-change approval PO-3 binds);
    `superseded_by` -> `policies` (M11, the new version that replaced this one). Every lookup is
    tenant-first, so every cross-tenant reference fails closed [C-1].

WHAT IS DELIBERATELY *NOT* HERE (the seams this unit does not own)

    ### NO `rules` table (M12 is not built), no brake lifecycle (M13 is not built), no autonomy-graduation
    column or table (V11: nothing graduates), no `PolicyOverridden` mechanism (### M11-AQ-4 / P6-D71,
    BLOCKED_AUTHORITY — that event is not registered and is minted by nobody but a founder/architect). No
    `compensation` mirror column or FK on `exceptions` (### M11-AQ-8 / P6-D73: PO-7 raises its Exception
    through M9's LANDED `raise_exception` entry point with `source_kind="policy"`, which M9 already accepts
    without a table — the seam is named and left UNWIRED, and M9 is not edited at all).

FRESH == MIGRATED, SHIPS DARK

    `create_canonical_schema` builds this table directly; a migrated database reaches the SAME shape
    through `create_phase6_policies_schema`. Built LAST of the P6 units (its FKs reach tenant_humans/M1
    and approvals/M4). Nothing routes production traffic through M11; `policy.py` is the only non-test
    module that reads it, and only `scripts/probe_phase6_policy.py` imports the machine. NO policy editor,
    admin screen, oversight queue, dashboard or notifier ships with M11.
"""

from __future__ import annotations

import sqlite3

MIGRATION_ID = "phase6_policies"
P6PO_SCHEMA_VERSION = "phase6-policies-1"

# Tenant-owned. A policy is the posture of ONE brokerage; the same scope in two tenants are two isolated
# policies [C-1]. Every query and every uniqueness constraint is tenant-first.
P6PO_TENANT_TABLES: tuple[str, ...] = ("policies",)

# Nothing tenant-exempt. Stated rather than omitted, so a future addition must defend its exemption.
P6PO_EXEMPT_TABLES: tuple[str, ...] = ()

# `state-machines/registry.md` §4, M11 / entity §12 / target spec §12.11 / machine §7 — the SEVEN, in the
# registry's own order. There is no eighth: no NARROWED, SUSPENDED, INVALID (the machine's opening
# paragraph refuses those three by name), no PENDING/ENABLED/DISABLED/CANCELLED/REJECTED, and no
# COMPILED/CONFIRMED/FAILED/ARCHIVED (M12 Rule's states).
POLICY_STATES: tuple[str, ...] = (
    "DRAFT", "PROPOSED", "APPROVED", "ACTIVE", "SUPERSEDED", "REVOKED", "EXPIRED",
)

# machine §8 — the three terminal states.
TERMINAL_POLICY_STATES: tuple[str, ...] = ("SUPERSEDED", "REVOKED", "EXPIRED")

# machine §9/§10 — the four non-terminal states, all recoverable. Initial is DRAFT.
NON_TERMINAL_POLICY_STATES: tuple[str, ...] = ("DRAFT", "PROPOSED", "APPROVED", "ACTIVE")

# The states that could only have been reached THROUGH the governed change (PROPOSED -> APPROVED at PO-3),
# so `approval_id` and `diff_fingerprint` are present: there is no admin path to any of them.
GOVERNED_STATES: tuple[str, ...] = ("APPROVED", "ACTIVE", "SUPERSEDED", "REVOKED", "EXPIRED")

# ### THE FOUR CANONICAL GATE DECISIONS (ADR-010 §3.1, amendment A3). Enumerated here as SQL literals so
# `gate_decision` is a database CHECK, not a comment. This is what makes this migration a CARRIER of the
# gate vocabulary (`eval/phase0/gate_scan.GATE_RUNTIME_MODULES`); it MINTS none — the enum lives in
# `checkpoint.py::GateDecision`, and `policy.py` imports it rather than redeclaring it.
GATE_DECISIONS: tuple[str, ...] = (
    "HUMAN_APPROVAL_REQUIRED",
    "AUTONOMOUS_WITHIN_CAPS",
    "PERMANENT_HUMAN_ASSERTION_REQUIRED",
    "FORBIDDEN",
)

# entity §10 — the scope KINDS a policy may name (action_class, counterparty, value-cap + money_direction,
# workflow, integration). `scope` names WHICH posture the row carries; `scope_kind` names of what sort.
SCOPE_KINDS: tuple[str, ...] = (
    "action_class", "counterparty", "value_cap", "workflow", "integration",
)

# The direction of the change a policy represents, relative to the previously ACTIVE policy for its scope
# (the FIRST policy in a scope is `initial`). ### PERSISTED AND CHECKABLE (### the expiry rule): only a
# `narrow` policy may carry an `expires_at`, because its expiry BROADENS and a broadening policy that
# carries an expiry is automatic broadening with a delay.
CHANGE_DIRECTIONS: tuple[str, ...] = ("initial", "narrow", "broaden")

# PO-6's revocation direction (the PolicyRevoked `direction` enum). Narrowing may be automation; broadening
# requires the Policy Owner (ER-12). Persisted so a rebuild reproduces which it was.
REVOKE_DIRECTIONS: tuple[str, ...] = ("narrow", "broaden")

_STATES_SQL = ",".join(f"'{s}'" for s in POLICY_STATES)
_GOVERNED_SQL = ",".join(f"'{s}'" for s in GOVERNED_STATES)
_GATES_SQL = ",".join(f"'{g}'" for g in GATE_DECISIONS)
_SCOPE_KINDS_SQL = ",".join(f"'{k}'" for k in SCOPE_KINDS)
_CHANGE_DIR_SQL = ",".join(f"'{d}'" for d in CHANGE_DIRECTIONS)
_REVOKE_DIR_SQL = ",".join(f"'{d}'" for d in REVOKE_DIRECTIONS)

# The exact abort texts, worded WITHOUT apostrophes: they are interpolated into single-quoted SQL literals
# inside RAISE(ABORT, ...). Matched by `policy.py` when it classifies an IntegrityError.
VERSION_ABORT = (
    "policies.version advances by exactly one per state transition [GR-3, C-10]: a state change that "
    "does not advance it silently overwrites another transition. OCC on the policy row version is the "
    "concurrency guard, and a version that stands still is a lost update"
)
IDENTITY_ABORT = (
    "the identity of a policy version is immutable [entity 14 sec 15/16/24, C-8]: the tenant, the id, the "
    "policy_version, the scope it governs, the gate decision, the caps, the predicate, the human who "
    "authored it and when it was created are what make it THIS policy version. A wrong policy is "
    "SUPERSEDED by a new version, never edited in place, because effects were judged under it and it must "
    "still explain them [entity 14 sec 23/24/29]"
)
DELETE_ABORT = (
    "a policy version is never deleted [entity 14 sec 28/29, C-9]: retention is permanent, every version "
    "is kept for historical explanation, and supersession does not erase. A row that quietly stops being "
    "visible is a decision nobody can defend — the effects it judged still exist. No sweep, no reaper, no "
    "scan, no TTL"
)

# ### THE POLICY OWNER SINGULARITY ABORT (### M11-AQ-7 / P6-D72). The partial unique index below refuses a
# second ACTIVE POLICY_OWNER at the database; this text is not interpolated into a trigger, it documents
# the intent beside the index.

P6PO_TARGET_SCHEMA: dict[str, str] = {
    # THE POLICY (`entities/14-policy.md`, spec §12.11, machine M11, ADR-010).
    #
    # Every column on its OWN line and every FOREIGN KEY / CHECK / PRIMARY KEY on its OWN physical line,
    # and every multi-condition CHECK on ONE physical line: `schema._canonical_columns` parses this DDL
    # line by line, reads only the first token of a line as a column, and skips a line that STARTS with
    # PRIMARY KEY / FOREIGN KEY / UNIQUE / CHECK. A wrapped clause would read as a phantom column.
    "policies": """
        CREATE TABLE policies (
            tenant TEXT NOT NULL,
            policy_id TEXT NOT NULL,
            -- ### THE VERSION NAMESPACE IS THE TENANT (entity §9/§17/§19, ### M11-AQ-6, C-10). Monotonic
            -- per tenant, UNIQUE (tenant, policy_version) below — so two scopes cannot each hold version 1.
            policy_version INTEGER NOT NULL,
            -- ### WHICH posture this row carries. It names the scope; it does NOT open a second numbering.
            scope TEXT NOT NULL,
            scope_kind TEXT NOT NULL CHECK (scope_kind IN (%(scope_kinds)s)),
            -- ### THE POSTURE — THE NEVER-NULL GATE DECISION (F-20, ADR-010 §3.1). One of the FOUR
            -- canonical members, enumerated inline. A null or invented gate is an unasserted gate. This
            -- CHECK is the DB half; the machine imports checkpoint.GateDecision and mints nothing.
            gate_decision TEXT NOT NULL CHECK (gate_decision IN (%(gates)s)),
            -- The caps (value/frequency/time) as canonical JSON. NOT NULL; an empty posture is '{}'.
            caps_json TEXT NOT NULL,
            -- ### THE DETERMINISTIC, TYPED PREDICATE over the §5.2 inputs, as canonical JSON. It may
            -- reference only MODELLED, NON-INFERRED fields (M-49, GR-8); `confidence` is structurally not
            -- an input. The compile check lives in `policy.py`; this column stores the compiled form.
            predicate_json TEXT NOT NULL,
            -- ### THE SEVEN CANONICAL STATES, ENUMERATED INLINE (registry §4, M11). No eighth state.
            state TEXT NOT NULL CHECK (state IN (%(states)s)),
            version INTEGER NOT NULL,
            effective_from TEXT NOT NULL,
            -- ### THE HUMAN WHO AUTHORED THE DRAFT (entity §18/§21): the Policy Owner or a delegate. A
            -- model may propose TEXT, never author an active policy. NOT NULL and FK-backed below.
            authored_by TEXT NOT NULL,
            -- ### THE AUTHENTICATED HUMAN WHO ACTIVATED (entity §16/§18, PO-4). NULL until ACTIVE; the
            -- CHECK below makes ACTIVE require it, and the FK makes it a recorded human — NEVER a model,
            -- NEVER automation, NEVER a retry handler.
            activated_by TEXT,
            -- ### ONLY A NARROWING POLICY MAY CARRY AN EXPIRY (entity §26, ADR-010 §4.1). The CHECK below
            -- ties it to change_direction = 'narrow'. Its expiry BROADENS and so needs a human (PO-7).
            expires_at TEXT,
            -- ### THE DIRECTION OF THIS CHANGE relative to the prior ACTIVE policy for the scope, PERSISTED
            -- and CHECKABLE. 'initial' for the first in a scope. Drives the expiry CHECK and PO-6/PO-7.
            change_direction TEXT NOT NULL CHECK (change_direction IN (%(change_dirs)s)),
            -- The new version that superseded this one (PO-5); NULL until then. FK into policies below.
            superseded_by TEXT,
            -- PO-6's revocation reason and its direction (narrow may be automation; broaden needs owner).
            revoked_reason TEXT,
            revoked_direction TEXT CHECK (revoked_direction IS NULL OR revoked_direction IN (%(revoke_dirs)s)),
            -- ### THE GOVERNED-CHANGE EVIDENCE (PO-3, entity §31). `approval_id` is the M4 approval bound
            -- to the policy DIFF as material facts; `diff_fingerprint` is that diff's material_facts
            -- fingerprint. Both are the "no admin path" proof: a policy that reached APPROVED came through
            -- an M2 pipeline, never a config file, a migration or a superuser command.
            approval_id TEXT,
            diff_fingerprint TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            PRIMARY KEY (tenant, policy_id),
            -- The author and activator are recorded humans of THIS tenant. Each FK on its OWN line so the
            -- readiness parser skips it as a non-column.
            FOREIGN KEY (tenant, authored_by) REFERENCES tenant_humans (tenant, human_id),
            FOREIGN KEY (tenant, activated_by) REFERENCES tenant_humans (tenant, human_id),
            FOREIGN KEY (tenant, approval_id) REFERENCES approvals (tenant, approval_id),
            FOREIGN KEY (tenant, superseded_by) REFERENCES policies (tenant, policy_id),
            CHECK (version >= 1),
            CHECK (policy_version >= 1),
            -- ### CHECK: state = ACTIVE requires a non-null activated_by (entity §16, verbatim). An ACTIVE
            -- policy with no activator is structurally impossible; the FK makes the activator a human.
            CHECK (state <> 'ACTIVE' OR activated_by IS NOT NULL),
            -- ### CHECK: only a NARROWING policy may carry an expiry (entity §26, ADR-010 §4.1). A
            -- broadening or initial policy carrying an expires_at is automatic broadening with a delay.
            CHECK (expires_at IS NULL OR change_direction = 'narrow'),
            -- A SUPERSEDED policy names its successor; a REVOKED one carries a reason and a direction.
            CHECK (state <> 'SUPERSEDED' OR superseded_by IS NOT NULL),
            CHECK (state <> 'REVOKED' OR (revoked_reason IS NOT NULL AND revoked_direction IS NOT NULL)),
            -- ### CHECK: THERE IS NO ADMIN PATH. Any state reached through the governed change carries the
            -- M4 approval and the diff fingerprint (PO-3). A policy cannot be APPROVED/ACTIVE/etc without
            -- them, so a config file / migration / superuser command cannot manufacture an active policy.
            CHECK (state NOT IN (%(governed)s) OR (approval_id IS NOT NULL AND diff_fingerprint IS NOT NULL)),
            CHECK (trim(policy_id) <> ''),
            CHECK (trim(scope) <> ''),
            CHECK (trim(caps_json) <> ''),
            CHECK (trim(predicate_json) <> ''),
            CHECK (trim(authored_by) <> ''),
            CHECK (trim(state) <> '')
        )""" % {
        "states": _STATES_SQL, "gates": _GATES_SQL, "scope_kinds": _SCOPE_KINDS_SQL,
        "change_dirs": _CHANGE_DIR_SQL, "revoke_dirs": _REVOKE_DIR_SQL, "governed": _GOVERNED_SQL,
    },
}


P6PO_INDEXES: dict[str, str] = {
    # ### ONE ACTIVE POLICY PER SCOPE — THE CANONICAL PARTIAL UNIQUE INDEX (entity §17, machine §17).
    # Tenant-first, partial on `state = 'ACTIVE'`. Drop the UNIQUE, or the WHERE, or the tenant, and two
    # active policies fit one scope, or one tenant's posture couples another's.
    "ix_policies_one_active_per_scope":
        "CREATE UNIQUE INDEX ix_policies_one_active_per_scope "
        "ON policies (tenant, scope) WHERE state = 'ACTIVE'",
    # ### THE VERSION NAMESPACE IS THE TENANT (entity §17, ### M11-AQ-6). UNIQUE across ALL states — every
    # version is retained — so two scopes cannot each hold version 1 and a version is never reused.
    "ix_policies_tenant_version":
        "CREATE UNIQUE INDEX ix_policies_tenant_version ON policies (tenant, policy_version)",
    # The scope lookup: the policy history for a scope, by version, tenant-first.
    "ix_policies_scope":
        "CREATE INDEX ix_policies_scope ON policies (tenant, scope, policy_version)",
    # The owner's one-screen view (R17): every action class's gate decision, by state. M11 owes the row
    # and the tenant-first index; it does NOT build the screen.
    "ix_policies_state":
        "CREATE INDEX ix_policies_state ON policies (tenant, state, scope)",
    # ### EXACTLY ONE ACTIVE POLICY OWNER PER TENANT (### M11-AQ-7 / P6-D72), ON THE M1-LANDED
    # tenant_humans RECORD. Tenant-first partial unique index: at most one ACTIVE row whose authority_role
    # is POLICY_OWNER, per tenant. It does NOT couple tenants — brokerage A and B each name their own.
    # This is the ONE constraint M11 adds to an M1..M10 table, and it invents no second authority system.
    "ix_tenant_humans_one_active_policy_owner":
        "CREATE UNIQUE INDEX ix_tenant_humans_one_active_policy_owner "
        "ON tenant_humans (tenant) WHERE authority_role = 'POLICY_OWNER' AND state = 'ACTIVE'",
}

# Nothing from an earlier phase is replaced. Declared so a future replacement has somewhere to go.
P6PO_REPLACED_INDEXES: tuple[str, ...] = ()


P6PO_TRIGGERS: dict[str, str] = {
    # ### OCC ON THE POLICY ROW (GR-3, C-10, machine §17). Every M11 transition changes state, so version
    # must advance by exactly one on every write; a state change that leaves version standing is two
    # transitions claiming one version.
    "trg_policies_version_advances_on_state_change": f"""
        CREATE TRIGGER trg_policies_version_advances_on_state_change
        BEFORE UPDATE ON policies
        WHEN NEW.state <> OLD.state AND NEW.version <> OLD.version + 1
        BEGIN SELECT RAISE(ABORT, '{VERSION_ABORT}'); END""",
    # ### THE IDENTITY OF A POLICY VERSION IS IMMUTABLE (entity §15/§16/§24). The tenant, id,
    # policy_version, scope, scope_kind, gate_decision, caps, predicate, author, created_at and
    # change_direction may not be edited — a wrong policy is a NEW version, never an edit in place, because
    # the old version still explains the effects judged under it. The state, activator, effective_from
    # (set at PO-4 activation), expiry, supersession, revocation and approval columns are DELIBERATELY
    # ABSENT because the transitions write them.
    "trg_policies_identity_immutable": f"""
        CREATE TRIGGER trg_policies_identity_immutable
        BEFORE UPDATE OF tenant, policy_id, policy_version, scope, scope_kind, gate_decision,
                         caps_json, predicate_json, authored_by, created_at, change_direction
        ON policies
        BEGIN SELECT RAISE(ABORT, '{IDENTITY_ABORT}'); END""",
    # ### NO DELETION, EVER (entity §28/§29, C-9). Retention is permanent; a policy version is never
    # outlived, swept, reaped or deleted — the effects it judged still exist and it must explain them.
    "trg_policies_no_delete": f"""
        CREATE TRIGGER trg_policies_no_delete
        BEFORE DELETE ON policies
        BEGIN SELECT RAISE(ABORT, '{DELETE_ABORT}'); END""",
}

# The referents the readiness oracle checks by name. Derived from the DDL by the generic FK loop too;
# naming them here is the unit stating what they are FOR.
P6PO_POLICY_REFERENTS: tuple[str, ...] = (
    "tenant_humans", "approvals", "policies",
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


def create_phase6_policies_schema(conn: sqlite3.Connection, *, now: str) -> list[str]:
    """Create whatever M11 structure is missing. Idempotent; returns what it did.

    Callable on a fresh canonical database and on an already-migrated one. Either way the resulting
    structure is byte-identical, because there is only one text. Built LAST of the P6 units because
    `policies` holds FKs into tenant_humans (M1) and approvals (M4), which is why `schema.py` orders it
    after them; and because the Policy Owner singularity index (### M11-AQ-7) is created ON tenant_humans,
    which M1 must have built first.
    """
    performed: list[str] = []
    present = _tables(conn)
    for name in (*P6PO_TENANT_TABLES, *P6PO_EXEMPT_TABLES):
        if name not in present:
            conn.execute(P6PO_TARGET_SCHEMA[name])
            performed.append(f"create-table:{name}")
    existing = _indexes(conn)
    live_tables = _tables(conn)
    for name, ddl in P6PO_INDEXES.items():
        # The tenant_humans singularity index targets an M1 table; it can only be built once that table
        # exists. On both entry paths it does by now, but guard so a bare M11 migration never half-builds.
        table = ddl.split(" ON ")[1].split(" ")[0].split("(")[0].strip()
        if name not in existing and table in live_tables:
            conn.execute(ddl)
            performed.append(f"create-index:{name}")
    for stale in P6PO_REPLACED_INDEXES:
        if stale in _indexes(conn):
            conn.execute(f"DROP INDEX {stale}")
            performed.append(f"drop-index:{stale}")
    existing_triggers = _triggers(conn)
    for name, ddl in P6PO_TRIGGERS.items():
        if name not in existing_triggers:
            conn.execute(ddl)
            performed.append(f"create-trigger:{name}")
    # NO VERSION STAMP HERE — marker-last, like every phase. A stamp on a half-migrated database is how a
    # missing trigger goes unnoticed.
    conn.commit()
    return performed


def stamp_phase6_policies_version(conn: sqlite3.Connection, *, now: str) -> None:
    """Record the M11 marker — callable ONLY once readiness holds. Marker-last, like every phase."""
    problems = phase6_policies_readiness_problems(conn)
    if problems:
        raise RuntimeError(
            f"refusing to stamp {P6PO_SCHEMA_VERSION} on a database that is NOT ready: "
            + "; ".join(problems)
        )
    if "schema_migrations" in _tables(conn):
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration, step, applied_at, detail) "
            "VALUES (?,?,?,?)",
            (MIGRATION_ID, f"version:{P6PO_SCHEMA_VERSION}", now,
             "the Policy: one policies row per tenant posture, tenant-first, seven states, a never-null "
             "gate decision (four canonical members), an authenticated-human activator FK-backed into "
             "tenant_humans (ACTIVE requires it), a deterministic predicate, the version namespace is the "
             "tenant (one active per scope, UNIQUE tenant+version), only a narrowing policy carries an "
             "expiry, no admin path (governed states carry the M4 approval + diff fingerprint), identity "
             "and history immutable and never deleted, and exactly one ACTIVE POLICY_OWNER per tenant on "
             "tenant_humans (P6-D72); readiness proven"),
        )
        conn.commit()


def phase6_policies_readiness_problems(conn: sqlite3.Connection) -> list[str]:
    """Every reason this database cannot carry Policies safely. Empty == ready.

    Structural, like the P2/P3/P5/M1..M10 oracles it extends. The seven-state CHECK, the four-member gate
    CHECK, the ACTIVE-requires-activator CHECK, the narrowing-only-expiry CHECK, the no-admin-path CHECK,
    the two partial/full unique indexes, the Policy Owner singularity index, the identity/no-delete
    triggers and the foreign keys are verified PRESENT because a `policies` table without them is an
    ordinary table with an aspirational comment: an ACTIVE policy could have no activator, a null or
    invented gate could be written, a broadening policy could auto-expire into wider authority, two active
    policies could govern one scope, two ACTIVE Policy Owners could exist, and a policy could be deleted.
    """
    problems: list[str] = []
    present = _tables(conn)
    for table in (*P6PO_TENANT_TABLES, *P6PO_EXEMPT_TABLES):
        if table not in present:
            problems.append(
                f"required Phase-6 table {table!r} is missing: run the {MIGRATION_ID} migration"
            )
    if not all(t in present for t in P6PO_TENANT_TABLES):
        return problems

    live_triggers = _triggers(conn)
    missing_triggers = sorted(t for t in P6PO_TRIGGERS if t not in live_triggers)
    if missing_triggers:
        problems.append(
            f"Policy invariant triggers missing: {missing_triggers}. Without them a policy version could "
            f"be deleted (a decision nobody can defend), a state transition could stand the version still "
            f"(a lost update), or the identity/gate/predicate could be edited in place "
            f"[entity §15/§24/§28, GR-3, C-9]."
        )
    live_indexes = _indexes(conn)
    for name in P6PO_INDEXES:
        if name not in live_indexes:
            problems.append(f"required Phase-6 index {name!r} is missing")
    for stale in P6PO_REPLACED_INDEXES:
        if stale in live_indexes:
            problems.append(f"replaced index {stale!r} is still present")

    # ### THE ONE-ACTIVE-PER-SCOPE PARTIAL UNIQUE INDEX, READ OUT OF THE LIVE DATABASE (entity §17). An
    # index of this name that is not UNIQUE, or that lost its `WHERE state = 'ACTIVE'` clause, is the
    # one-active rule switched off with the sign left up: two active policies for one scope become
    # insertable.
    problems.extend(_partial_unique_index_problems(
        conn, name="ix_policies_one_active_per_scope",
        must_have=("TENANT", "SCOPE"), where_fragment="WHERESTATE='ACTIVE'",
        what="two active policies for one scope",
        why="the one-active rule (entity §17) would be a convention, not a constraint"))

    # ### EXACTLY ONE ACTIVE POLICY OWNER PER TENANT (### M11-AQ-7 / P6-D72). The tenant-first partial
    # unique index on tenant_humans. Not UNIQUE, or missing its WHERE, and two ACTIVE Policy Owners become
    # insertable — "the Policy Owner activated this" becomes unprovable. Dropping the tenant would couple
    # brokerages. Verified by reading the live index SQL, not trusting its name.
    problems.extend(_partial_unique_index_problems(
        conn, name="ix_tenant_humans_one_active_policy_owner",
        must_have=("TENANT",),
        where_fragment="WHEREAUTHORITY_ROLE='POLICY_OWNER'ANDSTATE='ACTIVE'",
        what="two ACTIVE Policy Owners in one tenant",
        why="'the Policy Owner activated this' becomes unprovable (entity §7, I1, P6-D72)"))

    # ### THE (tenant, policy_version) FULL UNIQUE INDEX — the version namespace is the tenant (### M11-AQ-6).
    tv = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name = ?",
        ("ix_policies_tenant_version",)).fetchone()
    if tv is not None:
        tvsql = " ".join((tv[0] or "").split()).upper().replace(", ", ",")
        if "UNIQUE" not in tvsql:
            problems.append(
                "ix_policies_tenant_version is not UNIQUE: a policy_version could be REUSED within a "
                "tenant, and scope-local numbering (two scopes each holding version 1) would become "
                "possible — the version namespace is the TENANT (### M11-AQ-6)."
            )
        for column in ("TENANT", "POLICY_VERSION"):
            if column not in tvsql:
                problems.append(
                    f"ix_policies_tenant_version does not cover {column!r}: a dropped tenant would couple "
                    f"two brokerages' version namespaces; a dropped policy_version is not a version index."
                )

    # ### THE CHECKS AND THE VOCABULARY, READ OUT OF THE policies DDL. A CHECK the migration intended but a
    # live database does not carry is the invariant switched off.
    ddl_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='policies'").fetchone()
    ddl = " ".join((ddl_row[0] if ddl_row else "" or "").split()).upper()
    compact = ddl.replace(", ", ",")

    expected_states = ("STATE IN (" + ",".join(f"'{s}'" for s in POLICY_STATES) + ")").upper()
    if expected_states not in compact:
        problems.append(
            "policies does not enumerate the seven canonical states inline on the state column (registry "
            "§4, M11): without it an eighth state — a NARROWED, a SUSPENDED, an INVALID, a REJECTED or a "
            "COMPILED — would be writable, and the machine's opening paragraph and §14 say none exists."
        )
    expected_gates = ("GATE_DECISION IN (" + ",".join(f"'{g}'" for g in GATE_DECISIONS) + ")").upper()
    if expected_gates not in compact:
        problems.append(
            "policies does not enumerate the four canonical gate decisions inline on the gate_decision "
            "column (F-20, ADR-010 §3.1): without it a null, an invented or a fifth gate member would be "
            "writable, and a gate expressible as an absence is not a gate."
        )
    for clause, why in (
        ("STATE <> 'ACTIVE' OR ACTIVATED_BY IS NOT NULL",
         "an ACTIVE policy requires a non-null activated_by (entity §16, verbatim): an ACTIVE policy with "
         "no activator is a structurally impossible state, and the activator is FK-backed into "
         "tenant_humans so a model or automation cannot be it"),
        ("EXPIRES_AT IS NULL OR CHANGE_DIRECTION = 'NARROW'",
         "only a narrowing policy may carry an expiry (entity §26, ADR-010 §4.1): a broadening policy that "
         "carries an expires_at is automatic broadening with a delay — the clock may take authority away, "
         "never give it"),
        ("STATE NOT IN (" + ",".join(f"'{s}'" for s in GOVERNED_STATES) +
         ") OR (APPROVAL_ID IS NOT NULL AND DIFF_FINGERPRINT IS NOT NULL)",
         "a policy reached through the governed change carries the M4 approval and the diff fingerprint "
         "(PO-3): there is no admin path — a config file, a migration or a superuser command cannot "
         "manufacture an APPROVED or ACTIVE policy"),
    ):
        if clause.upper().replace(", ", ",") not in compact:
            problems.append(f"policies does not CHECK: {clause.lower()} — {why}.")

    # ### authored_by, gate_decision, state, policy_version, scope ARE NOT NULL (entity §10/§16). Read the
    # NOT NULL back rather than trust it.
    info = {r[1]: r for r in conn.execute("PRAGMA table_info(policies)").fetchall()}
    for col, why in (
        ("gate_decision",
         "a policy with no gate decision would be insertable, and F-20 names a gate expressible as an "
         "absence not a gate"),
        ("authored_by",
         "a policy authored by nobody would be insertable; authorship requires an authenticated human "
         "(entity §21, §35)"),
        ("state", "a policy with no state is not a policy (entity §10)"),
        ("policy_version", "a policy with no version cannot be bound into a witness or grant (entity §19)"),
        ("scope", "a policy governs a scope; a scopeless policy governs nothing (entity §10)"),
        ("change_direction",
         "the change direction is persisted and checkable so the expiry rule can enforce narrowing-only "
         "at the database, not in the machine's memory"),
    ):
        r = info.get(col)
        if r is None or r[3] != 1:
            problems.append(f"policies.{col} is not NOT NULL: {why}.")

    for referent in P6PO_POLICY_REFERENTS:
        if referent not in _referents(conn, "policies"):
            problems.append(
                f"policies declares no foreign key into {referent!r}: the author and activator are "
                f"recorded humans of THIS tenant (M1), the governed-change approval is an authorisation of "
                f"THIS tenant (M4), and a supersession names a policy of THIS tenant — 'a named X' is "
                f"decoration while the column is free text (entity §18, [C-1])."
            )
    return problems


def _partial_unique_index_problems(
    conn: sqlite3.Connection, *, name: str, must_have: tuple[str, ...], where_fragment: str,
    what: str, why: str,
) -> list[str]:
    """Read a partial unique index out of the live database and confirm it is UNIQUE, carries every
    required column, and still has its WHERE clause. An index verified by NAME proves nothing — a
    same-named index that lost its UNIQUE or its WHERE is the invariant switched off with the sign up."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name = ?", (name,)).fetchone()
    if row is None:
        return [f"required index {name!r} is missing"]
    sql = " ".join((row[0] or "").split()).upper().replace(", ", ",")
    problems: list[str] = []
    if "UNIQUE" not in sql:
        problems.append(f"{name} is not UNIQUE: {what} would be insertable, and {why}.")
    if where_fragment.upper() not in sql.replace(" ", ""):
        problems.append(
            f"{name} has lost its partial WHERE clause: without it {what} would be insertable — the "
            f"partial predicate is the canonical one, verbatim ({why})."
        )
    for column in must_have:
        if column not in sql:
            problems.append(
                f"{name} does not cover {column!r}: a dropped member changes what counts as a duplicate, "
                f"and a dropped tenant couples two brokerages ({why})."
            )
    return problems
