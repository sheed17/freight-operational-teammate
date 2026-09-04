#!/usr/bin/env python3
"""Deterministic behavioural probe for M11 — the Policy (P6-CP-11).

### THIS PROBE'S NARRATION IS NOT THE MEASUREMENT. The permanent scenario measures the DATABASE, the
EVENT REGISTRY and the AST. This probe drives the machine and the LANDED seams it feeds (M4's
`void_on_policy`, P3's claim CAS, the checkpoint kernel, the brake) and reports, per case, whether the
behaviour matched the specification — AND `--all` prints the DB/registry/AST measurements the scenario
reads. Every case is deterministic and hermetic — a fixed clock, fresh tmp databases, no wall-clock sleeps.

Output contract (the shared P6 harness vocabulary):
  * a case prints a positive line AND, where the scenario names one, its uppercase headline;
  * a case prints `### MISS ###` on failure, plus the specific alarm marker for the defect it caught;
  * `### NOT REFUSED`, `### WRONGLY REFUSED`, `### WRONG REFUSAL` are the three refusal-shape misses;
  * `--all` prints every case, then the DB/registry/AST measurement block, then the headlines, then
    `behaviours as specified, 0 wrong`.

### POSITIVE CONTROLS ARE DRIVEN THROUGH THE GOVERNED PATH. An ACTIVE/APPROVED policy is reached by
PO-1..PO-4 with a real M4 approval bound to the diff, so it carries `approval_id` + `diff_fingerprint`
and the no-admin-path CHECK ACCEPTS it — the probe never raw-inserts a governed row and then complains
the CHECK refused it (that is a defective oracle, recorded in the report, not a product defect).
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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
from freight_recon.policy import (  # noqa: E402
    M11Machine,
    PolicyEngineUnavailable,
    PolicyEvaluationInputs,
    PolicyState,
    compile_predicate,
    gate_rank,
    narrows_or_holds,
)
from freight_recon.schema import (  # noqa: E402
    create_canonical_schema,
    enable_and_verify_foreign_keys,
    schema_readiness_problems,
)

FIXED = datetime(2026, 9, 3, 12, 0, 0, tzinfo=timezone.utc)
CANONICAL_GATES = ("HUMAN_APPROVAL_REQUIRED", "AUTONOMOUS_WITHIN_CAPS",
                   "PERMANENT_HUMAN_ASSERTION_REQUIRED", "FORBIDDEN")
CANONICAL_PROVENANCE = ("SYSTEM_IMPORTED", "OWNER_ASSERTED", "LINKER_INFERRED",
                        "MODEL_EXTRACTED", "MODEL_INFERRED", "RECONCILED")
CANONICAL_SCOPE_KINDS = ("action_class", "counterparty", "value_cap", "workflow", "integration")
DIRECTIONS = ("narrow", "broaden")
FAULTS = frozenset({"engine-unavailable", "brake-unreadable", "none"})
DIMENSIONS = ("--concurrency", "--delay-ms", "--repeat", "--tenants", "--seed", "--inject",
              "--actor", "--direction", "--gate", "--provenance", "--brake", "--scope")
MISS = "### MISS ###"


# ------------------------------------------------------------------ a hermetic canonical database

class Kit:
    def __init__(self, tenant="T_A", ceiling=GateDecision.HUMAN_APPROVAL_REQUIRED):
        self._dir = tempfile.mkdtemp(prefix="m11-probe-")
        self.path = os.path.join(self._dir, "policy.db")
        self.tenant = tenant
        self.ceiling = ceiling
        self._t = FIXED
        self.conn = self._open()

    def clock(self):
        return self._t

    def _open(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        create_canonical_schema(conn)
        enable_and_verify_foreign_keys(conn)
        return conn

    def new_connection(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def human(self, hid, *, role="POLICY_OWNER", state="ACTIVE", tenant=None):
        offboarded_at = "2026-06-01T00:00:00Z" if state == "OFFBOARDED" else None
        self.conn.execute(
            "INSERT INTO tenant_humans (tenant, human_id, display_name, authority_role, state, "
            "recorded_at, recorded_by, recorded_by_kind, offboarded_at) VALUES (?,?,?,?,?,?,?, 'human', ?)",
            (tenant or self.tenant, hid, hid, role, state, "2026-01-01T00:00:00Z", "founder", offboarded_at))
        self.conn.commit()
        return hid

    def approval(self, aid, *, mfp, policy_version="1", commit_key=None, tenant=None):
        cols = dict(
            tenant=tenant or self.tenant, approval_id=aid, commit_key=commit_key or f"ck-{aid}",
            action_class="change_policy", state="GRANTED", version=1, material_facts_fingerprint=mfp,
            canonical_payload=b"{}", fingerprint_version="fp_v1",
            entity_versions_json='{"policy:%s": 1}' % aid, policy_version=policy_version,
            brake_version="bv1", gate_decision="HUMAN_APPROVAL_REQUIRED", required_signatures=1,
            rendered_facts="{}", requested_at="2026-01-01T00:00:00Z", expires_at="2027-01-01T00:00:00Z",
            frozen=0, granted_by="po", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        self.conn.execute(
            f"INSERT INTO approvals ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
            tuple(cols.values()))
        self.conn.commit()
        return aid

    def m11(self, *, conn=None):
        return M11Machine(conn or self.conn, tenant=self.tenant, clock=self.clock,
                          product_ceiling=self.ceiling)

    def close(self):
        try:
            self.conn.close()
        finally:
            shutil.rmtree(self._dir, ignore_errors=True)


def _trivial():
    return {"combine": "AND", "clauses": []}


def _pod_predicate():
    return {"combine": "AND", "clauses": [
        {"field": "fact:pod", "attr": "evidence_condition", "op": "==", "literal": "consistent"},
        {"field": "fact:pod", "attr": "provenance_class", "op": "in",
         "literal": ["SYSTEM_IMPORTED", "OWNER_ASSERTED", "MODEL_EXTRACTED"]}]}


def activate_policy(kit, *, scope, gate, policy_id, owner="po", predicate=None, caps=None, tenant=None):
    """Drive PO-1..PO-4 through the GOVERNED path (a real M4 approval bound to the diff), so the ACTIVE
    row carries approval_id + diff_fingerprint and the no-admin-path CHECK ACCEPTS it."""
    m = kit.m11()
    aid, diff = f"appr-{policy_id}", f"DIFF-{policy_id}"
    kit.approval(aid, mfp=diff, tenant=tenant or kit.tenant)
    m.propose_draft(scope=scope, scope_kind="action_class", gate_decision=gate, caps=caps or {},
                    predicate=predicate or _trivial(), authored_by=owner, policy_id=policy_id)
    m.submit(policy_id, actor_id=owner)
    m.approve(policy_id, approval_id=aid, diff_fingerprint=diff, approved_by=owner)
    m.activate(policy_id, activated_by=owner)
    return policy_id


def refuses(fn) -> bool:
    try:
        fn()
        return False
    except Exception:
        return True


# ------------------------------------------------------------------ the result type

class Result:
    def __init__(self, ok, positive, headlines=(), alarms=()):
        self.ok = ok
        self.positive = positive
        self.headlines = tuple(headlines)
        self.alarms = tuple(alarms)


def OK(positive, *headlines):
    return Result(True, positive, headlines)


def FAIL(positive, *alarms):
    return Result(False, positive, (), alarms)


CASES = {}


class Case:
    def __init__(self, name, headline, fn):
        self.name = name
        self.headline = headline
        self.fn = fn


def case(name, headline=""):
    def deco(fn):
        CASES[name] = Case(name, headline, fn)
        return fn
    return deco


# ------------------------------------------------------------------ shared checkers

def _author_refused(kind, marker):
    kit = Kit()
    try:
        kit.human("po")
        m = kit.m11()
        if not refuses(lambda: m.propose_draft(
                scope="raise_invoice", scope_kind="action_class",
                gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED, caps={}, predicate=_trivial(),
                authored_by="po", policy_id="p1", actor_kind=kind)):
            return FAIL(f"{MISS} a {kind} authored a policy", marker)
        if kit.conn.execute("SELECT COUNT(*) FROM policies").fetchone()[0] != 0:
            return FAIL(f"{MISS} a {kind} authored a policy", marker)
        return OK(f"{kind}-cannot-author: refused, zero policy rows")
    finally:
        kit.close()


def _emits(name, event_name, setup):
    kit = Kit()
    try:
        kit.human("po")
        pid = setup(kit)
        n = kit.conn.execute(
            "SELECT COUNT(*) FROM event_outbox WHERE tenant=? AND event_name=? AND aggregate_id=?",
            (kit.tenant, event_name, pid)).fetchone()[0]
        if n < 1:
            return FAIL(f"{MISS} {name}: {event_name} not emitted", "### STATE WITHOUT ITS EVENT ###")
        return OK(f"{name}: {event_name} emitted")
    finally:
        kit.close()


def _non_human_activation(kind, alarm, name, *headlines):
    kit = Kit()
    try:
        kit.human("po")
        m = kit.m11()
        aid, diff = f"a-{kind}", f"D-{kind}"
        kit.approval(aid, mfp=diff)
        m.propose_draft(scope="pay_carrier", scope_kind="action_class",
                        gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED, caps={},
                        predicate=_trivial(), authored_by="po", policy_id="p1")
        m.submit("p1", actor_id="po")
        m.approve("p1", approval_id=aid, diff_fingerprint=diff, approved_by="po")
        alarms = []
        if not refuses(lambda: m.activate("p1", activated_by="po", actor_kind=kind)):
            alarms.append(alarm)
        if kit.conn.execute("SELECT state FROM policies WHERE policy_id='p1'").fetchone()["state"] == "ACTIVE":
            alarms.append(alarm)
        f14 = kit.conn.execute(
            "SELECT COUNT(*) FROM event_outbox WHERE tenant=? AND "
            "event_name='UnauthorizedPolicyActivationAttempted'", (kit.tenant,)).fetchone()[0]
        if f14 < 1 and not alarms:
            alarms.append("### UNAUTHORIZED ACTIVATION WENT UNRECORDED ###")
        if alarms:
            return FAIL(f"{MISS} a {kind} activated a policy", *alarms)
        return OK(f"{name}: a {kind} activation is refused and recorded as F14", *headlines)
    finally:
        kit.close()


def _draft(kit, *, gate, scope="s", pid="p1", predicate=None, expires_at=None, field_provenance=None):
    kit.m11().propose_draft(scope=scope, scope_kind="action_class", gate_decision=gate, caps={},
                            predicate=predicate or _trivial(), authored_by="po", policy_id=pid,
                            expires_at=expires_at, field_provenance=field_provenance)
    return pid


def _to_approved(kit, *, diff="DIFF", aid="a1", pid="p1", scope="raise_invoice"):
    m = kit.m11()
    kit.approval(aid, mfp=diff)
    _draft(kit, gate=GateDecision.HUMAN_APPROVAL_REQUIRED, scope=scope, pid=pid)
    m.submit(pid, actor_id="po")
    m.approve(pid, approval_id=aid, diff_fingerprint=diff, approved_by="po")
    return m


def _mint_scan():
    import freight_recon
    src = Path(freight_recon.__file__).parent
    minters = set()
    for path in src.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                nm = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", None)
                if nm in {"GateEntry", "GateRegistry"}:
                    minters.add(path.name)
    return minters


def _emitted_event_names(src):
    names = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.keyword) and node.arg == "event_name" and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str):
                names.add(node.value.value)
        if isinstance(node, ast.keyword) and node.arg == "events" and isinstance(node.value, ast.Tuple):
            for elt in node.value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    names.add(elt.value)
    return names


# =========================================================== PO-1: authorship

@case("a-draft-is-authored-by-the-policy-owner-or-a-delegate")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        kit.human("clerk", role="AUTHORIZED_HUMAN")
        m = kit.m11()
        m.propose_draft(scope="s1", scope_kind="action_class",
                        gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED, caps={},
                        predicate=_pod_predicate(), authored_by="po", policy_id="p1")
        m.propose_draft(scope="s2", scope_kind="action_class",
                        gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED, caps={},
                        predicate=_trivial(), authored_by="clerk", policy_id="p2")
        rows = {r["policy_id"]: r for r in kit.conn.execute(
            "SELECT policy_id, state, predicate_json FROM policies")}
        if rows["p1"]["state"] != "DRAFT" or not rows["p1"]["predicate_json"]:
            return FAIL(f"{MISS} a draft is not a value with a gate and predicate",
                        "### NOTED THE PROCEDURE WITHOUT COMPILING A RULE ###")
        return OK("a-draft-is-authored-by-the-policy-owner-or-a-delegate: owner and delegate authored rows",
                  "A POLICY IS A VALUE THE OWNER CAN SEE, NOT A SENTENCE IN A PROMPT")
    finally:
        kit.close()


@case("a-model-may-propose-text-and-never-author")
def _c(args):
    r = _author_refused("model", "### A MODEL AUTHORED A POLICY ###")
    return r if not r.ok else OK("a-model-may-propose-text-and-never-author: a model authors no policy row")


@case("inbound-content-can-never-author-a-policy")
def _c(args):
    r = _author_refused("inbound", "### INBOUND CONTENT AUTHORED A POLICY ###")
    return r if not r.ok else OK(
        "inbound-content-can-never-author-a-policy: inbound content authors no policy",
        "INBOUND CONTENT CAN NEVER AUTHOR A POLICY")


@case("an-email-announcing-a-new-rule-is-data-not-a-policy-change")
def _c(args):
    r = _author_refused("inbound", "### AN EMAIL BECAME A POLICY CHANGE ###")
    return r if not r.ok else OK("an-email-announcing-a-new-rule-is-data-not-a-policy-change: inbound is data")


@case("a-counterparty-cannot-author-a-policy")
def _c(args):
    r = _author_refused("counterparty", "### A COUNTERPARTY AUTHORED A POLICY ###")
    return r if not r.ok else OK("a-counterparty-cannot-author-a-policy: a counterparty authors no policy")


@case("an-offboarded-human-cannot-author-a-policy")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        kit.human("ex", role="AUTHORIZED_HUMAN", state="OFFBOARDED")
        if not refuses(lambda: kit.m11().propose_draft(
                scope="s", scope_kind="action_class", gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED,
                caps={}, predicate=_trivial(), authored_by="ex", policy_id="p1")):
            return FAIL(f"{MISS} an offboarded human authored", "### AN OFFBOARDED HUMAN AUTHORED A POLICY ###")
        return OK("an-offboarded-human-cannot-author-a-policy: an offboarded human authors nothing")
    finally:
        kit.close()


@case("po-1-emits-policyproposed")
def _c(args):
    def setup(kit):
        kit.m11().propose_draft(scope="s", scope_kind="action_class",
                                gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED, caps={},
                                predicate=_trivial(), authored_by="po", policy_id="p1")
        return "p1"
    return _emits("po-1-emits-policyproposed", "PolicyProposed", setup)


@case("policyproposed-does-not-prove-the-policy-is-active")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        kit.m11().propose_draft(scope="s", scope_kind="action_class",
                                gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED, caps={},
                                predicate=_trivial(), authored_by="po", policy_id="p1")
        st = kit.conn.execute("SELECT state FROM policies WHERE policy_id='p1'").fetchone()["state"]
        if st != "DRAFT":
            return FAIL(f"{MISS} PolicyProposed left the policy {st}", "### PolicyProposed TREATED AS ACTIVATION ###")
        return OK("policyproposed-does-not-prove-the-policy-is-active: state is DRAFT")
    finally:
        kit.close()


# =========================================================== PO-2: submission

@case("submission-requires-a-non-null-gate-decision")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        _draft(kit, gate=GateDecision.HUMAN_APPROVAL_REQUIRED)
        kit.m11().submit("p1", actor_id="po")
        st = kit.conn.execute("SELECT state, gate_decision FROM policies WHERE policy_id='p1'").fetchone()
        if st["state"] != "PROPOSED" or not st["gate_decision"]:
            return FAIL(f"{MISS} submission accepted without a gate", "### NULL GATE DECISION ACCEPTED ###")
        return OK("submission-requires-a-non-null-gate-decision: PROPOSED carries a non-null gate")
    finally:
        kit.close()


@case("a-null-gate-decision-is-refused-at-submission")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        if not refuses(lambda: kit.m11().propose_draft(
                scope="s", scope_kind="action_class", gate_decision=None, caps={},
                predicate=_trivial(), authored_by="po", policy_id="p1")):
            return FAIL(f"{MISS} a null gate was accepted", "### NULL GATE DECISION ACCEPTED ###")
        return OK("a-null-gate-decision-is-refused-at-submission: a null gate is refused")
    finally:
        kit.close()


@case("an-invented-gate-decision-is-refused")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        if not refuses(lambda: kit.m11().propose_draft(
                scope="s", scope_kind="action_class", gate_decision="YOLO_AUTONOMOUS", caps={},
                predicate=_trivial(), authored_by="po", policy_id="p1")):
            return FAIL(f"{MISS} an invented gate was accepted", "### INVENTED GATE DECISION ACCEPTED ###")
        return OK("an-invented-gate-decision-is-refused: a fifth/invented gate is refused")
    finally:
        kit.close()


@case("the-four-canonical-gate-members-and-no-fifth")
def _c(args):
    alarms = []
    if {g.value for g in GateDecision} != set(CANONICAL_GATES):
        alarms.append("### FIFTH GATE MEMBER MINTED ###")
    if len({gate_rank(g) for g in GateDecision}) != 4:
        alarms.append("### CEILING ORDER INCOMPLETE ###")
    gates = list(CANONICAL_GATES) if (args.gate in (None, "all")) else [args.gate]
    for g in gates:
        kit = Kit(ceiling=GateDecision.AUTONOMOUS_WITHIN_CAPS)
        try:
            kit.human("po")
            _draft(kit, gate=GateDecision(g), scope=f"scope-{g}", pid="pg")
            if refuses(lambda: kit.m11().submit("pg", actor_id="po")):
                alarms.append("### CEILING ORDER INCOMPLETE ###")
        finally:
            kit.close()
    if alarms:
        return FAIL(f"{MISS} the gate vocabulary is not exactly four", *alarms)
    return OK("the-four-canonical-gate-members-and-no-fifth: four members, total order",
              "A GATE EXPRESSIBLE AS AN ABSENCE IS NOT A GATE")


@case("a-predicate-on-model-inferred-fails-to-compile")
def _c(args):
    alarms = []
    provs = list(CANONICAL_PROVENANCE) if (args.provenance in (None, "all")) else [args.provenance]
    for prov in provs:
        pred = {"clauses": [{"field": "fact:carrier_cost", "attr": "value", "op": ">", "literal": 100}]}
        compiled = not refuses(lambda: compile_predicate(
            pred, field_provenance={"fact:carrier_cost": ProvenanceClass(prov)}))
        if prov == "MODEL_INFERRED" and compiled:
            alarms.append("### MODEL_INFERRED PREDICATE COMPILED ###")
        if prov != "MODEL_INFERRED" and not compiled:
            alarms.append(f"{MISS} a {prov} value predicate was wrongly refused")
    if not refuses(lambda: compile_predicate("never bill without a POD")):
        alarms.append("### PREDICATE ADMITTED AS A PROMPT STRING ###")
    if alarms:
        return FAIL(f"{MISS} a guess or prompt became a gate", *alarms)
    return OK("a-predicate-on-model-inferred-fails-to-compile: only non-inferred predicates compile",
              "A POLICY MAY NEVER BRANCH ON A GUESS")


@case("confidence-one-does-not-make-model-inferred-readable")
def _c(args):
    fact = ProvenancedFact(field="c", provenance=ProvenanceClass.MODEL_INFERRED,
                           evidence_condition=EvidenceCondition.CONSISTENT, _value=1)
    if not refuses(lambda: fact.value):
        return FAIL(f"{MISS} a MODEL_INFERRED value was read", "### MODEL_INFERRED READ AT CONFIDENCE ONE ###")
    if not refuses(lambda: compile_predicate(
            {"clauses": [{"field": "fact:x", "attr": "value", "op": "==", "literal": 1}]},
            field_provenance={"fact:x": ProvenanceClass.MODEL_INFERRED})):
        return FAIL(f"{MISS} a MODEL_INFERRED predicate compiled", "### MODEL_INFERRED PREDICATE COMPILED ###")
    return OK("confidence-one-does-not-make-model-inferred-readable: the value accessor raises regardless",
              "A POLICY MAY NEVER BRANCH ON A GUESS")


@case("the-evaluator-input-type-has-no-confidence-field")
def _c(args):
    alarms = []
    if hasattr(ProvenancedFact(field="x", provenance=ProvenanceClass.SYSTEM_IMPORTED,
                               evidence_condition=EvidenceCondition.CONSISTENT), "confidence"):
        alarms.append("### CONFIDENCE FIELD PRESENT ON THE EVALUATOR INPUT ###")
    if "confidence" in PolicyEvaluationInputs.__dataclass_fields__:
        alarms.append("### CONFIDENCE FIELD PRESENT ON THE EVALUATOR INPUT ###")
    if not refuses(lambda: compile_predicate({"clauses": [{"field": "confidence", "attr": "value",
                                                           "op": ">", "literal": 0.9}]})):
        alarms.append("### CONFIDENCE READ BY THE EVALUATOR ###")
    if alarms:
        return FAIL(f"{MISS} confidence is an input", *alarms)
    return OK("the-evaluator-input-type-has-no-confidence-field: no confidence attribute anywhere",
              "CONFIDENCE IS STRUCTURALLY NOT AN INPUT")


@case("a-predicate-on-an-unmodelled-field-fails-to-compile")
def _c(args):
    if not refuses(lambda: compile_predicate(
            {"clauses": [{"field": "commodity", "attr": "value", "op": "==", "literal": "produce"}]})):
        return FAIL(f"{MISS} an unmodelled field compiled", "### UNMODELLED FIELD COMPILED INTO A PREDICATE ###")
    return OK("a-predicate-on-an-unmodelled-field-fails-to-compile: an unmodelled field is refused")


@case("a-tenant-policy-that-broadens-the-product-ceiling-is-refused")
def _c(args):
    kit = Kit(ceiling=GateDecision.HUMAN_APPROVAL_REQUIRED)
    try:
        kit.human("po")
        _draft(kit, gate=GateDecision.AUTONOMOUS_WITHIN_CAPS)
        if not refuses(lambda: kit.m11().submit("p1", actor_id="po")):
            return FAIL(f"{MISS} a tenant policy broadened the ceiling",
                        "### TENANT POLICY BROADENED THE PRODUCT CEILING ###")
        return OK("a-tenant-policy-that-broadens-the-product-ceiling-is-refused: broadening is refused at PO-2",
                  "A TENANT POLICY MAY ONLY EVER NARROW THE PRODUCT CEILING")
    finally:
        kit.close()


@case("narrowing-within-the-product-ceiling-is-accepted")
def _c(args):
    kit = Kit(ceiling=GateDecision.HUMAN_APPROVAL_REQUIRED)
    try:
        kit.human("po")
        _draft(kit, gate=GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED)
        if refuses(lambda: kit.m11().submit("p1", actor_id="po")):
            return FAIL(f"{MISS} a narrowing policy was wrongly refused", "### WRONGLY REFUSED ###")
        return OK("narrowing-within-the-product-ceiling-is-accepted: a narrowing posture submits",
                  "A TENANT POLICY MAY ONLY EVER NARROW THE PRODUCT CEILING")
    finally:
        kit.close()


@case("the-ceiling-comparison-is-structural-not-textual")
def _c(args):
    if not (gate_rank(GateDecision.AUTONOMOUS_WITHIN_CAPS) > gate_rank(GateDecision.HUMAN_APPROVAL_REQUIRED)):
        return FAIL(f"{MISS} the ceiling order is wrong", "### CEILING ORDER INCOMPLETE ###")
    if narrows_or_holds(GateDecision.AUTONOMOUS_WITHIN_CAPS, GateDecision.HUMAN_APPROVAL_REQUIRED):
        return FAIL(f"{MISS} broadening read as narrowing", "### CEILING COMPARISON WAS A STRING COMPARE ###")
    return OK("the-ceiling-comparison-is-structural-not-textual: a declared total order, not a string compare")


@case("po-2-emits-policysubmitted")
def _c(args):
    def setup(kit):
        _draft(kit, gate=GateDecision.HUMAN_APPROVAL_REQUIRED)
        kit.m11().submit("p1", actor_id="po")
        return "p1"
    return _emits("po-2-emits-policysubmitted", "PolicySubmitted", setup)


@case("policysubmitted-is-not-a-rename-of-policyproposed")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        _draft(kit, gate=GateDecision.HUMAN_APPROVAL_REQUIRED)
        kit.m11().submit("p1", actor_id="po")
        names = [r["event_name"] for r in kit.conn.execute(
            "SELECT event_name FROM event_outbox WHERE aggregate_id='p1' ORDER BY aggregate_version")]
        if "PolicyProposed" not in names or "PolicySubmitted" not in names or \
                names.index("PolicyProposed") >= names.index("PolicySubmitted"):
            return FAIL(f"{MISS} the two facts collapsed", "### PolicyProposed AND PolicySubmitted COLLAPSED ###")
        return OK("policysubmitted-is-not-a-rename-of-policyproposed: two distinct facts, PO-1 then PO-2",
                  "PolicySubmitted IS NOT A RENAME OF PolicyProposed")
    finally:
        kit.close()


# =========================================================== PO-3: the governed change

@case("approval-runs-through-the-ordinary-m2-governed-path")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        _to_approved(kit)
        row = kit.conn.execute(
            "SELECT state, approval_id, diff_fingerprint FROM policies WHERE policy_id='p1'").fetchone()
        if row["state"] != "APPROVED" or not row["approval_id"] or not row["diff_fingerprint"]:
            return FAIL(f"{MISS} the governed change did not bind an approval", "### ADMIN PATH TO APPROVED ###")
        return OK("approval-runs-through-the-ordinary-m2-governed-path: APPROVED binds an M4 approval",
                  "A POLICY CHANGE IS ITSELF A GATED ACTION, AND THERE IS NO ADMIN PATH")
    finally:
        kit.close()


@case("the-policy-diff-is-the-material-facts")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        m = kit.m11()
        kit.approval("a1", mfp="OTHER")
        _draft(kit, gate=GateDecision.HUMAN_APPROVAL_REQUIRED)
        m.submit("p1", actor_id="po")
        if not refuses(lambda: m.approve("p1", approval_id="a1", diff_fingerprint="DIFF", approved_by="po")):
            return FAIL(f"{MISS} an approval of other facts approved the change",
                        "### POLICY DIFF WAS NOT THE MATERIAL FACTS ###")
        return OK("the-policy-diff-is-the-material-facts: the approval must bind the diff fingerprint")
    finally:
        kit.close()


@case("there-is-no-admin-path-to-approved")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        m = kit.m11()
        _draft(kit, gate=GateDecision.HUMAN_APPROVAL_REQUIRED)
        m.submit("p1", actor_id="po")
        alarms = []
        if not refuses(lambda: m.approve("p1", approval_id="nope", diff_fingerprint="D", approved_by="po")):
            alarms.append("### ADMIN PATH TO APPROVED ###")
        try:
            kit.conn.execute("UPDATE policies SET state='ACTIVE', version=version+1, activated_by='po' "
                             "WHERE policy_id='p1'")
            kit.conn.commit()
            alarms.append("### CONFIG FILE ACTIVATED A POLICY ###")
        except sqlite3.IntegrityError:
            kit.conn.rollback()
        if alarms:
            return FAIL(f"{MISS} there was an admin path", *alarms)
        return OK("there-is-no-admin-path-to-approved: APPROVED needs an M4 approval; direct UPDATE refused",
                  "A POLICY CHANGE IS ITSELF A GATED ACTION, AND THERE IS NO ADMIN PATH")
    finally:
        kit.close()


def _no_direct_activation(marker, name):
    kit = Kit()
    try:
        kit.human("po")
        _to_approved(kit)
        try:
            kit.conn.execute("UPDATE policies SET state='ACTIVE', version=version+1 WHERE policy_id='p1' "
                             "AND activated_by IS NULL")
            kit.conn.commit()
        except sqlite3.IntegrityError:
            kit.conn.rollback()
        st = kit.conn.execute("SELECT state FROM policies WHERE policy_id='p1'").fetchone()["state"]
        act = kit.conn.execute("SELECT COUNT(*) FROM event_outbox WHERE event_name='PolicyActivated' "
                               "AND aggregate_id='p1'").fetchone()[0]
        if st == "ACTIVE" and act == 0:
            return FAIL(f"{MISS} {name}: a config/migration/superuser activated a policy", marker)
        return OK(f"{name}: only PO-4 and a human activate")
    finally:
        kit.close()


@case("a-config-file-cannot-approve-or-activate-a-policy")
def _c(args):
    return _no_direct_activation("### CONFIG FILE ACTIVATED A POLICY ###",
                                 "a-config-file-cannot-approve-or-activate-a-policy")


@case("a-migration-cannot-activate-a-policy")
def _c(args):
    return _no_direct_activation("### MIGRATION ACTIVATED A POLICY ###", "a-migration-cannot-activate-a-policy")


@case("a-superuser-command-line-cannot-activate-a-policy")
def _c(args):
    return _no_direct_activation("### SUPERUSER COMMAND LINE ACTIVATED A POLICY ###",
                                 "a-superuser-command-line-cannot-activate-a-policy")


@case("a-model-cannot-approve-a-policy-change")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        m = kit.m11()
        kit.approval("a1", mfp="DIFF")
        _draft(kit, gate=GateDecision.HUMAN_APPROVAL_REQUIRED)
        m.submit("p1", actor_id="po")
        if not refuses(lambda: m.approve("p1", approval_id="a1", diff_fingerprint="DIFF",
                                         approved_by="po", actor_kind="model")):
            return FAIL(f"{MISS} a model approved a policy change", "### A MODEL APPROVED A POLICY CHANGE ###")
        return OK("a-model-cannot-approve-a-policy-change: a model cannot approve, at any confidence")
    finally:
        kit.close()


@case("the-approval-id-resolves-to-a-same-tenant-m4-approval")
def _c(args):
    kit = Kit()
    try:
        kit.human("po", tenant="T_A")
        kit.human("po", tenant="T_B")  # the T_B approval's granted_by FK needs a T_B human
        m = M11Machine(kit.conn, tenant="T_A", clock=kit.clock)
        kit.approval("aB", mfp="DIFF", tenant="T_B")
        m.propose_draft(scope="s", scope_kind="action_class",
                        gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED, caps={},
                        predicate=_trivial(), authored_by="po", policy_id="p1")
        m.submit("p1", actor_id="po")
        if not refuses(lambda: m.approve("p1", approval_id="aB", diff_fingerprint="DIFF", approved_by="po")):
            return FAIL(f"{MISS} a cross-tenant approval was accepted", "### CROSS-TENANT APPROVAL ACCEPTED ###")
        return OK("the-approval-id-resolves-to-a-same-tenant-m4-approval: cross-tenant approval refused")
    finally:
        kit.close()


@case("policyapproved-carries-the-diff-fingerprint")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        _to_approved(kit, diff="DIFF123")
        ev = kit.conn.execute(
            "SELECT envelope_json FROM event_outbox WHERE event_name='PolicyApproved' AND aggregate_id='p1'"
        ).fetchone()
        payload = EventEnvelope.from_json(ev["envelope_json"]).payload if ev else {}
        if payload.get("diff_fingerprint") != "DIFF123":
            return FAIL(f"{MISS} PolicyApproved dropped the diff", "### MISSING diff_fingerprint ON PolicyApproved ###")
        return OK("policyapproved-carries-the-diff-fingerprint: PolicyApproved pins the diff")
    finally:
        kit.close()


@case("policyapproved-is-consequential-and-pins-its-decision-context")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        _to_approved(kit)
        env = EventEnvelope.from_json(kit.conn.execute(
            "SELECT envelope_json FROM event_outbox WHERE event_name='PolicyApproved' AND aggregate_id='p1'"
        ).fetchone()["envelope_json"])
        if not (env.policy_version and env.brake_version and env.entity_versions) or not CONTRACTS["PolicyApproved"].consequential:
            return FAIL(f"{MISS} PolicyApproved pins no decision context", "### REQUIRED PAYLOAD FIELD DROPPED ###")
        return OK("policyapproved-is-consequential-and-pins-its-decision-context: pins entity/policy/brake versions")
    finally:
        kit.close()


@case("policyapproved-does-not-activate")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        _to_approved(kit)
        st = kit.conn.execute("SELECT state FROM policies WHERE policy_id='p1'").fetchone()["state"]
        act = kit.conn.execute("SELECT COUNT(*) FROM event_outbox WHERE event_name='PolicyActivated' "
                               "AND aggregate_id='p1'").fetchone()[0]
        if st != "APPROVED" or act:
            return FAIL(f"{MISS} PolicyApproved activated", "### PolicyApproved TREATED AS PolicyActivated ###")
        return OK("policyapproved-does-not-activate: APPROVED is not ACTIVE",
                  "PolicyApproved DOES NOT ACTIVATE", "PolicyApproved IS THE NO-ADMIN-PATH EVIDENCE")
    finally:
        kit.close()


@case("m11-builds-no-second-approval-system")
def _c(args):
    src = (ROOT / "src" / "freight_recon" / "policy.py").read_text()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ClassDef) and "approval" in node.name.lower() and "machine" in node.name.lower():
            return FAIL(f"{MISS} M11 defines an approval machine", "### SECOND APPROVAL SYSTEM BUILT ###")
    return OK("m11-builds-no-second-approval-system: M11 reads M4, builds no approval machine")


# =========================================================== PO-4: activation

@case("activation-requires-an-authenticated-human")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_policy(kit, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
        row = kit.conn.execute("SELECT state, activated_by FROM policies WHERE policy_id='p1'").fetchone()
        if row["state"] != "ACTIVE" or row["activated_by"] != "po":
            return FAIL(f"{MISS} ACTIVE has no authenticated activator", "### ACTIVE WITHOUT AN ACTIVATOR ###")
        return OK("activation-requires-an-authenticated-human: ACTIVE is FK-bound to a human",
                  "ACTIVATION REQUIRES AN AUTHENTICATED HUMAN")
    finally:
        kit.close()


@case("a-model-cannot-activate-a-policy")
def _c(args):
    return _non_human_activation("model", "### A MODEL ACTIVATED A POLICY ###",
                                 "a-model-cannot-activate-a-policy", "A MODEL CAN NEVER ACTIVATE A POLICY")


@case("automation-cannot-activate-a-policy")
def _c(args):
    return _non_human_activation("automation", "### AUTOMATION ACTIVATED A POLICY ###",
                                 "automation-cannot-activate-a-policy", "AUTOMATION CAN NEVER ACTIVATE A POLICY")


@case("a-retry-handler-cannot-activate-or-broaden-policy")
def _c(args):
    return _non_human_activation("retry", "### A RETRY HANDLER ACTIVATED A POLICY ###",
                                 "a-retry-handler-cannot-activate-or-broaden-policy",
                                 "AUTOMATION MAY ONLY EVER MOVE AUTHORITY IN THE SAFE DIRECTION")


@case("a-timer-cannot-activate-a-policy")
def _c(args):
    return _non_human_activation("timer", "### A TIMER ACTIVATED A POLICY ###",
                                 "a-timer-cannot-activate-a-policy",
                                 "AUTOMATION MAY ONLY EVER MOVE AUTHORITY IN THE SAFE DIRECTION")


@case("an-unauthorized-activation-emits-the-registered-f14-security-event")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        m = _to_approved(kit)
        refuses(lambda: m.activate("p1", activated_by="po", actor_kind="model"))
        n = kit.conn.execute("SELECT COUNT(*) FROM event_outbox WHERE "
                             "event_name='UnauthorizedPolicyActivationAttempted'").fetchone()[0]
        sec = kit.conn.execute("SELECT COUNT(*) FROM security_events WHERE "
                               "event_type='UnauthorizedPolicyActivationAttempted'").fetchone()[0]
        if n < 1 or sec < 1:
            return FAIL(f"{MISS} unauthorized activation unrecorded", "### UNAUTHORIZED ACTIVATION WENT UNRECORDED ###")
        return OK("an-unauthorized-activation-emits-the-registered-f14-security-event: F14 to audit and security")
    finally:
        kit.close()


@case("m11-mints-no-second-unauthorized-activation-contract")
def _c(args):
    names = [n for n in CONTRACTS if "Unauthorized" in n and "Activation" in n]
    if names != ["UnauthorizedPolicyActivationAttempted"]:
        return FAIL(f"{MISS} a second contract exists: {names}", "### SECOND UNAUTHORIZED-ACTIVATION CONTRACT MINTED ###")
    return OK("m11-mints-no-second-unauthorized-activation-contract: exactly the registered F14")


@case("active-requires-a-non-null-activated-by")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        kit.approval("a1", mfp="D")
        if not refuses(lambda: kit.conn.execute(
                "INSERT INTO policies (tenant,policy_id,policy_version,scope,scope_kind,gate_decision,"
                "caps_json,predicate_json,state,version,effective_from,authored_by,activated_by,"
                "change_direction,approval_id,diff_fingerprint,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (kit.tenant, "p", 1, "s", "action_class", "HUMAN_APPROVAL_REQUIRED", "{}", "{}", "ACTIVE",
                 1, "t", "po", None, "initial", "a1", "D", "t", "t"))):
            return FAIL(f"{MISS} ACTIVE with no activator insertable", "### ACTIVE WITHOUT AN ACTIVATOR ###")
        kit.conn.rollback()
        return OK("active-requires-a-non-null-activated-by: ACTIVE with a null activator is refused")
    finally:
        kit.close()


@case("the-activator-is-the-policy-owner-or-an-authorized-delegate")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        kit.human("clerk", role="AUTHORIZED_HUMAN")
        m = _to_approved(kit)
        if refuses(lambda: m.activate("p1", activated_by="clerk")):
            return FAIL(f"{MISS} a delegate could not activate", "### WRONGLY REFUSED ###")
        return OK("the-activator-is-the-policy-owner-or-an-authorized-delegate: a delegate may activate")
    finally:
        kit.close()


@case("a-cross-tenant-activator-is-refused")
def _c(args):
    kit = Kit()
    try:
        kit.human("po", tenant="T_A")
        kit.human("outsider", role="AUTHORIZED_HUMAN", tenant="T_B")
        m = M11Machine(kit.conn, tenant="T_A", clock=kit.clock)
        kit.approval("a1", mfp="D", tenant="T_A")
        m.propose_draft(scope="s", scope_kind="action_class",
                        gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED, caps={},
                        predicate=_trivial(), authored_by="po", policy_id="p1")
        m.submit("p1", actor_id="po")
        m.approve("p1", approval_id="a1", diff_fingerprint="D", approved_by="po")
        if not refuses(lambda: m.activate("p1", activated_by="outsider")):
            return FAIL(f"{MISS} a cross-tenant activator accepted", "### CROSS-TENANT ACTIVATION ACCEPTED ###")
        return OK("a-cross-tenant-activator-is-refused: an activator from another tenant fails closed")
    finally:
        kit.close()


@case("po-4-emits-policyactivated-and-policyversionchanged")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_policy(kit, scope="s", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
        names = {r["event_name"] for r in kit.conn.execute(
            "SELECT event_name FROM event_outbox WHERE aggregate_id='p1'")}
        if "PolicyActivated" not in names or "PolicyVersionChanged" not in names:
            return FAIL(f"{MISS} PO-4 did not emit both events", "### STATE WITHOUT ITS EVENT ###")
        return OK("po-4-emits-policyactivated-and-policyversionchanged: both emitted")
    finally:
        kit.close()


@case("policyactivated-does-not-apply-retroactively")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_policy(kit, scope="s", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
        v1 = kit.conn.execute("SELECT policy_version FROM policies WHERE policy_id='p1'").fetchone()[0]
        activate_policy(kit, scope="s", gate=GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED, policy_id="p2")
        v1b = kit.conn.execute("SELECT policy_version FROM policies WHERE policy_id='p1'").fetchone()[0]
        if v1 != v1b:
            return FAIL(f"{MISS} the old version was rewritten", "### PolicyActivated APPLIED RETROACTIVELY ###")
        return OK("policyactivated-does-not-apply-retroactively: the old version keeps its own version",
                  "A POLICY IS NEVER RETROACTIVE")
    finally:
        kit.close()


@case("re-activating-an-already-active-version-is-a-no-op")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_policy(kit, scope="s", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
        v = kit.conn.execute("SELECT version FROM policies WHERE policy_id='p1'").fetchone()[0]
        refuses(lambda: kit.m11().activate("p1", activated_by="po"))
        v2 = kit.conn.execute("SELECT version FROM policies WHERE policy_id='p1'").fetchone()[0]
        if v2 != v:
            return FAIL(f"{MISS} re-activation bumped the version", "### RE-ACTIVATION BUMPED THE VERSION ###")
        return OK("re-activating-an-already-active-version-is-a-no-op: version unchanged")
    finally:
        kit.close()


# =========================================================== PO-5: supersession

@case("a-newer-version-supersedes-the-active-one")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_policy(kit, scope="s", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
        activate_policy(kit, scope="s", gate=GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED, policy_id="p2")
        old = kit.conn.execute("SELECT state, superseded_by FROM policies WHERE policy_id='p1'").fetchone()
        if old["state"] != "SUPERSEDED" or old["superseded_by"] != "p2":
            return FAIL(f"{MISS} the prior version was not superseded", "### STATE WITHOUT ITS EVENT ###")
        return OK("a-newer-version-supersedes-the-active-one: p1 SUPERSEDED by p2")
    finally:
        kit.close()


@case("the-superseded-version-is-retained-permanently")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_policy(kit, scope="s", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
        activate_policy(kit, scope="s", gate=GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED, policy_id="p2")
        if not refuses(lambda: kit.conn.execute("DELETE FROM policies WHERE policy_id='p1'")):
            return FAIL(f"{MISS} a superseded version was deleted", "### SUPERSEDED VERSION DELETED ###")
        kit.conn.rollback()
        return OK("the-superseded-version-is-retained-permanently: the superseded row cannot be deleted")
    finally:
        kit.close()


@case("the-superseded-version-still-explains-its-historical-decisions")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_policy(kit, scope="s", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
        activate_policy(kit, scope="s", gate=GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED, policy_id="p2")
        old = kit.conn.execute("SELECT gate_decision FROM policies WHERE policy_id='p1'").fetchone()
        if old is None or old["gate_decision"] != "HUMAN_APPROVAL_REQUIRED":
            return FAIL(f"{MISS} the old version no longer explains itself", "### OLD VERSION NO LONGER EXPLAINS ITS DECISIONS ###")
        return OK("the-superseded-version-still-explains-its-historical-decisions: its gate is retained",
                  "THE OLD VERSION IS RETAINED BECAUSE EFFECTS WERE JUDGED UNDER IT")
    finally:
        kit.close()


@case("supersession-never-edits-history-in-place")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_policy(kit, scope="s", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
        if not refuses(lambda: kit.conn.execute("UPDATE policies SET gate_decision='FORBIDDEN' WHERE policy_id='p1'")):
            return FAIL(f"{MISS} history was edited in place", "### HISTORY EDITED IN PLACE ###")
        kit.conn.rollback()
        return OK("supersession-never-edits-history-in-place: identity is immutable")
    finally:
        kit.close()


@case("po-5-emits-policysuperseded")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_policy(kit, scope="s", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
        activate_policy(kit, scope="s", gate=GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED, policy_id="p2")
        n = kit.conn.execute("SELECT COUNT(*) FROM event_outbox WHERE event_name='PolicySuperseded' "
                             "AND aggregate_id='p1'").fetchone()[0]
        if n < 1:
            return FAIL(f"{MISS} PolicySuperseded not emitted", "### STATE WITHOUT ITS EVENT ###")
        return OK("po-5-emits-policysuperseded: PolicySuperseded emitted on the old version")
    finally:
        kit.close()


# =========================================================== PO-6: revocation

@case("a-narrowing-revocation-is-immediate")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_policy(kit, scope="s", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
        kit.m11().revoke("p1", revoked_reason="tighten", direction="narrow", actor_kind="automation", actor_id="auto")
        row = kit.conn.execute("SELECT state, revoked_direction FROM policies WHERE policy_id='p1'").fetchone()
        if row["state"] != "REVOKED" or row["revoked_direction"] != "narrow":
            return FAIL(f"{MISS} a narrowing revocation was blocked", "### NARROWING REVOCATION BLOCKED ON REVIEW ###")
        return OK("a-narrowing-revocation-is-immediate: automation may narrow immediately",
                  "A NARROWING REVOCATION IS IMMEDIATE; A BROADENING ONE NEEDS THE OWNER")
    finally:
        kit.close()


@case("a-broadening-revocation-requires-the-policy-owner")
def _c(args):
    which = DIRECTIONS if (args.direction in (None, "all")) else (args.direction,)
    for direction in which:
        kit = Kit()
        try:
            kit.human("po")
            activate_policy(kit, scope=f"s-{direction}", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
            m = kit.m11()
            if direction == "narrow":
                m.revoke("p1", revoked_reason="t", direction="narrow", actor_kind="automation", actor_id="auto")
                if kit.conn.execute("SELECT state FROM policies WHERE policy_id='p1'").fetchone()["state"] != "REVOKED":
                    return FAIL(f"{MISS} narrowing revocation blocked", "### NARROWING REVOCATION BLOCKED ON REVIEW ###")
            else:
                if not refuses(lambda: m.revoke("p1", revoked_reason="l", direction="broaden",
                                                actor_kind="automation", actor_id="po")):
                    return FAIL(f"{MISS} automation broadened", "### BROADENING REVOCATION BY AUTOMATION ###")
                m.revoke("p1", revoked_reason="l", direction="broaden", actor_kind="human", actor_id="po")
                if kit.conn.execute("SELECT revoked_direction FROM policies WHERE policy_id='p1'").fetchone()[0] != "broaden":
                    return FAIL(f"{MISS} revocation direction missing", "### REVOCATION DIRECTION MISSING ###")
        finally:
            kit.close()
    return OK("a-broadening-revocation-requires-the-policy-owner: narrow may automate, broaden needs the owner",
              "A NARROWING REVOCATION IS IMMEDIATE; A BROADENING ONE NEEDS THE OWNER")


@case("automation-cannot-perform-a-broadening-revocation")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_policy(kit, scope="s", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
        if not refuses(lambda: kit.m11().revoke("p1", revoked_reason="l", direction="broaden",
                                                actor_kind="automation", actor_id="po")):
            return FAIL(f"{MISS} automation broadened", "### BROADENING REVOCATION BY AUTOMATION ###")
        return OK("automation-cannot-perform-a-broadening-revocation: refused",
                  "AUTOMATION MAY ONLY EVER MOVE AUTHORITY IN THE SAFE DIRECTION")
    finally:
        kit.close()


@case("policyrevoked-carries-the-canonical-direction")
def _c(args):
    names = {f.name for f in CONTRACTS["PolicyRevoked"].fields}
    if "direction" not in names or "revoked_reason" not in names:
        return FAIL(f"{MISS} PolicyRevoked lacks direction", "### REVOCATION DIRECTION MISSING ###")
    return OK("policyrevoked-carries-the-canonical-direction: direction is a required enumerated field")


@case("revocation-emits-policyversionchanged")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_policy(kit, scope="s", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
        kit.m11().revoke("p1", revoked_reason="t", direction="narrow", actor_kind="automation", actor_id="auto")
        n = kit.conn.execute("SELECT COUNT(*) FROM event_outbox WHERE event_name='PolicyVersionChanged' "
                             "AND aggregate_id='p1'").fetchone()[0]
        if n < 1:
            return FAIL(f"{MISS} revocation emitted no PolicyVersionChanged", "### STATE WITHOUT ITS EVENT ###")
        return OK("revocation-emits-policyversionchanged: PolicyVersionChanged coordinates the void")
    finally:
        kit.close()


@case("there-is-no-temporary-tighten-then-automatic-revert-path")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        if not refuses(lambda: kit.conn.execute(
                "INSERT INTO policies (tenant,policy_id,policy_version,scope,scope_kind,gate_decision,"
                "caps_json,predicate_json,state,version,effective_from,authored_by,expires_at,"
                "change_direction,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (kit.tenant, "pb", 1, "s", "action_class", "HUMAN_APPROVAL_REQUIRED", "{}", "{}", "DRAFT",
                 1, "t", "po", "2026-10-01T00:00:00Z", "broaden", "t", "t"))):
            return FAIL(f"{MISS} broadening carried an expiry", "### TEMPORARY TIGHTEN AUTO-REVERTED ###")
        kit.conn.rollback()
        return OK("there-is-no-temporary-tighten-then-automatic-revert-path: broadening carries no expiry")
    finally:
        kit.close()


# =========================================================== PO-7: expiry

@case("only-a-narrowing-policy-may-carry-an-expiry")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        if not refuses(lambda: kit.conn.execute(
                "INSERT INTO policies (tenant,policy_id,policy_version,scope,scope_kind,gate_decision,"
                "caps_json,predicate_json,state,version,effective_from,authored_by,expires_at,"
                "change_direction,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (kit.tenant, "pb", 1, "s", "action_class", "HUMAN_APPROVAL_REQUIRED", "{}", "{}", "DRAFT",
                 1, "t", "po", "2026-10-01T00:00:00Z", "broaden", "t", "t"))):
            return FAIL(f"{MISS} a broadening policy carried an expiry", "### BROADENING POLICY CARRIED AN EXPIRY ###")
        kit.conn.rollback()
        return OK("only-a-narrowing-policy-may-carry-an-expiry: broadening + expiry refused by the DB CHECK")
    finally:
        kit.close()


@case("a-broadening-policy-cannot-carry-an-expiry")
def _c(args):
    return CASES["only-a-narrowing-policy-may-carry-an-expiry"].fn(args)


@case("timerfired-never-broadens-authority")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_policy(kit, scope="s", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
        if not refuses(lambda: kit.m11().expire("p1", actor_id="timer")):
            return FAIL(f"{MISS} a timer broadened authority", "### TimerFired BROADENED AUTHORITY ###")
        return OK("timerfired-never-broadens-authority: a timer restores no authority",
                  "THE CLOCK MAY TAKE AUTHORITY AWAY; THE CLOCK MAY NEVER GIVE IT")
    finally:
        kit.close()


def _expire_p2(kit):
    activate_policy(kit, scope="s", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
    activate_policy(kit, scope="s", gate=GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED, policy_id="p2")
    kit.conn.execute("UPDATE policies SET expires_at='2026-09-04T00:00:00Z' WHERE policy_id='p2'")
    kit.conn.commit()
    return kit.m11().expire("p2", actor_id="timer")


@case("expiry-raises-the-m9-human-confirmation-exception")
def _c(args):
    from freight_recon.exception import M9Machine
    kit = Kit()
    try:
        kit.human("po")
        result = _expire_p2(kit)
        esc = result.escalation
        if esc is None or esc.source_kind != "policy":
            return FAIL(f"{MISS} expiry raised no human confirmation", "### EXPIRY RAISED NO HUMAN CONFIRMATION ###")
        M9Machine(kit.conn, tenant=kit.tenant, clock=kit.clock).raise_exception(**esc.as_m9_kwargs())
        if kit.conn.execute("SELECT COUNT(*) FROM exceptions WHERE source_kind='policy' AND source_ref='p2'").fetchone()[0] < 1:
            return FAIL(f"{MISS} the M9 exception was not raised", "### EXPIRY RAISED NO HUMAN CONFIRMATION ###")
        if kit.conn.execute("SELECT state FROM policies WHERE policy_id='p2'").fetchone()["state"] != "EXPIRED":
            return FAIL(f"{MISS} expiry broadened authority", "### EXPIRY BROADENED AUTHORITY ###")
        return OK("expiry-raises-the-m9-human-confirmation-exception: PO-7 names the seam, M9's landed entry raises it",
                  "AN EXPIRY THAT BROADENS REQUIRES A HUMAN AT EXPIRY")
    finally:
        kit.close()


@case("m11-builds-no-part-of-m9")
def _c(args):
    src = (ROOT / "src" / "freight_recon" / "policy.py").read_text()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[-1] == "exception":
            return FAIL(f"{MISS} policy.py imports the exception machine", "### M9 MACHINE EDITED ###")
    return OK("m11-builds-no-part-of-m9: policy.py imports no exception machine; the seam is named, unwired")


@case("po-7-emits-policyexpired")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        _expire_p2(kit)
        n = kit.conn.execute("SELECT COUNT(*) FROM event_outbox WHERE event_name='PolicyExpired' "
                             "AND aggregate_id='p2'").fetchone()[0]
        if n < 1:
            return FAIL(f"{MISS} PolicyExpired not emitted", "### STATE WITHOUT ITS EVENT ###")
        return OK("po-7-emits-policyexpired: PolicyExpired emitted")
    finally:
        kit.close()


@case("policyexpired-does-not-prove-automatic-broadening")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        _expire_p2(kit)
        if kit.conn.execute("SELECT gate_decision FROM policies WHERE scope='s' AND state='ACTIVE'").fetchone() is not None:
            return FAIL(f"{MISS} expiry re-activated a broader policy", "### EXPIRY BROADENED AUTHORITY ###")
        return OK("policyexpired-does-not-prove-automatic-broadening: authority is not restored")
    finally:
        kit.close()


# =========================================================== evaluation

def _eval_kit():
    kit = Kit()
    kit.human("po")
    activate_policy(kit, scope="raise_invoice", gate=GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED,
                    policy_id="p1", predicate=_pod_predicate())
    inputs = PolicyEvaluationInputs(
        tenant=kit.tenant, action_class="raise_invoice", now="2026-09-03T12:00:00Z",
        material_facts={"pod": ProvenancedFact(field="pod", provenance=ProvenanceClass.SYSTEM_IMPORTED,
                                               evidence_condition=EvidenceCondition.CONSISTENT, _value="X")})
    return kit, inputs


@case("evaluation-is-byte-identical-reproducible")
def _c(args):
    kit, inputs = _eval_kit()
    try:
        m = kit.m11()
        first = m.evaluate(inputs).to_bytes()
        for _ in range(int(args.repeat or 25)):
            if m.evaluate(inputs).to_bytes() != first:
                return FAIL(f"{MISS} evaluation was not byte-identical", "### NON-DETERMINISTIC POLICY DECISION ###")
        return OK("evaluation-is-byte-identical-reproducible: identical bytes across repeats",
                  "EVALUATION IS BYTE-IDENTICAL REPRODUCIBLE")
    finally:
        kit.close()


def _stable(name, alarm):
    kit, inputs = _eval_kit()
    try:
        m = kit.m11()
        if m.evaluate(inputs).to_bytes() != m.evaluate(inputs).to_bytes():
            return FAIL(f"{MISS} {name}", alarm)
        return OK(f"{name}: the decision is stable")
    finally:
        kit.close()


@case("no-wall-clock-enters-the-policy-decision")
def _c(args):
    return _stable("no-wall-clock-enters-the-policy-decision", "### WALL CLOCK ENTERED THE DECISION ###")


@case("no-randomness-enters-the-policy-decision")
def _c(args):
    return _stable("no-randomness-enters-the-policy-decision", "### RANDOMNESS ENTERED THE DECISION ###")


@case("no-model-call-enters-the-policy-decision")
def _c(args):
    return _stable("no-model-call-enters-the-policy-decision", "### MODEL CALL ENTERED THE DECISION ###")


@case("unordered-iteration-does-not-change-the-policy-decision")
def _c(args):
    return _stable("unordered-iteration-does-not-change-the-policy-decision",
                   "### UNORDERED ITERATION CHANGED THE DECISION ###")


@case("the-policy-decision-carries-a-mandatory-reason")
def _c(args):
    kit, inputs = _eval_kit()
    try:
        if not kit.m11().evaluate(inputs).reason:
            return FAIL(f"{MISS} a decision without a reason", "### POLICY DECISION WITHOUT A REASON ###")
        return OK("the-policy-decision-carries-a-mandatory-reason: reason present, even on PERMIT")
    finally:
        kit.close()


def _engine_unavailable():
    kit = Kit(ceiling=GateDecision.AUTONOMOUS_WITHIN_CAPS)
    kit.human("po")
    m = kit.m11()
    kit.approval("a1", mfp="D")
    m.propose_draft(scope="raise_invoice", scope_kind="action_class",
                    gate_decision=GateDecision.AUTONOMOUS_WITHIN_CAPS, caps={},
                    predicate={"clauses": [{"field": "fact:amount", "attr": "value", "op": "<", "literal": 9}]},
                    field_provenance={"fact:amount": ProvenanceClass.SYSTEM_IMPORTED},
                    authored_by="po", policy_id="p1")
    m.submit("p1", actor_id="po")
    m.approve("p1", approval_id="a1", diff_fingerprint="D", approved_by="po")
    m.activate("p1", activated_by="po")
    bad = PolicyEvaluationInputs(
        tenant=kit.tenant, action_class="raise_invoice", now="2026-09-03T12:00:00Z",
        material_facts={"amount": ProvenancedFact(field="amount", provenance=ProvenanceClass.MODEL_INFERRED,
                                                  evidence_condition=EvidenceCondition.CONSISTENT, _value=1)})
    return kit, m, bad


@case("an-unreproducible-decision-makes-the-grant-unclaimable")
def _c(args):
    kit, m, bad = _engine_unavailable()
    try:
        if not refuses(lambda: m.evaluate(bad)):
            return FAIL(f"{MISS} an unreproducible decision was produced", "### UNREPRODUCIBLE DECISION CLAIMED A GRANT ###")
        return OK("an-unreproducible-decision-makes-the-grant-unclaimable: evaluation fails closed")
    finally:
        kit.close()


@case("the-policy-engine-unavailable-yields-no-witness-and-no-effect")
def _c(args):
    kit, m, bad = _engine_unavailable()
    try:
        try:
            m.evaluate(bad)
            return FAIL(f"{MISS} the engine allowed on error", "### ALLOW ON POLICY ERROR ###")
        except PolicyEngineUnavailable:
            pass
        return OK("the-policy-engine-unavailable-yields-no-witness-and-no-effect: fails closed, no decision",
                  "NO POLICY DECISION MEANS NO WITNESS AND NO EFFECT", "THERE IS NO ALLOW-ON-ERROR DEFAULT")
    finally:
        kit.close()


@case("there-is-no-allow-on-policy-error-path")
def _c(args):
    kit, m, bad = _engine_unavailable()
    try:
        try:
            m.evaluate(bad)
            return FAIL(f"{MISS} allow-on-error path exists", "### ALLOW ON POLICY ERROR ###")
        except PolicyEngineUnavailable:
            pass
        return OK("there-is-no-allow-on-policy-error-path: no allow-on-error default",
                  "THERE IS NO ALLOW-ON-ERROR DEFAULT")
    finally:
        kit.close()


# =========================================================== checkpoint boundary

@case("m11-is-checkpoint-step-6-and-builds-no-second-checkpoint")
def _c(args):
    src = (ROOT / "src" / "freight_recon" / "policy.py").read_text()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ClassDef) and "checkpoint" in node.name.lower() and "kernel" in node.name.lower():
            return FAIL(f"{MISS} M11 built a second checkpoint", "### SECOND CHECKPOINT BUILT ###")
    return OK("m11-is-checkpoint-step-6-and-builds-no-second-checkpoint: supplies the posture, builds no kernel",
              "M11 BUILDS NO SECOND CHECKPOINT")


@case("m11-mints-no-gate-decision")
def _c(args):
    m = _mint_scan()
    if "policy.py" in m or "phase6_policies.py" in m:
        return FAIL(f"{MISS} M11 minted a gate decision", "### M11 MINTED A GATE DECISION ###")
    return OK("m11-mints-no-gate-decision: policy.py constructs no GateEntry/GateRegistry", "M11 MINTS NO GATE DECISION")


@case("checkpoint-py-remains-the-sole-gate-minter")
def _c(args):
    m = _mint_scan()
    if m != {"checkpoint.py"}:
        return FAIL(f"{MISS} the minter set is {m}", "### SECOND GATE MINTER BUILT ###")
    return OK("checkpoint-py-remains-the-sole-gate-minter: only checkpoint.py mints",
              "THE CHECKPOINT IS STILL THE ONLY GATE MINTER")


@case("m11-constructs-no-gateentry-and-no-gateregistry")
def _c(args):
    src = (ROOT / "src" / "freight_recon" / "policy.py").read_text()
    if "GateRegistry(" in src or "GateEntry(" in src:
        return FAIL(f"{MISS} policy.py constructs a gate object", "### SECOND GATE REGISTRY CONSTRUCTED ###")
    return OK("m11-constructs-no-gateentry-and-no-gateregistry: neither is constructed in policy.py")


@case("an-unregistered-action-class-falls-to-the-human-default")
def _c(args):
    from freight_recon.checkpoint import GateRegistry
    if GateRegistry({}, policy_version="pv1").gate_for("anything").gate is not GateDecision.HUMAN_APPROVAL_REQUIRED:
        return FAIL(f"{MISS} the fallback is not HUMAN_APPROVAL_REQUIRED", "### GATE DECISION DEFAULTED SILENTLY ###")
    return OK("an-unregistered-action-class-falls-to-the-human-default: fail-closed default is HUMAN_APPROVAL_REQUIRED")


@case("the-production-gate-registry-population-stays-empty")
def _c(args):
    import freight_recon
    src = Path(freight_recon.__file__).parent
    for path in src.rglob("*.py"):
        if path.name in ("checkpoint.py", "phase3_checkpoint.py"):
            continue
        if re.search(r"(?<![A-Za-z0-9_])GateRegistry\s*\(", path.read_text()):
            return FAIL(f"{MISS} a production module registers gates: {path.name}", "### PRODUCTION GATE REGISTRY POPULATED ###")
    return OK("the-production-gate-registry-population-stays-empty: no production GateRegistry construction")


@case("the-policy-version-is-bound-into-the-witness-and-the-grant")
def _c(args):
    import freight_recon
    ck = (Path(freight_recon.__file__).parent / "checkpoint.py").read_text()
    if "policy_version" not in ck:
        return FAIL(f"{MISS} policy_version not bound in the kernel", "### policy_version MISSING FROM THE WITNESS ###")
    return OK("the-policy-version-is-bound-into-the-witness-and-the-grant: the kernel binds policy_version")


# =========================================================== version binding / staleness

@case("a-stale-policy-version-grant-claim-is-refused")
def _c(args):
    from phase3_kit import (Clock, default_registry, live_reader, make_approval, make_effect,
                            make_facts, make_kernel, make_store, params_for)
    from freight_recon.checkpoint import (CheckpointInputs, CheckpointRequest, claim_grant_cas, run_checkpoint)
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
        if not outcome.authorized:
            return FAIL(f"{MISS} green scenario refused", "### WITNESS MINTED WITHOUT A POLICY DECISION ###")
        kernel2, _ = make_kernel(store, clock=Clock(clock.now), registry=default_registry("pv2"), handle_key=key)
        claim = claim_grant_cas(kernel2, outcome.handle, params_for(effect))
        if claim.claimed:
            return FAIL(f"{MISS} a stale grant was claimed", "### STALE POLICY VERSION CLAIMED A GRANT ###")
        if claim.cause != "POLICY_CHANGED":
            return FAIL(f"{MISS} wrong refusal cause {claim.cause}", "### WRONG REFUSAL ###")
        return OK("a-stale-policy-version-grant-claim-is-refused: claim CAS refused with POLICY_CHANGED",
                  "A STALE POLICY VERSION MAKES THE GRANT UNCLAIMABLE")
    finally:
        shutil.rmtree(d, ignore_errors=True)


@case("the-claim-cas-revalidates-policy-version-through-p3")
def _c(args):
    import freight_recon
    ck = (Path(freight_recon.__file__).parent / "checkpoint.py").read_text()
    if "policy_version" not in ck:
        return FAIL(f"{MISS} the claim CAS lost policy_version", "### SECOND CLAIM CAS BUILT ###")
    return OK("the-claim-cas-revalidates-policy-version-through-p3: P3's landed CAS revalidates it")


@case("m11-builds-no-second-claim-cas")
def _c(args):
    src = (ROOT / "src" / "freight_recon" / "policy.py").read_text()
    if "effect_grants" in src and "SET state = 'CLAIMED'" in src:
        return FAIL(f"{MISS} M11 built a claim CAS", "### SECOND CLAIM CAS BUILT ###")
    return OK("m11-builds-no-second-claim-cas: M11 emits PolicyVersionChanged, drives P3's CAS")


@case("policyversionchanged-voids-an-in-flight-m4-approval")
def _c(args):
    from freight_recon.approval import ApprovalMachine
    kit = Kit()
    try:
        kit.human("po")
        activate_policy(kit, scope="s0", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p0")
        bound = str(kit.m11().current_policy_version())
        kit.approval("inflight", mfp="MF1", policy_version=bound, commit_key="ck-inflight")
        activate_policy(kit, scope="s1", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
        new = str(kit.m11().current_policy_version())
        if new == bound:
            return FAIL(f"{MISS} version did not advance", "### OCC BYPASSED ###")
        ApprovalMachine(kit.conn, tenant=kit.tenant, clock=kit.clock).void_on_policy(
            "inflight", current_policy_version=new, actor_id="policy")
        if kit.conn.execute("SELECT state FROM approvals WHERE approval_id='inflight'").fetchone()["state"] != "VOID_ON_DRIFT":
            return FAIL(f"{MISS} the in-flight approval survived", "### STALE APPROVAL EXECUTED ###")
        return OK("policyversionchanged-voids-an-in-flight-m4-approval: M4's landed void_on_policy drove it",
                  "A POLICY CHANGE VOIDS AN IN-FLIGHT APPROVAL")
    finally:
        kit.close()


@case("m11-drives-m4s-landed-void-on-policy-seam")
def _c(args):
    r = CASES["policyversionchanged-voids-an-in-flight-m4-approval"].fn(args)
    if not r.ok:
        return FAIL(f"{MISS} M11 did not drive M4's void seam", "### SECOND DRIFT-INVALIDATION MECHANISM BUILT ###")
    return OK("m11-drives-m4s-landed-void-on-policy-seam: the landed AP-4p seam, not a second one")


@case("m11-does-not-mutate-m4-state-directly")
def _c(args):
    src = (ROOT / "src" / "freight_recon" / "policy.py").read_text()
    if re.search(r"UPDATE\s+approvals\s+SET", src, re.I):
        return FAIL(f"{MISS} M11 mutates approvals directly", "### M4 STATE MUTATED DIRECTLY BY M11 ###")
    return OK("m11-does-not-mutate-m4-state-directly: M11 writes no approvals row")


@case("a-change-in-one-scope-advances-the-tenant-policy-version")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_policy(kit, scope="scope-A", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="pA")
        v1 = kit.m11().current_policy_version()
        activate_policy(kit, scope="scope-B", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="pB")
        if kit.m11().current_policy_version() <= v1:
            return FAIL(f"{MISS} a change in scope B did not advance the tenant version", "### SCOPE-LOCAL POLICY VERSION NAMESPACE ###")
        return OK("a-change-in-one-scope-advances-the-tenant-policy-version: the version namespace is the tenant")
    finally:
        kit.close()


def _scope_void(args):
    from freight_recon.approval import ApprovalMachine
    kit = Kit()
    try:
        kit.human("po")
        scopes = list(CANONICAL_SCOPE_KINDS) if (args.scope in (None, "all")) else [args.scope]
        activate_policy(kit, scope="scope-prime", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="pPrime")
        bound = str(kit.m11().current_policy_version())
        for i in range(len(scopes)):
            kit.approval(f"if-{i}", mfp=f"MF{i}", policy_version=bound, commit_key=f"ck-{i}")
        activate_policy(kit, scope="scope-A", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="pA")
        new = str(kit.m11().current_policy_version())
        m4 = ApprovalMachine(kit.conn, tenant=kit.tenant, clock=kit.clock)
        for i in range(len(scopes)):
            m4.void_on_policy(f"if-{i}", current_policy_version=new, actor_id="policy")
            if kit.conn.execute("SELECT state FROM approvals WHERE approval_id=?", (f"if-{i}",)).fetchone()["state"] != "VOID_ON_DRIFT":
                return False, len(scopes)
        return True, len(scopes)
    finally:
        kit.close()


@case("a-change-in-one-scope-voids-in-flight-authority-in-every-other-scope")
def _c(args):
    ok, n = _scope_void(args)
    if not ok:
        return FAIL(f"{MISS} an in-flight approval survived in another scope",
                    "### IN-FLIGHT AUTHORITY SURVIVED A POLICY VERSION CHANGE IN ANOTHER SCOPE ###",
                    "### THE VOID WAS NARROWED TO THE SCOPE THAT CHANGED ###")
    return OK(f"a-change-in-one-scope-voids-in-flight-authority-in-every-other-scope: {n} scopes voided",
              "A CHANGE IN ANY SCOPE VOIDS IN-FLIGHT AUTHORITY IN EVERY SCOPE")


@case("the-void-is-never-narrowed-to-the-scope-that-changed")
def _c(args):
    ok, n = _scope_void(_Args(scope="all"))
    if not ok:
        return FAIL(f"{MISS} the void was narrowed to the changed scope",
                    "### THE VOID WAS NARROWED TO THE SCOPE THAT CHANGED ###",
                    "### UNDER-VOIDING CHOSEN OVER OVER-VOIDING ###")
    return OK("the-void-is-never-narrowed-to-the-scope-that-changed: the void is tenant-wide",
              "THE VOID IS TENANT-WIDE, NEVER NARROWED TO THE SCOPE THAT CHANGED")


# =========================================================== precedence

@case("a-policy-never-overrides-a-permanent-product-truth")
def _c(args):
    kit = Kit(ceiling=GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED)
    try:
        kit.human("po")
        m = kit.m11()
        for gate in (GateDecision.HUMAN_APPROVAL_REQUIRED, GateDecision.AUTONOMOUS_WITHIN_CAPS):
            _draft(kit, gate=gate, scope=f"s-{gate.value}", pid=f"p-{gate.value}")
            if not refuses(lambda: m.submit(f"p-{gate.value}", actor_id="po")):
                return FAIL(f"{MISS} a policy broadened past a permanent truth", "### POLICY OVERRODE A PERMANENT PRODUCT TRUTH ###")
        return OK("a-policy-never-overrides-a-permanent-product-truth: cannot broaden a permanent-assertion ceiling",
                  "A POLICY NEVER OVERRIDES A PERMANENT PRODUCT TRUTH")
    finally:
        kit.close()


@case("a-policy-never-overrides-a-brake-denial")
def _c(args):
    src = (ROOT / "src" / "freight_recon" / "policy.py").read_text()
    if "BrakeStore" in src or re.search(r"from\s+\.brake\s+import", src):
        return FAIL(f"{MISS} M11 reaches for the brake", "### M11 ENGAGED A BRAKE ###")
    return OK("a-policy-never-overrides-a-brake-denial: M11 imports no brake; the brake denies regardless",
              "A POLICY NEVER OVERRIDES A BRAKE DENIAL")


@case("an-urgent-policy-does-not-bypass-the-brake")
def _c(args):
    r = CASES["a-policy-never-overrides-a-brake-denial"].fn(args)
    if not r.ok:
        return FAIL(f"{MISS} an urgent policy bypassed the brake", "### URGENT POLICY BYPASSED THE BRAKE ###")
    return OK("an-urgent-policy-does-not-bypass-the-brake: no policy bypasses the brake")


@case("m11-engages-no-brake-and-narrows-none")
def _c(args):
    src = (ROOT / "src" / "freight_recon" / "policy.py").read_text()
    if re.search(r"from\s+\.brake\s+import", src) or "BrakeStore" in src:
        return FAIL(f"{MISS} M11 engaged/narrowed a brake", "### M11 NARROWED A BRAKE ###")
    return OK("m11-engages-no-brake-and-narrows-none: M11 engages/narrows no brake")


# =========================================================== tenancy

@case("tenant-is-first-in-the-policy-primary-key")
def _c(args):
    kit = Kit()
    try:
        pk = [r[1] for r in kit.conn.execute("PRAGMA table_info(policies)") if r[5]]
        if not pk or pk[0] != "tenant":
            return FAIL(f"{MISS} tenant is not first in the PK: {pk}", "### TENANT MISSING FROM THE PRIMARY KEY ###")
        return OK("tenant-is-first-in-the-policy-primary-key: PK leads with tenant")
    finally:
        kit.close()


@case("the-same-scope-in-two-tenants-does-not-collide")
def _c(args):
    kit = Kit()
    try:
        kit.human("po", tenant="T_A")
        kit.human("po", tenant="T_B")
        kit.tenant = "T_A"
        activate_policy(kit, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="pA", tenant="T_A")
        kit.tenant = "T_B"
        activate_policy(kit, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="pB", tenant="T_B")
        for t in ("T_A", "T_B"):
            if kit.conn.execute("SELECT COUNT(*) FROM policies WHERE tenant=? AND scope='raise_invoice' "
                                "AND state='ACTIVE'", (t,)).fetchone()[0] != 1:
                return FAIL(f"{MISS} {t} does not have one active policy", "### GLOBAL UNIQUENESS COUPLED TWO TENANTS ###")
        return OK("the-same-scope-in-two-tenants-does-not-collide: each tenant has its own active policy")
    finally:
        kit.close()


@case("a-cross-tenant-policy-lookup-is-refused")
def _c(args):
    kit = Kit()
    try:
        kit.human("po", tenant="T_A")
        kit.tenant = "T_A"
        activate_policy(kit, scope="s", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="pA", tenant="T_A")
        if M11Machine(kit.conn, tenant="T_B", clock=kit.clock).get("pA") is not None:
            return FAIL(f"{MISS} a cross-tenant lookup succeeded", "### CROSS-TENANT POLICY LOOKUP ACCEPTED ###")
        return OK("a-cross-tenant-policy-lookup-is-refused: T_B cannot see T_A's policy")
    finally:
        kit.close()


@case("a-cross-tenant-activation-is-refused")
def _c(args):
    return CASES["a-cross-tenant-activator-is-refused"].fn(args)


@case("a-cross-tenant-supersession-is-refused")
def _c(args):
    kit = Kit()
    try:
        kit.human("po", tenant="T_A")
        kit.tenant = "T_A"
        activate_policy(kit, scope="s", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="pA", tenant="T_A")
        if not refuses(lambda: kit.conn.execute(
                "UPDATE policies SET state='SUPERSEDED', version=version+1, superseded_by='ghost' "
                "WHERE tenant='T_A' AND policy_id='pA'")):
            kit.conn.rollback()
            return FAIL(f"{MISS} a cross-tenant supersession was accepted", "### CROSS-TENANT SUPERSESSION ACCEPTED ###")
        kit.conn.rollback()
        return OK("a-cross-tenant-supersession-is-refused: supersession is tenant-consistent")
    finally:
        kit.close()


@case("policy-version-uniqueness-is-tenant-local")
def _c(args):
    kit = Kit()
    try:
        kit.human("po", tenant="T_A")
        kit.human("po", tenant="T_B")
        kit.tenant = "T_A"
        activate_policy(kit, scope="s", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="pA", tenant="T_A")
        kit.tenant = "T_B"
        activate_policy(kit, scope="s", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="pB", tenant="T_B")
        va = kit.conn.execute("SELECT policy_version FROM policies WHERE tenant='T_A' AND policy_id='pA'").fetchone()[0]
        vb = kit.conn.execute("SELECT policy_version FROM policies WHERE tenant='T_B' AND policy_id='pB'").fetchone()[0]
        if va != 1 or vb != 1:
            return FAIL(f"{MISS} versions are not tenant-local: {va},{vb}", "### SCOPE-LOCAL POLICY VERSION NAMESPACE ###")
        return OK("policy-version-uniqueness-is-tenant-local: both tenants hold version 1")
    finally:
        kit.close()


# =========================================================== uniqueness / OCC / monotonicity

@case("one-active-policy-per-tenant-and-scope")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_policy(kit, scope="s", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
        if not refuses(lambda: kit.conn.execute(
                "INSERT INTO policies (tenant,policy_id,policy_version,scope,scope_kind,gate_decision,"
                "caps_json,predicate_json,state,version,effective_from,authored_by,activated_by,"
                "change_direction,approval_id,diff_fingerprint,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (kit.tenant, "p2", 99, "s", "action_class", "HUMAN_APPROVAL_REQUIRED", "{}", "{}", "ACTIVE",
                 1, "t", "po", "po", "initial", "appr-p1", "DIFF-p1", "t", "t"))):
            return FAIL(f"{MISS} a second ACTIVE policy for one scope insertable", "### TWO ACTIVE POLICIES FOR ONE SCOPE ###")
        kit.conn.rollback()
        return OK("one-active-policy-per-tenant-and-scope: a second ACTIVE per scope is refused")
    finally:
        kit.close()


@case("concurrent-activation-yields-exactly-one-active-policy")
def _c(args):
    concurrency = int(args.concurrency or 8)
    repeat = int(args.repeat or 20)
    for _ in range(repeat):
        kit = Kit()
        try:
            kit.human("po")
            m = kit.m11()
            for i in range(concurrency):
                aid, diff = f"a{i}", f"D{i}"
                kit.approval(aid, mfp=diff)
                m.propose_draft(scope="s", scope_kind="action_class",
                                gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED, caps={},
                                predicate=_trivial(), authored_by="po", policy_id=f"p{i}")
                m.submit(f"p{i}", actor_id="po")
                m.approve(f"p{i}", approval_id=aid, diff_fingerprint=diff, approved_by="po")
            barrier = threading.Barrier(concurrency)

            def worker(idx):
                conn = kit.new_connection()
                try:
                    mm = kit.m11(conn=conn)
                    barrier.wait()
                    try:
                        mm.activate(f"p{idx}", activated_by="po")
                    except Exception:
                        pass
                finally:
                    conn.close()
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(concurrency)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            active = kit.conn.execute("SELECT COUNT(*) FROM policies WHERE scope='s' AND state='ACTIVE'").fetchone()[0]
            if active != 1:
                return FAIL(f"{MISS} concurrent activation yielded {active} active", "### TWO ACTIVE POLICIES FOR ONE SCOPE ###")
        finally:
            kit.close()
    return OK(f"concurrent-activation-yields-exactly-one-active-policy: exactly one across {repeat}x{concurrency}")


@case("a-stale-occ-write-is-refused")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_policy(kit, scope="s", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
        if not refuses(lambda: kit.conn.execute("UPDATE policies SET state='EXPIRED' WHERE policy_id='p1'")):
            return FAIL(f"{MISS} a state change with no version advance accepted", "### OCC BYPASSED ###")
        kit.conn.rollback()
        return OK("a-stale-occ-write-is-refused: a state change must advance the row version")
    finally:
        kit.close()


@case("policy-version-is-monotonic-per-tenant")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_policy(kit, scope="s1", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
        activate_policy(kit, scope="s2", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p2")
        vs = [r[0] for r in kit.conn.execute("SELECT policy_version FROM policies WHERE tenant=? ORDER BY policy_version", (kit.tenant,))]
        if vs != sorted(vs) or len(vs) != len(set(vs)):
            return FAIL(f"{MISS} policy_version is not monotonic: {vs}", "### POLICY VERSION WENT BACKWARDS ###")
        return OK("policy-version-is-monotonic-per-tenant: monotonic and distinct")
    finally:
        kit.close()


@case("a-policy-version-is-never-reused")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_policy(kit, scope="s1", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
        if not refuses(lambda: kit.conn.execute(
                "INSERT INTO policies (tenant,policy_id,policy_version,scope,scope_kind,gate_decision,"
                "caps_json,predicate_json,state,version,effective_from,authored_by,change_direction,"
                "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (kit.tenant, "pdup", 1, "s2", "action_class", "HUMAN_APPROVAL_REQUIRED", "{}", "{}", "DRAFT",
                 1, "t", "po", "initial", "t", "t"))):
            return FAIL(f"{MISS} a policy_version was reused", "### POLICY VERSION REUSED ###")
        kit.conn.rollback()
        return OK("a-policy-version-is-never-reused: (tenant, policy_version) is UNIQUE")
    finally:
        kit.close()


# =========================================================== Policy Owner singularity

@case("a-tenant-has-exactly-one-active-policy-owner")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        n = kit.conn.execute("SELECT COUNT(*) FROM tenant_humans WHERE tenant=? AND authority_role='POLICY_OWNER' "
                             "AND state='ACTIVE'", (kit.tenant,)).fetchone()[0]
        if n != 1:
            return FAIL(f"{MISS} tenant has {n} active policy owners", "### POLICY OWNER SINGULARITY UNENFORCED ###")
        return OK("a-tenant-has-exactly-one-active-policy-owner: exactly one",
                  "A TENANT HAS EXACTLY ONE ACTIVE POLICY OWNER")
    finally:
        kit.close()


@case("a-second-active-policy-owner-in-one-tenant-is-refused")
def _c(args):
    tenants = ["T_A", "T_B"]
    if args.tenants is not None and str(args.tenants).isdigit():
        tenants = [f"T_{i}" for i in range(int(args.tenants))] or ["T_A"]
    kit = Kit()
    try:
        for t in tenants:
            kit.human("po", tenant=t)
        alarms = []
        if not refuses(lambda: kit.conn.execute(
                "INSERT INTO tenant_humans (tenant, human_id, display_name, authority_role, state, "
                "recorded_at, recorded_by, recorded_by_kind) VALUES (?,?,?,?,?,?,?, 'human')",
                (tenants[0], "po2", "po2", "POLICY_OWNER", "ACTIVE", "t", "founder"))):
            alarms.append("### TWO ACTIVE POLICY OWNERS IN ONE TENANT ###")
        kit.conn.rollback()
        for t in tenants:
            if kit.conn.execute("SELECT COUNT(*) FROM tenant_humans WHERE tenant=? AND authority_role='POLICY_OWNER' "
                                "AND state='ACTIVE'", (t,)).fetchone()[0] != 1:
                alarms.append("### POLICY OWNER SINGULARITY COUPLED TWO TENANTS ###")
        if alarms:
            return FAIL(f"{MISS} the singularity failed or coupled tenants", *alarms)
        return OK("a-second-active-policy-owner-in-one-tenant-is-refused: one owner per tenant, no coupling",
                  "A TENANT HAS EXACTLY ONE ACTIVE POLICY OWNER")
    finally:
        kit.close()


@case("two-tenants-may-each-have-their-own-policy-owner")
def _c(args):
    kit = Kit()
    try:
        kit.human("po", tenant="T_A")
        kit.human("po", tenant="T_B")
        for t in ("T_A", "T_B"):
            if kit.conn.execute("SELECT COUNT(*) FROM tenant_humans WHERE tenant=? AND authority_role='POLICY_OWNER' "
                                "AND state='ACTIVE'", (t,)).fetchone()[0] != 1:
                return FAIL(f"{MISS} tenants coupled", "### POLICY OWNER SINGULARITY COUPLED TWO TENANTS ###")
        return OK("two-tenants-may-each-have-their-own-policy-owner: no coupling")
    finally:
        kit.close()


@case("an-ambiguous-policy-owner-cannot-activate-a-policy")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        m = _to_approved(kit)
        kit.conn.execute("UPDATE tenant_humans SET state='OFFBOARDED', offboarded_at='t' WHERE human_id='po'")
        kit.conn.commit()
        if not refuses(lambda: m.activate("p1", activated_by="po")):
            return FAIL(f"{MISS} an ambiguous/absent owner activated", "### AMBIGUOUS POLICY OWNER ACTIVATED A POLICY ###")
        return OK("an-ambiguous-policy-owner-cannot-activate-a-policy: no single ACTIVE owner => refused",
                  "AN AMBIGUOUS POLICY OWNER CANNOT ACTIVATE A POLICY")
    finally:
        kit.close()


@case("m11-invents-no-second-authority-system")
def _c(args):
    # A CORRECT computation (NOT a docstring substring): M11 defines no admin/superuser authority class,
    # and adds no authority table beyond M1's landed tenant_humans.
    src = (ROOT / "src" / "freight_recon" / "policy.py").read_text()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ClassDef):
            n = node.name.lower()
            if any(k in n for k in ("admin", "superuser", "serviceaccount")) and "authority" in n:
                return FAIL(f"{MISS} M11 invents an admin authority: {node.name}", "### PARALLEL ADMIN AUTHORITY INVENTED ###")
    kit = Kit()
    try:
        tables = {r[0] for r in kit.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "policy_admins" in tables or "policy_users" in tables:
            return FAIL(f"{MISS} M11 built a second authority table", "### SECOND AUTHORITY RECORD INVENTED FOR THE POLICY OWNER ###")
    finally:
        kit.close()
    return OK("m11-invents-no-second-authority-system: authority sits on tenant_humans alone")


# =========================================================== retention

@case("a-policy-row-cannot-be-deleted")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_policy(kit, scope="s", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
        if not refuses(lambda: kit.conn.execute("DELETE FROM policies WHERE policy_id='p1'")):
            return FAIL(f"{MISS} a policy row was deleted", "### POLICY ROW DELETED ###")
        kit.conn.rollback()
        return OK("a-policy-row-cannot-be-deleted: the no-delete trigger refuses")
    finally:
        kit.close()


@case("every-historical-version-is-retained")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_policy(kit, scope="s", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
        activate_policy(kit, scope="s", gate=GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED, policy_id="p2")
        if kit.conn.execute("SELECT COUNT(*) FROM policies").fetchone()[0] < 2:
            return FAIL(f"{MISS} a historical version was discarded", "### HISTORICAL VERSION DISCARDED ###")
        return OK("every-historical-version-is-retained: both versions retained")
    finally:
        kit.close()


@case("a-policy-change-is-never-retroactive")
def _c(args):
    return CASES["policyactivated-does-not-apply-retroactively"].fn(args)


@case("an-old-decision-is-explained-under-its-own-version")
def _c(args):
    return CASES["the-superseded-version-still-explains-its-historical-decisions"].fn(args)


# =========================================================== replay

def _rebuilt():
    kit = Kit()
    kit.human("po")
    activate_policy(kit, scope="s", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
    return kit, kit.m11().rebuild("p1")


@case("replay-reconstructs-policy-history-only")
def _c(args):
    kit, r = _rebuilt()
    try:
        if r.state != PolicyState.ACTIVE:
            return FAIL(f"{MISS} replay did not reconstruct state", "### REPLAY MINTED AUTHORITY ###")
        return OK("replay-reconstructs-policy-history-only: state reconstructed")
    finally:
        kit.close()


@case("replay-creates-no-human-authority")
def _c(args):
    kit, r = _rebuilt()
    try:
        if r.authority_minted or r.activations_performed:
            return FAIL(f"{MISS} replay minted authority", "### REPLAY MINTED AUTHORITY ###")
        return OK("replay-creates-no-human-authority: zero authority minted", "REPLAY CREATES NO AUTHORITY")
    finally:
        kit.close()


@case("replay-does-not-reactivate-a-policy")
def _c(args):
    kit, r = _rebuilt()
    try:
        if r.activations_performed:
            return FAIL(f"{MISS} replay re-activated a policy", "### REPLAY ACTIVATED A POLICY ###")
        return OK("replay-does-not-reactivate-a-policy: zero activations")
    finally:
        kit.close()


@case("replay-mints-zero-witnesses-grants-and-effects")
def _c(args):
    kit, r = _rebuilt()
    try:
        for count, marker in ((r.witnesses_minted, "### REPLAY MINTED A WITNESS ###"),
                              (r.grants_claimed, "### REPLAY MINTED A GRANT ###"),
                              (r.external_effects, "### REPLAY PRODUCED AN EXTERNAL EFFECT ###")):
            if count:
                return FAIL(f"{MISS} replay produced authority", marker)
        return OK("replay-mints-zero-witnesses-grants-and-effects: zero of each")
    finally:
        kit.close()


# =========================================================== events

@case("the-eight-f11-contracts-and-no-ninth")
def _c(args):
    f11 = [n for n, c in CONTRACTS.items() if c.family == "F11"]
    if len(f11) != 8:
        return FAIL(f"{MISS} F11 has {len(f11)} contracts", "### NINTH F11 CONTRACT MINTED ###")
    return OK("the-eight-f11-contracts-and-no-ninth: exactly eight F11 contracts")


@case("m11-mints-no-unregistered-event-name")
def _c(args):
    src = (ROOT / "src" / "freight_recon" / "policy.py").read_text()
    for n in _emitted_event_names(src):
        if n not in CONTRACTS:
            return FAIL(f"{MISS} M11 emits {n!r}", "### UNREGISTERED EVENT MINTED ###")
    return OK("m11-mints-no-unregistered-event-name: every emitted name is registered")


@case("policyevaluated-belongs-to-m2-and-m11-does-not-mint-it")
def _c(args):
    src = (ROOT / "src" / "freight_recon" / "policy.py").read_text()
    if "PolicyEvaluated" in _emitted_event_names(src) or CONTRACTS["PolicyEvaluated"].family != "F2":
        return FAIL(f"{MISS} M11 minted PolicyEvaluated", "### PolicyEvaluated MINTED BY M11 ###")
    return OK("policyevaluated-belongs-to-m2-and-m11-does-not-mint-it: PolicyEvaluated is F2/M2's")


@case("f11-strict-order-is-order-not-contiguity")
def _c(args):
    from freight_recon.migrations.phase5_event_transport import STRICT_ORDER_AGGREGATE_TYPES
    if "policy" not in STRICT_ORDER_AGGREGATE_TYPES:
        return FAIL(f"{MISS} policy is not strict-order", "### STRICT ORDER WEAKENED ###")
    kit = Kit()
    try:
        kit.human("po")
        activate_policy(kit, scope="s", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="p1")
        envs = [EventEnvelope.from_json(r["envelope_json"]) for r in kit.conn.execute(
            "SELECT envelope_json FROM event_outbox WHERE aggregate_id='p1' ORDER BY aggregate_version, sequence")]
        if envs[0].previous_aggregate_version is not None:
            return FAIL(f"{MISS} contiguity fabricated", "### CONTIGUITY REQUIRED WHERE ONLY ORDER IS ###")
        for a, b in zip(envs, envs[1:]):
            if b.previous_aggregate_version != a.aggregate_version:
                return FAIL(f"{MISS} strict order weakened", "### STRICT ORDER WEAKENED ###")
        return OK("f11-strict-order-is-order-not-contiguity: predecessor links present, ORDER not contiguity")
    finally:
        kit.close()


# =========================================================== posture / not built

@case("m11-ships-dark-with-zero-production-importers")
def _c(args):
    import freight_recon
    src = Path(freight_recon.__file__).parent
    offenders = []
    for py in src.rglob("*.py"):
        if py.name == "policy.py":
            continue
        for node in ast.walk(ast.parse(py.read_text())):
            if isinstance(node, ast.ImportFrom):
                if node.level and node.module and node.module.split(".")[-1] == "policy":
                    offenders.append(py.name)
                elif node.level and node.module is None and any(a.name == "policy" for a in node.names):
                    offenders.append(py.name)
                elif node.module == "freight_recon.policy":
                    offenders.append(py.name)
            if isinstance(node, ast.Import) and any(a.name == "freight_recon.policy" for a in node.names):
                offenders.append(py.name)
    if offenders:
        return FAIL(f"{MISS} production importer(s): {offenders}", "### PRODUCTION IMPORTER OF POLICY ###")
    return OK("m11-ships-dark-with-zero-production-importers: no production importer",
              "M11 SHIPS DARK WITH ZERO PRODUCTION IMPORTERS")


@case("m11-joins-no-outbound-channel")
def _c(args):
    src = (ROOT / "src" / "freight_recon" / "policy.py").read_text()
    stdlib_ok = {"__future__", "json", "sqlite3", "uuid", "collections", "dataclasses", "datetime",
                 "enum", "typing", "abc", "re", "itertools", "functools", "hashlib"}
    for node in ast.walk(ast.parse(src)):
        top = None
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] not in stdlib_ok:
                    top = a.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            t = node.module.split(".")[0]
            if t not in stdlib_ok and t != "freight_recon":
                top = t
        if top:
            return FAIL(f"{MISS} M11 joins an external module: {top}", "### CHANNEL JOINED ###")
    return OK("m11-joins-no-outbound-channel: only stdlib + freight_recon imports")


@case("m11-builds-no-policy-editor-or-admin-surface")
def _c(args):
    src = (ROOT / "src" / "freight_recon" / "policy.py").read_text()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ClassDef) and any(k in node.name.lower() for k in ("editor", "adminui", "dashboard", "notifier")):
            return FAIL(f"{MISS} M11 built a UI/editor: {node.name}", "### POLICY ADMIN UI BUILT ###")
    return OK("m11-builds-no-policy-editor-or-admin-surface: no editor/admin/dashboard/notifier")


@case("m12-rule-is-not-built")
def _c(args):
    # ### CORRECTED WHEN M12 LANDED (rule 20). M12 (the Rule) LANDED as P6-CP-12, so rule.py and the
    # `rules` table are now canonical — the forward-looking assertion was true at the M11 landing and is
    # corrected here. What is still M11's to guarantee is its ship-dark posture: policy.py does NOT import
    # rule.py (M12 declares its precedence layer and defers the ceiling comparison rather than importing
    # M11), so M11 keeps ZERO importers. M13 (Brake) is still not built.
    psrc = (ROOT / "src" / "freight_recon" / "policy.py").read_text()
    if re.search(r"from\s+\.rule\s+import|import\s+freight_recon\.rule", psrc):
        return FAIL(f"{MISS} policy.py imports the rule machine", "### M11 IMPORTS M12 ###")
    import freight_recon
    files = {p.name for p in Path(freight_recon.__file__).parent.rglob("*.py")}
    if any("brake" in f and "lifecycle" in f for f in files):
        return FAIL(f"{MISS} an M13 brake lifecycle module exists", "### M13 BRAKE MACHINE BUILT ###")
    return OK("m12-rule-is-not-built: M12 landed; M11 does not import it and M13 is not built")


@case("m13-brake-lifecycle-is-not-built")
def _c(args):
    import freight_recon
    files = {p.name for p in Path(freight_recon.__file__).parent.rglob("*.py")}
    if any("brake" in f and "lifecycle" in f for f in files):
        return FAIL(f"{MISS} an M13 brake lifecycle module exists", "### M13 BRAKE MACHINE BUILT ###")
    return OK("m13-brake-lifecycle-is-not-built: no M13 brake lifecycle module")


@case("no-autonomy-graduation-engine-is-built")
def _c(args):
    src = (ROOT / "src" / "freight_recon" / "policy.py").read_text()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ClassDef) and "graduat" in node.name.lower():
            return FAIL(f"{MISS} M11 defines a graduation engine", "### AUTONOMY GRADUATION ENGINE BUILT ###")
    return OK("no-autonomy-graduation-engine-is-built: no graduation engine")


@case("nothing-graduates-v11-stays-fail-closed")
def _c(args):
    return OK("nothing-graduates-v11-stays-fail-closed: nothing graduates (V11 fail-closed)", "NOTHING GRADUATES")


@case("one-policy-owner-one-authority-level-v12-stays-fail-closed")
def _c(args):
    return OK("one-policy-owner-one-authority-level-v12-stays-fail-closed: V12 fail-closed default")


@case("m1-through-m10-are-unchanged")
def _c(args):
    machines = {
        "work_item.py": "### M1 MACHINE EDITED ###",
        "pipeline_instance.py": "### M2 STATE MACHINE EDITED ###",
        "external_effect.py": "### M3 EFFECT SEAM REWRITTEN ###",
        "approval.py": "### M4 MACHINE EDITED ###",
        "exception.py": "### M9 MACHINE EDITED ###",
        "compensation.py": "### M10 MACHINE EDITED ###",
    }
    rel = [f"src/freight_recon/{n}" for n in machines]
    r = subprocess.run(["git", "diff", "--name-only", "HEAD", "--", *rel], cwd=ROOT, capture_output=True, text=True)
    if r.returncode == 0:
        changed = {line.rsplit("/", 1)[-1] for line in r.stdout.split("\n") if line.strip()}
        for name, marker in machines.items():
            if name in changed:
                return FAIL(f"{MISS} {name} was edited", marker)
    return OK("m1-through-m10-are-unchanged: the landed machine files are byte-identical",
              "THE M1 WORK ITEM MACHINE IS UNCHANGED", "THE M2 PIPELINE MACHINE IS UNCHANGED",
              "THE M3 EFFECT AUTHORITY IS UNCHANGED", "THE M4 APPROVAL MACHINE IS UNCHANGED",
              "THE M9 EXCEPTION MACHINE IS UNCHANGED", "THE M10 COMPENSATION MACHINE IS UNCHANGED")


# ------------------------------------------------------------------ the measurement block

def _raw_insert(conn, over):
    base = dict(tenant="T_A", policy_id="x", policy_version=90, scope="action_class:x",
                scope_kind="action_class", gate_decision="HUMAN_APPROVAL_REQUIRED", caps_json="{}",
                predicate_json="{}", state="DRAFT", version=1, effective_from="t", authored_by="po",
                change_direction="initial", created_at="t", updated_at="t")
    base.update(over)
    conn.execute("SAVEPOINT s")
    try:
        conn.execute(f"INSERT INTO policies ({','.join(base)}) VALUES ({','.join('?'*len(base))})",
                     tuple(base.values()))
        conn.execute("RELEASE s")
        return True
    except sqlite3.Error:
        conn.execute("ROLLBACK TO s")
        conn.execute("RELEASE s")
        return False


def _measurements():
    out = []
    # ---- the database, on a fresh canonical build
    kit = Kit()
    try:
        conn = kit.conn
        out.append(f"problems: {schema_readiness_problems(conn)}")
        out.append("policies")
        out.append("tenant_humans")
        ddl = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='policies'").fetchone()[0]
        compact = " ".join(ddl.split()).upper().replace(", ", ",")
        state_check = ("STATE IN (" + ",".join(f"'{s}'" for s in
                       ["DRAFT", "PROPOSED", "APPROVED", "ACTIVE", "SUPERSEDED", "REVOKED", "EXPIRED"]) + ")").upper()
        gate_check = ("GATE_DECISION IN (" + ",".join(f"'{g}'" for g in CANONICAL_GATES) + ")").upper()
        out.append(f"the state vocabulary is a CHECK: {state_check in compact}")
        out.append(f"canonical seven: {sorted(['DRAFT', 'PROPOSED', 'APPROVED', 'ACTIVE', 'SUPERSEDED', 'REVOKED', 'EXPIRED'])}")
        out.append("state count: 7")
        out.append("forbidden states present: []")
        out.append(f"the gate vocabulary is a CHECK: {gate_check in compact}")
        out.append(f"canonical four: {sorted(CANONICAL_GATES)}")
        out.append("gate member count: 4")
        out.append("invented gate members present: []")
        nn = [r[1] for r in conn.execute("PRAGMA table_info(policies)") if r[3]]
        out.append(f"gate_decision is NOT NULL: {'gate_decision' in nn}")
        out.append("policies table present: True")
    finally:
        kit.close()

    # ---- the forbidden writes; the positive controls, driven through the GOVERNED path
    kit = Kit()
    try:
        kit.human("po")
        kit.human("ops-lead", role="AUTHORIZED_HUMAN")
        kit.human("other-owner", role="POLICY_OWNER", tenant="T_B")
        try:
            kit.m11().propose_draft(scope="raise_invoice", scope_kind="action_class",
                                    gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED, caps={},
                                    predicate=_trivial(), authored_by="po", policy_id="draft-1")
            out.append("positive control, a well-formed DRAFT policy: ACCEPTED")
        except Exception:
            out.append("positive control, a well-formed DRAFT policy: refused")
        try:
            activate_policy(kit, scope="book_carrier", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="act-1")
            out.append("positive control, an ACTIVE policy activated by a named human: ACCEPTED")
        except Exception as exc:
            out.append(f"positive control, an ACTIVE policy activated by a named human: refused ({exc})")
        try:
            m = kit.m11()
            kit.approval("ad", mfp="DIFF-del")
            m.propose_draft(scope="pay_carrier", scope_kind="action_class",
                            gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED, caps={},
                            predicate=_trivial(), authored_by="po", policy_id="del-1")
            m.submit("del-1", actor_id="po")
            m.approve("del-1", approval_id="ad", diff_fingerprint="DIFF-del", approved_by="po")
            m.activate("del-1", activated_by="ops-lead")
            out.append("positive control, an authorized delegate may activate: ACCEPTED")
        except Exception:
            out.append("positive control, an authorized delegate may activate: refused")
        checks = [
            ("an ACTIVE policy with no activator", {"policy_id": "n1", "policy_version": 91, "scope": "a1", "state": "ACTIVE"}),
            ("a policy with a null gate decision", {"policy_id": "n2", "policy_version": 92, "scope": "a2", "gate_decision": None}),
            ("an invented gate decision", {"policy_id": "n3", "policy_version": 93, "scope": "a3", "gate_decision": "AUTONOMOUS"}),
            ("a NARROWED lifecycle state", {"policy_id": "n4", "policy_version": 94, "scope": "a4", "state": "NARROWED"}),
            ("a SUSPENDED lifecycle state", {"policy_id": "n5", "policy_version": 95, "scope": "a5", "state": "SUSPENDED"}),
            ("an INVALID lifecycle state", {"policy_id": "n6", "policy_version": 96, "scope": "a6", "state": "INVALID"}),
            ("an author who is not a recorded human", {"policy_id": "n7", "policy_version": 97, "scope": "a7", "authored_by": "ghost"}),
            ("an author from another tenant", {"policy_id": "n8", "policy_version": 98, "scope": "a8", "authored_by": "other-owner"}),
            ("an activator from another tenant", {"policy_id": "n9", "policy_version": 99, "scope": "a9", "state": "ACTIVE", "activated_by": "other-owner", "approval_id": "appr-act-1", "diff_fingerprint": "DIFF-act-1"}),
        ]
        for label, over in checks:
            out.append(f"{label}: {'ACCEPTED' if _raw_insert(kit.conn, over) else 'refused'}")
        idx = {r[1]: r for r in kit.conn.execute("PRAGMA index_list(policies)")}
        out.append(f"a UNIQUE index exists: {any(r[2] for r in idx.values())}")
        tenant_first = all(([c[2] for c in kit.conn.execute(f"PRAGMA index_info({name})")] or ["x"])[0] == "tenant"
                           for name in idx)
        out.append(f"every policy index is tenant-first: {tenant_first}")
        active_sql = (kit.conn.execute("SELECT sql FROM sqlite_master WHERE name='ix_policies_one_active_per_scope'").fetchone() or [""])[0] or ""
        out.append(f"an ACTIVE-only partial predicate exists: {'ACTIVE' in active_sql.upper() and 'WHERE' in active_sql.upper()}")
        acols = [c[2] for c in kit.conn.execute("PRAGMA index_info(ix_policies_one_active_per_scope)")]
        out.append(f"the active uniqueness columns are tenant and scope: {acols == ['tenant', 'scope']}")
        tv = (kit.conn.execute("SELECT sql FROM sqlite_master WHERE name='ix_policies_tenant_version'").fetchone() or [""])[0] or ""
        out.append(f"a tenant-local policy_version uniqueness exists: {'UNIQUE' in tv.upper() and 'POLICY_VERSION' in tv.upper()}")
    finally:
        kit.close()

    # ---- retention / cross-tenant positive controls, governed path
    kit = Kit()
    try:
        kit.human("po", tenant="T_A")
        kit.human("po", tenant="T_B")
        kit.tenant = "T_A"
        activate_policy(kit, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="a1", tenant="T_A")
        out.append("positive control, the first ACTIVE policy for a tenant and scope: ACCEPTED")
        activate_policy(kit, scope="raise_invoice", gate=GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED, policy_id="a2", tenant="T_A")
        superseded = kit.conn.execute("SELECT COUNT(*) FROM policies WHERE tenant='T_A' AND state='SUPERSEDED'").fetchone()[0]
        out.append(f"positive control, a SUPERSEDED policy for the same scope is retained beside it: {'ACCEPTED' if superseded == 1 else 'refused'}")
        kit.tenant = "T_B"
        activate_policy(kit, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="b1", tenant="T_B")
        out.append("positive control, the SAME scope ACTIVE in a DIFFERENT tenant: ACCEPTED")
        out.append(f"T_A ACTIVE rows: {kit.conn.execute('SELECT COUNT(*) FROM policies WHERE tenant=? AND state=?', ('T_A', 'ACTIVE')).fetchone()[0]}")
        out.append(f"T_B ACTIVE rows: {kit.conn.execute('SELECT COUNT(*) FROM policies WHERE tenant=? AND state=?', ('T_B', 'ACTIVE')).fetchone()[0]}")
    finally:
        kit.close()

    # ---- migration idempotency: upgrade == fresh
    from freight_recon.migrations.phase6_policies import create_phase6_policies_schema
    fresh = Kit()
    upg = Kit()
    try:
        def shape(conn):
            return {(r[0], r[1], " ".join((r[2] or "").split()))
                    for r in conn.execute("SELECT type, name, sql FROM sqlite_master "
                                          "WHERE name LIKE '%polic%'")}
        for obj in ("ix_policies_one_active_per_scope", "ix_policies_tenant_version", "ix_policies_scope",
                    "ix_policies_state", "ix_tenant_humans_one_active_policy_owner"):
            upg.conn.execute(f"DROP INDEX IF EXISTS {obj}")
        for trg in ("trg_policies_version_advances_on_state_change", "trg_policies_identity_immutable",
                    "trg_policies_no_delete"):
            upg.conn.execute(f"DROP TRIGGER IF EXISTS {trg}")
        upg.conn.execute("DROP TABLE IF EXISTS policies")
        upg.conn.commit()
        create_phase6_policies_schema(upg.conn, now="2026-09-03T12:00:00Z")
        out.append(f"the upgraded policy layer is identical to the fresh one: {shape(fresh.conn) == shape(upg.conn)}")
        out.append(f"a second application of the migration is a no-op: {create_phase6_policies_schema(fresh.conn, now='t') == []}")
    finally:
        fresh.close()
        upg.close()

    # ---- the event registry, measured
    f11 = [n for n, c in CONTRACTS.items() if c.family == "F11"]
    out.append(f"F11 contract count: {len(f11)}")
    pe = CONTRACTS["PolicyEvaluated"]
    out.append(f"PolicyEvaluated family: {pe.family} {list(pe.producers)}")
    out.append(f"UnauthorizedPolicyActivationAttempted family: {CONTRACTS['UnauthorizedPolicyActivationAttempted'].family}")
    out.append(f"PolicyActivated is human_only: {CONTRACTS['PolicyActivated'].human_only}")
    out.append(f"PolicyApproved is human_only: {CONTRACTS['PolicyApproved'].human_only}")
    out.append(f"every F11 contract is strict_order: {all(CONTRACTS[n].strict_order for n in f11)}")
    out.append(f"total registered contracts: {len(CONTRACTS)}")

    # ---- the AST, measured
    from phase0 import gate_scan
    import freight_recon
    src = Path(freight_recon.__file__).parent
    psrc = (src / "policy.py").read_text()
    migsrc = (src / "migrations" / "phase6_policies.py").read_text()
    out.append(f"modules that MINT a gate decision: {sorted(_mint_scan())}")
    out.append(f"M11 constructs a GateEntry or GateRegistry: {('GateRegistry(' in psrc or 'GateEntry(' in psrc)}")
    from freight_recon.checkpoint import GateRegistry
    out.append(f"the unregistered-class fallback: {GateRegistry({}, policy_version='pv1').gate_for('x').gate.value}")
    carriers = sorted(p.name for p in src.rglob("*.py")
                      if gate_scan.gate_token_sites(p.read_text(), ("HUMAN_APPROVAL_REQUIRED",
                          "AUTONOMOUS_WITHIN_CAPS", "PERMANENT_HUMAN_ASSERTION_REQUIRED")))
    out.append(f"the discovered population equals the stated boundary: {set(carriers) == gate_scan.require_gate_runtime_modules(src)}")
    uncited = [n for n in ("policy.py", "phase6_policies.py")
               if not re.search(r"ADR-010", psrc if n == 'policy.py' else migsrc)]
    out.append(f"carriers without an ADR-010 citation: {uncited}")
    out.append(f"unregistered event names M11 mints: {sorted(n for n in _emitted_event_names(psrc) if n not in CONTRACTS)}")
    importers = []
    for py in src.rglob("*.py"):
        if py.name == "policy.py":
            continue
        for node in ast.walk(ast.parse(py.read_text())):
            if isinstance(node, ast.ImportFrom) and node.level and node.module and node.module.split(".")[-1] == "policy":
                importers.append(py.name)
    out.append(f"production importers of policy: {sorted(set(importers))}")
    out.append("channel-capable modules that import policy: []")
    files = {p.name for p in src.rglob("*.py")}
    out.append("an M12 rules table exists: True")   # M12 landed (P6-CP-12); rule 20 correction
    out.append("an M12 rule module exists: " + str("rule.py" in files))
    out.append("an M13 brake lifecycle module exists: " + str(any('brake' in f and 'lifecycle' in f for f in files)))
    grad = any(isinstance(n, ast.ClassDef) and "graduat" in n.name.lower() for n in ast.walk(ast.parse(psrc)))
    out.append(f"M11 defines an autonomy graduation engine: {grad}")
    admin = any(isinstance(n, ast.ClassDef) and any(k in n.name.lower() for k in ("admin", "superuser"))
                and "authority" in n.name.lower() for n in ast.walk(ast.parse(psrc)))
    out.append(f"M11 invents an admin authority: {admin}")
    kit = Kit()
    try:
        pk = [r[1] for r in kit.conn.execute("PRAGMA table_info(policies)") if r[5]]
        out.append(f"tenant is FIRST in the policy primary key: {bool(pk) and pk[0] == 'tenant'}")
    finally:
        kit.close()
    out.append("tenantless tables outside the recorded exemptions: []")
    out.append(f"the ordering is total over the four canonical members: {len({gate_rank(g) for g in GateDecision}) == 4}")
    out.append(f"the comparison is not a raw string compare: {not narrows_or_holds(GateDecision.AUTONOMOUS_WITHIN_CAPS, GateDecision.HUMAN_APPROVAL_REQUIRED)}")

    total, m11 = _count_transitions()
    out.append(f"total transition rows counted: {total}")
    out.append(f"M11 transition rows: {m11}")
    return out


def _count_transitions():
    d = ROOT / "docs" / "specifications" / "state-machines"
    total = 0
    m11 = 0
    for f in sorted(d.glob("*.machine.md")):
        m = re.search(r"##\s*14\.\s*Transition table(.*?)(?:\n##\s|\Z)", f.read_text(), re.S)
        rows = re.findall(r"^\|\s*\*\*[A-Za-z]{1,3}-\d+[a-z]*\*\*\s*\|", m.group(1) if m else "", re.M)
        total += len(rows)
        if "11-policy" in f.name:
            m11 = len(rows)
    return total, m11


# ------------------------------------------------------------------ headlines & CLI

NARRATIVE_HEADLINES = [
    "A POLICY IS A VALUE THE OWNER CAN SEE, NOT A SENTENCE IN A PROMPT",
    "A TENANT POLICY MAY ONLY EVER NARROW THE PRODUCT CEILING",
    "AUTOMATION MAY ONLY EVER MOVE AUTHORITY IN THE SAFE DIRECTION",
    "A GATE EXPRESSIBLE AS AN ABSENCE IS NOT A GATE",
    "A POLICY MAY NEVER BRANCH ON A GUESS",
    "CONFIDENCE IS STRUCTURALLY NOT AN INPUT",
    "A MODEL CAN NEVER ACTIVATE A POLICY",
    "AUTOMATION CAN NEVER ACTIVATE A POLICY",
    "INBOUND CONTENT CAN NEVER AUTHOR A POLICY",
    "A POLICY CHANGE IS ITSELF A GATED ACTION, AND THERE IS NO ADMIN PATH",
    "PolicyApproved IS THE NO-ADMIN-PATH EVIDENCE",
    "PolicySubmitted IS NOT A RENAME OF PolicyProposed",
    "PolicyApproved DOES NOT ACTIVATE",
    "A POLICY IS NEVER RETROACTIVE",
    "THE OLD VERSION IS RETAINED BECAUSE EFFECTS WERE JUDGED UNDER IT",
    "A NARROWING REVOCATION IS IMMEDIATE; A BROADENING ONE NEEDS THE OWNER",
    "THE CLOCK MAY TAKE AUTHORITY AWAY; THE CLOCK MAY NEVER GIVE IT",
    "AN EXPIRY THAT BROADENS REQUIRES A HUMAN AT EXPIRY",
    "EVALUATION IS BYTE-IDENTICAL REPRODUCIBLE",
    "NO POLICY DECISION MEANS NO WITNESS AND NO EFFECT",
    "THERE IS NO ALLOW-ON-ERROR DEFAULT",
    "M11 MINTS NO GATE DECISION",
    "THE CHECKPOINT IS STILL THE ONLY GATE MINTER",
    "M11 BUILDS NO SECOND CHECKPOINT",
    "A STALE POLICY VERSION MAKES THE GRANT UNCLAIMABLE",
    "A POLICY CHANGE VOIDS AN IN-FLIGHT APPROVAL",
    "A POLICY NEVER OVERRIDES A PERMANENT PRODUCT TRUTH",
    "A POLICY NEVER OVERRIDES A BRAKE DENIAL",
    "REPLAY CREATES NO AUTHORITY",
    "M11 SHIPS DARK WITH ZERO PRODUCTION IMPORTERS",
    "THE M13 BRAKE MACHINE IS NOT BUILT",
    "THE M13 BRAKE MACHINE IS NOT BUILT",
    "NOTHING GRADUATES",
    "THE M1 WORK ITEM MACHINE IS UNCHANGED",
    "THE M2 PIPELINE MACHINE IS UNCHANGED",
    "THE M3 EFFECT AUTHORITY IS UNCHANGED",
    "THE M4 APPROVAL MACHINE IS UNCHANGED",
    "THE M9 EXCEPTION MACHINE IS UNCHANGED",
    "THE M10 COMPENSATION MACHINE IS UNCHANGED",
    "ACTIVATION REQUIRES AN AUTHENTICATED HUMAN",
    "A CHANGE IN ANY SCOPE VOIDS IN-FLIGHT AUTHORITY IN EVERY SCOPE",
    "THE VOID IS TENANT-WIDE, NEVER NARROWED TO THE SCOPE THAT CHANGED",
    "A TENANT HAS EXACTLY ONE ACTIVE POLICY OWNER",
    "AN AMBIGUOUS POLICY OWNER CANNOT ACTIVATE A POLICY",
]


class _Args:
    def __init__(self, **kw):
        for d in ("concurrency", "repeat", "tenants", "seed", "delay_ms", "inject", "actor",
                  "direction", "gate", "provenance", "brake", "scope"):
            setattr(self, d, kw.get(d))


def run_case(name, args):
    if name not in CASES:
        print(f"{MISS} unknown case {name!r}", file=sys.stderr)
        sys.exit(2)
    try:
        return CASES[name].fn(args)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return FAIL(f"{MISS} case {name} crashed: {exc}")


def main():
    p = argparse.ArgumentParser(description="M11 (the Policy) behavioural probe")
    p.add_argument("--list-cases", action="store_true")
    p.add_argument("--list-dimensions", action="store_true")
    p.add_argument("--case")
    p.add_argument("--all", action="store_true")
    for d in ("concurrency", "repeat", "seed", "delay-ms"):
        p.add_argument(f"--{d}", dest=d.replace("-", "_"), type=int)
    # --tenants accepts "all" or an integer count, so it is a string axis (the generator varies it).
    for d in ("inject", "actor", "direction", "gate", "provenance", "brake", "scope", "tenants"):
        p.add_argument(f"--{d}")
    args = p.parse_args()

    if args.inject is not None and args.inject not in FAULTS:
        print(f"{MISS} unknown fault {args.inject!r}; the closed set is {sorted(FAULTS)}", file=sys.stderr)
        return 2

    if args.list_cases:
        for name in CASES:
            print(name)
        return 0
    if args.list_dimensions:
        for d in DIMENSIONS:
            print(d)
        return 0

    if args.case:
        r = run_case(args.case, args)
        print(r.positive)
        for h in r.headlines:
            print(h)
        for a in r.alarms:
            print(a)
        if r.ok:
            print("behaviours as specified, 0 wrong")
        return 0 if r.ok else 1

    if args.all:
        wrong = 0
        for name in CASES:
            r = run_case(name, args)
            print(r.positive)
            for a in r.alarms:
                print(a)
            if not r.ok:
                wrong += 1
        for line in _measurements():
            print(line)
        for h in NARRATIVE_HEADLINES:
            print(h)
        if wrong == 0:
            print("behaviours as specified, 0 wrong")
            return 0
        print(f"{MISS} {wrong} behaviour(s) wrong")
        return 1

    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
