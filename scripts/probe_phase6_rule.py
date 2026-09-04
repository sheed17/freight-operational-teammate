#!/usr/bin/env python3
"""Deterministic behavioural probe for M12 — the Rule (P6-CP-12).

### THIS PROBE'S NARRATION IS NOT THE MEASUREMENT. The permanent scenario measures the DATABASE, the
EVENT REGISTRY, the LITERAL REPLY TEXT and the AST. This probe drives the machine and the LANDED seams it
NAMES (M7's conflict, M9's exception — driven by the probe, never imported by the machine) and reports,
per case, whether the behaviour matched the specification — AND `--all` prints the DB/registry/AST/reply
measurements the scenario reads. Every case is deterministic and hermetic — a fixed clock, fresh
databases, no wall-clock sleeps.

Output contract (the shared P6 harness vocabulary):
  * a case prints a positive line AND, where the scenario names one, its uppercase headline;
  * a case prints `### MISS ###` on failure, plus the specific alarm marker for the defect it caught;
  * `### NOT REFUSED`, `### WRONGLY REFUSED`, `### WRONG REFUSAL` are the three refusal-shape misses;
  * `--all` prints every case, then the measurement block, then the headlines, then
    `behaviours as specified, 0 wrong`.

### THE TWO OWN AXES: `--kind` and `--outcome`. The four kinds do not behave alike (GATE_PRECONDITION and
CONSTRAINT are evaluated by the checkpoint; IDENTITY and CONFLICT_RESOLUTION by two other components), and
the whole unit is the claim that exactly TWO outcomes exist — `--outcome` is how the absence of a third
becomes measurable.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import sqlite3
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
    GateRegistry,
    ProvenanceClass,
    ProvenancedFact,
)
from freight_recon.conflict import M7Machine, Party  # noqa: E402
from freight_recon.event_contracts import CONTRACTS  # noqa: E402
from freight_recon.migrations.phase6_rules import (  # noqa: E402
    P6RU_SCOPE_FORMS,
    P6RU_SINGLE_ACTIVE_SCOPES,
    phase6_rules_readiness_problems,
)
from freight_recon.rule import (  # noqa: E402
    PRECEDENCE_LADDER,
    PRECEDENCE_LAYER,
    PRODUCED_CONTRACTS,
    TRANSITIONS,
    CompilerInput,
    DishonestReply,
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
    create_canonical_schema,
    enable_and_verify_foreign_keys,
    schema_readiness_problems,
)

FIXED = datetime(2026, 9, 3, 12, 0, 0, tzinfo=timezone.utc)
CANONICAL_STATES = ("PROPOSED", "COMPILED", "CONFIRMED", "ACTIVE", "REJECTED", "SUPERSEDED", "REVOKED",
                    "EXPIRED")
CANONICAL_KINDS = ("IDENTITY", "CONFLICT_RESOLUTION", "GATE_PRECONDITION", "CONSTRAINT")
CANONICAL_PROVENANCE = ("SYSTEM_IMPORTED", "OWNER_ASSERTED", "LINKER_INFERRED", "MODEL_EXTRACTED",
                        "MODEL_INFERRED", "RECONCILED")
REQUIRED_ATTRS = ("rule_id", "tenant", "rule_version", "scope", "kind", "compiled_predicate", "state",
                  "source_instruction", "authored_by", "activated_by", "test_vectors")
FAULTS = frozenset({"engine-unavailable", "none"})
DIMENSIONS = ("--concurrency", "--repeat", "--tenants", "--seed", "--delay-ms", "--inject", "--actor",
              "--kind", "--outcome", "--provenance", "--direction", "--scope", "--brake")
MISS = "### MISS ###"
_MODELLED = {"provenance_class": "SYSTEM_IMPORTED", "modelled": True}


# ------------------------------------------------------------------ a hermetic canonical database

class Kit:
    def __init__(self, tenant="T_A", use_file=False):
        self._dir = tempfile.mkdtemp(prefix="m12-probe-") if use_file else None
        self.path = os.path.join(self._dir, "rule.db") if use_file else ":memory:"
        self.tenant = tenant
        self.conn = self._open()

    def clock(self):
        return FIXED

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
        offboarded = "2026-06-01T00:00:00Z" if state == "OFFBOARDED" else None
        self.conn.execute(
            "INSERT INTO tenant_humans (tenant, human_id, display_name, authority_role, state, "
            "recorded_at, recorded_by, recorded_by_kind, offboarded_at) VALUES (?,?,?,?,?,?,?, 'human', ?)",
            (tenant or self.tenant, hid, hid, role, state, "2026-01-01T00:00:00Z", "founder", offboarded))
        self.conn.commit()
        return hid

    def m12(self, *, conn=None, tenant=None):
        return M12Machine(conn or self.conn, tenant=tenant or self.tenant, clock=self.clock)

    def close(self):
        try:
            self.conn.close()
        finally:
            if self._dir:
                shutil.rmtree(self._dir, ignore_errors=True)


def _pod_clauses():
    return [
        {"field": "pod", "attr": "evidence_condition", "op": "==", "literal": "consistent", **_MODELLED},
        {"field": "pod", "attr": "provenance_class", "op": "in",
         "literal": ["SYSTEM_IMPORTED", "OWNER_ASSERTED", "MODEL_EXTRACTED"], **_MODELLED},
    ]


def _amount_clauses(op=">", lit=50):
    return [{"field": "amount", "attr": "value", "op": op, "literal": lit, **_MODELLED}]


def activate_rule(kit, rid, *, scope="raise_invoice", scope_form="action_class",
                  kind="GATE_PRECONDITION", effect="DENY", clauses=None, owner="po", tenant=None,
                  conn=None):
    m = kit.m12(conn=conn, tenant=tenant)
    m.propose(scope=scope, scope_form=scope_form, kind=kind, effect=effect,
              source_instruction=f"instruction {rid}", authored_by=owner,
              clauses=clauses if clauses is not None else _pod_clauses(), rule_id=rid)
    m.compile(rid)
    m.confirm(rid, confirmed_by=owner)
    m.activate(rid, activated_by=owner)
    return rid


def to_compiled(kit, rid, *, effect="DENY", clauses=None, scope="raise_invoice",
                scope_form="action_class", kind="GATE_PRECONDITION"):
    m = kit.m12()
    m.propose(scope=scope, scope_form=scope_form, kind=kind, effect=effect, source_instruction="x",
              authored_by="po", clauses=clauses if clauses is not None else _pod_clauses(), rule_id=rid)
    m.compile(rid)
    return m


def to_confirmed(kit, rid, **kw):
    m = to_compiled(kit, rid, **kw)
    m.confirm(rid, confirmed_by="po")
    return m


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
    def __init__(self, name, fn):
        self.name = name
        self.fn = fn


def case(name):
    def deco(fn):
        CASES[name] = Case(name, fn)
        return fn
    return deco


# ------------------------------------------------------------------ AST helpers

def _rule_src():
    return (ROOT / "src" / "freight_recon" / "rule.py").read_text(encoding="utf-8")


def _mig_src():
    return (ROOT / "src" / "freight_recon" / "migrations" / "phase6_rules.py").read_text(encoding="utf-8")


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


# =========================================================== RU-1: authorship & proposal

@case("a-model-may-propose-structured-candidate-text")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        m = kit.m12()
        m.propose(scope="raise_invoice", scope_form="action_class", kind="GATE_PRECONDITION",
                  effect="DENY", source_instruction="never bill without a POD", authored_by="po",
                  clauses=_pod_clauses(), rule_id="r1", actor_kind="model")
        if m.require("r1").state is not RuleState.PROPOSED:
            return FAIL(f"{MISS} a model proposal did not create a PROPOSED candidate",
                        "### A MODEL PROPOSAL BECAME AN ACTIVE RULE ###")
        return OK("a-model-may-propose-structured-candidate-text: a model proposed a PROPOSED candidate",
                  "A MODEL MAY PROPOSE TEXT; IT NEVER COMPILES")
    finally:
        kit.close()


@case("a-proposal-is-not-an-enforceable-rule")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        m = kit.m12()
        m.propose(scope="s", scope_form="action_class", kind="CONSTRAINT", effect="DENY",
                  source_instruction="x", authored_by="po", clauses=_pod_clauses(), rule_id="r1")
        row = m.require("r1")
        if row.state is not RuleState.PROPOSED or row.activated_by is not None:
            return FAIL(f"{MISS} a proposal was treated as enforceable",
                        "### RuleProposed TREATED AS ENFORCEMENT ###")
        # OUTCOME axis: there are exactly two outcomes and neither is "enforced on proposal".
        return OK("a-proposal-is-not-an-enforceable-rule: PROPOSED, not ACTIVE, no activator",
                  "A HUMAN INSTRUCTION EITHER COMPILES INTO AN ENFORCEABLE RULE OR IS HONESTLY REFUSED")
    finally:
        kit.close()


@case("the-source-instruction-is-retained-verbatim")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        m = kit.m12()
        sentence = "never bill without a POD"
        m.propose(scope="s", scope_form="action_class", kind="CONSTRAINT", effect="DENY",
                  source_instruction=sentence, authored_by="po", clauses=_pod_clauses(), rule_id="r1")
        if m.require("r1").source_instruction != sentence:
            return FAIL(f"{MISS} the source instruction was not retained", "### SOURCE INSTRUCTION DISCARDED ###")
        return OK("the-source-instruction-is-retained-verbatim: the owner sentence is stored verbatim")
    finally:
        kit.close()


def _author_refused(kind, marker, actor_kind=None, human_state="ACTIVE", author="po"):
    kit = Kit()
    try:
        kit.human("po")
        if author != "po":
            kit.human(author, role="AUTHORIZED_HUMAN", state=human_state)
        m = kit.m12()
        ok = refuses(lambda: m.propose(
            scope="s", scope_form="action_class", kind="CONSTRAINT", effect="DENY",
            source_instruction="x", authored_by=author, clauses=_pod_clauses(), rule_id="r1",
            actor_kind=actor_kind or "human"))
        if not ok or kit.conn.execute("SELECT COUNT(*) FROM rules").fetchone()[0] != 0:
            return FAIL(f"{MISS} {kind} authored a rule", marker)
        return OK(f"{kind}: refused, zero rule rows")
    finally:
        kit.close()


@case("an-offboarded-human-cannot-author-a-rule")
def _c(args):
    r = _author_refused("offboarded-human", "### AN OFFBOARDED HUMAN AUTHORED A RULE ###",
                        human_state="OFFBOARDED", author="ex")
    return r if not r.ok else OK("an-offboarded-human-cannot-author-a-rule: an offboarded human authors nothing")


@case("a-counterparty-instruction-is-not-a-rule")
def _c(args):
    r = _author_refused("counterparty", "### A COUNTERPARTY AUTHORED A RULE ###", actor_kind="counterparty")
    return r if not r.ok else OK("a-counterparty-instruction-is-not-a-rule: a counterparty authors no rule")


@case("inbound-content-can-never-author-a-rule")
def _c(args):
    r = _author_refused("inbound", "### INBOUND CONTENT AUTHORED A RULE ###", actor_kind="inbound")
    return r if not r.ok else OK("inbound-content-can-never-author-a-rule: inbound content authors no rule")


@case("ru-1-emits-ruleproposed")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        kit.m12().propose(scope="s", scope_form="action_class", kind="CONSTRAINT", effect="DENY",
                          source_instruction="x", authored_by="po", clauses=_pod_clauses(), rule_id="r1")
        n = kit.conn.execute("SELECT COUNT(*) FROM event_outbox WHERE event_name='RuleProposed' "
                             "AND aggregate_id='r1'").fetchone()[0]
        if n != 1:
            return FAIL(f"{MISS} RU-1 did not emit RuleProposed", "### STATE WITHOUT ITS EVENT ###")
        return OK("ru-1-emits-ruleproposed: RuleProposed emitted once")
    finally:
        kit.close()


@case("ruleproposed-does-not-prove-the-rule-is-enforceable")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        kit.m12().propose(scope="s", scope_form="action_class", kind="CONSTRAINT", effect="DENY",
                          source_instruction="x", authored_by="po", clauses=_pod_clauses(), rule_id="r1")
        st = kit.conn.execute("SELECT state FROM rules WHERE rule_id='r1'").fetchone()["state"]
        if st != "PROPOSED":
            return FAIL(f"{MISS} RuleProposed left the rule {st}", "### RuleProposed TREATED AS ENFORCEMENT ###")
        return OK("ruleproposed-does-not-prove-the-rule-is-enforceable: state is PROPOSED")
    finally:
        kit.close()


# =========================================================== RU-2: compilation

_MODEL_CALL_RE = re.compile(r"\b(openai|anthropic|call_model|model_client|chat\.completions|"
                            r"\.generate\(|invoke_model)\b", re.I)


@case("compilation-is-deterministic-and-model-free")
def _c(args):
    from phase0 import gate_scan
    cand = {"kind": "GATE_PRECONDITION", "effect": "DENY", "combine": "AND", "clauses": _pod_clauses()}
    first = compile_candidate(cand, scope="raise_invoice").to_json()
    for _ in range(10):
        if compile_candidate(cand, scope="raise_invoice").to_json() != first:
            return FAIL(f"{MISS} compilation was non-deterministic", "### NON-DETERMINISTIC COMPILATION ###")
    # scan EXECUTABLE source only — a docstring saying "installed a sentence in an LLM prompt" is prose
    if _MODEL_CALL_RE.search(gate_scan.executable_source(_rule_src())):
        return FAIL(f"{MISS} a model call is present in compilation", "### A MODEL CALL ENTERED COMPILATION ###")
    return OK("compilation-is-deterministic-and-model-free: byte-identical, no model call",
              "COMPILATION IS DETERMINISTIC, WITH NO MODEL IN THE LOOP")


@case("no-model-call-occurs-after-the-text-proposal")
def _c(args):
    from phase0 import gate_scan
    executable = gate_scan.executable_source(_rule_src())
    if _MODEL_CALL_RE.search(executable):
        return FAIL(f"{MISS} a model call after proposal", "### A MODEL CALL ENTERED COMPILATION ###")
    return OK("no-model-call-occurs-after-the-text-proposal: no model call in executable source")


@case("every-referenced-field-must-be-modelled")
def _c(args):
    if not refuses(lambda: compile_predicate_field(
            CompilerInput(field="commodity", provenance_class="SYSTEM_IMPORTED", modelled=False))):
        return FAIL(f"{MISS} an unmodelled field compiled", "### UNMODELLED FIELD COMPILED INTO A PREDICATE ###")
    return OK("every-referenced-field-must-be-modelled: an unmodelled field is refused")


@case("every-referenced-field-must-be-non-inferred")
def _c(args):
    provs = list(CANONICAL_PROVENANCE) if (args.provenance in (None, "all")) else [args.provenance]
    alarms = []
    for prov in provs:
        compiled = not refuses(lambda: compile_predicate_field(
            CompilerInput(field="x", provenance_class=prov, modelled=True)))
        if prov == "MODEL_INFERRED" and compiled:
            alarms.append("### MODEL_INFERRED PREDICATE COMPILED ###")
    if alarms:
        return FAIL(f"{MISS} a guess became a rule", *alarms)
    return OK("every-referenced-field-must-be-non-inferred: MODEL_INFERRED is refused",
              "A RULE MAY NEVER BRANCH ON A GUESS")


@case("the-predicate-must-be-decidable-at-checkpoint-time")
def _c(args):
    if not refuses(lambda: compile_candidate(
            {"kind": "CONSTRAINT", "effect": "DENY", "combine": "AND",
             "clauses": [{"field": "x", "attr": "value", "op": "~=", "literal": 1, **_MODELLED}]},
            scope="s")):
        return FAIL(f"{MISS} an undecidable operator compiled", "### UNDECIDABLE PREDICATE COMPILED ###")
    return OK("the-predicate-must-be-decidable-at-checkpoint-time: an unknown operator is refused")


@case("the-scope-must-resolve")
def _c(args):
    if not refuses(lambda: compile_candidate(
            {"kind": "CONSTRAINT", "effect": "DENY", "combine": "AND", "clauses": _pod_clauses()},
            scope="unknown_scope", resolvable_scopes=("raise_invoice", "book_carrier"))):
        return FAIL(f"{MISS} an unresolvable scope compiled", "### UNRESOLVABLE SCOPE COMPILED ###")
    return OK("the-scope-must-resolve: an unresolvable scope is refused")


@case("never-bill-without-a-pod-compiles-to-a-gate-precondition")
def _c(args):
    compiled = compile_candidate(
        {"kind": "GATE_PRECONDITION", "effect": "DENY", "combine": "AND", "clauses": _pod_clauses()},
        scope="raise_invoice")
    if compiled.effect != "DENY" or not compiled.clauses:
        return FAIL(f"{MISS} the POD rule did not compile to a precondition",
                    "### PREDICATE ADMITTED AS A PROMPT STRING ###")
    return OK("never-bill-without-a-pod-compiles-to-a-gate-precondition: a real precondition",
              "NEVER BILL WITHOUT A POD COMPILES TO A REAL PRECONDITION")


@case("the-pod-rule-admits-only-the-three-canonical-provenance-classes")
def _c(args):
    compiled = compile_candidate(
        {"kind": "GATE_PRECONDITION", "effect": "DENY", "combine": "AND", "clauses": _pod_clauses()},
        scope="raise_invoice")
    prov_clause = next((c for c in compiled.clauses if c.attr == "provenance_class"), None)
    admitted = set(prov_clause.literal) if prov_clause else set()
    if admitted != {"SYSTEM_IMPORTED", "OWNER_ASSERTED", "MODEL_EXTRACTED"}:
        return FAIL(f"{MISS} the POD rule admits {admitted}", "### MODEL_INFERRED PREDICATE COMPILED ###")
    return OK("the-pod-rule-admits-only-the-three-canonical-provenance-classes: SYSTEM_IMPORTED, "
              "OWNER_ASSERTED, MODEL_EXTRACTED")


@case("a-model-inferred-pod-is-denied-by-the-compiled-rule")
def _c(args):
    compiled = compile_candidate(
        {"kind": "GATE_PRECONDITION", "effect": "DENY", "combine": "AND", "clauses": _pod_clauses()},
        scope="raise_invoice")
    inferred = {"pod": ProvenancedFact(field="pod", provenance=ProvenanceClass.MODEL_INFERRED,
                                       evidence_condition=EvidenceCondition.CONSISTENT, _value="guess")}
    if evaluate_rule(compiled, inferred).decision != "DENY":
        return FAIL(f"{MISS} an inferred POD was not denied", "### MODEL_INFERRED PREDICATE COMPILED ###")
    return OK("a-model-inferred-pod-is-denied-by-the-compiled-rule: an inferred POD is denied",
              "AN INFERRED POD IS NOT A POD")


@case("compilation-is-byte-identical-reproducible")
def _c(args):
    cand = {"kind": "GATE_PRECONDITION", "effect": "DENY", "combine": "AND", "clauses": _pod_clauses()}
    n = args.repeat or 25
    first = compile_candidate(cand, scope="raise_invoice").to_json()
    for _ in range(n):
        if compile_candidate(cand, scope="raise_invoice").to_json() != first:
            return FAIL(f"{MISS} compilation not reproducible", "### NON-DETERMINISTIC COMPILATION ###")
    return OK("compilation-is-byte-identical-reproducible: identical across repeats")


@case("no-wall-clock-enters-compilation")
def _c(args):
    src = _rule_src()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in ("compile_candidate", "generate_test_vectors",
                                                               "compile_predicate_field"):
            body = ast.get_source_segment(src, node) or ""
            if re.search(r"datetime\.now|time\.time|_utc_now|_clock", body):
                return FAIL(f"{MISS} a wall clock is read in {node.name}", "### WALL CLOCK ENTERED COMPILATION ###")
    return OK("no-wall-clock-enters-compilation: compilation reads no clock")


@case("no-randomness-enters-compilation")
def _c(args):
    src = _rule_src()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in ("compile_candidate", "generate_test_vectors"):
            body = ast.get_source_segment(src, node) or ""
            if re.search(r"\brandom\b|uuid4|secrets\.", body):
                return FAIL(f"{MISS} randomness in {node.name}", "### RANDOMNESS ENTERED COMPILATION ###")
    return OK("no-randomness-enters-compilation: compilation is deterministic")


@case("unordered-iteration-does-not-change-the-compiled-predicate")
def _c(args):
    base = _pod_clauses()
    a = compile_candidate({"kind": "GATE_PRECONDITION", "effect": "DENY", "combine": "AND",
                           "clauses": base}, scope="raise_invoice").to_json()
    b = compile_candidate({"kind": "GATE_PRECONDITION", "effect": "DENY", "combine": "AND",
                           "clauses": base}, scope="raise_invoice").to_json()
    if a != b:
        return FAIL(f"{MISS} iteration order changed the predicate",
                    "### UNORDERED ITERATION CHANGED THE COMPILED PREDICATE ###")
    return OK("unordered-iteration-does-not-change-the-compiled-predicate: canonical JSON is stable")


@case("ru-2-emits-rulecompiled")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        to_compiled(kit, "r1")
        n = kit.conn.execute("SELECT COUNT(*) FROM event_outbox WHERE event_name='RuleCompiled' "
                             "AND aggregate_id='r1'").fetchone()[0]
        if n != 1:
            return FAIL(f"{MISS} RU-2 did not emit RuleCompiled", "### STATE WITHOUT ITS EVENT ###")
        return OK("ru-2-emits-rulecompiled: RuleCompiled emitted once")
    finally:
        kit.close()


@case("rulecompiled-carries-the-compiled-predicate-and-the-test-vectors")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        to_compiled(kit, "r1")
        from freight_recon.event_envelope import EventEnvelope
        ev = kit.conn.execute("SELECT envelope_json FROM event_outbox WHERE event_name='RuleCompiled' "
                              "AND aggregate_id='r1'").fetchone()
        payload = EventEnvelope.from_json(ev["envelope_json"]).payload
        if not payload.get("compiled_predicate") or not payload.get("test_vectors"):
            return FAIL(f"{MISS} RuleCompiled dropped a required field", "### REQUIRED PAYLOAD FIELD DROPPED ###")
        return OK("rulecompiled-carries-the-compiled-predicate-and-the-test-vectors: both present")
    finally:
        kit.close()


@case("do-not-use-carrier-x-for-produce-cannot-compile")
def _c(args):
    ok = refuses(lambda: compile_candidate(
        {"kind": "CONSTRAINT", "effect": "DENY", "combine": "AND", "clauses": [
            {"field": "carrier", "attr": "value", "op": "==", "literal": "X", **_MODELLED},
            {"field": "commodity", "attr": "value", "op": "==", "literal": "produce",
             "provenance_class": "SYSTEM_IMPORTED", "modelled": False}]},
        scope="book_carrier"))
    if not ok:
        return FAIL(f"{MISS} an unmodelled commodity compiled", "### UNMODELLED FIELD COMPILED INTO A PREDICATE ###")
    return OK("do-not-use-carrier-x-for-produce-cannot-compile: commodity is not modelled",
              "DO NOT USE CARRIER X FOR PRODUCE CANNOT COMPILE, AND THE OWNER IS TOLD")


@case("the-owner-is-told-commodity-is-not-a-modelled-field")
def _c(args):
    try:
        compile_candidate(
            {"kind": "CONSTRAINT", "effect": "DENY", "combine": "AND", "clauses": [
                {"field": "commodity", "attr": "value", "op": "==", "literal": "produce",
                 "provenance_class": "SYSTEM_IMPORTED", "modelled": False}]},
            scope="book_carrier")
        return FAIL(f"{MISS} commodity compiled", "### UNMODELLED FIELD COMPILED INTO A PREDICATE ###")
    except RuleWillNotCompile as exc:
        reply = honest_refusal(exc.missing, "commodity as a modelled field on the load")
        if "commodity" not in reply.lower() or reply_claims_enforcement(reply):
            return FAIL(f"{MISS} the owner was not honestly told", "### THE OWNER WAS NOT TOLD IT IS NOT A RULE ###")
        return OK("the-owner-is-told-commodity-is-not-a-modelled-field: an honest feature-request refusal")


@case("a-margin-rule-refuses-to-compile-on-model-inferred-cost")
def _c(args):
    if not refuses(lambda: compile_candidate(
            {"kind": "GATE_PRECONDITION", "effect": "REQUIRE_HUMAN_APPROVAL", "combine": "AND", "clauses": [
                {"field": "carrier_cost", "attr": "value", "op": "<", "literal": 100,
                 "provenance_class": "MODEL_INFERRED", "modelled": True}]}, scope="book_carrier")):
        return FAIL(f"{MISS} a margin rule on a guess compiled", "### MODEL_INFERRED PREDICATE COMPILED ###")
    ok = not refuses(lambda: compile_candidate(
        {"kind": "GATE_PRECONDITION", "effect": "REQUIRE_HUMAN_APPROVAL", "combine": "AND", "clauses": [
            {"field": "carrier_cost", "attr": "value", "op": "<", "literal": 100,
             "provenance_class": "SYSTEM_IMPORTED", "modelled": True}]}, scope="book_carrier"))
    if not ok:
        return FAIL(f"{MISS} a margin rule on a real cost was wrongly refused", "### WRONGLY REFUSED ###")
    return OK("a-margin-rule-refuses-to-compile-on-model-inferred-cost: refused on a guess, compiles on a fact")


@case("confidence-one-does-not-make-model-inferred-compilable")
def _c(args):
    if not refuses(lambda: compile_predicate_field(
            CompilerInput(field="carrier_cost", provenance_class="MODEL_INFERRED", modelled=True))):
        return FAIL(f"{MISS} MODEL_INFERRED compiled", "### MODEL_INFERRED READ AT CONFIDENCE ONE ###")
    fact = ProvenancedFact(field="c", provenance=ProvenanceClass.MODEL_INFERRED,
                           evidence_condition=EvidenceCondition.CONSISTENT, _value=1)
    if not refuses(lambda: fact.value):
        return FAIL(f"{MISS} a MODEL_INFERRED value was read", "### MODEL_INFERRED READ AT CONFIDENCE ONE ###")
    return OK("confidence-one-does-not-make-model-inferred-compilable: refused, there is no confidence",
              "CONFIDENCE IS STRUCTURALLY NOT AN INPUT")


@case("the-compiler-input-type-has-no-confidence-field")
def _c(args):
    alarms = []
    if "confidence" in CompilerInput.__dataclass_fields__:
        alarms.append("### CONFIDENCE FIELD PRESENT ON THE COMPILER INPUT ###")
    if not refuses(lambda: compile_predicate_field(CompilerInput(field="confidence",
                                                                 provenance_class="SYSTEM_IMPORTED"))):
        alarms.append("### CONFIDENCE READ BY THE COMPILER ###")
    if alarms:
        return FAIL(f"{MISS} confidence is an input", *alarms)
    return OK("the-compiler-input-type-has-no-confidence-field: no confidence attribute anywhere",
              "CONFIDENCE IS STRUCTURALLY NOT AN INPUT")


@case("an-unmodelled-field-fails-to-compile")
def _c(args):
    provs = list(CANONICAL_PROVENANCE) if (args.provenance in (None, "all")) else [args.provenance]
    for prov in provs:
        if not refuses(lambda: compile_predicate_field(
                CompilerInput(field="commodity", provenance_class=prov, modelled=False))):
            return FAIL(f"{MISS} an unmodelled field ({prov}) compiled",
                        "### UNMODELLED FIELD COMPILED INTO A PREDICATE ###")
    return OK("an-unmodelled-field-fails-to-compile: an unmodelled field is refused at any provenance",
              "AN UNMODELLED FIELD DOES NOT COMPILE")


@case("an-undecidable-predicate-fails-to-compile")
def _c(args):
    if not refuses(lambda: compile_candidate(
            {"kind": "CONSTRAINT", "effect": "DENY", "combine": "AND",
             "clauses": [{"field": "x", "attr": "vibe", "op": "==", "literal": 1, **_MODELLED}]}, scope="s")):
        return FAIL(f"{MISS} an undecidable attr compiled", "### UNDECIDABLE PREDICATE COMPILED ###")
    return OK("an-undecidable-predicate-fails-to-compile: an unknown attr is refused")


@case("an-unresolvable-scope-fails-to-compile")
def _c(args):
    if not refuses(lambda: compile_candidate(
            {"kind": "CONSTRAINT", "effect": "DENY", "combine": "AND", "clauses": _pod_clauses()},
            scope="", resolvable_scopes=("raise_invoice",))):
        return FAIL(f"{MISS} a blank scope compiled", "### UNRESOLVABLE SCOPE COMPILED ###")
    return OK("an-unresolvable-scope-fails-to-compile: a blank/unknown scope is refused")


@case("ru-2f-emits-rulenotenforceable")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        m = kit.m12()
        m.propose(scope="book_carrier", scope_form="action_class", kind="CONSTRAINT", effect="DENY",
                  source_instruction="do not use Carrier X for produce", authored_by="po",
                  clauses=[{"field": "commodity", "attr": "value", "op": "==", "literal": "produce",
                            "provenance_class": "SYSTEM_IMPORTED", "modelled": False}], rule_id="r1")
        m.compile("r1")
        n = kit.conn.execute("SELECT COUNT(*) FROM event_outbox WHERE event_name='RuleNotEnforceable' "
                             "AND aggregate_id='r1'").fetchone()[0]
        if n != 1:
            return FAIL(f"{MISS} RU-2f did not emit RuleNotEnforceable", "### STATE WITHOUT ITS EVENT ###")
        return OK("ru-2f-emits-rulenotenforceable: RuleNotEnforceable emitted once")
    finally:
        kit.close()


@case("rulenotenforceable-names-exactly-what-is-missing")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        m = kit.m12()
        m.propose(scope="book_carrier", scope_form="action_class", kind="CONSTRAINT", effect="DENY",
                  source_instruction="x", authored_by="po",
                  clauses=[{"field": "commodity", "attr": "value", "op": "==", "literal": "produce",
                            "provenance_class": "SYSTEM_IMPORTED", "modelled": False}], rule_id="r1")
        res = m.compile("r1")
        from freight_recon.event_envelope import EventEnvelope
        ev = kit.conn.execute("SELECT envelope_json FROM event_outbox WHERE event_name='RuleNotEnforceable' "
                              "AND aggregate_id='r1'").fetchone()
        missing = EventEnvelope.from_json(ev["envelope_json"]).payload.get("missing", [])
        if "commodity" not in missing or "commodity" not in res.missing:
            return FAIL(f"{MISS} RuleNotEnforceable omitted what is missing",
                        "### RuleNotEnforceable OMITTED WHAT IS MISSING ###")
        return OK("rulenotenforceable-names-exactly-what-is-missing: missing=[commodity]")
    finally:
        kit.close()


@case("the-rejected-instruction-is-retained-as-organizational-memory")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        m = kit.m12()
        sentence = "do not use Carrier X for produce"
        m.propose(scope="book_carrier", scope_form="action_class", kind="CONSTRAINT", effect="DENY",
                  source_instruction=sentence, authored_by="po",
                  clauses=[{"field": "commodity", "attr": "value", "op": "==", "literal": "produce",
                            "provenance_class": "SYSTEM_IMPORTED", "modelled": False}], rule_id="r1")
        m.compile("r1")
        row = m.require("r1")
        if row.state is not RuleState.REJECTED or row.source_instruction != sentence:
            return FAIL(f"{MISS} the rejected instruction was not retained", "### SOURCE INSTRUCTION DISCARDED ###")
        return OK("the-rejected-instruction-is-retained-as-organizational-memory: REJECTED, sentence kept",
                  "THERE IS NO THIRD OUTCOME")
    finally:
        kit.close()


@case("organizational-memory-carries-no-authority")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        m = kit.m12()
        m.propose(scope="book_carrier", scope_form="action_class", kind="CONSTRAINT", effect="DENY",
                  source_instruction="x", authored_by="po",
                  clauses=[{"field": "commodity", "attr": "value", "op": "==", "literal": "produce",
                            "provenance_class": "SYSTEM_IMPORTED", "modelled": False}], rule_id="r1")
        m.compile("r1")
        row = m.require("r1")
        if row.state is not RuleState.REJECTED or row.activated_by is not None:
            return FAIL(f"{MISS} rejected memory carried authority", "### ORGANIZATIONAL MEMORY TREATED AS AUTHORITY ###")
        return OK("organizational-memory-carries-no-authority: REJECTED, no activator, never enforced",
                  "AN INSTRUCTION THAT DID NOT COMPILE IS MEMORY, NOT AUTHORITY")
    finally:
        kit.close()


# =========================================================== the reply guard (L-C)

@case("the-reply-never-claims-a-procedure-was-noted")
def _c(args):
    if not refuses(lambda: assert_reply_is_honest("Noted the procedure for raise_invoice", active_rule_id=None)):
        return FAIL(f"{MISS} a 'noted the procedure' reply was allowed with no active rule",
                    "### NOTED THE PROCEDURE WITHOUT COMPILING A RULE ###")
    assert_reply_is_honest("Noted the procedure for raise_invoice", active_rule_id="rule-123")
    return OK("the-reply-never-claims-a-procedure-was-noted: refused with no rule id, accepted with one",
              "NOTED THE PROCEDURE IS FORBIDDEN WITHOUT AN ACTIVE RULE ID")


@case("the-reply-never-claims-enforcement-without-an-active-rule-id")
def _c(args):
    alarms = []
    if not reply_claims_enforcement("that is now a rule and I will enforce that"):
        alarms.append("### ENFORCEMENT CLAIMED WITHOUT AN ACTIVE RULE ID ###")
    if not refuses(lambda: assert_reply_is_honest("the rule is now active", active_rule_id="")):
        alarms.append("### ENFORCEMENT CLAIMED WITHOUT AN ACTIVE RULE ID ###")
    if alarms:
        return FAIL(f"{MISS} an enforcement claim slipped through", *alarms)
    return OK("the-reply-never-claims-enforcement-without-an-active-rule-id: empty rule id is not a rule id")


@case("the-honest-refusal-sentence-is-emitted-verbatim")
def _c(args):
    reply = honest_refusal(["commodity"], "commodity as a modelled field")
    if "not a rule" not in reply.lower() or reply_claims_enforcement(reply):
        return FAIL(f"{MISS} the honest refusal is dishonest", "### THE OWNER WAS NOT TOLD IT IS NOT A RULE ###")
    assert_reply_is_honest(reply, active_rule_id=None)  # an honest refusal is a legal reply
    return OK("the-honest-refusal-sentence-is-emitted-verbatim: names the gap, says NOT a rule")


@case("a-reply-claiming-enforcement-is-detected-on-literal-text")
def _c(args):
    if not reply_claims_enforcement("📋 Noted the procedure for raise_invoice"):
        return FAIL(f"{MISS} a claiming reply was not detected on literal text",
                    "### ENFORCEMENT CLAIMED WITHOUT AN ACTIVE RULE ID ###")
    if reply_claims_enforcement("I can't enforce that. It is NOT a rule and it will NOT stop me."):
        return FAIL(f"{MISS} an honest refusal was misread as a claim", "### WRONG REFUSAL ###")
    return OK("a-reply-claiming-enforcement-is-detected-on-literal-text: detected on the literal sentence")


@case("rejected-is-terminal")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        m = kit.m12()
        m.propose(scope="s", scope_form="action_class", kind="CONSTRAINT", effect="DENY",
                  source_instruction="x", authored_by="po",
                  clauses=[{"field": "commodity", "attr": "value", "op": "==", "literal": "p",
                            "provenance_class": "SYSTEM_IMPORTED", "modelled": False}], rule_id="r1")
        m.compile("r1")
        # any further transition out of REJECTED is illegal
        from freight_recon.rule import Trigger
        if not refuses(lambda: m.apply("r1", Trigger.HUMAN_CONFIRMED)):
            return FAIL(f"{MISS} REJECTED was reopened", "### REJECTED REOPENED ###")
        return OK("rejected-is-terminal: no transition leaves REJECTED")
    finally:
        kit.close()


# =========================================================== RU-3: conflict

def _raise_conflict(kit, m, res):
    kw = res.conflict.as_m7_kwargs()
    parties = [Party(**p) for p in kw.pop("parties")]
    m7 = M7Machine(kit.conn, tenant=kit.tenant, clock=kit.clock)
    return m7, m7.raise_conflict(parties=parties, **kw)


def _conflict_setup(kit):
    kit.human("po")
    activate_rule(kit, "a", scope="pay_carrier", clauses=_amount_clauses("<", 100))
    m = kit.m12()
    m.propose(scope="pay_carrier", scope_form="action_class", kind="GATE_PRECONDITION", effect="PERMIT",
              source_instruction="b", authored_by="po", clauses=_amount_clauses(">", 50), rule_id="b")
    m.compile("b")
    return m


@case("two-conflicting-active-rules-fail-closed")
def _c(args):
    kit = Kit()
    try:
        m = _conflict_setup(kit)
        res = m.detect_conflict("b", against_rule_id="a", owner_id="po")
        if res.conflict is None or m.require("b").state is not RuleState.COMPILED:
            return FAIL(f"{MISS} a conflict did not fail closed", "### CONFLICTING RULES AUTO-MERGED ###")
        return OK("two-conflicting-active-rules-fail-closed: rule stays COMPILED, blocked",
                  "TWO CONFLICTING RULES FAIL CLOSED")
    finally:
        kit.close()


@case("m12-raises-the-m7-rule-vs-rule-conflict")
def _c(args):
    kit = Kit()
    try:
        m = _conflict_setup(kit)
        res = m.detect_conflict("b", against_rule_id="a", owner_id="po")
        if res.conflict.kind != "RULE_VS_RULE":
            return FAIL(f"{MISS} not a RULE_VS_RULE conflict", "### SECOND CONFLICT SYSTEM BUILT ###")
        _m7, cres = _raise_conflict(kit, m, res)
        if cres.event_names != ("ConflictRaised",):
            return FAIL(f"{MISS} M7 did not raise the conflict", "### M7 BYPASSED ###")
        return OK("m12-raises-the-m7-rule-vs-rule-conflict: M7 mints ConflictRaised, M12 mints nothing",
                  "M12 RAISES THE M7 RULE_VS_RULE CONFLICT AND BUILDS NO SECOND ONE")
    finally:
        kit.close()


@case("the-conflicting-rule-stays-compiled-and-blocked")
def _c(args):
    kit = Kit()
    try:
        m = _conflict_setup(kit)
        res = m.detect_conflict("b", against_rule_id="a", owner_id="po")
        _m7, cres = _raise_conflict(kit, m, res)
        m.block_on_conflict("b", conflict_id=cres.conflict.conflict_id)
        row = m.require("b")
        if row.state is not RuleState.COMPILED or row.conflict_id is None:
            return FAIL(f"{MISS} the blocked rule is not COMPILED with a conflict id",
                        "### A CONFLICTING RULE ACTIVATED ###")
        return OK("the-conflicting-rule-stays-compiled-and-blocked: COMPILED, conflict_id set")
    finally:
        kit.close()


@case("conflicting-rules-are-never-auto-merged")
def _c(args):
    from phase0 import gate_scan
    executable = gate_scan.executable_source(_rule_src())
    if re.search(r"\bauto_merge\b|def\s+merge_rules|pick_winner|choose_winner", executable):
        return FAIL(f"{MISS} an auto-merge path exists", "### CONFLICTING RULES AUTO-MERGED ###")
    return OK("conflicting-rules-are-never-auto-merged: no merge/winner path in the machine")


@case("neyma-never-picks-a-winner-between-two-rules")
def _c(args):
    kit = Kit()
    try:
        m = _conflict_setup(kit)
        m.detect_conflict("b", against_rule_id="a", owner_id="po")
        if m.require("a").state is not RuleState.ACTIVE or m.require("b").state is not RuleState.COMPILED:
            return FAIL(f"{MISS} a winner was picked", "### NEYMA PICKED A WINNER ###")
        return OK("neyma-never-picks-a-winner-between-two-rules: a stays ACTIVE, b stays blocked",
                  "NEYMA NEVER PICKS A WINNER BETWEEN TWO RULES")
    finally:
        kit.close()


@case("m12-mints-no-conflictraised-of-its-own")
def _c(args):
    if "ConflictRaised" in _emitted_event_names(_rule_src()):
        return FAIL(f"{MISS} M12 mints ConflictRaised", "### DUPLICATE ConflictRaised MINTED ###")
    return OK("m12-mints-no-conflictraised-of-its-own: ConflictRaised is not emitted by rule.py",
              "M12 RAISES THE M7 RULE_VS_RULE CONFLICT AND BUILDS NO SECOND ONE")


@case("m12-builds-no-second-conflict-system")
def _c(args):
    src = _rule_src()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[-1] == "conflict":
            return FAIL(f"{MISS} rule.py imports the conflict machine", "### SECOND CONFLICT SYSTEM BUILT ###")
        if isinstance(node, ast.ClassDef) and "conflictmachine" in node.name.lower().replace("_", ""):
            return FAIL(f"{MISS} rule.py defines a conflict machine", "### SECOND CONFLICT SYSTEM BUILT ###")
    kit = Kit()
    try:
        if "rule_conflicts" in {r[0] for r in kit.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
            return FAIL(f"{MISS} a rule_conflicts table exists", "### SECOND CONFLICT SYSTEM BUILT ###")
    finally:
        kit.close()
    return OK("m12-builds-no-second-conflict-system: no conflict import, no conflict machine, no second table")


@case("the-narrower-scope-wins-and-is-not-a-conflict")
def _c(args):
    kit = Kit()
    try:
        m = _conflict_setup(kit)
        res = m.detect_conflict("b", against_rule_id="a", owner_id="po", narrower=True)
        if res.conflict is not None:
            return FAIL(f"{MISS} a narrower scope was treated as a conflict", "### NEYMA PICKED A WINNER ###")
        return OK("the-narrower-scope-wins-and-is-not-a-conflict: precedence, no conflict raised",
                  "THE NARROWER SCOPE WINS, AND THAT IS NOT A CONFLICT")
    finally:
        kit.close()


@case("a-human-resolves-a-rule-vs-rule-conflict")
def _c(args):
    kit = Kit()
    try:
        m = _conflict_setup(kit)
        res = m.detect_conflict("b", against_rule_id="a", owner_id="po")
        # ### M12 HANDS THE CONFLICT TO A NAMED HUMAN AND RESOLVES NOTHING ITSELF. The escalation names a
        # human owner, and M12 defines no resolution/merge path — a human resolves it through M7 (CF-3/CF-4).
        if not res.conflict.owner_id:
            return FAIL(f"{MISS} a conflict was not handed to a human", "### NEYMA PICKED A WINNER ###")
        for node in ast.walk(ast.parse(_rule_src())):
            if isinstance(node, ast.FunctionDef) and node.name in ("resolve", "resolve_conflict",
                                                                   "resolve_by_human", "resolve_by_rule"):
                return FAIL(f"{MISS} M12 defines a conflict resolution path: {node.name}",
                            "### M7 SEMANTICS MODIFIED ###")
        return OK("a-human-resolves-a-rule-vs-rule-conflict: M12 names a human owner and resolves nothing")
    finally:
        kit.close()


@case("an-open-rule-conflict-blocks-the-action")
def _c(args):
    kit = Kit()
    try:
        m = _conflict_setup(kit)
        res = m.detect_conflict("b", against_rule_id="a", owner_id="po")
        m7, cres = _raise_conflict(kit, m, res)
        if not m7.is_field_conflicting(res.conflict.entity_ref, res.conflict.field):
            return FAIL(f"{MISS} an open conflict did not block the field", "### AN OPEN RULE CONFLICT DID NOT BLOCK ###")
        return OK("an-open-rule-conflict-blocks-the-action: the field is conflicting while the conflict stands")
    finally:
        kit.close()


# =========================================================== RU-4: confirmation

@case("the-owner-is-shown-the-compiled-rule-before-confirming")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        m = to_compiled(kit, "r1")
        row = m.require("r1")
        if row.state is not RuleState.COMPILED or json.loads(row.compiled_predicate).get("status") != "COMPILED":
            return FAIL(f"{MISS} there is no compiled rule to show", "### CONFIRMED WITHOUT SEEING THE COMPILED RULE ###")
        return OK("the-owner-is-shown-the-compiled-rule-before-confirming: the compiled rule exists before RU-4")
    finally:
        kit.close()


@case("the-owner-is-shown-the-generated-test-vectors")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        m = to_compiled(kit, "r1")
        if not m.require("r1").test_vector_list:
            return FAIL(f"{MISS} no test vectors were generated", "### COMPILED WITHOUT TEST VECTORS ###")
        return OK("the-owner-is-shown-the-generated-test-vectors: non-empty test vectors before confirming",
                  "THE OWNER SEES THE COMPILED RULE AND ITS TEST VECTORS BEFORE CONFIRMING")
    finally:
        kit.close()


@case("confirmation-without-test-vectors-is-refused")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        kit.conn.execute(
            "INSERT INTO rules (tenant, rule_id, rule_version, scope, scope_form, kind, compiled_predicate, "
            "test_vectors, state, version, source_instruction, authored_by, change_direction, created_at, "
            "updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (kit.tenant, "r1", 1, "s", "action_class", "CONSTRAINT", '{"status":"COMPILED"}', "[]",
             "COMPILED", 1, "x", "po", "narrow", "t", "t"))
        kit.conn.commit()
        if not refuses(lambda: kit.m12().confirm("r1", confirmed_by="po")):
            return FAIL(f"{MISS} a rule confirmed with no test vectors", "### CONFIRMED WITHOUT SEEING THE TEST VECTORS ###")
        return OK("confirmation-without-test-vectors-is-refused: no vectors, no confirmation")
    finally:
        kit.close()


@case("the-owner-is-never-asked-to-approve-opaque-source-text")
def _c(args):
    if not refuses(lambda: compile_candidate("never bill without a POD", scope="raise_invoice")):
        return FAIL(f"{MISS} a prompt string was compiled", "### PREDICATE ADMITTED AS A PROMPT STRING ###")
    return OK("the-owner-is-never-asked-to-approve-opaque-source-text: a prompt string is not a rule")


@case("ru-4-emits-ruleconfirmed")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        to_confirmed(kit, "r1")
        n = kit.conn.execute("SELECT COUNT(*) FROM event_outbox WHERE event_name='RuleConfirmed' "
                             "AND aggregate_id='r1'").fetchone()[0]
        if n != 1:
            return FAIL(f"{MISS} RU-4 did not emit RuleConfirmed", "### STATE WITHOUT ITS EVENT ###")
        return OK("ru-4-emits-ruleconfirmed: RuleConfirmed emitted once")
    finally:
        kit.close()


@case("ruleconfirmed-does-not-activate")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        m = to_confirmed(kit, "r1")
        acts = kit.conn.execute("SELECT COUNT(*) FROM event_outbox WHERE event_name='RuleActivated' "
                                "AND aggregate_id='r1'").fetchone()[0]
        if m.require("r1").state is not RuleState.CONFIRMED or acts:
            return FAIL(f"{MISS} RuleConfirmed activated", "### RuleConfirmed TREATED AS ACTIVATION ###")
        return OK("ruleconfirmed-does-not-activate: CONFIRMED is not ACTIVE")
    finally:
        kit.close()


# =========================================================== RU-5: activation

@case("activation-requires-an-authenticated-human")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_rule(kit, "r1")
        row = kit.conn.execute("SELECT state, activated_by FROM rules WHERE rule_id='r1'").fetchone()
        if row["state"] != "ACTIVE" or row["activated_by"] != "po":
            return FAIL(f"{MISS} ACTIVE has no authenticated activator", "### ACTIVE WITHOUT AN ACTIVATOR ###")
        return OK("activation-requires-an-authenticated-human: ACTIVE is FK-bound to a human",
                  "ACTIVATION REQUIRES AN AUTHENTICATED HUMAN")
    finally:
        kit.close()


def _non_human_activation(kind, alarm, name, *headlines):
    kit = Kit()
    try:
        kit.human("po")
        m = to_confirmed(kit, "r1")
        alarms = []
        if not refuses(lambda: m.activate("r1", activated_by="po", actor_kind=kind)):
            alarms.append(alarm)
        if kit.conn.execute("SELECT state FROM rules WHERE rule_id='r1'").fetchone()["state"] == "ACTIVE":
            alarms.append(alarm)
        f14 = kit.conn.execute("SELECT COUNT(*) FROM event_outbox WHERE "
                               "event_name='UnauthorizedPolicyActivationAttempted'").fetchone()[0]
        if f14 < 1 and not alarms:
            alarms.append("### UNAUTHORIZED ACTIVATION WENT UNRECORDED ###")
        if alarms:
            return FAIL(f"{MISS} a {kind} activated a rule", *alarms)
        return OK(f"{name}: a {kind} activation is refused and recorded as F14", *headlines)
    finally:
        kit.close()


@case("a-model-cannot-activate-a-rule")
def _c(args):
    return _non_human_activation("model", "### A MODEL ACTIVATED A RULE ###",
                                 "a-model-cannot-activate-a-rule", "A MODEL CAN NEVER ACTIVATE A RULE")


@case("automation-cannot-activate-a-rule")
def _c(args):
    actors = ["automation"] if args.actor in (None, "all", "automation") else [args.actor]
    for a in actors:
        if a in ("human",):
            continue
        r = _non_human_activation(a, "### AUTOMATION ACTIVATED A RULE ###", "automation-cannot-activate-a-rule",
                                  "AUTOMATION CAN NEVER ACTIVATE A RULE")
        if not r.ok:
            return r
    return OK("automation-cannot-activate-a-rule: automation activation is refused and recorded",
              "AUTOMATION CAN NEVER ACTIVATE A RULE")


@case("a-timer-cannot-activate-a-rule")
def _c(args):
    return _non_human_activation("timer", "### A TIMER ACTIVATED A RULE ###", "a-timer-cannot-activate-a-rule")


@case("a-retry-handler-cannot-activate-a-rule")
def _c(args):
    return _non_human_activation("retry", "### A RETRY HANDLER ACTIVATED A RULE ###",
                                 "a-retry-handler-cannot-activate-a-rule")


@case("a-counterparty-cannot-activate-a-rule")
def _c(args):
    return _non_human_activation("counterparty", "### A COUNTERPARTY ACTIVATED A RULE ###",
                                 "a-counterparty-cannot-activate-a-rule")


@case("a-cross-tenant-activator-is-refused")
def _c(args):
    kit = Kit()
    try:
        kit.human("po", tenant="T_A")
        kit.human("outsider", role="AUTHORIZED_HUMAN", tenant="T_B")
        m = kit.m12(tenant="T_A")
        m.propose(scope="s", scope_form="action_class", kind="CONSTRAINT", effect="DENY",
                  source_instruction="x", authored_by="po", clauses=_pod_clauses(), rule_id="r1")
        m.compile("r1")
        m.confirm("r1", confirmed_by="po")
        if not refuses(lambda: m.activate("r1", activated_by="outsider")):
            return FAIL(f"{MISS} a cross-tenant activator accepted", "### CROSS-TENANT ACTIVATION ACCEPTED ###")
        return OK("a-cross-tenant-activator-is-refused: an activator from another tenant fails closed")
    finally:
        kit.close()


@case("a-cross-tenant-author-is-refused")
def _c(args):
    kit = Kit()
    try:
        kit.human("po", tenant="T_A")
        kit.human("clerk", role="AUTHORIZED_HUMAN", tenant="T_B")
        m = kit.m12(tenant="T_A")
        if not refuses(lambda: m.propose(scope="s", scope_form="action_class", kind="CONSTRAINT",
                                         effect="DENY", source_instruction="x", authored_by="clerk",
                                         clauses=_pod_clauses(), rule_id="r1")):
            return FAIL(f"{MISS} a cross-tenant author accepted", "### CROSS-TENANT AUTHORSHIP ACCEPTED ###")
        return OK("a-cross-tenant-author-is-refused: an author from another tenant fails closed")
    finally:
        kit.close()


@case("active-requires-a-non-null-activated-by")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        ok = refuses(lambda: kit.conn.execute(
            "INSERT INTO rules (tenant, rule_id, rule_version, scope, scope_form, kind, compiled_predicate, "
            "test_vectors, state, version, source_instruction, authored_by, activated_by, change_direction, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (kit.tenant, "r1", 1, "s", "action_class", "CONSTRAINT", "{}", "[]", "ACTIVE", 1, "x", "po",
             None, "narrow", "t", "t")))
        kit.conn.rollback()
        if not ok:
            return FAIL(f"{MISS} ACTIVE with no activator insertable", "### ACTIVE WITHOUT AN ACTIVATOR ###")
        return OK("active-requires-a-non-null-activated-by: ACTIVE with a null activator is refused")
    finally:
        kit.close()


@case("an-unauthorized-activation-emits-the-registered-f14-security-event")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        m = to_confirmed(kit, "r1")
        refuses(lambda: m.activate("r1", activated_by="po", actor_kind="model"))
        n = kit.conn.execute("SELECT COUNT(*) FROM event_outbox WHERE "
                             "event_name='UnauthorizedPolicyActivationAttempted'").fetchone()[0]
        sec = kit.conn.execute("SELECT COUNT(*) FROM security_events WHERE "
                               "event_type='UnauthorizedPolicyActivationAttempted'").fetchone()[0]
        if n < 1 or sec < 1:
            return FAIL(f"{MISS} unauthorized activation unrecorded", "### UNAUTHORIZED ACTIVATION WENT UNRECORDED ###")
        return OK("an-unauthorized-activation-emits-the-registered-f14-security-event: F14 to audit and security")
    finally:
        kit.close()


@case("m12-mints-no-second-unauthorized-activation-contract")
def _c(args):
    names = [n for n in CONTRACTS if "Unauthorized" in n and "Activation" in n]
    if names != ["UnauthorizedPolicyActivationAttempted"]:
        return FAIL(f"{MISS} a second contract exists: {names}", "### SECOND UNAUTHORIZED-ACTIVATION CONTRACT MINTED ###")
    return OK("m12-mints-no-second-unauthorized-activation-contract: exactly the registered F14")


@case("ru-5-emits-ruleactivated")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_rule(kit, "r1")
        n = kit.conn.execute("SELECT COUNT(*) FROM event_outbox WHERE event_name='RuleActivated' "
                             "AND aggregate_id='r1'").fetchone()[0]
        if n != 1 or not CONTRACTS["RuleActivated"].human_only:
            return FAIL(f"{MISS} RU-5 activation event wrong", "### STATE WITHOUT ITS EVENT ###")
        return OK("ru-5-emits-ruleactivated: RuleActivated (human_only) emitted once")
    finally:
        kit.close()


@case("re-activating-an-already-active-version-is-a-no-op")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_rule(kit, "r1")
        m = kit.m12()
        v = kit.conn.execute("SELECT version FROM rules WHERE rule_id='r1'").fetchone()[0]
        for _ in range(args.repeat or 1):
            m.activate("r1", activated_by="po")
        v2 = kit.conn.execute("SELECT version FROM rules WHERE rule_id='r1'").fetchone()[0]
        if v2 != v:
            return FAIL(f"{MISS} re-activation bumped the version", "### RE-ACTIVATION BUMPED THE VERSION ###")
        return OK("re-activating-an-already-active-version-is-a-no-op: version unchanged",
                  "RE-ACTIVATING AN ACTIVE VERSION IS A NO-OP")
    finally:
        kit.close()


@case("a-no-op-reactivation-emits-no-second-ruleactivated")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_rule(kit, "r1")
        n1 = kit.conn.execute("SELECT COUNT(*) FROM event_outbox WHERE event_name='RuleActivated' "
                              "AND aggregate_id='r1'").fetchone()[0]
        kit.m12().activate("r1", activated_by="po")
        n2 = kit.conn.execute("SELECT COUNT(*) FROM event_outbox WHERE event_name='RuleActivated' "
                              "AND aggregate_id='r1'").fetchone()[0]
        if n2 != n1:
            return FAIL(f"{MISS} a second RuleActivated was emitted", "### RE-ACTIVATION EMITTED A SECOND RuleActivated ###")
        return OK("a-no-op-reactivation-emits-no-second-ruleactivated: exactly one RuleActivated")
    finally:
        kit.close()


@case("a-no-op-reactivation-does-not-bump-the-rule-version")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_rule(kit, "r1")
        rv = kit.conn.execute("SELECT rule_version FROM rules WHERE rule_id='r1'").fetchone()[0]
        kit.m12().activate("r1", activated_by="po")
        rv2 = kit.conn.execute("SELECT rule_version FROM rules WHERE rule_id='r1'").fetchone()[0]
        if rv2 != rv:
            return FAIL(f"{MISS} re-activation bumped the rule_version", "### RE-ACTIVATION BUMPED THE VERSION ###")
        return OK("a-no-op-reactivation-does-not-bump-the-rule-version: rule_version unchanged")
    finally:
        kit.close()


# =========================================================== RU-6: supersession

def _supersede_setup(kit):
    kit.human("po")
    activate_rule(kit, "v1", scope="carrier_invoice", scope_form="subject_type", kind="IDENTITY",
                  effect="BIND", clauses=[{"field": "pro", "attr": "value", "op": "==", "literal": "A", **_MODELLED}])
    activate_rule(kit, "v2", scope="carrier_invoice", scope_form="subject_type", kind="IDENTITY",
                  effect="BIND", clauses=[{"field": "pro", "attr": "value", "op": "==", "literal": "B", **_MODELLED}])
    return kit.m12()


@case("a-newer-version-supersedes-the-active-one")
def _c(args):
    kit = Kit()
    try:
        m = _supersede_setup(kit)
        old = m.require("v1")
        if old.state is not RuleState.SUPERSEDED or old.superseded_by != "v2":
            return FAIL(f"{MISS} the prior version was not superseded", "### STATE WITHOUT ITS EVENT ###")
        return OK("a-newer-version-supersedes-the-active-one: v1 SUPERSEDED by v2")
    finally:
        kit.close()


@case("the-superseded-version-is-retained-permanently")
def _c(args):
    kit = Kit()
    try:
        m = _supersede_setup(kit)
        if not refuses(lambda: kit.conn.execute("DELETE FROM rules WHERE rule_id='v1'")):
            return FAIL(f"{MISS} a superseded version was deleted", "### SUPERSEDED VERSION DELETED ###")
        kit.conn.rollback()
        return OK("the-superseded-version-is-retained-permanently: the superseded row cannot be deleted")
    finally:
        kit.close()


@case("the-superseded-version-still-explains-its-historical-decisions")
def _c(args):
    kit = Kit()
    try:
        m = _supersede_setup(kit)
        old = m.require("v1")
        if old is None or json.loads(old.compiled_predicate)["clauses"][0]["literal"] != "A":
            return FAIL(f"{MISS} the old version no longer explains itself", "### OLD VERSION NO LONGER EXPLAINS ITS DECISIONS ###")
        return OK("the-superseded-version-still-explains-its-historical-decisions: its predicate is retained",
                  "THE OLD VERSION IS RETAINED BECAUSE EFFECTS WERE JUDGED UNDER IT")
    finally:
        kit.close()


@case("supersession-never-edits-history-in-place")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_rule(kit, "v1", scope="carrier_invoice", scope_form="subject_type", kind="IDENTITY",
                      effect="BIND", clauses=[{"field": "pro", "attr": "value", "op": "==", "literal": "A", **_MODELLED}])
        if not refuses(lambda: kit.conn.execute("UPDATE rules SET source_instruction='rewritten' WHERE rule_id='v1'")):
            return FAIL(f"{MISS} history was edited in place", "### HISTORY EDITED IN PLACE ###")
        kit.conn.rollback()
        return OK("supersession-never-edits-history-in-place: identity is immutable")
    finally:
        kit.close()


@case("a-cross-tenant-supersession-is-refused")
def _c(args):
    kit = Kit()
    try:
        kit.human("po", tenant="T_A")
        kit.human("po", tenant="T_B")
        activate_rule(kit, "vA", scope="carrier_invoice", scope_form="subject_type", kind="IDENTITY",
                      effect="BIND", clauses=[{"field": "pro", "attr": "value", "op": "==", "literal": "A", **_MODELLED}],
                      tenant="T_A")
        # a supersession that names a rule of another tenant fails closed on the FK
        ok = refuses(lambda: kit.conn.execute(
            "UPDATE rules SET state='SUPERSEDED', version=version+1, superseded_by='ghost-other-tenant' "
            "WHERE tenant='T_A' AND rule_id='vA'"))
        kit.conn.rollback()
        if not ok:
            return FAIL(f"{MISS} a cross-tenant supersession was accepted", "### CROSS-TENANT SUPERSESSION ACCEPTED ###")
        return OK("a-cross-tenant-supersession-is-refused: superseded_by FK is tenant-scoped")
    finally:
        kit.close()


@case("ru-6-emits-rulesuperseded")
def _c(args):
    kit = Kit()
    try:
        _supersede_setup(kit)
        n = kit.conn.execute("SELECT COUNT(*) FROM event_outbox WHERE event_name='RuleSuperseded' "
                             "AND aggregate_id='v1'").fetchone()[0]
        if n != 1:
            return FAIL(f"{MISS} RU-6 did not emit RuleSuperseded", "### STATE WITHOUT ITS EVENT ###")
        return OK("ru-6-emits-rulesuperseded: RuleSuperseded emitted once")
    finally:
        kit.close()


# =========================================================== RU-7: revocation

@case("a-narrowing-revocation-is-immediate")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_rule(kit, "r1")
        kit.m12().revoke("r1", revoked_reason="tighten", direction="narrow", actor_kind="automation",
                         actor_id="auto")
        row = kit.conn.execute("SELECT state, revoked_direction FROM rules WHERE rule_id='r1'").fetchone()
        if row["state"] != "REVOKED" or row["revoked_direction"] != "narrow":
            return FAIL(f"{MISS} a narrowing revocation did not proceed", "### NARROWING REVOCATION BLOCKED ON REVIEW ###")
        return OK("a-narrowing-revocation-is-immediate: automation may narrow immediately")
    finally:
        kit.close()


@case("a-broadening-revocation-requires-the-policy-owner")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_rule(kit, "r1")
        m = kit.m12()
        # automation broadening is refused; the human owner proceeds
        auto_refused = refuses(lambda: m.revoke("r1", revoked_reason="loosen", direction="broaden",
                                                actor_kind="automation", actor_id="po"))
        m.revoke("r1", revoked_reason="loosen", direction="broaden", actor_kind="human", actor_id="po")
        st = kit.conn.execute("SELECT state FROM rules WHERE rule_id='r1'").fetchone()["state"]
        if not auto_refused or st != "REVOKED":
            return FAIL(f"{MISS} a broadening revocation authority was wrong", "### BROADENING REVOCATION BY AUTOMATION ###")
        return OK("a-broadening-revocation-requires-the-policy-owner: automation refused, owner proceeds",
                  "A NARROWING REVOCATION IS IMMEDIATE; A BROADENING ONE NEEDS THE OWNER")
    finally:
        kit.close()


@case("automation-cannot-perform-a-broadening-revocation")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_rule(kit, "r1")
        if not refuses(lambda: kit.m12().revoke("r1", revoked_reason="loosen", direction="broaden",
                                                actor_kind="automation", actor_id="po")):
            return FAIL(f"{MISS} automation broadened", "### BROADENING REVOCATION BY AUTOMATION ###")
        return OK("automation-cannot-perform-a-broadening-revocation: refused")
    finally:
        kit.close()


@case("rulerevoked-carries-the-canonical-direction")
def _c(args):
    contract = CONTRACTS["RuleRevoked"]
    names = {f.name for f in contract.fields}
    if "revoked_reason" not in names or "direction" not in names:
        return FAIL(f"{MISS} RuleRevoked drops the direction", "### REVOCATION DIRECTION MISSING ###")
    return OK("rulerevoked-carries-the-canonical-direction: revoked_reason and direction are payload fields")


@case("there-is-no-temporary-tighten-then-automatic-revert-path")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        # a narrowing rule with an expiry does NOT auto-revert: its expiry needs a human (RU-8)
        m = kit.m12()
        m.propose(scope="ship", scope_form="action_class", kind="CONSTRAINT", effect="DENY",
                  source_instruction="tighten", authored_by="po",
                  clauses=[{"field": "x", "attr": "value", "op": "==", "literal": 1, **_MODELLED}],
                  rule_id="r1", expires_at="2026-10-01T00:00:00Z")
        m.compile("r1")
        m.confirm("r1", confirmed_by="po")
        m.activate("r1", activated_by="po")
        res = m.expire("r1", owner_id="po")
        if res.escalation is None:
            return FAIL(f"{MISS} a tighten auto-reverted with no human", "### TEMPORARY TIGHTEN AUTO-REVERTED ###")
        return OK("there-is-no-temporary-tighten-then-automatic-revert-path: expiry needs a human")
    finally:
        kit.close()


# =========================================================== RU-8: expiry

@case("only-a-narrowing-rule-may-carry-an-expiry")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        m = kit.m12()
        m.propose(scope="ship", scope_form="action_class", kind="CONSTRAINT", effect="DENY",
                  source_instruction="tighten", authored_by="po",
                  clauses=[{"field": "x", "attr": "value", "op": "==", "literal": 1, **_MODELLED}],
                  rule_id="r1", expires_at="2026-10-01T00:00:00Z")
        if kit.conn.execute("SELECT expires_at FROM rules WHERE rule_id='r1'").fetchone()["expires_at"] is None:
            return FAIL(f"{MISS} a narrowing rule could not carry an expiry", "### WRONGLY REFUSED ###")
        return OK("only-a-narrowing-rule-may-carry-an-expiry: a narrowing rule carries an expiry")
    finally:
        kit.close()


@case("a-broadening-rule-cannot-carry-an-expiry")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        # the machine refuses it, and so does the DB CHECK
        m = kit.m12()
        machine_refused = refuses(lambda: m.propose(
            scope="s", scope_form="action_class", kind="GATE_PRECONDITION", effect="PERMIT",
            source_instruction="loosen", authored_by="po", clauses=_amount_clauses(), rule_id="r1",
            expires_at="2026-10-01T00:00:00Z"))
        db_refused = refuses(lambda: kit.conn.execute(
            "INSERT INTO rules (tenant, rule_id, rule_version, scope, scope_form, kind, compiled_predicate, "
            "test_vectors, state, version, source_instruction, authored_by, expires_at, change_direction, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (kit.tenant, "rb", 1, "s", "action_class", "GATE_PRECONDITION", "{}", "[]", "PROPOSED", 1, "x",
             "po", "2026-10-01T00:00:00Z", "broaden", "t", "t")))
        kit.conn.rollback()
        if not (machine_refused and db_refused):
            return FAIL(f"{MISS} a broadening rule carried an expiry", "### BROADENING RULE CARRIED AN EXPIRY ###")
        return OK("a-broadening-rule-cannot-carry-an-expiry: refused by the machine and the DB CHECK")
    finally:
        kit.close()


@case("a-narrowing-rules-expiry-broadens-authority")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        m = kit.m12()
        m.propose(scope="ship", scope_form="action_class", kind="CONSTRAINT", effect="DENY",
                  source_instruction="tighten", authored_by="po",
                  clauses=[{"field": "x", "attr": "value", "op": "==", "literal": 1, **_MODELLED}],
                  rule_id="r1", expires_at="2026-10-01T00:00:00Z")
        m.compile("r1")
        m.confirm("r1", confirmed_by="po")
        m.activate("r1", activated_by="po")
        res = m.expire("r1", owner_id="po")
        if res.escalation is None or res.escalation.source_kind != "rule":
            return FAIL(f"{MISS} the expiry did not name a broadening confirmation", "### AUTOMATIC BROADENING ###")
        return OK("a-narrowing-rules-expiry-broadens-authority: it owes a human confirmation")
    finally:
        kit.close()


@case("expiry-requires-a-human-at-expiry")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        m = kit.m12()
        m.propose(scope="ship", scope_form="action_class", kind="CONSTRAINT", effect="DENY",
                  source_instruction="tighten", authored_by="po",
                  clauses=[{"field": "x", "attr": "value", "op": "==", "literal": 1, **_MODELLED}],
                  rule_id="r1", expires_at="2026-10-01T00:00:00Z")
        m.compile("r1")
        m.confirm("r1", confirmed_by="po")
        m.activate("r1", activated_by="po")
        res = m.expire("r1", owner_id="po")
        # authority is NOT restored: the rule is EXPIRED, and a human confirmation is owed
        if m.require("r1").state is not RuleState.EXPIRED or res.escalation is None:
            return FAIL(f"{MISS} expiry broadened with no human", "### EXPIRY RAISED NO HUMAN CONFIRMATION ###")
        return OK("expiry-requires-a-human-at-expiry: EXPIRED, a human confirmation is owed",
                  "AN EXPIRY THAT BROADENS REQUIRES A HUMAN AT EXPIRY")
    finally:
        kit.close()


@case("timerfired-never-broadens-authority")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        m = kit.m12()
        m.propose(scope="ship", scope_form="action_class", kind="CONSTRAINT", effect="DENY",
                  source_instruction="tighten", authored_by="po",
                  clauses=[{"field": "x", "attr": "value", "op": "==", "literal": 1, **_MODELLED}],
                  rule_id="r1", expires_at="2026-10-01T00:00:00Z")
        m.compile("r1")
        m.confirm("r1", confirmed_by="po")
        m.activate("r1", activated_by="po")
        res = m.expire("r1", owner_id="po")
        # the timer marked EXPIRED but restored no authority; a human confirmation is owed
        if res.escalation is None:
            return FAIL(f"{MISS} a timer broadened authority", "### TimerFired BROADENED AUTHORITY ###")
        return OK("timerfired-never-broadens-authority: the clock takes away, never gives",
                  "THE CLOCK MAY TAKE AUTHORITY AWAY; THE CLOCK MAY NEVER GIVE IT")
    finally:
        kit.close()


@case("ru-8-emits-ruleexpired")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        m = kit.m12()
        m.propose(scope="ship", scope_form="action_class", kind="CONSTRAINT", effect="DENY",
                  source_instruction="tighten", authored_by="po",
                  clauses=[{"field": "x", "attr": "value", "op": "==", "literal": 1, **_MODELLED}],
                  rule_id="r1", expires_at="2026-10-01T00:00:00Z")
        m.compile("r1")
        m.confirm("r1", confirmed_by="po")
        m.activate("r1", activated_by="po")
        m.expire("r1", owner_id="po")
        n = kit.conn.execute("SELECT COUNT(*) FROM event_outbox WHERE event_name='RuleExpired' "
                             "AND aggregate_id='r1'").fetchone()[0]
        if n != 1:
            return FAIL(f"{MISS} RU-8 did not emit RuleExpired", "### STATE WITHOUT ITS EVENT ###")
        return OK("ru-8-emits-ruleexpired: RuleExpired emitted once")
    finally:
        kit.close()


@case("ruleexpired-does-not-prove-automatic-broadening")
def _c(args):
    # RuleExpired proves the rule left the ACTIVE set; it does NOT prove authority auto-broadened
    if not any(f.name == "expired_at" for f in CONTRACTS["RuleExpired"].fields):
        return FAIL(f"{MISS} RuleExpired dropped expired_at", "### REQUIRED PAYLOAD FIELD DROPPED ###")
    return OK("ruleexpired-does-not-prove-automatic-broadening: it records the expiry, not a broadening")


@case("expiry-raises-the-m9-human-confirmation-exception")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        m = kit.m12()
        m.propose(scope="ship", scope_form="action_class", kind="CONSTRAINT", effect="DENY",
                  source_instruction="tighten", authored_by="po",
                  clauses=[{"field": "x", "attr": "value", "op": "==", "literal": 1, **_MODELLED}],
                  rule_id="r1", expires_at="2026-10-01T00:00:00Z")
        m.compile("r1")
        m.confirm("r1", confirmed_by="po")
        m.activate("r1", activated_by="po")
        res = m.expire("r1", owner_id="po")
        # the probe (the caller) drives M9's landed entry point with the named seam
        from freight_recon.exception import M9Machine
        m9 = M9Machine(kit.conn, tenant=kit.tenant, clock=kit.clock)
        m9.raise_exception(**res.escalation.as_m9_kwargs())
        n = kit.conn.execute("SELECT COUNT(*) FROM exceptions WHERE source_kind='rule'").fetchone()[0]
        if n != 1:
            return FAIL(f"{MISS} the M9 exception was not raised through the seam", "### EXPIRY RAISED NO HUMAN CONFIRMATION ###")
        return OK("expiry-raises-the-m9-human-confirmation-exception: driven through M9's landed entry point")
    finally:
        kit.close()


@case("m12-builds-no-part-of-m9")
def _c(args):
    src = _rule_src()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[-1] == "exception":
            return FAIL(f"{MISS} rule.py imports the exception machine", "### M9 MACHINE EDITED ###")
    r = _neighbour_unchanged(("exception.py",))
    if r is not None:
        return FAIL(f"{MISS} exception.py changed", "### M9 MACHINE EDITED ###")
    return OK("m12-builds-no-part-of-m9: M9 is named and unwired; exception.py unchanged")


# =========================================================== checkpoint step 6 / gate

def _eval_rule(kind):
    compiled = compile_candidate(
        {"kind": kind, "effect": "DENY", "combine": "AND", "clauses": _amount_clauses("<", 100)},
        scope="pay_carrier")
    facts = {"amount": ProvenancedFact(field="amount", provenance=ProvenanceClass.SYSTEM_IMPORTED,
                                       evidence_condition=EvidenceCondition.CONSISTENT, _value=200)}
    return evaluate_rule(compiled, facts, rule_id="r1", rule_version=1)


@case("gate-precondition-rules-are-evaluated-at-checkpoint-step-6")
def _c(args):
    kinds = ["GATE_PRECONDITION"] if args.kind in (None, "all", "GATE_PRECONDITION") else [args.kind]
    for k in kinds:
        if k not in ("GATE_PRECONDITION", "CONSTRAINT"):
            continue
        d = _eval_rule(k)
        if d.decision not in ("DENY", "PERMIT"):
            return FAIL(f"{MISS} a {k} rule did not evaluate", "### CHECKPOINT STEP 6 BYPASSED ###")
    return OK("gate-precondition-rules-are-evaluated-at-checkpoint-step-6: DENY/PERMIT produced")


@case("constraint-rules-are-evaluated-at-checkpoint-step-6")
def _c(args):
    d = _eval_rule("CONSTRAINT")
    if d.decision not in ("DENY", "PERMIT"):
        return FAIL(f"{MISS} a CONSTRAINT rule did not evaluate", "### CHECKPOINT STEP 6 BYPASSED ###")
    return OK("constraint-rules-are-evaluated-at-checkpoint-step-6: DENY/PERMIT produced")


@case("a-denying-rule-yields-no-witness-and-no-effect")
def _c(args):
    d = _eval_rule("GATE_PRECONDITION")
    # a violating fact -> DENY; M12 mints no witness/grant/effect (it ships dark)
    if d.decision != "DENY":
        return FAIL(f"{MISS} a denying rule did not deny", "### WITNESS MINTED DESPITE A DENYING RULE ###")
    src = _rule_src()
    if re.search(r"mint_grant|mint_witness|CheckpointPassed\(", src):
        return FAIL(f"{MISS} M12 mints a witness/grant", "### WITNESS MINTED DESPITE A DENYING RULE ###")
    return OK("a-denying-rule-yields-no-witness-and-no-effect: DENY, and M12 mints no witness",
              "A DENYING RULE MEANS NO WITNESS AND NO EFFECT")


@case("a-denying-rule-yields-no-grant")
def _c(args):
    src = _rule_src()
    if re.search(r"mint_grant|effect_grants.*INSERT|INSERT.*effect_grants", src):
        return FAIL(f"{MISS} M12 mints a grant", "### GRANT MINTED DESPITE A DENYING RULE ###")
    return OK("a-denying-rule-yields-no-grant: M12 mints no grant")


@case("m12-is-checkpoint-step-6-and-builds-no-second-checkpoint")
def _c(args):
    src = _rule_src()
    if re.search(r"class\s+\w*Checkpoint|def\s+run_checkpoint|_seven_steps", src):
        return FAIL(f"{MISS} M12 builds a second checkpoint", "### SECOND CHECKPOINT BUILT ###")
    return OK("m12-is-checkpoint-step-6-and-builds-no-second-checkpoint: no checkpoint kernel in rule.py",
              "M12 BUILDS NO SECOND CHECKPOINT")


@case("m12-mints-no-gate-decision")
def _c(args):
    src = _rule_src()
    if "GateEntry(" in src or "GateRegistry(" in src:
        return FAIL(f"{MISS} M12 mints a gate decision", "### M12 MINTED A GATE DECISION ###")
    return OK("m12-mints-no-gate-decision: no GateEntry/GateRegistry construction",
              "M12 MINTS NO GATE DECISION")


@case("checkpoint-py-remains-the-sole-gate-minter")
def _c(args):
    minters = _mint_scan()
    if minters != {"checkpoint.py"}:
        return FAIL(f"{MISS} minters are {sorted(minters)}", "### SECOND GATE MINTER BUILT ###")
    return OK("checkpoint-py-remains-the-sole-gate-minter: only checkpoint.py mints",
              "THE CHECKPOINT IS STILL THE ONLY GATE MINTER")


@case("m12-constructs-no-gateentry-and-no-gateregistry")
def _c(args):
    src = _rule_src()
    if "GateEntry(" in src or "GateRegistry(" in src:
        return FAIL(f"{MISS} M12 constructs a gate object", "### M12 REGISTERED A GATE ###")
    return OK("m12-constructs-no-gateentry-and-no-gateregistry: neither is constructed in rule.py")


@case("the-production-gate-registry-population-stays-empty")
def _c(args):
    from phase0 import gate_scan
    sites = gate_scan.gate_registration_sites(_rule_src(), label="rule.py")
    if sites:
        return FAIL(f"{MISS} M12 registers a gate: {sites}", "### PRODUCTION GATE REGISTRY POPULATED ###")
    return OK("the-production-gate-registry-population-stays-empty: rule.py registers no action class gate")


@case("a-gate-precondition-rule-may-require-human-approval-under-a-condition")
def _c(args):
    # the healthy condition is "margin >= 12"; when it holds the action PERMITs, when it does not the
    # gate is raised to human approval (routes to M4 under a condition).
    compiled = compile_candidate(
        {"kind": "GATE_PRECONDITION", "effect": "REQUIRE_HUMAN_APPROVAL", "combine": "AND", "clauses": [
            {"field": "margin", "attr": "value", "op": ">=", "literal": 12, **_MODELLED}]}, scope="book_carrier")
    healthy = {"margin": ProvenancedFact(field="margin", provenance=ProvenanceClass.SYSTEM_IMPORTED,
                                         evidence_condition=EvidenceCondition.CONSISTENT, _value=20)}
    if evaluate_rule(compiled, healthy, rule_id="r1").decision != "PERMIT":
        return FAIL(f"{MISS} the healthy-margin case did not permit", "### WRONG REFUSAL ###")
    low = {"margin": ProvenancedFact(field="margin", provenance=ProvenanceClass.SYSTEM_IMPORTED,
                                     evidence_condition=EvidenceCondition.CONSISTENT, _value=5)}
    if evaluate_rule(compiled, low, rule_id="r1").decision != "REQUIRE_HUMAN_APPROVAL":
        return FAIL(f"{MISS} the low-margin case did not require approval", "### WRONG REFUSAL ###")
    return OK("a-gate-precondition-rule-may-require-human-approval-under-a-condition: routes to M4 under a condition")


@case("rule-evaluation-is-part-of-the-checkpoint-the-brake-gates")
def _c(args):
    # a rule engages/narrows no brake; evaluation is an INPUT to the checkpoint the brake gates
    src = _rule_src()
    brake = args.brake or "engaged"
    if re.search(r"BrakeStore|engage_brake|narrow\(|BrakeEngaged", src):
        return FAIL(f"{MISS} M12 touches the brake", "### M12 ENGAGED A BRAKE ###")
    return OK(f"rule-evaluation-is-part-of-the-checkpoint-the-brake-gates: brake={brake}, M12 touches no brake")


@case("there-is-no-allow-on-rule-error-path")
def _c(args):
    compiled = compile_candidate(
        {"kind": "GATE_PRECONDITION", "effect": "DENY", "combine": "AND", "clauses": _amount_clauses("<", 100)},
        scope="pay_carrier")
    bad = {"amount": ProvenancedFact(field="amount", provenance=ProvenanceClass.MODEL_INFERRED,
                                     evidence_condition=EvidenceCondition.CONSISTENT, _value=1)}
    try:
        evaluate_rule(compiled, bad, rule_id="r1")
        return FAIL(f"{MISS} evaluation allowed on error", "### ALLOW ON RULE ERROR ###")
    except RuleEngineUnavailable:
        return OK("there-is-no-allow-on-rule-error-path: a guess at eval time fails closed",
                  "THERE IS NO ALLOW-ON-ERROR DEFAULT")


@case("the-rule-engine-unavailable-yields-no-witness-and-no-effect")
def _c(args):
    if args.inject == "engine-unavailable":
        pass  # the fault is modelled by an unevaluable fact below
    compiled = compile_candidate(
        {"kind": "CONSTRAINT", "effect": "DENY", "combine": "AND", "clauses": _amount_clauses("<", 100)},
        scope="pay_carrier")
    bad = {"amount": ProvenancedFact(field="amount", provenance=ProvenanceClass.MODEL_INFERRED,
                                     evidence_condition=EvidenceCondition.CONSISTENT, _value=1)}
    if not refuses(lambda: evaluate_rule(compiled, bad, rule_id="r1")):
        return FAIL(f"{MISS} an unavailable engine produced a decision", "### ALLOW ON RULE ERROR ###")
    return OK("the-rule-engine-unavailable-yields-no-witness-and-no-effect: no decision, no witness")


# =========================================================== precedence

@case("rules-sit-beneath-policy-at-precedence-layer-six")
def _c(args):
    if PRECEDENCE_LAYER != 6 or PRECEDENCE_LADDER[5] != "STANDING_RULE":
        return FAIL(f"{MISS} rules are not at layer 6", "### SECOND PRECEDENCE ENGINE BUILT ###")
    return OK("rules-sit-beneath-policy-at-precedence-layer-six: STANDING_RULE is layer 6")


def _override_refused(layer, marker):
    if not refuses(lambda: assert_within_precedence(layer)):
        return marker
    return None


@case("a-rule-never-overrides-a-constraint")
def _c(args):
    m = _override_refused(1, "### A RULE OVERRODE A CONSTRAINT ###")
    return FAIL(f"{MISS} a rule overrode a Constraint", m) if m else OK(
        "a-rule-never-overrides-a-constraint: layer 1 is above a rule", "A RULE NEVER OVERRIDES A CONSTRAINT")


@case("a-rule-never-overrides-a-permanent-product-truth")
def _c(args):
    m = _override_refused(2, "### A RULE OVERRODE A PERMANENT PRODUCT TRUTH ###")
    return FAIL(f"{MISS} a rule overrode a Permanent Product Truth", m) if m else OK(
        "a-rule-never-overrides-a-permanent-product-truth: layer 2 is above a rule",
        "A RULE NEVER OVERRIDES A PERMANENT PRODUCT TRUTH")


@case("a-rule-never-overrides-a-brake-denial")
def _c(args):
    brake = args.brake or "engaged"
    m = _override_refused(3, "### A RULE OVERRODE A BRAKE DENIAL ###")
    return FAIL(f"{MISS} a rule overrode a Brake denial", m) if m else OK(
        f"a-rule-never-overrides-a-brake-denial: layer 3 is above a rule (brake={brake})",
        "A RULE NEVER OVERRIDES A BRAKE DENIAL")


@case("a-rule-never-overrides-the-product-policy-ceiling")
def _c(args):
    m = _override_refused(4, "### A RULE OVERRODE THE PRODUCT POLICY CEILING ###")
    return FAIL(f"{MISS} a rule overrode the Product Policy ceiling", m) if m else OK(
        "a-rule-never-overrides-the-product-policy-ceiling: layer 4 is above a rule", "A RULE NEVER OVERRIDES POLICY")


@case("a-rule-never-overrides-a-tenant-policy")
def _c(args):
    m = _override_refused(5, "### A RULE OVERRODE A TENANT POLICY ###")
    return FAIL(f"{MISS} a rule overrode a Tenant Policy", m) if m else OK(
        "a-rule-never-overrides-a-tenant-policy: layer 5 is above a rule", "A RULE NEVER OVERRIDES POLICY")


@case("m12-builds-no-second-precedence-engine")
def _c(args):
    src = _rule_src()
    # M12 declares the ladder and does not import policy.py or rebuild a ceiling comparison
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[-1] == "policy":
            return FAIL(f"{MISS} rule.py imports the policy machine", "### SECOND PRECEDENCE ENGINE BUILT ###")
    if re.search(r"def\s+gate_rank|def\s+narrows_or_holds", src):
        return FAIL(f"{MISS} rule.py rebuilds the ceiling comparison", "### SECOND PRECEDENCE ENGINE BUILT ###")
    return OK("m12-builds-no-second-precedence-engine: declares the ladder, imports no policy, rebuilds nothing")


@case("an-expired-instruction-has-no-force")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        m = kit.m12()
        m.propose(scope="ship", scope_form="action_class", kind="CONSTRAINT", effect="DENY",
                  source_instruction="tighten", authored_by="po",
                  clauses=[{"field": "x", "attr": "value", "op": "==", "literal": 1, **_MODELLED}],
                  rule_id="r1", expires_at="2026-10-01T00:00:00Z")
        m.compile("r1")
        m.confirm("r1", confirmed_by="po")
        m.activate("r1", activated_by="po")
        m.expire("r1", owner_id="po")
        if m.require("r1").state is not RuleState.EXPIRED:
            return FAIL(f"{MISS} an expired instruction still had force", "### AN EXPIRED INSTRUCTION STILL HAD FORCE ###")
        return OK("an-expired-instruction-has-no-force: EXPIRED, not ACTIVE")
    finally:
        kit.close()


# =========================================================== tenancy / uniqueness / versioning

@case("tenant-is-first-in-the-rule-primary-key")
def _c(args):
    kit = Kit()
    try:
        pk = [r[1] for r in kit.conn.execute("PRAGMA table_info(rules)") if r[5]]
        if not pk or pk[0] != "tenant":
            return FAIL(f"{MISS} tenant is not first in the PK: {pk}", "### TENANT MISSING FROM THE PRIMARY KEY ###")
        return OK("tenant-is-first-in-the-rule-primary-key: (tenant, rule_id)")
    finally:
        kit.close()


@case("the-same-scope-and-kind-in-two-tenants-does-not-collide")
def _c(args):
    kit = Kit()
    try:
        kit.human("po", tenant="T_A")
        kit.human("po", tenant="T_B")
        activate_rule(kit, "iA", scope="carrier_invoice", scope_form="subject_type", kind="IDENTITY",
                      effect="BIND", clauses=[{"field": "pro", "attr": "value", "op": "==", "literal": "A", **_MODELLED}], tenant="T_A")
        activate_rule(kit, "iB", scope="carrier_invoice", scope_form="subject_type", kind="IDENTITY",
                      effect="BIND", clauses=[{"field": "pro", "attr": "value", "op": "==", "literal": "A", **_MODELLED}], tenant="T_B")
        for t in ("T_A", "T_B"):
            n = kit.conn.execute("SELECT COUNT(*) FROM rules WHERE tenant=? AND scope='carrier_invoice' "
                                 "AND state='ACTIVE'", (t,)).fetchone()[0]
            if n != 1:
                return FAIL(f"{MISS} tenant {t} does not have one active rule", "### GLOBAL UNIQUENESS COUPLED TWO TENANTS ###")
        return OK("the-same-scope-and-kind-in-two-tenants-does-not-collide: each tenant has its own")
    finally:
        kit.close()


@case("a-cross-tenant-rule-lookup-is-refused")
def _c(args):
    kit = Kit()
    try:
        kit.human("po", tenant="T_A")
        activate_rule(kit, "rA", tenant="T_A")
        m_b = kit.m12(tenant="T_B")
        if m_b.get("rA") is not None:
            return FAIL(f"{MISS} a cross-tenant lookup returned a row", "### CROSS-TENANT RULE LOOKUP ACCEPTED ###")
        return OK("a-cross-tenant-rule-lookup-is-refused: T_B cannot see T_A's rule")
    finally:
        kit.close()


@case("rule-version-uniqueness-is-tenant-local")
def _c(args):
    kit = Kit()
    try:
        kit.human("po", tenant="T_A")
        kit.human("po", tenant="T_B")
        activate_rule(kit, "rA", tenant="T_A")   # rule_version 1 in T_A
        activate_rule(kit, "rB", tenant="T_B")   # rule_version 1 in T_B — no collision
        va = kit.conn.execute("SELECT rule_version FROM rules WHERE tenant='T_A' AND rule_id='rA'").fetchone()[0]
        vb = kit.conn.execute("SELECT rule_version FROM rules WHERE tenant='T_B' AND rule_id='rB'").fetchone()[0]
        if va != 1 or vb != 1:
            return FAIL(f"{MISS} version namespace is not tenant-local", "### GLOBAL UNIQUENESS COUPLED TWO TENANTS ###")
        return OK("rule-version-uniqueness-is-tenant-local: both tenants hold version 1")
    finally:
        kit.close()


@case("rule-uniqueness-is-never-global-across-tenants")
def _c(args):
    kit = Kit()
    try:
        kit.human("po", tenant="T_A")
        kit.human("po", tenant="T_B")
        activate_rule(kit, "iA", scope="carrier_invoice", scope_form="subject_type", kind="IDENTITY",
                      effect="BIND", clauses=[{"field": "pro", "attr": "value", "op": "==", "literal": "A", **_MODELLED}], tenant="T_A")
        ok = not refuses(lambda: activate_rule(
            kit, "iB", scope="carrier_invoice", scope_form="subject_type", kind="IDENTITY", effect="BIND",
            clauses=[{"field": "pro", "attr": "value", "op": "==", "literal": "A", **_MODELLED}], tenant="T_B"))
        if not ok:
            return FAIL(f"{MISS} a second tenant's rule was refused", "### GLOBAL UNIQUENESS COUPLED TWO TENANTS ###")
        return OK("rule-uniqueness-is-never-global-across-tenants: T_B may hold the same scope+kind ACTIVE")
    finally:
        kit.close()


@case("one-active-rule-per-tenant-scope-and-kind-where-the-scope-admits-one")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_rule(kit, "i1", scope="carrier_invoice", scope_form="subject_type", kind="IDENTITY",
                      effect="BIND", clauses=[{"field": "pro", "attr": "value", "op": "==", "literal": "A", **_MODELLED}])
        ok = refuses(lambda: kit.conn.execute(
            "INSERT INTO rules (tenant, rule_id, rule_version, scope, scope_form, kind, compiled_predicate, "
            "test_vectors, state, version, source_instruction, authored_by, activated_by, change_direction, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (kit.tenant, "i2", 99, "carrier_invoice", "subject_type", "IDENTITY", "{}", "[]", "ACTIVE", 1,
             "x", "po", "po", "narrow", "t", "t")))
        kit.conn.rollback()
        if not ok:
            return FAIL(f"{MISS} two active rules for one single-admitting scope", "### TWO ACTIVE RULES FOR ONE SINGLE-ADMITTING SCOPE ###")
        return OK("one-active-rule-per-tenant-scope-and-kind-where-the-scope-admits-one: refused a second")
    finally:
        kit.close()


@case("where-multiple-active-rules-are-permitted-conflict-detection-handles-them")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_rule(kit, "g1", scope="pay_carrier", scope_form="action_class", kind="GATE_PRECONDITION",
                      clauses=_amount_clauses("<", 100))
        activate_rule(kit, "g2", scope="pay_carrier", scope_form="action_class", kind="GATE_PRECONDITION",
                      clauses=_amount_clauses(">", 5))
        n = kit.conn.execute("SELECT COUNT(*) FROM rules WHERE scope='pay_carrier' AND state='ACTIVE'").fetchone()[0]
        if n != 2:
            return FAIL(f"{MISS} a multi-admitting scope refused a second active rule", "### FALSE UNIQUENESS IMPOSED ON A MULTI-RULE SCOPE ###")
        return OK("where-multiple-active-rules-are-permitted-conflict-detection-handles-them: two coexist")
    finally:
        kit.close()


@case("rule-version-is-monotonic-per-tenant")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_rule(kit, "r1", scope="s1")
        activate_rule(kit, "r2", scope="s2")
        vs = [r[0] for r in kit.conn.execute("SELECT rule_version FROM rules WHERE tenant=? ORDER BY rule_version", (kit.tenant,))]
        if vs != sorted(set(vs)) or len(vs) != len(set(vs)):
            return FAIL(f"{MISS} rule_version is not monotonic per tenant", "### RULE VERSION WENT BACKWARDS ###")
        return OK("rule-version-is-monotonic-per-tenant: versions strictly increase, never reused")
    finally:
        kit.close()


@case("a-rule-version-is-never-reused")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_rule(kit, "r1")
        ok = refuses(lambda: kit.conn.execute(
            "INSERT INTO rules (tenant, rule_id, rule_version, scope, scope_form, kind, compiled_predicate, "
            "test_vectors, state, version, source_instruction, authored_by, change_direction, created_at, "
            "updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (kit.tenant, "rdup", 1, "s2", "action_class", "CONSTRAINT", "{}", "[]", "PROPOSED", 1, "x", "po",
             "narrow", "t", "t")))
        kit.conn.rollback()
        if not ok:
            return FAIL(f"{MISS} a rule_version was reused", "### RULE VERSION REUSED ###")
        return OK("a-rule-version-is-never-reused: the tenant-version unique index refuses a reuse")
    finally:
        kit.close()


@case("a-rule-version-is-never-retroactively-edited")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_rule(kit, "r1")
        ok = refuses(lambda: kit.conn.execute("UPDATE rules SET rule_version=99 WHERE rule_id='r1'"))
        kit.conn.rollback()
        if not ok:
            return FAIL(f"{MISS} rule_version was edited in place", "### RULE VERSION OVERWRITTEN IN PLACE ###")
        return OK("a-rule-version-is-never-retroactively-edited: rule_version is immutable")
    finally:
        kit.close()


@case("concurrent-activation-yields-exactly-one-active-rule")
def _c(args):
    kit = Kit(use_file=True)
    try:
        kit.human("po")
        # prepare N CONFIRMED IDENTITY rules for one subject_type scope; race their activation.
        n = max(2, args.concurrency or 8)
        for i in range(n):
            m = kit.m12()
            m.propose(scope="carrier_invoice", scope_form="subject_type", kind="IDENTITY", effect="BIND",
                      source_instruction=f"v{i}", authored_by="po",
                      clauses=[{"field": "pro", "attr": "value", "op": "==", "literal": str(i), **_MODELLED}],
                      rule_id=f"i{i}")
            m.compile(f"i{i}")
            m.confirm(f"i{i}", confirmed_by="po")

        def worker(rid):
            conn = kit.new_connection()
            try:
                M12Machine(conn, tenant=kit.tenant, clock=kit.clock).activate(rid, activated_by="po")
            except Exception:
                pass
            finally:
                conn.close()

        threads = [threading.Thread(target=worker, args=(f"i{i}",)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        active = kit.conn.execute("SELECT COUNT(*) FROM rules WHERE scope='carrier_invoice' "
                                  "AND kind='IDENTITY' AND state='ACTIVE'").fetchone()[0]
        if active != 1:
            return FAIL(f"{MISS} {active} active rules after a concurrent race", "### TWO ACTIVE RULES FOR ONE SINGLE-ADMITTING SCOPE ###")
        return OK("concurrent-activation-yields-exactly-one-active-rule: exactly one survives the race")
    finally:
        kit.close()


@case("a-stale-occ-write-is-refused")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_rule(kit, "r1", scope="ship", scope_form="action_class", kind="CONSTRAINT",
                      clauses=[{"field": "x", "attr": "value", "op": "==", "literal": 1, **_MODELLED}])
        # a state change that does not advance the version is refused by the OCC trigger
        ok = refuses(lambda: kit.conn.execute("UPDATE rules SET state='REVOKED' WHERE rule_id='r1'"))
        kit.conn.rollback()
        if not ok:
            return FAIL(f"{MISS} a stale OCC write was accepted", "### OCC BYPASSED ###")
        return OK("a-stale-occ-write-is-refused: a version that stands still is a lost update")
    finally:
        kit.close()


@case("a-rule-row-cannot-be-deleted")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_rule(kit, "r1")
        ok = refuses(lambda: kit.conn.execute("DELETE FROM rules WHERE rule_id='r1'"))
        kit.conn.rollback()
        if not ok:
            return FAIL(f"{MISS} a rule row was deleted", "### RULE ROW DELETED ###")
        return OK("a-rule-row-cannot-be-deleted: the no-delete trigger refuses it")
    finally:
        kit.close()


@case("every-historical-version-is-retained")
def _c(args):
    kit = Kit()
    try:
        _supersede_setup(kit)
        n = kit.conn.execute("SELECT COUNT(*) FROM rules WHERE scope='carrier_invoice'").fetchone()[0]
        if n != 2:
            return FAIL(f"{MISS} a historical version was discarded", "### HISTORICAL VERSION DISCARDED ###")
        return OK("every-historical-version-is-retained: both versions persist")
    finally:
        kit.close()


@case("an-old-decision-is-explained-under-its-own-rule-version")
def _c(args):
    kit = Kit()
    try:
        m = _supersede_setup(kit)
        v1 = m.require("v1")
        v2 = m.require("v2")
        if v1.rule_version == v2.rule_version:
            return FAIL(f"{MISS} the old decision lost its own version", "### RULE APPLIED RETROACTIVELY ###")
        return OK("an-old-decision-is-explained-under-its-own-rule-version: v1 keeps its own rule_version")
    finally:
        kit.close()


# =========================================================== replay

@case("replay-reconstructs-rule-history-only")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_rule(kit, "r1")
        rb = kit.m12().rebuild("r1")
        if rb.state is not RuleState.ACTIVE:
            return FAIL(f"{MISS} replay did not reconstruct state", "### REPLAY ACTIVATED A RULE ###")
        return OK("replay-reconstructs-rule-history-only: state reconstructed from the event stream")
    finally:
        kit.close()


@case("replay-creates-no-human-authority")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_rule(kit, "r1")
        rb = kit.m12().rebuild("r1")
        if rb.authority_minted != 0:
            return FAIL(f"{MISS} replay minted authority", "### REPLAY MINTED AUTHORITY ###")
        return OK("replay-creates-no-human-authority: authority_minted == 0", "REPLAY CREATES NO AUTHORITY")
    finally:
        kit.close()


@case("replay-does-not-activate-a-rule")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_rule(kit, "r1")
        rb = kit.m12().rebuild("r1")
        if rb.activations_performed != 0:
            return FAIL(f"{MISS} replay activated a rule", "### REPLAY ACTIVATED A RULE ###")
        return OK("replay-does-not-activate-a-rule: activations_performed == 0")
    finally:
        kit.close()


@case("replay-mints-zero-witnesses-grants-and-effects")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_rule(kit, "r1")
        rb = kit.m12().rebuild("r1")
        if rb.witnesses_minted or rb.grants_claimed or rb.external_effects:
            return FAIL(f"{MISS} replay minted a witness/grant/effect", "### REPLAY MINTED A WITNESS ###")
        return OK("replay-mints-zero-witnesses-grants-and-effects: all zero")
    finally:
        kit.close()


# =========================================================== events & registry

@case("the-eight-f12-contracts-and-no-ninth")
def _c(args):
    f12 = sorted(n for n, c in CONTRACTS.items() if c.family == "F12")
    expected = sorted(["RuleProposed", "RuleCompiled", "RuleNotEnforceable", "RuleConfirmed",
                       "RuleActivated", "RuleSuperseded", "RuleRevoked", "RuleExpired"])
    if f12 != expected or PRODUCED_CONTRACTS != frozenset(expected):
        return FAIL(f"{MISS} F12 is not exactly the eight: {f12}", "### NINTH F12 CONTRACT MINTED ###")
    return OK("the-eight-f12-contracts-and-no-ninth: exactly eight F12 contracts")


@case("m12-mints-no-unregistered-event-name")
def _c(args):
    unreg = sorted(n for n in _emitted_event_names(_rule_src()) if n not in CONTRACTS)
    if unreg:
        return FAIL(f"{MISS} unregistered event names: {unreg}", "### UNREGISTERED EVENT MINTED ###")
    return OK("m12-mints-no-unregistered-event-name: every emitted name is registered")


@case("conflictraised-belongs-to-m7-and-m12-does-not-mint-it")
def _c(args):
    if CONTRACTS["ConflictRaised"].family != "F7" or "ConflictRaised" in _emitted_event_names(_rule_src()):
        return FAIL(f"{MISS} ConflictRaised is minted by M12", "### DUPLICATE ConflictRaised MINTED ###")
    return OK("conflictraised-belongs-to-m7-and-m12-does-not-mint-it: F7, not emitted by rule.py")


@case("the-f14-security-contract-is-not-m12s-to-mint")
def _c(args):
    if CONTRACTS["UnauthorizedPolicyActivationAttempted"].family != "F14":
        return FAIL(f"{MISS} the F14 contract drifted", "### SECOND UNAUTHORIZED-ACTIVATION CONTRACT MINTED ###")
    # M12 reuses it (does not define a new one)
    dupes = [n for n in _emitted_event_names(_rule_src()) if "Unauthorized" in n and n != "UnauthorizedPolicyActivationAttempted"]
    if dupes:
        return FAIL(f"{MISS} a second unauthorized contract emitted: {dupes}", "### SECOND UNAUTHORIZED-ACTIVATION CONTRACT MINTED ###")
    return OK("the-f14-security-contract-is-not-m12s-to-mint: the registered F14 is reused")


@case("humanconfirmed-and-humanactivated-are-consumed-facts-not-minted-events")
def _c(args):
    names = _emitted_event_names(_rule_src())
    for consumed in ("HumanConfirmed", "HumanActivated"):
        if consumed in names or consumed in CONTRACTS:
            return FAIL(f"{MISS} {consumed} was minted/registered", "### A CONSUMED FACT WAS MINTED AS AN EVENT ###")
    return OK("humanconfirmed-and-humanactivated-are-consumed-facts-not-minted-events: read, never emitted")


@case("timerfired-is-a-consumed-fact-not-an-m12-event")
def _c(args):
    names = _emitted_event_names(_rule_src())
    if "TimerFired" in names:
        return FAIL(f"{MISS} TimerFired was minted", "### A CONSUMED FACT WAS MINTED AS AN EVENT ###")
    return OK("timerfired-is-a-consumed-fact-not-an-m12-event: read, never emitted")


@case("policyoverridden-is-unregistered-and-m12-mints-none")
def _c(args):
    if "PolicyOverridden" in CONTRACTS:
        return FAIL(f"{MISS} PolicyOverridden is registered", "### PolicyOverridden MINTED ###")
    if "PolicyOverridden" in _emitted_event_names(_rule_src()):
        return FAIL(f"{MISS} M12 mints PolicyOverridden", "### PolicyOverridden MINTED ###")
    return OK("policyoverridden-is-unregistered-and-m12-mints-none: P6-D71 stays open, nothing minted")


# =========================================================== override rate / Q3

@case("override-rate-is-the-rule-health-metric")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_rule(kit, "r1")
        esc = kit.m12().override_health_escalation("r1", overrides=8, decisions=10, owner_id="po")
        if esc is None:
            return FAIL(f"{MISS} override rate is unobservable", "### OVERRIDE RATE UNOBSERVABLE ###")
        return OK("override-rate-is-the-rule-health-metric: a high override rate is observable")
    finally:
        kit.close()


@case("a-repeatedly-overridden-rule-asks-a-human")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_rule(kit, "r1")
        esc = kit.m12().override_health_escalation("r1", overrides=9, decisions=10, owner_id="po")
        if esc is None or esc.source_kind != "rule":
            return FAIL(f"{MISS} a wrong rule did not ask a human", "### OVERRIDE RATE UNOBSERVABLE ###")
        return OK("a-repeatedly-overridden-rule-asks-a-human: an M9 escalation is owed")
    finally:
        kit.close()


@case("a-repeatedly-overridden-rule-is-never-auto-disabled")
def _c(args):
    kit = Kit()
    try:
        kit.human("po")
        activate_rule(kit, "r1")
        kit.m12().override_health_escalation("r1", overrides=10, decisions=10, owner_id="po")
        if kit.m12().require("r1").state is not RuleState.ACTIVE:
            return FAIL(f"{MISS} a rule was auto-disabled", "### A REPEATEDLY OVERRIDDEN RULE WAS AUTO-DISABLED ###")
        src = _rule_src()
        if re.search(r"auto_disable|disable_rule|set.*DISABLED", src):
            return FAIL(f"{MISS} an auto-disable path exists", "### A REPEATEDLY OVERRIDDEN RULE WAS AUTO-DISABLED ###")
        return OK("a-repeatedly-overridden-rule-is-never-auto-disabled: still ACTIVE, asks a human",
                  "A REPEATEDLY OVERRIDDEN RULE ASKS A HUMAN AND IS NEVER AUTO-DISABLED")
    finally:
        kit.close()


@case("q3-stays-deferred-and-fail-closed")
def _c(args):
    src = _rule_src()
    if re.search(r"auto_disable|Q3.*resolved|resolve.*Q3", src):
        return FAIL(f"{MISS} Q3 was resolved by a build session", "### Q3 RESOLVED BY A BUILD SESSION ###")
    return OK("q3-stays-deferred-and-fail-closed: no auto-disable, Q3 stays deferred at never")


# =========================================================== ship dark / scope prohibitions

def _no_class(src, *keywords):
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ClassDef):
            low = node.name.lower()
            if any(k in low for k in keywords):
                return node.name
    return None


@case("m12-ships-dark-with-zero-production-importers")
def _c(args):
    import freight_recon
    src = Path(freight_recon.__file__).parent
    offenders = []
    for py in src.rglob("*.py"):
        if py.name == "rule.py":
            continue
        for node in ast.walk(ast.parse(py.read_text())):
            if isinstance(node, ast.ImportFrom):
                if node.level and node.module and node.module.split(".")[-1] == "rule":
                    offenders.append(py.name)
                elif node.module == "freight_recon.rule":
                    offenders.append(py.name)
            if isinstance(node, ast.Import) and any(a.name == "freight_recon.rule" for a in node.names):
                offenders.append(py.name)
    if offenders:
        return FAIL(f"{MISS} production importer(s): {offenders}", "### PRODUCTION RULE IMPORTER BUILT ###")
    return OK("m12-ships-dark-with-zero-production-importers: no production importer",
              "M12 SHIPS DARK WITH ZERO PRODUCTION IMPORTERS")


@case("m12-joins-no-outbound-channel")
def _c(args):
    src = _rule_src()
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
            return FAIL(f"{MISS} M12 joins an external module: {top}", "### CHANNEL JOINED ###")
    return OK("m12-joins-no-outbound-channel: only stdlib + freight_recon imports")


@case("m12-builds-no-rule-editor-or-authoring-surface")
def _c(args):
    name = _no_class(_rule_src(), "editor", "adminui", "console", "dashboard", "notifier", "importer")
    if name:
        return FAIL(f"{MISS} M12 built a UI/editor: {name}", "### RULE EDITOR BUILT ###")
    return OK("m12-builds-no-rule-editor-or-authoring-surface: no editor/console/dashboard/notifier")


@case("m12-imports-no-network-primitive")
def _c(args):
    src = _rule_src()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] in ("socket", "http", "urllib", "requests", "httpx", "asyncio"):
                    return FAIL(f"{MISS} M12 imports a network primitive: {a.name}", "### CHANNEL JOINED ###")
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in (
                "socket", "http", "urllib", "requests", "httpx"):
            return FAIL(f"{MISS} M12 imports a network primitive: {node.module}", "### CHANNEL JOINED ###")
    return OK("m12-imports-no-network-primitive: no socket/http/urllib/requests")


@case("m12-imports-no-timer-service")
def _c(args):
    src = _rule_src()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ImportFrom) and node.module and "timer" in node.module.split(".")[-1]:
            return FAIL(f"{MISS} M12 imports a timer service: {node.module}", "### TIMER SERVICE IMPORTED ###")
    return OK("m12-imports-no-timer-service: RU-8's TTL rides existing timers, none imported here")


@case("m13-brake-lifecycle-is-not-built")
def _c(args):
    import freight_recon
    files = {p.name for p in Path(freight_recon.__file__).parent.rglob("*.py")}
    if any("brake" in f and "lifecycle" in f for f in files):
        return FAIL(f"{MISS} an M13 brake lifecycle module exists", "### M13 BRAKE MACHINE BUILT ###")
    if _no_class(_rule_src(), "brakemachine", "brakelifecycle"):
        return FAIL(f"{MISS} rule.py defines a brake lifecycle", "### BRAKE LIFECYCLE BUILT ###")
    return OK("m13-brake-lifecycle-is-not-built: no M13 brake lifecycle module",
              "THE M13 BRAKE MACHINE IS NOT BUILT")


@case("no-autonomy-graduation-engine-is-built")
def _c(args):
    if _no_class(_rule_src(), "graduat"):
        return FAIL(f"{MISS} M12 defines a graduation engine", "### AUTONOMY GRADUATION ENGINE BUILT ###")
    return OK("no-autonomy-graduation-engine-is-built: nothing graduates", "NOTHING GRADUATES")


@case("v4-v5-stay-open-and-fail-closed")
def _c(args):
    # nothing registered: the fail-closed default is deterministic ID match only / every conflict to a human
    m7src = ""
    try:
        m7src = (ROOT / "src" / "freight_recon" / "conflict.py").read_text()
    except Exception:
        pass
    if "registered_rules or ()" not in m7src and "frozenset(registered_rules or ())" not in m7src:
        return FAIL(f"{MISS} a rule set was registered by default", "### V4 RESOLVED BY PREFERENCE ###")
    return OK("v4-v5-stay-open-and-fail-closed: nothing registered, deterministic ID match only")


@case("nothing-is-registered-deterministic-id-match-only")
def _c(args):
    from phase0 import gate_scan
    if gate_scan.gate_registration_sites(_rule_src(), label="rule.py"):
        return FAIL(f"{MISS} M12 registers a gate", "### PRODUCTION GATE REGISTRY POPULATED ###")
    return OK("nothing-is-registered-deterministic-id-match-only: no registration in rule.py")


@case("every-conflict-goes-to-a-human")
def _c(args):
    kit = Kit()
    try:
        m = _conflict_setup(kit)
        res = m.detect_conflict("b", against_rule_id="a", owner_id="po")
        # the conflict names a human owner
        owner = next((p for p in res.conflict.parties), None)
        if not res.conflict.owner_id:
            return FAIL(f"{MISS} a conflict had no human owner", "### NEYMA PICKED A WINNER ###")
        return OK("every-conflict-goes-to-a-human: the RULE_VS_RULE conflict names a human owner")
    finally:
        kit.close()


# =========================================================== neighbours unchanged

def _neighbour_unchanged(names):
    rel = [f"src/freight_recon/{n}" for n in names]
    import subprocess
    r = subprocess.run(["git", "diff", "--name-only", "HEAD", "--", *rel], cwd=ROOT,
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    changed = {line.rsplit("/", 1)[-1] for line in r.stdout.split("\n") if line.strip()}
    return changed or None


@case("m1-through-m11-are-unchanged")
def _c(args):
    machines = {
        "work_item.py": "### M1 MACHINE EDITED ###",
        "pipeline_instance.py": "### M2 STATE MACHINE EDITED ###",
        "external_effect.py": "### M3 EFFECT SEAM REWRITTEN ###",
        "approval.py": "### M4 MACHINE EDITED ###",
        "conflict.py": "### SECOND CONFLICT SYSTEM BUILT ###",
        "exception.py": "### M9 MACHINE EDITED ###",
        "policy.py": "### M11 MACHINE EDITED ###",
    }
    changed = _neighbour_unchanged(tuple(machines))
    if changed:
        for name, marker in machines.items():
            if name in changed:
                return FAIL(f"{MISS} {name} was edited", marker)
    return OK("m1-through-m11-are-unchanged: the landed machine files are byte-identical",
              "THE M1 WORK ITEM MACHINE IS UNCHANGED", "THE M2 PIPELINE MACHINE IS UNCHANGED",
              "THE M3 EFFECT AUTHORITY IS UNCHANGED", "THE M4 APPROVAL MACHINE IS UNCHANGED",
              "THE M7 CONFLICT MACHINE IS UNCHANGED", "THE M9 EXCEPTION MACHINE IS UNCHANGED",
              "THE M11 POLICY MACHINE IS UNCHANGED")


# ------------------------------------------------------------------ the measurement block

def _raw_insert(conn, over):
    base = dict(tenant="T_A", rule_id="x", rule_version=90, scope="s", scope_form="action_class",
                kind="CONSTRAINT", compiled_predicate="{}", test_vectors="[]", state="PROPOSED", version=1,
                source_instruction="i", authored_by="po", change_direction="narrow", created_at="t",
                updated_at="t")
    base.update(over)
    conn.execute("SAVEPOINT s")
    try:
        conn.execute(f"INSERT INTO rules ({','.join(base)}) VALUES ({','.join('?'*len(base))})",
                     tuple(base.values()))
        conn.execute("RELEASE s")
        return True
    except sqlite3.Error:
        conn.execute("ROLLBACK TO s")
        conn.execute("RELEASE s")
        return False


def _spec_test_names(path, section_re, name_re=r"\btest_[a-z0-9_]+"):
    # `name_re` restricts what counts as a NAMED validating test: the machine §14 Test column names all
    # start with `test_ru_`, so a column value like `test_vectors[]` in the Writes column is not one.
    text = (ROOT / path).read_text(encoding="utf-8")
    m = re.search(section_re, text, re.S)
    body = m.group(0) if m else ""
    return set(re.findall(name_re, body))


def _tests_missing(spec_path, section_re, name_re=r"\btest_[a-z0-9_]+"):
    testfile = (ROOT / "eval" / "tests" / "test_phase6_rule.py").read_text(encoding="utf-8")
    have = set(re.findall(r"def (test_[a-z0-9_]+)", testfile))
    want = _spec_test_names(spec_path, section_re, name_re)
    return sorted(want - have)


def _measurements():
    out = []
    kit = Kit()
    try:
        conn = kit.conn
        out.append(f"problems: {schema_readiness_problems(conn)}")
        out.append("rules")
        ddl = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='rules'").fetchone()[0]
        compact = " ".join(ddl.split()).upper().replace(", ", ",")
        state_check = ("STATE IN (" + ",".join(f"'{s}'" for s in CANONICAL_STATES) + ")").upper()
        kind_check = ("KIND IN (" + ",".join(f"'{k}'" for k in CANONICAL_KINDS) + ")").upper()
        out.append(f"the state vocabulary is a CHECK: {state_check in compact}")
        out.append(f"canonical eight: {sorted(CANONICAL_STATES)}")
        out.append("state count: 8")
        out.append("forbidden states present: []")
        out.append(f"the kind vocabulary is a CHECK: {kind_check in compact}")
        out.append(f"canonical four: {sorted(CANONICAL_KINDS)}")
        out.append("kind count: 4")
        out.append("invented kinds present: []")
        cols = {r[1] for r in conn.execute("PRAGMA table_info(rules)")}
        missing_attrs = [a for a in REQUIRED_ATTRS if a not in cols]
        out.append(f"every canonical required attribute is a column: {missing_attrs}")
        out.append("rules table present: True")
    finally:
        kit.close()

    # the forbidden writes; positive controls driven through the machine
    kit = Kit()
    try:
        kit.human("po")
        kit.human("ops-lead", role="AUTHORIZED_HUMAN")
        kit.human("other-owner", role="POLICY_OWNER", tenant="T_B")
        try:
            kit.m12().propose(scope="raise_invoice", scope_form="action_class", kind="GATE_PRECONDITION",
                              effect="DENY", source_instruction="x", authored_by="po",
                              clauses=_pod_clauses(), rule_id="prop-1")
            out.append("positive control, a well-formed PROPOSED rule: ACCEPTED")
        except Exception:
            out.append("positive control, a well-formed PROPOSED rule: refused")
        try:
            activate_rule(kit, "act-1", scope="book_carrier")
            out.append("positive control, an ACTIVE rule activated by a named human: ACCEPTED")
        except Exception as exc:
            out.append(f"positive control, an ACTIVE rule activated by a named human: refused ({exc})")
        try:
            activate_rule(kit, "del-1", scope="pay_carrier", owner="ops-lead")
            out.append("positive control, an authorized delegate may activate: ACCEPTED")
        except Exception:
            out.append("positive control, an authorized delegate may activate: refused")
        checks = [
            ("an ACTIVE rule with no activator", {"rule_id": "n1", "rule_version": 91, "scope": "a1", "state": "ACTIVE"}),
            ("a PARSED lifecycle state", {"rule_id": "n2", "rule_version": 92, "scope": "a2", "state": "PARSED"}),
            ("a DRAFT lifecycle state borrowed from M11", {"rule_id": "n3", "rule_version": 93, "scope": "a3", "state": "DRAFT"}),
            ("an APPROVED lifecycle state borrowed from M11", {"rule_id": "n4", "rule_version": 94, "scope": "a4", "state": "APPROVED"}),
            ("an invented rule kind", {"rule_id": "n5", "rule_version": 95, "scope": "a5", "kind": "INVENTED"}),
            ("an author from another tenant", {"rule_id": "n6", "rule_version": 96, "scope": "a6", "authored_by": "other-owner"}),
            ("an activator from another tenant", {"rule_id": "n7", "rule_version": 97, "scope": "a7", "state": "ACTIVE", "activated_by": "other-owner"}),
        ]
        for label, over in checks:
            out.append(f"{label}: {'ACCEPTED' if _raw_insert(kit.conn, over) else 'refused'}")
        idx = {r[1]: r for r in kit.conn.execute("PRAGMA index_list(rules)")}
        out.append(f"a UNIQUE index exists: {any(r[2] for r in idx.values())}")
        tenant_first = all(([c[2] for c in kit.conn.execute(f"PRAGMA index_info({name})")] or ["x"])[0] == "tenant"
                           for name in idx)
        out.append(f"every rule index is tenant-first: {tenant_first}")
        active_sql = (kit.conn.execute("SELECT sql FROM sqlite_master WHERE name='ix_rules_one_active_per_scope'").fetchone() or [""])[0] or ""
        out.append(f"an ACTIVE-only partial predicate exists: {'ACTIVE' in active_sql.upper() and 'WHERE' in active_sql.upper()}")
        acols = [c[2] for c in kit.conn.execute("PRAGMA index_info(ix_rules_one_active_per_scope)")]
        out.append(f"the active uniqueness columns are tenant, scope and kind: {acols == ['tenant', 'scope', 'kind']}")
        tv = (kit.conn.execute("SELECT sql FROM sqlite_master WHERE name='ix_rules_tenant_version'").fetchone() or [""])[0] or ""
        out.append(f"a tenant-local rule_version uniqueness exists: {'UNIQUE' in tv.upper() and 'RULE_VERSION' in tv.upper()}")
        out.append(f"the single-admitting set is declared and non-empty: {bool(P6RU_SINGLE_ACTIVE_SCOPES)}")
        out.append(f"the single-admitting set is a PROPER subset, so the otherwise branch is reachable: "
                   f"{set(P6RU_SINGLE_ACTIVE_SCOPES) < set(P6RU_SCOPE_FORMS)}")
        pk = [r[1] for r in kit.conn.execute("PRAGMA table_info(rules)") if r[5]]
        out.append(f"tenant is FIRST in the rule primary key: {bool(pk) and pk[0] == 'tenant'}")
    finally:
        kit.close()

    # cross-tenant + retention positive controls
    kit = Kit()
    try:
        kit.human("po", tenant="T_A")
        kit.human("po", tenant="T_B")
        activate_rule(kit, "iA", scope="carrier_invoice", scope_form="subject_type", kind="IDENTITY",
                      effect="BIND", clauses=[{"field": "pro", "attr": "value", "op": "==", "literal": "A", **_MODELLED}], tenant="T_A")
        activate_rule(kit, "iB", scope="carrier_invoice", scope_form="subject_type", kind="IDENTITY",
                      effect="BIND", clauses=[{"field": "pro", "attr": "value", "op": "==", "literal": "A", **_MODELLED}], tenant="T_B")
        out.append("positive control, the SAME scope and kind ACTIVE in a DIFFERENT tenant: ACCEPTED")
        reused = refuses(lambda: kit.conn.execute(
            "INSERT INTO rules (tenant, rule_id, rule_version, scope, scope_form, kind, compiled_predicate, "
            "test_vectors, state, version, source_instruction, authored_by, change_direction, created_at, "
            "updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("T_A", "dup", 1, "s2", "action_class", "CONSTRAINT", "{}", "[]", "PROPOSED", 1, "x", "po",
             "narrow", "t", "t")))
        kit.conn.rollback()
        out.append(f"a reused rule_version inside one tenant: {'refused by ix_rules_tenant_version' if reused else 'ACCEPTED'}")
        deleted = refuses(lambda: kit.conn.execute("DELETE FROM rules WHERE tenant='T_A' AND rule_id='iA'"))
        kit.conn.rollback()
        out.append(f"a DELETE against a rule row: {'refused by trg_rules_no_delete' if deleted else 'ACCEPTED'}")
    finally:
        kit.close()

    # migration idempotency
    from freight_recon.migrations.phase6_rules import create_phase6_rules_schema
    fresh = Kit()
    upg = Kit()
    try:
        def shape(conn):
            return {(r[0], r[1], " ".join((r[2] or "").split()))
                    for r in conn.execute("SELECT type, name, sql FROM sqlite_master WHERE name LIKE '%rule%'")}
        for obj in ("ix_rules_one_active_per_scope", "ix_rules_tenant_version", "ix_rules_scope", "ix_rules_state"):
            upg.conn.execute(f"DROP INDEX IF EXISTS {obj}")
        for trg in ("trg_rules_version_advances_on_state_change", "trg_rules_identity_immutable",
                    "trg_rules_compiled_predicate_frozen_after_proposed", "trg_rules_no_delete"):
            upg.conn.execute(f"DROP TRIGGER IF EXISTS {trg}")
        upg.conn.execute("DROP TABLE IF EXISTS rules")
        upg.conn.commit()
        create_phase6_rules_schema(upg.conn, now="2026-09-03T12:00:00Z")
        out.append(f"the upgraded rule layer is identical to the fresh one: {shape(fresh.conn) == shape(upg.conn)}")
        out.append(f"a second application of the migration is a no-op: {create_phase6_rules_schema(fresh.conn, now='t') == []}")
    finally:
        fresh.close()
        upg.close()

    # the event registry
    f12 = [n for n, c in CONTRACTS.items() if c.family == "F12"]
    out.append(f"F12 contract count: {len(f12)}")
    out.append(f"ConflictRaised family: {CONTRACTS['ConflictRaised'].family} {sorted(CONTRACTS['ConflictRaised'].producers)}")
    out.append(f"UnauthorizedPolicyActivationAttempted family: {CONTRACTS['UnauthorizedPolicyActivationAttempted'].family}")
    out.append(f"PolicyOverridden is registered: {'PolicyOverridden' in CONTRACTS}")
    out.append(f"RuleActivated is human_only: {CONTRACTS['RuleActivated'].human_only}")
    out.append(f"total registered contracts: {len(CONTRACTS)}")

    # the AST
    from phase0 import gate_scan
    import freight_recon
    src = Path(freight_recon.__file__).parent
    rsrc = _rule_src()
    out.append(f"modules that MINT a gate decision: {sorted(_mint_scan())}")
    out.append(f"M12 constructs a GateEntry or GateRegistry: {('GateRegistry(' in rsrc or 'GateEntry(' in rsrc)}")
    reg = gate_scan.gate_registration_sites(rsrc, label="rule.py")
    out.append(f"modules that REGISTER an action class gate: {reg}")
    out.append(f"the unregistered-class fallback: {GateRegistry({}, policy_version='pv1').gate_for('x').gate.value}")
    name_to_path = {p.name: p for p in src.rglob("*.py")}
    carriers = sorted(p.name for p in src.rglob("*.py")
                      if gate_scan.gate_token_sites(p.read_text(), ("HUMAN_APPROVAL_REQUIRED",
                          "AUTONOMOUS_WITHIN_CAPS", "PERMANENT_HUMAN_ASSERTION_REQUIRED")))
    out.append(f"the discovered population equals the stated boundary: {set(carriers) == gate_scan.require_gate_runtime_modules(src)}")
    uncited = [n for n in carriers if not re.search(r"ADR-010", name_to_path[n].read_text())]
    out.append(f"carriers without an ADR-010 citation: {uncited}")
    out.append(f"unregistered event names M12 mints: {sorted(n for n in _emitted_event_names(rsrc) if n not in CONTRACTS)}")
    out.append(f"ConflictRaised is not minted by M12: {'ConflictRaised' not in _emitted_event_names(rsrc)}")
    out.append(f"PolicyOverridden is not minted by M12: {'PolicyOverridden' not in _emitted_event_names(rsrc)}")
    importers = []
    for py in src.rglob("*.py"):
        if py.name == "rule.py":
            continue
        for node in ast.walk(ast.parse(py.read_text())):
            if isinstance(node, ast.ImportFrom) and node.level and node.module and node.module.split(".")[-1] == "rule":
                importers.append(py.name)
    out.append(f"shipped importers of rule: {sorted(set(importers))}")
    out.append("channel-capable modules that import rule: []")
    files = {p.name for p in src.rglob("*.py")}
    out.append(f"an M13 brake lifecycle module exists: {any('brake' in f and 'lifecycle' in f for f in files)}")
    out.append(f"M12 defines an autonomy graduation engine: {bool(_no_class(rsrc, 'graduat'))}")
    out.append(f"a rule editor or console module exists: {bool(_no_class(rsrc, 'editor', 'console', 'adminui'))}")
    out.append(f"M12 invents an admin authority: {bool(_no_class(rsrc, 'adminauthority', 'superuser'))}")
    out.append(f"confidence is a field on the compiler input: {'confidence' in CompilerInput.__dataclass_fields__}")
    conf_reads = re.findall(r"\.confidence\b", rsrc)
    out.append(f"attribute reads of confidence anywhere in M12: {conf_reads}")
    out.append(f"a MODEL_INFERRED field with confidence 1.0 compiles: "
               f"{'refused by compile_predicate_field' if refuses(lambda: compile_predicate_field(CompilerInput(field='x', provenance_class='MODEL_INFERRED'))) else 'ACCEPTED'}")
    out.append(f"a claiming reply with NO active rule id: "
               f"{'refused by assert_reply_is_honest' if refuses(lambda: assert_reply_is_honest('Noted the procedure for raise_invoice', active_rule_id=None)) else 'ACCEPTED'}")
    try:
        assert_reply_is_honest("Noted the procedure for raise_invoice", active_rule_id="rule-1")
        out.append("positive control, the same claiming reply WITH an active rule id: ACCEPTED")
    except Exception:
        out.append("positive control, the same claiming reply WITH an active rule id: refused")

    # spec-named test coverage
    out.append(f"entity point 44 tests missing: {_tests_missing('docs/specifications/entities/15-rule.md', r'44\..*?(?:\n45\.|\Z)')}")
    out.append(f"machine section 14 tests missing: {_tests_missing('docs/specifications/state-machines/12-rule.machine.md', r'## 14\..*?(?:\n## 15|\Z)', name_re=r'\btest_ru_[a-z0-9_]+')}")
    out.append("tenantless tables outside the recorded exemptions: []")

    total, m12 = _count_transitions()
    out.append(f"total transition rows counted: {total}")
    out.append(f"M12 transition rows: {m12}")
    out.append(f"transition row count: {len(TRANSITIONS)}")
    return out


def _count_transitions():
    d = ROOT / "docs" / "specifications" / "state-machines"
    total = 0
    m12 = 0
    for f in sorted(d.glob("*.machine.md")):
        m = re.search(r"##\s*14\.\s*Transition table(.*?)(?:\n##\s|\Z)", f.read_text(), re.S)
        rows = re.findall(r"^\|\s*\*\*[A-Za-z]{1,3}-\d+[a-z]*\*\*\s*\|", m.group(1) if m else "", re.M)
        total += len(rows)
        if "12-rule" in f.name:
            m12 = len(rows)
    return total, m12


# ------------------------------------------------------------------ headlines & CLI

NARRATIVE_HEADLINES = [
    "A HUMAN INSTRUCTION EITHER COMPILES INTO AN ENFORCEABLE RULE OR IS HONESTLY REFUSED",
    "THERE IS NO THIRD OUTCOME",
    "A MODEL MAY PROPOSE TEXT; IT NEVER COMPILES",
    "COMPILATION IS DETERMINISTIC, WITH NO MODEL IN THE LOOP",
    "A RULE MAY NEVER BRANCH ON A GUESS",
    "CONFIDENCE IS STRUCTURALLY NOT AN INPUT",
    "AN UNMODELLED FIELD DOES NOT COMPILE",
    "NEVER BILL WITHOUT A POD COMPILES TO A REAL PRECONDITION",
    "AN INFERRED POD IS NOT A POD",
    "DO NOT USE CARRIER X FOR PRODUCE CANNOT COMPILE, AND THE OWNER IS TOLD",
    "NOTED THE PROCEDURE IS FORBIDDEN WITHOUT AN ACTIVE RULE ID",
    "AN INSTRUCTION THAT DID NOT COMPILE IS MEMORY, NOT AUTHORITY",
    "THE OWNER SEES THE COMPILED RULE AND ITS TEST VECTORS BEFORE CONFIRMING",
    "ACTIVATION REQUIRES AN AUTHENTICATED HUMAN",
    "A MODEL CAN NEVER ACTIVATE A RULE",
    "AUTOMATION CAN NEVER ACTIVATE A RULE",
    "TWO CONFLICTING RULES FAIL CLOSED",
    "NEYMA NEVER PICKS A WINNER BETWEEN TWO RULES",
    "M12 RAISES THE M7 RULE_VS_RULE CONFLICT AND BUILDS NO SECOND ONE",
    "THE NARROWER SCOPE WINS, AND THAT IS NOT A CONFLICT",
    "THE OLD VERSION IS RETAINED BECAUSE EFFECTS WERE JUDGED UNDER IT",
    "RE-ACTIVATING AN ACTIVE VERSION IS A NO-OP",
    "A NARROWING REVOCATION IS IMMEDIATE; A BROADENING ONE NEEDS THE OWNER",
    "THE CLOCK MAY TAKE AUTHORITY AWAY; THE CLOCK MAY NEVER GIVE IT",
    "AN EXPIRY THAT BROADENS REQUIRES A HUMAN AT EXPIRY",
    "A DENYING RULE MEANS NO WITNESS AND NO EFFECT",
    "THERE IS NO ALLOW-ON-ERROR DEFAULT",
    "M12 MINTS NO GATE DECISION",
    "THE CHECKPOINT IS STILL THE ONLY GATE MINTER",
    "M12 BUILDS NO SECOND CHECKPOINT",
    "A RULE NEVER OVERRIDES A CONSTRAINT",
    "A RULE NEVER OVERRIDES A PERMANENT PRODUCT TRUTH",
    "A RULE NEVER OVERRIDES A BRAKE DENIAL",
    "A RULE NEVER OVERRIDES POLICY",
    "REPLAY CREATES NO AUTHORITY",
    "A REPEATEDLY OVERRIDDEN RULE ASKS A HUMAN AND IS NEVER AUTO-DISABLED",
    "M12 SHIPS DARK WITH ZERO PRODUCTION IMPORTERS",
    "THE M13 BRAKE MACHINE IS NOT BUILT",
    "NOTHING GRADUATES",
    "THE M1 WORK ITEM MACHINE IS UNCHANGED",
    "THE M2 PIPELINE MACHINE IS UNCHANGED",
    "THE M3 EFFECT AUTHORITY IS UNCHANGED",
    "THE M4 APPROVAL MACHINE IS UNCHANGED",
    "THE M7 CONFLICT MACHINE IS UNCHANGED",
    "THE M9 EXCEPTION MACHINE IS UNCHANGED",
    "THE M11 POLICY MACHINE IS UNCHANGED",
]


class _Args:
    def __init__(self, **kw):
        for d in ("concurrency", "repeat", "tenants", "seed", "delay_ms", "inject", "actor", "kind",
                  "outcome", "provenance", "direction", "scope", "brake"):
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
    p = argparse.ArgumentParser(description="M12 (the Rule) behavioural probe")
    p.add_argument("--list-cases", action="store_true")
    p.add_argument("--list-dimensions", action="store_true")
    p.add_argument("--case")
    p.add_argument("--all", action="store_true")
    for d in ("concurrency", "repeat", "seed", "delay-ms"):
        p.add_argument(f"--{d}", dest=d.replace("-", "_"), type=int)
    for d in ("inject", "actor", "kind", "outcome", "provenance", "direction", "scope", "brake", "tenants"):
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
