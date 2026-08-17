"""Phase 6 — the Pipeline Instance: one durable ATTEMPT to get one Work Item's effect done.

WHAT THIS TABLE IS, IN FREIGHT TERMS

    Work Item        "Get the POD for load 4471 and bill it."      — the obligation, and its owner
    Pipeline Instance "Attempt #1 to raise the invoice in the TMS." — one concrete try at it

A Work Item is 1:N to its Pipeline Instances. The Work Item is what the brokerage OWES; a Pipeline
Instance is what Neyma is DOING about it right now, durably, so that a crash, a restart or a
redelivered message cannot turn one attempt into two effects or lose one entirely.

WHY THE RESERVATION IS THE POINT (`ix_pipeline_instances_live_reservation`)

`02-pipeline-instance.machine.md` §14 PL-1: *"acquire Layer-1 reservation
`UNIQUE(tenant, commit_key) WHERE state ∉ terminal`"*. That partial unique index is not an
optimisation — it is the mechanism by which two proposals for the same logical effect become ONE
attempt and one operator card (PL-1b) instead of two invoices. The Commit Key is the identity of the
EFFECT (ADR-009, CLAUDE.md rule 8) and **the amount is not in it**, so "bill load 4471" is the same
logical effect whether the model proposed $1,400 or $1,450 — which is exactly why the second
proposal must be absorbed rather than raced.

### THE PREDICATE OF THAT INDEX IS ALSO §20's RETRY RULE, AND THAT IS NOT A COINCIDENCE.
§20: *"a retry is NEVER in place — a NEW Pipeline Instance, same `commit_key`, new grant, full
checkpoint. Only after a provable `FAILED` (PL-10f) or a pre-claim `VOIDED`; `NEEDS_VERIFICATION`
blocks any retry (Layer-1 held)."* Read the four terminal states against the sixteen:

    CLOSED · REJECTED · VOIDED · FAILED   terminal  ⇒ outside the index ⇒ the key is FREE ⇒ retry
    NEEDS_VERIFICATION                non-terminal  ⇒ inside  the index ⇒ the key is HELD ⇒ no retry

So "we cannot establish whether the effect happened, therefore nobody may try again" is enforced by
a database index rather than by a code path somebody has to remember. `NEEDS_VERIFICATION` never
auto-resolves and never expires (§23), so the block persists until a human establishes reality.

### TWO LAYERS, AND CLOSING A PIPELINE DOES NOT FREE THE EFFECT.
`CLOSED` is terminal, so it leaves this index — but the effect is still spoken for, because Layer-2
is `ix_effect_grants_live_hold` on `effect_grants (tenant, commit_key)` where the state is one of
GRANTED/CLAIMED/ATTEMPTED/VERIFIED/UNKNOWN_OUTCOME (P3). A verified effect holds its commit key
FOREVER there, so a second pipeline over a closed one reaches the checkpoint and is refused at the
mint with `COMMIT_KEY_HELD`. Layer 1 stops two attempts from RUNNING at once; Layer 2 stops two
effects from EXISTING. Neither is the other's backup.

WHY `checkpoint_id` AND `grant_id` ARE FOREIGN KEYS, AND WHY A TRIGGER GUARDS THE STATE SET

`foundational-machine-acceptance.md` gives M2's durable proof surface as *"row + witness/grant FK"*,
and §41(a) is *"`GRANTED` unreachable without a witness"*. A nullable text column would make that
sentence a convention. Here it is two foreign keys — into `checkpoint_witnesses` and
`effect_grants`, both P3's, both tenant-consistent — plus `trg_pipeline_instances_post_checkpoint_
carries_its_witness`, which refuses any row entering GRANTED or anything downstream of it without
both. An invented checkpoint id is not a bad value; it is an unwritable one.

WHAT IS DELIBERATELY *NOT* HERE

No grant STATE column. SD-2 gives the effect grant ONE row with EIGHT states and M3 owns it; this
machine's `GRANTED`/`CLAIMED` **reflect** that row and are co-transitioned with it. A `grant_state`
column here would be the second effect-authority system CLAUDE.md rule 17 forbids, and the two would
disagree the first time one of them was written without the other.

No money. `OutcomeUnknown` carries an `exposure`, and the canonical event is where it stays: this row
records `unknown_outcome_ref` — the event id — and `unknown_reason`. A projection that re-states an
exposure is a remembered money value with a fresh timestamp, which is the one thing K-4 forbids
outright. Ask the event; it is the audit record.

No deletion, and no reopening. §24: *"Reopening: never (reopening is at M1)."* A wrong verified
effect is undone by a Compensation (M10), never by editing the attempt that produced it — so unlike
`work_items`, whose `CLOSED` has WI-13's single door, terminal here is **absolutely** final.
"""

from __future__ import annotations

import re
import sqlite3

from .phase3_checkpoint import P3_TARGET_SCHEMA

MIGRATION_ID = "phase6_pipeline_instances"
P6PI_SCHEMA_VERSION = "phase6-pipeline-instances-1"

# Tenant-owned. A pipeline is an attempt made BY one brokerage, on one brokerage's obligation; there
# is no honest cross-tenant reading of "whose attempt is this" [C-1].
P6PI_TENANT_TABLES: tuple[str, ...] = ("pipeline_instances",)

# Nothing tenant-exempt. Stated rather than omitted, so a future addition must defend its exemption.
P6PI_EXEMPT_TABLES: tuple[str, ...] = ()

# `state-machines/registry.md` §4, M2 — the SIXTEEN, in the specification's own order.
PIPELINE_STATES: tuple[str, ...] = (
    "PROPOSED", "POLICY_CHECKED", "VALIDATED", "AWAITING_APPROVAL", "CHECKPOINT", "GRANTED",
    "CLAIMED", "EXECUTED", "VERIFIED", "RECORDED", "PROJECTED", "CLOSED", "REJECTED", "VOIDED",
    "FAILED", "NEEDS_VERIFICATION",
)

# §8. Four. Everything else is recoverable or human-owned, and both of those still hold the key.
TERMINAL_PIPELINE_STATES: tuple[str, ...] = ("CLOSED", "REJECTED", "VOIDED", "FAILED")

# §9. The two states whose progress depends on a named human doing something.
HUMAN_OWNED_PIPELINE_STATES: tuple[str, ...] = ("AWAITING_APPROVAL", "NEEDS_VERIFICATION")

# §10. The states a crash may be recovered FROM by re-deriving; `CLAIMED` and everything after it is
# NOT here, because §36 is explicit that a crash there is an UNKNOWN OUTCOME and never a re-run.
RECOVERABLE_PIPELINE_STATES: tuple[str, ...] = (
    "PROPOSED", "POLICY_CHECKED", "VALIDATED", "CHECKPOINT", "GRANTED", "CLAIMED", "EXECUTED",
    "VERIFIED", "RECORDED", "PROJECTED",
)

# ### THE STATES THAT MAY ONLY EXIST BEHIND A CHECKPOINT WITNESS AND A GRANT (§41(a), §15).
# `GRANTED` and every state reachable from it. `REJECTED` and `VOIDED` are absent because both are
# pre-effect refusals; `FAILED` is present because §14 reaches it only from `CLAIMED` (PL-10f) and
# from `NEEDS_VERIFICATION` (PL-15), and both are post-checkpoint.
POST_CHECKPOINT_STATES: tuple[str, ...] = (
    "GRANTED", "CLAIMED", "EXECUTED", "VERIFIED", "RECORDED", "PROJECTED", "CLOSED",
    "NEEDS_VERIFICATION", "FAILED",
)

# ### THE FOUR CANONICAL GATE DECISIONS — DERIVED FROM P3'S WITNESS TABLE, NOT RESTATED HERE.
#
# ADR-010's gate ladder belongs to the checkpoint kernel, and `test_phase0_null_gate.py` exists to
# notice the day a gate decision appears outside it. Typing the four names into this file would be
# a second copy of the policy vocabulary in a migration, and the first thing a second copy does is
# stop matching. `checkpoint_witnesses` already constrains exactly these four; this reads them out
# of that canonical DDL, so the pipeline's constraint IS the witness's constraint by construction.
#
# Importing the kernel itself is not available: `checkpoint.py` imports `workflow` → `schema` →
# this module, so the edge would be a cycle. `phase3_checkpoint` is a leaf migration (it imports
# `sqlite3` and nothing else), which is exactly why the vocabulary is read from there.
def _gate_decisions_from_the_witness_table() -> tuple[str, ...]:
    ddl = P3_TARGET_SCHEMA["checkpoint_witnesses"]
    match = re.search(
        r"gate_decision\s+TEXT\s+NOT\s+NULL\s+CHECK\s*\(\s*gate_decision\s+IN\s*\(([^)]*)\)",
        ddl, re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        raise RuntimeError(
            "the canonical checkpoint_witnesses DDL no longer declares a gate_decision CHECK. The "
            "Pipeline Instance derives its gate vocabulary from that one place rather than keeping "
            "a second copy, so this is a refusal and not a fallback: a silently-empty vocabulary "
            "would make `gate_decision` a free-text column and F-20's 'an unasserted gate' "
            "expressible again."
        )
    found = tuple(re.findall(r"'([A-Z_]+)'", match.group(1)))
    if len(found) < 4:
        raise RuntimeError(
            f"only {len(found)} gate decision(s) were derived from checkpoint_witnesses: {found}. "
            f"ADR-010's ladder has four, and a short vocabulary refuses valid decisions."
        )
    return found


GATE_DECISIONS: tuple[str, ...] = _gate_decisions_from_the_witness_table()

# K-1's two referent kinds, as M1 already spells them. PL-15 closes an UNKNOWN OUTCOME on a human
# decision, and a `decision_ref` whose namespace is guessed from the shape of the string resolves
# differently the day a rule id starts looking like a uuid.
DECISION_REF_KINDS: tuple[str, ...] = ("AUDIT_EVENT", "RULE")

_STATES_SQL = ",".join(f"'{s}'" for s in PIPELINE_STATES)
_TERMINAL_SQL = ",".join(f"'{s}'" for s in TERMINAL_PIPELINE_STATES)
_POST_CHECKPOINT_SQL = ",".join(f"'{s}'" for s in POST_CHECKPOINT_STATES)
_GATES_SQL = ",".join(f"'{g}'" for g in GATE_DECISIONS)
_REF_KINDS_SQL = ",".join(f"'{k}'" for k in DECISION_REF_KINDS)

# The exact abort texts, named here and matched by `pipeline_instance.py` when it classifies a
# `sqlite3.IntegrityError` — SQLite reports a trigger RAISE(ABORT) and a CHECK/UNIQUE violation
# through the same exception type, and a message that guesses which one happened sends the reader
# hunting for the wrong defect (the P5/P6 rule, kept).
#
# NOTE ON SPELLING: these are interpolated into single-quoted SQL literals inside `RAISE(ABORT, …)`,
# so an apostrophe would terminate the literal and the trigger would fail to compile. They are
# worded without apostrophes rather than escaped.
TERMINAL_ABORT = (
    "a terminal Pipeline Instance never transitions [02-pipeline-instance.machine.md sec 24]: "
    "reopening is at the Work Item, a retry is a NEW instance, and undoing a verified effect is a "
    "Compensation"
)
VERSION_ABORT = (
    "pipeline_instances.version advances by exactly one per transition [GR-3]: a write that does "
    "not advance it silently overwrites another transition"
)
WITNESS_ABORT = (
    "GRANTED and every state downstream of it require BOTH a checkpoint witness and a grant "
    "[sec 41(a), sec 15]: a pipeline that reached GRANTED without a witness would be an effect "
    "authorized by nobody"
)
IDENTITY_ABORT = (
    "the identity of an attempt is immutable: the tenant, the Work Item it serves, the logical "
    "effect it attempts and the commit key that names that effect are what make it THIS attempt, "
    "and editing them would retarget an authorized effect"
)
OWNER_ABORT = (
    "a Pipeline Instance is owned by its Work Items owner [sec 5, M-35, I1]: an attempt accountable "
    "to somebody other than the human who owes the work is an attempt nobody owes"
)
WITNESS_IMMUTABLE_ABORT = (
    "the checkpoint witness and the grant bound to an attempt are written ONCE, at PL-8, and never "
    "rebound: re-pointing them would let a claimed effect borrow another decisions authority"
)
DELETE_ABORT = (
    "pipeline_instances is never deleted: an attempt that may have touched the outside world is "
    "the only record that it did, and deleting it is how an effect becomes unaccounted for"
)
PROOF_ABORT = (
    "FAILED requires affirmative evidence the effect did NOT occur [GR-5, sec 11]: a timeout alone "
    "never proves failure, and a FAILED with no proof is an UNKNOWN OUTCOME wearing a resolution"
)


P6PI_TARGET_SCHEMA: dict[str, str] = {
    # THE PIPELINE INSTANCE (`entities/02-pipeline-instance.md`, spec §12.2/§19, machine M2).
    #
    # One durable attempt to produce one effect. §3: *"the Pipeline Instance IS the command"* —
    # there is no separate command object, which is why the intent's identity and the attempt's
    # identity are the same row.
    "pipeline_instances": """
        CREATE TABLE pipeline_instances (
            tenant TEXT NOT NULL,
            pipeline_instance_id TEXT NOT NULL,
            -- The obligation this attempt serves. NOT NULL *and* a foreign key: NOT NULL forbids the
            -- orphan, the FK forbids the invented. An attempt at work that does not exist is not a
            -- bad row, it is an unwritable one.
            work_item_id TEXT NOT NULL,
            state TEXT NOT NULL,
            version INTEGER NOT NULL,
            -- §5: the owner IS the Work Items owner, throughout. Carried on the row (rather than
            -- joined) so an event can pin the human accountable at the moment of the transition, and
            -- kept honest by trigger against the Work Item it serves.
            owner_id TEXT NOT NULL,

            -- THE LOGICAL EFFECT, DECOMPOSED — so the commit key is re-derivable and auditable
            -- rather than an opaque string somebody supplied. `commit_key.LogicalEffect` is exactly
            -- these five plus the tenant, and the AMOUNT IS NOT AMONG THEM (ADR-009, rule 8).
            action_class TEXT NOT NULL,
            target_system TEXT NOT NULL,
            target_resource_id TEXT NOT NULL,
            target_operation TEXT NOT NULL,
            occurrence_key TEXT NOT NULL,
            commit_key TEXT NOT NULL,

            -- Which attempt this is at that effect. §20: a retry is a NEW instance with the SAME
            -- commit key, so the pair (commit_key, attempt_seq) is what an operator reads as
            -- "attempt #2 to raise the invoice for load 4471".
            attempt_seq INTEGER NOT NULL,
            supersedes TEXT,

            -- PL-1b's "attach evidence". How many duplicate proposals this live attempt absorbed,
            -- and which one most recently. ### THIS IS A DURABLE WRITE AND NOT A COUNTER FOR
            -- CONVENIENCE: `DuplicateProposalAbsorbed` is an F2 contract, F2 requires STRICT
            -- per-aggregate ordering, and a strict event must OWN the version it rides at. An
            -- absorption that changed no row would have to ride at a version the previous
            -- transition already owns, which the outbox refuses outright — so "attach evidence" is
            -- the specification telling us this is a write, and the transport agrees.
            absorbed_count INTEGER NOT NULL,
            last_absorbed_ref TEXT,

            -- PL-2's durable answer. §14: `gate_decision` NOT NULL is GR-8/F-20 — an action class
            -- with no gate decision is an unasserted gate, and this column is where that stops being
            -- expressible from POLICY_CHECKED onward.
            policy_version TEXT,
            gate_decision TEXT,
            gate_reason TEXT,

            -- PL-7b / PL-8. The approval is M4's row; this is the binding.
            approval_id TEXT,
            material_facts_fingerprint TEXT,

            -- PL-8's co-commit. Both or neither, both real, both this tenants (the FKs are
            -- tenant-consistent), and once written never rebound.
            checkpoint_id TEXT,
            grant_id TEXT,
            claimed_at TEXT,

            -- The refusal record. PL-3/PL-5 (rejected), PL-7v/PL-9v (voided), PL-8f (checkpoint).
            reason TEXT,
            refused_step INTEGER,

            -- PL-10f. GR-5s affirmative evidence, without which FAILED is not reachable.
            failure_proof TEXT,
            -- PL-10u / PL-11c. The exposure itself stays on the canonical event (see the module
            -- docstring): this is the pointer to it plus the specific question a human must answer.
            unknown_reason TEXT,
            unknown_outcome_ref TEXT,
            -- PL-11d, the declared deferred-verification bound.
            recheck_at TEXT,
            -- PL-15. GR-14: closure of an unknown outcome resolves to a human decision or an
            -- ACTIVE rule, never to a timer and never to silence.
            decision_ref TEXT,
            decision_ref_kind TEXT,

            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            PRIMARY KEY (tenant, pipeline_instance_id),
            UNIQUE (tenant, checkpoint_id),
            UNIQUE (tenant, grant_id),
            UNIQUE (tenant, commit_key, attempt_seq),
            -- ### EACH FOREIGN KEY ON ONE LINE, DELIBERATELY. `schema._canonical_columns` parses
            -- this DDL line by line and skips a line that STARTS with FOREIGN KEY; a wrapped
            -- clause makes its continuation look like a column called `REFERENCES`, and the
            -- readiness oracle then reports a canonical column missing from every database. That
            -- is not a hypothetical — it is what the first version of this table did.
            FOREIGN KEY (tenant, work_item_id) REFERENCES work_items (tenant, work_item_id),
            FOREIGN KEY (tenant, owner_id) REFERENCES tenant_humans (tenant, human_id),
            FOREIGN KEY (tenant, supersedes) REFERENCES pipeline_instances (tenant, pipeline_instance_id),
            FOREIGN KEY (tenant, checkpoint_id) REFERENCES checkpoint_witnesses (tenant, checkpoint_id),
            FOREIGN KEY (tenant, grant_id) REFERENCES effect_grants (tenant, grant_id),
            CHECK (state IN (%(states)s)),
            CHECK (version >= 1),
            CHECK (attempt_seq >= 1),
            CHECK (absorbed_count >= 0),
            CHECK (absorbed_count = 0 OR last_absorbed_ref IS NOT NULL),
            CHECK (attempt_seq = 1 OR supersedes IS NOT NULL),
            CHECK (trim(pipeline_instance_id) <> ''),
            CHECK (trim(commit_key) <> ''),
            CHECK (trim(action_class) <> ''),
            CHECK (trim(target_system) <> ''),
            CHECK (trim(target_resource_id) <> ''),
            CHECK (trim(target_operation) <> ''),
            -- F-20 / GR-8: from POLICY_CHECKED onward a gate decision has been made, and NULL is
            -- not one of the four. PROPOSED and REJECTED are the two states that legitimately have
            -- none — PL-3 rejects a forbidden-gate intent straight out of PROPOSED. (The gate
            -- names themselves are derived above, never written literally in this file.)
            CHECK (state IN ('PROPOSED','REJECTED') OR gate_decision IS NOT NULL),
            CHECK (gate_decision IS NULL OR gate_decision IN (%(gates)s)),
            CHECK (gate_decision IS NULL OR policy_version IS NOT NULL),
            -- The witness and the grant arrive together at PL-8 or not at all.
            CHECK ((checkpoint_id IS NULL) = (grant_id IS NULL)),
            CHECK (decision_ref_kind IS NULL OR decision_ref_kind IN (%(ref_kinds)s)),
            CHECK (decision_ref IS NULL OR decision_ref_kind IS NOT NULL),
            CHECK (refused_step IS NULL OR (refused_step >= 1 AND refused_step <= 7))
        )""" % {
        "states": _STATES_SQL, "gates": _GATES_SQL, "ref_kinds": _REF_KINDS_SQL,
    },
}


P6PI_INDEXES: dict[str, str] = {
    # ### THE LAYER-1 RESERVATION (§14 PL-1). The whole duplicate-effect defence, and §20's retry
    # rule, in one partial unique index. See the module docstring for why the predicate is the
    # terminal set and not "state = something".
    "ix_pipeline_instances_live_reservation":
        "CREATE UNIQUE INDEX ix_pipeline_instances_live_reservation "
        "ON pipeline_instances (tenant, commit_key) WHERE state NOT IN (" + _TERMINAL_SQL + ")",
    # "What is this Work Item actually doing?" — the 1:N read, and the query behind an operator card.
    "ix_pipeline_instances_tenant_work_item":
        "CREATE INDEX ix_pipeline_instances_tenant_work_item "
        "ON pipeline_instances (tenant, work_item_id, state)",
    # The Sev-1 queue §38 requires: NEEDS_VERIFICATION by owner and age. Non-terminal states are the
    # operational surface; a terminal attempt is history.
    "ix_pipeline_instances_tenant_state_owner":
        "CREATE INDEX ix_pipeline_instances_tenant_state_owner "
        "ON pipeline_instances (tenant, state, owner_id, created_at)",
}

# Nothing from an earlier phase is replaced. Declared so a future replacement has somewhere to go.
P6PI_REPLACED_INDEXES: tuple[str, ...] = ()


P6PI_TRIGGERS: dict[str, str] = {
    # ### TERMINAL IS ABSOLUTELY TERMINAL — NO REOPEN DOOR AT ALL (§24).
    #
    # `work_items` has one: WI-13 reopens a CLOSED item into a new phase. This machine has none, and
    # the difference is the whole architecture. A Pipeline Instance that has ended may have touched
    # the outside world; letting it move again is `retry-in-place`, which §15 lists as ILLEGAL and
    # §20 answers with "a retry is a NEW instance". The trigger is what makes that true against a
    # connection, not only against the transition table.
    "trg_pipeline_instances_terminal_is_final": f"""
        CREATE TRIGGER trg_pipeline_instances_terminal_is_final
        BEFORE UPDATE ON pipeline_instances
        WHEN OLD.state IN ({_TERMINAL_SQL})
        BEGIN SELECT RAISE(ABORT, '{TERMINAL_ABORT}'); END""",
    # ### OCC IS NOT A CONVENTION (GR-3). The machine writes `WHERE version = :expected`, which
    # protects concurrent writers from each other; this protects the counter itself. A version that
    # stands still is how two events claim one aggregate version — and `pipeline_instance` is a
    # STRICT-ORDER family (events/registry.md §8), so downstream that is not a cosmetic collision.
    "trg_pipeline_instances_version_advances_by_one": f"""
        CREATE TRIGGER trg_pipeline_instances_version_advances_by_one
        BEFORE UPDATE ON pipeline_instances
        WHEN NEW.version <> OLD.version + 1
        BEGIN SELECT RAISE(ABORT, '{VERSION_ABORT}'); END""",
    # ### §41(a): `GRANTED` UNREACHABLE WITHOUT A WITNESS. Both directions — the state cannot be
    # entered without both ids, on INSERT as well as UPDATE, so a row cannot be created straight
    # into GRANTED either.
    "trg_pipeline_instances_post_checkpoint_carries_its_witness_insert": f"""
        CREATE TRIGGER trg_pipeline_instances_post_checkpoint_carries_its_witness_insert
        BEFORE INSERT ON pipeline_instances
        WHEN NEW.state IN ({_POST_CHECKPOINT_SQL})
         AND (NEW.checkpoint_id IS NULL OR NEW.grant_id IS NULL)
        BEGIN SELECT RAISE(ABORT, '{WITNESS_ABORT}'); END""",
    "trg_pipeline_instances_post_checkpoint_carries_its_witness_update": f"""
        CREATE TRIGGER trg_pipeline_instances_post_checkpoint_carries_its_witness_update
        BEFORE UPDATE ON pipeline_instances
        WHEN NEW.state IN ({_POST_CHECKPOINT_SQL})
         AND (NEW.checkpoint_id IS NULL OR NEW.grant_id IS NULL)
        BEGIN SELECT RAISE(ABORT, '{WITNESS_ABORT}'); END""",
    # ### THE WITNESS AND THE GRANT ARE BOUND ONCE. Rebinding is how a claimed effect borrows another
    # decisions authority: the ledger row would say CLAIMED for grant A while the pipeline pointed at
    # grant B, and the two-key rule would be satisfied by two different keys.
    "trg_pipeline_instances_witness_binding_is_write_once": f"""
        CREATE TRIGGER trg_pipeline_instances_witness_binding_is_write_once
        BEFORE UPDATE ON pipeline_instances
        WHEN (OLD.checkpoint_id IS NOT NULL AND NEW.checkpoint_id IS NOT OLD.checkpoint_id)
          OR (OLD.grant_id IS NOT NULL AND NEW.grant_id IS NOT OLD.grant_id)
        BEGIN SELECT RAISE(ABORT, '{WITNESS_IMMUTABLE_ABORT}'); END""",
    # ### THE IDENTITY OF AN ATTEMPT IS IMMUTABLE. Editing the commit key would retarget an
    # authorization that was granted for a different effect; editing `work_item_id` would move an
    # attempt onto another obligation with another owner. Both are the shape of change an audit
    # cannot detect afterwards, because the row afterwards is internally consistent.
    "trg_pipeline_instances_identity_is_immutable": f"""
        CREATE TRIGGER trg_pipeline_instances_identity_is_immutable
        BEFORE UPDATE OF tenant, pipeline_instance_id, work_item_id, commit_key, action_class,
                         target_system, target_resource_id, target_operation, occurrence_key,
                         attempt_seq, supersedes, created_at
        ON pipeline_instances
        BEGIN SELECT RAISE(ABORT, '{IDENTITY_ABORT}'); END""",
    # ### §5: THE OWNER IS THE WORK ITEMS OWNER. Checked against the Work Item itself, on INSERT and
    # on any write that NAMES `owner_id`. Naming the column only when ownership actually moves is
    # deliberate (the `UPDATE OF` trigger fires on a column being named, not on its value changing):
    # an ordinary transition must not re-assert an owner, or voiding an attempt whose owner has since
    # been offboarded would abort — and voiding is exactly what such an attempt needs.
    "trg_pipeline_instances_owner_follows_the_work_item_insert": f"""
        CREATE TRIGGER trg_pipeline_instances_owner_follows_the_work_item_insert
        BEFORE INSERT ON pipeline_instances
        WHEN NEW.owner_id IS NOT (SELECT owner_id FROM work_items
                                   WHERE tenant = NEW.tenant AND work_item_id = NEW.work_item_id)
        BEGIN SELECT RAISE(ABORT, '{OWNER_ABORT}'); END""",
    "trg_pipeline_instances_owner_follows_the_work_item_update": f"""
        CREATE TRIGGER trg_pipeline_instances_owner_follows_the_work_item_update
        BEFORE UPDATE OF owner_id ON pipeline_instances
        WHEN NEW.owner_id IS NOT (SELECT owner_id FROM work_items
                                   WHERE tenant = NEW.tenant AND work_item_id = NEW.work_item_id)
        BEGIN SELECT RAISE(ABORT, '{OWNER_ABORT}'); END""",
    # ### GR-5, AT THE ROW: `FAILED` NEEDS A PROOF. §11 restricts FAILED to *"provable
    # non-occurrence only"*, and §14 PL-10f writes `failure_proof`. Without this trigger the
    # difference between "we proved nothing happened" and "we gave up waiting" is a code path, and
    # the wrong one of those two is a retry that pays an invoice twice.
    "trg_pipeline_instances_failed_carries_its_proof": f"""
        CREATE TRIGGER trg_pipeline_instances_failed_carries_its_proof
        BEFORE UPDATE ON pipeline_instances
        WHEN NEW.state = 'FAILED'
         AND (NEW.failure_proof IS NULL OR trim(NEW.failure_proof) = '')
        BEGIN SELECT RAISE(ABORT, '{PROOF_ABORT}'); END""",
    "trg_pipeline_instances_no_delete": f"""
        CREATE TRIGGER trg_pipeline_instances_no_delete
        BEFORE DELETE ON pipeline_instances
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


def create_phase6_pipeline_schema(conn: sqlite3.Connection, *, now: str) -> list[str]:
    """Create whatever M2 structure is missing. Idempotent; returns what it did.

    Callable on a fresh canonical database and on an already-migrated one. Either way the resulting
    structure is byte-identical, because there is only one text — the discipline P3, P5 and the
    Work Item migration all use, and the reason a fresh database is never briefly unsafe.
    """
    performed: list[str] = []
    present = _tables(conn)
    for name in (*P6PI_TENANT_TABLES, *P6PI_EXEMPT_TABLES):
        if name not in present:
            conn.execute(P6PI_TARGET_SCHEMA[name])
            performed.append(f"create-table:{name}")
    existing = _indexes(conn)
    for name, ddl in P6PI_INDEXES.items():
        if name not in existing:
            conn.execute(ddl)
            performed.append(f"create-index:{name}")
    for stale in P6PI_REPLACED_INDEXES:
        if stale in _indexes(conn):
            conn.execute(f"DROP INDEX {stale}")
            performed.append(f"drop-index:{stale}")
    existing_triggers = _triggers(conn)
    for name, ddl in P6PI_TRIGGERS.items():
        if name not in existing_triggers:
            conn.execute(ddl)
            performed.append(f"create-trigger:{name}")
    # NO VERSION STAMP HERE — marker-last. A stamp written by the builder appears on a half-migrated
    # database the moment a later step fails, which is how a missing trigger goes unnoticed.
    conn.commit()
    return performed


def stamp_phase6_pipeline_version(conn: sqlite3.Connection, *, now: str) -> None:
    """Record the M2 marker — callable ONLY once readiness holds."""
    problems = phase6_pipeline_readiness_problems(conn)
    if problems:
        raise RuntimeError(
            f"refusing to stamp {P6PI_SCHEMA_VERSION} on a database that is NOT ready: "
            + "; ".join(problems)
        )
    if "schema_migrations" in _tables(conn):
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration, step, applied_at, detail) "
            "VALUES (?,?,?,?)",
            (MIGRATION_ID, f"version:{P6PI_SCHEMA_VERSION}", now,
             "the Pipeline Instance: one durable attempt, tenant-first, reserved by commit key; "
             "readiness proven"),
        )
        conn.commit()


def phase6_pipeline_readiness_problems(conn: sqlite3.Connection) -> list[str]:
    """Every reason this database cannot carry durable execution attempts. Empty == ready.

    Structural, like the P2/P3/P5/M1 oracles it extends. The reservation index and the triggers are
    verified PRESENT because a `pipeline_instances` table without them is an ordinary table with an
    aspirational comment: two attempts at one effect would both insert, a terminal attempt would
    transition, and `GRANTED` would be reachable by writing the word.
    """
    problems: list[str] = []
    present = _tables(conn)
    for table in (*P6PI_TENANT_TABLES, *P6PI_EXEMPT_TABLES):
        if table not in present:
            problems.append(
                f"required Phase-6 table {table!r} is missing: run the {MIGRATION_ID} migration"
            )
    if not all(t in present for t in P6PI_TENANT_TABLES):
        return problems

    live_triggers = _triggers(conn)
    missing_triggers = sorted(t for t in P6PI_TRIGGERS if t not in live_triggers)
    if missing_triggers:
        problems.append(
            f"Pipeline Instance invariant triggers missing: {missing_triggers}. Without them a "
            f"terminal attempt can transition, the version counter can stand still, GRANTED is "
            f"reachable with no witness, an attempt can be retargeted at another effect, and "
            f"FAILED needs no proof [§15, §24, §41(a), GR-3, GR-5]."
        )
    live_indexes = _indexes(conn)
    for name in P6PI_INDEXES:
        if name not in live_indexes:
            problems.append(f"required Phase-6 index {name!r} is missing")
    for stale in P6PI_REPLACED_INDEXES:
        if stale in live_indexes:
            problems.append(f"replaced index {stale!r} is still present")

    # ### THE LAYER-1 RESERVATION, READ OUT OF THE LIVE DATABASE RATHER THAN ASSUMED FROM ITS NAME.
    # An index called `..._live_reservation` that is not UNIQUE, or whose partial predicate has been
    # widened, is the duplicate-effect defence switched off with the sign left up. So the DDL of the
    # live index is re-read and both properties are checked.
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name = ?",
        ("ix_pipeline_instances_live_reservation",),
    ).fetchone()
    if row is not None:
        sql = " ".join((row[0] or "").split()).upper()
        if "UNIQUE" not in sql:
            problems.append(
                "ix_pipeline_instances_live_reservation is not UNIQUE: two live attempts at one "
                "logical effect would both insert, which is the duplicate-invoice defect PL-1/PL-1b "
                "exist to prevent."
            )
        for state in TERMINAL_PIPELINE_STATES:
            if f"'{state}'" not in sql:
                problems.append(
                    f"ix_pipeline_instances_live_reservation does not exclude {state!r}: the "
                    f"reservation predicate must be exactly the terminal set, or either a finished "
                    f"attempt blocks its own retry (§20) or an unfinished one releases the key."
                )

    # THE OWNERSHIP AND OBLIGATION FOREIGN KEYS, read from the live database by referent. The
    # generic oracle in `schema.py` checks every canonical FK; these two are the unit's whole point,
    # so they are also checked by name — a pipeline whose `work_item_id` has no referent is an
    # attempt at nothing, and one whose `owner_id` has none is an attempt nobody owes.
    referents = {r[2] for r in conn.execute(
        "PRAGMA foreign_key_list(pipeline_instances)").fetchall()}
    for table, why in (
        ("work_items", "an attempt with no obligation is work nobody asked for"),
        ("tenant_humans", "an attempt with no accountable human violates rule 13 structurally"),
        ("checkpoint_witnesses", "§41(a) requires GRANTED to be unreachable without a witness"),
        ("effect_grants", "SD-2 gives the effect ONE ledger row and this must point at it"),
    ):
        if table not in referents:
            problems.append(
                f"pipeline_instances declares no foreign key into {table!r}: {why}."
            )
    return problems
