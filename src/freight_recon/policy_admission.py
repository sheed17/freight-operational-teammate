"""U8.1 — THE POLICY ADMISSION KERNEL: the composition that makes checkpoint STEP 6 a real P8
policy authority instead of P3 scaffolding.

    ### PERMANENT PRODUCT TRUTH  ABOVE  PRODUCT POLICY  ABOVE  TENANT POLICY.
    ### A TENANT MAY NARROW. A TENANT MAY NEVER BROADEN.
    ### AUTOMATION, A MODEL, A RETRY AND A TIMER MAY NEVER BROADEN AUTHORITY.
    ### NO DECISION ⇒ NO WITNESS ⇒ NO EFFECT.

### WHAT THIS MODULE IS, AND WHY IT IS NOT A SECOND ANYTHING.

Three authorities already existed and none of them was composed:

  * `product_policy.py`  (U8.1, layers 2 and 4) — the Permanent Product Truth set and Neyma's own
    per-action-class ceiling, total over the DISCOVERED action-class population, failing startup on
    incomplete registration.
  * `policy.py`          (M11, layer 5) — the tenant's durable, versioned, human-activated posture:
    seven states, seven transitions, one ACTIVE policy per scope, and the tenant-monotonic
    `policy_version`. It LANDED at P6-CP-11 and shipped dark with zero production importers.
  * `checkpoint.py`      (P3) — the seven-step atomic kernel. STEP 6 held the *shape* of a policy
    evaluation (a typed gate ladder and a fail-closed registry lookup) over an EMPTY production
    population and a STATIC `policy_version` string.

### THIS MODULE IS THE COMPOSITION, AND IT IS THE ONLY PRODUCTION IMPORTER OF M11. It creates no
new entity, no second gate authority, no second version authority and no second brake. It MINTS
NOTHING: `checkpoint.py` remains the sole constructor of a `GateEntry`/`GateRegistry`, and the
`PolicyDecision` it returns is M11's own type (ADR-010 §5.3) — a VALUE, never a new orchestration
entity. The Brake is deliberately absent from this file: ADR-011 §0 is explicit that *"one of the
reasons you pull the brake is that the POLICY ENGINE IS WRONG"*, so a brake that depended on this
module would not work in the moment it exists for. STEP 7 reads `brake.py` and this module never
touches it.

### THE VERSION BINDING, AND THE UNDER-VOIDING DEFECT IT CLOSES.

`policy_version` is a MATERIAL FACT (ADR-005 §3.11), so a policy change must void in-flight
authority. M11's own docstring fixes the namespace: *"### THE VERSION NAMESPACE IS THE TENANT
(M11-AQ-6): a change in ANY scope advances the tenant's `policy_version`, so the void reaches
in-flight authority in EVERY scope — over-voiding is the fail-closed direction and under-voiding is
not available."*

### M11's `evaluate()` RETURNS THE GOVERNING ROW'S OWN `policy_version`, NOT THE TENANT'S CURRENT
ONE, AND THOSE ARE DIFFERENT NUMBERS. `policies` carries `UNIQUE (tenant, policy_version)`, so
activating a policy in scope B raises the tenant's MAX while the ACTIVE row in scope A keeps the
number it was born with. Binding the row's number would mean a policy change in another scope did
NOT change the value the claim CAS revalidates — **under-voiding, in the one direction the
architecture says is not available**. That is why this module binds
`M11Machine.current_policy_version()` (the tenant MAX, which is what P6's own tests and probe
already treat as the bound scalar) and carries the governing row's number in the decision's
`rules_evaluated` and `reason` instead of losing it. `test_p8_policy_admission.py` proves the
cross-scope case, and `scripts/mutate_p8_policy_admission.py` proves it by reintroducing the row's
own version and watching the claim wrongly succeed.

There is ONE version authority (M11) and ONE revalidation site (P3's existing claim CAS, which
already compares `policy_version` and `brake_version`). This module adds neither.

### DETERMINISM, AND THE MODEL'S ROLE.

The model has NO role (ADR-010 §5.4). There is no LLM call, no clock read, no randomness and no
unordered iteration in the decision path: `now` arrives as a BOUND input (the DB clock) and every
collection in the decision is sorted before it is rendered. Given identical deterministic inputs
and an identical `policy_version`, `PolicyDecision.to_bytes()` is byte-identical — asserted, not
asserted-about. `confidence` is structurally absent from `PolicyEvaluationInputs`, and
`ProvenancedFact.value` RAISES on a `MODEL_INFERRED` read, so a guess cannot become a gate by being
passed through this module either.

### FAIL CLOSED, EVERY WAY IN.

| what went wrong | what happens |
|---|---|
| the action class carries no explicit gate | `UnclassifiedActionClass` — refusal, never a default (F-20) |
| the tenant policy is BROADER than the ceiling | `DENY`, `escalation_required`, a security signal, and the attempted broadening named |
| M11 cannot produce a reproducible decision | `PolicyEngineUnavailable` propagates — no decision, no witness |
| a predicate is handed a `MODEL_INFERRED` fact | M11 raises; this module does not catch it into a pass |
| the policy store is unreadable | the exception propagates; STEP 6 refuses |

An allow-on-error default is how the money fence dies (ADR-010 §11), so there is none.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from typing import Any, Callable

from .checkpoint import GateDecision
from .policy import (
    M11Machine,
    PolicyDecision,
    PolicyEngineUnavailable,
    PolicyEvaluationInputs,
    gate_rank,
)
from .product_policy import (
    REGISTERED_ACTION_CLASS_COUNT,
    permanent_truth_for,
    product_gate_for,
)
from .tenant import require_tenant

#: The security signal recorded when a tenant policy is found to sit ABOVE the product ceiling.
#: ADR-010 §12: every attempt to broaden is a security event, because a rising rate of them is an
#: attack signature as much as a UX signal.
SIGNAL_TENANT_BROADENING_REFUSED = "TENANT_POLICY_BROADENING_REFUSED"

#: Recorded when a Permanent Product Truth is what actually decided the gate — so the owner can see
#: that the answer came from a layer nothing below may override (ADR-010 §8 layer 2).
SIGNAL_PERMANENT_TRUTH_APPLIED = "PERMANENT_PRODUCT_TRUTH_APPLIED"


class PolicyAdmissionError(RuntimeError):
    """A composition-level policy defect. Fail closed: no decision is produced."""


def resolve_ceiling(action_class: str) -> GateDecision:
    """### THE CEILING A TENANT MAY NARROW BUT NEVER BROADEN — layers 2 and 4 of ADR-010 §8.

    A Permanent Product Truth (layer 2) sits ABOVE Product Policy (layer 4): *"nothing below may
    override it. Not a policy. Not a human. Not an emergency."* So where a permanent truth exists
    it wins outright even if product policy nominally declares something BROADER — and that
    direction is the entire point of the layer.

    It lives here rather than in `product_policy.py` because the comparison needs the declared
    total order (`gate_rank`), and `product_policy.py` must keep NO edge to the policy engine so
    that M11 keeps exactly ONE production importer: this module. The order itself is declared in
    `checkpoint.py`, beside the enum it orders, and `policy.gate_rank` re-exports it — so there is
    exactly one order and neither the kernel nor this layer can drift from it.

    `product_gate_for` RAISES on an unclassified action class, so this function inherits the
    fail-closed behaviour rather than re-implementing it (F-20).
    """
    product = product_gate_for(action_class)
    permanent = permanent_truth_for(action_class)
    if permanent is None:
        return product
    # Not "one vote among two": a permanent truth CANNOT be overridden from below. If product
    # policy is broader, the permanent truth wins; if product policy is already narrower, narrower
    # stands (§8 — within a layer the narrower scope wins, and narrowing is always safe).
    return permanent if gate_rank(product) > gate_rank(permanent) else product


class PolicyAdmissionAuthority:
    """### CHECKPOINT STEP 6's POLICY AUTHORITY, bound to ONE tenant.

    Bound at construction, exactly as `M11Machine` is, so a caller cannot re-point it at another
    tenant and put [C-1] in its own hands. It owns no table: it reads the product policy (a pure
    declaration) and the tenant's M11 rows, and composes them under ADR-010 §8's precedence.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        tenant: str,
        clock: Callable[[], object] | None = None,
        machine: M11Machine | None = None,
    ) -> None:
        self._tenant = require_tenant(tenant, context="PolicyAdmissionAuthority")
        if machine is not None:
            if machine.tenant != self._tenant:
                raise PolicyAdmissionError(
                    f"the supplied M11 machine is bound to tenant {machine.tenant!r}, not "
                    f"{self._tenant!r}. One authority, one tenant ([C-1])."
                )
            self._m11 = machine
        else:
            # M11's own ceiling parameter is a single scalar, but the ceiling is PER ACTION CLASS
            # here. The per-class ceiling is enforced at resolve() time below regardless of what
            # the machine was constructed with — defence in depth, and this layer is the one that
            # knows the per-class answer.
            self._m11 = M11Machine(conn, tenant=self._tenant, clock=clock)  # type: ignore[arg-type]

    @property
    def tenant(self) -> str:
        return self._tenant

    @property
    def machine(self) -> M11Machine:
        return self._m11

    @property
    def conn(self) -> sqlite3.Connection:
        """### THE CONNECTION THIS AUTHORITY READS — exposed so the checkpoint kernel can assert it
        is the STORE'S connection at construction.

        The claim CAS re-reads `policy_version` through this authority atomically with the CAS
        (ADR-011 §8.2). That atomicity holds only if the read runs on the CAS's own connection, so
        the kernel refuses a bound authority whose `conn` is not `store.conn`. This delegates to the
        M11 machine, which owns the single connection every policy read and write goes through —
        there is no second connection to confuse."""
        return self._m11.conn

    @property
    def registered_action_class_count(self) -> int:
        """U8.1's non-zero denominator, carried so a caller can assert it rather than trust it."""
        return REGISTERED_ACTION_CLASS_COUNT

    def gate_for(self, action_class: str) -> GateDecision:
        """### THE CEILING ALONE — no database, no material facts, no tenant posture.

        Checkpoint step 1 needs to know whether an approval is required before step 2 has re-read
        the facts that a full evaluation depends on, so it asks for the CEILING here and the whole
        decision at step 6. That is safe in exactly one direction and it is the direction that
        holds: a tenant may only ever NARROW, and narrowing moves toward `HUMAN_APPROVAL_REQUIRED`,
        `PERMANENT_HUMAN_ASSERTION_REQUIRED` or `FORBIDDEN` — never away from needing a human. So
        a ceiling that demands an approval cannot be relaxed by the tenant into one that does not.

        The kernel still re-checks at step 6 that the EFFECTIVE gate's approval requirement was
        met, because "safe in one direction" is an argument and the check is a fact.

        Raises `UnclassifiedActionClass` on a class with no explicit gate (F-20).
        """
        return resolve_ceiling(action_class)

    def current_policy_version(self) -> str:
        """### THE ONE BOUND SCALAR: the tenant's current `policy_version` (M11's MAX across every
        scope). This is what the witness pins and what P3's claim CAS revalidates. There is no
        second version authority, and this method does not compute one — it delegates."""
        return str(self._m11.current_policy_version())

    def resolve_for(
        self,
        *,
        action_class: str,
        now: str,
        actor: str = "",
        accountable_owner: str = "",
        target_system: str = "",
        target_resource: str = "",
        material_facts: Mapping[str, Any] | None = None,
        open_conflicts: int = 0,
        approval_state: str = "",
    ) -> PolicyDecision:
        """### THE KERNEL'S ENTRY POINT: plain values in, one `PolicyDecision` out.

        The checkpoint calls THIS rather than `resolve()` so that `checkpoint.py` never has to
        import `policy.py` to build a `PolicyEvaluationInputs`. That matters for two reasons and
        both are structural, not stylistic:

          * `policy.py` already imports `checkpoint.py` for `GateDecision`, so a kernel-side
            import would be a **dependency cycle**;
          * a kernel that depends on the policy engine is the shape ADR-011 §0 spends a whole
            section warning about. The composition depends on the kernel. Never the reverse.

        ### EVERY FIELD IS DETERMINISTIC AND ALREADY IN THE CHECKPOINT'S HAND. `now` is the
        checkpoint's own bound clock, not a fresh wall-clock read, and `material_facts` is the
        STEP 2 LIVE RE-READ — so policy is evaluated against the same facts the fingerprint was
        computed over, not a second and possibly different read. There is no `confidence`
        parameter because the input type has no such field (ADR-010 §5.1).
        """
        return self.resolve(PolicyEvaluationInputs(
            tenant=self._tenant,
            action_class=action_class,
            now=now,
            actor=actor,
            accountable_owner=accountable_owner,
            target_system=target_system,
            target_resource=target_resource,
            material_facts=dict(material_facts or {}),
            open_conflicts=int(open_conflicts),
            approval_state=approval_state,
        ))

    def resolve(self, inputs: PolicyEvaluationInputs) -> PolicyDecision:
        """### EVALUATE LAYERS 2 → 4 → 5 AND RETURN ONE DETERMINISTIC `PolicyDecision`.

        Never returns a null gate. Never returns a gate broader than the ceiling. Raises rather
        than guessing when the engine cannot produce a reproducible answer.
        """
        if not isinstance(inputs, PolicyEvaluationInputs):
            raise PolicyEngineUnavailable(
                "policy admission requires typed PolicyEvaluationInputs; a loose mapping is "
                "refused, because a decision we cannot reproduce is a decision we cannot defend."
            )
        if inputs.tenant and inputs.tenant != self._tenant:
            raise PolicyAdmissionError(
                f"inputs name tenant {inputs.tenant!r} but this authority is bound to "
                f"{self._tenant!r}. The tenant is first in every key and is never inferred ([C-1])."
            )

        action_class = str(inputs.action_class or "").strip().lower()
        # Layers 2 + 4. `product_gate_for` RAISES on an unclassified class: a missing gate is a
        # refusal, not HUMAN_APPROVAL_REQUIRED (F-20). Propagated, never swallowed into a pass.
        ceiling = resolve_ceiling(action_class)
        permanent = permanent_truth_for(action_class)
        product = product_gate_for(action_class)

        # Layer 5 — the tenant's own posture, from the durable M11 rows.
        tenant_decision = self._m11.evaluate(inputs)
        tenant_gate = tenant_decision.gate_decision

        # ### THE ONE BOUND VERSION. Tenant-namespaced and monotonic, so a change in ANY scope
        # moves it and the claim CAS fails closed. See the module docstring.
        bound_version = self.current_policy_version()

        rules_evaluated = tuple(sorted(set(tenant_decision.rules_evaluated)))
        rules_matched = tuple(sorted(set(tenant_decision.rules_matched)))
        signals: list[str] = []
        rejected: list[tuple[str, str]] = []

        # ### A TENANT MAY NARROW. A TENANT MAY NEVER BROADEN. Enforced HERE as well as at M11's
        # activation guard, because an already-ACTIVE row that sits above the ceiling — a row
        # activated when the ceiling was broader, or written by a path that bypassed the guard —
        # must still be refused at the moment it would decide something.
        if gate_rank(tenant_gate) > gate_rank(ceiling):
            for rule_id in rules_evaluated:
                rejected.append((
                    rule_id,
                    f"tenant gate {tenant_gate.value} (rank {gate_rank(tenant_gate)}) is BROADER "
                    f"than the ceiling {ceiling.value} (rank {gate_rank(ceiling)})",
                ))
            signals.append(SIGNAL_TENANT_BROADENING_REFUSED)
            if permanent is not None:
                signals.append(SIGNAL_PERMANENT_TRUTH_APPLIED)
            return PolicyDecision(
                gate_decision=ceiling,
                decision="DENY",
                policy_version=bound_version,
                reason=(
                    f"tenant policy for action class {action_class!r} resolves to "
                    f"{tenant_gate.value}, which is BROADER than the ceiling {ceiling.value} "
                    f"(product {product.value}"
                    + (f", permanent product truth {permanent.value}" if permanent else "")
                    + f"). A tenant policy may only ever NARROW the product ceiling (ADR-010 "
                    f"§3.1/§8), so this is refused and the ceiling stands. Attempted broadening is "
                    f"a security event and is attributable to the policies named in "
                    f"rules_rejected."
                ),
                rules_evaluated=rules_evaluated,
                rules_matched=(),
                rules_rejected=tuple(rejected),
                caps_applied=(),
                security_signals=tuple(sorted(set(signals))),
                escalation_required=True,
            )

        if permanent is not None:
            signals.append(SIGNAL_PERMANENT_TRUTH_APPLIED)

        # The tenant gate is at or below the ceiling, so it stands — narrower always wins (§8).
        effective = tenant_gate
        reason = (
            f"action class {action_class!r}: product ceiling {product.value}"
            + (f"; permanent product truth {permanent.value} (layer 2, unoverridable)"
               if permanent else "")
            + f"; tenant posture {tenant_gate.value} ⇒ effective gate {effective.value}, "
              f"{tenant_decision.decision} at tenant policy_version {bound_version}. "
            + tenant_decision.reason
        )
        return PolicyDecision(
            gate_decision=effective,
            decision=tenant_decision.decision,
            policy_version=bound_version,
            reason=reason,
            rules_evaluated=rules_evaluated,
            rules_matched=rules_matched,
            rules_rejected=(),
            caps_applied=tenant_decision.caps_applied,
            security_signals=tuple(sorted(set(signals))),
            escalation_required=bool(tenant_decision.decision == "DENY"),
        )
