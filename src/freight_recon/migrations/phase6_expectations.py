"""Phase 6 — M8, the Expectation: one `expectations` row per owed observation, one machine, six
states, and the one honesty rule that makes Neyma tell "the POD never came" apart from "we were not
watching."

WHAT THIS TABLE IS, IN FREIGHT TERMS

    A load delivers at the Denver facility and a POD is owed by 17:00. Neyma RAISES an Expectation
    over a DECLARED channel (the carrier mailbox), storing the deadline in UTC with Denver retained
    beside it. 17:00 passes. If the mailbox was demonstrably healthy the whole window, the
    Expectation is `OVERDUE` and a named human owns it — the thing never came, and we can prove we
    were watching. If instead the tracking feed was down, it is `INDETERMINATE`, because accusing the
    carrier of a failure that was OURS is the one thing this machine may never do. The POD arrives in
    month four and it STILL discharges, because a late POD is still a POD. The appointment moves and
    the deadline RE-VERSIONS with its history rather than being edited. The load cancels and the
    Expectation `CANCELLED`s through its one canonical transition. An aged Expectation `EXPIRED`s
    explicitly and audibly — never swept away by a reaper nobody reads.

    ### AN EXPECTATION OWES SOMETHING; IT DOES NOT AUTHORIZE ANYTHING (entity §4/§38/§40). It is not
    a bare timer, not an SLA, not a gate. It carries OBSERVABILITY COVERAGE, and it is not an
    accusation until observability is proven.

WHY `OVERDUE` WITHOUT A HEALTHY coverage_ref IS STRUCTURALLY IMPOSSIBLE (entity §16/§37, M-32)

    `coverage_ref` points at an `observation_coverage` record — a positive, persisted statement that
    the declared channel was HEALTHY over the required window, written by the channel's own health
    probe (P9+) or, for the dark unit under test, by the probe and the tests. The health that
    justifies `OVERDUE` is not asserted by the Expectation: `coverage_health` is tied to the REAL
    coverage row by a COMPOSITE FOREIGN KEY `(tenant, coverage_ref, coverage_health)`, so it cannot
    lie about the row's health, and a `CHECK (state <> 'OVERDUE' OR coverage_health = 'HEALTHY')`
    then requires that tied-down health to be HEALTHY. Absent + Down + Unknown + Partial all fail the
    CHECK — it fails TOWARD blindness, the safe direction. ### THE ABSENCE OF A COVERAGE RECORD IS NOT
    HEALTH: no row ⇒ `INDETERMINATE`, never `OVERDUE`.

WHY THERE IS AT MOST ONE LIVE RAISED EXPECTATION PER KEY

    `expectation_key = (tenant, subject_ref, expected_type)` (entity §9), stored as a scalar, and
    ### `UNIQUE (tenant, expectation_key) WHERE state = 'RAISED'` (entity §17, machine §15/§17/§19) —
    a PARTIAL unique index, not an application-level check-then-insert two concurrent raisers both
    pass. M4's `WHERE state IN ('REQUESTED','GRANTED')` and M6's `WHERE state = 'CONFIRMED'` are the
    precedent. ### M8-AQ-3 — three canonical files (entity §17, machine §15, F8 cross-cutting) say
    `WHERE state = 'RAISED'`; the target-spec §12.8 Duplicate-prevention line says "while
    non-terminal". Both readings agree on AT MOST ONE `RAISED` per key; this migration implements the
    `WHERE state = 'RAISED'` reading (three files to one, and the tighter window is the same
    fail-closed direction), records the other, and resolves NEITHER by widening a specification.

WHY AN OVERDUE / INDETERMINATE EXPECTATION HAS A NAMED HUMAN OWNER

    `owner_id` is FK-backed into `tenant_humans` (M1's precedent) and required by
    `CHECK (state NOT IN ('OVERDUE','INDETERMINATE') OR owner_id IS NOT NULL)`. "A human owns the
    blindness" is decoration while `owner_id` is a free-text column, so an ownerless human-owned state
    is structurally impossible (AC-SAFE-028). A model is not a human and may not be the owner.

WHY THE OBSERVATION CHANNEL IS DECLARED AT CREATION OR THERE IS NO EXPECTATION

    `expected_source` is `NOT NULL` (entity §21). An Expectation with no declared channel cannot be
    judged at its deadline at all — it has no honest deadline behaviour to have.

WHAT IS DELIBERATELY *NOT* HERE (the seams this unit does not own)

    No seventh state — six only (`RAISED, DISCHARGED, OVERDUE, INDETERMINATE, CANCELLED, EXPIRED`),
    no `TIMED_OUT`, no `STALE`, no `RESOLVED` (M9's vocabulary), no `MISSED`, no `LATE`, no `CLOSED`,
    no `PENDING`. No `exceptions` table and no `EC-*` (### M8-AQ-1: M8 emits its OWN F8 events and
    leaves a durable, human-owned row; it mints no M9 event, exactly as M5's UNPARSEABLE/UNBOUND seam
    does). No `compensations`, `evidence`, `policies` or `rules` table. The freight subject
    projection (`subject_kind = 'entity'`) is P9+ and carries no FK (### M8-AQ-4).

WHAT THE FOREIGN KEYS POINT AT (entity §18, task §3.9)

    `owner_id` -> `tenant_humans` (M1). `discharge_observation_id` -> `observations` (M5).
    `coverage_ref` -> `observation_coverage` (M8's OWN table). `subject_observation_ref` (the
    `subject_kind = 'observation'` reading of `subject_ref`, K-2) -> `observations` (M5). The
    `subject_kind = 'entity'` reading (a load/document/movement, entity §10) points at a freight
    projection that is P9+ and so carries NO FK — the K-2/§10 disagreement is `M8-AQ-4`, REPORTED and
    built only where a target exists.

FRESH == MIGRATED, SHIPS DARK

    `create_canonical_schema` builds these tables directly; a database reached by
    `phase2_tenant_first.migrate` reaches the SAME shape through `create_phase6_expectations_schema`.
    Nothing routes production traffic through M8; `expectation.py` is the only non-test module that
    reads it, and only `scripts/probe_phase6_expectation.py` imports the machine. NO channel health
    probe, poller or coverage importer ships with M8 — coverage rows under test are written by the
    probe and the tests.
"""

from __future__ import annotations

import sqlite3

MIGRATION_ID = "phase6_expectations"
P6EX_SCHEMA_VERSION = "phase6-expectations-1"

# Tenant-owned. An Expectation is owed WITHIN one brokerage, and a coverage window is a statement
# about ONE brokerage's channel; the same key or channel in two tenants is two isolated rows [C-1].
P6EX_TENANT_TABLES: tuple[str, ...] = ("expectations", "observation_coverage")

# Nothing tenant-exempt. Stated rather than omitted, so a future addition must defend its exemption.
P6EX_EXEMPT_TABLES: tuple[str, ...] = ()

# `state-machines/registry.md` §4, M8 / target spec §12.8 — the SIX, in the registry's own order.
# There is no seventh: no TIMED_OUT, no STALE, no RESOLVED (M9's), no MISSED/LATE/CLOSED/PENDING.
EXPECTATION_STATES: tuple[str, ...] = (
    "RAISED", "DISCHARGED", "OVERDUE", "INDETERMINATE", "CANCELLED", "EXPIRED",
)

# machine §8 — the three terminal states (no outgoing enumerated transition to a live state).
TERMINAL_EXPECTATION_STATES: tuple[str, ...] = ("DISCHARGED", "CANCELLED", "EXPIRED")

# machine §9 — the two non-terminal human-owned states. Each carries a named owner_id (CHECK below).
HUMAN_OWNED_EXPECTATION_STATES: tuple[str, ...] = ("OVERDUE", "INDETERMINATE")

# entity §17, machine §15/§17/§19, F8 cross-cutting — the state the partial unique index covers.
# ### M8-AQ-3: three files say WHERE state='RAISED'; target spec §12.8 says "while non-terminal".
# Implemented as RAISED (recorded above); every reading agrees on at-most-one RAISED per key.
LIVE_EXPECTATION_STATES: tuple[str, ...] = ("RAISED",)

# K-2's reference-kind discriminator for `subject_ref` (### M8-AQ-4). `observation` is FK-backed into
# observations (M5, the table that exists); `entity` is a load/document/movement projection (P9+) and
# carries no FK. There is no third; the CHECK refuses one.
SUBJECT_KINDS: tuple[str, ...] = ("observation", "entity")

# The CLOSED coverage-health vocabulary (task §3.6). A positive assertion, or it is not health.
# `HEALTHY` is the ONLY value that may justify `OVERDUE`. `ABSENT` is DELIBERATELY NOT a value: the
# absence of a coverage record is modelled as NO ROW, and NO ROW ⇒ INDETERMINATE (M-32) — health is
# never inferred from an absence.
COVERAGE_HEALTH: tuple[str, ...] = ("HEALTHY", "DOWN", "UNKNOWN", "PARTIAL")

# The one health value that proves the channel was watching. Interpolated into the OVERDUE CHECK.
HEALTHY_COVERAGE = "HEALTHY"

# The referents the readiness oracle checks by name. Derived from the DDL by the generic FK loop too;
# naming them here is the unit stating what they are FOR.
P6EX_EXPECTATION_REFERENTS: tuple[str, ...] = (
    "tenant_humans", "observations", "observation_coverage",
)

_STATES_SQL = ",".join(f"'{s}'" for s in EXPECTATION_STATES)
_HUMAN_OWNED_SQL = ",".join(f"'{s}'" for s in HUMAN_OWNED_EXPECTATION_STATES)
_SUBJECT_KINDS_SQL = ",".join(f"'{k}'" for k in SUBJECT_KINDS)
_HEALTH_SQL = ",".join(f"'{h}'" for h in COVERAGE_HEALTH)

# The exact abort texts, worded WITHOUT apostrophes: they are interpolated into single-quoted SQL
# literals inside RAISE(ABORT, ...). Matched by `expectation.py` when it classifies an IntegrityError.
VERSION_ABORT = (
    "expectations.version advances by exactly one per state transition [GR-3, C-10]: a state change "
    "that does not advance it silently overwrites another transition. OCC on the expectation version "
    "is the concurrency guard, and a version that stands still is a lost update"
)
IDENTITY_ABORT = (
    "the identity of an expectation is immutable [entity 11 sec 22, C-8]: the tenant, the id, the "
    "subject it awaits, the kind of subject reference, the expected type, the duplicate-prevention "
    "key, the originating timezone and when it was raised are what make it THIS expectation. A "
    "deadline may be re-versioned [EX-5]; the subject and the expected type may not, or a POD "
    "expectation would quietly become a remittance expectation for another load"
)
DELETE_ABORT = (
    "an expectation is never deleted [entity 11 sec 28/29, C-9]: retention is permanent, and a "
    "cancelled or expired expectation is retained so the silence it recorded can be shown. A row "
    "that quietly stops being visible is the exact failure the Expectation exists to prevent, one "
    "level up — no sweep, no reaper, no scan"
)
COVERAGE_IMMUTABLE_ABORT = (
    "an observation-coverage record is immutable [entity 11 sec 34, GR-11, K-3]: replay reconstructs "
    "the OVERDUE-vs-INDETERMINATE honesty split from the coverage recorded AT THE TIME, so editing a "
    "recorded health or window would make a rebuild reach a different verdict next Tuesday. A changed "
    "channel state is a NEW coverage window, never an edit of an old one"
)
COVERAGE_DELETE_ABORT = (
    "an observation-coverage record is never deleted [entity 11 sec 34, C-9]: it is the positive "
    "evidence a replay folds to decide OVERDUE vs INDETERMINATE, and deleting it would turn a proven "
    "overdue into a blind window on rebuild — a fact reconstructed from an absence"
)


P6EX_TARGET_SCHEMA: dict[str, str] = {
    # THE EXPECTATION (`entities/11-expectation.md`, spec §12.8, machine M8).
    #
    # Every column on its OWN line and every FOREIGN KEY / CHECK / PRIMARY KEY / UNIQUE on its OWN
    # physical line, and every multi-condition CHECK on ONE physical line: `schema._canonical_columns`
    # parses this DDL line by line, reads only the first token of a line as a column, and skips a line
    # that STARTS with PRIMARY KEY / FOREIGN KEY / UNIQUE / CHECK. A wrapped clause would read as a
    # phantom column called `REFERENCES` or `OR` — the blind spot `phase6_pipeline_instances`
    # documents and this repository produced four times.
    "expectations": """
        CREATE TABLE expectations (
            tenant TEXT NOT NULL,
            expectation_id TEXT NOT NULL,
            -- ### THE AWAITED SUBJECT and its kind discriminator (### M8-AQ-4, K-2 vs entity §10).
            -- subject_ref is the single source of truth; subject_observation_ref MIRRORS it for the
            -- `observation` kind (the table that exists) and carries the FK, and the CHECKs below keep
            -- it consistent with subject_ref/subject_kind. The `entity` kind (a load/document/movement)
            -- is a freight projection (P9+) and carries no FK — a FK into a table this unit does not own
            -- would be half of a machine it does not build.
            subject_ref TEXT NOT NULL,
            subject_kind TEXT NOT NULL CHECK (subject_kind IN (%(subject_kinds)s)),
            subject_observation_ref TEXT,
            -- The kind of observation owed (POD, remittance, appointment confirmation…). Open by
            -- design (entity §10 ends with an ellipsis): it is freight-domain vocabulary, not a closed
            -- machine enum, so it is NOT NULL and non-empty rather than CHECK-enumerated.
            expected_type TEXT NOT NULL,
            -- ### THE OBSERVABILITY CHANNEL, DECLARED AT CREATION OR THERE IS NO EXPECTATION (entity
            -- §21). NOT NULL: an expectation with no declared channel cannot be judged at its deadline.
            expected_source TEXT NOT NULL,
            -- ### THE DUPLICATE-PREVENTION KEY = (tenant, subject_ref, expected_type) (entity §9),
            -- carried as a scalar so the partial unique index below is one tenant-first read. The
            -- machine derives it deterministically; the CHECK keeps it from being set to something else.
            expectation_key TEXT NOT NULL,
            -- ### THE DEADLINE, STORED IN UTC, WITH THE FACILITY TIMEZONE RETAINED (entity §16/§42,
            -- F-25). deadline_utc is an RFC-3339 UTC instant; originating_timezone is the facility IANA
            -- zone the appointment window was evaluated in. A 17:00 Denver appointment is not 17:00 UTC.
            deadline_utc TEXT NOT NULL,
            originating_timezone TEXT NOT NULL,
            -- ### THE SIX CANONICAL STATES, ENUMERATED INLINE ON THE COLUMN (registry §4, M8). One
            -- physical line so the readiness parser reads `state` as NOT NULL and DDL introspection
            -- finds the vocabulary ON the column: there is no seventh state, no TIMED_OUT, no STALE, no
            -- RESOLVED. Interpolated from EXPECTATION_STATES, the single source of truth.
            state TEXT NOT NULL CHECK (state IN (%(states)s)),
            version INTEGER NOT NULL,
            -- Set on discharge (EX-2/EX-4): the BOUND observation that discharged this expectation, and
            -- whether it arrived late. A late arrival is ALWAYS accepted and marked late (entity §26).
            discharge_observation_id TEXT,
            late INTEGER,
            -- ### THE COVERAGE BASIS FOR THE HONESTY SPLIT (entity §11/§13/§16). coverage_ref points at
            -- the observation_coverage record consulted at the deadline; coverage_health is the health
            -- of THAT row, tied to it by the composite FK below so it cannot be asserted independently.
            -- coverage_gap records WHY an INDETERMINATE window was blind (down / unknown / partial /
            -- absent). overdue_at stamps when the deadline was judged.
            coverage_ref TEXT,
            coverage_health TEXT,
            coverage_gap TEXT,
            overdue_at TEXT,
            -- ### THE NAMED HUMAN who owns an OVERDUE / INDETERMINATE expectation (entity §11, machine
            -- §5, AC-SAFE-028). A FK into the tenant's recorded humans; the CHECK below makes an
            -- ownerless human-owned state a structurally impossible state. A model is not a human.
            owner_id TEXT,
            -- The retained deadline history (entity §19, EX-5): a JSON array of prior deadline_utc
            -- values. A re-versioned deadline is NOT a supersession — the history is kept, not erased.
            deadline_history TEXT,
            -- The caller-supplied terminal age (V10, task §3.11). NO default that means anything — a
            -- test or probe supplies its own; the MECHANISM (EX-7) is complete, the THRESHOLD is not a
            -- product decision this unit makes. Milliseconds past OVERDUE/INDETERMINATE before EXPIRED.
            terminal_age_ms INTEGER,
            -- The model's PROPOSED confidence (entity §35, GR-8). Stored so the negative control is
            -- demonstrable and NEVER read by a guard: confidence never turns INDETERMINATE into OVERDUE.
            proposed_confidence TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            PRIMARY KEY (tenant, expectation_id),
            -- The owner is a recorded human of THIS tenant; the discharging observation and the
            -- subject-observation are observations of THIS tenant; the coverage record is this tenant's.
            -- Each on its OWN line so the readiness parser skips it as a non-column.
            FOREIGN KEY (tenant, owner_id) REFERENCES tenant_humans (tenant, human_id),
            FOREIGN KEY (tenant, discharge_observation_id) REFERENCES observations (tenant, observation_id),
            FOREIGN KEY (tenant, subject_observation_ref) REFERENCES observations (tenant, observation_id),
            FOREIGN KEY (tenant, coverage_ref) REFERENCES observation_coverage (tenant, coverage_id),
            -- ### THE COMPOSITE FK THAT TIES coverage_health TO THE REAL COVERAGE ROW (entity §16). It
            -- references the UNIQUE (tenant, coverage_id, health) index on observation_coverage, so an
            -- expectation cannot claim a health its coverage row does not carry. Combined with the
            -- OVERDUE CHECK below, `OVERDUE` without a genuinely HEALTHY coverage_ref is impossible.
            FOREIGN KEY (tenant, coverage_ref, coverage_health) REFERENCES observation_coverage (tenant, coverage_id, health),
            -- The state-vocabulary CHECK lives INLINE on the column above (declared once).
            CHECK (version >= 1),
            -- ### OVERDUE REQUIRES A coverage_ref PROVING THE CHANNEL WAS HEALTHY (entity §16/§37,
            -- M-32). On ONE physical line. The composite FK guarantees coverage_health is the row's
            -- real health; this CHECK requires it to be HEALTHY. No healthy coverage ⇒ no OVERDUE.
            CHECK (state <> 'OVERDUE' OR (coverage_ref IS NOT NULL AND coverage_health = '%(healthy)s')),
            -- ### AN OVERDUE OR INDETERMINATE EXPECTATION NAMES A HUMAN (entity §11, AC-SAFE-028). On
            -- ONE line: a wrapped continuation would read as a column called OR.
            CHECK (state NOT IN (%(human_owned)s) OR owner_id IS NOT NULL),
            -- Discharge records the observation that discharged it (entity §13, EX-2/EX-4).
            CHECK (state <> 'DISCHARGED' OR discharge_observation_id IS NOT NULL),
            -- coverage_health, when present, is one of the closed health values (belt-and-braces beside
            -- the composite FK, so a coverage_health with no coverage_ref is still constrained).
            CHECK (coverage_health IS NULL OR coverage_health IN (%(health)s)),
            -- ### THE subject_observation_ref MIRROR IS CONSISTENT WITH subject_kind (### M8-AQ-4). An
            -- `observation` subject sets subject_observation_ref = subject_ref; an `entity` subject sets
            -- neither, and subject_ref carries the projection token. Each on ONE physical line.
            CHECK (subject_kind <> 'observation' OR subject_observation_ref = subject_ref),
            CHECK (subject_kind = 'observation' OR subject_observation_ref IS NULL),
            -- The duplicate-prevention key is exactly (subject_ref, expected_type) joined — the machine
            -- may not point it at a different subject than the row's own. On ONE physical line.
            CHECK (expectation_key = subject_ref || '::' || expected_type),
            CHECK (trim(expectation_id) <> ''),
            CHECK (trim(subject_ref) <> ''),
            CHECK (trim(expected_type) <> ''),
            CHECK (trim(expected_source) <> ''),
            CHECK (trim(deadline_utc) <> ''),
            CHECK (trim(originating_timezone) <> ''),
            CHECK (trim(state) <> '')
        )""" % {
            "subject_kinds": _SUBJECT_KINDS_SQL, "states": _STATES_SQL,
            "human_owned": _HUMAN_OWNED_SQL, "health": _HEALTH_SQL, "healthy": HEALTHY_COVERAGE,
        },
    # THE OBSERVATION COVERAGE (target spec §12.8 M-32, §33). ### M8-AQ-2: canon names the state
    # `observation_coverage` and makes coverage_ref a FOREIGN KEY into it, but no 45-point entity file,
    # no machine and no event family specifies it. M8 READS it; it does not become an observation
    # system. This is the smallest shape every reading agrees on: a per-(channel, window) health
    # record, tenant-first, with a CLOSED health vocabulary, written by the channel's health probe
    # (P9+) or, under test, by the probe and the tests. It is NOT a second Observation (M5 is landed).
    "observation_coverage": """
        CREATE TABLE observation_coverage (
            tenant TEXT NOT NULL,
            coverage_id TEXT NOT NULL,
            -- The channel this record is a health statement ABOUT — it matches an expectation's
            -- expected_source. Coverage is a statement about a channel over a window, not about a fact.
            channel TEXT NOT NULL,
            -- The window this record covers. A HEALTHY row must span the whole required window, or the
            -- machine reads it as PARTIAL — "throughout the window" is the EX-3 half a partial defeats.
            window_start TEXT NOT NULL,
            window_end TEXT NOT NULL,
            -- ### HEALTH IS A PERSISTED, POSITIVE ASSERTION (task §3.6). One of the closed vocabulary;
            -- there is no ABSENT value, because absence is modelled as NO ROW and NO ROW ⇒
            -- INDETERMINATE. Enumerated inline so DDL introspection finds the vocabulary on the column.
            health TEXT NOT NULL CHECK (health IN (%(health)s)),
            -- Who wrote this coverage assertion (the channel health probe, or the probe/tests under the
            -- dark unit). Provenance of the observability statement itself; never a gate input.
            probe_source TEXT NOT NULL,
            recorded_at TEXT NOT NULL,

            PRIMARY KEY (tenant, coverage_id),
            CHECK (trim(coverage_id) <> ''),
            CHECK (trim(channel) <> ''),
            CHECK (trim(window_start) <> ''),
            CHECK (trim(window_end) <> ''),
            CHECK (trim(probe_source) <> '')
        )""" % {"health": _HEALTH_SQL},
}


P6EX_INDEXES: dict[str, str] = {
    # ### AT MOST ONE LIVE RAISED EXPECTATION PER KEY — A PARTIAL UNIQUE INDEX (entity §17, machine
    # §15/§17, F8 Dedup). Under a race of concurrent raisers, one wins and every other hits THIS
    # index — the loser then coalesces rather than creating a second live expectation for one owed
    # observation. Drop the UNIQUE, or drop the WHERE clause, or drop the tenant, and two live RAISED
    # expectations fit one key: the duplicate-prevention the whole unit rests on, switched off.
    "ix_expectations_one_live_per_key":
        "CREATE UNIQUE INDEX ix_expectations_one_live_per_key "
        "ON expectations (tenant, expectation_key) WHERE state IN (%(live)s)"
        % {"live": ",".join(f"'{s}'" for s in LIVE_EXPECTATION_STATES)},
    # The human's queue: the overdue/indeterminate expectations a human owns, by age.
    "ix_expectations_owner_queue":
        "CREATE INDEX ix_expectations_owner_queue ON expectations (tenant, state, owner_id)",
    # The subject read across every state (open and discharged/expired history).
    "ix_expectations_subject":
        "CREATE INDEX ix_expectations_subject "
        "ON expectations (tenant, subject_ref, expected_type, state)",
    # ### THE COMPOSITE-FK TARGET (entity §16). The composite FK (tenant, coverage_ref,
    # coverage_health) needs a UNIQUE index on the parent's (tenant, coverage_id, health) — coverage_id
    # is already unique per tenant, so this is trivially unique and exists to make the FK legal, which
    # is what ties coverage_health to the real coverage row.
    "ix_observation_coverage_health":
        "CREATE UNIQUE INDEX ix_observation_coverage_health "
        "ON observation_coverage (tenant, coverage_id, health)",
    # The coverage lookup the machine performs at a deadline: this tenant's records for one channel.
    "ix_observation_coverage_channel":
        "CREATE INDEX ix_observation_coverage_channel "
        "ON observation_coverage (tenant, channel, window_start, window_end)",
}

# Nothing from an earlier phase is replaced. Declared so a future replacement has somewhere to go.
P6EX_REPLACED_INDEXES: tuple[str, ...] = ()


P6EX_TRIGGERS: dict[str, str] = {
    # ### OCC ON THE EXPECTATION (GR-3, C-10, machine §17). A state transition advances version by
    # exactly one; a state change that leaves version standing is two transitions claiming one version.
    # (An EX-5 re-version changes deadline_utc AND advances version, so it does not fail this.)
    "trg_expectations_version_advances_on_state_change": f"""
        CREATE TRIGGER trg_expectations_version_advances_on_state_change
        BEFORE UPDATE ON expectations
        WHEN NEW.state <> OLD.state AND NEW.version <> OLD.version + 1
        BEGIN SELECT RAISE(ABORT, '{VERSION_ABORT}'); END""",
    # ### THE IDENTITY OF THE EXPECTATION IS IMMUTABLE, BUT THE DEADLINE IS NOT (entity §22, EX-5). The
    # subject, the subject kind, the expected type, the key, the originating timezone and created_at may
    # not be edited — editing them would retarget the expectation in place. deadline_utc is DELIBERATELY
    # ABSENT from this list because EX-5 re-versions it.
    "trg_expectations_identity_immutable": f"""
        CREATE TRIGGER trg_expectations_identity_immutable
        BEFORE UPDATE OF tenant, expectation_id, subject_ref, subject_kind, expected_type,
                         expectation_key, originating_timezone, created_at
        ON expectations
        BEGIN SELECT RAISE(ABORT, '{IDENTITY_ABORT}'); END""",
    # ### NO DELETION, EVER (entity §28/§29, C-9). Retention is permanent; a cancelled or expired
    # expectation is retained. NO SWEEP, NO REAPER: a row that quietly disappears is the failure this
    # machine exists to prevent one level up.
    "trg_expectations_no_delete": f"""
        CREATE TRIGGER trg_expectations_no_delete
        BEFORE DELETE ON expectations
        BEGIN SELECT RAISE(ABORT, '{DELETE_ABORT}'); END""",
    # ### A COVERAGE RECORD IS IMMUTABLE (entity §34, GR-11). Replay reconstructs the honesty split
    # from the coverage recorded at the time; editing a recorded health or window would make a rebuild
    # reach a different verdict. A changed channel state is a NEW window, never an edit.
    "trg_observation_coverage_immutable": f"""
        CREATE TRIGGER trg_observation_coverage_immutable
        BEFORE UPDATE OF health, window_start, window_end, channel ON observation_coverage
        BEGIN SELECT RAISE(ABORT, '{COVERAGE_IMMUTABLE_ABORT}'); END""",
    # ### A COVERAGE RECORD IS NEVER DELETED (entity §34, C-9). It is the positive evidence a replay
    # folds; deleting it would turn a proven overdue into a blind window on rebuild.
    "trg_observation_coverage_no_delete": f"""
        CREATE TRIGGER trg_observation_coverage_no_delete
        BEFORE DELETE ON observation_coverage
        BEGIN SELECT RAISE(ABORT, '{COVERAGE_DELETE_ABORT}'); END""",
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


def create_phase6_expectations_schema(conn: sqlite3.Connection, *, now: str) -> list[str]:
    """Create whatever M8 structure is missing. Idempotent; returns what it did.

    Callable on a fresh canonical database and on an already-migrated one. Either way the resulting
    structure is byte-identical, because there is only one text. Built AFTER M5 (`observations` FK)
    and M1 (`tenant_humans` FK), which is why `schema.py` orders it after them.
    """
    performed: list[str] = []
    present = _tables(conn)
    for name in (*P6EX_TENANT_TABLES, *P6EX_EXEMPT_TABLES):
        if name not in present:
            conn.execute(P6EX_TARGET_SCHEMA[name])
            performed.append(f"create-table:{name}")
    existing = _indexes(conn)
    for name, ddl in P6EX_INDEXES.items():
        if name not in existing:
            conn.execute(ddl)
            performed.append(f"create-index:{name}")
    for stale in P6EX_REPLACED_INDEXES:
        if stale in _indexes(conn):
            conn.execute(f"DROP INDEX {stale}")
            performed.append(f"drop-index:{stale}")
    existing_triggers = _triggers(conn)
    for name, ddl in P6EX_TRIGGERS.items():
        if name not in existing_triggers:
            conn.execute(ddl)
            performed.append(f"create-trigger:{name}")
    # NO VERSION STAMP HERE — marker-last, like every phase. A stamp on a half-migrated database is
    # how a missing trigger goes unnoticed.
    conn.commit()
    return performed


def stamp_phase6_expectations_version(conn: sqlite3.Connection, *, now: str) -> None:
    """Record the M8 marker — callable ONLY once readiness holds. Marker-last, like every phase."""
    problems = phase6_expectations_readiness_problems(conn)
    if problems:
        raise RuntimeError(
            f"refusing to stamp {P6EX_SCHEMA_VERSION} on a database that is NOT ready: "
            + "; ".join(problems)
        )
    if "schema_migrations" in _tables(conn):
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration, step, applied_at, detail) "
            "VALUES (?,?,?,?)",
            (MIGRATION_ID, f"version:{P6EX_SCHEMA_VERSION}", now,
             "the Expectation: one expectations row per owed observation, tenant-first, six states, a "
             "named ACTIVE human owner on OVERDUE/INDETERMINATE, OVERDUE structurally impossible "
             "without a HEALTHY coverage_ref (composite FK + CHECK), at most one live RAISED per key "
             "(the partial unique index), a durable-timer deadline, permanent retention, no sweep; "
             "plus observation_coverage, the persisted per-(channel, window) health record; readiness "
             "proven"),
        )
        conn.commit()


def phase6_expectations_readiness_problems(conn: sqlite3.Connection) -> list[str]:
    """Every reason this database cannot carry Expectations safely. Empty == ready.

    Structural, like the P2/P3/P5/M1..M7 oracles it extends. The partial unique index, the OVERDUE
    healthy-coverage CHECK, the human-owner CHECK, the composite coverage FK and the
    immutability/no-delete triggers are verified PRESENT because an `expectations` table without them
    is an ordinary table with an aspirational comment: a blind window could become an accusation, an
    ownerless human-owned state could exist, two live expectations could compete for one key, and a
    coverage record could be edited to change a replay's verdict.
    """
    problems: list[str] = []
    present = _tables(conn)
    for table in (*P6EX_TENANT_TABLES, *P6EX_EXEMPT_TABLES):
        if table not in present:
            problems.append(
                f"required Phase-6 table {table!r} is missing: run the {MIGRATION_ID} migration"
            )
    if not all(t in present for t in P6EX_TENANT_TABLES):
        return problems

    live_triggers = _triggers(conn)
    missing_triggers = sorted(t for t in P6EX_TRIGGERS if t not in live_triggers)
    if missing_triggers:
        problems.append(
            f"Expectation invariant triggers missing: {missing_triggers}. Without them an expectation "
            f"could be deleted (a recorded silence erased), a state transition could stand the version "
            f"still (a lost update), the subject/type could be edited in place, or a coverage record "
            f"could be mutated (a replay's honesty verdict changed) [entity §22/§28/§34, GR-3, C-9]."
        )
    live_indexes = _indexes(conn)
    for name in P6EX_INDEXES:
        if name not in live_indexes:
            problems.append(f"required Phase-6 index {name!r} is missing")
    for stale in P6EX_REPLACED_INDEXES:
        if stale in live_indexes:
            problems.append(f"replaced index {stale!r} is still present")

    # ### THE ONE-LIVE-RAISED-PER-KEY INDEX, READ OUT OF THE LIVE DATABASE RATHER THAN ASSUMED FROM
    # ITS NAME. An index called `..._one_live_per_key` that is not UNIQUE, or that has lost its
    # `WHERE state IN ('RAISED')` clause, is duplicate prevention switched off with the sign left up:
    # two live expectations for one owed observation would become insertable.
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name = ?",
        ("ix_expectations_one_live_per_key",),
    ).fetchone()
    if row is not None:
        sql = " ".join((row[0] or "").split()).upper().replace(", ", ",")
        if "UNIQUE" not in sql:
            problems.append(
                "ix_expectations_one_live_per_key is not UNIQUE: two live RAISED expectations for one "
                "key would be insertable, and 'at most one live expectation per owed observation' "
                "(entity §17) would be a convention, not a constraint."
            )
        expected_where = ("WHERE STATE IN (" + ",".join(f"'{s}'" for s in LIVE_EXPECTATION_STATES)
                          + ")").upper()
        if expected_where not in sql:
            problems.append(
                "ix_expectations_one_live_per_key has lost its `WHERE state IN ('RAISED')` clause: the "
                "partial index is what allows many discharged/expired expectations per key in history "
                "while permitting at most one live RAISED (entity §17)."
            )
        for column in ("TENANT", "EXPECTATION_KEY"):
            if column not in sql:
                problems.append(
                    f"ix_expectations_one_live_per_key does not cover {column!r}: a dropped tenant is "
                    f"cross-tenant coalescing of one key; a dropped key is not a duplicate guard."
                )

    # ### THE CHECKS AND THE VOCABULARIES, READ OUT OF THE expectations DDL. A CHECK the migration
    # intended but a live database does not carry is the invariant switched off.
    ddl_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='expectations'").fetchone()
    ddl = " ".join((ddl_row[0] if ddl_row else "" or "").split()).upper()
    compact = ddl.replace(", ", ",")

    expected_states = ("STATE IN (" + ",".join(f"'{s}'" for s in EXPECTATION_STATES) + ")").upper()
    if expected_states not in compact:
        problems.append(
            "expectations does not enumerate the six canonical states inline on the state column "
            "(registry §4, M8): without it a seventh state — a TIMED_OUT, a STALE or a bare RESOLVED — "
            "would be writable, and entity §12 and machine §14 say none exists."
        )
    for clause, why in (
        (f"STATE <> 'OVERDUE' OR (COVERAGE_REF IS NOT NULL AND COVERAGE_HEALTH = '{HEALTHY_COVERAGE}')",
         "OVERDUE requires a coverage_ref proving the channel was HEALTHY over the window (entity "
         "§16/§37, M-32): without it a blind or absent window could become an accusation — 'the POD "
         "never came' asserted while we were not watching"),
        (f"STATE NOT IN ({_HUMAN_OWNED_SQL.upper()}) OR OWNER_ID IS NOT NULL",
         "an OVERDUE or INDETERMINATE expectation names a human (entity §11, AC-SAFE-028): an "
         "ownerless human-owned state is a silent drop wearing a status"),
        ("STATE <> 'DISCHARGED' OR DISCHARGE_OBSERVATION_ID IS NOT NULL",
         "a DISCHARGED expectation records the BOUND observation that discharged it (entity §13)"),
        ("EXPECTATION_KEY = SUBJECT_REF || '::' || EXPECTED_TYPE",
         "the duplicate-prevention key is exactly (subject_ref, expected_type) (entity §9): a key "
         "pointing at a different subject than the row would defeat the partial unique index"),
    ):
        if clause not in compact:
            problems.append(f"expectations does not CHECK: {clause.lower()} — {why}.")

    # ### owner_id IS NULLABLE (it is set on OVERDUE/INDETERMINATE), so the guarantee is the CHECK
    # above plus the FK below — read the FK back rather than trust it.
    for referent in P6EX_EXPECTATION_REFERENTS:
        if referent not in _referents(conn, "expectations"):
            problems.append(
                f"expectations declares no foreign key into {referent!r}: the owner is a recorded "
                f"ACTIVE human (M1), the discharging/subject observation is an observation (M5), and "
                f"the coverage record is this tenant's (M8) — 'a named X' is decoration while the "
                f"column is free text (entity §18, task §3.9)."
            )

    # ### THE COMPOSITE COVERAGE FK, READ BACK — it is what ties coverage_health to the real coverage
    # row, so that a HEALTHY claim on an OVERDUE cannot be independently asserted. A single-column
    # coverage FK plus a free coverage_health would let a DOWN window be labelled HEALTHY.
    cov_fk_pairs = {
        (r[3], r[4]) for r in conn.execute("PRAGMA foreign_key_list(expectations)").fetchall()
        if r[2] == "observation_coverage"
    }
    if ("coverage_health", "health") not in cov_fk_pairs:
        problems.append(
            "expectations has no composite foreign key tying coverage_health to observation_coverage."
            "health: without it 'OVERDUE requires HEALTHY coverage' is only as strong as a free-text "
            "coverage_health column, and a DOWN window could be labelled HEALTHY (entity §16, M-32)."
        )

    # ### THE COVERAGE HEALTH VOCABULARY, READ OUT OF THE observation_coverage DDL. A coverage table
    # whose health column admits any string is one whose HEALTHY is not a closed, positive assertion.
    cov_ddl_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='observation_coverage'").fetchone()
    cov_ddl = " ".join((cov_ddl_row[0] if cov_ddl_row else "" or "").split()).upper()
    cov_compact = cov_ddl.replace(", ", ",")
    expected_health = ("HEALTH IN (" + ",".join(f"'{h}'" for h in COVERAGE_HEALTH) + ")").upper()
    if expected_health not in cov_compact:
        problems.append(
            "observation_coverage does not enumerate the closed health vocabulary inline on the health "
            "column (task §3.6): health is a positive, persisted assertion from a closed set — there is "
            "no ABSENT value, because absence is NO ROW and NO ROW ⇒ INDETERMINATE (M-32)."
        )
    return problems
