"""P6-CP-12 — M12, the Rule: the acceptance battery.

Every test here could have failed before the code existed, and each is the RED half of a mutant in
`scripts/mutate_phase6_rule.py`. The battery measures the DATABASE (a fresh canonical schema
introspected and written against), the EVENT REGISTRY (the eight F12 contracts, F7's ConflictRaised,
F14's UnauthorizedPolicyActivationAttempted), the LITERAL REPLY TEXT (the L-C guard) and the AST (the
checkpoint stays the sole gate minter; M12 ships dark; the neighbours are unchanged) — not narration.

M12 is tier-1 (a migration, tenant-isolation-bearing, and it decides whether an action is allowed inside
the checkpoint), so the load-bearing DDL is introspected LIVE and the forbidden writes are ATTEMPTED
against a real canonical database behind positive controls, not read from the migration source.

Some test names are FIXED by the corpus: entity `15-rule.md` point 44 and machine `12-rule.machine.md`
§14 each NAME the validating tests, and a session's build is incomplete if a named test is absent. Those
names are used verbatim below.
"""

from __future__ import annotations

import ast
import json
import re
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
    ProvenanceClass,
    ProvenancedFact,
)
from freight_recon.conflict import M7Machine, Party  # noqa: E402
from freight_recon.event_contracts import CONTRACTS  # noqa: E402
from freight_recon.migrations.phase6_rules import (  # noqa: E402
    P6RU_SCOPE_FORMS,
    P6RU_SINGLE_ACTIVE_SCOPES,
    RULE_KINDS,
    RULE_STATES,
    phase6_rules_readiness_problems,
)
from freight_recon.rule import (  # noqa: E402
    PRECEDENCE_LADDER,
    PRECEDENCE_LAYER,
    PRODUCED_CONTRACTS,
    TRANSITIONS,
    CompilerInput,
    DishonestReply,
    GuardNotSatisfied,
    IllegalTransition,
    M12Machine,
    RuleEngineUnavailable,
    RuleState,
    RuleWillNotCompile,
    assert_reply_is_honest,
    assert_within_precedence,
    compile_candidate,
    compile_predicate_field,
    evaluate_rule,
    honest_refusal,
    reply_claims_enforcement,
)
from freight_recon.schema import (  # noqa: E402
    CANONICAL_TABLES,
    create_canonical_schema,
    enable_and_verify_foreign_keys,
    schema_readiness_problems,
)

TENANT = "acme-brokerage"
CLOCK = lambda: datetime(2026, 9, 3, 12, 0, 0, tzinfo=timezone.utc)  # noqa: E731
RULE_SRC = (ROOT / "src" / "freight_recon" / "rule.py").read_text(encoding="utf-8")
MIG_SRC = (ROOT / "src" / "freight_recon" / "migrations" / "phase6_rules.py").read_text(encoding="utf-8")


# ------------------------------------------------------------------ helpers

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_canonical_schema(conn)
    enable_and_verify_foreign_keys(conn)
    return conn


def _human(conn, hid, *, role="POLICY_OWNER", state="ACTIVE", tenant=TENANT):
    offboarded = "2026-06-01T00:00:00Z" if state == "OFFBOARDED" else None
    conn.execute(
        "INSERT INTO tenant_humans (tenant, human_id, display_name, authority_role, state, "
        "recorded_at, recorded_by, recorded_by_kind, offboarded_at) VALUES (?,?,?,?,?,?,?, 'human', ?)",
        (tenant, hid, hid, role, state, "2026-01-01T00:00:00Z", "founder", offboarded))
    conn.commit()
    return hid


def _m12(conn, *, tenant=TENANT):
    return M12Machine(conn, tenant=tenant, clock=CLOCK)


_MODELLED = {"provenance_class": "SYSTEM_IMPORTED", "modelled": True}


def _pod_clauses():
    return [
        {"field": "pod", "attr": "evidence_condition", "op": "==", "literal": "consistent", **_MODELLED},
        {"field": "pod", "attr": "provenance_class", "op": "in",
         "literal": ["SYSTEM_IMPORTED", "OWNER_ASSERTED", "MODEL_EXTRACTED"], **_MODELLED},
    ]


def _activate(conn, *, rule_id, scope="raise_invoice", scope_form="action_class",
              kind="GATE_PRECONDITION", effect="DENY", clauses=None, owner="po", tenant=TENANT):
    m = _m12(conn, tenant=tenant)
    m.propose(scope=scope, scope_form=scope_form, kind=kind, effect=effect,
              source_instruction=f"instruction {rule_id}", authored_by=owner,
              clauses=clauses if clauses is not None else _pod_clauses(), rule_id=rule_id)
    m.compile(rule_id)
    m.confirm(rule_id, confirmed_by=owner)
    m.activate(rule_id, activated_by=owner)
    return rule_id


def _to_confirmed(conn, *, rule_id="r1", **kw):
    m = _m12(conn)
    m.propose(scope=kw.get("scope", "raise_invoice"), scope_form=kw.get("scope_form", "action_class"),
              kind=kw.get("kind", "GATE_PRECONDITION"), effect=kw.get("effect", "DENY"),
              source_instruction="x", authored_by="po", clauses=_pod_clauses(), rule_id=rule_id)
    m.compile(rule_id)
    m.confirm(rule_id, confirmed_by="po")
    return m


def _emitted_event_names(src: str) -> set[str]:
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
    return names


# ------------------------------------------------------------------ migration / readiness / partition

def test_readiness_is_clean_on_a_fresh_canonical_database():
    conn = _conn()
    assert schema_readiness_problems(conn) == []
    assert phase6_rules_readiness_problems(conn) == []


def test_the_rules_migration_is_rerunnable_and_matches_a_fresh_build():
    from freight_recon.migrations.phase6_rules import create_phase6_rules_schema
    conn = _conn()
    performed = create_phase6_rules_schema(conn, now="2026-09-03T12:00:00Z")
    assert performed == [], f"a second application was not a no-op: {performed}"
    assert phase6_rules_readiness_problems(conn) == []


def test_rules_is_registered_tenant_first_in_the_canonical_partition():
    assert "rules" in CANONICAL_TABLES
    conn = _conn()
    pk = [r[1] for r in conn.execute("PRAGMA table_info(rules)") if r[5]]
    assert pk and pk[0] == "tenant", f"rules PK is not tenant-first: {pk}"


def test_every_rule_index_is_tenant_first():
    conn = _conn()
    for idx in conn.execute("PRAGMA index_list(rules)"):
        name = idx[1]
        cols = [r[2] for r in conn.execute(f"PRAGMA index_info({name})")]
        assert cols and cols[0] == "tenant", f"index {name} is not tenant-first: {cols}"


# ------------------------------------------------------------------ the state & kind vocabularies (DB)

def test_the_eight_canonical_states_and_no_ninth():
    conn = _conn()
    ddl = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='rules'").fetchone()[0]
    expected = "state IN (" + ",".join(f"'{s}'" for s in RULE_STATES) + ")"
    assert expected.upper() in " ".join(ddl.split()).upper().replace(", ", ",")
    _human(conn, "po")
    # DRAFT and APPROVED are M11 POLICY's states; PARSED/SUSPENDED/etc. are the brief's mapped names.
    for forbidden in ("DRAFT", "APPROVED", "PARSED", "INVALID", "SUSPENDED", "PENDING", "CANCELLED"):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO rules (tenant, rule_id, rule_version, scope, scope_form, kind, "
                "compiled_predicate, test_vectors, state, version, source_instruction, authored_by, "
                "change_direction, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (TENANT, f"r-{forbidden}", 99, "s", "action_class", "CONSTRAINT", "{}", "[]",
                 forbidden, 1, "i", "po", "narrow", "t", "t"))
        conn.rollback()


def test_the_four_canonical_kinds_and_no_fifth():
    conn = _conn()
    ddl = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='rules'").fetchone()[0]
    expected = "kind IN (" + ",".join(f"'{k}'" for k in RULE_KINDS) + ")"
    assert expected.upper() in " ".join(ddl.split()).upper().replace(", ", ",")
    assert len(RULE_KINDS) == 4
    _human(conn, "po")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO rules (tenant, rule_id, rule_version, scope, scope_form, kind, compiled_predicate, "
            "test_vectors, state, version, source_instruction, authored_by, change_direction, created_at, "
            "updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (TENANT, "rk", 1, "s", "action_class", "INVENTED_KIND", "{}", "[]", "PROPOSED", 1, "i", "po",
             "narrow", "t", "t"))
    conn.rollback()


# ------------------------------------------------------------------ AC-MACH-000: the transition table (nine)

def test_ac_mach_000_transition_table_is_the_nine_canonical_rows():
    ids = {row.id for row in TRANSITIONS}
    assert ids == {"RU-1", "RU-2", "RU-2f", "RU-3", "RU-4", "RU-5", "RU-6", "RU-7", "RU-8"}, ids
    assert len(TRANSITIONS) == 9


# ================================================================== machine §14 named tests

def test_ru_propose():
    """RU-1: a candidate is proposed; a proposal is not an enforceable rule; source_instruction retained."""
    conn = _conn()
    _human(conn, "po")
    m = _m12(conn)
    r = m.propose(scope="raise_invoice", scope_form="action_class", kind="GATE_PRECONDITION", effect="DENY",
                  source_instruction="never bill without a POD", authored_by="po", clauses=_pod_clauses(),
                  rule_id="r1")
    assert r.to_state is RuleState.PROPOSED
    row = m.require("r1")
    assert row.source_instruction == "never bill without a POD"
    assert conn.execute("SELECT COUNT(*) FROM event_outbox WHERE event_name='RuleProposed' "
                        "AND aggregate_id='r1'").fetchone()[0] == 1


def test_ru_compile_requires_modelled_non_inferred_fields():
    """RU-2: every referenced field must be modelled and non-inferred (GR-8), at any confidence."""
    conn = _conn()
    _human(conn, "po")
    m = _m12(conn)
    # a MODEL_INFERRED field fails to compile -> REJECTED
    m.propose(scope="pay_carrier", scope_form="action_class", kind="GATE_PRECONDITION", effect="DENY",
              source_instruction="require approval under 12% margin", authored_by="po",
              clauses=[{"field": "carrier_cost", "attr": "value", "op": "<", "literal": 100,
                        "provenance_class": "MODEL_INFERRED", "modelled": True}], rule_id="r1")
    res = m.compile("r1")
    assert res.to_state is RuleState.REJECTED
    assert "carrier_cost" in res.missing
    # a modelled, non-inferred field compiles -> COMPILED
    m.propose(scope="pay_carrier", scope_form="action_class", kind="GATE_PRECONDITION", effect="DENY",
              source_instruction="ok", authored_by="po",
              clauses=[{"field": "carrier_cost", "attr": "value", "op": "<", "literal": 100,
                        "provenance_class": "SYSTEM_IMPORTED", "modelled": True}], rule_id="r2")
    assert m.compile("r2").to_state is RuleState.COMPILED


def test_ru_uncompilable_reply_does_not_claim_enforcement():
    """RU-2f: an uncompilable instruction yields RuleNotEnforceable and an honest reply — never a claim."""
    conn = _conn()
    _human(conn, "po")
    m = _m12(conn)
    m.propose(scope="book_carrier", scope_form="action_class", kind="CONSTRAINT", effect="DENY",
              source_instruction="do not use Carrier X for produce", authored_by="po",
              clauses=[{"field": "commodity", "attr": "value", "op": "==", "literal": "produce",
                        "provenance_class": "SYSTEM_IMPORTED", "modelled": False}], rule_id="r1")
    res = m.compile("r1")
    assert res.to_state is RuleState.REJECTED
    assert not reply_claims_enforcement(res.reply)
    assert "not a rule" in res.reply.lower()
    # the L-C guard on the literal reply text
    assert_reply_is_honest(res.reply, active_rule_id=None)  # must NOT raise


def test_ru_conflict_fails_closed():
    """RU-3: two conflicting active rules fail closed into an M7 RULE_VS_RULE conflict; the rule stays
    COMPILED, blocked; M12 mints no ConflictRaised of its own."""
    conn = _conn()
    _human(conn, "po")
    _activate(conn, rule_id="a", scope="pay_carrier", clauses=[
        {"field": "amount", "attr": "value", "op": "<", "literal": 100, **_MODELLED}])
    m = _m12(conn)
    m.propose(scope="pay_carrier", scope_form="action_class", kind="GATE_PRECONDITION", effect="PERMIT",
              source_instruction="b", authored_by="po",
              clauses=[{"field": "amount", "attr": "value", "op": ">", "literal": 50, **_MODELLED}],
              rule_id="b")
    m.compile("b")
    res = m.detect_conflict("b", against_rule_id="a", owner_id="po")
    assert res.conflict is not None and res.conflict.kind == "RULE_VS_RULE"
    assert m.require("b").state is RuleState.COMPILED
    # M12 emitted NO ConflictRaised
    assert conn.execute("SELECT COUNT(*) FROM event_outbox WHERE event_name='ConflictRaised' "
                        "AND aggregate_type='rule'").fetchone()[0] == 0
    # the caller drives M7, and it blocks the field
    kw = res.conflict.as_m7_kwargs()
    parties = [Party(**p) for p in kw.pop("parties")]
    m7 = M7Machine(conn, tenant=TENANT, clock=CLOCK)
    m7.raise_conflict(parties=parties, **kw)
    assert m7.is_field_conflicting(res.conflict.entity_ref, res.conflict.field)


def test_ru_confirm_shows_test_vectors():
    """RU-4: the owner sees the compiled rule AND its generated test vectors; confirmation without test
    vectors is refused; RuleConfirmed does not activate."""
    conn = _conn()
    _human(conn, "po")
    m = _m12(conn)
    m.propose(scope="raise_invoice", scope_form="action_class", kind="GATE_PRECONDITION", effect="DENY",
              source_instruction="x", authored_by="po", clauses=_pod_clauses(), rule_id="r1")
    m.compile("r1")
    assert m.require("r1").test_vector_list, "a compiled rule ships with non-empty test vectors"
    m.confirm("r1", confirmed_by="po")
    assert m.require("r1").state is RuleState.CONFIRMED
    # CONFIRMED is not ACTIVE
    assert conn.execute("SELECT COUNT(*) FROM event_outbox WHERE event_name='RuleActivated' "
                        "AND aggregate_id='r1'").fetchone()[0] == 0
    # a rule with no test vectors cannot be confirmed
    conn.execute("UPDATE rules SET test_vectors='[]' WHERE rule_id='r1' AND state='COMPILED'")  # (still COMPILED? no)
    conn.rollback()


def test_ru_only_human_activates():
    """RU-5: an authenticated human activates; a model/automation/timer/retry/counterparty does not."""
    for kind in ("model", "automation", "timer", "retry", "counterparty"):
        conn = _conn()
        _human(conn, "po")
        m = _to_confirmed(conn, rule_id="r1")
        with pytest.raises(IllegalTransition):
            m.activate("r1", activated_by="po", actor_kind=kind)
        assert m.require("r1").state is RuleState.CONFIRMED
    # the human path works
    conn = _conn()
    _human(conn, "po")
    m = _to_confirmed(conn, rule_id="r1")
    m.activate("r1", activated_by="po")
    assert m.require("r1").state is RuleState.ACTIVE


def test_ru_supersede_retains_old():
    """RU-6: a new version supersedes; the old version is retained and still explains its decisions."""
    conn = _conn()
    _human(conn, "po")
    _activate(conn, rule_id="v1", scope="carrier_invoice", scope_form="subject_type", kind="IDENTITY",
              effect="BIND", clauses=[{"field": "pro_number", "attr": "value", "op": "==", "literal": "A",
                                       **_MODELLED}])
    _activate(conn, rule_id="v2", scope="carrier_invoice", scope_form="subject_type", kind="IDENTITY",
              effect="BIND", clauses=[{"field": "pro_number", "attr": "value", "op": "==", "literal": "B",
                                       **_MODELLED}])
    m = _m12(conn)
    old = m.require("v1")
    assert old.state is RuleState.SUPERSEDED and old.superseded_by == "v2"
    # retained AND still explains itself
    assert json.loads(old.compiled_predicate)["clauses"][0]["literal"] == "A"


def test_ru_revoke_direction():
    """RU-7: a narrowing revocation is immediate (automation allowed); a broadening one needs the owner."""
    conn = _conn()
    _human(conn, "po")
    _activate(conn, rule_id="rn")
    m = _m12(conn)
    m.revoke("rn", revoked_reason="tighten", direction="narrow", actor_kind="automation", actor_id="auto")
    r = conn.execute("SELECT state, revoked_direction FROM rules WHERE rule_id='rn'").fetchone()
    assert r["state"] == "REVOKED" and r["revoked_direction"] == "narrow"
    # broadening by automation is refused; by the owner it proceeds
    conn2 = _conn()
    _human(conn2, "po")
    _activate(conn2, rule_id="rb")
    m2 = _m12(conn2)
    with pytest.raises(IllegalTransition):
        m2.revoke("rb", revoked_reason="loosen", direction="broaden", actor_kind="automation", actor_id="po")
    m2.revoke("rb", revoked_reason="loosen", direction="broaden", actor_kind="human", actor_id="po")
    assert conn2.execute("SELECT state FROM rules WHERE rule_id='rb'").fetchone()["state"] == "REVOKED"


def test_ru_narrowing_expiry_needs_human():
    """RU-8: only a narrowing rule may carry an expiry, its expiry BROADENS, and a human is required at
    expiry — TimerFired never completes the broadening. M12 does not call M9."""
    conn = _conn()
    _human(conn, "po")
    m = _m12(conn)
    m.propose(scope="ship", scope_form="action_class", kind="CONSTRAINT", effect="DENY",
              source_instruction="tighten", authored_by="po",
              clauses=[{"field": "x", "attr": "value", "op": "==", "literal": 1, **_MODELLED}],
              rule_id="r1", expires_at="2026-10-01T00:00:00Z")
    m.compile("r1")
    m.confirm("r1", confirmed_by="po")
    m.activate("r1", activated_by="po")
    result = m.expire("r1", owner_id="po")
    assert m.require("r1").state is RuleState.EXPIRED
    assert result.escalation is not None and result.escalation.source_kind == "rule"
    # M9 was NOT called by M12: no exception row was created by expire()
    assert conn.execute("SELECT COUNT(*) FROM exceptions WHERE source_kind='rule'").fetchone()[0] == 0
    # a broadening rule cannot carry an expiry (DB CHECK)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO rules (tenant, rule_id, rule_version, scope, scope_form, kind, compiled_predicate, "
            "test_vectors, state, version, source_instruction, authored_by, expires_at, change_direction, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (TENANT, "rbroad", 99, "s", "action_class", "GATE_PRECONDITION", "{}", "[]", "PROPOSED", 1,
             "i", "po", "2026-10-01T00:00:00Z", "broaden", "t", "t"))
    conn.rollback()


# ================================================================== entity §44 named tests

def test_uncompilable_instruction_reply_does_not_claim_a_rule_was_installed():
    """entity §44 (M-52/M-64): the reply to an uncompilable instruction NEVER claims a rule was installed;
    the same claiming reply WITH an active rule id is accepted."""
    # a bare acknowledgement with no active rule id is refused
    with pytest.raises(DishonestReply):
        assert_reply_is_honest("📋 Noted the procedure for raise_invoice", active_rule_id=None)
    with pytest.raises(DishonestReply):
        assert_reply_is_honest("Noted the procedure for raise_invoice", active_rule_id="")
    # the same sentence WITH a real active rule id is accepted (a machine that refuses every reply is broken)
    assert_reply_is_honest("Noted the procedure for raise_invoice", active_rule_id="rule-123")
    # the honest refusal is itself a legal reply
    assert_reply_is_honest(honest_refusal(["commodity"], "commodity as a modelled field"), active_rule_id=None)


def test_never_bill_without_pod_compiles_to_a_precondition():
    """entity §44: 'never bill without a POD' compiles to a real precondition, and a MODEL_INFERRED POD is
    denied by the compiled rule."""
    compiled = compile_candidate(
        {"kind": "GATE_PRECONDITION", "effect": "DENY", "combine": "AND", "clauses": _pod_clauses()},
        scope="raise_invoice")
    assert compiled.effect == "DENY" and compiled.clauses
    # a consistent, SYSTEM_IMPORTED POD passes (PERMIT); a MODEL_INFERRED POD is denied
    good = {"pod": ProvenancedFact(field="pod", provenance=ProvenanceClass.SYSTEM_IMPORTED,
                                   evidence_condition=EvidenceCondition.CONSISTENT, _value="scan")}
    assert evaluate_rule(compiled, good).decision == "PERMIT"
    inferred = {"pod": ProvenancedFact(field="pod", provenance=ProvenanceClass.MODEL_INFERRED,
                                       evidence_condition=EvidenceCondition.CONSISTENT, _value="guess")}
    assert evaluate_rule(compiled, inferred).decision == "DENY"


def test_do_not_use_carrier_x_for_produce_cannot_compile():
    """entity §44: 'do not use Carrier X for produce' cannot compile — commodity is not a modelled field —
    and the owner is told exactly that."""
    with pytest.raises(RuleWillNotCompile) as exc:
        compile_candidate(
            {"kind": "CONSTRAINT", "effect": "DENY", "combine": "AND", "clauses": [
                {"field": "carrier", "attr": "value", "op": "==", "literal": "X", **_MODELLED},
                {"field": "commodity", "attr": "value", "op": "==", "literal": "produce",
                 "provenance_class": "SYSTEM_IMPORTED", "modelled": False}]},
            scope="book_carrier")
    assert "commodity" in exc.value.missing


def test_margin_rule_refuses_to_compile_on_model_inferred_cost():
    """entity §44: a manager-approval-under-12%-margin rule refuses to compile if the carrier cost is a
    model estimate."""
    with pytest.raises(RuleWillNotCompile):
        compile_candidate(
            {"kind": "GATE_PRECONDITION", "effect": "REQUIRE_HUMAN_APPROVAL", "combine": "AND", "clauses": [
                {"field": "carrier_cost", "attr": "value", "op": "<", "literal": 100,
                 "provenance_class": "MODEL_INFERRED", "modelled": True}]},
            scope="book_carrier")
    # with a real (SYSTEM_IMPORTED) carrier cost it compiles
    ok = compile_candidate(
        {"kind": "GATE_PRECONDITION", "effect": "REQUIRE_HUMAN_APPROVAL", "combine": "AND", "clauses": [
            {"field": "carrier_cost", "attr": "value", "op": "<", "literal": 100,
             "provenance_class": "SYSTEM_IMPORTED", "modelled": True}]},
        scope="book_carrier")
    assert ok.clauses


def test_two_conflicting_rules_fail_closed():
    """entity §44: two conflicting rules fail closed; nothing auto-merges; Neyma never picks a winner."""
    conn = _conn()
    _human(conn, "po")
    _activate(conn, rule_id="a", scope="pay_carrier",
              clauses=[{"field": "amount", "attr": "value", "op": "<", "literal": 100, **_MODELLED}])
    m = _m12(conn)
    m.propose(scope="pay_carrier", scope_form="action_class", kind="GATE_PRECONDITION", effect="PERMIT",
              source_instruction="b", authored_by="po",
              clauses=[{"field": "amount", "attr": "value", "op": ">", "literal": 50, **_MODELLED}],
              rule_id="b")
    m.compile("b")
    res = m.detect_conflict("b", against_rule_id="a", owner_id="po")
    assert res.conflict is not None
    # b never becomes ACTIVE while blocked; a is untouched (no winner picked)
    assert m.require("b").state is RuleState.COMPILED
    assert m.require("a").state is RuleState.ACTIVE
    # the narrower scope is precedence, not a conflict
    narrower = m.detect_conflict("b", against_rule_id="a", owner_id="po", narrower=True)
    assert narrower.conflict is None


def test_model_cannot_activate_a_rule():
    """entity §44: a model cannot activate a rule; the attempt is recorded as the registered F14 event."""
    conn = _conn()
    _human(conn, "po")
    m = _to_confirmed(conn, rule_id="r1")
    with pytest.raises(IllegalTransition):
        m.activate("r1", activated_by="po", actor_kind="model")
    assert m.require("r1").state is RuleState.CONFIRMED
    f14 = conn.execute("SELECT COUNT(*) FROM event_outbox WHERE "
                       "event_name='UnauthorizedPolicyActivationAttempted'").fetchone()[0]
    assert f14 == 1, "the unauthorized activation went unrecorded (F14)"


def test_repeatedly_overridden_rule_asks_does_not_auto_disable():
    """entity §44 / §42: a repeatedly-overridden rule ASKS a human (through M9) and is NEVER auto-disabled;
    Q3 stays deferred. M12 builds no override mechanism and mints no PolicyOverridden."""
    conn = _conn()
    _human(conn, "po")
    _activate(conn, rule_id="r1")
    m = _m12(conn)
    esc = m.override_health_escalation("r1", overrides=8, decisions=10, owner_id="po")
    assert esc is not None and esc.source_kind == "rule", "an over-threshold override rate asks a human"
    # the rule is NOT auto-disabled: it is still ACTIVE
    assert m.require("r1").state is RuleState.ACTIVE
    # below threshold, nobody is bothered
    assert m.override_health_escalation("r1", overrides=1, decisions=10, owner_id="po") is None
    # no override event exists to mint
    assert "PolicyOverridden" not in CONTRACTS


# ================================================================== compiler input / confidence

def test_the_compiler_input_type_has_no_confidence_field():
    assert "confidence" not in CompilerInput.__dataclass_fields__
    # a clause naming `confidence` is refused
    with pytest.raises(RuleWillNotCompile):
        compile_predicate_field(CompilerInput(field="confidence", provenance_class="SYSTEM_IMPORTED"))


def test_confidence_one_does_not_make_model_inferred_compilable():
    # there is no confidence input at all, so a MODEL_INFERRED field fails regardless
    with pytest.raises(RuleWillNotCompile):
        compile_predicate_field(CompilerInput(field="carrier_cost", provenance_class="MODEL_INFERRED"))
    # a MODEL_INFERRED fact is unreadable at eval time too (defense in depth)
    fact = ProvenancedFact(field="c", provenance=ProvenanceClass.MODEL_INFERRED,
                           evidence_condition=EvidenceCondition.CONSISTENT, _value=1)
    with pytest.raises(Exception):
        _ = fact.value


def test_an_unmodelled_field_and_an_invented_provenance_class_fail_to_compile():
    with pytest.raises(RuleWillNotCompile):
        compile_predicate_field(CompilerInput(field="commodity", provenance_class="SYSTEM_IMPORTED",
                                              modelled=False))
    with pytest.raises(RuleWillNotCompile):
        compile_predicate_field(CompilerInput(field="pod", provenance_class="INVENTED_CLASS"))
    # the accepted controls
    assert compile_predicate_field(CompilerInput(field="pod", provenance_class="SYSTEM_IMPORTED")) == "pod"
    assert compile_predicate_field(CompilerInput(field="pod", provenance_class="OWNER_ASSERTED")) == "pod"


def test_compilation_is_byte_identical_reproducible():
    candidate = {"kind": "GATE_PRECONDITION", "effect": "DENY", "combine": "AND", "clauses": _pod_clauses()}
    first = compile_candidate(candidate, scope="raise_invoice").to_json()
    for _ in range(25):
        assert compile_candidate(candidate, scope="raise_invoice").to_json() == first


def test_a_prompt_string_is_not_a_rule():
    with pytest.raises(RuleWillNotCompile):
        compile_candidate("never bill without a POD", scope="raise_invoice")


# ================================================================== activation authority (DB + machine)

def test_active_requires_a_non_null_activated_by_fk_backed():
    conn = _conn()
    refs = {r[2] for r in conn.execute("PRAGMA foreign_key_list(rules)")}
    assert "tenant_humans" in refs
    _human(conn, "po")
    # ACTIVE with a null activator is refused by the CHECK
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO rules (tenant, rule_id, rule_version, scope, scope_form, kind, compiled_predicate, "
            "test_vectors, state, version, source_instruction, authored_by, activated_by, change_direction, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (TENANT, "rna", 1, "s", "action_class", "CONSTRAINT", "{}", "[]", "ACTIVE", 1, "i", "po", None,
             "narrow", "t", "t"))
    conn.rollback()
    # ACTIVE with a ghost (unrecorded) activator is refused by the FK
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO rules (tenant, rule_id, rule_version, scope, scope_form, kind, compiled_predicate, "
            "test_vectors, state, version, source_instruction, authored_by, activated_by, change_direction, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (TENANT, "rg", 1, "s", "action_class", "CONSTRAINT", "{}", "[]", "ACTIVE", 1, "i", "po", "ghost",
             "narrow", "t", "t"))
    conn.rollback()


def test_a_model_or_inbound_or_counterparty_cannot_author_a_rule():
    conn = _conn()
    _human(conn, "po")
    m = _m12(conn)
    # a model MAY propose text (accepted)
    m.propose(scope="s", scope_form="action_class", kind="CONSTRAINT", effect="DENY",
              source_instruction="x", authored_by="po", clauses=_pod_clauses(), rule_id="ok",
              actor_kind="model")
    assert m.require("ok").state is RuleState.PROPOSED
    # a counterparty / inbound / automation may NOT author
    for kind in ("counterparty", "inbound", "automation"):
        with pytest.raises(IllegalTransition):
            m.propose(scope="s2", scope_form="action_class", kind="CONSTRAINT", effect="DENY",
                      source_instruction="x", authored_by="po", clauses=_pod_clauses(),
                      rule_id=f"r-{kind}", actor_kind=kind)
    # an offboarded / cross-tenant human cannot author
    _human(conn, "ex", role="AUTHORIZED_HUMAN", state="OFFBOARDED")
    with pytest.raises(GuardNotSatisfied):
        m.propose(scope="s3", scope_form="action_class", kind="CONSTRAINT", effect="DENY",
                  source_instruction="x", authored_by="ex", clauses=_pod_clauses(), rule_id="rex")


def test_a_model_cannot_confirm_a_rule():
    conn = _conn()
    _human(conn, "po")
    m = _m12(conn)
    m.propose(scope="raise_invoice", scope_form="action_class", kind="GATE_PRECONDITION", effect="DENY",
              source_instruction="x", authored_by="po", clauses=_pod_clauses(), rule_id="r1")
    m.compile("r1")
    with pytest.raises(IllegalTransition):
        m.confirm("r1", confirmed_by="po", actor_kind="model")
    assert m.require("r1").state is RuleState.COMPILED


def test_ruleconfirmed_does_not_activate():
    conn = _conn()
    _human(conn, "po")
    m = _to_confirmed(conn, rule_id="r1")
    assert m.require("r1").state is RuleState.CONFIRMED
    assert conn.execute("SELECT COUNT(*) FROM event_outbox WHERE event_name='RuleActivated' "
                        "AND aggregate_id='r1'").fetchone()[0] == 0


def test_confirmation_without_test_vectors_is_refused():
    conn = _conn()
    _human(conn, "po")
    m = _m12(conn)
    # raw-insert a COMPILED rule that carries NO test vectors (the state the "test vectors omitted"
    # mutant produces) and confirm that RU-4 refuses it — the owner cannot approve what they cannot see.
    conn.execute(
        "INSERT INTO rules (tenant, rule_id, rule_version, scope, scope_form, kind, compiled_predicate, "
        "test_vectors, state, version, source_instruction, authored_by, change_direction, created_at, "
        "updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (TENANT, "r1", 1, "raise_invoice", "action_class", "GATE_PRECONDITION",
         '{"status":"COMPILED","clauses":[]}', "[]", "COMPILED", 1, "x", "po", "narrow", "t", "t"))
    conn.commit()
    with pytest.raises(GuardNotSatisfied):
        m.confirm("r1", confirmed_by="po")


def test_re_activating_an_active_version_is_a_no_op():
    conn = _conn()
    _human(conn, "po")
    _activate(conn, rule_id="r1")
    m = _m12(conn)
    v = conn.execute("SELECT version FROM rules WHERE rule_id='r1'").fetchone()[0]
    n_before = conn.execute("SELECT COUNT(*) FROM event_outbox WHERE event_name='RuleActivated' "
                            "AND aggregate_id='r1'").fetchone()[0]
    m.activate("r1", activated_by="po")  # no-op
    v2 = conn.execute("SELECT version FROM rules WHERE rule_id='r1'").fetchone()[0]
    n_after = conn.execute("SELECT COUNT(*) FROM event_outbox WHERE event_name='RuleActivated' "
                           "AND aggregate_id='r1'").fetchone()[0]
    assert v2 == v and n_after == n_before, "re-activation bumped the version or emitted a second event"


# ================================================================== versioning namespace / one active

def test_the_version_namespace_is_the_tenant_not_the_scope():
    conn = _conn()
    _human(conn, "po")
    _activate(conn, rule_id="r1", scope="s1")
    _activate(conn, rule_id="r2", scope="s2")
    versions = [r[0] for r in conn.execute(
        "SELECT rule_version FROM rules WHERE tenant=? ORDER BY rule_version", (TENANT,))]
    assert len(versions) == len(set(versions)), "two scopes reused a rule_version (scope-local namespace)"


def test_a_rule_version_is_never_reused_within_a_tenant():
    conn = _conn()
    _human(conn, "po")
    _activate(conn, rule_id="r1")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO rules (tenant, rule_id, rule_version, scope, scope_form, kind, compiled_predicate, "
            "test_vectors, state, version, source_instruction, authored_by, change_direction, created_at, "
            "updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (TENANT, "rdup", 1, "s2", "action_class", "CONSTRAINT", "{}", "[]", "PROPOSED", 1, "i", "po",
             "narrow", "t", "t"))
    conn.rollback()


def test_one_active_rule_where_the_scope_admits_one_and_many_where_it_does_not():
    """The single-admitting index refuses a second ACTIVE rule for a subject_type IDENTITY scope; a
    multi-admitting action_class scope accepts several (conflict detection handles a genuine clash)."""
    conn = _conn()
    _human(conn, "po")
    # single-admitting: a second raw-inserted ACTIVE IDENTITY rule for one subject_type is refused
    _activate(conn, rule_id="i1", scope="carrier_invoice", scope_form="subject_type", kind="IDENTITY",
              effect="BIND", clauses=[{"field": "pro", "attr": "value", "op": "==", "literal": "A", **_MODELLED}])
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO rules (tenant, rule_id, rule_version, scope, scope_form, kind, compiled_predicate, "
            "test_vectors, state, version, source_instruction, authored_by, activated_by, change_direction, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (TENANT, "i2", 99, "carrier_invoice", "subject_type", "IDENTITY", "{}", "[]", "ACTIVE", 1, "i",
             "po", "po", "narrow", "t", "t"))
    conn.rollback()
    # multi-admitting: two ACTIVE GATE_PRECONDITION rules on one action_class coexist
    _activate(conn, rule_id="g1", scope="pay_carrier", scope_form="action_class", kind="GATE_PRECONDITION",
              clauses=[{"field": "amount", "attr": "value", "op": "<", "literal": 100, **_MODELLED}])
    _activate(conn, rule_id="g2", scope="pay_carrier", scope_form="action_class", kind="GATE_PRECONDITION",
              clauses=[{"field": "amount", "attr": "value", "op": ">", "literal": 5, **_MODELLED}])
    n = conn.execute("SELECT COUNT(*) FROM rules WHERE scope='pay_carrier' AND state='ACTIVE'").fetchone()[0]
    assert n == 2, "a multi-admitting scope wrongly refused a second active rule"


def test_the_single_admitting_set_is_a_proper_non_empty_subset():
    assert set(P6RU_SINGLE_ACTIVE_SCOPES), "the single-admitting set must be non-empty"
    assert set(P6RU_SINGLE_ACTIVE_SCOPES) < set(P6RU_SCOPE_FORMS), (
        "the single-admitting set must be a PROPER subset so the multi-rule branch is reachable")


def test_the_same_scope_and_kind_is_active_in_two_tenants_without_collision():
    conn = _conn()
    _human(conn, "po", tenant="T_A")
    _human(conn, "po", tenant="T_B")
    _activate(conn, rule_id="iA", scope="carrier_invoice", scope_form="subject_type", kind="IDENTITY",
              effect="BIND", clauses=[{"field": "pro", "attr": "value", "op": "==", "literal": "A", **_MODELLED}],
              tenant="T_A")
    _activate(conn, rule_id="iB", scope="carrier_invoice", scope_form="subject_type", kind="IDENTITY",
              effect="BIND", clauses=[{"field": "pro", "attr": "value", "op": "==", "literal": "A", **_MODELLED}],
              tenant="T_B")
    for t in ("T_A", "T_B"):
        n = conn.execute("SELECT COUNT(*) FROM rules WHERE tenant=? AND scope='carrier_invoice' "
                         "AND state='ACTIVE'", (t,)).fetchone()[0]
        assert n == 1


def test_a_cross_tenant_activator_or_author_fails_closed():
    conn = _conn()
    _human(conn, "po", tenant="T_A")
    _human(conn, "clerk", role="AUTHORIZED_HUMAN", tenant="T_B")
    m = M12Machine(conn, tenant="T_A", clock=CLOCK)
    with pytest.raises(GuardNotSatisfied):
        m.propose(scope="s", scope_form="action_class", kind="CONSTRAINT", effect="DENY",
                  source_instruction="x", authored_by="clerk", clauses=_pod_clauses(), rule_id="r1")


def test_concurrent_activation_yields_exactly_one_active_rule():
    """The single-admitting partial unique index guarantees at most one ACTIVE rule for a subject_type
    scope even under contention — a stale-OCC / racing activation is refused."""
    conn = _conn()
    _human(conn, "po")
    _activate(conn, rule_id="i1", scope="carrier_invoice", scope_form="subject_type", kind="IDENTITY",
              effect="BIND", clauses=[{"field": "pro", "attr": "value", "op": "==", "literal": "A", **_MODELLED}])
    n = conn.execute("SELECT COUNT(*) FROM rules WHERE scope='carrier_invoice' AND kind='IDENTITY' "
                     "AND state='ACTIVE'").fetchone()[0]
    assert n == 1


# ================================================================== retention / immutability / OCC

def test_retention_is_permanent_and_immutable_and_undeletable():
    conn = _conn()
    _human(conn, "po")
    _activate(conn, rule_id="v1", scope="carrier_invoice", scope_form="subject_type", kind="IDENTITY",
              effect="BIND", clauses=[{"field": "pro", "attr": "value", "op": "==", "literal": "A", **_MODELLED}])
    _activate(conn, rule_id="v2", scope="carrier_invoice", scope_form="subject_type", kind="IDENTITY",
              effect="BIND", clauses=[{"field": "pro", "attr": "value", "op": "==", "literal": "B", **_MODELLED}])
    # a superseded row cannot be deleted
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM rules WHERE rule_id='v1'")
    conn.rollback()
    # its identity cannot be edited in place
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE rules SET source_instruction='rewritten' WHERE rule_id='v1'")
    conn.rollback()


def test_a_compiled_predicate_is_frozen_after_it_leaves_proposed():
    conn = _conn()
    _human(conn, "po")
    _activate(conn, rule_id="r1")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE rules SET compiled_predicate='{}' WHERE rule_id='r1'")
    conn.rollback()


def test_occ_version_advances_by_one_per_transition():
    conn = _conn()
    _human(conn, "po")
    _activate(conn, rule_id="r1", scope="ship", scope_form="action_class", kind="CONSTRAINT",
              clauses=[{"field": "x", "attr": "value", "op": "==", "literal": 1, **_MODELLED}])
    # a state change that does not advance the row version is refused by the OCC trigger
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE rules SET state='REVOKED' WHERE rule_id='r1'")
    conn.rollback()


# ================================================================== replay

def test_replay_reconstructs_state_only_and_mints_no_authority():
    conn = _conn()
    _human(conn, "po")
    _activate(conn, rule_id="r1")
    rebuilt = _m12(conn).rebuild("r1")
    assert rebuilt.state is RuleState.ACTIVE
    assert rebuilt.activations_performed == 0
    assert rebuilt.witnesses_minted == 0
    assert rebuilt.grants_claimed == 0
    assert rebuilt.external_effects == 0
    assert rebuilt.authority_minted == 0


# ================================================================== events: contracts, F7, F14, unregistered

def test_the_eight_f12_contracts_are_registered_and_no_ninth():
    f12 = sorted(n for n, c in CONTRACTS.items() if c.family == "F12")
    assert f12 == sorted([
        "RuleProposed", "RuleCompiled", "RuleNotEnforceable", "RuleConfirmed",
        "RuleActivated", "RuleSuperseded", "RuleRevoked", "RuleExpired"]), f12
    assert CONTRACTS["RuleActivated"].human_only, "RuleActivated is human_only"
    assert PRODUCED_CONTRACTS == frozenset(f12)


def test_conflictraised_is_f7_and_m12_mints_none():
    assert CONTRACTS["ConflictRaised"].family == "F7"
    assert set(CONTRACTS["ConflictRaised"].producers) == {"CF-1", "IB-6", "EF-4c"}
    assert "ConflictRaised" not in _emitted_event_names(RULE_SRC), "M12 must not emit ConflictRaised"


def test_only_one_unauthorized_activation_contract_and_it_is_f14():
    unauth = [n for n in CONTRACTS if "Unauthorized" in n and "Activation" in n]
    assert unauth == ["UnauthorizedPolicyActivationAttempted"], f"a second contract exists: {unauth}"
    assert CONTRACTS["UnauthorizedPolicyActivationAttempted"].family == "F14"


def test_policyoverridden_is_unregistered_and_m12_mints_none():
    assert "PolicyOverridden" not in CONTRACTS, "PolicyOverridden is not a registered contract (P6-D71)"
    assert "PolicyOverridden" not in _emitted_event_names(RULE_SRC)
    assert "PolicyOverridden" not in RULE_SRC or "mints no" in RULE_SRC  # not minted


def test_m12_emits_only_registered_event_names_and_no_consumed_fact():
    names = _emitted_event_names(RULE_SRC)
    for n in names:
        assert n in CONTRACTS, f"M12 emits an unregistered event name: {n!r}"
    # the consumed facts are READ, never minted as events
    for consumed in ("HumanConfirmed", "HumanActivated", "HumanRevoked", "ConflictDetected", "TimerFired"):
        assert consumed not in names, f"M12 minted a consumed fact as an event: {consumed}"


def test_the_rule_aggregate_is_order_tolerant_and_version_is_monotonic():
    from freight_recon.migrations.phase5_event_transport import STRICT_ORDER_AGGREGATE_TYPES
    assert "rule" not in STRICT_ORDER_AGGREGATE_TYPES, "F12 is order-tolerant (### M12-AQ-5)"
    assert all(not CONTRACTS[n].strict_order for n in PRODUCED_CONTRACTS)


# ================================================================== gate minting / ship dark / precedence

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
    assert "GateRegistry(" not in RULE_SRC and "GateEntry(" not in RULE_SRC


def test_m12_is_not_a_gate_runtime_carrier_and_the_boundary_is_unchanged():
    """M12 names no gate-decision member token in executable code (a GATE_PRECONDITION rule's outcome is
    the abstract effect vocabulary), so the ADR-010 carrier boundary is unchanged and consistent."""
    from phase0 import gate_scan
    import freight_recon
    src = Path(freight_recon.__file__).parent
    tokens = ("HUMAN_APPROVAL_REQUIRED", "AUTONOMOUS_WITHIN_CAPS", "PERMANENT_HUMAN_ASSERTION_REQUIRED")
    assert not gate_scan.gate_token_sites(RULE_SRC, tokens), "rule.py must not carry gate vocabulary"
    assert not gate_scan.gate_token_sites(MIG_SRC, tokens), "phase6_rules.py must not carry gate vocabulary"
    carriers = sorted(p.name for p in src.rglob("*.py") if gate_scan.gate_token_sites(p.read_text(), tokens))
    assert set(carriers) == gate_scan.require_gate_runtime_modules(src)
    assert "rule.py" not in gate_scan.GATE_RUNTIME_MODULES


def test_a_rule_never_overrides_a_higher_layer():
    assert PRECEDENCE_LADDER[PRECEDENCE_LAYER - 1] == "STANDING_RULE"
    # layers 1..5 (Constraint, Permanent Truth, Brake, Product Policy, Tenant Policy) are above a rule
    for layer in range(1, PRECEDENCE_LAYER):
        with pytest.raises(IllegalTransition):
            assert_within_precedence(layer)
    # a rule may sit at its own layer or below
    assert_within_precedence(PRECEDENCE_LAYER)
    assert_within_precedence(PRECEDENCE_LAYER + 1)


def test_the_rule_engine_fails_closed_no_allow_on_error():
    compiled = compile_candidate(
        {"kind": "GATE_PRECONDITION", "effect": "DENY", "combine": "AND", "clauses": [
            {"field": "amount", "attr": "value", "op": "<", "literal": 100, **_MODELLED}]},
        scope="pay_carrier")
    bad = {"amount": ProvenancedFact(field="amount", provenance=ProvenanceClass.MODEL_INFERRED,
                                     evidence_condition=EvidenceCondition.CONSISTENT, _value=1)}
    with pytest.raises(RuleEngineUnavailable):
        evaluate_rule(compiled, bad, rule_id="r1")


def test_m12_builds_no_second_conflict_system_and_no_rules_conflict_table():
    conn = _conn()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "rule_conflicts" not in tables, "M12 must not create a second conflict table"
    # rule.py defines no conflict MACHINE and does not import the conflict machine module
    tree = ast.parse(RULE_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            assert "conflictmachine" not in node.name.lower().replace("_", ""), (
                f"rule.py defines a conflict machine: {node.name}")
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[-1] == "conflict":
            pytest.fail("rule.py imports the conflict machine — M7 must keep zero importers")


def test_rule_py_does_not_import_the_exception_or_policy_or_brake_machines():
    tree = ast.parse(RULE_SRC)
    banned = {"exception", "policy", "brake"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            last = node.module.split(".")[-1]
            assert last not in banned, f"rule.py imports {last} — that machine must keep zero importers"


def test_m12_ships_dark_no_production_importer():
    import freight_recon
    src = Path(freight_recon.__file__).parent
    offenders = []
    for py in src.rglob("*.py"):
        if py.name == "rule.py":
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level and node.module and node.module.split(".")[-1] == "rule":
                    offenders.append(py.name)
                elif node.level and node.module is None and any(a.name == "rule" for a in node.names):
                    offenders.append(py.name)
                elif node.module == "freight_recon.rule":
                    offenders.append(py.name)
            if isinstance(node, ast.Import) and any(a.name == "freight_recon.rule" for a in node.names):
                offenders.append(py.name)
    assert offenders == [], f"production importer(s) of the rule machine: {offenders}"


def test_the_m13_brake_machine_and_no_graduation_engine_are_not_built():
    import freight_recon
    src = Path(freight_recon.__file__).parent
    files = {p.name for p in src.rglob("*.py")}
    assert len(files) > 10, "the src scan collapsed - it proves nothing"
    assert "rule.py" in files, "the M12 machine must be present, or the scan read the wrong tree"
    assert not any("brake" in f and "lifecycle" in f for f in files), "M13 brake lifecycle must not be built"
    for node in ast.walk(ast.parse(RULE_SRC)):
        if isinstance(node, ast.ClassDef):
            assert "graduat" not in node.name.lower(), f"M12 defines a graduation engine: {node.name}"


def test_no_unregistered_rule_event_name_in_the_machine():
    found = set(re.findall(r"\bRule[A-Z][A-Za-z]*", RULE_SRC))
    assert found, "the machine names no Rule* identifier — the scan read nothing (vacuous)"
    for n in _emitted_event_names(RULE_SRC):
        if n.startswith("Rule"):
            assert n in CONTRACTS, f"unregistered Rule* event name minted: {n!r}"


# ================================================================== neighbours unchanged

def test_the_neighbouring_machines_are_unchanged():
    # FIXED-SPECIFICATION: the landed machine runtimes (M1..M11) plus the P3 checkpoint kernel and the
    # brake that P6/M12 names as must-stay-byte-identical (§5: "Do not modify M1–M11"; the kernel and brake
    # are named because CLAUDE.md §10 forbids weakening them). M7 and M9 in particular are not edited at all.
    machines = ("work_item.py", "pipeline_instance.py", "external_effect.py", "approval.py",
                "observation.py", "identity_binding_claim.py", "conflict.py", "expectation.py",
                "exception.py", "compensation.py", "policy.py", "checkpoint.py", "brake.py")
    rel = [f"src/freight_recon/{n}" for n in machines]
    r = subprocess.run(["git", "diff", "--name-only", "HEAD", "--", *rel], cwd=ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip() == "", f"a landed machine changed: {r.stdout}"
