"""Phase 6 — M12, the Rule: one `rules` row per registered, versioned, deterministic decision
procedure WITH AN ID, and the one machine in Neyma that turns an owner's sentence from a string in a
prompt into a compiled, enforceable rule — or an honest refusal.

WHAT THIS TABLE IS, IN FREIGHT TERMS

    An owner types "never bill without a POD." The old system replied "📋 Noted the procedure for
    raise_invoice" and installed a sentence in an LLM prompt — the owner believed they installed a
    control; they installed a suggestion. Later an invoice goes out on a load with no proof of
    delivery, and the honest answer to "I told you not to do that" is "you told a text box."

    ### A HUMAN INSTRUCTION EITHER COMPILES INTO AN ENFORCEABLE RULE, OR IS HONESTLY REFUSED.
    ### THERE IS NO THIRD OUTCOME.
    ### A MODEL MAY PROPOSE TEXT; IT NEVER COMPILES, CONFIRMS, ACTIVATES, EVALUATES OR RESOLVES.
    ### A RULE MAY NEVER BRANCH ON A GUESS.
    ### TWO CONFLICTING RULES FAIL CLOSED; NEYMA NEVER PICKS A WINNER.

    M12 makes the difference real: a rule is a ROW — a `compiled_predicate` that references only
    MODELLED, NON-INFERRED fields (M-49, GR-8), a `rule_version` monotonic per tenant, generated
    `test_vectors` the owner sees before confirming, an `activated_by` that must be an authenticated
    human recorded in `tenant_humans`, and a lifecycle in which every version is retained forever
    because effects were judged under it.

THIS MIGRATION CARRIES NO GATE VOCABULARY, AND MINTS NOTHING

    Unlike M11's `policies`, the `rules` table has NO `gate_decision` column: a GATE_PRECONDITION
    rule's gate lives INSIDE its `compiled_predicate` (JSON), evaluated at checkpoint step 6. So this
    migration is NOT a carrier of the ADR-010 gate vocabulary (`eval/phase0/gate_scan`), and neither
    is `rule.py`, which validates any referenced gate through the checkpoint kernel's `GateDecision`
    constructor rather than naming a member literal. ### `checkpoint.py` STAYS THE SOLE MINTER of a
    gate decision, the production `GateRegistry` population stays EMPTY, and M12 constructs no
    `GateEntry` and no `GateRegistry` (R-07, AC-CKPT-6-missing, U8.1/P8).

THE EIGHT CANONICAL STATES, AND NO NINTH (registry §4 / M12, entity §12, target spec §12.12, machine §7)

    PROPOSED · COMPILED · CONFIRMED · ACTIVE · REJECTED · SUPERSEDED · REVOKED · EXPIRED. Terminal:
    REJECTED, SUPERSEDED, REVOKED, EXPIRED. Non-terminal (all recoverable): PROPOSED, COMPILED,
    CONFIRMED, ACTIVE. Initial: PROPOSED. ### THE BRIEF'S FIVE INFORMAL NAMES ARE ALREADY MAPPED INTO
    THAT SET: *parsed* = PROPOSED; *invalid* = REJECTED; *conflict-detected* = a raised M7 Conflict
    (the rule stays COMPILED, blocked); *awaiting-confirmation* = COMPILED; *suspended* = REVOKED.
    ### THERE IS NO PARSED, INVALID, CONFLICT_DETECTED, AWAITING_CONFIRMATION, SUSPENDED, PENDING,
    ENABLED, DISABLED, CANCELLED, FAILED or ARCHIVED — and NO DRAFT or APPROVED: those two are M11
    POLICY's states, and a rule machine written by copying the policy machine acquires them silently.

    Four kinds, and no fifth (entity §10): IDENTITY, CONFLICT_RESOLUTION, GATE_PRECONDITION, CONSTRAINT.

WHY THE DATABASE STATES THE INVARIANTS, NOT A COMMENT (entity §16)

    ### `CHECK (state <> 'ACTIVE' OR activated_by IS NOT NULL)` (entity §16, verbatim): an ACTIVE rule
    with no activator is structurally impossible, and `activated_by` is FK-backed into `tenant_humans`,
    so a model-activated or automation-activated rule is not insertable. ### `CHECK (expires_at IS NULL
    OR change_direction = 'narrow')` makes "only a NARROWING rule may carry an expiry" a fact the
    database enforces — a narrowing rule's expiry BROADENS authority, so a broadening rule that carried
    an expiry would be automatic broadening with a delay, refused at INSERT rather than by review. ### A
    `BEFORE DELETE` trigger refuses the delete outright (entity §28/§29, [C-9], retention permanent): a
    wrong rule is SUPERSEDED by a new version, never edited in place, because effects were judged under
    the old one and it still has to explain them under ITS OWN rule version.

    ### THE "references only modelled, non-inferred fields" CONSTRAINT IS DELIBERATELY *NOT* A ROW-LOCAL
    SQL `CHECK` (entity §16 states it and immediately says "(enforced at compile)"). It is a property of
    the compilation pipeline over data the row does not carry — the field provenance lives in the
    proposed candidate, not on the compiled row — so a SQL `CHECK` that pretended to express it would
    enforce nothing while reading as though it enforced everything. It is enforced at compile in
    `rule.py::compile_predicate_field`, and named HERE where the DDL would have said it, exactly as
    `01-work-item.md` ("enforced at the transition layer") and `15-rule.md` ("enforced at compile")
    name their own enforcement layer.

WHY THE VERSION NAMESPACE IS THE TENANT, NEVER THE SCOPE (entity §17, ### M12-AQ-4b, [C-10])

    `UNIQUE (tenant, rule_version)` plus per-tenant monotonicity make a scope-local numbering
    structurally impossible: two scopes cannot each hold version 1. Entity §9's natural identifier
    `(tenant_id, scope, rule_version)` reads as per-scope versioning, but entity §17's constraint is
    tenant-local, and ### §17 IS THE CONSTRAINT AUTHORITY (### M12-AQ-4b) — the same tension M11
    resolved at ### M11-AQ-6. `rule_version` monotonic per tenant is ALSO where F12's ordering
    guarantee actually lives: the family file says STRICT while `events/registry.md` §8 lists F12 in
    neither the strict nor the tolerant set and `event_contracts_data.json` records `strict_order:
    false` on all eight (### M12-AQ-5). This migration builds the fail-closed, stricter side — a
    DATABASE monotonicity constraint — WITHOUT touching the registered contract.

WHICH SCOPES ADMIT EXACTLY ONE ACTIVE RULE (### M12-AQ-4 — an OPEN question, answered explicitly here)

    Entity §17: "`UNIQUE (tenant_id, scope, kind) WHERE state = 'ACTIVE'` where a scope admits one
    rule; otherwise multiple active rules may coexist (and conflicts are detected)." Canon does not say
    WHICH scopes admit one, and `V4`/`V5` are open. Both mistakes fail in opposite directions: impose
    the index on EVERY scope and a legitimate second rule is refused by a constraint canon never granted
    (and the "otherwise" branch — where conflict detection lives — becomes unreachable, silently
    resolving V4/V5 by construction); omit it and two rules that must not coexist do, with nothing
    noticing. ### SO THE ANSWER IS DECLARED IN ONE PLACE, MECHANICAL, AND A PROPER SUBSET: a `scope_form`
    column discriminates the vocabulary, `P6RU_SINGLE_ACTIVE_SCOPES` names the forms that admit exactly
    ONE ACTIVE rule per `(tenant, scope, kind)`, and the partial index's WHERE predicate NAMES those
    forms. The single-admitting set is `('subject_type',)` — an IDENTITY rule IS the one canonical
    binding procedure for a subject type, and two would be genuinely incoherent (which one binds?). It
    is a PROPER SUBSET of `P6RU_SCOPE_FORMS`, so the "otherwise" branch (an `action_class`
    GATE_PRECONDITION/CONSTRAINT stacks with others; conflict detection covers a genuine clash) stays
    reachable. This is an answer to an OPEN validation question, RECORDED as such — not a finding.

WHAT THE FOREIGN KEYS POINT AT (entity §18)

    `authored_by` -> `tenant_humans` (the Policy Owner or a delegate who authored the candidate);
    `activated_by` -> `tenant_humans` (the authenticated human who activated — NEVER a model, NEVER
    automation); `superseded_by` -> `rules` (M12, the new version that replaced this one); `conflict_id`
    -> `conflicts` (M7, the RULE_VS_RULE conflict a COMPILED rule is blocked on). Every lookup is
    tenant-first, so every cross-tenant reference fails closed [C-1].

WHAT IS DELIBERATELY *NOT* HERE (the seams this unit does not own)

    ### NO brake lifecycle (M13 is not built), no autonomy-graduation column or table (nothing
    graduates), no `PolicyOverridden` mechanism (### M12-AQ-7 / P6-D71, BLOCKED_AUTHORITY — that event
    is not registered and is minted by nobody but a founder/architect). ### NO `rule_conflicts` table
    and no second conflict vocabulary (### M12-AQ / ADR-007 §5 — `RULE_VS_RULE` has been in M7's closed
    `CONFLICT_KINDS` and `conflicts.rule_id` a column since P6-CP-7; M12 CALLS M7's landed raise entry
    point through a named seam and mints nothing). ### NO mirror column or FK on `exceptions` (### M12-AQ-6
    / P6-D73: RU-8's expiry and the override-rate escalation are raised through M9's LANDED
    `raise_exception` entry point with `source_kind="rule"`, which M9 already accepts without a table —
    named and left UNWIRED, and M9 is not edited at all).

FRESH == MIGRATED, SHIPS DARK

    `create_canonical_schema` builds this table directly; a migrated database reaches the SAME shape
    through `create_phase6_rules_schema`. Built LAST of the P6 units (its FKs reach tenant_humans/M1 and
    conflicts/M7). Nothing routes production traffic through M12; `rule.py` is the only non-test module
    that reads it, and only `scripts/probe_phase6_rule.py` imports the machine. NO rule editor, admin
    screen, importer, oversight queue, dashboard or notifier ships with M12.
"""

from __future__ import annotations

import sqlite3

MIGRATION_ID = "phase6_rules"
P6RU_SCHEMA_VERSION = "phase6-rules-1"

# Tenant-owned. A rule is the standing procedure of ONE brokerage; the same scope and kind ACTIVE in
# two tenants are two isolated rules [C-1]. Every query and every uniqueness constraint is tenant-first.
P6RU_TENANT_TABLES: tuple[str, ...] = ("rules",)

# Nothing tenant-exempt. Stated rather than omitted, so a future addition must defend its exemption.
P6RU_EXEMPT_TABLES: tuple[str, ...] = ()

# `state-machines/registry.md` §4, M12 / entity §12 / target spec §12.12 / machine §7 — the EIGHT, in
# the registry's own order. There is no ninth, and no DRAFT/APPROVED (M11 POLICY's states), no
# PARSED/INVALID/CONFLICT_DETECTED/AWAITING_CONFIRMATION/SUSPENDED (the brief's informal names, mapped),
# and no PENDING/ENABLED/DISABLED/CANCELLED/FAILED/ARCHIVED.
RULE_STATES: tuple[str, ...] = (
    "PROPOSED", "COMPILED", "CONFIRMED", "ACTIVE", "REJECTED", "SUPERSEDED", "REVOKED", "EXPIRED",
)

# machine §8 — the four terminal states.
TERMINAL_RULE_STATES: tuple[str, ...] = ("REJECTED", "SUPERSEDED", "REVOKED", "EXPIRED")

# machine §9/§10 — the four non-terminal states, all recoverable. Initial is PROPOSED.
NON_TERMINAL_RULE_STATES: tuple[str, ...] = ("PROPOSED", "COMPILED", "CONFIRMED", "ACTIVE")

# entity §10 — the four kinds a rule may be, and no fifth. IDENTITY and CONFLICT_RESOLUTION are
# consulted by the Identity Service and Reconciliation; GATE_PRECONDITION and CONSTRAINT are evaluated
# by the checkpoint at step 6.
RULE_KINDS: tuple[str, ...] = (
    "IDENTITY", "CONFLICT_RESOLUTION", "GATE_PRECONDITION", "CONSTRAINT",
)

# ### THE SCOPE-FORM VOCABULARY (### M12-AQ-4). `scope` names WHICH thing a rule governs; `scope_form`
# names of what SORT, so the "where a scope admits one rule" clause of entity §17 can be mechanical
# rather than a sentence. The forms span the four kinds: a GATE_PRECONDITION/CONSTRAINT scopes an
# action_class or a field, an IDENTITY rule a subject_type, a CONFLICT_RESOLUTION rule a field, and a
# rule may be scoped to a counterparty or a workflow.
P6RU_SCOPE_FORMS: tuple[str, ...] = (
    "action_class", "counterparty", "subject_type", "field", "workflow",
)

# ### THE FORMS THAT ADMIT EXACTLY ONE ACTIVE RULE PER (tenant, scope, kind) (### M12-AQ-4 — ANSWER TO
# AN OPEN QUESTION). An IDENTITY rule IS the one canonical binding procedure for a subject type; two
# would be genuinely incoherent. It is a PROPER SUBSET of P6RU_SCOPE_FORMS, so the "otherwise" branch
# (an action_class GATE_PRECONDITION/CONSTRAINT stacks with others; a genuine clash is a M7 Conflict)
# stays reachable and conflict detection actually covers it. Empty would resolve nothing; the whole set
# would make the "otherwise" branch unreachable and silently resolve V4/V5 by construction.
P6RU_SINGLE_ACTIVE_SCOPES: tuple[str, ...] = ("subject_type",)

# The direction a rule moves authority. A CONSTRAINT/GATE_PRECONDITION that adds a restriction is
# 'narrow'; a rule that would loosen is 'broaden'. ### PERSISTED AND CHECKABLE: only a `narrow` rule may
# carry an `expires_at`, because its expiry BROADENS and a broadening rule that carried an expiry is
# automatic broadening with a delay. There is no 'initial' — a rule's direction is intrinsic to what it
# does, not relative to a prior version.
CHANGE_DIRECTIONS: tuple[str, ...] = ("narrow", "broaden")

# RU-7's revocation direction (the RuleRevoked `direction` enum). Narrowing may be automation;
# broadening requires the Policy Owner (ER-12). Persisted so a rebuild reproduces which it was.
REVOKE_DIRECTIONS: tuple[str, ...] = ("narrow", "broaden")

_STATES_SQL = ",".join(f"'{s}'" for s in RULE_STATES)
_KINDS_SQL = ",".join(f"'{k}'" for k in RULE_KINDS)
_SCOPE_FORMS_SQL = ",".join(f"'{f}'" for f in P6RU_SCOPE_FORMS)
_SINGLE_ACTIVE_SQL = ",".join(f"'{f}'" for f in P6RU_SINGLE_ACTIVE_SCOPES)
_CHANGE_DIR_SQL = ",".join(f"'{d}'" for d in CHANGE_DIRECTIONS)
_REVOKE_DIR_SQL = ",".join(f"'{d}'" for d in REVOKE_DIRECTIONS)

# The exact abort texts, worded WITHOUT apostrophes: they are interpolated into single-quoted SQL
# literals inside RAISE(ABORT, ...). Matched by `rule.py` when it classifies an IntegrityError.
VERSION_ABORT = (
    "rules.version advances by exactly one per state transition [GR-3, C-10]: a state change that "
    "does not advance it silently overwrites another transition. OCC on the rule row version is the "
    "concurrency guard, and a version that stands still is a lost update"
)
IDENTITY_ABORT = (
    "the identity of a rule version is immutable [entity 15 sec 15/16/19/24, C-8]: the tenant, the id, "
    "the rule_version, the scope and scope_form it governs, the kind, the source_instruction, the human "
    "who authored it, the direction it moves authority and when it was created are what make it THIS "
    "rule version. A wrong rule is SUPERSEDED by a new version, never edited in place, because effects "
    "were judged under it and it must still explain them under its own rule_version [entity 15 sec 23/24/29]"
)
COMPILED_FROZEN_ABORT = (
    "the compiled_predicate and test_vectors are written once by RU-2 out of PROPOSED and are frozen "
    "thereafter [entity 15 sec 21/22, ADR-010 sec 6]: a rule the owner confirmed and activated may not "
    "have its predicate rewritten under it. Compilation is deterministic and happens once; a new "
    "predicate is a new rule version, never an edit in place"
)
DELETE_ABORT = (
    "a rule version is never deleted [entity 15 sec 28/29, C-9]: retention is permanent, every version "
    "is kept because effects were judged under it, and supersession does not erase. A row that quietly "
    "stops being visible is a decision nobody can defend. No sweep, no reaper, no scan, no TTL"
)


P6RU_TARGET_SCHEMA: dict[str, str] = {
    # THE RULE (`entities/15-rule.md`, spec §12.12, machine M12, ADR-010 §6).
    #
    # Every column on its OWN line and every FOREIGN KEY / CHECK / PRIMARY KEY on its OWN physical
    # line, and every multi-condition CHECK on ONE physical line: `schema._canonical_columns` parses
    # this DDL line by line, reads only the first token of a line as a column, and skips a line that
    # STARTS with PRIMARY KEY / FOREIGN KEY / UNIQUE / CHECK. A wrapped clause would read as a phantom
    # column.
    "rules": """
        CREATE TABLE rules (
            tenant TEXT NOT NULL,
            rule_id TEXT NOT NULL,
            -- ### THE VERSION NAMESPACE IS THE TENANT (entity §17, ### M12-AQ-4b, C-10). Monotonic per
            -- tenant, UNIQUE (tenant, rule_version) below — so two scopes cannot each hold version 1,
            -- and this is where F12's ordering guarantee actually lives (### M12-AQ-5).
            rule_version INTEGER NOT NULL,
            -- ### WHICH thing this rule governs. It names the scope; it does NOT open a second numbering.
            scope TEXT NOT NULL,
            -- ### OF WHAT SORT the scope is (### M12-AQ-4). Drives the one-active partial index: only the
            -- forms in P6RU_SINGLE_ACTIVE_SCOPES admit exactly one ACTIVE rule per (tenant, scope, kind).
            scope_form TEXT NOT NULL CHECK (scope_form IN (%(scope_forms)s)),
            -- ### THE FOUR CANONICAL KINDS, ENUMERATED INLINE (entity §10). No fifth.
            kind TEXT NOT NULL CHECK (kind IN (%(kinds)s)),
            -- ### THE DETERMINISTIC, TYPED COMPILED PREDICATE over modelled, non-inferred fields (M-49,
            -- GR-8), as canonical JSON. NOT NULL — a PROPOSED rule carries the uncompiled candidate here;
            -- RU-2 rewrites it with the validated compiled form and RU-2f rejects. The
            -- "references only modelled, non-inferred fields" property is enforced at COMPILE (rule.py),
            -- not by a row-local CHECK (the field provenance is not on this row) — entity §16.
            compiled_predicate TEXT NOT NULL,
            -- ### THE GENERATED TEST VECTORS — "here are three loads this rule WOULD have blocked last
            -- month" (entity §10, ADR-010 §6.2). NOT NULL; '[]' until RU-2 generates them, and RU-4
            -- confirmation is REFUSED until they are non-empty: a rule whose consequences the owner
            -- cannot see is a rule they have not really approved.
            test_vectors TEXT NOT NULL,
            -- ### THE EIGHT CANONICAL STATES, ENUMERATED INLINE (registry §4, M12). No ninth state, and
            -- no DRAFT/APPROVED (those are M11 POLICY's).
            state TEXT NOT NULL CHECK (state IN (%(states)s)),
            version INTEGER NOT NULL,
            -- ### THE ORIGINAL HUMAN SENTENCE, RETAINED VERBATIM (entity §10). A rejected instruction is
            -- retained here as non-authoritative organizational memory.
            source_instruction TEXT NOT NULL,
            -- ### THE HUMAN WHO AUTHORED THE CANDIDATE (entity §18): the Policy Owner or a delegate. A
            -- model may propose the TEXT, but the accountable author is a recorded human. NOT NULL and
            -- FK-backed below.
            authored_by TEXT NOT NULL,
            -- ### THE AUTHENTICATED HUMAN WHO ACTIVATED (entity §16/§18, RU-5). NULL until ACTIVE; the
            -- CHECK below makes ACTIVE require it, and the FK makes it a recorded human — NEVER a model,
            -- NEVER automation, NEVER a retry handler, NEVER a timer.
            activated_by TEXT,
            -- ### ONLY A NARROWING RULE MAY CARRY AN EXPIRY (entity §26, ADR-010 §4.1/§6.2). The CHECK
            -- below ties it to change_direction = 'narrow'. Its expiry BROADENS and so needs a human (RU-8).
            expires_at TEXT,
            -- ### THE DIRECTION THIS RULE MOVES AUTHORITY, PERSISTED and CHECKABLE. Drives the expiry
            -- CHECK and RU-7/RU-8. Intrinsic to the rule; there is no 'initial'.
            change_direction TEXT NOT NULL CHECK (change_direction IN (%(change_dirs)s)),
            -- The new version that superseded this one (RU-6); NULL until then. FK into rules below.
            superseded_by TEXT,
            -- RU-7's revocation reason and its direction (narrow may be automation; broaden needs owner).
            revoked_reason TEXT,
            revoked_direction TEXT CHECK (revoked_direction IS NULL OR revoked_direction IN (%(revoke_dirs)s)),
            -- ### THE M7 RULE_VS_RULE CONFLICT a COMPILED rule is blocked on (RU-3, entity §11/§18). NULL
            -- unless it conflicts with an ACTIVE rule. FK into conflicts (M7) — M12 raises through M7's
            -- landed entry point and mints no conflict of its own.
            conflict_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            PRIMARY KEY (tenant, rule_id),
            -- The author and activator are recorded humans of THIS tenant. Each FK on its OWN line so
            -- the readiness parser skips it as a non-column.
            FOREIGN KEY (tenant, authored_by) REFERENCES tenant_humans (tenant, human_id),
            FOREIGN KEY (tenant, activated_by) REFERENCES tenant_humans (tenant, human_id),
            FOREIGN KEY (tenant, superseded_by) REFERENCES rules (tenant, rule_id),
            FOREIGN KEY (tenant, conflict_id) REFERENCES conflicts (tenant, conflict_id),
            CHECK (version >= 1),
            CHECK (rule_version >= 1),
            -- ### CHECK: state = ACTIVE requires a non-null activated_by (entity §16, verbatim). An
            -- ACTIVE rule with no activator is structurally impossible; the FK makes the activator a
            -- human, so a model-activated or automation-activated rule is not insertable.
            CHECK (state <> 'ACTIVE' OR activated_by IS NOT NULL),
            -- ### CHECK: only a NARROWING rule may carry an expiry (entity §26, ADR-010 §4.1). A
            -- broadening rule carrying an expires_at is automatic broadening with a delay — the clock
            -- may take authority away, never give it.
            CHECK (expires_at IS NULL OR change_direction = 'narrow'),
            -- A SUPERSEDED rule names its successor; a REVOKED one carries a reason and a direction.
            CHECK (state <> 'SUPERSEDED' OR superseded_by IS NOT NULL),
            CHECK (state <> 'REVOKED' OR (revoked_reason IS NOT NULL AND revoked_direction IS NOT NULL)),
            CHECK (trim(rule_id) <> ''),
            CHECK (trim(scope) <> ''),
            CHECK (trim(compiled_predicate) <> ''),
            CHECK (trim(source_instruction) <> ''),
            CHECK (trim(authored_by) <> ''),
            CHECK (trim(state) <> '')
        )""" % {
        "states": _STATES_SQL, "kinds": _KINDS_SQL, "scope_forms": _SCOPE_FORMS_SQL,
        "change_dirs": _CHANGE_DIR_SQL, "revoke_dirs": _REVOKE_DIR_SQL,
    },
}


P6RU_INDEXES: dict[str, str] = {
    # ### ONE ACTIVE RULE PER (tenant, scope, kind) — BUT ONLY WHERE THE SCOPE ADMITS ONE (### M12-AQ-4,
    # entity §17). Tenant-first, partial on `state = 'ACTIVE'` AND the scope_form being single-admitting.
    # Drop the UNIQUE and two active rules fit one single-admitting scope; drop the scope_form predicate
    # and a legitimate second rule on a multi-admitting scope is refused by a constraint canon never
    # granted, making the "otherwise" branch (conflict detection) unreachable; drop the tenant and one
    # brokerage's rule couples another's.
    "ix_rules_one_active_per_scope":
        "CREATE UNIQUE INDEX ix_rules_one_active_per_scope "
        "ON rules (tenant, scope, kind) "
        f"WHERE state = 'ACTIVE' AND scope_form IN ({_SINGLE_ACTIVE_SQL})",
    # ### THE VERSION NAMESPACE IS THE TENANT (entity §17, ### M12-AQ-4b, ### M12-AQ-5). UNIQUE across ALL
    # states — every version is retained — so two scopes cannot each hold version 1 and a version is
    # never reused. This is where F12's monotonicity guarantee lives (the fail-closed side, without
    # touching the registered order-tolerant contract).
    "ix_rules_tenant_version":
        "CREATE UNIQUE INDEX ix_rules_tenant_version ON rules (tenant, rule_version)",
    # The scope lookup: the rule history for a scope, by version, tenant-first.
    "ix_rules_scope":
        "CREATE INDEX ix_rules_scope ON rules (tenant, scope, kind, rule_version)",
    # The ACTIVE-rule read the checkpoint's step 6 would consult, by state, tenant-first.
    "ix_rules_state":
        "CREATE INDEX ix_rules_state ON rules (tenant, state, scope)",
}

# Nothing from an earlier phase is replaced. Declared so a future replacement has somewhere to go.
P6RU_REPLACED_INDEXES: tuple[str, ...] = ()


P6RU_TRIGGERS: dict[str, str] = {
    # ### OCC ON THE RULE ROW (GR-3, C-10, machine §17). Every M12 transition changes state, so version
    # must advance by exactly one on every write; a state change that leaves version standing is two
    # transitions claiming one version.
    "trg_rules_version_advances_on_state_change": f"""
        CREATE TRIGGER trg_rules_version_advances_on_state_change
        BEFORE UPDATE ON rules
        WHEN NEW.state <> OLD.state AND NEW.version <> OLD.version + 1
        BEGIN SELECT RAISE(ABORT, '{VERSION_ABORT}'); END""",
    # ### THE IDENTITY OF A RULE VERSION IS IMMUTABLE (entity §15/§16/§19/§24). The tenant, id,
    # rule_version, scope, scope_form, kind, source_instruction, author, change_direction and created_at
    # may not be edited — a wrong rule is a NEW version, never an edit in place. The state, activator,
    # compiled_predicate, test_vectors, expiry, supersession, revocation and conflict columns are
    # DELIBERATELY ABSENT because the transitions write them.
    "trg_rules_identity_immutable": f"""
        CREATE TRIGGER trg_rules_identity_immutable
        BEFORE UPDATE OF tenant, rule_id, rule_version, scope, scope_form, kind, source_instruction,
                         authored_by, change_direction, created_at
        ON rules
        BEGIN SELECT RAISE(ABORT, '{IDENTITY_ABORT}'); END""",
    # ### THE COMPILED PREDICATE AND TEST VECTORS ARE WRITTEN ONCE, OUT OF PROPOSED, AND FROZEN
    # THEREAFTER (entity §21/§22, ADR-010 §6). RU-2/RU-2f write them while OLD.state = 'PROPOSED'; any
    # later edit is refused, so a rule the owner confirmed and activated cannot have its predicate
    # rewritten under it. Compilation is deterministic and happens once; a new predicate is a new version.
    "trg_rules_compiled_predicate_frozen_after_proposed": f"""
        CREATE TRIGGER trg_rules_compiled_predicate_frozen_after_proposed
        BEFORE UPDATE OF compiled_predicate, test_vectors
        ON rules
        WHEN OLD.state <> 'PROPOSED'
        BEGIN SELECT RAISE(ABORT, '{COMPILED_FROZEN_ABORT}'); END""",
    # ### NO DELETION, EVER (entity §28/§29, C-9). Retention is permanent; a rule version is never
    # outlived, swept, reaped or deleted — the effects it judged still exist and it must explain them.
    "trg_rules_no_delete": f"""
        CREATE TRIGGER trg_rules_no_delete
        BEFORE DELETE ON rules
        BEGIN SELECT RAISE(ABORT, '{DELETE_ABORT}'); END""",
}

# The referents the readiness oracle checks by name. Derived from the DDL by the generic FK loop too;
# naming them here is the unit stating what they are FOR.
P6RU_RULE_REFERENTS: tuple[str, ...] = (
    "tenant_humans", "rules", "conflicts",
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


def create_phase6_rules_schema(conn: sqlite3.Connection, *, now: str) -> list[str]:
    """Create whatever M12 structure is missing. Idempotent; returns what it did.

    Callable on a fresh canonical database and on an already-migrated one. Either way the resulting
    structure is byte-identical, because there is only one text. Built LAST of the P6 units because
    `rules` holds FKs into tenant_humans (M1) and conflicts (M7), which is why `schema.py` orders it
    after them.
    """
    performed: list[str] = []
    present = _tables(conn)
    for name in (*P6RU_TENANT_TABLES, *P6RU_EXEMPT_TABLES):
        if name not in present:
            conn.execute(P6RU_TARGET_SCHEMA[name])
            performed.append(f"create-table:{name}")
    existing = _indexes(conn)
    live_tables = _tables(conn)
    for name, ddl in P6RU_INDEXES.items():
        table = ddl.split(" ON ")[1].split(" ")[0].split("(")[0].strip()
        if name not in existing and table in live_tables:
            conn.execute(ddl)
            performed.append(f"create-index:{name}")
    for stale in P6RU_REPLACED_INDEXES:
        if stale in _indexes(conn):
            conn.execute(f"DROP INDEX {stale}")
            performed.append(f"drop-index:{stale}")
    existing_triggers = _triggers(conn)
    for name, ddl in P6RU_TRIGGERS.items():
        if name not in existing_triggers:
            conn.execute(ddl)
            performed.append(f"create-trigger:{name}")
    # NO VERSION STAMP HERE — marker-last, like every phase. A stamp on a half-migrated database is how
    # a missing trigger goes unnoticed.
    conn.commit()
    return performed


def stamp_phase6_rules_version(conn: sqlite3.Connection, *, now: str) -> None:
    """Record the M12 marker — callable ONLY once readiness holds. Marker-last, like every phase."""
    problems = phase6_rules_readiness_problems(conn)
    if problems:
        raise RuntimeError(
            f"refusing to stamp {P6RU_SCHEMA_VERSION} on a database that is NOT ready: "
            + "; ".join(problems)
        )
    if "schema_migrations" in _tables(conn):
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration, step, applied_at, detail) "
            "VALUES (?,?,?,?)",
            (MIGRATION_ID, f"version:{P6RU_SCHEMA_VERSION}", now,
             "the Rule: one rules row per registered versioned deterministic decision procedure, "
             "tenant-first, eight states, four kinds, a compiled predicate over modelled non-inferred "
             "fields (enforced at compile), generated test vectors before confirmation, an "
             "authenticated-human activator FK-backed into tenant_humans (ACTIVE requires it), the "
             "version namespace is the tenant (UNIQUE tenant+version), one active rule per (tenant, "
             "scope, kind) only where the scope_form admits one, only a narrowing rule carries an "
             "expiry, identity and compiled predicate immutable and history never deleted; readiness "
             "proven"),
        )
        conn.commit()


def phase6_rules_readiness_problems(conn: sqlite3.Connection) -> list[str]:
    """Every reason this database cannot carry Rules safely. Empty == ready.

    Structural, like the P2/P3/P5/M1..M11 oracles it extends. The eight-state CHECK, the four-kind
    CHECK, the ACTIVE-requires-activator CHECK, the narrowing-only-expiry CHECK, the scope-form CHECK,
    the two partial/full unique indexes, the identity/compiled-frozen/no-delete triggers and the
    foreign keys are verified PRESENT because a `rules` table without them is an ordinary table with an
    aspirational comment: an ACTIVE rule could have no activator, a broadening rule could auto-expire
    into wider authority, two active rules could govern one single-admitting scope, and a rule could be
    deleted.
    """
    problems: list[str] = []
    present = _tables(conn)
    for table in (*P6RU_TENANT_TABLES, *P6RU_EXEMPT_TABLES):
        if table not in present:
            problems.append(
                f"required Phase-6 table {table!r} is missing: run the {MIGRATION_ID} migration"
            )
    if not all(t in present for t in P6RU_TENANT_TABLES):
        return problems

    live_triggers = _triggers(conn)
    missing_triggers = sorted(t for t in P6RU_TRIGGERS if t not in live_triggers)
    if missing_triggers:
        problems.append(
            f"Rule invariant triggers missing: {missing_triggers}. Without them a rule version could "
            f"be deleted (a decision nobody can defend), a state transition could stand the version "
            f"still (a lost update), or the identity/compiled predicate could be edited in place "
            f"[entity §15/§21/§24/§28, GR-3, C-9]."
        )
    live_indexes = _indexes(conn)
    for name in P6RU_INDEXES:
        if name not in live_indexes:
            problems.append(f"required Phase-6 index {name!r} is missing")
    for stale in P6RU_REPLACED_INDEXES:
        if stale in live_indexes:
            problems.append(f"replaced index {stale!r} is still present")

    # ### THE ONE-ACTIVE-PER-SINGLE-ADMITTING-SCOPE PARTIAL UNIQUE INDEX, READ OUT OF THE LIVE DATABASE
    # (entity §17, ### M12-AQ-4). An index of this name that is not UNIQUE, or that lost its `WHERE
    # state = 'ACTIVE'` clause, or that lost its scope_form predicate, is the one-active rule switched
    # off — either two active rules for one single-admitting scope become insertable, or a legitimate
    # second rule on a multi-admitting scope is wrongly refused.
    problems.extend(_partial_unique_index_problems(
        conn, name="ix_rules_one_active_per_scope",
        must_have=("TENANT", "SCOPE", "KIND"),
        where_fragments=("WHERESTATE='ACTIVE'", "SCOPE_FORMIN("),
        what="two active rules for one single-admitting scope",
        why="the one-active rule (entity §17, ### M12-AQ-4) would be a convention, not a constraint"))

    # ### THE (tenant, rule_version) FULL UNIQUE INDEX — the version namespace is the tenant (### M12-AQ-4b).
    tv = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name = ?",
        ("ix_rules_tenant_version",)).fetchone()
    if tv is not None:
        tvsql = " ".join((tv[0] or "").split()).upper().replace(", ", ",")
        if "UNIQUE" not in tvsql:
            problems.append(
                "ix_rules_tenant_version is not UNIQUE: a rule_version could be REUSED within a "
                "tenant, and scope-local numbering (two scopes each holding version 1) would become "
                "possible — the version namespace is the TENANT (### M12-AQ-4b)."
            )
        for column in ("TENANT", "RULE_VERSION"):
            if column not in tvsql:
                problems.append(
                    f"ix_rules_tenant_version does not cover {column!r}: a dropped tenant would couple "
                    f"two brokerages' version namespaces; a dropped rule_version is not a version index."
                )

    # ### THE CHECKS AND THE VOCABULARY, READ OUT OF THE rules DDL. A CHECK the migration intended but a
    # live database does not carry is the invariant switched off.
    ddl_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='rules'").fetchone()
    ddl = " ".join((ddl_row[0] if ddl_row else "" or "").split()).upper()
    compact = ddl.replace(", ", ",")

    expected_states = ("STATE IN (" + ",".join(f"'{s}'" for s in RULE_STATES) + ")").upper()
    if expected_states not in compact:
        problems.append(
            "rules does not enumerate the eight canonical states inline on the state column (registry "
            "§4, M12): without it a ninth state — a DRAFT or APPROVED borrowed from M11, a PARSED, a "
            "SUSPENDED, an INVALID — would be writable, and the machine's opening paragraph and §14 say "
            "none exists."
        )
    expected_kinds = ("KIND IN (" + ",".join(f"'{k}'" for k in RULE_KINDS) + ")").upper()
    if expected_kinds not in compact:
        problems.append(
            "rules does not enumerate the four canonical kinds inline on the kind column (entity §10): "
            "without it an invented fifth kind would be writable."
        )
    expected_forms = ("SCOPE_FORM IN (" + ",".join(f"'{f}'" for f in P6RU_SCOPE_FORMS) + ")").upper()
    if expected_forms not in compact:
        problems.append(
            "rules does not enumerate the scope-form vocabulary inline on the scope_form column (### "
            "M12-AQ-4): without it the one-active partial index cannot mechanically name which forms "
            "admit exactly one active rule."
        )
    for clause, why in (
        ("STATE <> 'ACTIVE' OR ACTIVATED_BY IS NOT NULL",
         "an ACTIVE rule requires a non-null activated_by (entity §16, verbatim): an ACTIVE rule with "
         "no activator is a structurally impossible state, and the activator is FK-backed into "
         "tenant_humans so a model or automation cannot be it"),
        ("EXPIRES_AT IS NULL OR CHANGE_DIRECTION = 'NARROW'",
         "only a narrowing rule may carry an expiry (entity §26, ADR-010 §4.1): a broadening rule that "
         "carries an expires_at is automatic broadening with a delay — the clock may take authority "
         "away, never give it"),
    ):
        if clause.upper().replace(", ", ",") not in compact:
            problems.append(f"rules does not CHECK: {clause.lower()} — {why}.")

    # ### THE NOT NULL COLUMNS (entity §10/§16). Read the NOT NULL back rather than trust it.
    info = {r[1]: r for r in conn.execute("PRAGMA table_info(rules)").fetchall()}
    for col, why in (
        ("rule_version", "a rule with no version cannot be bound into a decision (entity §19)"),
        ("scope", "a rule governs a scope; a scopeless rule governs nothing (entity §10)"),
        ("scope_form", "the scope form is persisted so the one-active partial index can name which "
         "forms admit one active rule (### M12-AQ-4)"),
        ("kind", "a rule has one of the four canonical kinds (entity §10)"),
        ("compiled_predicate", "a rule with no compiled predicate is not a decision procedure "
         "(entity §10/§16); a PROPOSED rule carries its uncompiled candidate here"),
        ("state", "a rule with no state is not a rule (entity §10)"),
        ("source_instruction", "the original human sentence is retained verbatim (entity §10/§30)"),
        ("authored_by", "a rule authored by nobody would be insertable; authorship names an "
         "accountable human (entity §18)"),
        ("change_direction", "the change direction is persisted and checkable so the expiry rule can "
         "enforce narrowing-only at the database, not in the machine's memory"),
    ):
        r = info.get(col)
        if r is None or r[3] != 1:
            problems.append(f"rules.{col} is not NOT NULL: {why}.")

    for referent in P6RU_RULE_REFERENTS:
        if referent not in _referents(conn, "rules"):
            problems.append(
                f"rules declares no foreign key into {referent!r}: the author and activator are "
                f"recorded humans of THIS tenant (M1), a supersession names a rule of THIS tenant, and "
                f"a blocking conflict is a conflict of THIS tenant (M7) — 'a named X' is decoration "
                f"while the column is free text (entity §18, [C-1])."
            )
    return problems


def _partial_unique_index_problems(
    conn: sqlite3.Connection, *, name: str, must_have: tuple[str, ...],
    where_fragments: tuple[str, ...], what: str, why: str,
) -> list[str]:
    """Read a partial unique index out of the live database and confirm it is UNIQUE, carries every
    required column, and still has every WHERE fragment. An index verified by NAME proves nothing — a
    same-named index that lost its UNIQUE or its WHERE is the invariant switched off with the sign up."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name = ?", (name,)).fetchone()
    if row is None:
        return [f"required index {name!r} is missing"]
    sql = " ".join((row[0] or "").split()).upper().replace(", ", ",")
    problems: list[str] = []
    if "UNIQUE" not in sql:
        problems.append(f"{name} is not UNIQUE: {what} would be insertable, and {why}.")
    for fragment in where_fragments:
        if fragment.upper() not in sql.replace(" ", ""):
            problems.append(
                f"{name} has lost its partial predicate fragment {fragment!r}: without it {what} would "
                f"be insertable, or a legitimate rule on a multi-admitting scope would be wrongly "
                f"refused — the partial predicate is the canonical one ({why})."
            )
    for column in must_have:
        if column not in sql:
            problems.append(
                f"{name} does not cover {column!r}: a dropped member changes what counts as a "
                f"duplicate, and a dropped tenant couples two brokerages ({why})."
            )
    return problems
