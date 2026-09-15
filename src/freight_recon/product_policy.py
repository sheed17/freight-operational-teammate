"""U8.1 — PRODUCT POLICY: Neyma's own default posture for every registered Action Class, and the
Permanent Product Truth layer that sits above it.

    ### A GATE EXPRESSIBLE AS AN ABSENCE IS NOT A GATE (F-20).
    ### A DEFAULT SAYS "NOBODY DECIDED, SO WE PICKED THE SAFE ANSWER".
    ### THE CANONICAL RULE SAYS "NOBODY DECIDED, SO REFUSE TO START".

### WHAT CHANGED AT U8.1, AND WHY THE VALUE BEING THE SAME IS NOT THE POINT.

From P3 until this unit, `checkpoint.GateRegistry` carried a `_DEFAULT` fallback: an action class
absent from the registry resolved to `HUMAN_APPROVAL_REQUIRED`. That was defensible while the
production population was EMPTY — it could only ever cost a human tap — but it is exactly the
mechanism ADR-010 §2 names as **F-20**: *"if a gate decision can be null, missing, **defaulted**,
or inherited by accident, then forgetting to classify an action class makes it ungated."* The
dangerous property was never the VALUE the default produced; it was that **forgetting was
survivable**. A class nobody had thought about looked exactly like a class somebody had decided
needed a human.

So this module does not change what the gate for any class IS. It changes what happens when a
class has no gate: the system **refuses to start** (`IncompleteProductPolicy`) instead of quietly
answering `HUMAN_APPROVAL_REQUIRED`. That is the whole of U8.1's registration obligation, and the
difference is only visible in the failure mode — which is why it is proved by mutation
(`scripts/mutate_p8_policy_admission.py`) and not by reading.

### THE POPULATION IS DISCOVERED, NEVER MAINTAINED HERE.

`ACTION_CLASS_POPULATION` is derived from `commit_key.OCCURRENCE_RULES` — the repository's existing
per-action-class registration, and the authority K-5 (`entities/00-conventions.md`) names: *"each
action class is registered once, and its registration declares `gate_decision` (NOT NULL — the
system fails to start otherwise), `verification_mode`, `money_direction` and
`occurrence_key_rule`."* `OCCURRENCE_RULES` already declares the fourth of those four and already
fails closed on a class it does not know. This module declares the first, over **exactly that same
population**, and `verify_registration_complete()` fails closed in BOTH directions:

  * a member of the population with no gate            ⇒ `IncompleteProductPolicy` (F-20)
  * a gate declared for a non-member                   ⇒ `IncompleteProductPolicy` (drift)

A hand-written parallel list would drift from the real population and the drift would be invisible,
which is the same defect wearing different clothes. **This module never enumerates the population;
it enumerates its own opinion about the population and is refused if the two disagree.**

### WHY EVERY CLASS IS `HUMAN_APPROVAL_REQUIRED`, AND WHY THAT IS A DECISION.

ADR-010 §15 Q1 is explicit: graduation thresholds are `NEEDS VALIDATION`, and *"until set, nothing
graduates. (Fail-closed default: everything stays `HUMAN_APPROVAL_REQUIRED`.)"* `PHASE-OUTPUTS.md`
P8 records **autonomy as still prohibited (P14)** and live effects as still prohibited (P12). So
`AUTONOMOUS_WITHIN_CAPS` has **no member** at U8.1, and that is not an omission — no class has a
graduation dossier, and inventing one would be granting autonomy by symmetry.

`caps` is `None` on every entry for the same reason: a cap is only meaningful on an autonomous
class, and a cap invented for a class that cannot act alone would be a freight business rule
nobody chose (CLAUDE.md §4 rule 18).

### THE TWO SETS THAT ARE EMPTY ON PURPOSE.

`PERMANENT_PRODUCT_TRUTHS` and the `FORBIDDEN` set are **empty, and an empty set is a positive
assertion, not an oversight** (ADR-010 §3.1, which says exactly this about `FORBIDDEN` and
deliberately leaves it empty at v1).

  * **`FORBIDDEN`** — ADR-010 §15 Q3: *"Recommend leaving it empty and saying so. Inventing a
    member to make the enum feel used would be design by symmetry."*
  * **`PERMANENT_PRODUCT_TRUTHS`** — ADR-010 §3.1 records exactly ONE permanent member today:
    *"any action whose correctness depends on an undocumented authorization"* ⇒
    `PERMANENT_HUMAN_ASSERTION_REQUIRED` (ADR-003). ### THAT MEMBER IS CONDITIONED ON THE EVIDENCE
    BEHIND ONE DECISION, NOT ON THE ACTION CLASS, so it cannot be keyed by action class here
    without inventing the accessorial/authorization material-fact model that arrives at P9. It is
    **already enforced in code**, which is where ADR-010 says a Permanent Product Truth belongs:
    M4 (`approval.py`) and M6 (`identity_binding_claim.py`) refuse to promote a counterparty claim
    to `OWNER_ASSERTED` and raise `CounterpartySelfAuthorizationDetected`.

    ### THE LAYER IS BUILT ANYWAY, AND IT IS NOT DECORATION. `permanent_truth_for()` and the
    precedence in `resolve_ceiling()` are real and are exercised against a fixture permanent truth,
    because the layer's job is to be **unoverridable by product or tenant policy** — and a layer
    whose override-refusal has never been seen to fire is a decoration (CLAUDE.md §6). Binding
    ADR-003's conditional member to a deterministic input is recorded as debt, not guessed at.

### WHAT THIS MODULE IS NOT.

It MINTS NOTHING. It declares `action_class -> GateDecision` and constructs **no `GateEntry` and no
`GateRegistry`** — `checkpoint.py` remains the sole minter of a gate decision, because a second
gate authority is the same defect as no gate authority (ADR-010; the confinement is asserted by
`test_only_the_checkpoint_kernel_may_MINT_a_gate_decision`). It reads no database, evaluates no
tenant posture, calls no model, and has no clock: it is the CEILING, and the tenant's own narrowing
is M11's business (`policy.py`), composed above this by `policy_admission.py`.

### AND IT DOES NOT IMPORT `policy.py`. The ceiling COMPOSITION (`resolve_ceiling`) lives in
`policy_admission.py`, not here, so that M11 keeps exactly ONE production importer — the
composition layer — rather than two. This module is a pure declaration with no policy-engine edge.

It graduates nothing, registers no `FORBIDDEN` member, invents no cap, and enables no effect.
"""

from __future__ import annotations

from dataclasses import dataclass

# The population authority. `OCCURRENCE_RULES` is the repository's existing per-action-class
# registration (K-5's `occurrence_key_rule`), so the gate population is DISCOVERED from it rather
# than restated here. Importing it is what makes the two sets impossible to drift apart silently.
from .commit_key import OCCURRENCE_RULES

# ### THE FOUR CANONICAL MEMBERS, IMPORTED AND NEVER REDECLARED (ADR-010 §3.1 amendment A3).
# This module NAMES them to classify with; `checkpoint.py` alone brings a decision into existence.
from .checkpoint import GateDecision
from .checkpoint import UnclassifiedActionClass as _KernelUnclassifiedActionClass


class ProductPolicyError(RuntimeError):
    """A product-policy defect. Always fail-closed: nothing is classified, nothing may run."""


class IncompleteProductPolicy(ProductPolicyError):
    """### THE STARTUP FAILURE U8.1 OWES (F-20, AC-CKPT-6-missing).

    Raised when the declared classification and the discovered action-class population disagree in
    either direction. This is the "system FAILS TO START" of ADR-010 §3.1 and §10 — not a warning,
    not a default.
    """


class UnclassifiedActionClass(ProductPolicyError, _KernelUnclassifiedActionClass):
    """An action class carries no explicit gate decision. A gate expressible as an absence is not a
    gate (F-20), so this is a refusal and never a fallback.

    ### IT SUBCLASSES THE KERNEL'S `UnclassifiedActionClass` DELIBERATELY. The same condition
    reached from the product policy and from the kernel's own registry is ONE refusal, so the
    kernel's `except UnclassifiedActionClass` catches both and step 6 reports one named cause. The
    alternative — two same-named classes bridged by comparing `type(exc).__name__` — is the kind
    of string-matching seam that silently stops matching after a rename.
    """


#: ### THE DISCOVERED POPULATION. Every action class the repository has registered an occurrence
#: rule for — the set U8.1 must classify exactly. Derived, never typed out.
ACTION_CLASS_POPULATION: frozenset[str] = frozenset(OCCURRENCE_RULES)


@dataclass(frozen=True, slots=True)
class ProductPolicyEntry:
    """One action class's product-level posture: the gate, and the authority that chose it.

    `authority` is mandatory and non-blank. A classification without a citation is an engineer's
    preference wearing a policy's clothes, and the whole point of ADR-010 is that a control the
    owner believes in is traceable to a decision somebody actually made.
    """

    gate: GateDecision
    authority: str
    caps: None = None

    def __post_init__(self) -> None:
        if not isinstance(self.gate, GateDecision):
            raise ProductPolicyError(
                f"a product policy entry carries one of the four canonical gate decisions, got "
                f"{self.gate!r}. A null or invented gate is an unasserted gate (F-20)."
            )
        if not str(self.authority or "").strip():
            raise ProductPolicyError(
                "a product policy entry must cite the authority that chose its gate; an "
                "uncited classification is a preference, not a policy (ADR-010 §3)."
            )


# ### AUTONOMY IS NOT AVAILABLE AT U8.1, SO NO ENTRY BELOW NAMES IT.
# ADR-010 §15 Q1: graduation thresholds are NEEDS VALIDATION and "until set, nothing graduates
# (fail-closed default: everything stays HUMAN_APPROVAL_REQUIRED)". PHASE-OUTPUTS.md P8 records
# autonomy as prohibited until P14. Every class below is therefore HUMAN_APPROVAL_REQUIRED, each
# with the authority that puts it there — and NOT because a default picked it.
_FAIL_CLOSED = (
    "ADR-010 §15 Q1 (graduation thresholds NEEDS VALIDATION; until set nothing graduates, "
    "fail-closed default HUMAN_APPROVAL_REQUIRED) + PHASE-OUTPUTS.md P8 (autonomy prohibited "
    "until P14)"
)
_MONEY_OUT = (
    "ADR-010 §3 (money-out requires a human — CURRENT PRODUCT POLICY, never silently promoted to "
    "a permanent truth) + operating-model §7; " + _FAIL_CLOSED
)

#: ### THE PRODUCT CEILING PER ACTION CLASS — EXPLICIT, TOTAL OVER THE DISCOVERED POPULATION, AND
#: NOT A DEFAULT. Every member of `ACTION_CLASS_POPULATION` appears here exactly once; the
#: verification below refuses the module if that stops being true.
PRODUCT_POLICY: dict[str, ProductPolicyEntry] = {
    # --- money, in both directions -------------------------------------------------------------
    "raise_invoice": ProductPolicyEntry(
        gate=GateDecision.HUMAN_APPROVAL_REQUIRED,
        authority="ADR-010 §3 (the model never chooses an amount); " + _FAIL_CLOSED),
    "record_payable": ProductPolicyEntry(
        gate=GateDecision.HUMAN_APPROVAL_REQUIRED, authority=_MONEY_OUT),
    "record_payment": ProductPolicyEntry(
        gate=GateDecision.HUMAN_APPROVAL_REQUIRED, authority=_MONEY_OUT),
    "adjust_invoice": ProductPolicyEntry(
        gate=GateDecision.HUMAN_APPROVAL_REQUIRED,
        authority="ADR-008 §3.10 / AC-SAFE-020 (a compensation is an ordinary effect and gets the "
                  "ordinary pipeline — no privileged path); " + _MONEY_OUT),
    # --- non-money effects on a system of record ------------------------------------------------
    "create_load": ProductPolicyEntry(
        gate=GateDecision.HUMAN_APPROVAL_REQUIRED, authority=_FAIL_CLOSED),
    "file_document": ProductPolicyEntry(
        gate=GateDecision.HUMAN_APPROVAL_REQUIRED, authority=_FAIL_CLOSED),
    "update_status": ProductPolicyEntry(
        gate=GateDecision.HUMAN_APPROVAL_REQUIRED, authority=_FAIL_CLOSED),
    "check_call": ProductPolicyEntry(
        gate=GateDecision.HUMAN_APPROVAL_REQUIRED, authority=_FAIL_CLOSED),
}

#: ### EMPTY BY DECISION, NOT BY OVERSIGHT (ADR-010 §3.1, §15 Q3). Today's single recorded
#: permanent member is conditioned on one decision's EVIDENCE rather than on an action class, and
#: is already enforced in code by M4/M6 — see the module docstring. Keying it here would require
#: the P9 authorization material-fact model, so it is recorded as debt and not guessed.
PERMANENT_PRODUCT_TRUTHS: dict[str, GateDecision] = {}


def verify_registration_complete(
    *,
    population: frozenset[str] | None = None,
    policy: dict[str, ProductPolicyEntry] | None = None,
) -> int:
    """### U8.1's REGISTRATION OBLIGATION, EXECUTED AT IMPORT. Returns the count it verified.

    `pr-sequence.md` U8.1: *"enumerate every registered Action Class · require exactly ONE positive
    gate decision each · reject null · reject default · reject unregistered action classes · FAIL
    STARTUP on incomplete registration · prove a NON-ZERO evaluated registration count."*

    All six clauses are here. The returned count is the **denominator** — a check that verified
    nothing is worse than no check (CLAUDE.md §6), so the caller can assert it is non-zero and the
    module refuses to be imported over an empty population.
    """
    pop = ACTION_CLASS_POPULATION if population is None else population
    pol = PRODUCT_POLICY if policy is None else policy

    if not pop:
        raise IncompleteProductPolicy(
            "the action-class population is EMPTY, so this verification would pass over nothing "
            "and report a non-existent classification as complete (M-9, the zero-row false "
            "green). `commit_key.OCCURRENCE_RULES` is the population authority — it has been "
            "emptied, renamed or moved."
        )

    unclassified = sorted(pop - set(pol))
    if unclassified:
        raise IncompleteProductPolicy(
            f"action class(es) {unclassified} are registered but carry NO gate decision. A gate "
            f"expressible as an absence is not a gate (F-20, ADR-010 §3.1): the system FAILS TO "
            f"START rather than resolving them to a safe-looking default. Classify them in "
            f"PRODUCT_POLICY with the authority that chose the gate."
        )

    unknown = sorted(set(pol) - pop)
    if unknown:
        raise IncompleteProductPolicy(
            f"gate decision(s) declared for {unknown}, which are NOT registered action classes "
            f"(not in commit_key.OCCURRENCE_RULES). A classification of a class that does not "
            f"exist is drift between this module and the population authority, and drift that is "
            f"tolerated in one direction is drift that becomes invisible in both."
        )

    for name, entry in sorted(pol.items()):
        if not isinstance(entry, ProductPolicyEntry):
            raise IncompleteProductPolicy(
                f"action class {name!r} is classified with {entry!r}, not a ProductPolicyEntry. "
                f"A gate must be one of the four canonical members, carried by the typed entry."
            )
    return len(pol)


def product_gate_for(action_class: str) -> GateDecision:
    """The product ceiling for one action class, or REFUSE. There is no fallback here on purpose."""
    name = str(action_class or "").strip().lower()
    entry = PRODUCT_POLICY.get(name)
    if entry is None:
        raise UnclassifiedActionClass(
            f"action class {name!r} carries no explicit product gate decision. A missing gate is "
            f"NOT equivalent to HUMAN_APPROVAL_REQUIRED (F-20, ADR-010 §3.1) — it is a refusal. "
            f"Register it in product_policy.PRODUCT_POLICY."
        )
    return entry.gate


def permanent_truth_for(action_class: str) -> GateDecision | None:
    """The Permanent Product Truth for a class, if one applies. `None` means none is recorded —
    which is the whole population today, and is asserted rather than assumed."""
    return PERMANENT_PRODUCT_TRUTHS.get(str(action_class or "").strip().lower())


# ### FAIL STARTUP ON INCOMPLETE REGISTRATION. This runs at IMPORT, so a tree whose classification
# has drifted from its action-class population cannot be imported, let alone reach a checkpoint.
# The count is bound so the guard can prove it was non-zero (U8.1's last clause).
REGISTERED_ACTION_CLASS_COUNT: int = verify_registration_complete()
