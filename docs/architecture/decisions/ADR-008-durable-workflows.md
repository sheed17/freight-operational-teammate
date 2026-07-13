# ADR-008 — Durable Workflows, State Machines, Outbox & Inbox

**Status:** ✅ **FINAL — ACCEPTED.** *(Superseded the DRAFT of 2026-07-11. All open questions resolved by owner decision, 2026-07-13.)*
**Baseline:** `f0e801b4dfd611345ca6c2842e946d58a7512ae5`
**Resolves:** correction-plan **Group E** — **F-06** (CRITICAL), **F-13**, **F-19**, **F-21**, **F-29**, **F-30**, **F-34**, and the durable-state half of **F-33**.
**Paired with:** **ADR-004.** The effect boundary rides on these machines; these machines are pointless without it.

---

## 1. CONTEXT

Target Specification §12 lists the *requirements* of a lifecycle and the *entities that need one* — and then defines **not a single state, transition, guard, terminal state, reopening rule, cancellation rule, timeout, or compensation path** (F-19).

> **Two engineers implementing from §12 would produce two incompatible systems, and neither would be wrong according to the text.**

Simultaneously §19 describes the Action Pipeline as a **sequence of stages** (`execute → verify → record → project`) with **no transactional mechanism** (F-06). That is the textbook dual-write problem, walked into while asserting **I10** (*no action both taken and unrecorded*).

**Concrete failure:** the pipeline writes an invoice to the TMS, verifies it, and the process is killed before the event persists. **The invoice exists. Neyma has no record it ever acted.** I2, I3 and I10 fail at once — **and a retry bills the customer twice.**

**This ADR replaces §12's prose with machinery.**

---

## 2. DECISION

### 2.1 Owner decisions, recorded

| Decision | Ruling |
|---|---|
| **Store** | **ONE transactional relational store** for machine state, the outbox, the inbox, and the **Effect Grant Ledger**. They must share a transaction; therefore they share a store. (P36) |
| **Work Item : Pipeline Instance** | **1:N.** One business intent, many attempts. |
| **Attempts and compensations** | **Every attempt and every compensation may have its own Pipeline Instance.** |
| **Unit of responsibility and closure** | **The Work Item.** A pipeline instance is an *attempt*; the **Work Item** is what the business owes someone. |
| **Reopening (freight policy)** | **`NEEDS VALIDATION`** where it depends on freight policy (e.g. *may a written-off load be re-billed when a POD surfaces in month 4?*). **The generic machinery is NOT optional and must exist regardless.** |
| **Reopening (mechanism)** | **A reopened workflow NEVER mutates historical closure events.** It **creates a new work phase or a linked Work Item**, preserving prior history intact. |
| **Persistence** | **Transactional outbox** for state + events. |
| **Consumption** | **Durable inbox**, keyed by **`(tenant_id, event_id)`**. |
| **Event versioning** | **Versioned from the FIRST event.** Historical events are interpreted through **explicit upcasters** — never rewritten. |
| **Replay** | **Side-effect free STRUCTURALLY** — it cannot produce an Effect Grant (ADR-004 §4.6). |

### 2.2 The Action Pipeline is a durable state machine, not a function call

**Every stage transition is durably checkpointed before the next stage begins.** A crash at any point leaves a **resumable, inspectable instance — never a void.**

### 2.3 The canonical Durable Machine — the machinery **every** lifecycle uses

**No lifecycle invents its own machinery.**

| Element | Requirement |
|---|---|
| **Identity** | `machine_id`, **`tenant_id` (always, first)**, `type` |
| **State** | A value from an **enumerated set**. `unknown` is a **legal state** wherever the domain admits it (**I7**). |
| **Version** | Monotonic. Optimistic concurrency (ADR-009); detects lost updates. |
| **Transition table** | **Declarative data**, not `if` branches. `(state, event_type) → (next_state, guard, emitted_events)`. |
| **Guards** | Deterministic predicates over **evidence and state**. **NEVER model-evaluated** (P2). |
| **Terminal states** | Explicitly enumerated. |
| **Closure** | **Closure is an emitted event, never an inference** (**I11**). A machine is closed because something closed it — **not because nothing happened lately.** |
| **Cancellation** | Every machine declares whether it is cancellable, from which states, and what it emits. |
| **Timeout** | A **durable timer** emitting `TimerFired`. **A timeout is an event, not a background sweep.** |
| **Failure states** | Explicit. **A machine may fail; it may not vanish.** |
| **Compensation** | Declared wherever an effect may need undoing. |
| **Ownership** | Machines representing *work* carry an **accountable human owner at all times** (**I1**). |
| **Provenance** | Every field carries its **provenance class** — `OWNER_ASSERTED` · `LINKER_INFERRED` · `SYSTEM_IMPORTED`. **Machine recomputation may never overwrite `OWNER_ASSERTED`.** *(Stream B lesson **L-A**.)* |

### 2.4 Illegal transitions are hard errors (F-30, P10)

An event not in the transition table for the current state:
1. **raises**, and
2. **persists no state change**, and
3. **emits `IllegalTransitionAttempted`** — an audit **and security** event.

> **A silently-ignored illegal transition is how a state machine rots back into a pile of `if` statements.**

### 2.5 Transactional outbox (F-06)

> **The state transition and the events it emits are written in ONE atomic commit.**

- **One transaction:** `UPDATE machine_state (version++)` **+** `INSERT events INTO outbox`. **Both, or neither.**
- **A relay** publishes from the outbox and marks rows published. Publication is **at-least-once** and retried.
- **The Effect Grant Ledger (ADR-004) lives in this same transaction**, so minting a grant, transitioning the pipeline, and recording the attempt are **atomic**.

> **I10 stops being a slogan and becomes a database guarantee.**

### 2.6 Consumer inbox (F-06, F-13)

- Every consumer has an inbox with **`UNIQUE (consumer_id, tenant_id, event_id)`**.
- **Processing the event and inserting the inbox row happen in ONE transaction.** A duplicate delivery finds the row present and is a **no-op**.

> **This is *how* "consumers must be idempotent" is achieved. Previously it was an instruction — and instructions are not mechanisms.**

### 2.7 Observation identity (F-13)

- Natural key: **`(tenant_id, source_system, external_id, content_digest)`**. Ingestion is an **idempotent upsert**.
- **Re-observing an unchanged fact is a CONFIRMATION, not a new fact.** It updates `as_of` and emits `ObservationConfirmed`. **It does not create a second Observation and must not re-trigger downstream work.**

> **This is the mechanism that makes "the same email delivered twice" a no-op** rather than a duplicate expectation discharge, a duplicate work item, and a duplicate invoice.

### 2.8 Event versioning and upcasting (F-21)

- Every event carries `type` **and `version`**, **from the first event ever written.**
- **Within a version: additive only.** A breaking change ⇒ **new version + a registered upcaster `vN → vN+1`.**
- **Readers apply upcasters on read. Historical events are NEVER rewritten.** *History is not mutated to make the present tidy.*
- **The rebuild test runs against the FULL historical corpus**, not a recent window — otherwise it passes for eighteen months, then goes permanently red, then gets disabled, **which is worse than never having had it.**

### 2.9 Dangling references — parking (F-34)

An event referencing a machine that does not exist yet is **neither dropped nor failed**:
1. **Parked** in `pending_references`, keyed by the referenced id, with arrival sequence and a **TTL**;
2. **drained in arrival order** when the referenced machine is created;
3. **TTL expiry ⇒ an Exception with an accountable owner.** *A permanently dangling reference is a real problem, and it gets a human — not a log line.*

### 2.10 Crash recovery

On startup, scan machines in **non-terminal transient states**:
- **Pre-effect stages** ⇒ **re-run the checkpoint from the beginning.** Nothing happened.
- **`CLAIMED` / `EXECUTING`** ⇒ ⚠️ **UNKNOWN OUTCOME. NEVER re-execute.** Resolve by **verification** (ADR-006). Unresolvable ⇒ **`NEEDS_VERIFICATION`**, human-owned, entity frozen (F-33).

> **Recovery never guesses. It re-derives, or it escalates.**

**Retry classification is part of recovery** *(Stream B lesson **L-D**)*: every failure is classified **TRANSIENT** (transport — bounded retry with backoff) or **PERMANENT** (authentication, authorization, configuration, protocol — **fail loudly, once, never retried, raise an Exception with a human owner**). **A catch-all base class is not a classification.**

### 2.11 Side-effect-free replay

Replay reconstructs state by applying events through the transition tables. **It cannot cause an effect — not by discipline, but because it cannot construct a `CheckpointPassed` and therefore cannot mint an Effect Grant** (ADR-004). *The guarantee is a consequence of the capability model.*

### 2.12 There is NO Command entity (F-29) — resolved by removal

- **Business intent** = the **Work Item** (*"we intend to bill this load"*).
- **One attempt to effect it** = a durable **Pipeline Instance**.
- **The Pipeline Instance IS the command** — durable, idempotent, inspectable, replayable.
- **Events remain facts.** The *Command* language in §11.1 is **deleted**.

*Fewer concepts (P36). The ambiguity was guaranteeing divergent implementations; the fix is to remove the ambiguity, not to specify a third thing.*

### 2.13 The two states that must never auto-resolve

| State | Rule |
|---|---|
| **`NEEDS_VERIFICATION`** (F-33) | **Non-terminal. Human-owned.** Commit key **stays reserved**. Entity **frozen** for consequential actions. **MUST NOT time out into success or failure.** |
| **`COMPENSATION_FAILED`** (F-17) | **Non-terminal. Human-owned.** Reality and the projection are **known to diverge**. Entity **frozen**, **dollar exposure stated**, escalated. **Never auto-resolves.** |

> **Both are deliberately uncomfortable. Any timeout here is a decision to guess about money.**

### 2.14 Generic reopening machinery *(owner decision)*

**Applies to every closable machine. The freight-policy question of *when* is `NEEDS VALIDATION`; the mechanism of *how* is settled here.**

1. **A closure event is immutable.** Reopening **never** mutates, deletes, or rewrites it.
2. Reopening emits **`Reopened{prior_closure_ref, reason, decision_ref, actor}`** and creates **either**:
   - a **new work phase** on the same Work Item (`phase_seq++`, prior phase preserved), **or**
   - a **new linked Work Item** (`reopens: <prior_work_item_id>`).
3. **Which one:** same obligation to the same party ⇒ **new phase**. A materially different obligation ⇒ **linked Work Item**.
4. **Reopening requires a `decision_ref`** — a human decision id or a deterministic rule id. **Never an inference.**
5. **History is append-only.** *The record of what we believed and when we believed it is the audit trail; a system that rewrites its own closure history cannot be trusted about money.*

---

## 3. THE TEN FOUNDATIONAL LIFECYCLES

**Complete enough that implementers do not invent their own semantics.** Domain lifecycles (Quote, Brokerage Load, Carrier Movement, Document, Customer Invoice, Carrier Payable) are written later, **on this machinery**, and may not deviate from it.

**Legend:** every transition emits an event; every guard is deterministic; **any `(state, event)` pair absent from a table is an ILLEGAL TRANSITION (§2.4).**

---

### 3.1 WORK ITEM — *the unit of business responsibility and closure*

**States:** `OPEN` · `IN_PROGRESS` · `BLOCKED` · `AWAITING_HUMAN` · `ESCALATED` · `CLOSED` **(T)** · `CANCELLED` **(T)**

| From | Trigger | Guard | → | Emits |
|---|---|---|---|---|
| — | `WorkItemCreated` | **owner assigned (I1)** | `OPEN` | `WorkItemCreated` |
| `OPEN` | `PipelineStarted` | ≥1 pipeline instance exists | `IN_PROGRESS` | `WorkStarted` |
| `IN_PROGRESS` | `PipelineClosed` | **no open pipeline; obligation satisfied** | `CLOSED` | `WorkItemClosed{decision_ref}` |
| `IN_PROGRESS` | `PipelineFailed` | retries remain (**TRANSIENT** only) | `IN_PROGRESS` | `AttemptFailed` |
| `IN_PROGRESS` | `PipelineFailed` | **PERMANENT**, or retries exhausted | `BLOCKED` | `WorkBlocked{reason}` |
| `IN_PROGRESS` \| `OPEN` | `EvidenceMissing` \| `ConflictRaised` | — | `BLOCKED` | `WorkBlocked` |
| `IN_PROGRESS` \| `OPEN` | `HumanDecisionRequired` | — | `AWAITING_HUMAN` | `HumanRequested` |
| `BLOCKED` | `BlockerCleared` | blocker resolved | `IN_PROGRESS` | `WorkUnblocked` |
| `AWAITING_HUMAN` | `HumanDecided` | **`decision_ref` present** | `IN_PROGRESS` | `HumanDecided` |
| any non-terminal | `AgeThresholdCrossed` \| `EscalationRequested` | — | `ESCALATED` | `WorkEscalated` |
| `ESCALATED` | `OwnerReassigned` | new owner present | *(prior state)* | `OwnershipTransferred` |
| any non-terminal | `CancellationRequested` | **`decision_ref` present** | `CANCELLED` | `WorkItemCancelled{decision_ref}` |
| `CLOSED` | `ReopenRequested` | **`decision_ref` present** (§2.14) | `IN_PROGRESS` *(new phase)* | `Reopened{prior_closure_ref}` |

| Property | Ruling |
|---|---|
| **Owner** | **A human. Always. From creation.** (I1) Never null, never "the system." |
| **Terminal** | `CLOSED`, `CANCELLED` |
| **Cancellation** | From any non-terminal state, **with a `decision_ref`**. |
| **Expiry** | **NEVER expires.** It ages and escalates. **Work does not disappear because it got old.** |
| **Retry** | Not retried directly — it **spawns another Pipeline Instance** (1:N). |
| **Reopening** | Per §2.14 — new phase or linked item. **Never mutates the closure event.** Freight-policy *when* = **`NEEDS VALIDATION`**. |
| **Failure** | `BLOCKED` — **not a terminal state.** A blocked work item still has an owner. |
| **Correction** | Emits `Corrected{field, prior, new, provenance, decision_ref}` and **propagates** to dependents (F-17). |
| **Compensation** | If a completed effect is invalidated by a correction ⇒ raises a **Compensation** (§3.10). |
| **Closure rule** | **`CLOSED` requires an explicit closure event with a `decision_ref`. Inactivity is not closure** (**I11**). |

---

### 3.2 PIPELINE INSTANCE — *one attempt to produce one effect*

**States:** `PROPOSED` · `POLICY_CHECKED` · `VALIDATED` · `AWAITING_APPROVAL` · `CHECKPOINT` · `GRANTED` · `CLAIMED` · `EXECUTED` · `VERIFIED` · `RECORDED` · `PROJECTED` · `CLOSED` **(T)** · `REJECTED` **(T)** · `VOIDED` **(T)** · `FAILED` **(T)** · **`NEEDS_VERIFICATION`** *(non-terminal, human-owned)*

| From | Trigger | Guard | → | Emits |
|---|---|---|---|---|
| — | `IntentProposed` | `ProposedIntent` is **inert data**; **no effect capability** | `PROPOSED` | `PipelineStarted` |
| `PROPOSED` | `PolicyEvaluated` | **gate decision NOT NULL** (F-20) | `POLICY_CHECKED` | `PolicyEvaluated{policy_version}` |
| `PROPOSED` | `PolicyEvaluated` | policy **denies** | `REJECTED` | `PipelineRejected{reason}` |
| `POLICY_CHECKED` | `Validated` | money fence + document fence + evidence complete | `VALIDATED` | `IntentValidated` |
| `POLICY_CHECKED` | `ValidationFailed` | — | `REJECTED` | `PipelineRejected` |
| `VALIDATED` | — | gate = **`HUMAN_REQUIRED`** | `AWAITING_APPROVAL` | `ApprovalRequested` |
| `VALIDATED` | — | gate = `AUTONOMOUS_WITHIN_CAPS` **and within caps** | `CHECKPOINT` | — |
| `VALIDATED` | — | gate = **`UNGATABLE_PERMANENT`** | `REJECTED` | `PipelineRejected{ungatable}` |
| `AWAITING_APPROVAL` | `ApprovalGranted` | approval binds **this** commit key + fingerprint (ADR-005) | `CHECKPOINT` | `ApprovalBound` |
| `AWAITING_APPROVAL` | `ApprovalDenied` \| `ApprovalExpired` \| `BrakeEngaged` | — | `VOIDED` | `PipelineVoided{reason}` |
| `CHECKPOINT` | `CheckpointPassed` | **all 7 checks** (ADR-004 §2.4) | `GRANTED` | `EffectGranted{grant_id}` |
| `CHECKPOINT` | `CheckpointFailed` | **any** of the 7 fails | `VOIDED` | `PipelineVoided{failed_check}` |
| `GRANTED` | `GrantClaimed` | **atomic CAS succeeded** | `CLAIMED` | `EffectAttempted` |
| `GRANTED` | `GrantExpired` \| `GrantRevoked` | — | `VOIDED` | `PipelineVoided` — **nothing happened** |
| `CLAIMED` | `EffectSucceeded` | adapter returned success | `EXECUTED` | `EffectExecuted` |
| `CLAIMED` | `EffectFailedCleanly` | **provably no effect** (pre-flight rejection) | `FAILED` | `EffectFailed` |
| **`CLAIMED`** | **`OutcomeUnknown`** \| crash \| timeout | ⚠️ **cannot prove nothing happened** | **`NEEDS_VERIFICATION`** | `OutcomeUnknown{exposure}` |
| `EXECUTED` | `ReadbackConfirmed` | readback matches **the approved facts** (ADR-006) | `VERIFIED` | `EffectVerified` |
| `EXECUTED` | `ReadbackContradicts` | readback ≠ approved | **`NEEDS_VERIFICATION`** | `VerificationConflict` |
| `EXECUTED` | `ReadbackUnavailable` | verification channel dead (F-33) | **`NEEDS_VERIFICATION`** | `VerificationUnavailable` |
| `VERIFIED` | `Recorded` | **same atomic commit as verify** (§2.5) | `RECORDED` | `EffectRecorded` |
| `RECORDED` | `Projected` | projection updated | `PROJECTED` | `ProjectionUpdated` |
| `PROJECTED` | `Closed` | — | `CLOSED` | `PipelineClosed` |
| **`NEEDS_VERIFICATION`** | `HumanEstablishedReality` | **`decision_ref` present** | `VERIFIED` \| `FAILED` | `RealityEstablished{decision_ref}` |
| **`NEEDS_VERIFICATION`** | *(any timer)* | — | ⛔ **ILLEGAL** | `IllegalTransitionAttempted` |

| Property | Ruling |
|---|---|
| **Owner** | The **Work Item's** owner. A pipeline is never orphaned. |
| **Terminal** | `CLOSED`, `REJECTED`, `VOIDED`, `FAILED` |
| **Cancellation** | Only **before `CLAIMED`** (⇒ `VOIDED`). **After `CLAIMED`, cancellation is meaningless** — the world may already have changed. **Post-claim undo is COMPENSATION (§3.10), not cancellation.** |
| **Expiry** | Grant TTL ⇒ `VOIDED` (pre-claim, safe). **`NEEDS_VERIFICATION` NEVER expires.** |
| **Retry** | **Never in-place.** A retry is a **NEW Pipeline Instance** with the **same commit key** and a **new grant** (ADR-004 §3.8). |
| **Reopening** | **Never.** A pipeline instance is an attempt; attempts are immutable history. **Reopening happens at the Work Item.** |
| **Failure** | `FAILED` **only when provably no effect occurred.** **Otherwise `NEEDS_VERIFICATION`. When in doubt, it is NOT failure.** |
| **Correction** | Corrections do not mutate a closed instance. They raise a **Compensation**. |
| **Compensation** | A compensation is **its own Pipeline Instance** (owner decision, 1:N) — **fully gated**. |

> **The single most important row in this table is `CLAIMED → NEEDS_VERIFICATION`.** Every system that gets money wrong got it wrong by making that arrow point at `FAILED`.

---

### 3.3 EXTERNAL EFFECT — *the record of touching the world*

**States:** `GRANTED` · `CLAIMED` · `ATTEMPTED` · `VERIFIED` **(T)** · `FAILED` **(T)** · `EXPIRED_UNCLAIMED` **(T)** · **`UNKNOWN_OUTCOME`** *(non-terminal, human-owned)*

| From | Trigger | Guard | → | Emits |
|---|---|---|---|---|
| — | `GrantMinted` | **`CheckpointPassed` witness** (ADR-004) | `GRANTED` | `EffectGranted` |
| `GRANTED` | `ClaimAttempted` | **CAS `GRANTED→CLAIMED`** succeeds | `CLAIMED` | `GrantClaimed` |
| `GRANTED` | `ClaimAttempted` | CAS **fails** (already claimed / expired / revoked) | *(no change)* | `ClaimRefused` — **adapter does nothing** |
| `GRANTED` | `TimerFired` | TTL elapsed, unclaimed | `EXPIRED_UNCLAIMED` | `GrantExpired` — **nothing happened** |
| `GRANTED` | `Revoked` | brake / approval revoked / policy changed | `EXPIRED_UNCLAIMED` | `GrantRevoked` |
| `CLAIMED` | `AdapterReturnedSuccess` | — | `ATTEMPTED` | `EffectAttempted` |
| `CLAIMED` | `AdapterRejectedPreFlight` | **provably no effect** | `FAILED` | `EffectFailed` |
| **`CLAIMED`** | `AdapterTimedOut` \| `ProcessCrashed` \| `ResponseLost` | ⚠️ — | **`UNKNOWN_OUTCOME`** | `OutcomeUnknown{exposure}` |
| `ATTEMPTED` | `Readback` matches | ADR-006 | `VERIFIED` | `EffectVerified` |
| `ATTEMPTED` | `Readback` contradicts / unavailable | — | **`UNKNOWN_OUTCOME`** | `VerificationConflict` |
| **`UNKNOWN_OUTCOME`** | `HumanEstablishedReality` \| `LaterObservationProves` | **`decision_ref`** or a **deterministic observation** | `VERIFIED` \| `FAILED` | `RealityEstablished` |

| Property | Ruling |
|---|---|
| **Owner** | System until `UNKNOWN_OUTCOME`; **then a named human**. |
| **Terminal** | `VERIFIED`, `FAILED`, `EXPIRED_UNCLAIMED` |
| **Cancellation** | **Only in `GRANTED`.** Once `CLAIMED`, cancellation is a lie. |
| **Expiry** | Only `GRANTED` expires. **`UNKNOWN_OUTCOME` NEVER expires** (F-33). |
| **Retry** | **Never.** A new attempt is a **new grant** under the **same commit key** — and the unique index means **if the first one committed, the second cannot.** |
| **Failure** | `FAILED` requires **proof** that nothing happened. **Absence of a success signal is NOT proof of failure** (**I8**). |
| **Compensation** | Undoing a `VERIFIED` effect ⇒ **Compensation (§3.10)**, itself a fully gated effect. |

---

### 3.4 APPROVAL — *(binding detail in ADR-005)*

**States:** `REQUESTED` · `GRANTED` · `CONSUMED` **(T)** · `DENIED` **(T)** · `EXPIRED` **(T)** · `REVOKED` **(T)** · `VOID_ON_DRIFT` **(T)** · `VOID_ON_BRAKE` **(T)**

| From | Trigger | Guard | → | Emits |
|---|---|---|---|---|
| — | `ApprovalRequested` | gate = `HUMAN_REQUIRED`; **material facts fingerprinted** | `REQUESTED` | `ApprovalRequested{fingerprint}` |
| `REQUESTED` | `HumanApproved` | **authorized human**; **the human is authenticated, not asserted** (ADR-003) | `GRANTED` | `ApprovalGranted` |
| `REQUESTED` | `HumanDenied` | — | `DENIED` | `ApprovalDenied` |
| `REQUESTED` \| `GRANTED` | `TimerFired` | TTL elapsed | `EXPIRED` | `ApprovalExpired` |
| `GRANTED` | `MaterialFactsChanged` | **fingerprint ≠ fingerprint at approval** | **`VOID_ON_DRIFT`** | `ApprovalVoided{drift}` |
| `GRANTED` | `BrakeEngaged` | — | `VOID_ON_BRAKE` | `ApprovalVoided{brake}` |
| `GRANTED` | `HumanRevoked` | — | `REVOKED` | `ApprovalRevoked` |
| `GRANTED` | `EffectCommitted` | commit key matches; **checkpoint passed** | `CONSUMED` | `ApprovalConsumed` |
| `GRANTED` | `AttemptFailedProvably` | **provably no effect** | `GRANTED` | — **survives a provably-failed attempt** |
| `GRANTED` | `AttemptOutcomeUnknown` | — | `GRANTED` *(frozen)* | — **must NOT be reused until reality is established** |

| Property | Ruling |
|---|---|
| **Owner** | The approving human. |
| **Terminal** | `CONSUMED`, `DENIED`, `EXPIRED`, `REVOKED`, `VOID_ON_DRIFT`, `VOID_ON_BRAKE` |
| **Expiry** | **Yes — approvals go stale.** An approval given Friday must not execute Monday against changed facts. |
| **Retry** | An approval **survives a provably-failed attempt** and may authorize a **new** pipeline instance under the **same commit key**. **It is consumed exactly once, on commit.** |
| **Correction** | **Any change to a material fact VOIDS the approval.** *(F-01: the human approved £2,850 for load 4471. If either changes, there is no approval — there is a new question.)* |
| **Never** | An approval **cannot** be asserted by a model, a counterparty, or inbound content (**ADR-003 — PERMANENT**). |
| **Ordinals** | The approved **subject** is bound by **immutable id**, never re-resolved from a list *(Stream B lesson **L-B**)*. |

---

### 3.5 OBSERVATION — *what the world told us*

**States:** `RECEIVED` · `PARSED` · `BOUND` **(T)** · `UNBOUND` · `CONFIRMED` · `SUPERSEDED` **(T)** · `UNPARSEABLE` **(T)**

| From | Trigger | Guard | → | Emits |
|---|---|---|---|---|
| — | `ObservationIngested` | **idempotent upsert** on `(tenant, source, external_id, digest)` §2.7 | `RECEIVED` | `ObservationReceived` |
| — | `ObservationIngested` | **natural key already exists, content identical** | `CONFIRMED` | **`ObservationConfirmed`** — *updates `as_of` only; **NOT a new fact**; does **NOT** re-trigger work* |
| `RECEIVED` | `Parsed` | extraction succeeded | `PARSED` | `ObservationParsed` |
| `RECEIVED` | `ParseFailed` | — | `UNPARSEABLE` | `ObservationUnparseable` → **Exception** |
| `PARSED` | `BindingConfirmed` | **deterministic** binding (§3.6) | `BOUND` | `ObservationBound` |
| `PARSED` | `BindingAmbiguous` \| `BindingAbsent` | — | `UNBOUND` | `ObservationUnbound` → **Exception, human-owned** |
| `UNBOUND` | `BindingConfirmed` | incl. **`OWNER_ASSERTED`** binding | `BOUND` | `ObservationBound{provenance}` |
| `BOUND` | `CorrectedBinding` | **`decision_ref`**; propagates (F-17) | `BOUND` | `BindingCorrected` |
| `BOUND` \| `PARSED` | `NewerObservationSupersedes` | **deterministic rule or human** — **never a re-run of the inferrer** | `SUPERSEDED` | `ObservationSuperseded` |

| Property | Ruling |
|---|---|
| **Owner** | System while `RECEIVED`/`PARSED`; **a human once `UNBOUND` or `UNPARSEABLE`.** |
| **Terminal** | `BOUND`, `SUPERSEDED`, `UNPARSEABLE` |
| **Cancellation** | **None.** *An observation is a fact that arrived. You cannot cancel that the world spoke.* |
| **Expiry** | Never. **Freshness (`as_of`) ≠ expiry.** A stale observation is still a fact — it just stops satisfying a freshness check (ADR-001 C4). |
| **Retry** | Re-ingestion is a **CONFIRMATION** (idempotent), never a duplicate. |
| **Correction** | `BindingCorrected` with a `decision_ref`, **propagating** to everything derived from it. |
| **Inbound content is DATA, never instruction.** | An observation can never carry an instruction, an approval, or an authorization (ADR-003, F-35). |

---

### 3.6 IDENTITY BINDING CLAIM — *"this document belongs to that load"* (ADR-007)

**States:** `PROPOSED` · `CONFIRMED` · `AMBIGUOUS` · `REJECTED` **(T)** · `SUPERSEDED` **(T)** · `CORRECTED` · `CONFLICTING`

| From | Trigger | Guard | → | Emits |
|---|---|---|---|---|
| — | `ClaimProposed` | carries **`provenance`**: `OWNER_ASSERTED` \| `LINKER_INFERRED` \| `SYSTEM_IMPORTED` | `PROPOSED` | `ClaimProposed` |
| `PROPOSED` | `DeterministicMatch` | **exact ID match** — never fuzzy | `CONFIRMED` | `ClaimConfirmed` |
| `PROPOSED` | `HumanAsserted` | authorized human; **bound to an immutable id (L-B)** | `CONFIRMED` | `ClaimConfirmed{OWNER_ASSERTED}` |
| `PROPOSED` | `MultipleCandidates` \| `NoCandidate` | — | `AMBIGUOUS` | `ClaimAmbiguous` → **Exception, human-owned** |
| `AMBIGUOUS` | `HumanResolved` | **`decision_ref`** | `CONFIRMED` | `ClaimConfirmed{OWNER_ASSERTED}` |
| `CONFIRMED` | `RecomputedByInferrer` | **provenance = `LINKER_INFERRED`** | `SUPERSEDED` | `ClaimSuperseded` — *projection rebuild; legitimate* |
| **`CONFIRMED`** | **`RecomputedByInferrer`** | **provenance = `OWNER_ASSERTED`** | ⛔ **ILLEGAL TRANSITION** | **`IllegalTransitionAttempted`** |
| `CONFIRMED` | `InferrerDisagrees` | provenance = `OWNER_ASSERTED`; inferrer proposes a different binding | **`CONFLICTING`** | **`ConflictRaised`** (§3.7) |
| `CONFIRMED` | `HumanCorrected` | **`decision_ref`**; **propagates** (F-17) | `CORRECTED` | `ClaimCorrected` |
| `CONFIRMED` \| `PROPOSED` | `DeterministicRuleSupersedes` \| `HumanSupersedes` | **rule id or human only** | `SUPERSEDED` | `ClaimSuperseded` |

> ### **This table is where Stream B lesson L-A becomes machinery.**
> **`OWNER_ASSERTED` + `RecomputedByInferrer` is an ILLEGAL TRANSITION — it raises, persists nothing, and emits a security event.**
> **B3's every-cycle re-route could not compile against this table.** And when the linker genuinely disagrees with the owner, the system does **not** pick a winner — it raises a **Conflict** and **blocks consequential actions** until a human decides. *(I8: missing evidence and contradictory evidence are different states.)*

| Property | Ruling |
|---|---|
| **Owner** | Human once `AMBIGUOUS` or `CONFLICTING`. |
| **Terminal** | `CONFIRMED` *(stable, not frozen)*, `REJECTED`, `SUPERSEDED` |
| **Expiry** | Never. |
| **Retry** | The inferrer may re-run **freely against `LINKER_INFERRED` claims** — that is a projection rebuild. **Against `OWNER_ASSERTED`, never.** |
| **Correction** | `CORRECTED` + **propagation** to every downstream derived fact (F-17). **A correction that does not propagate is a lie with a timestamp.** |
| **Compensation** | If a corrected binding invalidates a **completed effect** (*we billed the wrong customer*) ⇒ raises **Compensation (§3.10)**. |

---

### 3.7 CONFLICT — *two sources disagree*

**States:** `RAISED` · `OPEN` · `ESCALATED` · `RESOLVED_BY_RULE` **(T)** · `RESOLVED_BY_HUMAN` **(T)**

| From | Trigger | Guard | → | Emits |
|---|---|---|---|---|
| — | `ConflictDetected` | system-vs-system · **claim-vs-claim** · claim-vs-observation · **inferrer-vs-owner (§3.6)** | `RAISED` | `ConflictRaised` |
| `RAISED` | `Acknowledged` | owner assigned | `OPEN` | `ConflictOpened` |
| `OPEN` | `DeterministicRuleApplies` | **a registered rule id** — never a model | `RESOLVED_BY_RULE` | `ConflictResolved{rule_id}` |
| `OPEN` | `HumanResolved` | **`decision_ref`** | `RESOLVED_BY_HUMAN` | `ConflictResolved{decision_ref}` |
| `OPEN` | `AgeThresholdCrossed` | — | `ESCALATED` | `ConflictEscalated` |
| `OPEN` \| `RAISED` | `AutoResolve` | — | ⛔ **ILLEGAL** | `IllegalTransitionAttempted` |

| Property | Ruling |
|---|---|
| **Owner** | **A human, from `RAISED`.** |
| **Terminal** | `RESOLVED_BY_RULE`, `RESOLVED_BY_HUMAN` |
| **THE INVARIANT** | ### **While a Conflict is OPEN, the affected field is `conflicting` and BLOCKS every consequential action on that entity.** *(ADR-002 C6.)* |
| **Expiry** | **NEVER.** It escalates. **A conflict that times out is a conflict that got resolved by a clock.** |
| **Cancellation** | Only if the **underlying disagreement disappears** (e.g. a source retracts) ⇒ still requires an event, never silence. |
| **Never** | **Neyma never silently chooses a winner** (ADR-001). *Not on confidence. Not on recency. Not on source priority — unless a registered deterministic rule says so, in writing, with an id.* |

---

### 3.8 EXPECTATION — *"a POD should arrive by Thursday"* (Group G)

**States:** `RAISED` · `DISCHARGED` **(T)** · `OVERDUE` · **`INDETERMINATE`** · `CANCELLED` **(T)** · `EXPIRED` **(T)**

| From | Trigger | Guard | → | Emits |
|---|---|---|---|---|
| — | `ExpectationRaised` | deadline + **observability channel declared** | `RAISED` | `ExpectationRaised` |
| `RAISED` | `ObservationBound` | **discharging observation** matches | `DISCHARGED` | `ExpectationDischarged` |
| `RAISED` | `TimerFired` | deadline passed **AND the observability channel was demonstrably HEALTHY** (F-14) | `OVERDUE` | `ExpectationOverdue` → **Exception** |
| **`RAISED`** | `TimerFired` | deadline passed **AND the channel was DOWN / unknown** | **`INDETERMINATE`** | `ExpectationIndeterminate` |
| `OVERDUE` \| `INDETERMINATE` | `ObservationBound` | late arrival | `DISCHARGED` | `ExpectationDischarged{late}` |
| `RAISED` \| `OVERDUE` | `ReasonDisappeared` | e.g. the load cancelled | `CANCELLED` | `ExpectationCancelled` |
| `RAISED` | `DeadlineChanged` | — | `RAISED` *(v++)* | `ExpectationReVersioned` |
| `OVERDUE` \| `INDETERMINATE` | `TimerFired` | terminal age reached | `EXPIRED` | `ExpectationExpired` → **Exception** |

> ### **`OVERDUE` vs `INDETERMINATE` is the whole point of this machine.**
> **"The POD never came" and "we were not watching" are different facts** (**I8**, F-14).
> **A system that cannot tell them apart will confidently report an on-time delivery as late, and a blind window as clean.** **Overdue may only be asserted when the channel is provably healthy.** Otherwise: **we were blind, and we say so.**

| Property | Ruling |
|---|---|
| **Owner** | System until `OVERDUE`/`INDETERMINATE`; **then a human**. |
| **Terminal** | `DISCHARGED`, `CANCELLED`, `EXPIRED` |
| **Expiry** | Yes — into an **Exception**, never into silence. |
| **Retry** | n/a. |
| **Reopening** | A **late discharge is always accepted** from `OVERDUE`/`INDETERMINATE`. *The POD that arrives in month 4 is still a POD.* |

---

### 3.9 EXCEPTION — *something needs a human*

**States:** `OPEN` · `ACKNOWLEDGED` · `AGEING` · `ESCALATED` · `RESOLVED` **(T)**

| From | Trigger | Guard | → | Emits |
|---|---|---|---|---|
| — | `ExceptionRaised` | **owner assigned at creation (I1)** | `OPEN` | `ExceptionRaised{severity, exposure}` |
| `OPEN` | `Acknowledged` | a human saw it | `ACKNOWLEDGED` | `ExceptionAcknowledged` |
| `ACKNOWLEDGED` \| `OPEN` | `Resolved` | ### **REQUIRES `decision_ref`** | `RESOLVED` | `ExceptionResolved{decision_ref}` |
| `ACKNOWLEDGED` \| `OPEN` | `Resolved` | **NO `decision_ref`** | ⛔ **ILLEGAL TRANSITION** | `IllegalTransitionAttempted` |
| `OPEN` \| `ACKNOWLEDGED` | `TimerFired` | age threshold | `AGEING` | `ExceptionAgeing` |
| `AGEING` | `TimerFired` | escalation threshold | `ESCALATED` | `ExceptionEscalated` |
| any | `AutoClose` \| `Inactivity` | — | ⛔ **ILLEGAL** | `IllegalTransitionAttempted` |

| Property | Ruling |
|---|---|
| **Owner** | **A named human, always, from creation.** |
| **Terminal** | `RESOLVED` — **and ONLY with a `decision_ref`.** |
| **THE RULE** | ### **An exception closed without a decision is not closed — it is forgotten.** *(F-30.)* |
| **Expiry** | **NEVER.** It ages, then escalates. **An exception cannot be outlived.** |
| **Cancellation** | Only if the **underlying cause is retracted** — still an event, still a `decision_ref`. |
| **PERMANENT-failure exceptions** *(L-D)* | An **authentication/configuration** failure raises an Exception **immediately** and **is never retried.** |

---

### 3.10 COMPENSATION — *undoing an effect that should not have happened*

**States:** `REQUIRED` · `APPROVED` · `EXECUTING` · `COMPLETED` **(T)** · **`COMPENSATION_FAILED`** *(non-terminal, human-owned)* · `NOT_POSSIBLE` *(non-terminal, human-owned)*

| From | Trigger | Guard | → | Emits |
|---|---|---|---|---|
| — | `CorrectionInvalidatedAnEffect` | a **`VERIFIED`** effect is now known to be wrong | `REQUIRED` | `CompensationRequired{exposure}` |
| `REQUIRED` | `HumanApproved` | ### **money-affecting compensation is ALWAYS `HUMAN_REQUIRED`** | `APPROVED` | `CompensationApproved` |
| `REQUIRED` | `NoCompensatingActionExists` | *the world offers no undo* | **`NOT_POSSIBLE`** | `CompensationImpossible{exposure}` |
| `APPROVED` | `PipelineStarted` | ### **its OWN Pipeline Instance — fully gated (§3.2)** | `EXECUTING` | `CompensationStarted` |
| `EXECUTING` | `PipelineClosed` | compensating effect **verified by readback** | `COMPLETED` | `CompensationCompleted` |
| `EXECUTING` | `PipelineFailed` \| `NEEDS_VERIFICATION` | — | **`COMPENSATION_FAILED`** | `CompensationFailed{exposure}` |
| **`COMPENSATION_FAILED`** \| **`NOT_POSSIBLE`** | `HumanEstablishedReality` | **`decision_ref`** | `COMPLETED` | `RealityEstablished` |
| **`COMPENSATION_FAILED`** | *(any timer)* | — | ⛔ **ILLEGAL** | `IllegalTransitionAttempted` |

| Property | Ruling |
|---|---|
| **Owner** | **A human, from `REQUIRED`.** |
| **Terminal** | `COMPLETED` **only.** |
| **THE RULE** | ### **A compensation is an EFFECT. It passes through the full pipeline — checkpoint, grant, approval, readback. There is no fast path for undo.** *(An "undo" that bypasses the gates is just an ungated write with a good excuse.)* |
| **`COMPENSATION_FAILED`** | **Non-terminal. Never auto-resolves. Entity frozen. Dollar exposure stated. A human owns it.** *Reality and the projection are known to diverge — that is the most dangerous state the system can be in, and it must be loud.* |
| **`NOT_POSSIBLE`** | **Some things cannot be undone.** A sent email, a wire. **The system must say so honestly and escalate — not pretend it compensated.** |
| **Expiry** | **NEVER.** |
| **Retry** | A failed compensation is **not auto-retried.** A human decides. |

---

## 4. CONSEQUENCES

1. **I10 becomes a database guarantee**, not a slogan.
2. **Idempotency becomes a mechanism** (the inbox), not an instruction.
3. **§12 becomes implementable.** Two engineers now produce the same system.
4. **Crash recovery is defined, testable, and never guesses.**
5. **Stream B's defects become structurally unrepresentable** — `OWNER_ASSERTED` + recompute is an illegal transition (§3.6); a permanent auth failure cannot be retried (§2.10).
6. **Cost:** more tables, more transactions, more machinery. **Accepted — this *is* the reliability.**
7. **Constraint:** **no lifecycle may be implemented ad hoc.** All use §2.3.

---

## 5. TESTING REQUIREMENTS *(merge-gating)*

- **Crash matrix** — crash at every stage of §3.2; assert the resumed state; assert **no effect is ever double-executed**.
- **Dual-write** — kill between effect and event persistence; assert the outbox guarantees the event exists.
- **Duplicate delivery** — same event twice ⇒ inbox makes it a **no-op**.
- **Duplicate observation** — same email twice ⇒ **one** Observation, **one** `ObservationConfirmed`, **zero** duplicate work items.
- **Illegal transition** — attempt **every** illegal `(state, event)` pair; assert it raises, persists nothing, emits the security event.
- ### **Owner-binding protection (L-A)** — assert `RecomputedByInferrer` against an **`OWNER_ASSERTED`** claim is an **ILLEGAL TRANSITION**. *This is the B3 regression test.*
- ### **Conflict blocks money** — an open Conflict on a material field ⇒ **every consequential action on that entity is refused.**
- **Exception closure** — closure without a `decision_ref` ⇒ **illegal transition**.
- **Expectation blindness (F-14)** — deadline passes while the channel is **down** ⇒ **`INDETERMINATE`, never `OVERDUE`.**
- **Retry classification (L-D)** — an auth failure ⇒ **Exception immediately**, **zero retries**.
- **Upcaster** — rebuild from the **full historical corpus** across ≥1 schema version change.
- **Dangling reference** — child before parent ⇒ parked, drained in order; TTL expiry ⇒ Exception.
- **Replay** — replay the full corpus ⇒ **zero Effect Grants minted** (ADR-004).
- **No auto-resolve** — assert **no timer** can move `NEEDS_VERIFICATION`, `COMPENSATION_FAILED`, or an open `Conflict`.

---

## 6. MIGRATION IMPLICATIONS

- The existing **`WorkflowStore`** (`workflow_runs`, `audit_events`) is the **ancestor** of this machinery: it already has explicit states, an allowed-transition table, and an audit log. **The discipline is right; the shape is document-shaped.** **Generalize it — do not discard it.**
- **`enter_approved_payable`** is the **ancestor of the Pipeline Instance** (audit **R-03**). **It is the spine, not the mock.**
- **No historical domain state exists to migrate.** The projection is built **forward from observation**. Existing run/audit rows are **retained as evidence**, never converted into domain state.

---

## 7. REMAINING `NEEDS VALIDATION`

| # | Question | Nature |
|---|---|---|
| **V1** | **May a written-off load be re-billed when a POD surfaces in month 4?** And the equivalents for short-pay, TONU, and post-close carrier disputes. | **Freight policy, not technical.** The **generic reopening machinery (§2.14) is built regardless**; only the *when* is open. |
| **V2** | **Durable timer granularity**, and DST/timezone handling for freight deadlines (F-25). | Implementation. |
| **V3** | **Exception ageing/escalation thresholds** per lane. | Product/policy. |

**None of these block implementation of the machinery.** They block only the **domain** lifecycles that sit on it.
