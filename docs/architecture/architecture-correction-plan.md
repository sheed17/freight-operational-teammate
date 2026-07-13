# Architecture Correction Plan

**Input:** `architecture-review.md` (32 findings; 25 scenarios: 2 PASS / 9 PARTIAL / 14 FAIL)
**Purpose:** convert 32 isolated findings into **13 coherent architectural mechanisms**. Patching findings one at a time would produce 32 uncoordinated accretions and violate P36 (minimize surface area) and P18 (one canonical path).
**Constraint:** the Target System Specification is **NOT modified by this document.** This is the plan to modify it.
**Date:** 2026-07-09

---

## 0. THREE CORRECTIONS TO THE REVIEW ITSELF

Before planning, the review's own defects must be recorded.

### 0.1 Three scenario failures were never assigned finding IDs
The review marked them FAIL/PARTIAL and then never enumerated them. **A finding without an ID does not get fixed.**

| New ID | Finding | Severity | From |
|---|---|---|---|
| **F-33** | **No terminal handling for an *unresolvable* unknown-outcome.** When the verification channel dies with the effect (e.g. the browser session expires mid-write), the effect is neither confirmed nor refuted, and **nothing owns it.** | **CRITICAL** | Scenario 18 |
| **F-34** | **Dangling event references.** An event arriving before the entity it references exists has no specified behaviour. No parking, no reorder, no TTL. | **HIGH** | Scenario 23 |
| **F-35** | **Prompt-injection containment is stated, never designed.** §24.1 asserts the boundary and mandates adversarial tests; **no mechanism explains how untrusted content reaches an extraction/vision model without occupying an instruction position.** | **HIGH** | Scenario 14 |

**Revised totals: 35 findings — 8 CRITICAL, 17 HIGH, 8 MEDIUM, 2 LOW.**

### 0.2 The requested mechanism taxonomy has no home for security containment
Groups A–L cover pipeline, approval, verification, identity, state, concurrency, observation, tenancy, control, migration, replay, and operability. **None of them owns untrusted-content containment or fraud signals.** F-35, and the fraud-signal half of ADR-003, would have been orphaned.

➡️ **Adding Group M — Untrusted Content Containment & Fraud Signals.**

### 0.3 ⚠️ The review's own recommended correction for F-20 would have violated a frozen document
F-20's correction proposed that **money-out** be made *"structurally ungatable-away… enforced in code, not config."*

**That contradicts the frozen Operating Model §7.6**, which explicitly classifies *"money leaving the business requires explicit human approval"* as **current product policy — evolvable by deliberate decision** — and §7.5, which states that what is permanent is **the capability to gate**, not which gate is closed.

> **Had this been implemented as written, the architecture would have silently overruled a frozen product decision** — the exact failure the document hierarchy exists to prevent. The reviewer caught a real defect and then proposed a fix that broke the constitution.

**Reconciliation (adopted below in Group B):**
1. **Mechanism (universal):** *no gate is expressible as an absence.* Every action class carries a **positively-asserted** gate decision — including `AUTONOMOUS_WITHIN_CAPS(cap)`. There is no null, no default, no omission. Changing one requires an ADR and emits a security event.
2. **Permanent set (narrow):** a **small, code-enforced, ungatable-away** set containing **only permanent truths** (Operating Model §7.5). **Today that set contains exactly one member: Authorization Assertion (ADR-003).**
3. **Money-out remains a policy gate** — strongly defaulted, changeable only by explicit product decision and ADR. **Erosion is prevented by the ADR requirement and the security event, not by pretending it is a truth.**

---

# THE THIRTEEN MECHANISM GROUPS

---

## GROUP A — Effect Capability & the Durable Action Pipeline

**Findings resolved:** F-02 *(CRITICAL)*, and the pipeline-durability half of F-06 *(CRITICAL)*.

**Sections affected:** §15.2, §18.2, §19 (recast), §23.4, §28 (new bypass test), §30.5.

**ADRs required:** **ADR-004 — Execution Capability Tokens and the Unbypassable Effect Boundary.**

### Mechanism
1. **Execution Capability Token (ECT).** An adapter accepts **only** an ECT. An ECT is minted **solely by the Action Pipeline**, only after every prior stage has passed. It is scoped to: `(tenant, action_class, commit_key, declared_entity_versions, approval_id?, single_use, short TTL)`. It is a **capability object, not a string** — unforgeable and non-constructible by callers.
2. **Adapters are non-constructible outside the pipeline.** The adapter registry is reachable only from the pipeline module. There is no public constructor.
3. **CI enforcement (preventive).** A static check fails the build if **any** module outside `pipeline/` imports `adapters/`. This is the mechanism that makes §19's claim true rather than aspirational.
4. **Orphan detection (detective).** Every adapter invocation emits an `EffectAttempted` event carrying its ECT id. A reconciler asserts that **every adapter invocation has a matching pipeline record**. An orphan is a **Sev-0**.
5. **No admin backdoor.** Migration tooling, admin tooling, retry handlers, and compensating workflows are **ordinary pipeline clients**. There is no elevated path, for anyone, ever.
6. **The Pipeline is a durable saga, not a function call.** Every stage transition is **durably checkpointed before the next stage begins**, so a crash at any point leaves a resumable, inspectable instance rather than a void.

### Invariants enforced
**P3, P18, R6, R7, R14, I2, I10.** Directly discharges Operating Model §11 binding #6 (*a gate on any action, enforceable permanently*).

### Interactions
- **Enables B** (the gate is only meaningful if it cannot be skipped).
- **Enables K** — *replay literally cannot cause side effects, because replay is never granted an ECT.* This is a far stronger guarantee than "replay must be side-effect free."
- **Enables J** — migration tooling has no privileged path.
- **Required by everything.** No other mechanism is real without this one.

### Unresolved assumptions
None. This is unconditional.

### Scenarios moved
Prerequisite for **5, 21, 25**. Directly flips none — **it is the foundation the others stand on.**

### Frozen-document change
**No.**

---

## GROUP B — Approval Binding, Revalidation, Retry & Expiry

**Findings resolved:** F-01 *(CRITICAL)*, F-08, F-09, F-20, F-22, and the pipeline-order half of ADR-003.

**Sections affected:** §19.1 (stage order — **corrected**), §19.2, §19.4, §20.6, §21.1, §29.4.

**ADRs required:** **ADR-005 — Approval Binding, the Material-Facts Fingerprint, and Gate Assertion.**

### Mechanism
1. **Corrected stage order** *(the defect in §19.1)*:
```
intent
  → policy (pre-check, cheap rejection only)
  → deterministic validation
  → [GATE: escalate · await human decision — an UNBOUNDED asynchronous wait]
  → REVALIDATION (immediately before execution)          ← moved here
  → policy (final, authoritative)
  → commit-key reservation
  → execute (with ECT)
  → verify
  → record
  → project
```
**The pre-gate check is a cheap early rejection. It authorizes nothing.** The authorizing check happens *after* the human decision, immediately before the effect.

2. **Material-Facts Fingerprint (MFF).** The exact set of facts the human's decision depended on — **projected *and* native** (F-22) — captured as `(field_ref, value, as_of, source, state_class)` and hashed. **The approval is bound to the MFF, not merely to the action.**

3. **Void-on-drift.** At post-gate revalidation the MFF is **recomputed**. Any difference → **the approval is VOID.** The action does not execute. It **re-escalates showing the human exactly what changed.**

4. **Native-state revalidation (F-22).** "Revalidate against the authoritative source" is meaningless for native state, where **Neyma *is* the source.** Revalidation of a native dependency = **re-read the claim and assert it is still valid, unretracted, unsuperseded, and not `conflicting`.** Every dependency — projected and native — is enumerated and revalidated. *"Authoritative" is not a synonym for "stable."*

5. **Approval semantics — the truth table** (resolves F-09's contradiction):

| Event | Approval |
|---|---|
| Attempt **provably did not execute** (deterministic failure, pre-execution abort) | **SURVIVES** — a network flake must not cost a human's attention (§2.8) |
| **Unknown outcome** | **VOID** + escalate (Group C, F-33) |
| **MFF drift** | **VOID** + re-escalate with the diff |
| **TTL expiry** | **VOID** |
| **Brake engaged** before execution | **VOID** |
| **Effect committed** | **CONSUMED** |

> **The rule: an approval authorizes one *committed effect*, not one *attempt*.**

6. **Gate assertion (F-20, reconciled per §0.3):**
   - **No gate is expressible as an absence.** Every action class carries a positively-asserted decision: `HUMAN_REQUIRED` · `AUTONOMOUS_WITHIN_CAPS(cap)` · `UNGATABLE_PERMANENT`. **There is no null and no default.**
   - **`UNGATABLE_PERMANENT` is a code-enforced set containing only permanent truths.** **Today: exactly one member — Authorization Assertion (ADR-003).**
   - **Money-out remains a policy gate** (Operating Model §7.6): strongly defaulted to `HUMAN_REQUIRED`, changeable **only** by explicit product decision + ADR, and **any change emits a security event** (§24).

### Invariants enforced
**P3, P4, P12, R4, R7, I3, I12.** ADR-001 C4. ADR-003.

### Interactions
- **Depends on A** (a gate that can be bypassed is not a gate).
- **Depends on C** (unknown-outcome → VOID requires the unknown-outcome protocol).
- **Depends on F** (entity versions are part of the MFF — this is how optimistic concurrency is *enforced*, at the same checkpoint).
- **Depends on D** (an Authorization claim is an MFF member; ADR-003).

### Unresolved assumptions
**Approval TTL length** is `NEEDS VALIDATION` — it depends on how the partner actually works (an overnight approval may be normal). **Do not hardcode.** Per-tenant configuration, defaulted conservatively.

### Scenarios moved
**7 FAIL → PASS.** **9 FAIL → PASS** (with D). Contributes to **5**.

### Frozen-document change
**YES — already executed.** Operating Model §7.5 amended with permanent truth #6 (ADR-003). No further frozen changes; §7.6 is **preserved intact** per §0.3.

---

## GROUP C — Verification Taxonomy & Unknown-Outcome Handling

**Findings resolved:** F-03 *(CRITICAL)*, F-11, **F-33 *(CRITICAL, new)***.

**Sections affected:** §18.2, §19.2, §19.6, §19.8, §21 (surfacing weaker verification), §26.1.

**ADRs required:** **ADR-006 — Verification Modes and the Unknown-Outcome Protocol.**

### Mechanism
1. **Verification mode is a mandatory property of every action class:**

| Mode | Meaning | Evidence | Example |
|---|---|---|---|
| **Readback-verifiable** | The effect creates observable state in an authoritative system. **MUST be read back.** | The state itself | TMS invoice · filed document · recorded payable |
| **Receipt-verifiable** | No readable state; an external party issues a durable acknowledgement. **Strictly weaker.** | The receipt | Email message-id · SMS delivery receipt |
| **Unverifiable** | Neither exists. | None | Fire-and-forget portal POST |

2. **The readback contract** (F-11). A readback MUST: **(a)** force a **fresh, cache-defeating** read; **(b)** address the target by an identifier **captured from the write response** or a pre-registered idempotency reference — **never "the most recent record"**; **(c)** confirm the **specific expected delta**, not merely that a plausible value exists. **If the target cannot be addressed, the action class is *not* readback-verifiable** — it falls to receipt or unverifiable.

3. **Unverifiable effects:** carry a **stronger gate before them** (§4.5 of the Principles), are **explicitly enumerated and accepted by product** (never discovered by an implementer at 2am), and are **never reported to the owner with the same confidence as a verified effect.** *The owner sees the difference.*

4. **The unknown-outcome protocol.** On an unknown outcome the entity enters **`NEEDS_VERIFICATION`**:
   - the **commit key remains reserved** (never released) — so no retry can double-act;
   - **all further consequential effects on that entity are BLOCKED**;
   - a human is escalated **with the dollar exposure stated**;
   - the approval is **VOID** (Group B).

5. **F-33 — the unresolvable unknown.** If the **verification channel is also unavailable** (the browser session died with the write), the effect **remains `NEEDS_VERIFICATION` indefinitely.** It **MUST NOT** time out into success, and it **MUST NOT** time out into failure. **A human owns it. The entity stays frozen for consequential actions until reality is established.**
> **This is the correct behaviour and it is deliberately uncomfortable.** Any timeout here is a decision to guess about money.

### Invariants enforced
**P5, P6, P8, R9, R10, I10.**

### Interactions
- **Depends on A** (verification is a pipeline stage; the ECT scopes the readback).
- **Feeds B** (unknown → approval VOID).
- **Feeds I** (an aborted-in-flight effect *creates* `NEEDS_VERIFICATION` by design).
- **Feeds F** (a frozen entity refuses new reservations).

### Unresolved assumptions
The **complete list of unverifiable action classes** is `NEEDS VALIDATION` — it depends on which external systems the partner actually uses (**B4**).

### Scenarios moved
**5 PARTIAL → PASS · 6 FAIL → PASS · 18 FAIL → PASS.**

### Frozen-document change
**No.**

---

## GROUP D — Identity Confirmation, Claims, Conflicts & Corrections

**Findings resolved:** F-04 *(CRITICAL)*, F-05 *(CRITICAL — decided by ADR-003)*, F-16, F-17, F-26.

**Sections affected:** §6.3, §8.3, §9.2, §9.4, §10 (whole), §22, §5.2 (the I8/P4 traceability claim is currently **false**).

**ADRs required:** **ADR-007 — Deterministic Identity Confirmation, Claim Conflict & Correction Compensation.** *(ADR-003 already covers authorization assertion.)*

### Mechanism
1. **The deterministic confirmation predicate (F-04).** A binding is confirmed **only** by an **exact match on a trusted identifier**, or an exact match on a **documented composite key**. **Candidate count is irrelevant** — the review's "two candidates or none" test was simply wrong. The correct test is: ***is there sufficient evidence to confirm?*** Everything else escalates.
2. **Confidence appears nowhere in the confirmation predicate** (P4). It may **rank an escalation queue**. Nothing more. *This closes the side door through which confidence was authorizing.*
3. **Trusted identifier registry**, per tenant, documenting each identifier's **collision characteristics** — explicitly including that **a load number is not globally unique across a tenant's customers.**
4. **Binding strength tiers.** An **informational binding** may be probabilistic and is **visibly labelled**. A **consequential binding** (one that gates an effect) **MUST be deterministically confirmed.** A consequential action **cannot** proceed on an unconfirmed binding.
5. **Claim-vs-claim conflict (F-16).** Claims **MUST NOT** silently supersede one another. A new claim contradicting an existing one **raises a Conflict**; the field becomes `conflicting`; **consequential actions are blocked** (ADR-002 C6). Supersession requires a **deterministic rule or a human** — never recency, and never a model. *Last-writer-wins is exactly what ADR-001 forbids, and it was reachable through a state class the ADR did not consider.*
6. **Correction → compensation (F-17).** A correction that invalidates an **already-completed external effect** MUST: raise a **Compensation work item** with an accountable owner **and the dollar exposure stated**; **NOT** silently mutate the projection to a state reality does not hold *(which would also break the rebuild test)*; mark affected fields `conflicting` until reality and projection agree again.
7. **Authorization assertion (ADR-003).** An Authorization claim carries an **`asserting_actor`**. **Model-asserted ⇒ candidate only, zero authority to gate money, permanently.** A counterparty assertion is an **unverified counterparty claim and a fraud signal** (Group M).
8. **Knowledge conflict (F-26).** A **direct human instruction supersedes a standing rule for that instance only**, is recorded as such, and **never silently updates the standing rule.** Rule-vs-rule conflicts **escalate**. **A model never resolves a knowledge conflict** (P2).

### Invariants enforced
**P2, P4, P11, P30, P32, I8.** ADR-001 §2.4, ADR-002 §1.3, ADR-003.

### Interactions
- **Feeds B** (an Authorization claim is an MFF member; a `conflicting` field voids an approval).
- **Feeds M** (counterparty assertions become fraud signals).
- **Depends on E** (the Conflict and Compensation lifecycles must exist).

### Unresolved assumptions
- **B6 — how the partner authorizes accessorials in the moment, and where it is recorded.** **This is now the highest-value field question in the project.** If a **structured record** exists, authorizations become **projected** state and the human burden largely disappears. If it does not, every undocumented accessorial requires a human assertion **forever**.
- **B1 (Fork A)** — *which* member of the load family an artifact binds to. **Safely deferred**; the design already binds to a specific member.

### Scenarios moved
**9 FAIL → PASS · 15 FAIL → PASS · 16 PARTIAL → PASS · 17 FAIL → PASS · 8 PARTIAL → PASS** (supersession semantics distinguish amendment from duplicate/fraud).

### Frozen-document change
**YES — already executed** (Operating Model §7.5 truth #6, ADR-003).

---

## GROUP E — Durable State Machines, Inbox/Outbox & Event Versioning

**Findings resolved:** F-06 *(CRITICAL — outbox/inbox half)*, F-19, F-21, F-23, F-24 *(divergence response)*, F-29, F-30, **F-34 *(new)***.

**Sections affected:** §11, §12 **(substantial rewrite — currently specifies zero state machines)**, §13, §16.1, §16.3, §17, §19 (durability), §26.

**ADRs required:** **ADR-008 — Transactional Outbox, Consumer Inbox & Event Versioning.** *(The state machines themselves are specification content, not an ADR.)*

### Mechanism
1. **Write the state machines (F-19 — the largest gap in the document).** For **every** lifecycle: state set · transition table · **guard for every transition** · terminal states · **reopening rules** *(a POD arriving after a load was written off)* · **cancellation** · **timeout** · **failure states** · **compensation states** · **ownership-transfer triggers**. Lifecycles required: each load-family member · Quote · Carrier compliance · Document · **Expectation** · **Exception** · **Conflict** · Customer Invoice · Payable · Claim (OS&D) · **Work Item** · **Pipeline Instance**.
2. **Transactional outbox.** The **state transition and the event that records it are written in ONE atomic commit.** Publication to the backbone is a **separate, retried** step. *This is how I10 stops being a slogan.*
3. **Consumer inbox.** A dedup table keyed by event id, per consumer. **This is the mechanism by which §17.1's "consumers MUST be idempotent" is actually achieved** — at present it is only an instruction.
4. **Event versioning (F-21).** Every event carries a **version**. Compatibility is **additive-only**, or **upcasters are mandatory**. **The rebuild test runs against the FULL historical corpus, not a recent window** — otherwise it will pass for eighteen months and then be permanently red.
5. **Dangling references (F-34).** An event referencing a not-yet-existent entity is **parked** in a pending-reference buffer with a TTL. It is **not dropped** and **not failed**. TTL expiry → an **Exception** with an owner.
6. **Command model (F-29) — resolve the ambiguity by removing it.** There is **no separate Command entity.** **Intent is represented by the Work Item and the durable Pipeline Instance.** The Pipeline Instance *is* the command: durable, idempotent, and inspectable. *Fewer concepts (P36).* The Command language in §11.1 is deleted; the **Event-is-not-a-Command** rule remains.
7. **Exception closure guard (F-30).** The Exception lifecycle's terminal transition **requires a decision reference** (a human decision id, or a deterministic rule id). **A closure event without one is an illegal transition — a hard error** (P10). *This is how "an exception closed without a decision is not closed" becomes real.*
8. **Work-item ownership (F-23).** A **default owner** (a tenant-level escalation role) is assigned **at creation**. Explicit **reassignment**, **absence**, and **role-revocation** rules. Ownership transfer is an event (already required); its **triggers** are now defined.
9. **Rebuild divergence (F-24).** Divergence is a **Sev-0**: freeze consequential actions on the affected entities, escalate, and **diagnose whether it is a rebuild bug or an undeclared write.** *An undeclared write means Group A has been breached.*

### Invariants enforced
**P8, P9, P10, I4, I9, I10, I11.** ADR-001 C2.

### Interactions
- **Underpins A** (the pipeline is one of these state machines).
- **Underpins C, F, G, I** — all of which need lifecycles that currently do not exist.
- **F-24's divergence response is the detective control for a Group A breach.**

### Unresolved assumptions
The **reopening rules** are partly domain-dependent (*can a written-off load be re-billed when a POD surfaces months later?*) — **`NEEDS VALIDATION` (B5, B6)**.

### Scenarios moved
**1 FAIL → PASS** (with G) · **20 PARTIAL → PASS** · **23 FAIL → PASS** · **24 PARTIAL → PASS** · **11 PARTIAL → PASS** (cascade rules live in the state machines).

### Frozen-document change
**No.**

---

## GROUP F — Entity Concurrency & Work Reservations

**Findings resolved:** F-10.

**Sections affected:** §12, §13, §19.4 (revalidation includes entity versions).

**ADRs required:** **ADR-009 — Optimistic Entity Concurrency and Loop Reservations.**

### Mechanism
1. **Entity versioning (optimistic concurrency).** Every consequential action **declares the entities it will mutate and the versions it read.** Those versions are **part of the MFF** (Group B). Execution is **conditional on those versions still holding** at the post-gate revalidation checkpoint. A version conflict **aborts and re-escalates** — showing the human what changed.
2. **Loop reservations.** A Work Item may hold an **exclusive reservation on `(entity, loop)`** — *"load 4471 is being covered by W-123."* A second attempt to run the same loop on the same entity is **refused at the front door**, not discovered at the effect.
3. **Reservations have a TTL**, are released on closure, and a **stale reservation is an Exception, not a deadlock.**
4. Reservations are **advisory against humans, authoritative against automation** — a human covering a load manually cannot be blocked by our lock, but the **projection will observe their action** and the automation's version check will then **fail safely** (scenario 4).

### Invariants enforced
**P8, P10, I9.**

### Interactions
- **Enforced at Group B's revalidation checkpoint** — one mechanism, one place, not two.
- **Depends on E** (reservation lifecycle).
- **Interacts with C**: an entity in `NEEDS_VERIFICATION` **refuses all new reservations.**

### Unresolved assumptions
None material.

### Scenarios moved
**3 FAIL → PASS · 4 FAIL → PASS.**

### Frozen-document change
**No.**

---

## GROUP G — Observation Identity, Expectations & Observability Continuity

**Findings resolved:** F-13, F-14, F-25.

**Sections affected:** §9.1, §14.2, §14.3, §14.4, §17.1, §25.5, §8.4.

**ADRs required:** **ADR-010 — Observation Identity, the Observability Ledger & Time Semantics.**

### Mechanism
1. **Observation natural key (F-13).** Every Observation carries `(source_system, external_id, content_digest)`. Ingestion is **idempotent** on it. **Crucially: re-observation of an unchanged fact is a *confirmation* — it updates `as_of` — not a new fact.** *This distinction has direct consequences for freshness (§6.5) and for expectation discharge.*
2. **The Observability Ledger (F-14) — the mechanism the architecture was missing.** A durable, queryable record, per `(tenant, channel)`, of **when we could and could not observe.**
3. **The overdue guard.** An Expectation may transition to **`overdue` ONLY IF the Observability Ledger demonstrates continuous coverage of the discharging channel across the entire window.** Otherwise it transitions to **`indeterminate`** — *a distinct exception meaning "I could not watch for this"* — which is **routed differently** and is **never** presented to the owner as a counterparty failure.
> **This is the fix for the reincarnated `SCAR`.** Without it, a six-hour mail outage causes us to chase a carrier for a POD they already sent, and to tell the owner a load is not billable when it is.
4. **Duplicate-expectation prevention:** a natural key on `(what, from whom, why)`.
5. **Deadline change ⇒ a new Expectation version**, never an in-place mutation (preserves I4/I6).
6. **Time semantics (F-25).** All instants stored in **UTC with the originating zone retained**. All **business windows** (appointments, detention clocks, terms, HOS, COI expiry) evaluated in the **facility's / counterparty's local zone**. **DST-safe deadline arithmetic is mandatory.** This becomes a **named test category** (§28) — including the DST-gap deadline.

### Invariants enforced
**I7, I8, I9, P6, R10.** Operating Model §11 binding #1 (*work from a non-event*).

### Interactions
- **Directly mitigates Fork B's consequence.** Under human-established sessions (§4.3), blindness is common — the Observability Ledger makes the architecture **honest** about it rather than silently wrong. **This is what makes deferring Fork B safe.**
- **Feeds §25.5** (honest health: *"I have not been able to check X since T"*).
- **Depends on E** (Expectation lifecycle).

### Unresolved assumptions
**Fork B** determines *coverage*, not design. The mechanism is correct under either posture.

### Scenarios moved
**1 FAIL → PASS · 12 PARTIAL → PASS · 13 FAIL → PASS.**

### Frozen-document change
**No.**

---

## GROUP H — Tenant Isolation & Event Partitioning

**Findings resolved:** F-12.

**Sections affected:** §7.1, §16.5, §17.2, §27.3, §28.

**ADRs required:** *None* — this is enforcement of **P16**, already decided. *(A finding that a frozen principle was not implemented is a bug, not a decision.)*

### Mechanism
1. **Tenant is the first component of every partition key.** No exceptions.
2. **Consumers are leased per tenant.** Cross-tenant consumption is **rejected at the transport**, not at the handler. *A handler-level check is a check that someone will forget.*
3. **The data-access layer enforces tenant scoping structurally** — cross-tenant reads are **impossible to express**, not merely denied (R15).
4. **No shared caches, no shared browser/session state, no shared credential material across tenants.**
5. **A test attempts a cross-tenant read and asserts it is impossible.** *An isolation claim with no test is a hope.*

### Invariants enforced
**P16, R15.**

### Interactions
- **Constrains L** (per-tenant concurrency limits are also the noisy-neighbour control).
- **Constrains Fork B** (a credential vault is per-tenant by construction).

### Unresolved assumptions
None.

### Scenarios moved
**19 FAIL → PASS.**

### Frozen-document change
**No.**

---

## GROUP I — Human Brake & Operational Control Semantics

**Findings resolved:** F-15, F-31.

**Sections affected:** §20.5, §21.3, §25.6, §26, §29.6.

**ADRs required:** **ADR-011 — Brake Semantics and Escalation Aggregation.**

### Mechanism
1. **The brake is admission control, not termination.**
   - It **immediately prevents any new effect from entering `execute`.**
   - **In-flight effects complete `verify` + `record`.** *You cannot un-ring a bell, and abandoning an effect without verifying it is strictly worse than completing it — it manufactures an unknown-outcome, the most dangerous state in the system.*
   - It **reports exactly what was in flight** when it engaged.
2. **`ABORT-IN-FLIGHT` is a separate, higher-severity operation** — it **creates `NEEDS_VERIFICATION` entities by design** (Group C) and carries its own escalation and its own confirmation. **It is not the brake.** Conflating them is how a safety feature becomes an incident.
3. **Brake scope:** global · per-tenant · per-action-class · per-workflow. Every engagement is an **audited event with an actor and a reason.**
4. **Escalation aggregation (F-31).** Escalations are **deduplicated and aggregated** by `(loop, entity, cause)`; duplicates are **suppressed**; a **digest path** exists for low-urgency items. *Ten identical missing-POD escalations are one escalation with a count — not ten interruptions.* **Escalation precision is measured** (§25.6); *escalating everything is the same failure as escalating nothing.*

### Invariants enforced
**P14, I12.** Operating Model §7.5 truth #5 (*a human brake always exists and always works*).

### Interactions
- **Depends on A** (admission control lives at the ECT-minting step — **the brake is enforced by refusing to mint tokens**, which is elegant and unbypassable).
- **Feeds B** (brake engaged ⇒ pending approvals VOID).
- **Feeds C** (abort-in-flight ⇒ `NEEDS_VERIFICATION`).

### Unresolved assumptions
None.

### Scenarios moved
**22 FAIL → PASS.**

### Frozen-document change
**No.**

---

## GROUP J — Migration Mutual Exclusion

**Findings resolved:** F-07 *(CRITICAL)*. **Blocked by B10 (repository hygiene).**

**Sections affected:** §30 (whole).

**ADRs required:** **ADR-012 — Migration Mutual Exclusion and Capability Cutover.**

### Mechanism
1. **⛔ PREREQUISITE — repository hygiene (B10).** A **committed, attributed, test-green baseline.** **Nothing in this group proceeds without it.** *A rewrite forked from an unreconciled tree silently inherits changes nobody has reviewed — and F-07 shows the cost is double-billing.*
2. **PREFERRED: hard cutover per capability.** The legacy path is **physically deleted in the same change** that routes the capability through the new spine. **Deletion is part of the step, not a follow-up ticket** (P37, §30.5 step 5).
3. **IF coexistence is unavoidable** for a given capability: a **shared effect ledger** — **one durable commit-key namespace that BOTH runtimes must reserve against.** Neither may execute without a successful reservation. *This is the only safe form of coexistence, and it is deliberately expensive so that (2) is preferred.*
4. **Sever the mock write path (`tms_write.py`) from every production path immediately** — **independent of, and prior to, ADR-007's decision about retaining it as test infrastructure.** It is a live risk today.
5. **Rollback boundaries** defined per capability, before cutover.

### Invariants enforced
**P8, P18, P37, R14.**

### Interactions
- **Depends on A** (migration tooling is an ordinary pipeline client with no privileged path — *this alone eliminates the most likely bypass*).
- **Depends on E** (commit keys are durable).

### Unresolved assumptions
**B10 is an open operational blocker, not a technical one.** It requires Rasheed to attribute or discard the pre-existing uncommitted changes.

### Scenarios moved
**21 FAIL → PASS.**

### Frozen-document change
**No.**

---

## GROUP K — Replayable Decision Context & Pinned Versions

**Findings resolved:** F-18.

**Sections affected:** §22.1, §22.2, §25.4, §16.1.

**ADRs required:** **ADR-013 — The Decision Record and Content-Addressed Context Pinning.**

### Mechanism
1. **The Decision Record.** Every consequential decision **pins**:
   - the **content-addressed identity** of **every knowledge item injected**,
   - the identity of **every evidence item consumed**,
   - the **model id + prompt version**,
   - the **policy version**,
   - the **MFF** (Group B).
2. **Replay resolves against the pinned versions, not current state.** *This is the difference between an audit and an anecdote.*
3. **Knowledge items are content-addressed and immutable.** **Revocation creates a new version; it never mutates the old.** Otherwise I6 is unsatisfiable by construction.
4. **Replay is side-effect free — structurally.** Replay **is never granted an ECT** (Group A). It therefore **cannot** reach an adapter, cannot mint a token, and cannot cause an effect. *The guarantee is enforced by capability, not by discipline.*

### Invariants enforced
**I3, I4, I6.** P9, P15.

### Interactions
- **Depends on A** (the ECT is what makes replay structurally inert).
- **Depends on D** (knowledge conflict resolution is part of the pinned context).

### Unresolved assumptions
Retention horizon for pinned context is `NEEDS VALIDATION` — driven by **49 CFR §371.3** and dispute windows.

### Scenarios moved
**25 PARTIAL → PASS.**

### Frozen-document change
**No.**

---

## GROUP L — Operability & Scale

**Findings resolved:** F-24 *(time budget)*, F-27, F-28, F-32.

**Sections affected:** §15.2, §16.4, §17.4, §25.2, §27.

**ADRs required:** *None yet.* **Deliberately deferred — these must be driven by real query patterns and real volumes, not by speculation (P36; and `NEEDS VALIDATION` on B-questions).**

### Mechanism
1. **Backpressure (F-27).** Per-tenant **concurrency and rate limits** *(which are simultaneously the noisy-neighbour control — one mechanism, two problems)*. Queue-depth SLOs. Explicit **shed-load** behaviour. **DLQ replay routes through the consumer inbox** (Group E), so replay cannot double-act.
2. **Rebuild economics (F-24).** Rebuild is **incremental and partitionable, per tenant**. A full-corpus rebuild has a **stated time budget**; if it cannot run continuously, it runs **continuously per partition**.
3. **Storage growth (F-28).** Retention and **tiering** (hot/cold) for observations, evidence, and blobs. A **documented growth model**.
4. **Explainability performance (F-28).** A **stated performance target for the "why did you do that?" query.** *An audit answer that takes four minutes will not be used, and an unused audit trail is a decoration.*
5. **Surface ownership (F-32).** An explicit **notification/surface adapter boundary** under Approval & Oversight — *so that we do not grow a second god-module where the first one was* (§2.6).

### Invariants enforced
**R17.** Operability of §25.

### Interactions
- **Depends on H** (per-tenant limits are the isolation boundary).
- **Depends on E** (DLQ replay through the inbox).

### Unresolved assumptions
**Volumes are unknown (B-question: loads/day, emails/day).** **Do not design for scale we cannot evidence** — that is exactly the surface-area inflation P36 forbids.

### Scenarios moved
None directly. **Prevents the architecture from failing at week 20 rather than week 1.**

### Frozen-document change
**No.**

---

## GROUP M — Untrusted Content Containment & Fraud Signals *(NEW — see §0.2)*

**Findings resolved:** **F-35 *(new)***, and the fraud-signal half of **F-05 / ADR-003**.

**Sections affected:** §9.1, §18.6, §19.2, §23, §24.1, §24.2, §28.

**ADRs required:** **ADR-014 — Untrusted Content Containment and Fraud-Signal Handling.**

### Mechanism
1. **Structural containment (F-35).** Untrusted content **NEVER occupies an instruction position.**
   - Content is passed as a **clearly delimited data payload**, with the system-level instruction that the payload is **data to be described, never instructions to be followed**.
   - **The model's output is constrained to a typed schema.** It emits **fields**, never actions. **There is no output channel through which a model can request an effect.**
   - **The strongest containment is Group A:** even a fully compromised model **cannot reach an adapter**, because it has no ECT and cannot mint one. *Injection can corrupt a Claim; it cannot execute an effect.* **This is why A is the keystone.**
2. **Model outputs are Claims, never facts** (ADR-002 §1.3). An injected instruction becomes, at worst, **a bad Claim** — which is **correctable, conflict-detectable (Group D), and blocked from consequential use** until deterministically confirmed.
3. **Fraud signals as first-class evidence.** The following **raise a fraud signal** — which is **evidence routed to a human**, never auto-resolved:
   - a **counterparty assertion of an authorization** (ADR-003: *"per our call, you approved this"*),
   - a **mid-relationship remittance / banking-detail change**,
   - an **MC / identity / contact mismatch** against the carrier of record,
   - a **duplicate invoice** from a different sender identity.
4. **Counterparty payment-detail change is a maximum-scrutiny action class** (§19.2): **always human-gated**, and requiring **out-of-band verification** — never verified through the channel that requested the change. *(`CONFIRMED INDUSTRY PATTERN`: identity theft using stolen MC numbers, emails, and phone numbers is active and escalating — Freight Discovery §12.)*
5. **Adversarial injection is a named test category** (§28) — *we test that the fence holds no matter what the content says* (§4.8).

### Invariants enforced
**P13, R8.** ADR-003.

### Interactions
- **Depends critically on A.** *Containment is defence-in-depth; the capability boundary is the actual wall.*
- **Feeds D** (a counterparty assertion is a Claim + a fraud signal, never an authorization).

### Unresolved assumptions
The partner's actual fraud exposure and history is `NEEDS VALIDATION`.

### Scenarios moved
**14 PARTIAL → PASS.**

### Frozen-document change
**YES — already executed** (Operating Model §7.5 truth #6 explicitly names the counterparty assertion as a fraud signal).

---

# SUMMARY

## Findings → groups (35 total)

| Group | Findings | CRITICAL |
|---|---|---|
| **A** Effect capability & durable pipeline | F-02, F-06(a) | 2 |
| **B** Approval binding, revalidation, retry, expiry | F-01, F-08, F-09, F-20, F-22 | 1 |
| **C** Verification taxonomy & unknown-outcome | F-03, F-11, **F-33** | 2 |
| **D** Identity, claims, conflicts, corrections | F-04, F-05, F-16, F-17, F-26 | 2 |
| **E** State machines, inbox/outbox, event versioning | F-06(b), F-19, F-21, F-23, F-24a, F-29, F-30, **F-34** | 1 |
| **F** Entity concurrency & reservations | F-10 | — |
| **G** Observation identity, expectations, observability | F-13, F-14, F-25 | — |
| **H** Tenant isolation & partitioning | F-12 | — |
| **I** Brake & operational control | F-15, F-31 | — |
| **J** Migration mutual exclusion | F-07 | 1 |
| **K** Replayable decision context | F-18 | — |
| **L** Operability & scale | F-24b, F-27, F-28, F-32 | — |
| **M** Untrusted content & fraud *(new)* | **F-35**, F-05(fraud) | — |

## Scenario outcome if all groups land

| | Before | After |
|---|---|---|
| **PASS** | 2 | **25** |
| **PARTIAL** | 9 | 0 |
| **FAIL** | 14 | 0 |

## ADRs required (11 new)
ADR-004 (effect capability) · ADR-005 (approval binding) · ADR-006 (verification modes) · ADR-007 (identity/claims/corrections) · ADR-008 (outbox/inbox/versioning) · ADR-009 (entity concurrency) · ADR-010 (observation identity & observability ledger) · ADR-011 (brake semantics) · ADR-012 (migration exclusion) · ADR-013 (decision record pinning) · ADR-014 (content containment & fraud).
*(ADR-003 authorization assertion is **done**.)*

## Frozen-document changes
**Exactly one, and it is already executed:** Operating Model **§7.5 truth #6** (Authorization Assertion, ADR-003).
**§7.6 is preserved intact** — see §0.3. **No other frozen document changes.**

## Execution order (dependency-forced, not preference)

| Wave | Groups | Why |
|---|---|---|
| **0** | **B10 — repository hygiene** | Blocks everything. Not technical. |
| **1** | **A**, then **E** | Nothing else is real without the capability boundary and durable state machines. **E must include actually writing the state machines.** |
| **2** | **B**, **C**, **F** | The gate, the verification, the concurrency check — **all three meet at the same post-gate checkpoint**, so they are designed together or not at all. |
| **3** | **D**, **M** | Identity/claims/authorization, and the containment that protects them. |
| **4** | **G**, **H**, **I**, **K** | Honesty about blindness; isolation; control; auditability. |
| **5** | **J** | Migration. Only after the spine exists and B10 is closed. |
| **6** | **L** | Operability, driven by real volumes — not speculation. |

> **Wave 2 is the one most likely to be got wrong by splitting it.** The approval gate, the freshness revalidation, and the entity-version check **all execute at the same instant, immediately before the effect.** They are **one checkpoint**, not three. Designing them separately is how a race condition is born.
