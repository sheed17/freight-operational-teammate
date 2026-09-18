"""P8/U8.3 — the real Human Brake: the INTEGRATION scope landing, the COUNTERPARTY adjudication,
and the durable release-evidence backstop, adversarially.

The M13 kernel (admission control, the ratchet, no-TTL, fail-closed reads) landed in P3
(`test_phase3_brake.py`) and the M13 lifecycle machine landed dark in P6 (`test_phase6_brake.py`).
This module proves ONLY the U8.3 delta and its hostile edges, and preserves every landed guarantee:

  * INTEGRATION(target_system) becomes a landed scope — deterministic because `target_system` is a
    frozen field of the canonical `LogicalEffect` (part of the commit key, revalidated by the claim
    CAS). An ACTIVE integration brake denies the matching effect at the mint AND, by the
    global-per-tenant version rule, invalidates every outstanding grant at the claim.
  * COUNTERPARTY stays UNSPELLABLE — adjudicated at P8/U8.3 as NOT deterministic at the effect
    boundary (no field on the effect; only an optional free-form SYSTEM_IMPORTED material fact; the
    canonical identity model arrives at P9). An unspellable scope forces a WIDER brake, never none.
  * The release-evidence contract gains a DURABLE backstop: the caller's attestation may not outrun
    the ONE canonical effect ledger. A CLAIMED/ATTEMPTED effect still in flight blocks release, and
    an UNKNOWN_OUTCOME in the ledger cannot be hidden by omission — using no new schema and no
    second release workflow.

Every load-bearing assertion here is the RED half of a mutant in scripts/mutate_phase6_brake.py.
"""

from __future__ import annotations

import sqlite3
import sys
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
from freight_recon.schema import (  # noqa: E402
    create_canonical_schema,
    enable_and_verify_foreign_keys,
)

TENANT = "acme-brokerage"
TO = "tms:truckingoffice"          # the integration used by the green scenario's effect
OTHER = "tms:some-other-system"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_canonical_schema(conn)
    enable_and_verify_foreign_keys(conn)
    return conn


def _human(conn: sqlite3.Connection, human_id: str, *, tenant: str = TENANT) -> str:
    conn.execute(
        "INSERT OR IGNORE INTO tenant_humans (tenant, human_id, display_name, authority_role, "
        "state, recorded_at, recorded_by, recorded_by_kind) VALUES (?,?,?,'POLICY_OWNER','ACTIVE',"
        "?, 'seed','human')",
        (tenant, human_id, human_id, "2026-09-17"),
    )
    conn.commit()
    return human_id


def _store(conn: sqlite3.Connection) -> BrakeStore:
    return BrakeStore(conn)


def _machine(conn: sqlite3.Connection) -> BrakeMachine:
    return BrakeMachine(_store(conn))


def _evidence(**over):
    ev = {"in_flight_accounted": True, "unresolved_sev0": False,
          "integration_health": {"kind": "positive_control", "verified": True},
          "decision_ref": "decision:closed", "unknown_outcomes": []}
    ev.update(over)
    return ev


def _boundary(tmp_path):
    """The green checkpoint scenario plus a BrakeStore on the same connection. The effect's
    target_system is `tms:truckingoffice`, tenant `tenant-alpha`."""
    from freight_recon.checkpoint import claim_grant_cas, run_checkpoint
    from phase3_kit import green_scenario, params_for
    store, kernel, clock, effect, facts, versions, approval, world, inputs, request = (
        green_scenario(tmp_path))
    brakes = BrakeStore(store.conn)
    return store, kernel, effect, inputs, request, brakes, run_checkpoint, claim_grant_cas, params_for


def _seed_ops(store, tenant):
    store.conn.execute(
        "INSERT OR IGNORE INTO tenant_humans (tenant, human_id, display_name, authority_role, state, "
        "recorded_at, recorded_by, recorded_by_kind) VALUES (?, 'ops','ops','POLICY_OWNER','ACTIVE',"
        "'now','seed','human')", (tenant,))
    store.conn.commit()


# ============================================================ INTEGRATION scope — store level

def test_an_integration_brake_denies_the_matching_effect_and_spares_others():
    conn = _conn()
    _human(conn, "ops")
    store = _store(conn)
    s = store.engage(tenant=TENANT, target_system=TO, actor="ops", actor_kind="HUMAN",
                     reason="stop all TruckingOffice writes")
    assert s.scope == "integration:tms:truckingoffice" and s.state == "ACTIVE"
    # the matching integration is denied — regardless of action class (integration is cross-action)
    for action in ("raise_invoice", "file_document", "update_status"):
        d = store.admission_denied(tenant=TENANT, action_class=action, target_system=TO)
        assert d is not None and d.scope == "integration:tms:truckingoffice", action
    # a DIFFERENT integration keeps writing — the brake is scoped, not a blanket tenant stop
    assert store.admission_denied(tenant=TENANT, action_class="raise_invoice",
                                  target_system=OTHER) is None


def test_the_integration_scope_is_normalised_consistently():
    conn = _conn()
    _human(conn, "ops")
    store = _store(conn)
    store.engage(tenant=TENANT, target_system="TMS:TruckingOffice", actor="ops", actor_kind="HUMAN",
                 reason="mixed case")
    # engage lower-cased the scope; admission lower-cases the query target the same way, so they meet
    assert store.admission_denied(tenant=TENANT, action_class="raise_invoice",
                                  target_system="tms:truckingoffice") is not None


def test_an_integration_brake_is_tenant_isolated():
    conn = _conn()
    _human(conn, "ops")
    store = _store(conn)
    store.engage(tenant=TENANT, target_system=TO, actor="ops", actor_kind="HUMAN", reason="A only")
    assert store.admission_denied(tenant=TENANT, action_class="raise_invoice",
                                  target_system=TO) is not None
    # a different tenant with the SAME integration is untouched — one tenant's incident is not another's
    assert store.admission_denied(tenant="tenant-b", action_class="raise_invoice",
                                  target_system=TO) is None


def test_overlapping_scopes_report_the_widest_and_any_denies():
    conn = _conn()
    _human(conn, "ops")
    store = _store(conn)
    store.engage(tenant=TENANT, action_class="raise_invoice", actor="ops", actor_kind="HUMAN",
                 reason="action")
    store.engage(tenant=TENANT, target_system=TO, actor="ops", actor_kind="HUMAN", reason="integration")
    # both cover the effect; the wider (integration) is reported ahead of the action-class one
    d = store.admission_denied(tenant=TENANT, action_class="raise_invoice", target_system=TO)
    assert d is not None and d.scope == "integration:tms:truckingoffice"
    # a tenant-wide brake is wider still
    store.engage(tenant=TENANT, actor="ops", actor_kind="HUMAN", reason="tenant")
    d2 = store.admission_denied(tenant=TENANT, action_class="raise_invoice", target_system=TO)
    assert d2 is not None and d2.scope == "tenant"
    # and the platform brake dominates everything
    store.engage_platform(actor="detector:iso", actor_kind="DETECTOR", reason="global")
    d3 = store.admission_denied(tenant=TENANT, action_class="raise_invoice", target_system=TO)
    assert d3 is not None and d3.scope == "GLOBAL"


def test_a_legacy_admission_caller_without_target_system_matches_no_integration_brake():
    """target_system is optional so the P3-era call shape still works — it simply cannot match an
    integration scope. The checkpoint passes it; a caller that does not is fail-safe (an integration
    brake still bumps the tenant version and the claim CAS refuses)."""
    conn = _conn()
    _human(conn, "ops")
    store = _store(conn)
    store.engage(tenant=TENANT, target_system=TO, actor="ops", actor_kind="HUMAN", reason="integration")
    assert store.admission_denied(tenant=TENANT, action_class="raise_invoice") is None
    # but a tenant-wide brake still denies the legacy call
    store.engage(tenant=TENANT, actor="ops", actor_kind="HUMAN", reason="tenant")
    assert store.admission_denied(tenant=TENANT, action_class="raise_invoice") is not None


def test_the_landed_grammar_has_no_composite_scope():
    conn = _conn()
    _human(conn, "ops")
    store = _store(conn)
    with pytest.raises(BrakeError, match="composite"):
        store.engage(tenant=TENANT, action_class="raise_invoice", target_system=TO,
                     actor="ops", actor_kind="HUMAN", reason="both at once")


def test_the_platform_brake_carries_no_integration_or_action_scope():
    conn = _conn()
    _human(conn, "ops")
    store = _store(conn)
    with pytest.raises(BrakeError):
        store.engage(tenant=None, target_system=TO, actor="ops", actor_kind="HUMAN", reason="global?")


def test_fail_closed_on_unreadable_brake_with_an_integration_target():
    conn = _conn()
    conn.execute("DROP TABLE platform_brake")   # the row is undeletable; a dropped table is unreadable
    conn.commit()
    with pytest.raises(BrakeStoreUnreachable):
        _store(conn).admission_denied(tenant=TENANT, action_class="raise_invoice", target_system=TO)


# ============================================================ INTEGRATION scope — the facade & ratchet

def test_a_detector_may_engage_an_integration_brake_but_never_release_it():
    """ADR-011 §5.2: repeated UNKNOWN_OUTCOMEs engage a `tenant + integration` brake. A detector may
    engage it; it may NEVER clear its own alarm."""
    conn = _conn()
    m = _machine(conn)
    s = m.engage_brake(tenant=TENANT, target_system=TO, actor="detector:unknowns",
                       actor_class="detector", reason="2 unknown outcomes on this integration")
    assert s.scope == "integration:tms:truckingoffice" and s.actor_kind == "DETECTOR"
    with pytest.raises(BrakeRefused):
        m.release_brake(tenant=TENANT, brake_id=s.brake_id, actor="detector:unknowns",
                        actor_class="detector", decision_ref="d", evidence=_evidence())
    got = conn.execute("SELECT COUNT(*) FROM event_outbox WHERE "
                       "event_name='UnauthorizedBrakeReleaseAttempted'").fetchone()[0]
    assert got == 1


def test_a_model_may_not_engage_an_integration_brake():
    conn = _conn()
    m = _machine(conn)
    with pytest.raises(BrakeRefused):
        m.engage_brake(tenant=TENANT, target_system=TO, actor="agent:gpt", actor_class="model",
                       reason="I decided the TMS looks unhealthy")


def test_an_integration_brake_engages_with_the_policy_engine_and_tms_down():
    # engage touches only the brake tables — no policy engine, rule store, or TMS read
    conn = _conn()
    _human(conn, "ops")
    s = _machine(conn).engage_brake(tenant=TENANT, target_system=TO, actor="ops",
                                    actor_class="human", reason="everything downstream is down")
    assert s.state == "ACTIVE" and s.scope == "integration:tms:truckingoffice"


def test_reads_continue_under_an_integration_brake():
    conn = _conn()
    m = _machine(conn)
    m.engage_brake(tenant=TENANT, target_system=TO, actor="detector:orphan", actor_class="detector",
                   reason="repeated unknowns")
    r = m.report(tenant=TENANT)[0]
    assert r.scope == "integration:tms:truckingoffice"
    assert set(r.still_allowed) >= {"observation", "reconciliation", "reads"}
    # a consequential write, a compensation and a migration write are all blocked (no admin bypass)
    assert {"consequential_write", "compensation", "migration_tool"} <= set(bl.BLOCKED_UNDER_BRAKE)


def test_integration_scope_parses_to_its_target_system():
    assert bl.parse_scope("integration:tms:truckingoffice") == ("INTEGRATION", "tms:truckingoffice")
    with pytest.raises(BrakeError):
        bl.parse_scope("integration:")   # an empty target refuses; it never scopes to nothing


# ============================================================ COUNTERPARTY — adjudicated deferred

def test_counterparty_scope_stays_unspellable_and_the_partition_is_clean():
    """COUNTERPARTY is adjudicated NOT deterministic at the effect boundary today: the effect has no
    counterparty field, and the only counterparty value is an optional free-form SYSTEM_IMPORTED
    material fact whose canonical identity arrives at P9. An unspellable scope forces a wider brake,
    never none. INTEGRATION, by contrast, IS deterministic and landed this run."""
    assert "COUNTERPARTY" in bl.DEFERRED_SCOPE_DIMENSIONS
    assert "COUNTERPARTY" not in bl.LANDED_SCOPE_DIMENSIONS
    assert "INTEGRATION" in bl.LANDED_SCOPE_DIMENSIONS
    # landed ∪ deferred == the canonical five, with a recorded reason for the one deferral
    assert bl.scope_partition_problems() == []
    assert bl.SCOPE_DEFERRAL_REASONS.get("COUNTERPARTY", "").strip()
    assert bl.SCOPE_DEFERRAL_REASONS.get("INTEGRATION") is None   # no longer deferred
    for spelling in ("counterparty:redline", "counterparty:", "COUNTERPARTY", "person:dave"):
        with pytest.raises(BrakeError):
            bl.parse_scope(spelling)


def test_rejected_dimensions_are_never_landed():
    """ADR-011 §9 explicitly rejects ENTITY, WORKFLOW and PERSON scopes; none may appear."""
    for rejected in ("ENTITY", "WORKFLOW", "PERSON", "ACCOUNTABLE_OWNER"):
        assert rejected not in bl.CANONICAL_SCOPE_DIMENSIONS
        assert rejected not in bl.LANDED_SCOPE_DIMENSIONS


# ============================================================ end-to-end through the checkpoint

def test_an_integration_brake_refuses_the_mint_through_the_checkpoint(tmp_path):
    store, kernel, effect, inputs, request, brakes, run_checkpoint, claim, params_for = _boundary(tmp_path)
    brakes.engage(tenant="tenant-alpha", target_system=TO, actor="ops", actor_kind="HUMAN",
                  reason="stop TruckingOffice")
    out = run_checkpoint(kernel, request, inputs)
    assert not out.authorized and out.step == 7 and out.reason == "BRAKE_ENGAGED"


def test_an_integration_brake_on_another_system_admits_the_mint(tmp_path):
    store, kernel, effect, inputs, request, brakes, run_checkpoint, claim, params_for = _boundary(tmp_path)
    brakes.engage(tenant="tenant-alpha", target_system=OTHER, actor="ops", actor_kind="HUMAN",
                  reason="stop a different integration")
    out = run_checkpoint(kernel, request, inputs)
    assert out.authorized   # the effect's integration is not the braked one


def test_engaging_an_integration_brake_between_mint_and_claim_refuses_the_claim(tmp_path):
    """Global-per-tenant invalidation (§8.3) still holds for an integration brake: engaging one
    bumps the tenant version, so the claim CAS matches zero rows — the effect does nothing."""
    store, kernel, effect, inputs, request, brakes, run_checkpoint, claim, params_for = _boundary(tmp_path)
    out = run_checkpoint(kernel, request, inputs)
    assert out.authorized
    brakes.engage(tenant="tenant-alpha", target_system=TO, actor="ops", actor_kind="HUMAN",
                  reason="between mint and claim")
    c = claim(kernel, out.handle, params_for(effect))
    assert c.claimed is False and c.cause == "BRAKE_CHANGED"


def test_an_integration_brake_after_the_claim_never_kills_the_in_flight_effect(tmp_path):
    """Positions 3-5 run to a verified conclusion; the brake stops the NEXT effect, not the last."""
    store, kernel, effect, inputs, request, brakes, run_checkpoint, claim, params_for = _boundary(tmp_path)
    out = run_checkpoint(kernel, request, inputs)
    assert claim(kernel, out.handle, params_for(effect)).claimed is True
    brakes.engage(tenant="tenant-alpha", target_system=TO, actor="ops", actor_kind="HUMAN",
                  reason="after the claim")
    state = store.conn.execute("SELECT state FROM effect_grants WHERE grant_id=?",
                               (out.handle.grant_id,)).fetchone()[0]
    assert state == "CLAIMED"
    n_unknown = store.conn.execute(
        "SELECT COUNT(*) FROM effect_grants WHERE state='UNKNOWN_OUTCOME'").fetchone()[0]
    assert n_unknown == 0, "the brake manufactured an unknown outcome"


def test_the_engage_vs_claim_race_for_an_integration_brake_is_one_or_the_other(tmp_path):
    """Either the claim wins (proceeds to verification, reported in-flight) or the brake wins (the
    claim finds zero rows and nothing happens) — never both, never neither — for integration scope."""
    from phase3_kit import (
        CheckpointInputs, CheckpointRequest, live_reader, make_approval, make_effect, make_facts)
    from freight_recon.checkpoint import claim_grant_cas, run_checkpoint
    from phase3_kit import make_kernel, make_store, params_for
    store = make_store(tmp_path)
    kernel, clock = make_kernel(store)
    brakes = BrakeStore(store.conn)
    _seed_ops(store, "tenant-alpha")
    outcomes = []
    for i in range(24):
        resource = f"load:int-{i}"
        effect = make_effect(resource=resource)   # target_system == tms:truckingoffice
        facts = make_facts(entity_ref=resource)
        approval = make_approval(effect, facts, {resource: 1}, clock)
        inputs = CheckpointInputs(
            material_facts_reader=live_reader(lambda f=facts: dict(f)),
            projection_assertion={}, projected_state_reader=live_reader({}),
            entity_version_reader=live_reader({resource: 1}), approval=approval)
        request = CheckpointRequest(effect=effect, actor="pipeline",
                                    accountable_owner="owner:rasheed", target_entity_ref=resource)
        out = run_checkpoint(kernel, request, inputs)
        assert out.authorized, f"iter {i}: {out}"
        engage_before = i % 2 == 0
        bid = None
        if engage_before:
            bid = brakes.engage(tenant="tenant-alpha", target_system=TO, actor="ops",
                                actor_kind="HUMAN", reason=f"race {i}").brake_id
        claim = claim_grant_cas(kernel, out.handle, params_for(effect))
        if not engage_before:
            bid = brakes.engage(tenant="tenant-alpha", target_system=TO, actor="ops",
                                actor_kind="HUMAN", reason=f"race {i}").brake_id
        blocked = claim.claimed is False and claim.cause == "BRAKE_CHANGED"
        assert claim.claimed != blocked, f"iter {i}: both or neither ({claim})"
        assert claim.claimed is (not engage_before), f"iter {i}: wrong winner"
        brakes.release(tenant="tenant-alpha", brake_id=bid, actor="ops", actor_kind="HUMAN",
                       decision_ref=f"d-{i}")
        outcomes.append(claim.claimed)
    assert any(outcomes) and not all(outcomes), "the interleave population collapsed to one branch"
    store.close()


# ============================================================ durable release-evidence backstop

def test_release_refused_while_a_claimed_effect_is_in_flight_despite_attestation(tmp_path):
    """The caller attests `in_flight_accounted=True`, but the DURABLE ledger shows a CLAIMED effect
    still in flight. The ledger wins; the attestation may not outrun it (ADR-011 §6/§3)."""
    store, kernel, effect, inputs, request, brakes, run_checkpoint, claim, params_for = _boundary(tmp_path)
    _seed_ops(store, "tenant-alpha")
    out = run_checkpoint(kernel, request, inputs)
    assert claim(kernel, out.handle, params_for(effect)).claimed is True   # CLAIMED = in flight
    m = BrakeMachine(brakes)
    s = brakes.engage(tenant="tenant-alpha", actor="ops", actor_kind="HUMAN", reason="incident")
    with pytest.raises(BrakeRefused) as refused:
        m.release_brake(tenant="tenant-alpha", brake_id=s.brake_id, actor="ops", actor_class="human",
                        decision_ref="d", evidence=_evidence(in_flight_accounted=True))
    assert "durable" in str(refused.value) and "in flight" in str(refused.value)
    # the brake stays ACTIVE and the in-flight effect was never killed
    assert brakes.status(tenant="tenant-alpha", brake_id=s.brake_id).state == "ACTIVE"
    assert store.conn.execute("SELECT state FROM effect_grants WHERE grant_id=?",
                              (out.handle.grant_id,)).fetchone()[0] == "CLAIMED"


def test_release_refused_when_an_unknown_outcome_is_hidden_by_omission(tmp_path):
    """An UNKNOWN_OUTCOME in the ledger cannot be made to disappear by leaving it out of the release
    evidence. It does NOT block release once acknowledged and owned — but omission is refused, and
    the release never thaws it (ADR-011 §6, rule 12)."""
    store, kernel, effect, inputs, request, brakes, run_checkpoint, claim, params_for = _boundary(tmp_path)
    _seed_ops(store, "tenant-alpha")
    out = run_checkpoint(kernel, request, inputs)
    claim(kernel, out.handle, params_for(effect))
    # verification became impossible → the grant is UNKNOWN_OUTCOME in the durable ledger
    store.conn.execute("UPDATE effect_grants SET state='UNKNOWN_OUTCOME' WHERE grant_id=?",
                       (out.handle.grant_id,))
    store.conn.commit()
    m = BrakeMachine(brakes)
    s = brakes.engage(tenant="tenant-alpha", actor="ops", actor_kind="HUMAN", reason="incident")
    # omitting it → refused
    with pytest.raises(BrakeRefused) as refused:
        m.release_brake(tenant="tenant-alpha", brake_id=s.brake_id, actor="ops", actor_class="human",
                        decision_ref="d", evidence=_evidence(unknown_outcomes=[]))
    assert "UNKNOWN_OUTCOME" in str(refused.value)
    # acknowledged + owned → released (they do not block release)
    released = m.release_brake(
        tenant="tenant-alpha", brake_id=s.brake_id, actor="ops", actor_class="human",
        decision_ref="d",
        evidence=_evidence(unknown_outcomes=[
            {"grant_id": out.handle.grant_id, "acknowledged": True, "owner": "ops"}]))
    assert released.state == "RELEASED"
    # the release did NOT thaw the unknown outcome — its ledger row is untouched
    assert store.conn.execute("SELECT state FROM effect_grants WHERE grant_id=?",
                              (out.handle.grant_id,)).fetchone()[0] == "UNKNOWN_OUTCOME"


def test_an_owned_but_unacknowledged_unknown_outcome_is_refused(tmp_path):
    """Owned is not enough — it must be ACKNOWLEDGED too (both, per ADR-011 §6)."""
    store, kernel, effect, inputs, request, brakes, run_checkpoint, claim, params_for = _boundary(tmp_path)
    _seed_ops(store, "tenant-alpha")
    out = run_checkpoint(kernel, request, inputs)
    claim(kernel, out.handle, params_for(effect))
    store.conn.execute("UPDATE effect_grants SET state='UNKNOWN_OUTCOME' WHERE grant_id=?",
                       (out.handle.grant_id,))
    store.conn.commit()
    m = BrakeMachine(brakes)
    s = brakes.engage(tenant="tenant-alpha", actor="ops", actor_kind="HUMAN", reason="incident")
    with pytest.raises(BrakeRefused):
        m.release_brake(
            tenant="tenant-alpha", brake_id=s.brake_id, actor="ops", actor_class="human",
            decision_ref="d",
            evidence=_evidence(unknown_outcomes=[
                {"grant_id": out.handle.grant_id, "acknowledged": False, "owner": "ops"}]))


def test_a_clean_ledger_releases_normally(tmp_path):
    """The durable backstop is additive: with no in-flight effect and no unknown outcome, release
    proceeds exactly as before."""
    store, kernel, effect, inputs, request, brakes, run_checkpoint, claim, params_for = _boundary(tmp_path)
    _seed_ops(store, "tenant-alpha")
    m = BrakeMachine(brakes)
    s = brakes.engage(tenant="tenant-alpha", actor="ops", actor_kind="HUMAN", reason="incident")
    released = m.release_brake(tenant="tenant-alpha", brake_id=s.brake_id, actor="ops",
                               actor_class="human", decision_ref="d", evidence=_evidence())
    assert released.state == "RELEASED"


def test_the_durable_shortfalls_are_specific_not_contact_an_administrator(tmp_path):
    store, kernel, effect, inputs, request, brakes, run_checkpoint, claim, params_for = _boundary(tmp_path)
    _seed_ops(store, "tenant-alpha")
    out = run_checkpoint(kernel, request, inputs)
    claim(kernel, out.handle, params_for(effect))
    m = BrakeMachine(brakes)
    shortfalls = m.release_ledger_shortfalls(tenant="tenant-alpha", acknowledged_unknowns=())
    assert shortfalls and any("in flight" in s for s in shortfalls)
    assert all("contact an administrator" not in s.lower() for s in shortfalls)


# ============================================================ ships dark / single authority preserved

def test_the_integration_landing_added_no_production_importer_of_the_dark_facade():
    pkg = ROOT / "src" / "freight_recon"
    importers = []
    for py in sorted(pkg.rglob("*.py")):
        if py.name == "brake_lifecycle.py":
            continue
        src = py.read_text(encoding="utf-8")
        if ("import brake_lifecycle" in src or "from .brake_lifecycle" in src
                or "from freight_recon.brake_lifecycle" in src):
            importers.append(py.name)
    assert importers == [], f"a production module imports the dark M13 surface: {importers}"


def test_brake_py_still_does_not_import_the_policy_engine():
    """The integration landing must not make the brake depend on the subsystem it exists to overrule
    (ADR-011 §0). Asserted by AST over brake.py's real imports."""
    import ast
    tree = ast.parse((ROOT / "src" / "freight_recon" / "brake.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.rsplit(".", 1)[-1])
        elif isinstance(node, ast.Import):
            imported |= {a.name.rsplit(".", 1)[-1] for a in node.names}
    assert not (imported & {"policy", "product_policy", "policy_admission", "rule", "rule_admission"})


# ============================================================ the mutation battery, OPERATED here
#
# The guards above assert refusals and scoped denials — an ABSENCE proves nothing until a realised
# forbidden state shows the guard still FIRES. That proof lives in scripts/mutate_phase6_brake.py,
# which this change edited (it grew the six U8.3 mutants). A battery that only a hand-run CLI
# exercises is one the STANDARD RUNNER cannot measure — and a guard's own green is not evidence it
# was measured. So the battery is invoked HERE, through pytest, exactly as U8.1 did for its admission
# battery (`test_p8_policy_admission.py::test_the_whole_p8_admission_mutation_battery_is_OPERATED_by_
# the_runner`). Loading it as a non-`__main__` module does not trigger its `main()`.


def _load_brake_battery():
    import importlib.util
    battery_path = ROOT / "scripts" / "mutate_phase6_brake.py"
    assert battery_path.exists(), f"the mutation battery is gone: {battery_path}"
    spec = importlib.util.spec_from_file_location("_mutate_phase6_brake_for_test", battery_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_each_new_u83_brake_guard_fires_under_its_mutant_through_the_runner():
    """### THE U8.3 DELTA'S GUARDS, PROVEN DISCRIMINATING BY RUNNER-COLLECTED MUTATIONS (CLAUDE.md §6).

    Every load-bearing guard this change added asserts a refusal or a scoped denial. That is exactly
    the kind of claim that passes vacuously until a realised forbidden state shows it still FIRES. The
    battery carries one mutant per new guard; this drives EACH through the mutation harness — GREEN
    before, RED under the reintroduced defect (CAUGHT), GREEN after a byte-for-byte in-memory restore.
    It NEVER uses git to undo a mutation (CLAUDE.md §6). The population is DISCOVERED — the mutants
    this change added are exactly those whose guard lives in THIS file — and floored so 'all CAUGHT'
    is a measurement over a non-empty set, not a vacuous pass over nothing (M-9).
    """
    mod = _load_brake_battery()
    new_cases = [(label, edits, guard) for (label, edits, guard) in mod.CASES
                 if "test_p8_brake_scope.py" in guard]
    assert len(new_cases) >= 6, (
        f"expected the six U8.3 delta mutants (integration match, checkpoint wiring, composite "
        f"refusal, counterparty deferral, in-flight ledger, unknown-outcome completeness); found "
        f"{len(new_cases)}: {[label for label, _e, _g in new_cases]}. The runner-collected firing "
        f"proof requires each new guard's mutant to exist.")
    results = {label: mod._run_edits(edits, guard) for label, edits, guard in new_cases}
    escaped = {label: (verdict, note) for label, (verdict, note) in results.items()
               if verdict != "CAUGHT"}
    assert not escaped, (
        f"a U8.3 brake guard is NOT discriminating (its mutant escaped): {escaped}. A guard whose "
        f"refusal cannot be shown to fire is a decoration (CLAUDE.md §6); the tier-1 brake edit is "
        f"unverified.")


def test_the_whole_m13_brake_mutation_battery_is_OPERATED_by_the_runner():
    """### THE ENTIRE M13 MUTATION BATTERY, OPERATED THROUGH PYTEST — not only the ad-hoc CLI.

    `scripts/mutate_phase6_brake.py` is a verification deliverable this change edited. A battery only
    a hand-run command exercises is one the standard runner cannot MEASURE, and an unmeasured guard is
    not a passing guard. This invokes the battery's own approved entry point, `main()`, which for
    EVERY case runs the guard GREEN on the un-mutated tree, reintroduces the real defect, requires the
    guard RED (CAUGHT), and restores brake.py / brake_lifecycle.py / checkpoint.py / phase6_brakes.py
    byte-for-byte from memory — never with git (CLAUDE.md §6). `main()` returns 0 only if every mutant
    is caught AND the anti-vacuity control is GREEN, so a single `== 0` is the whole battery, measured
    by the runner. It is slow by nature (a subprocess pytest per mutant); that cost is the measurement.

    Command the runner executes it under:
        .venv/bin/python -m pytest -q -p no:cacheprovider eval/tests/test_p8_brake_scope.py
    """
    mod = _load_brake_battery()
    # A non-empty, GROWN population (M-9): the 18 landed M13 mutants plus the 6 this change added, or
    # 'every mutant CAUGHT' would be a vacuous pass over few.
    assert len(mod.CASES) >= 24, (
        f"the M13 brake battery has {len(mod.CASES)} mutants; it must carry all of them (the 18 "
        f"landed M13 guards plus the 6 U8.3 delta guards) for 'every mutant CAUGHT' to mean anything.")
    rc = mod.main()
    assert rc == 0, (
        "the M13 brake mutation battery did NOT report every mutant CAUGHT with a GREEN anti-vacuity "
        "control (main() returned nonzero). A guard that cannot be shown to fire is unverified "
        "(CLAUDE.md §6); see the per-mutant report captured above.")
