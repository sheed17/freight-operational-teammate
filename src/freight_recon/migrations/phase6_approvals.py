"""Phase 6 — M4, the Approval: one `approvals` row that makes "the human agreed to THIS" a fact a
database can CHECK, rather than a sentence in an audit log.

WHAT THIS TABLE IS, IN FREIGHT TERMS

    The owner approved invoicing load 4471 at £2,850, read from the TMS invoice screen. Forty
    minutes later the TMS says £3,100. `ADR-005` F-01: the old architecture invoiced £3,100 and the
    audit log recorded a human approval, because the approval was bound to the ACTION, not to the
    FACTS that made it correct. This row binds both — a `material_facts_fingerprint` computed from
    RUNTIME reads (never model output) plus the full `canonical_payload` it was computed from — so a
    drifted fact is not a weaker approval; it is a new question (`ADR-005` §3.1).

WHY THE FINGERPRINT IS A COLUMN AND THE PAYLOAD IS ANOTHER

    `material_facts_fingerprint` is the fast equality check at checkpoint step 2. `canonical_payload`
    is the full `fp_v1` bytes it was hashed from, retained permanently (`ADR-005` §3.5, `[C-9]`): a
    hash can prove that something drifted; it can never say WHAT. The human-readable `drift_diff`
    (§3.13) is generated from two retained payloads, which is the only reason it can name the field,
    the old value and the new. `fp_v1` is `fingerprint.py`'s and is CONSUMED, never reimplemented —
    a serialization change is the single most dangerous bug class in `ADR-005` §7 (it produces false
    no-drift, which is a wrong payment).

WHY `granted_by` IS A FOREIGN KEY AND `state = 'GRANTED'` CHECKS IT

    "An authenticated, authorized human granted this" is decoration while `granted_by` is a text
    column any string satisfies — the same argument M1 made for `owner_id`. So it is a FOREIGN KEY
    into `tenant_humans`, and entity §37 names a `GRANTED` approval with no `granted_by` as a
    structurally impossible state — the only version of that sentence a database enforces is
    `CHECK (state <> 'GRANTED' OR granted_by IS NOT NULL)`.

WHY THE GATE CHECK SUBSUMES "NO AUTONOMOUS APPROVAL"

    An Approval exists ONLY where the gate is human (entity §12/§16). The gate CHECK admits exactly
    the two human gates, so the autonomous gate is unwritable for ANY action class — the
    money-affecting-cannot-be-autonomous rule of entity §16, enforced more strongly than "for
    money-affecting classes only", and stated explicitly beside it. The gate literals are DERIVED
    from the kernel vocabulary, not restated (so the Phase-0 confinement guard still confines them).

WHY THE FREEZE BINDS ITS CHAIN, AND WHY THERE IS AN `effect_grants` FK AT ALL

    `ER-16`: a quarantine fact is reconstructed from POSITIVE evidence, never from an absence. So a
    frozen approval carries the `unknown_outcome_ref` and `effect_grant_id` that froze it, enforced
    by `CHECK (frozen = 0 OR (unknown_outcome_ref IS NOT NULL AND effect_grant_id IS NOT NULL ...))`.
    The `effect_grant_id` FK into `effect_grants` also answers `schema._second_ledger_problems`: an
    `approvals` row carries both `commit_key` and `state`, so — like `pipeline_instances` — it must
    declare a foreign key into the ONE effect ledger to prove it is ANSWERABLE to it and is not a
    second effect authority (CLAUDE.md rule 17). M4 reserves at most one LIVE approval per commit key
    (the partial unique index below); it never claims a grant.

THE LAYER-1 RESERVATION, ONE APPROVAL PER LIVE EFFECT

    `UNIQUE (tenant, commit_key) WHERE state IN ('REQUESTED','GRANTED')` (entity §17): at most one
    live approval per effect, enforced by the database rather than hoped for by the application. A
    re-approval supersedes only after the prior is terminal (drift-void ∪ duplicate-refusal; there
    is NO `SUPERSEDED` state — entity §24).

WHAT IS DELIBERATELY *NOT* HERE

    No amount column, ever (K-4, the money-in-memory rule): the amount lives inside the
    `canonical_payload` bytes, which are the human's decision, not a remembered money value with a
    fresh timestamp. No grant STATE: SD-2 gives the effect grant ONE row and M3 owns it; the
    approval is CONSUMED by M3's claim CAS, it does not mirror the grant's lifecycle. No `SUPERSEDED`
    state and no unfreeze path — `G2-D15` records the UNFREEZE direction as an open, strictly-safer
    residual, and no column here clears `frozen`.

FRESH == MIGRATED, SHIPS DARK

    `create_canonical_schema` builds these tables directly; a database reached by
    `phase2_tenant_first.migrate` reaches the same shape through `create_phase6_approvals_schema`.
    Nothing routes production traffic through M4; `approval.py` is the only non-test module that reads
    it, and only `scripts/probe_phase6_approval.py` imports the machine.
"""

from __future__ import annotations

import sqlite3

MIGRATION_ID = "phase6_approvals"
P6AP_SCHEMA_VERSION = "phase6-approvals-1"

# Tenant-owned. An approval is a human's consent WITHIN one brokerage; the same commit_key in two
# tenants is two isolated approvals [C-1]. There is no honest cross-tenant reading of "who agreed".
P6AP_TENANT_TABLES: tuple[str, ...] = ("approvals", "approval_signatures")

# Nothing tenant-exempt. Stated rather than omitted, so a future addition must defend its exemption.
P6AP_EXEMPT_TABLES: tuple[str, ...] = ()

# `state-machines/registry.md` §4, M4 — the EIGHT, in the specification's own order.
APPROVAL_STATES: tuple[str, ...] = (
    "REQUESTED", "GRANTED", "CONSUMED", "DENIED", "EXPIRED", "REVOKED",
    "VOID_ON_DRIFT", "VOID_ON_BRAKE",
)

# §8. Six terminal; `REQUESTED`/`GRANTED` are the only non-terminal states.
TERMINAL_APPROVAL_STATES: tuple[str, ...] = (
    "CONSUMED", "DENIED", "EXPIRED", "REVOKED", "VOID_ON_DRIFT", "VOID_ON_BRAKE",
)

# §9/§10. Recoverable non-terminal states — a crash before consumption leaves a GRANTED approval,
# and recovery re-runs the checkpoint (incl. the live drift check) before any claim (§36).
NON_TERMINAL_APPROVAL_STATES: tuple[str, ...] = ("REQUESTED", "GRANTED")

# entity §12: an Approval exists ONLY for the two HUMAN gates, and never the autonomous one — which
# is how "a money-affecting action class cannot be autonomous-approved" becomes unwritable.
#
# ### THE GATE VOCABULARY IS DERIVED, NOT RESTATED, so no gate-decision token appears in this file.
# ADR-010 puts gate evaluation at the checkpoint kernel, and the Phase-0 confinement guard
# (`test_phase0_null_gate`) scans every `.py` for the four gate tokens and confines them to the
# kernel. M2's migration solved this by reading the four literals out of P3's `checkpoint_witnesses`
# DDL at import time; M4 reads the SAME derived tuple from M2's migration and filters it by role.
from .phase6_pipeline_instances import GATE_DECISIONS as _KERNEL_GATE_DECISIONS

APPROVAL_GATE_DECISIONS: tuple[str, ...] = tuple(
    g for g in _KERNEL_GATE_DECISIONS if "HUMAN" in g)
_AUTONOMOUS_GATE = next(g for g in _KERNEL_GATE_DECISIONS if "AUTONOMOUS" in g)
if len(APPROVAL_GATE_DECISIONS) != 2 or not _AUTONOMOUS_GATE:
    raise RuntimeError(
        "the kernel's gate vocabulary did not yield exactly two human gates and one autonomous "
        f"gate: human={APPROVAL_GATE_DECISIONS!r}, autonomous={_AUTONOMOUS_GATE!r}. M4 derives its "
        "gate CHECK from the kernel rather than restating it; a refusal here beats a silent miss."
    )

_STATES_SQL = ",".join(f"'{s}'" for s in APPROVAL_STATES)
_TERMINAL_SQL = ",".join(f"'{s}'" for s in TERMINAL_APPROVAL_STATES)
_LIVE_SQL = ",".join(f"'{s}'" for s in NON_TERMINAL_APPROVAL_STATES)
_GATES_SQL = ",".join(f"'{g}'" for g in APPROVAL_GATE_DECISIONS)
_AUTONOMOUS_SQL = _AUTONOMOUS_GATE

# The two referents the readiness oracle checks by name, the way M2/M3 name theirs. The generic
# oracle derives them from the DDL too; naming them here is the unit stating what it is FOR.
P6AP_REQUIRED_REFERENTS: tuple[str, ...] = ("tenant_humans", "effect_grants")

# The exact abort texts, worded WITHOUT apostrophes (they are interpolated into single-quoted SQL
# literals inside RAISE(ABORT, ...); an apostrophe would terminate the literal). Named here and
# matched by `approval.py` when it classifies an IntegrityError — SQLite reports a trigger
# RAISE(ABORT) and a CHECK/UNIQUE violation through the same exception type.
TERMINAL_ABORT = (
    "a terminal Approval never transitions [04-approval.machine.md sec 15/26]: CONSUMED plus "
    "anything is ILLEGAL (single-use), a re-approval is a NEW approval with a NEW fingerprint, and "
    "there is no SUPERSEDED state and no reopen door"
)
VERSION_ABORT = (
    "approvals.version advances by exactly one per transition [GR-3]: a write that does not advance "
    "it silently overwrites another transition, and approval is a STRICT-ORDER aggregate"
)
IDENTITY_ABORT = (
    "the identity of an approval is immutable: the tenant, the approval id, the commit key it "
    "authorizes, the action class and when it was requested are what make it THIS approval, and "
    "editing them would retarget a human consent onto a different effect"
)
FINGERPRINT_ABORT = (
    "a GRANTED or terminal approval is never re-fingerprinted in place [04-approval.machine.md "
    "sec 22/26]: an approval is never refreshed, extended or re-validated in place; a changed "
    "decision is a NEW approval with a NEW fingerprint. Only a REQUESTED approval collecting "
    "dual-control signatures may take a fresh fingerprint, and only because ALL prior signatures "
    "are voided with it (ADR-005 sec 3.16)"
)
DELETE_ABORT = (
    "approvals is never deleted [C-9]: you must be able to reconstruct, years later, exactly what "
    "the human saw when they said yes, and deleting the row is how that evidence disappears"
)


P6AP_TARGET_SCHEMA: dict[str, str] = {
    # THE APPROVAL (`entities/06-approval.md`, spec §12.4, machine M4, ADR-005).
    #
    # One human consent, bound to the exact facts that made it correct. Every new column on its OWN
    # line and every FOREIGN KEY on its OWN line: `schema._canonical_columns` parses this DDL line by
    # line and reads only the first token of a line as a column, skipping a line that STARTS with
    # PRIMARY KEY / FOREIGN KEY / UNIQUE / CHECK. A wrapped clause reads as a column called
    # `REFERENCES`, the blind spot `phase6_pipeline_instances` documents.
    "approvals": """
        CREATE TABLE approvals (
            tenant TEXT NOT NULL,
            approval_id TEXT NOT NULL,
            -- The logical effect this consent authorizes. commit_key consistent with the Pipeline
            -- Instance; the AMOUNT IS NOT IN IT (ADR-009, rule 8) — it is inside canonical_payload.
            commit_key TEXT NOT NULL,
            action_class TEXT NOT NULL,
            state TEXT NOT NULL,
            version INTEGER NOT NULL,

            -- ADR-005 sec 3.4/3.5: the fast equality check AND the full fp_v1 bytes it was hashed
            -- from, retained so a drift can be EXPLAINED (the diff), not merely detected.
            material_facts_fingerprint TEXT NOT NULL,
            canonical_payload TEXT NOT NULL,
            fingerprint_version TEXT NOT NULL,

            -- The decision context sec 5 requires a CONSEQUENTIAL approval event to pin, computed at
            -- request time from RUNTIME reads (M-13/M-55), never model output. entity_versions is the
            -- SD-3 set the decision read; brake_version and policy_version are the admission context.
            entity_versions_json TEXT NOT NULL,
            policy_version TEXT NOT NULL,
            brake_version TEXT NOT NULL,
            gate_decision TEXT NOT NULL,
            required_authority TEXT,
            -- V3 (NEEDS VALIDATION): which classes need dual control, at what threshold. The
            -- mechanism does not depend on the answer; the fail-closed default is single approval.
            required_signatures INTEGER NOT NULL,

            -- What was shown to the human (ADR-005 sec 3.2/3.17): if it was on the card it is
            -- material; if it was material it must have been on the card. Retained so the evidentiary
            -- record can reconstruct exactly what the human saw when they said yes.
            rendered_facts TEXT NOT NULL,

            requested_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,

            -- AP-2. OWNER_ASSERTED-grade and a FK into the tenant's recorded humans: an authenticated
            -- human is decoration while this is a text column any string satisfies.
            granted_by TEXT,
            granted_at TEXT,
            -- AP-7. Set once, in the same transaction as the M3 claim CAS.
            consumed_at TEXT,
            -- AP-4/4p/5/6. The refusal record and, for a drift void, the field-level diff.
            void_reason TEXT,
            drift_diff TEXT,

            -- AP-9. The quarantine flag and the exact chain that froze it (ER-16 positive evidence):
            -- frozen is set from the PRESENCE of ApprovalFrozen, never inferred from an absence.
            frozen INTEGER NOT NULL,
            unknown_outcome_ref TEXT,
            effect_grant_id TEXT,
            frozen_at TEXT,

            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            PRIMARY KEY (tenant, approval_id),
            -- granted_by and effect_grant_id are FKs on their OWN lines. The effect_grants FK is also
            -- what makes this row ANSWERABLE to the one ledger (schema._second_ledger_problems): an
            -- approval carries commit_key and state, so without it the row would read as a second
            -- effect authority (rule 17). It reserves an approval, never a claim.
            FOREIGN KEY (tenant, granted_by) REFERENCES tenant_humans (tenant, human_id),
            FOREIGN KEY (tenant, effect_grant_id) REFERENCES effect_grants (tenant, grant_id),
            CHECK (state IN (%(states)s)),
            CHECK (version >= 1),
            CHECK (required_signatures >= 1),
            CHECK (frozen IN (0, 1)),
            -- entity sec 12/16: an Approval exists ONLY for a human gate. The autonomous gate is
            -- unwritable, which is the money-affecting-cannot-be-autonomous rule, enforced for ALL
            -- classes and stated explicitly beside it. Both gate literals are DERIVED from the
            -- kernel vocabulary (see the module head), so no gate token appears in this file.
            CHECK (gate_decision IN (%(gates)s)),
            CHECK (gate_decision <> '%(autonomous)s'),
            -- entity sec 37: a GRANTED approval with no granted_by is a structurally impossible
            -- state, and the only version of that sentence a database enforces is this CHECK.
            CHECK (state <> 'GRANTED' OR granted_by IS NOT NULL),
            -- ER-16: a freeze binds the exact unknown-outcome chain that froze it. On ONE line: the
            -- readiness parser reads the first token of each line as a column, so a wrapped CHECK
            -- continuation would read as a column called AND.
            CHECK (frozen = 0 OR (unknown_outcome_ref IS NOT NULL AND effect_grant_id IS NOT NULL AND frozen_at IS NOT NULL)),
            CHECK (trim(approval_id) <> ''),
            CHECK (trim(commit_key) <> ''),
            CHECK (trim(action_class) <> ''),
            CHECK (trim(material_facts_fingerprint) <> ''),
            CHECK (trim(canonical_payload) <> ''),
            CHECK (trim(fingerprint_version) <> ''),
            CHECK (trim(policy_version) <> ''),
            CHECK (trim(brake_version) <> ''),
            CHECK (trim(rendered_facts) <> '')
        )""" % {"states": _STATES_SQL, "gates": _GATES_SQL, "autonomous": _AUTONOMOUS_SQL},

    # THE DUAL-CONTROL SIGNATURES (ADR-005 sec 3.16). An EVIDENCE record attached to the existing
    # machine, not a new lifecycle and not a new primitive. The PK is (tenant, approval_id, actor_id)
    # so a DUPLICATE ACTOR CANNOT SATISFY QUORUM — the database counts distinct authenticated actors,
    # not signatures. Every signature binds the fingerprint it signed; drift between signatures voids
    # all of them (the machine deletes them and re-fingerprints while still REQUESTED).
    "approval_signatures": """
        CREATE TABLE approval_signatures (
            tenant TEXT NOT NULL,
            approval_id TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            signed_fingerprint TEXT NOT NULL,
            signed_at TEXT NOT NULL,
            PRIMARY KEY (tenant, approval_id, actor_id),
            FOREIGN KEY (tenant, approval_id) REFERENCES approvals (tenant, approval_id),
            FOREIGN KEY (tenant, actor_id) REFERENCES tenant_humans (tenant, human_id),
            CHECK (trim(actor_id) <> ''),
            CHECK (trim(signed_fingerprint) <> '')
        )""",
}


P6AP_INDEXES: dict[str, str] = {
    # ### THE LAYER-1 RESERVATION (entity sec 17). At most one LIVE approval per effect, enforced by
    # the database. A re-approval supersedes only after the prior is terminal (drift-void or
    # duplicate-refusal; there is no SUPERSEDED state). Read the six terminal states against the
    # eight: only REQUESTED and GRANTED are inside the predicate, so a voided/expired/consumed/denied
    # approval frees the key for the new question ADR-005 sec 3.10 describes.
    "ix_approvals_live_per_commit_key":
        "CREATE UNIQUE INDEX ix_approvals_live_per_commit_key "
        "ON approvals (tenant, commit_key) WHERE state IN (" + _LIVE_SQL + ")",
    # The operator surface: approvals awaiting a human, by age. Drift-void rate and time-to-approve
    # are first-class metrics (ADR-005 sec 9), and this is the query behind the card queue.
    "ix_approvals_tenant_state":
        "CREATE INDEX ix_approvals_tenant_state "
        "ON approvals (tenant, state, requested_at)",
    # Signatures for one approval, in signing order — the dual-control quorum read.
    "ix_approval_signatures_tenant_approval":
        "CREATE INDEX ix_approval_signatures_tenant_approval "
        "ON approval_signatures (tenant, approval_id, signed_at)",
}

# Nothing from an earlier phase is replaced. Declared so a future replacement has somewhere to go.
P6AP_REPLACED_INDEXES: tuple[str, ...] = ()


P6AP_TRIGGERS: dict[str, str] = {
    # ### TERMINAL IS ABSOLUTELY TERMINAL (sec 15/26). CONSUMED plus anything is ILLEGAL (single
    # use); a denied/voided/expired/revoked approval never moves again. This makes that true against
    # a connection, not only against the transition table.
    "trg_approvals_terminal_is_final": f"""
        CREATE TRIGGER trg_approvals_terminal_is_final
        BEFORE UPDATE ON approvals
        WHEN OLD.state IN ({_TERMINAL_SQL})
        BEGIN SELECT RAISE(ABORT, '{TERMINAL_ABORT}'); END""",
    # ### OCC IS NOT A CONVENTION (GR-3). approval is a STRICT-ORDER family (events/registry.md sec
    # 8), so a version that stands still is how two events claim one aggregate version — not a
    # cosmetic collision. AP-8 (a provably-failed attempt that changes nothing) writes no row at all,
    # so it never trips this; every write that DOES happen advances the version by exactly one.
    "trg_approvals_version_advances_by_one": f"""
        CREATE TRIGGER trg_approvals_version_advances_by_one
        BEFORE UPDATE ON approvals
        WHEN NEW.version <> OLD.version + 1
        BEGIN SELECT RAISE(ABORT, '{VERSION_ABORT}'); END""",
    # ### THE IDENTITY OF AN APPROVAL IS IMMUTABLE. Editing the commit key would retarget a human
    # consent onto a different effect; editing the action class would change what was agreed to. Both
    # are the shape of change an audit cannot detect afterwards, because the row afterwards is
    # internally consistent.
    "trg_approvals_identity_is_immutable": f"""
        CREATE TRIGGER trg_approvals_identity_is_immutable
        BEFORE UPDATE OF tenant, approval_id, commit_key, action_class, gate_decision,
                         requested_at, created_at
        ON approvals
        BEGIN SELECT RAISE(ABORT, '{IDENTITY_ABORT}'); END""",
    # ### AN APPROVAL IS NEVER RE-FINGERPRINTED IN PLACE ONCE IT LEAVES REQUESTED (sec 22/26). A
    # changed decision is a NEW approval. The one exception is a REQUESTED approval collecting
    # dual-control signatures: signature drift voids ALL signatures and re-fingerprints (ADR-005 sec
    # 3.16), which is legal precisely because it is still REQUESTED and nobody has been shown a stale
    # basis for consent yet.
    "trg_approvals_fingerprint_frozen_after_request": f"""
        CREATE TRIGGER trg_approvals_fingerprint_frozen_after_request
        BEFORE UPDATE OF material_facts_fingerprint, canonical_payload ON approvals
        WHEN OLD.state <> 'REQUESTED'
        BEGIN SELECT RAISE(ABORT, '{FINGERPRINT_ABORT}'); END""",
    "trg_approvals_no_delete": f"""
        CREATE TRIGGER trg_approvals_no_delete
        BEFORE DELETE ON approvals
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


def create_phase6_approvals_schema(conn: sqlite3.Connection, *, now: str) -> list[str]:
    """Create whatever M4 structure is missing. Idempotent; returns what it did.

    Callable on a fresh canonical database and on an already-migrated one. Either way the resulting
    structure is byte-identical, because there is only one text — the discipline every other phase
    uses, and the reason a fresh database is never briefly unsafe. Built AFTER M1 (tenant_humans FK)
    and M3 (effect_grants FK), which is why `schema.py` orders it last.
    """
    performed: list[str] = []
    present = _tables(conn)
    for name in (*P6AP_TENANT_TABLES, *P6AP_EXEMPT_TABLES):
        if name not in present:
            conn.execute(P6AP_TARGET_SCHEMA[name])
            performed.append(f"create-table:{name}")
    existing = _indexes(conn)
    for name, ddl in P6AP_INDEXES.items():
        if name not in existing:
            conn.execute(ddl)
            performed.append(f"create-index:{name}")
    for stale in P6AP_REPLACED_INDEXES:
        if stale in _indexes(conn):
            conn.execute(f"DROP INDEX {stale}")
            performed.append(f"drop-index:{stale}")
    existing_triggers = _triggers(conn)
    for name, ddl in P6AP_TRIGGERS.items():
        if name not in existing_triggers:
            conn.execute(ddl)
            performed.append(f"create-trigger:{name}")
    # NO VERSION STAMP HERE — marker-last. A stamp written by the builder appears on a half-migrated
    # database the moment a later step fails, which is how a missing trigger goes unnoticed.
    conn.commit()
    return performed


def stamp_phase6_approvals_version(conn: sqlite3.Connection, *, now: str) -> None:
    """Record the M4 marker — callable ONLY once readiness holds. Marker-last, like every phase."""
    problems = phase6_approvals_readiness_problems(conn)
    if problems:
        raise RuntimeError(
            f"refusing to stamp {P6AP_SCHEMA_VERSION} on a database that is NOT ready: "
            + "; ".join(problems)
        )
    if "schema_migrations" in _tables(conn):
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration, step, applied_at, detail) "
            "VALUES (?,?,?,?)",
            (MIGRATION_ID, f"version:{P6AP_SCHEMA_VERSION}", now,
             "the Approval: one human consent bound to the exact facts, tenant-first, one live "
             "approval per commit key, granted_by a recorded human; readiness proven"),
        )
        conn.commit()


def phase6_approvals_readiness_problems(conn: sqlite3.Connection) -> list[str]:
    """Every reason this database cannot carry human consent bound to facts. Empty == ready.

    Structural, like the P2/P3/P5/M1/M2/M3 oracles it extends. The reservation index and the
    triggers are verified PRESENT because an `approvals` table without them is an ordinary table
    with an aspirational comment: two live approvals for one effect would both insert, a terminal
    approval would transition, and a GRANTED approval with no human would be writable.
    """
    problems: list[str] = []
    present = _tables(conn)
    for table in (*P6AP_TENANT_TABLES, *P6AP_EXEMPT_TABLES):
        if table not in present:
            problems.append(
                f"required Phase-6 table {table!r} is missing: run the {MIGRATION_ID} migration"
            )
    if not all(t in present for t in P6AP_TENANT_TABLES):
        return problems

    live_triggers = _triggers(conn)
    missing_triggers = sorted(t for t in P6AP_TRIGGERS if t not in live_triggers)
    if missing_triggers:
        problems.append(
            f"Approval invariant triggers missing: {missing_triggers}. Without them a terminal "
            f"approval can transition, the version counter can stand still, an approval can be "
            f"retargeted at another effect, a granted approval can be re-fingerprinted in place, "
            f"and the evidentiary row can be deleted [sec 15, sec 22, GR-3, C-9]."
        )
    live_indexes = _indexes(conn)
    for name in P6AP_INDEXES:
        if name not in live_indexes:
            problems.append(f"required Phase-6 index {name!r} is missing")
    for stale in P6AP_REPLACED_INDEXES:
        if stale in live_indexes:
            problems.append(f"replaced index {stale!r} is still present")

    # ### THE LAYER-1 RESERVATION, READ OUT OF THE LIVE DATABASE RATHER THAN ASSUMED FROM ITS NAME.
    # An index called `..._live_per_commit_key` that is not UNIQUE, or whose partial predicate has
    # been widened to include a terminal state, is the one-live-approval defence switched off with
    # the sign left up.
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name = ?",
        ("ix_approvals_live_per_commit_key",),
    ).fetchone()
    if row is not None:
        sql = " ".join((row[0] or "").split()).upper()
        if "UNIQUE" not in sql:
            problems.append(
                "ix_approvals_live_per_commit_key is not UNIQUE: two live approvals for one effect "
                "would both insert, and 'at most one live approval per commit key' (entity sec 17) "
                "would be a convention, not a constraint."
            )
        for state in TERMINAL_APPROVAL_STATES:
            if f"'{state}'" in sql:
                problems.append(
                    f"ix_approvals_live_per_commit_key includes terminal state {state!r} in its "
                    f"predicate: a terminal approval would keep holding the key, so a re-approval "
                    f"after a drift-void could never be requested (ADR-005 sec 3.10)."
                )
        for state in NON_TERMINAL_APPROVAL_STATES:
            if f"'{state}'" not in sql:
                problems.append(
                    f"ix_approvals_live_per_commit_key does not cover live state {state!r}: a "
                    f"second live approval for one effect would insert."
                )

    # ### THE granted_by CHECK, READ OUT OF THE approvals DDL. entity sec 37 names a GRANTED approval
    # with no granted_by as a structurally impossible state; without the CHECK it is a writable one.
    ddl_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='approvals'").fetchone()
    ddl = " ".join((ddl_row[0] if ddl_row else "" or "").split()).upper()
    if "STATE <> 'GRANTED' OR GRANTED_BY IS NOT NULL" not in ddl:
        problems.append(
            "approvals does not CHECK that a GRANTED approval has a non-null granted_by: entity sec "
            "37 names that a structurally impossible state, and a database enforces it with a CHECK."
        )
    # The expected gate CHECK substring is DERIVED from the (kernel-derived) human gates, so this
    # file names no gate-decision token even in the readiness oracle.
    expected_gate_check = ("GATE_DECISION IN ("
                           + ",".join(f"'{g}'" for g in APPROVAL_GATE_DECISIONS) + ")").upper()
    if expected_gate_check not in ddl.replace(", ", ","):
        problems.append(
            "approvals does not constrain gate_decision to the two human gates: without it the "
            "autonomous gate would be writable and an approval could exist for an autonomous "
            "action class (entity sec 12/16)."
        )
    if "FROZEN = 0 OR (UNKNOWN_OUTCOME_REF IS NOT NULL AND EFFECT_GRANT_ID IS NOT NULL" not in ddl:
        problems.append(
            "approvals does not CHECK that a frozen approval binds its unknown-outcome chain: ER-16 "
            "requires the quarantine to rest on POSITIVE evidence (the unknown_outcome_ref and the "
            "effect_grant_id), not on an absence."
        )

    for table in P6AP_TENANT_TABLES:
        referents = _referents(conn, table)
        needed = P6AP_REQUIRED_REFERENTS if table == "approvals" else ("approvals", "tenant_humans")
        for referent in needed:
            if referent not in referents:
                problems.append(
                    f"{table} declares no foreign key into {referent!r}: "
                    + ("'granted by an authenticated recorded human' is decoration while granted_by "
                       "is a free-text column (entity sec 18)"
                       if referent == "tenant_humans" and table == "approvals" else
                       "an approval carries commit_key and state, so it must be ANSWERABLE to the "
                       "one effect ledger (schema._second_ledger_problems, rule 17)"
                       if referent == "effect_grants" else
                       f"a {table} row must reference a real {referent} row")
                )
    return problems
