# ADR-003 — Authorization Assertion Requires Human Confirmation

**Status:** ACCEPTED — explicit product decision by Rasheed, 2026-07-09.
**Origin:** Architecture review finding **F-05** (CRITICAL).
**Classification:** **PERMANENT PRODUCT TRUTH.** Amends `operating-model.md` §7.5 (truths), **not** §7.6 (policy).
**Cannot be graduated away** by autonomy, confidence, historical performance, or configuration.

---

## 1. CONTEXT

The Operating Model's deepest domain finding is that **the commitment precedes the document** (§3.3, P31): a rate is agreed on the phone before the rate confirmation exists; **detention is authorized verbally at the dock**; a delay is excused in a text. The architecture was therefore required to be able to represent **an authorization that has no artifact** — because a system that can only represent what is written down *"will confidently accuse honest people."*

The Target System Specification implemented this by modelling an **Accessorial Authorization** as a **Claim** (§8.3) — native, inferred state, which a model could produce from a call transcript or an email thread.

**The adversarial review (F-05) found that this converts the architecture's greatest strength into its most dangerous vulnerability.**

> A carrier emails: *"Per our call, you agreed to the $300 detention."*
> The extraction model creates an Authorization claim at 0.81 confidence.
> The reconciler now sees the detention line as **authorized**. The invoice reconciles clean. It flows to a routine, graduated payable and is paid.
> **The call never happened.**

The system was socially engineered into paying — **through the safety spine, not around it.** Every guardrail behaved exactly as specified.

**Root error:** *"The commitment precedes the document"* was implemented as *"the model may assert that a commitment occurred."* **Those are not the same statement, and the difference is money.**

---

## 2. DECISION

**Where an authorization is not already confirmed by an authoritative structured record, only an authorized human may assert that the authorization exists.**

### 2.1 What a model MAY do
- Detect language suggesting an authorization.
- Identify the amount and the charge type.
- Retrieve the supporting communications.
- Assemble a timeline.
- **Surface a candidate authorization.**
- **Recommend that a human review it.**

*(All of this is legitimate, valuable, and encouraged. The model does the work; it does not make the assertion.)*

### 2.2 What a model MAY NEVER do
- Create an authoritative accessorial authorization by itself.
- **Promote a counterparty's assertion into a confirmed authorization.**
- Allow an inferred verbal agreement to satisfy a financial guardrail.
- Authorize payment on the basis of **confidence, similarity, or model interpretation**.

### 2.3 Requirements of a human assertion
A human-asserted authorization MUST be:

| Requirement | Meaning |
|---|---|
| **Explicit** | An affirmative act. Never inferred from silence or from approving something adjacent. |
| **Attributed** | To the specific human actor, with their role and authority (§7.3). |
| **Scoped** | Tied to the specific **load, charge type, amount, counterparty, and time period**. |
| **Evidenced** | Records the evidence the human reviewed when asserting it. |
| **Versioned** | Supersession creates a new version; it never mutates the old. |
| **Correctable** | With a full correction history. |
| **Auditable** | Reconstructable at any future date (I3, I6). |
| **Fingerprinted** | **Included in the material-facts fingerprint of any approval that depends on it** (review Group B). |

### 2.4 Counterparty assertions are a fraud signal
A statement such as *"per our call, you approved this detention"* is an **unverified counterparty claim.** It is **evidence that a claim was made** — nothing more.

It MUST be treated as a **fraud signal** (Freight Discovery §12: *identity theft and invoice fraud are active and escalating; fraud is not an edge case*) and routed to a human. **It is not authorization, and it never becomes authorization by repetition, confidence, or the passage of time.**

---

## 3. CONSEQUENCES

| # | Consequence |
|---|---|
| **1** | **An Authorization claim carries an `asserting_actor`.** A **model-asserted** authorization has **zero authority** to gate money — permanently. It exists only as a *candidate*, and it is visibly labelled as such. |
| **2** | **Authorization assertion is a structurally ungatable-away action class.** The Action Pipeline refuses to accept a human-asserted authorization without a human approval id, **enforced in code, not configuration** (review F-20). |
| **3** | The **inferred-authorization path becomes an escalation path**, not an execution path. The model's job is to make the human's review **cost seconds instead of minutes** — assembling the timeline, the amount, the communications, and the counterparty history. *That is Assist, not Execute* (Operating Model §6). |
| **4** | **The reconciliation engine may not treat a model-asserted authorization as satisfying an accessorial line.** An accessorial with only a model-asserted authorization is `unconfirmed` → **blocks the payable** (ADR-002 C6). |
| **5** | This raises the value of open question **B6** — *how does the partner actually authorize accessorials in the moment, and where is it recorded?* If a **structured record** exists (a TMS note, a logged approval), authorizations can be **projected** rather than asserted, and the human burden collapses. **B6 is now the highest-value field question we have.** |

---

## 4. WHAT THIS DOES NOT SAY

- It does **not** say verbal authorizations are invalid. **They are real, and the system must represent them** (P31).
- It does **not** say a human must re-key data. The model assembles everything; **the human performs one attributed act of assertion.**
- It does **not** forbid automation of accessorials **that are confirmed by an authoritative structured record** — those are projected state (ADR-001) and follow the normal path.

**The rule is narrow and absolute: an *undocumented* authorization becomes real only when a human says it is real.**

---

## 5. ALTERNATIVES REJECTED

- **Confidence threshold** (auto-accept above 0.9). Rejected: **confidence may route, never authorize** (P4). A confident model reading a fraudulent email is a confident fraud.
- **Graduation** (earn the right to auto-accept after N correct inferences). Rejected: this is precisely the **erosion** the Operating Model §7.6 names. And the adversary adapts to exactly the behaviour we have graduated.
- **Counterparty corroboration** (accept if the carrier says it twice). Rejected: the counterparty is the interested party. **Repetition by the beneficiary is not evidence.**
