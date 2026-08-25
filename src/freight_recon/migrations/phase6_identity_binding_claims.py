"""Phase 6 — M6, the Identity Binding Claim: one `identity_binding_claims` row that makes identity a
first-class, evidenced, correctable, escalatable DECISION rather than a silent guess baked into a
projection.

WHAT THIS TABLE IS, IN FREIGHT TERMS

    A POD arrives and its load number matches exactly one open load, so the binding confirms. A
    second POD's reference matches two loads and nobody may pick one. A model READS "4471" off a
    scanned page — that is evidence to be matched, never a confirmation. A model merely FEELS an
    email is about load 4471 — that goes to a human at confidence 1.0 exactly as it would at 0.4.
    The owner assigns an unlinked message by hand; the linker then decides it knows better — and does
    not get to win. The owner discovers the POD was load 44718's all along, after an invoice already
    went out on it — the correction propagates and every completed effect that rested on the wrong
    binding is named for a Compensation.

    ### AN IDENTITY BINDING CLAIM IS A CLAIM THAT ARTIFACT X BELONGS TO ENTITY Y. IT IS EVIDENCED,
    CORRECTABLE AND ESCALATABLE. IT IS NOT AN OBSERVATION, NOT A FACT, NOT AUTHORITY, NOT A
    CARGO/FREIGHT `Claim`, AND NOT SOMETHING A MODEL MAY CONFIRM (entity §2/§4, ADR-007 §2/§3).

WHY `provenance_class` IS THE WHOLE UNIT

    ### SD-6 — `provenance_class` IS A DETERMINISTIC, IMMUTABLE FUNCTION OF `match_method`, computed
    ONCE at creation and never independently edited (entity §13, ADR-002 §2.3). The two fields cannot
    drift: `provenance_class` is stored for indexing/queries but is DERIVED, and every write MUST
    satisfy the mapping. Here that mapping is a database CHECK (`ck_ibc_provenance_is_derived`), and a
    trigger (`trg_ibc_provenance_class_immutable`) refuses any UPDATE of it — the way
    `trg_checkpoint_witnesses_append_only_update` and M5's `raw_value` trigger already are. A stored
    derived field with no CHECK behind it is a comment; a change of belief is a NEW claim with a new
    `match_method` (R-P2), never an edit of `provenance_class`.

        EXACT_ID       -> LINKER_INFERRED   (may auto-confirm: exactly one open entity — IB-2)
        RULE           -> LINKER_INFERRED   (may auto-confirm: a registered rule with an id — IB-2r)
        RECONCILIATION -> RECONCILED        (may auto-confirm: >=2 agreeing sources — IB-2r)
        MODEL_EXTRACT  -> MODEL_EXTRACTED   (### EVIDENCE, never a confirmation; re-enters IB-2 — IB-3)
        MODEL_INFER    -> MODEL_INFERRED    (### NEVER confirms; routes to AMBIGUOUS — IB-4)
        HUMAN          -> OWNER_ASSERTED    (authenticated human; never machine-recomputed — IB-2h)

    `match_method` is protected beside it (`trg_ibc_match_method_immutable`), because the mapping is a
    FUNCTION: a method that can be rewritten is a provenance that can be rewritten one indirection
    later. `SYSTEM_IMPORTED` is the sixth `provenance_class` and appears in entity §38's allow-list
    for a consequential binding, but NO `match_method` maps to it — so no M6 claim can carry it, and
    no seventh `match_method` is invented to reach it (task §3.4).

WHY THERE IS AT MOST ONE CONFIRMED BINDING PER SUBJECT

    ### `UNIQUE (tenant, subject_ref) WHERE state = 'CONFIRMED'` (entity §17) — a PARTIAL unique
    index, not an application-level check-then-insert two writers both pass. Under a race of competing
    confirmations, one wins and the rest hit this index and are refused (machine §17). OCC on
    `version` (`[C-10]`) is the other half of the concurrency story.

WHY A MODEL GUESS CAN NEVER BE A CONFIRMED BINDING

    A CONFIRMED binding carries an ALLOWED provenance (`ck_ibc_confirmed_provenance`:
    LINKER_INFERRED / RECONCILED / OWNER_ASSERTED — M-18, entity §38). MODEL_EXTRACTED is evidence
    and MODEL_INFERRED is a guess; neither may occupy CONFIRMED, so "a MODEL_INFERRED claim in
    CONFIRMED" is a structurally impossible state (entity §37) — at any confidence. Confidence is a
    nullable column used ONLY to order a human's queue (`ix_ibc_ambiguous_queue`); it gates nothing,
    and no CHECK reads it (GR-8, M-16, ADR-007 §8).

WHY A `MODEL_EXTRACTED` CLAIM CANNOT EXIST WITHOUT AN EVIDENCE SPAN

    `ck_ibc_model_extracted_needs_span`: `provenance_class = MODEL_EXTRACTED` requires a non-null
    `evidence_id` AND `span` (entity §16/§37, §43(c), §44). That CHECK is the line between
    MODEL_EXTRACTED (a human can open the document and look) and MODEL_INFERRED (nothing to look at).
    A forged span fails closed at the machine; a missing one is refused by the database.

WHAT IS DELIBERATELY *NOT* HERE (the seams this unit does not own)

    No `conflicts` table and no `CF-*` — M7 is NOT built (task §3.7); `conflict_id` is a constrained
    column with no foreign key. No `compensations` table and no `CM-*` — M10 is NOT built (task §3.8);
    the correction's propagation obligation is recorded on the claim row itself
    (`propagation_obligation`, required-when-CORRECTED), naming the dependents and the completed
    effects that need a Compensation — and NO Compensation is fabricated as completed. No `rules`
    table — M12 is NOT built (task §3.6); `rule_id` is a constrained column with no foreign key, and
    V4 (the registered freight identity rule set) is NOT resolved. No `evidence` table / Evidence
    Store — it is not an M-numbered P6 machine (task §3.11); `evidence_id` + `span` are constrained
    columns with no foreign key. No `entity_ref` foreign key — a load/carrier/movement is freight
    domain, P9+. No `EXPIRED`/`ARCHIVED`/`DELETED`/`RESOLVED` state — there is no eighth state (entity
    §26/§28, task §3.2), no deletion policy (`trg_ibc_no_delete`), and retention is permanent.

    ### M6-AQ-2 (task §3.9), the reading this schema implements and REPORTS: entity §16's CHECK says
    `provenance_class ∈ {LINKER_INFERRED, RECONCILED}` requires a non-null `rule_id`, and IB-2's own
    guard names an exact-trusted-ID match with no rule. This schema keeps the CHECK exactly as entity
    §16 writes it (`ck_ibc_rule_backed`), so IB-2's exact-ID confirmation carries the built-in
    exact-ID match rule id (`EXACT_ID_RULE`, machine constant) — which honours the CHECK WITHOUT
    inventing a customer freight rule (V4 stays open; no MC+date+amount / BOL / PRO rule is defined).
    The alternative reading (IB-2 carries no rule_id, ADR-007 §4.1 step 1) is REPORTED, not silently
    taken; the CHECK is not dropped either way.

WHAT `subject_ref`, `decision_human_id` AND THE LINEAGE FOREIGN KEYS POINT AT

    entity §18 names six foreign keys; two and a half have a table to point at today (task §3.6):
    `subject_ref` -> `observations` (M5); `decision_human_id` (the human behind `decision_ref`) ->
    `tenant_humans` (M1, the precedent for a named ACTIVE human); `corrected_from`/`superseded_by` ->
    self (the retained lineage). The other three (`entity_ref`, `evidence_id`, `rule_id`,
    `conflict_id`) point at tables this unit does not own and so are constrained columns with no FK.

FRESH == MIGRATED, SHIPS DARK

    `create_canonical_schema` builds this table directly; a database reached by
    `phase2_tenant_first.migrate` reaches the SAME shape through
    `create_phase6_identity_binding_claims_schema`. Nothing routes production traffic through M6;
    `identity_binding_claim.py` is the only non-test module that reads it, and only
    `scripts/probe_phase6_identity_binding_claim.py` imports the machine.
"""

from __future__ import annotations

import sqlite3

MIGRATION_ID = "phase6_identity_binding_claims"
P6IBC_SCHEMA_VERSION = "phase6-identity-binding-claims-1"

# Tenant-owned. A claim that "artifact X belongs to entity Y" is a claim WITHIN one brokerage; the
# same subject_ref and entity_ref in two tenants are two isolated claims [C-1]. Every query and every
# uniqueness constraint is tenant-first — there is no honest cross-tenant reading of a binding.
P6IBC_TENANT_TABLES: tuple[str, ...] = ("identity_binding_claims",)

# Nothing tenant-exempt. Stated rather than omitted, so a future addition must defend its exemption.
P6IBC_EXEMPT_TABLES: tuple[str, ...] = ()

# `state-machines/registry.md` §4, M6 / target spec §12.6 — the SEVEN, in the registry's own order.
# There is no eighth: no RESOLVED (M7's), no EXPIRED (entity §26: never), no ARCHIVED, no DELETED
# (entity §28: no deletion policy).
CLAIM_STATES: tuple[str, ...] = (
    "PROPOSED", "CONFIRMED", "AMBIGUOUS", "REJECTED", "SUPERSEDED", "CORRECTED", "CONFLICTING",
)

# machine §8 — the two terminal states (no outgoing enumerated transition).
TERMINAL_CLAIM_STATES: tuple[str, ...] = ("REJECTED", "SUPERSEDED")

# machine §9 / registry §4 (NH) — the two non-terminal human-owned states.
HUMAN_OWNED_CLAIM_STATES: tuple[str, ...] = ("AMBIGUOUS", "CONFLICTING")

# entity §12 — the six canonical `match_method` values. RECONCILIATION is spelled in full here (M6's
# canonical enum); M5's `DETERMINISTIC_MATCH_METHODS` spells its third member `RECONCILE`, and that
# difference is RECORDED (task §3.5), never repaired — M5's constant is not renamed and this table
# uses the canonical six.
MATCH_METHODS: tuple[str, ...] = (
    "EXACT_ID", "RULE", "RECONCILIATION", "MODEL_EXTRACT", "MODEL_INFER", "HUMAN",
)

# SD-6 — the deterministic, immutable mapping `provenance_class = f(match_method)` (entity §13,
# ADR-002 §2.3). A total function; the DB CHECK below is this table verbatim.
PROVENANCE_BY_METHOD: dict[str, str] = {
    "EXACT_ID": "LINKER_INFERRED",
    "RULE": "LINKER_INFERRED",
    "RECONCILIATION": "RECONCILED",
    "MODEL_EXTRACT": "MODEL_EXTRACTED",
    "MODEL_INFER": "MODEL_INFERRED",
    "HUMAN": "OWNER_ASSERTED",
}

# C-7 — the six canonical provenance classes (checkpoint.ProvenanceClass). No seventh. SYSTEM_IMPORTED
# is a member but no `match_method` maps to it, so no M6 claim carries it.
PROVENANCE_CLASSES: tuple[str, ...] = (
    "SYSTEM_IMPORTED", "OWNER_ASSERTED", "LINKER_INFERRED", "MODEL_EXTRACTED", "MODEL_INFERRED",
    "RECONCILED",
)

# entity §38 / M-18 — the provenance a CONFIRMED (consequential) binding may carry. MODEL_EXTRACTED
# (evidence) and MODEL_INFERRED (a guess) are excluded, so a MODEL_INFERRED claim in CONFIRMED is a
# structurally impossible state (entity §37). SYSTEM_IMPORTED is allowed by §38 but unreachable here.
CONFIRMED_ALLOWED_PROVENANCE: tuple[str, ...] = ("LINKER_INFERRED", "RECONCILED", "OWNER_ASSERTED")

# The provenance produced by the model paths — used by the machine to keep the R-P2 laundering
# refusal a SINGLE guard, and named here so the DB CHECK, the machine and the readiness oracle point
# at the same words.
LAUNDERABLE_MODEL_PROVENANCE: tuple[str, ...] = ("MODEL_INFERRED", "MODEL_EXTRACTED")

# events/06-identity-binding-claim-events.md — the closed `ClaimAmbiguous.reason` enum.
AMBIGUOUS_REASONS: tuple[str, ...] = ("model_inferred", "multiple", "single_weak")

# The referents the readiness oracle checks by name. Derived from the DDL by the generic FK loop too;
# naming them here is the unit stating what they are FOR.
P6IBC_REQUIRED_REFERENTS: tuple[str, ...] = (
    "observations", "tenant_humans", "identity_binding_claims",
)

_STATES_SQL = ",".join(f"'{s}'" for s in CLAIM_STATES)
_HUMAN_OWNED_SQL = ",".join(f"'{s}'" for s in HUMAN_OWNED_CLAIM_STATES)
_METHODS_SQL = ",".join(f"'{m}'" for m in MATCH_METHODS)
_PROV_SQL = ",".join(f"'{p}'" for p in PROVENANCE_CLASSES)
_CONFIRMED_PROV_SQL = ",".join(f"'{p}'" for p in CONFIRMED_ALLOWED_PROVENANCE)
_REASONS_SQL = ",".join(f"'{r}'" for r in AMBIGUOUS_REASONS)

# The SD-6 mapping, rendered as ONE physical CHECK line (the schema parser reads a wrapped clause as
# a phantom column). Every legal (match_method, provenance_class) pair, and only those.
_SD6_MAPPING_SQL = " OR ".join(
    f"(match_method = '{m}' AND provenance_class = '{p}')"
    for m, p in PROVENANCE_BY_METHOD.items()
)

# The exact abort texts, worded WITHOUT apostrophes: they are interpolated into single-quoted SQL
# literals inside RAISE(ABORT, ...); an apostrophe would terminate the literal. Matched by
# `identity_binding_claim.py` when it classifies an IntegrityError.
PROVENANCE_CLASS_ABORT = (
    "provenance_class is immutable [entity 09 sec 13 SD-6, ADR-002 R-P2]: it is a DERIVED, immutable "
    "function of match_method, computed once at creation and never independently edited. A change of "
    "belief is a NEW claim with a new match_method, never an edit of provenance_class. This is the "
    "single field a laundering attempt would rewrite, and it does not move"
)
MATCH_METHOD_ABORT = (
    "match_method is immutable [entity 09 sec 13 SD-6]: the mapping provenance_class = f(match_method) "
    "is a function, so a method that could be rewritten is a provenance that could be rewritten one "
    "indirection later. A claim that matched a different way is a NEW claim, not an edit of this one"
)
IDENTITY_ABORT = (
    "the identity and evidence of a binding claim are immutable [entity 09 sec 13/22, C-8]: the "
    "tenant, the claim id, the subject it binds, the entity it claims, the evidence span it rests on, "
    "the rule it fired, the human decision behind it and when it was created are what make it THIS "
    "claim. Editing them would retarget or relaunder a recorded decision in place"
)
VERSION_ABORT = (
    "identity_binding_claims.version advances by exactly one per state transition [GR-3, C-10]: a "
    "state change that does not advance it silently overwrites another transition. OCC on the claim "
    "version is the concurrency guard, and a version that stands still is a lost update"
)
DELETE_ABORT = (
    "identity_binding_claims is never deleted [entity 09 sec 28/29, C-9]: retention is permanent — the "
    "evidence chain. A superseded, rejected or corrected claim is retained as history so an angry "
    "person can be shown exactly what was decided and when, and deleting the row is how that "
    "disappears"
)


P6IBC_TARGET_SCHEMA: dict[str, str] = {
    # THE IDENTITY BINDING CLAIM (`entities/09-identity-binding-claim.md`, spec §12.6, machine M6).
    #
    # Every column on its OWN line and every FOREIGN KEY / CHECK on its OWN line, and every
    # multi-condition CHECK on ONE physical line: `schema._canonical_columns` parses this DDL line by
    # line, reads only the first token of a line as a column, and skips a line that STARTS with
    # PRIMARY KEY / FOREIGN KEY / UNIQUE / CHECK. A wrapped clause reads as a column called
    # `REFERENCES` or `OR` — the blind spot `phase6_pipeline_instances` documents.
    "identity_binding_claims": """
        CREATE TABLE identity_binding_claims (
            tenant TEXT NOT NULL,
            binding_claim_id TEXT NOT NULL,
            -- ### THE CLAIM: artifact `subject_ref` belongs to entity `entity_ref`. subject_ref is an
            -- observation (M5) and carries a FK; entity_ref is a load/carrier/movement (freight
            -- domain, P9+) and carries none — a FK into a table this unit does not own would be half
            -- of a machine it does not build.
            subject_ref TEXT NOT NULL,
            entity_ref TEXT NOT NULL,
            -- ### PROVENANCE IS DERIVED FROM match_method (SD-6), never chosen and never edited. The
            -- CHECK `ck_ibc_provenance_is_derived` below is the mapping verbatim; the trigger
            -- `trg_ibc_provenance_class_immutable` refuses any UPDATE of this column.
            provenance_class TEXT NOT NULL,
            -- ### THE SEVEN CANONICAL STATES, ENUMERATED INLINE ON THE COLUMN (registry sec 4, M6).
            -- One physical line so the readiness parser still reads `state` as NOT NULL and so DDL
            -- introspection finds the vocabulary ON the column: no eighth state, no RESOLVED, no
            -- EXPIRED, no DELETED. Interpolated from CLAIM_STATES, the single source of truth.
            state TEXT NOT NULL CHECK (state IN (%(states)s)),
            version INTEGER NOT NULL,
            -- ### THE SIX CANONICAL match_method VALUES, ENUMERATED INLINE ON THE COLUMN (entity §12).
            -- One physical line, exactly like `state` above, so DDL introspection finds the vocabulary
            -- ON the column: EXACT_ID, RULE, RECONCILIATION, MODEL_EXTRACT, MODEL_INFER, HUMAN, and no
            -- seventh (task §3.4). The composite SD-6 CHECK below then pins each to its derived
            -- provenance_class. Interpolated from MATCH_METHODS, the single source of truth.
            match_method TEXT NOT NULL CHECK (match_method IN (%(methods)s)),
            -- ### CONFIDENCE ORDERS A HUMAN QUEUE AND GATES NOTHING (GR-8, M-16, ADR-007 sec 8).
            -- Nullable, never read by a CHECK, never a guard input. provenance_class gates; confidence
            -- sorts.
            confidence REAL,
            -- Evidence span: REQUIRED when provenance_class = MODEL_EXTRACTED (ck_ibc_model_extracted_
            -- needs_span). No FK — the Evidence Store is not built here (task sec 3.11).
            evidence_id TEXT,
            span TEXT,
            -- rule_id: REQUIRED when provenance_class IN (LINKER_INFERRED, RECONCILED)
            -- (ck_ibc_rule_backed, entity sec 16). No FK — M12 (rules) is not built (task sec 3.6).
            rule_id TEXT,
            -- The human decision behind an OWNER_ASSERTED confirmation or a correction. decision_ref
            -- is the reference; decision_human_id is the FK-backed named ACTIVE human (M1/M4 precedent)
            -- — "an authenticated human" is decoration while it is a free-text column.
            decision_ref TEXT,
            decision_human_id TEXT,
            -- ### THE NAMED HUMAN who owns an AMBIGUOUS / CONFLICTING claim (machine sec 5/9, registry
            -- sec 4 NH). A FK into the tenant's recorded humans: "human-owned" is decoration while
            -- this is a free-text column any string satisfies (M1's argument for owner_id, M5's for
            -- UNBOUND). The CHECK below makes an AMBIGUOUS/CONFLICTING row with no owner impossible.
            owner_id TEXT,
            -- The ClaimAmbiguous reason (model_inferred / multiple / single_weak), set on IB-4.
            ambiguous_reason TEXT,
            -- Lineage (entity sec 18, self-FK): the prior claim a correction was made from, and the
            -- newer claim a supersession points at. The old claim is RETAINED, never deleted.
            corrected_from TEXT,
            superseded_by TEXT,
            -- The conflict a CONFIRMED-vs-owner disagreement raised (IB-6). No FK — M7 (conflicts) is
            -- not built (task sec 3.7); this carries the conflict aggregate id the emitted
            -- ConflictRaised names.
            conflict_id TEXT,
            -- ### THE CORRECTION PROPAGATION OBLIGATION (IB-7, ADR-007 sec 6, M-20). REQUIRED when
            -- state = CORRECTED (ck_ibc_corrected_has_obligation): a JSON record naming the dependents
            -- to re-derive and the completed effects that rested on the wrong binding and therefore
            -- need a Compensation (M10). Nothing silently drops or closes it, and NO Compensation is
            -- fabricated as completed. M10 is not built here (task sec 3.8).
            propagation_obligation TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            PRIMARY KEY (tenant, binding_claim_id),
            -- The subject is an observation of THIS tenant; the human is a recorded human of THIS
            -- tenant; the lineage links are self-FKs. Each on its OWN line so the readiness parser
            -- skips it as a non-column.
            FOREIGN KEY (tenant, subject_ref) REFERENCES observations (tenant, observation_id),
            FOREIGN KEY (tenant, decision_human_id) REFERENCES tenant_humans (tenant, human_id),
            FOREIGN KEY (tenant, owner_id) REFERENCES tenant_humans (tenant, human_id),
            FOREIGN KEY (tenant, corrected_from) REFERENCES identity_binding_claims (tenant, binding_claim_id),
            FOREIGN KEY (tenant, superseded_by) REFERENCES identity_binding_claims (tenant, binding_claim_id),
            -- The state-vocabulary CHECK lives INLINE on the column above (declared once).
            CHECK (version >= 1),
            -- ### AN AMBIGUOUS OR CONFLICTING CLAIM NAMES A HUMAN, or it is a silent drop wearing a
            -- status (machine sec 5/9). On ONE line: a wrapped continuation reads as a column OR.
            CHECK (state NOT IN (%(human_owned)s) OR owner_id IS NOT NULL),
            -- The match_method enumeration CHECK lives INLINE on the column above (declared once).
            CHECK (provenance_class IN (%(prov)s)),
            -- ### SD-6: provenance_class IS THE DERIVED FUNCTION OF match_method. One physical line;
            -- every legal pair and only those. A caller cannot choose provenance independently of
            -- match_method, and the immutability trigger stops it being edited afterwards.
            CHECK (%(sd6)s),
            -- ### A CONFIRMED BINDING CARRIES AN ALLOWED PROVENANCE (entity sec 37/38, M-18): a
            -- MODEL_INFERRED or MODEL_EXTRACTED claim in CONFIRMED is structurally impossible.
            CHECK (state <> 'CONFIRMED' OR provenance_class IN (%(confirmed_prov)s)),
            -- ### A MODEL_EXTRACTED CLAIM REQUIRES AN EVIDENCE SPAN (entity sec 16/37/44): the line
            -- between MODEL_EXTRACTED (a human can look) and MODEL_INFERRED (nothing to look at).
            CHECK (provenance_class <> 'MODEL_EXTRACTED' OR (evidence_id IS NOT NULL AND span IS NOT NULL)),
            -- ### LINKER_INFERRED / RECONCILED REQUIRE A rule_id (entity sec 16). Kept exactly as
            -- written; M6-AQ-2 is reported, not resolved by dropping it (module docstring, task sec 3.9).
            CHECK (provenance_class NOT IN ('LINKER_INFERRED','RECONCILED') OR rule_id IS NOT NULL),
            -- ### A CORRECTED CLAIM CARRIES ITS PROPAGATION OBLIGATION (ADR-007 sec 6): "a correction
            -- that does not propagate is a lie with a timestamp". Dropping the obligation write is a
            -- forbidden mutation, and this CHECK is why the DB refuses the transition without it.
            CHECK (state <> 'CORRECTED' OR propagation_obligation IS NOT NULL),
            CHECK (ambiguous_reason IS NULL OR ambiguous_reason IN (%(reasons)s)),
            CHECK (trim(binding_claim_id) <> ''),
            CHECK (trim(subject_ref) <> ''),
            CHECK (trim(entity_ref) <> ''),
            CHECK (trim(state) <> '')
        )""" % {
            "states": _STATES_SQL, "methods": _METHODS_SQL, "prov": _PROV_SQL,
            "sd6": _SD6_MAPPING_SQL, "confirmed_prov": _CONFIRMED_PROV_SQL,
            "reasons": _REASONS_SQL, "human_owned": _HUMAN_OWNED_SQL,
        },
}


P6IBC_INDEXES: dict[str, str] = {
    # ### AT MOST ONE CONFIRMED BINDING PER SUBJECT — A PARTIAL UNIQUE INDEX (entity sec 17, machine
    # sec 17). Under a race of competing confirmations, one wins and every other hits THIS index and
    # is refused. Drop the UNIQUE, or drop the WHERE clause, and two CONFIRMED bindings for one
    # subject become insertable — the canonical-binding invariant switched off.
    "ix_ibc_one_confirmed_per_subject":
        "CREATE UNIQUE INDEX ix_ibc_one_confirmed_per_subject "
        "ON identity_binding_claims (tenant, subject_ref) WHERE state = 'CONFIRMED'",
    # The human's queue: the AMBIGUOUS / CONFLICTING claims a human owns, ordered by confidence — the
    # ONE legitimate use of confidence (ADR-007 sec 4.2). It sorts the queue; it gates nothing.
    "ix_ibc_ambiguous_queue":
        "CREATE INDEX ix_ibc_ambiguous_queue "
        "ON identity_binding_claims (tenant, state, confidence)",
    # The lineage read: walk corrected_from / superseded_by forward for propagation and history.
    "ix_ibc_subject_state":
        "CREATE INDEX ix_ibc_subject_state "
        "ON identity_binding_claims (tenant, subject_ref, state)",
}

# Nothing from an earlier phase is replaced. Declared so a future replacement has somewhere to go.
P6IBC_REPLACED_INDEXES: tuple[str, ...] = ()


P6IBC_TRIGGERS: dict[str, str] = {
    # ### provenance_class NEVER MUTATES (entity sec 13 SD-6, ADR-002 R-P2). This makes SD-6 true
    # against a connection, not only against the Python. A change of belief is a NEW claim.
    "trg_ibc_provenance_class_immutable": f"""
        CREATE TRIGGER trg_ibc_provenance_class_immutable
        BEFORE UPDATE OF provenance_class ON identity_binding_claims
        BEGIN SELECT RAISE(ABORT, '{PROVENANCE_CLASS_ABORT}'); END""",
    # ### match_method NEVER MUTATES (entity sec 13). The mapping is a function; a rewritable method
    # is a rewritable provenance one indirection later.
    "trg_ibc_match_method_immutable": f"""
        CREATE TRIGGER trg_ibc_match_method_immutable
        BEFORE UPDATE OF match_method ON identity_binding_claims
        BEGIN SELECT RAISE(ABORT, '{MATCH_METHOD_ABORT}'); END""",
    # ### THE IDENTITY AND EVIDENCE OF THE CLAIM ARE IMMUTABLE TOO. Editing the subject, the entity,
    # the evidence span, the rule, the human decision, the correction lineage or created_at would
    # retarget or relaunder a recorded decision in place — the shape of change an audit cannot detect
    # afterwards, because the row is then internally consistent.
    "trg_ibc_identity_immutable": f"""
        CREATE TRIGGER trg_ibc_identity_immutable
        BEFORE UPDATE OF tenant, binding_claim_id, subject_ref, entity_ref, evidence_id, span,
            rule_id, decision_ref, decision_human_id, corrected_from, created_at
        ON identity_binding_claims
        BEGIN SELECT RAISE(ABORT, '{IDENTITY_ABORT}'); END""",
    # ### OCC ON THE CLAIM (GR-3, C-10, machine sec 17). A state transition advances version by
    # exactly one; a state change that leaves version standing is two transitions claiming one
    # version.
    "trg_ibc_version_advances_on_state_change": f"""
        CREATE TRIGGER trg_ibc_version_advances_on_state_change
        BEFORE UPDATE ON identity_binding_claims
        WHEN NEW.state <> OLD.state AND NEW.version <> OLD.version + 1
        BEGIN SELECT RAISE(ABORT, '{VERSION_ABORT}'); END""",
    # ### NO DELETION, EVER (entity sec 28/29, C-9). Retention is permanent — the evidence chain.
    "trg_ibc_no_delete": f"""
        CREATE TRIGGER trg_ibc_no_delete
        BEFORE DELETE ON identity_binding_claims
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


def create_phase6_identity_binding_claims_schema(conn: sqlite3.Connection, *, now: str) -> list[str]:
    """Create whatever M6 structure is missing. Idempotent; returns what it did.

    Callable on a fresh canonical database and on an already-migrated one. Either way the resulting
    structure is byte-identical, because there is only one text. Built AFTER M5 (`observations` FK)
    and M1 (`tenant_humans` FK), which is why `schema.py` orders it last of the P6 units.
    """
    performed: list[str] = []
    present = _tables(conn)
    for name in (*P6IBC_TENANT_TABLES, *P6IBC_EXEMPT_TABLES):
        if name not in present:
            conn.execute(P6IBC_TARGET_SCHEMA[name])
            performed.append(f"create-table:{name}")
    existing = _indexes(conn)
    for name, ddl in P6IBC_INDEXES.items():
        if name not in existing:
            conn.execute(ddl)
            performed.append(f"create-index:{name}")
    for stale in P6IBC_REPLACED_INDEXES:
        if stale in _indexes(conn):
            conn.execute(f"DROP INDEX {stale}")
            performed.append(f"drop-index:{stale}")
    existing_triggers = _triggers(conn)
    for name, ddl in P6IBC_TRIGGERS.items():
        if name not in existing_triggers:
            conn.execute(ddl)
            performed.append(f"create-trigger:{name}")
    # NO VERSION STAMP HERE — marker-last, like every phase. A stamp on a half-migrated database is
    # how a missing trigger goes unnoticed.
    conn.commit()
    return performed


def stamp_phase6_identity_binding_claims_version(conn: sqlite3.Connection, *, now: str) -> None:
    """Record the M6 marker — callable ONLY once readiness holds. Marker-last, like every phase."""
    problems = phase6_identity_binding_claims_readiness_problems(conn)
    if problems:
        raise RuntimeError(
            f"refusing to stamp {P6IBC_SCHEMA_VERSION} on a database that is NOT ready: "
            + "; ".join(problems)
        )
    if "schema_migrations" in _tables(conn):
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration, step, applied_at, detail) "
            "VALUES (?,?,?,?)",
            (MIGRATION_ID, f"version:{P6IBC_SCHEMA_VERSION}", now,
             "the Identity Binding Claim: one claim per row, tenant-first, provenance_class derived "
             "from match_method and immutable by trigger, at most one CONFIRMED binding per subject, "
             "MODEL_EXTRACTED requires an evidence span, a correction carries its propagation "
             "obligation; readiness proven"),
        )
        conn.commit()


def phase6_identity_binding_claims_readiness_problems(conn: sqlite3.Connection) -> list[str]:
    """Every reason this database cannot carry identity binding claims safely. Empty == ready.

    Structural, like the P2/P3/P5/M1/M2/M3/M4/M5 oracles it extends. The partial unique index and the
    immutability triggers are verified PRESENT because an `identity_binding_claims` table without them
    is an ordinary table with an aspirational comment: two writers could both confirm one subject,
    provenance_class could be edited, and a guess could be filed as a confirmed binding.
    """
    problems: list[str] = []
    present = _tables(conn)
    for table in (*P6IBC_TENANT_TABLES, *P6IBC_EXEMPT_TABLES):
        if table not in present:
            problems.append(
                f"required Phase-6 table {table!r} is missing: run the {MIGRATION_ID} migration"
            )
    if not all(t in present for t in P6IBC_TENANT_TABLES):
        return problems

    live_triggers = _triggers(conn)
    missing_triggers = sorted(t for t in P6IBC_TRIGGERS if t not in live_triggers)
    if missing_triggers:
        problems.append(
            f"Identity-binding-claim invariant triggers missing: {missing_triggers}. Without them "
            f"provenance_class or match_method could be rewritten (a laundered belief), a state "
            f"transition could stand the version still, or the immutable claim could be deleted "
            f"[entity sec 13/28, GR-3, C-9, R-P2]."
        )
    live_indexes = _indexes(conn)
    for name in P6IBC_INDEXES:
        if name not in live_indexes:
            problems.append(f"required Phase-6 index {name!r} is missing")
    for stale in P6IBC_REPLACED_INDEXES:
        if stale in live_indexes:
            problems.append(f"replaced index {stale!r} is still present")

    # ### THE ONE-CONFIRMED-PER-SUBJECT INDEX, READ OUT OF THE LIVE DATABASE RATHER THAN ASSUMED FROM
    # ITS NAME. An index called `..._one_confirmed_per_subject` that is not UNIQUE, or that has lost
    # its `WHERE state = 'CONFIRMED'` clause, is the canonical-binding defence switched off with the
    # sign left up: two CONFIRMED bindings for one subject would become insertable.
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name = ?",
        ("ix_ibc_one_confirmed_per_subject",),
    ).fetchone()
    if row is not None:
        sql = " ".join((row[0] or "").split()).upper()
        if "UNIQUE" not in sql:
            problems.append(
                "ix_ibc_one_confirmed_per_subject is not UNIQUE: two CONFIRMED bindings for one "
                "subject would be insertable, and 'at most one CONFIRMED binding per subject' "
                "(entity sec 17) would be a convention, not a constraint."
            )
        if "WHERE STATE = 'CONFIRMED'" not in sql.replace(", ", ","):
            problems.append(
                "ix_ibc_one_confirmed_per_subject has lost its `WHERE state = 'CONFIRMED'` clause: "
                "the partial index is what allows many PROPOSED/AMBIGUOUS claims per subject while "
                "permitting at most one CONFIRMED (entity sec 14/17)."
            )
        for column in ("TENANT", "SUBJECT_REF"):
            if column not in sql:
                problems.append(
                    f"ix_ibc_one_confirmed_per_subject does not cover {column!r}: the canonical "
                    f"binding is unique per (tenant, subject_ref), and dropping a member widens or "
                    f"narrows what counts as 'the same subject'."
                )

    # ### THE CHECKS AND THE STATE VOCABULARY, READ OUT OF THE identity_binding_claims DDL. A CHECK
    # the migration intended but a live database does not carry is the invariant switched off.
    ddl_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='identity_binding_claims'"
    ).fetchone()
    ddl = " ".join((ddl_row[0] if ddl_row else "" or "").split()).upper()
    compact = ddl.replace(", ", ",")

    expected_states = ("STATE IN (" + ",".join(f"'{s}'" for s in CLAIM_STATES) + ")").upper()
    if expected_states not in compact:
        problems.append(
            "identity_binding_claims does not enumerate the seven canonical states inline on the "
            "state column (registry sec 4, M6): without it an eighth state — a RESOLVED, an EXPIRED "
            "or a DELETED — would be writable, and entity sec 26/28 say none exists."
        )
    # ### SD-6, READ BACK: every legal (match_method, provenance_class) pair must be present in the
    # mapping CHECK, or provenance has stopped being the derived function of match_method.
    for method, prov in PROVENANCE_BY_METHOD.items():
        pair = f"(MATCH_METHOD = '{method}' AND PROVENANCE_CLASS = '{prov}')"
        if pair not in compact:
            problems.append(
                f"identity_binding_claims does not CHECK the SD-6 mapping {method} -> {prov}: "
                f"provenance_class must be the DETERMINISTIC, IMMUTABLE function of match_method "
                f"(entity sec 13, ADR-002 R-P2), and a missing pair is a provenance a caller could "
                f"choose."
            )
    if "PROVENANCE_CLASS <> 'MODEL_EXTRACTED' OR (EVIDENCE_ID IS NOT NULL AND SPAN IS NOT NULL)" \
            not in compact:
        problems.append(
            "identity_binding_claims does not CHECK that a MODEL_EXTRACTED claim carries an evidence "
            "span: entity sec 16/37 name a MODEL_EXTRACTED claim with no span a structurally "
            "impossible state — the line between evidence a human can look at and a guess."
        )
    if "PROVENANCE_CLASS NOT IN ('LINKER_INFERRED','RECONCILED') OR RULE_ID IS NOT NULL" \
            not in compact:
        problems.append(
            "identity_binding_claims does not CHECK that a LINKER_INFERRED/RECONCILED claim carries a "
            "rule_id (entity sec 16): the CHECK is kept exactly as written; M6-AQ-2 is reported, not "
            "closed by dropping it."
        )
    confirmed_prov = (
        "STATE <> 'CONFIRMED' OR PROVENANCE_CLASS IN ("
        + ",".join(f"'{p}'" for p in CONFIRMED_ALLOWED_PROVENANCE) + ")").upper()
    if confirmed_prov not in compact:
        problems.append(
            "identity_binding_claims does not CHECK that a CONFIRMED binding carries an allowed "
            "provenance (entity sec 37/38, M-18): without it a MODEL_INFERRED guess could occupy "
            "CONFIRMED, which the whole unit exists to prevent."
        )
    if "STATE <> 'CORRECTED' OR PROPAGATION_OBLIGATION IS NOT NULL" not in compact:
        problems.append(
            "identity_binding_claims does not CHECK that a CORRECTED claim carries its propagation "
            "obligation (ADR-007 sec 6): a correction that does not record which effects rested on "
            "the wrong binding is a lie with a timestamp."
        )
    human_owned_check = (
        "STATE NOT IN (" + ",".join(f"'{s}'" for s in HUMAN_OWNED_CLAIM_STATES)
        + ") OR OWNER_ID IS NOT NULL").upper()
    if human_owned_check not in compact:
        problems.append(
            "identity_binding_claims does not CHECK that an AMBIGUOUS or CONFLICTING claim names an "
            "owner (machine sec 5/9): a human-owned state with no named human is a silent drop "
            "wearing a status, and a database enforces it with a CHECK plus the tenant_humans FK."
        )

    for table in P6IBC_TENANT_TABLES:
        referents = _referents(conn, table)
        for referent in P6IBC_REQUIRED_REFERENTS:
            if referent not in referents:
                problems.append(
                    f"{table} declares no foreign key into {referent!r}: the subject is an "
                    f"observation (M5), the human behind a decision is a recorded ACTIVE human (M1), "
                    f"and the lineage is a self-FK — 'a named subject/human/prior claim' is "
                    f"decoration while these are free-text columns (entity sec 18)."
                )
    return problems
