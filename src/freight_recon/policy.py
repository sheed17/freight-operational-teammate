"""Machine M11 — the Policy: the typed, versioned, scoped, deterministic tenant posture evaluated at
CHECKPOINT STEP 6, returning a NEVER-NULL canonical gate decision. This is the machine that answers
"what may Neyma do alone, for whom, and up to what caps", and the one place in the architecture where the
answer must be a VALUE the owner can see, version and revoke rather than a sentence in a prompt.

    ### A POLICY IS A VALUE THE OWNER CAN SEE, NOT A SENTENCE IN A PROMPT.
    ### A TENANT POLICY MAY ONLY EVER NARROW THE PRODUCT CEILING.
    ### AUTOMATION MAY ONLY EVER MOVE AUTHORITY IN THE SAFE DIRECTION.
    ### A GATE EXPRESSIBLE AS AN ABSENCE IS NOT A GATE.
    ### A POLICY MAY NEVER BRANCH ON A GUESS.

An owner types "never bill without a POD." The old system replied "noted the procedure" and installed a
sentence in an LLM prompt — the owner believed they installed a control; they installed a suggestion.
M11 makes the difference real: a policy is a ROW whose `gate_decision` cannot be null and is one of the
four canonical members (ADR-010 §3.1), whose `predicate` cannot read a `MODEL_INFERRED` guess, whose
`policy_version` is bound into every witness and grant, and whose activation only an AUTHENTICATED HUMAN
recorded in `tenant_humans` can perform.

### WHAT THIS MACHINE OWNS, AND WHAT IT ONLY FEEDS.

It owns the SEVEN states DRAFT/PROPOSED/APPROVED/ACTIVE/SUPERSEDED/REVOKED/EXPIRED and the SEVEN
transitions PO-1…PO-7 of `11-policy.machine.md` §14, and it is the canonical producer of the EIGHT
already-registered F11 `Policy*` contracts (ADR-010; entity §31; events registry §3). The `policy`
aggregate is STRICT-ORDER (registry §8), so every event carries `previous_aggregate_version` and the
consumer blocks on an unapplied predecessor — ORDER, never CONTIGUITY (P6-D11).

### IT IS CHECKPOINT STEP 6; IT MINTS NO GATE DECISION AND BUILDS NO SECOND CHECKPOINT. `M11 IS
checkpoint step 6` (entity §38): it supplies the POSTURE the kernel's step 6 reads. It imports
`checkpoint.GateDecision` and NEVER redeclares the enum; it constructs NO `GateEntry` and NO
`GateRegistry` — a second gate authority is the same defect as no gate authority, so `checkpoint.py`
stays the SOLE minter of a gate decision and the production `GateRegistry` population stays EMPTY (R-07,
AC-CKPT-6-missing, U8.1/P8). `PolicyEvaluated` is F2's, produced by M2's PL-2 on the pipeline_instance
aggregate — M11 emits NO `PolicyEvaluated`.

### THE INVALIDATION MECHANISMS ARE ALREADY BUILT; M11 DRIVES THEM, NEVER A SECOND ONE (rule 17). A
policy change VOIDS in-flight authority: the M4 Approval becomes `VOID_ON_DRIFT` (`approval.void_on_policy`
/ AP-4p), the Checkpoint Witness becomes invalid, and the Effect Grant becomes unclaimable (P3's claim CAS
already revalidates `policy_version`). M11 emits the COORDINATION event `PolicyVersionChanged` and those
consumers void by their OWN guards. ### THE VERSION NAMESPACE IS THE TENANT (### M11-AQ-6): a change in
ANY scope advances the tenant's `policy_version`, so the void reaches in-flight authority in EVERY scope —
over-voiding is the fail-closed direction and under-voiding is not available.

### EXPIRY IS THE ONE PLACE A CLOCK COULD BROADEN AUTHORITY, AND IT MAY NOT. Only a NARROWING policy may
carry an `expires_at`; its expiry BROADENS, so PO-7 raises a human-confirmation Exception through M9's
LANDED `raise_exception(source_kind="policy")` and RESTORES NO AUTHORITY on its own. The clock may take
authority away; the clock may never give it. M11 edits no part of M9 (### M11-AQ-8 / P6-D73: the seam is
named and left unwired, exactly as M10 left `compensation` unwired).

### HUMAN AUTHORITY. A policy is owned by exactly ONE named Policy Owner per tenant (I1) — enforced on the
M1-landed `tenant_humans` record by the Policy Owner singularity index this unit adds (### M11-AQ-7 /
P6-D72). Authorship: the Policy Owner or a delegate. Activation: only an authenticated human — NEVER a
model, NEVER automation, NEVER a retry handler, NEVER a timer; an attempt by any of those emits the
already-registered F14 `UnauthorizedPolicyActivationAttempted`. Inbound content can never author a policy.

### IT SHIPS DARK. Nothing under `src/freight_recon/` imports this module; the only script that may is
`scripts/probe_phase6_policy.py`. It joins no importer, editor, admin screen, oversight queue, dashboard
or notifier; it builds no part of M12 (Rule) or M13 (Brake); nothing graduates (V11); it invents no admin
authority (V12); it mints no `PolicyOverridden` and builds no override mechanism (### M11-AQ-4 / P6-D71,
BLOCKED_AUTHORITY).
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

# ### IMPORT THE FOUR CANONICAL GATE MEMBERS AND THE GATING ACCESSOR — NEVER REDECLARE THEM (ADR-010
# §3.1). `GateDecision` is minted nowhere but `checkpoint.py`; `ProvenancedFact.value` already RAISES on a
# MODEL_INFERRED read and carries NO confidence field, so M11 reuses that pattern rather than inventing a
# second one. `GateReadOfInferredFact` is the raise. This is checkpoint step 6's posture, not a second gate.
from .checkpoint import (
    GateDecision,
    GateReadOfInferredFact,
    ProvenanceClass,
    ProvenancedFact,
)
from .event_contracts import CONTRACTS
from .event_envelope import EventEnvelope, format_instant
from .event_inbox import ConsumeResult, DedupInbox
from .migrations.phase6_policies import (
    GATE_DECISIONS,
    NON_TERMINAL_POLICY_STATES,
    POLICY_STATES,
    REVOKE_DIRECTIONS,
    SCOPE_KINDS,
    TERMINAL_POLICY_STATES,
)
from .tenant import require_tenant

# The aggregate this machine owns. `policy` IS in `STRICT_ORDER_AGGREGATE_TYPES` (phase5): the eight F11
# contracts are strict per-aggregate, so every M11 event carries `previous_aggregate_version` and the
# consumer blocks on an unapplied predecessor — ORDER, never CONTIGUITY (P6-D11, registry §8).
AGGREGATE_TYPE = "policy"

# entity §5 — the Policy Engine owns policies.
PRODUCER_COMPONENT = "policy_engine"

# The one consumer identity M11 presents to the dedup inbox. Fixed, because the dedup key is
# `(tenant, consumer_id, event_id)` and a renamed consumer would re-arm every duplicate.
CONSUMER_ID = "m11-policy"

# GR-1's producer id for `IllegalTransitionAttempted` — the RULE, not a transition. Identical to M1..M10's.
ILLEGAL_TRANSITION_PRODUCER = "GR-1"

# A refusal advances no version; two refusals against one policy at one version would otherwise collide on
# one idempotency identity — the poison-loop defect M1 shipped. Applied here.
ILLEGAL_ATTEMPT_IDENTITY_PREFIX = "ita_v1"

HUMAN = "HUMAN"

# ### THE DECLARED TOTAL ORDER OVER THE FOUR CANONICAL GATE MEMBERS (ADR-010 §3.1), BROADEST FIRST:
#   AUTONOMOUS_WITHIN_CAPS > HUMAN_APPROVAL_REQUIRED > PERMANENT_HUMAN_ASSERTION_REQUIRED > FORBIDDEN
# ### THIS IS NOT A STRING COMPARE. `AUTONOMOUS_WITHIN_CAPS` sorts BEFORE `HUMAN_APPROVAL_REQUIRED`
# alphabetically, so a string comparison would call the single most dangerous broadening in the system a
# narrowing — silently, on the exact path where nobody is watching. The rank makes the order EXPLICIT.
_GATE_RANK: dict[GateDecision, int] = {
    GateDecision.AUTONOMOUS_WITHIN_CAPS: 3,
    GateDecision.HUMAN_APPROVAL_REQUIRED: 2,
    GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED: 1,
    GateDecision.FORBIDDEN: 0,
}

# The fail-closed product ceiling. Spec §20.2 enforces Product Policy in CONFIG, which does not exist yet;
# until it does, the ceiling is the workflow default HUMAN_APPROVAL_REQUIRED (ADR-010 §8 layer 7, the
# kernel's own `_DEFAULT`). Nothing graduates (V11), so a tenant policy can never reach AUTONOMOUS_WITHIN_
# CAPS under this default — that is the safe direction, and it is deliberate.
DEFAULT_PRODUCT_CEILING = GateDecision.HUMAN_APPROVAL_REQUIRED


def gate_rank(gate: GateDecision) -> int:
    """The rank of a gate member in the declared total order (broadest = highest). Raises on anything not
    a `GateDecision`, so a raw string can never be ranked — the comparison is typed, never textual."""
    if not isinstance(gate, GateDecision):
        raise M11Error(
            f"a gate decision must be one of the four canonical members, got {gate!r}: the ceiling "
            f"comparison is over a declared total order, never a raw string compare (ADR-010 §3.1).")
    return _GATE_RANK[gate]


def narrows_or_holds(new: GateDecision, ceiling: GateDecision) -> bool:
    """True iff `new` is no broader than `ceiling` in the declared total order — the ONLY direction a
    tenant policy may move (ADR-010 §3.1/§8). Broadening (`gate_rank(new) > gate_rank(ceiling)`) is
    refused at the PO-2 guard and by machine §15's illegal transition — MECHANICALLY IMPOSSIBLE, not
    merely refused in review."""
    return gate_rank(new) <= gate_rank(ceiling)


# ### THE §5.2 EVALUATION INPUTS A PREDICATE MAY REFERENCE — all deterministic (ADR-010 §5.2). `confidence`
# is DELIBERATELY ABSENT: it is structurally not an input, and a predicate that names it fails to compile.
ALLOWED_PREDICATE_FIELDS: frozenset[str] = frozenset({
    "tenant", "actor", "accountable_owner", "action_class", "target_system", "target_resource",
    "counterparty", "value", "money_direction", "workflow", "entity_versions", "material_facts",
    "policy_version", "autonomy_state", "open_conflicts", "open_exceptions", "approval_state", "now",
    "applicable_caps",
})

# The three attributes a predicate clause may read of a material fact. `value` is the GATING accessor
# (raises on MODEL_INFERRED); `provenance_class` and `evidence_condition` are deterministic METADATA that a
# policy is entitled to branch on (that is exactly "never bill without a POD" — branch on the POD's
# evidence, not a guess about its contents).
PREDICATE_ATTRS: frozenset[str] = frozenset({"value", "provenance_class", "evidence_condition"})

# The name a predicate may NEVER reference, at any confidence — because there is no confidence.
FORBIDDEN_PREDICATE_NAME = "confidence"


# ------------------------------------------------------------------------------------ errors

class M11Error(RuntimeError):
    """This machine will not do what was asked. Never degraded into a partial transition."""


class UnknownPolicy(M11Error):
    """No `policies` row with this id exists FOR THIS TENANT. Indistinguishable from "belongs to another
    tenant" on purpose — [C-1] rejects a cross-tenant question."""


class GuardNotSatisfied(M11Error):
    """The (state, trigger) pair IS legal here and a precondition is false. No event is emitted."""


class IllegalTransition(M11Error):
    """GR-1 / [C-4] / GR-7. The (state, trigger) pair is not enumerated, or a model/automation attempted
    an activation or a broadening. Raised AFTER the tripwire is recorded."""


class StateConflict(M11Error):
    """A state-guarded UPDATE matched zero rows: the policy moved under us (GR-3). Reload."""


class MalformedPolicy(M11Error):
    """The inputs are not a canonical policy — a null/invented gate, a blank scope, a bad scope kind, a
    predicate that is a prompt string. Fail closed; nothing is persisted."""


class PredicateWillNotCompile(M11Error):
    """### A GUESS CANNOT BECOME A GATE BY BEING PASSED THROUGH A POLICY ENGINE (ADR-010 §5.1, §6). The
    predicate references a `MODEL_INFERRED` value, an unmodelled field, or `confidence` — so it FAILS TO
    COMPILE and never reaches ACTIVE. The honest reply is 'I cannot enforce that, and here is why', never
    'noted the procedure'."""


class PolicyEngineUnavailable(M11Error):
    """### THE POLICY ENGINE IS UNAVAILABLE AT CHECKPOINT ⇒ NO DECISION ⇒ NO WITNESS ⇒ NO EFFECT (spec
    §11). There is no allow-on-error default anywhere in this unit; an allow-on-error default is how the
    money fence dies, quietly, at the moment the system is least able to tell anyone."""


# ------------------------------------------------------------------------------- the state set

class PolicyState(str, Enum):
    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class Trigger(str, Enum):
    """The closed set of driving facts, named from §14's triggers and §33's "Events consumed", plus the
    illegal `TimerFired`-that-broadens and the illegal model/automation activation, so GR-1 answers them
    uniformly. `H` human, `S` system, `T` timer."""

    AUTHORED = "Authored"                          # PO-1
    SUBMITTED = "Submitted"                         # PO-2
    APPROVED = "Approved"                           # PO-3
    HUMAN_ACTIVATED = "HumanActivated"              # PO-4
    NEW_VERSION_ACTIVATED = "NewVersionActivated"   # PO-5
    REVOKED = "Revoked"                             # PO-6
    TIMER_EXPIRED = "TimerFired"                    # PO-7 (narrowing TTL) — raises a human Exception


class RowKind(str, Enum):
    PRODUCER = "PRODUCER"


# --------------------------------------------------------------------------- the transition table

@dataclass(frozen=True)
class TransitionRow:
    """One row of §14. Data, so `AC-MACH-000` can enumerate it and compare to the specification — a
    transition table written as if/elif cannot be enumerated, and a rule nobody can enumerate is a rule
    nobody can test."""

    id: str
    from_states: tuple[PolicyState, ...]
    to_state: PolicyState | None
    triggers: tuple[Trigger, ...]
    trigger_types: tuple[str, ...]      # H|S|T — the registry §1 codes
    kind: RowKind
    events: tuple[str, ...] = ()        # the canonical events this row emits
    consequential: bool = False         # §5: pins the decision context at emission

    @property
    def independently_fireable(self) -> bool:
        return True


TRANSITIONS: tuple[TransitionRow, ...] = (
    TransitionRow(
        # PO-1 — the raise: — -> DRAFT, authored by the Policy Owner or a delegate (a model may propose
        # TEXT, never a policy row). A creation row (no from-state).
        id="PO-1", from_states=(), to_state=PolicyState.DRAFT,
        triggers=(Trigger.AUTHORED,), trigger_types=("H",), kind=RowKind.PRODUCER,
        events=("PolicyProposed",),
    ),
    TransitionRow(
        # PO-2 — DRAFT -> PROPOSED: gate NOT NULL (F-20), predicate references only MODELLED NON-INFERRED
        # fields (GR-8), tenant policy may only NARROW the product ceiling.
        id="PO-2", from_states=(PolicyState.DRAFT,), to_state=PolicyState.PROPOSED,
        triggers=(Trigger.SUBMITTED,), trigger_types=("H",), kind=RowKind.PRODUCER,
        events=("PolicySubmitted",),
    ),
    TransitionRow(
        # PO-3 — PROPOSED -> APPROVED: the change ran through an M2 pipeline with the DIFF as material
        # facts. Consequential; the "no admin path" evidence. Does NOT activate.
        id="PO-3", from_states=(PolicyState.PROPOSED,), to_state=PolicyState.APPROVED,
        triggers=(Trigger.APPROVED,), trigger_types=("H",), kind=RowKind.PRODUCER,
        events=("PolicyApproved",), consequential=True,
    ),
    TransitionRow(
        # PO-4 — APPROVED -> ACTIVE: an AUTHENTICATED human activates — NEVER a model, NEVER automation.
        # Emits PolicyActivated + the coordination PolicyVersionChanged.
        id="PO-4", from_states=(PolicyState.APPROVED,), to_state=PolicyState.ACTIVE,
        triggers=(Trigger.HUMAN_ACTIVATED,), trigger_types=("H",), kind=RowKind.PRODUCER,
        events=("PolicyActivated", "PolicyVersionChanged"), consequential=True,
    ),
    TransitionRow(
        # PO-5 — ACTIVE -> SUPERSEDED: a new version activated. Old version RETAINED.
        id="PO-5", from_states=(PolicyState.ACTIVE,), to_state=PolicyState.SUPERSEDED,
        triggers=(Trigger.NEW_VERSION_ACTIVATED,), trigger_types=("H",), kind=RowKind.PRODUCER,
        events=("PolicySuperseded",),
    ),
    TransitionRow(
        # PO-6 — ACTIVE -> REVOKED: immediate if it NARROWS; the Policy Owner if it BROADENS.
        id="PO-6", from_states=(PolicyState.ACTIVE,), to_state=PolicyState.REVOKED,
        triggers=(Trigger.REVOKED,), trigger_types=("H", "S"), kind=RowKind.PRODUCER,
        events=("PolicyRevoked", "PolicyVersionChanged"),
    ),
    TransitionRow(
        # PO-7 — ACTIVE -> EXPIRED: a narrowing policy's TTL fires ⇒ raises a human-confirmation Exception.
        # Restores NO authority on its own.
        id="PO-7", from_states=(PolicyState.ACTIVE,), to_state=PolicyState.EXPIRED,
        triggers=(Trigger.TIMER_EXPIRED,), trigger_types=("T",), kind=RowKind.PRODUCER,
        events=("PolicyExpired",),
    ),
)

TRANSITIONS_BY_ID: Mapping[str, TransitionRow] = {row.id: row for row in TRANSITIONS}

# §32 "Events emitted", derived from the table: the eight F11 contracts. A second hand-kept list would
# stop matching. The contract gate refuses an envelope whose producer_transition_id is not among the
# contract's declared producers, so this is also what the outbox accepts from this machine.
PRODUCED_CONTRACTS: frozenset[str] = frozenset(ev for row in TRANSITIONS for ev in row.events)

TERMINAL_STATES: frozenset[PolicyState] = frozenset(PolicyState(s) for s in TERMINAL_POLICY_STATES)
NON_TERMINAL_STATES: frozenset[PolicyState] = frozenset(
    PolicyState(s) for s in NON_TERMINAL_POLICY_STATES)


def legal_transitions(state: PolicyState | None, trigger: Trigger) -> tuple[TransitionRow, ...]:
    """Every row whose (from-state, trigger) matches. Empty ⇒ GR-1 refuses it. A None state matches a
    creation row (PO-1)."""
    return tuple(
        row for row in TRANSITIONS
        if trigger in row.triggers and (
            (state is None and not row.from_states) or (state is not None and state in row.from_states)))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------------------- the predicate

@dataclass(frozen=True)
class PredicateClause:
    """One deterministic clause of a compiled predicate: read `attr` of material fact `field` and compare
    it with `op` to `literal`. `attr='value'` is the GATING accessor and may never read a MODEL_INFERRED
    field; `provenance_class`/`evidence_condition` are deterministic metadata a policy is entitled to."""

    field: str
    attr: str
    op: str
    literal: Any

    def canonical(self) -> dict[str, Any]:
        return {"field": self.field, "attr": self.attr, "op": self.op, "literal": self.literal}


@dataclass(frozen=True)
class CompiledPredicate:
    """A predicate that COMPILED — every referenced field is modelled and non-inferred, and none is
    `confidence`. A predicate that cannot be evaluated deterministically FAILS TO COMPILE and never
    reaches ACTIVE (ADR-010 §5.1/§6). An empty clause set is the trivially-true predicate (permit)."""

    combine: str                    # "AND" | "OR"
    clauses: tuple[PredicateClause, ...]

    def canonical(self) -> dict[str, Any]:
        return {"combine": self.combine, "clauses": [c.canonical() for c in self.clauses]}

    def to_json(self) -> str:
        return json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"))


def compile_predicate(
    predicate: Any, *, field_provenance: Mapping[str, ProvenanceClass] | None = None,
) -> CompiledPredicate:
    """### THE HONEST RESOLUTION OF "A PROMPT STRING IS NOT A POLICY" (ADR-010 §6). There are exactly two
    outcomes: it compiles, or it fails to compile and the owner is told why. There is no third.

    Refuses, in order: a bare string ("noted the procedure" — a prompt is not a predicate); a malformed
    structure; an unknown combine; a clause naming a field outside the §5.2 inputs; a clause naming
    `confidence` (structurally not an input, at any confidence); a clause reading the `value` of a field
    declared `MODEL_INFERRED` (a guess cannot gate). `field_provenance` declares the provenance of each
    material fact the predicate reads a value of — a value-read of an undeclared field is refused too,
    because an unproven provenance is not a non-inferred one.
    """
    if isinstance(predicate, str):
        raise PredicateWillNotCompile(
            "a policy predicate is a typed, structured expression over the §5.2 inputs, not a sentence: a "
            "prompt string is not a policy (ADR-010 §6, lesson L-C). I cannot enforce a text box.")
    if not isinstance(predicate, Mapping):
        raise PredicateWillNotCompile(
            f"a predicate is a structured mapping {{combine, clauses}}; got {type(predicate).__name__}.")
    combine = str(predicate.get("combine", "AND")).upper()
    if combine not in ("AND", "OR"):
        raise PredicateWillNotCompile(f"predicate combine must be AND or OR; got {combine!r}.")
    raw_clauses = predicate.get("clauses", [])
    if not isinstance(raw_clauses, (list, tuple)):
        raise PredicateWillNotCompile("predicate clauses must be a list.")
    provmap = {str(k): v for k, v in (field_provenance or {}).items()}
    clauses: list[PredicateClause] = []
    for raw in raw_clauses:
        if not isinstance(raw, Mapping):
            raise PredicateWillNotCompile(f"each predicate clause is a mapping; got {raw!r}.")
        fld = str(raw.get("field", "")).strip()
        attr = str(raw.get("attr", "value")).strip()
        op = str(raw.get("op", "==")).strip()
        literal = raw.get("literal")
        if fld == FORBIDDEN_PREDICATE_NAME or attr == FORBIDDEN_PREDICATE_NAME:
            raise PredicateWillNotCompile(
                "a predicate may never reference `confidence`: it is structurally not an input (ADR-010 "
                "§5.1 corollary). At confidence 1.0 it still fails, because there is no confidence.")
        if not fld:
            raise PredicateWillNotCompile("a predicate clause names a field; a blank field is not one.")
        if fld not in ALLOWED_PREDICATE_FIELDS and not fld.startswith("fact:"):
            raise PredicateWillNotCompile(
                f"predicate clause references {fld!r}, which is not one of the §5.2 inputs and is not a "
                f"material fact (prefix 'fact:'): an unmodelled field cannot be compiled into a predicate.")
        if attr not in PREDICATE_ATTRS:
            raise PredicateWillNotCompile(
                f"predicate clause attr must be one of {sorted(PREDICATE_ATTRS)}; got {attr!r}.")
        if attr == "value" and fld.startswith("fact:"):
            declared = provmap.get(fld) or provmap.get(fld[len("fact:"):])
            if declared is None:
                raise PredicateWillNotCompile(
                    f"predicate reads the VALUE of material fact {fld!r} but its provenance was not "
                    f"declared: an unproven provenance is not a non-inferred one (ADR-010 §5.1).")
            if _as_provenance(declared) is ProvenanceClass.MODEL_INFERRED:
                raise PredicateWillNotCompile(
                    f"predicate branches on the VALUE of MODEL_INFERRED material fact {fld!r}: a policy "
                    f"may never branch on a guess, at any confidence (M-49, GR-8). It FAILS TO COMPILE.")
        clauses.append(PredicateClause(field=fld, attr=attr, op=op, literal=literal))
    return CompiledPredicate(combine=combine, clauses=tuple(clauses))


def _as_provenance(value: Any) -> ProvenanceClass:
    if isinstance(value, ProvenanceClass):
        return value
    try:
        return ProvenanceClass(str(value))
    except ValueError as exc:
        raise PredicateWillNotCompile(f"unknown provenance class {value!r}") from exc


# ------------------------------------------------------------------------------- the evaluator

@dataclass(frozen=True)
class PolicyEvaluationInputs:
    """The typed inputs of one policy evaluation (ADR-010 §5.2), all deterministic. ### THERE IS NO
    `confidence` FIELD ON THIS TYPE — a predicate cannot read one even by trying. Material facts arrive as
    `checkpoint.ProvenancedFact`, whose `.value` RAISES on MODEL_INFERRED and which carries no confidence
    either — the same gating accessor the checkpoint uses, reused rather than reinvented."""

    tenant: str
    action_class: str
    now: str                                    # the DB clock, a BOUND input — never wall-clock at eval
    actor: str = ""
    accountable_owner: str = ""
    target_system: str = ""
    target_resource: str = ""
    counterparty: str = ""
    money_direction: str = ""
    workflow: str = ""
    autonomy_state: str = ""
    approval_state: str = ""
    open_conflicts: int = 0
    open_exceptions: int = 0
    material_facts: Mapping[str, ProvenancedFact] = dataclass_field(default_factory=dict)
    applicable_caps: Mapping[str, Any] = dataclass_field(default_factory=dict)


@dataclass(frozen=True)
class PolicyDecision:
    """The output of checkpoint step 6 (ADR-010 §5.3) — a VALUE, never a new entity. `gate_decision` is
    NEVER NULL; `reason` is mandatory, always, including on PERMIT (a system that can block but not explain
    has merely relocated the owner's problem). Given the same inputs and the same `policy_version`, this is
    BYTE-IDENTICAL reproducible (M-50): `canonical()` sorts everything and no wall clock, randomness, model
    call or unordered iteration enters it."""

    gate_decision: GateDecision
    decision: str                               # "PERMIT" | "DENY"
    policy_version: str
    reason: str
    rules_evaluated: tuple[str, ...] = ()
    rules_matched: tuple[str, ...] = ()
    caps_applied: tuple[tuple[str, Any], ...] = ()

    def canonical(self) -> dict[str, Any]:
        return {
            "gate_decision": self.gate_decision.value,
            "decision": self.decision,
            "policy_version": self.policy_version,
            "reason": self.reason,
            "rules_evaluated": list(self.rules_evaluated),
            "rules_matched": list(self.rules_matched),
            "caps_applied": [list(c) for c in self.caps_applied],
        }

    def to_bytes(self) -> bytes:
        return json.dumps(self.canonical(), sort_keys=True, separators=(",", ":")).encode("utf-8")


def evaluate_predicate(predicate: CompiledPredicate, inputs: PolicyEvaluationInputs) -> bool:
    """Evaluate a compiled predicate deterministically over the inputs. `attr='value'` reads
    `ProvenancedFact.value`, which RAISES on MODEL_INFERRED — defense in depth behind compile-time refusal,
    so even a compiled predicate handed a guess at runtime FAILS CLOSED rather than deciding on it."""
    if not predicate.clauses:
        return True
    results: list[bool] = []
    for clause in predicate.clauses:
        results.append(_evaluate_clause(clause, inputs))
    return all(results) if predicate.combine == "AND" else any(results)


def _evaluate_clause(clause: PredicateClause, inputs: PolicyEvaluationInputs) -> bool:
    if clause.field.startswith("fact:"):
        name = clause.field[len("fact:"):]
        fact = inputs.material_facts.get(name)
        if fact is None:
            return False
        if clause.attr == "value":
            observed: Any = fact.value  # RAISES on MODEL_INFERRED (checkpoint.ProvenancedFact)
        elif clause.attr == "provenance_class":
            observed = fact.provenance.value
        else:
            observed = fact.evidence_condition.value
    else:
        observed = getattr(inputs, clause.field, None)
    return _apply_op(clause.op, observed, clause.literal)


def _apply_op(op: str, observed: Any, literal: Any) -> bool:
    if op == "==":
        return observed == literal
    if op == "!=":
        return observed != literal
    if op == "in":
        return observed in literal if isinstance(literal, (list, tuple, set)) else False
    if op == "not_in":
        return observed not in literal if isinstance(literal, (list, tuple, set)) else False
    if op in (">", ">=", "<", "<="):
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
    raise M11Error(f"unknown predicate operator {op!r}: the operator set is fixed and deterministic.")


# ------------------------------------------------------------------------------------ the row

@dataclass(frozen=True)
class PolicyRecord:
    """One `policies` row, as the machine reads it."""

    tenant: str
    policy_id: str
    policy_version: int
    scope: str
    scope_kind: str
    gate_decision: GateDecision
    caps: dict[str, Any]
    predicate: CompiledPredicate
    state: PolicyState
    version: int
    effective_from: str
    authored_by: str
    activated_by: str | None
    expires_at: str | None
    change_direction: str
    superseded_by: str | None
    revoked_reason: str | None
    revoked_direction: str | None
    approval_id: str | None
    diff_fingerprint: str | None
    created_at: str

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES


@dataclass(frozen=True)
class ExpiryEscalation:
    """### PO-7's NAMED-BUT-UNWIRED M9 SEAM (### M11-AQ-8 / P6-D73). A narrowing policy's expiry BROADENS,
    so it OWES a human-confirmation Exception — but M11 does NOT import or call M9, exactly as M10 left its
    F10->M9 escalation unwired ("wiring a seam is precisely what shipping dark forbids"). This value NAMES
    the Exception that is owed, in the exact shape M9's LANDED `raise_exception` accepts (`source_kind=
    "policy"`, already in M9's `SOURCE_KINDS` without a table). A caller — the probe — DRIVES M9's landed
    entry point with it; policy.py stays free of any exception.py import, so M9 keeps ZERO production
    importers. Authority is NOT restored by the expiry; this is only the human's cue."""

    source_kind: str
    source_ref: str
    owner_id: str
    type: str
    severity: str
    summary: str

    def as_m9_kwargs(self) -> dict[str, Any]:
        """The exact keyword arguments M9's landed `raise_exception` takes. The caller unpacks these into
        `M9Machine(...).raise_exception(**escalation.as_m9_kwargs())` — M11 names the seam, the caller
        wires it."""
        return {"type": self.type, "severity": self.severity, "source_ref": self.source_ref,
                "source_kind": self.source_kind, "owner_id": self.owner_id, "summary": self.summary}


@dataclass(frozen=True)
class TransitionResult:
    transition_id: str
    policy: PolicyRecord | None
    from_state: PolicyState | None
    to_state: PolicyState | None
    event_ids: tuple[str, ...] = ()
    event_names: tuple[str, ...] = ()
    event_producer: str | None = None
    escalation: ExpiryEscalation | None = None  # PO-7's named-but-unwired M9 human-confirmation seam


@dataclass(frozen=True)
class ReconstructedPolicy:
    """A full-history fold of one policy's F11 event stream — sandboxed, zero authority (GR-11, ER-2,
    K-3). ### REPLAY RE-ACTIVATES NOTHING, MINTS NO WITNESS, CLAIMS NO GRANT AND PRODUCES NO EXTERNAL
    EFFECT. Every count of what the rebuild created is zero."""

    policy_id: str
    state: PolicyState | None
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

class M11Machine:
    """M11, on an existing connection, bound to ONE tenant. Bound at construction so a caller cannot
    re-point it at another tenant and put [C-1] in its own hands."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        tenant: str,
        clock: Callable[[], datetime] | None = None,
        producer_component: str = PRODUCER_COMPONENT,
        product_ceiling: GateDecision = DEFAULT_PRODUCT_CEILING,
    ) -> None:
        if getattr(conn, "row_factory", None) is not sqlite3.Row:
            raise M11Error("M11Machine reads columns by name and requires `row_factory = sqlite3.Row`.")
        self._conn = conn
        self._tenant = require_tenant(tenant, context="M11Machine")
        self._clock = clock or _utc_now
        self._component = producer_component
        if not isinstance(product_ceiling, GateDecision):
            raise M11Error("the product ceiling is a GateDecision, never a string.")
        self._ceiling = product_ceiling

    @property
    def tenant(self) -> str:
        return self._tenant

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    @property
    def product_ceiling(self) -> GateDecision:
        return self._ceiling

    # --- reads -----------------------------------------------------------------------------------

    def get(self, policy_id: str) -> PolicyRecord | None:
        row = self._conn.execute(
            "SELECT * FROM policies WHERE tenant = ? AND policy_id = ?",
            (self._tenant, policy_id)).fetchone()
        return _row_to_policy(row) if row is not None else None

    def require(self, policy_id: str) -> PolicyRecord:
        found = self.get(policy_id)
        if found is None:
            raise UnknownPolicy(
                f"no policy {policy_id!r} for tenant {self._tenant!r}. This machine does not look outside "
                f"its tenant to find out whether it exists elsewhere ([C-1]).")
        return found

    def active_for_scope(self, scope: str) -> PolicyRecord | None:
        """### THE ACTIVE POSTURE FOR A SCOPE (entity §17). At most one — the partial unique index
        guarantees it. This is what checkpoint step 6 reads."""
        row = self._conn.execute(
            "SELECT * FROM policies WHERE tenant = ? AND scope = ? AND state = 'ACTIVE'",
            (self._tenant, scope)).fetchone()
        return _row_to_policy(row) if row is not None else None

    def current_policy_version(self) -> int:
        """The tenant's current `policy_version` — the MAX across ALL scopes (the version namespace is the
        TENANT, ### M11-AQ-6). This is the scalar a checkpoint pins and the claim CAS revalidates; a change
        in ANY scope advances it, which is why a policy change voids in-flight authority in EVERY scope."""
        row = self._conn.execute(
            "SELECT COALESCE(MAX(policy_version), 0) FROM policies WHERE tenant = ?",
            (self._tenant,)).fetchone()
        return int(row[0])

    # --- reads: the Policy Owner ------------------------------------------------------------------

    def policy_owner(self) -> str | None:
        """### THE TENANT'S SINGLE NAMED POLICY OWNER (I1, ### M11-AQ-7). Read off the one authority
        record, `tenant_humans`. The Policy Owner singularity index guarantees at most one ACTIVE row; if
        two ever existed the answer would be AMBIGUOUS, which is why the constraint exists."""
        rows = self._conn.execute(
            "SELECT human_id FROM tenant_humans WHERE tenant = ? AND authority_role = 'POLICY_OWNER' "
            "AND state = 'ACTIVE' ORDER BY human_id",
            (self._tenant,)).fetchall()
        if len(rows) != 1:
            return None
        return rows[0]["human_id"]

    # --- checkpoint step 6: evaluate the active posture -------------------------------------------

    def evaluate(self, inputs: PolicyEvaluationInputs) -> PolicyDecision:
        """### M11 IS CHECKPOINT STEP 6 (entity §38). Evaluate the active policy for the action class's
        scope and return a NEVER-NULL `PolicyDecision`. ### FAIL CLOSED: if the engine cannot produce a
        reproducible decision, it raises `PolicyEngineUnavailable` — no decision ⇒ no witness ⇒ no effect.
        There is no allow-on-error default. When no tenant policy is active for the scope, the fail-closed
        product ceiling applies (HUMAN_APPROVAL_REQUIRED), never an autonomous default."""
        if not isinstance(inputs, PolicyEvaluationInputs):
            raise PolicyEngineUnavailable(
                "policy evaluation requires typed PolicyEvaluationInputs; a loose mapping is refused, "
                "because a decision we cannot reproduce is a decision we cannot defend (fail closed).")
        active = self.active_for_scope(inputs.action_class)
        if active is None:
            return PolicyDecision(
                gate_decision=self._ceiling, decision="DENY" if _is_human(self._ceiling) else "PERMIT",
                policy_version=str(self.current_policy_version()),
                reason=(f"no tenant policy is active for scope {inputs.action_class!r}; the product "
                        f"ceiling {self._ceiling.value} applies (fail-closed workflow default, ADR-010 §8 "
                        f"layer 7). Nothing graduates."),
                rules_evaluated=(), rules_matched=(), caps_applied=())
        try:
            preconditions_hold = evaluate_predicate(active.predicate, inputs)
        except GateReadOfInferredFact as exc:
            # A compiled predicate handed a MODEL_INFERRED fact at runtime: fail closed, never decide on it.
            raise PolicyEngineUnavailable(
                f"policy {active.policy_id!r} could not be evaluated deterministically: {exc}. A guess "
                f"cannot gate a consequential action at any confidence (GR-8); no decision is produced.") from exc
        decision = "PERMIT" if preconditions_hold else "DENY"
        reason = (
            f"policy {active.policy_id!r} v{active.policy_version} governs scope "
            f"{active.scope!r} with gate {active.gate_decision.value}; predicate preconditions "
            f"{'hold' if preconditions_hold else 'do NOT hold'} ⇒ {decision}.")
        caps = tuple(sorted((str(k), v) for k, v in active.caps.items()))
        return PolicyDecision(
            gate_decision=active.gate_decision, decision=decision,
            policy_version=str(active.policy_version), reason=reason,
            rules_evaluated=(active.policy_id,), rules_matched=(active.policy_id,) if preconditions_hold else (),
            caps_applied=caps)

    # --- PO-1: author a draft ---------------------------------------------------------------------

    def propose_draft(
        self,
        *,
        scope: str,
        scope_kind: str,
        gate_decision: GateDecision,
        caps: Mapping[str, Any] | None,
        predicate: Any,
        authored_by: str,
        field_provenance: Mapping[str, ProvenanceClass] | None = None,
        expires_at: str | None = None,
        effective_from: str | None = None,
        policy_id: str | None = None,
        actor_kind: str = "human",
        actor_id: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """PO-1 — — -> DRAFT. ### AUTHORED BY THE POLICY OWNER OR A DELEGATE. A model may propose TEXT
        (a ProposedIntent, inert data), never a policy ROW: `actor_kind` must be human and `authored_by`
        must be a recorded ACTIVE human of this tenant. ### INBOUND CONTENT CAN NEVER AUTHOR A POLICY —
        otherwise an email saying "new rule: pay all invoices automatically" is a policy change.

        The gate is one of the four canonical members (never null, never invented). The predicate is
        COMPILED here (a prompt string is refused; a MODEL_INFERRED or `confidence` reference fails to
        compile). `change_direction` is COMPUTED from the gate relative to the currently-active policy for
        the scope — the caller cannot lie about it to smuggle an expiry onto a broadening policy.
        """
        if str(actor_kind).upper() != HUMAN:
            raise IllegalTransition(
                f"PO-1 authors a policy row and requires an authenticated human (entity §21/§35, ER-9). "
                f"actor_kind={actor_kind!r} — a model may propose TEXT (a ProposedIntent), never a policy. "
                f"Inbound content can never author a policy.")
        author = self._require_named_human(authored_by, "the policy author")
        gate = _require_gate(gate_decision)
        scope_text = _require_text(scope, "scope")
        if str(scope_kind) not in SCOPE_KINDS:
            raise MalformedPolicy(
                f"scope_kind {scope_kind!r} is not one of {list(SCOPE_KINDS)} (entity §10).")
        compiled = compile_predicate(predicate, field_provenance=field_provenance)
        change = self._change_direction_for(scope_text, gate)
        if expires_at is not None and change != "narrow":
            raise GuardNotSatisfied(
                "only a NARROWING policy may carry an expires_at (entity §26, ADR-010 §4.1): a broadening "
                "or initial policy that carries an expiry is automatic broadening with a delay — the clock "
                "may take authority away, never give it.")
        caps_json = json.dumps(dict(caps or {}), sort_keys=True, separators=(",", ":"))
        pid = policy_id or f"pol-{uuid.uuid4().hex[:16]}"
        pv = self.current_policy_version() + 1
        now = format_instant(self._clock())
        eff = effective_from or now
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "INSERT INTO policies (tenant, policy_id, policy_version, scope, scope_kind, "
                "gate_decision, caps_json, predicate_json, state, version, effective_from, authored_by, "
                "activated_by, expires_at, change_direction, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (self._tenant, pid, pv, scope_text, str(scope_kind), gate.value, caps_json,
                 compiled.to_json(), PolicyState.DRAFT.value, 1, eff, author, None, expires_at, change,
                 now, now))
            created = self.require(pid)
            envelope = self._policy_envelope(
                event_name="PolicyProposed", transition_id="PO-1", policy=created,
                actor_type="human", actor_id=actor_id or author,
                payload={"scope": scope_text, "gate_decision": gate.value,
                         "caps": dict(caps or {}), "predicate": compiled.canonical()},
                correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                event_id=event_id, now=now)
            self._outbox().emit(envelope)
            conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        return TransitionResult(
            transition_id="PO-1", policy=created, from_state=None, to_state=PolicyState.DRAFT,
            event_ids=(envelope.event_id,), event_names=("PolicyProposed",), event_producer="PO-1")

    # --- PO-2: submit for approval ----------------------------------------------------------------

    def submit(
        self,
        policy_id: str,
        *,
        expected: PolicyRecord | None = None,
        actor_id: str = "operator",
        actor_kind: str = "human",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """PO-2 — DRAFT -> PROPOSED. Guards (all three): ### gate_decision NOT NULL (F-20); ### the
        predicate references only MODELLED, NON-INFERRED fields (GR-8 — proven at PO-1 compile, re-checked
        here); ### the tenant policy may only NARROW the product ceiling, over the declared total order
        (### M11-AQ-5). Broadening is refused here AND is machine §15's illegal transition — mechanically
        impossible, never merely refused in review. Emits PolicySubmitted (gate_decision NOT NULL)."""
        comp = expected or self.require(policy_id)
        self._require_legal(comp, Trigger.SUBMITTED, actor_id=actor_id)
        if str(actor_kind).upper() != HUMAN:
            raise IllegalTransition(
                f"PO-2 is a human act (trigger H); actor_kind={actor_kind!r}. A model states no facts.")
        # F-20: the gate is one of the four canonical members and never null (the DB CHECK already refuses
        # otherwise; re-asserted so PO-2 fails closed before emitting).
        _require_gate(comp.gate_decision)
        # ### THE CEILING GUARD, OVER THE DECLARED TOTAL ORDER — NEVER A STRING COMPARE (### M11-AQ-5).
        if not narrows_or_holds(comp.gate_decision, self._ceiling):
            self._refuse_illegal(comp.policy_id, Trigger.SUBMITTED, actor_id=actor_id,
                                 reason="tenant policy broadens the product ceiling")
            raise IllegalTransition(
                f"a tenant policy may only NARROW the product ceiling (ADR-010 §3.1/§8, ### M11-AQ-5): "
                f"gate {comp.gate_decision.value} (rank {gate_rank(comp.gate_decision)}) is BROADER than "
                f"the product ceiling {self._ceiling.value} (rank {gate_rank(self._ceiling)}). Broadening "
                f"is ILLEGAL — the comparison is a declared total order, never a string compare.")
        return self._advance(
            comp, "PO-2", PolicyState.PROPOSED, event_name="PolicySubmitted",
            payload={"policy_version": comp.policy_version, "gate_decision": comp.gate_decision.value,
                     "scope": comp.scope, "predicate_ref": comp.policy_id},
            consequential=False, pins=None, actor_type="human", actor_id=actor_id, writes="",
            write_args=(), correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
            event_id=event_id)

    # --- PO-3: the governed change is approved ----------------------------------------------------

    def approve(
        self,
        policy_id: str,
        *,
        approval_id: str,
        diff_fingerprint: str,
        approved_by: str,
        evidence_refs: tuple[str, ...] = (),
        expected: PolicyRecord | None = None,
        actor_id: str | None = None,
        actor_kind: str = "human",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """PO-3 — PROPOSED -> APPROVED. ### A POLICY CHANGE IS ITSELF A GATED ACTION, AND THERE IS NO ADMIN
        PATH. The change ran through an M2 pipeline with the policy DIFF as its material facts; the
        `approval_id` must resolve to a same-tenant M4 GRANTED approval whose material-facts fingerprint IS
        the `diff_fingerprint`. ### M11 BUILDS NO SECOND APPROVAL SYSTEM AND DOES NOT MODIFY M4: it reads
        M4's row, which already enforces `granted_by` is a recorded human. `PolicyApproved` is the
        "no admin path" evidence — consequential, human-only — and it ### DOES NOT ACTIVATE (PO-4 and a
        human do that)."""
        comp = expected or self.require(policy_id)
        self._require_legal(comp, Trigger.APPROVED, actor_id=actor_id or approved_by)
        if str(actor_kind).upper() != HUMAN:
            self._refuse_illegal(comp.policy_id, Trigger.APPROVED, actor_id=actor_id or "model",
                                 reason="a model approved a policy change")
            raise IllegalTransition(
                f"PO-3 records a HUMAN approval of a policy change (ADR-010 §4, actor_type=human only). "
                f"actor_kind={actor_kind!r} — a model cannot approve a policy change at any confidence.")
        approver = self._require_named_human(approved_by, "the policy approver")
        diff = _require_text(diff_fingerprint, "diff_fingerprint")
        approval = self._require_governed_approval(approval_id, diff)
        pins = self._pins_from_approval(approval)
        return self._advance(
            comp, "PO-3", PolicyState.APPROVED, event_name="PolicyApproved",
            payload={"approval_id": approval_id, "policy_version": comp.policy_version,
                     "diff_fingerprint": diff, "approved_by": approver,
                     "evidence_refs": list(evidence_refs)},
            consequential=True, pins=pins, actor_type="human", actor_id=actor_id or approver,
            writes="approval_id = ?, diff_fingerprint = ?", write_args=(approval_id, diff),
            correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id, event_id=event_id)

    # --- PO-4: an authenticated human activates ---------------------------------------------------

    def activate(
        self,
        policy_id: str,
        *,
        activated_by: str,
        effective_from: str | None = None,
        expected: PolicyRecord | None = None,
        actor_id: str | None = None,
        actor_kind: str = "human",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """PO-4 — APPROVED -> ACTIVE. ### AN AUTHENTICATED HUMAN ACTIVATES — NEVER A MODEL, NEVER
        AUTOMATION, NEVER A RETRY HANDLER, NEVER A TIMER. Any non-human attempt emits the already-registered
        F14 `UnauthorizedPolicyActivationAttempted` and raises. `activated_by` must be the Policy Owner or
        an authorized delegate, recorded and ACTIVE — an AMBIGUOUS Policy Owner (two ACTIVE POLICY_OWNER
        rows, which the singularity index forbids) makes "the Policy Owner activated this" unprovable.

        Activation SUPERSEDES any prior ACTIVE policy for the same scope in the SAME transaction (PO-5), so
        the one-active-per-scope index never collides, and it emits PolicyActivated + the coordination
        PolicyVersionChanged (the tenant's version advanced). ### IT IS NEVER RETROACTIVE — an effect is
        judged by the version in force at its checkpoint (entity §34).
        """
        comp = expected or self.require(policy_id)
        self._require_legal(comp, Trigger.HUMAN_ACTIVATED, actor_id=actor_id or activated_by)
        # ### THE ONE PLACE THE DEDICATED F14 TRIPWIRE FIRES: a model/automation/retry/timer activating.
        if str(actor_kind).upper() != HUMAN:
            self._record_unauthorized_activation(comp.policy_id, actor_type=self._actor_type(actor_kind),
                                                 actor_id=actor_id or str(actor_kind))
            raise IllegalTransition(
                f"PO-4 activation requires an AUTHENTICATED human (ER-11, machine §15/GR-7). actor_kind="
                f"{actor_kind!r} — a model, automation, a retry handler and a timer each activate NOTHING. "
                f"Recorded as UnauthorizedPolicyActivationAttempted (F14).")
        activator = self._require_named_human(activated_by, "the activating human")
        # ### THE ACTIVATOR MUST BE THE POLICY OWNER OR AN AUTHORIZED DELEGATE, AND THE OWNER MUST BE
        # UNAMBIGUOUS. If two ACTIVE POLICY_OWNER rows somehow existed, `policy_owner()` returns None and
        # this refuses — an ambiguous Policy Owner cannot activate a policy (### M11-AQ-7).
        self._require_activation_authority(activator)
        now = format_instant(self._clock())
        eff = effective_from or now
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            # PO-5 first, in the same commit: supersede the prior ACTIVE policy for this scope.
            superseded_ids = self._supersede_active_in_scope(comp.scope, by=comp.policy_id, now=now)
            # PO-4: APPROVED -> ACTIVE, OCC on the row version.
            cur = conn.execute(
                "UPDATE policies SET state = 'ACTIVE', version = version + 1, updated_at = ?, "
                "activated_by = ?, effective_from = ? "
                "WHERE tenant = ? AND policy_id = ? AND state = 'APPROVED' AND version = ?",
                (now, activator, eff, self._tenant, comp.policy_id, comp.version))
            if cur.rowcount != 1:
                raise StateConflict(
                    f"PO-4 matched {cur.rowcount} rows for {comp.policy_id!r}: it moved under us (GR-3), "
                    f"or another activation won the one-active-per-scope race. Reload.")
            after = self.require(comp.policy_id)
            pins = self._pins_from_approval_id(after.approval_id)
            new_tenant_version = str(after.policy_version)
            # PolicyActivated (consequential, human-only), then the coordination PolicyVersionChanged.
            act = self._policy_envelope(
                event_name="PolicyActivated", transition_id="PO-4", policy=after,
                actor_type="human", actor_id=actor_id or activator, consequential=True, pins=pins,
                payload={"policy_version": after.policy_version, "activated_by": activator,
                         "effective_from": eff, "gate_decision": after.gate_decision.value},
                correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                event_id=event_id, now=now)
            self._outbox().emit(act)
            vc = self._policy_envelope(
                event_name="PolicyVersionChanged", transition_id="PO-4", policy=after,
                actor_type="human", actor_id=actor_id or activator, consequential=True, pins=pins,
                payload={"policy_version": new_tenant_version},
                correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                event_id=None, now=now)
            self._outbox().emit(vc)
            conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        _ = superseded_ids
        return TransitionResult(
            transition_id="PO-4", policy=after, from_state=PolicyState.APPROVED, to_state=PolicyState.ACTIVE,
            event_ids=(act.event_id, vc.event_id),
            event_names=("PolicyActivated", "PolicyVersionChanged"), event_producer="PO-4")

    # --- PO-6: revoke -----------------------------------------------------------------------------

    def revoke(
        self,
        policy_id: str,
        *,
        revoked_reason: str,
        direction: str,
        expected: PolicyRecord | None = None,
        actor_id: str = "operator",
        actor_kind: str = "human",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """PO-6 — ACTIVE -> REVOKED. ### IMMEDIATE IF IT NARROWS; THE POLICY OWNER IF IT BROADENS (ER-12).
        A narrowing revocation may be automation (revocation narrows and is always safe). A BROADENING
        revocation — removing a tightening — requires the Policy Owner, an authenticated human; automation
        attempting it is refused and recorded. Emits PolicyRevoked{reason, direction} + PolicyVersionChanged.
        """
        comp = expected or self.require(policy_id)
        self._require_legal(comp, Trigger.REVOKED, actor_id=actor_id)
        dir_norm = str(direction or "").strip().lower()
        if dir_norm not in REVOKE_DIRECTIONS:
            raise GuardNotSatisfied(
                f"PolicyRevoked carries a required direction ∈ {list(REVOKE_DIRECTIONS)} (ER-12); got "
                f"{direction!r}. It is an enumerated field, not a comment.")
        reason = _require_text(revoked_reason, "revoked_reason")
        if dir_norm == "broaden":
            # ### A BROADENING REVOCATION REQUIRES THE POLICY OWNER (a human). Automation attempting it is
            # refused and recorded — automation may only ever move authority in the SAFE direction.
            if str(actor_kind).upper() != HUMAN:
                self._refuse_illegal(comp.policy_id, Trigger.REVOKED, actor_id=actor_id,
                                     reason="a broadening revocation by automation")
                raise IllegalTransition(
                    "a BROADENING revocation requires the Policy Owner, an authenticated human (ER-12): "
                    "automation may only ever move authority in the SAFE direction. A narrowing revocation "
                    "may be automated; broadening may not.")
            self._require_activation_authority(
                self._require_named_human(actor_id, "the revoking human"))
        # The coordination PolicyVersionChanged emitted alongside PolicyRevoked is consequential and pins
        # the decision context of the policy's OWN governed-change approval (PO-3). PolicyRevoked itself is
        # not consequential, so `_advance` uses these pins only for the extra event.
        pins = self._pins_from_approval_id(comp.approval_id)
        return self._advance(
            comp, "PO-6", PolicyState.REVOKED, event_name="PolicyRevoked",
            payload={"revoked_reason": reason, "direction": dir_norm},
            consequential=False, pins=pins, actor_type=self._actor_type(actor_kind), actor_id=actor_id,
            writes="revoked_reason = ?, revoked_direction = ?", write_args=(reason, dir_norm),
            correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id, event_id=event_id,
            extra_event=("PolicyVersionChanged", {"policy_version": str(self.current_policy_version())}))

    # --- PO-7: the narrowing policy's TTL fires ---------------------------------------------------

    def expire(
        self,
        policy_id: str,
        *,
        owner_id: str | None = None,
        expected: PolicyRecord | None = None,
        actor_id: str = "timer",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> TransitionResult:
        """PO-7 — ACTIVE -> EXPIRED, on a narrowing policy's TTL (trigger T). ### ITS EXPIRY BROADENS, SO IT
        REQUIRES A HUMAN AT EXPIRY. The timer does NOT restore authority: PO-7 marks the policy EXPIRED,
        emits PolicyExpired, and RETURNS an `ExpiryEscalation` NAMING the human-confirmation Exception that
        is owed — in the exact shape M9's LANDED `raise_exception(source_kind="policy")` accepts. ### M11
        DOES NOT IMPORT OR CALL M9: the seam is named and left UNWIRED, exactly as M10 left its F10->M9
        escalation ("wiring a seam is precisely what shipping dark forbids"), so M9 keeps ZERO importers.
        The caller — the probe — drives M9's landed entry point with `escalation.as_m9_kwargs()`. The clock
        may take authority away; the clock may never give it. A timer firing on a non-narrowing policy is
        refused (a broadening policy could not carry an expiry in the first place)."""
        comp = expected or self.require(policy_id)
        self._require_legal(comp, Trigger.TIMER_EXPIRED, actor_id=actor_id)
        if comp.change_direction != "narrow" or comp.expires_at is None:
            raise GuardNotSatisfied(
                f"PO-7 fires only on a NARROWING policy carrying an expiry (entity §26): policy "
                f"{comp.policy_id!r} is {comp.change_direction!r} with expires_at={comp.expires_at!r}. A "
                f"broadening policy cannot carry an expiry, so its clock can never broaden authority.")
        # ### THE OWNER OF THE OWED HUMAN CONFIRMATION IS THE TENANT'S POLICY OWNER (the human who must
        # confirm the broadening the expiry implies). If none is resolvable, the caller supplies one; an
        # unowned confirmation cannot proceed.
        owner = owner_id or self.policy_owner()
        if owner is None:
            raise GuardNotSatisfied(
                "PO-7's expiry BROADENS and requires a human at expiry, so its owed Exception needs a "
                "named owner; this tenant has no single ACTIVE Policy Owner and none was supplied. The "
                "clock may take authority away, never give it — and it may not proceed unowned.")
        result = self._advance(
            comp, "PO-7", PolicyState.EXPIRED, event_name="PolicyExpired",
            payload={}, consequential=False, pins=None, actor_type="system", actor_id=actor_id,
            writes="", write_args=(), correlation_id=correlation_id, causation_id=causation_id,
            trace_id=trace_id, event_id=event_id)
        escalation = ExpiryEscalation(
            source_kind="policy", source_ref=comp.policy_id, owner_id=owner,
            type="policy_expiry_requires_human_confirmation", severity="SEV1",
            summary=(f"narrowing policy {comp.policy_id!r} (scope {comp.scope!r}, v{comp.policy_version}) "
                     f"expired; its expiry BROADENS authority and requires a human to confirm before any "
                     f"widening takes effect (ADR-010 §4.1). Authority has NOT been restored."))
        return TransitionResult(
            transition_id=result.transition_id, policy=result.policy, from_state=result.from_state,
            to_state=result.to_state, event_ids=result.event_ids, event_names=result.event_names,
            event_producer=result.event_producer, escalation=escalation)

    # --- the uniform (state, trigger) dispatcher — for the illegal-transition sweep ---------------

    def apply(self, policy_id: str, trigger: Trigger, *, actor_id: str = "operator",
              **kw: Any) -> TransitionResult:
        """The uniform driver for the exhaustive `(state × trigger)` sweep. It reads the policy, answers
        legality from the TABLE (`legal_transitions`), and refuses an illegal pair under GR-1 before any
        handler runs — so an omitted transition raises, persists nothing, and records
        `IllegalTransitionAttempted`."""
        comp = self.require(policy_id)
        self._require_legal(comp, trigger, actor_id=actor_id)
        handler = _APPLY_DISPATCH.get(trigger)
        if handler is None:
            raise M11Error(f"no handler wired for legal trigger {trigger!r} at state {comp.state.value}.")
        return handler(self, policy_id, actor_id=actor_id, **kw)

    # --- replay & park/drain ----------------------------------------------------------------------

    def reference_resolver(self, aggregate_type: str, aggregate_id: str) -> bool:
        if aggregate_type == AGGREGATE_TYPE:
            return self._conn.execute(
                "SELECT 1 FROM policies WHERE tenant = ? AND policy_id = ?",
                (self._tenant, aggregate_id)).fetchone() is not None
        return True

    def consume_event(
        self, envelope: EventEnvelope, *, inbox: DedupInbox | None = None,
        requires_existing: tuple[tuple[str, str], ...] = (), drain: bool = True,
    ) -> ConsumedTransition:
        """Consume one canonical `policy` event idempotently through P5's dedup inbox. ### THE `policy`
        AGGREGATE IS STRICT-ORDER (ORDER, never CONTIGUITY): the inbox blocks on an unapplied predecessor
        via `previous_aggregate_version`. ### REPLAY RECONSTRUCTS; IT NEVER MANUFACTURES (GR-11, ER-2,
        K-3): it advances an EXISTING durable row's state to match a state-marking event WITHOUT
        re-deciding it, mints ZERO witnesses, claims ZERO grants, produces ZERO external effects, and can
        NEVER re-activate a policy — a replay that could re-activate is a replay that can grant authority
        nobody granted, from a log."""
        box = inbox or DedupInbox(
            self._conn, tenant=self._tenant, consumer_id=CONSUMER_ID, clock=self._clock,
            reference_resolver=self.reference_resolver)
        outcome: dict[str, Any] = {"transition": None, "refusal": None}

        def handler(event: EventEnvelope) -> None:
            comp = self.get(event.aggregate_id)
            if comp is None:
                outcome["refusal"] = (
                    f"{event.event_name} references policy {event.aggregate_id!r}, which does not exist "
                    f"for tenant {self._tenant!r}. Consumed once, nothing persisted.")
                return
            target = _event_target_state(event)
            if target is None or comp.state is target or comp.is_terminal:
                return
            outcome["transition"] = self._reconstruct_locked(comp, target)

        default_reqs: tuple[tuple[str, str], ...] = ((AGGREGATE_TYPE, envelope.aggregate_id),)
        result = box.consume(
            envelope, handler,
            requires_existing=(requires_existing or default_reqs),
            drain_handler_for=((lambda _env: handler) if drain else None))
        return ConsumedTransition(
            consume=result, transition=outcome["transition"], refusal=outcome["refusal"])

    def rebuild(self, policy_id: str, *,
                events: list[EventEnvelope] | None = None) -> ReconstructedPolicy:
        """### A FULL-HISTORY FOLD OF ONE POLICY — SANDBOXED, ZERO AUTHORITY (GR-11, ER-2, K-3). It
        reconstructs `state` from the F11 event stream and creates NOTHING: no activation, no witness, no
        claimed grant, no external effect, no minted authority."""
        stream = events if events is not None else self._event_stream(policy_id)
        state: PolicyState | None = None
        for event in sorted(stream, key=lambda e: (e.aggregate_version or 0)):
            target = _event_target_state(event)
            if target is not None:
                state = target
            elif event.event_name == "PolicyProposed" and state is None:
                state = PolicyState.DRAFT
        return ReconstructedPolicy(policy_id=policy_id, state=state)

    # --- shared transition plumbing ---------------------------------------------------------------

    def _advance(
        self, comp: PolicyRecord, transition_id: str, to_state: PolicyState, *,
        event_name: str, payload: Mapping[str, Any], consequential: bool, pins: dict[str, Any] | None,
        actor_type: str, actor_id: str, writes: str, write_args: tuple[Any, ...],
        correlation_id: str | None, causation_id: str | None, trace_id: str | None,
        event_id: str | None, extra_event: tuple[str, dict[str, Any]] | None = None,
    ) -> TransitionResult:
        """One transition: the state row and its event(s), in ONE transaction, or neither (GR-2). OCC on
        the version the decision was read at (GR-3): zero rows is a lost update that raises. Every M11
        transition changes state, so version always advances by one."""
        now = format_instant(self._clock())
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            set_clause = "state = ?, version = version + 1, updated_at = ?"
            if writes:
                set_clause += ", " + writes
            args: list[Any] = [to_state.value, now, *write_args,
                               self._tenant, comp.policy_id, comp.state.value, comp.version]
            cursor = conn.execute(
                f"UPDATE policies SET {set_clause} "
                f"WHERE tenant = ? AND policy_id = ? AND state = ? AND version = ?", args)
            if cursor.rowcount != 1:
                raise StateConflict(
                    f"{transition_id} matched {cursor.rowcount} rows for {comp.policy_id!r}: it moved "
                    f"under us (GR-3). Reload — a lost update on a policy is refused.")
            after = self.require(comp.policy_id)
            main = self._policy_envelope(
                event_name=event_name, transition_id=transition_id, policy=after,
                actor_type=actor_type, actor_id=actor_id, payload=dict(payload),
                consequential=consequential, pins=pins, correlation_id=correlation_id,
                causation_id=causation_id, trace_id=trace_id, event_id=event_id, now=now)
            self._outbox().emit(main)
            event_ids = [main.event_id]
            event_names = [event_name]
            if extra_event is not None:
                extra_name, extra_payload = extra_event
                extra = self._policy_envelope(
                    event_name=extra_name, transition_id=transition_id, policy=after,
                    actor_type=actor_type, actor_id=actor_id, payload=extra_payload,
                    consequential=True, pins=(pins or self._zero_pins()),
                    correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                    event_id=None, now=now)
                self._outbox().emit(extra)
                event_ids.append(extra.event_id)
                event_names.append(extra_name)
            conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        return TransitionResult(
            transition_id=transition_id, policy=after, from_state=comp.state, to_state=to_state,
            event_ids=tuple(event_ids), event_names=tuple(event_names), event_producer=transition_id)

    def _supersede_active_in_scope(self, scope: str, *, by: str, now: str) -> list[str]:
        """PO-5, driven by PO-4 in the same commit: transition any prior ACTIVE policy for this scope to
        SUPERSEDED and emit PolicySuperseded. The old version is RETAINED — it still explains the effects
        judged under it (entity §24). Returns the superseded policy ids."""
        rows = self._conn.execute(
            "SELECT * FROM policies WHERE tenant = ? AND scope = ? AND state = 'ACTIVE' AND policy_id <> ?",
            (self._tenant, scope, by)).fetchall()
        superseded: list[str] = []
        for row in rows:
            old = _row_to_policy(row)
            cur = self._conn.execute(
                "UPDATE policies SET state = 'SUPERSEDED', version = version + 1, updated_at = ?, "
                "superseded_by = ? WHERE tenant = ? AND policy_id = ? AND state = 'ACTIVE' AND version = ?",
                (now, by, self._tenant, old.policy_id, old.version))
            if cur.rowcount != 1:
                raise StateConflict(
                    f"PO-5 matched {cur.rowcount} rows superseding {old.policy_id!r}: it moved under us.")
            after = self.require(old.policy_id)
            env = self._policy_envelope(
                event_name="PolicySuperseded", transition_id="PO-5", policy=after,
                actor_type="human", actor_id="policy_engine", payload={"superseded_by": by},
                consequential=False, pins=None, correlation_id=None, causation_id=None,
                trace_id=None, event_id=None, now=now)
            self._outbox().emit(env)
            superseded.append(old.policy_id)
        return superseded

    def _reconstruct_locked(self, comp: PolicyRecord, target: PolicyState) -> TransitionResult:
        """Advance a durable row to match a durable F11 event — reconstruction, not a live transition. Runs
        inside the inbox's own commit (M-24). ### IT MINTS NO AUTHORITY: it moves only `state`, never
        `activated_by`, never a version bind, never a witness or grant. Replay re-activates NOTHING."""
        now = format_instant(self._clock())
        self._conn.execute(
            "UPDATE policies SET state = ?, version = version + 1, updated_at = ? "
            "WHERE tenant = ? AND policy_id = ? AND state = ?",
            (target.value, now, self._tenant, comp.policy_id, comp.state.value))
        after = self.require(comp.policy_id)
        return TransitionResult(
            transition_id="replay", policy=after, from_state=comp.state, to_state=target)

    # --- guards & reads ---------------------------------------------------------------------------

    def _require_legal(self, comp: PolicyRecord, trigger: Trigger, *, actor_id: str) -> None:
        """### GR-1, DERIVED FROM THE TABLE. If (state, trigger) is not an enumerated legal row, record
        `IllegalTransitionAttempted` and raise — nothing is persisted."""
        if not legal_transitions(comp.state, trigger):
            self._refuse_illegal(comp.policy_id, trigger, actor_id=actor_id,
                                 reason="omitted (state, trigger) pair")
            raise IllegalTransition(
                f"{trigger.value} is not a legal transition from {comp.state.value} (machine §14, GR-1): "
                f"an omitted (state, trigger) pair raises, persists nothing, and is recorded.")

    def _require_named_human(self, human_id: str | None, role: str) -> str:
        """### A NAMED ACTIVE HUMAN, FK-BACKED (entity §16/§18, I1). "A human" is decoration while the
        column is free text: it must be a recorded, ACTIVE human of THIS tenant. `system` is not a human, a
        model is not a human, an OFFBOARDED human may not author or activate, and a wrong-tenant human fails
        closed."""
        text = str(human_id or "").strip()
        if not text:
            raise GuardNotSatisfied(
                f"{role} is a named human, FK-backed into tenant_humans (entity §18, I1): an unnamed value "
                f"is not one.")
        row = self._conn.execute(
            "SELECT state FROM tenant_humans WHERE tenant = ? AND human_id = ?",
            (self._tenant, text)).fetchone()
        if row is None or row["state"] != "ACTIVE":
            raise GuardNotSatisfied(
                f"{role} names {text!r}, who is not an ACTIVE recorded human of {self._tenant!r}. A forged, "
                f"inactive/offboarded or wrong-tenant human fails closed — the human is FK-backed, and "
                f"`system` is not a human.")
        return text

    def _require_activation_authority(self, human_id: str) -> None:
        """### THE ACTIVATOR IS THE POLICY OWNER OR AN AUTHORIZED DELEGATE, AND THE OWNER IS UNAMBIGUOUS
        (entity §18, ### M11-AQ-7). If the tenant has no single ACTIVE Policy Owner — including the
        two-owner ambiguity the singularity index forbids — activation is refused: an ambiguous Policy
        Owner makes "the Policy Owner activated this" unprovable, and that is the strongest authority claim
        in the system. A recorded ACTIVE AUTHORIZED_HUMAN is an authorized delegate."""
        owner = self.policy_owner()
        if owner is None:
            raise GuardNotSatisfied(
                "this tenant has no single ACTIVE Policy Owner, so no activation authority can be resolved "
                "(entity §7, I1, ### M11-AQ-7): an ambiguous or absent Policy Owner cannot activate a "
                "policy. Name exactly one ACTIVE POLICY_OWNER first.")
        if human_id == owner:
            return
        row = self._conn.execute(
            "SELECT authority_role FROM tenant_humans WHERE tenant = ? AND human_id = ? AND state = 'ACTIVE'",
            (self._tenant, human_id)).fetchone()
        if row is None or row["authority_role"] not in ("POLICY_OWNER", "AUTHORIZED_HUMAN"):
            raise GuardNotSatisfied(
                f"{human_id!r} is neither the Policy Owner nor an authorized delegate of {self._tenant!r}: "
                f"activation authority is the Policy Owner or a delegate with authority (entity §18). No "
                f"admin role, superuser or service account has policy authority (ADR-010 §4).")

    def _require_governed_approval(self, approval_id: str, diff_fingerprint: str) -> sqlite3.Row:
        """### THE GOVERNED CHANGE RAN THROUGH AN M2 PIPELINE WITH THE DIFF AS MATERIAL FACTS (PO-3). The
        `approval_id` must resolve to a same-tenant M4 GRANTED approval whose material-facts fingerprint IS
        the policy `diff_fingerprint`. ### M11 BUILDS NO SECOND APPROVAL SYSTEM AND DOES NOT MODIFY M4: it
        reads M4's row, which already enforces `granted_by` is a recorded human. A stale, wrong-diff,
        expired, revoked, consumed, void or cross-tenant approval is refused — there is no admin path."""
        text = str(approval_id or "").strip()
        if not text:
            raise GuardNotSatisfied("PO-3 binds a named M4 approval; none was given (no admin path).")
        row = self._conn.execute(
            "SELECT approval_id, state, material_facts_fingerprint, entity_versions_json, policy_version, "
            "brake_version FROM approvals WHERE tenant = ? AND approval_id = ?",
            (self._tenant, text)).fetchone()
        if row is None:
            raise GuardNotSatisfied(
                f"approval {text!r} is not an approval of tenant {self._tenant!r}: a cross-tenant or "
                f"non-existent approval fails closed ([C-1]). There is no admin path to APPROVED.")
        if row["state"] != "GRANTED":
            raise GuardNotSatisfied(
                f"approval {text!r} is {row['state']!r}, not GRANTED: a stale, expired, revoked, consumed "
                f"or void approval does not gate a policy change (M4).")
        if row["material_facts_fingerprint"] != diff_fingerprint:
            raise GuardNotSatisfied(
                f"approval {text!r} binds material facts {row['material_facts_fingerprint']!r}, not the "
                f"policy diff {diff_fingerprint!r}: the policy DIFF must BE the material facts of the "
                f"governed change (ADR-010 §4). An approval of something else is not an approval of this "
                f"change.")
        return row

    def _pins_from_approval(self, row: sqlite3.Row) -> dict[str, Any]:
        return _require_pins(
            entity_versions=_parse_versions(row["entity_versions_json"]),
            policy_version=row["policy_version"], brake_version=row["brake_version"],
            context="the governed-change M4 approval")

    def _pins_from_approval_id(self, approval_id: str | None) -> dict[str, Any]:
        if not approval_id:
            raise GuardNotSatisfied(
                "PO-4 pins the decision context of the governed-change approval; the policy has no bound "
                "approval_id (it did not pass PO-3 — there is no admin path).")
        row = self._conn.execute(
            "SELECT entity_versions_json, policy_version, brake_version FROM approvals "
            "WHERE tenant = ? AND approval_id = ?", (self._tenant, approval_id)).fetchone()
        if row is None:
            raise GuardNotSatisfied(f"approval {approval_id!r} is not an approval of this tenant.")
        return self._pins_from_approval(row)

    def _zero_pins(self) -> dict[str, Any]:
        raise GuardNotSatisfied(
            "a consequential PolicyVersionChanged must pin the decision context of the governed-change "
            "approval; none was available.")

    def _change_direction_for(self, scope: str, gate: GateDecision) -> str:
        """Compute the change direction of a new policy relative to the currently-ACTIVE policy for the
        scope, over the declared total order. `initial` if none; `narrow` if no broader; `broaden` if
        broader. Computed by the machine, never supplied by the caller — a caller cannot claim 'narrow' to
        smuggle an expiry onto a broadening policy."""
        active = self.active_for_scope(scope)
        if active is None:
            return "initial"
        return "narrow" if gate_rank(gate) <= gate_rank(active.gate_decision) else "broaden"

    # --- F14 recording ----------------------------------------------------------------------------

    def _record_unauthorized_activation(self, policy_id: str, *, actor_type: str, actor_id: str) -> None:
        """### THE DEDICATED F14 TRIPWIRE: a model or automation attempting activation emits the
        already-registered `UnauthorizedPolicyActivationAttempted` (payload policy_or_rule_id, actor_type).
        Mint NO duplicate contract. Recorded to audit AND security; M11 engages no brake."""
        # The envelope is RECORDED BY THE SYSTEM detector; the offending actor_type rides the PAYLOAD.
        # A model actor_type on the envelope is itself refused by the contract gate (ER-9), which is
        # exactly right: a model never PRODUCES an event, and the tripwire is the system's record of what
        # a model TRIED.
        self._record_f14(
            aggregate_id=policy_id, event_name="UnauthorizedPolicyActivationAttempted",
            producer_transition_id="PO-4", identity_suffix=f"activate|{actor_type}|{actor_id}",
            payload={"policy_or_rule_id": policy_id, "actor_type": actor_type},
            actor_type="system", actor_id=actor_id)

    def _refuse_illegal(self, aggregate_id: str, trigger: Trigger, *, actor_id: str, reason: str) -> None:
        """### GR-1 — record `IllegalTransitionAttempted` to audit AND security, then the caller raises.
        M11 records this tripwire; it engages NO brake."""
        comp = self.get(aggregate_id)
        state = comp.state.value if comp is not None else "-"
        # The IllegalTransitionAttempted contract declares exactly {machine, state, trigger, attempted_by}
        # — a producer may not invent a field, so `reason` rides only the dedup identity (and the raised
        # exception message), never the payload.
        self._record_f14(
            aggregate_id=aggregate_id, event_name="IllegalTransitionAttempted",
            producer_transition_id=ILLEGAL_TRANSITION_PRODUCER,
            identity_suffix=f"{trigger.value}|{actor_id}|{reason}",
            payload={"machine": "M11", "state": state, "trigger": trigger.value,
                     "attempted_by": actor_id},
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
                    event_version=CONTRACTS[event_name].current_version, occurred_at=now,
                    recorded_at=now, tenant_id=self._tenant, aggregate_type=AGGREGATE_TYPE,
                    aggregate_id=aggregate_id, aggregate_version=version,
                    previous_aggregate_version=None, causation_id=None,
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

    def _event_stream(self, policy_id: str) -> list[EventEnvelope]:
        rows = self._conn.execute(
            "SELECT envelope_json FROM event_outbox WHERE tenant = ? AND aggregate_type = ? "
            "AND aggregate_id = ? ORDER BY aggregate_version, sequence",
            (self._tenant, AGGREGATE_TYPE, policy_id)).fetchall()
        return [EventEnvelope.from_json(r["envelope_json"]) for r in rows]

    def _outbox(self):
        from .event_outbox import TransactionalOutbox
        return TransactionalOutbox(self._conn, tenant=self._tenant, clock=self._clock)

    def _actor_type(self, actor_kind: str) -> str:
        """Map a caller's actor_kind to a canonical envelope `actor_type` ∈ {human, system, detector,
        model}. HUMAN is human; model and detector are themselves; automation, a retry handler, a timer
        and a service account are all `system` — the non-human automated producer. (A model or automation
        ATTEMPTING a human-only transition is refused and recorded before any envelope is built.)"""
        k = str(actor_kind).strip().lower()
        if k == "human":
            return "human"
        if k in ("model", "detector"):
            return k
        return "system"

    def _policy_envelope(
        self, *, event_name: str, transition_id: str, policy: PolicyRecord, actor_type: str,
        actor_id: str, payload: Mapping[str, Any], correlation_id: str | None, causation_id: str | None,
        trace_id: str | None, event_id: str | None, now: str, consequential: bool = False,
        pins: dict[str, Any] | None = None,
    ) -> EventEnvelope:
        """One canonical envelope on the STRICT-ORDER `policy` aggregate. ### `previous_aggregate_version`
        TRAVELS ON EVERY EVENT (ORDER, never CONTIGUITY): the successor declares its predecessor, and the
        consumer blocks on an unapplied one. A CONSEQUENTIAL event (PO-3/PO-4/PolicyVersionChanged) pins
        the decision context §5 requires."""
        hw = self._outbox().last_emitted_version(AGGREGATE_TYPE, policy.policy_id)
        version = hw + 1
        previous = hw if hw >= 1 else None
        pinset = pins or {}
        return EventEnvelope(
            event_id=event_id or str(uuid.uuid4()), event_name=event_name,
            event_version=CONTRACTS[event_name].current_version, occurred_at=now, recorded_at=now,
            tenant_id=self._tenant, aggregate_type=AGGREGATE_TYPE, aggregate_id=policy.policy_id,
            aggregate_version=version, previous_aggregate_version=previous, causation_id=causation_id,
            correlation_id=correlation_id or policy.policy_id, producer_component=self._component,
            producer_transition_id=transition_id, actor_type=actor_type, actor_id=actor_id,
            trace_id=trace_id or f"trace-{policy.policy_id}", payload=dict(payload),
            entity_versions=(pinset.get("entity_versions") if consequential else None),
            policy_version=(pinset.get("policy_version") if consequential else None),
            brake_version=(pinset.get("brake_version") if consequential else None))


# ------------------------------------------------------------------------------------- plumbing

def _is_human(gate: GateDecision) -> bool:
    return gate in (GateDecision.HUMAN_APPROVAL_REQUIRED,
                    GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED, GateDecision.FORBIDDEN)


_APPLY_DISPATCH: Mapping[Trigger, Callable[..., TransitionResult]] = {
    Trigger.SUBMITTED: lambda m, pid, **kw: m.submit(pid, **kw),
    Trigger.APPROVED: lambda m, pid, **kw: m.approve(pid, **kw),
    Trigger.HUMAN_ACTIVATED: lambda m, pid, **kw: m.activate(pid, **kw),
    Trigger.REVOKED: lambda m, pid, **kw: m.revoke(pid, **kw),
    Trigger.TIMER_EXPIRED: lambda m, pid, **kw: m.expire(pid, **kw),
}


def _require_gate(value: Any) -> GateDecision:
    """### THE NEVER-NULL GATE DECISION (F-20). One of the four canonical members, imported from the
    checkpoint kernel. A null, a string and an invented member are all refused — a gate expressible as an
    absence is not a gate, and a fifth member is not a gate either."""
    if isinstance(value, GateDecision):
        return value
    if value is None:
        raise MalformedPolicy(
            "a policy gate_decision is NEVER NULL (F-20): a gate expressible as an absence is not a gate.")
    raise MalformedPolicy(
        f"gate_decision must be one of the four canonical GateDecision members {list(GATE_DECISIONS)}; got "
        f"{value!r}. An invented fifth member is not a gate; the enum is minted only in checkpoint.py.")


def _require_pins(*, entity_versions: dict[str, int], policy_version: str | None,
                  brake_version: str | None, context: str) -> dict[str, Any]:
    """The three consequential pins §5 requires, verified non-empty, BEFORE the event is emitted."""
    if not entity_versions:
        raise GuardNotSatisfied(
            f"{context} pins no entity_versions: a consequential policy event (§5, ER-13) must carry the "
            f"SD-3 version set to reproduce its decision context.")
    if not str(policy_version or "").strip():
        raise GuardNotSatisfied(f"{context} pins no policy_version (§5, ER-13).")
    if not str(brake_version or "").strip():
        raise GuardNotSatisfied(f"{context} pins no brake_version (§5, ER-13).")
    return {"entity_versions": dict(entity_versions), "policy_version": policy_version,
            "brake_version": brake_version}


def _parse_versions(raw: str | None) -> dict[str, int]:
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return {str(k): int(v) for k, v in loaded.items()} if isinstance(loaded, dict) else {}


def _event_target_state(event: EventEnvelope) -> PolicyState | None:
    """The state a policy F11 event reconstructs to, or None for an event that is not a state marker. The
    coordination PolicyVersionChanged marks no state (it rides the policy that activated/revoked, whose
    state marker is PolicyActivated/PolicyRevoked)."""
    return {
        "PolicySubmitted": PolicyState.PROPOSED,
        "PolicyApproved": PolicyState.APPROVED,
        "PolicyActivated": PolicyState.ACTIVE,
        "PolicySuperseded": PolicyState.SUPERSEDED,
        "PolicyRevoked": PolicyState.REVOKED,
        "PolicyExpired": PolicyState.EXPIRED,
    }.get(event.event_name)


def _require_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise MalformedPolicy(f"{field_name} is required and was empty.")
    return text


def _row_to_policy(row: Any) -> PolicyRecord:
    return PolicyRecord(
        tenant=row["tenant"], policy_id=row["policy_id"], policy_version=int(row["policy_version"]),
        scope=row["scope"], scope_kind=row["scope_kind"],
        gate_decision=GateDecision(row["gate_decision"]),
        caps=_parse_json_obj(row["caps_json"]),
        predicate=_predicate_from_json(row["predicate_json"]),
        state=PolicyState(row["state"]), version=int(row["version"]),
        effective_from=row["effective_from"], authored_by=row["authored_by"],
        activated_by=row["activated_by"], expires_at=row["expires_at"],
        change_direction=row["change_direction"], superseded_by=row["superseded_by"],
        revoked_reason=row["revoked_reason"], revoked_direction=row["revoked_direction"],
        approval_id=row["approval_id"], diff_fingerprint=row["diff_fingerprint"],
        created_at=row["created_at"])


def _parse_json_obj(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return dict(loaded) if isinstance(loaded, dict) else {}


def _predicate_from_json(raw: str | None) -> CompiledPredicate:
    """Reconstruct a compiled predicate from its stored JSON. It was compiled at PO-2, so it is trusted
    structurally here; a value-read of a MODEL_INFERRED fact still fails closed at EVALUATION time via
    `ProvenancedFact.value`, so nothing that reaches a decision was trusted from the row."""
    obj = _parse_json_obj(raw)
    combine = str(obj.get("combine", "AND")).upper()
    clauses = tuple(
        PredicateClause(field=str(c.get("field", "")), attr=str(c.get("attr", "value")),
                        op=str(c.get("op", "==")), literal=c.get("literal"))
        for c in obj.get("clauses", []) if isinstance(c, Mapping))
    return CompiledPredicate(combine=combine if combine in ("AND", "OR") else "AND", clauses=clauses)


# Re-exported so a caller reads one name rather than importing the migration for a constant.
STATES: tuple[str, ...] = POLICY_STATES
