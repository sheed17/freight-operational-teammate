"""U8.5 — THE `lane` -> `action_class` migration: acceptance guards + pressure tests.

These are the load-bearing guards the U8.5 mutation battery (scripts/mutate_p8_action_class.py)
reintroduces defects against. Each proves one property of a mechanical, behavior-free migration:
the operational-control `lane` is gone from product authority; the persistence migrated
idempotently and tenant-safely; the effect ledger's `action_class` is authority and its `lane` a
byte-identical non-authoritative mirror; commit-key / effect identity is unchanged; F-20 still
refuses an unregistered action class; and no autonomy, gate, or live route was created.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))          # eval/
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))  # src/

import json  # noqa: E402

from phase0 import action_class_migration as acm  # noqa: E402

from freight_recon import commit_key as ck  # noqa: E402
from freight_recon import product_policy as pp  # noqa: E402
from freight_recon.action_class_graduation import ActionClassGraduation  # noqa: E402
from freight_recon.commit_key import LogicalEffect, commit_key  # noqa: E402
from freight_recon.migrations.phase8_action_class import (  # noqa: E402
    migrate_phase8_action_class,
    phase8_action_class_readiness_problems,
)
from freight_recon.operation_router import OperationRouter, freight_routes  # noqa: E402
from freight_recon.schema import create_canonical_schema, enable_and_verify_foreign_keys, schema_readiness_problems  # noqa: E402
from freight_recon.slack_delegate import CommandIntent, CommandKind  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402

# The commit key of a raise_invoice effect, frozen. If the rename altered effect identity this changes.
GOLDEN_COMMIT_KEY = "d6fa2a7b2fbc3d14bac427b6d02d007933f79df48388ac8f35ed1263d585adc5"


def _fresh_conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    enable_and_verify_foreign_keys(c)
    create_canonical_schema(c)
    return c


# ---------------------------------------------------------------- the detector / acceptance gate

def test_no_unresolved_operational_lane_in_product_authority():
    """### THE ACCEPTANCE GATE. After U8.5 no operational-control `lane` acts as current authority.

    Prints the denominator: a zero-unresolved result over a NON-EMPTY discovered population is
    'the detector looked and found nothing', not a vacuous pass (CLAUDE.md §6)."""
    occ = acm.scan_production()
    assert len(occ) >= 40, f"the detector inspected a suspiciously small population ({len(occ)})"
    unresolved = [o for o in occ if o.category == acm.UNRESOLVED_OPERATIONAL]
    assert not unresolved, (
        "operational-control `lane` still acts as authority in product code:\n  "
        + "\n  ".join(f"{o.file}:{o.lineno}: {o.line}" for o in unresolved)
    )


def test_the_detector_is_non_vacuous_a_reintroduced_operational_lane_is_caught(tmp_path):
    """### THE POSITIVE CONTROL. The SAME detector, pointed at a planted operational `lane`, flags it
    — so a zero-result scan of the real tree is meaningful, not blind."""
    planted = tmp_path / "planted.py"
    planted.write_text('def route(intent):\n    params = {"lane": intent.summary}\n    return params\n')
    occ = acm.scan([tmp_path])
    flagged = [o for o in occ if o.category == acm.UNRESOLVED_OPERATIONAL]
    assert flagged, "the detector did NOT flag a reintroduced operational lane — it is vacuous"
    # and a genuine compat read / freight lane in the same temp tree is NOT flagged
    (tmp_path / "compat.py").write_text('ac = d.get("action_class") or d.get("lane")\n')
    occ2 = acm.scan([tmp_path / "compat.py"])
    assert not [o for o in occ2 if o.category == acm.UNRESOLVED_OPERATIONAL], (
        "a bounded compat read was wrongly flagged operational — the detector over-reports")


def test_the_migration_ledger_is_complete_and_records_the_inventory_conclusion():
    led = acm.ledger()
    assert led["status"] == "COMPLETE", led["unresolved_operational"]
    # the union's other two arms are empty in this repository, recorded not forced
    assert led["inventory_conclusion"]["workflow_id_occurrences"] == 0
    assert led["inventory_conclusion"]["policy_scope_distinct_from_action_class_occurrences"] == 0


def test_detector_flags_operational_lane_writes_not_only_dict_literals(tmp_path):
    """R1: a reintroduced operational `lane` WRITE cannot masquerade as a bounded compat read.

    A subscript assignment and a non-first dict-key write are flagged UNRESOLVED, while a genuine
    legacy-key compat read on the same shape stays resolved."""
    (tmp_path / "sub.py").write_text('m["lane"] = intent.summary\n')
    (tmp_path / "dictkey.py").write_text('payload = {"action_class": x, "lane": y}\n')
    (tmp_path / "compat.py").write_text('ac = row.get("action_class") or row.get("lane")\n')
    cats = {p.name: [o.category for o in acm.scan([tmp_path / p.name])]
            for p in (Path("sub.py"), Path("dictkey.py"), Path("compat.py"))}
    assert cats["sub.py"] == [acm.UNRESOLVED_OPERATIONAL], cats
    assert cats["dictkey.py"] == [acm.UNRESOLVED_OPERATIONAL], cats
    assert acm.UNRESOLVED_OPERATIONAL not in cats["compat.py"], cats


# ------------------------------------------------------------------------- persistence migration

def test_migration_fails_closed_when_both_lane_and_action_class_present():
    """R3: a counter table carrying BOTH the legacy `lane` and the canonical `action_class` is a
    dual-field anomaly the migration refuses to guess through — it fails closed."""
    import sqlite3
    from freight_recon.migrations.phase8_action_class import migrate_phase8_action_class
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE autonomous_run_counters (tenant TEXT, lane TEXT, action_class TEXT, "
              "day TEXT, runs INTEGER, updated_at TEXT, PRIMARY KEY (tenant, action_class, day))")
    c.commit()
    try:
        migrate_phase8_action_class(c, now="t")
        assert False, "the migration accepted a dual-field counter table instead of failing closed"
    except RuntimeError as exc:
        assert "BOTH" in str(exc)

def test_autonomous_run_counter_is_keyed_by_action_class_not_lane():
    c = _fresh_conn()
    cols = {r[1] for r in c.execute("PRAGMA table_info(autonomous_run_counters)")}
    pk = [r[1] for r in c.execute("PRAGMA table_info(autonomous_run_counters)") if r[5]]
    assert "action_class" in cols and "lane" not in cols, cols
    assert pk == ["tenant", "action_class", "day"], pk


def test_persistence_migration_is_idempotent_and_tenant_safe():
    """An old row migrates ONCE; a retry is a no-op; and a rename cannot mix tenants."""
    c = _fresh_conn()
    # Simulate a pre-U8.5 shape by reverting the column name, then seed two tenants.
    c.execute("ALTER TABLE autonomous_run_counters RENAME COLUMN action_class TO lane")
    c.execute("INSERT INTO autonomous_run_counters (tenant, lane, day, runs, updated_at) "
              "VALUES ('acme','raise_invoice','2026-09-19',3,'t')")
    c.execute("INSERT INTO autonomous_run_counters (tenant, lane, day, runs, updated_at) "
              "VALUES ('beta','raise_invoice','2026-09-19',7,'t')")
    c.commit()
    first = migrate_phase8_action_class(c, now="t")
    assert first == ["rename-column:autonomous_run_counters.lane->action_class"]
    assert migrate_phase8_action_class(c, now="t") == []          # idempotent retry
    assert phase8_action_class_readiness_problems(c) == []
    rows = {r["tenant"]: r["runs"] for r in
            c.execute("SELECT tenant, runs FROM autonomous_run_counters")}
    assert rows == {"acme": 3, "beta": 7}, rows                   # tenant-isolated, counts preserved


def test_concurrent_cap_result_is_unchanged_under_the_renamed_column(tmp_path):
    """The atomic daily-cap claim keeps its BEGIN IMMEDIATE serialization after the rename: exactly
    one of two contenders wins a cap of 1."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from concurrency_kit import run_race
    db = tmp_path / "w.sqlite3"
    WorkflowStore(db, tenant="acme").close()
    got = []

    def claim():
        s = WorkflowStore(db, tenant="acme")
        try:
            got.append(s.claim_autonomous_run("acme", "raise_invoice", cap=1)[0])
        finally:
            s.close()

    run_race(claim, [(), ()])
    assert sorted(got) == [False, True]


def test_autonomous_counter_stays_tenant_scoped_after_rename(tmp_path):
    """Tenant A's counter can never be moved by tenant B: the claim reads/writes its own tenant."""
    db = tmp_path / "w.sqlite3"
    WorkflowStore(db, tenant="acme").close()
    a = WorkflowStore(db, tenant="acme")
    b = WorkflowStore(db, tenant="beta")
    try:
        a.claim_autonomous_run("acme", "raise_invoice", cap=5)
        a.claim_autonomous_run("acme", "raise_invoice", cap=5)
        assert a.autonomous_runs_today("acme", "raise_invoice") == 2
        assert b.autonomous_runs_today("beta", "raise_invoice") == 0   # untouched by A
    finally:
        a.close(); b.close()


# ------------------------------------------------------------- effect_grants mirror + identity

def test_effect_grants_action_class_is_authority_and_lane_is_a_byte_identical_mirror(tmp_path):
    db = tmp_path / "w.sqlite3"
    store = WorkflowStore(db, tenant="acme")
    try:
        eff = LogicalEffect(tenant="acme", action_class="raise_invoice", target_system="tms",
                            target_resource_id="LD-1|Acme", target_operation="raise_invoice",
                            occurrence_key="")
        store.claim_operation_commit(commit_key=eff.key(), target_system="tms",
                                     action_class="raise_invoice", load_ref="LD-1", party="Acme",
                                     approved_amount="2850.00", payload={"status": "RESERVED"})
        row = store.conn.execute(
            "SELECT action_class, lane FROM effect_grants WHERE tenant='acme' AND commit_key=?",
            (eff.key(),)).fetchone()
        assert row["action_class"] == "raise_invoice"
        assert row["action_class"] == row["lane"], "the lane mirror diverged from action_class"
    finally:
        store.close()


def test_legacy_lookup_reads_action_class_not_the_lane_mirror(tmp_path):
    """The compatibility bridge queries the AUTHORITY column (action_class), not the legacy `lane`
    mirror. Proven with a deliberately DIVERGENT row: the lookup finds it by action_class even when
    `lane` says something else (old-field-wins would miss it)."""
    db = tmp_path / "w.sqlite3"
    store = WorkflowStore(db, tenant="acme")
    try:
        store.conn.execute(
            "INSERT INTO effect_grants (tenant, grant_id, commit_key, action_class, target_system, "
            "target_resource_id, target_operation, state, approved_amount, material_facts_json, "
            "lane, load_ref, party, payload_json, issued_at, created_at) "
            "VALUES ('acme','g1','legacy-ck','raise_invoice','tms','LD-1|Acme','raise_invoice',"
            "'VERIFIED','2850.00','{}','DIVERGENT','LD-1','Acme','{}','t','t')")
        store.conn.commit()
        rows = store.legacy_commit_rows(action_class="raise_invoice", load_ref="LD-1",
                                        party="Acme", canonical_commit_key="different-canonical")
        assert len(rows) == 1, "lookup did not read the action_class authority column"
    finally:
        store.close()


def test_commit_key_bytes_are_unchanged_by_the_rename():
    """The rename touches FIELD NAMES, never effect identity. The commit key of a raise_invoice
    effect is byte-for-byte the frozen golden value."""
    eff = LogicalEffect(tenant="acme", action_class="raise_invoice", target_system="tms:truckingoffice",
                        target_resource_id="ld-1|acme corp", target_operation="raise_invoice",
                        occurrence_key="")
    assert commit_key(eff) == GOLDEN_COMMIT_KEY


def test_router_reservation_carries_action_class_and_preserves_the_commit_key():
    """The router builds its reservation under the canonical action_class field, and the reservation's
    commit key equals the direct LogicalEffect key — the value is preserved, only the field renamed."""
    from freight_recon.operation_router import _commit_reservation
    route = {r.name: r for r in freight_routes()}["raise_invoice"]
    intent = CommandIntent(CommandKind.OPERATE, "invoice LD-1 for Acme Corp",
                           {"customer": "Acme Corp", "load_ref": "LD-1"})
    res = _commit_reservation("acme", "tms:truckingoffice", route, intent, "2850.00")
    assert res["action_class"] == "raise_invoice"
    assert "lane" not in res
    assert res["commit_key"] == GOLDEN_COMMIT_KEY


# --------------------------------------------------------------------------- F-20 / registry

def test_unregistered_action_class_still_refuses_f20():
    """U8.5 preserves U8.1: an unregistered action class REFUSES (never a safe-looking default)."""
    try:
        pp.product_gate_for("frobnicate")
        assert False, "an unregistered action class resolved to a gate — F-20 is broken"
    except pp.UnclassifiedActionClass:
        pass


def test_no_second_action_class_registry_and_population_unchanged():
    assert pp.ACTION_CLASS_POPULATION == frozenset(ck.OCCURRENCE_RULES)
    assert len(pp.ACTION_CLASS_POPULATION) == 8
    assert pp.REGISTERED_ACTION_CLASS_COUNT == 8


def test_no_autonomy_was_granted_and_no_gate_changed():
    """Every P8 action class stays HUMAN_APPROVAL_REQUIRED; AUTONOMOUS_WITHIN_CAPS has no member."""
    from freight_recon.checkpoint import GateDecision
    gates = {name: e.gate for name, e in pp.PRODUCT_POLICY.items()}
    assert all(g is GateDecision.HUMAN_APPROVAL_REQUIRED for g in gates.values()), gates
    assert not any(e.gate is GateDecision.AUTONOMOUS_WITHIN_CAPS for e in pp.PRODUCT_POLICY.values())


# --------------------------------------------------------- ambiguous input cannot bypass classification

def test_ambiguous_lane_input_cannot_select_an_unregistered_action_class():
    """Inbound content naming a made-up action class routes to NOTHING — the router matches only the
    action classes it was CONSTRUCTED with, whether the key is the canonical `action_class` or a
    legacy `lane`."""
    router = OperationRouter(routes=freight_routes(), build_agent=lambda **_: None)
    for key in ("action_class", "lane"):
        got = router.route_for(CommandIntent(CommandKind.OPERATE, "zzz", {key: "frobnicate_pay_everyone"}))
        assert got is None, f"a bogus {key} value selected a route"
    # and a legacy `lane` key still translates to a REGISTERED route (bounded compat)
    got = router.route_for(CommandIntent(CommandKind.OPERATE, "zzz", {"lane": "raise_invoice"}))
    assert got is not None and got.name == "raise_invoice"


# ------------------------------------------------------------------ graduation JSON compat

def test_graduation_reads_a_legacy_lane_json_one_directionally_and_writes_canonical(tmp_path):
    legacy = tmp_path / "action_class_graduation.json"
    legacy.write_text(json.dumps({
        "lanes": {"acme::raise_invoice": {"tenant": "acme", "lane": "raise_invoice",
                                          "autonomous": True, "max_amount": "2500"}},
        "history": [{"tenant": "acme", "lane": "raise_invoice", "autonomous": True}],
    }))
    canonical = tmp_path / "action_class_graduation.json"
    grad = ActionClassGraduation(canonical, legacy_path=legacy)
    assert grad.is_autonomous("acme", "raise_invoice") is True        # legacy read translated once
    # a new write emits the canonical shape only — no `lane` field survives as authority
    grad.graduate("acme", "record_payable", actor="R")
    written = json.loads(canonical.read_text())
    assert "action_classes" in written and "lanes" not in written
    for entry in written["action_classes"].values():
        assert "lane" not in entry and "action_class" in entry


# ------------------------------------------------------------------- schema stays green overall

def test_full_canonical_schema_is_ready_after_the_migration():
    c = _fresh_conn()
    assert schema_readiness_problems(c) == []
