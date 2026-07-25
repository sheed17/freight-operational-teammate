# Wave 2 Review — Architecture Completion

**Baseline:** `f0e801b4dfd611345ca6c2842e946d58a7512ae5`
**Delivered:** ADR-005 (approval binding & drift) · ADR-006 (verification & unknown outcomes) · ADR-007 (identity, claims & conflict) · ADR-009 (concurrency & reservations)
**Date:** 2026-07-13
**Discipline held:** *"Default to refinement. Not invention."*

---

## 0. NEW PRIMITIVES INTRODUCED: **ZERO**

**Wave 2 introduced no new architectural primitives, no new state machines, and no new tables.** Every mechanism was expressed with entities that already existed.

**Three places where a new concept was tempting, and was refused:**

| Tempting concept | What was done instead | Why |
|---|---|---|
| **A `reservations` table** (ADR-009) | ### **The Pipeline Instance IS the reservation** — one partial unique index. | ADR-008 already ruled *"the Pipeline Instance IS the command."* A command in flight **is** a claim on its target. A separate table would be **a second source of truth that can silently drift out of sync with the first — about money.** |
| **A `SUPERSEDED` approval state** (ADR-005) | ### **Supersession decomposes into drift-void ∪ duplicate-refusal.** | Every supersession is *either* a new proposal with different facts (⇒ `VOID_ON_DRIFT`) *or* an identical duplicate (⇒ refused by the reservation). **There is no third case, so there is no third state.** |
| **A `Verification` state machine** (ADR-006) | ### **`VerificationOutcome` is a VALUE that triggers ADR-008's existing transitions.** | All eight outcomes map onto the existing External Effect states. A parallel machine would have to be kept in lockstep with the one that already exists. |

**Two things were *added* to existing entities** (extension, not invention): `ApprovalSignature` (an evidence record on the existing Approval machine, for dual control) and `unknown_reason` (a mandatory field on the existing `UNKNOWN_OUTCOME` state).

---

## 1. FINDINGS FULLY RESOLVED

| # | Finding | Closed by | The mechanism |
|---|---|---|---|
| **F-01** | **CRITICAL** — revalidation before the human gate ⇒ **would pay the wrong amount** | **ADR-005** | The **material-facts fingerprint**, re-checked **inside** the atomic pre-effect checkpoint, against **live authoritative reads**. Drift ⇒ `VOID_ON_DRIFT`, with a field-level diff. |
| **F-03 / F-11** | Verification undefined | **ADR-006** | An **eight-outcome taxonomy**, each with an explicit **proof standard**. |
| **F-33** | No answer for *"what if verification is also dead?"* | **ADR-006** | `NEEDS_VERIFICATION`, non-terminal, human-owned, **no timeout in either direction**. |
| **F-04** | Observation / evidence / claim / fact used interchangeably | **ADR-007** | **Nine distinct terms**, each with a state class and a mutability rule. |
| **F-05** | A model-asserted authorization could gate money | **ADR-007 §4.4** *(+ frozen ADR-003)* | A counterparty assertion is **`MODEL_EXTRACTED` at best, forever**, and **cannot be promoted** (R-P2). It **blocks** and is recorded as a **fraud signal**. |
| **F-16 / F-26** | Conflicts undefined | **ADR-007 §5** | A Conflict **blocks all consequential actions** on the entity; closable **only** by a registered rule id or a human `decision_ref`. **`AutoResolve` is an illegal transition.** |
| **F-17** | Corrections did not propagate | **ADR-007 §6** | A correction **walks the lineage forward** and **raises a Compensation** for every completed effect that rested on it. |
| **F-08 / F-09** | Approval staleness | **ADR-005 §3.9** | Absolute TTLs per action class, fired by **durable timers**. |
| **F-20** | A gate expressible as an absence | **ADR-005 §3.2** | `gate_decision` is a **material fact** and is **never null**. |
| **F-22** | Approval scope creep | **ADR-005 §3.2/§3.7** | The **target resource** is inside the fingerprint; **one approval = one commit key**. |
| **F-10** | **CRITICAL** — no entity concurrency control | **ADR-009** | **Two partial unique indexes.** Layer 1 (pipeline) prevents a duplicate *proposal*; Layer 2 (grant ledger) prevents a duplicate *effect*. |
| **L-A** | An inference overwrote human state | **ADR-007 §4.3 + ADR-008 §3.6** | `OWNER_ASSERTED` + `RecomputedByInferrer` = **ILLEGAL TRANSITION** (raises, persists nothing, security event). |
| **L-B** | Human corrections bound to an ordinal | **ADR-007 §4.3** | Ordinals **resolve to an immutable id at render time**; the action binds to the id, or **fails closed**. |
| **L-D** | Permanent failures retried forever | **ADR-006 §3.7** | **TRANSIENT vs PERMANENT** classification; a permanent failure **raises an Exception immediately, zero retries**. |

---

## 2. FINDINGS PARTIALLY RESOLVED

| # | Finding | Status |
|---|---|---|
| **F-07 / R-02** | Multiple runtimes, one effect | **Mechanism complete; not built.** ADR-004 (grant ledger) + ADR-009 (commit key + two indexes) together **are** the shared exclusion namespace. **R-02 closes when this is implemented — not when it is written.** Until then the runbook warning is **operator discipline, and I will not call it a fix.** |
| **F-35** | Untrusted content & injection | **Capability half CLOSED** (ADR-004: a model cannot mint a grant). **Content half** — sanitisation, quarantine, and the fraud-signal taxonomy — **is defence-in-depth and belongs to Group M.** Not blocking. |
| **F-14** | `OVERDUE` asserted while blind | **Mechanism defined** (ADR-008 `INDETERMINATE`; ADR-006 §3.4 channel health). **The per-screen health control is a discovery task per integration.** |
| **F-12** | Tenant isolation | **Structurally enforced** in every key and index defined in Wave 1/2 (`tenant_id` first, always). **A dedicated ADR is not required.** |

---

## 3. REMAINING BLOCKERS

### 3.1 ⛔ Architecture blockers — **two ADRs are required before the checkpoint can be implemented**

**This is the honest finding of Wave 2, and I want it stated plainly rather than buried:**

> ### **ADR-004's atomic pre-effect checkpoint has seven steps. Wave 1 and Wave 2 define five of them. Steps 6 and 7 have no ADR.**

| Checkpoint step | Defined by | Status |
|---|---|---|
| 1. Approval validity | ADR-005 | ✅ |
| 2. Material-facts fingerprint | ADR-005 | ✅ |
| 3. Projected-state freshness | ADR-001 C4 | ✅ |
| 4. Native-state revalidation | ADR-002, ADR-007 | ✅ |
| 5. Entity-version concurrency | ADR-009 | ✅ |
| **6. Policy evaluation** | ### **ADR-010 — NOT WRITTEN** | ⛔ **BLOCKING** |
| **7. Human-brake admission** | ### **ADR-011 — NOT WRITTEN** | ⛔ **BLOCKING** |

**The checkpoint is the single most important function in the system, and it cannot be written until steps 6 and 7 have contracts.** They are also load-bearing elsewhere: `policy_version` is a **material fact** (ADR-005 §3.11 — a policy change voids in-flight approvals), and the brake is enforced **by refusing to mint a grant** (ADR-004 §2.4).

**These were not written in Wave 2 because they were not in scope, and I did not expand the scope.** They are the recommended Wave 3.

| ADR | Minimum contract it must provide |
|---|---|
| **ADR-010 — Policy, Autonomy & Learned Rules** | A **typed, versioned, deterministic** policy predicate, evaluable inside the checkpoint, returning a **never-null gate decision**. Must resolve **Stream B lesson L-C**: an owner-stated rule (*"never bill without a POD"*) either **compiles to an enforceable policy** or is **honestly reported as memory**. **A prompt-string is not a policy.** Also owns ADR-005 Q3 (drift tolerance bands — **recommend NO for money-out**) and ADR-007 Q3 (auto-disabling a bad linker rule). |
| **ADR-011 — The Human Brake & Operational Control** | Brake scope (tenant / lane / action class), engagement + disengagement authority, **and the guarantee that engaging it stops effects *without killing in-flight work* — by refusing to mint** (ADR-004 §2.4 step 7). Must define what happens to already-`CLAIMED` grants (**answer: nothing — they may already have acted; they go to verification**). |

**ADR-012 (migration/coexistence) is referenced but is NOT implementation-blocking** — ADR-004 §5 already states the coexistence rule (*claim from the same ledger, or do not act*).

### 3.2 ⛔ Live code defect — recorded, not fixed *(no implementation code in Wave 2)*

> ### **`_commit_identity` (`operation_router.py:335`) is a live double-billing hole in the frozen baseline.**

**(A)** `approved_amount` is **part of the commit key**. Two proposals to bill load 4471 — one reading **£2,850**, one reading **£3,100** — have **different commit keys**. **Commit-once does not fire. Both commit. The customer is invoiced twice.** *Commit-once fails in exactly the case it exists for, because the amount is the field most likely to differ between two racing reads.*

**(B)** `if not amount: return None` ⇒ **every non-money effect has no commit-once protection at all.** A POD can be filed twice; a status can be written twice.

**Fixed by ADR-009 §4** (the commit key is the identity of the **effect**, not the content of the **decision**). **The code is unchanged, per instruction.** This is now a **known, recorded, blocking defect against `f0e801b`** and it should be the **first implementation task** of the migration.

---

## 4. REMAINING CUSTOMER-VALIDATION QUESTIONS

**None of these block implementation.** Each has a **fail-closed default** — where the answer is unknown, the work goes to a human.

| # | Question | Owner | Default if unanswered |
|---|---|---|---|
| **V1** | May a **written-off load be re-billed** when a POD surfaces in month 4? *(+ short-pay, TONU, post-close disputes)* | Freight policy | Generic reopening machinery **exists** (ADR-008 §2.14); the *when* goes to a human. |
| **V2** | **Approval TTLs** — how long is a rate good for? *(1 h / 8 h / 24 h are placeholders)* | Customer | Conservative defaults; **an expired approval is not a weak approval, it is not an approval.** |
| **V3** | **Which action classes need dual control**, at what threshold? | Customer/policy | Mechanism complete (ADR-005 §3.16); default single approval. |
| **V4** | **Registered deterministic identity rules** *(MC + date + amount? BOL? PRO?)* | Customer/domain | Deterministic ID-match only; everything else → **`AMBIGUOUS` → human.** |
| **V5** | **Registered conflict-resolution rules** *(does the TMS always beat the portal?)* | Customer | **No rule ⇒ every conflict goes to a human.** Safe, just more work. |
| **V6** | **Deferred-verification bounds** per TMS *(how long until a write is visible?)* | Per integration | Treat as `AWAITING_OBSERVATION` with an Expectation. |
| **V7** | Can a **commit key be written into the external record**, so a later read can deterministically discharge `NEEDS_VERIFICATION`? | Per integration | **If not: a human resolves it. We do not infer.** |
| **V8** | **Re-issue after credit** — distinct action class, or same effect repeated? | Customer | ⚠️ **Recommend a distinct action class** — modelling a re-issue as "the same effect again" is how a credit-and-rebill loop becomes a double-bill. |
| **V9** | **Partial payments** — one effect per remittance reference? | Customer | ⚠️ Recommend yes. |
| **V10** | **Per-lane exception ageing/escalation thresholds** | Product | Ages and escalates; **never expires**. |

---

## 5. CROSS-ADR CONSISTENCY REVIEW

**Checked mechanically across all nine ADRs, not by eye.**

| Check | Result |
|---|---|
| **State names identical** | ✅ **`NEEDS_VERIFICATION` (45) · `UNKNOWN_OUTCOME` (22) · `VOID_ON_DRIFT` (17) · `COMPENSATION_FAILED` (8) · `EXPIRED_UNCLAIMED` (4)** — no variant spellings. *(Two prose instances of "UNKNOWN OUTCOME" with a space, both immediately followed by the correct backticked state — emphasis, not a state reference.)* |
| **Provenance classes identical** | ✅ All six, one spelling each, across ADR-002/007/008. |
| **Gate decisions identical** | ✅ `HUMAN_REQUIRED` · `AUTONOMOUS_WITHIN_CAPS` · `UNGATABLE_PERMANENT`. |
| **Evidence conditions** | ✅ Exactly five — `absent` · `unknown` · `consistent` · `conflicting` · `stale` — never collapsed. |
| **No duplicate concepts** | ✅ See §0. Every temptation was refused **with a written justification**. |
| **No ADR contradicts another** | ✅ — **after one fix**, below. |
| **No guarantee rests on developer discipline** | ✅ Every guarantee is a **type**, a **DB constraint**, a **CI gate**, an **illegal transition**, or a **merge-gating test**. |
| **Every frozen document remains valid** | ✅ — see §6. |

### 5.1 The one inconsistency found — and fixed

**`UNKNOWN_OUTCOME` was overloaded:** it is a `VerificationOutcome` (ADR-006 #3) **and** an External Effect state (ADR-008 §3.3) — **and three different outcomes (#3 unknown, #7 blind, #8 conflicting) all map into that single state.**

**Left alone, this would have destroyed the exact distinction ADR-006 exists to draw.** *"I was blind"*, *"what I found contradicts what you approved"*, and *"I genuinely cannot tell"* demand **three different questions to the human** — and they would have arrived as one indistinguishable state.

**Fixed (ADR-006 §3.3.1):** the `UNKNOWN_OUTCOME` state now carries a **mandatory `unknown_reason`**; a transition into it without one is an **illegal transition**. **No new state** — the *consequences* are identical (freeze, escalate, never retry, never auto-resolve), but **the conversation with the owner is not**, so the reason is retained.

*(`OBSERVATION_CONFLICTING` is the one to watch: it can mean **something else acted on this entity** — it is the R-02 signature, arriving as data.)*

---

## 6. DOES ANY HIGHER-LEVEL DOCUMENT REQUIRE AMENDMENT?

> ## **NO. Zero amendments required.**

Every frozen document remains valid, and **Wave 2 was checked against each**:

| Frozen document | Verdict |
|---|---|
| **Engineering Principles** | ✅ **Reinforced.** P2 (guards never model-evaluated) is now enforced by ADR-007 §4.2 — **confidence prioritizes, it never authorizes.** P11 (*a model's output is a claim, not a fact*) is enforced by the `MODEL_EXTRACTED` / `MODEL_INFERRED` split. |
| **Operating Model** | ✅ **I7, I8, I10, I11 all strengthened.** **I8** (*missing ≠ contradictory*) is the spine of ADR-006 (`VERIFIED_FAILURE` vs `OBSERVATION_UNAVAILABLE`) and ADR-007 (`conflicting` ≠ `unknown`). Money-out remains **policy**, not a permanent truth (§7.6) — **untouched**. |
| **ADR-001** | ✅ **C4 is now mechanized** (ADR-005 §3.12: material facts re-read **live**, never from a cache, inside the checkpoint). C5's five conditions preserved exactly. |
| **ADR-002** *(incl. amendments A1, A2)* | ✅ **ADR-007 is the machinery of A2.** `provenance_class`, R-P1/R-P2/R-P3 are enforced, not merely honoured. |
| **ADR-003** | ✅ **Now a column, not a policy.** A counterparty's *"you approved this"* is `MODEL_EXTRACTED`, **cannot be promoted (R-P2)**, blocks the payable, and raises a fraud signal. |
| **ADR-004** | ✅ **Completed, not contradicted.** ADR-009 **composes** the commit key ADR-004 used but never defined; ADR-005 defines the fingerprint it carried; ADR-006 defines the unknown-outcome semantics it named. **The Effect Grant Ledger is used, not duplicated** — exactly as instructed. |
| **ADR-008** | ✅ **Completed, not contradicted.** All eight verification outcomes fit its existing state set. `ApprovalSignature` and `unknown_reason` are **fields on existing machines**, not new machines. |
| **Current-State Reconciliation · Freight Discovery** | ✅ Evidence documents; unaffected. |

---

## 7. IS THE TARGET SPECIFICATION READY FOR REVISION?

> ## **YES — with two conditions, and I would not start without them.**

**What is now ready.** The specification's four worst sections have real mechanisms behind them: **§12** (lifecycles — ten complete tables), **§19** (the pipeline — durable, transactional, capability-gated), **§11.1** (the Command entity — deleted), **§29.2** (actuation topology — co-located in v1, contract-stable under later separation).

**The two conditions:**

1. ### **ADR-010 and ADR-011 must exist first** (§3.1).
   The specification will have to describe the pre-effect checkpoint — **the single most important function in the system** — and **two of its seven steps currently have no contract.** Writing §19 now would mean writing prose over a hole, which is **exactly how the specification got into trouble the first time** (F-19: *"§12 lists the requirements of a lifecycle and then defines not a single state"*).

2. **The revision must be a rewrite of the affected sections, not a patch.**
   Nine ADRs now constrain the specification. **§11, §12, §19, §23, §29 are substantially superseded**, and a patch would leave contradictions between the ADRs and the document they are supposed to govern — **a lower layer contradicting a higher one**, which the document hierarchy forbids.

**Recommendation: Wave 3 = ADR-010 + ADR-011 (two ADRs, tightly scoped). Then the specification revision, in one pass.**

---

## 8. WHAT WAVE 2 ACTUALLY BOUGHT

**Three defects that would have cost real money are now structurally impossible:**

1. ### **The wrong amount cannot be paid.** *(F-01.)* The owner approves £2,850; the TMS moves to £3,100; **the effect does not happen**, and the owner is told exactly which number moved, from what, to what, and when.
2. ### **The customer cannot be billed twice.** *(F-10 + the live commit-key defect.)* The commit key is the identity of the **effect**, not the content of the **decision** — so the two racing reads that used to produce two invoices now produce **one**, at the database level.
3. ### **A guess cannot become a fact.** *(L-A, F-05.)* `MODEL_INFERRED` may never gate a consequential action **at any confidence**, `OWNER_ASSERTED` may never be machine-recomputed, and a counterparty's claim of authorization is **a fraud signal, not an input.**

**And one thing the system can now do that it could not before: say "I don't know."**

> `NEEDS_VERIFICATION` is non-terminal, human-owned, never auto-resolves, and **holds its commit key indefinitely.**
>
> **It will be uncomfortable. Engineers will want to add a timeout to it. That timeout is a decision to guess about money, and it is the one change that would undo this entire wave.**
