# ADR-008 — Durable Workflows, State Machines, Outbox & Inbox

**Status:** DRAFT for approval.
**Resolves:** Correction-plan **Group E** — **F-06** (CRITICAL), **F-13**, **F-19**, **F-21**, **F-29**, **F-30**, **F-34**, and the durable-state half of **F-33**.
**Paired with:** ADR-004 (the effect boundary rides on these machines).
**Numbering note:** ADR-005 (approval binding), ADR-006 (verification modes), ADR-007 (identity/claims) are **reserved** per the correction plan; they are Wave 2/3.

---

## 1. CONTEXT

The Target Specification §12 lists the *requirements* of a lifecycle and the *entities that need one* — and then defines **not a single state, transition, guard, terminal state, reopening rule, cancellation rule, timeout, or compensation path** (F-19). **Two engineers implementing from §12 would produce two incompatible systems, and neither would be wrong according to the text.**

Simultaneously, §19 describes the Action Pipeline as a **sequence of stages** (`execute → verify → record → project`) with **no transactional or outbox mechanism** (F-06). This is the textbook dual-write problem, walked into while asserting **I10** (*no action both taken and unrecorded*).

**Concrete failure:** the pipeline writes an invoice to the TMS, verifies it, and the process is killed before the event is persisted. **The invoice exists. Neyma has no record it ever acted.** I2, I3, and I10 fail at once — and a retry could bill it again.

---

## 2. DECISION

### 2.1 The Action Pipeline is a **durable state machine**, not a function call

**Every stage transition is durably checkpointed before the next stage begins.** A crash at any point leaves a **resumable, inspectable instance** — never a void.

### 2.2 The canonical Durable Machine — the minimum machinery **every** lifecycle uses

Every stateful entity in the system is a **Durable Machine** with exactly this shape. **No lifecycle invents its own machinery.**

| Element | Requirement |
|---|---|
| **Identity** | `machine_id`, **`tenant_id` (always, first)**, `type` |
| **State** | A value from an **enumerated set**. `unknown` is a legal state where the domain admits it (**I7**). |
| **Version** | Monotonic. Used for **optimistic concurrency** (ADR-009) and to detect lost updates. |
| **Transition table** | **Declarative data**, not code branches. `(state, event_type) → (next_state, guard, emitted_events)`. |
| **Guards** | Predicates over **evidence and state** (§9). Deterministic. **Never model-evaluated** (P2). |
| **Terminal states** | Explicitly enumerated. |
| **Closure** | **Closure is an emitted event, never an inference** (I11). A machine is closed because something closed it — **not because nothing happened lately.** |
| **Cancellation** | Every machine defines whether it is cancellable, from which states, and what it emits. |
| **Timeout** | Expressed as a **durable timer** that emits a `TimerFired` event. **A timeout is an event, not a background sweep.** |
| **Failure states** | Explicit. A machine may fail; it may not vanish. |
| **Compensation states** | Where an effect may need undoing. |
| **Ownership** | Machines that represent *work* carry an **accountable human owner at all times** (**I1**). |

### 2.3 Illegal-transition enforcement (F-30, P10)
An event that is not in the transition table for the current state is an **illegal transition**. It:
1. **Raises**, and
2. **Does not persist any state change**, and
3. **Emits `IllegalTransitionAttempted`** — an audit **and security** event.

> **An illegal transition is a hard error, not a warning.** *(A silently-ignored illegal transition is how state machines rot into `if` statements.)*

### 2.4 Transactional persistence — the outbox (F-06)

> **The state transition and the events it emits are written in ONE atomic commit.**

- **One transaction:** `UPDATE machine_state (version++)` **+** `INSERT emitted events into the outbox`. Both, or neither.
- **A separate relay** reads the outbox and publishes to the backbone, marking rows published. **Publication is at-least-once and is retried.**
- **Consequence:** it is **impossible** for a state transition to occur without its event, or for an event to exist without its transition. **I10 becomes a database guarantee.**
- **The Effect Grant Ledger (ADR-004) lives in this same transactional store**, so minting/claiming a grant and recording the attempt are **atomic with the pipeline's state.**

### 2.5 Consumer inbox and de-duplication (F-06, F-13)
- Every consumer has an **inbox**: `(consumer_id, event_id)` unique.
- **Processing the event and inserting the inbox row happen in ONE transaction.** A duplicate delivery finds the row present and is a **no-op**.
- **This is *how* "consumers MUST be idempotent" is achieved.** Currently it is only an instruction; instructions are not mechanisms.

### 2.6 Observation identity (F-13)
- Every Observation carries a **natural key**: `(source_system, external_id, content_digest)`.
- **Ingestion is an idempotent upsert on that key.**
- **Re-observation of an unchanged fact is a *confirmation*, not a new fact.** It updates `as_of` (freshness, §6.5) and emits `ObservationConfirmed` — **it does not create a second Observation**, and it must not re-trigger downstream work.
- **This is the mechanism that makes "the same email delivered twice" a no-op** rather than a duplicate expectation discharge and a duplicate work item.

### 2.7 Event schema versioning and upcasting (F-21)
- Every event carries `type` **and `version`**.
- **Within a version: additive-only.** A breaking change requires a **new version** plus a registered **upcaster** `vN → vN+1`.
- **Readers apply upcasters on read.** Old events are never rewritten. *(History is not mutated to make the present tidy — §2.2.)*
- **The rebuild test (ADR-001 C2) runs against the FULL historical corpus, not a recent window.** Otherwise it passes for eighteen months and is then permanently red — and gets disabled, which is worse than never having had it.

### 2.8 Dangling references — parking (F-34)
An event referencing a machine that does not yet exist is **neither dropped nor failed**:
1. It is **parked** in a `pending_references` table keyed by the referenced id, with an arrival sequence and a **TTL**.
2. On creation of the referenced machine, parked events are **drained in arrival order**.
3. **TTL expiry ⇒ an Exception** with an accountable owner. *(A permanently dangling reference is a real problem, and it gets a human — not a log line.)*

### 2.9 Crash recovery
On startup, a **recovery pass** scans machines in **non-terminal transient states**:
- Pipeline instances in a pre-effect stage ⇒ **re-run the checkpoint from the beginning.** Nothing happened.
- Pipeline instances in `CLAIMED` / `EXECUTING` ⇒ ⚠️ **UNKNOWN OUTCOME.** **Never re-execute.** Resolve by **verification** (ADR-006). If unresolvable ⇒ **`NEEDS_VERIFICATION`**, human-owned, entity frozen (F-33).
- **Recovery never guesses.** It **re-derives** or it **escalates.**

### 2.10 Side-effect-free replay
Replay reconstructs state by applying events through the transition tables. **It cannot cause an effect** — not by discipline, but because **replay cannot construct a `CheckpointPassed` and therefore cannot mint an Effect Grant** (ADR-004 §2.5). *The guarantee is a consequence of the capability model.*

### 2.11 Command / intent representation (F-29) — **resolved by removal**
> **There is NO separate Command entity.**

- **Business intent** is represented by the **Work Item** (*"we intend to bill this load"*).
- **One attempt to effect that intent** is represented by a **durable Pipeline Instance**.
- **The Pipeline Instance IS the command** — durable, idempotent, inspectable, replayable.
- **Events remain facts.** The **Event-is-not-a-Command** rule stands. The *Command* language in §11.1 is **deleted** as a distinct entity.

**Rationale:** fewer concepts (**P36**). The ambiguity in §11.1 was guaranteeing divergent implementations; the cheapest fix is to remove the ambiguity, not to specify a third thing.

### 2.12 Exception closure requires a decision reference (F-30)
The **Exception** machine's terminal transition **requires a `decision_ref`** — either a **human decision id** or a **deterministic rule id**.
**A closure event without one is an ILLEGAL TRANSITION** (§2.3).

> This is the mechanism that makes the Operating Model's rule real: *"an exception closed without a decision is not closed — it is forgotten."*

### 2.13 Terminal handling for the two states that must never auto-resolve

| State | Rule |
|---|---|
| **`NEEDS_VERIFICATION`** (F-33) | **Non-terminal. Human-owned.** The commit key **stays reserved**. The entity is **frozen** for consequential actions. **It MUST NOT time out into success or into failure.** Resolved only by verification or by a human establishing reality. |
| **`COMPENSATION_FAILED`** (F-17, scenario 24) | **Non-terminal. Human-owned.** Reality and the projection are known to diverge. The entity stays **frozen**, the **dollar exposure is stated**, and it is escalated. **It never auto-resolves.** |

> **Both are deliberately uncomfortable. Any timeout here is a decision to guess about money.**

---

## 3. STATE MACHINES THAT MUST BE WRITTEN INTO THE REVISED SPECIFICATION

**The complete transition tables belong in the specification, not this ADR.** What follows is the **mandatory state set and transition categories** each must expand into.

### 3.1 Action Pipeline Instance
**States:** `PROPOSED → POLICY_CHECKED → VALIDATED → AWAITING_APPROVAL → CHECKPOINT → GRANTED → CLAIMED → EXECUTED → VERIFIED → RECORDED → PROJECTED → CLOSED` · plus `REJECTED`, `VOIDED`, `FAILED`, **`NEEDS_VERIFICATION`**
**Transition categories:** advance · reject (policy/validation) · void (approval drift, brake, expiry) · **unknown-outcome** · fail · resume-after-crash · close.

### 3.2 Approval *(detail in ADR-005)*
**States:** `REQUESTED → GRANTED → CONSUMED` · plus `VOID_ON_DRIFT`, `EXPIRED`, `REVOKED`, `VOID_ON_BRAKE`
**Transition categories:** grant · consume-on-commit · **void** (drift / expiry / revocation / brake) · **survive-failed-attempt**.

### 3.3 Work Item
**States:** `OPEN → IN_PROGRESS → BLOCKED → AWAITING_HUMAN → CLOSED` · plus `CANCELLED`, `ESCALATED`
**Transition categories:** create (**with a default owner — I1**) · **ownership transfer** · block/unblock · escalate · **close (requires a closure event — I11)** · cancel · reopen.

### 3.4 Expectation *(Group G)*
**States:** `RAISED → DISCHARGED` · `OVERDUE` · **`INDETERMINATE`** · `CANCELLED` · `EXPIRED`
**Transition categories:** discharge-by-observation · **overdue (ONLY with demonstrated observability — F-14)** · **indeterminate (we were blind)** · cancel (reason disappeared) · **re-version on deadline change** · expire.

### 3.5 Identity Binding Claim *(ADR-007)*
**States:** `PROPOSED → CONFIRMED` · `AMBIGUOUS` · `REJECTED` · `SUPERSEDED` · `CORRECTED` · `CONFLICTING`
**Transition categories:** deterministic confirmation · escalate-on-ambiguity · **correct (with propagation — F-17)** · supersede (deterministic rule or human **only**) · raise-conflict.

### 3.6 Conflict
**States:** `RAISED → RESOLVED_BY_RULE` | `RESOLVED_BY_HUMAN` · `OPEN` · `ESCALATED`
**Transition categories:** raise (system-vs-system, **claim-vs-claim**, claim-vs-observation) · deterministic resolution · human resolution.
**Invariant:** **while OPEN, the affected field is `conflicting` and BLOCKS consequential actions** (ADR-002 C6).

### 3.7 Exception
**States:** `OPEN → ACKNOWLEDGED → RESOLVED` · `ESCALATED` · `AGEING`
**Transition categories:** raise · acknowledge · **resolve (REQUIRES `decision_ref` — §2.12)** · escalate · age.

### 3.8 Compensation
**States:** `REQUIRED → APPROVED → EXECUTING → COMPLETED` · **`COMPENSATION_FAILED`**
**Transition categories:** raise (from a correction that invalidated a completed effect) · gate (**it is an effect — full pipeline**) · execute · **fail terminally into a human-owned, entity-freezing state (§2.13)**.

### 3.9 External Effect
**States:** `GRANTED → CLAIMED → ATTEMPTED → VERIFIED` · **`UNKNOWN_OUTCOME`** · `FAILED` · `EXPIRED_UNCLAIMED`
**Transition categories:** claim (atomic CAS) · attempt · verify (**per the verification taxonomy — ADR-006**) · **unknown** · fail · expire.

### 3.10 Observation
**States:** `RECEIVED → PARSED → BOUND` · `UNBOUND` · `SUPERSEDED` · `CONFIRMED`
**Transition categories:** ingest (**idempotent on the natural key — §2.6**) · parse · bind (via §3.5) · **confirm (re-observation — NOT a new fact)** · supersede.

### 3.11 Quote
**States:** `REQUESTED → PRICED → SENT → ACCEPTED` | `DECLINED` | `EXPIRED`
**Transition categories:** receive · price (**the sell rate is HUMAN — Operating Model §6**) · send (**gated outbound**) · outcome · expire.

### 3.12 Brokerage Load *(`PROVISIONAL — FORK A`)*
**States:** `TENDERED → COVERED → DISPATCHED → IN_TRANSIT → DELIVERED → DOCUMENTED → BILLED → PAID` · `CANCELLED` · `TONU`
**Transition categories:** advance · cancel · **reopen (a POD surfaces after write-off — `NEEDS VALIDATION`, B5/B6)** · exception-branch.

### 3.13 Carrier Movement *(`PROVISIONAL — FORK A`)*
**States:** `OFFERED → BOOKED → CONFIRMED → PICKED_UP → DELIVERED → INVOICED → SETTLED` · `FELL_OFF` · `CANCELLED`
**Transition categories:** offer/counter · book (**gated — carrier trust is HUMAN**) · confirm · execute · settle · fall-off.

### 3.14 Document
**States:** `EXPECTED → RECEIVED → EXTRACTED → BOUND → FILED` · `ILLEGIBLE` · `REJECTED` · `SUPERSEDED`
**Transition categories:** expect (creates an **Expectation** — §3.4) · receive · extract · bind (§3.5) · file (**an effect — full pipeline**) · escalate-on-illegible.

### 3.15 Customer Invoice
**States:** `ELIGIBLE → PREPARED → APPROVED → ISSUED → SENT → PAID` · `SHORT_PAID` · `DISPUTED` · `VOIDED` · `CREDITED`
**Transition categories:** eligibility (**POD-gated**) · prepare · **approve (HUMAN)** · issue (**effect**) · payment · short-pay/dispute branch · **void/credit (compensation — §3.8)**.
**Note:** the loop **closes at `PAID`**, not at `ISSUED` (Operating Model L8, P24).

### 3.16 Carrier Payable
**States:** `INVOICE_RECEIVED → RECONCILED → APPROVED → RECORDED → PAID` · `DISPUTED` · `HELD` · `SHORT_PAID` · `DUPLICATE_SUPPRESSED`
**Transition categories:** receive · **reconcile (deterministic; an accessorial with only a model-asserted authorization is `unconfirmed` and BLOCKS — ADR-003)** · **approve (HUMAN — money out)** · record (**effect**) · dispute/hold · **suppress duplicate**.

---

## 4. CONSEQUENCES

1. **I10 becomes a database guarantee**, not a slogan.
2. **Idempotency becomes a mechanism** (the inbox), not an instruction.
3. **§12 becomes implementable.** Two engineers now produce the same system.
4. **Crash recovery is defined, testable, and never guesses.**
5. **Cost:** more tables, more transactions, more machinery. **Accepted** — this *is* the reliability.
6. **Constraint:** no lifecycle may be implemented ad hoc. **All use the canonical machinery (§2.2).**

---

## 5. TESTING REQUIREMENTS

- **Crash matrix**: crash injected at every stage of the Pipeline Instance; assert the correct resumed state and that **no effect is ever double-executed**.
- **Dual-write test**: kill the process between effect and event persistence; assert the outbox guarantees the event exists.
- **Duplicate-delivery test**: deliver the same event twice; assert the inbox makes it a no-op.
- **Duplicate-observation test**: ingest the same email twice; assert **one** Observation, **one** confirmation, **no** duplicate work.
- **Illegal-transition test**: attempt every illegal `(state, event)` pair; assert it raises, persists nothing, and emits the security event.
- **Exception-closure test**: attempt closure without a `decision_ref`; assert **illegal transition**.
- **Upcaster test**: rebuild from the **full historical corpus** across at least one schema version change.
- **Dangling-reference test**: deliver a child event before its parent; assert parking, then draining in order; assert TTL expiry raises an Exception.
- **Replay test**: replay the full corpus; assert **zero** Effect Grants minted (ADR-004).

---

## 6. MIGRATION IMPLICATIONS

- The existing `WorkflowStore` (`workflow_runs`, `audit_events`) is the **ancestor** of this machinery: it already has explicit states, an allowed-transition table, and an audit log. **The discipline is right; the shape is document-shaped** (Reconciliation §1.1 A). **Generalize it — do not discard it.**
- The existing `enter_approved_payable` gated driver (audit R-03) is the **ancestor of the Pipeline Instance**. **It is the spine, not the mock.**
- **No historical domain state exists to migrate** — the projection is built **forward from observation** (Target Spec §30.6). Existing run/audit rows are **retained as evidence**, not converted into domain state.

---

## 7. OPEN QUESTIONS

| # | Question | Blocks |
|---|---|---|
| **Q1** | **One store or several?** The outbox demands that machine state + emitted events + the Effect Grant Ledger share a transaction. **Strong recommendation: one transactional store for all three** (P36). | ADR (data). Recommend: **yes, one.** |
| **Q2** | **Reopening rules** — can a written-off load be re-billed when a POD surfaces months later? | **`NEEDS VALIDATION` — B5/B6.** Domain question, not technical. |
| **Q3** | **Timer granularity** for durable timers (expectation deadlines, TTLs). | Implementation. Interacts with **F-25** (timezone/DST). |
| **Q4** | **Are Work Item and Pipeline Instance ever 1:N?** *(One intent, several attempts.)* **Recommendation: YES** — one Work Item may spawn several Pipeline Instances over time. | Must be settled before the tables are written. |
