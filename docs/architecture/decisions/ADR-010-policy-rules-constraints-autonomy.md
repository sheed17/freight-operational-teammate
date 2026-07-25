# ADR-010 — Policy, Rules, Constraints & Autonomy

**Status:** ✅ **FINAL — Wave 4.**
**Completes:** **atomic pre-effect checkpoint STEP 6** (ADR-004 §2.4).
**Resolves:** correction-plan **Group I** (partial), **F-20**; and **Stream B lesson L-C** (*a prompt-string is not a policy*).
**Amends (with an explicit record):** **ADR-004 §3.2** and **ADR-008 §3.2** — the gate-decision enum (§3, and the Amendment Record at the end).
**Language:** `docs/architecture/semantic-model.md` — **canonical, used verbatim.**

---

## 1. CONTEXT

ADR-004 requires the checkpoint to evaluate **policy** and bind a **`policy_version`** to the Effect Grant. ADR-005 makes `policy_version` a **material fact**, so a policy change **voids in-flight approvals**. ADR-008's Pipeline Instance branches on a **gate decision**.

**All three depend on a mechanism that does not exist.** **This ADR is that mechanism.**

## 2. PROBLEM STATEMENT

**Three distinct failures, one missing concept.**

1. **F-20 — a gate expressible as an absence.** If a gate decision can be `null`, missing, defaulted, or inherited by accident, then **forgetting to classify an action class makes it ungated.** *The most dangerous action in the system would be the one nobody remembered to think about.*
2. ### **L-C — the system lies about what it enforces.** An owner types *"never bill without a POD"*; the system replies *"📋 Noted the procedure"*; **what was installed was a sentence in an LLM prompt.** The owner believes they installed a control. **They installed a suggestion.**
3. **Autonomy has no ratchet.** Nothing says how Neyma earns the right to act alone, or how that right is taken back.

> ### **A control the owner believes in must be enforced in code, or it must not claim to be a control.**

---

## 3. DECISION — THE SEVEN CONCEPTS, NOT COLLAPSED

**These are seven different things. Collapsing any two is a defect.**

| Concept | What it is | Who may change it | Can policy override it? |
|---|---|---|---|
| **Principle** | A **human commitment** about how we build (Engineering Principles P1–P39). | Amended **in writing, with the reason** — never bypassed. | n/a — *not machine-evaluated* |
| ### **Permanent Product Truth** | A rule that ### **can never graduate away**, enforced **in code**, not in config. **Today there is exactly ONE: Authorization Assertion (ADR-003).** | ### **NOBODY. Not the owner, not Neyma, not a policy.** Changing it is a **code change + an ADR amendment.** | ### **NEVER** |
| **Product Policy** | **Neyma's** default posture for an action class — *e.g. money-out requires a human*. **Evolvable by Neyma, in writing** (Operating Model §7.6). | Neyma, via an ADR/product decision. | It **is** policy |
| **Tenant Policy** | **This customer's** posture. ### **May only NARROW product policy — never broaden it.** | The tenant's **policy owner** (§4). | Within the product ceiling |
| **Rule** | A **registered, versioned, deterministic decision procedure with an id** — *"the TMS beats the portal on delivery status."* Auditable, re-runnable. | Tenant policy owner, via compilation (§6). | — |
| **Constraint** | An invariant the system ### **cannot violate** — a DB constraint, an illegal transition, a type. **Not evaluated. Enforced.** | Only a code change. | ### **NEVER** |
| **Organizational Knowledge** | ### **Non-authoritative memory.** Recalled into a model's context. **Helps Neyma be useful. NEVER gates anything.** | Anyone. | ### **It has no authority to override — it has no authority at all.** |

> ### **The line that matters: a Permanent Product Truth is enforced in CODE. A Product Policy is enforced in CONFIG.**
> **Money-out requiring a human is CURRENT PRODUCT POLICY. It is NOT a permanent truth, and it must never be silently promoted into one** (Operating Model §7.6). *The day we can prove a class of money-out is safe to automate, that must be a **written product decision** — not something the architecture quietly forbade forever because it felt safer.*

### 3.1 The canonical gate-decision set — **four members**

> ### **Every action class carries EXACTLY ONE gate decision. It is NOT NULL. There is no default, no inheritance-by-accident, and no implicit value. An action class with no gate decision CANNOT BE REGISTERED — the system fails to start.**

| Gate decision | Meaning | May a human unlock it? | May it ever become autonomous? |
|---|---|---|---|
| **`HUMAN_APPROVAL_REQUIRED`** | Needs an **Approval** bound to the material facts (ADR-005). | ✅ yes — that is the point | ### ✅ **Yes — via autonomy graduation (§7).** *This is current policy, and policy evolves.* |
| **`AUTONOMOUS_WITHIN_CAPS`** | May proceed with **no human**, **if and only if** every cap holds. | n/a | already is |
| ### **`PERMANENT_HUMAN_ASSERTION_REQUIRED`** | Requires an ### **authenticated human ASSERTION** — not merely an approval of a proposal, but a human **positively asserting a fact the system cannot observe.** | ✅ yes — **only** an authenticated human | ### ❌ **NEVER. Cannot graduate. Ever.** |
| ### **`FORBIDDEN`** | ### **May never be performed. By anyone. No approval unlocks it.** | ### ❌ **NO** | ❌ never |

**Proof that all four are semantically distinct** *(required before adding a state):*

- ### **`PERMANENT_HUMAN_ASSERTION_REQUIRED` ≠ `HUMAN_APPROVAL_REQUIRED`.** Both need a human — but one is **permanent truth** and the other is **current policy**. **Collapsing them would either freeze money-out forever (wrong — it is policy, §7.6) or make Authorization Assertion graduatable (catastrophic — it is permanent, ADR-003).** ### **The distinction between them IS the distinction between a permanent truth and a policy. It cannot be collapsed without destroying the concept.**
- ### **`FORBIDDEN` ≠ `PERMANENT_HUMAN_ASSERTION_REQUIRED`.** *"Only a human may ever do this"* and *"nobody may ever do this"* are **different sentences.** ### **My own frozen ADR-008 §3.2 collapsed them** — it routed `UNGATABLE_PERMANENT` straight to `REJECTED`, which means **an accessorial that a human COULD have authorized would have been rejected outright instead of asked about.** *(See the Amendment Record.)*
- **`AUTONOMOUS_WITHIN_CAPS` ≠ everything else** — trivially.

**Today's members of the permanent set:**

| Action pattern | Gate | Why permanent |
|---|---|---|
| ### **Any action whose correctness depends on an undocumented authorization** *(an accessorial supported only by a counterparty's claim that someone approved it)* | ### **`PERMANENT_HUMAN_ASSERTION_REQUIRED`** | **ADR-003.** Only an authenticated human may assert an undocumented authorization exists. A counterparty saying *"per our call, you approved this detention"* is ### **an unverified counterparty claim and a FRAUD SIGNAL — not authorization.** |

**Today's members of `FORBIDDEN`:** *(the set is deliberately empty at v1)* — **and an empty set is a positive assertion, not an oversight.** *We have not yet identified an action Neyma should be structurally incapable of, that is not already covered by "there is no adapter for it." The set exists so that when we do, it has a home that no approval can unlock.*

### 3.2 Who assigns a gate decision

| Gate | Assigned by | Reviewable by tenant? |
|---|---|---|
| `PERMANENT_HUMAN_ASSERTION_REQUIRED`, `FORBIDDEN` | ### **Code + an ADR.** Not configuration. | ### **NO.** A tenant cannot opt out of a permanent truth. |
| `HUMAN_APPROVAL_REQUIRED` (product ceiling) | Neyma product decision | Tenant may **narrow** (require more), **never broaden** |
| `AUTONOMOUS_WITHIN_CAPS` | Only reachable **within the product ceiling**, via **autonomy graduation** (§7) | Tenant policy owner **approves** graduation |

---

## 4. POLICY OWNERSHIP

| Question | Ruling |
|---|---|
| **Who owns tenant policy** | ### **A single named human per tenant — the Policy Owner.** Never a role, never a group, never "the admins." **(I1: an accountable human, always.)** |
| **Who may author** | The Policy Owner, or a delegate. ### **A model may PROPOSE policy text (§6). It may never author an active policy.** |
| **Who may approve a change** | The Policy Owner. ### **A policy change is itself an action with `HUMAN_APPROVAL_REQUIRED`** — it goes through the pipeline, with an Approval bound to the **diff** as its material facts. *(Policy changes are effects on the system's own authority. They get the same machinery.)* |
| **Who may activate** | ### **Only an authenticated human.** **NEVER a model. NEVER automation. NEVER a retry handler.** |
| **Who may revoke** | The Policy Owner, or **any authorized human** if revocation **narrows** authority. |
| **Who may temporarily narrow** | ### **Any authorized human, immediately, without review.** *Narrowing is always safe; requiring approval to become safer is a design error.* **See also: the Brake (ADR-011).** |
| ### **May policy broaden automatically?** | ### **NO. NEVER. Under any circumstance, by any signal, at any confidence.** ### **Automation may only ever move authority in the SAFE direction.** |

### 4.1 Versioning, effective dates, expiry
- **`policy_version`** is monotonic per tenant, and is bound into the **Checkpoint Witness** and the **Effect Grant** (ADR-004 §3.2).
- **Effective dates** are supported. ### **A policy is never retroactive** — an effect is judged by the policy version **in force at its checkpoint**.
- **Expiry** is supported **for narrowing policies only** (*"require dual control for the next 30 days"*). ### **A BROADENING policy may never carry an expiry that broadens authority when it fires** — that would be automatic broadening with a delay. **A narrowing policy's expiry is itself a broadening event, and therefore requires a human to confirm at expiry.** *(Otherwise "temporarily tighten" becomes "automatically loosen later, when nobody is watching.")*

### 4.2 Scope
A policy is scoped by any combination of: **tenant** · **action class** · **counterparty** (customer/carrier — **never the ambiguous `party`**) · **value** (a cap, with money direction) · **workflow** (Operating Model loop) · **integration** (target system).
**Scopes intersect. Narrower always wins** (§8).

---

## 5. POLICY EVALUATION — inputs, output, determinism

### 5.1 The governing rule

> ## **A policy predicate may only read deterministic inputs.**
> ## **A policy may NEVER branch on a `MODEL_INFERRED` value — at any confidence.**

**This falls straight out of Semantic Invariant S3, and it is the rule that keeps the whole architecture standing.** *If a policy could branch on a guess, then every guarantee above it — the money fence, the gate, the cap — would be conditioned on a model's mood.*

**Enforcement (structural, not advisory):** the policy evaluator's input type **carries `provenance_class` on every field**, and the evaluator ### **raises on read** if a predicate touches a `MODEL_INFERRED` field. **A rule that cannot be evaluated deterministically FAILS TO COMPILE** (§6). *A guess cannot become a gate by being passed through a policy engine.*

**Corollary:** `confidence` is **not an input**. It is structurally absent. ### **A guard cannot read it.**

### 5.2 Inputs

`tenant` · `actor` · `accountable_owner` · `action_class` · `target_system` · `target_resource` · `counterparty` · `value` + **`money_direction` (IN / OUT — never ambiguous)** · `workflow` · `entity_versions` · `material_facts` · ### **`provenance_class` of every material fact** · ### **`evidence_condition` of every material fact** (`absent`/`unknown`/`consistent`/`conflicting`/`stale`) · `policy_version` · `autonomy_state` · ### **`open_conflicts`** · `open_exceptions` · `approval_state` · `now` (**DB clock**) · `applicable_caps`.

### 5.3 Output — `PolicyDecision` (a value, not a new entity)

```
PolicyDecision {
  gate_decision      : GateDecision        # NEVER NULL
  decision           : PERMIT | DENY
  policy_version     : string
  rules_evaluated    : [rule_id]           # everything considered
  rules_matched      : [rule_id]
  rules_rejected     : [(rule_id, why)]
  caps_applied       : [(cap_id, limit, observed)]
  reason             : human-readable      # REQUIRED, always
  security_signals   : [signal]            # e.g. FRAUD_SIGNAL_COUNTERPARTY_AUTHORIZATION
  escalation_required: bool
}
```

**It must be deterministic and reproducible.** ### **Given the same inputs and the same `policy_version`, the evaluation MUST produce a byte-identical `PolicyDecision`.** *This is testable, and it is tested (§10).*

**`reason` is mandatory, always — including on `PERMIT`.** *A system that can block but not explain has merely relocated the owner's problem* (I3 applies to refusals).

### 5.4 The model's role

> ### **NONE. The model has NO role in the final evaluation.**
> It may **propose** a rule's text (§6). It may **never** evaluate one, resolve a conflict between two, activate one, or reinterpret one. **(P2: guards are never model-evaluated.)**

---

## 6. RULE COMPILATION — the honest resolution of L-C

**An owner types a sentence. There are exactly TWO honest outcomes. There is no third.**

```
   owner sentence
        │
        ▼
   [1] PARSE  ── a model MAY propose a structured candidate rule
        │
        ▼
   [2] VALIDATE (deterministic, no model)
        │   • is every referenced field MODELLED?
        │   • is every referenced field NON-INFERRED (§5.1)?
        │   • is the predicate decidable at checkpoint time?
        │   • is the scope resolvable?
        │
        ├── FAILS ─────────────────────────────────────────────┐
        │                                                       │
        ▼ PASSES                                                ▼
   [3] CONFLICT DETECTION (vs active rules)              ### OUTCOME B
        │   conflict ⇒ raise a CONFLICT (ADR-007)        ### ORGANIZATIONAL KNOWLEDGE
        │   ⇒ FAIL CLOSED, escalate — never auto-merge   Stored as non-authoritative
        ▼                                                 memory. AND THE OWNER IS TOLD:
   [4] HUMAN CONFIRMATION                                 "I can't enforce that — I don't
        │   The owner is shown the COMPILED rule           track commodity type. I've saved
        │   in structured form and confirms it IS          it as a note I'll keep in mind,
        │   what they meant.                               but it is NOT a rule and it will
        ▼                                                  NOT stop me. Here's what I'd need
   [5] ACTIVATION (versioned, effective-dated)            to make it a real rule: …"
        │
        ▼
   ### OUTCOME A — AN ENFORCEABLE RULE
```

> ### **The system must NEVER acknowledge a prompt string as if a deterministic policy was installed.**
> **`"📋 Noted the procedure for raise_invoice"` is FORBIDDEN unless a rule actually compiled and activated.**
> The honest failure sentence is: ### ***"I can't enforce that. Here's why, and here's what I'd need."*** *That is a better answer than a false yes, and the owner can act on it.*

### 6.1 The four worked examples

| Owner says | Compiles to | Outcome |
|---|---|---|
| ### *"Never bill without a POD."* | ### **GATE POLICY + CONSTRAINT.** A precondition on `RAISE_INVOICE`: the `pod` field's `evidence_condition` **must be `consistent`**, and its `provenance_class` **must be one of** `SYSTEM_IMPORTED`, `OWNER_ASSERTED`, or `MODEL_EXTRACTED` **with the artifact retained**. ### **`MODEL_INFERRED` POD ⇒ DENY.** *(An "inferred" POD is not a POD.)* | ✅ **OUTCOME A.** Every field is modelled and deterministic. **This is a real, enforceable rule** — and note it is *already* enforced in code today by the document fence, which is why the owner was right to expect it. |
| ### *"Do not use Carrier X for produce."* | Wants: `FORBIDDEN` for `BOOK_CARRIER` where `carrier = X` **and `commodity = produce`**. ### **But `commodity` is not a modelled field.** | ### ⚠️ **OUTCOME B — and this is the important one.** ### **It CANNOT compile.** The owner is told: *"I can't enforce that — I don't track commodity type on a load. I've saved it as a note. To make it a real rule I'd need commodity as a field on the load."* ### **This is a FEATURE REQUEST surfaced by an honest refusal**, not a silent failure. *The old system would have said "noted" and then booked Carrier X for a load of lettuce.* |
| ### *"Customer Y requires hourly updates."* | ### **WORKFLOW EXPECTATION** — not a gate at all. Compiles to a **recurring Expectation** (ADR-008 §3.8) on Customer Y's active loads, with a deadline and an observability channel. | ✅ **OUTCOME A**, via **existing machinery** — *no new primitive.* **It gates nothing; it OWES something.** *An expectation that goes `OVERDUE` raises an Exception with a human owner.* |
| ### *"Require manager approval under 12% margin."* | Wants: `gate = HUMAN_APPROVAL_REQUIRED` with `required_authority = MANAGER` where `margin < 12%`. ### **Compiles ONLY IF margin is deterministic** — i.e. both the customer rate and the carrier cost are `SYSTEM_IMPORTED` / `OWNER_ASSERTED`. | ### ⚠️ **CONDITIONAL.** If the carrier cost is a **model estimate** (`MODEL_INFERRED`), ### **the rule REFUSES TO COMPILE (§5.1) — a policy may never branch on a guess.** The owner is told: *"I can enforce this on loads where I have a real carrier rate. On loads where I'd have to estimate the cost, I'll escalate to you rather than guess at the margin."* ### **The honest partial answer, not a confident wrong one.** |

### 6.2 Rule lifecycle
**Uses the canonical Durable Machine (ADR-008 §2.3). No new lifecycle.**
`PROPOSED → COMPILED → CONFIRMED → ACTIVE` · `REJECTED` · `SUPERSEDED` · `REVOKED` · `EXPIRED`
- **Supersession:** a new rule version supersedes; ### **the old version is retained** — because effects were judged under it.
- **Revocation:** immediate if it **narrows**; requires the Policy Owner if it **broadens**.
- **Testability:** ### **every compiled rule ships with generated test vectors** — the owner is shown *"here are three loads this rule WOULD have blocked last month."* ### **A rule the owner cannot see the consequences of is a rule they have not really approved.**

---

## 7. AUTONOMY — the one-way ratchet

> ## **Autonomy may NARROW automatically. Autonomy may NEVER broaden automatically.**
> ### **Automation may only ever move authority in the safe direction.** *(This one sentence is the whole of §7, and of ADR-011 §4.)*

### 7.1 Graduation — how an action class earns `AUTONOMOUS_WITHIN_CAPS`

**Automation may PROPOSE graduation. ### A HUMAN ACTIVATES IT. Always.**
**Graduation is itself an action with `HUMAN_APPROVAL_REQUIRED`**, whose material facts are **the evidence below** — so the Policy Owner approves *the evidence*, not a vibe.

| Evidence required | Why |
|---|---|
| **Supervised execution history** — N consecutive approved-and-verified executions in this exact scope | The scope matters: *"invoiced 200 loads"* is not evidence about **carrier payables**. |
| ### **ZERO wrong actions** | ### **Not "a low rate." ZERO.** *A single wrong money action is a customer relationship, and there is no acceptable non-zero rate for it.* |
| **Minimum sample size** | **`NEEDS VALIDATION`** — proposed **≥ 100** in-scope executions. *A number chosen without data is a guess with a threshold.* |
| **Escalation precision** | When it escalated, was it **right to**? A system that escalates everything is not ready; it is just noisy. |
| **Verification success rate** | ≥ threshold of `VERIFIED_SUCCESS` (ADR-006). |
| ### **Unknown-outcome rate** | ### **Must be ~0.** *An action class that regularly cannot be verified must NEVER be autonomous — there would be nobody watching when it goes unknown.* |
| **Counterparty scope** | Graduated **per counterparty class**, not globally. |
| **Value cap** | A hard money ceiling. |
| **Frequency cap** | Per hour / per day. *A bug that acts once is an incident; a bug that acts 400 times is a business.* |
| **Time window** | Graduation **expires** and must be **re-confirmed** — see §7.2. |
| **Named accountable owner** | **I1.** *Autonomy does not remove the human; it changes what they are accountable for.* |

**And a hard precondition:** ### **an action class whose verification is `VERIFICATION_IMPOSSIBLE` (ADR-006 §3.6) may NEVER be `AUTONOMOUS_WITHIN_CAPS`.** *If we cannot check it, a human must be the check.*

### 7.2 Autonomy expiry — and why its expiry is a *narrowing*

**A graduation carries a time window.** At expiry, ### **the action class reverts to `HUMAN_APPROVAL_REQUIRED`** and must be **re-graduated by a human**.

> **Note the direction: expiry NARROWS.** That is what makes it safe to automate. ### **The clock may take authority away. The clock may never give it.** *(Contrast §4.1: a narrowing policy's expiry would BROADEN, and therefore requires a human at expiry.)*

### 7.3 Automatic narrowing — the triggers

**Any of these narrows autonomy immediately, with no human in the loop, and emits a security/audit event:**

a **wrong action** (any) · a **rising unknown-outcome rate** · a **verification failure rate** breach · **repeated drift-voids** on one entity *(a flapping source)* · an **open Conflict** in scope · a **fraud signal** (ADR-003) · a **cap breach** · **integration degradation** · an **orphan adapter invocation** (Sev-0, ADR-004 §4.5).

**Narrowing is graduated:** `AUTONOMOUS_WITHIN_CAPS` → *reduced caps* → `HUMAN_APPROVAL_REQUIRED` → **the Brake** (ADR-011).

### 7.4 Does a policy change invalidate in-flight authority?

> ### **YES — all three. Unambiguously.**

| Artifact | On policy/autonomy change |
|---|---|
| **Approval** | ### **`VOID_ON_DRIFT`** — `policy_version` is a **material fact** (ADR-005 §3.11). *You cannot act under a policy that no longer exists.* |
| **Checkpoint Witness** | ### **INVALID.** It binds `policy_version`. |
| **Effect Grant** | ### **UNCLAIMABLE.** The claim revalidates the bound `policy_version` (§8). |

**Worked:** the owner tightens the cap from £5,000 to £2,000 while a £3,000 payable sits awaiting approval. ### **That payable does not execute.** The approval is `VOID_ON_DRIFT`, reason: *"the policy changed."* **A policy change that does not bind in-flight work is a policy change that does not mean anything.**

---

## 8. POLICY CONFLICTS — deterministic precedence

> ### **A model may NEVER resolve a policy conflict. An unresolved policy conflict FAILS CLOSED and escalates.**

**Strict precedence, highest first. Deterministic. No ties.**

| # | Layer | Note |
|---|---|---|
| **1** | ### **Constraint** | Cannot be violated. Not evaluated — **enforced**. |
| **2** | ### **Permanent Product Truth** | ### **Nothing below may override it. Not a policy. Not a human. Not an emergency.** |
| **3** | ### **Human Brake** (ADR-011) | **Admission control.** Denies regardless of everything below. *(Separate from policy on purpose — see ADR-011 §0.)* |
| **4** | **Product Policy** *(the ceiling)* | Neyma's default posture. |
| **5** | **Tenant Policy** | ### **May only NARROW #4. A tenant can never exceed the product ceiling.** |
| **6** | **Standing Rules** | Compiled, versioned, tenant-authored. |
| **7** | **Workflow default** | The fallback — **and it is never `AUTONOMOUS`.** |

**Within a layer:**

| Conflict | Resolution |
|---|---|
| **Broad rule vs narrow rule** | ### **The NARROWER scope wins** — it is more specific, and specificity is intent. |
| **Customer rule vs workflow default** | The **customer rule** wins (more specific). |
| ### **Two standing rules that genuinely conflict** | ### **FAIL CLOSED.** Raise a **Conflict** (ADR-007 §5 — **existing machinery, no new primitive**). ### **The affected field is `conflicting`, which BLOCKS the action** (ADR-002 C6). **A human resolves it.** ### **Neyma NEVER picks a winner.** |
| **Two rules where one is strictly narrower** | Not a conflict — **precedence applies.** |
| **Current instruction vs expired instruction** | The expired one **has no force.** *It is not "weaker." It is not a rule.* |
| **Policy-version drift during approval** | ### **`VOID_ON_DRIFT`** (§7.4). |
| **Policy change while an effect waits in queue** | The queued work **must pass a NEW checkpoint** under the **new** policy version. ### **Nothing executes on a stale policy decision.** |

### 8.1 Direct human instruction vs a standing rule

> **An authorized human may override a standing rule ### for ONE BOUNDED INSTANCE only.**

**Requirements, all mandatory:**
1. The actor has **authority** for that action class and value.
2. The override is **recorded explicitly** — `PolicyOverridden{rule_id, actor, reason, decision_ref, commit_key}` — as an **audit event AND a security event**.
3. It is **bound to exactly one commit key.** ### **It is single-use, exactly like an Approval.**
4. ### **It NEVER rewrites the standing rule.** The rule remains active, unchanged, for everything else.
5. ### **An override CANNOT cross layers 1–3.** **No human may override a Constraint, a Permanent Truth, or the Brake.** *(There is no break-glass. ADR-004 §2.5.)*

> ### **An override that silently edits the rule is how a one-time exception becomes the new default, and nobody remembers deciding.**

---

## 9. ENFORCEMENT — how step 6 joins the atomic checkpoint

**Inside the single checkpoint transaction (ADR-004 §2.4), step 6 evaluates policy against the inputs of §5.2, and:**

- **DENY ⇒ no `CheckpointPassed` is constructed ⇒ no grant can be minted ⇒ no effect is possible.** *(There is no partial authorization. The checkpoint produces one witness, or none.)*
- **PERMIT ⇒ the `PolicyDecision` is bound into the Witness and onto the Effect Grant** (`policy_version`, `gate_decision`, `rules_matched`, `caps_applied`).

### 9.1 An Effect Grant is **unclaimable** if — *(revalidated at CLAIM, in the claim transaction)*

| Condition | Because |
|---|---|
| `policy_version` ≠ current | You cannot act under a policy that no longer exists |
| `autonomy_state` changed | Authority was narrowed after the grant was minted |
| a **cap** is now exceeded | Caps are evaluated against **current** counters, not minted ones |
| the **required gate is absent** (`gate_decision` null/missing) | ### **F-20 — a gate expressible as an absence is not a gate** |
| a **Permanent Product Truth** applies and is unsatisfied | ADR-003 |
| a relevant **Conflict** is OPEN | ADR-002 C6 |
| ### **the policy decision cannot be REPRODUCED** | ### **A decision we cannot re-derive is a decision we cannot defend.** *(I3.)* |
| the **Brake** is engaged in scope | ADR-011 |

---

## 10. TESTING REQUIREMENTS *(merge-gating)*

| Test | Asserts |
|---|---|
| ### **No null gate** | An action class registered **without** a gate decision ⇒ ### **the system FAILS TO START.** *Not a warning. Not a default.* **(F-20.)** |
| ### **A policy cannot branch on a guess** | A rule referencing a `MODEL_INFERRED` field ⇒ ### **FAILS TO COMPILE.** At confidence **1.0**, still fails. **(S3.)** |
| ### **Confidence is unreadable** | The policy evaluator's input type ### **has no confidence field.** A predicate cannot reference one. |
| ### **L-C — no false acknowledgement** | An uncompilable instruction ⇒ ### **the reply MUST NOT claim a rule was installed**, and MUST state what is missing. *(Assert on the literal reply text.)* |
| ### **A permanent truth cannot be overridden** | A human with maximum authority attempts to override `PERMANENT_HUMAN_ASSERTION_REQUIRED` ⇒ **refused.** A tenant policy attempting it ⇒ **refused at activation.** |
| ### **Automation never broadens** | Every automated path ⇒ **assert it can only narrow.** Property test over all triggers. |
| **Determinism** | Same inputs + same `policy_version` ⇒ ### **byte-identical `PolicyDecision`.** |
| **Policy drift voids** | Tighten a cap while a proposal awaits approval ⇒ ### **`VOID_ON_DRIFT`**, reason names the policy. |
| **Stale policy rejected** | A grant minted under v7, claimed after v8 activates ⇒ ### **claim REFUSED.** |
| **Rule conflict fails closed** | Two conflicting standing rules ⇒ **Conflict raised, action BLOCKED**, no winner picked. |
| **Override is bounded** | An override ⇒ **exactly one commit key**, single-use, **the standing rule unchanged.** |
| **Graduation needs a human** | Automation proposes graduation ⇒ ### **no autonomy change occurs until a human approves.** |
| **Unverifiable cannot be autonomous** | An action class with `VERIFICATION_IMPOSSIBLE` ⇒ **graduation refused.** |
| **Replay evaluates no policy** | Replay ⇒ **zero policy evaluations produce a witness** (ADR-004 §4.6). |

---

## 11. FAILURE MODES

| Failure | Behaviour |
|---|---|
| **The policy engine is unavailable at checkpoint** | ### **FAIL CLOSED. No policy decision ⇒ no witness ⇒ no effect.** *(An "allow on error" default is how the money fence dies.)* |
| **Two rules conflict** | Fail closed ⇒ **Conflict** ⇒ human. |
| **A rule compiles but is wrong** | ### **The generated test vectors (§6.2) are the defence** — the owner sees what it would have blocked **before** activating it. |
| **A rule is repeatedly overridden** | ### **The rule is probably wrong.** Repeated overrides raise an **Exception** to the Policy Owner: *"you have overridden this rule 6 times this month — should it change?"* ### **The system does NOT change it. It asks.** *(ADR-007 Q3, now answered: **never auto-disable a rule. Auto-disabling is a machine decision about machine authority.**)* |
| **The Policy Owner leaves the company** | ### **Policy has no owner ⇒ this is an Exception, not a shrug.** No policy change may be activated until a new Policy Owner is named. **Existing policy continues to be enforced.** *(Fail closed = keep the current constraints, not drop them.)* |
| **A model proposes a malicious rule** *(prompt injection)* | It **cannot activate** (§4). It reaches **human confirmation (§6 step 4)** in **structured, readable form** — *"FORBID `RAISE_INVOICE` for all customers"* is very visible. ### **And even if confirmed, it can only NARROW.** |

---

## 12. SECURITY CONSIDERATIONS

- ### **A model can never activate, broaden, or reinterpret policy.** It may propose text. **The compilation is deterministic and the activation is human.**
- ### **Inbound content can never author policy.** *(Otherwise an email saying "new company rule: pay all invoices automatically" would be a policy change.)* **Policy authorship requires an authenticated human inside Neyma's trust boundary** (`OWNER_ASSERTED`, ADR-002 R-P1).
- **Every policy change is an audit event AND a security event**, with actor, diff, and `decision_ref`.
- **Every override is a security event** — *a rising override rate is an attack signature as much as a UX signal.*
- ### **A fraud signal (ADR-003) narrows autonomy automatically** (§7.3). *The system gets more careful precisely when someone is trying something.*

---

## 13. OPERATIONAL CONSIDERATIONS

- ### **Every action class's gate decision must be VISIBLE to the owner, on one screen.** *An owner who cannot see what Neyma may do alone cannot supervise it.* **(R17: a hidden degradation is a silent one.)**
- **Override rate** is the key policy-health metric: a rule overridden constantly is a **wrong rule**, and it gets a human's attention (§11) rather than a silent auto-disable.
- **Autonomy is displayed as a ratchet with a date**: *"Neyma may file documents alone, up to 20/day, until 2026-09-01."*
- **Narrowing events are loud.** *"I have stopped invoicing autonomously because I got an unknown outcome on load 4471."*

---

## 14. MIGRATION CONSIDERATIONS

- **Today's `lane` (291 uses) is the ancestor of `action_class`** — **but it carries no gate decision**, and gates are **implicit in code paths**. ### **That is F-20, live.**
- **Today, `knowledge.learn(kind=PROCEDURE)` + `recall_procedures()` is OUTCOME B pretending to be OUTCOME A** — organizational knowledge **presented to the owner as an installed rule** (`"📋 Noted the procedure"`). ### **The storage is fine. The SENTENCE is the defect.** **Fixing the reply is a one-line honesty fix and should land early.**
- **The POD gate exists in code today** (the document fence) and is genuinely enforced. ### **Under this ADR it becomes the first compiled rule, and gains a `rule_id` — so the owner can finally SEE that it is real.**

---

## 15. OPEN QUESTIONS

| # | Question | Status |
|---|---|---|
| **Q1** | **Graduation thresholds** — minimum sample size (**proposed ≥100**), verification-success floor, escalation-precision floor. | ### **`NEEDS VALIDATION` — customer + data.** *A number chosen without data is a guess with a threshold.* **Until set, nothing graduates.** *(Fail-closed default: everything stays `HUMAN_APPROVAL_REQUIRED`.)* |
| **Q2** | **Which authorities exist per tenant** (owner / manager / clerk)? Needed for *"require manager approval under 12% margin."* | **`NEEDS VALIDATION` — customer.** Default: **one Policy Owner, one authority level.** |
| **Q3** | Should the **`FORBIDDEN`** set have a v1 member? | ⚠️ **Recommend leaving it empty and saying so.** *An empty set is a positive assertion. Inventing a member to make the enum feel used would be design by symmetry.* |
| **Q4** | **Drift tolerance bands** for low-value classes *(ADR-005 Q3)*. | ### ⚠️ **Recommendation: NO, for money-out.** *A tolerance band is a licence to be wrong by a bounded amount, chosen by an engineer, applied to someone else's money.* If ever allowed: an **explicit, versioned, capped policy** — **never a default, never a code constant.** |

---

## AMENDMENT RECORD — **ADR-004 §3.2 and ADR-008 §3.2** *(frozen; amended here, in writing)*

**These amendments are REQUIRED. Wave 4's gate-decision set (§3.1) cannot coexist with the frozen enum.** *Reported prominently in the Wave 4 review, not applied silently.*

| # | Document | Was | Now | Why |
|---|---|---|---|---|
| **A3** | **ADR-004 §3.2** (`gate_decision`) | `HUMAN_REQUIRED` · `AUTONOMOUS_WITHIN_CAPS` · `UNGATABLE_PERMANENT` | ### `HUMAN_APPROVAL_REQUIRED` · `AUTONOMOUS_WITHIN_CAPS` · `PERMANENT_HUMAN_ASSERTION_REQUIRED` · `FORBIDDEN` | **Four members are semantically distinct (§3.1).** The old three **collapsed a permanent truth with a prohibition.** |
| **A4** | ### **ADR-008 §3.2** (Pipeline Instance transition) | ### `VALIDATED` + gate = `UNGATABLE_PERMANENT` ⇒ **`REJECTED`** | ### `VALIDATED` + gate = `FORBIDDEN` ⇒ **`REJECTED`**; `VALIDATED` + gate = `PERMANENT_HUMAN_ASSERTION_REQUIRED` ⇒ **`AWAITING_APPROVAL`** *(requiring an authenticated human **assertion**)* | ### **THIS WAS A LATENT DEFECT.** The frozen table routed the permanent-truth gate straight to `REJECTED` — meaning ### **an accessorial that a human COULD legitimately have authorized would have been REJECTED OUTRIGHT instead of asked about.** *ADR-003 says only a human may assert it — **not that it may never happen.*** **"Only a human may ever do this" and "nobody may ever do this" are different sentences, and my own frozen ADR conflated them.** |
