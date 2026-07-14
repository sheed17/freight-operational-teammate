# The Neyma Semantic Model — Canonical Language

**Status:** ✅ **CANONICAL — Wave 3.** Binding on every subsequent document, specification, and line of code.
**Layer:** This sits **beside** the architecture, not inside it. It defines the *language* the architecture is written in.
**Baseline:** `f0e801b4dfd611345ca6c2842e946d58a7512ae5`
**Date:** 2026-07-13

> ### **This document introduces NO new architectural primitives.**
> Every term below is expressible in the frozen architecture (ADR-001…009, Operating Model, Engineering Principles). **Where a definition appeared to need a new primitive, I stopped and said so** — see **§7.3**.

---

## 0. WHY THIS DOCUMENT EXISTS

**Two engineers implementing the same subsystem must derive identical meanings from these words.** Today they would not, and this is not hypothetical:

| The code says | The architecture says | They are the same thing |
|---|---|---|
| `lane` *(291 uses)* | **action class** | ✅ |
| `run`, `workflow_runs` *(423 uses)* | **Pipeline Instance** | ✅ |
| `CommandIntent` *(51 uses)* | **ProposedIntent** | ✅ — and **`Command` is an entity ADR-008 deleted** |
| `commit_identity` | **commit key** | ✅ — and **its composition is wrong** (ADR-009 §2.2) |

**Every one of those is a defect waiting to happen**, because an engineer reading `lane` will not know that ADR-004 binds a *gate decision* to it, and an engineer reading `run` will not know that ADR-009 makes it a *reservation*.

> **Semantic drift is not a documentation problem. It is how a guess ends up stored next to a fact, and read by code that cannot tell the difference.** *(That is F-04, and it is exactly how the pre-baseline linker silently overwrote the owner's correction.)*

---

# PART 1 — CANONICAL VOCABULARY

---

## A. STATE & TRUTH

### `Authoritative System`
**Definition.** An external system that **owns** a domain of truth. The TMS owns load and invoice status. The bank owns payment status. FMCSA owns carrier authority.
**Purpose.** To be the thing we act *against* and revalidate *from*.
**Why it exists.** Because Neyma does not own the freight. **Someone else's database is the world.**
**It is NOT.** Not a cache. Not a peer. Not something Neyma may overrule. **Not always right** — but always *authoritative*, which is a different claim.
**Owner.** The external party.
**Source of truth.** Itself, by definition.
**Relationships.** Emits **Observations**. Receives **External Effects**. Is revalidated against at the **Checkpoint** (ADR-001 **C4**).
**Example.** TruckingOffice is the authoritative system for *"is load 4471 delivered?"*
**Misconception.** *"Our projection is up to date, so we can act on it."* ⇒ **No. The projection is for KNOWING. The authoritative system is for ACTING.** (ADR-001 C4.)

### `Projected State`
**Definition.** State **derived from observations of an authoritative system**. (ADR-002 §1.1.)
**Why it exists.** So Neyma can *know* things without scraping on every read.
**It is NOT.** **Not authority.** Not optimistically updatable. Not a place intent may live.
**Owner.** The authoritative system.
**Lifecycle.** Observed → reconciled → materialized → refreshed by **verified readback**. **Rebuildable from retained evidence** (C2).
**Misconception.** *"We wrote it, so we can update our copy."* ⇒ **No — projected state is refreshed by verified readback, never by intent** (ADR-002 §1.1). *A system that updates its own projection on send has just invented a fact.*

### `Native State`
**Definition.** State that exists **because Neyma created it**: work items, claims, approvals, exceptions, conflicts, policy, audit. (ADR-002 §1.2.)
**Why it exists.** No external system holds it, and none could. **Nobody else knows who owes us an answer.**
**It is NOT.** Not derivable from any external system. **Not a licence to be unaccountable** — it still carries provenance, evidence, actor, and correction history.
**Owner.** **Neyma is authoritative.**
**Misconception.** *"An inference is just derived data, so it's projected."* ⇒ ### **NO. An inference is NATIVE state** (ADR-002 §1.3). *"This email belongs to load 4471"* is **a correctable claim**, not an observed fact. **This confusion is F-04 and it is the most expensive one in this document.**

### `Projection` / `Canonical Projection`
**Definition.** The **materialized, strongly-typed view** of projected state that business logic reads. *(One concept; "canonical projection" emphasizes that there is exactly one per field.)*
**Why it exists.** So business logic reads a `Load`, not a bag of attributed cells (ADR-002 §2.2).
**It is NOT.** ### **Not the source of truth. Not authority. Not permission to act.**
**Source of truth.** The **Observations** behind it — which is why the projection must be **rebuildable** and every field **traversable** back to its evidence (ADR-002 §2.1 concern 5).
**Misconception.** *"The projection says delivered, so we can bill."* ⇒ **The projection tells you it's WORTH billing. The Checkpoint's live re-read tells you it's SAFE to bill.**

### `Business State` vs `Operational State`
**`Business State`** — what is true *about the freight*: this load is delivered, this invoice is unpaid. **Mostly projected.**
**`Operational State`** — what is true *about the work*: this work item is blocked, this pipeline is awaiting approval, this exception is unresolved. **Always native.**
**Why the split.** They have **different owners and different failure modes.** A load being delivered is the TMS's business. A work item being unowned is **ours**, and it is **I1**.
**Misconception.** Treating "the invoice is unpaid" (business, projected) and "we haven't chased it" (operational, native) as one field. **They diverge, and the divergence is where money is lost.**

---

## B. EVIDENCE & BELIEF

### `Observation`
**Definition.** **An immutable record that a source said something, at a time.**
**Purpose.** To be the atom of truth. Everything projected is derived from observations.
**It is NOT.** Not a claim. Not a fact about the world — **a fact about what a source SAID.** *(The TMS can be wrong; the observation that it said so is still true.)*
**Owner.** System (a human owns it once `UNBOUND`).
**Lifecycle.** ADR-008 §3.5: `RECEIVED → PARSED → BOUND` · `UNBOUND` · `CONFIRMED` · `SUPERSEDED` · `UNPARSEABLE`.
**Mutability.** ### **NEVER.** Superseded, never edited.
**Identity.** Natural key `(tenant, source_system, external_id, content_digest)` — **ingestion is an idempotent upsert** (ADR-008 §2.7).
**Example.** *"The TruckingOffice loads page, read at 09:14, showed load 4471 as Delivered."*
**Misconception.** *"We re-received the same email, so it's new information."* ⇒ **No. It is a CONFIRMATION** — it updates `as_of` and **must not re-trigger work** (ADR-008 §2.7).

### `Evidence`
**Definition.** **A retained artifact, and the span within it, that supports a claim.** The POD PDF, page 1, the region containing "4471".
**Why it exists.** So a human can **check** a claim. **Evidence is what you show the angry customer** (**I3**).
**It is NOT.** ### **Not a claim.** Evidence does not assert anything — **it is what an assertion points at.**
**Misconception.** *"The document says £2,850, so £2,850 is a fact."* ⇒ The document **is evidence**. *"The rate is £2,850"* is **a claim supported by it.** The document could be the wrong document.

### `Claim`
**Definition.** **A proposition Neyma holds**, carrying a `provenance_class`, evidence, and optionally a confidence.
**Why it exists.** Because most of what Neyma "knows" it **worked out**, and worked-out things must be **correctable, attributable, and challengeable**.
**It is NOT.** ### **NOT A FACT.** Not an observation. **Not authority.**
**State class.** ### **Native** (ADR-002 §1.2).
**Owner.** A human, once `AMBIGUOUS` or `CONFLICTING`.
**Misconception.** *"High confidence means it's basically a fact."* ⇒ ### **No.** **Confidence may PRIORITIZE. It may never AUTHORIZE** (ADR-007 §4.2). **There is no threshold — not 0.99, not 1.0 — at which a claim becomes a fact.**

### `Inference`
**Definition.** **A claim produced by reasoning rather than by reading.** The model concluding *"this feels like load 4471"* with **no artifact saying so**.
**`provenance_class`.** `MODEL_INFERRED`.
**It is NOT.** ### **Not an observation. Not evidence. Not extraction.**
**Governing rule.** ### **`MODEL_INFERRED` may NEVER gate a consequential action — at any confidence.** It routes to `AMBIGUOUS` and **gets a human** (ADR-002 §2.3, ADR-008 §3.6).
**Misconception.** *"It's derived from the data, so it's data."* ⇒ **An inference is a guess with a good vocabulary.**

### `Provenance` / `Provenance Class`
**`Provenance`** — the complete lineage of a field: which observation or claim produced it, from which source, at what time, with what reconciliation status.
**`Provenance Class`** — ### **HOW a field came to be believed.** Six values (ADR-002 §2.3):
`SYSTEM_IMPORTED` · `OWNER_ASSERTED` · `LINKER_INFERRED` · `MODEL_EXTRACTED` · `MODEL_INFERRED` · `RECONCILED`
**Why it exists.** ADR-002 §1.3 ruled that an inference must never masquerade as truth — **but gave no field in which to express the difference, so no guard was expressible.** `provenance_class` is that field.
**Rules.** **R-P1** runtime-assigned, never model-chosen, **never settable from inbound content**. **R-P2** no laundering — may be weakened, **never strengthened**, except by an authenticated human act. **R-P3** `OWNER_ASSERTED` is **never machine-recomputed**.
**Misconception.** *"`MODEL_EXTRACTED` and `MODEL_INFERRED` are both just model output."* ⇒ ### **One is checkable and one is not.** *"The rate con says £2,850, here is the line"* can be handed to an angry customer. *"It's probably £2,850"* cannot.

### `Identity` vs `Identity Binding`
**`Identity`** — **what a thing IS**, persistently, across every observation of it. Load 4471 is load 4471 whether it arrives by email, portal, or phone.
**`Identity Binding`** — **a CLAIM of the form *"artifact X belongs to entity Y."*** The most common and most dangerous claim in freight.
**Why it exists.** ### **Nearly every operational failure in freight begins as an identity failure.** *Whose POD is this? Is this the carrier we booked, or one with a similar name?*
**Lifecycle.** ADR-008 §3.6.
**Rule.** ### **`OWNER_ASSERTED` bindings are NEVER machine-recomputed. A machine that disagrees raises a Conflict.** *(This is Stream B lesson L-A, made structural.)*
**Misconception.** *"We can re-link everything each cycle as the linker improves."* ⇒ **You may re-link `LINKER_INFERRED` bindings freely. You may never re-link the owner's.** *A projection rebuild rebuilds projections. It does not rebuild the owner's mind.*

### `Conflict`
**Definition.** **Two or more mutually exclusive claims or observations on the same field.**
**Purpose.** To make disagreement **visible and blocking**, instead of silently resolved.
**It is NOT.** ### **Not `unknown`.** *We do not lack information — we have too much, and it disagrees.* **(I8.)**
**The invariant.** ### **While a Conflict is OPEN, the field is `conflicting` and it BLOCKS every consequential action on that entity** (ADR-002 **C6**).
**Closure.** **Only** a registered deterministic **rule id** or a human **`decision_ref`**. **`AutoResolve` is an ILLEGAL TRANSITION.**
**Misconception.** *"Resolve conflicts by recency / confidence / source priority."* ⇒ **A conflict resolved by arrival order is a conflict resolved by network jitter.** Source priority is fine **as a registered rule with an id** — never as an ambient default.

### `Resolution` · `Supersession` · `Correction`
**`Resolution`** — **closing a Conflict**, by rule or by human.
**`Supersession`** — a **newer** claim/observation **replaces** an older one. ### **The old one was TRUE when made.** Nothing downstream is invalidated.
**`Correction`** — an existing `CONFIRMED` claim is declared ### **WRONG**. It **propagates** to everything derived from it and **may raise a Compensation**.
> ### **Conflating supersession and correction loses money.**
> *"The TMS now says £3,100"* is **supersession** — the £2,850 observation was true at 09:14. *"That POD was never load 4471's"* is **correction** — ### **and we may have already billed on it.**
**Misconception.** *"A correction just updates the value."* ⇒ ### **A correction that does not propagate is a lie with a timestamp** (ADR-007 §6).

---

## C. WORK & EXECUTION

### `Work Item`
**Definition.** ### **The unit of business responsibility and closure.** *"We intend to bill this load."*
**Purpose.** To hold **what the business owes someone**, with **an accountable human owner at all times** (**I1**).
**It is NOT.** Not an attempt. Not a task queue entry. **Not closable by silence.**
**Lifecycle.** ADR-008 §3.1. **Work Item : Pipeline Instance = 1:N.**
**Terminal.** `CLOSED` (**requires an explicit closure event with a `decision_ref`**), `CANCELLED`.
**Expiry.** ### **NEVER. Work does not disappear because it got old.** It ages and escalates.
**Misconception.** *"Nothing happened on it for 30 days, so it's done."* ⇒ ### **Closure is an emitted event, never an inference** (**I11**). *An exception closed without a decision is not closed — it is forgotten.*

### `Pipeline Instance`
**Definition.** ### **One durable attempt to produce one effect.** *(Preferred term. Deprecated synonyms: **run**, **workflow run**, **operation run**.)*
**Purpose.** ### **The Pipeline Instance IS the command** (ADR-008 §2.12) — durable, idempotent, inspectable, replayable.
**It is NOT.** Not a function call. **Not the Work Item** (that is the intent; this is the attempt). ### **Not a `Command` — that entity was DELETED.**
**Lifecycle.** ADR-008 §3.2: `PROPOSED → POLICY_CHECKED → VALIDATED → AWAITING_APPROVAL → CHECKPOINT → GRANTED → CLAIMED → EXECUTED → VERIFIED → RECORDED → PROJECTED → CLOSED`, plus `REJECTED`, `VOIDED`, `FAILED`, **`NEEDS_VERIFICATION`**.
**Doubles as.** ### **The Reservation** (ADR-009 §3.1) — a unique index on `(tenant, commit_key)` while non-terminal.
**Misconception.** *"Retry the pipeline."* ⇒ ### **You never retry a Pipeline Instance in place. A retry is a NEW instance, same commit key, new grant, full checkpoint.**

### `External Effect`
**Definition.** **The record of touching the world.** The thing that cannot be undone by rolling back a transaction.
**Why it exists.** Because ### **an effect is the only thing in this system that is irreversible**, and everything else exists to control it.
**Lifecycle.** ADR-008 §3.3: `GRANTED → CLAIMED → ATTEMPTED → VERIFIED` · `FAILED` · `EXPIRED_UNCLAIMED` · **`UNKNOWN_OUTCOME`**.
**Rule.** ### **`FAILED` requires POSITIVE PROOF that nothing happened.** Absence of a success signal is **not** proof of failure.
**Misconception.** *"The adapter returned 200, so it worked."* ⇒ **A 200 means the REQUEST succeeded. The money is in the record, not in the response.** *That is a proxy, not a signal.*

### `Compensation`
**Definition.** **Undoing an effect that should not have happened.**
**Rule.** ### **A Compensation IS an effect.** It passes through the **full pipeline** — checkpoint, grant, approval, readback. ### **There is no fast path for undo.**
**Forbidden.** ### **You may NEVER compensate an `UNKNOWN_OUTCOME`** (ADR-006 §3.12). **You cannot undo what you cannot prove you did** — and a compensating write can **create** the very state it meant to remove.
**Terminal.** `COMPLETED` only. **`COMPENSATION_FAILED` and `NOT_POSSIBLE` are non-terminal and human-owned.**
**Misconception.** *"Just roll it back."* ⇒ **An 'undo' that bypasses the gates is an ungated write with a good excuse.**

### `Exception`
**Definition.** **Something that needs a human.**
**Owner.** ### **A named human, always, from creation** (**I1**).
**Terminal.** `RESOLVED` — ### **and ONLY with a `decision_ref`.** Closure without one is an **ILLEGAL TRANSITION**.
**Expiry.** ### **NEVER.** It ages, then escalates. **An exception cannot be outlived.**
**Misconception.** *"It's been quiet, close it."* ⇒ ### **An exception closed without a decision is not closed — it is forgotten.**

### `Expectation`
**Definition.** **A commitment that something should be observed by a deadline.** *"A POD should arrive by Thursday."*
**The point of it.** ### **`OVERDUE` vs `INDETERMINATE`.** *"The POD never came"* and *"we were not watching"* are ### **different facts** (**I8**, F-14).
**Rule.** ### **`OVERDUE` may only be asserted when the observability channel was demonstrably HEALTHY.** Otherwise: **we were blind, and we say so.**
**Misconception.** *"Deadline passed, so it's late."* ⇒ **Only if you were looking.** A system that cannot tell blindness from absence will report a clean window as clean when it saw nothing at all.

---

## D. AUTHORITY & SAFETY

### `Approval`
**Definition.** ### **An authenticated, authorized human agreeing to an action TOGETHER WITH the exact facts that made it correct.**
**It is NOT.** ### **Not an instruction. Not a mandate. Not reusable. Not extendable. Not refreshable.** Not creatable by a model, a counterparty, a document, a confidence score, a policy default, a retry handler, an agent, or an admin tool.
**Lifecycle.** ADR-008 §3.4. Consumed **exactly once**, on commit.
**Survives.** A **provably-failed** attempt.
**Does NOT survive.** ### **Material-facts drift. Ever.**
**Misconception.** *"They approved billing load 4471."* ⇒ ### **No. They approved billing load 4471 FOR £2,850, on THAT evidence, under THAT policy.** Change any of it and **there is no approval — there is a new question.**

### `Material Facts` / `Material Facts Fingerprint`
**`Material Facts`** — ### **exactly what was rendered to the approver**, plus the identity of the effect. *If it was on the card, it is material. If it was material, it must have been on the card.*
**`Material Facts Fingerprint`** — `SHA-256` over the **canonical `fp_v1` serialization** of those facts.
**Includes.** Tenant, action class, target, commit key, **amount (integer minor units)**, counterparty, entity ref, bound documents + digests, **the evidence condition of every field**, ### **the `provenance_class` of every field**, policy version, entity versions.
**Excludes.** Cosmetics, thread ids, and ### **confidence scores** *(a confidence score is not a fact)*.
**Why the payload is retained, not just the hash.** ### **A hash proves THAT something drifted. It can never say WHAT. You cannot diff a hash** — and the owner needs the diff.
**Misconception.** *"Same amount, so no drift."* ⇒ ### **Not if its provenance changed.** The same number, believed for a different reason, is a different fact.

### `Checkpoint` / `Checkpoint Witness`
**`Checkpoint`** — ### **ONE atomic validation of seven things, immediately before an effect** (ADR-004 §2.4): approval validity · fingerprint · projected freshness (live, never cached) · native-state validity · entity versions · policy · brake.
**It is NOT.** ### **NOT seven independent checks separated by asynchronous work.** *That is the same thing spelled differently, and it is F-01.*
**`Checkpoint Witness`** — **proof the checkpoint passed.** In-process it is a type (`CheckpointPassed`) with **no public constructor**; across processes it is a **ledger row**.
**Why the witness exists.** ### **So that code which has not passed the checkpoint CANNOT EXPRESS a call to mint a grant.** *Capability by construction — the type system refuses to compile the bypass.*
**Misconception.** *"We validated at proposal time."* ⇒ **The window that matters is the one AFTER the human taps.**

### `Effect Grant`
**Definition.** ### **Permission for ONE attempt to touch the world, right now.** A durable row in the **Effect Grant Ledger**, plus a signed opaque handle pointing at it.
**It is NOT.** ### **Not the authority itself** — *the authority is the ledger row.* **Not reusable. Not refreshable. Not sufficient on its own.**
**The two-key rule.** ### **A grant is NECESSARY but NOT SUFFICIENT.** The adapter also requires a **fresh Checkpoint Witness**. *A grant answers "may this attempt exist?" — a question about the past. It says nothing about whether the world still looks the way it did.*
**Single-use.** ### **An atomic CAS `GRANTED → CLAIMED`. A database guarantee, not a token property.**
**Forgery.** ### **Irrelevant.** A forged handle names no ledger row, so the claim fails.
**Misconception.** *"Sign the token so it can't be faked."* ⇒ **A signature proves ORIGIN, never SINGLE-USE. A replayed signed token executes twice.**

### `Commit Key`
**Definition.** ### **The identity of the EFFECT.** *"Raise an invoice on load 4471 in TMS-A."*
**It is NOT.** ### **NOT the content of the decision.** ### **The amount is NOT in it.**
**Why this matters, concretely.** ### **The current code puts `approved_amount` in the commit key** (`operation_router.py:335`). Two proposals to bill load 4471 — one reading £2,850, one £3,100 — get **different commit keys**, **both commit**, and ### **the customer is invoiced twice.** *Commit-once fails in precisely the case it exists for, because the amount is the field most likely to differ between two racing reads.*
**Stable across.** All attempts. **A retry re-uses the commit key. That is what makes it safe.**
**Misconception.** *"Different amount, different effect."* ⇒ ### **No. Different amount = DRIFT = the approval is VOID.** *It does not become a different effect; it becomes a new question.*

### `Reservation`
**Definition.** ### **The exclusive right to be the pipeline working on this commit key.**
**Mechanism.** ### **NOT a new entity.** It is a **partial unique index on the Pipeline Instance** — *a command in flight IS a claim on its target* (ADR-009 §3.2).
**Expiry.** ### **None of its own.** Released **exactly** when its pipeline terminates. *A reservation with an independent TTL is a second clock, and two clocks disagree.*
**Renewal / lease / heartbeat.** ### **Do not exist.** *A lease is a promise to keep being alive, and a crashed process makes that promise too.*
**`NEEDS_VERIFICATION`.** ### **NEVER releases its reservation.** **The stuck reservation is not a bug — it is the last line between an unknown outcome and a double payment.**
**Misconception.** *"Reap stale reservations to unblock work."* ⇒ ### **That is the change that would double-pay a carrier.**

### `Entity Version`
**Definition.** A monotonic counter per entity, used for **optimistic concurrency**.
**Rule.** ### **No entity lock is EVER held across human time.** Versions are read and CAS'd **inside** the checkpoint (short). The long wait is protected by the **Reservation**, not by a lock.
**Misconception.** *"Lock the load while the owner decides."* ⇒ **Humans think for four hours. A lock held that long is an outage.**

### `Human Gate` vs `Human Brake`
**`Human Gate`** — ### **a per-action decision.** *"Do you approve THIS invoice?"* Produces an **Approval**. **Prospective.**
**`Human Brake`** — ### **a global stop.** *"Stop all TMS writes, now."* **Not a decision about any one action** — a **withdrawal of the capability to act at all**. **Retrospective and immediate.**
**Mechanism.** ### **The brake is enforced by REFUSING TO MINT a grant** (ADR-004 §2.4 step 7). **That is why it is unbypassable and why it never needs to kill a worker mid-flight.**
**Misconception.** *"The brake cancels in-flight work."* ⇒ ### **It cannot cancel a CLAIMED grant** — the world may already have changed. Those go to **verification**. **The brake stops the NEXT effect, not the last one.**

### `Policy` · `Rule` · `Constraint` · `Autonomy`
**`Policy`** — ### **a typed, versioned, scoped, deterministic predicate** evaluated in **checkpoint step 6**, returning a **never-null gate decision**. **Enforceable. Fails closed.**
**`Rule`** — a **registered, versioned, deterministic** decision procedure with an **id** (identity matching, conflict resolution). **Auditable and re-runnable.**
**`Constraint`** — an invariant the system **cannot violate** (a DB constraint, an illegal transition, a type). **Not evaluated — enforced.**
**`Autonomy`** — **how far Neyma may act without asking**, per lane and action class. **A policy value, not a property of the code.**
> ### **A prompt-string memory is NOT a policy.** *(Stream B lesson **L-C**.)* If an owner says *"never bill without a POD"* and the system replies *"Noted the procedure"*, then **either a real enforceable rule was created, or the system lied.** ### **A control the owner believes in must be enforced in code, or it must not claim to be a control.**
**Misconception.** *"We told the model the rule, so the rule is in force."* ⇒ ### **You gave an LLM a suggestion and the owner a false sense of safety.** *(P2: guards are never model-evaluated.)*

---

## E. VERIFICATION

### `Verification`
**Definition.** ### **Establishing what actually happened in the authoritative system**, by reading it back.
**It is NOT.** Not the adapter's return code. Not the absence of an exception. **Not "the page loaded."**
**Rule.** ### **`VERIFIED_SUCCESS` requires the readback to MATCH THE APPROVED MATERIAL FACTS** — not merely that *a* record exists. *Finding an invoice for £3,100 when £2,850 was approved is not success. It is a conflict.*
**Misconception.** *"We found the record, so it worked."* ⇒ **"A record is there" answers a question nobody asked. The question is: is it THE ONE THE HUMAN APPROVED?**

### `Verification Outcome`
**Definition.** ### **A VALUE (not a state machine)** with eight members, each with a **proof standard** (ADR-006 §3.2):
`VERIFIED_SUCCESS` · `VERIFIED_FAILURE` · `UNKNOWN_OUTCOME` · `VERIFICATION_DEFERRED` · `VERIFICATION_IMPOSSIBLE` · `AWAITING_OBSERVATION` · `OBSERVATION_UNAVAILABLE` · `OBSERVATION_CONFLICTING`
**The load-bearing distinction.** ### **`VERIFIED_FAILURE` vs `OBSERVATION_UNAVAILABLE`.** **Both look identical at the call site — "I didn't find it."** ### **One means retry. The other means STOP.**
**The rule that separates them.** ### **PROOF OF ABSENCE REQUIRES A HEALTHY CHANNEL.** *"The record is not there"* is only meaningful if we can show **we would have seen it had it been there.** ### **"The page loaded" is not a health signal — a logged-out page also loads.**
**Misconception.** *"Not found ⇒ failed ⇒ retry."* ⇒ ### **That is the double-billing machine.**

### `Unknown Outcome`
**Definition.** ### **We do not know whether the effect happened.**
**Rules.** **Non-terminal. Human-owned. Entity frozen. Commit key held. Never retried. Never compensated.** ### **It MUST NOT time out into success OR into failure.**
**Carries.** A mandatory ### **`unknown_reason`** — *blind* vs *conflicting* vs *exhausted* — because **the consequences are identical but the question we ask the human is not** (ADR-006 §3.3.1).
**Misconception.** *"Time it out after an hour, it's probably fine."* ⇒ ### **Any timeout here is a decision to guess about money.** **This is the single change that would undo the entire architecture.**

---

## F. SYSTEM

### `Integration Adapter`
**Definition.** ### **The ONLY thing that can produce an external effect.**
**Rule.** Its sole public entry point requires ### **an Effect Grant AND a Checkpoint Witness.** Constructors are **module-private**; the registry is reachable **only** from `pipeline/`; a **CI import-graph gate fails the build** if anything outside `pipeline/` imports `adapters/`.
**Credentials.** Resolvable **only inside an adapter**, **only on a claimed grant**. ### **Never reachable by agents, tooling, or even the pipeline itself.**
**Misconception.** *"I'll just call the adapter from a script."* ⇒ ### **The build fails. And if it didn't, the adapter would refuse — it has no grant.** *That friction is the feature.*

### `Audit Event` vs `Business Event`
**`Business Event`** — ### **something that happened in the freight world.** *`InvoiceIssued`, `LoadDelivered`.* **Domain-meaningful. Drives projections and downstream work.**
**`Audit Event`** — ### **something that happened in NEYMA.** *`ApprovalGranted`, `GrantClaimed`, `IllegalTransitionAttempted`, `CheckpointFailed`.* **Explains WHY the system did what it did.**
**Both are FACTS.** Neither is a command. **Events are not commands** (Engineering Principles).
**Why the split.** ### **A business event tells the owner what happened to their freight. An audit event tells the owner why Neyma believed it should act.** *Conflating them makes the system's authority impossible to audit* — you get a log that says what changed but never who decided.
**Misconception.** *"Emit an event to make something happen."* ⇒ ### **An event says what HAPPENED. If you want something to happen, create a Work Item.**

### `Operational Loop`
**Definition.** One of the **11 named end-to-end business loops** (Operating Model L1–L11): quote→book, book→cover, cover→dispatch, POD→bill, bill→cash, etc.
**Purpose.** The unit in which **value** is measured. **A loop closes at CASH, not at "sent"** (L8, P24).
**Misconception.** *"The invoice went out, the loop is done."* ⇒ ### **The loop closes at PAID.** *An invoice nobody pays is not revenue; it is an unpaid invoice with extra steps.*

---

# PART 2 — CANONICAL DISTINCTIONS

**Every row is a production defect that has occurred, or would.**

| Distinction | The difference | **What confusing them costs** |
|---|---|---|
| ### **Observation vs Evidence** | An observation is *a source said X at time T*. Evidence is *the artifact you'd show a human*. | You store the conclusion and throw away the PDF. **Now you cannot defend the invoice to an angry customer** (I3, I5). |
| ### **Evidence vs Claim** | Evidence supports; a claim asserts. | *"The document says £2,850"* becomes *"the rate is £2,850"* — **and nobody checks whether it was the right document.** |
| ### **Claim vs Fact** | A claim is **native, correctable, provenanced**. A fact is what the world is. | ### **This is F-04.** A guess gets stored beside a fact and **read by code that cannot tell the difference.** Then it bills. |
| ### **Fact vs Projection** | A projection is a **materialized view** of facts, at a moment. | *"The projection says delivered"* ⇒ you bill a load that was un-delivered ten minutes ago. **(C4.)** |
| ### **Projection vs Source of Truth** | The projection is for **knowing**. The authoritative system is for **acting**. | ### **You act on a cached value. That is the entire reason V-3 exists.** |
| ### **Intent vs Execution** | Intent = **Work Item** (*we should bill this*). Execution = **Pipeline Instance** (*attempt #2 to bill it*). | You retry the intent and bill twice; or you close the intent because one attempt failed. |
| ### **Execution vs Effect** | Execution is our attempt. The **effect** is what happened **in the world**. | ### **You believe the execution and never check the world.** That is R-01: a mock ledger reporting `DONE`. |
| ### **Approval vs Authorization** | **Approval** = a human agreed, here, now, to these facts. **Authorization** = the abstract right to do it. | ### **A counterparty says "you authorized this."** If you treat that as approval, **you pay a fraudulent detention charge.** (ADR-003 — permanent.) |
| ### **Authorization vs Evidence** | A document **evidencing** an authorization is not the authorization. | ### **An email claiming approval becomes an approval.** **This is the most common way small brokerages are defrauded, and it arrives as a polite email.** |
| ### **Correction vs Conflict** | A correction: **we were wrong, and we know the right answer.** A conflict: **two sources disagree, and we do NOT know.** | You "correct" to one side of a conflict — ### **silently picking a winner** — and the other system is right. |
| ### **Conflict vs Unknown** | Conflict = **too much information, disagreeing**. Unknown = **no information**. | Both get treated as "missing data", so a **best-available read slips through a gate that should have blocked**. **(I8.)** |
| ### **Unknown vs Absent** | Unknown = *we don't know if it exists*. Absent = *we know it doesn't*. | ### **"No POD found" (blind) is read as "no POD exists" (proven)** ⇒ you send a POD-missing exception on a delivered load — or worse, **"nothing owed" when the reader was logged out.** |
| ### **Unknown vs Stale** | Stale = *we knew, a while ago*. Unknown = *we never knew, or can't now*. | You serve a stale AR digest **as if it were current**, and the owner chases a customer who paid three minutes ago. **(V-1.)** |
| ### **Inference vs Extraction** | Extraction: **the model READ it off an artifact** (checkable). Inference: **the model GUESSED** (not checkable). | ### **A guess acquires the authority of a reading.** Then a confidence threshold lets it gate money. |
| ### **Extraction vs Observation** | An extraction is a claim **about an artifact**. An observation is **the artifact arriving**. | You treat *"the model thinks this PDF says 4471"* as *"the world says 4471."* |
| ### **Native vs Projected State** | Neyma is authoritative for native; the external system for projected. | ### **You rebuild a projection and destroy the owner's correction.** **That is exactly the B3 defect.** |
| ### **Identity vs Identifier** | Identity = **what a thing IS**. Identifier = **a string that points at it**, in one system, today. | You key on the TMS's invoice number; **the TMS renumbers on edit**; your idempotency evaporates. |
| ### **Reservation vs Ownership** | Reservation = **exclusive right to WORK on it** (a pipeline). Ownership = **the accountable human** (I1). | You "release the reservation" on an unknown outcome to unblock things — ### **and double-pay.** |
| ### **Retry vs Replay** | **Retry** = a NEW attempt at the world (**new pipeline, new grant, same commit key**). **Replay** = re-deriving state from events (### **produces NO effects, structurally**). | ### **Replay causes side effects.** You reprocess history and re-send every invoice you ever sent. |
| ### **Policy vs Principle** | A **principle** is a human commitment (amendable in writing). A **policy** is **machine-enforced, versioned, and fails closed**. | ### **"Never bill without a POD" is written in a prompt.** The owner thinks it is a rule. **It is a suggestion.** (L-C.) |
| ### **Human Gate vs Human Brake** | Gate = *approve this one action*. Brake = *stop being able to act*. | You build a brake that "cancels in-flight work" — ### **but it cannot cancel a CLAIMED grant**, and now you think you stopped something you didn't. |
| ### **Business vs Technical (Audit) Event** | Business: *what happened to the freight*. Audit: *why Neyma believed it should act*. | Your audit log records **what changed** but never **who decided** — ### **and an exception is closed by nobody.** |

---

# PART 3 — CANONICAL FREIGHT SEMANTICS

**Where a word has several industry meanings, all are recorded; ONE is canonical in Neyma.**

| Word | ### **CANONICAL NEYMA MEANING** | Other industry meanings *(recognized, NOT used)* |
|---|---|---|
| **Load** | ### **The commercial unit we are paid for.** One customer obligation, one bill. **The unit the owner says "bill load 4471" about.** | *Truckload* (equipment); *a shipment on a trailer*; *the TMS's row id*. ⚠️ **A load may contain several movements.** |
| **Shipment** | ### **The customer's goods moving from A to B.** The **commercial** view. | Often used interchangeably with Load. ⚠️ **In Neyma, Shipment ≈ Load's cargo content — it is NOT the billing unit.** |
| **Movement** | ### **One carrier's physical execution of part of a load.** The **operational** view. **This is what gets settled with a carrier.** | *Leg*; *trip*; *dispatch*. |
| **Order** | ### **The customer's request, BEFORE it is a load.** Pre-booking. | *Purchase order* (the shipper's, not ours); *sales order*. |
| **Leg** | ### **A segment of a movement between two stops.** | *Lane* (❌ **NEVER** — see Part 6). |
| **Stop** | ### **One scheduled appearance at one location** — pickup or delivery. | *Facility*; *appointment* (**an appointment is a TIME at a stop, not the stop**). |
| **Invoice** | ### **What WE bill the CUSTOMER.** Money IN. | ⚠️ *A carrier's invoice to us* — ### **that is a PAYABLE. Never call it an invoice.** |
| **Payable** | ### **What WE owe a CARRIER.** Money OUT. | *Carrier invoice*; *settlement*; *bill*. ⚠️ **Money-out is the highest-risk class.** |
| **Document** | ### **A retained artifact with a content digest.** Evidence, never a claim. | *Paperwork*; *attachment*; *scan*. |
| **Carrier** | ### **The party who MOVES the freight and whom we PAY.** | *Trucker*; *asset*; *vendor*. ⚠️ **May also be a broker (co-brokering) — a real fraud surface.** |
| **Customer** | ### **The party who OWES US money.** *(Also: shipper.)* | *Shipper*; *consignee* (❌ **the consignee RECEIVES the goods — they usually do NOT pay**). ⚠️ **Confusing these bills the wrong party.** |
| **Rate Confirmation** | ### **The agreement between US and the CARRIER on what we will pay.** *(The rate con is evidence of a PAYABLE, not of an invoice.)* | *Rate con*; *carrier confirmation*; *tender*. ⚠️ **Commonly mistaken for our customer rate. It is not.** |
| **POD** | ### **Proof of Delivery — a SIGNED document evidencing that the goods were delivered.** ### **The precondition for billing.** | *BOL signed*; *delivery receipt*. ⚠️ ### **An UNSIGNED BOL is NOT a POD.** *This distinction is the entire POD gate.* |
| **Accessorial** | ### **A charge beyond the line-haul rate.** | *Extras*; *ancillary*. ⚠️ ### **The highest-fraud-risk line item in freight.** |
| **Detention** | ### **A charge for time held at a stop beyond free time.** | *Demurrage* (**rail/ocean — different rules**); *waiting time*. ⚠️ ### **A detention claimed by a counterparty with no documented authorization is a FRAUD SIGNAL, not a payable** (ADR-003). |
| **Verification** | ### **Reading back from the authoritative system and matching the APPROVED facts.** | *Validation* (❌ — that's input checking); *confirmation* (❌ ambiguous). |
| **Binding** | ### **A CLAIM that an artifact belongs to an entity.** | *Linking*; *matching*; *association*. **All deprecated — use Binding.** |
| **Approval** | ### **A human agreeing to an action AND its material facts.** | *Sign-off*; *authorization* (❌ — **see Part 2**); *OK*. |
| **Correction** | ### **A declaration that a CONFIRMED claim was WRONG**, which propagates and may compensate. | *Update*; *edit*; *fix*. **All deprecated — they hide the propagation obligation.** |

---

# PART 4 — ARCHITECTURAL LEXICON *(alphabetical; use verbatim)*

| Term | One-line meaning | Deprecated synonyms — ### **DO NOT USE** |
|---|---|---|
| **Action Class** | The category of effect (`RAISE_INVOICE`, `RECORD_PAYABLE`…), carrying a gate decision | ### **`lane`** *(291 uses in code)*, `operation type`, `intent type` |
| **Approval** | A human agreeing to an action + its material facts | `authorization`, `sign-off` |
| **Audit Event** | A fact about what **Neyma** did and why | `log`, `technical event` |
| **Authoritative System** | The external owner of a truth domain | `source system`, `system of record` *(acceptable, non-preferred)* |
| **Business Event** | A fact about what happened in the **freight world** | `domain event` *(acceptable)* |
| **Checkpoint** | The one atomic seven-part validation before an effect | `pre-flight`, `validation`, `guard chain` |
| **Checkpoint Witness** | Proof the checkpoint passed (`CheckpointPassed`) | `token`, `ticket` |
| **Claim** | A proposition Neyma holds, with provenance and evidence | `fact`, `inference result`, `match` |
| **Commit Key** | The identity of the **effect** | ### **`commit_identity`** *(and its composition is wrong)*, `idempotency key` *(acceptable)* |
| **Compensation** | A gated effect that undoes a prior effect | `rollback`, `undo`, `reversal` |
| **Conflict** | Mutually exclusive claims/observations on one field | `mismatch`, `discrepancy` |
| **Correction** | A declaration that a confirmed claim was **wrong** | `update`, `edit`, `fix` |
| **Effect Grant** | Permission for **one attempt** to touch the world | `capability token`, `ECT` *(acceptable)*, `permission` |
| **Entity Version** | Monotonic counter for optimistic concurrency | `revision`, `etag` |
| **Evidence** | A retained artifact + span supporting a claim | `proof` *(too strong)*, `source` |
| **Exception** | Something that needs a human | `error`, `alert`, `issue` |
| **Expectation** | A commitment that something should be observed by a deadline | `SLA`, `timer`, `reminder` |
| **External Effect** | The record of touching the world | `write`, `action`, `transaction` |
| **Human Brake** | Global withdrawal of the capability to act | `kill switch` *(acceptable)*, `pause` |
| **Human Gate** | A per-action approval requirement | `approval step`, `HITL` |
| **Identity Binding** | A claim that an artifact belongs to an entity | `link`, `match`, `association` |
| **Inference** | A claim produced by reasoning, not reading (`MODEL_INFERRED`) | `guess` *(honest but informal)*, `prediction` |
| **Integration Adapter** | The only thing that can produce an external effect | `connector`, `client`, `driver` |
| **Material Facts** | Exactly what was rendered to the approver | `context`, `payload` |
| **Native State** | State Neyma is authoritative for | `internal state`, `local state` |
| **Observation** | An immutable record that a source said something at a time | `reading`, `scrape`, `data point` |
| **Pipeline Instance** | One durable attempt to produce one effect | ### **`run`, `workflow run`** *(423 uses in code)*, `job`, `task`, ### **`Command`** *(deleted entity)* |
| **Policy** | A typed, versioned, deterministic, enforceable predicate | ### **`procedure`, `SOP`, `memory`, `prompt rule`** |
| **Projected State** | State derived from observations of an authoritative system | `cache` ### **(dangerously wrong)**, `mirror` |
| **Projection** | The materialized typed view business logic reads | `model`, `view` *(acceptable)*, `read model` *(acceptable)* |
| **Provenance Class** | **How** a field came to be believed (6 values) | `source type`, `origin` |
| **ProposedIntent** | The **inert data** an agent emits — its only output | ### **`CommandIntent`** *(51 uses in code)*, `command`, `instruction` |
| **Reservation** | Exclusive right to be the pipeline working on a commit key | `lock`, `lease`, `claim` *(overloaded — avoid)* |
| **Resolution** | Closing a conflict, by rule id or human decision_ref | `fix`, `merge` |
| **Supersession** | A newer claim replaces an older one (the old one was **true**) | `overwrite`, `update` |
| **Verification** | Reading back and matching the **approved** facts | `confirmation`, `validation`, `check` |
| **Work Item** | The unit of business responsibility and closure | `ticket`, `task`, `case` |

---

# PART 5 — SEMANTIC INVARIANTS

**Each is enforced by a mechanism, not by discipline.**

| # | Invariant | Governing authority | Enforced by |
|---|---|---|---|
| **S1** | ### **A Claim is never a Fact.** | ADR-002 §1.3; P11 | `provenance_class` on every lineage record |
| **S2** | ### **An Inference never becomes an Observation.** | ADR-002 §2.3 **R-P2** | No-laundering test (adversarial, ADR-008 §5) |
| **S3** | ### **`MODEL_INFERRED` may never gate a consequential action — at ANY confidence.** | ADR-002 §2.3; ADR-007 §4.2 | Confidence is **structurally absent** from the checkpoint's inputs — **a guard cannot read it** |
| **S4** | ### **`MODEL_INFERRED` never becomes `OWNER_ASSERTED` without an authenticated human act.** | ADR-002 **R-P2** | Provenance may be **weakened, never strengthened** |
| **S5** | ### **Machine recomputation never overwrites `OWNER_ASSERTED` state.** | ADR-002 **R-P3**; L-A | **ILLEGAL TRANSITION** (ADR-008 §3.6) — raises, persists nothing, security event |
| **S6** | ### **A Projection is never Authority.** | ADR-001 **C4** | The checkpoint re-reads **live**; a consequential reader **structurally cannot take a cache** (V-3 guard, in the baseline) |
| **S7** | ### **Replay never produces Effects.** | ADR-004 §4.6 | Replay cannot construct a `CheckpointPassed` ⇒ **cannot mint a grant** |
| **S8** | ### **A Correction never rewrites History.** | ADR-008 §2.8, §2.14 | Append-only; a **closure event is immutable**; reopening creates a new phase |
| **S9** | ### **A Correction always propagates.** | ADR-007 §6 (F-17) | Lineage walk ⇒ re-derive ⇒ **raise Compensation** for every effect that rested on it |
| **S10** | ### **An Approval never survives Material-Facts Drift.** | ADR-005 §3.12 (F-01) | Fingerprint recomputed **live inside the checkpoint** ⇒ `VOID_ON_DRIFT` + a field-level diff |
| **S11** | ### **An Approval is consumed exactly once.** | ADR-005 §3.15 | Atomic CAS `GRANTED → CONSUMED`, in the grant-claim transaction |
| **S12** | ### **An Effect Grant is necessary but NOT sufficient.** | ADR-004 §2.2 | The adapter also requires a **fresh Checkpoint Witness** |
| **S13** | ### **An effect happens at most once per commit key.** | ADR-009 §3.1 | `UNIQUE (tenant, commit_key) WHERE state='CLAIMED'` — **a database constraint** |
| **S14** | ### **`FAILED` requires positive proof that nothing happened.** | ADR-006 §3.1 | **Proof of absence requires a healthy channel** (positive control) |
| **S15** | ### **An Unknown Outcome never silently becomes success or failure.** | ADR-006 §3.1; ADR-004 §3.9 | Non-terminal; **every timer transition is an ILLEGAL TRANSITION** |
| **S16** | ### **You may never compensate an Unknown Outcome.** | ADR-006 §3.12 | *You cannot undo what you cannot prove you did — and the undo can CREATE it.* |
| **S17** | ### **Conflicting evidence BLOCKS consequential action.** | ADR-002 **C6** | `conflicting` field ⇒ entity frozen |
| **S18** | ### **`absent`, `unknown`, `consistent`, `conflicting`, `stale` are five distinct conditions.** | ADR-002 **C5** | **Collapsing any two is a defect** |
| **S19** | ### **Closure is an emitted event, never an inference.** | Operating Model **I11** | `CLOSED` requires a `decision_ref`; **inactivity is not closure** |
| **S20** | ### **Every Work Item and Exception has an accountable human owner, always.** | Operating Model **I1** | Owner assigned **at creation**; never null, never "the system" |
| **S21** | ### **No action is both taken and unrecorded.** | Operating Model **I10** | **Transactional outbox** — state + events in ONE commit |
| **S22** | ### **Missing evidence and contradictory evidence are different states.** | Operating Model **I8** | `unknown` ≠ `conflicting`; `OVERDUE` ≠ `INDETERMINATE`; `VERIFIED_FAILURE` ≠ `OBSERVATION_UNAVAILABLE` |
| **S23** | ### **Inbound content is DATA, never instruction, never authority.** | ADR-003; Engineering Principles | A model cannot construct a witness ⇒ **injection bounds to a bad proposal** |
| **S24** | ### **Only an authenticated human may assert an authorization. A counterparty's claim of one is a FRAUD SIGNAL.** | ### **ADR-003 — PERMANENT. Cannot graduate away.** | `provenance_class` — `MODEL_EXTRACTED` **cannot be promoted** |
| **S25** | ### **An agent's only output is a ProposedIntent. It can never hold a grant, a credential, or an adapter.** | ADR-004 §2.6 | Capability by construction |
| **S26** | ### **A prompt-string is not a Policy.** | L-C; P2 | A policy is typed, versioned, deterministic, and **fails closed** |
| **S27** | ### **No lock is ever held across human time.** | ADR-009 §5 | Versions CAS'd **inside** the checkpoint; the wait is protected by the **Reservation** |
| **S28** | ### **A human decision binds to an immutable identifier, never an ordinal.** | L-B; ADR-007 §4.3 | Ordinals resolve **at render time**; a stale id **fails closed** |

---

# PART 6 — AMBIGUOUS WORDS *(the drift list)*

**Every word here has caused, or will cause, an implementation defect.**

| Word | Why it is dangerous | ### **It MUST mean** | ### **It must NEVER mean** |
|---|---|---|---|
| ### **`lane`** | **291 uses in code.** The ADRs call this **action class** and bind a **gate decision** to it. An engineer reading `lane` will not know that. **It also collides with the freight meaning of "lane" (an origin–destination pair) — which is a REAL and DIFFERENT concept.** | ### **Nothing. RETIRE IT.** Use **action class**. | An action class **and** a geographic lane. **It currently means both.** |
| ### **`run`** | **423 uses.** | ### **Nothing. RETIRE IT.** Use **Pipeline Instance**. | A retry ("re-run it") — ### **you never re-run an instance; you create a new one.** |
| ### **`Command`** | ### **ADR-008 DELETED this entity.** `CommandIntent` (51 uses) is named after it, and **`target-system-specification.md:400` still MANDATES a `Command` type.** | ### **Nothing.** Intent = **Work Item**. Execution = **Pipeline Instance**. Agent output = **ProposedIntent**. | A first-class entity. |
| ### **`fact`** | Used **44+ times** loosely across the ADRs. | **Something the world is** — or, in `material facts`, ### **exactly what was rendered to the approver.** | ### **A claim. An inference. A model output.** |
| ### **`verify` / `confirm` / `validate`** | Three words, three meanings, used interchangeably. | **Verify** = read back from the authoritative system and **match the approved facts**. **Confirm** = re-observe an unchanged fact (`ObservationConfirmed`). **Validate** = check an input's shape. | ### **"Verify" must NEVER mean "the call returned 200."** |
| ### **`done` / `complete`** | The most dangerous word in the product. | ### **`VERIFIED_SUCCESS` and nothing else.** | ### **"We sent it." "The adapter returned." "The state machine advanced."** *(That is R-01 — a mock ledger reporting `DONE`.)* |
| ### **`sent`** | | **The transmission was accepted by the relay, and here is the byte-for-byte copy.** | ### **"Delivered." "Received." "Read."** We **cannot** know those, and we must never claim them. |
| ### **`approve` / `authorize`** | | **Approve** = a human agreed to an action **and its facts**. **Authorize** = the abstract right. | ### **A counterparty "authorizing" anything.** That is a fraud signal (S24). |
| ### **`retry` / `replay`** | | **Retry** = new pipeline, same commit key, **new grant**, full checkpoint. **Replay** = re-derive state from events, ### **producing zero effects**. | ### **Replay must NEVER touch the world.** |
| ### **`cache`** | | A **failure-fallback for informational/decision-support reads**, with **disclosed staleness**. | ### **Anything a consequential read can touch.** *(V-3: the money resolver is structurally forbidden a cache.)* |
| ### **`confidence`** | | A number that **sorts a human's queue**. | ### **A gate. A threshold. An authorization. Ever.** *(S3 — this is the single most likely way the architecture gets defeated.)* |
| ### **`owner`** | Overloaded: the **business owner** (the customer, a person) vs the **accountable owner** of a work item. | **The accountable human** for a Work Item / Exception (**I1**). | The freight customer. **Say `customer` for that.** |
| ### **`party`** | Used in the current commit key. Vague. | Nothing — ### **be specific: `customer` (owes us) or `carrier` (we owe them).** | An ambiguous counterparty. **Money direction must never be ambiguous.** |
| ### **`status`** | Every system has one and they all mean different things. | **Always qualified**: `load_status`, `invoice_status`, `pipeline_state`. | ### **A bare `status` field.** |
| ### **`sync`** | | Nothing. **RETIRE.** | ### **It implies two-way authority.** Neyma **observes** and **effects**. It does not "sync." |
| ### **`update`** | | Nothing — say **Supersession** (the old was true) or **Correction** (the old was **wrong**, and it propagates). | A single verb covering both. ### **The distinction is the difference between a no-op and a compensation.** |
| ### **`match` / `link`** | | Nothing. Say **Identity Binding**, and name its **provenance class**. | A binding with no provenance. ### **That is precisely how B3 destroyed the owner's correction.** |
| ### **`procedure` / `SOP` / `memory`** | | **Memory** = something recalled into a prompt. **Policy** = typed, versioned, **enforceable**. | ### **A memory described to the owner as a rule.** *(L-C: "Noted the procedure" when nothing was installed.)* |

---

# PART 7 — SEMANTIC REVIEW

## 7.1 Ambiguous terms removed

**Nineteen** (Part 6). The five that will cost real money if left in place:

1. ### **`done`** — must mean `VERIFIED_SUCCESS` **and nothing else.** *(R-01 was a system saying `DONE` about a JSON file.)*
2. ### **`lane`** — means **two different things today** (action class **and** origin–destination pair) in a codebase that gates money on one of them.
3. ### **`confidence`** — must never be readable by a guard. *One `if confidence > 0.98` defeats ADR-002, ADR-007, and the money fence simultaneously.*
4. ### **`retry` vs `replay`** — conflating them re-sends every invoice in history.
5. ### **`update`** — hides the difference between a harmless supersession and a correction that **owes a compensation**.

## 7.2 Deprecated terminology *(with real usage counts — these are code changes, not doc changes)*

| Deprecated | ### **Canonical** | Uses in code | Impact |
|---|---|---|---|
| `lane` | **action class** | **291** | Large but mechanical. **Must not be done by find-and-replace** — freight "lane" is real and must survive. |
| `run` / `workflow_runs` | **Pipeline Instance** | **423** | Large. Ancestor of the real entity — **generalize, don't discard.** |
| `CommandIntent` | **ProposedIntent** | **51** | ### **Named after a DELETED entity.** Rename with the type. |
| `commit_identity` | **commit key** | **16** | ### **Rename AND recompose — its current composition is a live double-billing hole** (ADR-009 §2.2). |
| `operation_action_claims` | `effect_grants` | 1 table | The **ancestor of the Effect Grant Ledger.** Discipline right, key wrong. |

> **None of these are cosmetic. Each is a place where an engineer reading the code would derive a different meaning from an engineer reading the architecture.**

## 7.3 A new primitive was NOT invented — but I was tempted once, and I want it on the record

**Defining `Business State` vs `Operational State` looked like it needed a new primitive** — something to hold *"the business truth about the freight"* separately from *"the truth about our work."*

### **It does not.** It is **exactly** ADR-002's existing split: **Business State ≈ projected state; Operational State ≈ native state.** The two names are a *lens*, not an entity. **Nothing new is introduced, and no implementer should create a `BusinessState` table.**

**Similarly, `Identity` (as distinct from `Identity Binding`) is NOT a stored entity.** It is the *concept* a binding points at. **Do not build an `identities` table.**

## 7.4 Conflicts discovered

| # | Conflict | Severity | Disposition |
|---|---|---|---|
| **C-1** | ### **`target-system-specification.md:400` MANDATES a `Command` type. ADR-008 §2.12 DELETED the Command entity.** | ### **DIRECT CONTRADICTION** | The spec is **below** the ADRs and is **awaiting revision**. **This is exactly what the Wave 3→4 revision must fix.** ✅ Already scheduled — **but it must not be forgotten, because the code (`CommandIntent`, 51 uses) currently follows the SPEC, not the ADR.** |
| **C-2** | **`lane`** means *action class* in code and *origin–destination pair* in freight. | **HIGH** | Retire the code usage. **Reserve `lane` for its freight meaning.** |
| **C-3** | **`claim`** is overloaded: an **Identity Binding Claim** (ADR-007) vs **claiming a grant** (ADR-004 CAS). | **MEDIUM** | Both are entrenched and both are correct in their domain. ### **Disambiguate by always qualifying: "binding claim" vs "grant claim."** **Do not rename either.** |
| **C-4** | **`party`** in the current commit key does not distinguish **money-in** from **money-out**. | **HIGH** | ### **Money direction must never be ambiguous.** Use `customer` / `carrier`. |
| **C-5** | **`Projection`** appears twice in the Wave 3 concept list (as itself and as *Canonical Projection*). | LOW | **One concept.** Defined once. |

## 7.5 Recommendations before specification engineering begins

1. ### **Fix C-1 in the specification revision, and rename `CommandIntent` in the same change.** Today the **code follows a spec line that the ADRs have overruled.** That is a lower layer contradicting a higher one, and it is exactly the failure mode the document hierarchy exists to prevent.
2. ### **Treat §7.2 as a migration checklist, not a style guide.** `commit_identity` in particular is **a rename AND a recomposition** — and the recomposition is **the fix for a live double-billing defect.**
3. ### **Every subsequent document uses Part 4 verbatim.** If a specification needs a word that is not in the lexicon, **that is a signal that a concept is missing from the architecture** — stop and check, do not coin.
4. ### **The five semantic invariants most likely to be violated by a well-meaning engineer are S3, S5, S7, S15, and S16.** Each is defeated by a single plausible line of code (`if confidence > 0.98`; a re-linker loop; a replay that calls an adapter; a timeout on `NEEDS_VERIFICATION`; an auto-rollback). ### **Each therefore needs a merge-gating test that fails loudly, and each already has one specified.**
5. **The remaining Wave 3 blockers are unchanged: ADR-010 (Policy) and ADR-011 (Brake).** ### **Note that `Policy`, `Autonomy`, `Rule`, and `Constraint` are defined in Part 1 §D of this document — but they are defined as *language*, not as *mechanism*.** **The mechanism still needs its ADR, and checkpoint steps 6 and 7 remain unwritten.**

---

## THE ONE-PARAGRAPH VERSION

> **Neyma observes an authoritative system it does not own, forms claims it must be able to defend, projects a view it may never act on, and — only after one atomic checkpoint against the live world — spends a single-use grant to touch reality once, and then reads it back to find out what actually happened.**
>
> **Every word in that sentence is defined above. If a document uses one of them to mean something else, the document is wrong.**
