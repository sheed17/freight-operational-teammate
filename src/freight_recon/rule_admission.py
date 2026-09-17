"""U8.2 — THE STANDING-RULE ADMISSION LAYER: ADR-010 §8 LAYER 6, composed into the U8.1
`PolicyDecision` so that a tenant's compiled M12 Rules become REAL deterministic evidence in the
checkpoint's step-6 decision — never a decorative field.

    ### A STANDING RULE SITS AT PRECEDENCE LAYER 6. IT MAY NARROW. IT MAY OVERRIDE NOTHING ABOVE IT.
    ### A RULE MAY NEVER BROADEN AUTHORITY, AND MAY NEVER FLIP A DENY INTO A PERMIT.
    ### A RULE THAT CANNOT BE EVALUATED DETERMINISTICALLY FAILS CLOSED — NO DECISION, NO WITNESS.
    ### THE MODEL, AUTOMATION, A RETRY AND REPLAY MAY PROPOSE OR OBSERVE; THEY NEVER ACTIVATE OR EVALUATE.

### WHAT THIS MODULE IS, AND WHY IT IS NOT A SECOND ANYTHING.

M12 (`rule.py`) is the LANDED canonical Durable Machine for the Rule (P6-CP-12): an owner's sentence
either compiles into a registered, versioned, deterministic decision procedure WITH AN ID, or it is
honestly refused (ADR-010 §6). It compiles, confirms and activates through its own eight-state
lifecycle, routes a rule-vs-rule clash through M7's landed Conflict authority (RU-3), and refuses any
non-human activation. It shipped DARK: nothing under `src/freight_recon/` imported it.

### THIS MODULE IS THE FIRST PRODUCTION IMPORTER OF M12, AND IT IS ONLY A COMPOSITION. It creates no
entity, no second lifecycle, no second conflict engine, no second precedence engine and no gate
authority. It reads the tenant's ALREADY-ACTIVE rules for a scope and folds their deterministic
verdicts into the `PolicyDecision` M11 / `policy_admission.py` already produce — exactly as
`policy_admission.py` is the first production importer of M11 and composes the tenant posture without
becoming a second policy engine.

### IT NAMES NO GATE MEMBER, ON PURPOSE. A GATE_PRECONDITION / CONSTRAINT rule's outcome is the
ABSTRACT effect vocabulary (`DENY` / `REQUIRE_HUMAN_APPROVAL` / `PERMIT`), never a `GateDecision`
member. This layer therefore carries NO gate-decision token in executable code (`eval/phase0/
gate_scan`) — `checkpoint.py` stays the SOLE minter of a gate decision, and the R-07 gate-runtime
allowlist is UNCHANGED by U8.2. Concretely: a standing rule only ever tightens the DECISION (turns a
PERMIT into a DENY, or is refused for trying to loosen); it never rewrites the gate member the tenant
posture set. Because nothing graduates in this slice, every checkpoint-evaluated action class is
already at or below `HUMAN_APPROVAL_REQUIRED`, so a `REQUIRE_HUMAN_APPROVAL` rule's requirement is
already carried by the effective gate — it is recorded as MATCHED evidence and changes no member.

### PRECEDENCE — A RULE IS LAYER 6 (ADR-010 §8), AND EVERYTHING IT DOES IS A NARROWING.

The tenant's posture (layer 5) is already at or below the product ceiling (layers 2 + 4). A standing
rule may only make that decision MORE restrictive:

  * a rule whose deterministic effect is **DENY** turns the decision into DENY — the action is
    blocked at step 6, no witness, no grant;
  * a rule whose effect is **REQUIRE_HUMAN_APPROVAL** is recorded as MATCHED; its requirement (a
    human) is already enforced by the effective human gate, and it never loosens anything;
  * a rule whose effect is **PERMIT** is a BROADENING effect (`rule._direction_for_effect`): if
    applying it would loosen a DENY into a PERMIT it is REFUSED and recorded in `rules_rejected`,
    otherwise it is neutral. A rule that could loosen authority would be worse than no rule at all.

`scripts/mutate_p8_rule_admission.py` proves the never-loosen guard fires by reintroducing a rule
that loosens a DENY and watching the refusal disappear.

### DETERMINISM, AND FAIL-CLOSED.

There is no model call, no clock read, no randomness and no unordered iteration: active rules are
read and sorted by `rule_id`, evaluated in that order through `rule.evaluate_rule` (which reads
`ProvenancedFact.value` and RAISES on a `MODEL_INFERRED` read), and every collection is sorted before
it is rendered. A rule that cannot be evaluated deterministically — a fact that is `MODEL_INFERRED`
at checkpoint time, an uncompiled predicate, an unreadable rule store — FAILS CLOSED by raising
`RuleEngineUnavailable`: no decision ⇒ no witness ⇒ no effect (ADR-010 §11). There is no
allow-on-rule-error path.

### RULE-VS-RULE CONFLICT IS M7'S, AND IT HAPPENS BEFORE ACTIVATION. A genuinely conflicting rule is
frozen COMPILED and blocked on an M7 Conflict by M12's RU-3 — it never becomes ACTIVE, so it is never
read here. For a multi-admitting scope (e.g. an `action_class` GATE_PRECONDITION), several ACTIVE
rules STACK and are evaluated conjunctively — any DENY denies, the most restrictive wins. That is
fail-closed conjunction, NEVER an auto-merge: this layer never picks a winner and never loosens.

### IT PRESERVES THE SHIP-DARK POSTURE AND BRAKE INDEPENDENCE. This layer is imported only by
`policy_admission.py`, which is itself bound by nothing in production: the kernel's `GateRegistry`
population stays EMPTY, the governed route still answers `ROUTE_NOT_CONFIGURED`, and no external
effect and no autonomy are enabled. It never imports `brake.py`, so the brake's independence from the
policy engine (ADR-011 §0) is untouched.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .rule import (
    CHECKPOINT_EVALUATED_KINDS,
    PRECEDENCE_LADDER,
    PRECEDENCE_LAYER,
    M12Machine,
    RuleEngineUnavailable,
    RuleRecord,
    compiled_predicate_from_json,
    evaluate_rule,
)
from .tenant import require_tenant

#: The scope form under which a GATE_PRECONDITION / CONSTRAINT rule governs an action class
#: (`migrations/phase6_rules.P6RU_SCOPE_FORMS`). A rule's persisted scope is the form-prefixed string
#: `action_class:<action_class>`; this layer looks rules up by that string.
_ACTION_CLASS_SCOPE_FORM = "action_class"

#: The abstract rule effects. `DENY` and `REQUIRE_HUMAN_APPROVAL` are NARROWING (they add a
#: restriction); `PERMIT` is the one BROADENING effect (`rule._direction_for_effect`); `BIND` /
#: `RESOLVE` are IDENTITY / CONFLICT_RESOLUTION effects and are never gate decisions.
_DENY = "DENY"
_REQUIRE_HUMAN_APPROVAL = "REQUIRE_HUMAN_APPROVAL"
_PERMIT = "PERMIT"
_GATE_EFFECTS: frozenset[str] = frozenset({_PERMIT, _DENY, _REQUIRE_HUMAN_APPROVAL})

#: Recorded when a standing rule DENIES a decision the tenant posture would otherwise have permitted —
#: real, attributable evidence that a rule (not a prompt) blocked the action.
SIGNAL_RULE_DENIED = "STANDING_RULE_DENIED"

#: Recorded when a rule is REFUSED because applying its effect would LOOSEN a DENY into a PERMIT — the
#: one thing a layer-6 rule may never do (ADR-010 §7/§8). The mutation battery proves this fires.
SIGNAL_RULE_BROADENING_REFUSED = "STANDING_RULE_BROADENING_REFUSED"

# A standing rule sits at precedence layer 6. If M12's ladder ever renumbered the layer above the
# policy ceiling (layer 5), this module's whole premise — that a rule overrides nothing above it —
# would be false, so it is asserted at import rather than assumed.
assert PRECEDENCE_LAYER == 6 and PRECEDENCE_LADDER[PRECEDENCE_LAYER - 1] == "STANDING RULE", (
    "a standing rule must be ADR-010 §8 precedence layer 6; the ladder moved and layer 6 composition "
    "would no longer be a pure narrowing below the policy ceiling.")


class RuleAdmissionError(RuntimeError):
    """A composition-level rule-admission defect. Fail closed: no decision is produced."""


@dataclass(frozen=True)
class RuleContribution:
    """What the standing-rule layer folded into a `PolicyDecision`. A VALUE, never a new entity.

    `decision` is the base handed in, possibly tightened to DENY. The three evidence tuples are the
    ADR-010 §5.3 fields, now carrying REAL rule ids: every ACTIVE rule considered, every rule that
    acted, and every rule refused for attempting to loosen. `reason_suffix` is appended to the
    decision's reason only when a rule acted, so a scope with no rules leaves the U8.1 decision
    byte-identical.
    """

    decision: str
    rules_evaluated: tuple[str, ...]
    rules_matched: tuple[str, ...]
    rules_rejected: tuple[tuple[str, str], ...]
    security_signals: tuple[str, ...]
    reason_suffix: str

    @property
    def acted(self) -> bool:
        return bool(self.rules_matched or self.rules_rejected)


class RuleAdmissionLayer:
    """### ADR-010 §8 LAYER 6, BOUND TO ONE TENANT. Reads the tenant's ACTIVE M12 rules and composes
    their deterministic verdicts into a `PolicyDecision`, narrowing only. Owns no table: it reads the
    `rules` rows through an `M12Machine` on the SAME connection the policy read and the claim CAS use,
    so the rule read at step 6 is atomic with the rest of the checkpoint."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        tenant: str,
        clock: Callable[[], object] | None = None,
        machine: M12Machine | None = None,
    ) -> None:
        self._tenant = require_tenant(tenant, context="RuleAdmissionLayer")
        if machine is not None:
            if machine.tenant != self._tenant:
                raise RuleAdmissionError(
                    f"the supplied M12 machine is bound to tenant {machine.tenant!r}, not "
                    f"{self._tenant!r}. One authority, one tenant ([C-1]).")
            self._m12 = machine
        else:
            self._m12 = M12Machine(conn, tenant=self._tenant, clock=clock)  # type: ignore[arg-type]

    @property
    def tenant(self) -> str:
        return self._tenant

    @property
    def conn(self) -> sqlite3.Connection:
        return self._m12.conn

    def active_rules(self, action_class: str) -> tuple[RuleRecord, ...]:
        """The tenant's ACTIVE GATE_PRECONDITION / CONSTRAINT rules for this action class, sorted by
        `rule_id` so evaluation order is deterministic. IDENTITY and CONFLICT_RESOLUTION rules are NOT
        evaluated at the checkpoint (entity §38) — they are the Identity Service's and Reconciliation's,
        so this layer never consults them."""
        scope = f"{_ACTION_CLASS_SCOPE_FORM}:{str(action_class or '').strip().lower()}"
        found: dict[str, RuleRecord] = {}
        for kind in sorted(CHECKPOINT_EVALUATED_KINDS):
            for rec in self._m12.active_for_scope(scope, kind):
                found[rec.rule_id] = rec
        return tuple(sorted(found.values(), key=lambda r: r.rule_id))

    def compose(
        self,
        *,
        action_class: str,
        base_decision: str,
        material_facts: Mapping[str, Any],
    ) -> RuleContribution:
        """### FOLD THE ACTIVE STANDING RULES INTO THE DECISION — NARROWING ONLY.

        With no active rules the contribution is empty and the decision is byte-identical to U8.1. A
        DENY rule tightens the decision to DENY; a REQUIRE_HUMAN_APPROVAL rule is matched evidence
        (its human requirement is already carried by the effective gate); a PERMIT rule that would
        loosen a DENY is refused. A rule that cannot be evaluated deterministically raises
        `RuleEngineUnavailable` — fail closed, no decision, no witness, no effect.
        """
        rules = self.active_rules(action_class)
        evaluated = tuple(r.rule_id for r in rules)         # already sorted by rule_id
        matched: list[str] = []
        rejected: list[tuple[str, str]] = []
        signals: list[str] = []
        decision = base_decision
        acted_reasons: list[str] = []

        for rec in rules:
            verdict = self._evaluate(rec, material_facts)
            effect = verdict.decision
            if effect not in _GATE_EFFECTS:
                # A BIND / RESOLVE effect on a checkpoint-evaluated rule is not a gate decision:
                # unusable, and there is no allow-on-error path (ADR-010 §11).
                raise RuleEngineUnavailable(
                    f"rule {rec.rule_id!r} produced non-gate effect {effect!r} at checkpoint step 6; a "
                    f"GATE_PRECONDITION/CONSTRAINT rule decides PERMIT/DENY/REQUIRE_HUMAN_APPROVAL only. "
                    f"Fail closed — no decision, no witness, no effect.")

            if effect == _DENY:
                decision = _DENY
                matched.append(rec.rule_id)
                signals.append(SIGNAL_RULE_DENIED)
                acted_reasons.append(f"{rec.rule_id} v{rec.rule_version} ⇒ DENY")
                continue

            if effect == _REQUIRE_HUMAN_APPROVAL:
                # A narrowing effect whose requirement (a human) is already carried by the effective
                # gate in this ships-dark slice (nothing graduates). Recorded as MATCHED evidence; it
                # never loosens, so the decision is unchanged.
                matched.append(rec.rule_id)
                acted_reasons.append(f"{rec.rule_id} v{rec.rule_version} ⇒ REQUIRE_HUMAN_APPROVAL")
                continue

            # effect == PERMIT — the one BROADENING effect. ### THE NEVER-LOOSEN GUARD (ADR-010 §7/§8).
            # A layer-6 rule may only ever tighten: if applying this PERMIT would loosen a DENY into a
            # PERMIT it is REFUSED, attributably, and the decision stays DENY. Otherwise it is neutral
            # (a PERMIT rule over an already-PERMIT decision changes nothing).
            if decision == _DENY:
                rejected.append((
                    rec.rule_id,
                    f"rule effect PERMIT would LOOSEN the running decision from DENY to PERMIT; a "
                    f"layer-6 standing rule may only ever NARROW (ADR-010 §7/§8), never override the "
                    f"tenant posture or a prior rule's DENY."))
                signals.append(SIGNAL_RULE_BROADENING_REFUSED)
                # decision stays DENY — refused, not applied.

        reason_suffix = ""
        if matched or rejected:
            reason_suffix = (
                f" Standing rules (layer 6) evaluated {list(evaluated)}; "
                f"acted {sorted(matched)}"
                + (f"; refused-as-loosening {[r for r, _ in rejected]}" if rejected else "")
                + (f" — {'; '.join(acted_reasons)}" if acted_reasons else "")
                + f" ⇒ {decision}.")
        return RuleContribution(
            decision=decision,
            rules_evaluated=tuple(sorted(set(evaluated))),
            rules_matched=tuple(sorted(set(matched))),
            rules_rejected=tuple(rejected),
            security_signals=tuple(sorted(set(signals))),
            reason_suffix=reason_suffix)

    def _evaluate(self, rec: RuleRecord, material_facts: Mapping[str, Any]):
        """Evaluate one ACTIVE rule deterministically, failing closed on any non-deterministic input.

        `rule.compiled_predicate_from_json` refuses an uncompiled candidate, and `rule.evaluate_rule`
        RAISES on a `MODEL_INFERRED` value read — a guess never becomes a gate by being passed through
        this layer either (ADR-010 §5.1/§11). Both surface here as `RuleEngineUnavailable`, which the
        admission caller lets propagate so step 6 refuses (no decision ⇒ no witness ⇒ no effect)."""
        compiled = compiled_predicate_from_json(rec.compiled_predicate)
        return evaluate_rule(compiled, material_facts,
                             rule_id=rec.rule_id, rule_version=rec.rule_version)
