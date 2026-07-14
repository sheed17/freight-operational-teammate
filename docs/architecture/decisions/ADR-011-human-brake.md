# ADR-011 — The Human Brake & Operational Control

**Status:** ✅ **FINAL — Wave 4.**
**Completes:** **atomic pre-effect checkpoint STEP 7** (ADR-004 §2.4). ### **With this, all seven steps are defined.**
**Resolves:** correction-plan **Group I** — **F-15**, **F-31**.
**Language:** `docs/architecture/semantic-model.md` — **canonical, used verbatim.**

---

## 0. WHY THE BRAKE IS NOT A POLICY

**The obvious economy is to model the brake as a policy that denies everything in scope.** ### **It is wrong, and it is worth saying exactly why, because the reasoning is the ADR.**

> ### **One of the reasons you pull the brake is that the POLICY ENGINE IS WRONG.**
>
> A brake implemented as a policy **depends on the very subsystem it exists to overrule.** A bad policy deployment, a corrupt rule, a policy store that will not load — **these are precisely the moments the brake must work**, and precisely the moments a policy-based brake would not.

**Three further reasons they cannot be one mechanism:**

| | **Policy** (step 6) | ### **Brake** (step 7) |
|---|---|---|
| **Authoring** | Author → confirm → activate. **Reviewed.** | ### **Instant. One authenticated human. No review, no approval, no ceremony.** |
| **Health precondition** | Needs the policy engine, the rule store, the compiler | ### **NONE. The brake MUST be engageable when the system is broken.** *A safety control that requires the system to be healthy is not a safety control.* |
| **Direction** | Permits or denies, per rules | ### **Only ever DENIES.** It cannot permit anything. |

**This is exactly why ADR-004 §2.4 made them steps 6 and 7 — two checks, not one.** ### **The brake is the thing you pull when everything else is wrong, so it may depend on nothing else.**

---

## 1. THE DECISION

> ## **The brake is ADMISSION CONTROL, not process termination.**
>
> ### **It is enforced by REFUSING TO MINT and REFUSING TO CLAIM — never by killing a worker.**

**A brake that kills workers manufactures the exact thing the architecture fears most:** ### **an `UNKNOWN_OUTCOME`.** A process killed mid-adapter-call leaves an effect that **may have landed**, with **nobody to verify it**. *You would engage the brake to become safer and, in the act of engaging it, create a payable of unknown status.*

> ### **DO NOT CREATE AN UNKNOWN OUTCOME MERELY BY KILLING WORKERS.**

---

## 2. WHAT ENGAGEMENT DOES

| Within scope, when the brake is `ACTIVE` | |
|---|---|
| ### **No new Effect Grant may be MINTED** | The checkpoint's step 7 fails ⇒ **no `CheckpointPassed`** ⇒ nothing to mint from. |
| ### **No existing Effect Grant may be CLAIMED** | The claim transaction re-checks brake state (§8). **An unclaimed grant becomes unclaimable.** |
| **No pipeline may enter execution** | It halts at `CHECKPOINT`, durably. |
| **Pending approvals remain RECORDED** | ### **They are not deleted and not denied.** They simply **cannot execute**. *(They may later be `VOID_ON_BRAKE` — ADR-008 §3.4.)* |
| **Queued work remains DURABLE** | ### **Nothing is lost. The brake is a pause on ACTING, not on KNOWING.** |
| **Observation and reconciliation CONTINUE** | ### **By default, yes.** *Blinding yourself during an incident is the opposite of what you want.* They may be **explicitly** disabled by a separate, narrower control. |
| ### **In-flight effects past the claim CONTINUE — through verification and durable recording** | ### **This is the critical rule.** §5. |
| **The system REPORTS exactly what was in flight** | §7. |

---

## 3. THE BOUNDARY — five positions, and the brake treats them differently

**This table is the heart of the ADR.**

| Position | Ledger state | Did the world change? | ### **Brake behaviour** |
|---|---|---|---|
| **1. Not yet executing** *(pre-checkpoint, or checkpoint passed but grant unminted)* | none | ### **NO** | ### **STOP.** Halt durably. Nothing happened. |
| **2. Checkpoint passed, grant MINTED but UNCLAIMED** | `GRANTED` | ### **NO — the adapter never acted** | ### **STOP.** The grant is **revoked** (`EXPIRED_UNCLAIMED`, ADR-008 §3.3). Pipeline ⇒ `VOIDED`. **Safe.** |
| **3. Grant CLAIMED, adapter not yet called** | `CLAIMED` | ⚠️ **We cannot prove it didn't** | ### **DO NOT KILL.** Let it complete and verify. *(The CAS is placed immediately before the call precisely to make this window as small as physically possible — ADR-004 §7 — but it is not zero, and the architecture must not pretend otherwise.)* |
| **4. Adapter called, response pending** | `CLAIMED` | ### ⚠️ **POSSIBLY — this is the money** | ### **DO NOT KILL. LET IT FINISH AND VERIFY.** Killing here **converts a knowable outcome into an unknown one.** |
| **5. Verification in progress** | `ATTEMPTED` | **Yes, and we are finding out what** | ### **LET IT FINISH.** *Verification is a READ. It is not an effect. The brake has no reason to stop a read.* |

> ### **The brake stops the NEXT effect. It cannot stop the LAST one.**
> Anything at position **3, 4, or 5 runs to a verified conclusion**, because ### **the only thing worse than an effect you didn't want is an effect you didn't want AND cannot describe.**

**If verification becomes impossible** *(the channel is down, the session is dead, the process died)*: ### **ownership transfers to the `UNKNOWN_OUTCOME` process of ADR-006** — non-terminal, human-owned, entity frozen, **commit key held**, escalated with the **dollar exposure**. **The brake does not resolve it. Nothing resolves it but a human or a proof.**

**Compensation in progress:** a compensation **is an effect**, so it obeys this same table. ### **A compensation that has CLAIMED runs to verification.** **`COMPENSATION_FAILED` remains non-terminal and human-owned** (ADR-008 §2.13) — **the brake does not, and cannot, clear it.**

---

## 4. BRAKE STATES — **two, and no more**

> ### **`ACTIVE` · `RELEASED`**

**Uses the canonical Durable Machine (ADR-008 §2.3). No new lifecycle machinery.**

| From | Trigger | Guard | → | Emits |
|---|---|---|---|---|
| — | `BrakeEngaged` | authenticated human **OR** an automated Sev-0 detector (§5) | **`ACTIVE`** | `BrakeEngaged{scope, actor, reason, brake_version++}` |
| `ACTIVE` | `BrakeWidened` | **narrows authority** ⇒ human **or automation** | `ACTIVE` *(new scope)* | `BrakeWidened{brake_version++}` |
| `ACTIVE` | `BrakeReleased` | ### **authenticated human ONLY** + release conditions (§6) | **`RELEASED`** | `BrakeReleased{actor, decision_ref, brake_version++}` |
| `ACTIVE` | `BrakeNarrowed` *(partial release)* | ### **broadens authority ⇒ authenticated human ONLY** | `ACTIVE` *(smaller scope)* | `BrakeNarrowed{brake_version++}` |
| `ACTIVE` | ### `TimerFired` | — | ### ⛔ **ILLEGAL TRANSITION** | `IllegalTransitionAttempted` |

### 4.1 A brake **never expires**

> ### **There is no `EXPIRED` state, and there is no TTL.**
>
> **A brake that expires is a brake that releases itself while nobody is looking — and the condition that caused it may still be true.** ### **A clock cannot know whether the fire is out.**

### 4.2 Why two states and not more

**Proof of sufficiency, as required:**
- ### **"Engaged by a human" vs "engaged by automation" is an `actor` FIELD, not a state.** *(It changes who may release — §6 — not what the brake does.)*
- **"Partially released"** is ### **a scope change, not a state** — the brake is still `ACTIVE`, over a smaller scope.
- **"Pending release"** would be a state ### **only if release needed an approval workflow. It must not** — *requiring ceremony to become safer is a design error, and requiring ceremony to become UNsafe is what §6's conditions are for.*

**⇒ Two states. Everything else is a field on the record.**

### 4.3 The brake record *(a Durable Machine instance — not a new primitive)*

`brake_id` · **`tenant_id`** · `scope` (§9) · `state` · ### **`brake_version` (monotonic, GLOBAL per tenant)** · `actor` (human id **or** detector id) · `engaged_reason` · `engaged_at` · `released_by` · `release_decision_ref` · `released_at`.

---

## 5. ACTIVATION

### 5.1 Who may engage

| Actor | May engage / widen? | May release / narrow? |
|---|---|---|
| **Any authenticated authorized human** | ### ✅ **YES — instantly, no approval, no review, no ceremony** | ✅ (subject to §6) |
| ### **Automated Sev-0 detectors** | ### ✅ **YES** | ### ❌ **NEVER** |
| **A model / an agent** | ### ❌ **NEVER.** *(It may raise a signal; a detector may act on it.)* | ### ❌ **NEVER** |

> ## **Automation may only ever move authority in the SAFE direction.**
> ### **Automation may ENGAGE and WIDEN a brake. Automation may NEVER RELEASE or NARROW one.**
> *(Identical in shape to ADR-010 §7's autonomy ratchet. **The same sentence governs both. That is not a coincidence — it is the invariant.**)*

**A note on the word "narrow", because it is genuinely ambiguous and has been resolved:** ### **throughout this ADR, "narrow" and "broaden" refer to AUTHORITY — what Neyma is allowed to do — never to brake scope.** **Widening a brake narrows authority (safe; automation may).** **Narrowing a brake broadens authority (unsafe; humans only).** *(Recorded in the Semantic Model's ambiguous-words list.)*

### 5.2 The automated Sev-0 triggers

**Each engages a brake, scoped as tightly as the signal justifies:**

| Signal | Scope engaged |
|---|---|
| ### **Unauthorized adapter invocation** *(an `EffectAttempted` with no matching claimed grant — ADR-004 §4.5)* | ### **tenant + action class.** *The effect boundary has been breached; the system is acting outside its own architecture.* |
| **Runtime orphan detection** | tenant + action class |
| **Tenant isolation breach signal** | ### **GLOBAL.** *A tenant boundary failure is never one tenant's problem.* |
| **Projection rebuild divergence** *(a rebuild does not reproduce the current projection)* | tenant | 
| ### **Repeated `UNKNOWN_OUTCOME`s** | tenant + integration. *We cannot see what we are doing; we must stop doing it.* |
| **Credential compromise** | tenant + integration |
| ### **Fraud-signal threshold** *(ADR-003 — counterparty authorization claims)* | tenant + action class + **counterparty** |
| **Integration corruption** *(readback structure gone; the TMS changed under us)* | tenant + integration |

**Never a precondition:** ### **the system does not need to be healthy for the brake to engage.** The brake record is a **single row write** in the transactional store. **If that store is down, no effect can happen anyway** — the grant cannot be claimed. ### **The brake fails SAFE by construction: no store ⇒ no claim ⇒ no effect.**

---

## 6. RELEASE

> ### **Only an authenticated human. Never automation. Never a timer. Never a model.**

| Question | Ruling |
|---|---|
| **May the activating actor release?** | ### **A human who engaged it, yes.** ### **An AUTOMATED detector that engaged it, NEVER** — *a detector that could clear its own alarm is not a detector.* |
| **Required evidence** *(all mandatory, all recorded on the release)* | **1.** ### **Every in-flight effect at engagement is ACCOUNTED FOR** — each is `VERIFIED`, `FAILED`, or explicitly acknowledged as `UNKNOWN_OUTCOME` **with a named owner**. **2.** ### **No unresolved Sev-0 security event** in scope. **3.** ### **Integration health is POSITIVELY demonstrated** (ADR-006 §3.4 — a **positive control**, not "the page loaded"). **4.** A **`decision_ref`.** |
| **Do unresolved `UNKNOWN_OUTCOME`s block release?** | ### **They do NOT block it — but they must be EXPLICITLY ACKNOWLEDGED and OWNED.** *Blocking release on them would create a perverse incentive to resolve them carelessly in order to get the system running.* ### **Their entities remain frozen and their commit keys remain held regardless of the brake** (ADR-009 §3.3). **The brake's release does not release them. Nothing does but a human or a proof.** |
| **Does release create new Checkpoint Witnesses?** | ### **NO.** |
| **Do old approvals remain valid?** | ### **Only if their material facts have not drifted** — and after an incident **they almost certainly have.** They are re-checked at a **new** checkpoint; most will be `VOID_ON_DRIFT` (ADR-005). **That is correct: the world moved while we were stopped.** |
| ### **Must queued work be re-evaluated?** | ### **YES. ALL of it. Every queued consequential action passes a NEW, FULL checkpoint** — new policy version, new brake version, fresh live re-reads, fresh drift check. |

> ### **RELEASE MUST NOT REACTIVATE STALE WITNESSES OR GRANTS.**
> **Every Checkpoint Witness and every unclaimed Effect Grant minted before the brake engaged is DEAD** — the `brake_version` moved (§8), so **every one of them is invalid, permanently.** ### **They are not "resumed." The work is re-checkpointed from the beginning.**
>
> *A brake that released a queue of pre-authorized effects into a world that has changed since would be worse than no brake at all — it would be a stored-up volley.*

---

## 7. OPERATOR VISIBILITY

> ### **A hidden brake is a silent degradation, and it violates R17.**
> **A system that has quietly stopped working is indistinguishable, to an owner, from a system with nothing to do.**

**Whenever a brake is `ACTIVE`, every operator surface — Slack, CLI, health — states, unprompted:**

- **Scope** (what is stopped) and ### **what is STILL ALLOWED** *(reads, observation, reconciliation — so the owner knows Neyma is still watching)*
- **Reason**, in plain language
- **Actor** — the named human, **or the named automated detector**
- **Time engaged**, and how long ago
- **Affected workflows** and **prevented effects** *(what Neyma would have done)*
- ### **In-flight effects at the moment of engagement, and their current status**
- ### **Unresolved `UNKNOWN_OUTCOME`s, with dollar exposure**
- ### **The exact requirements for release** — *not "contact an administrator"*

**Example:**

> ### ⛔ **NEYMA IS STOPPED — carrier payables, TruckingOffice**
> **Engaged automatically 14 minutes ago** by the **orphan-effect detector**: *an adapter was invoked without a valid Effect Grant.*
> **I am not writing anything to the TMS.** I am **still reading** and still watching your inbox.
> **Prevented:** 3 payables (£11,400 total) — all held, none lost.
> ### **In flight when I stopped: 1.** Payable to Redline Carriers, £4,200 — ### **I do not know if it went through. Frozen. Owner: you.**
> **To release, I need:** (1) that payable resolved, (2) the orphan investigated, (3) a healthy TMS read.

---

## 8. ENFORCEMENT — how step 7 joins the atomic checkpoint

### 8.1 In the checkpoint transaction

**Step 7 reads the brake admission state for the scope, ### inside the same transaction as steps 1–6.**

- ### **Brake `ACTIVE` in scope ⇒ no `CheckpointPassed` ⇒ no grant ⇒ no effect.**
- **Brake clear ⇒ the observed `brake_version` is bound into the Witness and onto the Effect Grant.**

### 8.2 At grant claim — the second gate

**The claim transaction (ADR-004 §3.5) revalidates, atomically with the CAS:**

```sql
UPDATE effect_grants SET state='CLAIMED', claimed_at=now()
 WHERE grant_id=$1 AND state='GRANTED' AND expires_at>now()
   AND brake_version  = (SELECT current_brake_version FROM brake WHERE tenant_id=$2)
   AND policy_version = (SELECT current_policy_version FROM policy WHERE tenant_id=$2)
```

> ### **If the brake version changed between mint and claim, the Witness is invalid and the CAS matches ZERO ROWS. The adapter does nothing.**

**This is the race that matters**, and it is closed by the database, not by a check:

> **A human hits the brake at the exact moment a £4,200 payable is being claimed.** ### **Either the claim wins (the effect proceeds and is verified — and the brake report SHOWS it as in-flight), or the brake wins (the claim finds zero rows and NOTHING HAPPENS).** ### **There is no interleaving in which the effect half-happens, and no interleaving in which we don't know which occurred.**

### 8.3 `brake_version` is **global per tenant**, not per scope

**Deliberately.** ### **Any brake change invalidates ALL outstanding witnesses and grants for that tenant** — even ones outside the engaged scope.

**Why the bluntness is correct:** scope-precise invalidation would require reasoning about **scope overlap at claim time**, ### **and a bug in that reasoning would let an effect through during a brake.** **A conservative over-invalidation costs a re-checkpoint** *(cheap, and correct)*. **A precise under-invalidation costs a payment** *(irreversible)*. **We take the cheap failure.**

---

## 9. SCOPE — five dimensions, reusing existing concepts

**No new scope vocabulary is introduced. Every dimension already exists in the architecture.**

| Dimension | Source | Example |
|---|---|---|
| **Global (platform)** | — | *"Stop everything, everywhere."* |
| **Tenant** | ADR-004 (`tenant_id`, first in every key) | *"Stop for this brokerage."* |
| **Integration** | `target_system` | *"Stop all TruckingOffice writes."* |
| **Action class** | ADR-010 §3.1 | *"Stop carrier payables."* |
| **Counterparty** | ADR-005 material facts (customer / carrier) | *"Stop all payables to Redline."* |

**Deliberately NOT scope dimensions** *(and this is a decision, not an omission)*:

| Rejected | Why |
|---|---|
| ### **Entity** *("brake load 4471")* | ### **Already exists, and better: an entity is FROZEN by an open Conflict, a `NEEDS_VERIFICATION`, or a `COMPENSATION_FAILED`** (ADR-002 C6, ADR-006, ADR-009). ### **Adding an entity-scoped brake would be a SECOND mechanism for freezing an entity — two things that mean the same, which is precisely how they drift apart.** |
| **Workflow** | An Operating Model loop is a *sequence of action classes*. **Action-class scope already expresses it.** |
| **Accountable owner** | ### **A brake on a PERSON is an HR control, not a safety control.** *Stopping "everything Dave approved" does not describe a hazard; it describes a suspicion.* If Dave's authority is the problem, **that is a POLICY change** (ADR-010 §4) — **narrowing authority, which any human may do instantly.** |

---

## 10. INTERACTION WITH EVERYTHING ELSE

| Subject | Effect of an `ACTIVE` brake |
|---|---|
| **Checkpoint Witnesses** | ### **All invalidated** for the tenant (§8.3). |
| **Unclaimed Effect Grants** | ### **Unclaimable ⇒ effectively revoked.** *Nothing happened.* |
| ### **Claimed Effect Grants** | ### **UNAFFECTED. They run to verification** (§3). ### **The brake cannot un-ring a bell.** |
| **Approvals** | Remain recorded; **cannot execute**. May be `VOID_ON_BRAKE` (ADR-008 §3.4). |
| **Retries** | ### **A retry is a NEW pipeline needing a NEW grant ⇒ BLOCKED.** *(Which is exactly right: retrying into a braked system is the last thing you want.)* |
| ### **Compensation** | ### **A compensation IS an effect ⇒ it is BLOCKED too.** ⚠️ **This is uncomfortable and it is correct.** *A brake engaged because the system is misbehaving must not permit that same system to start writing "corrections" into the TMS.* **An urgent compensation requires a human to NARROW the brake** — an explicit, recorded, authorized act. |
| **Migration tools** | ### **Blocked.** They are **ordinary pipeline clients** (ADR-004 §2.5). ### **There is no admin bypass.** |
| ### **Agents** | ### **Blocked — and they were never a threat.** An agent's only output is a `ProposedIntent`, which is **inert data**. It cannot mint, cannot claim, cannot act. ### **A braked system with a hallucinating agent is still a safe system.** |
| **Observation / reconciliation / reads** | ### **CONTINUE.** *The brake stops ACTING, not KNOWING.* |
| **Policy** | Orthogonal. **The brake denies regardless of what policy permits** (ADR-010 §8, precedence 3 > 4). |
| **Permanent Product Truths** | ### **Unaffected — they are ABOVE the brake** (precedence 2). **Releasing the brake does not unlock them.** |

---

## 11. FAILURE MODES

| Failure | Behaviour |
|---|---|
| **The brake store is unreachable at checkpoint** | ### **FAIL CLOSED — no witness, no effect.** *("Cannot read the brake" must never mean "the brake is off." That inversion is how a safety control becomes decorative.)* |
| **The brake is engaged during a claim** | **§8.2 — the database decides. One or the other. Never both, never neither.** |
| **A worker is killed anyway** *(OOM, k8s eviction)* | This is **not the brake's doing** — it is **crash recovery** (ADR-008 §2.10). Post-claim ⇒ **`NEEDS_VERIFICATION`**. ### **The brake does not make this better or worse; it is why the brake must not kill workers itself.** |
| **A detector flaps** *(engage / engage / engage)* | Engagement is **idempotent** on scope. Repeated engagement is **one `ACTIVE` brake** and a rising **signal count**. ### **It cannot self-release, so flapping cannot open a window.** |
| **A brake is engaged and forgotten** | ### **IMPOSSIBLE TO HIDE** (§7). **Every surface reports it, unprompted, on every interaction.** *An owner asking "what's up?" is told, first, that Neyma is stopped.* |
| **A human releases prematurely** | Release requires the **evidence of §6**, and is a **recorded decision with a `decision_ref`.** ### **A bad release is auditable and attributable — which is the most a system can honestly do about a human with authority.** |

---

## 12. TESTING REQUIREMENTS *(merge-gating)*

| Test | Asserts |
|---|---|
| ### **The brake does not create unknowns** | Engage the brake **during an adapter call.** ### **Assert the in-flight effect COMPLETES and is VERIFIED.** **Assert NO `UNKNOWN_OUTCOME` is created by the brake itself.** *This is the test the ADR exists for.* |
| ### **Mint refusal** | Brake `ACTIVE` ⇒ **no `CheckpointPassed` can be constructed** ⇒ **zero grants minted.** |
| ### **Claim refusal (the race)** | Engage the brake **between mint and claim** ⇒ ### **the CAS matches zero rows; the adapter does nothing.** Run it 10,000× interleaved ⇒ ### **never both, never neither.** |
| ### **Stale witness after release** | Mint a grant → brake → release → attempt the claim ⇒ ### **REFUSED** (brake_version moved). **Assert the work is fully re-checkpointed.** |
| ### **No auto-release** | Advance the clock arbitrarily ⇒ ### **the brake does not move.** Assert every timer transition is an **ILLEGAL TRANSITION**. |
| ### **Automation cannot release** | Every automated path ⇒ ### **assert it can engage/widen but NEVER release/narrow.** Property test over all detectors. |
| ### **A model cannot engage or release** | An agent/model attempting either ⇒ **refused**, security event. |
| **Detector cannot clear its own alarm** | The engaging detector attempts release ⇒ **refused.** |
| **Compensation is blocked** | Brake `ACTIVE` ⇒ a compensation ⇒ **BLOCKED** until a human narrows the brake. |
| **Migration tools blocked** | A migration write under an active brake ⇒ **refused.** No bypass. |
| **Reads continue** | Brake `ACTIVE` ⇒ observation, reconciliation, and owner reads ⇒ **still work.** |
| ### **Unhealthy engagement** | Take down the policy engine, the rule store, and the TMS ⇒ ### **the brake still engages.** |
| ### **Fail-closed on an unreadable brake** | Brake store unreachable ⇒ ### **no effect is possible.** |
| **Visibility** | Brake `ACTIVE` ⇒ **every** operator surface reports it **unprompted** (assert on literal output). |
| **Queued work re-evaluated** | Release ⇒ ### **every queued action passes a NEW full checkpoint** — assert fresh live reads and a fresh drift check. |

---

## 13. OPERATIONAL CONSIDERATIONS

- ### **Time-to-engage must be near zero, from any surface** — Slack, CLI, or an API call. *A brake you have to log in to is a brake you will not reach in time.*
- ### **The brake must be exercised, not merely built.** **A safety control that has never been pulled is a hypothesis.** *Engage it in production, deliberately, on a schedule.*
- **Engagements are a Sev-1 metric.** **Automated engagements are a Sev-0.**
- ### **Mean time to release is NOT a metric to optimize.** *Optimizing it creates pressure to release before the evidence is in — which is exactly the failure §6 exists to prevent.*
- **The brake report (§7) is the incident timeline.** It should be good enough to paste into a post-mortem unedited.

---

## 14. MIGRATION CONSIDERATIONS

- **A brake exists today**: `pause tms writes` / `resume tms writes` in `ops_control`. ### **The instinct is right and it is already live.**
- ### **But today it is a FLAG CHECKED BY CONVENTION**, not admission control at the effect boundary. **Anything that does not check it can still write** — and **six entry points do not go through the Slack path at all** (audit R-02). **Today's brake would not stop `enter_truckingoffice_invoice.py`.**
- ### **Under this ADR it becomes unbypassable, because it moves into the CHECKPOINT and the CLAIM — the two places every effect must pass.** **Generalize it; do not discard it.**

---

## 15. OPEN QUESTIONS

| # | Question | Status |
|---|---|---|
| **Q1** | **Who, per tenant, may engage the brake?** ⚠️ **Recommendation: EVERYONE authenticated.** *The cost of a spurious engagement is a pause. The cost of a delayed engagement is a payment. **Those are not close**, and any policy that makes an operator hesitate to hit the brake is a bad policy.* | **`NEEDS VALIDATION` — customer.** **Default: everyone.** |
| **Q2** | **Who may RELEASE?** ⚠️ **Recommendation: a narrower set than may engage** — asymmetry is the point. | **`NEEDS VALIDATION` — customer.** Default: the **Policy Owner**. |
| **Q3** | Should **repeated `NEEDS_VERIFICATION`** auto-engage a brake, and at what count? ⚠️ **Recommendation: YES, at 2 within a window, per integration.** *Two unknowns on one integration is not bad luck — it means we cannot see what we are doing.* | **`NEEDS VALIDATION` — threshold.** Mechanism (§5.2) complete. |
