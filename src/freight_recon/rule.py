"""Machine M12 — the Rule: the registered, versioned, deterministic decision procedure WITH AN ID that
an owner's sentence either compiles into, or honestly does not. This is the machine that resolves Stream
B lesson L-C — the one lesson about what Neyma SAYS rather than what it does.

    ### A HUMAN INSTRUCTION EITHER COMPILES INTO AN ENFORCEABLE RULE, OR IS HONESTLY REFUSED.
    ### THERE IS NO THIRD OUTCOME.
    ### A MODEL MAY PROPOSE TEXT; IT NEVER COMPILES, CONFIRMS, ACTIVATES, EVALUATES OR RESOLVES.
    ### A RULE MAY NEVER BRANCH ON A GUESS.
    ### TWO CONFLICTING RULES FAIL CLOSED; NEYMA NEVER PICKS A WINNER.

An owner types "never bill without a POD." The old system replied "📋 Noted the procedure for
raise_invoice" and installed a sentence in an LLM prompt — the owner believed they installed a control;
they installed a suggestion. M12 makes exactly two outcomes possible: OUTCOME A, the instruction compiles
deterministically into an enforceable Rule with a rule_id, generated test vectors, human confirmation and
authenticated human activation; or OUTCOME B, it does NOT compile, it is retained as non-authoritative
organizational memory, and THE OWNER IS TOLD IN THE LITERAL REPLY that it is not a rule and what is
missing. `assert_reply_is_honest` is the executable form of that guard.

### WHAT THIS MACHINE OWNS, AND WHAT IT ONLY FEEDS.

It owns the EIGHT states PROPOSED/COMPILED/CONFIRMED/ACTIVE/REJECTED/SUPERSEDED/REVOKED/EXPIRED and the
NINE transitions RU-1…RU-8 of `12-rule.machine.md` §14 (the target spec's §12.12 table has EIGHT rows and
is one short — ### M12-AQ-3; the machine table governs, so this builds NINE). It is the canonical producer
of the EIGHT already-registered F12 `Rule*` contracts (entity §31; events registry §3). The `rule`
aggregate is ORDER-TOLERANT (`event_contracts_data.json` records `strict_order: false` on all eight; the
family file says STRICT and `events/registry.md` §8 lists F12 in NEITHER set — ### M12-AQ-5): M12 builds
the fail-closed, stricter side — `rule_version` monotonic per tenant as a DATABASE constraint — and, being
additive and strictly safer, still sets §1's optional `previous_aggregate_version` on emission, WITHOUT
flipping the registered contract's classification.

### IT IS CHECKPOINT STEP 6's RULE EVALUATION; IT MINTS NO GATE DECISION AND BUILDS NO SECOND CHECKPOINT.
A GATE_PRECONDITION/CONSTRAINT rule is evaluated in checkpoint step 6 (entity §38). M12 carries NO gate
vocabulary in executable code — a GATE_PRECONDITION rule's outcome is expressed with the abstract effect
vocabulary (DENY / REQUIRE_HUMAN_APPROVAL / PERMIT), not a `GateDecision` member literal — so `rule.py`
is not a gate-runtime carrier, constructs NO `GateEntry` and NO `GateRegistry`, calls no `register_gate`,
and the production `GateRegistry` population stays EMPTY. `checkpoint.py` remains the SOLE minter of a gate
decision (R-07, AC-CKPT-6-missing, U8.1/P8). A second gate authority is the same defect as no gate
authority, and there is NO allow-on-rule-error path: a rule that cannot be evaluated deterministically
raises and produces no decision, no witness and no effect.

### THE CONFLICT AND EXCEPTION MACHINERY IS ALREADY BUILT; M12 CALLS IT AND MINTS NOTHING (rule 17,
### M12-AQ-2/§3.7). `RULE_VS_RULE` has been in M7's closed `CONFLICT_KINDS` since P6-CP-7 and
`conflicts.rule_id` a column since then; `rule` has been in M9's `SOURCE_KINDS` since P6-CP-9. RU-3 CALLS
M7's landed `raise_conflict` entry point (M7 mints the F7 rule-vs-rule event; M12 mints none, defines no
conflict vocabulary and writes no `conflicts` row directly), and RU-8 / the override-rate seam CALL M9's
landed `raise_exception(source_kind="rule")` entry point. ### M12 IMPORTS `conflict.M7Machine` AND
`exception.M9Machine` AND EDITS NEITHER: it adds no FK, no mirror column and no migration to M7 or M9
(### M12-AQ-6 / P6-D73), and their machine runtimes stay byte-identical. M12 mints no second
unauthorized-activation contract (F14's `UnauthorizedPolicyActivationAttempted` is REUSED) and no
`PolicyOverridden` (unregistered, ### M12-AQ-7 / P6-D71 — BLOCKED_AUTHORITY, minted by nobody but a
founder/architect).

### IT SHIPS DARK. Nothing under `src/freight_recon/` imports this module; the only script that may is
`scripts/probe_phase6_rule.py`. It joins no importer, editor, admin screen, importer, oversight queue,
dashboard or notifier; it builds no part of M13 (Brake) and no autonomy-graduation engine; nothing
graduates. Override rate is the key rule-health metric (entity §42): a repeatedly-overridden rule ASKS a
human through M9 and is NEVER auto-disabled — Q3 stays deferred at "never", and no override mechanism is
built (### M12-AQ-7).
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

# ### THE GATING FACT ACCESSOR AND ITS RAISE, REUSED FROM THE CHECKPOINT KERNEL — NEVER REINVENTED.
# `ProvenancedFact.value` RAISES on a MODEL_INFERRED read and carries NO confidence field, so an evaluated
# rule handed a guess at runtime FAILS CLOSED rather than deciding on it. M12 imports NO `GateDecision`:
# it names no gate member in executable code (a GATE_PRECONDITION rule's outcome is the abstract effect
# vocabulary), so it is not a gate-runtime carrier and mints nothing.
from .checkpoint import GateReadOfInferredFact, ProvenancedFact
# ### M12 CALLS M7 AND M9'S LANDED ENTRY POINTS (§3.7 "CALLS it"; the permanent scenario asserts M12
# reaches both by import). RU-3 raises the rule-vs-rule conflict through `M7Machine.raise_conflict`; RU-8
# and the override-rate seam raise a human-confirmation Exception through `M9Machine.raise_exception`. M12
# edits NEITHER machine — no FK, no mirror column, no migration — and both runtimes stay byte-identical.
from .conflict import M7Machine, Party
from .event_contracts import CONTRACTS
from .event_envelope import EventEnvelope, format_instant
from .event_inbox import ConsumeResult, DedupInbox
from .exception import M9Machine
# ### REUSE M7's LANDED SIX-MEMBER PROVENANCE CLASSES AND ITS RULE_VS_RULE KIND — NO PRIVATE COPY.
from .migrations.phase6_conflicts import CONFLICT_KINDS, PROVENANCE_CLASSES
from .migrations.phase6_rules import (
    NON_TERMINAL_RULE_STATES,
    P6RU_SCOPE_FORMS,
    P6RU_SINGLE_ACTIVE_SCOPES,
    RULE_KINDS,
    RULE_STATES,
    REVOKE_DIRECTIONS,
    TERMINAL_RULE_STATES,
)
from .tenant import require_tenant

# The aggregate this machine owns. `rule` is ORDER-TOLERANT (### M12-AQ-5): the DB monotonicity constraint
# is the real ordering guarantee; the additive `previous_aggregate_version` is set as the safer side.
AGGREGATE_TYPE = "rule"

# entity §5 — the Policy Engine owns rule compilation.
PRODUCER_COMPONENT = "policy_engine"

# The one consumer identity M12 presents to the dedup inbox. Fixed, because the dedup key is
# `(tenant, consumer_id, event_id)` and a renamed consumer would re-arm every duplicate.
CONSUMER_ID = "m12-rule"

# GR-1's producer id for `IllegalTransitionAttempted` — the RULE, not a transition. Identical to M1..M11's.
ILLEGAL_TRANSITION_PRODUCER = "GR-1"

# A refusal advances no version; two refusals against one rule at one version would otherwise collide on
# one idempotency identity — the poison-loop defect M1 shipped. Applied here.
ILLEGAL_ATTEMPT_IDENTITY_PREFIX = "ita_v1"

HUMAN = "HUMAN"

# The M7 conflict kind M12 fails closed into (RU-3). Reused from M7's closed vocabulary; not redefined.
RULE_VS_RULE = "RULE_VS_RULE"
assert RULE_VS_RULE in CONFLICT_KINDS, "RULE_VS_RULE must be one of M7's landed conflict kinds"

# ### THE ABSTRACT RULE-EFFECT VOCABULARY (kept deliberately FREE of the four gate-decision member tokens,
# so `rule.py` is not a gate-runtime carrier). A GATE_PRECONDITION/CONSTRAINT rule DENIES, REQUIRES HUMAN
# APPROVAL under a condition, or PERMITs; an IDENTITY rule BINDs; a CONFLICT_RESOLUTION rule RESOLVEs.
# The mapping of REQUIRE_HUMAN_APPROVAL onto the checkpoint's human-approval gate happens at step 6 (P8),
# in the kernel — never here.
RULE_EFFECTS: tuple[str, ...] = ("DENY", "REQUIRE_HUMAN_APPROVAL", "PERMIT", "BIND", "RESOLVE")

# The effects that NARROW authority (add a restriction). Everything else BROADENS (loosens). Only a
# narrowing rule may carry an expiry, because its expiry BROADENS and needs a human at expiry.
_NARROWING_EFFECTS: frozenset[str] = frozenset({"DENY", "REQUIRE_HUMAN_APPROVAL", "BIND", "RESOLVE"})

# The kinds evaluated by the checkpoint at step 6 (entity §38). IDENTITY and CONFLICT_RESOLUTION are
# consulted by the Identity Service and Reconciliation instead — the four kinds do not behave alike.
CHECKPOINT_EVALUATED_KINDS: frozenset[str] = frozenset({"GATE_PRECONDITION", "CONSTRAINT"})

# The eight registered F12 contracts M12 mints, and no ninth. Derived below from the transition table.
PRODUCED_CONTRACTS: frozenset[str]

# ### THE ADR-010 §8 PRECEDENCE LADDER, HIGHEST FIRST. A rule sits at LAYER 6; five things sit above it and
# a rule may override NONE of them. M12 declares the ladder it sits in and refuses to sit above it; it
# builds NO second precedence engine and writes NO second ceiling comparison — the precedence/conflict-
# resolution ENGINE is P8's, and the ceiling comparison is M11's (M12 does not import policy.py, to keep
# M11's ship-dark posture — it declares its position and defers the comparison to the checkpoint).
PRECEDENCE_LADDER: tuple[str, ...] = (
    "CONSTRAINT",                 # 1 — enforced, not evaluated
    "PERMANENT PRODUCT TRUTH",    # 2 — nothing below may override it
    "HUMAN BRAKE",                # 3 — admission control; denies regardless of everything below
    "PRODUCT POLICY",             # 4 — the ceiling
    "TENANT POLICY",              # 5 — may only narrow #4
    "STANDING RULE",              # 6 — ### YOU ARE HERE
    "WORKFLOW DEFAULT",           # 7 — the fallback, never autonomous
)
PRECEDENCE_LAYER = 6  # STANDING RULE, 1-indexed. A rule may never claim a layer above this.


# ### THE LITERAL PHRASES A REPLY MAY NEVER CARRY WITHOUT AN ACTIVE rule_id (M-52/M-64/T16). "Noted the
# procedure" is the exact sentence the old system used to install nothing while sounding like it installed
# a control. Case-insensitive substrings; the honest refusal deliberately contains NONE of them.
FORBIDDEN_ACKNOWLEDGEMENTS: frozenset[str] = frozenset({
    "noted the procedure",
    "📋 noted the procedure",
    "noted the rule",
    "procedure noted",
    "i've noted the procedure",
    "i have noted the procedure",
    "consider it noted",
    "got it, noted",
})

# The broader set of AFFIRMATIVE "it is now enforced/installed" claims a reply may not make without an
# ACTIVE rule_id — a SUPERSET of the acknowledgements above. Deliberately affirmative only: the honest
# refusal ("I can't enforce that … it is NOT a rule and it will NOT stop me") matches none of these.
_ENFORCEMENT_CLAIMS: frozenset[str] = FORBIDDEN_ACKNOWLEDGEMENTS | frozenset({
    "i'll enforce that",
    "i will enforce that",
    "i've enforced that",
    "i have enforced that",
    "that is now a rule",
    "that's now a rule",
    "it is now a rule",
    "the rule is now active",
    "the rule is active",
    "i've set that up as a rule",
    "i've installed the rule",
    "i will make sure that never happens again",
    "from now on i will enforce",
})


# ------------------------------------------------------------------------------------ errors

class M12Error(RuntimeError):
    """This machine will not do what was asked. Never degraded into a partial transition."""


class UnknownRule(M12Error):
    """No `rules` row with this id exists FOR THIS TENANT. Indistinguishable from "belongs to another
    tenant" on purpose — [C-1] rejects a cross-tenant question."""


class GuardNotSatisfied(M12Error):
    """The (state, trigger) pair IS legal here and a precondition is false. No event is emitted."""


class IllegalTransition(M12Error):
    """GR-1 / [C-4] / GR-7. The (state, trigger) pair is not enumerated, or a model/automation/inbound
    actor attempted an authorship or activation it may never perform. Raised AFTER the tripwire."""


class StateConflict(M12Error):
    """A state-guarded UPDATE matched zero rows: the rule moved under us (GR-3). Reload."""


class MalformedRule(M12Error):
    """The inputs are not a canonical rule — an invented state/kind/scope_form, a blank scope. Fail
    closed; nothing is persisted."""


class RuleWillNotCompile(M12Error):
    """### A GUESS CANNOT BECOME A RULE BY BEING PASSED THROUGH A COMPILER (M-49, GR-8, ADR-010 §5.1/§6).
    A referenced field is unmodelled or `MODEL_INFERRED`, the predicate is undecidable, the scope does not
    resolve, or a prompt string was handed in where a structured candidate belongs — so it FAILS TO COMPILE
    and the owner is TOLD it is not a rule. `missing` names exactly what is missing."""

    def __init__(self, message: str, *, missing: Sequence[str] = ()) -> None:
        super().__init__(message)
        self.missing: tuple[str, ...] = tuple(missing)


class RuleEngineUnavailable(M12Error):
    """### THE RULE ENGINE CANNOT PRODUCE A DETERMINISTIC DECISION ⇒ NO DECISION ⇒ NO WITNESS ⇒ NO EFFECT.
    There is no allow-on-error default anywhere in this unit; an allow-on-error default is how the fence
    dies quietly, at the moment the system is least able to tell anyone."""


class DishonestReply(M12Error):
    """### THE L-C GUARD, ON THE LITERAL REPLY TEXT (M-52/M-64/T16). A reply claims a procedure was noted or
    that enforcement exists, and no ACTIVE rule_id backs it. An empty-string rule id is not a rule id."""


# ------------------------------------------------------------------- the honest-reply guard

def reply_claims_enforcement(text: str) -> bool:
    """True iff `text` claims (affirmatively) that a procedure was noted or that a control is now enforced.
    Case-insensitive. Detects the "noted the procedure" family and the broader affirmative-installation
    family; deliberately does NOT fire on an honest refusal ("I can't enforce that", "it is NOT a rule")."""
    low = str(text or "").lower()
    return any(phrase in low for phrase in _ENFORCEMENT_CLAIMS)


def honest_refusal(missing: str | Sequence[str], why: str) -> str:
    """### THE HONEST FAILURE SENTENCE (ADR-010 §6). It NAMES what is missing, says plainly it is NOT a
    rule and will NOT stop anything, and says what would be needed. It is a better answer than a false
    yes, and the owner can act on it. It contains none of FORBIDDEN_ACKNOWLEDGEMENTS.

    `missing` may be a SINGLE field name (a str) or a list of them. ### A bare string is ONE field name,
    not a sequence of characters — iterating it into 'c, o, m, m, o, d, i, t, y' would tell the owner
    nothing, which is the exact failure the honest-reply surface exists to prevent."""
    names = [missing] if isinstance(missing, str) else [str(m) for m in missing]
    missing_names = ", ".join(n for n in names if n) or "the information this rule would need"
    return (
        f"I can't enforce that. I don't track {missing_names}, so this is NOT a rule and it will NOT stop "
        f"me on its own. I've kept it as a note. To make it a real, enforceable rule I'd need: {why}."
    )


def assert_reply_is_honest(text: str, active_rule_id: str | None = None) -> None:
    """### RAISES WHEN A REPLY CLAIMS ENFORCEMENT AND NO ACTIVE rule_id BACKS IT. Accepts the SAME claiming
    sentence when a real ACTIVE rule_id is supplied — a machine that refuses every reply is a different
    broken product. An empty-string rule id is not a rule id."""
    backed = bool(active_rule_id) and str(active_rule_id).strip() != ""
    if reply_claims_enforcement(text) and not backed:
        raise DishonestReply(
            "a reply claims a procedure was noted or that enforcement exists, but no ACTIVE rule_id backs "
            f"it (M-64, T16). The reply was: {text!r}. Either an enforceable rule compiled AND activated "
            "and its rule_id backs this reply, or the reply must be the honest refusal — there is no third."
        )


def _resolve_precedence_layer(layer: int | str) -> int:
    """Resolve a precedence layer to its 1-indexed position. Accepts an int position, or a layer NAME —
    the ladder's spaced form ('PRODUCT POLICY') or the underscore form ('PRODUCT_POLICY', 'STANDING_RULE',
    'BRAKE'). A name is matched against PRECEDENCE_LADDER after normalising underscores to spaces."""
    if isinstance(layer, bool):  # bool is an int subclass; a boolean is not a layer
        raise M12Error(f"a precedence layer is a position or a name, not {layer!r}.")
    if isinstance(layer, int):
        return layer
    key = str(layer).upper().replace("_", " ").strip()
    for i, name in enumerate((n.upper() for n in PRECEDENCE_LADDER), start=1):
        if key == name or key in name or name in key:
            return i
    raise M12Error(f"unknown precedence layer {layer!r}: not a position in PRECEDENCE_LADDER.")


def assert_within_precedence(target_layer: int | str) -> None:
    """### A RULE SITS AT LAYER 6 AND MAY OVERRIDE NOTHING ABOVE IT (ADR-010 §8). Refuses any attempt to
    place a rule at a layer above (higher precedence than) STANDING RULE — a rule never overrides a
    Constraint, a Permanent Product Truth, a Brake denial, the Product Policy ceiling or a Tenant Policy.
    A rule narrowing WITHIN its own layer (or below) is accepted. Takes a layer position or a layer name.
    M12 builds no second precedence engine; it only asserts its own position."""
    idx = _resolve_precedence_layer(target_layer)
    if idx < PRECEDENCE_LAYER:
        raise IllegalTransition(
            f"a standing rule is precedence layer {PRECEDENCE_LAYER} ({PRECEDENCE_LADDER[PRECEDENCE_LAYER-1]}); "
            f"it may not sit at layer {idx} ({PRECEDENCE_LADDER[idx-1]}), which is above it (ADR-010 §8). A "
            f"rule never overrides a Constraint, a Permanent Product Truth, a Brake denial, the Product "
            f"Policy ceiling or a Tenant Policy.")


# ------------------------------------------------------------------- the compiler input

@dataclass(frozen=True)
class CompilerInput:
    """### A TYPED FIELD INPUT TO THE RULE COMPILER. Carries `provenance_class` on every field; ### there
    is NO `confidence` field on this type, so a predicate cannot read a guess's certainty even by trying
    (ADR-010 §5.1 corollary). `modelled` says whether the field exists in the data model at all."""

    field: str
    provenance_class: str            # one of M7's six canonical classes (reused)
    modelled: bool = True
    # ### NO confidence FIELD. Structurally absent.


def compile_predicate_field(inp: CompilerInput) -> str:
    """### THE TYPED, NON-BLACKLIST REFUSAL. Returns the field name if it compiles; raises otherwise.
    Refuses: an unmodelled field, an invented provenance class, and a `MODEL_INFERRED` field (a guess, at
    ANY confidence — there is no confidence). Accepts SYSTEM_IMPORTED and OWNER_ASSERTED (and the other
    non-inferred canonical classes). The refusal is typed on `provenance_class`, not a string blacklist
    over field names."""
    if not isinstance(inp, CompilerInput):
        raise RuleWillNotCompile(
            "compile_predicate_field takes a typed CompilerInput carrying provenance_class and no "
            "confidence; a loose value is refused.")
    field = str(inp.field or "").strip()
    if not field:
        raise RuleWillNotCompile("a predicate clause names a field; a blank field is not one.",
                                 missing=("<unnamed field>",))
    if field == "confidence":
        raise RuleWillNotCompile(
            "a predicate may never reference `confidence`: it is structurally not an input (ADR-010 §5.1 "
            "corollary). At confidence 1.0 it still fails, because there is no confidence.", missing=(field,))
    if not inp.modelled:
        raise RuleWillNotCompile(
            f"field {field!r} is not a modelled field on the load: an unmodelled field cannot be compiled "
            f"into a predicate (M-49). This is a FEATURE REQUEST, surfaced by an honest refusal.",
            missing=(field,))
    pc = str(inp.provenance_class)
    if pc not in PROVENANCE_CLASSES:
        raise RuleWillNotCompile(
            f"field {field!r} declares provenance class {pc!r}, which is not one of M7's six canonical "
            f"classes {list(PROVENANCE_CLASSES)}: an invented provenance is not a non-inferred one.",
            missing=(field,))
    if pc == "MODEL_INFERRED":
        raise RuleWillNotCompile(
            f"field {field!r} is MODEL_INFERRED: a rule may never branch on a guess, at any confidence "
            f"(M-49, GR-8, ADR-010 §5.1). It FAILS TO COMPILE — the owner is told it is not a rule.",
            missing=(field,))
    return field


# ------------------------------------------------------------------- the candidate & compiled predicate

@dataclass(frozen=True)
class PredicateClause:
    """One deterministic clause: read `attr` of field `field` and compare with `op` to `literal`.
    `provenance_class`/`modelled` describe the FIELD (compile-time), not a runtime value."""

    field: str
    attr: str
    op: str
    literal: Any
    provenance_class: str = "SYSTEM_IMPORTED"
    modelled: bool = True

    def canonical(self) -> dict[str, Any]:
        return {"field": self.field, "attr": self.attr, "op": self.op, "literal": self.literal,
                "provenance_class": self.provenance_class, "modelled": self.modelled}


# The attributes a clause may read. `value` is the GATING accessor (raises on MODEL_INFERRED at eval);
# `provenance_class`/`evidence_condition` are deterministic metadata a rule is entitled to branch on
# (that is exactly "never bill without a POD" — branch on the POD's evidence, not a guess about it).
PREDICATE_ATTRS: frozenset[str] = frozenset({"value", "provenance_class", "evidence_condition"})
_OPERATORS: frozenset[str] = frozenset({"==", "!=", "in", "not_in", ">", ">=", "<", "<="})


@dataclass(frozen=True)
class CompiledPredicate:
    """A predicate that COMPILED — every referenced field modelled and non-inferred, every attr and op
    decidable at checkpoint time. Byte-identical reproducible: `to_json` sorts keys and no wall clock,
    randomness or unordered iteration enters compilation."""

    kind: str
    effect: str
    combine: str
    clauses: tuple[PredicateClause, ...]

    def canonical(self) -> dict[str, Any]:
        return {"status": "COMPILED", "kind": self.kind, "effect": self.effect, "combine": self.combine,
                "clauses": [c.canonical() for c in self.clauses]}

    def to_json(self) -> str:
        return json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"))


def _uncompiled_candidate_json(*, kind: str, effect: str, combine: str,
                               clauses: Sequence[Mapping[str, Any]]) -> str:
    """The candidate stored on a PROPOSED row: retained verbatim, marked UNCOMPILED. RU-2 reads it back."""
    payload = {"status": "UNCOMPILED", "kind": kind, "effect": effect, "combine": combine,
               "clauses": [dict(c) for c in clauses]}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def compile_candidate(candidate: Any, *, scope: str,
                      resolvable_scopes: Sequence[str] | None = None) -> CompiledPredicate:
    """### THE DETERMINISTIC COMPILE, WITH NO MODEL IN THE LOOP (ADR-010 §6). Exactly two outcomes: it
    compiles, or it raises `RuleWillNotCompile(missing=…)` and the owner is told. There is no third.

    Refuses, in order: a bare string (a prompt is not a rule); a malformed structure; an unknown effect;
    an unknown combine; an undecidable clause (bad attr or op); an unresolvable scope; and any field that
    is unmodelled or MODEL_INFERRED (collected into `missing`). Byte-identical over the same candidate."""
    if isinstance(candidate, str):
        raise RuleWillNotCompile(
            "a rule is a typed, structured candidate over modelled fields, not a sentence: a prompt string "
            "is not a rule (ADR-010 §6, lesson L-C). I cannot enforce a text box.", missing=("<prompt text>",))
    if not isinstance(candidate, Mapping):
        raise RuleWillNotCompile(
            f"a candidate is a structured mapping {{kind, effect, combine, clauses}}; got "
            f"{type(candidate).__name__}.")
    kind = str(candidate.get("kind", "")).strip()
    if kind not in RULE_KINDS:
        raise MalformedRule(f"kind {kind!r} is not one of the four canonical kinds {list(RULE_KINDS)}.")
    effect = str(candidate.get("effect", "")).strip()
    if effect not in RULE_EFFECTS:
        raise RuleWillNotCompile(
            f"rule effect {effect!r} is not one of {list(RULE_EFFECTS)}: an undecidable effect cannot "
            f"compile.", missing=("<effect>",))
    combine = str(candidate.get("combine", "AND")).upper()
    if combine not in ("AND", "OR"):
        raise RuleWillNotCompile(f"predicate combine must be AND or OR; got {combine!r}.")
    raw_clauses = candidate.get("clauses", [])
    if not isinstance(raw_clauses, (list, tuple)):
        raise RuleWillNotCompile("predicate clauses must be a list.")
    # ### THE SCOPE MUST RESOLVE. When a resolvable set is supplied, an unlisted scope fails to compile.
    scope_text = str(scope or "").strip()
    if not scope_text:
        raise RuleWillNotCompile("a rule governs a scope; a blank scope does not resolve.",
                                 missing=("<scope>",))
    if resolvable_scopes is not None and scope_text not in set(resolvable_scopes):
        raise RuleWillNotCompile(
            f"scope {scope_text!r} does not resolve against the known scope set: an unresolvable scope "
            f"cannot compile.", missing=(f"scope:{scope_text}",))

    missing: list[str] = []
    clauses: list[PredicateClause] = []
    for raw in raw_clauses:
        if not isinstance(raw, Mapping):
            raise RuleWillNotCompile(f"each predicate clause is a mapping; got {raw!r}.")
        fld = str(raw.get("field", "")).strip()
        attr = str(raw.get("attr", "value")).strip()
        op = str(raw.get("op", "==")).strip()
        literal = raw.get("literal")
        provenance = str(raw.get("provenance_class", "SYSTEM_IMPORTED"))
        modelled = bool(raw.get("modelled", True))
        # ### THE PREDICATE MUST BE DECIDABLE AT CHECKPOINT TIME — a known attr and a known operator.
        if attr not in PREDICATE_ATTRS:
            raise RuleWillNotCompile(
                f"clause attr must be one of {sorted(PREDICATE_ATTRS)}; got {attr!r}: an undecidable "
                f"predicate cannot compile.", missing=(fld or "<unnamed field>",))
        if op not in _OPERATORS:
            raise RuleWillNotCompile(
                f"clause operator {op!r} is not one of the fixed, deterministic set {sorted(_OPERATORS)}: "
                f"an undecidable predicate cannot compile.", missing=(fld or "<unnamed field>",))
        # ### EVERY REFERENCED FIELD MODELLED AND NON-INFERRED — collect what is missing, in order.
        try:
            compile_predicate_field(CompilerInput(field=fld, provenance_class=provenance, modelled=modelled))
        except RuleWillNotCompile as exc:
            for m in (exc.missing or (fld,)):
                if m not in missing:
                    missing.append(m)
            continue
        clauses.append(PredicateClause(field=fld, attr=attr, op=op, literal=literal,
                                       provenance_class=provenance, modelled=modelled))
    if missing:
        raise RuleWillNotCompile(
            f"the rule references field(s) that are unmodelled or MODEL_INFERRED: {missing}. It FAILS TO "
            f"COMPILE and the owner is told it is not a rule (RU-2f, M-49, GR-8).", missing=missing)
    return CompiledPredicate(kind=kind, effect=effect, combine=combine, clauses=tuple(clauses))


def generate_test_vectors(compiled: CompiledPredicate) -> list[dict[str, Any]]:
    """### EVERY COMPILED RULE SHIPS WITH GENERATED TEST VECTORS — "here are the loads this rule WOULD have
    acted on" (ADR-010 §6.2). Deterministic and byte-identical: derived from the compiled clauses in order,
    with NO wall clock and NO randomness. A rule whose consequences the owner cannot see is a rule they
    have not really approved, so RU-4 confirmation is refused until these are non-empty."""
    vectors: list[dict[str, Any]] = []
    for i, clause in enumerate(compiled.clauses):
        vectors.append({
            "vector_id": f"tv-{i + 1}",
            "field": clause.field,
            "attr": clause.attr,
            "would_act": True,
            "effect": compiled.effect,
            "reason": f"a load whose {clause.field}.{clause.attr} does not satisfy "
                      f"{clause.op} {clause.literal!r} would be {compiled.effect}",
        })
    if not vectors:
        vectors.append({
            "vector_id": "tv-1", "field": "<none>", "attr": "<none>", "would_act": False,
            "effect": compiled.effect,
            "reason": "a clause-free rule matches every load; the owner sees it acts on all in scope",
        })
    return vectors


# ------------------------------------------------------------------- evaluation (checkpoint step 6)

@dataclass(frozen=True)
class RuleDecision:
    """The output of evaluating a GATE_PRECONDITION/CONSTRAINT rule at checkpoint step 6 — a VALUE, never a
    new entity and NEVER a gate decision (checkpoint.py mints those). `decision` is one of the abstract
    effects; `reason` is always present. Byte-identical over the same inputs."""

    rule_id: str
    rule_version: int
    decision: str            # one of RULE_EFFECTS
    reason: str

    def canonical(self) -> dict[str, Any]:
        return {"rule_id": self.rule_id, "rule_version": self.rule_version, "decision": self.decision,
                "reason": self.reason}


def evaluate_rule(compiled: CompiledPredicate, facts: Mapping[str, ProvenancedFact], *,
                  rule_id: str = "", rule_version: int = 0) -> RuleDecision:
    """### EVALUATE A COMPILED RULE DETERMINISTICALLY, AND FAIL CLOSED. Reading `attr='value'` of a
    MODEL_INFERRED fact RAISES `RuleEngineUnavailable` (defense in depth behind the compile-time refusal),
    so even a compiled predicate handed a guess at runtime produces NO decision — never a PERMIT. There is
    no allow-on-error path. A DENYing rule's decision is DENY, which at step 6 yields no witness and no
    grant (entity §39) — but M12 mints neither anyway; the checkpoint reads this."""
    results: list[bool] = []
    for clause in compiled.clauses:
        fact = facts.get(clause.field)
        if fact is None:
            results.append(False)
            continue
        try:
            if clause.attr == "value":
                observed: Any = fact.value  # RAISES on MODEL_INFERRED (checkpoint.ProvenancedFact)
            elif clause.attr == "provenance_class":
                observed = fact.provenance.value
            else:
                observed = fact.evidence_condition.value
        except GateReadOfInferredFact as exc:
            raise RuleEngineUnavailable(
                f"rule {rule_id!r} could not be evaluated deterministically: {exc}. A guess cannot gate a "
                f"consequential action at any confidence (GR-8); no decision, no witness, no effect.") from exc
        results.append(_apply_op(clause.op, observed, clause.literal))
    satisfied = all(results) if compiled.combine == "AND" else (any(results) if results else True)
    # A CONSTRAINT/GATE_PRECONDITION acts (its effect) when its guarding clauses do NOT hold; PERMIT
    # otherwise. E.g. "never bill without a POD" DENIES when the POD conditions are not satisfied.
    if compiled.effect in ("DENY", "REQUIRE_HUMAN_APPROVAL"):
        decision = "PERMIT" if satisfied else compiled.effect
    else:
        decision = compiled.effect
    reason = (f"rule {rule_id!r} v{rule_version} ({compiled.kind}/{compiled.effect}): guarding clauses "
              f"{'hold' if satisfied else 'do NOT hold'} ⇒ {decision}.")
    return RuleDecision(rule_id=rule_id, rule_version=rule_version, decision=decision, reason=reason)


def _apply_op(op: str, observed: Any, literal: Any) -> bool:
    if op == "==":
        return observed == literal
    if op == "!=":
        return observed != literal
    if op == "in":
        return observed in literal if isinstance(literal, (list, tuple, set)) else False
    if op == "not_in":
        return observed not in literal if isinstance(literal, (list, tuple, set)) else False
    try:
        if op == ">":
            return observed > literal
        if op == ">=":
            return observed >= literal
        if op == "<":
            return observed < literal
        return observed <= literal
    except TypeError:
        return False


# ------------------------------------------------------------------------------- the state set

class RuleState(str, Enum):
    PROPOSED = "PROPOSED"
    COMPILED = "COMPILED"
    CONFIRMED = "CONFIRMED"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class Trigger(str, Enum):
    """The closed vocabulary of driving facts, named from §14's triggers and §33's "Events consumed". The
    five consumed facts (HumanConfirmed, HumanActivated, HumanRevoked, ConflictDetected, TimerFired) are
    READ, never minted; PROPOSE/COMPILE/NEW_VERSION_ACTIVATED are the machine's own decisions. `H` human,
    `S` system, `T` timer."""

    PROPOSE = "Propose"                             # RU-1 (H|S) — a model MAY propose the candidate text
    COMPILE = "Compile"                             # RU-2 / RU-2f (S) — deterministic compilation attempt
    CONFLICT_DETECTED = "ConflictDetected"          # RU-3 (S) — consumed fact
    HUMAN_CONFIRMED = "HumanConfirmed"              # RU-4 (H) — consumed fact
    HUMAN_ACTIVATED = "HumanActivated"             # RU-5 (H) — consumed fact
    NEW_VERSION_ACTIVATED = "NewVersionActivated"   # RU-6 (H) — driven by RU-5
    HUMAN_REVOKED = "HumanRevoked"                 # RU-7 (H|S) — consumed fact
    TIMER_FIRED = "TimerFired"                      # RU-8 (T) — consumed fact


class RowKind(str, Enum):
    PRODUCER = "PRODUCER"


# --------------------------------------------------------------------------- the transition table

@dataclass(frozen=True)
class TransitionRow:
    """One row of §14. Data, so `AC-MACH-000` can enumerate it and compare to the specification. NINE rows
    (### M12-AQ-3): the machine table governs, and it has RU-1, RU-2, RU-2f, RU-3, RU-4, RU-5, RU-6, RU-7,
    RU-8 — not the target spec's eight."""

    id: str
    from_states: tuple[RuleState, ...]
    to_state: RuleState | None       # None ⇒ the rule does not change state (RU-3 stays COMPILED, blocked)
    triggers: tuple[Trigger, ...]
    trigger_types: tuple[str, ...]
    kind: RowKind
    events: tuple[str, ...] = ()
    blocked: bool = False            # RU-3: fail closed, the rule STAYS COMPILED

    @property
    def independently_fireable(self) -> bool:
        return True


TRANSITIONS: tuple[TransitionRow, ...] = (
    TransitionRow(
        # RU-1 — — -> PROPOSED. ### A MODEL MAY PROPOSE THE STRUCTURED CANDIDATE TEXT. source_instruction
        # retained verbatim. A creation row (no from-state). H|S.
        id="RU-1", from_states=(), to_state=RuleState.PROPOSED,
        triggers=(Trigger.PROPOSE,), trigger_types=("H", "S"), kind=RowKind.PRODUCER,
        events=("RuleProposed",),
    ),
    TransitionRow(
        # RU-2 — PROPOSED -> COMPILED. ### DETERMINISTIC, NO MODEL. Every referenced field MODELLED and
        # NON-INFERRED (GR-8); predicate decidable; scope resolvable. Writes compiled_predicate + test_vectors.
        id="RU-2", from_states=(RuleState.PROPOSED,), to_state=RuleState.COMPILED,
        triggers=(Trigger.COMPILE,), trigger_types=("S",), kind=RowKind.PRODUCER,
        events=("RuleCompiled",),
    ),
    TransitionRow(
        # RU-2f — PROPOSED -> REJECTED. A referenced field is unmodelled or MODEL_INFERRED ⇒
        # RuleNotEnforceable{missing} and the owner is TOLD it is not a rule.
        id="RU-2f", from_states=(RuleState.PROPOSED,), to_state=RuleState.REJECTED,
        triggers=(Trigger.COMPILE,), trigger_types=("S",), kind=RowKind.PRODUCER,
        events=("RuleNotEnforceable",),
    ),
    TransitionRow(
        # RU-3 — COMPILED -> (blocked). Conflicts with an ACTIVE rule ⇒ M7 RULE_VS_RULE Conflict, fail
        # closed, never auto-merge (GR-15). ### THE RULE STAYS COMPILED. M12 mints no F7 event of its own;
        # it CALLS M7's landed raise entry point, and M7 mints.
        id="RU-3", from_states=(RuleState.COMPILED,), to_state=None,
        triggers=(Trigger.CONFLICT_DETECTED,), trigger_types=("S",), kind=RowKind.PRODUCER,
        events=(), blocked=True,
    ),
    TransitionRow(
        # RU-4 — COMPILED -> CONFIRMED. ### THE OWNER IS SHOWN THE COMPILED RULE AND ITS GENERATED TEST
        # VECTORS. Does NOT activate.
        id="RU-4", from_states=(RuleState.COMPILED,), to_state=RuleState.CONFIRMED,
        triggers=(Trigger.HUMAN_CONFIRMED,), trigger_types=("H",), kind=RowKind.PRODUCER,
        events=("RuleConfirmed",),
    ),
    TransitionRow(
        # RU-5 — CONFIRMED -> ACTIVE. ### AN AUTHENTICATED HUMAN ACTIVATES — NEVER A MODEL, NEVER AUTOMATION.
        # Writes activated_by, rule_version. RuleActivated is human_only.
        id="RU-5", from_states=(RuleState.CONFIRMED,), to_state=RuleState.ACTIVE,
        triggers=(Trigger.HUMAN_ACTIVATED,), trigger_types=("H",), kind=RowKind.PRODUCER,
        events=("RuleActivated",),
    ),
    TransitionRow(
        # RU-6 — ACTIVE -> SUPERSEDED. A new version; the old version is RETAINED. Writes superseded_by.
        id="RU-6", from_states=(RuleState.ACTIVE,), to_state=RuleState.SUPERSEDED,
        triggers=(Trigger.NEW_VERSION_ACTIVATED,), trigger_types=("H",), kind=RowKind.PRODUCER,
        events=("RuleSuperseded",),
    ),
    TransitionRow(
        # RU-7 — ACTIVE -> REVOKED. Immediate if it NARROWS; the Policy Owner if it BROADENS. Writes
        # revoked_reason, direction.
        id="RU-7", from_states=(RuleState.ACTIVE,), to_state=RuleState.REVOKED,
        triggers=(Trigger.HUMAN_REVOKED,), trigger_types=("H", "S"), kind=RowKind.PRODUCER,
        events=("RuleRevoked",),
    ),
    TransitionRow(
        # RU-8 — ACTIVE -> EXPIRED. Narrowing-rule TTL. ### ITS EXPIRY BROADENS, SO A HUMAN IS REQUIRED AT
        # EXPIRY — TimerFired cannot complete the broadening; RU-8 raises an M9 exception seam.
        id="RU-8", from_states=(RuleState.ACTIVE,), to_state=RuleState.EXPIRED,
        triggers=(Trigger.TIMER_FIRED,), trigger_types=("T",), kind=RowKind.PRODUCER,
        events=("RuleExpired",),
    ),
)

TRANSITIONS_BY_ID: Mapping[str, TransitionRow] = {row.id: row for row in TRANSITIONS}

# §32 "Events emitted", derived from the table: the eight F12 contracts. RU-3 mints nothing.
PRODUCED_CONTRACTS = frozenset(ev for row in TRANSITIONS for ev in row.events)

# ### THE PUBLIC STATE SETS ARE STRINGS (like RULE_STATES), so a caller reading them sees canonical state
# names, not enum reprs. The machine compares against the private enum sets below.
TERMINAL_STATES: frozenset[str] = frozenset(TERMINAL_RULE_STATES)
NON_TERMINAL_STATES: frozenset[str] = frozenset(NON_TERMINAL_RULE_STATES)
_TERMINAL_STATE_ENUMS: frozenset[RuleState] = frozenset(RuleState(s) for s in TERMINAL_RULE_STATES)


def legal_transitions(state: RuleState | None, trigger: Trigger) -> tuple[TransitionRow, ...]:
    """Every row whose (from-state, trigger) matches. Empty ⇒ GR-1 refuses it. A None state matches a
    creation row (RU-1)."""
    return tuple(
        row for row in TRANSITIONS
        if trigger in row.triggers and (
            (state is None and not row.from_states) or (state is not None and state in row.from_states)))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _direction_for_effect(effect: str) -> str:
    """A narrowing effect (a restriction) is 'narrow'; anything else 'broaden'. Computed, never supplied,
    so a caller cannot claim 'narrow' to smuggle an expiry onto a broadening rule."""
    return "narrow" if effect in _NARROWING_EFFECTS else "broaden"


def scope_form_of(scope: str) -> str:
    """### THE SCOPE-FORM PREFIX (### M12-AQ-4). A rule's `scope` is a form-prefixed string
    `<scope_form>:<detail>`; the form is the part before the first ':'. This is the single-admitting
    discriminator, and it is what the one-active partial index keys off — so a rule constructed by any
    means (the machine, a raw insert, an oracle) carries its form in the value the index reads."""
    return str(scope).split(":", 1)[0]


def is_single_admitting(scope: str) -> bool:
    """True iff this scope's FORM PREFIX admits exactly ONE ACTIVE rule per (tenant, scope, kind) — the
    ### M12-AQ-4 answer. Everything else admits multiple, and conflict detection covers a genuine clash."""
    return scope_form_of(scope) in P6RU_SINGLE_ACTIVE_SCOPES


# ------------------------------------------------------------------------------- the raised seam records

@dataclass(frozen=True)
class RaisedConflict:
    """### THE M7 RULE_VS_RULE CONFLICT RU-3 RAISED THROUGH M7's LANDED ENTRY POINT (### M12-AQ-2 / §3.7).
    Two genuinely conflicting ACTIVE rules fail closed: RU-3 CALLS `M7Machine.raise_conflict`, which mints
    the F7 rule-vs-rule event and freezes the field; M12 mints nothing, defines no conflict vocabulary and
    writes no `conflicts` row directly, and Neyma picks no winner. This record is what M7 returned."""

    conflict_id: str
    kind: str
    entity_ref: str
    field: str
    owner_id: str


@dataclass(frozen=True)
class RaisedException:
    """### THE M9 HUMAN-CONFIRMATION EXCEPTION RU-8 / THE OVERRIDE-RATE SEAM RAISED THROUGH M9's LANDED
    ENTRY POINT (### M12-AQ-6 / P6-D73). RU-8's expiry BROADENS, so it CALLS `M9Machine.raise_exception
    (source_kind="rule")` — authority is NOT restored by the expiry; this is the human's cue. M12 adds no
    FK, no mirror column and no migration to M9. This record is what M9 returned."""

    exception_id: str
    source_kind: str
    source_ref: str
    owner_id: str
    type: str


# ------------------------------------------------------------------------------------ the row

@dataclass(frozen=True)
class RuleRecord:
    """One `rules` row, as the machine reads it."""

    tenant: str
    rule_id: str
    rule_version: int
    scope: str
    kind: str
    compiled_predicate: str
    test_vectors: str
    state: RuleState
    version: int
    source_instruction: str
    authored_by: str
    activated_by: str | None
    expires_at: str | None
    change_direction: str
    superseded_by: str | None
    revoked_reason: str | None
    revoked_direction: str | None
    conflict_id: str | None
    created_at: str

    @property
    def is_terminal(self) -> bool:
        return self.state in _TERMINAL_STATE_ENUMS

    @property
    def test_vector_list(self) -> list[Any]:
        try:
            loaded = json.loads(self.test_vectors)
        except (ValueError, TypeError):
            return []
        return list(loaded) if isinstance(loaded, list) else []


@dataclass(frozen=True)
class TransitionResult:
    transition_id: str
    rule: RuleRecord | None
    from_state: RuleState | None
    to_state: RuleState | None
    event_ids: tuple[str, ...] = ()
    event_names: tuple[str, ...] = ()
    event_producer: str | None = None
    missing: tuple[str, ...] = ()
    reply: str | None = None                          # the honest refusal sentence (RU-2f)
    conflict: RaisedConflict | None = None            # the M7 conflict RU-3 raised
    escalation: RaisedException | None = None         # the M9 exception RU-8 / override raised


@dataclass(frozen=True)
class ReconstructedRule:
    """A full-history fold of one rule's F12 event stream — sandboxed, zero authority (GR-11, ER-2, K-3).
    ### REPLAY RE-ACTIVATES NOTHING, MINTS NO WITNESS, CLAIMS NO GRANT AND PRODUCES NO EXTERNAL EFFECT."""

    rule_id: str
    state: RuleState | None
    activations_performed: int = 0
    witnesses_minted: int = 0
    grants_claimed: int = 0
    external_effects: int = 0
    authority_minted: int = 0


@dataclass(frozen=True)
class ConsumedTransition:
    consume: ConsumeResult
    transition: TransitionResult | None = None
    refusal: str | None = None

    @property
    def moved(self) -> bool:
        return self.transition is not None


# --------------------------------------------------------------------------------- the machine

class M12Machine:
    """M12, on an existing connection, bound to ONE tenant. Bound at construction so a caller cannot
    re-point it at another tenant and put [C-1] in its own hands."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        tenant: str,
        clock: Callable[[], datetime] | None = None,
        producer_component: str = PRODUCER_COMPONENT,
    ) -> None:
        if getattr(conn, "row_factory", None) is not sqlite3.Row:
            raise M12Error("M12Machine reads columns by name and requires `row_factory = sqlite3.Row`.")
        self._conn = conn
        self._tenant = require_tenant(tenant, context="M12Machine")
        self._clock = clock or _utc_now
        self._component = producer_component

    @property
    def tenant(self) -> str:
        return self._tenant

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    # --- reads -----------------------------------------------------------------------------------

    def get(self, rule_id: str) -> RuleRecord | None:
        row = self._conn.execute(
            "SELECT * FROM rules WHERE tenant = ? AND rule_id = ?",
            (self._tenant, rule_id)).fetchone()
        return _row_to_rule(row) if row is not None else None

    def require(self, rule_id: str) -> RuleRecord:
        found = self.get(rule_id)
        if found is None:
            raise UnknownRule(
                f"no rule {rule_id!r} for tenant {self._tenant!r}. This machine does not look outside its "
                f"tenant to find out whether it exists elsewhere ([C-1]).")
        return found

    def active_for_scope(self, scope: str, kind: str) -> list[RuleRecord]:
        """The ACTIVE rules for a (scope, kind). At most one where the scope_form admits one; possibly
        several otherwise (and conflict detection handles a genuine clash)."""
        rows = self._conn.execute(
            "SELECT * FROM rules WHERE tenant = ? AND scope = ? AND kind = ? AND state = 'ACTIVE' "
            "ORDER BY rule_version",
            (self._tenant, scope, kind)).fetchall()
        return [_row_to_rule(r) for r in rows]

    def current_rule_version(self) -> int:
        """The tenant's current `rule_version` — the MAX across ALL scopes (### M12-AQ-4b: the version
        namespace is the TENANT). Monotonic, never reused."""
        row = self._conn.execute(
            "SELECT COALESCE(MAX(rule_version), 0) FROM rules WHERE tenant = ?",
            (self._tenant,)).fetchone()
        return int(row[0])

    def policy_owner(self) -> str | None:
        """The tenant's single named Policy Owner, read off the M1-landed `tenant_humans` record — the
        human RU-7's broadening revocation and RU-8's expiry escalation route to (entity §5/§25/§26)."""
        rows = self._conn.execute(
            "SELECT human_id FROM tenant_humans WHERE tenant = ? AND authority_role = 'POLICY_OWNER' "
            "AND state = 'ACTIVE' ORDER BY human_id",
            (self._tenant,)).fetchall()
        return rows[0]["human_id"] if len(rows) == 1 else None

    # --- RU-1: propose a candidate ----------------------------------------------------------------

    def propose(
        self,
        *,
        scope: str,
        kind: str,
        effect: str,
        source_instruction: str,
        authored_by: str,
        clauses: Sequence[Mapping[str, Any]] = (),
        combine: str = "AND",
        expires_at: str | None = None,
        rule_id: str | None = None,
        actor_kind: str = "human",
        actor_id: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """RU-1 — — -> PROPOSED. ### A MODEL MAY PROPOSE THE STRUCTURED CANDIDATE TEXT. `actor_kind` may be
        `human` or `model` (Neyma's owner or Neyma's model on the owner's behalf); a counterparty, inbound
        content, automation or a timer may NOT author — a proposal from those is refused. `authored_by`
        must be a recorded ACTIVE human of this tenant (an offboarded or cross-tenant human fails closed).
        `scope` is a form-prefixed string `<scope_form>:<detail>` (### M12-AQ-4); the form prefix must be
        one of P6RU_SCOPE_FORMS and drives the one-active partial index. ### A PROPOSAL IS NOT AN
        ENFORCEABLE RULE: the state is PROPOSED, source_instruction is retained verbatim, and RuleProposed
        ¬proves the rule is enforceable. The candidate is stored UNCOMPILED; RU-2 compiles it
        deterministically."""
        proposer = str(actor_kind).strip().lower()
        if proposer not in ("human", "model"):
            raise IllegalTransition(
                f"RU-1 authors a rule candidate for an accountable human. actor_kind={actor_kind!r}: a "
                f"counterparty, inbound content, automation, a retry handler and a timer may NOT author a "
                f"rule (entity §35, ER-9). A model MAY propose TEXT; a counterparty instruction is not a rule.")
        author = self._require_named_human(authored_by, "the rule author")
        if kind not in RULE_KINDS:
            raise MalformedRule(f"kind {kind!r} is not one of {list(RULE_KINDS)} (entity §10).")
        scope_text = _require_text(scope, "scope")
        if scope_form_of(scope_text) not in P6RU_SCOPE_FORMS:
            raise MalformedRule(
                f"scope {scope_text!r} must be a form-prefixed string <scope_form>:<detail> whose form is "
                f"one of {list(P6RU_SCOPE_FORMS)} (### M12-AQ-4).")
        if effect not in RULE_EFFECTS:
            raise MalformedRule(f"effect {effect!r} is not one of {list(RULE_EFFECTS)}.")
        instruction = _require_text(source_instruction, "source_instruction")
        direction = _direction_for_effect(effect)
        if expires_at is not None and direction != "narrow":
            raise GuardNotSatisfied(
                "only a NARROWING rule may carry an expires_at (entity §26, ADR-010 §4.1): a broadening "
                "rule that carries an expiry is automatic broadening with a delay — the clock may take "
                "authority away, never give it.")
        candidate_json = _uncompiled_candidate_json(
            kind=kind, effect=effect, combine=str(combine).upper(), clauses=clauses)
        rid = rule_id or f"rule-{uuid.uuid4().hex[:16]}"
        rv = self.current_rule_version() + 1
        now = format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "INSERT INTO rules (tenant, rule_id, rule_version, scope, kind, "
                "compiled_predicate, test_vectors, state, version, source_instruction, authored_by, "
                "activated_by, expires_at, change_direction, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (self._tenant, rid, rv, scope_text, kind, candidate_json, "[]",
                 RuleState.PROPOSED.value, 1, instruction, author, None, expires_at, direction, now, now))
            created = self.require(rid)
            envelope = self._rule_envelope(
                event_name="RuleProposed", transition_id="RU-1", rule=created,
                actor_type=("model" if proposer == "model" else "human"), actor_id=actor_id or author,
                payload={"source_instruction": instruction, "scope": scope_text, "kind": kind},
                correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                event_id=event_id, now=now)
            self._outbox().emit(envelope)
            conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        return TransitionResult(
            transition_id="RU-1", rule=created, from_state=None, to_state=RuleState.PROPOSED,
            event_ids=(envelope.event_id,), event_names=("RuleProposed",), event_producer="RU-1")

    # --- RU-2 / RU-2f: deterministic compilation --------------------------------------------------

    def compile(
        self,
        rule_id: str,
        *,
        resolvable_scopes: Sequence[str] | None = None,
        expected: RuleRecord | None = None,
        actor_id: str = "compiler",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """RU-2 / RU-2f — PROPOSED -> COMPILED or REJECTED. ### DETERMINISTIC, NO MODEL. Reads the stored
        candidate and validates it: every referenced field MODELLED and NON-INFERRED (GR-8), the predicate
        decidable at checkpoint time, the scope resolvable. On success writes compiled_predicate AND
        generated test_vectors and emits RuleCompiled{rule_id, compiled_predicate, test_vectors}. On
        failure it does NOT install anything: state -> REJECTED, RuleNotEnforceable{missing}, and the
        honest refusal reply is returned — the instruction becomes organizational memory, and the owner is
        TOLD it is not a rule. There is no third outcome."""
        comp = expected or self.require(rule_id)
        self._require_legal(comp, Trigger.COMPILE, actor_id=actor_id)
        candidate = _parse_json_obj(comp.compiled_predicate)
        try:
            compiled = compile_candidate(
                {"kind": comp.kind, "effect": candidate.get("effect"),
                 "combine": candidate.get("combine", "AND"), "clauses": candidate.get("clauses", [])},
                scope=comp.scope, resolvable_scopes=resolvable_scopes)
        except RuleWillNotCompile as exc:
            missing = exc.missing or ("<unspecified>",)
            reply = honest_refusal(
                missing, why=f"each of {list(missing)} to be a modelled, non-inferred field I can check "
                             f"deterministically at decision time")
            result = self._advance(
                comp, "RU-2f", RuleState.REJECTED, event_name="RuleNotEnforceable",
                payload={"missing": list(missing)}, actor_type="system", actor_id=actor_id, writes="",
                write_args=(), correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                event_id=event_id)
            return TransitionResult(
                transition_id=result.transition_id, rule=result.rule, from_state=result.from_state,
                to_state=result.to_state, event_ids=result.event_ids, event_names=result.event_names,
                event_producer=result.event_producer, missing=tuple(missing), reply=reply)
        vectors = generate_test_vectors(compiled)
        return self._advance(
            comp, "RU-2", RuleState.COMPILED, event_name="RuleCompiled",
            payload={"rule_id": comp.rule_id, "compiled_predicate": compiled.canonical(),
                     "test_vectors": vectors},
            actor_type="system", actor_id=actor_id,
            writes="compiled_predicate = ?, test_vectors = ?",
            write_args=(compiled.to_json(), json.dumps(vectors, sort_keys=True, separators=(",", ":"))),
            correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id, event_id=event_id)

    # --- RU-3: fail closed into an M7 conflict ----------------------------------------------------

    def detect_conflict(
        self,
        rule_id: str,
        *,
        against_rule_id: str,
        owner_id: str | None = None,
        narrower: bool = False,
        expected: RuleRecord | None = None,
    ) -> TransitionResult:
        """RU-3 — COMPILED -> (blocked). ### TWO GENUINELY CONFLICTING RULES FAIL CLOSED. If the COMPILED
        rule conflicts with an ACTIVE rule, this CALLS M7's landed `raise_conflict` (RULE_VS_RULE), which
        mints the F7 rule-vs-rule event and freezes the field, then records the conflict id on this rule so
        it STAYS COMPILED and blocked. ### M12 mints NOTHING itself, defines no conflict vocabulary, writes
        no `conflicts` row directly, and Neyma NEVER picks a winner. Where one rule is strictly NARROWER
        than another that is PRECEDENCE, not a conflict (the narrower scope wins) — `narrower=True` raises
        no conflict."""
        comp = expected or self.require(rule_id)
        self._require_legal(comp, Trigger.CONFLICT_DETECTED, actor_id="reconciliation")
        if narrower:
            # ### THE NARROWER SCOPE WINS, AND THAT IS NOT A CONFLICT (ADR-010 §8). Precedence applies;
            # nothing is raised, nothing is blocked, the rule stays COMPILED on its own merits.
            return TransitionResult(
                transition_id="RU-3", rule=comp, from_state=RuleState.COMPILED,
                to_state=RuleState.COMPILED, event_names=(), event_producer="RU-3")
        other = self.require(against_rule_id)
        owner = owner_id or self.policy_owner()
        if owner is None:
            raise GuardNotSatisfied(
                "a RULE_VS_RULE conflict is owned by a named human; this tenant has no single ACTIVE "
                "Policy Owner and none was supplied. A conflict without an owner cannot be raised.")
        field = f"rule:{comp.scope}:{comp.kind}"
        # ### CALL M7'S LANDED ENTRY POINT — M7 mints, M12 does not.
        m7_result = M7Machine(self._conn, tenant=self._tenant, clock=self._clock).raise_conflict(
            kind=RULE_VS_RULE, entity_ref=comp.scope, field=field,
            parties=[
                Party(party_ref=comp.rule_id, party_kind="rule", provenance_class="OWNER_ASSERTED",
                      stated_value=comp.rule_id),
                Party(party_ref=other.rule_id, party_kind="rule", provenance_class="OWNER_ASSERTED",
                      stated_value=other.rule_id),
            ],
            owner_id=owner, actor_id="policy_engine")
        conflict_id = m7_result.conflict.conflict_id
        # Record the conflict on this rule so it stays COMPILED and blocked (the FK is now satisfiable).
        self.block_on_conflict(rule_id, conflict_id=conflict_id, expected=comp)
        raised = RaisedConflict(conflict_id=conflict_id, kind=RULE_VS_RULE, entity_ref=comp.scope,
                                field=field, owner_id=owner)
        return TransitionResult(
            transition_id="RU-3", rule=self.require(comp.rule_id), from_state=RuleState.COMPILED,
            to_state=RuleState.COMPILED, event_names=(), event_producer="RU-3", conflict=raised)

    def block_on_conflict(self, rule_id: str, *, conflict_id: str,
                          expected: RuleRecord | None = None) -> TransitionResult:
        """Record the M7 conflict id on a COMPILED rule AFTER the caller drove M7's raise_conflict (so the
        FK into `conflicts` is satisfied). ### THE RULE STAYS COMPILED AND BLOCKED; it never reaches ACTIVE
        while the conflict stands. No state change; version advances for OCC."""
        comp = expected or self.require(rule_id)
        if comp.state is not RuleState.COMPILED:
            raise GuardNotSatisfied(
                f"only a COMPILED rule is blocked on a conflict; {comp.rule_id!r} is {comp.state.value}.")
        now = format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            cur = conn.execute(
                "UPDATE rules SET conflict_id = ?, version = version + 1, updated_at = ? "
                "WHERE tenant = ? AND rule_id = ? AND state = 'COMPILED' AND version = ?",
                (conflict_id, now, self._tenant, comp.rule_id, comp.version))
            if cur.rowcount != 1:
                raise StateConflict(
                    f"block_on_conflict matched {cur.rowcount} rows for {comp.rule_id!r}: it moved under us.")
            conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        after = self.require(comp.rule_id)
        return TransitionResult(
            transition_id="RU-3", rule=after, from_state=RuleState.COMPILED, to_state=RuleState.COMPILED,
            event_producer="RU-3")

    # --- RU-4: the owner confirms -----------------------------------------------------------------

    def confirm(
        self,
        rule_id: str,
        *,
        confirmed_by: str,
        expected: RuleRecord | None = None,
        actor_kind: str = "human",
        actor_id: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """RU-4 — COMPILED -> CONFIRMED. ### THE OWNER IS SHOWN THE COMPILED RULE AND ITS GENERATED TEST
        VECTORS. Confirmation without test vectors is REFUSED — a rule whose consequences the owner cannot
        see is a rule they have not really approved. RuleConfirmed does NOT activate (RU-5 and a human do)."""
        comp = expected or self.require(rule_id)
        self._require_legal(comp, Trigger.HUMAN_CONFIRMED, actor_id=actor_id or confirmed_by)
        if str(actor_kind).strip().lower() != "human":
            self._refuse_illegal(comp.rule_id, Trigger.HUMAN_CONFIRMED,
                                 actor_id=actor_id or str(actor_kind), reason="a model confirmed a rule")
            raise IllegalTransition(
                f"RU-4 is a human confirmation; actor_kind={actor_kind!r}. A model never confirms a rule "
                f"(ADR-010 §6; entity §35).")
        self._require_named_human(confirmed_by, "the confirming human")
        if not comp.test_vector_list:
            raise GuardNotSatisfied(
                "RU-4 requires the owner to have SEEN the generated test vectors; this rule has none "
                "(entity §42, ADR-010 §6.2). Confirmation without test vectors is refused.")
        return self._advance(
            comp, "RU-4", RuleState.CONFIRMED, event_name="RuleConfirmed", payload={},
            actor_type="human", actor_id=actor_id or confirmed_by, writes="", write_args=(),
            correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id, event_id=event_id)

    # --- RU-5: an authenticated human activates ---------------------------------------------------

    def activate(
        self,
        rule_id: str,
        *,
        activated_by: str,
        expected: RuleRecord | None = None,
        actor_kind: str = "human",
        actor_id: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """RU-5 — CONFIRMED -> ACTIVE. ### AN AUTHENTICATED HUMAN ACTIVATES — NEVER A MODEL, NEVER
        AUTOMATION, NEVER A RETRY HANDLER, NEVER A TIMER, NEVER A COUNTERPARTY. Any non-human attempt emits
        the already-registered F14 `UnauthorizedPolicyActivationAttempted` and raises. `activated_by` must
        be a recorded ACTIVE human of this tenant. ### RE-ACTIVATING AN ALREADY-ACTIVE VERSION IS A NO-OP
        (GR-4): no second RuleActivated, no rule_version bump. Where the scope_form admits one ACTIVE rule,
        activation SUPERSEDES the prior ACTIVE rule for (scope, kind) in the SAME transaction (RU-6)."""
        comp = expected or self.require(rule_id)
        # ### IDEMPOTENT NO-OP: re-activating an already-ACTIVE version mints nothing and bumps nothing.
        if comp.state is RuleState.ACTIVE:
            return TransitionResult(
                transition_id="RU-5", rule=comp, from_state=RuleState.ACTIVE, to_state=RuleState.ACTIVE,
                event_producer="RU-5")
        self._require_legal(comp, Trigger.HUMAN_ACTIVATED, actor_id=actor_id or activated_by)
        if str(actor_kind).strip().lower() != "human":
            self._record_unauthorized_activation(
                comp.rule_id, actor_type=self._actor_type(actor_kind), actor_id=actor_id or str(actor_kind))
            raise IllegalTransition(
                f"RU-5 activation requires an AUTHENTICATED human (ER-11, machine §15/GR-7). "
                f"actor_kind={actor_kind!r} — a model, automation, a retry handler, a timer and a "
                f"counterparty each activate NOTHING. Recorded as UnauthorizedPolicyActivationAttempted (F14).")
        activator = self._require_named_human(activated_by, "the activating human")
        now = format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            if is_single_admitting(comp.scope):
                self._supersede_active_in_scope(comp.scope, comp.kind, by=comp.rule_id, now=now)
            cur = conn.execute(
                "UPDATE rules SET state = 'ACTIVE', version = version + 1, updated_at = ?, activated_by = ? "
                "WHERE tenant = ? AND rule_id = ? AND state = 'CONFIRMED' AND version = ?",
                (now, activator, self._tenant, comp.rule_id, comp.version))
            if cur.rowcount != 1:
                raise StateConflict(
                    f"RU-5 matched {cur.rowcount} rows for {comp.rule_id!r}: it moved under us (GR-3), or "
                    f"another activation won the one-active-per-scope race. Reload.")
            after = self.require(comp.rule_id)
            act = self._rule_envelope(
                event_name="RuleActivated", transition_id="RU-5", rule=after, actor_type="human",
                actor_id=actor_id or activator,
                payload={"rule_id": after.rule_id, "rule_version": after.rule_version,
                         "activated_by": activator},
                correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                event_id=event_id, now=now)
            self._outbox().emit(act)
            conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        return TransitionResult(
            transition_id="RU-5", rule=after, from_state=RuleState.CONFIRMED, to_state=RuleState.ACTIVE,
            event_ids=(act.event_id,), event_names=("RuleActivated",), event_producer="RU-5")

    # --- RU-6: supersede --------------------------------------------------------------------------

    def supersede(self, rule_id: str, *, superseded_by: str, expected: RuleRecord | None = None,
                  actor_id: str = "policy_engine", correlation_id: str | None = None,
                  causation_id: str | None = None, trace_id: str | None = None,
                  event_id: str | None = None) -> TransitionResult:
        """RU-6 — ACTIVE -> SUPERSEDED. A new version supersedes; ### THE OLD VERSION IS RETAINED, because
        effects were judged under it and it must still explain them under ITS OWN rule_version. Writes
        superseded_by. History is never edited in place."""
        comp = expected or self.require(rule_id)
        self._require_legal(comp, Trigger.NEW_VERSION_ACTIVATED, actor_id=actor_id)
        successor = _require_text(superseded_by, "superseded_by")
        return self._advance(
            comp, "RU-6", RuleState.SUPERSEDED, event_name="RuleSuperseded",
            payload={"superseded_by": successor}, actor_type="human", actor_id=actor_id,
            writes="superseded_by = ?", write_args=(successor,), correlation_id=correlation_id,
            causation_id=causation_id, trace_id=trace_id, event_id=event_id)

    # --- RU-7: revoke -----------------------------------------------------------------------------

    def revoke(self, rule_id: str, *, revoked_reason: str, direction: str,
               expected: RuleRecord | None = None, actor_id: str = "operator", actor_kind: str = "human",
               correlation_id: str | None = None, causation_id: str | None = None,
               trace_id: str | None = None, event_id: str | None = None) -> TransitionResult:
        """RU-7 — ACTIVE -> REVOKED. ### IMMEDIATE IF IT NARROWS; THE POLICY OWNER IF IT BROADENS (ER-12).
        A narrowing revocation may be automation. A BROADENING revocation — removing a tightening —
        requires the Policy Owner, an authenticated human; automation attempting it is refused and
        recorded. Emits RuleRevoked{revoked_reason, direction}."""
        comp = expected or self.require(rule_id)
        self._require_legal(comp, Trigger.HUMAN_REVOKED, actor_id=actor_id)
        dir_norm = str(direction or "").strip().lower()
        if dir_norm not in REVOKE_DIRECTIONS:
            raise GuardNotSatisfied(
                f"RuleRevoked carries a required direction ∈ {list(REVOKE_DIRECTIONS)} (ER-12); got "
                f"{direction!r}. It is an enumerated field, not a comment.")
        reason = _require_text(revoked_reason, "revoked_reason")
        if dir_norm == "broaden":
            if str(actor_kind).strip().lower() != "human":
                self._refuse_illegal(comp.rule_id, Trigger.HUMAN_REVOKED, actor_id=actor_id,
                                     reason="a broadening revocation by automation")
                raise IllegalTransition(
                    "a BROADENING revocation requires the Policy Owner, an authenticated human (ER-12): "
                    "automation may only ever move authority in the SAFE direction. A narrowing revocation "
                    "may be automated; broadening may not.")
            self._require_named_human(actor_id, "the revoking human")
        return self._advance(
            comp, "RU-7", RuleState.REVOKED, event_name="RuleRevoked",
            payload={"revoked_reason": reason, "direction": dir_norm},
            actor_type=self._actor_type(actor_kind), actor_id=actor_id,
            writes="revoked_reason = ?, revoked_direction = ?", write_args=(reason, dir_norm),
            correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id, event_id=event_id)

    # --- RU-8: the narrowing rule's TTL fires -----------------------------------------------------

    def expire(self, rule_id: str, *, owner_id: str | None = None, expected: RuleRecord | None = None,
               actor_id: str = "timer", correlation_id: str | None = None, causation_id: str | None = None,
               trace_id: str | None = None, event_id: str | None = None) -> TransitionResult:
        """RU-8 — ACTIVE -> EXPIRED, on a narrowing rule's TTL (trigger T). ### ITS EXPIRY BROADENS, SO IT
        REQUIRES A HUMAN AT EXPIRY. The timer does NOT restore authority: RU-8 marks the rule EXPIRED,
        emits RuleExpired{rule_id, rule_version, expired_at}, and CALLS M9's landed `raise_exception
        (source_kind="rule")` for the human-confirmation Exception. ### M12 EDITS NO PART OF M9. The clock
        may take authority away; the clock may never give it. A timer firing on a non-narrowing rule is
        refused."""
        comp = expected or self.require(rule_id)
        self._require_legal(comp, Trigger.TIMER_FIRED, actor_id=actor_id)
        if comp.change_direction != "narrow" or comp.expires_at is None:
            raise GuardNotSatisfied(
                f"RU-8 fires only on a NARROWING rule carrying an expiry (entity §26): rule {comp.rule_id!r} "
                f"is {comp.change_direction!r} with expires_at={comp.expires_at!r}. A broadening rule cannot "
                f"carry an expiry, so its clock can never broaden authority.")
        owner = owner_id or self.policy_owner()
        if owner is None:
            raise GuardNotSatisfied(
                "RU-8's expiry BROADENS and requires a human at expiry, so its owed Exception needs a named "
                "owner; this tenant has no single ACTIVE Policy Owner and none was supplied. The clock may "
                "take authority away, never give it — and it may not proceed unowned.")
        result = self._advance(
            comp, "RU-8", RuleState.EXPIRED, event_name="RuleExpired",
            payload={"rule_id": comp.rule_id, "rule_version": comp.rule_version,
                     "expired_at": format_instant(self._clock())},
            actor_type="system", actor_id=actor_id, writes="", write_args=(),
            correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id, event_id=event_id)
        raised = self._raise_rule_exception(
            source_ref=comp.rule_id, owner_id=owner, type_="rule_expiry_requires_human_confirmation",
            summary=(f"narrowing rule {comp.rule_id!r} (scope {comp.scope!r}, v{comp.rule_version}) expired; "
                     f"its expiry BROADENS authority and requires a human to confirm before any widening "
                     f"takes effect (ADR-010 §4.1). Authority has NOT been restored."))
        return TransitionResult(
            transition_id=result.transition_id, rule=result.rule, from_state=result.from_state,
            to_state=result.to_state, event_ids=result.event_ids, event_names=result.event_names,
            event_producer=result.event_producer, escalation=raised)

    # --- override-rate health (entity §42) — never auto-disabling ---------------------------------

    def override_health_escalation(self, rule_id: str, *, overrides: int, decisions: int,
                                   threshold: float = 0.5, owner_id: str | None = None,
                                   ) -> RaisedException | None:
        """### OVERRIDE RATE IS THE KEY RULE-HEALTH METRIC (entity §42). A rule overridden constantly is a
        wrong rule and gets a HUMAN's attention through M9 — it is NEVER silently auto-disabled (Q3 stays
        deferred at 'never'). This computes the observable override rate from a caller-supplied count (M12
        tracks NO override events, because `PolicyOverridden` is unregistered — ### M12-AQ-7) and, if it
        exceeds `threshold`, CALLS M9's landed `raise_exception` to ASK a human. It NEVER changes the rule's
        state — nothing is auto-disabled, and no override mechanism is built."""
        comp = self.require(rule_id)
        rate = (overrides / decisions) if decisions > 0 else 0.0
        if rate < threshold:
            return None
        owner = owner_id or self.policy_owner()
        if owner is None:
            raise GuardNotSatisfied(
                "a repeatedly-overridden rule asks a HUMAN; this tenant has no single ACTIVE Policy Owner "
                "and none was supplied. It is never auto-disabled.")
        return self._raise_rule_exception(
            source_ref=comp.rule_id, owner_id=owner, type_="rule_repeatedly_overridden_needs_human",
            summary=(f"rule {comp.rule_id!r} (scope {comp.scope!r}) was overridden {overrides} of "
                     f"{decisions} decisions (rate {rate:.2f} >= {threshold}); a repeatedly-wrong rule "
                     f"gets a human's attention and is NEVER auto-disabled (entity §42, Q3 deferred)."))

    def _raise_rule_exception(self, *, source_ref: str, owner_id: str, type_: str,
                              summary: str) -> RaisedException:
        """### CALL M9'S LANDED `raise_exception(source_kind="rule")` — M9 mints, M12 adds no FK, mirror
        column or migration to M9. Returns the record M9 created."""
        m9_result = M9Machine(self._conn, tenant=self._tenant, clock=self._clock).raise_exception(
            type=type_, severity="SEV1", source_ref=source_ref, source_kind="rule", owner_id=owner_id,
            summary=summary, actor_id="policy_engine")
        return RaisedException(exception_id=m9_result.exception.exception_id, source_kind="rule",
                               source_ref=source_ref, owner_id=owner_id, type=type_)

    # --- the uniform (state, trigger) dispatcher --------------------------------------------------

    def apply(self, rule_id: str, trigger: Trigger, *, actor_id: str = "operator",
              **kw: Any) -> TransitionResult:
        """The uniform driver for the exhaustive `(state × trigger)` sweep. Reads the rule, answers
        legality from the TABLE, and refuses an illegal pair under GR-1 before any handler runs."""
        comp = self.require(rule_id)
        self._require_legal(comp, trigger, actor_id=actor_id)
        handler = _APPLY_DISPATCH.get(trigger)
        if handler is None:
            raise M12Error(f"no handler wired for legal trigger {trigger!r} at state {comp.state.value}.")
        return handler(self, rule_id, actor_id=actor_id, **kw)

    # --- replay & park/drain ----------------------------------------------------------------------

    def reference_resolver(self, aggregate_type: str, aggregate_id: str) -> bool:
        if aggregate_type == AGGREGATE_TYPE:
            return self._conn.execute(
                "SELECT 1 FROM rules WHERE tenant = ? AND rule_id = ?",
                (self._tenant, aggregate_id)).fetchone() is not None
        return True

    def consume_event(
        self, envelope: EventEnvelope, *, inbox: DedupInbox | None = None,
        requires_existing: tuple[tuple[str, str], ...] = (), drain: bool = True,
    ) -> ConsumedTransition:
        """Consume one canonical `rule` event idempotently through P5's dedup inbox. ### REPLAY
        RECONSTRUCTS; IT NEVER MANUFACTURES (GR-11, ER-2, K-3): it advances an EXISTING durable row's state
        to match a state-marking event WITHOUT re-deciding it, mints ZERO witnesses, claims ZERO grants,
        produces ZERO external effects, and can NEVER re-activate a rule."""
        box = inbox or DedupInbox(
            self._conn, tenant=self._tenant, consumer_id=CONSUMER_ID, clock=self._clock,
            reference_resolver=self.reference_resolver)
        outcome: dict[str, Any] = {"transition": None, "refusal": None}

        def handler(event: EventEnvelope) -> None:
            comp = self.get(event.aggregate_id)
            if comp is None:
                outcome["refusal"] = (
                    f"{event.event_name} references rule {event.aggregate_id!r}, which does not exist for "
                    f"tenant {self._tenant!r}. Consumed once, nothing persisted.")
                return
            target = _event_target_state(event)
            if target is None or comp.state is target or comp.is_terminal:
                return
            outcome["transition"] = self._reconstruct_locked(comp, target)

        default_reqs: tuple[tuple[str, str], ...] = ((AGGREGATE_TYPE, envelope.aggregate_id),)
        result = box.consume(
            envelope, handler,
            requires_existing=(requires_existing or default_reqs),
            drain_handler_for=((lambda _: handler) if drain else None))
        return ConsumedTransition(
            consume=result, transition=outcome["transition"], refusal=outcome["refusal"])

    def rebuild(self, rule_id: str, *, events: list[EventEnvelope] | None = None) -> ReconstructedRule:
        """### A FULL-HISTORY FOLD OF ONE RULE — SANDBOXED, ZERO AUTHORITY (GR-11, ER-2, K-3). Reconstructs
        `state` from the F12 event stream and creates NOTHING: no activation, no witness, no claimed grant,
        no external effect, no minted authority."""
        stream = events if events is not None else self._event_stream(rule_id)
        state: RuleState | None = None
        for event in sorted(stream, key=lambda e: (e.aggregate_version or 0)):
            target = _event_target_state(event)
            if target is not None:
                state = target
            elif event.event_name == "RuleProposed" and state is None:
                state = RuleState.PROPOSED
        return ReconstructedRule(rule_id=rule_id, state=state)

    # --- shared transition plumbing ---------------------------------------------------------------

    def _advance(
        self, comp: RuleRecord, transition_id: str, to_state: RuleState, *,
        event_name: str, payload: Mapping[str, Any], actor_type: str, actor_id: str, writes: str,
        write_args: tuple[Any, ...], correlation_id: str | None, causation_id: str | None,
        trace_id: str | None, event_id: str | None,
    ) -> TransitionResult:
        """One transition: the state row and its event, in ONE transaction, or neither (GR-2). OCC on the
        version the decision was read at (GR-3): zero rows is a lost update that raises."""
        now = format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            set_clause = "state = ?, version = version + 1, updated_at = ?"
            if writes:
                set_clause += ", " + writes
            args: list[Any] = [to_state.value, now, *write_args,
                               self._tenant, comp.rule_id, comp.state.value, comp.version]
            cursor = conn.execute(
                f"UPDATE rules SET {set_clause} "
                f"WHERE tenant = ? AND rule_id = ? AND state = ? AND version = ?", args)
            if cursor.rowcount != 1:
                raise StateConflict(
                    f"{transition_id} matched {cursor.rowcount} rows for {comp.rule_id!r}: it moved under "
                    f"us (GR-3). Reload — a lost update on a rule is refused.")
            after = self.require(comp.rule_id)
            envelope = self._rule_envelope(
                event_name=event_name, transition_id=transition_id, rule=after, actor_type=actor_type,
                actor_id=actor_id, payload=dict(payload), correlation_id=correlation_id,
                causation_id=causation_id, trace_id=trace_id, event_id=event_id, now=now)
            self._outbox().emit(envelope)
            conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        return TransitionResult(
            transition_id=transition_id, rule=after, from_state=comp.state, to_state=to_state,
            event_ids=(envelope.event_id,), event_names=(event_name,), event_producer=transition_id)

    def _supersede_active_in_scope(self, scope: str, kind: str, *, by: str, now: str) -> list[str]:
        """RU-6, driven by RU-5 in the same commit for a single-admitting scope: transition any prior
        ACTIVE rule for this (scope, kind) to SUPERSEDED and emit RuleSuperseded. The old version is
        RETAINED — it still explains the effects judged under it (entity §24)."""
        rows = self._conn.execute(
            "SELECT * FROM rules WHERE tenant = ? AND scope = ? AND kind = ? AND state = 'ACTIVE' "
            "AND rule_id <> ?",
            (self._tenant, scope, kind, by)).fetchall()
        superseded: list[str] = []
        for row in rows:
            old = _row_to_rule(row)
            cur = self._conn.execute(
                "UPDATE rules SET state = 'SUPERSEDED', version = version + 1, updated_at = ?, "
                "superseded_by = ? WHERE tenant = ? AND rule_id = ? AND state = 'ACTIVE' AND version = ?",
                (now, by, self._tenant, old.rule_id, old.version))
            if cur.rowcount != 1:
                raise StateConflict(
                    f"RU-6 matched {cur.rowcount} rows superseding {old.rule_id!r}: it moved under us.")
            after = self.require(old.rule_id)
            env = self._rule_envelope(
                event_name="RuleSuperseded", transition_id="RU-6", rule=after, actor_type="human",
                actor_id="policy_engine", payload={"superseded_by": by}, correlation_id=None,
                causation_id=None, trace_id=None, event_id=None, now=now)
            self._outbox().emit(env)
            superseded.append(old.rule_id)
        return superseded

    def _reconstruct_locked(self, comp: RuleRecord, target: RuleState) -> TransitionResult:
        """Advance a durable row to match a durable F12 event — reconstruction, not a live transition. ###
        IT MINTS NO AUTHORITY: it moves only `state`, never `activated_by`, never a witness or grant.
        Replay re-activates NOTHING."""
        now = format_instant(self._clock())
        self._conn.execute(
            "UPDATE rules SET state = ?, version = version + 1, updated_at = ? "
            "WHERE tenant = ? AND rule_id = ? AND state = ?",
            (target.value, now, self._tenant, comp.rule_id, comp.state.value))
        after = self.require(comp.rule_id)
        return TransitionResult(
            transition_id="replay", rule=after, from_state=comp.state, to_state=target)

    # --- guards & reads ---------------------------------------------------------------------------

    def _require_legal(self, comp: RuleRecord, trigger: Trigger, *, actor_id: str) -> None:
        """### GR-1, DERIVED FROM THE TABLE. If (state, trigger) is not an enumerated legal row, record
        `IllegalTransitionAttempted` and raise — nothing is persisted."""
        if not legal_transitions(comp.state, trigger):
            self._refuse_illegal(comp.rule_id, trigger, actor_id=actor_id,
                                 reason="omitted (state, trigger) pair")
            raise IllegalTransition(
                f"{trigger.value} is not a legal transition from {comp.state.value} (machine §14, GR-1): "
                f"an omitted (state, trigger) pair raises, persists nothing, and is recorded.")

    def _require_named_human(self, human_id: str | None, role: str) -> str:
        """### A NAMED ACTIVE HUMAN, FK-BACKED (entity §16/§18). "A human" is decoration while the column
        is free text: it must be a recorded, ACTIVE human of THIS tenant. A model is not a human, an
        OFFBOARDED human may not author or activate, and a wrong-tenant human fails closed."""
        text = str(human_id or "").strip()
        if not text:
            raise GuardNotSatisfied(
                f"{role} is a named human, FK-backed into tenant_humans (entity §18): an unnamed value is "
                f"not one.")
        row = self._conn.execute(
            "SELECT state FROM tenant_humans WHERE tenant = ? AND human_id = ?",
            (self._tenant, text)).fetchone()
        if row is None or row["state"] != "ACTIVE":
            raise GuardNotSatisfied(
                f"{role} names {text!r}, who is not an ACTIVE recorded human of {self._tenant!r}. A forged, "
                f"inactive/offboarded or wrong-tenant human fails closed — the human is FK-backed, and a "
                f"counterparty is not a human.")
        return text

    # --- F14 recording ----------------------------------------------------------------------------

    def _record_unauthorized_activation(self, rule_id: str, *, actor_type: str, actor_id: str) -> None:
        """### THE DEDICATED F14 TRIPWIRE, REUSED — a model or automation attempting activation emits the
        already-registered `UnauthorizedPolicyActivationAttempted` (payload policy_or_rule_id, actor_type).
        ### M12 MINTS NO SECOND UNAUTHORIZED-ACTIVATION CONTRACT (rule 17). Recorded to audit AND security;
        M12 engages no brake."""
        self._record_f14(
            aggregate_id=rule_id, event_name="UnauthorizedPolicyActivationAttempted",
            producer_transition_id="RU-5", identity_suffix=f"activate|{actor_type}|{actor_id}",
            payload={"policy_or_rule_id": rule_id, "actor_type": actor_type},
            actor_type="system", actor_id=actor_id)

    def _refuse_illegal(self, aggregate_id: str, trigger: Trigger, *, actor_id: str, reason: str) -> None:
        """### GR-1 — record `IllegalTransitionAttempted` to audit AND security, then the caller raises.
        M12 records this tripwire; it engages NO brake."""
        comp = self.get(aggregate_id)
        state = comp.state.value if comp is not None else "-"
        self._record_f14(
            aggregate_id=aggregate_id, event_name="IllegalTransitionAttempted",
            producer_transition_id=ILLEGAL_TRANSITION_PRODUCER,
            identity_suffix=f"{trigger.value}|{actor_id}|{reason}",
            payload={"machine": "M12", "state": state, "trigger": trigger.value, "attempted_by": actor_id},
            actor_type="system", actor_id=actor_id)

    def _record_f14(self, *, aggregate_id: str, event_name: str, producer_transition_id: str,
                    identity_suffix: str, payload: Mapping[str, Any], actor_type: str,
                    actor_id: str) -> None:
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            version = max(1, self._outbox().last_emitted_version(AGGREGATE_TYPE, aggregate_id))
            identity = (f"{ILLEGAL_ATTEMPT_IDENTITY_PREFIX}|{self._tenant}|{AGGREGATE_TYPE}"
                        f"|{aggregate_id}|{version}|{event_name}|{identity_suffix}")
            existing = conn.execute(
                "SELECT event_id FROM event_outbox WHERE tenant = ? AND idempotency_identity = ?",
                (self._tenant, identity)).fetchone()
            if existing is None:
                now = format_instant(self._clock())
                envelope = EventEnvelope(
                    event_id=str(uuid.uuid4()), event_name=event_name,
                    event_version=CONTRACTS[event_name].current_version, occurred_at=now, recorded_at=now,
                    tenant_id=self._tenant, aggregate_type=AGGREGATE_TYPE, aggregate_id=aggregate_id,
                    aggregate_version=version, previous_aggregate_version=None, causation_id=None,
                    correlation_id=aggregate_id, producer_component=self._component,
                    producer_transition_id=producer_transition_id, actor_type=actor_type,
                    actor_id=actor_id, trace_id=f"trace-{aggregate_id}", payload=dict(payload),
                    idempotency_identity=identity)
                self._outbox().emit(envelope)
                self._store_security_event(envelope, actor_id, event_name)
            conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise

    def _store_security_event(self, envelope: EventEnvelope, actor_id: str, event_type: str) -> None:
        next_id = self._conn.execute(
            "SELECT COALESCE(MAX(id), 0) + 1 FROM security_events WHERE tenant = ?",
            (self._tenant,)).fetchone()[0]
        self._conn.execute(
            "INSERT INTO security_events (tenant, id, event_type, actor, payload_json, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (self._tenant, next_id, event_type, actor_id,
             json.dumps(envelope.payload, sort_keys=True), format_instant(self._clock())))

    # --- outbox / envelope plumbing ---------------------------------------------------------------

    def _event_stream(self, rule_id: str) -> list[EventEnvelope]:
        rows = self._conn.execute(
            "SELECT envelope_json FROM event_outbox WHERE tenant = ? AND aggregate_type = ? "
            "AND aggregate_id = ? ORDER BY aggregate_version, sequence",
            (self._tenant, AGGREGATE_TYPE, rule_id)).fetchall()
        return [EventEnvelope.from_json(r["envelope_json"]) for r in rows]

    def _outbox(self):
        from .event_outbox import TransactionalOutbox
        return TransactionalOutbox(self._conn, tenant=self._tenant, clock=self._clock)

    def _actor_type(self, actor_kind: str) -> str:
        """Map a caller's actor_kind to a canonical envelope `actor_type` ∈ {human, system, detector,
        model}. HUMAN is human; model and detector are themselves; automation, a retry handler, a timer, a
        counterparty and a service account are all `system`."""
        k = str(actor_kind).strip().lower()
        if k == "human":
            return "human"
        if k in ("model", "detector"):
            return k
        return "system"

    def _rule_envelope(
        self, *, event_name: str, transition_id: str, rule: RuleRecord, actor_type: str, actor_id: str,
        payload: Mapping[str, Any], correlation_id: str | None, causation_id: str | None,
        trace_id: str | None, event_id: str | None, now: str,
    ) -> EventEnvelope:
        """One canonical envelope on the `rule` aggregate. ### THE AGGREGATE IS ORDER-TOLERANT (### M12-AQ-5);
        the DB monotonicity constraint is the real ordering guarantee. `previous_aggregate_version` is set
        as the ADDITIVE, strictly-safer side, WITHOUT flipping the registered order-tolerant contract."""
        hw = self._outbox().last_emitted_version(AGGREGATE_TYPE, rule.rule_id)
        version = hw + 1
        previous = hw if hw >= 1 else None
        return EventEnvelope(
            event_id=event_id or str(uuid.uuid4()), event_name=event_name,
            event_version=CONTRACTS[event_name].current_version, occurred_at=now, recorded_at=now,
            tenant_id=self._tenant, aggregate_type=AGGREGATE_TYPE, aggregate_id=rule.rule_id,
            aggregate_version=version, previous_aggregate_version=previous, causation_id=causation_id,
            correlation_id=correlation_id or rule.rule_id, producer_component=self._component,
            producer_transition_id=transition_id, actor_type=actor_type, actor_id=actor_id,
            trace_id=trace_id or f"trace-{rule.rule_id}", payload=dict(payload))


# ------------------------------------------------------------------------------------- plumbing

_APPLY_DISPATCH: Mapping[Trigger, Callable[..., TransitionResult]] = {
    Trigger.COMPILE: lambda m, rid, **kw: m.compile(rid, **{k: v for k, v in kw.items() if k != "actor_id"}),
    Trigger.HUMAN_CONFIRMED: lambda m, rid, **kw: m.confirm(rid, **kw),
    Trigger.HUMAN_ACTIVATED: lambda m, rid, **kw: m.activate(rid, **kw),
    Trigger.NEW_VERSION_ACTIVATED: lambda m, rid, **kw: m.supersede(rid, **kw),
    Trigger.HUMAN_REVOKED: lambda m, rid, **kw: m.revoke(rid, **kw),
    Trigger.TIMER_FIRED: lambda m, rid, **kw: m.expire(rid, **{k: v for k, v in kw.items() if k != "actor_id"}),
    Trigger.CONFLICT_DETECTED: lambda m, rid, **kw: m.detect_conflict(rid, **{k: v for k, v in kw.items() if k != "actor_id"}),
}


def _event_target_state(event: EventEnvelope) -> RuleState | None:
    """The state a rule F12 event reconstructs to, or None for an event that is not a state marker."""
    return {
        "RuleCompiled": RuleState.COMPILED,
        "RuleNotEnforceable": RuleState.REJECTED,
        "RuleConfirmed": RuleState.CONFIRMED,
        "RuleActivated": RuleState.ACTIVE,
        "RuleSuperseded": RuleState.SUPERSEDED,
        "RuleRevoked": RuleState.REVOKED,
        "RuleExpired": RuleState.EXPIRED,
    }.get(event.event_name)


def _require_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise MalformedRule(f"{field_name} is required and was empty.")
    return text


def _parse_json_obj(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return dict(loaded) if isinstance(loaded, dict) else {}


def _row_to_rule(row: Any) -> RuleRecord:
    return RuleRecord(
        tenant=row["tenant"], rule_id=row["rule_id"], rule_version=int(row["rule_version"]),
        scope=row["scope"], kind=row["kind"],
        compiled_predicate=row["compiled_predicate"], test_vectors=row["test_vectors"],
        state=RuleState(row["state"]), version=int(row["version"]),
        source_instruction=row["source_instruction"], authored_by=row["authored_by"],
        activated_by=row["activated_by"], expires_at=row["expires_at"],
        change_direction=row["change_direction"], superseded_by=row["superseded_by"],
        revoked_reason=row["revoked_reason"], revoked_direction=row["revoked_direction"],
        conflict_id=row["conflict_id"], created_at=row["created_at"])


# Re-exported so a caller reads one name rather than importing the migration for a constant.
STATES: tuple[str, ...] = RULE_STATES
