# ADR-009 — Entity Concurrency, Reservations & Versioning

**Status:** ✅ **FINAL — Wave 2.**
**Baseline:** `f0e801b4dfd611345ca6c2842e946d58a7512ae5`
**Resolves:** correction-plan **Group F** — **F-10** (CRITICAL); and the **entity-exclusion half of audit R-02 / F-07**.
**Consumed by:** ADR-004 §2.4 (checkpoint step 5), ADR-005 (entity versions are material facts), ADR-008 §3.2.
**Constrained by (frozen):** ADR-004 (the Effect Grant Ledger), ADR-008 (the Pipeline Instance).

---

## 1. CONTEXT

ADR-004 gives the effect boundary its **capability** control. ADR-008 gives work its **durability**. **Neither prevents two pipelines from doing the same thing at the same time.**

The instruction for this ADR was explicit: ***"Use the Effect Grant Ledger where appropriate. Do not duplicate reservation concepts unnecessarily."*** **This ADR therefore introduces NO new table and NO new primitive.** It does three things:

1. **Defines the commit key** — which ADR-004 *uses* but never *composes*.
2. **Turns the Pipeline Instance into the reservation** — using a unique index, not a new entity.
3. **Defines optimistic concurrency** on entity versions.

---

## 2. PROBLEM STATEMENT

### 2.1 The architectural gap (F-10)

Nothing reserves a **business entity**. Two pipelines can both propose *"invoice load 4471"*. Both post a Slack card. The owner taps both. **The customer gets two invoices.** Every gate passed. Both are audited. **Each is invisible to the other.**

### 2.2 ⛔ The live defect — and it is worse than the architecture gap

**Baseline `f0e801b`, `operation_router.py:335`:**

```python
def _commit_identity(tenant, lane, intent, amount) -> dict | None:
    if not amount:
        return None                      # ⛔ (B)
    return {
        "tenant": tenant, "lane": lane,
        "load_ref": load_ref, "party": party,
        "approved_amount": normalize_money_amount(amount),   # ⛔ (A)
    }
```

> ### **(A) The approved amount is part of the commit key.**
>
> Two proposals to bill load 4471 — one that read **£2,850**, one that read **£3,100** — produce **two different commit keys**. **Commit-once does not fire. Both commit. The customer is invoiced twice, for two different amounts.**
>
> ### **Commit-once fails in precisely the case it exists for.** The amount is the thing most likely to differ between two racing reads — so it is the *worst possible* field to put in the identity of the effect.

> ### **(B) No amount ⇒ no commit key ⇒ NO commit-once protection at all.**
>
> Every non-money effect — **filing a POD, flipping a status, updating a load** — has **no duplicate protection whatsoever**. The POD can be attached twice; the status can be written twice.

**The root confusion:** the commit key was built from **the content of the decision** (how much) instead of **the identity of the effect** (what, on what). **Those are different, and ADR-005 already separates them: the amount is a *material fact*, bound in the fingerprint. It is not an identity.**

---

## 3. DECISION

### 3.1 The two-layer rule

> ## **Layer 1 — the Pipeline Instance IS the reservation.** *(early; protects the owner's attention)*
> ## **Layer 2 — the Effect Grant Ledger IS commit-once.** *(late; protects the money)*

**No third mechanism. No `reservations` table. No lease. No lock manager.**

| | Layer 1 — Reservation | Layer 2 — Commit-once |
|---|---|---|
| **Lives in** | `pipeline_instances` (**ADR-008**) | `effect_grants` (**ADR-004 §3.2**) |
| **Mechanism** | `UNIQUE (tenant_id, commit_key) WHERE state NOT IN (terminal)` | `UNIQUE (tenant_id, commit_key) WHERE state = 'CLAIMED'` |
| **Held for** | **the whole pipeline — including human time** | **the instant of the effect** |
| **Prevents** | a **second proposal** ⇒ **a second Slack card** | a **second effect** ⇒ **a second invoice** |
| **If it fails** | the second proposal is **refused at `PROPOSED`**, and joins the existing work item | the second claim is **refused**; the adapter **does nothing** |

**Layer 2 alone is sufficient for safety. Layer 1 exists so the owner is never shown two cards for the same thing** — and so the duplicate is caught *before* a human wastes a decision on it. **Layer 1 is UX and sanity; Layer 2 is the guarantee.** *If Layer 1 is ever bypassed, the database still refuses.*

### 3.2 Why the Pipeline Instance, and not a new reservation entity

**ADR-008 §2.12 already ruled: *"The Pipeline Instance IS the command."*** A command that is in flight **is** a claim on its target. Adding a `reservations` table would create a second thing that means the same thing — with its own lifecycle, its own expiry, its own crash semantics, and its own way of getting out of sync with the pipeline it shadows.

**Applying the mandated test for a new concept:**

| Question | Answer |
|---|---|
| **1. Why can't an existing mechanism express it?** | **It can.** The Pipeline Instance already has: identity, tenant, a target, a durable lifecycle, terminal states, crash recovery, and an owner. **A reservation is a pipeline instance that hasn't finished.** |
| **2. Why would extending an existing mechanism be incorrect?** | **It isn't** — one partial unique index is the entire change. |
| **3. What complexity would a new concept add?** | A table, a lifecycle, a lease/renewal protocol, expiry, orphan reaping, **and a permanent two-sources-of-truth problem.** |
| **4. Is that complexity justified?** | **No.** |
| **5. What maintenance burden?** | **A reservation that outlives its pipeline, or a pipeline that outlives its reservation.** Both are silent, and both are money. |

> ### **Verdict: NO new primitive. A unique index on an entity we already have.**

### 3.3 Reservation semantics

| Property | Ruling |
|---|---|
| **Ownership** | The **Pipeline Instance** holds it. Its **human owner** is the Work Item's owner (**I1**). |
| **Acquisition** | At `PROPOSED`, in the same transaction that creates the instance. **Failure to acquire is not an error** — the proposal is **absorbed** into the existing pipeline (§3.4). |
| **Expiry** | ### **The reservation has no TTL of its own.** It is released **exactly when its pipeline reaches a terminal state** (`CLOSED`, `REJECTED`, `VOIDED`, `FAILED`). *A reservation with an independent TTL is a second clock, and two clocks disagree.* |
| **What bounds it, then?** | **The pipeline's own timers** — the **approval TTL** (ADR-005 §3.9) and the **grant TTL** (ADR-004 §3.4). An abandoned proposal expires its approval ⇒ `VOIDED` ⇒ **the reservation releases itself.** |
| **Renewal** | ### **Does not exist.** No heartbeat, no lease. *(A lease is a promise to keep being alive, and a crashed process makes that promise too.)* Liveness is handled by **crash recovery** (ADR-008 §2.10), which is already correct. |
| **Stealing** | ### **NEVER silently.** A reservation is released **only** by its pipeline reaching a terminal state. |
| **`NEEDS_VERIFICATION`** | ### **NEVER releases the reservation.** It is **non-terminal by design.** **The commit key stays reserved indefinitely** — which is exactly ADR-004 §3.9's requirement, and it means **nothing can retry an effect whose outcome we do not know.** *The stuck reservation is not a bug. It is the point.* |
| **Cancellation** | A human may **cancel** a pipeline (⇒ `VOIDED`, pre-claim only), which releases it. **After `CLAIMED`, cancellation is meaningless** — the world may already have changed. That is **Compensation**, not cancellation (ADR-008 §3.2). |

### 3.4 Duplicate proposals are absorbed, not rejected

**A second proposal for a reserved commit key is not an error.** It is *the same intent, arriving twice*.

⇒ It **attaches to the existing Pipeline Instance** and **adds itself as evidence** (*"the AR sweep also thinks load 4471 should be billed"*). ⇒ **The owner sees ONE card.** ⇒ **No second approval is ever requested.**

*This is what B4's failure taught, generalized: an owner shown two cards for the same load will tap both, and be right to.*

---

## 4. THE COMMIT KEY — composed, at last

> ## **The commit key is the identity of the EFFECT. It is NOT the content of the decision.**

```
commit_key = SHA256( "ck_v1"
                   | tenant_id
                   | action_class          # RAISE_INVOICE
                   | target_system         # tms:truckingoffice
                   | target_resource_id    # load:4471
                   | target_operation      # create_invoice
                   | occurrence_key )      # §4.2
```

### 4.1 What is deliberately **NOT** in it

| Excluded | Because |
|---|---|
| ### **`approved_amount`** | ### **This is defect (A).** The amount is a **material fact** (ADR-005 §3.2), bound in the **fingerprint**. **If the amount changes, the approval is VOID (drift) — the effect does not become a different effect.** *"Bill load 4471" is one effect whether it is £2,850 or £3,100. Putting the amount in the identity is what lets the customer be billed twice.* |
| `approval_id` | An approval authorizes an effect. **It does not define one.** A retry uses the same commit key with a new grant. |
| `pipeline_instance_id` | The whole point is that **many instances share one commit key**. |
| Confidence, evidence, provenance | Not identity. |

### 4.2 `occurrence_key` — how a legitimate repeat is distinguished

Some effects legitimately repeat: two partial payments on one invoice; a re-issued invoice after a credit.

**`occurrence_key` is derived from the WORLD, never from a counter.** *(A counter would let the system authorize its own repetition.)*

| Effect | `occurrence_key` |
|---|---|
| Raise invoice on a load | `""` — **an invoice is raised once.** A re-issue is a **different action class** (`REISSUE_INVOICE`) after a credit. |
| Record a customer payment | **the remittance reference** (check no. / ACH trace) — *the world's name for this payment* |
| Record a carrier payable | the **carrier invoice number** |
| File a document | the **document content digest** — *the same bytes filed twice is one effect* |

> ### **THE FAIL-CLOSED RULE:**
> ## **If you cannot name what makes this occurrence different from the last one, you may not repeat the effect.**
>
> A missing `occurrence_key` where one is required ⇒ **the pipeline is REJECTED at `PROPOSED`.** ***"I don't know why this is a second payment"* is a refusal, not a default.**

### 4.3 Every effect has a commit key — **no exceptions**

**Defect (B) is closed by construction:** the commit key **no longer depends on an amount**, so **filing a POD, flipping a status, and updating a load all have one.** **A commit key is mandatory. `None` is not a legal value**, and the pipeline cannot be created without one.

---

## 5. OPTIMISTIC CONCURRENCY — entity versioning

**Reservations prevent duplicate *work*. Versions prevent lost *updates*. They are different problems and they need different tools.**

| Property | Ruling |
|---|---|
| **Version** | Every entity (ADR-008 §2.3) carries a **monotonic `version`**, incremented on every state transition, in the same transaction (outbox, §2.5). |
| **Read** | The checkpoint records `entity_versions` — the versions of **every entity whose state made this action correct** (ADR-004 §3.2). |
| **Check** | **Checkpoint step 5:** re-read the versions **live**. **Any change ⇒ the checkpoint FAILS ⇒ no grant.** |
| **Write** | `UPDATE … WHERE version = $expected`. **Zero rows ⇒ lost update ⇒ raise.** |
| ### **Locks** | ### **NO entity lock is EVER held across human time.** Versions are **read and CAS'd inside the checkpoint**, which is short. **The long wait (approval) is protected by the reservation, not by a lock.** |

> **This is the distinction that prevents the classic disaster: a system that holds a row lock while a human thinks about it, and then discovers that humans think for four hours.**

**Entity versions are material facts (ADR-005 §3.2 #12)** — so a version change is *also* drift, and it produces a human-readable explanation rather than a bare optimistic-concurrency exception.

---

## 6. RACES — the complete table

| Race | Resolution |
|---|---|
| **Two pipelines, same effect** | **Layer 1** absorbs the second at `PROPOSED` (§3.4). If bypassed, **Layer 2** refuses the second claim. **One effect.** |
| **Two humans approve the same card** | Approval CAS `GRANTED → CONSUMED` (ADR-005 §3.15). One wins; the other is told *"already approved by <name>"* — **not an error.** |
| **Two humans approve *different* proposals for the same load** | **Cannot happen** — Layer 1 means there was only ever one card. |
| ### **Human vs agent** | ### **The human wins. Always.** An `OWNER_ASSERTED` action on an entity with an in-flight autonomous pipeline **VOIDs that pipeline** (pre-claim). Post-claim, the human's action proceeds **and the entity is frozen** if the agent's outcome is unknown. |
| **The owner acts directly in the TMS** *(the ADR-004 emergency path)* | Neyma **observes** it ⇒ the entity version and material facts change ⇒ ### **any in-flight approval is `VOID_ON_DRIFT`.** *The emergency path is safe **because** of drift detection, not in spite of it. The two mechanisms were designed apart and meet here exactly.* |
| **Concurrent corrections** (two humans correct the same binding) | **Version CAS.** The loser is **re-shown the current state** and asked again. **Never silently merged.** |
| **Parallel agents** | Agents **cannot hold grants** (ADR-004 §2.6). They emit `ProposedIntent`s, which **serialize at the reservation.** ### **N agents produce at most one effect.** |
| **A retry racing a secretly-successful first attempt** | **Layer 2.** The first attempt's `CLAIMED` row blocks the retry's claim. **The retry does not need to be trusted — the database is.** |
| **Two effects on different entities in one logical operation** | §7. |

---

## 7. MULTI-ENTITY OPERATIONS & DEADLOCK

> ### **Deadlock is structurally impossible, because no pipeline ever holds two reservations.**

**Rule: one Pipeline Instance reserves exactly ONE commit key — therefore exactly one target resource.** **There is no hold-and-wait. Therefore there is no deadlock.** *(This is not a mitigation; it is the removal of a precondition.)*

**A logical operation spanning several entities is decomposed into several Pipeline Instances, coordinated by the Work Item** (ADR-008: Work Item : Pipeline = **1:N**). Each is **individually gated, individually reserved, individually verified.**

**What about atomicity across entities?**

> ### **We do not have it, and we must not pretend to.**
>
> **The external world offers no distributed transaction.** We cannot invoice a customer and settle a carrier atomically — the TMS does not offer it, and no amount of local machinery creates it.
>
> **So we do not fake it.** A multi-entity operation is a **sequence of individually-verified effects**, and a failure partway leaves a **Work Item that is visibly, honestly incomplete**, with a human owner and a stated exposure. **Partial completion is surfaced, never hidden behind a fake transaction boundary.**

**Where entity versions must be read across several entities** (inside one checkpoint), they are acquired in **canonical sorted order by `(entity_type, entity_id)`** — deterministic, and momentary.

---

## 8. ALTERNATIVES REJECTED

| Alternative | Rejected because |
|---|---|
| ### **A `reservations` table** | **Duplicates the Pipeline Instance** (§3.2). Creates a second lifecycle that can drift out of sync with the first — **silently, and about money.** |
| **Pessimistic row locks on the entity** | **They would be held across human time.** A lock waiting on an owner who went to lunch is an outage. |
| **A distributed lock service (Redis/etcd)** | **New infrastructure, new failure mode, no new guarantee.** The transactional store already gives us CAS. **P36.** |
| **Advisory locks / lock manager** | A lock that can be ignored is documentation. |
| **Keep `approved_amount` in the commit key** *(status quo)* | ### **This is the double-billing defect.** §2.2(A). |
| **Lease + heartbeat renewal** | A crashed process heartbeats right up until it doesn't; then a timeout has to guess. **Crash recovery (ADR-008 §2.10) already solves liveness correctly, without guessing.** |
| **Auto-expire a `NEEDS_VERIFICATION` reservation to unblock work** | ### **This is the one that would kill someone's business.** It would free the commit key of an effect **whose outcome we do not know**, permitting a retry that could double-pay. **The stuck reservation is the safety property.** |
| **Serialize everything (one global writer)** | Safe and useless. Does not scale past one tenant, and does not actually fix identity — **two proposals for one load would still both be valid, just sequential.** |

---

## 9. CONSEQUENCES

1. **F-10 closes. R-02's entity-exclusion half closes** — the **Effect Grant Ledger + the pipeline unique index** together are the shared namespace the six entry points never had. **There is no second write path, because there is only one row that can be claimed.**
2. **The live double-billing defect (§2.2) is closed by the commit-key composition.**
3. **Every effect now has commit-once protection**, not just money effects.
4. **No new tables. No new lifecycle. No lock manager. Two partial unique indexes.**
5. **Deadlock is impossible by construction**, not by careful lock ordering.
6. **Cost:** a legitimate repeat now requires a **named `occurrence_key`**. **This will occasionally block something a human wanted.** **Accepted** — *"I don't know why this is a second payment"* is the right thing for a machine to say.
7. **`NEEDS_VERIFICATION` permanently blocks its commit key.** **This is intended, and it will feel wrong to an engineer under pressure.** It is the last line between an unknown outcome and a double payment.

---

## 10. FAILURE MODES

| Failure | Behaviour |
|---|---|
| Crash holding a reservation | **Crash recovery** (ADR-008 §2.10) resumes the pipeline. Pre-effect ⇒ re-checkpoint. Post-claim ⇒ **`NEEDS_VERIFICATION`** — ### **and the reservation stays held.** |
| A pipeline is stuck in `AWAITING_APPROVAL` forever | The **approval TTL** fires ⇒ `VOIDED` ⇒ reservation released. **Bounded, without a lease.** |
| Clock skew between processes | Irrelevant to correctness: **exclusion is a database constraint**, not a time comparison. Only TTLs use time, and they use **the DB clock**. |
| Unique-index violation under load | **Expected and normal.** It is caught and turned into "absorbed" (Layer 1) or "already committed" (Layer 2). ### **It is a control, not an exception to be logged and swallowed.** |
| Two tenants, same load number | **Impossible to collide** — `tenant_id` is the first component of every key and every index (F-12). |
| An `occurrence_key` is reused by mistake | The effect is refused as a duplicate. **Fail-closed, and correct** — a repeated remittance reference *is* the same payment. |
| A hot entity (many proposals for one load) | They **absorb** into one pipeline (§3.4). **Contention produces one card, not a queue.** |

---

## 11. SECURITY CONSIDERATIONS

- **The unique index is not bypassable from application code.** It is not a check that can be forgotten — **it is a constraint that must be violated.**
- **Agents cannot hold reservations or grants**, so **no number of parallel agents can produce more than one effect** (§6). *An agent compromised by prompt injection gains the ability to propose; the reservation and the ledger cap what that can become.*
- **`NEEDS_VERIFICATION` freezing the commit key is a security property**, not just a safety one: an attacker who induces an ambiguous outcome **cannot then trigger a retry**.
- **Tenant is the first component of every key**, so cross-tenant collision or interference is **structurally impossible** (F-12).

---

## 12. OPERATIONAL CONSIDERATIONS

- **Absorbed-duplicate rate** is a health metric: a high rate means two triggers are proposing the same work (e.g. the AR sweep and an email trigger). **Not harmful — but it means something upstream is redundant.**
- **Layer-2 refusals should be ~zero.** ### **A Layer-2 refusal means Layer 1 was bypassed — i.e. something proposed an effect outside the pipeline. That is a Sev-1**, and it is exactly the R-02 signature.
- **Held reservations on `NEEDS_VERIFICATION`** must be a **visible operational queue** — they are, by construction, blocking real work, and that is the pressure that gets a human to resolve them. **Do not build a way to clear them in bulk.**
- **Long-held reservations** (an approval sitting for hours) are a **product** signal: the owner is not tapping. That is a UX problem, not a concurrency one.

---

## 13. TESTING REQUIREMENTS *(merge-gating)*

| Test | Asserts |
|---|---|
| ### **The double-billing regression (§2.2 A)** | Two proposals to bill load 4471 at **£2,850** and **£3,100** ⇒ **the SAME commit key** ⇒ **exactly one invoice.** *This test fails against the current baseline. That is the point.* |
| ### **Non-money commit-once (§2.2 B)** | File the same POD twice ⇒ **one attachment.** *(Today: two.)* |
| **Layer-1 absorption** | Two concurrent proposals ⇒ **one Pipeline Instance, one Slack card, one approval request.** |
| **Layer-2 last line** | Bypass Layer 1 and drive two pipelines to claim ⇒ **exactly one claim succeeds.** |
| **Retry vs secret success** | First attempt commits but its response is lost ⇒ retry ⇒ **claim refused; no second effect.** |
| ### **`NEEDS_VERIFICATION` holds the key** | An effect goes unknown ⇒ **assert no new pipeline for that commit key can be created or claimed**, indefinitely. **Assert no timer releases it.** |
| **Human beats agent** | Owner acts while an autonomous pipeline is `AWAITING_APPROVAL` ⇒ **the pipeline VOIDs.** |
| **Owner acts in the TMS directly** | Out-of-band TMS change ⇒ in-flight approval ⇒ **`VOID_ON_DRIFT`** with an explanation. |
| **N parallel agents** | 50 agents propose the same effect ⇒ **one effect.** |
| **Missing `occurrence_key`** | A second payment with no remittance reference ⇒ **REJECTED at `PROPOSED`**, with the reason. |
| **No deadlock** | Property test: no pipeline ever holds >1 reservation. |
| **Approval TTL releases** | Abandon a proposal ⇒ TTL ⇒ `VOIDED` ⇒ **reservation released**, verified by a successful subsequent proposal. |
| **Tenant isolation** | Same load number, two tenants ⇒ **two independent commit keys, no interference.** |

---

## 14. MIGRATION CONSIDERATIONS

- ### ⛔ **`_commit_identity` (`operation_router.py:335`) must be rewritten. It is a live double-billing hole** (§2.2). **It is NOT fixed in this ADR** — no implementation code in Wave 2 — **but it is now a known, recorded, blocking defect against the baseline.**
- The existing `operation_action_claims` table (`workflow.py:167`) is **the ancestor of the Effect Grant Ledger** — it already implements a single-use claim keyed by `action_id`. ### **The discipline is right; the key is wrong.** **Generalize it. Do not discard it.**
- **`claim_operation_commit` is Layer 2 in embryo.** It needs: the corrected key (§4), the partial unique index, and to become **transactional with the pipeline state** (ADR-008 §2.5) rather than a separate SQLite commit.
- **There is no Layer 1 today at all.** Duplicate proposals are, today, **only** caught (if at all) at claim time — which is why an owner can be shown two cards.

---

## 15. OPEN QUESTIONS

| # | Question | Status |
|---|---|---|
| **Q1** | **`occurrence_key` for a re-issued invoice after a credit** — is that `REISSUE_INVOICE` (a distinct action class), or `RAISE_INVOICE` with an occurrence key? | ⚠️ **Recommendation: a distinct action class.** *A re-issue after a credit is a different business act with a different approval and a different risk. Modelling it as "the same effect, again" is how a credit-and-rebill loop becomes a double-bill.* **`NEEDS VALIDATION` — customer.** |
| **Q2** | **Partial payments** — is each partial payment a separate effect keyed by remittance reference? | ⚠️ **Recommendation: yes.** Confirm against a real remittance file. **`NEEDS VALIDATION` — customer.** |
| **Q3** | Should Layer-1 absorption **notify** the owner (*"the AR sweep also flagged this"*)? | **Product.** ⚠️ Recommend **no** by default — **it is noise**; but it must appear in the **audit trail**. |
