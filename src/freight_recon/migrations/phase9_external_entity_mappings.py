"""### P9 — THE EXTERNAL ENTITY MAPPING (domain entity #38): the one durable table the freight-domain
spine adds, and the ONLY way an outside system's record enters the canonical model.

### WHAT THIS TABLE IS. One row says: *"within THIS brokerage, the identifier `external_id` of kind
`external_id_kind` in outside system `external_system` refers to the Neyma entity
`(neyma_entity_type, neyma_entity_id)`"*. A Brokerage Load keeps its TMS load number, its customer PO,
its carrier PRO and its BOL number as FOUR rows pointing at ONE canonical id — and none of those
strings is ever the canonical identity.

### WHAT IT IS NOT. It is not a domain entity (there is no "TMS Load" entity — domain-entities/
03-load-family.md), and it is not an Identity Binding Claim (M6 binds an ARTIFACT to an entity; this
binds an ENTITY to its outside names).

### THE FOUR RULES THE STRUCTURE ENFORCES, RATHER THAN DOCUMENTS.

  * **Tenant-first.** `tenant` is the first column and the first PK member, and every foreign key is
    composite on `tenant`. The same `LD-48219` in two brokerages is two unrelated rows; a mapping
    cannot cite another tenant's observation or another tenant's human, because the composite FK has
    no way to spell it [C-1, CD-19].

  * **An external id is trusted only within `(tenant, external_system, external_id_kind)`.** That
    triple plus the id is the lookup key; nothing resolves across systems or across tenants.

  * **One reference may point at several entities, and that is recorded as AMBIGUITY, not resolved.**
    The uniqueness is on the full binding (reference + entity), never on the reference alone. A
    customer PO that covers two loads is two ACTIVE rows; a lookup returns both and the caller fails
    closed to a human. Neyma never force-binds the closest candidate (GR-8).

  * **Corrections preserve history.** A row is never deleted and its content is never edited. The
    only legal UPDATE retires an ACTIVE row to SUPERSEDED (it was true when made; the outside system
    renumbered) or CORRECTED (it was wrong), and the replacement is a NEW row whose
    `replaces_mapping_id` points back [CD-6, CD-7, GR-12].

### NO MODEL-ORIGINATED MAPPING CAN EXIST HERE. `provenance_class` admits the four classes a
deterministic or human act produces and neither model class. A model-proposed mapping is a CANDIDATE,
and candidates are not stored in the table an exact lookup reads — the boundary where probabilistic
candidate generation will later attach is `freight_domain/entity_mapping.py`, not this table.

### SHIPS DARK. Only the P9 freight-domain spine reads or writes this table, and nothing on a live
path reaches the spine. It enables no external effect and grants no autonomy.
"""

from __future__ import annotations

import sqlite3

MIGRATION_ID = "phase9_external_entity_mappings"
P9XM_SCHEMA_VERSION = "phase9-external-entity-mappings-1"

# Tenant-owned. A mapping is one brokerage's knowledge of one outside system's naming [C-1].
P9XM_TENANT_TABLES: tuple[str, ...] = ("external_entity_mappings",)

# Nothing tenant-exempt. Stated rather than omitted, so a future addition must defend its exemption.
P9XM_EXEMPT_TABLES: tuple[str, ...] = ()

# The referents the readiness oracle checks by name: the Observation the mapping was read from, the
# human who asserted or corrected it, and the prior mapping it replaces.
P9XM_REQUIRED_REFERENTS: tuple[str, ...] = (
    "observations", "tenant_humans", "external_entity_mappings",
)

#: The three states. ACTIVE resolves; SUPERSEDED was true when made; CORRECTED was wrong. Neither
#: retired state ever resolves an exact lookup.
P9XM_STATES: tuple[str, ...] = ("ACTIVE", "SUPERSEDED", "CORRECTED")
P9XM_RETIRED_STATES: tuple[str, ...] = ("SUPERSEDED", "CORRECTED")

#: The provenance a mapping may carry. MODEL_EXTRACTED and MODEL_INFERRED are deliberately absent: a
#: model-originated mapping is a candidate, never a row an exact lookup can return.
P9XM_ALLOWED_PROVENANCE: tuple[str, ...] = (
    "SYSTEM_IMPORTED", "OWNER_ASSERTED", "LINKER_INFERRED", "RECONCILED",
)

_STATES_SQL = ",".join(f"'{s}'" for s in P9XM_STATES)
_PROVENANCE_SQL = ",".join(f"'{p}'" for p in P9XM_ALLOWED_PROVENANCE)

# The exact abort texts, WITHOUT apostrophes: they are interpolated into single-quoted SQL literals
# inside RAISE(ABORT, ...); an apostrophe would terminate the literal.
MAPPING_IMMUTABLE_ABORT = (
    "an external entity mapping is immutable [CD-6/CD-7, GR-12]: its content is never edited and a "
    "retired mapping never returns to ACTIVE. The only legal change retires an ACTIVE row to "
    "SUPERSEDED or CORRECTED; a changed binding is a NEW row that names the one it replaces"
)
MAPPING_DELETE_ABORT = (
    "an external entity mapping is never deleted [CD-7, C-9]: the history of what an outside "
    "reference was believed to mean is what a later correction is explained against"
)

P9XM_TARGET_SCHEMA: dict[str, str] = {
    # Every column on its OWN line and every FOREIGN KEY / CHECK / PRIMARY KEY on its OWN physical
    # line, and every multi-condition CHECK on ONE physical line: `schema._canonical_columns` parses
    # this DDL line by line and reads only the first token of a line as a column.
    "external_entity_mappings": f"""
        CREATE TABLE external_entity_mappings (
            tenant TEXT NOT NULL,
            mapping_id TEXT NOT NULL,
            -- The canonical Neyma entity. The id is Neyma-minted and opaque; no outside string is it.
            neyma_entity_type TEXT NOT NULL,
            neyma_entity_id TEXT NOT NULL,
            -- The outside name. Trusted only within this tenant, this system and this id kind.
            external_system TEXT NOT NULL,
            external_id_kind TEXT NOT NULL,
            external_id TEXT NOT NULL,
            -- HOW the mapping came to be believed. Runtime-assigned; never a model class.
            provenance_class TEXT NOT NULL CHECK (provenance_class IN ({_PROVENANCE_SQL})),
            state TEXT NOT NULL CHECK (state IN ({_STATES_SQL})),
            -- The Observation this mapping was read from. A mapping from nowhere has no lineage.
            source_observation_id TEXT NOT NULL,
            decision_ref TEXT,
            decision_human_id TEXT,
            -- The prior mapping this row replaces, when it is a correction or a supersession.
            replaces_mapping_id TEXT,
            retired_reason TEXT,
            created_at TEXT NOT NULL,
            retired_at TEXT,
            PRIMARY KEY (tenant, mapping_id),
            FOREIGN KEY (tenant, source_observation_id) REFERENCES observations (tenant, observation_id),
            FOREIGN KEY (tenant, decision_human_id) REFERENCES tenant_humans (tenant, human_id),
            FOREIGN KEY (tenant, replaces_mapping_id) REFERENCES external_entity_mappings (tenant, mapping_id),
            CHECK (provenance_class <> 'OWNER_ASSERTED' OR (decision_ref IS NOT NULL AND decision_human_id IS NOT NULL)),
            CHECK (state = 'ACTIVE' OR (retired_at IS NOT NULL AND retired_reason IS NOT NULL)),
            CHECK (state <> 'ACTIVE' OR retired_at IS NULL),
            CHECK (trim(mapping_id) <> ''),
            CHECK (trim(neyma_entity_type) <> ''),
            CHECK (trim(neyma_entity_id) <> ''),
            CHECK (trim(external_system) <> ''),
            CHECK (trim(external_id_kind) <> ''),
            CHECK (trim(external_id) <> ''),
            CHECK (trim(source_observation_id) <> '')
        )""",
}

P9XM_INDEXES: dict[str, str] = {
    # ### ONE ACTIVE ROW PER (REFERENCE, ENTITY) — NOT PER REFERENCE. Uniqueness on the reference
    # alone would force a PO that legitimately covers two loads to pick one; this index forbids only
    # the duplicate of an identical binding, so ambiguity stays representable.
    "ix_xmap_one_active_per_binding": (
        "CREATE UNIQUE INDEX ix_xmap_one_active_per_binding "
        "ON external_entity_mappings (tenant, external_system, external_id_kind, external_id, "
        "neyma_entity_type, neyma_entity_id) WHERE state = 'ACTIVE'"
    ),
    # The exact lookup: tenant first, then the reference. A cross-tenant read cannot use this index
    # without naming a tenant, and there is no index that leads with the reference.
    "ix_xmap_tenant_reference": (
        "CREATE INDEX ix_xmap_tenant_reference "
        "ON external_entity_mappings (tenant, external_system, external_id_kind, external_id, state)"
    ),
    # The reverse read: every outside name one canonical entity carries.
    "ix_xmap_tenant_entity": (
        "CREATE INDEX ix_xmap_tenant_entity "
        "ON external_entity_mappings (tenant, neyma_entity_type, neyma_entity_id, state)"
    ),
}

P9XM_REPLACED_INDEXES: tuple[str, ...] = ()

P9XM_TRIGGERS: dict[str, str] = {
    # The ONLY legal UPDATE: an ACTIVE row retiring, with every content column unchanged. `IS NOT`
    # rather than `<>` so a NULL-to-value edit of a nullable column is caught too.
    "trg_xmap_immutable": f"""
        CREATE TRIGGER trg_xmap_immutable
        BEFORE UPDATE ON external_entity_mappings
        WHEN OLD.state <> 'ACTIVE'
          OR NEW.state = 'ACTIVE'
          OR NEW.tenant IS NOT OLD.tenant
          OR NEW.mapping_id IS NOT OLD.mapping_id
          OR NEW.neyma_entity_type IS NOT OLD.neyma_entity_type
          OR NEW.neyma_entity_id IS NOT OLD.neyma_entity_id
          OR NEW.external_system IS NOT OLD.external_system
          OR NEW.external_id_kind IS NOT OLD.external_id_kind
          OR NEW.external_id IS NOT OLD.external_id
          OR NEW.provenance_class IS NOT OLD.provenance_class
          OR NEW.source_observation_id IS NOT OLD.source_observation_id
          OR NEW.decision_ref IS NOT OLD.decision_ref
          OR NEW.decision_human_id IS NOT OLD.decision_human_id
          OR NEW.replaces_mapping_id IS NOT OLD.replaces_mapping_id
          OR NEW.created_at IS NOT OLD.created_at
        BEGIN SELECT RAISE(ABORT, '{MAPPING_IMMUTABLE_ABORT}'); END""",
    "trg_xmap_no_delete": f"""
        CREATE TRIGGER trg_xmap_no_delete
        BEFORE DELETE ON external_entity_mappings
        BEGIN SELECT RAISE(ABORT, '{MAPPING_DELETE_ABORT}'); END""",
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


def create_phase9_external_entity_mappings_schema(conn: sqlite3.Connection, *, now: str) -> list[str]:
    """Create whatever mapping structure is missing. Idempotent; returns what it did.

    Callable on a fresh canonical database and on an already-migrated one. Either way the resulting
    structure is byte-identical, because there is only one text. Built AFTER M5 (`observations`, the
    `source_observation_id` referent) and M1's `tenant_humans`.
    """
    performed: list[str] = []
    present = _tables(conn)
    for name in (*P9XM_TENANT_TABLES, *P9XM_EXEMPT_TABLES):
        if name not in present:
            conn.execute(P9XM_TARGET_SCHEMA[name])
            performed.append(f"create-table:{name}")
    existing = _indexes(conn)
    for name, ddl in P9XM_INDEXES.items():
        if name not in existing:
            conn.execute(ddl)
            performed.append(f"create-index:{name}")
    for stale in P9XM_REPLACED_INDEXES:
        if stale in _indexes(conn):
            conn.execute(f"DROP INDEX {stale}")
            performed.append(f"drop-index:{stale}")
    existing_triggers = _triggers(conn)
    for name, ddl in P9XM_TRIGGERS.items():
        if name not in existing_triggers:
            conn.execute(ddl)
            performed.append(f"create-trigger:{name}")
    # NO VERSION STAMP HERE — marker-last. A stamp written by the builder appears on a half-migrated
    # database the moment a later step fails, which is how a missing trigger goes unnoticed.
    conn.commit()
    return performed


def stamp_phase9_external_entity_mappings_version(conn: sqlite3.Connection, *, now: str) -> None:
    """Record the mapping marker — callable ONLY once readiness holds. Marker-last, like every phase."""
    problems = phase9_external_entity_mappings_readiness_problems(conn)
    if problems:
        raise RuntimeError(
            f"refusing to stamp {P9XM_SCHEMA_VERSION} on a database that is NOT ready: "
            + "; ".join(problems)
        )
    if "schema_migrations" in _tables(conn):
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration, step, applied_at, detail) "
            "VALUES (?,?,?,?)",
            (MIGRATION_ID, f"version:{P9XM_SCHEMA_VERSION}", now,
             "External Entity Mapping: tenant-first binding of a canonical Neyma entity to its "
             "outside references, trusted only within (tenant, system, id kind); ambiguity is "
             "representable, corrections retire and never edit or delete, and no model-originated "
             "mapping can exist; readiness proven"),
        )
        conn.commit()


def phase9_external_entity_mappings_readiness_problems(conn: sqlite3.Connection) -> list[str]:
    """Every reason this database cannot carry a trustworthy external entity mapping. Empty == ready.

    Structural, like the P2..P8 oracles it extends. The immutability and no-delete triggers are
    verified PRESENT because a mapping table without them is an ordinary table with an aspirational
    comment: a load's TMS number could be quietly re-pointed at another load, and the document that
    arrived under the old number would move with it and leave no trace [CD-6].
    """
    problems: list[str] = []
    present = _tables(conn)
    for table in (*P9XM_TENANT_TABLES, *P9XM_EXEMPT_TABLES):
        if table not in present:
            problems.append(
                f"required Phase-9 table {table!r} is missing: run the {MIGRATION_ID} migration"
            )
    if not all(t in present for t in P9XM_TENANT_TABLES):
        return problems

    live_triggers = _triggers(conn)
    missing_triggers = sorted(t for t in P9XM_TRIGGERS if t not in live_triggers)
    if missing_triggers:
        problems.append(
            f"external-entity-mapping invariant triggers missing: {missing_triggers}. Without them a "
            f"mapping could be rewritten or deleted, and a document bound through it would move "
            f"loads with no history [CD-6/CD-7]."
        )
    live_indexes = _indexes(conn)
    for name in P9XM_INDEXES:
        if name not in live_indexes:
            problems.append(f"required Phase-9 index {name!r} is missing")

    cols = _columns(conn, "external_entity_mappings")
    for required in ("tenant", "mapping_id", "neyma_entity_type", "neyma_entity_id",
                     "external_system", "external_id_kind", "external_id", "provenance_class",
                     "state", "source_observation_id", "replaces_mapping_id", "created_at"):
        if required not in cols:
            problems.append(f"external_entity_mappings is missing the {required!r} column")

    referents = _referents(conn, "external_entity_mappings")
    for referent in P9XM_REQUIRED_REFERENTS:
        if referent not in referents:
            problems.append(
                f"external_entity_mappings does not reference {referent!r}: a mapping whose source "
                f"observation, asserting human or replaced predecessor is not tenant-consistent "
                f"could cite another brokerage's record [C-1]"
            )
    return problems
