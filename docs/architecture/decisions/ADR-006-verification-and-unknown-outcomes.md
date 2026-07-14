# ADR-006 — Verification, Unknown Outcomes & Effect Verification

**Status:** ✅ **FINAL — Wave 2.**
**Baseline:** `f0e801b4dfd611345ca6c2842e946d58a7512ae5`
**Resolves:** correction-plan **Group C** — **F-03**, **F-11**, **F-33**.
**Consumed by:** ADR-004 §3.9 (unknown-outcome semantics), ADR-008 §3.3 (the External Effect lifecycle).
**Constrained by (frozen):** ADR-001 (C4, C5), ADR-002, ADR-004, ADR-008, Operating Model **I7/I8/I10**.

---

## 1. CONTEXT

ADR-004 names **`NEEDS_VERIFICATION`** and rules that it must never auto-resolve. ADR-008 gives the External Effect the states `ATTEMPTED → VERIFIED | UNKNOWN_OUTCOME | FAILED`.

**Neither says how to decide which one you are in.** That decision is this ADR.

## 2. PROBLEM STATEMENT

**The system reads a page back and does not find the invoice. What does that mean?**

It means one of at least five different things:

1. The invoice was never created. *(Verified failure.)*
2. The invoice was created, but the page has not refreshed. *(Deferred.)*
3. The invoice was created, but we were logged out and read an error page that renders like an empty list. *(Blind.)*
4. The invoice was created under a different number than we searched for. *(Conflicting.)*
5. We genuinely cannot tell. *(Unknown.)*

> ### **Four of those five are not failure. A system that collapses them into "failed" and retries will bill the customer twice.**

**F-03/F-11:** the specification had one notion of "verified" and no vocabulary for the rest. **F-33:** it had no answer at all for *"what if the verification channel is also down?"* — and a system that cannot verify **and cannot admit it** will eventually **report `DONE` for an effect that never happened**, which is exactly R-01 with better manners.

**I8 is the governing invariant: *missing evidence and contradictory evidence are different states.*** This ADR is I8 applied to effects.

---

## 3. DECISION

### 3.1 The rule

> ## **An unknown outcome MUST NEVER silently become a success or a failure.**
> ## **`FAILED` requires POSITIVE PROOF that nothing happened. Absence of a success signal is NOT proof of failure.**

**And its corollary, which is the one that gets forgotten:**

> ### **Proof of absence requires a HEALTHY channel.**
> **"The record is not there" is only meaningful if we can show we would have seen it had it been there.** Otherwise we were **blind**, and blindness is not evidence.

### 3.2 `VerificationOutcome` — a value, not a new lifecycle

**No new state machine is introduced.** *(Wave 2 is completion, not expansion.)* `VerificationOutcome` is a **typed value** produced by the verifier and **consumed as the trigger** for the existing External Effect transitions in ADR-008 §3.3.

**Eight outcomes. They are exhaustive and mutually exclusive.**

| # | `VerificationOutcome` | Means | Proof required to assert it |
|---|---|---|---|
| **1** | **`VERIFIED_SUCCESS`** | The effect exists in the authoritative system **AND matches the approved material facts** | A **live, healthy** read returning a record whose material facts equal the approved fingerprint (ADR-005) |
| **2** | **`VERIFIED_FAILURE`** | The effect **provably does not exist** | A **live, healthy** read of a source that **would have shown it**, returning nothing — **plus a positive health signal** (§3.4) |
| **3** | **`UNKNOWN_OUTCOME`** | We cannot establish either, and have exhausted what we can do | *(This is the honest default. It requires no proof — it is what remains.)* |
| **4** | **`VERIFICATION_DEFERRED`** | The effect is real; the authoritative system **will not reflect it yet** (batch posting, overnight settlement, async queue) | The adapter **declares in advance** that this operation posts asynchronously, **with a bound** on when |
| **5** | **`VERIFICATION_IMPOSSIBLE`** | The external system offers **no readback at all**, ever | **Declared per adapter, per operation, up front** — never discovered at runtime (§3.6) |
| **6** | **`AWAITING_OBSERVATION`** | Verification depends on an **inbound** observation that has not arrived (a remittance, a confirmation email) | An **Expectation** is raised (ADR-008 §3.8) with a deadline |
| **7** | **`OBSERVATION_UNAVAILABLE`** | ### **We were blind.** The read channel was down, logged out, rate-limited, or rendering an error | A **negative health signal** — we know we could not see |
| **8** | **`OBSERVATION_CONFLICTING`** | Two authoritative reads disagree, **or** the readback **contradicts the approved facts** | Two observations that cannot both be true |

> ### **The load-bearing distinction is #2 vs #7.**
> **`VERIFIED_FAILURE` and `OBSERVATION_UNAVAILABLE` look identical at the call site — both are "I didn't find it."**
> **One means retry. The other means STOP.** Collapsing them is the single most expensive mistake available in this system, and it is the mistake the code makes by default unless the channel health is checked explicitly.

### 3.3 Mapping to ADR-008 §3.3 — no new states

| `VerificationOutcome` | External Effect → | Pipeline Instance → | Entity frozen? | Human? |
|---|---|---|---|---|
| `VERIFIED_SUCCESS` | **`VERIFIED`** | `VERIFIED → RECORDED → PROJECTED → CLOSED` | no | no |
| `VERIFIED_FAILURE` | **`FAILED`** | `FAILED` | no | no *(a clean failure is safe to retry — §3.7)* |
| `VERIFICATION_DEFERRED` | stays **`ATTEMPTED`** *(non-terminal)* + durable timer | stays in-flight | **yes** | not yet |
| `AWAITING_OBSERVATION` | stays **`ATTEMPTED`** + an **Expectation** | stays in-flight | **yes** | on `OVERDUE`/`INDETERMINATE` |
| `UNKNOWN_OUTCOME` | **`UNKNOWN_OUTCOME`** | **`NEEDS_VERIFICATION`** | **yes** | ### **YES** |
| `OBSERVATION_UNAVAILABLE` | **`UNKNOWN_OUTCOME`** | **`NEEDS_VERIFICATION`** | **yes** | ### **YES** |
| `OBSERVATION_CONFLICTING` | **`UNKNOWN_OUTCOME`** + raises a **Conflict** (ADR-007) | **`NEEDS_VERIFICATION`** | **yes** | ### **YES** |
| `VERIFICATION_IMPOSSIBLE` | **`ATTEMPTED`** → recorded as *transmitted, not confirmed* (§3.6) | `CLOSED` **with an honest label** | no | at proposal time |

**Every one of the eight is expressible in ADR-008's existing state set. No amendment to ADR-008 is required.**

### 3.3.1 Name collision, resolved — the `unknown_reason` field

> **Note the overload:** `UNKNOWN_OUTCOME` is **both** a `VerificationOutcome` (#3) **and** the External Effect state (ADR-008 §3.3) — **and three different outcomes (#3, #7, #8) all land in that one state.**

**Left alone, that would destroy the very distinction this ADR exists to draw.** *"I was blind"*, *"the readback contradicted the approval"*, and *"I tried everything and still cannot tell"* are three different situations demanding three different human questions — and they would arrive at the owner as one indistinguishable state.

**Resolution — no new state, one mandatory field:**

> ### **The `UNKNOWN_OUTCOME` state MUST carry `unknown_reason: VerificationOutcome`.**
> **A transition into `UNKNOWN_OUTCOME` without an `unknown_reason` is an ILLEGAL TRANSITION** (ADR-008 §2.4).

| `unknown_reason` | The question we ask the human |
|---|---|
| `UNKNOWN_OUTCOME` | *"I don't know if this happened. Please look."* |
| `OBSERVATION_UNAVAILABLE` | *"I couldn't see — I was logged out. Please look, and please re-authenticate the session."* |
| `OBSERVATION_CONFLICTING` | *"I found something, but **it isn't what you approved**. Please look at this immediately."* ⚠️ *(This one may mean someone or something else acted — it is the R-02 signature.)* |

**The state is the same because the *consequences* are identical — freeze, escalate, never retry, never auto-resolve. The reason is retained because the *conversation* is not.**

### 3.4 Channel health — the mechanism that makes `VERIFIED_FAILURE` assertable

**A verifier may NOT return `VERIFIED_FAILURE` unless it holds a positive health signal for the channel it read.**

A **health signal** is a **positive control** — evidence that the read was capable of seeing the thing:

| Channel | Positive control |
|---|---|
| TMS invoice list (browser) | **A known-present sentinel row is visible** — e.g. an unrelated invoice we know exists, or the table header + a non-zero row count for a period we know is non-empty. **"The page loaded" is NOT a health signal — a logged-out page also loads.** |
| TMS record page | An HTTP 200 **plus** an authenticated-session marker **plus** the expected page structure. |
| Email/IMAP | A successful `SELECT` returning a mailbox with a plausible message count. |
| Any API | A 2xx on a known-good probe within the same session. |

> **This is the "real signal, not a proxy" principle, made mandatory.** The live-hardened browser agent already learned this the hard way: **an unrendered page and an empty result set are indistinguishable to a naive reader**, and the naive reader concludes "nothing owed."

**No health signal ⇒ `OBSERVATION_UNAVAILABLE`. Never `VERIFIED_FAILURE`.**

### 3.5 The readback must compare against **the approved facts**, not merely "a record exists"

**`VERIFIED_SUCCESS` requires the readback to match the approved material fingerprint (ADR-005).**

Finding *an* invoice on load 4471 is **not** verification. Finding an invoice on load 4471 **for £3,100 when £2,850 was approved** is not success — **it is `OBSERVATION_CONFLICTING`**, and it means something acted that we did not authorize, or we acted wrongly.

> **"A record is there" answers a question nobody asked. The question is: is the record *the one the human approved*?**

### 3.6 `VERIFICATION_IMPOSSIBLE` — declared, never discovered

Some effects cannot be read back **at all**: an email leaves; a fax leaves; a wire is submitted to a portal that shows nothing until settlement.

**Rules:**
1. **The adapter declares it, per operation, up front.** It is a **static property of the capability**, not a runtime surprise.
2. ### **An operation whose verification is `IMPOSSIBLE` may NOT be `AUTONOMOUS_WITHIN_CAPS`.** It is **`HUMAN_REQUIRED`** — and the human is told, on the card, *"I will not be able to confirm this."* **The human is the verification.**
3. **We record only what we can prove.** For an email: *the transmission was accepted by the relay (SMTP 250) at 14:02, and here is the exact byte-for-byte copy of what was sent.* ### **We NEVER record "delivered", "received", or "read".**
4. The projection stores the field as **`unknown`**, never as a success.

> **The honest sentence is *"I sent it; I cannot prove it arrived."* Any system that says "Sent ✅" and means "handed to a relay" is lying by omission — and the owner will find out on the day it matters.**

### 3.7 Retry policy

> ### **The VERIFICATION may be retried. The EFFECT may never be retried on an unknown outcome.**

| Situation | Retry the effect? | Retry the verification? |
|---|---|---|
| `VERIFIED_FAILURE` (**proven** clean failure) | ✅ **Yes** — a new Pipeline Instance, **same commit key**, **new grant**, **full checkpoint incl. drift** | n/a |
| `UNKNOWN_OUTCOME` / `OBSERVATION_UNAVAILABLE` / `OBSERVATION_CONFLICTING` | ### ❌ **NEVER** | ✅ Yes — bounded, with backoff |
| `VERIFICATION_DEFERRED` | ❌ | ✅ On the declared schedule, until the declared bound |
| `AWAITING_OBSERVATION` | ❌ | Driven by the **Expectation**, not by a retry loop |

**Verification retries are classified (Stream B lesson L-D, ADR-008 §2.10):**
- **TRANSIENT** (timeout, socket, throttle, browser busy) ⇒ bounded retry with backoff.
- **PERMANENT** (auth failure, page structure gone, capability removed) ⇒ ### **stop immediately, raise an Exception, escalate.** **Never retried.** *A permanent verification failure retried in a loop is a system hiding a fixable problem from the only person who can fix it.*

**Even for a proven `VERIFIED_FAILURE`, the effect retry is a *new pipeline* — never an in-place re-execution.** The commit key is unchanged, so **if the first attempt secretly committed after all, the database refuses the second claim** (ADR-004 §3.5). *The retry does not need to be trusted; the database is.*

### 3.8 Escalation and human intervention

**`NEEDS_VERIFICATION` is non-terminal, human-owned, and never expires.**

The escalation carries, mandatorily:
- **the dollar exposure** *(what could have happened, at what amount, to whom)*,
- what we attempted, and the exact time,
- **what we tried in order to verify, and why each attempt was inconclusive**,
- **what we have frozen as a result**,
- **the specific question we need the human to answer** — *"Please look at load 4471 in TruckingOffice. Is there an invoice for £2,850? Tell me yes or no."*

**Resolution:** `HumanEstablishedReality{decision_ref}` ⇒ `VERIFIED` or `FAILED`. **A later authoritative observation may also resolve it deterministically** (the invoice appears in the next AR read with our commit key) — that is `LaterObservationProves`, and it requires the **same evidence standard** as any verification.

> **No timer may move it. No inference may move it. No confidence score may move it. A human or a proof — nothing else.**

### 3.9 Projection behavior

- **The projection is updated ONLY on `VERIFIED_SUCCESS`** — **never optimistically** (ADR-002 §1.1: *projected state is never optimistically updated from an intended action*).
- On `UNKNOWN_OUTCOME`, the affected field becomes **`unknown`** — ### **not `absent`, and not the old value.** *(ADR-002 C5: five distinct conditions. Reverting to the old value would be a lie; marking it absent would be a worse one.)*
- The **entity is frozen** for consequential actions while any effect on it is `UNKNOWN_OUTCOME`.

### 3.10 User-visible behavior — honest health

| State | What Neyma says |
|---|---|
| `VERIFIED_SUCCESS` | *"Invoiced load 4471 — £2,850. Invoice #560010. I read it back and confirmed it."* |
| `VERIFIED_FAILURE` | *"I could not invoice load 4471 — the TMS rejected it (missing customer). Nothing was created. I have not retried."* |
| `VERIFICATION_IMPOSSIBLE` | *"I sent the reminder to accounts@acme.com at 14:02. **I cannot confirm it arrived.** Here is exactly what I sent."* |
| **`NEEDS_VERIFICATION`** | ### *"⚠️ I tried to record a £4,200 payable to Redline Carriers. **I do not know whether it went through.** I could not read the page back — I was logged out. **I have frozen this payable and I will not retry.** Please look in TruckingOffice: is there a payable for £4,200? Tell me and I'll finish."* |

> **The word `DONE` is reserved for `VERIFIED_SUCCESS`. It has no other use.** (Operating Model: *DONE only on readback*.)
> **Never a spinner. Never "processing". Never silence.** *An owner who is not told is an owner who assumes.*

### 3.11 Event emission

`VerificationAttempted{effect_id, method, channel_health}` · `EffectVerified{fingerprint_match}` · `EffectFailed{proof}` · `OutcomeUnknown{exposure, attempts}` · `VerificationConflict{expected, observed}` · `VerificationUnavailable{channel, health_signal}` · `VerificationDeferred{recheck_at}` · `RealityEstablished{decision_ref, outcome}`

**All emitted through the transactional outbox** (ADR-008 §2.5) — **the verification result and the state transition are one commit.** *(This is what closes the "verified but not recorded" window; ADR-004 §7 relies on it.)*

### 3.12 Compensation eligibility

| Outcome | May we compensate (undo)? |
|---|---|
| `VERIFIED_SUCCESS` (but wrong — e.g. a correction invalidated it) | ✅ **Yes** — raise a **Compensation** (ADR-008 §3.10), itself a fully gated effect |
| `VERIFIED_FAILURE` | n/a — nothing happened |
| ### `UNKNOWN_OUTCOME` | ### ❌ **NO. Compensation is FORBIDDEN.** |

> **You cannot undo something you cannot prove you did.** A compensating write against an unknown outcome can **create** the very state it was trying to remove — *"cancel the invoice" against a TMS where no invoice exists can, in some systems, create a credit note out of nothing.*
>
> **`UNKNOWN_OUTCOME` must be resolved to `VERIFIED` or `FAILED` FIRST — by a human or by proof. Only then may compensation be considered.** This ordering is not a preference; it is the difference between undoing an error and manufacturing one.

---

## 4. ALTERNATIVES REJECTED

| Alternative | Rejected because |
|---|---|
| **"Not found ⇒ failed ⇒ retry"** *(the naive default)* | **This is the double-billing machine.** It cannot distinguish "no record" from "no vision" (§3.2 #2 vs #7). |
| **Timeout `UNKNOWN` into `FAILED` after N minutes** | **A timeout here is a decision to guess about money**, dressed as an operational policy. The clock knows nothing about the TMS. |
| **Timeout `UNKNOWN` into `SUCCESS`** ("it probably worked") | Worse. It closes the work item and **stops anyone from looking**. |
| **A confidence score on the verification** | **Confidence is not evidence** (ADR-007 §5). A 0.94-confident verification of a £4,200 payable is an unverified payable with a decoration. |
| **Compensate automatically on unknown** | **Can create the state it meant to remove** (§3.12). |
| **A separate `Verification` state machine** | **Unnecessary.** All eight outcomes map onto ADR-008's existing External Effect states (§3.3). *Wave 2 is completion, not expansion.* |
| **Trust the adapter's return code** | An HTTP 200 from a TMS means the *request* succeeded. **It is a proxy, not a signal.** The money is in the record, not the response. |

---

## 5. CONSEQUENCES

1. **F-03/F-11/F-33 close.** Every outcome has a name, a proof standard, and a destination.
2. **`NEEDS_VERIFICATION` will occur in production, and it will be uncomfortable.** ### **That discomfort is the product working.** Every occurrence is a moment where the old system would have guessed about money.
3. **Some effects can never be verified** (§3.6) — and the system now says so **out loud, in advance**, rather than pretending.
4. **Cost:** every verification needs a **positive health control**, which is extra reads. **Accepted.** It is the only thing that makes `FAILED` mean anything.
5. **Retry becomes rare and deliberate**, instead of ambient.

---

## 6. FAILURE MODES

| Failure | Behaviour |
|---|---|
| Verification channel dead **and** the effect is unknown (**F-33**) | **`NEEDS_VERIFICATION` persists indefinitely.** Entity frozen. Human owns it. **No timeout, in either direction.** |
| The health control itself is wrong (a sentinel that is legitimately absent) | ⇒ **`OBSERVATION_UNAVAILABLE`** — i.e. it **fails toward blindness**, which is the safe direction. *A broken health check must never manufacture a `VERIFIED_FAILURE`.* |
| Readback matches an invoice we did **not** create *(someone else billed it)* | **`OBSERVATION_CONFLICTING`** ⇒ Conflict ⇒ **entity frozen.** *This is exactly the R-02 double-write, detected.* |
| The TMS renumbers the record after creation | Verification keys on the **commit key** written into the record where possible, else on the material facts — **never on a guessed record number.** |
| Verification succeeds but the process dies before recording | **Impossible** — one atomic commit (§3.11, ADR-008 §2.5). |
| A flapping channel produces alternating outcomes | Repeated `OBSERVATION_UNAVAILABLE` on one entity ⇒ **Exception**. *A flapping authoritative source is an operational fact, and it gets a human.* |

---

## 7. SECURITY CONSIDERATIONS

- **A model never determines a verification outcome.** Verification is **deterministic code** reading an authoritative source and comparing to a fingerprint. *(P2: guards are never model-evaluated.)* A model may **assist in locating** a record; it may **never assert** that it found one.
- **Inbound content cannot assert a verification.** A counterparty email saying *"payment received"* is an **Observation** with `provenance_class = MODEL_EXTRACTED` at best (ADR-002 §2.3) — **it is not proof of our effect**, and it may not discharge `NEEDS_VERIFICATION`.
- **Health signals must not be spoofable by the page under test.** *(A page that renders "no results" and a page injected to look like "no results" are the same bytes — hence the positive sentinel, which an attacker controlling the page could also fake. Therefore: **a hostile TMS is out of scope; a broken one is not.** This is stated, not hidden.)*
- **`NEEDS_VERIFICATION` freezes the entity** — which is also the correct security posture: an entity in an unknown state cannot be operated on by anything, including an agent.

---

## 8. OPERATIONAL CONSIDERATIONS

- **`NEEDS_VERIFICATION` count is a Sev-1 operational metric.** It should be **near zero**; a rising count means a channel is degrading.
- **Every `NEEDS_VERIFICATION` has an owner and an ageing clock** (ADR-008 §3.9), and **ageing escalates** — because the one thing worse than an unknown outcome is an unknown outcome nobody is looking at.
- **Mean time to human resolution** is the metric that matters, and it is a **product** metric, not an engineering one: it measures how good the escalation message was.
- **Channel health must be monitored independently of verification** — otherwise the first time we learn the readback is broken is when money is in flight.

---

## 9. TESTING REQUIREMENTS *(merge-gating)*

| Test | Asserts |
|---|---|
| ### **The blindness test** | Log the session out, then attempt verification. **Assert `OBSERVATION_UNAVAILABLE`, NOT `VERIFIED_FAILURE`. Assert no retry. Assert the entity is frozen.** *This is the test the ADR exists for.* |
| **Proof-of-absence requires health** | Remove the health control ⇒ **assert `VERIFIED_FAILURE` is unreachable**. |
| **Readback must match approved facts** | Effect created at £3,100 when £2,850 was approved ⇒ **`OBSERVATION_CONFLICTING`**, not success. |
| **No auto-resolve** | Advance the clock arbitrarily on `NEEDS_VERIFICATION` ⇒ **assert it does not move.** Assert every timer transition is an **illegal transition**. |
| **No compensation on unknown** | Attempt to compensate an `UNKNOWN_OUTCOME` ⇒ **refused**. |
| **Retry only on proven failure** | `VERIFIED_FAILURE` ⇒ a new pipeline is permitted. `UNKNOWN_OUTCOME` ⇒ **effect retry refused**, verification retry allowed. |
| **Same commit key on retry** | Retry after a *secretly-successful* first attempt ⇒ **the second claim is refused by the DB.** |
| **Impossible verification is declared** | An adapter with no readback ⇒ its operation **cannot be `AUTONOMOUS_WITHIN_CAPS`**; build/config check fails. |
| **Never say delivered** | The email adapter's success payload contains **no** `delivered`/`received`/`read` field. |
| **Atomic verify+record** | Kill between verify and record ⇒ the outbox guarantees the event exists. |
| **Permanent verification failure** | Auth failure during verification ⇒ **Exception immediately, zero retries.** |

---

## 10. MIGRATION CONSIDERATIONS

- **The live browser agent already implements the instinct**: it has settle-detection, readback, amount reconciliation, and a `NEEDS_VERIFICATION` path in `operation_router`. **The discipline is right.** What it lacks is the **taxonomy** (it has ~2 outcomes, not 8) and, critically, **the positive health control** (§3.4) — *today, an unrendered page and an empty list are still capable of looking alike.*
- **The `invoices_table_present` retry-once check is an early, partial health control.** **Keep it. Generalize it.**
- The existing `NEEDS_VERIFICATION` payload in `operation_router.py:290` is **the ancestor** of §3.8 — but it does not yet carry the **exposure** or the **specific question**.

---

## 11. OPEN QUESTIONS

| # | Question | Status |
|---|---|---|
| **Q1** | **What is the right positive health control per TMS screen?** It is screen-specific and must be discovered per system. | **Implementation + discovery.** Mechanism is settled; the sentinel is per-adapter. |
| **Q2** | **Deferred-verification bounds** — how long does TruckingOffice take to reflect a write? Observed ~immediate; other TMSs batch. | **`NEEDS VALIDATION` — per integration.** |
| **Q3** | Can a **later AR read** deterministically discharge a `NEEDS_VERIFICATION` without a human, if the record carries our commit key? | ✅ **Yes in principle** (§3.8, `LaterObservationProves`) — **but only if the commit key is written into the external record.** Whether TruckingOffice permits that is **`NEEDS VALIDATION`**. **If it does not, a human resolves it. We do not infer.** |
