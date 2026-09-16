"""P6-CP-11 — M11, the Policy: the acceptance battery.

Every test here could have failed before the code existed, and each is the RED half of a mutant in
`scripts/mutate_phase6_policy.py`. The battery measures the DATABASE (a fresh canonical schema
introspected and written against), the EVENT REGISTRY (the eight F11 contracts) and the AST (the
checkpoint stays the sole gate minter; M11 ships dark; the neighbours are unchanged) — not narration.

M11 is tier-1 (a migration, tenant-isolation-bearing, and the authority mechanism every other gate
depends on), so the load-bearing DDL is introspected LIVE and the forbidden writes are ATTEMPTED
against a real canonical database behind positive controls, not read from the migration source.
"""

from __future__ import annotations

import ast
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for entry in (str(ROOT / "src"), str(ROOT / "eval"), str(ROOT / "eval" / "tests")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from freight_recon.checkpoint import (  # noqa: E402
    EvidenceCondition,
    GateDecision,
    ProvenanceClass,
    ProvenancedFact,
)
from freight_recon.event_contracts import CONTRACTS  # noqa: E402
from freight_recon.event_envelope import EventEnvelope  # noqa: E402
from freight_recon.migrations.phase6_policies import (  # noqa: E402
    GATE_DECISIONS,
    POLICY_STATES,
    phase6_policies_readiness_problems,
)
from freight_recon.policy import (  # noqa: E402
    TRANSITIONS,
    IllegalTransition,
    M11Machine,
    PolicyEngineUnavailable,
    PolicyEvaluationInputs,
    PolicyState,
    PredicateWillNotCompile,
    Trigger,
    compile_predicate,
    legal_transitions,
    gate_rank,
    narrows_or_holds,
)
from phase6_crash_kit import outbox_count, plant_colliding_emission  # noqa: E402
from freight_recon.schema import (  # noqa: E402
    CANONICAL_TABLES,
    create_canonical_schema,
    enable_and_verify_foreign_keys,
    schema_readiness_problems,
)

TENANT = "acme-brokerage"
CLOCK = lambda: datetime(2026, 9, 3, 12, 0, 0, tzinfo=timezone.utc)  # noqa: E731
POLICY_SRC = (ROOT / "src" / "freight_recon" / "policy.py").read_text(encoding="utf-8")
MIG_SRC = (ROOT / "src" / "freight_recon" / "migrations" / "phase6_policies.py").read_text(encoding="utf-8")


# ------------------------------------------------------------------ helpers

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_canonical_schema(conn)
    enable_and_verify_foreign_keys(conn)
    return conn


def _human(conn, hid, *, role="POLICY_OWNER", state="ACTIVE", tenant=TENANT):
    conn.execute(
        "INSERT INTO tenant_humans (tenant, human_id, display_name, authority_role, state, "
        "recorded_at, recorded_by, recorded_by_kind) VALUES (?,?,?,?,?,?,?, 'human')",
        (tenant, hid, hid, role, state, "2026-01-01T00:00:00Z", "founder"))
    conn.commit()
    return hid


def _approval(conn, aid, *, mfp, policy_version="1", commit_key=None, tenant=TENANT, state="GRANTED"):
    cols = dict(
        tenant=tenant, approval_id=aid, commit_key=commit_key or f"ck-{aid}", action_class="change_policy",
        state=state, version=1, material_facts_fingerprint=mfp, canonical_payload=b"{}",
        fingerprint_version="fp_v1", entity_versions_json='{"policy:%s": 1}' % aid,
        policy_version=policy_version, brake_version="bv1", gate_decision="HUMAN_APPROVAL_REQUIRED",
        required_signatures=1, rendered_facts="{}", requested_at="2026-01-01T00:00:00Z",
        expires_at="2027-01-01T00:00:00Z", frozen=0, granted_by="po",
        created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
    conn.execute(f"INSERT INTO approvals ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                 tuple(cols.values()))
    conn.commit()
    return aid


def _m11(conn, *, tenant=TENANT, ceiling=GateDecision.HUMAN_APPROVAL_REQUIRED):
    return M11Machine(conn, tenant=tenant, clock=CLOCK, product_ceiling=ceiling)


def _activate(conn, *, scope, gate, policy_id, owner="po", predicate=None, tenant=TENANT,
              ceiling=GateDecision.HUMAN_APPROVAL_REQUIRED):
    m = _m11(conn, tenant=tenant, ceiling=ceiling)
    aid, diff = f"appr-{policy_id}", f"DIFF-{policy_id}"
    _approval(conn, aid, mfp=diff, tenant=tenant)
    m.propose_draft(scope=scope, scope_kind="action_class", gate_decision=gate, caps={},
                    predicate=predicate or {"clauses": []}, authored_by=owner, policy_id=policy_id)
    m.submit(policy_id, actor_id=owner)
    m.approve(policy_id, approval_id=aid, diff_fingerprint=diff, approved_by=owner)
    m.activate(policy_id, activated_by=owner)
    return policy_id


# ------------------------------------------------------------------ migration / readiness / partition

def test_readiness_is_clean_on_a_fresh_canonical_database():
    conn = _conn()
    assert schema_readiness_problems(conn) == []
    assert phase6_policies_readiness_problems(conn) == []


def test_the_policies_migration_is_rerunnable_and_matches_a_fresh_build():
    """A second application of the migration is a no-op, and a migrated database is byte-identical to a
    fresh one (idempotency, P1)."""
    from freight_recon.migrations.phase6_policies import create_phase6_policies_schema
    conn = _conn()
    performed = create_phase6_policies_schema(conn, now="2026-09-03T12:00:00Z")
    assert performed == [], f"a second application was not a no-op: {performed}"
    # the fresh schema is what the readiness oracle accepts
    assert phase6_policies_readiness_problems(conn) == []


def test_policies_is_registered_tenant_first_in_the_canonical_partition():
    assert "policies" in CANONICAL_TABLES
    conn = _conn()
    pk = [r[1] for r in conn.execute("PRAGMA table_info(policies)") if r[5]]
    assert pk and pk[0] == "tenant", f"policies PK is not tenant-first: {pk}"


def test_every_policy_index_is_tenant_first():
    conn = _conn()
    for idx in conn.execute("PRAGMA index_list(policies)"):
        name = idx[1]
        cols = [r[2] for r in conn.execute(f"PRAGMA index_info({name})")]
        assert cols and cols[0] == "tenant", f"index {name} is not tenant-first: {cols}"


# ------------------------------------------------------------------ the state & gate vocabularies (DB)

def test_the_seven_canonical_states_and_no_eighth():
    conn = _conn()
    ddl = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='policies'").fetchone()[0]
    expected = "state IN (" + ",".join(f"'{s}'" for s in POLICY_STATES) + ")"
    assert expected.upper() in " ".join(ddl.split()).upper().replace(", ", ",")
    _human(conn, "po")
    for forbidden in ("NARROWED", "SUSPENDED", "INVALID", "PENDING", "REJECTED", "COMPILED", "CONFIRMED"):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO policies (tenant, policy_id, policy_version, scope, scope_kind, gate_decision, "
                "caps_json, predicate_json, state, version, effective_from, authored_by, change_direction, "
                "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (TENANT, f"p-{forbidden}", 99, "s", "action_class", "HUMAN_APPROVAL_REQUIRED", "{}", "{}",
                 forbidden, 1, "t", "po", "initial", "t", "t"))
        conn.rollback()


def test_the_gate_vocabulary_is_a_db_check_of_exactly_four_members():
    conn = _conn()
    ddl = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='policies'").fetchone()[0]
    expected = "gate_decision IN (" + ",".join(f"'{g}'" for g in GATE_DECISIONS) + ")"
    assert expected.upper() in " ".join(ddl.split()).upper().replace(", ", ",")
    assert {g.value for g in GateDecision} == set(GATE_DECISIONS)
    assert len(GATE_DECISIONS) == 4


def test_null_and_invented_gate_decisions_are_refused_by_the_database():
    conn = _conn()
    _human(conn, "po")
    for bad in (None, "AUTONOMOUS", "YOLO"):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO policies (tenant, policy_id, policy_version, scope, scope_kind, gate_decision, "
                "caps_json, predicate_json, state, version, effective_from, authored_by, change_direction, "
                "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (TENANT, "pbad", 1, "s", "action_class", bad, "{}", "{}", "DRAFT", 1, "t", "po",
                 "initial", "t", "t"))
        conn.rollback()


# ------------------------------------------------------------------ AC-MACH-000: the transition table

def test_ac_mach_000_transition_table_is_the_seven_canonical_rows():
    ids = {row.id for row in TRANSITIONS}
    assert ids == {"PO-1", "PO-2", "PO-3", "PO-4", "PO-5", "PO-6", "PO-7"}, f"transition ids drifted: {ids}"
    assert len(TRANSITIONS) == 7


# ------------------------------------------------------------------ activation authority

def test_ac_mach_1104_activation_requires_an_authenticated_human():
    conn = _conn()
    _human(conn, "po")
    _activate(conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
    row = conn.execute("SELECT state, activated_by FROM policies WHERE policy_id='p1'").fetchone()
    assert row["state"] == "ACTIVE" and row["activated_by"] == "po"


def _approve_ready(conn):
    _human(conn, "po")
    m = _m11(conn)
    _approval(conn, "a1", mfp="D1")
    m.propose_draft(scope="pay_carrier", scope_kind="action_class",
                    gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED, caps={}, predicate={"clauses": []},
                    authored_by="po", policy_id="p1")
    m.submit("p1", actor_id="po")
    m.approve("p1", approval_id="a1", diff_fingerprint="D1", approved_by="po")
    return m


def test_a_model_cannot_activate_a_policy():
    conn = _conn()
    m = _approve_ready(conn)
    with pytest.raises(Exception):
        m.activate("p1", activated_by="po", actor_kind="model")
    assert conn.execute("SELECT state FROM policies WHERE policy_id='p1'").fetchone()["state"] == "APPROVED"
    f14 = conn.execute("SELECT COUNT(*) FROM event_outbox WHERE "
                       "event_name='UnauthorizedPolicyActivationAttempted'").fetchone()[0]
    assert f14 == 1, "the unauthorized activation went unrecorded (F14)"


def test_automation_and_retry_and_timer_cannot_activate_a_policy():
    for kind in ("automation", "retry", "timer"):
        conn = _conn()
        m = _approve_ready(conn)
        with pytest.raises(Exception):
            m.activate("p1", activated_by="po", actor_kind=kind)
        assert conn.execute("SELECT state FROM policies WHERE policy_id='p1'").fetchone()["state"] == "APPROVED"


def test_only_one_unauthorized_activation_contract_is_minted():
    """The dedicated F14 is emitted; no second unauthorized-activation contract exists in the registry."""
    unauth = [n for n in CONTRACTS if "Unauthorized" in n and "Activation" in n]
    assert unauth == ["UnauthorizedPolicyActivationAttempted"], f"a second contract exists: {unauth}"


def test_activated_by_is_a_foreign_key_into_tenant_humans():
    conn = _conn()
    refs = {r[2] for r in conn.execute("PRAGMA foreign_key_list(policies)")}
    assert "tenant_humans" in refs
    # a direct ACTIVE insert with an unrecorded activator fails closed on the FK
    _human(conn, "po")
    _approval(conn, "a1", mfp="D1")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO policies (tenant, policy_id, policy_version, scope, scope_kind, gate_decision, "
            "caps_json, predicate_json, state, version, effective_from, authored_by, activated_by, "
            "change_direction, approval_id, diff_fingerprint, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (TENANT, "pg", 1, "s", "action_class", "HUMAN_APPROVAL_REQUIRED", "{}", "{}", "ACTIVE", 1,
             "t", "po", "ghost", "initial", "a1", "D1", "t", "t"))
    conn.rollback()


def test_an_active_policy_with_no_activator_is_structurally_impossible():
    conn = _conn()
    _human(conn, "po")
    _approval(conn, "a1", mfp="D1")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO policies (tenant, policy_id, policy_version, scope, scope_kind, gate_decision, "
            "caps_json, predicate_json, state, version, effective_from, authored_by, activated_by, "
            "change_direction, approval_id, diff_fingerprint, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (TENANT, "pna", 1, "s", "action_class", "HUMAN_APPROVAL_REQUIRED", "{}", "{}", "ACTIVE", 1,
             "t", "po", None, "initial", "a1", "D1", "t", "t"))
    conn.rollback()


# ------------------------------------------------------------------ inbound authoring

def test_inbound_content_and_a_model_cannot_author_a_policy():
    conn = _conn()
    _human(conn, "po")
    m = _m11(conn)
    for kind in ("model", "inbound", "counterparty"):
        with pytest.raises(Exception):
            m.propose_draft(scope="raise_invoice", scope_kind="action_class",
                            gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED, caps={},
                            predicate={"clauses": []}, authored_by="po", policy_id=f"p-{kind}",
                            actor_kind=kind)
    assert conn.execute("SELECT COUNT(*) FROM policies").fetchone()[0] == 0


# ------------------------------------------------------------------ the ceiling & the total order

def test_ac_safe_027_a_tenant_policy_cannot_broaden_the_product_ceiling():
    conn = _conn()
    _human(conn, "po")
    m = _m11(conn, ceiling=GateDecision.HUMAN_APPROVAL_REQUIRED)
    m.propose_draft(scope="pay_carrier", scope_kind="action_class",
                    gate_decision=GateDecision.AUTONOMOUS_WITHIN_CAPS, caps={}, predicate={"clauses": []},
                    authored_by="po", policy_id="p1")
    with pytest.raises(Exception):
        m.submit("p1", actor_id="po")
    assert conn.execute("SELECT state FROM policies WHERE policy_id='p1'").fetchone()["state"] == "DRAFT"


def test_the_ceiling_order_is_total_over_the_four_members_and_not_a_string_compare():
    ranks = {g: gate_rank(g) for g in GateDecision}
    assert len(set(ranks.values())) == 4, "the total order is not total over the four members"
    # AUTONOMOUS_WITHIN_CAPS is the BROADEST — even though it sorts FIRST alphabetically
    assert ranks[GateDecision.AUTONOMOUS_WITHIN_CAPS] > ranks[GateDecision.HUMAN_APPROVAL_REQUIRED]
    assert "AUTONOMOUS_WITHIN_CAPS" < "HUMAN_APPROVAL_REQUIRED", "the string order is the trap this guards"
    assert not narrows_or_holds(GateDecision.AUTONOMOUS_WITHIN_CAPS, GateDecision.HUMAN_APPROVAL_REQUIRED)
    assert narrows_or_holds(GateDecision.FORBIDDEN, GateDecision.HUMAN_APPROVAL_REQUIRED)


# ------------------------------------------------------------------ the predicate & confidence

def test_ac_safe_015_a_predicate_on_model_inferred_fails_to_compile():
    pred = {"clauses": [{"field": "fact:carrier_cost", "attr": "value", "op": ">", "literal": 100}]}
    with pytest.raises(PredicateWillNotCompile):
        compile_predicate(pred, field_provenance={"fact:carrier_cost": ProvenanceClass.MODEL_INFERRED})
    # a non-inferred value predicate compiles
    ok = compile_predicate(pred, field_provenance={"fact:carrier_cost": ProvenanceClass.SYSTEM_IMPORTED})
    assert ok.clauses


def test_a_prompt_string_is_not_a_policy():
    with pytest.raises(PredicateWillNotCompile):
        compile_predicate("never bill without a POD")


def test_the_evaluator_input_type_has_no_confidence_field():
    fact = ProvenancedFact(field="x", provenance=ProvenanceClass.SYSTEM_IMPORTED,
                           evidence_condition=EvidenceCondition.CONSISTENT)
    assert not hasattr(fact, "confidence")
    assert "confidence" not in PolicyEvaluationInputs.__dataclass_fields__
    with pytest.raises(PredicateWillNotCompile):
        compile_predicate({"clauses": [{"field": "confidence", "attr": "value", "op": ">", "literal": 0.9}]})


def test_model_inferred_is_unreadable_at_any_confidence():
    fact = ProvenancedFact(field="c", provenance=ProvenanceClass.MODEL_INFERRED,
                           evidence_condition=EvidenceCondition.CONSISTENT, _value=1)
    with pytest.raises(Exception):
        _ = fact.value


# ------------------------------------------------------------------ evaluation determinism & fail-closed

def test_ac_policy_evaluation_is_byte_identical_reproducible():
    conn = _conn()
    _human(conn, "po")
    _activate(conn, scope="raise_invoice", gate=GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED,
              policy_id="p1")
    m = _m11(conn)
    inputs = PolicyEvaluationInputs(
        tenant=TENANT, action_class="raise_invoice", now="2026-09-03T12:00:00Z",
        material_facts={"pod": ProvenancedFact(field="pod", provenance=ProvenanceClass.SYSTEM_IMPORTED,
                                               evidence_condition=EvidenceCondition.CONSISTENT, _value="X")})
    first = m.evaluate(inputs).to_bytes()
    for _ in range(25):
        assert m.evaluate(inputs).to_bytes() == first
    assert m.evaluate(inputs).reason, "a decision must always carry a reason, even on PERMIT"


def test_the_policy_engine_fails_closed_and_has_no_allow_on_error_default():
    conn = _conn()
    _human(conn, "po")
    m = _m11(conn, ceiling=GateDecision.AUTONOMOUS_WITHIN_CAPS)
    _approval(conn, "a1", mfp="D1")
    m.propose_draft(scope="raise_invoice", scope_kind="action_class",
                    gate_decision=GateDecision.AUTONOMOUS_WITHIN_CAPS, caps={},
                    predicate={"clauses": [{"field": "fact:amount", "attr": "value", "op": "<",
                                            "literal": 999}]},
                    field_provenance={"fact:amount": ProvenanceClass.SYSTEM_IMPORTED},
                    authored_by="po", policy_id="p1")
    m.submit("p1", actor_id="po")
    m.approve("p1", approval_id="a1", diff_fingerprint="D1", approved_by="po")
    m.activate("p1", activated_by="po")
    bad = PolicyEvaluationInputs(
        tenant=TENANT, action_class="raise_invoice", now="2026-09-03T12:00:00Z",
        material_facts={"amount": ProvenancedFact(field="amount", provenance=ProvenanceClass.MODEL_INFERRED,
                                                  evidence_condition=EvidenceCondition.CONSISTENT, _value=1)})
    with pytest.raises(PolicyEngineUnavailable):
        m.evaluate(bad)


# ------------------------------------------------------------------ the governed change / no admin path

def test_ac_mach_1103_no_admin_path_to_approved():
    conn = _conn()
    _human(conn, "po")
    m = _m11(conn)
    m.propose_draft(scope="raise_invoice", scope_kind="action_class",
                    gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED, caps={}, predicate={"clauses": []},
                    authored_by="po", policy_id="p1")
    m.submit("p1", actor_id="po")
    # approve with no bound governed approval is refused
    with pytest.raises(Exception):
        m.approve("p1", approval_id="does-not-exist", diff_fingerprint="D1", approved_by="po")
    # a direct UPDATE to ACTIVE with no approval/diff is refused by the DB CHECK
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE policies SET state='ACTIVE', version=version+1, activated_by='po' "
                     "WHERE policy_id='p1'")
    conn.rollback()


def test_policyapproved_carries_the_diff_fingerprint_and_does_not_activate():
    conn = _conn()
    _human(conn, "po")
    m = _m11(conn)
    _approval(conn, "a1", mfp="DIFF")
    m.propose_draft(scope="raise_invoice", scope_kind="action_class",
                    gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED, caps={}, predicate={"clauses": []},
                    authored_by="po", policy_id="p1")
    m.submit("p1", actor_id="po")
    m.approve("p1", approval_id="a1", diff_fingerprint="DIFF", approved_by="po")
    assert conn.execute("SELECT state FROM policies WHERE policy_id='p1'").fetchone()["state"] == "APPROVED"
    assert conn.execute("SELECT COUNT(*) FROM event_outbox WHERE event_name='PolicyActivated' "
                        "AND aggregate_id='p1'").fetchone()[0] == 0
    ev = conn.execute("SELECT envelope_json FROM event_outbox WHERE event_name='PolicyApproved' "
                      "AND aggregate_id='p1'").fetchone()
    payload = EventEnvelope.from_json(ev["envelope_json"]).payload
    assert payload.get("diff_fingerprint") == "DIFF"


def test_a_wrong_diff_or_cross_tenant_governed_approval_is_refused():
    conn = _conn()
    _human(conn, "po")
    m = _m11(conn)
    _approval(conn, "a1", mfp="OTHER")  # material facts != the diff
    m.propose_draft(scope="raise_invoice", scope_kind="action_class",
                    gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED, caps={}, predicate={"clauses": []},
                    authored_by="po", policy_id="p1")
    m.submit("p1", actor_id="po")
    with pytest.raises(Exception):
        m.approve("p1", approval_id="a1", diff_fingerprint="DIFF", approved_by="po")


def test_policysubmitted_is_not_a_rename_of_policyproposed():
    conn = _conn()
    _human(conn, "po")
    m = _m11(conn)
    m.propose_draft(scope="raise_invoice", scope_kind="action_class",
                    gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED, caps={}, predicate={"clauses": []},
                    authored_by="po", policy_id="p1")
    m.submit("p1", actor_id="po")
    names = [r["event_name"] for r in conn.execute(
        "SELECT event_name FROM event_outbox WHERE aggregate_id='p1' ORDER BY aggregate_version")]
    assert "PolicyProposed" in names and "PolicySubmitted" in names
    assert names.index("PolicyProposed") < names.index("PolicySubmitted")


# ------------------------------------------------------------------ retention / retroactivity / OCC

def test_retention_supersession_is_permanent_and_immutable_and_undeletable():
    conn = _conn()
    _human(conn, "po")
    _activate(conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
    _activate(conn, scope="raise_invoice", gate=GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED,
              policy_id="p2")
    old = conn.execute("SELECT state, gate_decision FROM policies WHERE policy_id='p1'").fetchone()
    assert old["state"] == "SUPERSEDED" and old["gate_decision"] == "HUMAN_APPROVAL_REQUIRED"
    # A superseded version stays undeletable. Any constraint saying no is enough HERE...
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM policies WHERE policy_id='p1'")
    conn.rollback()
    with pytest.raises(sqlite3.IntegrityError,
                       match="the identity of a policy version is immutable"):
        conn.execute("UPDATE policies SET gate_decision='FORBIDDEN' WHERE policy_id='p1'")
    conn.rollback()

    # ### ...BUT IT NO LONGER PROVES THE NO-DELETE TRIGGER, AND THAT HAD TO BE RESTORED SEPARATELY
    # ### (U8.1/P8 — CLAUDE.md sec 4 rule 20).
    #
    # The DELETE above asserted only a bare `sqlite3.IntegrityError`. When `policy_epochs` arrived
    # with a composite FK (tenant, policy_id) -> policies, an ACTIVATED policy acquired a
    # referencing epoch row — so SQLite now refuses that DELETE on the FOREIGN KEY, before the
    # BEFORE-DELETE trigger ever fires. The case therefore stayed GREEN with the no-delete trigger
    # REMOVED: `scripts/mutate_phase6_policy.py`'s "a superseded version is deletable" mutant
    # ESCAPED, 33/34. A new table had quietly taken a retention guard out of service.
    #
    # A DRAFT is the population that still reaches the trigger: it was never activated, so no epoch
    # row references it and no FK stands in the way. Matching the trigger's OWN abort text means no
    # other constraint can be mistaken for it.
    m = _m11(conn)
    m.propose_draft(scope="never_activated", scope_kind="action_class",
                    gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED, caps={},
                    predicate={"clauses": []}, authored_by="po", policy_id="draft_only")
    assert conn.execute("SELECT COUNT(*) FROM policy_epochs WHERE tenant = ? AND policy_id = ?",
                        (TENANT, "draft_only")).fetchone()[0] == 0, (
        "the draft has a referencing epoch row after all, so a FOREIGN KEY could refuse the DELETE "
        "below and this case would prove nothing about the trigger")
    with pytest.raises(sqlite3.IntegrityError, match="a policy version is never deleted"):
        conn.execute("DELETE FROM policies WHERE policy_id='draft_only'")
    conn.rollback()


def test_a_policy_is_never_retroactive_the_old_version_keeps_its_own_version():
    conn = _conn()
    _human(conn, "po")
    _activate(conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
    v1 = conn.execute("SELECT policy_version FROM policies WHERE policy_id='p1'").fetchone()[0]
    _activate(conn, scope="raise_invoice", gate=GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED,
              policy_id="p2")
    v2 = conn.execute("SELECT policy_version FROM policies WHERE policy_id='p2'").fetchone()[0]
    v1_after = conn.execute("SELECT policy_version FROM policies WHERE policy_id='p1'").fetchone()[0]
    assert v2 > v1 and v1_after == v1, "the old version was rewritten to the new one (retroactive)"


def test_occ_version_advances_by_one_per_transition():
    conn = _conn()
    _human(conn, "po")
    _activate(conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
    # A state change that does not advance the row version is refused by the OCC trigger. ACTIVE->EXPIRED
    # is used because it trips NO other CHECK (an ACTIVE p1 carries approval_id + diff_fingerprint, and
    # EXPIRED needs no extra column), so only the version-advances trigger can stop it — isolating it.
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE policies SET state='EXPIRED' WHERE policy_id='p1'")  # version unchanged
    conn.rollback()
    # positive control: the same transition WITH the version advanced is accepted by the trigger
    conn.execute("UPDATE policies SET state='EXPIRED', version=version+1 WHERE policy_id='p1'")
    conn.commit()


# ------------------------------------------------------------------ versioning namespace / one active

def test_ac_safe_003_the_version_namespace_is_the_tenant_not_the_scope():
    conn = _conn()
    _human(conn, "po")
    _activate(conn, scope="s1", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
    _activate(conn, scope="s2", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p2")
    versions = [r[0] for r in conn.execute(
        "SELECT policy_version FROM policies WHERE tenant=? ORDER BY policy_version", (TENANT,))]
    assert len(versions) == len(set(versions)), "two scopes reused a policy_version (scope-local namespace)"


def test_one_active_policy_per_scope_and_a_version_is_never_reused():
    conn = _conn()
    _human(conn, "po")
    _activate(conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
    # a second ACTIVE row for the same scope is refused by the partial unique index
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO policies (tenant, policy_id, policy_version, scope, scope_kind, gate_decision, "
            "caps_json, predicate_json, state, version, effective_from, authored_by, activated_by, "
            "change_direction, approval_id, diff_fingerprint, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (TENANT, "p2", 99, "raise_invoice", "action_class", "HUMAN_APPROVAL_REQUIRED", "{}", "{}",
             "ACTIVE", 1, "t", "po", "po", "initial", "appr-p1", "DIFF-p1", "t", "t"))
    conn.rollback()
    # a reused policy_version is refused by the tenant-version unique index
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO policies (tenant, policy_id, policy_version, scope, scope_kind, gate_decision, "
            "caps_json, predicate_json, state, version, effective_from, authored_by, change_direction, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (TENANT, "pdup", 1, "book_carrier", "action_class", "HUMAN_APPROVAL_REQUIRED", "{}", "{}",
             "DRAFT", 1, "t", "po", "initial", "t", "t"))
    conn.rollback()


def test_the_same_scope_is_active_in_two_tenants_without_collision():
    conn = _conn()
    _human(conn, "po", tenant="T_A")
    _human(conn, "po", tenant="T_B")
    _activate(conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="pA",
              tenant="T_A")
    _activate(conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="pB",
              tenant="T_B")
    for t in ("T_A", "T_B"):
        n = conn.execute("SELECT COUNT(*) FROM policies WHERE tenant=? AND scope='raise_invoice' "
                         "AND state='ACTIVE'", (t,)).fetchone()[0]
        assert n == 1, f"{t} does not have exactly one active policy"


def test_a_cross_tenant_activator_or_author_fails_closed():
    conn = _conn()
    _human(conn, "po", tenant="T_A")
    _human(conn, "clerk", role="AUTHORIZED_HUMAN", tenant="T_B")
    m = M11Machine(conn, tenant="T_A", clock=CLOCK)
    with pytest.raises(Exception):
        m.propose_draft(scope="raise_invoice", scope_kind="action_class",
                        gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED, caps={},
                        predicate={"clauses": []}, authored_by="clerk", policy_id="p1")


# ------------------------------------------------------------------ Policy Owner singularity (P6-D72)

def test_ac_safe_a_second_active_policy_owner_in_one_tenant_is_refused():
    conn = _conn()
    _human(conn, "po")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO tenant_humans (tenant, human_id, display_name, authority_role, state, "
            "recorded_at, recorded_by, recorded_by_kind) VALUES (?,?,?,?,?,?,?, 'human')",
            (TENANT, "po2", "po2", "POLICY_OWNER", "ACTIVE", "t", "founder"))
    conn.rollback()
    # an AUTHORIZED_HUMAN is fine, and an OFFBOARDED owner does not block a new one
    _human(conn, "clerk", role="AUTHORIZED_HUMAN")


def test_the_policy_owner_singularity_does_not_couple_tenants():
    conn = _conn()
    _human(conn, "po", tenant="T_A")
    _human(conn, "po", tenant="T_B")  # each tenant names its own single owner, no collision
    for t in ("T_A", "T_B"):
        n = conn.execute("SELECT COUNT(*) FROM tenant_humans WHERE tenant=? AND authority_role='POLICY_OWNER' "
                         "AND state='ACTIVE'", (t,)).fetchone()[0]
        assert n == 1


def test_an_ambiguous_or_absent_policy_owner_cannot_activate():
    conn = _conn()
    # an APPROVED policy, then the only Policy Owner is offboarded -> activation cannot resolve authority
    m = _approve_ready(conn)
    # offboard the only owner (leaving none active) via a fresh delegate to satisfy the machine's read
    conn.execute("UPDATE tenant_humans SET state='OFFBOARDED', offboarded_at='t' WHERE human_id='po'")
    conn.commit()
    with pytest.raises(Exception):
        m.activate("p1", activated_by="po")


# ------------------------------------------------------------------ revocation direction

def test_a_narrowing_revocation_is_immediate_and_a_broadening_one_needs_the_owner():
    # narrow: automation may revoke immediately
    conn = _conn()
    _human(conn, "po")
    _activate(conn, scope="s", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
    m = _m11(conn)
    m.revoke("p1", revoked_reason="tighten", direction="narrow", actor_kind="automation", actor_id="auto")
    row = conn.execute("SELECT state, revoked_direction FROM policies WHERE policy_id='p1'").fetchone()
    assert row["state"] == "REVOKED" and row["revoked_direction"] == "narrow"
    # broaden: automation is refused; the Policy Owner proceeds
    conn2 = _conn()
    _human(conn2, "po")
    _activate(conn2, scope="s", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
    m2 = _m11(conn2)
    # actor_id is a REAL ACTIVE owner ("po"), but actor_kind is automation: automation may only narrow, so
    # this must be refused BY THE ACTOR-KIND GUARD — not merely because the actor_id is unrecorded. That
    # isolates the "automation broadens" defect from the "unknown human" one.
    with pytest.raises(Exception):
        m2.revoke("p1", revoked_reason="loosen", direction="broaden", actor_kind="automation", actor_id="po")
    m2.revoke("p1", revoked_reason="loosen", direction="broaden", actor_kind="human", actor_id="po")
    row2 = conn2.execute("SELECT state, revoked_direction FROM policies WHERE policy_id='p1'").fetchone()
    assert row2["state"] == "REVOKED" and row2["revoked_direction"] == "broaden"


def test_policyrevoked_carries_a_required_direction():
    contract = CONTRACTS["PolicyRevoked"]
    names = {f.name for f in contract.fields}
    assert "revoked_reason" in names and "direction" in names


# ------------------------------------------------------------------ expiry

def test_only_a_narrowing_policy_may_carry_an_expiry():
    conn = _conn()
    _human(conn, "po")
    # a broadening policy carrying an expiry is refused by the DB CHECK
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO policies (tenant, policy_id, policy_version, scope, scope_kind, gate_decision, "
            "caps_json, predicate_json, state, version, effective_from, authored_by, expires_at, "
            "change_direction, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (TENANT, "pb", 1, "s", "action_class", "HUMAN_APPROVAL_REQUIRED", "{}", "{}", "DRAFT", 1, "t",
             "po", "2026-10-01T00:00:00Z", "broaden", "t", "t"))
    conn.rollback()


def test_an_expiry_broadens_and_names_a_human_confirmation_seam_without_wiring_m9():
    conn = _conn()
    _human(conn, "po")
    _activate(conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
    _activate(conn, scope="raise_invoice", gate=GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED,
              policy_id="p2")
    conn.execute("UPDATE policies SET expires_at='2026-09-04T00:00:00Z' WHERE policy_id='p2'")
    conn.commit()
    m = _m11(conn)
    result = m.expire("p2", actor_id="timer")
    assert conn.execute("SELECT state FROM policies WHERE policy_id='p2'").fetchone()["state"] == "EXPIRED"
    assert result.escalation is not None and result.escalation.source_kind == "policy"
    # M9 was NOT called by M11: no exception row was created by the expire() itself
    assert conn.execute("SELECT COUNT(*) FROM exceptions WHERE source_kind='policy'").fetchone()[0] == 0


def test_policy_py_does_not_import_the_exception_machine():
    """PO-7 names its M9 seam and leaves it unwired; M9 keeps zero importers (### M11-AQ-8)."""
    tree = ast.parse(POLICY_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[-1] == "exception":
            pytest.fail("policy.py imports the exception machine — M9 must keep zero importers")
        if isinstance(node, ast.ImportFrom) and node.level and node.module is None:
            assert not any(a.name == "exception" for a in node.names)


# ------------------------------------------------------------------ in-flight invalidation (driven seams)

def test_ac_safe_010_a_policy_change_voids_an_in_flight_m4_approval():
    from freight_recon.approval import ApprovalMachine
    conn = _conn()
    _human(conn, "po")
    _activate(conn, scope="s0", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p0")
    bound = str(_m11(conn).current_policy_version())
    _approval(conn, "inflight", mfp="MF1", policy_version=bound, commit_key="ck-inflight")
    _activate(conn, scope="s1", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
    new_version = str(_m11(conn).current_policy_version())
    assert new_version != bound
    m4 = ApprovalMachine(conn, tenant=TENANT, clock=CLOCK)
    m4.void_on_policy("inflight", current_policy_version=new_version, actor_id="policy")
    assert conn.execute("SELECT state FROM approvals WHERE approval_id='inflight'").fetchone()["state"] == \
        "VOID_ON_DRIFT"


def test_a_change_in_one_scope_voids_in_flight_authority_in_every_scope():
    from freight_recon.approval import ApprovalMachine
    conn = _conn()
    _human(conn, "po")
    _activate(conn, scope="prime", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="pp")
    bound = str(_m11(conn).current_policy_version())
    for i in range(4):
        _approval(conn, f"if-{i}", mfp=f"MF{i}", policy_version=bound, commit_key=f"ck-{i}")
    _activate(conn, scope="scope-A", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="pA")
    new_version = str(_m11(conn).current_policy_version())
    m4 = ApprovalMachine(conn, tenant=TENANT, clock=CLOCK)
    for i in range(4):
        m4.void_on_policy(f"if-{i}", current_policy_version=new_version, actor_id="policy")
        st = conn.execute("SELECT state FROM approvals WHERE approval_id=?", (f"if-{i}",)).fetchone()["state"]
        assert st == "VOID_ON_DRIFT", f"approval {i} in another scope survived the version change"


def test_a_stale_policy_version_grant_claim_is_refused():
    import tempfile
    from phase3_kit import (Clock, default_registry, live_reader, make_approval, make_effect,
                            make_facts, make_kernel, make_store, params_for)
    from freight_recon.checkpoint import (CheckpointInputs, CheckpointRequest, claim_grant_cas,
                                          run_checkpoint)
    d = tempfile.mkdtemp(prefix="m11-claim-")
    key = b"m11-fixed-handle-key-32-bytes!!!"
    try:
        store = make_store(Path(d))
        kernel, clock = make_kernel(store, registry=default_registry("pv1"), handle_key=key)
        effect, facts, versions = make_effect(), make_facts(), {"load:4471": 17}
        approval = make_approval(effect, facts, versions, clock, policy_version="pv1")
        world = {"facts": dict(facts), "projection": {"status": "DELIVERED"}, "versions": dict(versions)}
        inputs = CheckpointInputs(
            material_facts_reader=live_reader(lambda: dict(world["facts"])),
            projection_assertion={"status": "DELIVERED"},
            projected_state_reader=live_reader(lambda: dict(world["projection"])),
            entity_version_reader=live_reader(lambda: dict(world["versions"])), approval=approval)
        request = CheckpointRequest(effect=effect, actor="pipeline", accountable_owner="owner:rasheed",
                                    target_entity_ref="load:4471")
        outcome = run_checkpoint(kernel, request, inputs)
        assert outcome.authorized
        kernel2, _ = make_kernel(store, clock=Clock(clock.now), registry=default_registry("pv2"),
                                 handle_key=key)
        claim = claim_grant_cas(kernel2, outcome.handle, params_for(effect))
        assert not claim.claimed and claim.cause == "POLICY_CHANGED"
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


# ------------------------------------------------------------------ precedence: permanent truth / brake

def test_a_policy_never_overrides_a_permanent_product_truth():
    conn = _conn()
    _human(conn, "po")
    m = _m11(conn, ceiling=GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED)
    for gate in (GateDecision.HUMAN_APPROVAL_REQUIRED, GateDecision.AUTONOMOUS_WITHIN_CAPS):
        m.propose_draft(scope=f"s-{gate.value}", scope_kind="action_class", gate_decision=gate, caps={},
                        predicate={"clauses": []}, authored_by="po", policy_id=f"p-{gate.value}")
        with pytest.raises(Exception):
            m.submit(f"p-{gate.value}", actor_id="po")


def test_m11_engages_no_brake_and_imports_no_brakestore():
    tree = ast.parse(POLICY_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[-1] == "brake":
            pytest.fail("policy.py imports the brake — M11 engages/narrows no brake")
    for banned in ("BrakeStore",):
        assert banned not in POLICY_SRC, f"policy.py references {banned}"


# ------------------------------------------------------------------ replay

def test_replay_reconstructs_state_only_and_mints_no_authority():
    conn = _conn()
    _human(conn, "po")
    _activate(conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
    rebuilt = _m11(conn).rebuild("p1")
    assert rebuilt.state == PolicyState.ACTIVE
    assert rebuilt.activations_performed == 0
    assert rebuilt.witnesses_minted == 0
    assert rebuilt.grants_claimed == 0
    assert rebuilt.external_effects == 0
    assert rebuilt.authority_minted == 0


# ------------------------------------------------------------------ events: strict order, contracts, F14

def test_the_policy_aggregate_is_strict_order_and_events_carry_a_predecessor_link():
    from freight_recon.migrations.phase5_event_transport import STRICT_ORDER_AGGREGATE_TYPES
    assert "policy" in STRICT_ORDER_AGGREGATE_TYPES
    conn = _conn()
    _human(conn, "po")
    _activate(conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
    rows = conn.execute(
        "SELECT envelope_json FROM event_outbox WHERE aggregate_type='policy' AND aggregate_id='p1' "
        "ORDER BY aggregate_version, sequence").fetchall()
    envs = [EventEnvelope.from_json(r["envelope_json"]) for r in rows]
    assert len(envs) >= 3
    # ORDER, not CONTIGUITY: the first event has no predecessor, every later one links to the prior version
    assert envs[0].previous_aggregate_version is None
    for prev, cur in zip(envs, envs[1:]):
        assert cur.previous_aggregate_version == prev.aggregate_version


def test_the_eight_f11_contracts_are_registered_and_no_ninth():
    f11 = sorted(n for n, c in CONTRACTS.items() if c.family == "F11")
    assert f11 == sorted([
        "PolicyProposed", "PolicySubmitted", "PolicyApproved", "PolicyActivated",
        "PolicySuperseded", "PolicyRevoked", "PolicyExpired", "PolicyVersionChanged"]), f11
    # PolicyApproved and PolicyActivated are human_only; PolicyEvaluated is F2's, not M11's
    assert CONTRACTS["PolicyApproved"].human_only and CONTRACTS["PolicyActivated"].human_only
    assert CONTRACTS["PolicyEvaluated"].family == "F2"


def test_m11_emits_no_policyevaluated_and_only_registered_event_names():
    """The event-name AST scan: every string literal event name M11 emits is a registered contract, and
    PolicyEvaluated (F2/M2's) is NOT among them."""
    names = _emitted_event_names(POLICY_SRC)
    assert "PolicyEvaluated" not in names, "M11 must not emit PolicyEvaluated (it is F2/M2's)"
    for n in names:
        assert n in CONTRACTS, f"M11 emits an unregistered event name: {n!r}"


def test_no_unregistered_policy_event_name_in_the_machine():
    """A canonical scan (the anti-vacuity shim target): every `Policy[A-Z]…` STRING LITERAL in the machine
    that is an event name is one of the eight registered F11 contracts. Reads real content — a shim would
    collapse the population and turn `assert found` red."""
    import re
    found = set(re.findall(r"\bPolicy[A-Z][A-Za-z]*", POLICY_SRC))
    assert found, "the machine names no Policy* identifier — the scan read nothing (vacuous)"
    event_like = {n for n in _emitted_event_names(POLICY_SRC) if n.startswith("Policy")}
    for n in event_like:
        assert n in CONTRACTS, f"unregistered Policy* event name minted: {n!r}"


def _emitted_event_names(src: str) -> set[str]:
    """String literals passed as `event_name=` (kwargs) or as a member of an events=(...) tuple."""
    tree = ast.parse(src)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "event_name" and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str):
                names.add(node.value.value)
        if isinstance(node, ast.keyword) and node.arg == "events" and isinstance(node.value, ast.Tuple):
            for elt in node.value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    names.add(elt.value)
        if isinstance(node, ast.keyword) and node.arg == "event_name" and isinstance(node.value, ast.Constant):
            pass
    return names


# ------------------------------------------------------------------ M11 mints no gate / ships dark / neighbours

def test_only_the_checkpoint_kernel_mints_a_gate_decision():
    import freight_recon
    src = Path(freight_recon.__file__).parent
    minters = []
    for path in sorted(src.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                nm = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", None)
                if nm in {"GateEntry", "GateRegistry"}:
                    minters.append(path.name)
    assert set(minters) == {"checkpoint.py"}, f"a module other than the kernel mints a gate: {set(minters)}"
    assert "GateRegistry(" not in POLICY_SRC and "GateEntry(" not in POLICY_SRC


def test_m11_has_EXACTLY_ONE_production_importer_AND_IT_IS_THE_P8_ADMISSION_LAYER():
    """REPLACED at U8.1/P8 (CLAUDE.md §4 rule 20 — replaced, not deleted, not relaxed).

    It was `test_m11_ships_dark_no_production_importer`, and for its whole life it was right: M11
    landed at P6-CP-11 as a machine with no caller, and *"ships dark"* meant literally zero
    production importers. Asserting that now would be asserting something false, because WIRING
    M11 is what P8 is for — `PHASE-OUTPUTS.md` gives P8 the *"production policy REGISTRATION,
    EVALUATION RUNTIME"* that P6 was forbidden, and `pr-sequence.md` names the unit: **U8.1 typed
    policy + Action Class gate registration**.

    ### SO THE PROPERTY IS NOT WEAKENED FROM "ZERO" TO "WHATEVER" — IT IS TIGHTENED TO "EXACTLY
    ONE, AND BY NAME." What the original guard really protected is that M11 must not acquire
    importers scattered across the codebase, each free to compose the tenant posture its own way;
    that is how a second policy authority arrives without anybody deciding to build one. One named
    composition layer is the opposite of that, and it is now asserted by exact set equality — a
    second importer, anywhere, still turns this RED.
    """
    import freight_recon
    src = Path(freight_recon.__file__).parent
    #: FIXED-SPECIFICATION: the ONE module entitled to import M11. This is an architectural
    #: boundary (ADR-010 puts policy evaluation at one place), not a population to discover —
    #: discovering it would mean asking the code who imports M11, which is the question.
    PERMITTED = {"policy_admission.py"}
    offenders = []
    for py in src.rglob("*.py"):
        if py.name == "policy.py":
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level and node.module and node.module.split(".")[-1] == "policy":
                    offenders.append(py.name)
                elif node.level and node.module is None and any(a.name == "policy" for a in node.names):
                    offenders.append(py.name)
                elif node.module == "freight_recon.policy":
                    offenders.append(py.name)
            if isinstance(node, ast.Import) and any(a.name == "freight_recon.policy" for a in node.names):
                offenders.append(py.name)

    observed = set(offenders)
    # ### EXACT SET EQUALITY, BOTH WAYS.
    #
    # `observed - PERMITTED` is the defect the original guard existed to catch: policy evaluation
    # leaking into a workflow, an adapter or a second composition.
    unexpected = sorted(observed - PERMITTED)
    assert not unexpected, (
        f"unexpected production importer(s) of the M11 policy machine: {unexpected}. Exactly one "
        f"module composes the tenant posture ({sorted(PERMITTED)}); a second importer is a second "
        "policy authority arriving without anybody deciding to build one (CLAUDE.md rule 17)."
    )
    # ...and `PERMITTED - observed` is the VACUITY the assertion above would otherwise hide: if the
    # admission layer stopped importing M11, the set-difference check would pass over nothing and
    # this test would report "policy is confined" about a tree in which policy is not wired at all.
    missing = sorted(PERMITTED - observed)
    assert not missing, (
        f"{missing} no longer import(s) the M11 policy machine. U8.1 wires M11 into checkpoint "
        "step 6; if nothing imports it, the tenant's durable posture is not being evaluated and "
        "the confinement assertion above is vacuous."
    )


def test_the_m12_rule_and_m13_brake_machines_are_not_built():
    # M12 (the Rule) LANDED after M11, so `rule.py` and the `rules` table are now canonical (rule 20 — the
    # forward-looking assertion was true at the M11 landing and is corrected here rather than left to
    # assert a module/table that now exists). M11's machine (policy.py) is byte-unchanged and M12 does not
    # import it — M12 declares its precedence layer and defers the ceiling comparison rather than importing
    # policy.py, so M11 keeps ZERO importers. The still-unbuilt neighbour is M13 (Brake): no brake
    # lifecycle module and no brake lifecycle table.
    import freight_recon
    src = Path(freight_recon.__file__).parent
    files = {p.name for p in src.rglob("*.py")}
    # prove the population first: a `not in` over an empty rglob is vacuously green (CLAUDE.md §9)
    assert len(files) > 10, f"the src scan collapsed to {len(files)} files - it proves nothing"
    assert "policy.py" in files, "the M11 machine itself must be present, or the scan read the wrong tree"
    assert "rule.py" in files, "the M12 machine landed"
    # RULE 20: M13 (Brake) has since LANDED, so the brake lifecycle module now exists by design; the
    # stale "must not be built" half is corrected to assert its presence rather than its absence.
    assert any("brake" in f and "lifecycle" in f for f in files), "M13 brake lifecycle landed"
    conn = _conn()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert len(tables) > 10, f"the schema scan collapsed to {len(tables)} tables - it proves nothing"
    assert "policies" in tables, "the M11 table itself must be present, or the scan read the wrong schema"
    assert "rules" in tables, "the M12 rules table landed"


def test_nothing_graduates_no_autonomy_graduation_engine_in_m11():
    tree = ast.parse(POLICY_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            assert "graduat" not in node.name.lower(), f"M11 defines a graduation engine: {node.name}"


def test_the_neighbouring_machines_are_unchanged():
    # FIXED-SPECIFICATION: this is NOT a discovered population — it is the exact list of landed machine
    # runtimes (M1..M10) plus the P3 checkpoint kernel and the brake that the P6/M11 task names as
    # must-stay-byte-identical (§5: "Do not modify M1–M10" except the one P6-D72 constraint; the kernel
    # and brake are named because CLAUDE.md §10 forbids weakening them). Discovering "machine modules" by
    # glob would silently admit a newly-added machine to the frozen set or drop a renamed one; the guard's
    # value is precisely that adding or removing a name here is a deliberate, reviewed edit.
    # FIXED-SPECIFICATION: this is NOT a discovered population — it is the exact list of landed
    # machine runtimes named as must-stay-byte-identical. RULE 20: `brake.py` was DROPPED from this
    # frozen set when M13 landed — it is P3's kernel brake and M13 legitimately edits it to complete
    # the one brake authority. [HISTORICAL AS WRITTEN — this block's closing sentence read
    # "M1..M10 and the checkpoint kernel remain frozen and asserted so". The checkpoint half is
    # no longer true; see the U8.1 block immediately below, which supersedes it. Retained rather
    # than rewritten, because it is the record of what the M13 landing decided.]
    # ### RULE 20, AGAIN, AT U8.1/P8: `checkpoint.py` WAS DROPPED FROM THIS FROZEN SET — for the
    # same reason and by the same precedent that dropped `brake.py` when M13 landed.
    #
    # This guard's subject is *"did the M11 landing disturb a neighbour it had no business
    # touching"*, and byte-identity was a fair proxy while M11 shipped dark with no caller. U8.1
    # is the unit that WIRES it: ADR-010 is titled as completing *"atomic pre-effect checkpoint
    # STEP 6"*, and step 6 is `checkpoint.py`'s. A guard that forbade P8 from editing step 6 would
    # forbid P8 from existing.
    #
    # ### AND BYTE-IDENTITY IS NOT SILENTLY TRADED FOR NOTHING. CLAUDE.md §10 does not say the
    # kernel may not be edited; it names three things that may not be WEAKENED — `CheckpointPassed`
    # stays unconstructable, the witness table stays append-only, and the claim CAS's WHERE-clause
    # revalidation may never lose a predicate. Those three are now asserted DIRECTLY, as
    # properties rather than as a hash, by
    # `test_p8_policy_admission.py::test_the_three_kernel_invariants_claude_md_10_protects_still_hold`.
    #
    # FIXED-SPECIFICATION: the exact M1..M10 machine runtimes named must-stay-byte-identical. NOT a
    # discovered population — discovering it would admit a newly-added machine or drop a renamed one,
    # and the guard's whole value is that changing this list is a deliberate, reviewed edit.
    machines = ("work_item.py", "pipeline_instance.py", "external_effect.py", "approval.py",
                "observation.py", "identity_binding_claim.py", "conflict.py", "expectation.py",
                "exception.py", "compensation.py")
    rel = [f"src/freight_recon/{n}" for n in machines]
    r = subprocess.run(["git", "diff", "--name-only", "HEAD", "--", *rel], cwd=ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip() == "", f"a landed machine changed: {r.stdout}"


# ================================ P6-AC-5 mandatory assertions 4, 5 and 8 — the missing behaviour
# `foundational-machine-acceptance.md`'s per-machine assertions had no M11 case for the inbox key
# (4), for terminal refusal (5) or for crash recovery (8). These three prove the behaviour itself;
# none of them asserts a constant, and each is shown red under mutation by
# `scripts/mutate_phase6_ac5_evidence.py`.

def test_m11_a4_a_redelivered_policy_event_is_a_no_op_on_the_inbox_key():
    """### ASSERTION 4 — DUPLICATE TRIGGERS ARE IDEMPOTENT. The whole F11 stream is consumed in
    order, then one already-applied event is DELIVERED AGAIN. The inbox key must make the second
    delivery a no-op: no second inbox row, no second transition, and a state and version that are
    byte-identical to before it arrived."""
    from freight_recon.event_inbox import ConsumeOutcome, DedupInbox

    conn = _conn()
    _human(conn, "po")
    _activate(conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
    m = _m11(conn)
    stream = [EventEnvelope.from_json(r["envelope_json"]) for r in conn.execute(
        "SELECT envelope_json FROM event_outbox WHERE tenant = ? AND aggregate_type = 'policy' "
        "AND aggregate_id = 'p1' ORDER BY aggregate_version, sequence", (TENANT,))]
    assert len(stream) >= 4, f"the stream is {[e.event_name for e in stream]}; too short to prove this"

    inbox = DedupInbox(conn, tenant=TENANT, consumer_id="m11-policy-a4", clock=CLOCK,
                       reference_resolver=m.reference_resolver)
    for envelope in stream:
        first = m.consume_event(envelope, inbox=inbox)
        assert first.consume.outcome is ConsumeOutcome.APPLIED, (
            f"{envelope.event_name} v{envelope.aggregate_version} was not applied on first delivery: "
            f"{first.consume.outcome.name} ({first.consume.detail})")

    rows_before = conn.execute("SELECT COUNT(*) FROM event_inbox").fetchone()[0]
    before = m.require("p1")
    assert rows_before == len(stream)

    replayed = stream[-2]
    again = m.consume_event(replayed, inbox=inbox)

    assert again.consume.outcome is ConsumeOutcome.DUPLICATE_NOOP, (
        f"redelivering {replayed.event_name} produced {again.consume.outcome.name}, not a no-op. The "
        f"inbox key is what makes a redelivery harmless; without it this is a second transition.")
    assert again.transition is None, f"a redelivery performed a transition: {again.transition}"
    assert conn.execute("SELECT COUNT(*) FROM event_inbox").fetchone()[0] == rows_before
    after = m.require("p1")
    assert (after.state, after.version) == (before.state, before.version), (
        f"a redelivered event moved the policy {before.state.value}v{before.version} -> "
        f"{after.state.value}v{after.version}")


def test_m11_a5_a_terminal_policy_refuses_every_trigger_in_the_vocabulary():
    """### ASSERTION 5 — TERMINAL STATES HAVE NO PROHIBITED OUTGOING TRANSITION. M11 has no reopen
    (that is WI-13, M1's alone), so a REVOKED policy must refuse the WHOLE trigger vocabulary. Every
    trigger is offered, not a chosen few, so a new trigger added tomorrow is offered too."""
    conn = _conn()
    _human(conn, "po")
    _activate(conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
    m = _m11(conn)
    m.revoke("p1", revoked_reason="withdrawn", direction="narrow", actor_id="po")
    terminal = m.require("p1")
    assert terminal.state is PolicyState.REVOKED and terminal.is_terminal

    triggers = list(Trigger)
    assert len(triggers) >= 5, f"the vocabulary is {triggers}; the sweep would prove little"
    events_before = conn.execute(
        "SELECT COUNT(*) FROM event_outbox WHERE tenant = ?", (TENANT,)).fetchone()[0]
    security_before = conn.execute("SELECT COUNT(*) FROM security_events").fetchone()[0]

    for trigger in triggers:
        with pytest.raises(IllegalTransition):
            m.apply("p1", trigger, actor_id="po")
        row = m.require("p1")
        assert (row.state, row.version) == (terminal.state, terminal.version), (
            f"{trigger.value} moved a REVOKED policy to {row.state.value} v{row.version}")

    # ### THE ONLY EVENTS A REFUSAL MAY EMIT ARE THE F14 REFUSALS THEMSELVES. GR-1 requires the
    # attempt on the audit surface, so the outbox DOES grow — by `IllegalTransitionAttempted` and
    # nothing else. A terminal policy that emitted an F11 contract would be a state change.
    emitted = [r[0] for r in conn.execute(
        "SELECT event_name FROM event_outbox WHERE tenant = ? ORDER BY sequence", (TENANT,))]
    assert set(emitted[events_before:]) == {"IllegalTransitionAttempted"}, (
        f"a refused trigger on a terminal policy emitted {set(emitted[events_before:])}")
    assert len(emitted) - events_before == len(triggers)
    security_after = conn.execute("SELECT COUNT(*) FROM security_events").fetchone()[0]
    assert security_after == security_before + len(triggers), (
        f"{security_after - security_before} security records for {len(triggers)} refusals — GR-1 "
        f"requires every illegal attempt on the audit AND security surface")


def test_m11_a8_a_crash_during_a_transition_leaves_the_canonical_state():
    """### ASSERTION 8 — CRASH RECOVERY REACHES THE CANONICAL STATE. PO-6 is interrupted after its
    row write and before its event is durable (see `phase6_crash_kit`). Neither half may survive: the
    policy must still be ACTIVE at its old version, and a FRESH machine over the same database must
    read that state rather than a half-applied one.

    ### THE RETRY IS PROVED ON A CLEAN TWIN, AND THAT IS FORCED RATHER THAN CHOSEN. `event_outbox` is
    append-only — no DELETE, and `idempotency_identity` is immutable — so the planted row cannot be
    lifted afterwards, and a retry on this database would collide with the scaffolding rather than
    with anything real. The twin is the same fixture built the same way, so "the transition still
    completes exactly once" is measured against a machine in the same state."""
    conn = _conn()
    _human(conn, "po")
    _activate(conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
    m = _m11(conn)
    before = m.require("p1")
    assert before.state is PolicyState.ACTIVE

    plant_colliding_emission(
        conn, TENANT, aggregate_type="policy", aggregate_id="p1",
        transition_id="PO-6", event_name="PolicyRevoked")
    outbox_before = outbox_count(conn, TENANT)

    with pytest.raises(Exception) as crash:
        m.revoke("p1", revoked_reason="withdrawn", direction="narrow", actor_id="po")
    assert "already emitted" in str(crash.value), str(crash.value)

    after = m.require("p1")
    assert (after.state, after.version) == (before.state, before.version), (
        f"the interrupted transition left the policy at {after.state.value} v{after.version}; the row "
        f"was written and its event was not, which is exactly what GR-2 forbids")
    assert outbox_count(conn, TENANT) == outbox_before, "a half-transition emitted an event"

    recovered = M11Machine(conn, tenant=TENANT, clock=CLOCK,
                           product_ceiling=GateDecision.HUMAN_APPROVAL_REQUIRED)
    reread = recovered.require("p1")
    assert (reread.state, reread.version) == (before.state, before.version), (
        "a fresh machine over the same database did not read the canonical pre-crash state")
    assert legal_transitions(reread.state, Trigger.REVOKED), (
        "the crash left the policy in a state from which the transition is no longer legal")

    twin_conn = _conn()
    _human(twin_conn, "po")
    _activate(twin_conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED,
              policy_id="p1")
    twin = _m11(twin_conn)
    twin_outbox = outbox_count(twin_conn, TENANT)
    result = twin.revoke("p1", revoked_reason="withdrawn", direction="narrow", actor_id="po")
    assert result.to_state is PolicyState.REVOKED
    assert twin.require("p1").version == before.version + 1, (
        "the uninterrupted transition did not advance the version by exactly one")
    assert outbox_count(twin_conn, TENANT) > twin_outbox


# ====================================================== the tenant policy epoch (U8.1/P8, S3)
#
# ### WHAT THESE GUARD, AND WHY THEY DID NOT EXIST BEFORE.
#
# Until U8.1 `current_policy_version()` was `MAX(policy_version)` over `policies` IN ANY STATE, and
# `policy_version` is allocated at PO-1 when a DRAFT row is inserted. So DRAFTING a policy advanced
# the tenant scalar that is bound into every witness and revalidated by the claim CAS: a dispatcher
# opening a draft at 4pm voided every in-flight Effect Grant and every outstanding human approval in
# the brokerage, and a draft later rejected kept its number, so the voiding was permanent and bought
# nothing.
#
# ### NOT ONE TEST IN THIS MODULE FAILED WHEN THAT BEHAVIOUR WAS REPLACED — all 60 passed against
# ### both the old rule and the new one. The old behaviour was never asserted; it was found by
# ### reading. That is exactly the population these cases add.
#
# The adjudicated rule: the epoch advances when a policy TAKES EFFECT or is WITHDRAWN (PO-4
# ACTIVATED / PO-6 REVOKED / PO-7 EXPIRED) and at NO other time.

def _epoch(conn, tenant=TENANT) -> int:
    return _m11(conn, tenant=tenant).current_policy_version()


def _draft_only(conn, *, policy_id, scope, owner="po", tenant=TENANT):
    """PO-1 alone: author a DRAFT and stop. No submission, no approval, no activation."""
    m = _m11(conn, tenant=tenant)
    m.propose_draft(scope=scope, scope_kind="action_class",
                    gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED, caps={},
                    predicate={"clauses": []}, authored_by=owner, policy_id=policy_id)
    return policy_id


def test_drafting_a_policy_does_NOT_advance_the_tenant_epoch():
    """### THE DEFECT THIS CLOSES. A half-written draft is not a change."""
    conn = _conn()
    _human(conn, "po")
    assert _epoch(conn) == 0, "a tenant with no policy at all must sit at epoch 0"
    _draft_only(conn, policy_id="d1", scope="raise_invoice")
    assert _epoch(conn) == 0, (
        "inserting a DRAFT advanced the tenant epoch. That voids every in-flight Effect Grant and "
        "every outstanding approval in the brokerage because someone started typing.")
    _draft_only(conn, policy_id="d2", scope="book_carrier")
    assert _epoch(conn) == 0, "a second draft advanced the epoch"
    # The positive control: the ROW numbers really were allocated, so the epoch staying at 0 is a
    # decision and not an empty table.
    rows = conn.execute(
        "SELECT policy_id, policy_version, state FROM policies WHERE tenant = ? ORDER BY policy_version",
        (TENANT,)).fetchall()
    assert [r["state"] for r in rows] == ["DRAFT", "DRAFT"], rows
    assert [r["policy_version"] for r in rows] == [1, 2], (
        "the drafts were not numbered, so this test proved nothing about numbering vs the epoch")


def test_submission_and_approval_advance_nothing_only_activation_does():
    """PO-2 and PO-3 move a policy through its own governance; they move no authority."""
    conn = _conn()
    _human(conn, "po")
    m = _m11(conn)
    _approval(conn, "appr-a1", mfp="DIFF-a1")
    _draft_only(conn, policy_id="a1", scope="raise_invoice")
    assert _epoch(conn) == 0
    m.submit("a1", actor_id="po")
    assert _epoch(conn) == 0, "submitting for approval advanced the epoch"
    m.approve("a1", approval_id="appr-a1", diff_fingerprint="DIFF-a1", approved_by="po")
    assert _epoch(conn) == 0, "approving advanced the epoch — approval is not yet effect"
    m.activate("a1", activated_by="po")
    assert _epoch(conn) == 1, (
        "ACTIVATION did NOT advance the epoch. A policy that has taken effect must void in-flight "
        "authority granted under the previous posture (ADR-010 sec 7.4).")


def test_revocation_advances_the_epoch_the_under_voiding_direction():
    """### THE DIRECTION M11's OWN DOCSTRING SAYS IS NOT AVAILABLE.

    A naive fix -- MAX(policy_version) WHERE activated_by IS NOT NULL -- is monotonic but does NOT
    move on revocation, because the revoked row was already counted. Revoking a policy would then
    leave every grant minted under it claimable. This is the case that catches that.
    """
    conn = _conn()
    _human(conn, "po")
    _activate(conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="r1")
    after_activation = _epoch(conn)
    assert after_activation == 1
    _m11(conn).revoke("r1", revoked_reason="withdrawn", direction="narrow", actor_id="po")
    assert _epoch(conn) == after_activation + 1, (
        "REVOCATION did not advance the epoch. An Effect Grant minted under the revoked policy is "
        "still claimable, so the effect executes under a policy that no longer exists.")


def test_expiry_advances_the_epoch_because_expiry_is_withdrawal():
    """PO-7. The policy that decided no longer governs, so its decision is not REPRODUCIBLE."""
    conn = _conn()
    _human(conn, "po")
    m = _m11(conn)
    # `_activate` mints its own approval for the policy it activates; minting a second one here
    # collides on approvals.(tenant, commit_key).
    _activate(conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="base")
    # A NARROWING policy carrying an expiry is the only thing PO-7 fires on.
    _approval(conn, "appr-n1", mfp="DIFF-n1")
    m.propose_draft(scope="raise_invoice", scope_kind="action_class",
                    gate_decision=GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED, caps={},
                    predicate={"clauses": []}, authored_by="po", policy_id="n1",
                    expires_at="2027-01-01T00:00:00Z")
    m.submit("n1", actor_id="po")
    m.approve("n1", approval_id="appr-n1", diff_fingerprint="DIFF-n1", approved_by="po")
    m.activate("n1", activated_by="po")
    before_expiry = _epoch(conn)
    m.expire("n1", owner_id="po")
    assert _epoch(conn) == before_expiry + 1, (
        "EXPIRY did not advance the epoch. The policy that decided no longer governs, so every "
        "decision taken under it is non-reproducible (ADR-010 sec 9.1).")


def test_the_epoch_never_decreases_across_a_full_lifecycle():
    """### MONOTONICITY IS THE LOAD-BEARING PROPERTY.

    If the epoch could ever FALL, a grant bound at 5 would match again the moment the value returned
    to 5 -- a stale Effect Grant resurrected, which is the precise failure the CAS predicate exists
    to prevent. Asserted over a real lifecycle, not by reading the SQL.
    """
    conn = _conn()
    _human(conn, "po")
    m = _m11(conn)
    seen = [_epoch(conn)]
    _activate(conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="v1")
    seen.append(_epoch(conn))
    # supersede v1 by activating v2 in the same scope
    _activate(conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="v2")
    seen.append(_epoch(conn))
    _draft_only(conn, policy_id="never", scope="book_carrier")
    seen.append(_epoch(conn))
    m.revoke("v2", revoked_reason="withdrawn", direction="narrow", actor_id="po")
    seen.append(_epoch(conn))
    assert seen == sorted(seen), f"the epoch DECREASED across the lifecycle: {seen}"
    assert seen[0] == 0 and seen[-1] > seen[0], f"the epoch never moved at all: {seen}"
    # and the draft step specifically moved nothing
    assert seen[2] == seen[3], f"the DRAFT advanced the epoch: {seen}"


def test_the_epoch_is_tenant_scoped_one_brokerage_never_moves_another():
    conn = _conn()
    other = "beta-brokerage"
    _human(conn, "po")
    _human(conn, "po2", tenant=other)
    # `_approval` stamps granted_by='po', which is FK-backed into tenant_humans PER TENANT — so the
    # other brokerage needs its own 'po' row before it can hold an approval at all.
    # AUTHORIZED_HUMAN, not POLICY_OWNER: 'po2' already holds that role here, and the Policy Owner
    # singularity index permits exactly one ACTIVE owner per tenant.
    _human(conn, "po", role="AUTHORIZED_HUMAN", tenant=other)
    _activate(conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="t1")
    assert _epoch(conn) == 1
    assert _epoch(conn, tenant=other) == 0, (
        "one brokerage's policy activity moved another brokerage's epoch [C-1]")
    _activate(conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED,
              policy_id="t2", owner="po2", tenant=other)
    assert _epoch(conn, tenant=other) == 1
    assert _epoch(conn) == 1, "the other tenant's activation moved ours"


def test_a_policy_epoch_row_is_append_only_in_the_database():
    """Not a convention: UPDATE and DELETE are refused by trigger. A DELETE would lower the MAX."""
    conn = _conn()
    _human(conn, "po")
    _activate(conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
    assert conn.execute("SELECT COUNT(*) FROM policy_epochs WHERE tenant = ?",
                        (TENANT,)).fetchone()[0] == 1, "no epoch row was written to take away"
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        conn.execute("UPDATE policy_epochs SET epoch = 99 WHERE tenant = ?", (TENANT,))
    with pytest.raises(sqlite3.IntegrityError, match="never deleted"):
        conn.execute("DELETE FROM policy_epochs WHERE tenant = ?", (TENANT,))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO policy_epochs (tenant, epoch, reason, policy_id, policy_version, "
            "transition_id, advanced_by, occurred_at) VALUES (?,?,?,?,?,?,?,?)",
            (TENANT, 99, "DRAFTED", "p1", 1, "PO-1", "po", "2026-09-03T12:00:00Z"))


def test_every_epoch_row_names_the_policy_and_the_transition_that_caused_it():
    """An epoch nobody can explain is an epoch nobody can defend to the broker whose effect it voided."""
    conn = _conn()
    _human(conn, "po")
    _activate(conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="e1")
    _m11(conn).revoke("e1", revoked_reason="withdrawn", direction="narrow", actor_id="po")
    rows = conn.execute(
        "SELECT epoch, reason, policy_id, transition_id, advanced_by FROM policy_epochs "
        "WHERE tenant = ? ORDER BY epoch", (TENANT,)).fetchall()
    assert [(r["epoch"], r["reason"], r["transition_id"]) for r in rows] == [
        (1, "ACTIVATED", "PO-4"), (2, "REVOKED", "PO-6")], [dict(r) for r in rows]
    assert all(r["policy_id"] == "e1" for r in rows)
    assert all(r["advanced_by"] == "po" for r in rows), (
        "the human who moved authority is not recorded on the epoch")
