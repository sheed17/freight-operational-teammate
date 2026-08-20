"""Phase 6 — M3, the External Effect / Effect Grant: the ONE `effect_grants` row that is the only
serialization point between a decision and the outside world.

WHAT THIS MIGRATION IS, AND IS NOT

    It does NOT create a table. `effect_grants` has existed since P2, carries the eight canonical
    states in a `CHECK` since P2, and is minted-into and claimed by P3's kernel. SD-2 is emphatic
    (`entities/03-external-effect.md`, `entities/04-effect-grant.md`): the External Effect and the
    Effect Grant are the SAME durable ledger row viewed through two aspects, so there is exactly one
    table and this migration must not fork it into a second.

    What M3 owes the ledger is the OUTCOME aspect's evidence and two structural authorities:

      * the columns `state-machines/03-external-effect-grant.machine.md` §14 *Writes* names for the
        outcome transitions — `attempted_at` (EF-3), `verified_at` (EF-4), `failure_proof` (EF-3f),
        `exposure` (EF-3u), `health_signal` (EF-4), `reality_decision_ref` (EF-5). `claimed_at`,
        `verification_outcome` and `unknown_reason` already exist from P2.

      * two tenant-first FOREIGN KEYs — into `checkpoint_witnesses` and into `pipeline_instances`.
        "Mint requires real checkpoint authority" is decoration while `checkpoint_id` is an
        unconstrained text column that any string satisfies; the FK is the same argument M1 made for
        `owner_id` and M2 made for its witness and grant references. A `checkpoint_id` naming no
        witness is not a bad value — it is an unwritable one.

WHY THE WITNESS FK IS DEFERRABLE, AND THE PIPELINE FK IS NOT

    `checkpoint_witnesses` already declares `FOREIGN KEY (tenant, grant_id) REFERENCES effect_grants`
    (P3). Adding `effect_grants (tenant, checkpoint_id) -> checkpoint_witnesses` closes a cycle, and
    the kernel's `mint_grant` inserts the GRANT row FIRST and the WITNESS row SECOND inside one
    transaction (`checkpoint.py`; the order is asserted by `test_phase3_witness`). An IMMEDIATE FK
    would refuse the grant insert because its witness does not exist yet. So the witness FK is
    `DEFERRABLE INITIALLY DEFERRED` — checked at COMMIT, by which point both rows exist — and nothing
    about the mint changes. The pipeline FK is ordinary: `pipeline_instance_id` is NULL on a
    kernel-minted grant (SQLite does not enforce a composite FK with a NULL column), and becomes
    real only when a Pipeline Instance binds itself, at which point the referent must already exist.

WHY THE `entities/03` §16 CHECKS ARE ENFORCED IN THE MACHINE, NOT HERE

    §16 wants `unknown_reason NOT NULL iff state = UNKNOWN_OUTCOME`, `FAILED` to carry a
    `failure_proof`, and `VERIFIED` to carry a `health_signal`. Those are true invariants and M3
    enforces every one — but as machine guards proven by `scripts/mutate_phase6_external_effect.py`,
    not as DB CHECKs, because a DB CHECK on `effect_grants` is a P2/P3/P4-shared surface and the
    existing fixtures (`test_phase3_schema` inserts a bare `UNKNOWN_OUTCOME` row with no reason; the
    P2 legacy migration writes a non-canonical `unknown_reason`) would fail one. Strengthening a
    shared table's CHECK set to serve M3 would weaken P2/P3 tests, which CLAUDE.md forbids without
    saying so first. The FKs are safe because every existing insert leaves both FK columns NULL.

FRESH == MIGRATED

    `create_canonical_schema` builds `effect_grants` directly from the extended DDL below (it
    overrides P2's in the merged view), so a fresh database carries the columns and FKs from its
    first statement. A database reached by `phase2_tenant_first.migrate` is built in P2's shape and
    then transformed HERE by `create_phase6_external_effects_schema`, which adds the columns with
    `ALTER TABLE` and, if the FKs are absent, rebuilds the table from the SAME extended DDL. Both
    paths end byte-identical, which `test_u26bc_schema_readiness` asserts structurally.

    IT SHIPS DARK. Nothing routes production traffic through M3; `create_canonical_schema` builds the
    shape, and `external_effect.py` is the only non-test module that reads it.
"""

from __future__ import annotations

import sqlite3

from .phase2_tenant_first import TARGET_SCHEMA as _P2_TARGET_SCHEMA

MIGRATION_ID = "phase6_external_effects"
P6EF_SCHEMA_VERSION = "phase6-external-effects-1"

# M3 adds no table of its own — `effect_grants` is P2's and stays P2's. These are declared so the
# readiness oracle and `create_canonical_schema` account for M3 the way they account for every phase,
# even though the answer is "no new tenant table, no exempt table".
P6EF_TENANT_TABLES: tuple[str, ...] = ()
P6EF_EXEMPT_TABLES: tuple[str, ...] = ()

# The eight canonical states (`registry.md` §4, M3 / SD-2). Identical set to P2's `GRANT_STATES`;
# named here so `external_effect.py` reads one authority for the machine's state domain.
EF_STATES: tuple[str, ...] = (
    "GRANTED", "CLAIMED", "ATTEMPTED", "VERIFIED",
    "FAILED", "EXPIRED_UNCLAIMED", "REVOKED", "UNKNOWN_OUTCOME",
)

# §8 terminal. `UNKNOWN_OUTCOME` is DELIBERATELY ABSENT — it is non-terminal and human-owned (§9),
# and reading it as terminal is exactly how "we do not know" gets laundered into a closed ledger.
EF_TERMINAL_STATES: tuple[str, ...] = ("VERIFIED", "FAILED", "EXPIRED_UNCLAIMED", "REVOKED")

# §9. The one state whose resolution waits on a named human (or a later deterministic proof).
EF_HUMAN_OWNED_STATES: tuple[str, ...] = ("UNKNOWN_OUTCOME",)

# §10. The states a crash may be recovered FROM without re-executing. `CLAIMED` and everything after
# it is NOT here: §36 makes a crash after the claim an UNKNOWN OUTCOME, never a re-run.
EF_RECOVERABLE_STATES: tuple[str, ...] = ("GRANTED", "CLAIMED", "ATTEMPTED")

# The outcome-aspect evidence columns §14 *Writes* names and P2 did not carry. Each is nullable: a
# GRANTED grant has attempted nothing, verified nothing, failed nothing. `claimed_at`,
# `verification_outcome` and `unknown_reason` are already on the P2 row and are not repeated here.
EF_OUTCOME_COLUMNS: tuple[str, ...] = (
    "attempted_at", "verified_at", "failure_proof", "exposure", "health_signal",
    "reality_decision_ref",
)

# The two tenant-first FKs M3 adds, by referent, for the readiness oracle to check by name (the way
# `phase6_pipeline_readiness_problems` checks its own). The generic oracle derives them from the DDL
# too; naming them here is the unit stating what it is FOR.
EF_REQUIRED_REFERENTS: tuple[str, ...] = ("checkpoint_witnesses", "pipeline_instances")

_PRIMARY_KEY_ANCHOR = "PRIMARY KEY (tenant, grant_id)"

# Each new column on its OWN line: `schema._canonical_columns` parses the DDL line by line and reads
# only the first token of a line as a column, so two columns on one line would hide the second from
# the oracle. Each FK on its OWN line for the mirror reason (a wrapped FK clause reads as a column
# named `REFERENCES`) — the exact blind spot `phase6_pipeline_instances` documents.
_NEW_COLUMNS_SQL = "".join(f"            {col} TEXT,\n" for col in EF_OUTCOME_COLUMNS)
_NEW_FOREIGN_KEYS_SQL = (
    ",\n"
    "            FOREIGN KEY (tenant, checkpoint_id) REFERENCES checkpoint_witnesses "
    "(tenant, checkpoint_id) DEFERRABLE INITIALLY DEFERRED,\n"
    "            FOREIGN KEY (tenant, pipeline_instance_id) REFERENCES pipeline_instances "
    "(tenant, pipeline_instance_id)"
)


def _extended_effect_grants_ddl() -> str:
    """P2's `effect_grants` DDL, with the six outcome columns and two FKs woven in.

    Derived from P2's text rather than restated, so a change to the base ledger shape flows here
    automatically instead of drifting. The columns go BEFORE the primary-key table constraint (a
    column definition may not follow a table constraint in SQLite) and the FKs go AFTER it.
    """
    base = _P2_TARGET_SCHEMA["effect_grants"]
    if _PRIMARY_KEY_ANCHOR not in base:
        raise RuntimeError(
            "the canonical effect_grants DDL no longer declares "
            f"{_PRIMARY_KEY_ANCHOR!r}; M3 injects its columns and FKs around that anchor and cannot "
            "guess where they belong. This is a refusal, not a fallback."
        )
    if base.count(_PRIMARY_KEY_ANCHOR) != 1:
        raise RuntimeError(
            f"the effect_grants DDL declares {_PRIMARY_KEY_ANCHOR!r} more than once; the injection "
            "anchor must be unique."
        )
    return base.replace(
        _PRIMARY_KEY_ANCHOR,
        _NEW_COLUMNS_SQL + "            " + _PRIMARY_KEY_ANCHOR + _NEW_FOREIGN_KEYS_SQL,
        1,
    )


# The overriding view: merged LAST into `schema._ALL_TARGET_SCHEMA`, so the readiness oracle's
# derived column/FK contract and the fresh-database builder both see the M3-shaped ledger.
P6EF_TARGET_SCHEMA: dict[str, str] = {"effect_grants": _extended_effect_grants_ddl()}

# M3 adds no index and no trigger. The Layer-1 reservation is M2's; the Layer-2 live-hold and
# commit-once indexes are P3's and are untouched. Declared empty so a future addition is deliberate.
P6EF_INDEXES: dict[str, str] = {}
P6EF_REPLACED_INDEXES: tuple[str, ...] = ()

# The ledger's own indexes, recreated verbatim after a table rebuild. Read from P3/P2 rather than
# retyped: a rebuild that silently dropped the live-hold index would let two effects exist at once.
from .phase2_tenant_first import INDEXES as _P2_INDEXES  # noqa: E402
from .phase3_checkpoint import P3_INDEXES as _P3_INDEXES  # noqa: E402

_EFFECT_GRANTS_INDEX_DDLS: tuple[str, ...] = tuple(
    ddl for ddl in {**_P2_INDEXES, **_P3_INDEXES}.values()
    if " ON effect_grants " in ddl and "ix_effect_grants_tenant_commit_key" not in ddl
)


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _referents(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[2] for r in conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()}


def _rebuild_effect_grants_with_foreign_keys(conn: sqlite3.Connection) -> list[str]:
    """Add the two FKs to an existing `effect_grants` the only way SQLite allows: rebuild it.

    The canonical 12-step ALTER (SQLite docs §"Making Other Kinds Of Table Schema Changes"): FKs
    OFF (outside a transaction), copy every existing column into a new table built from the extended
    DDL, drop the old, rename, recreate the ledger's indexes, verify no FK violation, FKs back ON.
    The new outcome columns land NULL — a grant that predates M3 attempted, verified and failed
    nothing, which is exactly what NULL says.

    Only the migrated path reaches this; a fresh database is already M3-shaped and never rebuilds.
    """
    performed: list[str] = []
    existing = set(_columns(conn, "effect_grants"))
    carried = [c for c in existing if c not in EF_OUTCOME_COLUMNS]
    carried_sql = ", ".join(carried)
    new_ddl = _extended_effect_grants_ddl().replace(
        "CREATE TABLE effect_grants", "CREATE TABLE _p6ef_effect_grants_new", 1)

    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(new_ddl)
        conn.execute(
            f"INSERT INTO _p6ef_effect_grants_new ({carried_sql}) "
            f"SELECT {carried_sql} FROM effect_grants"
        )
        conn.execute("DROP TABLE effect_grants")
        conn.execute("ALTER TABLE _p6ef_effect_grants_new RENAME TO effect_grants")
        for ddl in _EFFECT_GRANTS_INDEX_DDLS:
            conn.execute(ddl)
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(
                f"rebuilding effect_grants introduced {len(violations)} foreign-key violation(s): "
                f"{violations}. The rebuild is abandoned; the ledger is unchanged."
            )
        conn.commit()
        performed.append("rebuild-table:effect_grants(+fk checkpoint_witnesses,pipeline_instances)")
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
    return performed


def create_phase6_external_effects_schema(conn: sqlite3.Connection, *, now: str) -> list[str]:
    """Give `effect_grants` the outcome columns and the two FKs. Idempotent; returns what it did.

    On a fresh canonical database the ledger already carries both (the extended DDL built it), so
    this is a no-op. On a P2-shaped database it adds the columns with `ALTER TABLE` and rebuilds the
    table to add the FKs. Either way the resulting shape is byte-identical to the fresh one.
    """
    performed: list[str] = []
    if "effect_grants" not in _tables(conn):
        # The ledger itself is missing — a broken database, not M3's to create. Readiness reports it.
        return performed

    present_columns = set(_columns(conn, "effect_grants"))
    missing_columns = [c for c in EF_OUTCOME_COLUMNS if c not in present_columns]
    for column in missing_columns:
        conn.execute(f"ALTER TABLE effect_grants ADD COLUMN {column} TEXT")
        performed.append(f"add-column:effect_grants.{column}")

    referents = _referents(conn, "effect_grants")
    if any(ref not in referents for ref in EF_REQUIRED_REFERENTS):
        performed.extend(_rebuild_effect_grants_with_foreign_keys(conn))

    conn.commit()
    return performed


def stamp_phase6_external_effects_version(conn: sqlite3.Connection, *, now: str) -> None:
    """Record the M3 marker — callable ONLY once readiness holds. Marker-last, like every phase."""
    problems = phase6_external_effects_readiness_problems(conn)
    if problems:
        raise RuntimeError(
            f"refusing to stamp {P6EF_SCHEMA_VERSION} on a database that is NOT ready: "
            + "; ".join(problems)
        )
    if "schema_migrations" in _tables(conn):
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration, step, applied_at, detail) "
            "VALUES (?,?,?,?)",
            (MIGRATION_ID, f"version:{P6EF_SCHEMA_VERSION}", now,
             "the External Effect / Effect Grant outcome columns and the witness/pipeline foreign "
             "keys; readiness proven"),
        )
        conn.commit()


def phase6_external_effects_readiness_problems(conn: sqlite3.Connection) -> list[str]:
    """Every reason the ledger cannot carry the M3 outcome aspect. Empty == ready.

    Structural, like the P2/P3/P5/M1/M2 oracles it extends. The FKs are read out of the live database
    by referent — a `checkpoint_id` that any string satisfies is the decoration this unit exists to
    remove — and the outcome columns are verified present because a machine that writes `failure_proof`
    to a column that is not there fails at runtime, not at readiness.
    """
    problems: list[str] = []
    if "effect_grants" not in _tables(conn):
        # The generic oracle already reports the missing ledger; M3 adds nothing to that noise.
        return problems

    live_columns = set(_columns(conn, "effect_grants"))
    missing = [c for c in EF_OUTCOME_COLUMNS if c not in live_columns]
    if missing:
        problems.append(
            f"effect_grants is missing the M3 outcome column(s) {missing}: "
            f"03-external-effect-grant.machine.md §14 writes these at EF-3/EF-3f/EF-3u/EF-4/EF-5, and "
            f"a machine that writes to a column that is not there fails closed at the worst moment."
        )

    referents = _referents(conn, "effect_grants")
    for referent in EF_REQUIRED_REFERENTS:
        if referent not in referents:
            problems.append(
                f"effect_grants declares no foreign key into {referent!r}: 'mint requires real "
                f"checkpoint authority' is decoration while checkpoint_id and pipeline_instance_id "
                f"are unconstrained text columns any string satisfies (the same argument M1 made for "
                f"owner_id and M2 for its witness and grant references)."
            )
    return problems
