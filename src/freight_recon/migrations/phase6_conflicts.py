"""Phase 6 — M7, the Conflict: one `conflicts` row per disputed field, one machine, five states, and
the rule that makes disagreement a decision a human OWNS rather than a winner a machine PICKED.

WHAT THIS TABLE IS, IN FREIGHT TERMS

    The TMS says load 4471 is delivered and the carrier portal says it is still in transit. Neyma does
    NOT pick the more recent source, the more confident source, or the source it likes — it FREEZES the
    delivery field and a named human owns the disagreement. The owner assigned a POD to load 4471 by
    hand and the linker now insists it belongs to 44718; Neyma preserves the owner's binding and RAISES
    rather than choosing. A readback of the payable just entered does not match the invoice the owner
    approved — not an ordinary failure, not a silent retry. Two standing rules disagree about which
    source governs — that fails closed too. A third source arrives and ATTACHES to the same conflict
    rather than starting another. The clock advances and the conflict ESCALATES — it never expires and
    it never resolves. Nothing closes it except a registered rule with an id or an authenticated human
    with a decision, and an invoice cannot go out while it stands.

    ### A CONFLICT IS TWO OR MORE MUTUALLY EXCLUSIVE CLAIMS OR OBSERVATIONS ON THE SAME FIELD. ITS
    PURPOSE IS TO MAKE DISAGREEMENT VISIBLE AND BLOCKING — THE MECHANISM BY WHICH NEYMA NEVER SILENTLY
    CHOOSES. IT IS NOT `unknown` (we do not lack information — we have too much, and it disagrees — I8),
    NOT AN ERROR, AND NOT RESOLVABLE BY RECENCY, CONFIDENCE, A MODEL, OR A CLOCK (entity §2/§3/§4).

WHY THE CONFLICT ROW *IS* THE DURABLE FIELD CONDITION (task §3.9)

    entity §15 requires raising a Conflict and setting the disputed field's evidence condition to
    `conflicting` in ONE transaction. `entity_ref` is a canonical projection row (`K-2`), the freight
    projection is P9+, and no universal field-condition table exists today. The smallest implementation
    consistent with the current architecture — and the one the corpus directs — is that THE CONFLICT
    ROW IS THE FIELD CONDITION. `(tenant, entity_ref, field)` is the natural key (entity §9), and the
    partial unique index over the three OPEN states makes "is this field `conflicting`?" a single
    tenant-first query. One row insert is one commit, which is exactly what entity §15 asks for, and
    `conflict.py` projects that row into the checkpoint's existing `NativeClaim(conflicting=…)` /
    `EvidenceCondition.CONFLICTING` types — it BLOCKS values, it never writes projected ones (F7). No
    projection store, entity/field registry, Expectation, Exception, Compensation or Rule registry is
    built to hold it — that is M8+ infrastructure and it is not this unit's.

WHY THERE IS AT MOST ONE OPEN CONFLICT PER FIELD

    ### `UNIQUE (tenant, entity_ref, field) WHERE state IN ('RAISED','OPEN','ESCALATED')` (entity §17,
    machine §17) — a PARTIAL unique index, not an application-level check-then-insert two concurrent
    detectors both pass. A second detection of the same `(entity, field)` disagreement ATTACHES a party
    to the existing open Conflict (CF-7), it does not create a second one. M6's `WHERE state =
    'CONFIRMED'` index is the precedent. The three OPEN states are one set for this purpose.

WHY AN OWNERLESS CONFLICT IS STRUCTURALLY IMPOSSIBLE

    `owner_id` is `NOT NULL` from creation and FOREIGN-KEY-backed into `tenant_humans` (M1's precedent
    for a named ACTIVE human; M4's for `granted_by`; M6's for the human behind a `decision_ref`). "A
    Conflict has a human owner" is decoration while `owner_id` is a free-text column any string
    satisfies. A system-detected Conflict STILL gets a named ACTIVE human at creation (entity §10/§16,
    §37; CF-1's trigger type is `S|X`) — the CALLER supplies the human; the machine never picks one, and
    `system` is not a human, and a model actor may never be the owner (`[C-6]`, `ER-9`).

WHY RESOLUTION HAS EXACTLY TWO WAYS AND NEVER A THIRD (ADR-007 §5.3)

    `CHECK: state = RESOLVED_BY_RULE requires a non-null rule_id`; `CHECK: state = RESOLVED_BY_HUMAN
    requires a non-null decision_ref` (entity §16). And `CHECK (rule_id IS NULL OR decision_ref IS
    NULL)` — a resolution carries at most one basis, so combined with the two state CHECKs a resolved
    Conflict carries EXACTLY ONE. There is no recency, no confidence, no source priority (unless a
    REGISTERED rule with an id says so), no model, and no timer. A CF-3 rule must be REGISTERED, and the
    rule SET ships EMPTY (V5 stays open, fail-closed default: no rule ⇒ every conflict to a human).

WHAT IS DELIBERATELY *NOT* HERE (the seams this unit does not own)

    No sixth state — five only (`RAISED, OPEN, ESCALATED, RESOLVED_BY_RULE, RESOLVED_BY_HUMAN`), no
    `CANCELLED` (M7-AQ-3 held open, task §3.8), no `EXPIRED` (entity §26/machine §12/§23: a Conflict
    NEVER expires — it ages and escalates), no bare `RESOLVED` (M9's vocabulary), no `AUTO_RESOLVED`,
    no `DISMISSED`. No deletion policy (`trg_conflicts_no_delete`) and permanent retention (entity
    §28/§29). No `rules` table — M12 is not built (task §3.11); `rule_id` and the rule half of
    `decision_ref` are constrained columns with no foreign key, and V5 is not resolved. No
    `compensations` table and no `CM-*` — M10 is not built (task §3.9); a resolution records nothing on
    M6's behalf. No `entity_ref` foreign key — a load/carrier/movement is freight domain, P9+.

WHAT THE FOREIGN KEYS POINT AT (entity §18, task §3.9)

    `owner_id` -> `tenant_humans` (M1). `decision_human_id` (the human behind `decision_ref`) ->
    `tenant_humans` (M1, M6's precedent). A party child row -> its `conflict_id` self-FK into
    `conflicts`; a party that is an identity binding claim -> `identity_binding_claims` (M6); a party
    that is an observation -> `observations` (M5). The others (`entity_ref`, `rule_id`, and the
    `audit_events`/`rules` polymorphic half of `decision_ref`) point at tables this unit does not own
    and so are constrained columns with no FK, with a resolvable-kind discriminator beside them —
    exactly M6's `K-1` shape. Nothing here builds `rules`, `evidence`, `expectations`, `exceptions` or
    `compensations` to satisfy one.

FRESH == MIGRATED, SHIPS DARK

    `create_canonical_schema` builds these tables directly; a database reached by
    `phase2_tenant_first.migrate` reaches the SAME shape through `create_phase6_conflicts_schema`.
    Nothing routes production traffic through M7; `conflict.py` is the only non-test module that reads
    it, and only `scripts/probe_phase6_conflict.py` imports the machine.
"""

from __future__ import annotations

import sqlite3

MIGRATION_ID = "phase6_conflicts"
P6CF_SCHEMA_VERSION = "phase6-conflicts-1"

# Tenant-owned. A Conflict is a disagreement WITHIN one brokerage; the same entity_ref and field in two
# tenants are two isolated Conflicts [C-1]. Every query and every uniqueness constraint is tenant-first.
P6CF_TENANT_TABLES: tuple[str, ...] = ("conflicts", "conflict_parties")

# Nothing tenant-exempt. Stated rather than omitted, so a future addition must defend its exemption.
P6CF_EXEMPT_TABLES: tuple[str, ...] = ()

# `state-machines/registry.md` §4, M7 / target spec §12.7 — the FIVE, in the registry's own order.
# There is no sixth: no CANCELLED (M7-AQ-3), no EXPIRED (entity §26: NEVER), no bare RESOLVED (M9's),
# no AUTO_RESOLVED, no DISMISSED.
CONFLICT_STATES: tuple[str, ...] = (
    "RAISED", "OPEN", "ESCALATED", "RESOLVED_BY_RULE", "RESOLVED_BY_HUMAN",
)

# machine §8 — the two terminal states (no outgoing enumerated transition).
TERMINAL_CONFLICT_STATES: tuple[str, ...] = ("RESOLVED_BY_RULE", "RESOLVED_BY_HUMAN")

# machine §16/§17/§36 — the three OPEN states: while in any of these the field is `conflicting` and
# BLOCKS every consequential action on the entity. "Not acknowledged yet" is not "not blocking yet".
OPEN_CONFLICT_STATES: tuple[str, ...] = ("RAISED", "OPEN", "ESCALATED")

# machine §9 — the two non-terminal human-owned states (OPEN, ESCALATED). RAISED is recoverable.
HUMAN_OWNED_CONFLICT_STATES: tuple[str, ...] = ("OPEN", "ESCALATED")

# entity §12 / the `ConflictRaised` `kind` enum / ADR-007 §5.1 — the six canonical kinds. There is no
# seventh; the event contract refuses one at emission.
CONFLICT_KINDS: tuple[str, ...] = (
    "SYSTEM_VS_SYSTEM", "CLAIM_VS_CLAIM", "CLAIM_VS_OBSERVATION", "INFERRER_VS_OWNER",
    "READBACK_VS_APPROVED", "RULE_VS_RULE",
)

# `[C-7]` — the six canonical provenance classes (checkpoint.ProvenanceClass). Each `parties[]` entry
# carries its OWN provenance_class, one of these six, carried and never strengthened (ER-14, R-P2). No
# seventh.
PROVENANCE_CLASSES: tuple[str, ...] = (
    "SYSTEM_IMPORTED", "OWNER_ASSERTED", "LINKER_INFERRED", "MODEL_EXTRACTED", "MODEL_INFERRED",
    "RECONCILED",
)

# A `parties[]` reference is polymorphic — a claim (M6), an observation (M5), a readback (M3), a
# standing rule (M12), or a system reading — so it needs a kind discriminator beside it (task §3.9,
# K-1's shape). The FK is built for each kind whose table EXISTS today; the others are constrained.
PARTY_KINDS: tuple[str, ...] = (
    "identity_binding_claim", "observation", "readback", "rule", "system",
)

# `decision_ref`'s resolvable-kind discriminator (K-1): a human decision resolves into `audit_events`
# (that table exists) and the human is FK-backed into `tenant_humans`; a rule-basis decision_ref would
# resolve into `rules` (M12, NOT built), so that half is carried, not FK-backed. Follows M6.
DECISION_REF_KINDS: tuple[str, ...] = ("audit_event", "rule")

# The referents the readiness oracle checks by name. Derived from the DDL by the generic FK loop too;
# naming them here is the unit stating what they are FOR.
P6CF_CONFLICT_REFERENTS: tuple[str, ...] = ("tenant_humans",)
P6CF_PARTY_REFERENTS: tuple[str, ...] = (
    "conflicts", "identity_binding_claims", "observations",
)

_STATES_SQL = ",".join(f"'{s}'" for s in CONFLICT_STATES)
_OPEN_SQL = ",".join(f"'{s}'" for s in OPEN_CONFLICT_STATES)
_KINDS_SQL = ",".join(f"'{k}'" for k in CONFLICT_KINDS)
_PROV_SQL = ",".join(f"'{p}'" for p in PROVENANCE_CLASSES)
_PARTY_KINDS_SQL = ",".join(f"'{k}'" for k in PARTY_KINDS)
_DECISION_KINDS_SQL = ",".join(f"'{k}'" for k in DECISION_REF_KINDS)

# The exact abort texts, worded WITHOUT apostrophes: they are interpolated into single-quoted SQL
# literals inside RAISE(ABORT, ...). Matched by `conflict.py` when it classifies an IntegrityError.
VERSION_ABORT = (
    "conflicts.version advances by exactly one per state transition [GR-3, C-10]: a state change that "
    "does not advance it silently overwrites another transition. OCC on the conflict version is the "
    "concurrency guard, and a version that stands still is a lost update"
)
IDENTITY_ABORT = (
    "the identity of a conflict is immutable [entity 10 sec 15/16, C-8]: the tenant, the conflict id, "
    "the entity it is about, the disputed field, the kind of disagreement and when it was raised are "
    "what make it THIS conflict. Editing them would retarget or relaunder a recorded disagreement in "
    "place, and the field it froze would no longer be the field it named"
)
DELETE_ABORT = (
    "a conflict is never deleted [entity 10 sec 28/29, C-9]: retention is permanent. A resolved "
    "conflict is retained and the resolution basis is retained with it, so an angry person can be "
    "shown exactly what disagreed, who owned it, and how it closed. Deleting the row is how that "
    "disappears, and a conflict NEVER expires either [entity 10 sec 26]"
)
PARTY_PROVENANCE_ABORT = (
    "a party provenance_class is carried, never strengthened [ER-14, R-P2, ADR-002 R-P2]: each party "
    "of a conflict records its OWN provenance, assigned at detection, and an INFERRER_VS_OWNER conflict "
    "specifically records that one party is OWNER_ASSERTED as the evidence of why the inferrer did not "
    "overwrite it. Editing a recorded party provenance would launder a guess into a stronger claim"
)
PARTY_DELETE_ABORT = (
    "a conflict party is never deleted [entity 10 sec 28/29, C-9]: the parties are the evidence of the "
    "disagreement, and a full-history rebuild folds them. Deleting one would reproduce a stale party "
    "set on replay, an AC-EVT-008 digest divergence"
)


P6CF_TARGET_SCHEMA: dict[str, str] = {
    # THE CONFLICT (`entities/10-conflict.md`, spec §12.7, machine M7).
    #
    # Every column on its OWN line and every FOREIGN KEY / CHECK on its OWN physical line, and every
    # multi-condition CHECK on ONE physical line: `schema._canonical_columns` parses this DDL line by
    # line, reads only the first token of a line as a column, and skips a line that STARTS with
    # PRIMARY KEY / FOREIGN KEY / UNIQUE / CHECK. A wrapped clause reads as a phantom column called
    # `REFERENCES` or `OR` — the blind spot `phase6_pipeline_instances` documents.
    "conflicts": """
        CREATE TABLE conflicts (
            tenant TEXT NOT NULL,
            conflict_id TEXT NOT NULL,
            -- ### THE DISPUTED FIELD: `(tenant, entity_ref, field)` is the natural key (entity §9) and,
            -- through the partial unique index below, the durable field condition. entity_ref is a
            -- load/carrier/movement projection (freight domain, P9+) and carries no FK — a FK into a
            -- table this unit does not own would be half of a machine it does not build.
            entity_ref TEXT NOT NULL,
            field TEXT NOT NULL,
            -- ### THE SIX CANONICAL KINDS, ENUMERATED INLINE ON THE COLUMN (entity §12, ADR-007 §5.1).
            -- One physical line so the readiness parser reads `kind` as NOT NULL and DDL introspection
            -- finds the vocabulary ON the column: no seventh kind. Interpolated from CONFLICT_KINDS.
            kind TEXT NOT NULL CHECK (kind IN (%(kinds)s)),
            -- ### THE FIVE CANONICAL STATES, ENUMERATED INLINE ON THE COLUMN (registry §4, M7). One
            -- physical line, like `kind`: no sixth state — no CANCELLED, no EXPIRED, no bare RESOLVED,
            -- no AUTO_RESOLVED. Interpolated from CONFLICT_STATES, the single source of truth.
            state TEXT NOT NULL CHECK (state IN (%(states)s)),
            version INTEGER NOT NULL,
            -- ### THE NAMED HUMAN who owns the Conflict FROM CREATION (entity §10/§16/§37, machine §5).
            -- NOT NULL, and FK-backed into the tenant's recorded humans below: an ownerless Conflict is
            -- structurally impossible, and `system` is not a human. The caller supplies the human; the
            -- machine never picks one, and a model actor may never be the owner.
            owner_id TEXT NOT NULL,
            -- Resolution basis (entity §11). rule_id is set on RESOLVED_BY_RULE (a REGISTERED, versioned
            -- rule id); decision_ref on RESOLVED_BY_HUMAN. No FK — M12 (rules) and the rules half of
            -- decision_ref are not built (task §3.9). decision_ref_kind is K-1's resolvable-kind
            -- discriminator; decision_human_id is the FK-backed ACTIVE human behind a human decision.
            rule_id TEXT,
            decision_ref TEXT,
            decision_ref_kind TEXT,
            decision_human_id TEXT,
            -- When it aged past the escalation threshold (CF-5), set from the durable-timer arrival.
            escalation_at TEXT,
            -- Optional operational exposure annotation (entity §11). Never a gate input.
            exposure TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            PRIMARY KEY (tenant, conflict_id),
            -- The owner and the decision-human are recorded humans of THIS tenant. Each on its OWN line
            -- so the readiness parser skips it as a non-column.
            FOREIGN KEY (tenant, owner_id) REFERENCES tenant_humans (tenant, human_id),
            FOREIGN KEY (tenant, decision_human_id) REFERENCES tenant_humans (tenant, human_id),
            -- The kind and state vocabulary CHECKs live INLINE on the columns above (declared once).
            CHECK (version >= 1),
            -- ### RESOLUTION HAS EXACTLY TWO WAYS AND NEVER A THIRD (entity §16, ADR-007 §5.3). A
            -- RESOLVED_BY_RULE carries a rule_id; a RESOLVED_BY_HUMAN carries a decision_ref; and a
            -- resolution carries AT MOST ONE basis, so a resolved conflict carries EXACTLY one. Each on
            -- ONE physical line.
            CHECK (state <> 'RESOLVED_BY_RULE' OR rule_id IS NOT NULL),
            CHECK (state <> 'RESOLVED_BY_HUMAN' OR decision_ref IS NOT NULL),
            CHECK (rule_id IS NULL OR decision_ref IS NULL),
            -- ### A HUMAN RESOLUTION NAMES THE ACTIVE HUMAN BEHIND ITS decision_ref (K-1, entity §35):
            -- "an authenticated human" is decoration while decision_human_id is free text, so the FK
            -- above plus this CHECK make a RESOLVED_BY_HUMAN with no named human impossible.
            CHECK (state <> 'RESOLVED_BY_HUMAN' OR decision_human_id IS NOT NULL),
            CHECK (decision_ref_kind IS NULL OR decision_ref_kind IN (%(decision_kinds)s)),
            CHECK (trim(conflict_id) <> ''),
            CHECK (trim(entity_ref) <> ''),
            CHECK (trim(field) <> ''),
            CHECK (trim(owner_id) <> ''),
            CHECK (trim(state) <> '')
        )""" % {
            "kinds": _KINDS_SQL, "states": _STATES_SQL, "decision_kinds": _DECISION_KINDS_SQL,
        },
    # THE CONFLICT PARTIES (entity §14, §31; F7 `parties[]`). One row per disagreeing claim/observation.
    "conflict_parties": """
        CREATE TABLE conflict_parties (
            tenant TEXT NOT NULL,
            party_id TEXT NOT NULL,
            conflict_id TEXT NOT NULL,
            -- ### THE POLYMORPHIC PARTY REFERENCE plus its kind discriminator (task §3.9). party_ref is
            -- the single source of truth (a claim id, an observation id, a readback token, a rule id, a
            -- system reading); claim_ref / observation_ref MIRROR it for the kinds whose table exists,
            -- so those two carry the FK and the CHECKs below keep them consistent with party_ref/kind.
            party_ref TEXT NOT NULL,
            party_kind TEXT NOT NULL CHECK (party_kind IN (%(party_kinds)s)),
            claim_ref TEXT,
            observation_ref TEXT,
            -- ### EACH PARTY CARRIES ITS OWN provenance_class, one of the canonical six (entity §13/§31,
            -- [C-7]), CARRIED and NEVER STRENGTHENED (ER-14, R-P2). An INFERRER_VS_OWNER conflict
            -- specifically records that one party is OWNER_ASSERTED — the evidence of why the inferrer
            -- did not overwrite it. Enumerated inline; the immutability trigger stops it being edited.
            provenance_class TEXT NOT NULL CHECK (provenance_class IN (%(prov)s)),
            -- What this party SAYS the disputed field is (the conflicting value). Never a gate input.
            stated_value TEXT,
            attach_seq INTEGER NOT NULL,
            attached_at TEXT NOT NULL,

            PRIMARY KEY (tenant, party_id),
            -- The party belongs to a conflict of THIS tenant (self-FK); a claim party is an
            -- identity_binding_claim of THIS tenant (M6); an observation party is an observation of THIS
            -- tenant (M5). Each on its OWN line so the readiness parser skips it as a non-column.
            FOREIGN KEY (tenant, conflict_id) REFERENCES conflicts (tenant, conflict_id),
            FOREIGN KEY (tenant, claim_ref) REFERENCES identity_binding_claims (tenant, binding_claim_id),
            FOREIGN KEY (tenant, observation_ref) REFERENCES observations (tenant, observation_id),
            -- ### THE DISCRIMINATOR IS CONSISTENT WITH THE FK-BACKED COLUMNS. A claim party sets
            -- claim_ref = party_ref (and nothing else); an observation party sets observation_ref =
            -- party_ref; a readback/rule/system party sets neither, and party_ref carries the token.
            -- Each on ONE physical line.
            CHECK (party_kind <> 'identity_binding_claim' OR claim_ref = party_ref),
            CHECK (party_kind = 'identity_binding_claim' OR claim_ref IS NULL),
            CHECK (party_kind <> 'observation' OR observation_ref = party_ref),
            CHECK (party_kind = 'observation' OR observation_ref IS NULL),
            CHECK (trim(party_id) <> ''),
            CHECK (trim(party_ref) <> ''),
            CHECK (attach_seq >= 1)
        )""" % {
            "party_kinds": _PARTY_KINDS_SQL, "prov": _PROV_SQL,
        },
}


P6CF_INDEXES: dict[str, str] = {
    # ### AT MOST ONE OPEN CONFLICT PER FIELD — A PARTIAL UNIQUE INDEX (entity §17, machine §17). It is
    # ALSO the durable field condition: "is (tenant, entity_ref, field) conflicting?" is a single
    # tenant-first read of this index. Under a race of concurrent detectors, one wins and every other
    # hits THIS index — the loser then ATTACHES its party to the existing conflict (CF-7). Drop the
    # UNIQUE, or drop the WHERE clause, and two OPEN conflicts fit one field: the whole unit switched off.
    "ix_conflicts_one_open_per_field":
        "CREATE UNIQUE INDEX ix_conflicts_one_open_per_field "
        "ON conflicts (tenant, entity_ref, field) WHERE state IN (%(open)s)" % {"open": _OPEN_SQL},
    # The human's queue: the open conflicts a human owns.
    "ix_conflicts_owner_queue":
        "CREATE INDEX ix_conflicts_owner_queue ON conflicts (tenant, state, owner_id)",
    # The field-condition read across every state (open and resolved history).
    "ix_conflicts_entity_field":
        "CREATE INDEX ix_conflicts_entity_field ON conflicts (tenant, entity_ref, field, state)",
    # The parties of one conflict, in attach order.
    "ix_conflict_parties_by_conflict":
        "CREATE INDEX ix_conflict_parties_by_conflict "
        "ON conflict_parties (tenant, conflict_id, attach_seq)",
    # ### ONE PARTY REFERENCE PER CONFLICT — a second detection of the SAME party attaches nothing new
    # (entity §33, GR-4). A partial-unique this is not: it is a full unique on (tenant, conflict_id,
    # party_ref), so a redelivered detection is refused at the database, not only short-circuited above.
    "ix_conflict_parties_dedup":
        "CREATE UNIQUE INDEX ix_conflict_parties_dedup "
        "ON conflict_parties (tenant, conflict_id, party_ref)",
}

# Nothing from an earlier phase is replaced. Declared so a future replacement has somewhere to go.
P6CF_REPLACED_INDEXES: tuple[str, ...] = ()


P6CF_TRIGGERS: dict[str, str] = {
    # ### OCC ON THE CONFLICT (GR-3, C-10, machine §17). A state transition advances version by exactly
    # one; a state change that leaves version standing is two transitions claiming one version. (A CF-7
    # party attach does not change state, so it may advance version freely — this fires only on a state
    # change that fails to advance it.)
    "trg_conflicts_version_advances_on_state_change": f"""
        CREATE TRIGGER trg_conflicts_version_advances_on_state_change
        BEFORE UPDATE ON conflicts
        WHEN NEW.state <> OLD.state AND NEW.version <> OLD.version + 1
        BEGIN SELECT RAISE(ABORT, '{VERSION_ABORT}'); END""",
    # ### THE IDENTITY OF THE CONFLICT IS IMMUTABLE. Editing the entity, the field, the kind or
    # created_at would retarget or relaunder a recorded disagreement in place — the field it froze would
    # no longer be the field it named.
    "trg_conflicts_identity_immutable": f"""
        CREATE TRIGGER trg_conflicts_identity_immutable
        BEFORE UPDATE OF tenant, conflict_id, entity_ref, field, kind, created_at
        ON conflicts
        BEGIN SELECT RAISE(ABORT, '{IDENTITY_ABORT}'); END""",
    # ### NO DELETION, EVER, AND NO EXPIRY (entity §26/§28/§29, C-9). Retention is permanent; a conflict
    # ages and escalates but never times out into deletion.
    "trg_conflicts_no_delete": f"""
        CREATE TRIGGER trg_conflicts_no_delete
        BEFORE DELETE ON conflicts
        BEGIN SELECT RAISE(ABORT, '{DELETE_ABORT}'); END""",
    # ### A PARTY provenance_class NEVER MUTATES (ER-14, R-P2). Carried at detection, never strengthened.
    "trg_conflict_parties_provenance_immutable": f"""
        CREATE TRIGGER trg_conflict_parties_provenance_immutable
        BEFORE UPDATE OF provenance_class ON conflict_parties
        BEGIN SELECT RAISE(ABORT, '{PARTY_PROVENANCE_ABORT}'); END""",
    # ### A PARTY IS NEVER DELETED — it is the evidence a rebuild folds (entity §28/§29, F7).
    "trg_conflict_parties_no_delete": f"""
        CREATE TRIGGER trg_conflict_parties_no_delete
        BEFORE DELETE ON conflict_parties
        BEGIN SELECT RAISE(ABORT, '{PARTY_DELETE_ABORT}'); END""",
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


def create_phase6_conflicts_schema(conn: sqlite3.Connection, *, now: str) -> list[str]:
    """Create whatever M7 structure is missing. Idempotent; returns what it did.

    Callable on a fresh canonical database and on an already-migrated one. Either way the resulting
    structure is byte-identical, because there is only one text. Built AFTER M6
    (`identity_binding_claims` FK), M5 (`observations` FK) and M1 (`tenant_humans` FK), which is why
    `schema.py` orders it last of the P6 units.
    """
    performed: list[str] = []
    present = _tables(conn)
    for name in (*P6CF_TENANT_TABLES, *P6CF_EXEMPT_TABLES):
        if name not in present:
            conn.execute(P6CF_TARGET_SCHEMA[name])
            performed.append(f"create-table:{name}")
    existing = _indexes(conn)
    for name, ddl in P6CF_INDEXES.items():
        if name not in existing:
            conn.execute(ddl)
            performed.append(f"create-index:{name}")
    for stale in P6CF_REPLACED_INDEXES:
        if stale in _indexes(conn):
            conn.execute(f"DROP INDEX {stale}")
            performed.append(f"drop-index:{stale}")
    existing_triggers = _triggers(conn)
    for name, ddl in P6CF_TRIGGERS.items():
        if name not in existing_triggers:
            conn.execute(ddl)
            performed.append(f"create-trigger:{name}")
    # NO VERSION STAMP HERE — marker-last, like every phase. A stamp on a half-migrated database is how
    # a missing trigger goes unnoticed.
    conn.commit()
    return performed


def stamp_phase6_conflicts_version(conn: sqlite3.Connection, *, now: str) -> None:
    """Record the M7 marker — callable ONLY once readiness holds. Marker-last, like every phase."""
    problems = phase6_conflicts_readiness_problems(conn)
    if problems:
        raise RuntimeError(
            f"refusing to stamp {P6CF_SCHEMA_VERSION} on a database that is NOT ready: "
            + "; ".join(problems)
        )
    if "schema_migrations" in _tables(conn):
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration, step, applied_at, detail) "
            "VALUES (?,?,?,?)",
            (MIGRATION_ID, f"version:{P6CF_SCHEMA_VERSION}", now,
             "the Conflict: one conflicts row per disputed field, tenant-first, five states, a named "
             "ACTIVE human owner from creation, at most one OPEN conflict per field (the partial unique "
             "index that is also the durable field condition), resolution by a registered rule id or an "
             "authenticated decision_ref and never a third way, permanent retention, no expiry; readiness "
             "proven"),
        )
        conn.commit()


def phase6_conflicts_readiness_problems(conn: sqlite3.Connection) -> list[str]:
    """Every reason this database cannot carry Conflicts safely. Empty == ready.

    Structural, like the P2/P3/P5/M1..M6 oracles it extends. The partial unique index and the
    immutability/no-delete triggers are verified PRESENT because a `conflicts` table without them is an
    ordinary table with an aspirational comment: two detectors could both open one field, a party's
    provenance could be laundered, a resolved conflict could be deleted, and a state transition could
    stand the version still.
    """
    problems: list[str] = []
    present = _tables(conn)
    for table in (*P6CF_TENANT_TABLES, *P6CF_EXEMPT_TABLES):
        if table not in present:
            problems.append(
                f"required Phase-6 table {table!r} is missing: run the {MIGRATION_ID} migration"
            )
    if not all(t in present for t in P6CF_TENANT_TABLES):
        return problems

    live_triggers = _triggers(conn)
    missing_triggers = sorted(t for t in P6CF_TRIGGERS if t not in live_triggers)
    if missing_triggers:
        problems.append(
            f"Conflict invariant triggers missing: {missing_triggers}. Without them a conflict could be "
            f"deleted (an evidence chain erased), a state transition could stand the version still (a "
            f"lost update), a party provenance could be strengthened (a laundered guess), or the "
            f"identity of the disagreement could be edited in place [entity §13/§17/§26/§28, GR-3, "
            f"ER-14, C-9]."
        )
    live_indexes = _indexes(conn)
    for name in P6CF_INDEXES:
        if name not in live_indexes:
            problems.append(f"required Phase-6 index {name!r} is missing")
    for stale in P6CF_REPLACED_INDEXES:
        if stale in live_indexes:
            problems.append(f"replaced index {stale!r} is still present")

    # ### THE ONE-OPEN-CONFLICT-PER-FIELD INDEX, READ OUT OF THE LIVE DATABASE RATHER THAN ASSUMED FROM
    # ITS NAME. An index called `..._one_open_per_field` that is not UNIQUE, or that has lost its
    # `WHERE state IN (RAISED,OPEN,ESCALATED)` clause, is the never-silently-choose defence switched off
    # with the sign left up: two OPEN conflicts for one field would become insertable.
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name = ?",
        ("ix_conflicts_one_open_per_field",),
    ).fetchone()
    if row is not None:
        sql = " ".join((row[0] or "").split()).upper().replace(", ", ",")
        if "UNIQUE" not in sql:
            problems.append(
                "ix_conflicts_one_open_per_field is not UNIQUE: two OPEN conflicts for one field would "
                "be insertable, and 'at most one open conflict per field' (entity §17) would be a "
                "convention, not a constraint — Neyma would silently hold two disagreements about one "
                "value."
            )
        expected_where = ("WHERE STATE IN (" + ",".join(f"'{s}'" for s in OPEN_CONFLICT_STATES)
                          + ")").upper()
        if expected_where not in sql:
            problems.append(
                "ix_conflicts_one_open_per_field has lost its `WHERE state IN "
                "('RAISED','OPEN','ESCALATED')` clause: the partial index is what allows many resolved "
                "conflicts per field in history while permitting at most one OPEN (entity §17/§24)."
            )
        for column in ("TENANT", "ENTITY_REF", "FIELD"):
            if column not in sql:
                problems.append(
                    f"ix_conflicts_one_open_per_field does not cover {column!r}: the open conflict is "
                    f"unique per (tenant, entity_ref, field), and dropping a member widens or narrows "
                    f"what counts as 'the same field' — a dropped tenant is cross-tenant coalescing."
                )

    # ### THE CHECKS AND THE VOCABULARIES, READ OUT OF THE conflicts DDL. A CHECK the migration intended
    # but a live database does not carry is the invariant switched off.
    ddl_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='conflicts'").fetchone()
    ddl = " ".join((ddl_row[0] if ddl_row else "" or "").split()).upper()
    compact = ddl.replace(", ", ",")

    expected_states = ("STATE IN (" + ",".join(f"'{s}'" for s in CONFLICT_STATES) + ")").upper()
    if expected_states not in compact:
        problems.append(
            "conflicts does not enumerate the five canonical states inline on the state column "
            "(registry §4, M7): without it a sixth state — a CANCELLED, an EXPIRED or a bare RESOLVED — "
            "would be writable, and entity §26/§28 and machine §14 say none exists."
        )
    expected_kinds = ("KIND IN (" + ",".join(f"'{k}'" for k in CONFLICT_KINDS) + ")").upper()
    if expected_kinds not in compact:
        problems.append(
            "conflicts does not enumerate the six canonical kinds inline on the kind column (entity "
            "§12, ADR-007 §5.1): without it a seventh kind would be writable, and the closed set is what "
            "the ConflictRaised contract also refuses."
        )
    for clause, why in (
        ("STATE <> 'RESOLVED_BY_RULE' OR RULE_ID IS NOT NULL",
         "a RESOLVED_BY_RULE conflict must carry a rule_id (entity §16): resolution by a registered "
         "rule with an id is one of only two ways to close, and the other is a human decision_ref"),
        ("STATE <> 'RESOLVED_BY_HUMAN' OR DECISION_REF IS NOT NULL",
         "a RESOLVED_BY_HUMAN conflict must carry a decision_ref (entity §16): an authenticated human "
         "decision is one of only two ways to close a conflict"),
        ("RULE_ID IS NULL OR DECISION_REF IS NULL",
         "a resolution carries AT MOST ONE basis (ADR-007 §5.3): rule_id AND decision_ref together is "
         "two answers to a one-of, and combined with the two state CHECKs a resolved conflict must "
         "carry EXACTLY one"),
        ("STATE <> 'RESOLVED_BY_HUMAN' OR DECISION_HUMAN_ID IS NOT NULL",
         "a RESOLVED_BY_HUMAN conflict must name the ACTIVE human behind its decision_ref (K-1, entity "
         "§35): 'an authenticated human' is decoration while decision_human_id is a free-text column"),
    ):
        if clause not in compact:
            problems.append(f"conflicts does not CHECK: {clause.lower()} — {why}.")

    # ### owner_id IS NOT NULL FROM CREATION (entity §37). An ownerless Conflict is structurally
    # impossible: the column is NOT NULL and FK-backed. Read the NOT NULL back rather than trust it.
    owner_notnull = any(
        r[1] == "owner_id" and r[3] == 1
        for r in conn.execute("PRAGMA table_info(conflicts)").fetchall())
    if not owner_notnull:
        problems.append(
            "conflicts.owner_id is not NOT NULL: an ownerless Conflict would be insertable, and entity "
            "§37 names it a structurally impossible state — the owner is assigned at creation."
        )

    # ### THE PARTY provenance CHECK, READ BACK: each party carries one of the six canonical classes.
    party_ddl_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='conflict_parties'").fetchone()
    party_ddl = " ".join((party_ddl_row[0] if party_ddl_row else "" or "").split()).upper()
    party_compact = party_ddl.replace(", ", ",")
    expected_prov = ("PROVENANCE_CLASS IN (" + ",".join(f"'{p}'" for p in PROVENANCE_CLASSES)
                     + ")").upper()
    if expected_prov not in party_compact:
        problems.append(
            "conflict_parties does not enumerate the six canonical provenance classes inline on the "
            "provenance_class column ([C-7], entity §13/§31): each party carries its OWN provenance, "
            "carried and never strengthened (ER-14)."
        )
    expected_party_kinds = ("PARTY_KIND IN (" + ",".join(f"'{k}'" for k in PARTY_KINDS) + ")").upper()
    if expected_party_kinds not in party_compact:
        problems.append(
            "conflict_parties does not enumerate the party-kind discriminator inline on the party_kind "
            "column (task §3.9): the reference is polymorphic and its kind is what tells a reader which "
            "table (if any) it points at."
        )

    for referent in P6CF_CONFLICT_REFERENTS:
        if referent not in _referents(conn, "conflicts"):
            problems.append(
                f"conflicts declares no foreign key into {referent!r}: the owner and the decision-human "
                f"are recorded ACTIVE humans of THIS tenant (M1's precedent) — 'a named human owner' is "
                f"decoration while owner_id is a free-text column (entity §18)."
            )
    for referent in P6CF_PARTY_REFERENTS:
        if referent not in _referents(conn, "conflict_parties"):
            problems.append(
                f"conflict_parties declares no foreign key into {referent!r}: a party belongs to a "
                f"conflict of this tenant (self-FK), a claim party is an identity_binding_claim (M6) and "
                f"an observation party is an observation (M5) — 'a named party' is decoration while "
                f"these are free-text columns (entity §18, task §3.9)."
            )
    return problems
