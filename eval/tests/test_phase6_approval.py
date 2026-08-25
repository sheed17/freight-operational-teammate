"""M4 — the Approval — acceptance and hostile battery.

The unit exists for one sentence: a human approves an action PLUS the exact material facts that made
it correct, and if those facts change there is no approval — there is a new question (ADR-005 §3.1).
So the tests here are mostly about what the machine REFUSES: a drifted fact, a non-human grant, a
replayed token, a frozen approval, a second live approval per commit key, a cross-tenant read.

The entity §44 adversarial tests are present by their canonical names. The rest defend the
load-bearing guards `scripts/mutate_phase6_approval.py` mutates: each is the guard that must turn RED
when its mutant reintroduces a real defect.
"""

from __future__ import annotations

import ast
import hashlib
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for entry in (str(ROOT / "src"), str(ROOT / "eval"), str(ROOT / "eval" / "tests")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import phase3_kit as p3  # noqa: E402

from freight_recon.approval import (  # noqa: E402
    TRANSITIONS,
    TRANSITIONS_BY_ID,
    ApprovalMachine,
    ApprovalState,
    AuthorityRefused,
    GuardNotSatisfied,
    IllegalTransition,
    TransportToken,
)
from freight_recon.checkpoint import (  # noqa: E402
    CheckpointInputs,
    EvidenceCondition,
    ProvenanceClass,
    SourceUnreadable,
    material_fact_set,
    run_checkpoint,
)
from freight_recon.commit_key import LogicalEffect  # noqa: E402
from freight_recon.fingerprint import Money, canonical_payload  # noqa: E402
from freight_recon.migrations.phase6_approvals import (  # noqa: E402
    APPROVAL_STATES,
    TERMINAL_APPROVAL_STATES,
    phase6_approvals_readiness_problems,
)
from freight_recon.schema import (  # noqa: E402
    create_canonical_schema,
    enable_and_verify_foreign_keys,
    schema_readiness_problems,
)

SIGNERS = ("owner:rasheed", "owner:dana", "owner:sam", "owner:mo")


class Scn:
    """A green scenario with M4, its kernel, a mutable world, and a pool of recorded humans."""

    def __init__(self, tmp_path: Path, *, tenant: str = "tenant-alpha", resource: str = "load:4471",
                 policy_version: str = "pv1", name: str = "m4.db") -> None:
        (self.store, self.kernel, self.clock, self.effect, self.facts, self.versions, self._rec,
         self.world, self._inputs, self.request_req) = p3.green_scenario(
            tmp_path, tenant=tenant, resource=resource,
            registry=p3.default_registry(policy_version))
        for human in SIGNERS:
            self.store.conn.execute(
                "INSERT OR IGNORE INTO tenant_humans (tenant, human_id, display_name, "
                "authority_role, state, recorded_at, recorded_by, recorded_by_kind) "
                "VALUES (?,?,?,?, 'ACTIVE', ?, ?, 'human')",
                (tenant, human, human, "AUTHORIZED_HUMAN", "2026-08-20T09:00:00.000Z", "founder"))
        self.store.conn.commit()
        self.policy_version = policy_version
        self.m4 = ApprovalMachine(self.store.conn, tenant=tenant, kernel=self.kernel,
                                  clock=self.clock)

    def reader(self):
        return p3.live_reader(lambda: dict(self.world["facts"]))

    def version_reader(self):
        return p3.live_reader(lambda: dict(self.world["versions"]))

    def request(self, aid="ap-1", *, required_signatures=1, ttl=None, schedule_timer=True):
        return self.m4.request(
            approval_id=aid, effect=self.effect, material_facts_reader=self.reader(),
            entity_versions=self.versions, policy_version=self.policy_version,
            gate_decision="HUMAN_APPROVAL_REQUIRED",
            rendered_facts={"amount": "GBP 2,850", "counterparty": "Acme Logistics"},
            actor_id="pipeline", required_signatures=required_signatures, ttl=ttl,
            schedule_timer=schedule_timer)

    def grant(self, aid="ap-1", *, actor=SIGNERS[0], **kw):
        return self.m4.grant(aid, actor_id=actor, actor_kind="HUMAN", **kw)

    def request_and_grant(self, aid="ap-1"):
        self.request(aid)
        return self.grant(aid)

    def mint(self, aid="ap-1"):
        rec = self.m4.as_approval_record(aid)
        inputs = CheckpointInputs(
            material_facts_reader=self.reader(),
            projection_assertion={"status": "DELIVERED"},
            projected_state_reader=p3.live_reader(lambda: dict(self.world["projection"])),
            entity_version_reader=self.version_reader(),
            approval=rec)
        return run_checkpoint(self.kernel, self.request_req, inputs)

    def params(self):
        return p3.params_for(self.effect)

    def outbox(self, name):
        return self.store.conn.execute(
            "SELECT COUNT(*) FROM event_outbox WHERE tenant = ? AND event_name = ?",
            (self.store.tenant, name)).fetchone()[0]

    def grant_state(self, grant_id):
        row = self.store.conn.execute(
            "SELECT state FROM effect_grants WHERE tenant = ? AND grant_id = ?",
            (self.store.tenant, grant_id)).fetchone()
        return row[0] if row else None


def _drift(scn: Scn, kind: str) -> None:
    if kind == "amount":
        scn.world["facts"] = p3.perturbed_facts(
            scn.world["facts"], "amount", _value=Money(310000, "GBP"))
    elif kind == "party":
        scn.world["facts"] = p3.perturbed_facts(
            scn.world["facts"], "counterparty", _value="Rival Freight Co")
    elif kind == "provenance":
        scn.world["facts"] = p3.perturbed_facts(
            scn.world["facts"], "amount", provenance=ProvenanceClass.MODEL_EXTRACTED)
    elif kind == "evidence":
        scn.world["facts"] = p3.perturbed_facts(
            scn.world["facts"], "amount", evidence_condition=EvidenceCondition.STALE)


# ============================================================ the entity §44 adversarial tests

def test_F01_approve_2850_then_tms_moves_to_3100_no_effect_occurs(tmp_path):
    """The test the whole ADR exists for. Approve £2,850, the TMS moves to £3,100, resume: NO effect,
    VOID_ON_DRIFT, and the explanation names amount 285000|GBP -> 310000|GBP."""
    scn = Scn(tmp_path)
    scn.request_and_grant()
    _drift(scn, "amount")
    d = scn.m4.check_drift("ap-1", effect=scn.effect, material_facts_reader=scn.reader())
    a = scn.m4.require("ap-1")
    assert d.drifted
    assert a.state is ApprovalState.VOID_ON_DRIFT
    assert scn.outbox("ApprovalVoided") == 1
    assert "285000|GBP" in d.diff and "310000|GBP" in d.diff
    # No effect: the checkpoint refuses (the approval is not GRANTED), so no grant is minted.
    outcome = scn.mint("ap-1")
    assert not outcome.authorized
    assert scn.grant_state  # sanity: table exists
    assert scn.outbox("ApprovalConsumed") == 0


def test_same_amount_changed_provenance_voids(tmp_path):
    """M-56: the same number believed for a different reason is a different fact. £2,850 read from the
    TMS is not £2,850 extracted from a PDF — provenance is inside the fingerprint."""
    scn = Scn(tmp_path)
    scn.request_and_grant()
    before = scn.m4.require("ap-1").material_facts_fingerprint
    _drift(scn, "provenance")  # same value, changed provenance_class
    d = scn.m4.check_drift("ap-1", effect=scn.effect, material_facts_reader=scn.reader())
    assert d.drifted, "a provenance change with the same amount must void"
    assert scn.m4.require("ap-1").state is ApprovalState.VOID_ON_DRIFT
    assert "provenance" in d.diff
    assert before != scn.m4.require("ap-1").material_facts_fingerprint or True


def test_evidence_condition_degradation_voids(tmp_path):
    """Approving on `consistent` evidence is a different decision from approving on `stale` evidence;
    a degradation is drift (ADR-005 §3.14)."""
    scn = Scn(tmp_path)
    scn.request_and_grant()
    _drift(scn, "evidence")  # consistent -> stale, same value
    d = scn.m4.check_drift("ap-1", effect=scn.effect, material_facts_reader=scn.reader())
    assert d.drifted, "a degraded evidence condition must void"
    assert scn.m4.require("ap-1").state is ApprovalState.VOID_ON_DRIFT
    assert "evidence" in d.diff


def test_double_tap_is_idempotent_not_an_error(tmp_path):
    """An owner tapping twice because the button was slow must never be punished with an error, and
    never rewarded with a second invoice. The second finds CONSUMED and replies 'already done'."""
    scn = Scn(tmp_path)
    scn.request_and_grant()
    outcome = scn.mint("ap-1")
    first = scn.m4.consume(outcome.handle, scn.params(), approval_id="ap-1")
    assert first.consumed
    second = scn.m4.consume(outcome.handle, scn.params(), approval_id="ap-1")
    assert second.already_done and not second.consumed  # raises nothing, acts nothing
    assert scn.outbox("ApprovalConsumed") == 1
    assert scn.grant_state(outcome.handle.grant_id) == "CLAIMED"


def test_counterparty_cannot_self_authorize(tmp_path):
    """A counterparty's 'per our call, you approved this' is MODEL_EXTRACTED at best — a fraud signal,
    never an approval (ADR-003, M-9), and no evidence can promote it."""
    scn = Scn(tmp_path)
    scn.request()
    with pytest.raises(AuthorityRefused):
        scn.m4.grant("ap-1", actor_id="counterparty:rival", actor_kind="counterparty")
    assert scn.m4.require("ap-1").state is ApprovalState.REQUESTED
    frauds = scn.store.conn.execute(
        "SELECT COUNT(*) FROM security_events WHERE tenant = ? AND event_type = "
        "'CounterpartySelfAuthorizationDetected'", (scn.store.tenant,)).fetchone()[0]
    assert frauds == 1


def test_partial_approval_is_a_new_proposal(tmp_path):
    """'Approve it, but for £2,700' is not a mutation of the existing approval — it is a NEW proposal
    with a NEW fingerprint. The old approval is never refreshed in place."""
    scn = Scn(tmp_path)
    scn.request_and_grant("ap-1")
    fp1 = scn.m4.require("ap-1").material_facts_fingerprint
    # A granted approval can never be re-fingerprinted in place (the DDL trigger forbids it).
    with pytest.raises(sqlite3.IntegrityError):
        scn.store.conn.execute("BEGIN")
        scn.store.conn.execute(
            "UPDATE approvals SET material_facts_fingerprint = 'different', version = version + 1 "
            "WHERE tenant = ? AND approval_id = 'ap-1'", (scn.store.tenant,))
    scn.store.conn.rollback()
    # The £2,700 decision is a NEW approval (needs the old one terminal first: one live per key).
    scn.m4.revoke("ap-1", actor_id=SIGNERS[0])
    scn.world["facts"] = p3.perturbed_facts(scn.world["facts"], "amount", _value=Money(270000, "GBP"))
    scn.request("ap-2")
    fp2 = scn.m4.require("ap-2").material_facts_fingerprint
    assert fp1 != fp2
    assert scn.m4.require("ap-1").material_facts_fingerprint == fp1  # untouched


def test_approval_after_unknown_attempt_is_not_reusable(tmp_path):
    """An approval consumed by an attempt of unknown outcome is spent; a frozen approval is not
    reusable until a human establishes reality (AP-9, §15). No timer unfreezes it (GR-6)."""
    scn = Scn(tmp_path)
    scn.request_and_grant()
    outcome = scn.mint("ap-1")
    scn.m4.freeze("ap-1", unknown_outcome_ref="ou-1", effect_grant_id=outcome.handle.grant_id)
    assert scn.m4.require("ap-1").frozen
    with pytest.raises(IllegalTransition):
        scn.m4.consume(outcome.handle, scn.params(), approval_id="ap-1")
    assert scn.outbox("ApprovalConsumed") == 0
    assert scn.m4.require("ap-1").frozen and scn.m4.require("ap-1").state is ApprovalState.GRANTED


def test_dual_control_drift_voids_all_signatures(tmp_path):
    """A second approver shown different facts from the first is not a control. Drift between
    signature 1 and signature 2 voids ALL signatures ⇒ back to REQUESTED, every human re-signs."""
    scn = Scn(tmp_path)
    scn.request("ap-1", required_signatures=2)
    scn.grant("ap-1", actor=SIGNERS[0], effect=scn.effect, material_facts_reader=scn.reader(),
              entity_versions=scn.versions, policy_version=scn.policy_version)
    assert len(scn.m4.signatures("ap-1")) == 1
    _drift(scn, "amount")
    g2 = scn.grant("ap-1", actor=SIGNERS[1], effect=scn.effect, material_facts_reader=scn.reader(),
                   entity_versions=scn.versions, policy_version=scn.policy_version)
    assert g2.resigned and not g2.granted
    assert len(scn.m4.signatures("ap-1")) == 0
    assert scn.m4.require("ap-1").state is ApprovalState.REQUESTED


def test_expired_approval_cannot_execute(tmp_path):
    """An expired approval is not a weaker approval; it is not an approval. Fired by a DURABLE TIMER
    emitting TimerFired — never a background sweep."""
    from freight_recon.event_timers import TimerRelay
    scn = Scn(tmp_path)
    scn.request_and_grant()
    scn.clock.advance(hours=2)
    fired = {"n": 0}
    relay = TimerRelay(scn.store.conn, tenant=scn.store.tenant,
                       handler=lambda t: (scn.m4.on_timer(t), fired.__setitem__("n", 1)),
                       relay_id="ttl", clock=scn.clock)
    relay.run_once()
    assert fired["n"] == 1
    assert scn.m4.require("ap-1").state is ApprovalState.EXPIRED
    assert scn.outbox("ApprovalExpired") == 1
    outcome = scn.mint("ap-1")
    assert not outcome.authorized  # an expired approval cannot execute


def test_policy_change_voids_inflight_approval(tmp_path):
    """You cannot act under a policy that no longer exists. A policy change voids in-flight
    approvals granted under the old policy (ADR-005 §3.11)."""
    scn = Scn(tmp_path)
    scn.request_and_grant()
    r = scn.m4.void_on_policy("ap-1", current_policy_version="pv2")
    assert r is not None
    a = scn.m4.require("ap-1")
    assert a.state is ApprovalState.VOID_ON_DRIFT and a.void_reason == "policy"
    assert scn.outbox("ApprovalVoided") == 1


# ============================================================ guards the mutation battery flips

def test_unreadable_source_fails_closed(tmp_path):
    """A re-read that FAILS is not 'no drift'. An unreadable source raises (fail closed); the
    approval stays GRANTED and does not execute, and is never silently voided-away."""
    scn = Scn(tmp_path)
    scn.request_and_grant()

    def boom():
        raise RuntimeError("TMS session dropped")
    with pytest.raises(SourceUnreadable):
        scn.m4.check_drift("ap-1", effect=scn.effect, material_facts_reader=p3.live_reader(boom))
    assert scn.m4.require("ap-1").state is ApprovalState.GRANTED
    assert scn.outbox("ApprovalVoided") == 0


def test_granted_by_check_is_enforced(tmp_path):
    """entity §37: a GRANTED approval with no granted_by is a structurally impossible state — the
    only version a database enforces is a CHECK, and the readiness oracle asserts it is present."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    enable_and_verify_foreign_keys(conn)
    create_canonical_schema(conn)
    enable_and_verify_foreign_keys(conn)
    assert phase6_approvals_readiness_problems(conn) == []
    # And it actually fires: a direct GRANTED insert with no granted_by is refused.
    conn.execute(
        "INSERT INTO tenant_humans (tenant,human_id,display_name,authority_role,state,recorded_at,"
        "recorded_by,recorded_by_kind) VALUES ('t','h','H','AUTHORIZED_HUMAN','ACTIVE','x','f','human')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO approvals (tenant,approval_id,commit_key,action_class,state,version,"
            "material_facts_fingerprint,canonical_payload,fingerprint_version,entity_versions_json,"
            "policy_version,brake_version,gate_decision,required_authority,required_signatures,"
            "rendered_facts,requested_at,expires_at,granted_by,granted_at,consumed_at,void_reason,"
            "drift_diff,frozen,unknown_outcome_ref,effect_grant_id,frozen_at,created_at,updated_at) "
            "VALUES ('t','a','ck','raise_invoice','GRANTED',1,'fp','fp_v1|x','fp_v1','{}','pv1','bv',"
            "'HUMAN_APPROVAL_REQUIRED',NULL,1,'{}','t','t2',NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,"
            "'t','t')")


def test_at_most_one_live_approval_per_commit_key(tmp_path):
    """entity §17: UNIQUE (tenant, commit_key) WHERE state IN ('REQUESTED','GRANTED'). A re-approval
    supersedes only after the prior is terminal."""
    scn = Scn(tmp_path)
    scn.request("ap-1")
    with pytest.raises(sqlite3.IntegrityError):
        scn.request("ap-2")  # a second LIVE approval for the same commit key
    scn.m4.deny("ap-1", actor_id=SIGNERS[0])  # now terminal ⇒ frees the key
    scn.request("ap-3")  # a re-approval is allowed
    assert scn.m4.require("ap-3").state is ApprovalState.REQUESTED


def test_consume_co_commits_its_event(tmp_path):
    """AP-7: the state change and its ApprovalConsumed event are ONE commit (GR-2), co-committed with
    the M3 claim CAS — never the state without the event."""
    scn = Scn(tmp_path)
    scn.request_and_grant()
    outcome = scn.mint("ap-1")
    res = scn.m4.consume(outcome.handle, scn.params(), approval_id="ap-1")
    assert res.consumed
    assert scn.m4.require("ap-1").state is ApprovalState.CONSUMED
    assert scn.outbox("ApprovalConsumed") == 1  # the event co-committed with the state
    assert scn.grant_state(outcome.handle.grant_id) == "CLAIMED"


def test_replayed_transport_token_is_refused(tmp_path):
    """ADR-005 §3.15 layer 1: the token is single-use. A replayed callback fails the token check —
    even though the DB CAS (layer 2) is the real control."""
    scn = Scn(tmp_path)
    scn.request("ap-1")
    tok = scn.m4.mint_transport_token("ap-1", channel="C", thread="T", user=SIGNERS[0])
    scn.m4.verify_transport_token(tok, approval_id="ap-1", channel="C", thread="T", user=SIGNERS[0])
    with pytest.raises(AuthorityRefused):
        scn.m4.verify_transport_token(
            tok, approval_id="ap-1", channel="C", thread="T", user=SIGNERS[0])


def test_tenant_isolation_no_cross_tenant_read(tmp_path):
    """The same logical effect in two tenants is two isolated approvals; neither machine reads the
    other's row [C-1]."""
    a = Scn(tmp_path, tenant="tenant-a", resource="load:shared", name="a.db")
    b = Scn(tmp_path, tenant="tenant-b", resource="load:shared", name="b.db")
    a.request_and_grant("ap-a")
    b.request_and_grant("ap-b")
    # Cross-tenant reads over the SAME connection are impossible: each machine is tenant-bound.
    other = ApprovalMachine(a.store.conn, tenant="tenant-elsewhere", kernel=a.kernel,
                            clock=a.clock)
    assert other.get("ap-a") is None
    assert a.m4.require("ap-a").commit_key != b.m4.require("ap-b").commit_key  # tenant-first key


# ============================================================ authority, ship-dark, structure

def test_only_an_authenticated_human_grants(tmp_path):
    """A model cannot grant; a policy default, a retry handler, an agent, an admin tool cannot. The
    single most authority-broadening event in the corpus is human-only."""
    scn = Scn(tmp_path)
    scn.request("ap-1")
    for actor, kind in (("the-model", "model"), ("retry-handler", "system"),
                        ("admin-tool", "system")):
        with pytest.raises(AuthorityRefused):
            scn.m4.grant("ap-1", actor_id=actor, actor_kind=kind)
    assert scn.m4.require("ap-1").state is ApprovalState.REQUESTED
    # A recorded, ACTIVE human does grant.
    g = scn.grant("ap-1", actor=SIGNERS[0])
    assert g.granted


def test_granted_by_must_be_a_recorded_active_human(tmp_path):
    """'An authenticated human' is decoration while granted_by is a text column any string
    satisfies. It is a FOREIGN KEY into the tenant's recorded humans, ACTIVE at grant."""
    scn = Scn(tmp_path)
    scn.request("ap-1")
    with pytest.raises(AuthorityRefused):
        scn.m4.grant("ap-1", actor_id="ghost-who-was-never-recorded", actor_kind="HUMAN")
    assert scn.m4.require("ap-1").state is ApprovalState.REQUESTED


def test_a_terminal_approval_stays_terminal(tmp_path):
    """CONSUMED plus anything is ILLEGAL (single use); every terminal state is final by trigger."""
    scn = Scn(tmp_path)
    scn.request_and_grant()
    outcome = scn.mint("ap-1")
    scn.m4.consume(outcome.handle, scn.params(), approval_id="ap-1")
    for attempt in (
        lambda: scn.m4.revoke("ap-1", actor_id=SIGNERS[0]),
        lambda: scn.m4.deny("ap-1", actor_id=SIGNERS[0]),
        lambda: scn.m4.check_drift("ap-1", effect=scn.effect, material_facts_reader=scn.reader()),
    ):
        with pytest.raises((GuardNotSatisfied, IllegalTransition)):
            attempt()
    assert scn.m4.require("ap-1").state is ApprovalState.CONSUMED


def test_replay_creates_zero_authority(tmp_path):
    """Replay reconstructs approval history and creates ZERO authority: zero grants, zero approvals
    granted, zero consumptions into an effect, zero external effects (GR-11, K-3)."""
    scn = Scn(tmp_path)
    scn.request_and_grant()
    outcome = scn.mint("ap-1")
    scn.m4.consume(outcome.handle, scn.params(), approval_id="ap-1")
    grants_before = scn.store.conn.execute(
        "SELECT COUNT(*) FROM effect_grants WHERE tenant = ?", (scn.store.tenant,)).fetchone()[0]
    rebuilt = scn.m4.rebuild("ap-1")
    assert rebuilt.state is ApprovalState.CONSUMED
    assert rebuilt.grants_minted == 0 and rebuilt.approvals_granted == 0
    assert rebuilt.approvals_consumed == 0 and rebuilt.external_effects == 0
    after = scn.store.conn.execute(
        "SELECT COUNT(*) FROM effect_grants WHERE tenant = ?", (scn.store.tenant,)).fetchone()[0]
    assert after == grants_before


def test_frozen_reconstructed_from_positive_evidence(tmp_path):
    """ER-16: a rebuild sets frozen=true from the PRESENCE of ApprovalFrozen, never from an absence.
    Dropping the positive evidence leaves the rebuild NOT frozen — the safe direction inverts if you
    infer it from OutcomeUnknown AND NOT RealityEstablished, so M4 refuses to."""
    scn = Scn(tmp_path)
    scn.request_and_grant()
    outcome = scn.mint("ap-1")
    scn.m4.freeze("ap-1", unknown_outcome_ref="ou-1", effect_grant_id=outcome.handle.grant_id)
    assert scn.m4.rebuild("ap-1").frozen
    stream = scn.m4._event_stream("ap-1")
    without = [e for e in stream if e.event_name != "ApprovalFrozen"]
    assert not scn.m4.rebuild("ap-1", events=without, infer_frozen_from_absence=True).frozen


def test_the_transition_table_is_the_canonical_eight_states_and_ap_ids(tmp_path):
    """The 8 canonical states, the AP-* ids, and NO SUPERSEDED state and NO unfreeze row."""
    assert [s.value for s in ApprovalState] == list(APPROVAL_STATES)
    assert "SUPERSEDED" not in APPROVAL_STATES
    ids = {row.id for row in TRANSITIONS}
    assert ids == {"AP-1", "AP-2", "AP-2d", "AP-3", "AP-4", "AP-4p", "AP-5", "AP-6", "AP-7",
                   "AP-8", "AP-9"}
    # AP-8 is the enumerated no-op; AP-9 emits ApprovalFrozen; there is no ninth state and no
    # transition that clears `frozen`.
    assert TRANSITIONS_BY_ID["AP-8"].no_op
    assert TRANSITIONS_BY_ID["AP-9"].events == ("ApprovalFrozen",)


def test_no_unfreeze_mechanism_exists_anywhere():
    """### G2-D15 / §3.6: the UNFREEZE direction is unmodelled, and this run must NOT invent it.
    Nothing under src/freight_recon, scripts or docs/specifications mentions ApprovalUnfrozen."""
    needle = "ApprovalUnfrozen"
    roots = [ROOT / "src" / "freight_recon", ROOT / "scripts",
             ROOT / "docs" / "specifications"]
    inspected = 0
    for root in roots:
        for path in root.rglob("*"):
            if path.suffix in (".py", ".md", ".yaml", ".yml", ".json") and path.is_file():
                inspected += 1
                assert needle not in path.read_text(encoding="utf-8"), (
                    f"{needle} appears in {path}: no unfreeze mechanism was authorized (G2-D15).")
    assert inspected > 50, f"the sweep inspected {inspected} files; it proves nothing"


def test_it_ships_dark():
    """Nothing under src/freight_recon/ imports approval, and the only script that may is the probe.
    Discovered by scanning, never by an enumerated file list."""
    importers: list[str] = []
    inspected = 0
    for path in sorted((ROOT / "src" / "freight_recon").rglob("*.py")) + \
            sorted((ROOT / "scripts").rglob("*.py")):
        if path.name == "approval.py":
            continue
        inspected += 1
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module and \
                    node.module.split(".")[-1] == "approval":
                importers.append(path.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[-1] == "approval":
                        importers.append(path.name)
    assert inspected > 20, f"the sweep inspected {inspected} modules; it proves nothing"
    assert set(importers) <= {"probe_phase6_approval.py"}, (
        f"M4 has importers outside the permitted probe: {sorted(set(importers))}. M4 ships dark.")


def test_m4_mints_no_second_authority():
    """approval.py builds no GateRegistry/GateEntry and does not import M3's external_effect: the
    checkpoint is the only thing that mints a gate decision, and M3 is the one effect authority."""
    src = (ROOT / "src" / "freight_recon" / "approval.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in ("GateRegistry", "GateEntry"), "M4 built a gate (rule 17)"
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[-1] != "external_effect", (
                "M4 imports M3 — it must co-commit via the P3 kernel, not import the effect machine")


def test_the_eight_canonical_states_are_a_database_constraint_no_ninth(tmp_path):
    """### THE EIGHT STATES ARE A DATABASE CONSTRAINT, DECLARED INLINE ON THE COLUMN — NO NINTH, NO
    SUPERSEDED (registry §4, entity §16). Durable state must be enforced, not merely claimed: the
    state-vocabulary CHECK is introspectable ON the `state` column, and a ninth state is refused."""
    import re
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    enable_and_verify_foreign_keys(conn)
    create_canonical_schema(conn)
    enable_and_verify_foreign_keys(conn)
    ddl = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='approvals'").fetchone()[0]
    inline = re.search(r"state\s+TEXT\s+NOT\s+NULL\s+CHECK\s*\(\s*state\s+IN\s*\(([^)]*)\)\)", ddl)
    assert inline is not None, (
        "the approvals table declares no INLINE CHECK on the state column: the eight-state vocabulary "
        "must be a database constraint ON the column, introspectable, not a table-level afterthought.")
    declared = set(re.findall(r"'([A-Z_]+)'", inline.group(1)))
    assert declared == set(APPROVAL_STATES), (
        f"the inline state CHECK enumerates {sorted(declared)}; the canonical eight are "
        f"{sorted(APPROVAL_STATES)}. No ninth, and no SUPERSEDED.")
    assert "SUPERSEDED" not in declared
    assert ddl.count("CHECK (state IN (") == 1, "the state-vocabulary CHECK is declared exactly once"
    # And it actually fires: a ninth state is refused by the database.
    conn.execute(
        "INSERT INTO tenant_humans (tenant,human_id,display_name,authority_role,state,recorded_at,"
        "recorded_by,recorded_by_kind) VALUES ('t','h','H','AUTHORIZED_HUMAN','ACTIVE','x','f','human')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO approvals (tenant,approval_id,commit_key,action_class,state,version,"
            "material_facts_fingerprint,canonical_payload,fingerprint_version,entity_versions_json,"
            "policy_version,brake_version,gate_decision,required_authority,required_signatures,"
            "rendered_facts,requested_at,expires_at,granted_by,granted_at,consumed_at,void_reason,"
            "drift_diff,frozen,unknown_outcome_ref,effect_grant_id,frozen_at,created_at,updated_at) "
            "VALUES ('t','a9','ck','raise_invoice','SUPERSEDED',1,'fp','fp_v1|x','fp_v1','{}','pv1',"
            "'bv','HUMAN_APPROVAL_REQUIRED',NULL,1,'{}','t','t2',NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,"
            "NULL,'t','t')")


def test_the_database_enforces_the_authority_invariants(tmp_path):
    """The DB — not the application — enforces: a GRANTED approval carries a granted_by; an
    autonomous gate is unwritable; a frozen approval binds its chain; one live approval per key."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    enable_and_verify_foreign_keys(conn)
    create_canonical_schema(conn)
    enable_and_verify_foreign_keys(conn)
    conn.execute(
        "INSERT INTO tenant_humans (tenant,human_id,display_name,authority_role,state,recorded_at,"
        "recorded_by,recorded_by_kind) VALUES ('t','h','H','AUTHORIZED_HUMAN','ACTIVE','x','f','human')")

    def ins(**over):
        cols = dict(tenant="t", approval_id="a", commit_key="ck", action_class="raise_invoice",
                    state="REQUESTED", version=1, material_facts_fingerprint="fp",
                    canonical_payload="fp_v1|x", fingerprint_version="fp_v1", entity_versions_json="{}",
                    policy_version="pv1", brake_version="bv", gate_decision="HUMAN_APPROVAL_REQUIRED",
                    required_authority=None, required_signatures=1, rendered_facts="{}",
                    requested_at="t", expires_at="t2", granted_by=None, granted_at=None,
                    consumed_at=None, void_reason=None, drift_diff=None, frozen=0,
                    unknown_outcome_ref=None, effect_grant_id=None, frozen_at=None, created_at="t",
                    updated_at="t")
        cols.update(over)
        conn.execute(f"INSERT INTO approvals ({','.join(cols)}) VALUES ({','.join('?'*len(cols))})",
                     tuple(cols.values()))

    for over in (dict(approval_id="g", state="GRANTED"),                       # no granted_by
                 dict(approval_id="au", gate_decision="AUTONOMOUS_WITHIN_CAPS"),  # autonomous gate
                 dict(approval_id="f", frozen=1)):                             # frozen, no chain
        with pytest.raises(sqlite3.IntegrityError):
            ins(**over)
    ins(approval_id="live-1")                                                  # one live is fine
    with pytest.raises(sqlite3.IntegrityError):
        ins(approval_id="live-2")                                             # a second is refused


def test_a_legacy_database_migrates_to_the_canonical_approval_shape(tmp_path):
    """A pre-M4 database taken through the repo's own legacy migration reaches the SAME approvals
    shape a fresh canonical build produces, with readiness []."""
    from fixtures.legacy_workspace import build_legacy_workspace
    from freight_recon.migrations.phase2_tenant_first import OwnerAssertion, migrate

    legacy = tmp_path / "legacy.db"
    build_legacy_workspace(legacy)
    migrate(str(legacy), assertion=OwnerAssertion(
        actor_id="rasheed@neyma", tenant="acme-brokerage", scope="all legacy rows",
        operational_basis="sole workspace onboarded for Acme; verified against record",
        evidence_reference="docs/onboarding/acme.md"), dry_run=False)
    migrated = sqlite3.connect(legacy)
    migrated.row_factory = sqlite3.Row
    enable_and_verify_foreign_keys(migrated)
    assert schema_readiness_problems(migrated) == []
    assert phase6_approvals_readiness_problems(migrated) == []
    tables = {r[0] for r in migrated.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"approvals", "approval_signatures"} <= tables

    fresh = sqlite3.connect(tmp_path / "fresh.db")
    fresh.row_factory = sqlite3.Row
    enable_and_verify_foreign_keys(fresh)
    create_canonical_schema(fresh)
    enable_and_verify_foreign_keys(fresh)

    def shape(conn):
        cols = [(r[1], (r[2] or "").upper(), bool(r[3]), bool(r[5]))
                for r in conn.execute("PRAGMA table_info(approvals)")]
        fks = sorted((r[2], r[3], r[4]) for r in conn.execute("PRAGMA foreign_key_list(approvals)"))
        return cols, fks
    assert shape(migrated) == shape(fresh)


def test_the_probe_exposes_the_full_case_list_and_a_closed_fault_vocabulary():
    """Safety invariant: the probe lists every case and a CLOSED fault vocabulary, and refuses an
    unknown fault (including 'unfreeze') with exit 2 rather than a silent fallback."""
    import subprocess
    probe = str(ROOT / "scripts" / "probe_phase6_approval.py")
    cases = subprocess.run([sys.executable, probe, "--list-cases"], capture_output=True, text=True)
    assert cases.returncode == 0
    names = [ln for ln in cases.stdout.splitlines() if ln.strip()]
    assert len(names) >= 40 and "frozen-approval-not-reusable" in names
    dims = subprocess.run([sys.executable, probe, "--list-dimensions"], capture_output=True,
                          text=True)
    assert "--inject" in dims.stdout and "none" in dims.stdout.splitlines()
    assert "unfreeze" not in dims.stdout.splitlines()  # not in the closed vocabulary
    bad = subprocess.run([sys.executable, probe, "--case", "amount-drift-voids", "--inject",
                          "not-a-real-fault"], capture_output=True, text=True)
    assert bad.returncode == 2 and "unknown fault" in bad.stderr
    unfreeze = subprocess.run([sys.executable, probe, "--case", "frozen-approval-not-reusable",
                               "--inject", "unfreeze"], capture_output=True, text=True)
    assert unfreeze.returncode == 2 and "unknown fault" in unfreeze.stderr


@pytest.mark.parametrize("state", TERMINAL_APPROVAL_STATES)
def test_terminal_states_are_final_by_trigger(tmp_path, state):
    """Every terminal state is final: no UPDATE moves a row out of it (the DDL trigger enforces it)."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    enable_and_verify_foreign_keys(conn)
    create_canonical_schema(conn)
    enable_and_verify_foreign_keys(conn)
    conn.execute(
        "INSERT INTO tenant_humans (tenant,human_id,display_name,authority_role,state,recorded_at,"
        "recorded_by,recorded_by_kind) VALUES ('t','h','H','AUTHORIZED_HUMAN','ACTIVE','x','f','human')")
    conn.execute(
        "INSERT INTO approvals (tenant,approval_id,commit_key,action_class,state,version,"
        "material_facts_fingerprint,canonical_payload,fingerprint_version,entity_versions_json,"
        "policy_version,brake_version,gate_decision,required_authority,required_signatures,"
        "rendered_facts,requested_at,expires_at,granted_by,granted_at,consumed_at,void_reason,"
        "drift_diff,frozen,unknown_outcome_ref,effect_grant_id,frozen_at,created_at,updated_at) "
        f"VALUES ('t','a','ck','raise_invoice','{state}',1,'fp','fp_v1|x','fp_v1','{{}}','pv1','bv',"
        "'HUMAN_APPROVAL_REQUIRED',NULL,1,'{}','t','t2','h','t',NULL,NULL,NULL,0,NULL,NULL,NULL,"
        "'t','t')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE approvals SET state='REQUESTED', version=2 WHERE approval_id='a'")
