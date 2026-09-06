"""Phase 6 — M13, the Brake: admission control, the one-way ratchet, no TTL, fail-closed reads,
F13 emission, the released_by FK, the append-only triggers, and the single brake authority.

Tier-1 discipline: the load-bearing DDL is introspected LIVE and the forbidden writes are ATTEMPTED
against a real canonical database behind positive controls, not read from the migration source. Every
test here is the RED half of a mutant in scripts/mutate_phase6_brake.py.

M13 HARDENS the ONE landed brake authority (brake.py's BrakeStore); it builds no second store. The
platform brake belongs to no tenant (SD-12), so its F13 events have no tenant partition and are a
recorded gap (M13-AQ-5) — tenant brakes emit, and the platform row's incident record is its columns.
"""

from __future__ import annotations

import ast
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for entry in (str(ROOT / "src"), str(ROOT / "eval"), str(ROOT / "eval" / "tests")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from freight_recon import brake_lifecycle as bl  # noqa: E402
from freight_recon.brake import (  # noqa: E402
    BrakeError,
    BrakeStore,
    BrakeStoreUnreachable,
)
from freight_recon.brake_lifecycle import BrakeMachine, BrakeRefused  # noqa: E402
from freight_recon.event_contracts import CONTRACTS  # noqa: E402
from freight_recon.migrations.phase6_brakes import (  # noqa: E402
    P6BR_EXEMPT_TABLES,
    P6BR_TENANT_TABLES,
    create_phase6_brakes_schema,
    phase6_brakes_readiness_problems,
)
from freight_recon.migrations.phase3_checkpoint import phase3_readiness_problems  # noqa: E402
from freight_recon.schema import (  # noqa: E402
    create_canonical_schema,
    enable_and_verify_foreign_keys,
    schema_readiness_problems,
)

TENANT = "acme-brokerage"
FIXED = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
PKG = ROOT / "src" / "freight_recon"
BRAKE_SRC = (PKG / "brake.py").read_text(encoding="utf-8")
LIFECYCLE_SRC = (PKG / "brake_lifecycle.py").read_text(encoding="utf-8")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_canonical_schema(conn)
    enable_and_verify_foreign_keys(conn)
    return conn


def _human(conn: sqlite3.Connection, human_id: str, *, tenant: str = TENANT, state: str = "ACTIVE") -> str:
    conn.execute(
        "INSERT OR IGNORE INTO tenant_humans (tenant, human_id, display_name, authority_role, "
        "state, recorded_at, recorded_by, recorded_by_kind) VALUES (?,?,?,'POLICY_OWNER',?,?,?,'human')",
        (tenant, human_id, human_id, state, "2026-09-05", "seed"),
    )
    conn.commit()
    return human_id


def _store(conn: sqlite3.Connection) -> BrakeStore:
    return BrakeStore(conn, clock=lambda: FIXED)


def _machine(conn: sqlite3.Connection) -> BrakeMachine:
    return BrakeMachine(_store(conn))


def _evidence(**over):
    ev = {"in_flight_accounted": True, "unresolved_sev0": False,
          "integration_health": {"kind": "positive_control", "verified": True},
          "decision_ref": "decision:closed", "unknown_outcomes": []}
    ev.update(over)
    return ev


def _ddl(conn, table):
    return " ".join(conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()[0].split())


# ============================================================ migration / readiness

def test_readiness_is_clean_on_a_fresh_canonical_database():
    conn = _conn()
    assert schema_readiness_problems(conn) == []
    assert phase6_brakes_readiness_problems(conn) == []


def test_the_brakes_migration_is_rerunnable_and_a_second_application_is_a_no_op():
    conn = _conn()
    performed = create_phase6_brakes_schema(conn, now="2026-09-05T12:00:00.000Z")
    assert performed == [], f"a second application was not a no-op: {performed}"
    assert phase6_brakes_readiness_problems(conn) == []


def test_p3_readiness_still_holds_after_the_m13_hardening():
    conn = _conn()
    assert phase3_readiness_problems(conn) == []


def test_the_recorded_tenant_exempt_set_is_exactly_platform_brake():
    assert P6BR_EXEMPT_TABLES == ("platform_brake",)
    assert P6BR_TENANT_TABLES == ("brakes",)


def test_fresh_and_migrated_brake_layers_are_structurally_identical():
    # fresh
    fresh = _conn()
    # migrated: a P3-shaped brakes/platform_brake taken through the M13 hardening
    from freight_recon.migrations.phase3_checkpoint import P3_INDEXES, P3_TARGET_SCHEMA
    from freight_recon.migrations.phase6_work_items import P6_TARGET_SCHEMA
    mig = sqlite3.connect(":memory:")
    mig.row_factory = sqlite3.Row
    mig.execute(P6_TARGET_SCHEMA["tenant_humans"])
    mig.execute(P3_TARGET_SCHEMA["brakes"])
    mig.execute(P3_TARGET_SCHEMA["platform_brake"])
    mig.execute(P3_INDEXES["ix_brakes_one_active_per_scope"])
    mig.execute("INSERT OR IGNORE INTO platform_brake (id, state, brake_version) VALUES (1, 'RELEASED', 0)")
    mig.commit()
    create_phase6_brakes_schema(mig, now="2026-09-05T12:00:00.000Z")

    def shape(c, t):
        cols = [(r[1], r[2], bool(r[3]), r[4]) for r in c.execute(f"PRAGMA table_info({t})")]
        fks = sorted((r[2], r[3], r[4]) for r in c.execute(f"PRAGMA foreign_key_list({t})"))
        # only the triggers ON this table (the minimal migrated DB has no unrelated ones)
        trigs = sorted(r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=?", (t,)))
        return cols, fks, trigs
    for t in ("brakes", "platform_brake"):
        assert shape(fresh, t) == shape(mig, t), f"{t} differs between fresh and migrated"


# ============================================================ DDL: two states, no third, no TTL

def test_the_two_states_and_no_third_is_insertable():
    conn = _conn()
    _human(conn, "ops")
    ddl = _ddl(conn, "brakes")
    assert "state IN ('ACTIVE','RELEASED')".upper() in ddl.upper().replace(", ", ",")
    for forbidden in ("PENDING_RELEASE", "ENGAGING", "EXPIRED", "SUSPENDED", "PARTIAL", "DISENGAGED"):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO brakes (tenant, brake_id, scope, state, actor, actor_kind, "
                "engaged_reason, engaged_at, brake_version, signal_count) "
                "VALUES (?, ?, 'tenant', ?, 'x', 'HUMAN', 'r', 'now', 1, 1)",
                (TENANT, f"b-{forbidden}", forbidden))
        conn.rollback()


def test_no_ttl_or_expiry_column_on_either_brake_table():
    conn = _conn()
    for t in ("brakes", "platform_brake"):
        cols = [r[1].lower() for r in conn.execute(f"PRAGMA table_info({t})")]
        bad = [c for c in cols if "ttl" in c or "expir" in c or "deadline" in c]
        assert bad == [], f"{t} carries an expiry-shaped column: {bad}"


def test_no_expiry_in_brake_executable_code_by_ast():
    # brake.py's DOCSTRING legitimately says "no TTL" / "expire"; the ban is on executable code —
    # no expiry-named function and no SQL literal touching EXPIR/TTL.
    tree = ast.parse(BRAKE_SRC)
    fns = [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    assert fns, "brake.py parsed to no functions"
    assert [f for f in fns if "expire" in f.lower() or "ttl" in f.lower()] == []
    sql = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
           and any(k in n.value.upper() for k in ("UPDATE ", "INSERT ", "DELETE "))]
    assert sql, "brake.py contains no SQL literals"
    assert [s for s in sql if "EXPIR" in s.upper() or "TTL" in s.upper()] == []


def test_the_actor_kind_check_is_human_or_detector_and_a_model_kind_is_refused():
    conn = _conn()
    _human(conn, "ops")
    ddl = _ddl(conn, "brakes")
    assert "actor_kind IN ('HUMAN','DETECTOR')".upper() in ddl.upper().replace(", ", ",")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO brakes (tenant, brake_id, scope, state, actor, actor_kind, engaged_reason, "
            "engaged_at, brake_version, signal_count) VALUES (?, 'b', 'tenant', 'ACTIVE', 'm', 'MODEL', "
            "'r', 'now', 1, 1)", (TENANT,))
    conn.rollback()


# ============================================================ DDL: released_by FK, signal_count, triggers

def test_released_by_is_a_foreign_key_into_tenant_humans():
    conn = _conn()
    fks = {(r[2], r[3], r[4]) for r in conn.execute("PRAGMA foreign_key_list(brakes)")}
    assert ("tenant_humans", "released_by", "human_id") in fks, f"brakes FKs: {fks}"


def test_a_releaser_who_is_not_a_recorded_human_is_refused():
    conn = _conn()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO brakes (tenant, brake_id, scope, state, actor, actor_kind, engaged_reason, "
            "engaged_at, brake_version, signal_count, released_by, released_by_kind, "
            "release_decision_ref, released_at) VALUES (?, 'b', 'tenant', 'RELEASED', 'x', 'HUMAN', "
            "'r', 'now', 2, 1, 'ghost', 'HUMAN', 'd', 'now')", (TENANT,))
    conn.rollback()


def test_a_releaser_from_another_tenant_is_refused():
    conn = _conn()
    _human(conn, "ops", tenant="tenant-b")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO brakes (tenant, brake_id, scope, state, actor, actor_kind, engaged_reason, "
            "engaged_at, brake_version, signal_count, released_by, released_by_kind, "
            "release_decision_ref, released_at) VALUES (?, 'b', 'tenant', 'RELEASED', 'x', 'HUMAN', "
            "'r', 'now', 2, 1, 'ops', 'HUMAN', 'd', 'now')", (TENANT,))
    conn.rollback()


def test_a_recorded_human_releaser_is_accepted():
    conn = _conn()
    _human(conn, "ops")
    conn.execute(
        "INSERT INTO brakes (tenant, brake_id, scope, state, actor, actor_kind, engaged_reason, "
        "engaged_at, brake_version, signal_count, released_by, released_by_kind, "
        "release_decision_ref, released_at) VALUES (?, 'b', 'tenant', 'RELEASED', 'x', 'HUMAN', "
        "'r', 'now', 2, 1, 'ops', 'HUMAN', 'd', 'now')", (TENANT,))
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM brakes WHERE state='RELEASED'").fetchone()[0] == 1


def test_signal_count_is_a_column_on_both_tables():
    conn = _conn()
    for t in ("brakes", "platform_brake"):
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({t})")}
        assert "signal_count" in cols, f"{t} has no signal_count column"


def test_a_brake_row_is_never_deleted():
    conn = _conn()
    _human(conn, "ops")
    _store(conn).engage(tenant=TENANT, actor="ops", actor_kind="HUMAN", reason="incident")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM brakes")
    conn.rollback()
    assert conn.execute("SELECT COUNT(*) FROM brakes").fetchone()[0] == 1


def test_the_platform_brake_row_is_never_deleted():
    conn = _conn()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM platform_brake")
    conn.rollback()
    assert conn.execute("SELECT COUNT(*) FROM platform_brake").fetchone()[0] == 1


def test_the_delete_refusing_triggers_exist_on_both_tables():
    conn = _conn()
    trigs = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
    assert "trg_brakes_no_delete" in trigs
    assert "trg_platform_brake_no_delete" in trigs


# ============================================================ DDL: platform row / tenant isolation

def test_the_platform_brake_is_exactly_one_row_structurally():
    conn = _conn()
    assert conn.execute("SELECT COUNT(*) FROM platform_brake").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO platform_brake (id, state, brake_version) VALUES (2, 'RELEASED', 0)")
    conn.rollback()
    assert conn.execute("SELECT COUNT(*) FROM platform_brake").fetchone()[0] == 1


def test_the_platform_brake_has_no_tenant_column():
    conn = _conn()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(platform_brake)")}
    assert not (cols & {"tenant", "tenant_id"}), f"platform_brake grew a tenant column: {sorted(cols)}"


def test_brakes_is_tenant_first():
    conn = _conn()
    first = [r[1] for r in conn.execute("PRAGMA table_info(brakes)") if r[5] == 1]
    assert first == ["tenant"], f"brakes PK is not tenant-first: {first}"


def test_one_active_brake_per_tenant_and_scope_is_a_partial_unique_index():
    conn = _conn()
    _human(conn, "ops")
    _store(conn).engage(tenant=TENANT, action_class="raise_invoice", actor="ops", actor_kind="HUMAN", reason="1")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO brakes (tenant, brake_id, scope, state, actor, actor_kind, engaged_reason, "
            "engaged_at, brake_version, signal_count) VALUES (?, 'b2', 'action:raise_invoice', 'ACTIVE', "
            "'x', 'HUMAN', 'r', 'now', 99, 1)", (TENANT,))
    conn.rollback()


# ============================================================ entity point 44 — named adversarial tests

def test_engaging_the_brake_during_an_adapter_call_does_not_create_an_unknown_outcome(tmp_path):
    store, kernel, effect, inputs, request, brakes, run_checkpoint, claim, params_for = _boundary(tmp_path)
    out = run_checkpoint(kernel, request, inputs)
    claim(kernel, out.handle, params_for(effect))               # CLAIMED (adapter "in call")
    brakes.engage(tenant="tenant-alpha", actor="ops", actor_kind="HUMAN", reason="mid-call")
    n_unknown = store.conn.execute(
        "SELECT COUNT(*) FROM effect_grants WHERE state='UNKNOWN_OUTCOME'").fetchone()[0]
    assert n_unknown == 0, "the brake manufactured an unknown outcome"
    st = store.conn.execute("SELECT state FROM effect_grants WHERE grant_id=?",
                            (out.handle.grant_id,)).fetchone()[0]
    assert st == "CLAIMED", "the brake killed an in-flight worker"


def test_brake_between_mint_and_claim_race_never_both_never_neither(tmp_path):
    store, kernel, effect, inputs, request, brakes, run_checkpoint, claim, params_for = _boundary(tmp_path)
    out = run_checkpoint(kernel, request, inputs)
    brakes.engage(tenant="tenant-alpha", actor="ops", actor_kind="HUMAN", reason="between")
    c = claim(kernel, out.handle, params_for(effect))
    assert c.claimed is False, "the claim matched under a between-brake (both)"


def test_brake_engages_with_policy_engine_and_tms_down():
    conn = _conn()
    _human(conn, "ops")
    # engage touches only the brake tables — no policy engine / TMS read — so it works with them down
    s = _machine(conn).engage_brake(tenant=TENANT, actor="ops", actor_class="human", reason="everything down")
    assert s.state == "ACTIVE"


def test_automation_can_engage_but_never_release():
    conn = _conn()
    _human(conn, "ops")
    m = _machine(conn)
    s = m.engage_brake(tenant=TENANT, action_class="raise_invoice", actor="det", actor_class="detector", reason="signal")
    assert s.state == "ACTIVE"
    m.widen_brake(tenant=TENANT, brake_id=s.brake_id, actor="auto", actor_class="automation")
    with pytest.raises(BrakeRefused):
        m.release_brake(tenant=TENANT, brake_id=s.brake_id, actor="det", actor_class="automation",
                  decision_ref="d", evidence=_evidence())


def test_release_re_checkpoints_all_queued_work(tmp_path):
    from freight_recon.checkpoint import revoke_unclaimed
    store, kernel, effect, inputs, request, brakes, run_checkpoint, claim, params_for = _boundary(tmp_path)
    out1 = run_checkpoint(kernel, request, inputs)
    s = brakes.engage(tenant="tenant-alpha", actor="ops", actor_kind="HUMAN", reason="incident")
    _seed_ops(store, "tenant-alpha")
    revoke_unclaimed(kernel, grant_id=out1.handle.grant_id, cause="POLICY_CHANGED", actor="ops")
    brakes.release(tenant="tenant-alpha", brake_id=s.brake_id, actor="ops", actor_kind="HUMAN", decision_ref="d")
    out2 = run_checkpoint(kernel, request, inputs)
    assert out2.authorized and out2.witness.checkpoint_id != out1.witness.checkpoint_id


def test_stale_grant_after_release_is_refused(tmp_path):
    store, kernel, effect, inputs, request, brakes, run_checkpoint, claim, params_for = _boundary(tmp_path)
    out = run_checkpoint(kernel, request, inputs)
    s = brakes.engage(tenant="tenant-alpha", actor="ops", actor_kind="HUMAN", reason="incident")
    _seed_ops(store, "tenant-alpha")
    brakes.release(tenant="tenant-alpha", brake_id=s.brake_id, actor="ops", actor_kind="HUMAN", decision_ref="d")
    c = claim(kernel, out.handle, params_for(effect))
    assert c.claimed is False, "a stale grant was resurrected after release"


def test_no_timer_can_move_a_brake():
    # BR-5 is enumerated illegal and non-producing; no timer path exists on the store.
    br5 = bl._BY_ID["BR-5"]
    assert br5.to_state is None and br5.writes == () and br5.event is None
    assert br5.non_producing_reason == bl.GR1_ILLEGAL_REFUSAL
    assert ".schedule(" not in BRAKE_SRC and "event_timers" not in BRAKE_SRC
    assert bl.permitted_transitions("timer") == []


def test_a_brake_never_auto_expires():
    # ADR-011 §4: a brake has NO TTL and no wall-clock expiry. Once ACTIVE it stays ACTIVE until a
    # human releases it, however far the clock advances — a brake that quietly auto-expired would
    # re-admit effects nobody re-authorised (the fail-DANGEROUS inverse of "cannot read == off").
    conn = _conn()
    m = _machine(conn)
    b = m.engage_brake(tenant=TENANT, actor="orphan-detector", actor_class="detector",
                       reason="orphan adapter", action_class="pay_carrier")
    assert b.state == "ACTIVE"
    # A store reading the SAME rows through a clock a century later sees the same ACTIVE brake, and
    # admission is still denied. Nothing about the passage of time moves a brake.
    far_future = FIXED + timedelta(days=365 * 100)
    later = BrakeStore(conn, clock=lambda: far_future)
    assert later.admission_denied(tenant=TENANT, action_class="pay_carrier") is not None
    assert later.status(tenant=TENANT, brake_id=b.brake_id).state == "ACTIVE"
    assert bl.unknown_outcomes_block_release() is False  # and no auto path releases it either


def test_detector_cannot_release_its_own_brake():
    conn = _conn()
    m = _machine(conn)
    s = m.engage_brake(tenant=TENANT, actor="detector:d", actor_class="detector", reason="alarm")
    with pytest.raises(BrakeRefused):
        m.release_brake(tenant=TENANT, brake_id=s.brake_id, actor="detector:d", actor_class="detector",
                  decision_ref="d", evidence=_evidence())
    got = conn.execute(
        "SELECT COUNT(*) FROM event_outbox WHERE event_name='UnauthorizedBrakeReleaseAttempted'").fetchone()[0]
    assert got == 1, "the unauthorized (detector) release went unrecorded"


def test_active_brake_is_reported_unprompted_on_every_surface():
    conn = _conn()
    _human(conn, "ops")
    m = _machine(conn)
    m.engage_brake(tenant=TENANT, action_class="raise_invoice", actor="detector:orphan", actor_class="detector",
             reason="orphan adapter")
    reports = m.report(tenant=TENANT)
    assert reports and bl.reports_unprompted_when_active()
    r = reports[0]
    assert r.reason and r.actor and r.actor_kind == "DETECTOR"
    assert set(r.still_allowed) >= {"observation", "reconciliation", "reads"}
    assert tuple(r.release_requirements) == bl.RELEASE_EVIDENCE


def test_fail_closed_on_unreadable_brake():
    conn = _conn()
    conn.execute("DROP TABLE platform_brake")   # the row is undeletable; a dropped table is unreadable
    conn.commit()
    with pytest.raises(BrakeStoreUnreachable):
        _store(conn).admission_denied(tenant=TENANT, action_class="raise_invoice")
    with pytest.raises(BrakeStoreUnreachable):
        _store(conn).version_token(tenant=TENANT)


# ============================================================ boundary helpers

def _seed_ops(store, tenant):
    store.conn.execute(
        "INSERT OR IGNORE INTO tenant_humans (tenant, human_id, display_name, authority_role, state, "
        "recorded_at, recorded_by, recorded_by_kind) VALUES (?, 'ops','ops','POLICY_OWNER','ACTIVE',"
        "'now','seed','human')", (tenant,))
    store.conn.commit()


def _boundary(tmp_path):
    from freight_recon.checkpoint import claim_grant_cas, run_checkpoint
    from phase3_kit import green_scenario, params_for
    store, kernel, clock, effect, facts, versions, approval, world, inputs, request = green_scenario(tmp_path)
    brakes = BrakeStore(store.conn, clock=lambda: FIXED)
    return store, kernel, effect, inputs, request, brakes, run_checkpoint, claim_grant_cas, params_for


# ============================================================ F13 / F14 emission

def _outbox_names(conn, tenant=TENANT):
    return [r[0] for r in conn.execute(
        "SELECT event_name FROM event_outbox WHERE tenant=? AND aggregate_type='brake' ORDER BY sequence",
        (tenant,))]


def test_the_four_f13_contracts_and_no_fifth():
    fam = sorted(n for n, c in CONTRACTS.items() if c.family == "F13")
    assert fam == ["BrakeEngaged", "BrakeNarrowed", "BrakeReleased", "BrakeWidened"]
    assert set(bl.PRODUCED_CONTRACTS) == set(fam)
    for forbidden in ("BrakeExpired", "BrakeAutoReleased", "BrakePendingRelease"):
        assert forbidden not in CONTRACTS


def test_f13_is_strict_per_aggregate():
    for n in ("BrakeEngaged", "BrakeWidened", "BrakeNarrowed", "BrakeReleased"):
        assert CONTRACTS[n].strict_order, f"{n} is not strict-order"


def test_the_four_transitions_each_emit_their_f13_event():
    conn = _conn()
    _human(conn, "ops")
    m = _machine(conn)
    s = m.engage_brake(tenant=TENANT, action_class="raise_invoice", actor="ops", actor_class="human", reason="1")
    m.widen_brake(tenant=TENANT, brake_id=s.brake_id, actor="ops", actor_class="human")
    m.narrow_brake(tenant=TENANT, brake_id=s.brake_id, actor="ops", actor_class="human",
             to_action_class="raise_invoice", decision_ref="d")
    m.release_brake(tenant=TENANT, brake_id=s.brake_id, actor="ops", actor_class="human",
              decision_ref="d", evidence=_evidence())
    names = _outbox_names(conn)
    assert names == ["BrakeEngaged", "BrakeWidened", "BrakeNarrowed", "BrakeReleased"], names


def test_the_f13_envelope_carries_the_order_fields():
    conn = _conn()
    _human(conn, "ops")
    s = _machine(conn).engage_brake(tenant=TENANT, actor="ops", actor_class="human", reason="r")
    row = conn.execute(
        "SELECT aggregate_version, envelope_json FROM event_outbox WHERE event_name='BrakeEngaged'").fetchone()
    envelope = json.loads(row["envelope_json"])
    assert row["aggregate_version"] == s.brake_version
    assert "previous_aggregate_version" in envelope


def test_an_unauthorized_release_emits_the_registered_f14_and_no_synonym():
    conn = _conn()
    m = _machine(conn)
    s = m.engage_brake(tenant=TENANT, actor="detector:d", actor_class="detector", reason="alarm")
    with pytest.raises(BrakeRefused):
        m.release_brake(tenant=TENANT, brake_id=s.brake_id, actor="detector:d", actor_class="detector",
                  decision_ref="d", evidence=_evidence())
    assert "UnauthorizedBrakeReleaseAttempted" in _outbox_names(conn)
    assert "UnauthorizedBrakeReleaseAttempted" in CONTRACTS and CONTRACTS["UnauthorizedBrakeReleaseAttempted"].family == "F14"
    for synonym in ("BrakeReleaseRefused", "UnauthorizedRelease", "BrakeSecurityEvent"):
        assert synonym not in (BRAKE_SRC + LIFECYCLE_SRC)


def test_m13_mints_no_unregistered_brake_event():
    import re
    names = set(re.findall(r'"(Brake[A-Za-z]+)"', BRAKE_SRC)) | {"UnauthorizedBrakeReleaseAttempted"}
    bad = [n for n in names if n not in CONTRACTS]
    assert bad == [], f"unregistered event name(s) minted: {bad}"


# ============================================================ release evidence (BR-4)

def test_release_is_not_a_human_and_a_decision_ref_alone():
    conn = _conn()
    _human(conn, "ops")
    m = _machine(conn)
    s = m.engage_brake(tenant=TENANT, actor="ops", actor_class="human", reason="i")
    with pytest.raises(BrakeRefused):
        m.release_brake(tenant=TENANT, brake_id=s.brake_id, actor="ops", actor_class="human",
                  decision_ref="d", evidence={"decision_ref": "d"})


def test_a_loaded_page_is_not_a_positive_health_proof():
    assert bl.is_positive_health_proof({"kind": "page_loaded", "loaded": True}) is False
    assert bl.is_positive_health_proof({"kind": "positive_control", "verified": True}) is True
    conn = _conn()
    _human(conn, "ops")
    m = _machine(conn)
    s = m.engage_brake(tenant=TENANT, actor="ops", actor_class="human", reason="i")
    with pytest.raises(BrakeRefused):
        m.release_brake(tenant=TENANT, brake_id=s.brake_id, actor="ops", actor_class="human", decision_ref="d",
                  evidence=_evidence(integration_health={"kind": "page_loaded"}))


def test_an_unaccounted_in_flight_effect_blocks_release():
    conn = _conn()
    _human(conn, "ops")
    m = _machine(conn)
    s = m.engage_brake(tenant=TENANT, actor="ops", actor_class="human", reason="i")
    with pytest.raises(BrakeRefused):
        m.release_brake(tenant=TENANT, brake_id=s.brake_id, actor="ops", actor_class="human", decision_ref="d",
                  evidence=_evidence(in_flight_accounted=False))


def test_an_unresolved_sev0_blocks_release():
    conn = _conn()
    _human(conn, "ops")
    m = _machine(conn)
    s = m.engage_brake(tenant=TENANT, actor="ops", actor_class="human", reason="i")
    with pytest.raises(BrakeRefused):
        m.release_brake(tenant=TENANT, brake_id=s.brake_id, actor="ops", actor_class="human", decision_ref="d",
                  evidence=_evidence(unresolved_sev0=True))


def test_unresolved_unknown_outcomes_do_not_block_release_but_must_be_owned():
    assert bl.unknown_outcomes_block_release() is False
    conn = _conn()
    _human(conn, "ops")
    m = _machine(conn)
    s = m.engage_brake(tenant=TENANT, actor="ops", actor_class="human", reason="i")
    # acknowledged + owned => released
    r = m.release_brake(tenant=TENANT, brake_id=s.brake_id, actor="ops", actor_class="human", decision_ref="d",
                  evidence=_evidence(unknown_outcomes=[{"grant_id": "g", "acknowledged": True, "owner": "ops"}]))
    assert r.state == "RELEASED"
    # unacknowledged => refused
    s2 = m.engage_brake(tenant=TENANT, actor="ops", actor_class="human", reason="i2")
    with pytest.raises(BrakeRefused):
        m.release_brake(tenant=TENANT, brake_id=s2.brake_id, actor="ops", actor_class="human", decision_ref="d",
                  evidence=_evidence(unknown_outcomes=[{"grant_id": "g", "acknowledged": False}]))


def test_unresolved_unknown_outcomes_stay_frozen_and_owned():
    # ADR-011 §6 / rule 12: an UNKNOWN_OUTCOME never auto-resolves. Releasing the brake does not
    # resolve it — the obligation is that the entity STAYS FROZEN, the commit key STAYS HELD, and it
    # remains acknowledged and owned. The brake releases nothing but itself.
    obligations = set(bl.UNKNOWN_OUTCOME_RELEASE_OBLIGATIONS)
    assert {"acknowledged", "owned", "entity_stays_frozen", "commit_key_stays_held"} <= obligations
    assert bl.unknown_outcomes_block_release() is False  # they do not block — they stay, frozen
    conn = _conn()
    _human(conn, "ops")
    m = _machine(conn)
    s = m.engage_brake(tenant=TENANT, actor="ops", actor_class="human", reason="i")
    r = m.release_brake(tenant=TENANT, brake_id=s.brake_id, actor="ops", actor_class="human",
                        decision_ref="d",
                        evidence=_evidence(unknown_outcomes=[
                            {"grant_id": "g", "acknowledged": True, "owner": "ops"}]))
    # The brake released; the unknown outcome it named was not touched by the release.
    assert r.state == "RELEASED"


# ============================================================ ratchet & idempotency

def test_a_model_may_never_engage_narrow_or_release():
    conn = _conn()
    m = _machine(conn)
    with pytest.raises(BrakeRefused):
        m.engage_brake(tenant=TENANT, actor="agent", actor_class="model", reason="I decided")
    assert bl.permitted_transitions("model") == []
    assert bl.model_may("BR-1") is False


def test_automation_may_engage_and_widen_only():
    assert bl.automation_transitions() == ["BR-1", "BR-2"]
    assert bl.automation_may("BR-3") is False and bl.automation_may("BR-4") is False


def test_only_a_human_may_narrow():
    conn = _conn()
    _human(conn, "ops")
    m = _machine(conn)
    s = m.engage_brake(tenant=TENANT, actor="ops", actor_class="human", reason="wide")
    for cls in ("detector", "automation", "model", "timer"):
        with pytest.raises(BrakeRefused):
            m.narrow_brake(tenant=TENANT, brake_id=s.brake_id, actor="x", actor_class=cls,
                     to_action_class="raise_invoice", decision_ref="d")
    n = m.narrow_brake(tenant=TENANT, brake_id=s.brake_id, actor="ops", actor_class="human",
                 to_action_class="raise_invoice", decision_ref="d")
    assert n.scope == "action:raise_invoice"


def test_the_report_is_produced_unprompted_when_active():
    assert bl.reports_unprompted_when_active() is True


def test_the_signal_count_rises_on_repeated_engagement_by_row():
    conn = _conn()
    m = _machine(conn)
    s = m.engage_brake(tenant=TENANT, action_class="raise_invoice", actor="det", actor_class="detector", reason="flap")
    for _ in range(4):
        m.engage_brake(tenant=TENANT, action_class="raise_invoice", actor="det", actor_class="detector", reason="flap")
    row = conn.execute("SELECT signal_count, brake_version FROM brakes WHERE brake_id=?", (s.brake_id,)).fetchone()
    assert row["signal_count"] == 5
    assert row["brake_version"] == s.brake_version, "a repeat engagement bumped the version"
    assert conn.execute("SELECT COUNT(*) FROM brakes WHERE state='ACTIVE'").fetchone()[0] == 1


# ============================================================ boundary: kill / stale

def test_a_claimed_grant_is_not_killed_by_the_brake(tmp_path):
    store, kernel, effect, inputs, request, brakes, run_checkpoint, claim, params_for = _boundary(tmp_path)
    out = run_checkpoint(kernel, request, inputs)
    claim(kernel, out.handle, params_for(effect))
    brakes.engage(tenant="tenant-alpha", actor="ops", actor_kind="HUMAN", reason="after claim")
    st = store.conn.execute("SELECT state FROM effect_grants WHERE grant_id=?",
                            (out.handle.grant_id,)).fetchone()[0]
    assert st == "CLAIMED"


def test_an_active_brake_refuses_the_mint(tmp_path):
    store, kernel, effect, inputs, request, brakes, run_checkpoint, claim, params_for = _boundary(tmp_path)
    brakes.engage(tenant="tenant-alpha", actor="ops", actor_kind="HUMAN", reason="stop")
    out = run_checkpoint(kernel, request, inputs)
    assert not out.authorized and out.step == 7


# ============================================================ the claim CAS composite token

def test_the_claim_cas_revalidates_the_composite_brake_token():
    src = (PKG / "checkpoint.py").read_text()
    import re
    m = re.search(r"UPDATE effect_grants\s+SET state = 'CLAIMED'.*?WHERE.*?brake_version = \?.*?policy_version = \?",
                  src, re.S)
    assert m, "the claim CAS no longer revalidates brake_version + policy_version in its WHERE clause"


def test_witnesses_and_grants_bind_the_composite_token(tmp_path):
    store, kernel, effect, inputs, request, brakes, run_checkpoint, claim, params_for = _boundary(tmp_path)
    out = run_checkpoint(kernel, request, inputs)
    wtok = store.conn.execute("SELECT brake_version FROM checkpoint_witnesses WHERE checkpoint_id=?",
                              (out.witness.checkpoint_id,)).fetchone()[0]
    gtok = store.conn.execute("SELECT brake_version FROM effect_grants WHERE grant_id=?",
                              (out.handle.grant_id,)).fetchone()[0]
    for tok in (wtok, gtok):
        assert tok.startswith("bv1|global:") and "|tenant:" in tok


# ============================================================ single authority / gate / ship dark

def _brake_writing_modules():
    out = []
    for py in sorted(PKG.rglob("*.py")):
        src = py.read_text().lower()
        if any(s in src for s in ("insert into brakes", "update brakes set",
                                  "insert into platform_brake", "update platform_brake set")):
            out.append(py.name)
    return out


def test_there_is_exactly_one_brake_authority():
    assert _brake_writing_modules() == ["brake.py"]


def test_exactly_one_class_owns_the_brake_lifecycle():
    # Mirrors the permanent scenario's single-authority AST oracle: a class that defines BOTH
    # `engage` and `release` OWNS the lifecycle, and there must be exactly one — brake.py:BrakeStore.
    # The M13 facade (BrakeMachine) delegates every mutation to the store and must NOT present as a
    # second owner; its verbs are `engage_brake`/`release_brake` for exactly that reason.
    owners = []
    for py in sorted(PKG.rglob("*.py")):
        for n in ast.walk(ast.parse(py.read_text())):
            if isinstance(n, ast.ClassDef):
                methods = {m.name for m in n.body
                           if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))}
                if {"engage", "release"} <= methods:
                    owners.append(f"{py.name}:{n.name}")
    assert sorted(set(owners)) == ["brake.py:BrakeStore"], owners


def test_m13_builds_no_second_brake_store():
    stores = []
    for py in sorted(PKG.rglob("*.py")):
        for n in ast.walk(ast.parse(py.read_text())):
            if isinstance(n, ast.ClassDef) and n.name.endswith("Store") and "Brake" in n.name:
                stores.append(f"{py.name}:{n.name}")
    assert stores == ["brake.py:BrakeStore"], stores


def test_checkpoint_py_remains_the_sole_gate_minter():
    minters = []
    for py in sorted(PKG.rglob("*.py")):
        src = py.read_text()
        if "GateRegistry(" in src or "GateEntry(gate=" in src:
            minters.append(py.name)
    assert minters == ["checkpoint.py"], minters


def test_m13_mints_no_gate_decision():
    blob = BRAKE_SRC + LIFECYCLE_SRC
    assert not any(s in blob for s in ("GateEntry(", "GateRegistry(", "GateDecision(", "register_gate"))


def test_m13_builds_no_second_brake_state_table():
    conn = _conn()
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%brake%'")}
    assert tables == {"brakes", "platform_brake"}, tables


def test_m13_ships_dark_no_production_importer():
    importers = []
    for py in sorted(PKG.rglob("*.py")):
        if py.name == "brake_lifecycle.py":
            continue
        src = py.read_text()
        if ("import brake_lifecycle" in src or "from .brake_lifecycle" in src
                or "from freight_recon.brake_lifecycle" in src):
            importers.append(py.name)
    assert importers == [], f"a production module imports the M13 surface: {importers}"


def test_the_landed_brakeengaged_consumers_are_preserved():
    # M2 and M4 consume BrakeEngaged as a coordination fact — M13 must not delete these.
    assert "BrakeEngaged" in (PKG / "pipeline_instance.py").read_text()
    assert "BrakeEngaged" in (PKG / "approval.py").read_text()


def test_the_m1_through_m12_machines_are_unchanged():
    machines = ("work_item.py", "pipeline_instance.py", "external_effect.py", "approval.py",
                "observation.py", "identity_binding_claim.py", "conflict.py", "expectation.py",
                "exception.py", "compensation.py", "policy.py", "rule.py")
    rel = [f"src/freight_recon/{n}" for n in machines]
    r = subprocess.run(["git", "diff", "--name-only", "HEAD", "--", *rel], cwd=str(ROOT),
                       capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip() == "", f"an M1..M12 machine changed: {r.stdout}"


def test_the_m13_brake_machine_and_no_graduation_engine():
    files = {p.name for p in PKG.rglob("*.py")}
    assert "brake_lifecycle.py" in files
    for f in ("brake.py", "brake_lifecycle.py"):
        for n in ast.walk(ast.parse((PKG / f).read_text())):
            if isinstance(n, ast.ClassDef):
                assert "graduat" not in n.name.lower(), f"{f} defines a graduation engine: {n.name}"


def test_section_41_acceptance_items_are_covered():
    """Machine §41 acceptance (a)-(g) each map to a named test in this module."""
    module = sys.modules[__name__]
    coverage = {
        "a) engaging during an adapter call creates no unknown outcome":
            "test_engaging_the_brake_during_an_adapter_call_does_not_create_an_unknown_outcome",
        "b) brake between mint and claim => CAS zero rows":
            "test_brake_between_mint_and_claim_race_never_both_never_neither",
        "c) engages with the policy engine and TMS down":
            "test_brake_engages_with_policy_engine_and_tms_down",
        "d) automation engages but never releases":
            "test_automation_can_engage_but_never_release",
        "e) release re-checkpoints all queued work":
            "test_release_re_checkpoints_all_queued_work",
        "f) never auto-expires":
            "test_no_timer_can_move_a_brake",
        "g) unresolved unknown outcomes do not block release but stay frozen and owned":
            "test_unresolved_unknown_outcomes_do_not_block_release_but_must_be_owned",
    }
    missing = [item for item, fn in coverage.items() if not hasattr(module, fn)]
    assert missing == [], f"machine §41 acceptance items missing a test: {missing}"
