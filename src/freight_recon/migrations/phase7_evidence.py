"""Phase 7 — Evidence: the retained artifact, and the span within it, that a human would look at to
check a claim. Two tables, `evidence` and `evidence_spans`, that make "provenance survives" (I5) and
"explainable to an angry person" (I3) something a database ENFORCES.

WHAT THIS IS, IN FREIGHT TERMS

    A POD PDF arrives and is retained EXACTLY as its bytes. A model reads "4471" off page 1 and
    records WHERE it read it (the span). The identical PDF is delivered again from a second mailbox
    an hour later; it is ONE Evidence, not two — content addressing makes the same bytes one artifact
    (entity 08-evidence sec 21/33). Later a revised POD arrives with different bytes: that is a NEW
    Evidence with a new digest that may SUPERSEDE the old one, and the old is RETAINED because a claim
    may have rested on it (entity sec 24/28).

WHY EVIDENCE IS DATA AND NEVER A CLAIM

    ### Evidence is the ANCHOR of provenance, not a bearer of it (entity sec 13/35, ADR-002 sec 2.3).
    A document may EVIDENCE a claim; it may never MAKE one, authorize an effect, or set provenance
    (M-66). So `evidence` carries NO `provenance_class` column and NO state machine: it is an
    immutable retained artifact, written once, never edited (entity sec 6/10/12/20/22). The
    provenance_class that says HOW a value came to be believed lives on the CLAIM that points at the
    span (M6's `identity_binding_claims`, whose `ck_ibc_model_extracted_needs_span` already REQUIRES a
    span for a MODEL_EXTRACTED claim — the span this table now stores).

WHY CONTENT ADDRESSING IS THE IDENTITY

    `content_digest` is a RUNTIME sha256 of the stored bytes (never taken from inbound content, R-P1
    analog); `UNIQUE (tenant, content_digest)` makes "identical bytes are one Evidence" a database
    constraint that genuinely SERIALIZES concurrent retention (entity sec 17/33). The digest is
    verified against the bytes ON WRITE by the Evidence Store — a row whose stored bytes do not match
    its digest is a structurally impossible state (entity sec 16/37/43(b)).

WHY IMMUTABILITY IS A TRIGGER, NOT A COMMENT

    `content_digest`, `content_ref`, `media_type`, `source_observation_id` and the identity columns
    never mutate — a BEFORE UPDATE trigger refuses it, the way `observations` refuses an edit of
    `raw_value` (entity sec 16/22, C-8). A span, once written, is an annotation of WHERE a claim
    points and is itself immutable. Neither row is ever deleted: Evidence is never deleted while any
    claim or effect rests on it (entity sec 26/28), so the fail-closed default is a no-delete trigger.
    The ONLY mutable columns on `evidence` are the `illegible` flag (a legibility observation) and
    `superseded_by` (a supersession link) — both annotations, neither a content edit.

WHAT IS DELIBERATELY NOT HERE

    No `provenance_class` (Evidence sets none), no state/lifecycle enum (entity sec 12/20), no
    `commit_key` (Evidence evidences a claim and never makes one, so it is not answerable to the
    effect ledger and `schema._second_ledger_problems` does not reach it), no EXPIRED/DELETED and no
    retention sweep (entity sec 26/28). No new canonical event is minted: the Evidence lifecycle
    events (EvidenceRetained/EvidenceSuperseded/EvidenceIllegible, entity sec 31) would extend the
    frozen 105-event registry, which is a separate founder-authorized decision; this layer ships dark
    and emits none.

FRESH == MIGRATED, SHIPS DARK

    `create_canonical_schema` builds these tables directly; a database reached by
    `phase2_tenant_first.migrate` reaches the same shape through `create_phase7_evidence_schema`.
    Nothing routes production traffic through the Evidence Store; `evidence.py` is the only non-test
    module that reads it, and only `scripts/probe_phase7_evidence.py` imports the store.
"""

from __future__ import annotations

import sqlite3

MIGRATION_ID = "phase7_evidence"
P7EV_SCHEMA_VERSION = "phase7-evidence-1"

# Tenant-owned. Evidence may contain sensitive customer documents; the same digest in two tenants is
# two isolated artifacts [C-1], and there is no honest cross-tenant reading of a retained document
# (entity sec 7/35, adversarial test test_cross_tenant_evidence_isolation).
P7EV_TENANT_TABLES: tuple[str, ...] = ("evidence", "evidence_spans")

# Nothing tenant-exempt. Stated rather than omitted, so a future addition must defend its exemption.
P7EV_EXEMPT_TABLES: tuple[str, ...] = ()

# The one referent the readiness oracle checks by name: an Evidence enters via the Observation that
# retained it (entity sec 10 `source_observation_id`, sec 14 "Observation 1 : N Evidence").
P7EV_REQUIRED_REFERENTS: tuple[str, ...] = ("observations",)

# The exact abort texts, WITHOUT apostrophes: they are interpolated into single-quoted SQL literals
# inside RAISE(ABORT, ...); an apostrophe would terminate the literal. Named here and matched by
# `evidence.py` when it classifies an IntegrityError.
CONTENT_IMMUTABLE_ABORT = (
    "evidence content is immutable [entity 08-evidence sec 6/10/16/22, C-8]: an Evidence is a "
    "content-addressed retained artifact, written once and never edited. A revised document is a NEW "
    "Evidence with a new digest that may supersede this one; the bytes behind this row never change"
)
SPAN_IMMUTABLE_ABORT = (
    "an evidence span is immutable [entity 08-evidence sec 22]: a span records WHERE a claim points "
    "into an artifact and is an annotation, never an edit. A different region is a new span, not a "
    "rewrite of this one"
)
EVIDENCE_DELETE_ABORT = (
    "evidence is never deleted [entity 08-evidence sec 26/28]: it is retained while any claim or "
    "effect rests on it, so the fact stays defensible years later. A lost artifact BLOCKS the "
    "consequential action that rests on it; it is never quietly removed"
)
SPAN_DELETE_ABORT = (
    "an evidence span is never deleted [entity 08-evidence sec 26/28]: the region a claim points at "
    "must stay walkable for as long as the claim stands"
)


P7EV_TARGET_SCHEMA: dict[str, str] = {
    # THE EVIDENCE (`entities/08-evidence.md`, ADR-007 sec 3, ADR-002 sec 2.1 concern 1/5).
    #
    # Every column on its OWN line and every FOREIGN KEY / CHECK on its OWN line, and every
    # multi-condition CHECK on ONE physical line: `schema._canonical_columns` parses this DDL line by
    # line, reads only the first token of a line as a column, and skips a line that STARTS with
    # PRIMARY KEY / FOREIGN KEY / UNIQUE / CHECK. A wrapped clause reads as a column called
    # `REFERENCES` or `AND` — the blind spot phase6 migrations document.
    "evidence": """
        CREATE TABLE evidence (
            tenant TEXT NOT NULL,
            evidence_id TEXT NOT NULL,
            -- ### CONTENT ADDRESSING. content_digest is a RUNTIME sha256 of the stored bytes (never
            -- taken from inbound content); content_ref is the content-addressed pointer to those
            -- bytes. Both immutable by trigger. Identical bytes collide on the UNIQUE index below and
            -- deduplicate to ONE Evidence (entity sec 8/9/13/17/21/33).
            content_digest TEXT NOT NULL,
            content_ref TEXT NOT NULL,
            media_type TEXT NOT NULL,
            -- How this artifact entered: the Observation that retained it (entity sec 10/14). FK below.
            source_observation_id TEXT NOT NULL,
            -- ### ANNOTATIONS, NOT CONTENT (the only mutable columns). illegible is a legibility
            -- observation (entity sec 11/36 — an illegible artifact escalates and BLOCKS, it does not
            -- degrade to best-available); superseded_by links to the newer artifact (entity sec 24),
            -- the old being RETAINED. Neither changes the bytes.
            illegible INTEGER NOT NULL DEFAULT 0,
            superseded_by TEXT,
            created_at TEXT NOT NULL,

            PRIMARY KEY (tenant, evidence_id),
            -- The retaining Observation is of THIS tenant; the supersession link is a self-FK into
            -- evidence. Each on its OWN line so the readiness parser skips it as a non-column.
            FOREIGN KEY (tenant, source_observation_id) REFERENCES observations (tenant, observation_id),
            FOREIGN KEY (tenant, superseded_by) REFERENCES evidence (tenant, evidence_id),
            CHECK (illegible IN (0, 1)),
            CHECK (trim(evidence_id) <> ''),
            CHECK (trim(content_digest) <> ''),
            CHECK (trim(content_ref) <> ''),
            CHECK (trim(media_type) <> ''),
            CHECK (trim(source_observation_id) <> ''),
            CHECK (trim(created_at) <> '')
        )""",
    # THE EVIDENCE SPAN (entity sec 11 `spans[]` = {page|offset, region, extracted_text}). The WHERE a
    # claim points into the artifact — what makes a MODEL_EXTRACTED claim checkable against the source
    # (entity sec 13, ADR-002 sec 2.3). Immutable and append-only; a span is an annotation, never an
    # edit (entity sec 22).
    "evidence_spans": """
        CREATE TABLE evidence_spans (
            tenant TEXT NOT NULL,
            span_id TEXT NOT NULL,
            evidence_id TEXT NOT NULL,
            -- The locator: a page number or a byte offset — the coarse WHERE (entity sec 11).
            locator TEXT NOT NULL,
            -- The region within the page/offset, and the text read there. Optional: some artifacts
            -- (an image region) carry no extracted text, but a span always names WHERE it is.
            region TEXT,
            extracted_text TEXT,
            created_at TEXT NOT NULL,

            PRIMARY KEY (tenant, span_id),
            FOREIGN KEY (tenant, evidence_id) REFERENCES evidence (tenant, evidence_id),
            CHECK (trim(span_id) <> ''),
            CHECK (trim(evidence_id) <> ''),
            CHECK (trim(locator) <> ''),
            CHECK (trim(created_at) <> '')
        )""",
}


P7EV_INDEXES: dict[str, str] = {
    # ### CONTENT ADDRESSING — A UNIQUE INDEX THAT SERIALIZES CONCURRENT RETENTION (entity sec 17/33).
    # Under a race, one INSERT of a given (tenant, content_digest) wins and every other hits THIS
    # index; the store treats the collision as a dedup and returns the existing Evidence. Drop the
    # UNIQUE and the same POD delivered twice becomes two Evidence rows — two artifacts where the
    # architecture guarantees one.
    "ix_evidence_content_addressing":
        "CREATE UNIQUE INDEX ix_evidence_content_addressing "
        "ON evidence (tenant, content_digest)",
    # Span lookup / lineage traversal: from an Evidence, walk to its spans (entity sec 14, ADR-007
    # sec 13 evidence traversal). Tenant-first, like every index in the system.
    "ix_evidence_spans_by_evidence":
        "CREATE INDEX ix_evidence_spans_by_evidence "
        "ON evidence_spans (tenant, evidence_id)",
}

# Nothing from an earlier phase is replaced. Declared so a future replacement has somewhere to go.
P7EV_REPLACED_INDEXES: tuple[str, ...] = ()


P7EV_TRIGGERS: dict[str, str] = {
    # ### THE CONTENT AND IDENTITY NEVER MUTATE (entity sec 6/10/16/22, C-8). The bytes behind a
    # content-addressed row are what make it THIS Evidence; a row whose digest or ref could be
    # rewritten has no identity, and content addressing would stop meaning anything. illegible and
    # superseded_by are NOT listed here — they are annotations the store may set.
    "trg_evidence_content_immutable": f"""
        CREATE TRIGGER trg_evidence_content_immutable
        BEFORE UPDATE OF tenant, evidence_id, content_digest, content_ref, media_type,
                         source_observation_id, created_at
        ON evidence
        BEGIN SELECT RAISE(ABORT, '{CONTENT_IMMUTABLE_ABORT}'); END""",
    # ### EVIDENCE IS NEVER DELETED (entity sec 26/28). No expiry, no retention sweep. A lost artifact
    # BLOCKS the consequential action that rests on it (entity sec 36); it is never tidied away.
    "trg_evidence_no_delete": f"""
        CREATE TRIGGER trg_evidence_no_delete
        BEFORE DELETE ON evidence
        BEGIN SELECT RAISE(ABORT, '{EVIDENCE_DELETE_ABORT}'); END""",
    # ### A SPAN IS IMMUTABLE (entity sec 22). Once written, the region a claim points at does not
    # change; a different region is a new span.
    "trg_evidence_spans_immutable": f"""
        CREATE TRIGGER trg_evidence_spans_immutable
        BEFORE UPDATE ON evidence_spans
        BEGIN SELECT RAISE(ABORT, '{SPAN_IMMUTABLE_ABORT}'); END""",
    # ### A SPAN IS NEVER DELETED (entity sec 26/28). It stays walkable for as long as the claim stands.
    "trg_evidence_spans_no_delete": f"""
        CREATE TRIGGER trg_evidence_spans_no_delete
        BEFORE DELETE ON evidence_spans
        BEGIN SELECT RAISE(ABORT, '{SPAN_DELETE_ABORT}'); END""",
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


def create_phase7_evidence_schema(conn: sqlite3.Connection, *, now: str) -> list[str]:
    """Create whatever Evidence structure is missing. Idempotent; returns what it did.

    Callable on a fresh canonical database and on an already-migrated one. Either way the resulting
    structure is byte-identical, because there is only one text. Built AFTER M5 (`observations`, the
    `source_observation_id` FK referent), which is why `schema.py` and the migrate path order it after
    the Observation.
    """
    performed: list[str] = []
    present = _tables(conn)
    for name in (*P7EV_TENANT_TABLES, *P7EV_EXEMPT_TABLES):
        if name not in present:
            conn.execute(P7EV_TARGET_SCHEMA[name])
            performed.append(f"create-table:{name}")
    existing = _indexes(conn)
    for name, ddl in P7EV_INDEXES.items():
        if name not in existing:
            conn.execute(ddl)
            performed.append(f"create-index:{name}")
    for stale in P7EV_REPLACED_INDEXES:
        if stale in _indexes(conn):
            conn.execute(f"DROP INDEX {stale}")
            performed.append(f"drop-index:{stale}")
    existing_triggers = _triggers(conn)
    for name, ddl in P7EV_TRIGGERS.items():
        if name not in existing_triggers:
            conn.execute(ddl)
            performed.append(f"create-trigger:{name}")
    # NO VERSION STAMP HERE — marker-last. A stamp written by the builder appears on a half-migrated
    # database the moment a later step fails, which is how a missing trigger goes unnoticed.
    conn.commit()
    return performed


def stamp_phase7_evidence_version(conn: sqlite3.Connection, *, now: str) -> None:
    """Record the Evidence marker — callable ONLY once readiness holds. Marker-last, like every phase."""
    problems = phase7_evidence_readiness_problems(conn)
    if problems:
        raise RuntimeError(
            f"refusing to stamp {P7EV_SCHEMA_VERSION} on a database that is NOT ready: "
            + "; ".join(problems)
        )
    if "schema_migrations" in _tables(conn):
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration, step, applied_at, detail) "
            "VALUES (?,?,?,?)",
            (MIGRATION_ID, f"version:{P7EV_SCHEMA_VERSION}", now,
             "Evidence: content-addressed immutable retained artifacts and their spans, tenant-first, "
             "content and identity immutable by trigger, deduplicated by (tenant, content_digest), "
             "never deleted; readiness proven"),
        )
        conn.commit()


def phase7_evidence_readiness_problems(conn: sqlite3.Connection) -> list[str]:
    """Every reason this database cannot carry content-addressed immutable Evidence. Empty == ready.

    Structural, like the P2/P3/P5/P6 oracles it extends. The content-addressing UNIQUE index and the
    immutability/no-delete triggers are verified PRESENT because an `evidence` table without them is
    an ordinary table with an aspirational comment: the same POD twice would insert twice, the bytes
    would be editable, and a lost artifact could be silently deleted.
    """
    problems: list[str] = []
    present = _tables(conn)
    for table in (*P7EV_TENANT_TABLES, *P7EV_EXEMPT_TABLES):
        if table not in present:
            problems.append(
                f"required Phase-7 table {table!r} is missing: run the {MIGRATION_ID} migration"
            )
    if not all(t in present for t in P7EV_TENANT_TABLES):
        return problems

    live_triggers = _triggers(conn)
    missing_triggers = sorted(t for t in P7EV_TRIGGERS if t not in live_triggers)
    if missing_triggers:
        problems.append(
            f"Evidence invariant triggers missing: {missing_triggers}. Without them the content "
            f"could be rewritten, a span could be edited, and a retained artifact could be deleted "
            f"[entity 08-evidence sec 16/22/26/28, C-8]."
        )
    live_indexes = _indexes(conn)
    for name in P7EV_INDEXES:
        if name not in live_indexes:
            problems.append(f"required Phase-7 index {name!r} is missing")
    for stale in P7EV_REPLACED_INDEXES:
        if stale in live_indexes:
            problems.append(f"replaced index {stale!r} is still present")

    # ### CONTENT ADDRESSING, READ OUT OF THE LIVE DATABASE RATHER THAN ASSUMED FROM ITS NAME. An
    # index called `..._content_addressing` that is not UNIQUE, or that has dropped content_digest, is
    # the one-Evidence-per-artifact defence switched off with the sign left up (entity sec 17/33).
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name = ?",
        ("ix_evidence_content_addressing",),
    ).fetchone()
    if row is not None:
        sql = " ".join((row[0] or "").split()).upper()
        if "UNIQUE" not in sql:
            problems.append(
                "ix_evidence_content_addressing is not UNIQUE: the same artifact retained twice would "
                "insert as two Evidence rows, and 'identical bytes are one Evidence' (entity sec 17/33) "
                "would be a convention, not a constraint."
            )
        for column in ("TENANT", "CONTENT_DIGEST"):
            if column not in sql:
                problems.append(
                    f"ix_evidence_content_addressing does not cover {column!r}: content addressing is "
                    f"(tenant, content_digest), and dropping a member widens or narrows what counts as "
                    f"'the same artifact'."
                )

    # ### EVIDENCE IS DATA — IT CARRIES NO PROVENANCE (entity sec 35, ADR-002 sec 2.3, M-66). A
    # provenance_class column on `evidence` would make the artifact look like it could set the trust
    # of the claim that points at it; provenance lives on the CLAIM, never on the artifact.
    ev_columns = _columns(conn, "evidence")
    if "provenance_class" in ev_columns:
        problems.append(
            "evidence carries a provenance_class column: Evidence is DATA and sets no provenance "
            "(entity sec 35, ADR-002 sec 2.3). A document may EVIDENCE a claim; it may never set the "
            "trust of one."
        )
    if "state" in ev_columns:
        problems.append(
            "evidence carries a state column: Evidence is an immutable record with NO lifecycle "
            "(entity sec 12/20). A revised artifact is a new Evidence, not a state change of this one."
        )

    for table in P7EV_TENANT_TABLES:
        referents = _referents(conn, table)
        if table == "evidence":
            for referent in P7EV_REQUIRED_REFERENTS:
                if referent not in referents:
                    problems.append(
                        f"{table} declares no foreign key into {referent!r}: an Evidence enters via "
                        f"the Observation that retained it (entity sec 10/14), and without the FK "
                        f"'how it entered' is a free-text column."
                    )
        if table == "evidence_spans" and "evidence" not in referents:
            problems.append(
                "evidence_spans declares no foreign key into 'evidence': a span that points at no "
                "retained artifact is a location into nothing (entity sec 11/14)."
            )
    return problems
