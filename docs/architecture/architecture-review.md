# Architecture Review — Target System Specification

**Reviewer role:** Principal Staff Engineer, adversarial. Mandate: reject unsafe, incomplete, or internally inconsistent architectures **before** implementation.
**Under review:** `target-system-specification.md` (32 §§) · `engineering-principles.md` · `operating-model.md` · `current-state-reconciliation.md` · `freight-discovery.md` · ADR-001 · ADR-002.
**Date:** 2026-07-09
**Posture:** *Assume this architecture will fail in production. Find out how.*

---

## 0. THE GOVERNING CRITICISM

The specification is **structurally sound and mechanically incomplete.**

It repeatedly states a **requirement** where an architecture must state a **mechanism**. "MUST be idempotent," "MUST fail closed," "MUST be verifiable," "the capability to gate exists permanently" — these are **assertions of intent, not designs**. An engineer or a coding agent implementing from this document would be forced to invent the load-bearing mechanism themselves, and would invent it differently each time.

**The single worst instance:** §19 declares itself "the single effect boundary" and then **specifies no mechanism that prevents anything from bypassing it.** A boundary that is enforced by good intentions is not a boundary.

There is also **one ordering defect in §19.1 that is straightforwardly wrong** and would move money incorrectly in production (F-01).

Verdict at a glance: the foundations hold. **The mechanisms do not yet exist. Implementation must not begin.**

---

# PART A — FINDINGS

---

## CRITICAL

---

### F-01 — The mandatory stage order is wrong: freshness revalidation precedes the human gate
- **Severity:** **CRITICAL**
- **Section:** §19.1, §19.4, §21.1
- **Violates:** P5, P6, P12, ADR-001 C4, I3
- **Description:** §19.1 fixes the order as `… → freshness revalidation → human gate → commit-key reservation → execute …`. **A human gate is not instantaneous.** An approval may sit for minutes, hours, or overnight. Revalidating *before* the gate means the system validates data, then waits an unbounded interval, then executes against data it has **not** revalidated. The document's own rule — *"consequential actions MUST revalidate against the authoritative source **at execution time**"* — is **contradicted by its own stage order.**
- **Concrete production failure:** At 09:00 the pipeline revalidates: carrier invoice for load 4471 is $1,421, matching the rate con. An approval is posted. At 14:00 the owner taps Approve. Between 09:00 and 14:00 the carrier issued a corrected invoice for $2,180 and the TMS payable was updated. The pipeline executes the **approved** $1,421 — or worse, executes against the *current* record while the human believed they approved something else. **Either way, a human approved one thing and a different thing happened.**
- **Root weakness:** The architecture treats approval as a *stage* rather than as **an asynchronous boundary that invalidates everything computed before it.**
- **Correction:**
  1. **Revalidate immediately before execution, after the gate** — this is non-negotiable and the current order must be inverted.
  2. Bind every approval to a **material-facts fingerprint** (a hash of the exact field values the decision depended on, with their `as_of`).
  3. **If revalidation shows any material fact changed, the approval is VOID.** The action MUST NOT execute; it must re-escalate showing *what changed*.
  4. A pre-gate validation MAY remain, but only as a *cheap early rejection*, never as the authorizing check.
- **Implementation blocked:** **YES.**
- **Must change:** §19.1, §19.4, §21.1. New ADR (approval–data binding).

---

### F-02 — The "single effect boundary" is asserted, not enforced
- **Severity:** **CRITICAL**
- **Section:** §19 (whole), §18.2, §23.4
- **Violates:** P18, R14, R6, R7, P3
- **Description:** §19 states that every effect passes through one pipeline, and §23.4 states agents "have no privileged path." **No mechanism enforces either claim.** The Integration & Actuation layer (§18) exposes adapters. Anything that can construct or import an adapter — a migration script, an admin tool, a retry handler, a compensating workflow, a background reconciler, a well-meaning engineer, **or a coding agent implementing from this document** — can call the outside world directly. The architecture's entire safety model rests on a convention.
- **Concrete production failure:** A migration script (§30) writes directly through the TMS adapter to backfill invoices. No policy check, no commit key, no verification, no audit record. Six weeks later a customer disputes an invoice and there is **no provenance for it at all** (I2, I10 violated). Nobody knows it happened.
- **Root weakness:** **Capability is ambient.** Adapters are reachable by anyone who can name them.
- **Correction:** Make bypass *structurally impossible*, not merely forbidden:
  1. **Adapters MUST NOT be constructible outside the Action Pipeline.** They accept an **unforgeable execution token** minted only by the pipeline after all prior stages have passed, scoped to (tenant, action class, commit key, single use).
  2. The Agent Runtime, migration tooling, admin tooling, and compensating workflows are **ordinary clients** with no elevated path. **There is no admin backdoor.**
  3. A build-time/CI check MUST fail if any module outside the pipeline imports an adapter.
  4. Every adapter call emits an event; **an adapter invocation with no corresponding pipeline record is a Sev-0 alarm** (detective control behind the preventive one).
- **Implementation blocked:** **YES.** This is the keystone. Nothing else in the safety model is real without it.
- **Must change:** §18.2, §19, §23.4, §28 (add the bypass test). New ADR (execution capability tokens).

---

### F-03 — Universal readback-verifiability is assumed, and it is false
- **Severity:** **CRITICAL**
- **Section:** §19.6, §18.2, §26.1
- **Violates:** P5, R9, I10
- **Description:** §19.6 makes "verify by readback" a mandatory pipeline stage for **every** effect. **Many effects in this domain cannot be read back.** Sending an email. Sending an SMS. Submitting a portal form that renders no confirmation. Posting to an API that returns 202 with no resource id. The specification defines **no verification taxonomy** and **no behaviour for an effect that cannot be verified** — so an implementer will either (a) fake a verification, or (b) mark the effect DONE unverified. **Both are R9 violations, and (a) is worse.**
- **Concrete production failure:** Neyma sends a dunning email to a customer. The provider accepts it; the pipeline has nothing to read back. The implementer, obeying the MUST, "verifies" by re-reading the local sent-record it just wrote — **verifying its own claim against itself.** The email in fact bounced. The system reports the customer was chased. They were not.
- **Root weakness:** The architecture conflates **three distinct verification modes** and specifies only one.
- **Correction:** Define an explicit **verification taxonomy**, and make it a required property of every action class (§19.2):
  | Mode | Meaning | Example |
  |---|---|---|
  | **Readback-verifiable** | The effect creates observable state in an authoritative system. **Must** be read back. | TMS invoice, filed document, recorded payable |
  | **Receipt-verifiable** | No readable state; an external party issues a durable acknowledgement. **The receipt is the evidence**, and it is weaker. | Email provider message-id; SMS delivery receipt |
  | **Unverifiable** | Neither. | A fire-and-forget portal POST |
  - **Unverifiable effects MUST carry a stronger gate before them** (§4.5 of the Principles — irreversibility earns a stronger gate, not a compensation story) and MUST be **explicitly enumerated and accepted by product**, not discovered by an implementer at 2am.
  - The system MUST NEVER report an unverifiable or receipt-verified effect with the same confidence as a readback-verified one. **The owner sees the difference.**
- **Implementation blocked:** **YES.**
- **Must change:** §19.2, §19.6, §18.2, §21 (how weaker verification is surfaced to a human). New ADR.

---

### F-04 — Identity binding: a single weak candidate binds silently
- **Severity:** **CRITICAL**
- **Section:** §10.3
- **Violates:** P32, P4, P6, R6, I8
- **Description:** §10.3 step 3 reads: *"**Two** plausible candidates, **or none**, MUST escalate."* **A single, low-confidence, weakly-evidenced candidate is neither** — so it passes. This is precisely the *"path where probabilistic similarity can silently create a consequential binding"* the architecture claims to prevent. The definition of ambiguity is **wrong**: ambiguity is not "more than one candidate," it is **"insufficient evidence to confirm."**
- **Concrete production failure:** A carrier invoice PDF for "Load 4471" arrives. The tenant has no load 4471, but has load 4-471 and a customer reference 04471. The model proposes one candidate at 0.62 confidence. There is exactly one candidate → **it binds**. The invoice is reconciled against the wrong load's rate con, the delta looks fine, and **$2,400 is paid against the wrong movement.** The audit trail is perfect and completely wrong.
- **Root weakness:** **Confidence is being used to authorize** (violating P4), through the side door of a mis-specified ambiguity test.
- **Correction:**
  1. Restate: **a binding is confirmed ONLY by a deterministic rule that establishes identity** (an exact identifier match on a trusted identifier, or an exact match on a documented composite key). **Everything else escalates.** Candidate count is irrelevant.
  2. **Confidence MUST NOT appear anywhere in the confirmation predicate** (P4). It may rank an escalation queue. Nothing more.
  3. Bindings that gate a **consequential** action require **strictly stronger** evidence than bindings that only inform a read.
  4. Define, explicitly, the trusted identifier set and their collision characteristics — including that **`load #` is not globally unique across a tenant's customers**.
- **Implementation blocked:** **YES.**
- **Must change:** §10.3, §9.4, §5.2 (I8/P4 traceability is currently *false*). New ADR (identity confirmation rules).

---

### F-05 — An LLM-derived authorization claim can gate money with no human confirmation
- **Severity:** **CRITICAL**
- **Section:** §8.3, §9.2, §19.4, §22.4
- **Violates:** P2, P3, P11, R6, R7, Operating Model §7.6
- **Description:** The architecture's proudest domain insight — *"an Authorization MAY exist with no document"* (§8.3, P31) — creates its most dangerous path. An Accessorial Authorization is a **Claim**: a native, **inferred** assertion, potentially produced by a model reading a call transcript or an email thread. §19.4 requires revalidation of dependent fields **against the authoritative source** — but a native claim **has no authoritative external source to revalidate against** (see also F-22). Nothing in the specification prevents a **model's interpretation of a phone call from authorizing a payment.**
- **Concrete production failure:** A carrier emails: *"per our call, you agreed to the $300 detention."* The extraction model creates an Authorization claim at 0.81 confidence. The reconciler now sees the $300 detention line as **authorized**, the invoice reconciles clean, and it flows to a routine, graduated, auto-approved payable. **The call never happened.** The system has been socially engineered into paying, and it did so *through the safety spine, not around it.*
- **Root weakness:** **"Commitment precedes document" was implemented as "the model may assert a commitment."** That is not the same thing, and the difference is money.
- **Correction:**
  1. **An Authorization claim MUST NEVER be created by a model alone.** A model may *surface a candidate authorization* to a human. **Only a human may assert that an authorization exists** — and that assertion is itself a first-class, attributed, auditable native fact.
  2. Authorization claims MUST carry their **asserting actor**. A model-asserted authorization has **zero** authority to gate money — permanently, and not subject to graduation.
  3. **Inbound content claiming an authorization is a fraud vector** (§24.2), not evidence. It MUST be treated as an *unverified assertion by a counterparty*, and it MUST route to a human.
  4. This is a **permanent product truth**, not a policy: it belongs in Operating Model §7.5, not §7.6.
- **Implementation blocked:** **YES.**
- **Must change:** §8.3, §9.2, §19.4, §24.2. Amend Operating Model §7.5 (product decision required). New ADR.

---

### F-06 — Dual-write: no atomicity between effect, event persistence, and projection update
- **Severity:** **CRITICAL**
- **Section:** §19.7, §11.2, §17, §16
- **Violates:** I10, P7, P9, ADR-001 C2
- **Description:** §19.1 ends with `… execute → verify → record → update projection`. These are **three separate writes to three separate stores, with no transactional or outbox mechanism specified.** The specification never mentions an **outbox**, an **inbox**, or a **transactional boundary**. This is the textbook dual-write problem, and the architecture walks straight into it while asserting I10 (*no action both taken and unrecorded*).
- **Concrete production failure:** The pipeline executes an invoice write in the TMS, verifies it by readback, and the process is killed (OOM, deploy, node eviction) **before the event is persisted**. The invoice exists in the TMS. **Neyma has no record that it ever acted.** The next reconciliation cycle observes an invoice it did not create, cannot attribute it, and the owner asks *"who billed this?"* — **I2, I10, and I3 all fail simultaneously.** Worse: a retry could bill it again, because the commit key was never durably resolved.
- **Root weakness:** The pipeline is described as a **sequence**, when it must be described as a **saga with durable checkpoints**.
- **Correction:**
  1. **Every pipeline stage transition MUST be durably checkpointed before the next stage begins.** The pipeline is a persistent state machine (§12), not a function call.
  2. **Transactional outbox:** the state transition and the event that records it are written **in one atomic commit**; publication to the backbone is a separate, retried step.
  3. **Inbox / dedup table** on every consumer, keyed by event id, so at-least-once delivery cannot double-act (this is *how* §17.1's "MUST be idempotent" is actually achieved — currently it is only an instruction).
  4. **Crash recovery is a defined, tested procedure**: on restart, every pipeline instance in a non-terminal stage is resumed and its stage re-derived — never re-executed blindly.
- **Implementation blocked:** **YES.**
- **Must change:** §11, §16, §17, §19 (recast the pipeline as a durable state machine), §26. New ADR (outbox/inbox and pipeline durability).

---

### F-07 — Migration: old and new runtimes can both produce the same effect
- **Severity:** **CRITICAL**
- **Section:** §30.5, §19.5
- **Violates:** P8, P18, R14
- **Description:** The strangler sequence (§30.5) routes "one capability" through the new spine while the old system remains live. **The commit key (§19.5) exists only in the new system.** The legacy path — which today performs live TMS writes — has **its own, incompatible** idempotency mechanism. Nothing prevents both from acting on the same load.
- **Concrete production failure:** The legacy AR trigger proposes and (on approval) bills load 4471. In the same window, the new pipeline observes the load as delivered-and-billable and bills it. **The customer receives two invoices for the same load.** Both systems' audit trails are internally consistent and mutually invisible.
- **Root weakness:** The strangler is described as a routing change; **it is actually a distributed-mutual-exclusion problem**, and none is specified.
- **Correction:**
  1. A **shared effect ledger** spanning both runtimes for the duration of the migration — a single durable commit-key namespace that **both** systems must reserve against. This is the only safe form of coexistence.
  2. Or: **hard cutover per capability**, with the legacy path **physically deleted** (not disabled, not flagged off) in the same change. **Deletion is part of the step** (§30.5 step 5, P37).
  3. Prefer (2). Two systems that can both act are two systems that will both act.
- **Implementation blocked:** **YES — blocks migration specifically.**
- **Must change:** §30.5. New ADR (migration mutual exclusion).

---

## HIGH

---

### F-08 — Approval is bound to an action, not to the facts it approved
- **Severity:** HIGH · **Section:** §21.1 · **Violates:** P12, R4, I3
- **Description:** "Bound to the specific effect" is not "bound to the data the effect depends on." A human approves *"pay Iron Horse $1,421 on LD-5."* If the underlying payable changes before execution, the approval is silently applied to different facts.
- **Failure:** The owner approves a $1,421 payable. The TMS payable is edited to $1,721 by a colleague. Execution pays $1,721 under an approval for $1,421 — or pays $1,421 into a record that no longer means what the human read.
- **Correction:** Approval carries a **material-facts fingerprint**; any drift **voids** it (see F-01). The re-escalation MUST show the human **what changed**.
- **Blocked:** YES. · **Changes:** §21.1, §19.4.

### F-09 — "Single-use approval" contradicts "retry"
- **Severity:** HIGH · **Section:** §21.1 vs §19.5, §26.2 · **Violates:** internal consistency; R4
- **Description:** §21.1 mandates single-use approvals. §19.5/§26.2 mandate bounded retries of failed effects. If a *failed* (definitely-not-executed) effect is retried, is the approval consumed or not? The specification does not say. Both readings are defensible and they produce opposite systems.
- **Failure:** An implementer consumes the approval on first attempt; a transient network failure now forces a human to re-approve every flake — approval fatigue, then rubber-stamping (§2.8). The other implementer keeps the approval alive; it is later reused after data drift (F-08).
- **Correction:** Specify explicitly: **an approval authorizes one *committed effect*, not one *attempt*.** It survives an attempt that **provably did not execute**; it is **void** on unknown-outcome (which must escalate) and **void** on material-fact drift (F-08). State this as a rule with a truth table.
- **Blocked:** YES. · **Changes:** §19.5, §21.1, §26.2.

### F-10 — No entity-level concurrency control: two *different* effects can race on one entity
- **Severity:** HIGH · **Section:** §19, §12, §13 · **Violates:** P10, I9
- **Description:** The commit key prevents **the same logical effect** happening twice. It does **nothing** to prevent **two different effects** from conflicting on the same business entity. There is no optimistic concurrency, no entity version, no reservation.
- **Failure (scenarios 3 & 4):** Two carriers accept the same load within seconds; two pipelines each pass all gates and each issue a rate confirmation. **The load is double-covered and we owe two carriers a TONU.** Or: a human covers a load manually in the TMS while an automated negotiation is mid-flight; neither knows about the other.
- **Correction:** Introduce **entity-level optimistic concurrency**: every consequential action declares the entities it mutates and the **version it read**; execution is conditional on that version still holding at execution time. A conflict aborts and re-escalates. Additionally, **loop-level reservations** (this load is being covered by work item W) so a second attempt is refused at the front door, not discovered at the effect.
- **Blocked:** YES. · **Changes:** §12, §13, §19.

### F-11 — The readback target is never identified; verification can confirm the wrong record
- **Severity:** HIGH · **Section:** §19.6 · **Violates:** P5, R9
- **Description:** "Read back and confirm" presumes we can **unambiguously address the thing we just created**. Frequently we cannot: creating an invoice yields an invoice number **we did not choose and cannot predict**. The naive implementation reads "the most recent invoice" — which may belong to someone else.
- **Failure (scenario 6):** The write silently fails. The readback reads a **stale, cached page** showing the *previous* invoice for the same customer. Values match closely enough. The pipeline reports verified. **This is a re-run of a defect the current system already shipped** (`SCAR`: commit-detection false positive).
- **Correction:** Verification MUST (a) force a **fresh** read (cache-defeating), (b) confirm the **specific expected delta**, not merely that *a* plausible value exists, and (c) address the target by an **identifier captured from the write response itself**. If the target cannot be addressed, the effect is **not readback-verifiable** and falls under F-03.
- **Blocked:** YES. · **Changes:** §19.6, §18.2.

### F-12 — Tenant is absent from the event backbone's partitioning and consumer scoping
- **Severity:** HIGH · **Section:** §17.2, §7.1 · **Violates:** P16, R15
- **Description:** §7.1 asserts cross-tenant access is "structurally impossible." §17.2 then partitions the event stream **by entity or work item** — with **no mention of tenant** in the key, in consumer scoping, or in the dedup/inbox design (which does not exist, F-06).
- **Failure (scenario 19):** A worker leased for tenant A is assigned a partition containing tenant B's events. It processes them with tenant A's policy, tenant A's knowledge, and tenant A's credentials. **This is a data breach with a perfect audit trail.**
- **Correction:** **Tenant is the first component of every partition key.** Consumers are leased **per tenant**. Cross-tenant consumption must be rejected at the transport, not at the handler. The data-access layer enforces tenant scoping structurally (§16.5), and there is a **test that attempts a cross-tenant read and asserts it is impossible.**
- **Blocked:** YES. · **Changes:** §7.1, §16.5, §17.2, §28.

### F-13 — Observation identity and de-duplication are unspecified
- **Severity:** HIGH · **Section:** §9.1, §17.1 · **Violates:** P8, I8
- **Description:** §17.1 says consumers must be idempotent, but **an Observation has no defined identity**. What makes two inbound emails "the same email"? Message-Id? Content hash? Provider delivery id? A re-polled mailbox will re-deliver; a provider will retry a webhook.
- **Failure (scenario 1):** The same POD email is ingested twice. Two Observations → two extraction Claims → two candidate bindings → **an Expectation is discharged twice**, and a second work item is created to file a document that is already filed. Best case: noise. Worst case: a duplicate document attached to the load and a duplicate exception.
- **Correction:** Every Observation carries a **source-natural key** (system + external id + content digest). Ingestion is idempotent on it. **Re-observation of an unchanged fact is a *confirmation* (it updates `as_of`), not a new fact** — a distinction with real consequences for freshness (§6.5).
- **Blocked:** YES. · **Changes:** §9.1, §17.1.

### F-14 — An Expectation can go "overdue" while we were blind
- **Severity:** HIGH · **Section:** §14.2, §14.3 · **Violates:** I7, R10, P6
- **Description:** §14.3 correctly distinguishes `not yet` / `overdue` / `unknown`. But §14.2's lifecycle says an expectation becomes **overdue by time** — with **no requirement that we were actually able to observe during the window.** The architecture protects against reporting `unknown` as `absent` in one place and then reintroduces exactly that bug through the expectation clock.
- **Failure (scenario 13):** The mail integration is down for six hours. The POD *did* arrive. The expectation ticks past its deadline and is raised as an exception. Neyma chases the carrier for a document it already has, and tells the owner the load is not billable. **This is the "every invoice is paid in full" SCAR wearing a different hat.**
- **Correction:** An Expectation MUST NOT transition to `overdue` unless the system can demonstrate **continuous observability of the discharging channel across the window.** Where observability was interrupted, the expectation transitions to **`indeterminate`** — which is a *different* exception ("I could not watch for this"), routed differently and **never** presented as "the carrier failed to send it."
- **Blocked:** YES. · **Changes:** §14.2, §14.3, §25.5.

### F-15 — The human brake has no defined semantics for in-flight effects
- **Severity:** HIGH · **Section:** §20.5 · **Violates:** P14, P5, I10
- **Description:** "The brake MUST actually stop the system" is not a design. **What happens to an effect currently between `execute` and `verify`?** Aborting mid-flight *manufactures an unknown outcome* — the most dangerous state in the system (§19.8). Letting it run contradicts "stop."
- **Failure (scenario 22):** The owner hits the brake mid-payment-run. An implementer kills the workers. Three effects were in flight; **nobody knows whether they landed.** The brake — a safety feature — has created three unresolved unknown-outcomes.
- **Correction:** Specify precisely: **the brake is admission control, not termination.** It (a) **immediately** prevents any new effect entering `execute`, (b) **allows in-flight effects to complete `verify` + `record`** — *you cannot un-ring a bell, and abandoning an effect without verifying it is strictly worse than completing it* — and (c) reports exactly what was in flight when it engaged. A separate, explicit **"abort in-flight"** is a distinct, higher-severity operation with its own escalation, because it *creates* unknown-outcomes by design.
- **Blocked:** YES. · **Changes:** §20.5, §26.

### F-16 — Conflict is modeled between external systems only; conflict between *claims* is not modeled
- **Severity:** HIGH · **Section:** §6.3, §9.2, §10 · **Violates:** I8, P11, P32
- **Description:** §6.3 handles disagreement **between authoritative systems**. It says nothing about disagreement **between two native Claims** — two agents, or an agent and an earlier claim, or an agent and a human correction, asserting different bindings or different extracted values.
- **Failure (scenario 15):** The extraction agent binds a POD to Movement A; a later re-processing binds the same POD to Movement B. Both are Claims. **The projection takes whichever wrote last.** No conflict is recorded because the conflict model does not cover this case. **Last-writer-wins is exactly what ADR-001 §2.4 forbids** — reintroduced through a class of state the ADR did not consider.
- **Correction:** Extend the Conflict entity to cover **claim-vs-claim** and **claim-vs-observation**. Claims MUST NOT silently supersede each other: a new claim contradicting an existing one **raises a Conflict** and the field becomes `conflicting` — which blocks consequential actions (§6.4.4). Supersession requires a **deterministic rule or a human**.
- **Blocked:** YES. · **Changes:** §6.3, §9.2, §10.4.

### F-17 — Correction has no compensation path once an effect has already occurred
- **Severity:** HIGH · **Section:** §10.4 · **Violates:** P7, I3, §4.5 of the Principles
- **Description:** §10.4 requires that a correction "propagate to everything derived from the wrong binding." **`Propagate` is doing enormous unspecified work.** If a wrong binding already produced a *consequential effect in an external system*, propagation is not a data update — it is **compensation in the real world**, which the architecture explicitly says is not always possible.
- **Failure (scenario 16):** A POD was bound to the wrong movement; the load was billed. The binding is corrected. **What happens to the invoice that is already in the customer's TMS and their AP queue?** The specification is silent. An implementer will "propagate" by mutating the projection — leaving reality and the projection **permanently divergent**, which also breaks the rebuild test (§16.3).
- **Correction:** A correction that invalidates a **completed consequential effect** MUST: (a) raise a **Compensation work item** with an accountable owner, (b) **NOT** silently mutate the projection to a state that reality does not hold, (c) mark the affected fields `conflicting` until reality and the projection agree again, and (d) be **escalated with the dollar exposure stated**.
- **Blocked:** YES. · **Changes:** §10.4, §26.3, §13.

### F-18 — I6 is rhetorical: decisions do not pin the knowledge and evidence they used
- **Severity:** HIGH · **Section:** §25.4, §22.1, §22.2 · **Violates:** **I6**, P9
- **Description:** I6 requires decisions be *"reproducible from the evidence available **at the time**."* §25.4 claims replay discharges it. But **Knowledge (§22) is versioned and mutable, and retrieval is dynamic.** Replaying an old decision **today** retrieves **today's** knowledge. The reconstruction will not match. §22.2 requires recording *why* each piece was included — not **which version of what content**.
- **Failure (scenario 25):** Six months later a customer disputes a payment. We replay. The knowledge base now contains a rule that did not exist then, and lacks one that has since been revoked. **We cannot show what the system knew when it decided.** I6 fails on the exact use case it exists for.
- **Correction:** Every decision record MUST **pin**: the **content-addressed identity** of every knowledge item injected, every evidence item consumed, the model + prompt version, and the policy version. Replay resolves against the **pinned versions**, not current state. *This is the difference between an audit and an anecdote.*
- **Blocked:** YES. · **Changes:** §22.1, §22.2, §25.4, §16.

### F-19 — §12 specifies zero state machines
- **Severity:** HIGH · **Section:** §12 (whole) · **Violates:** P10, I4, I9
- **Description:** §12 lists the *requirements* of a lifecycle and the *entities that need one* — and then defines **not a single state, transition, guard, terminal state, reopening rule, cancellation rule, timeout, or compensation path.** This is the largest incompleteness in the document. **Two engineers implementing from §12 will produce two incompatible systems**, and neither will be wrong according to the text.
- **Failure:** Everything downstream of §12 (work model, expectations, pipeline durability, exceptions) is unimplementable without inventing the state machines. **Invention is where the safety properties silently die.**
- **Correction:** §12 must specify, per lifecycle: the state set, the transition table, the guard for every transition, terminal states, **reopening rules** (can a closed loop reopen? — a POD arriving after a load was written off), **cancellation** semantics, **timeout** behaviour, **failure** states, and **compensation** states. *This is architecture, not specification-layer detail* — because the invariants (I4, I9, I11) live in these tables.
- **Blocked:** YES. · **Changes:** §12 (substantial addition).

### F-20 — "The capability to gate is permanent" is unenforced rhetoric
- **Severity:** HIGH · **Section:** §20.6, §19.2 · **Violates:** Operating Model §7.5, P25
- **Description:** §19.2 says action classes carry their gate requirements **as data**. §20.6 says the *capability* to gate is permanent. **Nothing prevents someone from defining a new action class with `gate: none`, or setting a cap to infinity.** The permanent truth is enforced by nobody.
- **Failure:** Under commercial pressure, a "low-risk auto-settle" action class is added with no gate. It is a config change. It passes review because *"the architecture supports configurable gates."* **This is exactly the erosion the Operating Model §7.6 names — arriving through the mechanism designed to prevent it.**
- **Correction:** (a) **"No gate" MUST NOT be expressible as an absence.** Every action class carries an **explicit, positively-asserted gate decision**, including `AUTONOMOUS_WITHIN_CAPS(cap)` — there is no null. (b) A defined set of action classes (**money out**, **counterparty payment-detail change**, **outbound bad-news communication**) is **structurally ungatable-away**: the pipeline refuses to execute them without a human approval id, and this is enforced in code, not config. (c) Any change to a gate emits a **security event** (§24) and requires the seven-question ADR.
- **Blocked:** YES. · **Changes:** §19.2, §20.6, §29.4.

### F-21 — No event versioning or schema evolution strategy
- **Severity:** HIGH · **Section:** §11, §16.1, §17 · **Violates:** P9, I4
- **Description:** The event store is **immutable and permanent**, the system is intended to run for **years**, and the specification contains **no event schema versioning, no upcasting strategy, and no compatibility rules.** Replay (§25.4) and rebuild (§16.3) both depend on old events being interpretable by new code — forever.
- **Failure:** Eighteen months in, a field is renamed. Rebuild now fails on all historical events. **The rebuildability test — the one thing standing between "derived projection" and "undeclared source of truth" (ADR-001 C2) — is now permanently red, and gets disabled.**
- **Correction:** Every event carries a **version**. Compatibility rules are explicit (additive-only, or upcasters mandatory). **The rebuild test runs against the full historical corpus, not a recent window.**
- **Blocked:** YES. · **Changes:** §11, §16.1, §17, §28.5.

### F-22 — Freshness revalidation is undefined for native-state dependencies
- **Severity:** HIGH · **Section:** §19.4, §6.5 · **Violates:** ADR-001 C4, ADR-002 §1.2
- **Description:** §19.4 requires revalidation *"against the authoritative source."* For **native state** (bindings, authorizations, exceptions, approvals) **Neyma is the authoritative source** — so "revalidate against the authoritative source" is either a no-op or meaningless. The rule silently exempts exactly the state class that is *inferred* and therefore *least trustworthy*.
- **Failure:** A payable depends on (i) the TMS payable amount — projected, revalidated — and (ii) an Authorization claim — native, **not revalidated**. The claim was **retracted** by a human 20 minutes ago. The action proceeds on a retracted authorization. (Compounds F-05.)
- **Correction:** Revalidation for native state = **re-read the current claim state and assert it is still valid, unretracted, unsuperseded, and not `conflicting`.** Every dependency of a consequential action — projected **and** native — is enumerated and revalidated. **"Authoritative" is not a synonym for "stable."**
- **Blocked:** YES. · **Changes:** §19.4, §6.5.

---

## MEDIUM

---

### F-23 — Work-item ownership has a gap at creation and no reassignment rules
- **Severity:** MEDIUM · **Section:** §13.1 · **Violates:** I1
- **Description:** "Exactly one accountable human owner **at every moment**" — but a work item is created by the system, often before any human sees it. Who owns it in the interval? What happens when the owner is on holiday, leaves, or loses the role?
- **Correction:** Define a **default owner** (a tenant-level escalation role) assigned at creation, plus explicit **reassignment**, **absence**, and **role-revocation** rules. Ownership transfer is an event (already stated); the *triggers* for it are not.
- **Blocked:** No. · **Changes:** §7.2, §13.1.

### F-24 — Projection rebuild: no response to divergence, no time budget
- **Severity:** MEDIUM · **Section:** §16.3, §28.5 · **Violates:** ADR-001 C2
- **Description:** The rebuild test asserts equivalence. It does not say **what happens when it fails**, nor bound **how long a rebuild takes**. A rebuild that takes 9 hours cannot be run continuously, so it will be run rarely, so drift will be discovered late.
- **Failure (scenario 20):** Rebuild diverges. Is production halted? Is the projection replaced (destroying data that only exists there — which would prove it was *not* derived)? Nobody knows, so nobody acts.
- **Correction:** Divergence is a **Sev-0**. Define the response: freeze consequential actions on affected entities, escalate, and **diagnose whether the divergence is a rebuild bug or an undeclared write**. Bound rebuild time and make it incremental/partitionable.
- **Blocked:** No (but must be closed before the first loop runs unattended). · **Changes:** §16.3, §28.5.

### F-25 — Time, timezones, and DST are entirely unaddressed
- **Severity:** MEDIUM · **Section:** §14, §8.4, §16 · **Violates:** I9
- **Description:** The architecture makes **time a first-class trigger** (§14) in a domain saturated with time-sensitive semantics — appointment windows, detention clocks (billed by the minute), payment terms, HOS, COI expiry — across **multiple US timezones**, with DST transitions. The word "timezone" does not appear in the specification.
- **Failure:** A detention clock computed in the wrong zone under-bills by an hour. An appointment window is evaluated in UTC and a load is marked late that was on time. An expectation deadline lands in the DST gap and never fires.
- **Correction:** All instants stored in UTC with the **originating zone retained**; all *business* windows evaluated in the **facility's local zone**; DST-safe deadline arithmetic mandated; and this is a named test category (§28).
- **Blocked:** No. · **Changes:** §8.4, §14.2, §16, §28.

### F-26 — Knowledge conflict resolution is unspecified
- **Severity:** MEDIUM · **Section:** §22 · **Violates:** §2.4 of the Principles
- **Description:** §22 mentions knowledge has scope, confidence, and revocability — but **no resolution rule when two knowledge items conflict**, and no rule for a **standing rule vs. a newer direct instruction**.
- **Failure (scenario 17):** A standing rule says *"Customer X requires the lumper receipt attached or they short-pay."* The owner says today: *"Just bill X without it, they're waiving it this once."* Which wins? A specificity rule? Recency? The architecture does not say, so the agent picks — **which is a model resolving a policy conflict** (P2 violation).
- **Correction:** Specify precedence: **a direct, in-context human instruction supersedes a standing rule for that instance only**, is recorded as such, and **MUST NOT silently update the standing rule.** Conflicts between standing rules escalate. **A model never resolves a knowledge conflict.**
- **Blocked:** No. · **Changes:** §22.

### F-27 — No backpressure strategy; dead-letter replay semantics undefined
- **Severity:** MEDIUM · **Section:** §17.4, §27 · **Violates:** R17
- **Description:** DLQ is mentioned; **backpressure is not.** When the LLM provider is slow, or a tenant dumps 10,000 emails, what sheds load? What is the queue-depth alarm? Is a dead-lettered event replayable, and is replay idempotent given F-06's missing inbox?
- **Correction:** Define per-tenant concurrency and rate limits (also addresses noisy-neighbour), queue-depth SLOs, shed-load behaviour, and **explicit DLQ replay semantics** that route through the inbox.
- **Blocked:** No. · **Changes:** §17.4, §27.3.

### F-28 — Evidence/blob growth and audit-query performance are unaddressed
- **Severity:** MEDIUM · **Section:** §16.4, §25 · **Violates:** operability
- **Description:** Raw observations are retained forever, documents are retained forever, every agent step is evidence. **No storage growth model, no tiering, no cost envelope, and no index strategy for the audit queries §25.3 promises** (*"why did you do that?"* is a graph traversal across four stores).
- **Correction:** Retention/tiering policy (hot/cold), a documented growth model, and a **stated performance target for the explainability query** — because an audit answer that takes four minutes will not be used.
- **Blocked:** No. · **Changes:** §16.4, §25.2, §27.

### F-29 — The Command model is required but never specified
- **Severity:** MEDIUM · **Section:** §11.1, §15 · **Violates:** internal consistency
- **Description:** §11.1 mandates the type system distinguish Event from Command. **No Command entity, no command bus, and no command lifecycle is specified anywhere**, and the service map has no owner for it. §13.2 gestures at "intent lives in the work item," which is not the same thing.
- **Correction:** Either specify Commands as first-class (with their own durability and idempotency), or **explicitly state that intent is represented solely by Work Items and pipeline instances** — and remove the Command language from §11.1. **Ambiguity here guarantees divergent implementations.**
- **Blocked:** No. · **Changes:** §11.1, §13.2, §15.

### F-30 — "An exception closed without a decision is not closed" is enforced by nobody
- **Severity:** MEDIUM · **Section:** §12.2, §13 · **Violates:** Operating Model L7, I11
- **Description:** The Operating Model is emphatic that an exception closed without a recorded decision is *forgotten, not closed.* **No mechanism enforces this.** No lifecycle forbids the transition.
- **Correction:** The Exception lifecycle's terminal transition **requires a decision reference** (a human decision, or a deterministic rule id). A closure event without one is an **illegal transition** (P10 — a hard error).
- **Blocked:** No. · **Changes:** §12 (as part of F-19).

---

## LOW

### F-31 — Escalation precision is measured but has no mechanism
- **Severity:** LOW · **Section:** §21.3, §25.6
- Escalation precision is named as a metric and a "designed constraint," but there is **no deduplication, aggregation, batching, or suppression design**. Ten identical missing-POD escalations arrive as ten interruptions. **Metric without mechanism is an aspiration.**
- **Correction:** Specify escalation aggregation (by loop/entity/cause), suppression of duplicates, and a digest path. · **Changes:** §21.3.

### F-32 — The service map lacks an owner for the oversight/notification surface
- **Severity:** LOW · **Section:** §15.2, §21.4
- §21.4 requires channel-agnostic oversight adapters; §15.2's service map has no service owning them. Minor, but it is the kind of gap that grows a second god-module.
- **Correction:** Add an explicit surface/notification adapter boundary under Approval & Oversight. · **Changes:** §15.2.

---

# PART B — SCENARIO ATTACKS

*A `PASS` requires the architecture to specify the behaviour **concretely**. Words like "idempotent," "auditable," or "fail-closed" without a mechanism earn `FAIL`.*

| # | Scenario | Verdict | Why |
|---|---|---|---|
| 1 | Same inbound email delivered twice | **FAIL** | No Observation identity/dedup key (F-13). "Consumers must be idempotent" is an instruction, not a mechanism (F-06). |
| 2 | One document plausibly matches two active loads | **PASS** | §10.3 escalates on two candidates. *(But note: this is the only ambiguity case it catches — see #15 and F-04.)* |
| 3 | Two carriers accept the same load simultaneously | **FAIL** | No entity-level concurrency control or loop reservation (F-10). Both pipelines pass all gates independently. |
| 4 | Broker manually covers while automation is active | **FAIL** | F-10. The projection learns of the human's action only on the next observation — **after** the second rate con is issued. |
| 5 | TMS write succeeds, response times out | **PARTIAL** | §19.8 says *verify, don't retry* — correct. But the readback target is unaddressable (F-11) and durability of the commit key is unspecified (F-06). |
| 6 | Readback sees a stale page, reports the old value | **FAIL** | No freshness requirement on the readback, no delta confirmation (F-11). **This exact defect has already shipped once.** |
| 7 | Approval granted, then the amount changes before execution | **FAIL** | The stage order revalidates *before* the gate (F-01) and the approval is not bound to the facts (F-08). **This is the most likely way this architecture pays the wrong amount.** |
| 8 | Carrier sends two conflicting rate confirmations | **PARTIAL** | §6.3 records a Conflict and blocks (good). But no rule distinguishes an **amendment** from a **duplicate/fraud**, and no supersession semantics exist. |
| 9 | Detention verbally approved, no artifact exists | **FAIL** | The model *can represent it* (§8.3 — a genuine strength). But a **model-asserted** authorization can then gate money with no human confirmation (F-05). The strength is the vulnerability. |
| 10 | Carrier invoice with one missing line and one conflicting line | **PASS** | The five conditions are distinct and both `absent` and `conflicting` block consequential action (§6.4.4, §3.3). |
| 11 | Customer changes an appointment after dispatch | **PARTIAL** | The projection updates on observation. **No cascade rules**: which expectations, work items, and downstream commitments are invalidated is undefined (relates to F-19). |
| 12 | Tracking integration unavailable for six hours | **PARTIAL** | Correctly yields `unknown` and announces blindness (§25.5). But expectations can still tick to `overdue` during the blackout (F-14). |
| 13 | POD never arrives **and** the observation channel is offline | **FAIL** | F-14 exactly. The system will chase a carrier for a POD it may already have, and tell the owner the load isn't billable. **This is the "all invoices paid in full" SCAR, reincarnated.** |
| 14 | Malicious PDF contains instructions aimed at the agent | **PARTIAL** | §24.1 states the boundary and requires adversarial testing, but the **containment mechanism is not designed** (how content reaches a vision/extraction model without occupying an instruction position). Stated, not built. |
| 15 | Two agents produce conflicting identity-binding claims | **FAIL** | Claim-vs-claim conflict is not modeled (F-16). **Last-writer-wins** — the precise behaviour ADR-001 forbids, arriving through a state class the ADR didn't consider. |
| 16 | A correction is later discovered to have been wrong | **PARTIAL** | Correction history exists. But correction-of-correction is undefined, and there is **no compensation path** once the wrong binding already caused an external effect (F-17). |
| 17 | A customer-specific rule conflicts with a newer direct instruction | **FAIL** | No precedence rule (F-26). The agent resolves it — **a model resolving a policy conflict** (P2 violation). |
| 18 | Browser session expires halfway through a consequential action | **FAIL** | Unknown-outcome protocol says *verify* — **but verification requires the session that just died.** The architecture has **no terminal handling for an unresolvable unknown-outcome.** The effect is neither confirmed nor refuted, and nothing owns it. |
| 19 | A tenant-scoped worker consumes another tenant's event | **FAIL** | Tenant is absent from the partition key and consumer scoping (F-12). §7.1's "structurally impossible" is contradicted by §17.2. |
| 20 | Projection rebuild differs from production | **PARTIAL** | The test exists (§28.5). **The response does not** (F-24). No one knows whether to halt, replace, or investigate. |
| 21 | Old runtime and new runtime both attempt the same effect | **FAIL** | No shared commit-key namespace across the strangler boundary (F-07). **Double-billing is reachable during migration.** |
| 22 | The human brake is activated while work is executing | **FAIL** | Undefined (F-15). The naive implementation (kill workers) **manufactures unknown-outcomes** — the safety feature creates the most dangerous state in the system. |
| 23 | An event arrives before the entity it references exists | **FAIL** | No ordering guarantee across partitions and **no specified behaviour** for a dangling reference. No parking/retry/reorder design. |
| 24 | A compensating action fails after the original succeeded | **PARTIAL** | §26.3 says compensations are gated and idempotent. **No terminal state** for a failed compensation → the work item is stuck with a real-world inconsistency and no owner (relates to F-19, F-17). |
| 25 | An owner asks why an action occurred six months later | **PARTIAL** | Events replay, but **knowledge and evidence are not version-pinned** (F-18). We can show *what we did*; we cannot faithfully show *what we knew*. **I6 fails on its own use case.** |

**Scenario tally:** **PASS 2** · **PARTIAL 9** · **FAIL 14**

---

# PART C — VERDICT

## 1. Overall verdict

> ## **APPROVE WITH REQUIRED CHANGES**
> **Implementation is BLOCKED.**

The **foundations are correct and should not be redesigned**: the authority model (ADR-001/002), the state-class separation, the loop/work model, the expectation-and-absence design, the placement of guardrails before agents, and the decision to remain a modular monolith are all **right**, and several are genuinely hard-won.

The document **fails as an implementable architecture** because its most load-bearing guarantees are **asserted rather than mechanised**. Fourteen of twenty-five adversarial scenarios fail. **Three of the failures are re-runs of defects this project has already shipped once** (stale readback; unknown rendered as absent; false completion) — which is the strongest possible evidence that stating a principle does not implement it.

**This is not a rejection.** The architecture is one revision away from being sound. It is a refusal to let anyone build from it in its current state.

## 2. Findings by severity

| Severity | Count |
|---|---|
| **CRITICAL** | **7** |
| **HIGH** | **15** |
| **MEDIUM** | **8** |
| **LOW** | **2** |
| **Total** | **32** |

## 3. Implementation-blocking findings (must close before any code)

**All 7 CRITICAL, plus the HIGH findings that are unimplementable-without:**

| ID | Blocker |
|---|---|
| **F-01** | Stage order defect — revalidation must follow the human gate; approvals must be void on data drift |
| **F-02** | Effect boundary must be **structurally** unbypassable (execution capability tokens + CI enforcement) |
| **F-03** | Verification taxonomy — not every effect is readback-verifiable |
| **F-04** | Identity confirmation must be deterministic; confidence must never confirm |
| **F-05** | A model-asserted authorization must never gate money — **permanent, not policy** |
| **F-06** | Pipeline durability + transactional outbox + consumer inbox |
| **F-07** | Migration mutual exclusion (shared commit-key namespace, or hard cutover with deletion) |
| **F-08/F-09** | Approval bound to material facts; approval-vs-retry truth table |
| **F-10** | Entity-level concurrency control |
| **F-11** | Readback target addressing + delta confirmation |
| **F-12** | Tenant in the partition key and consumer lease |
| **F-13** | Observation identity / dedup |
| **F-14** | No `overdue` without demonstrated observability |
| **F-15** | Brake semantics = admission control, not termination |
| **F-16** | Claim-vs-claim conflict |
| **F-17** | Correction → compensation path |
| **F-18** | Version-pinned decision context (I6) |
| **F-19** | **The state machines must actually be written** |
| **F-20** | Gates must be positively asserted and partially ungatable-away |
| **F-21** | Event versioning |
| **F-22** | Revalidation of native-state dependencies |

## 4. Provisional decisions that are safe to defer

- **FORK A (load family)** — **SAFE TO DEFER.** The provisional choice (keep all six distinct, default 1:1, never collapse) is genuinely reversible in the correct direction. *Collapsing later is trivial; splitting later is impossible.* **This reasoning survives review.**
- **FORK B (credentials/session)** — **SAFE TO DEFER as a decision**, but **NOT safe to defer its consequences.** The `SessionProvider` abstraction is correct. **However, F-14 and scenario 18 show the architecture is not yet honest about operating without a session.** Deferring the fork is fine; deferring *degraded-mode design* is not.
- **ADR-005 (physical schema)** — safe to defer; correctly gated on real query patterns.
- **ADR-006 (channel strategy)** — safe to defer; the adapter boundary is right.
- **ADR-007 (mock estate)** — safe to defer, **but §30.3 (sever the mock write path from the live stack) is NOT deferrable** — it is a live risk today.

## 5. Open questions requiring customer evidence

| # | Question | Now blocking |
|---|---|---|
| **B10** | **Repository hygiene** | **Blocks all implementation. Unchanged, and now compounded by F-07.** |
| **B6** | How accessorials are authorized in the moment, and where recorded | **Escalated by F-05.** This determines whether an authorization can *ever* be safely inferred, or must *always* be human-asserted. It is now the highest-value field question. |
| **B5** | What is in their spreadsheets | Likely reveals entities and an unmodeled source (§6). |
| **B3** | Roles and approval authority | Blocks §7.3 and F-20's ungatable-away class list. |
| **B1** | Load-family relationships | Deferred safely (Fork A). |
| **B4** | Real TMS and API availability | Affects adapter cost only. |

## 6. Sections that are strong and require no redesign

- **§4** (assumptions register) — **the reasoning on Fork A's reversibility is the strongest single argument in the document** and should be preserved verbatim.
- **§6.1–6.2, ADR-001, ADR-002** — the projection/lineage separation is correct. The narrowing of C1 (typed records, field-level lineage) avoided a serious self-inflicted wound.
- **§14 (Expectations)** — the *concept* is right and it is the document's most original contribution. It fails only at the edges (F-14), not at the core.
- **§3.3 / five evidence conditions** — correct and load-bearing. Keep.
- **§15.1 (modular monolith)** — correct, and correctly justified by P36 rather than by fashion.
- **§20 placed before §23** — correct. Order encodes intent.
- **§28.2 (bounding non-determinism adversarially)** — correct and unusually well-specified.
- **§30.1 (blocking prerequisite)** — correct, and vindicated by F-07.

## 7. Prioritized correction order

**Wave 1 — the spine cannot be built without these (do first, in order):**
1. **F-02** — make the effect boundary structurally unbypassable. *Nothing else is real until this is.*
2. **F-06** — pipeline durability, outbox, inbox. *The pipeline is a state machine, not a function.*
3. **F-01 + F-08 + F-09** — correct the stage order; bind approvals to facts; define the approval/retry truth table.
4. **F-19** — **write the state machines.** Everything above depends on them existing.

**Wave 2 — cannot run consequential work without these:**
5. **F-03** — verification taxonomy.
6. **F-04** — deterministic identity confirmation.
7. **F-05** — human-only authorization assertion *(and the Operating Model §7.5 amendment it requires)*.
8. **F-11** — readback target addressing.
9. **F-10** — entity concurrency control.
10. **F-22** — native-state revalidation.

**Wave 3 — cannot operate multi-tenant or unattended without these:**
11. **F-12** — tenant partitioning.
12. **F-13** — observation identity.
13. **F-14** — no `overdue` without observability.
14. **F-15** — brake semantics.
15. **F-16, F-17** — claim conflict and compensation.
16. **F-20** — ungatable-away action classes.
17. **F-18, F-21** — version pinning and event versioning.

**Wave 4 — before migration:**
18. **F-07** — migration mutual exclusion. **And B10 (repository hygiene) first, always.**

**Wave 5 — before scale:** F-23 through F-32.

---

## CLOSING NOTE FROM THE REVIEWER

The architecture's own constitution contains the sentence that condemns this draft:

> **P17 — "Tests are necessary and never sufficient."**

The same is true one layer up. **A principle is necessary and never sufficient.** This document states the right principles with unusual clarity and then, in its most important places, **stops at the principle.** The result is a specification that would pass a values check and fail production — which is the most dangerous kind, because it *reads* safe.

**Fourteen of twenty-five scenarios fail. Three of them are defects this codebase has already shipped once.** That is not a coincidence; it is the signature of an architecture that has described its intentions and not yet built its walls.

Close the seven CRITICALs and write the state machines. Then it is buildable.
