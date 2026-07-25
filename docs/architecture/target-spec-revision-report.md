# Target Specification — Canonical Revision Report

**Subject:** `docs/architecture/target-system-specification.md` — **Revision 2**, a complete rewrite.
**Supersedes:** Revision 1 (`8c94646`, 1,088 lines) **in full.**
**Result:** **1,614 lines · 74 MUST blocks · 141 named validating tests.**
**Baseline:** `f0e801b4dfd611345ca6c2842e946d58a7512ae5`
**Date:** 2026-07-13

---

## 1. WHY THIS WAS A REWRITE AND NOT A PATCH

**Revision 1 predates the entire ADR set.** Patching it would have preserved language that the frozen architecture has since overruled — and one of those preserved lines is currently **shaping production code**:

> ### **`target-system-specification.md:400` (Rev 1) MANDATED: *"the type system MUST distinguish an Event from a **Command**."***
> ### **ADR-008 §2.12 DELETED the Command entity. And the CODE FOLLOWS THE SPEC — `CommandIntent`, 51 uses.**
>
> **That is a lower layer contradicting a higher one, live in the repository.** *Patching around it would have left the contradiction in place and called the document current.*

**Revision 1 also revalidated material facts BEFORE the human gate.** Under Revision 2 the checkpoint is **after** it (§19.4, **M-42**). ### **The old sequence would have paid the wrong amount. That is F-01, and it is the defect this architecture exists to prevent.**

---

## 2. SECTIONS REWRITTEN

**All 32 sections were rewritten or rebuilt. Structure preserved; §33 (traceability) and §34 (governance) formalized.**

| § | Section | What changed |
|---|---|---|
| **3** | Canonical Vocabulary | ### **Normative by reference to the Semantic Model.** Twelve terms an implementer must not get wrong. |
| **6** | Truth & Authority | ### **Eight kinds of thing, not one.** The five evidence conditions. `projection ≠ authority`. |
| **7** | Tenancy & Authority | `tenant_id` **first in every key**; cross-tenant breach ⇒ ### **GLOBAL brake**. |
| **8** | Domain Entities | ### **`party` FORBIDDEN — `customer` (owes us) / `carrier` (we owe them), and `money_direction`.** |
| **9** | Evidence & Provenance | ### **The six `provenance_class` values + R-P1/R-P2/R-P3.** |
| **10** | Identity & Correlation | Deterministic-first; ### **a single weak candidate is still AMBIGUOUS**; trusted-identifier **collision characteristics**; ### **supersession ≠ correction**. |
| **11** | Domain Events | ### **The `Command` entity DELETED.** Full envelope; outbox/inbox/upcasters/parking; **replay structurally inert**. |
| **12** | Lifecycles | ### **13 COMPLETE transition tables** + **10 domain lifecycle contracts** + generic reopening. |
| **13** | Work Model | 1:N; ### **an accountable human owner, always.** |
| **14** | Triggers & Time | Durable timers; ### **never a background sweep.** |
| **15** | Service Architecture | The safety-kernel diagram; ### **the CI import gate.** |
| **16** | Data Architecture | ### **The two unique indexes that carry the architecture.** The three read classes. |
| **17** | Event Backbone | Outbox → relay → inbox. |
| **18** | Integration & Actuation | ### **The 7-step adapter validation algorithm.** Verification modes declared up front. |
| **19** | **Action Pipeline** | ### **The 7-check atomic checkpoint. The Witness. The Effect Grant Ledger. THE COMMIT KEY — and the live defect.** |
| **20** | Safety Kernel | ### **Four gate decisions, NOT NULL. Policy cannot branch on a guess. The one-way ratchet. Precedence.** |
| **21** | Approval & Oversight | Material facts + `fp_v1` + ### **the drift explanation**. ### **The brake: admission control, five in-flight positions.** |
| **22** | Knowledge & Learning | ### **A prompt-string is not a policy.** |
| **23** | Agent Orchestration | ### **A `ProposedIntent` and nothing else.** |
| **24** | Security | ### **Counterparty fraud as the most common REAL attack.** A hostile TMS: **out of scope, stated not hidden.** |
| **25** | Observability | ### **Explain with the beliefs OF THAT DAY.** Rebuild divergence ⇒ Sev-0 ⇒ brake. |
| **26** | Verification & Recovery | ### **8 outcomes. Proof of absence requires a HEALTHY channel.** |
| **28** | Testing | ### **Green tests are not evidence. Only a live drive is.** |
| **29** | Deployment | Co-located v1; ### **no mock adapter in production.** |
| **30** | Migration | ### **Baseline recorded. Entry-point disposition. Semantic migrations. SAFETY TASK #1.** |
| **31** | Sequencing | ### **Wave 2 cannot be decomposed.** |
| **32** | Open Questions | 16, **all fail-closed**, none blocking. |
| **33** | Traceability | ### **Rebuilt: mechanism + test + status for every requirement.** |

---

## 3. OBSOLETE CONCEPTS REMOVED

| Removed | Replaced by |
|---|---|
| ### **`Command` as a canonical entity** | ### **Intent → Work Item. Execution → Pipeline Instance. Events record what occurred.** |
| **"workflow run"** | **Pipeline Instance** |
| **`lane`** *(as action class)* | **action class** — ### **`lane` is reserved for its REAL freight meaning (an origin–destination pair)** |
| **"commit identity"** | **commit key** — ### **and RECOMPOSED (§19.7)** |
| **`operation_action_claim`** | **Effect Grant** |
| ### **ambiguous `done`** | ### **`VERIFIED_SUCCESS` — and nothing else** |
| **Revalidation before the human gate** | ### **The atomic checkpoint AFTER it (F-01)** |

---

## 4. ADRs INCORPORATED

**All eleven, plus amendments A1–A4.** ADR-001 (C4 → the read classes) · ADR-002 (+A1, A2 → §6, §9) · ADR-003 (→ `PERMANENT_HUMAN_ASSERTION_REQUIRED` + the fraud signal) · ADR-004 (+A3 → §19) · ADR-005 (→ §21) · ADR-006 (→ §26) · ADR-007 (→ §10) · ADR-008 (+A4 → §12) · ADR-009 (→ §16.1, §19.7) · ADR-010 (→ §20) · ADR-011 (→ §21.4).

**Plus the Semantic Model's 28 invariants and 4 Stream B lessons (L-A…L-D), each with a mechanism and a test.**

---

## 5. REVIEW FINDINGS CLOSED

**Closed by mechanism + test:** F-01 · F-02 · F-03 · F-04 · F-05 · F-06 · F-08 · F-09 · F-10 · F-11 · F-12 · F-13 · F-14 · F-16 · F-17 · F-18 · F-19 · F-20 · F-21 · F-22 · F-25 · F-26 · F-29 · F-30 · F-33 · F-34 · F-35 · R-01 · R-03 · L-A · L-B · L-C · L-D.

### 5.1 Still open — **two, and both are honest**

| # | Finding | Why it is still open |
|---|---|---|
| ### **F-07 / R-02** | Multiple runtimes, one effect | ### **The mechanism is complete (shared ledger + commit namespace + the two indexes). It closes on IMPLEMENTATION, not on a document.** **Six entry points can still produce a live financial write, and the runbook warning is DISCIPLINE, not a fix.** |
| ### **The live commit-key defect** | `_commit_identity` | ### **Recorded in §19.8 and §30.1. NOT fixed — no implementation code in this task. It is SAFETY TASK #1.** |

---

## 6. SEMANTIC MIGRATIONS REQUIRED IN CODE — **not performed**

| Symbol | Uses | Canonical | Hazard |
|---|---|---|---|
| ### `lane` | **291** | action class | ### **It means TWO things today — action class AND origin–destination pair — in a codebase that gates money on one of them. MUST NOT be find-and-replaced.** |
| `run` / `workflow_runs` | **423** | Pipeline Instance | the ancestor — **generalize, don't discard** |
| ### `CommandIntent` | **51** | `ProposedIntent` | ### **Named after a DELETED entity — and it followed Revision 1 of this very document.** |
| ### `commit_identity` | **16** | commit key | ### **A rename AND a recomposition — it is the double-billing fix.** |
| `operation_action_claims` | 1 | `effect_grants` | discipline right, **key wrong** |
| ambiguous `done` | many | `VERIFIED_SUCCESS` | — |
| overloaded `claim` | many | *(both correct)* | ### **QUALIFY, never rename** |

---

## 7. UNRESOLVED CUSTOMER-VALIDATION QUESTIONS

**Sixteen (V1–V16, §32).** ### **NONE block architecture. NONE block implementation.** Every one has a fail-closed default, and **every default sends the unknown case to a human**.

**The three I would actually ask a broker first:** ### **how long is a rate good for** (V2, the approval TTL) · ### **does the TMS always beat the portal** (V5, conflict rules) · ### **is a re-issue after a credit a different act** (V8 — *modelling it as "the same effect again" is how a credit-and-rebill loop becomes a double-bill*).

---

## 8. MECHANICAL CONSISTENCY RESULTS

**Run by grep, not by eye.**

| Check | Result |
|---|---|
| **Deprecated terminology in the body** | ### ✅ **ZERO.** *(Seven grep hits, all legitimate: the header's own deprecation list, §11.1's note explaining the deletion, and §19.8's verbatim quote of the defective code.)* |
| **Gate decisions** | ✅ All four canonical members; ### **zero stale `UNGATABLE_PERMANENT` / `HUMAN_REQUIRED`** *(one hit in §34, a historical reference naming the defect that was fixed — not a use)*. |
| **Provenance classes** | ✅ All six, one spelling each. |
| **State names** | ✅ `NEEDS_VERIFICATION` (20) · `UNKNOWN_OUTCOME` (20) · `VOID_ON_DRIFT` (5) · `OBSERVATION_UNAVAILABLE` (8) — no variants. |
| **Verification outcomes** | ✅ All eight; `unknown_reason` mandatory. |
| **Evidence conditions** | ✅ Exactly five, never collapsed. |
| **Commit-key semantics** | ✅ ### **The amount is structurally absent.** |
| **Tenant fields** | ✅ First in every key, index, envelope, and adapter call. |
| **Brake semantics** | ✅ Admission control; **never kills a worker**; two states; **never expires**. |
| **Ownership rules** | ✅ `owner_id NOT NULL`; **I1** everywhere. |
| **Every MUST has a mechanism + test** | ### ✅ **74 MUST blocks · 141 named tests.** |
| **No lower layer contradicts an ADR** | ✅ — ### **and §34 states that if it ever does, THE ADR WINS and this document is defective.** |

---

## 9. IS THE SPECIFICATION READY FOR SPECIFICATION ENGINEERING?

> # ✅ **YES.**

**Every gate I set across four waves is met:**

- ✅ **The atomic pre-effect checkpoint is fully specified.** All seven steps have mechanisms. It produces ### **one immutable Checkpoint Witness, or none — there is no partial authorization.**
- ✅ **Thirteen complete state machines**, plus ten domain lifecycle contracts. ### **Two engineers implementing from §12 now produce the same system** *(F-19 was that they would not)*.
- ✅ **Every MUST carries its mechanism, owner, durable state, failure behaviour, event, and test.** ### **There is no guarantee in this document that rests on developer discipline.**
- ✅ **The canonical language is used verbatim**, and the obsolete concepts — above all `Command` — are gone.
- ✅ **No open question blocks anything.**

**Entity, event, adapter, workflow, and acceptance specifications may now begin** — and they may be derived **without inventing a single safety-critical mechanism**, which was the whole test.

### 9.1 Two things that must go with them

1. ### **SAFETY TASK #1 — the commit key.** It is a **live double-billing hole** in the current baseline. **It should be the first line of implementation code written.**
2. ### **R-02 is open and will stay open until the cutover.** ### **The runbook warning is operator discipline. I will not call it a fix, and neither should the spec.**

---

## 10. WHAT THIS REVISION ACTUALLY CHANGED

**Revision 1 said what the system should be. ### Revision 2 says how each of those claims is enforced, who owns it, what breaks when it doesn't hold, and which test proves it.**

**Three of its statements would have caused a money defect if implemented as written in Revision 1:**

1. ### **Revalidate before the human gate** ⇒ **the wrong amount gets paid.** *(Now: the checkpoint is after it.)*
2. ### **Mandate a `Command` type** ⇒ **the code did, and the entity was deleted a wave later.** *(Now: intent lives in a Work Item; the Pipeline Instance IS the command.)*
3. ### **"The single effect boundary"** with no mechanism ⇒ **eleven entry points reached the live TMS, and a production flag routed approved payables into a mock ledger while reporting `DONE`.** *(Now: six enforcement layers, and the mock path is severed in the baseline.)*

> ### **A specification that states a guarantee without a mechanism does not create the guarantee. It creates the belief that someone else already did.**
