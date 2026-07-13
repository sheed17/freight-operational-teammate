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

## 3. CONFIRMED CONSEQUENCES (ADR-001 C2–C8, with nuance)

| # | Confirmed |
|---|---|
| **C2** | **Projected state MUST be rebuildable** from retained source evidence and events. **Native state MUST be replayable and reconstructable from Neyma's own event and audit history — but NOT necessarily from external systems.** *(It is the source; there is nothing external to rebuild it from.)* |
| **C3** | **Intent belongs in commands or work items — never in the projection.** Observed facts enter projected state **only after verification**. |
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
