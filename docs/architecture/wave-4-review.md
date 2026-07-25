# Wave 4 Consistency Review — The Checkpoint Is Complete

**Delivered:** **ADR-010** (Policy, Rules, Constraints & Autonomy — checkpoint **step 6**) · **ADR-011** (The Human Brake — checkpoint **step 7**)
**Amendments applied:** **A3** (ADR-004) · **A4** (ADR-008) — *frozen documents, amended in writing, with the reason*
**Baseline:** `f0e801b4dfd611345ca6c2842e946d58a7512ae5`
**Date:** 2026-07-13

---

## 0. THE HEADLINE

> # **The atomic pre-effect checkpoint is now fully specified. All seven steps have mechanisms.**

| Step | Mechanism | ADR | Status |
|---|---|---|---|
| 1 | Approval validity | ADR-005 | ✅ |
| 2 | Material-facts fingerprint | ADR-005 | ✅ |
| 3 | Projected-state freshness *(live; never a cache)* | ADR-001 C4 | ✅ |
| 4 | Native-state validity | ADR-002 / ADR-007 | ✅ |
| 5 | Entity-version concurrency | ADR-009 | ✅ |
| **6** | **Policy & autonomy authorization** | ### **ADR-010** | ### ✅ **NEW** |
| **7** | **Human-brake admission** | ### **ADR-011** | ### ✅ **NEW** |

**Atomicity holds:** all seven evaluate **in one transaction**; **no asynchronous work occurs between them and the grant claim**; **no individual result is cached or reused**; the checkpoint produces ### **one immutable Checkpoint Witness, or none.** ### **There is no partial authorization** — a failed checkpoint constructs no witness, and **a grant cannot be minted from a witness that does not exist.**

---

## 1. DECISIONS MADE

### 1.1 The gate-decision set — **four members, and the fourth one mattered**

`HUMAN_APPROVAL_REQUIRED` · `AUTONOMOUS_WITHIN_CAPS` · `PERMANENT_HUMAN_ASSERTION_REQUIRED` · `FORBIDDEN`

**Not null. No default. No inheritance-by-accident.** ### **An action class registered without a gate decision makes the system FAIL TO START** — F-20 dies at boot, not at runtime.

### 1.2 The brake is **admission control**, never process termination

> ### **It is enforced by refusing to MINT and refusing to CLAIM — never by killing a worker.**
> **A brake that kills workers manufactures the exact thing the architecture fears most: an `UNKNOWN_OUTCOME`.** *You would engage it to become safer and, in the act, create a payable of unknown status.*

**Anything past the claim runs to a verified conclusion.** ### **The brake stops the NEXT effect. It cannot stop the LAST one — and it must not pretend to.**

### 1.3 The brake is **not** a policy — and the reason is the ADR

> ### **One of the reasons you pull the brake is that the policy engine is wrong.**

A brake implemented as a policy **depends on the subsystem it exists to overrule.** It must be engageable when the system is broken, instantly, with no authoring ceremony. ### **That is why ADR-004 made them steps 6 and 7 — two checks, not one.**

### 1.4 The one-way ratchet — **one sentence governs both ADRs**

> ## **Automation may only ever move authority in the SAFE direction.**
> **It may narrow autonomy and engage/widen a brake. It may NEVER broaden autonomy or release/narrow a brake.**

*(This is not a coincidence between two ADRs. It is the invariant, appearing twice.)*

### 1.5 A policy may never branch on a guess

> ### **A policy predicate may only read deterministic inputs. It may NEVER branch on a `MODEL_INFERRED` value — at any confidence.**

**Structurally enforced:** the evaluator's input type carries `provenance_class` per field and **raises on read** of an inferred field. ### **A rule that cannot be evaluated deterministically FAILS TO COMPILE.** **`confidence` is not an input at all — a guard cannot read it.**

*This falls straight out of Semantic Invariant S3, and it is what stops the whole architecture being defeated by one `if confidence > 0.98`.*

### 1.6 L-C is resolved — two honest outcomes, and no third

**A** — it compiles into a **structured, scoped, versioned, enforceable rule**, confirmed by a human.
**B** — it is stored as **non-authoritative organizational memory**, ### **and the owner is TOLD it is not a rule and will not stop anything.**

> ### **`"📋 Noted the procedure"` is FORBIDDEN unless a rule actually compiled and activated.**
> The honest sentence is: ***"I can't enforce that. Here's why, and here's what I'd need."*** *That is a better answer than a false yes — and the owner can act on it.*

---

## 2. EXISTING PRIMITIVES REUSED *(the point of Wave 4)*

| Requirement | Reused | Not invented |
|---|---|---|
| Rule lifecycle | **Canonical Durable Machine** (ADR-008 §2.3) | no new lifecycle machinery |
| Brake lifecycle | **Canonical Durable Machine** — **two states** | no new machinery |
| **Two standing rules conflict** | ### **The Conflict machine (ADR-007 §5)** — it raises, blocks, and gets a human | ### **no "policy conflict" concept** |
| *"Customer Y requires hourly updates"* | ### **The Expectation machine (ADR-008 §3.8)** | ### **no "SLA" primitive** |
| Policy change voids in-flight authority | ### **`policy_version` is already a MATERIAL FACT** (ADR-005) ⇒ `VOID_ON_DRIFT` | no new invalidation mechanism |
| Brake invalidates grants | ### **`brake_version` bound into the Witness; revalidated in the CLAIM CAS** (ADR-004 §3.5) | no new revocation path |
| Policy change is itself gated | ### **It is an ordinary action class with `HUMAN_APPROVAL_REQUIRED`, through the ordinary pipeline** | ### **no "admin path"** |
| Entity-level freeze | ### **Already exists** — an open Conflict, `NEEDS_VERIFICATION`, or `COMPENSATION_FAILED` freezes an entity | ### **entity-scoped brake REJECTED (§3.2)** |

---

## 3. PROPOSED NEW PRIMITIVES — **and the two I refused**

### 3.1 What was added

**Two durable entities — `Policy/Rule` and `Brake` — both instances of the existing canonical Durable Machine, and both already NAMED by frozen ADR-004 §2.4 (steps 6 and 7).**

> ### **These are not new primitives. They are the completion of two the architecture already declared and left undefined.** Refusing to build them would leave the keystone ADR unimplementable.

**Applying the five-part test to the `Brake`, honestly:**
1. **Can an existing mechanism express it?** ### **Policy CAN express "deny everything in scope" — but it must not** (§1.3). **The dependency is backwards.**
2. **Why would extension violate an invariant?** It would make the safety control depend on the correctness of the thing it exists to overrule. ### **A safety control that requires the system to be healthy is not a safety control.**
3. **New state / failure modes?** **Two states, one row, one monotonic version.** New failure mode: *brake store unreachable* ⇒ ### **fail closed** (no store ⇒ no claim ⇒ no effect). **It fails safe by construction.**
4. **Maintenance obligation?** **The brake must be EXERCISED in production, deliberately, on a schedule.** ### **A safety control that has never been pulled is a hypothesis.**
5. **What does it replace?** ### **`ops_control`'s `pause tms writes` flag** — which is checked **by convention** today and **would not stop `enter_truckingoffice_invoice.py`.**

### 3.2 What I refused

| Refused | Why |
|---|---|
| ### **An entity-scoped brake** | ### **An entity is ALREADY frozen** by an open Conflict / `NEEDS_VERIFICATION` / `COMPENSATION_FAILED`. **A second way to freeze an entity is two things that mean the same — which is precisely how they drift apart.** |
| ### **An accountable-owner-scoped brake** | ### **A brake on a PERSON is an HR control, not a safety control.** *Stopping "everything Dave approved" describes a suspicion, not a hazard.* If Dave's authority is the problem, ### **that is a POLICY change** — narrowing authority, which any human may do instantly. |
| **A "policy conflict" concept** | It **is** a Conflict (ADR-007). |
| **An `EXPIRED` brake state** | ### **A brake that expires releases itself while nobody is looking.** **A clock cannot know whether the fire is out.** |
| **A "pending release" state** | Release must not need an approval workflow. *Requiring ceremony to become safer is a design error.* |

---

## 4. FINDINGS FULLY RESOLVED

| # | Finding | Closed by |
|---|---|---|
| **F-20** | A gate expressible as an absence | **ADR-010 §3.1** — four members, NOT NULL, ### **an unregistered gate fails the BUILD**, not a request |
| **F-15** | The brake was undefined | **ADR-011** — admission control at mint **and** claim |
| **F-31** | Operational control / visibility | **ADR-011 §7** — ### **a hidden brake violates R17**; every surface reports it unprompted |
| **L-C** | *"Noted the procedure"* — a prompt string presented as a rule | **ADR-010 §6** — **two honest outcomes, and a merge-gating test that asserts on the literal reply text** |
| **A4 (latent)** | ### **`UNGATABLE_PERMANENT → REJECTED`** | ### **A defect I introduced in Wave 1 and found in Wave 4.** See §8. |

---

## 5. FINDINGS PARTIALLY RESOLVED

| # | Finding | Status |
|---|---|---|
| **F-07 / R-02** | Multiple runtimes, one effect | **Mechanism complete across ADR-004/009/011.** ### **Still NOT BUILT. R-02 closes when it is implemented, and the runbook warning remains discipline, not a fix.** |
| **Group M** (F-35 content half) | Untrusted content, fraud taxonomy | **Capability half closed.** ADR-010 §7.3 adds the **fraud signal → automatic autonomy narrowing** link. **Content sanitisation remains defence-in-depth, not blocking.** |

---

## 6. REMAINING IMPLEMENTATION BLOCKERS

> ### **NONE at the architecture layer. The checkpoint is complete.**

**What remains is not architecture:**

| # | Blocker | Nature |
|---|---|---|
| **B1** | ### **The Target Specification is stale and CONTRADICTS the ADRs.** `target-system-specification.md:400` still **mandates a `Command` type** that ADR-008 §2.12 deleted; §11/§12/§19/§23/§29 are substantially superseded. | ### **This is Wave 5. It is the last thing between here and entity/state-machine specifications.** |
| **B2** | ### **The live commit-key defect** (`operation_router.py:335`) — `approved_amount` in the commit key ⇒ **two racing reads ⇒ two invoices**; and no commit-once at all for non-money effects. | ### **Implementation, and it should be the FIRST task.** Recorded, not fixed (ADR-009 §2.2). |
| **B3** | Semantic-model deprecations (`lane`→action class, `run`→Pipeline Instance, `CommandIntent`→`ProposedIntent`) | **A migration obligation, not permission to rename now.** |

---

## 7. REMAINING CUSTOMER-VALIDATION QUESTIONS

**None block implementation. Every one has a fail-closed default.**

| # | Question | Fail-closed default |
|---|---|---|
| **V11** | ### **Autonomy graduation thresholds** — sample size (proposed **≥100**), verification floor, escalation precision | ### **Until set, NOTHING graduates. Everything stays `HUMAN_APPROVAL_REQUIRED`.** *A number chosen without data is a guess with a threshold.* |
| **V12** | **Which authorities exist per tenant** (owner/manager/clerk)? | One Policy Owner, one authority level. |
| **V13** | **Who may engage the brake?** ⚠️ **Recommend: everyone authenticated.** *The cost of a spurious engagement is a pause. The cost of a delayed engagement is a payment. **Those are not close.*** | Everyone. |
| **V14** | **Who may release?** ⚠️ **Recommend: a narrower set than may engage — the asymmetry IS the control.** | The Policy Owner. |
| **V15** | Should repeated `NEEDS_VERIFICATION` auto-engage a brake? ⚠️ **Recommend YES, at 2 per integration per window.** *Two unknowns on one integration is not bad luck — it means we cannot see what we are doing.* | Mechanism ready; threshold unset. |
| **V16** | Does `FORBIDDEN` have a v1 member? ⚠️ **Recommend leaving it EMPTY and saying so.** *An empty set is a positive assertion. Inventing a member to make the enum feel used would be design by symmetry.* | Empty. |
| — | *(V1–V10 from Wave 2 remain open and unchanged.)* | |

---

## 8. HIGHER-LEVEL DOCUMENTS REQUIRING AMENDMENT — **two, applied, and one was a real defect**

> **Reported prominently, not applied silently. Both frozen documents carry a written Amendment Record.**

### A3 — ADR-004 §3.2 (the gate-decision enum) · *housekeeping*
Replaced `HUMAN_REQUIRED · AUTONOMOUS_WITHIN_CAPS · UNGATABLE_PERMANENT` with the four-member set. The `approval_id` CHECK constraint widened.

### ### A4 — ADR-008 §3.2 · ⚠️ **THIS FIXED A LATENT DEFECT I SHIPPED IN WAVE 1**

**The frozen transition table said:**

```
VALIDATED + gate = UNGATABLE_PERMANENT  ⇒  REJECTED
```

**`UNGATABLE_PERMANENT`'s only member is the ADR-003 Authorization Assertion.** So the frozen table meant:

> ### **An accessorial that an authenticated human COULD legitimately have authorized would have been REJECTED OUTRIGHT — instead of asked about.**

**ADR-003 says *only a human may assert an undocumented authorization*. ### It does NOT say the action may never happen.** I had collapsed **"only a human may ever do this"** into **"nobody may ever do this"** — ### **a usability failure wearing a safety property's clothes.** It would have made Neyma **structurally unable to pay a legitimate, human-authorized detention charge**, and the owner would have had to go around the system to do their job — **which is how a safety control gets switched off for real.**

**Fixed:** `FORBIDDEN ⇒ REJECTED`; ### **`PERMANENT_HUMAN_ASSERTION_REQUIRED ⇒ AWAITING_APPROVAL`.**

> **This is the second time a Wave has found a defect in a previous Wave's frozen output** *(the first: `UNKNOWN_OUTCOME`'s three-way overload, Wave 2 §5.1)*. **Both were found by writing the next layer down and discovering the layer above could not express what it needed to.** *That is what these reviews are for, and it is why they are not a formality.*

**No other document requires amendment.** Engineering Principles, Operating Model, Semantic Model, ADR-001/002/003/005/006/007/009 are all **unaffected and reinforced**.

---

## 9. CROSS-ADR CONSISTENCY — verified

| Check | Result |
|---|---|
| **No new primitive without justification** | ✅ Two entities, both **already named by frozen ADR-004**, both on the **existing Durable Machine**. **Two scope dimensions and three states actively REFUSED** (§3.2). |
| **Terminology matches the Semantic Model exactly** | ✅ `counterparty` (never `party`) · `money_direction` (IN/OUT, never ambiguous) · **Pipeline Instance** (never `run`) · **action class** (never `lane`) · **Policy vs Organizational Knowledge** (never conflated). |
| ### **All seven checkpoint steps defined** | ### ✅ |
| **Gate & brake decisions cannot be null or implicit** | ✅ Gate: **NOT NULL, no default; unregistered ⇒ build fails.** Brake: **unreadable brake store ⇒ FAIL CLOSED** *(cannot-read must never mean "off")*. |
| **Permanent truths distinct from current policy** | ### ✅ **This is exactly what A3/A4 fixed.** **Money-out remains PRODUCT POLICY (§7.6) and was NOT silently promoted.** |
| **Policy cannot override a permanent truth** | ✅ Precedence: **Constraint > Permanent Truth > Brake > Product Policy > Tenant Policy > Rules > Default.** Tenant policy may **only narrow**. |
| **Automation narrows, never broadens** | ✅ ADR-010 §7 + ADR-011 §5. **One sentence, two ADRs.** Property-tested. |
| **No model output can activate policy or release a brake** | ✅ A model may **propose rule text**. It may never compile, activate, evaluate, resolve, engage, or release. |
| **Replay cannot bypass policy or brake** | ✅ Replay cannot construct a `CheckpointPassed` ⇒ **no witness** ⇒ **it never reaches steps 6 or 7 at all.** *The guarantee is free.* |
| **Every guarantee has a structural mechanism** | ✅ Type, DB constraint/CAS, CI gate, illegal transition, or merge-gating test. ### **Nothing rests on developer discipline.** |
| **`brake_version` race is closed** | ✅ In the **claim CAS**. **10,000× interleaved test: never both, never neither.** |

---

## 10. IS THE TARGET SPECIFICATION READY FOR CANONICAL REVISION?

> # **YES. Without reservation, and for the first time.**

**Every condition I set in the Wave 2 review is met:**

- ✅ **ADR-010 and ADR-011 exist.** ### **The checkpoint — the single most important function in the system — no longer has a hole in it.** *(That was the sole blocking condition, and it was the right one: writing §19 over an undefined step 6 and 7 is exactly how the spec got into trouble the first time.)*
- ✅ **The language is canonical** (Semantic Model, Wave 3).
- ✅ **Eleven ADRs now constrain the spec**, and **every internal contradiction found across four waves has been closed** — including two I introduced myself.

**The revision must be a REWRITE of §11, §12, §19, §23, §29 — not a patch.** ### **Today the spec still MANDATES a `Command` type the ADRs deleted, and the CODE follows the SPEC (`CommandIntent`, 51 uses).** **A lower layer is currently contradicting a higher one, in production.**

---

## 11. WHAT WAVE 4 ACTUALLY BOUGHT

1. ### **Neyma can no longer lie about what it enforces.** *"Never bill without a POD"* either **becomes a real rule with an id the owner can see**, or the owner is **told, plainly, that it did not.** **There is no third outcome.**
2. ### **A guess can never become a gate.** A policy that branches on `MODEL_INFERRED` **does not compile.** Not at 0.98. Not at 1.0.
3. ### **The owner can stop it — and stopping it cannot hurt them.** The brake refuses to *mint* and refuses to *claim*; it **never kills a worker**, so it **cannot manufacture an unknown outcome in the act of trying to be safe.**
4. ### **Authority only ever ratchets one way without a human.** Automation may take authority away. ### **Only a human may ever give it.**

> **And one thing found by writing this Wave that no review would have caught:**
> ### **The frozen architecture, as of Wave 1, would have refused to pay a legitimate detention charge that a human had personally authorized** — because I had collapsed *"only a human may do this"* into *"nobody may do this."*
> **A safety property that stops the owner doing their job is not a safety property. It is the reason people switch safety properties off.**
