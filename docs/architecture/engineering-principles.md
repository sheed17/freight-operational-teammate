# Neyma — Engineering Principles

**Status:** Constitution. This document governs every architectural decision that follows it.
**Scope:** Engineering philosophy only. **No freight workflows. No entities. No services. No implementation.**
**Date:** 2026-07-09

---

## 0. WHY THIS DOCUMENT EXISTS

Neyma operates a business's **money, documents, and relationships** across systems it does not own, using a component (an LLM) that is **non-deterministic and confidently wrong**. That combination is unforgiving. A web app that renders the wrong number shows a bad page. Neyma that renders the wrong number **pays the wrong carrier**.

Every principle below is stated as a rule, followed by **the reason it exists**. Where the reason is scar tissue from this project, it is marked **`SCAR`** — a defect we actually shipped, found live, and fixed. Principles earned from real failure are worth more than principles copied from a blog post.

Principles are numbered (`P1`…) so future documents can cite them. **When a design decision conflicts with a principle, the principle wins, or the principle gets amended in writing — never silently overridden.**

---

## 1. CORE DESIGN PRINCIPLES

### P1 — Reliability over autonomy
A system that does less, correctly and predictably, beats a system that does more, sometimes. **We never trade correctness for capability.** Autonomy is a reward for demonstrated reliability, not a design goal.

### P2 — Deterministic systems before AI reasoning
If a decision can be made by deterministic code, **it must be**. The LLM is used for *understanding ambiguity* (unstructured language, messy documents, intent) — never for *arithmetic, comparison, policy, or authority*. **Money math is never model-judged.**

### P3 — The model proposes; the runtime disposes
The LLM may **suggest** an action. The runtime **supplies the consequential values** and **executes**. It is structurally impossible for the model to originate a value that moves money or touches a resource.
> **`SCAR`** — the *money fence*: the model never chooses an amount; the runtime substitutes the human-approved value. And the *document fence*: the model chooses the field, the runtime supplies the file. A model that can name a file path can name **any** file path.

### P4 — Evidence over confidence
A high model confidence score is not evidence. **Evidence is an observation of the world.** An action is justified by what the system *saw*, not by how sure it *felt*. Confidence may route work; it may never authorize it.

### P5 — Nothing is done until the system confirms it is done (verify by readback)
Completion is asserted only after **reading the resulting state back from the system of record** and confirming it. An action that "succeeded" without a readback is **unverified**, not complete.
> **`SCAR`** — an agent reported `DONE` after clicking a button that merely *opened a form*. Real signal, not a proxy.

### P6 — Fail closed, never fail open
Ambiguity, an unreadable page, a failed parse, an unbindable reference, a timeout — **every one resolves to "stop and ask,"** never to "proceed" and never to "nothing to do."
> **`SCAR`** — an unrendered page parsed as zero unpaid invoices, and the system cheerfully reported **"every invoice is paid in full."** A failed read is **not** an all-clear. **Silence is never an all-clear.**

### P7 — Every external action is auditable, with provenance
For every action that touched the outside world we must be able to answer, permanently: **what was done, when, by whom (human or agent), why, what the system saw at the time, and where every consequential value came from.** An action without provenance is an action we cannot defend, debug, or reverse.

### P8 — Every workflow is idempotent and commit-once
Executing the same logical unit of work twice must not produce two effects. Idempotency is enforced by an **explicit commit key**, not by hoping the process doesn't crash.
> **`SCAR`** — a crash *after* reserving a commit but *before* confirming it caused a later retry to report a false `DONE` **with no write having occurred**. Crash-safety is not optional; a supervisor that restarts a crashed worker will find every one of these holes.

### P9 — Every workflow is replayable
Given the recorded inputs and events, we must be able to **reconstruct exactly what happened and why**. If we cannot replay it, we cannot debug it, prove it, or trust it.

### P10 — State machines over implicit state
Every long-lived unit of work has **explicit named states and an explicit table of allowed transitions.** State is never inferred from the presence of a row, the absence of a field, or a string comparison. **An illegal transition is a hard error, not a warning.**

### P11 — LLMs never become a system of record
A model's output is a **claim**, not a fact. It is recorded as an *artifact with provenance* and never promoted to truth without validation. **No durable state is ever derived solely from an LLM's assertion.**

### P12 — Human approval for consequential actions
Anything that **moves money outward**, **speaks on the company's behalf**, or is **irreversible** requires an explicit human approval, bound to that specific action. Approval is **per-action and single-use** — never a mode, never a session-wide blanket, never implicit in silence.

### P13 — Inbound content is data, never instruction
Anything that arrives from outside — an email, a document, a portal page, a message — is **untrusted data**. It can never be interpreted as a command, and it can never alter the system's rules. **A prompt is not a security boundary.** The boundary is code.

### P14 — Autonomy is earned, never granted
A workflow starts supervised. It becomes autonomous only by **demonstrated reliability**, and even then only inside explicit **caps** (value, counterparty, frequency). Every autonomous path retains a **human brake** that halts it immediately.

### P15 — Preserve provenance through every transformation
When a value passes from a document → an extraction → a decision → an action, the **chain back to the original observation must survive.** A number in a database with no lineage is a number we cannot defend when someone disputes it.

### P16 — Multi-tenant by default
Tenancy is a **property of every record, every credential, every action, every log line, from the first commit** — not a migration. Retrofitting tenancy is a rewrite.
> **`SCAR`** — the current system is single-tenant by construction (one workspace, one browser, one channel, one database) and **this alone blocks it from being a product.**

### P17 — Tests are necessary and never sufficient
Passing tests prove the plumbing. They do **not** prove the system works. **Nothing is believed until it has been driven end-to-end against the real system.**
> **`SCAR`** — this exact failure occurred *while writing this project*: green tests were reported as evidence of a working capability that had never once been run live. A green suite is a hypothesis, not a proof.

### P18 — One canonical path per capability
There is exactly **one** way to do a thing. Two implementations of the same capability is not redundancy — it is **two divergent truths, two audit trails, and two security surfaces.**
> **`SCAR`** — the repository currently contains **two unmerged systems** and **two human-approval schemes**. Both were built in good faith. Neither can now be reasoned about in isolation.

---

## 2. ARCHITECTURAL PHILOSOPHY

### 2.1 State
- State is **explicit, named, durable, and typed.** If it matters, it is written down; if it is written down, it has an owner.
- **Derived state is always recomputable** and never the only copy of a fact.
- **No global mutable context.** Context is passed explicitly, scoped to a unit of work, and dies with it.
- **We do not hold state we cannot reconstruct**, and we do not scrape the same fact repeatedly *in place of* holding it.
- **Where a fact is authoritative is a declared property of that fact**, not an accident of which code wrote it last.

### 2.2 Events
- **What happened is a first-class, immutable record.** State is the *consequence* of events, never a substitute for them.
- Events are **append-only, ordered, and carry provenance.** We never mutate history to make the present look tidy.
- An event describes **an observation or a decision** — not an intention. "We intend to pay" is state. "We paid, and here is what we saw when we did" is an event.
- **If it isn't an event, it didn't happen** — and we cannot prove it did.

### 2.3 Evidence
- Evidence is **an observation of the external world, captured at a point in time, attributable to a source.**
- Every consequential decision must be traceable to evidence. **"The model said so" is not evidence.**
- Evidence is **kept**, not summarized away. The summary is a convenience; the observation is the record.
- **Absence of evidence is a state** (`unknown`), and it is **not** the same as evidence of absence (`none`). Conflating those two is how P6 gets violated.

### 2.4 Knowledge
- Knowledge is **learned rules and context** — durable, correctable, and attributable.
- Knowledge is **retrieved and injected deliberately**, scoped to the task at hand. It is never dumped wholesale into a context window.
- **Every piece of knowledge has a provenance and an owner**: who asserted it, when, and from what. A rule nobody can trace is a rule nobody can revoke.
- **Knowledge is not truth.** It informs a decision; it does not authorize one.
- **Human corrections are the highest-value input the system receives.** A correction must be captured, attributed, and made to change future behavior — otherwise the human is doing unpaid, repeated work.

### 2.5 Agents
- An agent is **a bounded worker with a goal, a limited action set, and a hard budget** — not an open-ended intelligence.
- An agent operates **inside a fence it cannot reach past.** Its action space is enumerated, its consequential values are supplied to it, its steps are capped, and its escapes are explicit.
- **An agent's job is to handle ambiguity**, not to exercise authority.
- Agents are **observable**: every step, every observation, every decision is recorded.
- **An agent that is stuck must escalate, not improvise.** Repeating a failing action is a bug, not persistence.

### 2.6 Services
- A service owns **one capability and one body of state.** If two services need to write the same fact, the boundary is wrong.
- Boundaries are drawn along **ownership and failure domains**, not along nouns or along team convenience.
- Services communicate through **explicit contracts**. A contract that can be violated silently is not a contract.
- **A module that does routing, validation, execution, rendering, and persistence is not a service — it is a liability.**
  > **`SCAR`** — a single ~2,000-line module in this repo currently performs HTTP routing, signature verification, payload parsing, proposal construction, approval verification, background execution, conversational routing, external reads, and rendering.

### 2.7 Workflows
- A workflow is **an explicit state machine**, not a call stack and not a chain of callbacks.
- Every workflow is **resumable** (it survives a crash), **idempotent** (P8), **replayable** (P9), and **cancellable**.
- Every workflow declares its **gates** up front: what it requires before it may run, and what it requires before it may commit. **Gates are enforced at the front door, not discovered mid-flight.**
- A workflow that cannot be safely interrupted at any step **is not production-ready.**

### 2.8 Humans
- The human is **part of the system, not an escape hatch.** Their approvals, corrections, and escalations are **first-class, recorded, and attributable events.**
- We **never waste a human's attention.** Escalating everything is the same failure as escalating nothing — it teaches the human to rubber-stamp.
- An escalation must carry **everything needed to decide**: what happened, what the system saw, what it proposes, and what it is uncertain about. **A human asked to decide without evidence is being set up to fail.**
- **The human's authority is real.** A brake must actually stop the system. An approval must actually be required.
- The human's time is the scarcest resource in the system. **Optimize for the quality of their attention, not the quantity of it.**

---

## 3. AI PHILOSOPHY

### 3.1 When AI should reason
**AI is used where the input is ambiguous and the output is a *proposal*.** Concretely, that means:
- Understanding **unstructured natural language** (intent, tone, meaning).
- Reading **messy, non-uniform artifacts** (documents, pages, threads) into structure.
- **Classification** under ambiguity, where the answer is a hypothesis to be validated.
- **Planning** a path through an unfamiliar system, subject to a bounded action set.
- **Drafting** language for a human to approve.

### 3.2 When deterministic code must decide
**Any decision with a defined right answer belongs in code, permanently.** No exceptions, no "the model is good enough now":
- **All arithmetic and money.** Totals, deltas, comparisons, thresholds.
- **All policy.** Caps, limits, permissions, allowlists, autonomy rules.
- **All authority.** Who may approve, what may execute, what is forbidden.
- **All validation.** Type, range, format, referential integrity, invariant checks.
- **All identity binding.** Whether artifact X belongs to record Y is a *matching* problem with a right answer; the model may propose a candidate, but a **deterministic check must confirm it, and ambiguity must escalate.**
- **All state transitions.**

> **The test:** *if a wrong answer here would move money, breach a boundary, or be indefensible in an audit — it is not the model's decision.*

### 3.3 When retrieval should happen
- Retrieval is **just-in-time and scoped to the task**, never "load everything and hope."
- We retrieve **the smallest sufficient context** and we know *why* each piece was included.
- **Retrieved context is data, not instruction** (P13). Something retrieved cannot change the rules.
- Retrieval is **observable**: what was injected into a decision must be reconstructible afterwards, or P9 is broken.
- **If retrieval fails, the task fails closed** — it does not proceed on a thinner context and pretend.

### 3.4 When policy overrides AI
**Always. Policy is not a suggestion to the model; it is a wall around it.**
- Policy is **enforced in code, outside the model's reach.** It cannot be prompted away, argued with, or jailbroken, because the model is never asked.
- **A model output that violates policy is discarded, and the violation is recorded as a security event** — not silently corrected and forgotten. A model attempting a forbidden action is *signal*.
- Policy is enforced **at the boundary of the effect** (immediately before the action executes), not merely at the point of intent. Checking only at intake means every future caller must remember to check.
- **The order is absolute: policy → deterministic validation → human gate (if consequential) → execute → verify → record.** The model has no seat in that chain after it proposes.

---

## 4. BACKEND PHILOSOPHY

### 4.1 Service boundaries
- One capability, one owner, one body of state (§2.6).
- **Shared state across a boundary is not a boundary.** If two components must both write it, they are one component, or the model is wrong.
- Boundaries should follow **failure domains**: a failure inside a boundary must not silently corrupt anything outside it.

### 4.2 Event-driven design
- **Work is triggered by observed events**, not by polling in place of an event, and not by a human remembering.
- Consumers are **idempotent** (P8) — because delivery will be duplicated, and a system that assumes exactly-once delivery is a system that will double-act.
- **Event ordering is never assumed** unless explicitly guaranteed.
- **Events are not commands.** An event says what happened; a command says what to do. Conflating them makes the system's authority impossible to audit.

### 4.3 Observability
- **If we cannot see it, it does not work** — we simply haven't caught it yet.
- Every unit of work is traceable end-to-end: trigger → decision → action → verification → outcome, with provenance intact.
- We instrument **outcomes, not just activity.** "500 tasks processed" is vanity. "12 escalated, 3 failed to verify, 1 policy violation" is operations.
- **Health must be honest.** A health surface that reports green while the system is blind is worse than no health surface at all.
- **Silence must be alarming.** A component that stops emitting is presumed broken, never presumed idle.

### 4.4 Retries
- **Retries are explicit, bounded, and recorded.** Never silent, never infinite.
- **Only idempotent operations may be retried automatically.** A non-idempotent operation that fails is escalated, not re-attempted.
- **A retry must know why it is retrying.** Retrying a deterministic failure is a busy-loop, not resilience.
- **The unknown-outcome case is the dangerous one**: when we do not know whether the effect landed, we **verify** — we never blindly retry and we never assume it failed. (See P8 `SCAR`.)

### 4.5 Compensation
- **We prefer reversibility to cleverness.** Where possible, design so a mistake can be undone.
- Where an action **cannot** be reversed, it gets **a stronger gate before it**, not a compensation story after it. *"We'll fix it afterwards" is not a safety model for money.*
- Compensating actions are **themselves auditable, gated, and idempotent** — a rollback is an action, subject to every rule an action is subject to.

### 4.6 Failure recovery
- **Recovery is a designed path, not an improvisation.** Every workflow declares what happens on crash, on timeout, and on partial completion.
- The system must be able to answer, after any failure: **"did the effect land?"** If it cannot, that is a design defect, not an operational one.
- **Restart must be safe.** A supervisor that restarts a crashed worker must never cause a double-effect — which means crash-safety is a *precondition* of automatic restart, not a companion feature.
- **A degraded system announces itself.** It never quietly does less while appearing to do everything.

### 4.7 Replay
- Recorded events + recorded inputs must be sufficient to **reconstruct any past decision**.
- Replay is **the primary debugging tool** and the **basis of trust**. When the customer asks *"why did you do that?"* the answer is reconstructed, not remembered.
- **Replay must be side-effect free.** Reconstructing history must never re-execute it.

### 4.8 Testing
- **Determinism is tested exhaustively.** Anything with a right answer (money, policy, transitions, validation) gets tests that pin the right answer.
- **Non-determinism is bounded, not asserted.** We do not test that the model says a specific sentence; we test that **the fence holds no matter what it says.** *The correct test of the money fence is: the model tries to inject a value, and the value never reaches the world.*
- **Failure injection is a first-class test category.** Hostile states — stale pages, partial renders, expired sessions, mid-write crashes, duplicate deliveries, unreadable documents — must be **deliberately produced**, because they cannot be reliably provoked against a live system, and they are exactly where the money is lost.
- **Every test suite is a hypothesis until the workflow has run live.** (P17.) Live verification is a release gate, not a nice-to-have.

---

## 5. THINGS WE REFUSE TO DO

These are not preferences. **A change that does any of these is rejected, regardless of how much it improves the demo.**

| # | We refuse | Because |
|---|---|---|
| R1 | **No hidden state.** | State that isn't written down cannot be audited, replayed, or recovered. |
| R2 | **No duplicated sources of truth.** | Two copies of a fact means one of them is wrong and nobody knows which. |
| R3 | **No silent retries.** | An unrecorded retry is an unrecorded second attempt at a real-world effect. |
| R4 | **No implicit approvals.** | Silence is not consent. A mode is not an approval. A prior approval is not a future one. |
| R5 | **No global mutable context.** | It makes every behavior a function of unknowable history. |
| R6 | **No agent write without deterministic validation.** | The model's word is never the last check before the world changes. |
| R7 | **No model-chosen consequential value.** | Amounts, paths, recipients, identifiers: supplied by the runtime, never originated by the model. (P3) |
| R8 | **No prompt as a security boundary.** | Instructions are not enforcement. Enforcement is code the model cannot reach. (P13) |
| R9 | **No unverified completion.** | "It probably saved" is not a state. Nothing is `DONE` without a readback. (P5) |
| R10 | **No failed read rendered as a clean result.** | The single most dangerous bug class we have shipped. (P6) |
| R11 | **No irreversible action without a human gate.** | If it can't be undone, a human decides. |
| R12 | **No autonomy without caps and a brake.** | Unbounded autonomy is not a feature; it is an unpriced liability. |
| R13 | **No untraceable action.** | If we can't explain it later, we shouldn't have done it. (P7) |
| R14 | **No second implementation of an existing capability.** | Divergence is guaranteed; discovery of the divergence is not. (P18) |
| R15 | **No tenancy retrofit.** | It is a rewrite pretending to be a migration. (P16) |
| R16 | **No shipping on green tests alone.** | Tests prove the plumbing, not the product. (P17) |
| R17 | **No silent degradation.** | A system doing less must say so, loudly. |
| R18 | **No dead code in a live path.** | It will be executed eventually, by someone who assumed it was live for a reason. |

---

## 6. DEFINITION OF PRODUCTION-READY

**A workflow may not execute automatically until every one of these is true.** This is a gate, not a rubric. There is no partial credit and no "we'll add it after launch" — the items below are precisely the ones that are never added after launch.

### 6.1 Correctness
- ☐ Its **state machine is explicit**, with an enumerated transition table; illegal transitions are hard errors. (P10)
- ☐ It is **idempotent** under a durable commit key, and **crash-safe**: after any crash, the system can determine whether the effect landed. (P8)
- ☐ It is **replayable** from recorded events and inputs, side-effect free. (P9)
- ☐ Every **consequential value is runtime-supplied**, never model-originated. (P3)
- ☐ Every model output that matters is **deterministically validated** before it reaches the world. (R6)

### 6.2 Safety
- ☐ It **fails closed** on every ambiguity: unreadable input, unbindable reference, timeout, parse failure, low confidence. (P6)
- ☐ It **cannot mistake a failed read for an empty result.** `unknown ≠ none`. (§2.3)
- ☐ **Consequential actions are human-gated**, with per-action, single-use approval. (P12)
- ☐ **Policy is enforced in code at the effect boundary**, not in a prompt. (§3.4)
- ☐ **Inbound content cannot alter behavior.** The injection boundary is enforced and tested. (P13)
- ☐ If it is **irreversible**, the gate in front of it is stronger, and that is a deliberate, documented decision. (§4.5)

### 6.3 Accountability
- ☐ Every external action emits an **audit record with full provenance**: what, when, who, why, what was observed, and where each value came from. (P7, P15)
- ☐ Completion is asserted **only after readback verification.** (P5)
- ☐ We can answer **"why did you do that?"** by reconstruction, not by recollection. (§4.7)

### 6.4 Operability
- ☐ It is **observable end-to-end**, and its health surface is **honest** (it reports blind as blind, not as green). (§4.3)
- ☐ **Failure is a designed path**: crash, timeout, and partial-completion behavior are specified, not emergent. (§4.6)
- ☐ **Retries are explicit, bounded, recorded**, and only applied to idempotent operations. (§4.4)
- ☐ A **human brake exists and actually stops it.** (P14)
- ☐ It **degrades loudly**, never quietly. (R17)

### 6.5 Autonomy (additional gate — only if it is to run *unattended*)
- ☐ It has run **supervised**, live, long enough to have earned it. (P14)
- ☐ It runs inside explicit **caps**: value, counterparty, frequency.
- ☐ Its **failure blast radius is bounded and understood** — we can state, precisely, the worst thing it can do before a human notices.
- ☐ **Someone is accountable** for its behavior, and they know it.

### 6.6 The final gate
- ☐ It has been **driven end-to-end against the real system**, and someone watched it work. **A green test suite does not satisfy this.** (P17)
- ☐ **Its failure modes have been deliberately provoked** — not merely reasoned about. (§4.8)

---

## 7. HOW THIS DOCUMENT IS USED

- **It is cited.** Design documents reference principles by number. "This violates P6" is a complete and sufficient objection.
- **It is enforced at review.** A change that breaks a refusal (§5) is rejected on that basis alone.
- **It is amended, never bypassed.** If a principle is wrong, we change it in writing, with the reason. We do not quietly make exceptions — an unwritten exception is how a constitution becomes decoration.
- **It outlives the domain.** Nothing here depends on freight. If the domain changed tomorrow, this document would still be true.

> **The one-line summary, if the rest is ever lost:**
> **Be deterministic where it matters, be honest about what you don't know, never let the model touch the money, prove it happened before you say it did — and earn autonomy instead of assuming it.**

---
---

# EXTENSIONS (appended 2026-07-09)

> The sections above are unchanged. What follows **extends** the constitution; it does not revise it.
> Principle numbering continues from P18. Refusals continue from R18.

---

## 8. PRODUCT PHILOSOPHY

### P19 — We automate operational loops, not screens
A screen is **where work happens to be done today**. A loop is **the work itself**. Automating a screen binds us to a vendor's UI and dies when they redesign it. Automating a loop survives the vendor entirely.
> The question is never *"can we click this?"* It is *"what is the work, where does it start, and what must be true for it to be finished?"*

### P20 — We optimize for operational throughput, not UI interactions
Success is **work leaving the queue**, not sessions, clicks, dashboards viewed, or messages sent. Engagement is an **anti-metric**: a teammate you have to keep visiting is a teammate that hasn't done its job.
> A beautiful interface that does not reduce the queue has accomplished nothing.

### P21 — Every feature must remove work from a human
If a feature adds a place to look, a thing to check, a queue to monitor, or a decision to make that didn't exist before — **it is a cost wearing the costume of a feature.**
> The default outcome of software is *more* work for the human, not less. We are permanently fighting that default. **Anything we add must be paid for in work removed.**

### P22 — Every feature must have measurable operational value, named before it is built
Before it exists, we must be able to state: **what work disappears, for whom, and how we would know.** If we cannot state the metric, we do not yet understand the feature well enough to build it.
> "It would be cool if it could…" is not a justification. It is a hypothesis awaiting a metric.

### P23 — We model the business before we model the software
The domain is the master; the software is the servant. We understand **what the business actually does** — including the parts that happen off-system — before we design anything that claims to run it.
> **`SCAR`** — the entire reconciliation. We modeled *a TMS*, not *a brokerage*. The result: the persistent data model became a **document-processing run log** with no Customer, no Carrier, no Load — because we had modeled the tool the work was done in, rather than the work.

### P24 — The product is the loop **closing**, not the moment of action
An action taken but unverified, a document filed but never billed, an exception raised but never resolved — **none of these delivered value.** Value is realized **only at loop closure**, and our accounting of what we've achieved must be honest about that.
> A system that performs many actions and closes few loops is *busy*, not *useful*.

### P25 — Trust is the product, not a feature of the product
An owner hands us their money, their documents, and their reputation with their customers. **The first wrong action costs more trust than a hundred right ones earn.** The bar is therefore asymmetric, and it is *supposed* to be.
> This is why P1 (reliability over autonomy) is the first principle and not the fifth. **Capability that outruns trust is not progress; it is exposure.**

---

## 9. DOMAIN MODELING PRINCIPLES

### P26 — Business entities exist independently of software
If the business would still recognize a thing **with every computer turned off**, it is an entity. If it exists only because some code needed somewhere to put a value, **it is not an entity — it is a table**, and it must be named and treated as one.

### P27 — State transitions belong to the business, not the UI
A load does not become *delivered* because someone clicked a button. It became delivered **when the freight was accepted at the dock**; the button merely *recorded* that. We model **the event that occurred in the world**, and treat the UI as one (unreliable, delayed, incomplete) *reporter* of it.
> Modeling the click instead of the event is how a system becomes unable to represent anything that happened while nobody was at a keyboard.

### P28 — External systems are integrations, not the business
A vendor's schema is an implementation detail **of that vendor**. It must never become our domain model, and its identifiers must never become our identity.
> **`SCAR`** — `load_id`, a **row identifier in one TMS**, became the de facto identity of the business's most important concept. The vendor's table shape silently became our ontology. (See also the discovery: *order ≠ load ≠ movement ≠ leg ≠ stop ≠ TMS row.*)

### P29 — Never create an entity because it is convenient for code
Convenience entities are how a domain model rots. Each one is a small lie about the business that the next engineer will believe. **If it has no meaning to the people who run the company, it does not belong in the domain model.**

### P30 — Never collapse distinct concepts because they usually coincide
Two concepts that are *usually* the same are still two concepts. They coincide **until they don't** — and the day they don't is precisely the day money moves to the wrong place, because the model had no way to express the difference.
> Collapsing is easy to do and nearly impossible to undo: once code has assumed the two are one, every read, write, and join encodes the assumption.

### P31 — Model what is **true**, not merely what is **observable**
Things happen that leave no artifact. **An authorization exists even when no document records it.** A commitment is real before the paperwork catches up.
> If the model can only represent what we can *see*, then everything that happened out of view becomes either invisible or **misclassified as an error**. That is not a gap in coverage — it is a systematic misreading of the business.
> **A model that cannot represent "this happened, and I have no evidence of it" will confidently accuse honest people.**

### P32 — Identity resolution is a first-class domain problem, not a helper function
Deciding which real-world thing an artifact belongs to is **the highest-consequence inference the system makes.** Binding to the wrong record is the failure that quietly moves real money to the wrong party.
> It therefore gets what any first-class concern gets: **its own model, its own confidence, its own evidence, its own escalation path — and a deterministic confirmation before it is acted on** (§3.2). It is never a fuzzy string match buried in a utility module.

---

## 10. EVOLUTION PRINCIPLES

### P33 — Prefer extending an existing workflow to creating a new one
A new workflow is a new state machine, a new audit path, a new set of failure modes, and a new thing to keep correct forever. **Extension is cheap; proliferation is permanent.**

### P34 — Prefer strengthening a deterministic service to adding an agent
An agent is **the most expensive way to solve a problem**: non-deterministic, slow, costly per call, hard to test, and difficult to reason about under failure. It is justified **only where ambiguity is irreducible** (§3.1).
> If a problem can be solved by making a deterministic component smarter, that is **always** the better trade.

### P35 — Every new agent must justify, in writing, why an existing workflow cannot hold the responsibility
The justification is written **before** the agent exists, in the design document, and it must survive challenge. "An agent felt natural here" is not a justification. **The burden of proof is on the agent, always.**

### P36 — Minimize architectural surface area
Every service, queue, store, integration, and abstraction is a **permanent maintenance liability and a permanent failure mode**. Surface area compounds: each new component multiplies the number of interactions that must be correct.
> **The best component is the one we did not add.**

### P37 — Remove before you add
Every significant addition should name **what it replaces**. If nothing is replaced, the system just got bigger — and we should be certain that is what we intended.
> **`SCAR`** — this repository accumulated **two unmerged lineages, two human-approval surfaces, and three overlapping orchestrators.** Every one was added in good faith. **Not one was ever removed.** That is how a codebase becomes unreasonable-about — not through bad decisions, but through good decisions that were never retired.

### P38 — Capability is added at the edge, not by mutating the core
Onboarding a new kind of work should not require changing the spine. **If adding a work type forces a change to the core, the core is wrong** — and that is a signal to fix the core, not to special-case around it.

### P39 — The architecture must be able to shrink
We design so that things **can be deleted**. A component that cannot be removed without a rewrite is not a component we own — **it is a component that owns us.**
> A healthy architecture gets *smaller* at least as often as it gets larger.

---

## 11. CHANGE PROCESS

**Every architectural change must answer all seven questions, in writing, before it is built.** The answers live in the design document and are reviewed as part of it.

| # | Question | Why it is asked |
|---|---|---|
| 1 | **Why does this exist?** | Forces a purpose that is not "it seemed like the next thing to do." |
| 2 | **Which principle supports it?** | Cite by number. A change no principle supports is a change that needs a principle — or needs to not happen. |
| 3 | **What scar or operational observation motivated it?** | Real pain, real defect, real field observation. **Not** a hypothetical. Not a feature we imagined an owner might enjoy. |
| 4 | **What problem does it solve?** | Stated as the problem, not as the solution. If the problem can only be described in terms of the proposed feature, there is no problem. |
| 5 | **What complexity does it introduce?** | Every change has a cost. A change that claims to have none has not been examined. |
| 6 | **What existing capability could it replace?** | (P37.) If the honest answer is "nothing," say so explicitly and accept that surface area grew. |
| 7 | **What future maintenance cost does it create?** | **This is the question that is always skipped, and it is always the real cost.** Who keeps this correct in a year? What breaks when the vendor changes? What must be re-tested forever? |

**Rules of the process:**
- **A change that cannot answer all seven is not ready.** Not rejected — *not ready*. It goes back.
- **Question 3 is a hard gate.** We do not build for imagined pain. If nothing hurt, nothing is being fixed.
- **Question 7 is a hard gate.** An unpriced maintenance cost is a debt taken out in someone else's name.
- **A change that violates a refusal (§5) is rejected outright**, and no amount of value elsewhere in the proposal redeems it.
- **A change that conflicts with a principle** must either be abandoned, or the principle must be **amended in writing, with its reason** (§7). There is no third option, and there are no silent exceptions.

---

## 12. CANONICAL DOCUMENT HIERARCHY

### 12.1 The normative chain

```
        ┌──────────────────────────────┐
        │   ENGINEERING PRINCIPLES     │   ← this document (the constitution)
        └──────────────┬───────────────┘
                       ↓
        ┌──────────────────────────────┐
        │       PRODUCT VISION         │   ← what we are building, and for whom
        └──────────────┬───────────────┘
                       ↓
        ┌──────────────────────────────┐
        │        ARCHITECTURE          │   ← the shape of the system
        └──────────────┬───────────────┘
                       ↓
        ┌──────────────────────────────┐
        │       SPECIFICATIONS         │   ← precise behavior of each part
        └──────────────┬───────────────┘
                       ↓
        ┌──────────────────────────────┐
        │       IMPLEMENTATION         │   ← the plan to build it
        └──────────────┬───────────────┘
                       ↓
        ┌──────────────────────────────┐
        │            CODE              │   ← the artifact
        └──────────────────────────────┘
```

### 12.2 The rule that makes the hierarchy real

> **A lower layer may never contradict a higher layer.**

- If **code** contradicts a **specification**, the code is a bug.
- If a **specification** contradicts the **architecture**, the specification is invalid.
- If the **architecture** contradicts the **product vision**, the architecture is wrong.
- If the **product vision** contradicts these **principles**, then either the vision changes, **or the principle is amended in writing** — never bypassed.

**A conflict is never resolved downward by exception.** It is resolved by **changing the higher document deliberately, with a recorded reason**, or by **abandoning the lower one.** An undocumented exception is not a decision; it is a leak — and it is how a constitution quietly becomes decoration (§7).

**Every document must cite the layer above it.** A specification that cannot point to the architectural decision it implements has no authority to exist.

### 12.3 The evidence base (not part of the normative chain)

Two documents sit **beside** the hierarchy, not inside it. They are **factual, not normative** — they establish *what is true*, and every normative layer must be consistent with them:

| Document | What it is | What it is not |
|---|---|---|
| **`docs/architecture/current-state-reconciliation.md`** | What we have built, and what it assumes. | A statement of what we *should* build. |
| **`docs/product/freight-discovery.md`** | What the domain actually is, with evidence labels. | A statement of what our customer does. |

> **Evidence does not command; it constrains.** A design that contradicts a `CONFIRMED INDUSTRY PATTERN` is not forbidden — but it must **say so explicitly and justify itself.** A design that contradicts a `REPO_CONFIRMED` fact is simply **wrong about reality** and must be corrected.
>
> **A design built on something labeled `NEEDS VALIDATION` is a design built on sand.** It may proceed only if it *names the assumption*, states what breaks if the assumption is false, and marks itself provisional until the assumption is validated.

### 12.4 Where we stand

| Layer | Status |
|---|---|
| Engineering Principles | **FROZEN** (this document) |
| Evidence base — Reconciliation | **FROZEN** |
| Evidence base — Freight Discovery | **FROZEN** |
| Product Vision | *not yet written* |
| Architecture | *not yet written* |
| Specifications | *not yet written* |
| Implementation | *blocked — see reconciliation §0.3 (repository hygiene)* |
| Code | *frozen for the reset* |
