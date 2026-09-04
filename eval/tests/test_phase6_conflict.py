"""P6 / M7 — the Conflict — acceptance and hostile battery.

Entity §44 names eight adversarial tests by name; they are here by those names. Machine §14 names one
per-transition test by name; they are here too. The rest of the battery covers the five states and the
CF-1…CF-7 transitions, the resolution invariant (a registered rule id or an authenticated decision_ref
and NEVER a third way), the durable-timer escalation that never resolves, the partial unique index that
is also the durable field condition, the party set that survives a rebuild, the M6/M3 seams M7 must not
rewrite, the checkpoint seam, and the ship-dark posture. Several node ids are the guards
`scripts/mutate_phase6_conflict.py` turns RED — a guard never seen to fail is a decoration.

The suite protects M7's actual behaviour: a disagreement can never be silently resolved by recency,
confidence, a model, a counterparty, or a clock, and a consequential action can never proceed on a
field two sources disagree about.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

from freight_recon.conflict import (  # noqa: E402
    CONFLICT_RAISED_PRODUCERS,
    M7_AQ1_SEAM,
    PRODUCED_CONTRACTS,
    CfState,
    GuardNotSatisfied,
    IllegalTransition,
    M7Machine,
    MalformedConflict,
    Party,
    StateConflict,
    UnknownConflict,
)
from freight_recon.event_timers import TimerFired, TimerRelay  # noqa: E402
from freight_recon.migrations.phase6_conflicts import (  # noqa: E402
    CONFLICT_KINDS,
    CONFLICT_STATES,
    phase6_conflicts_readiness_problems,
)
from freight_recon.schema import (  # noqa: E402
    create_canonical_schema,
    enable_and_verify_foreign_keys,
    schema_readiness_problems,
)

TENANT = "acme-brokerage"
HUMAN = "owner:dana"
REG_RULE = "rule:tms-beats-portal-v1"


def _conn() -> sqlite3.Connection:
    tmp = Path(tempfile.mkdtemp(prefix="p6m7-test-"))
    conn = sqlite3.connect(str(tmp / "cf.db"))
    conn.row_factory = sqlite3.Row
    enable_and_verify_foreign_keys(conn)
    create_canonical_schema(conn)
    enable_and_verify_foreign_keys(conn)
    return conn


def _human(conn: sqlite3.Connection, tenant: str = TENANT, human_id: str = HUMAN,
           state: str = "ACTIVE") -> str:
    off = "off" if state == "OFFBOARDED" else None
    conn.execute(
        "INSERT OR IGNORE INTO tenant_humans (tenant, human_id, display_name, authority_role, "
        "state, recorded_at, recorded_by, recorded_by_kind, offboarded_at) "
        "VALUES (?,?,?,?, ?, ?, ?, 'human', ?)",
        (tenant, human_id, human_id, "AUTHORIZED_HUMAN", state, "2026-08-20T09:00:00.000Z",
         "founder", off))
    conn.commit()
    return human_id


def _observation(conn: sqlite3.Connection, oid: str, tenant: str = TENANT) -> str:
    conn.execute(
        "INSERT OR IGNORE INTO observations (tenant, observation_id, source_system, external_id, "
        "content_digest, raw_value, as_of, received_at, state, version, provenance_class, "
        "created_at, updated_at) VALUES (?,?, 'tms:read', ?, ?, 'v', 't', 't', 'RECEIVED', 1, "
        "'SYSTEM_IMPORTED', 't', 't')", (tenant, oid, oid, oid))
    conn.commit()
    return oid


def _machine(conn: sqlite3.Connection, tenant: str = TENANT, *, registered_rules=None) -> M7Machine:
    _human(conn, tenant)
    return M7Machine(conn, tenant=tenant, registered_rules=registered_rules)


def _rb(ref: str, prov: str = "MODEL_EXTRACTED", value: str = "v") -> Party:
    return Party(ref, "readback", prov, value)


def _two(a: str = "src-a", b: str = "src-b") -> list[Party]:
    return [_rb(a, "MODEL_EXTRACTED", "delivered"), _rb(b, "MODEL_INFERRED", "in_transit")]


def _raise(m: M7Machine, *, kind="SYSTEM_VS_SYSTEM", entity="load:4471", field="delivery",
           parties=None, owner=HUMAN):
    return m.raise_conflict(kind=kind, entity_ref=entity, field=field,
                            parties=(parties or _two()), owner_id=owner)


def _open(m: M7Machine, **kw) -> str:
    r = _raise(m, **kw)
    m.acknowledge(r.conflict.conflict_id)
    return r.conflict.conflict_id


# ============================ entity §44 — the eight adversarial tests ============================

def test_open_conflict_blocks_all_consequential_actions():
    """(a) an open Conflict blocks all consequential actions on the entity (entity §43a, AC-SAFE-017).

    Feeds M7's native projection into the P3 checkpoint's EXISTING step 4 for every open state —
    RAISED, OPEN and ESCALATED all block. M7 supplies native state; the checkpoint is the one gate."""
    from phase3_kit import green_scenario
    from freight_recon.checkpoint import (CheckpointInputs, NativeClaim, ProvenanceClass,
                                          run_checkpoint)
    conn = _conn()
    m = _machine(conn)
    r = _raise(m, entity="load:4471", field="amount")
    cid = r.conflict.conflict_id
    for state in ("RAISED", "OPEN", "ESCALATED"):
        if state == "OPEN":
            m.acknowledge(cid)
        elif state == "ESCALATED":
            m.escalate(cid)
        proj = m.get(cid).native_projection()
        assert proj.conflicting
        tmp = Path(tempfile.mkdtemp(prefix="p6m7-ck-"))
        store, kernel, clock, effect, facts, versions, approval, world, inputs, request = \
            green_scenario(tmp)
        nc = NativeClaim(claim_id=proj.claim_id, status=proj.status, conflicting=proj.conflicting,
                         provenance=ProvenanceClass(proj.provenance))
        inputs = CheckpointInputs(
            material_facts_reader=inputs.material_facts_reader,
            projection_assertion=inputs.projection_assertion,
            projected_state_reader=inputs.projected_state_reader,
            entity_version_reader=inputs.entity_version_reader, native_claims=(nc,),
            approval=approval)
        outcome = run_checkpoint(kernel, request, inputs)
        assert not outcome.authorized and outcome.step == 4, state
        store.close()


def test_no_timer_or_model_resolves_a_conflict():
    """(b) no timer/model resolves it (entity §43b, ADR-007 §5.3, machine §15)."""
    conn = _conn()
    m = _machine(conn, registered_rules={REG_RULE})
    cid = _open(m)
    # A model actor cannot resolve — ILLEGAL, recorded to audit AND security.
    with pytest.raises(IllegalTransition):
        m.resolve(cid, decision_ref="d", decision_human_id=HUMAN, actor_kind="model")
    # A durable timer firing with any kind other than the age-threshold escalation is ILLEGAL — there
    # is no timer_kind that reaches a resolution.
    with pytest.raises(IllegalTransition):
        m.handle_timer_fired(TimerFired(
            tenant=TENANT, timer_id="t", aggregate_type="conflict", aggregate_id=cid,
            timer_kind="conflict_resolve", fire_at="t", fired_at="t", payload={}))
    assert m.get(cid).state is CfState.OPEN
    sec = [r["event_type"] for r in conn.execute(
        "SELECT event_type FROM security_events WHERE tenant = ?", (TENANT,))]
    assert "IllegalTransitionAttempted" in sec


def test_resolution_requires_rule_id_or_decision_ref():
    """(c) resolution requires a rule id or a decision ref (entity §43c, §16)."""
    conn = _conn()
    m = _machine(conn, registered_rules={REG_RULE})
    cid = _open(m)
    # Neither → ILLEGAL.
    with pytest.raises(IllegalTransition):
        m.resolve(cid)
    # Both → refused (exactly one).
    with pytest.raises(GuardNotSatisfied):
        m.resolve(cid, rule_id=REG_RULE, decision_ref="d", decision_human_id=HUMAN)
    assert m.get(cid).state is CfState.OPEN
    # A registered rule alone resolves; a decision_ref alone resolves.
    r = m.resolve(cid, rule_id=REG_RULE)
    assert r.conflict.state is CfState.RESOLVED_BY_RULE
    cid2 = _open(m, entity="load:2")
    r2 = m.resolve(cid2, decision_ref="audit:d", decision_human_id=HUMAN, actor_kind="human")
    assert r2.conflict.state is CfState.RESOLVED_BY_HUMAN


def test_inferrer_vs_owner_raises_conflict():
    """(d) inferrer-vs-owner disagreement raises a Conflict recording the OWNER_ASSERTED party
    (entity §43d/§13)."""
    conn = _conn()
    m = _machine(conn)
    r = _raise(m, kind="INFERRER_VS_OWNER", entity="pod:1", field="belongs_to",
               parties=[_rb("owner-binding", "OWNER_ASSERTED", "load:4471"),
                        _rb("relinker", "LINKER_INFERRED", "load:44718")])
    provs = {p["provenance_class"] for p in m.parties(r.conflict.conflict_id)}
    assert "OWNER_ASSERTED" in provs
    assert m.get(r.conflict.conflict_id).kind == "INFERRER_VS_OWNER"


def test_two_conflicting_rules_fail_closed():
    """(e) two conflicting rules block, not auto-merge (entity §43e, spec §20.7, GR-15)."""
    conn = _conn()
    m = _machine(conn, registered_rules={REG_RULE})
    r = _raise(m, kind="RULE_VS_RULE", entity="load:4471", field="delivery",
               parties=[_rb("rule:portal-governs", "RECONCILED", "in_transit"),
                        _rb("rule:tms-governs", "RECONCILED", "delivered")])
    c = m.get(r.conflict.conflict_id)
    # Even with a registered rule present, RULE_VS_RULE is raised and blocks — never auto-merged.
    assert c.state is CfState.RAISED and c.native_projection().conflicting


def test_readback_vs_approved_raises_conflict():
    """The M7-OWNED half only (§3.7, M7-AQ-2): a readback contradicting the approved facts is a
    Conflict that BLOCKS and is NOT laundered into a normal failure. M3 is not edited and no
    UNKNOWN_OUTCOME is moved."""
    conn = _conn()
    m = _machine(conn)
    r = _raise(m, kind="READBACK_VS_APPROVED", entity="payable:77", field="amount",
               parties=[_rb("approved", "OWNER_ASSERTED", "285000"),
                        _rb("readback", "SYSTEM_IMPORTED", "310000")])
    c = m.get(r.conflict.conflict_id)
    assert c.kind == "READBACK_VS_APPROVED" and c.native_projection().conflicting
    # M7 mints no substitute event and does not touch M3's tables.
    assert conn.execute("SELECT COUNT(*) FROM effect_grants").fetchone()[0] == 0
    src = (ROOT / "src" / "freight_recon" / "conflict.py").read_text(encoding="utf-8")
    assert "from .external_effect" not in src and "import external_effect" not in src


def test_injected_competing_claim_freezes_entity_not_control():
    """spec §24 — an attacker injecting a competing claim gains a FROZEN entity and a human's
    attention, NOT control."""
    conn = _conn()
    m = _machine(conn)
    r = _raise(m, kind="CLAIM_VS_OBSERVATION", entity="load:4471", field="pay_to",
               parties=[_rb("legit", "SYSTEM_IMPORTED", "acme"),
                        _rb("injected", "MODEL_EXTRACTED", "attacker")])
    c = m.get(r.conflict.conflict_id)
    assert c.native_projection().conflicting          # the entity is frozen
    assert c.owner_id == HUMAN                          # a human owns it
    assert c.state is CfState.RAISED              # and nothing resolved it


def test_ownerless_conflict_impossible():
    """entity §37 — an ownerless Conflict is structurally impossible."""
    conn = _conn()
    m = _machine(conn)
    with pytest.raises(GuardNotSatisfied):
        _raise(m, owner="")
    with pytest.raises(GuardNotSatisfied):
        _raise(m, owner="model:extractor")          # not a recorded ACTIVE human
    assert conn.execute("SELECT COUNT(*) FROM conflicts").fetchone()[0] == 0
    # And the database itself refuses a NULL owner.
    _observation(conn, "o")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO conflicts (tenant, conflict_id, entity_ref, field, kind, state, version, "
            "owner_id, created_at, updated_at) VALUES (?, 'x', 'e', 'f', 'SYSTEM_VS_SYSTEM', "
            "'RAISED', 1, NULL, 't', 't')", (TENANT,))
    conn.rollback()


# ============================ machine §14 — the per-transition tests =============================

def test_cf_raise_freezes_field_and_assigns_owner():
    """CF-1 — the raise, the freeze and the owner in ONE commit."""
    conn = _conn()
    m = _machine(conn)
    before = conn.execute(
        "SELECT COUNT(*) FROM event_outbox WHERE tenant=? AND event_name='ConflictRaised'",
        (TENANT,)).fetchone()[0]
    r = _raise(m, entity="load:4471", field="delivery")
    c = m.get(r.conflict.conflict_id)
    assert r.transition_id == "CF-1"
    assert c.state is CfState.RAISED and c.owner_id == HUMAN
    assert m.is_field_conflicting("load:4471", "delivery")       # the field is frozen
    after = conn.execute(
        "SELECT COUNT(*) FROM event_outbox WHERE tenant=? AND event_name='ConflictRaised'",
        (TENANT,)).fetchone()[0]
    assert after == before + 1                                    # the event landed, once


def test_cf_open():
    """CF-2 — RAISED → OPEN."""
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    r2 = m.acknowledge(r.conflict.conflict_id)
    assert r2.transition_id == "CF-2" and r2.conflict.state is CfState.OPEN
    assert r2.event_names == ("ConflictOpened",)


def test_cf_rule_resolution_requires_registered_rule_id():
    """CF-3 — a REGISTERED, versioned, deterministic rule may resolve; an unregistered one may not."""
    conn = _conn()
    m = _machine(conn, registered_rules={REG_RULE})
    cid = _open(m)
    with pytest.raises(GuardNotSatisfied):
        m.resolve(cid, rule_id="rule:unregistered")
    assert m.get(cid).state is CfState.OPEN
    r = m.resolve(cid, rule_id=REG_RULE)
    assert r.conflict.state is CfState.RESOLVED_BY_RULE and r.event_producer == "CF-3"


def test_cf_human_resolution_requires_decision_ref():
    """CF-4 — a valid decision_ref naming an authenticated ACTIVE human."""
    conn = _conn()
    m = _machine(conn)
    cid = _open(m)
    with pytest.raises(IllegalTransition):
        m.resolve_by_human(cid, decision_ref="", decision_human_id=HUMAN)
    r = m.resolve(cid, decision_ref="audit:d", decision_human_id=HUMAN, actor_kind="human")
    assert r.conflict.state is CfState.RESOLVED_BY_HUMAN and r.event_producer == "CF-4"
    assert m.get(cid).decision_human_id == HUMAN


def test_cf_ages_to_escalated():
    """CF-5 — OPEN → ESCALATED on AgeThresholdCrossed, via the existing durable-timer substrate."""
    conn = _conn()
    m = _machine(conn)
    from datetime import datetime, timedelta, timezone
    now = datetime(2026, 8, 26, tzinfo=timezone.utc)
    m2 = M7Machine(conn, tenant=TENANT, clock=lambda: now)
    r = _raise(m2)
    cid = r.conflict.conflict_id
    m2.acknowledge(cid, escalation_at=now + timedelta(hours=1))
    later = now + timedelta(hours=2)
    relay = TimerRelay(conn, tenant=TENANT, handler=lambda tr: M7Machine(
        conn, tenant=TENANT, clock=lambda: later).handle_timer_fired(tr), relay_id="r",
        clock=lambda: later)
    relay.run_once()
    assert m2.get(cid).state is CfState.ESCALATED
    assert conn.execute(
        "SELECT COUNT(*) FROM event_outbox WHERE tenant=? AND event_name='ConflictEscalated'",
        (TENANT,)).fetchone()[0] == 1


def test_cf_escalated_resolves():
    """CF-6 — an ESCALATED conflict resolves BY TARGET STATE (CF-3/CF-4), never positionally."""
    conn = _conn()
    m = _machine(conn, registered_rules={REG_RULE})
    # by rule
    r = _raise(m, entity="load:1")
    m.acknowledge(r.conflict.conflict_id)
    m.escalate(r.conflict.conflict_id)
    rr = m.resolve(r.conflict.conflict_id, rule_id=REG_RULE)
    assert rr.transition_id == "CF-6" and rr.event_producer == "CF-3"
    assert rr.conflict.state is CfState.RESOLVED_BY_RULE
    # by human
    r2 = _raise(m, entity="load:2")
    m.acknowledge(r2.conflict.conflict_id)
    m.escalate(r2.conflict.conflict_id)
    rh = m.resolve(r2.conflict.conflict_id, decision_ref="audit:d", decision_human_id=HUMAN,
                   actor_kind="human")
    assert rh.transition_id == "CF-6" and rh.event_producer == "CF-4"
    assert rh.conflict.state is CfState.RESOLVED_BY_HUMAN


def test_cf_new_party_attaches_not_new_conflict():
    """CF-7 — a new disagreeing party attaches to the existing open conflict, never a second one."""
    conn = _conn()
    m = _machine(conn)
    r = _raise(m, entity="load:4471", field="delivery")
    cid = r.conflict.conflict_id
    r2 = m.attach_party(cid, _rb("third", "RECONCILED", "delivered"))
    assert r2.transition_id == "CF-7" and r2.event_names == ("ConflictPartyAttached",)
    assert "third" in m.party_refs(cid)
    assert conn.execute(
        "SELECT COUNT(*) FROM conflicts WHERE tenant=? AND entity_ref='load:4471' AND field='delivery' "
        "AND state IN ('RAISED','OPEN','ESCALATED')", (TENANT,)).fetchone()[0] == 1


# ============================ the guards the mutation battery turns RED ==========================

def test_auto_resolve_is_illegal():
    """ADR-007 §5.3 names AutoResolve by hand as ILLEGAL — a resolution with no basis is not a
    resolution. GR-1 records it and persists nothing."""
    conn = _conn()
    m = _machine(conn)
    cid = _open(m)
    with pytest.raises(IllegalTransition):
        m.resolve(cid)                        # neither rule nor decision — the AutoResolve shape
    assert m.get(cid).state is CfState.OPEN


def test_confidence_never_resolves_at_1_0():
    """GR-8 / ADR-007 §8 — confidence orders a queue and gates nothing. A confidence pseudo-rule is
    unregistered and refused."""
    conn = _conn()
    m = _machine(conn, registered_rules={REG_RULE})
    cid = _open(m)
    with pytest.raises(GuardNotSatisfied):
        m.resolve(cid, rule_id="confidence:1.0")
    assert m.get(cid).state is CfState.OPEN


def test_recency_never_resolves():
    """ADR-007 §5.3 — the newest source is not a winner; a recency pseudo-rule is unregistered."""
    conn = _conn()
    m = _machine(conn, registered_rules={REG_RULE})
    cid = _open(m)
    with pytest.raises(GuardNotSatisfied):
        m.resolve(cid, rule_id="recency:newest-wins")
    assert m.get(cid).state is CfState.OPEN


def test_a_timer_transition_to_resolved_is_illegal():
    """machine §15 — ANY TimerFired-to-resolved is ILLEGAL. The only conflict timer escalates."""
    conn = _conn()
    m = _machine(conn)
    cid = _open(m)
    with pytest.raises(IllegalTransition):
        m.handle_timer_fired(TimerFired(
            tenant=TENANT, timer_id="t", aggregate_type="conflict", aggregate_id=cid,
            timer_kind="conflict_resolve", fire_at="t", fired_at="t", payload={}))
    assert m.get(cid).state is CfState.OPEN


def test_owner_notnull_makes_ownerless_impossible():
    """entity §37 — the owner_id NOT NULL column and its FK make an ownerless conflict impossible."""
    conn = _conn()
    m = _machine(conn)
    with pytest.raises(GuardNotSatisfied):
        _raise(m, owner="")
    assert conn.execute("SELECT COUNT(*) FROM conflicts").fetchone()[0] == 0


def test_raise_and_freeze_are_one_transaction():
    """entity §15 — a party FK failing mid-raise rolls back the conflict row AND the freeze AND the
    event: there is never a durable conflict without its frozen field, or a frozen field with no
    conflict."""
    conn = _conn()
    m = _machine(conn)
    with pytest.raises(sqlite3.IntegrityError):
        _raise(m, kind="CLAIM_VS_CLAIM", entity="load:4471", field="delivery",
               parties=[_rb("ok"),
                        Party("ghost", "identity_binding_claim", "LINKER_INFERRED", "x")])
    if conn.in_transaction:
        conn.rollback()
    assert conn.execute("SELECT COUNT(*) FROM conflicts").fetchone()[0] == 0
    assert not m.is_field_conflicting("load:4471", "delivery")
    assert conn.execute(
        "SELECT COUNT(*) FROM event_outbox WHERE tenant=? AND event_name='ConflictRaised'",
        (TENANT,)).fetchone()[0] == 0


def test_partial_unique_index_refuses_two_open_conflicts_per_field():
    """entity §17 — at most one OPEN conflict per (tenant, entity_ref, field)."""
    conn = _conn()
    m = _machine(conn)
    _raise(m, entity="load:4471", field="delivery")
    conn.execute("BEGIN IMMEDIATE")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO conflicts (tenant, conflict_id, entity_ref, field, kind, state, version, "
            "owner_id, created_at, updated_at) VALUES (?, 'dup', 'load:4471', 'delivery', "
            "'SYSTEM_VS_SYSTEM', 'RAISED', 1, ?, 't', 't')", (TENANT, HUMAN))
    conn.rollback()


def test_second_detection_attaches_rather_than_raising_a_second_conflict():
    """entity §33 — a concurrent second raise on an open field COALESCES into a party attach."""
    conn = _conn()
    m = _machine(conn)
    r = _raise(m, entity="load:4471", field="delivery", parties=_two("a", "b"))
    dup = _raise(m, entity="load:4471", field="delivery",
                 parties=[_rb("c", "RECONCILED", "x"), _rb("d", "MODEL_INFERRED", "y")])
    assert dup.coalesced
    assert conn.execute(
        "SELECT COUNT(*) FROM conflicts WHERE tenant=? AND entity_ref='load:4471' AND field='delivery' "
        "AND state IN ('RAISED','OPEN','ESCALATED')", (TENANT,)).fetchone()[0] == 1
    assert m.party_refs(r.conflict.conflict_id) == {"a", "b", "c", "d"}


def test_conflict_party_attached_rebuilds_the_full_party_set():
    """F7 — without ConflictPartyAttached a full-history rebuild reproduces a STALE party set."""
    conn = _conn()
    m = _machine(conn)
    r = _raise(m, parties=_two("p1", "p2"))
    cid = r.conflict.conflict_id
    m.attach_party(cid, _rb("p3", "RECONCILED", "x"))
    m.attach_party(cid, _rb("p4", "MODEL_INFERRED", "y"))
    rebuilt = m.rebuild(cid)
    assert set(rebuilt.parties) == {"p1", "p2", "p3", "p4"}
    assert conn.execute(
        "SELECT COUNT(*) FROM event_outbox WHERE tenant=? AND event_name='ConflictPartyAttached'",
        (TENANT,)).fetchone()[0] == 2


def test_party_provenance_is_carried_never_strengthened():
    """ER-14, R-P2 — an attached party's provenance is recorded verbatim and cannot be edited."""
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    cid = r.conflict.conflict_id
    m.attach_party(cid, _rb("weak", "MODEL_INFERRED", "x"))
    stored = {p["party_ref"]: p["provenance_class"] for p in m.parties(cid)}
    assert stored["weak"] == "MODEL_INFERRED"
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE conflict_parties SET provenance_class='OWNER_ASSERTED' "
            "WHERE tenant=? AND conflict_id=? AND party_ref='weak'", (TENANT, cid))
    conn.rollback()


def test_tenant_predicate_isolates_the_open_conflict_lookup():
    """[C-1] — the field-condition lookup is tenant-first; the same (entity, field) in two tenants
    are two isolated conflicts."""
    conn = _conn()
    ta, tb = "t-a", "t-b"
    a, b = _machine(conn, ta), _machine(conn, tb)
    a.raise_conflict(kind="SYSTEM_VS_SYSTEM", entity_ref="load:1", field="f", parties=_two(),
                     owner_id=_human(conn, ta))
    assert a.is_field_conflicting("load:1", "f")
    assert not b.is_field_conflicting("load:1", "f")     # tenant B's field is not frozen


def test_cf6_resolution_is_by_target_state_not_ordinal_position():
    """machine §14 CF-6 — the emitted producer (CF-3/CF-4) is chosen by the RESOLVED state reached,
    not by the order the escalated conflict was resolved in."""
    conn = _conn()
    m = _machine(conn, registered_rules={REG_RULE})
    r1 = _raise(m, entity="load:1")
    m.acknowledge(r1.conflict.conflict_id)
    m.escalate(r1.conflict.conflict_id)
    # First resolution is by HUMAN → producer CF-4, not CF-3-because-it-came-first.
    rh = m.resolve(r1.conflict.conflict_id, decision_ref="audit:d", decision_human_id=HUMAN,
                   actor_kind="human")
    assert rh.event_producer == "CF-4"
    r2 = _raise(m, entity="load:2")
    m.acknowledge(r2.conflict.conflict_id)
    m.escalate(r2.conflict.conflict_id)
    rr = m.resolve(r2.conflict.conflict_id, rule_id=REG_RULE)
    assert rr.event_producer == "CF-3"


def test_open_conflict_blocks_the_consequential_projection_gr10():
    """GR-10 — while OPEN the field is conflicting and BLOCKS. The native projection carries
    conflicting=True; resolving it clears the block."""
    conn = _conn()
    m = _machine(conn, registered_rules={REG_RULE})
    cid = _open(m, entity="load:4471", field="amount")
    assert m.get(cid).native_projection().conflicting
    m.resolve(cid, rule_id=REG_RULE)
    assert not m.get(cid).native_projection().conflicting        # resolution unfreezes


# ============================ concurrency, OCC, idempotency, replay ==============================

def test_occ_refuses_a_lost_update():
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    cid = r.conflict.conflict_id
    snap = m.get(cid)
    m.acknowledge(cid)
    with pytest.raises((StateConflict, GuardNotSatisfied)):
        m.acknowledge(cid, expected=snap)
    assert m.get(cid).state is CfState.OPEN


def test_competing_resolutions_serialize_one_wins():
    conn = _conn()
    m = _machine(conn, registered_rules={REG_RULE})
    cid = _open(m)
    snap = m.get(cid)
    wins = refused = 0
    for _ in range(4):
        try:
            m.resolve(cid, rule_id=REG_RULE, expected=snap)
            wins += 1
        except (StateConflict, GuardNotSatisfied):
            refused += 1
    assert wins == 1 and refused == 3
    assert m.get(cid).state is CfState.RESOLVED_BY_RULE


def test_redelivered_detection_is_a_no_op():
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    cid = r.conflict.conflict_id
    m.attach_party(cid, _rb("third", "RECONCILED", "x"))
    before = len(m.parties(cid))
    m.attach_party(cid, _rb("third", "RECONCILED", "x"))
    m.attach_party(cid, _rb("third", "RECONCILED", "x"))
    assert len(m.parties(cid)) == before


def test_replay_resolves_nothing_and_keeps_the_field_frozen():
    conn = _conn()
    m = _machine(conn)
    cid = _open(m, entity="e", field="f")
    m.attach_party(cid, _rb("p3", "RECONCILED", "x"))
    rebuilt = m.rebuild(cid)
    assert rebuilt.state is CfState.OPEN and rebuilt.frozen
    assert (rebuilt.resolutions, rebuilt.duplicate_conflicts, rebuilt.lost_parties,
            rebuilt.new_authority, rebuilt.external_effects) == (0, 0, 0, 0, 0)


def test_restart_preserves_the_open_conflict():
    conn = _conn()
    m = _machine(conn)
    cid = _open(m, entity="load:4471", field="delivery")
    path = conn.execute("PRAGMA database_list").fetchone()["file"]
    conn.close()
    conn2 = sqlite3.connect(path)
    conn2.row_factory = sqlite3.Row
    enable_and_verify_foreign_keys(conn2)
    m2 = M7Machine(conn2, tenant=TENANT)
    c = m2.get(cid)
    assert c is not None and c.is_open and m2.is_field_conflicting("load:4471", "delivery")


@pytest.mark.parametrize(
    "crash_point, expected",
    [("before-acknowledge", CfState.RAISED), ("after-escalate", CfState.ESCALATED)],
)
def test_a_crash_mid_workflow_recovers_to_the_canonical_state(crash_point, expected):
    """### A CRASH BETWEEN TRANSITIONS RECOVERS TO THE CANONICAL STATE, NEVER A TORN ONE (machine
    §36, GR-2). Every transition co-commits its state row and its event in one BEGIN IMMEDIATE, so a
    process death between two transitions leaves the LAST committed state — which is canonical by
    construction — and the field stays frozen while that state is open. A crash BEFORE the CF-2
    acknowledge recovers to RAISED (a RAISED conflict already blocks); a crash AFTER CF-5 recovers to
    ESCALATED. Neither is `unknown`, and neither silently advances or resolves."""
    conn = _conn()
    m = _machine(conn)
    if crash_point == "before-acknowledge":
        cid = _raise(m, entity="load:4471", field="delivery").conflict.conflict_id
    else:
        cid = _open(m, entity="load:4471", field="delivery")
        m.escalate(cid)
    assert m.get(cid).state is expected           # the durable state at the crash point
    path = conn.execute("PRAGMA database_list").fetchone()["file"]
    conn.close()                                  # process death — no acknowledge/resolve in flight

    conn2 = sqlite3.connect(path)
    conn2.row_factory = sqlite3.Row
    enable_and_verify_foreign_keys(conn2)
    m2 = M7Machine(conn2, tenant=TENANT)
    c = m2.get(cid)
    assert c is not None and c.state is expected  # recovered to the canonical state, not advanced
    assert c.is_open and m2.is_field_conflicting("load:4471", "delivery")   # still frozen
    rebuilt = m2.rebuild(cid)                      # full-history fold agrees, resolves nothing
    assert rebuilt.state is expected and rebuilt.frozen and rebuilt.resolutions == 0


# ============================ retention, reopening, expiry ======================================

def test_a_resolved_conflict_is_retained_and_a_delete_is_refused():
    conn = _conn()
    m = _machine(conn, registered_rules={REG_RULE})
    cid = _open(m)
    m.resolve(cid, rule_id=REG_RULE)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM conflicts WHERE tenant=? AND conflict_id=?", (TENANT, cid))
    conn.rollback()
    assert m.get(cid) is not None


def test_db_refuses_a_resolved_conflict_with_no_basis():
    """entity §16 — a RESOLVED_BY_RULE with no rule_id (or RESOLVED_BY_HUMAN with no decision_ref) is
    refused by the database CHECK, not only by the machine."""
    conn = _conn()
    _human(conn, human_id="h1")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO conflicts (tenant, conflict_id, entity_ref, field, kind, state, version, "
            "owner_id, created_at, updated_at) VALUES (?, 'x', 'e', 'f', 'SYSTEM_VS_SYSTEM', "
            "'RESOLVED_BY_RULE', 1, 'h1', 't', 't')", (TENANT,))
    conn.rollback()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO conflicts (tenant, conflict_id, entity_ref, field, kind, state, version, "
            "owner_id, rule_id, decision_ref, decision_human_id, decision_ref_kind, created_at, "
            "updated_at) VALUES (?, 'y', 'e', 'f', 'SYSTEM_VS_SYSTEM', 'RESOLVED_BY_RULE', 1, 'h1', "
            "'r', 'd', 'h1', 'audit_event', 't', 't')", (TENANT,))     # both bases refused
    conn.rollback()


def test_new_evidence_after_resolution_raises_a_new_conflict():
    conn = _conn()
    m = _machine(conn, registered_rules={REG_RULE})
    cid = _open(m, entity="load:4471", field="delivery")
    m.resolve(cid, rule_id=REG_RULE)
    r2 = _raise(m, entity="load:4471", field="delivery", parties=_two("x", "y"))
    assert not r2.coalesced and r2.conflict.conflict_id != cid
    assert m.get(r2.conflict.conflict_id).state is CfState.RAISED
    assert m.get(cid).state is CfState.RESOLVED_BY_RULE


def test_no_expired_or_cancelled_state_exists():
    """entity §26/§28, M7-AQ-3 — there is no sixth state, no EXPIRED and no CANCELLED."""
    assert set(CONFLICT_STATES) == {"RAISED", "OPEN", "ESCALATED", "RESOLVED_BY_RULE",
                                    "RESOLVED_BY_HUMAN"}
    assert "EXPIRED" not in CONFLICT_STATES and "CANCELLED" not in CONFLICT_STATES
    assert not any("Cancel" in n or "Expire" in n for n in PRODUCED_CONTRACTS)


# ============================ contracts, seams, ship-dark ========================================

def test_produces_exactly_the_five_registered_f7_contracts():
    assert PRODUCED_CONTRACTS == frozenset(
        {"ConflictRaised", "ConflictOpened", "ConflictPartyAttached", "ConflictEscalated",
         "ConflictResolved"})


def test_conflict_raised_has_three_registered_producers():
    assert set(CONFLICT_RAISED_PRODUCERS) == {"CF-1", "IB-6", "EF-4c"}
    assert "M7-AQ-1" in M7_AQ1_SEAM and "IB-6" in M7_AQ1_SEAM and "EF-4c" in M7_AQ1_SEAM


def test_six_kinds_are_closed():
    conn = _conn()
    m = _machine(conn)
    assert len(CONFLICT_KINDS) == 6
    with pytest.raises(MalformedConflict):
        _raise(m, kind="OWNER_VS_UNIVERSE")


def test_ships_dark_no_production_importer():
    """Nothing under src/freight_recon imports the conflict module; only its own probe does."""
    import ast
    src_dir = ROOT / "src" / "freight_recon"
    offenders = []
    for path in src_dir.rglob("*.py"):
        if path.name == "conflict.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "conflict" in node.module:
                if node.module.endswith("conflict") and "conflicts" not in node.module:
                    offenders.append(f"{path.name}: from {node.module}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.endswith(".conflict"):
                        offenders.append(f"{path.name}: import {alias.name}")
    assert offenders == [], offenders


def test_m7_does_not_import_m6_or_m3():
    src = (ROOT / "src" / "freight_recon" / "conflict.py").read_text(encoding="utf-8")
    # Prove the population before asserting over it: three `not in` claims are all vacuously true
    # against an empty or truncated read, and against a re-export shim left at this path after the
    # real M7 module moved elsewhere. Assert positively that this IS the M7 module and that its
    # sibling-import region - the exact region the negative claims scan - was actually read.
    assert "class M7Machine:" in src, "conflict.py is not the M7 module"
    assert "from .event_envelope import" in src, "conflict.py sibling-import region not read"
    assert "from .identity_binding_claim import" not in src
    assert "from .external_effect import" not in src
    assert "GateDecision(" not in src and "GateRegistry(" not in src


def test_no_m9_m10_m11_m12_tables_are_built():
    # M8 (Expectation), M9 (Exception), M10 (Compensation), M11 (Policy) and now M12 (Rule) LANDED as the
    # build checkpoints after M7, so `expectations`, `observation_coverage`, `exceptions`, `compensations`,
    # `policies` and `rules` are now canonical (rule 20 — each forward-looking assertion was true at the M7
    # landing and is corrected here rather than left to assert a table that now exists). M7's own machine
    # (conflict.py) is byte-unchanged and M12 does not import it — RU-3 names its M7 RULE_VS_RULE seam and
    # leaves it unwired, so M7 keeps ZERO importers. The remaining unbuilt neighbour is M13 (Brake).
    conn = _conn()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "rules" in tables                      # M12 landed
    src = (ROOT / "src" / "freight_recon" / "conflict.py").read_text(encoding="utf-8")
    import re
    assert not re.findall(r"\bRU-\d+", src)       # conflict.py carries no M12 transitions (byte-unchanged)


# ============================ schema / migration ================================================

def test_fresh_database_readiness_is_empty():
    conn = _conn()
    assert schema_readiness_problems(conn) == []
    assert phase6_conflicts_readiness_problems(conn) == []


def test_tenant_first_partition_gains_conflicts_and_conflict_parties():
    from freight_recon.migrations.phase6_conflicts import P6CF_TENANT_TABLES
    assert P6CF_TENANT_TABLES == ("conflicts", "conflict_parties")
    conn = _conn()
    for table in P6CF_TENANT_TABLES:
        pk = [r for r in conn.execute(f"PRAGMA table_info({table})") if r["pk"] > 0]
        assert pk and pk[0]["name"] == "tenant", table


def test_migrated_and_fresh_conflict_shape_are_identical():
    from fixtures.legacy_workspace import build_legacy_workspace
    from freight_recon.migrations.phase2_tenant_first import OwnerAssertion, migrate
    tmp = Path(tempfile.mkdtemp(prefix="p6m7-mig-"))
    legacy = tmp / "legacy.db"
    build_legacy_workspace(legacy)
    migrate(str(legacy), assertion=OwnerAssertion(
        actor_id="rasheed@neyma", tenant="acme-brokerage", scope="all legacy rows",
        operational_basis="sole workspace onboarded for Acme; verified against record",
        evidence_reference="docs/onboarding/acme.md"), dry_run=False)
    migrated = sqlite3.connect(legacy)
    migrated.row_factory = sqlite3.Row
    enable_and_verify_foreign_keys(migrated)
    assert phase6_conflicts_readiness_problems(migrated) == []
    fresh = _conn()

    def shape(conn, table):
        cols = [(r[1], (r[2] or "").upper(), bool(r[3])) for r in conn.execute(
            f"PRAGMA table_info({table})")]
        fks = sorted((r[2], r[3], r[4]) for r in conn.execute(f"PRAGMA foreign_key_list({table})"))
        return cols, fks
    assert shape(migrated, "conflicts") == shape(fresh, "conflicts")
    assert shape(migrated, "conflict_parties") == shape(fresh, "conflict_parties")


def test_unknown_conflict_is_tenant_scoped():
    conn = _conn()
    m = _machine(conn)
    with pytest.raises(UnknownConflict):
        m.require("conf-does-not-exist")
    assert m.get("conf-does-not-exist") is None
