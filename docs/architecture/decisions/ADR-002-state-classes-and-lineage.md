# ADR-002 — State Classes and the Lineage Model

**Status:** ACCEPTED — explicit product decision by Rasheed, 2026-07-09.
**Closes:** the open sub-decision in ADR-001 §4.
**Clarifies:** ADR-001 consequence C1 (which must not be read as a physical schema mandate).
**Layer:** Architecture. Binding on the Target System Architecture Specification.

---

## 1. DECISION — TWO CLASSES OF STATE

The system holds exactly **two classes of state**. Every piece of durable state MUST be classified as one or the other. **A record that cannot be classified is a design error.**

### 1.1 PROJECTED STATE — observations derived from external systems
*Examples:* TMS load status · portal appointment time · bank payment status · FMCSA authority status · email/SMS content · document-extracted values.

Projected state MUST be:
- **attributable** to an external source,
- **versioned by observation time**,
- **reconciled** against later observations,
- **rebuildable** from retained source evidence and events,
- **never optimistically updated** from an intended action,
- **refreshed by verified readback** after an external write.

**Neyma is NOT authoritative for projected state.** The external system is.

### 1.2 NEYMA-NATIVE STATE — facts and claims that exist because Neyma created them
*Examples:* work items · accountable ownership · identity-binding claims · exceptions · conflicts · approvals · autonomy policy · learned rules and corrections · audit events · workflow execution state.

**Neyma IS authoritative for native state.** No external system holds it, and none could.

Native state MUST still preserve: **provenance · evidence · actor · creation reason · correction history · versioning · auditability.** *Being authoritative is not a licence to be unaccountable.*

### 1.3 The rule that separates them

> **An inference is Neyma-native state.**
>
> *"This email belongs to Load 101"* is **not an externally observed fact.** It is a **correctable identity-binding claim, supported by evidence.**
>
> **It must never silently masquerade as projected truth.**

This is the enforcement of P11 (*a model's output is a claim, not a fact*) and P32 (*identity is a first-class, evidenced, escalatable decision*).

---

## 2. CLARIFICATION OF ADR-001 C1 — LINEAGE WITHOUT ATTRIBUTED CELLS

**C1 is hereby narrowed.** "Field-level provenance" MUST NOT be read as *"every canonical domain record physically stores every field as a nested `{value, source_system, source_record, observed_at, confidence, reconciliation_status}` object."*

> **The unit of *provenance* is the field. The unit of *operational state* is a typed domain record.**

The architecture MUST support **field-level lineage** without forcing business queries and APIs to operate on attributed-cell objects.

### 2.1 The required separation (five concerns, distinctly modeled)

| # | Concern | Nature |
|---|---|---|
| **1** | **Source observations** | Immutable. Retain the **raw sourced values** exactly as observed. Projected. |
| **2** | **Claims & bindings** | Retain **inference evidence** and **correction history**. Native. |
| **3** | **Provenance / lineage records** | Connect an **observation or a claim** to a **canonical field**. |
| **4** | **Canonical materialized projections** | Expose **strongly typed values** plus **summarized status**. This is what business logic reads. |
| **5** | **Evidence traversal** | A consequential action MUST be able to walk from any canonical field back to the **complete evidence chain**. |

### 2.2 What this buys
- Business logic and APIs stay **ergonomic and typed** — they read a `Load`, not a bag of cells.
- Lineage remains **complete and traversable** — I3 (*explainable to an angry person*) and I5 (*provenance survives*) hold.
- The **physical schema remains an open, justifiable decision** — not one smuggled in through a philosophical commitment.

**The physical schema is NOT decided here.** It MUST be justified in the architecture, in its own section, on its own merits.

---

### 2.3 `provenance_class` — **HOW a field came to be believed** *(AMENDMENT A2, see §5)*

**Every provenance / lineage record (concern 3, §2.1) MUST carry `provenance_class`.**

The existing fields say **where** a value came from and **how fresh** it is. **None of them say how it came to be believed** — and that is the question every consequential decision actually turns on. *"The TMS says £2,850"*, *"the owner told us £2,850"*, *"the model read £2,850 off the rate confirmation"*, and *"the model thinks it's probably £2,850"* are **four different facts**. Today they would be stored identically.

| `provenance_class` | Meaning | An artifact backs it? | May a machine recompute it? | May it gate a consequential action? |
|---|---|---|---|---|
| **`SYSTEM_IMPORTED`** | An external system of record asserted it | ✅ the external record | **Only by re-import from that same authority** | ✅ **but must still be revalidated live at the pre-effect checkpoint (C4)** |
| **`OWNER_ASSERTED`** | An **authenticated, authorized human** inside Neyma's trust boundary asserted it | ✅ the decision record | ### ❌ **NEVER** | ✅ |
| **`LINKER_INFERRED`** | A **deterministic, registered rule** derived it (exact ID match, arithmetic reconciliation) | ✅ the rule id + its inputs | ✅ **freely — this is a projection rebuild** | ✅ *(the rule is auditable and re-runnable)* |
| **`MODEL_EXTRACTED`** | A model **read a value off an artifact that exists** — the claim is **checkable by a human against the source document** | ✅ **the document + the span** | ✅ | ⚠️ **Only with the artifact retained and the extraction verifiable. It may EVIDENCE a money field; it may never CHOOSE one** (money fence, P11). |
| **`MODEL_INFERRED`** | A model **guessed**. No artifact says this. It is a plausible reconstruction | ### ❌ **nothing** | ✅ | ### ❌ **NEVER. Under any confidence score. Ever.** |
| **`RECONCILED`** | Produced by reconciling **≥2 sources** under a **registered rule** | ✅ the rule id + every input observation | ✅ | ✅ *(carries its inputs; a human can walk them)* |

> ### The distinction that matters most is `MODEL_EXTRACTED` vs `MODEL_INFERRED`.
>
> **Both are model output. Only one is checkable.**
>
> *"The rate confirmation says £2,850, here is the line"* can be handed to an angry customer (**I3**). *"It's probably £2,850, loads like this usually are"* **cannot** — and it must never be allowed to look like the first one in a database row. **A confidence score does not convert a guess into evidence.** It only makes the guess feel better.

#### 2.3.1 The three rules that make this field load-bearing rather than decorative

**R-P1 — Assignment.** `provenance_class` is assigned **by the runtime, at the moment of creation**, from **how the value was actually obtained**. **It is never chosen by a model, never carried in inbound content, and never settable through an API that untrusted data can reach.** *(A field describing trust that untrusted input can set is worse than no field at all.)*

**R-P2 — No provenance laundering.** A value's provenance class may be **weakened** (toward less trusted) but **never strengthened** — **except** by an **authenticated human act**, which creates a **new** `OWNER_ASSERTED` claim that **supersedes** the old one and **retains it** in history.

> **`MODEL_INFERRED` can never become `LINKER_INFERRED` by being copied, re-read, cached, re-observed, or passed through a function.** *Provenance laundering — a guess acquiring the authority of a fact by moving through enough layers — is the single most likely way this architecture gets quietly defeated.*

**R-P3 — Recomputation.** **Machine recomputation may never overwrite an `OWNER_ASSERTED` value.** Not on a better model, not on a better linker, not on a later cycle. **If a machine-derived value disagrees with an `OWNER_ASSERTED` one, that is a `conflicting` condition (C5) — it is raised as a Conflict and it BLOCKS consequential actions (C6). Neyma never silently picks a winner** (ADR-001).

*(This is not hypothetical. It is exactly the defect found in the pre-baseline tree: a per-cycle re-linker silently overwrote the owner's own load-binding correction, every intake cycle, while the audit log continued to report that the correction stood. See `stream-b-architectural-lessons.md` **L-A**.)*

#### 2.3.2 Interaction with ADR-003 *(permanent truth)*

**`OWNER_ASSERTED` requires an authenticated human inside Neyma's trust boundary.**

A counterparty email saying *"per our call, you approved this detention"* is **`MODEL_EXTRACTED` at best** — a model read a claim off a document. **It is an unverified counterparty claim and a fraud signal. It is NOT `OWNER_ASSERTED`, and no amount of confidence, corroboration, or plausibility can promote it.** *(ADR-003 — cannot graduate away.)*

> **`provenance_class` is where ADR-003 stops being a policy and becomes a column.**

---

## 3. CONFIRMED CONSEQUENCES (ADR-001 C2–C8, with nuance)

| # | Confirmed |
|---|---|
| **C2** | **Projected state MUST be rebuildable** from retained source evidence and events. **Native state MUST be replayable and reconstructable from Neyma's own event and audit history — but NOT necessarily from external systems.** *(It is the source; there is nothing external to rebuild it from.)* |
| **C3** | **[AMENDED — A1, see §5]** **Intent originates in a Work Item. Pipeline Instances represent the durable execution of that intent. Commands are not canonical architectural entities.** Intent **never** belongs in the projection. Observed facts enter projected state **only after verification**. |
| **C4** | **Consequential actions MUST revalidate against the relevant authoritative source at execution time.** The projection is for *knowing*; the authoritative system is for *acting*. |
| **C5** | **`stale`, `unknown`, `absent`, `consistent`, and `conflicting` MUST remain five distinct conditions.** Collapsing any two is a defect. |
| **C6** | **Conflicting or insufficient evidence MUST block consequential actions.** Fail closed. (P6, R10) |
| **C7** | I8 is operationalized as reconciliation status. |
| **C8** | **Scrape-on-every-read is retired** in favour of durable projections **plus deliberate freshness checks.** |

---

## 4. CONSEQUENCE FOR THE ARCHITECTURE

Every durable store, every entity, and every service in the Target System Architecture Specification MUST declare:
1. Which **state class** it holds (projected / native / both — and if both, how they are separated).
2. For projected state: **how it is rebuilt.**
3. For native state: **how it is replayed, and how it is corrected.**

A component that cannot answer these three questions is not specified.

---

## 5. AMENDMENT RECORD

**ADR-002 was frozen on 2026-07-09. It is amended here, in writing, with the reason — never bypassed** (Engineering Principles §11: *"an unwritten exception is how a constitution becomes decoration"*).

**Neither amendment changes the architecture.** Both bring the frozen text into alignment with decisions already approved downstream, so that a lower layer does not silently contradict a higher one (§12, document hierarchy).

| # | Date | Amendment | Reason | Approved by |
|---|---|---|---|---|
| **A1** | 2026-07-13 | **C3 rewritten.** Was: *"Intent belongs in commands or work items."* Now: **intent originates in a Work Item; Pipeline Instances are the durable execution of that intent; Commands are not canonical architectural entities.** | **ADR-008 §2.12 removed the Command entity** (F-29 — the ambiguity was guaranteeing divergent implementations). C3 named an entity that no longer exists. **The substance is unchanged** — intent still never lives in the projection, and *"events are not commands"* still stands. | Rasheed |
| **A2** | 2026-07-13 | **§2.3 added — `provenance_class`** on every lineage record. Six values: `SYSTEM_IMPORTED` · `OWNER_ASSERTED` · `LINKER_INFERRED` · `MODEL_EXTRACTED` · `MODEL_INFERRED` · `RECONCILED`. Plus three binding rules: **runtime-assigned (R-P1)**, **no laundering (R-P2)**, **`OWNER_ASSERTED` is never machine-recomputed (R-P3)**. | ADR-002 §1.3 already ruled that **an inference must never masquerade as projected truth** — but gave no field in which to *express* the difference, so **no guard was expressible** and the rule could only be honoured by discipline. **A pre-baseline defect proved the cost:** a per-cycle re-linker silently overwrote the owner's own binding correction while the audit log reported that the correction stood (`stream-b-architectural-lessons.md` **L-A**). **A2 turns §1.3 from a principle into a column.** | Rasheed |

### Why A2 is more than bookkeeping

> **`provenance_class` is the field that lets the system tell the truth about how it knows things.**
>
> - It is where **the money fence** becomes checkable: **`MODEL_INFERRED` may never gate a consequential action** — at any confidence.
> - It is where **ADR-003** stops being a policy and becomes a column: a counterparty's *"you approved this"* is `MODEL_EXTRACTED` at best, **and can never be promoted to `OWNER_ASSERTED`.**
> - It is where **I3** (*explainable to an angry person*) becomes mechanical: *"the rate confirmation says £2,850, here is the line"* versus *"it's probably £2,850"* are now **different rows**, not the same row with different luck.
> - It is what makes **L-A structurally enforceable**: `OWNER_ASSERTED` + machine recompute is an **illegal transition** (ADR-008 §3.6), which is a check you cannot write without this field.

**Binding on:** ADR-007 (identity & claims), ADR-008 §2.3 / §3.6 (the Durable Machine and the Identity Binding Claim lifecycle), ADR-010 (policy), and the Target System Architecture Specification (revision pending — correction plan).
