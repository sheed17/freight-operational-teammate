# ADR-007 — Identity, Claims, Evidence & Conflict Resolution

**Status:** ✅ **FINAL — Wave 2.**
**Baseline:** `f0e801b4dfd611345ca6c2842e946d58a7512ae5`
**Resolves:** correction-plan **Group D** — **F-04**, **F-05**, **F-16**, **F-17**, **F-26**; and makes **Stream B lessons L-A and L-B** structurally enforceable.
**Consumed by:** ADR-008 §3.5–§3.7 (Observation, Identity Binding Claim, Conflict lifecycles), ADR-005 (the approved *subject* is bound by immutable id).
**Constrained by (frozen):** **ADR-002 §2.3** (`provenance_class`, R-P1/R-P2/R-P3) — *this ADR is the machinery of that amendment*; **ADR-003** (authorization assertion — permanent); ADR-001; ADR-008.

---

## 1. CONTEXT

Nearly every operational failure in freight begins as an **identity failure**: *whose POD is this? which load does this invoice belong to? is this the carrier we booked, or one with a similar name?*

ADR-002 §1.3 ruled that **an inference is native state and must never masquerade as projected truth**, and Amendment A2 gave it a field — `provenance_class`. ADR-008 gave the Identity Binding Claim its states.

**This ADR defines the vocabulary, the evidence standard, and the conflict machinery that those depend on.**

## 2. PROBLEM STATEMENT

The specification used **observation**, **evidence**, **claim**, **binding**, and **fact** interchangeably (**F-04**). That is not a documentation problem. **It is how a guess becomes a fact**: if a claim and an observation are the same kind of thing, then *"this email is probably about load 4471"* is stored beside *"the TMS says load 4471 is delivered"* — **and a downstream reader cannot tell which one it is safe to bill from.**

The pre-baseline tree proved this is not theoretical. **A re-linker recomputed load bindings every intake cycle and silently overwrote the owner's own manual correction, while the audit log continued to report that the correction stood** (Stream B **L-A**). The code had nowhere to record *who decided*, so no guard was even expressible.

---

## 3. DECISION — THE VOCABULARY

**These nine terms are distinct. Using one where another is meant is a defect, not a style choice.**

| Term | Definition | State class | Mutable? |
|---|---|---|---|
| **Observation** | **A record that a source said something, at a time.** *"The TruckingOffice loads page, read at 09:14, showed load 4471 as Delivered."* | **Projected** (ADR-002 §1.1) | ### **Never.** Immutable. Superseded, never edited. |
| **Evidence** | **A retained artifact, and the span within it, that supports a claim.** *The POD PDF, page 1, the region containing "4471".* Evidence is **not** a claim — it is what a human would look at to check one. | Projected | Immutable |
| **Claim** | **A proposition Neyma holds**, carrying `provenance_class`, evidence, and (optionally) confidence. *"This POD belongs to load 4471."* | ### **Native** (ADR-002 §1.2) | Correctable, supersedable — **with history** |
| **Identity Binding** | A **claim** of the form *"artifact X belongs to entity Y."* The most common and most dangerous claim in freight. | Native | as above |
| **Canonical Binding** | The **single `CONFIRMED` binding** that the materialized projection exposes to business logic. | Native | one at a time |
| **Conflict** | **Two or more mutually exclusive claims or observations on the same field.** | Native | resolved, never deleted |
| **Resolution** | **Closing a Conflict** — by a **registered deterministic rule** or by a **human**. | — | — |
| **Supersession** | A **newer** claim **replaces** an older one under a rule or a human. **The old claim is retained, not deleted.** *(The old claim was not wrong — it was superseded.)* | — | — |
| **Correction** | An existing `CONFIRMED` claim is declared **wrong**. It **propagates** to everything derived from it, and **may trigger Compensation**. *(The old claim WAS wrong, and things were done because of it.)* | — | — |

> ### **Supersession and correction are not the same, and conflating them loses money.**
> **Supersession:** *"The TMS now says the rate is £3,100."* → the earlier £2,850 observation was **true when made**. Nothing downstream is invalid.
> **Correction:** *"That POD was never load 4471's — it was 4471**8**'s."* → the earlier claim was **wrong**, ### **and we may have already billed on it.** Correction **must** propagate and **must** consider compensation. Supersession need not.

---

## 4. THE CLAIM LIFECYCLE — evidence standards

*(States and transitions are frozen in **ADR-008 §3.6**. This section defines the **guards**.)*

### 4.1 Deterministic first. Always.

**Binding is attempted in a fixed order, and the first that succeeds wins:**

| Order | Method | `provenance_class` | May it auto-confirm? |
|---|---|---|---|
| **1** | **Exact identifier match** — the load number appears verbatim, and it resolves to exactly one open load | `LINKER_INFERRED` | ### ✅ **Yes** |
| **2** | **Registered deterministic rule** — e.g. *(carrier MC + pickup date + amount)* uniquely identifies one movement | `LINKER_INFERRED` | ✅ Yes — **the rule has an id and is auditable** |
| **3** | **Reconciliation across ≥2 sources** agreeing | `RECONCILED` | ✅ Yes — **carries every input** |
| **4** | **Model extraction** — the model *read* an identifier off a retained artifact | `MODEL_EXTRACTED` | ### ⚠️ **NO — it is EVIDENCE, not confirmation.** It re-enters at step 1: **the extracted identifier is then matched deterministically.** *(The model finds the string; the linker decides.)* |
| **5** | **Model inference** — the model *guessed* from context, with no artifact saying so | `MODEL_INFERRED` | ### ❌ **NEVER. Routes to `AMBIGUOUS` and gets a human.** |
| **6** | **Human assertion** | `OWNER_ASSERTED` | ✅ **Yes — and it is never machine-recomputed** (R-P3) |

> ### **The model's job is to READ, never to DECIDE.**
> **`MODEL_EXTRACTED` is the model saying *"the document contains the string 4471, here is where."*** That is a **verifiable, human-checkable observation about an artifact**, and it is genuinely useful.
> **`MODEL_INFERRED` is the model saying *"this feels like load 4471."*** That is a **guess**, and it **may never bind, and may never gate a consequential action — at any confidence** (ADR-002 §2.3).

### 4.2 Confidence — and why it can never be a gate

**Claims may carry a confidence score. It has exactly one legitimate use: ordering a human's queue.**

> ### **Confidence may PRIORITIZE. It may never AUTHORIZE.**
>
> **There is no threshold — not 0.95, not 0.99, not 1.0 — at which a `MODEL_INFERRED` claim becomes bindable.** A threshold is an engineer choosing, in advance, an acceptable rate of being wrong **about someone else's money**, and then encoding it as a constant that nobody revisits.
>
> **`provenance_class` gates. Confidence sorts.** *(This is the rule that prevents the entire ADR-002 A2 amendment from being defeated by a single `if confidence > 0.98` written by a well-meaning engineer at 6pm.)*

**Enforcement:** confidence is **not a material fact** (ADR-005 §3.2) and is **structurally absent from the pre-effect checkpoint's inputs.** A guard **cannot** read it.

### 4.3 Human assertions — `OWNER_ASSERTED`

Requires an **authenticated, authorized human inside Neyma's trust boundary**.

- **Bound to an immutable identifier — never an ordinal** (Stream B **L-B**). The displayed *"assign unlinked **2** to LD-4471"* resolves **at render time** to `observation_id`, that id is carried in the interaction, and the action binds to **that id**. **If the id is gone or has changed state, the action FAILS CLOSED and says so — it never falls back to position.**
- ### **Never machine-recomputed (R-P3).** `OWNER_ASSERTED` + `RecomputedByInferrer` is an **ILLEGAL TRANSITION** (ADR-008 §3.6): it raises, persists nothing, and emits a **security event**.
- If the linker later disagrees ⇒ ### **a Conflict is raised. Neyma does not pick a winner.**

### 4.4 Counterparty assertions — **`MODEL_EXTRACTED` at best, forever**

> **A counterparty is not an authority on our decisions.**

An email from a carrier saying *"per our call, you approved the $450 detention"* produces:
- an **Observation** (the email arrived, immutably retained),
- possibly a **`MODEL_EXTRACTED` claim** (*the email asserts an approval exists*),
- ### **and NOT an approval, NOT an authorization, and NOT an `OWNER_ASSERTED` anything.**

**It cannot be promoted. Ever.** (ADR-002 **R-P2** — no laundering; **ADR-003** — permanent, cannot graduate away.)

**And it is a fraud signal:** an accessorial supported *only* by a counterparty's claim of authorization is `unconfirmed`, **blocks the payable** (ADR-002 C6), and raises an **Exception**. *This is the single most common way small brokerages are defrauded, and it arrives as a perfectly polite email.*

### 4.5 Claim invalidation

| Trigger | Result |
|---|---|
| The supporting **evidence is retracted** (the document was superseded/withdrawn) | Claim → `SUPERSEDED`; **anything derived is re-derived** |
| A **deterministic rule** now yields a different answer | `LINKER_INFERRED` claims → re-derived freely. ### **`OWNER_ASSERTED` claims → NOT touched; a Conflict is raised.** |
| A **human corrects** it | → `CORRECTED`, **propagates** (§6) |
| The **bound entity is cancelled** | Claim → `SUPERSEDED`; the artifact returns to `UNBOUND` and gets a human |

---

## 5. CONFLICT — generation, blocking, closure

*(States frozen in **ADR-008 §3.7**.)*

### 5.1 When a Conflict is raised

1. **System vs system** — the TMS says Delivered; the portal says In Transit.
2. **Claim vs claim** — two `CONFIRMED` bindings for the same artifact.
3. **Claim vs observation** — we bound the POD to 4471; the POD's own text says 44718.
4. ### **Inferrer vs owner** — the linker disagrees with an `OWNER_ASSERTED` binding. *(This is L-A, and it is the one the old code silently resolved in the machine's favour.)*
5. **Readback vs approved facts** — `OBSERVATION_CONFLICTING` (ADR-006 §3.2 #8).

### 5.2 The invariant

> ## **While a Conflict is OPEN, the affected field's evidence condition is `conflicting`, and it BLOCKS every consequential action on that entity.**
> *(ADR-002 **C5** — five distinct conditions; **C6** — conflicting or insufficient evidence must block. **Fail closed.**)*

**`conflicting` is not `unknown`.** *We do not lack information — we have too much, and it disagrees.* **I8.** Treating a conflict as merely "missing data" would let a "best available" read slip through; treating it as `conflicting` stops everything, which is correct.

### 5.3 Closure — two ways, and no others

| Way | Requires |
|---|---|
| **`RESOLVED_BY_RULE`** | A **registered, versioned, deterministic rule** with an **id** — *e.g. "for delivery status, the TMS beats the portal."* **Written down, in advance, auditable, and re-runnable.** |
| **`RESOLVED_BY_HUMAN`** | A **`decision_ref`**. |

> ### **There is no third way. Not recency. Not confidence. Not source priority — unless a registered rule says so, with an id. Not a model. Not a timeout.**
> **A Conflict that times out is a Conflict resolved by a clock**, and the clock knows nothing about freight. **`AutoResolve` is an ILLEGAL TRANSITION** (ADR-008 §3.7).

**A Conflict never expires. It ages, and it escalates.**

---

## 6. CORRECTION AND PROPAGATION (F-17) — the part everyone forgets

**A correction that does not propagate is a lie with a timestamp.**

When a `CONFIRMED` claim is **corrected**:

1. Emit `ClaimCorrected{prior, new, decision_ref, provenance_class}`. **The prior claim is retained** — never deleted, never edited (append-only, ADR-008 §2.8).
2. ### **Walk the lineage forward** (ADR-002 §2.1, concern 5: *evidence traversal*) and identify **every canonical field derived from the corrected claim**, and **every effect executed on the basis of those fields**.
3. **Re-derive** the projected fields.
4. For each **completed external effect** now known to rest on a wrong binding: ### **raise a Compensation** (ADR-008 §3.10) — *itself a fully gated effect, with an approval*.
5. Any effect **in flight** on the affected entity: **VOID it** at the checkpoint — the material facts have drifted (**ADR-005 §3.12**).

**Worked example — the whole system in one paragraph:**
> The owner corrects a POD binding: it was load **44718**, not **4471**. But we already invoiced 4471 on the strength of that POD.
> ⇒ The claim is `CORRECTED`. ⇒ The POD-gate evidence for load 4471 evaporates, so 4471's `documented` field is re-derived to **`absent`**. ⇒ **Invoice #560010 rests on a binding that is now known to be wrong** ⇒ a **Compensation** is raised: *"Invoice #560010 (£2,850, Acme) was issued on a POD that turned out to belong to load 44718. It needs to be credited. Approve?"* ⇒ Compensation goes through **the full pipeline** — checkpoint, approval, grant, readback. ⇒ Meanwhile load **44718** is now `documented`, and becomes billable.
>
> **Nothing was silently fixed. Nothing was silently left broken. A human was told, in money.**

---

## 7. IDENTITY PERSISTENCE

A `CONFIRMED` `OWNER_ASSERTED` binding **survives**, unchanged: re-observation of the same document · re-ingestion of the same email · a linker improvement · a **model upgrade** · a **full projection rebuild** · a replay of the entire event corpus.

> **This is the direct, structural answer to Stream B L-A.** The owner's decision is **native state** (ADR-002 §1.2). **A projection rebuild rebuilds projections. It does not rebuild the owner's mind.**

---

## 8. ALTERNATIVES REJECTED

| Alternative | Rejected because |
|---|---|
| **Confidence thresholds authorize binding** | **The single most likely way this architecture gets defeated.** An engineer writes `if confidence > 0.98` and every guarantee above becomes decorative. **`provenance_class` gates; confidence sorts** (§4.2). |
| **Let the model bind directly** (it is usually right) | *Usually right* is the problem statement, not the solution. **The model reads; the linker decides** (§4.1). |
| **Last-write-wins on conflict** | A conflict resolved by **arrival order** is a conflict resolved by **network jitter**. |
| **Source-priority resolution as a default** (TMS always wins) | Fine **as a registered rule with an id** — **not as an ambient default**. The difference is auditability. |
| **Auto-resolve conflicts after N days** | **A clock is not a decision.** It just makes the conflict stop being visible. |
| **Delete superseded claims** | Destroys the evidence chain (**I5**), and makes I3 (*explain it to an angry person*) impossible. |
| **One "fact" table, with a source column** *(the status quo)* | This is **F-04**. It is how a guess ends up stored beside a fact and read by code that cannot tell the difference. |

---

## 9. CONSEQUENCES

1. **F-04 closes** — the vocabulary is now load-bearing, not descriptive.
2. **F-05, F-16, F-17, F-26 close** — counterparty claims cannot authorize; corrections propagate; conflicts block.
3. **L-A and L-B become structurally enforced**, not documented: an illegal transition and an immutable-id binding.
4. **More things will stop and ask a human.** Every one of them is a case where the old system silently guessed. **This will feel like a regression, and it is the opposite of one.**
5. **Cost:** every claim carries provenance + evidence + lineage. **Storage and complexity. Accepted** — this *is* the auditability.
6. **The model becomes cheaper and safer to change.** A better model produces better *proposals*. **It cannot produce more authority.**

---

## 10. FAILURE MODES

| Failure | Behaviour |
|---|---|
| Two `CONFIRMED` bindings for one artifact | **Conflict** ⇒ entity **frozen** ⇒ human. |
| The linker "improves" and disagrees with the owner | ### **ILLEGAL TRANSITION if it tries to overwrite; Conflict if it merely disagrees.** *(This is B3, made impossible.)* |
| An artifact binds to a **cancelled** load | Claim `SUPERSEDED`, artifact → `UNBOUND`, **human owns it.** |
| A correction propagates to an effect that is **`UNKNOWN_OUTCOME`** | ### **Compensation is FORBIDDEN until reality is established** (ADR-006 §3.12). The correction is recorded; **the compensation waits for the human.** |
| Correction storm (one correction invalidates 200 invoices) | **Each raises its own Compensation, each individually gated.** **There is no bulk-undo.** *(A bulk undo is 200 ungated writes with one tap.)* **The owner is shown the aggregate exposure first.** |
| Evidence artifact is deleted/lost | The claim's evidence becomes **`absent`** ⇒ any consequential action on it **blocks** ⇒ Exception. *A claim whose evidence we can no longer show is a claim we can no longer defend.* |
| Model upgrade changes extraction | `MODEL_EXTRACTED` claims are **re-derivable** ⇒ new candidates ⇒ **deterministic match re-runs.** `OWNER_ASSERTED` untouched. |

---

## 11. SECURITY CONSIDERATIONS

- **Inbound content is DATA, never instruction, never authority** (Engineering Principles; ADR-003). A document may **evidence** a claim; it may never **make** one.
- **`provenance_class` is runtime-assigned (R-P1)** and **never settable from inbound content** — *a field describing trust that untrusted input can set is worse than no field at all.*
- **No laundering (R-P2):** `MODEL_INFERRED` cannot become `LINKER_INFERRED` by being cached, re-observed, reconciled, re-serialized, or passed through a function. ### **This is the most adversarially-tested rule in the system** (ADR-008 §5).
- ### **Counterparty authorization claims are FRAUD SIGNALS** (§4.4), not inputs. They block and escalate.
- **A conflict is a security control, not just a data-quality one.** An attacker who injects a competing claim **does not gain control — they gain a frozen entity and a human's attention.** *That is the correct outcome, and it means the attack surfaces itself.*

---

## 12. OPERATIONAL CONSIDERATIONS

- **`AMBIGUOUS` binding rate** is the key onboarding metric: it measures how well the deterministic linker knows *this* customer's data. **It should fall over the first weeks** — and if it does not, the linker rules are wrong, not the owner.
- **Every `AMBIGUOUS` artifact is a human's queue item**, sorted by confidence (§4.2 — its only job) and by **dollar exposure**.
- **Conflict count should be near zero.** A persistent conflict means **two systems genuinely disagree**, which is an **operational** problem in the business, not a bug in Neyma. **Surfacing it is the product.**
- **Correction rate is the trust metric.** A falling correction rate means the linker is learning. **A rising one means we shipped something wrong** — and the propagation machinery (§6) is what stops that from becoming money.

---

## 13. TESTING REQUIREMENTS *(merge-gating)*

| Test | Asserts |
|---|---|
| ### **The B3 regression** | `OWNER_ASSERTED` binding + an inferrer re-run ⇒ **ILLEGAL TRANSITION**, state unchanged, security event emitted. |
| ### **Confidence cannot gate** | `MODEL_INFERRED` at confidence **1.0** ⇒ **still `AMBIGUOUS`**, still blocked, still human-owned. |
| ### **No laundering (R-P2)** | Push a `MODEL_INFERRED` claim through copy / cache / re-observe / reconcile / serialize / cross-process ⇒ **it emerges `MODEL_INFERRED` every time.** |
| **Counterparty cannot authorize** | An inbound email asserting an approval ⇒ `MODEL_EXTRACTED`, **payable blocked**, Exception raised, **fraud signal recorded.** |
| **Ordinal binding (L-B)** | Render an unlinked list, insert a new message, then run `assign unlinked 2` ⇒ **binds the originally-rendered id, or FAILS CLOSED — never the new occupant of slot 2.** |
| **Conflict blocks money** | Open Conflict on a material field ⇒ **every consequential action on that entity is refused.** |
| **No auto-resolve** | Advance the clock on an open Conflict ⇒ **it does not move.** |
| **Correction propagates (F-17)** | Correct a POD binding that an invoice was issued on ⇒ **a Compensation is raised for that invoice**, with the exposure. |
| **Correction cannot compensate an unknown** | Same, but the invoice is `UNKNOWN_OUTCOME` ⇒ **compensation refused; it waits for the human.** |
| **Supersession ≠ correction** | A new TMS rate observation ⇒ **supersedes, no compensation.** A wrong binding ⇒ **corrects, compensation considered.** |
| **Rebuild preserves owner** | Replay the full event corpus ⇒ **every `OWNER_ASSERTED` binding survives byte-identical.** |
| **Evidence traversal** | From any canonical field, walk to the complete evidence chain in one query. |

---

## 14. MIGRATION CONSIDERATIONS

- The existing **email→load linker** (`email_triage.py`) already does **deterministic ID-match first, model fuzzy second, fail-closed** — ### **this is exactly §4.1, and it was built before the ADR existed.** **Keep it. It is the ancestor.** What it lacks is `provenance_class` on the output, and a Conflict path.
- `mailbox_intake`'s routing fields (`hinted_load_id`, `linked_load_ids`, `packet_load_id`) are **proto-bindings with no provenance.** Under this ADR they become **Identity Binding Claims**, and **B3 becomes unrepresentable.**
- **Stream B's B4 (`assign unlinked N to <LOAD>`) is the right feature with the wrong binding** (ordinal, §4.3). It is **`PROMOTE_AFTER_FIXES`, blocked on B3** — and this ADR is what unblocks it.
- **No historical claims to migrate** — bindings are re-derived forward from retained observations. **Any existing owner corrections must be re-captured as `OWNER_ASSERTED`, or they will be silently re-derived as `LINKER_INFERRED`.** *(This is a real migration hazard and must be an explicit step.)*

---

## 15. OPEN QUESTIONS

| # | Question | Status |
|---|---|---|
| **Q1** | **Which deterministic rules are registered for freight identity?** *(MC + date + amount? BOL number? PRO number?)* | **`NEEDS VALIDATION` — customer/domain.** The mechanism (§4.1 step 2) is complete; the rule set is per-customer and is **discovered at onboarding**. |
| **Q2** | **Registered conflict-resolution rules** — *does the TMS always beat the portal on delivery status?* | **`NEEDS VALIDATION` — customer.** Until a rule is registered, **conflicts go to a human.** *(Fail-closed default; the absence of an answer is not a blocker, it is just more human work.)* |
| **Q3** | Should a **repeatedly-corrected linker rule** auto-disable itself? | **DEFERRED — ADR-010 (policy/learning).** ⚠️ **A rule that keeps being wrong is a rule that should stop firing** — but **auto-disabling is itself a machine decision about machine authority**, and it needs its own gate. **Not decided here.** |
