# ADR-001 — The Authority Model: Canonical Operational Projection

**Status:** ACCEPTED — explicit product decision by Rasheed, 2026-07-09.
**Supersedes:** the `NEEDS VALIDATION` deferral in `current-state-reconciliation.md` §4.1 and `operating-model.md` §3.2 / §7.1.
**Layer:** Architecture. Binding on the Target System Architecture Specification.

---

## 1. CONTEXT

The Reconciliation established (`REPO_CONFIRMED`) that Neyma holds **no domain model** — only a document-processing run log — and that every read is a live scrape of an external system. It deliberately refused to resolve **whether Neyma should be authoritative, derived, or mixed**, marking it `NEEDS VALIDATION` (§4.1).

The Operating Model established (§3.2) that **there is no single source of truth in a brokerage** — truth is *distributed*, each system authoritative for a slice — and that the operator's job is to **reconcile** it.

The architecture cannot be written without resolving this. It determines what an entity *is*.

---

## 2. DECISION

**Neyma maintains its own canonical operational state as a *projection*.**

It is **not** a replacement for the TMS, and **not** the global source of truth.

### 2.1 External systems remain authoritative for their domains
- **Email / SMS / phone** — authoritative for **communication**.
- **The TMS** — authoritative for **its operational records** (loads, invoices, payables of record).
- **Banking / accounting** — authoritative for **financial transactions actually settled**.
- **Customer and facility portals** — authoritative for **their portal data** (e.g. the dock appointment).
- **FMCSA / insurers** — authoritative for **authority and insurance**.

### 2.2 Neyma maintains a canonical operational projection
A single coherent operational model that **reconciles information across those systems**. The projection is:
- **Derived** — from observations of authoritative systems.
- **Continuously reconciled** — not a one-time import.
- **Fully auditable** — every value can be traced to what was observed, where, and when.

### 2.3 Field-level provenance is mandatory
**Every field** in the projection preserves:

| Provenance attribute | Meaning |
|---|---|
| **Originating system** | Which authoritative system this value came from. |
| **Originating record** | The specific record/row/message/document within that system. |
| **Observation timestamp** | When we observed it. **Not** when we wrote it. |
| **Confidence** | How sure we are of the read. (May route work; **may never authorize** an action — P4.) |
| **Reconciliation status** | Whether this value is currently consistent, conflicting, unreconciled, or stale. |

### 2.4 Conflict is never silently resolved
When authoritative systems disagree, **Neyma does not choose.** It:
1. **Records the conflict** as a first-class fact, and
2. Routes it through **deterministic reconciliation** (a rule with a right answer) **or human approval** — never a model's judgment (P2, §3.2 of the Principles).

---

## 3. CONSEQUENCES (binding on the architecture)

### C1 — The unit of state is the **field**, not the record
Provenance is per-field, so the projection cannot be modeled as a plain record. Every value is an **attributed cell**: `{ value, source_system, source_record, observed_at, confidence, reconciliation_status }`.
**Cost, accepted knowingly:** larger storage, more complex queries, and less ergonomic internal APIs. This is the price of I3 (*explainable to an angry person*) and I5 (*provenance survives*).

### C2 — The projection MUST be rebuildable from its sources and the event log
**This is the property that makes "derived" true rather than a comfortable fiction.** If the projection cannot be reconstructed, it has silently become authoritative.
**Therefore:** rebuildability is a **tested, enforced invariant**, not an aspiration (§2.1 of the Principles; P9).

### C3 — The projection is **never optimistically updated**
The projection reflects **observed reality**, never *intended* reality. A write to an external system does **not** update the projection; the **verified readback** of that write updates it (P5).
> **Intent lives in the work item. Fact lives in the projection.** Conflating them re-creates a shadow source of truth through the back door.

### C4 — The projection is for **knowing**. The authoritative system is for **acting**.
A consequential action **re-verifies against the authoritative system at the moment of action** — it does not trust the projection's freshness. The projection answers *"what is going on?"*; it never authorizes *"therefore pay."* (P5, P6)

### C5 — Staleness is a first-class state, distinct from unknown and from wrong
"Last confirmed against the authoritative system at T" is a queryable property of every field. **A stale field is not a wrong field, and it is not an unknown field** — but it may not be sufficient for a consequential action.

### C6 — A conflicted field is **unusable** for consequential action until resolved
Fail closed (P6, R10). **You may not bill, pay, or send off a field whose reconciliation status is `conflicting`.** The conflict must be resolved first — deterministically or by a human.

### C7 — This operationalizes I8 at the field level
The Operating Model's invariant — *absent ≠ present-and-consistent ≠ present-and-conflicting* — is exactly the `reconciliation_status` of §2.3. **I8 is no longer a philosophical stance; it is a column.**

### C8 — Scrape-on-every-read is retired
The current system's pattern (Reconciliation §1.1 B — every read is a live browser scrape) is replaced by *observe → project → reconcile*. This changes latency, cost, and concurrency characteristics fundamentally (§27 of the architecture).

---

## 4. OPEN SUB-DECISION — `NEEDS VALIDATION`

**The decision as stated covers state that is *derived from* an external system. It is silent on state that has no external owner.**

Some facts exist **only because Neyma created them**, and no external system holds them:

| Neyma-native state | Who else could be authoritative? |
|---|---|
| **The binding** — that *this* email belongs to *that* load | Nobody. It is Neyma's inference. |
| **The work item** and its accountable owner | Nobody. |
| **The exception** — that something is open, aging, at risk | Nobody. |
| **The conflict record** itself | Nobody. |
| **Learned knowledge and human corrections** | Nobody. |
| **The autonomy policy** | Nobody. |
| **The audit / event log** | Nobody. |
| **An extracted interpretation** — e.g. "the customer verbally approved $300 detention" | The *call* is authoritative for what was said. **The conclusion is Neyma's.** |

**Proposed reading (requires confirmation):** there are **two classes of state**, and they must be architecturally distinguished:

1. **Projected state** — derived, provenanced, rebuildable, never authored. *(This ADR.)*
2. **Neyma-native state** — authored by Neyma, still evidenced and fully auditable, but **not rebuildable from external sources, because it *is* the source.**

**Critical corollary:** an **inference is native state, not projected state.** The binding of an artifact to a load is Neyma's **assertion with evidence** — not a fact read from a system. It must be labelled as such, and it must be **correctable** (P11 — a model's output is a claim, not a fact; P32 — identity is a first-class, escalatable decision).

**Risk if this is not distinguished:** engineers will either try to *derive* things that cannot be derived, or allow native assertions to masquerade as observed facts **without provenance** — which is precisely how a "derived projection" quietly becomes a fabricated source of truth.

---

## 5. WHAT THIS CHANGES IN THE ARCHITECTURE SPEC

| Section | Change |
|---|---|
| **§4 Assumptions & Open Decisions** | The authority fork is **CLOSED**. Two remain open: load-family relationships, credential/session posture. |
| **§6** | Retitled: **The Canonical Operational Projection & Reconciliation Model.** No longer an open fork — now a specification of this ADR. |
| **§8 Entities** | Every entity field carries the provenance envelope (C1). |
| **§9 Evidence** | `reconciliation_status` is the field-level expression of I8 (C7). Staleness added as a state (C5). |
| **§10 Identity** | A binding is **native state, an evidenced assertion** — not an observed fact (§4 above). |
| **§15 Services** | A **Reconciliation** capability becomes a named service with its own state and cadence. |
| **§16 Data** | Attributed-cell storage; rebuildability as a tested property (C2). |
| **§19 Action Pipeline** | Re-verify against authority at the moment of action (C4); refuse to act on `conflicting` fields (C6). |
| **§25 Audit & Replay** | Replay is now a **correctness property** (rebuild the projection), not only a debugging tool. |
| **§27 Performance** | Scrape-on-read retired; projection freshness/staleness budgets replace it (C8). |

---

## 6. ALTERNATIVES REJECTED

- **Neyma as global source of truth.** Rejected: it would make us a TMS replacement, which is a permanent product boundary (Operating Model §7.5) and the reason customers can adopt us without fear.
- **Neyma holds no state (scrape on every read).** Rejected: it is the current design. It makes cross-system correlation impossible, cannot represent a non-event (§4.5), and cannot answer *"what do we know about this carrier?"* without a scrape.
- **Silent last-writer-wins conflict resolution.** Rejected outright: it hides a real problem and moves money on an unexamined assumption (P6, R10).
