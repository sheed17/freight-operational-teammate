# Neyma — Target System Architecture Specification

**Status:** ✅ **CANONICAL — Revision 2 (complete rewrite).** Supersedes Revision 1 (`8c94646`) in full.
**Derived from (authoritative, frozen):** Engineering Principles · Operating Model · Current-State Reconciliation · Freight Discovery · **Semantic Model** · **ADR-001 … ADR-011 incl. amendments A1–A4** · Architecture Review · Correction Plan · Wave 1–4 review records.
**Migration baseline:** `f0e801b4dfd611345ca6c2842e946d58a7512ae5`
**Date:** 2026-07-13

> ### **This document states MECHANISMS, not aspirations.**
> **Every MUST is followed by: the enforcing mechanism · the owning component · the durable state · the failure behaviour · the emitted event · the validating test.**
> **A MUST without a mechanism is a wish. There are none in this document.**

**Reading convention — the MUST block:**

> **M-n.** *The requirement.*
> **Mech:** how it is enforced · **Owner:** which component · **State:** what is durable · **Fails:** what happens when it doesn't hold · **Event:** what is emitted · **Test:** what proves it.

**Language:** `docs/architecture/semantic-model.md`, **used verbatim.** Deprecated terms (`Command`, `CommandIntent`, `run`, `lane`-as-action-class, `commit identity`, `operation_action_claim`, ambiguous `done`) **do not appear in this document** except in §30, where they are listed as migration obligations.

---

# PART I — FRAME

## §1. Purpose, Scope & Non-Goals

**Purpose.** Neyma is an **AI operational teammate for a freight brokerage back office**. It observes the systems the business already runs, forms defensible claims about what is true, proposes work, and — **only through one structurally enforced boundary** — performs external effects in those systems, then reads back to find out what actually happened.

**Scope.** The 11 operational loops of the Operating Model (L1–L11), quote through cash, across the TMS, email, documents, portals, and accounting.

**Non-goals (v1).**
- Neyma is **not** a TMS. **External systems remain authoritative for their domains** (ADR-001).
- Neyma **never** holds TMS credentials where the integration is browser-actuated. `human_established_session_only` — **the human logs in; Neyma attaches.**
- Neyma does **not** price freight. **The sell rate is a human decision** (Operating Model §6).
- Neyma is **not** a distributed system in v1. **Modular monolith** (P36, ADR-004 §2.5).

**The governing sentence of the whole architecture:**

> **Neyma observes an authoritative system it does not own, forms claims it must be able to defend, projects a view it may never act on, and — only after one atomic checkpoint against the live world — spends a single-use grant to touch reality once, and then reads it back to find out what actually happened.**

---

## §2. How to Read This Document

**Document hierarchy (Engineering Principles §12).** Lower layers may never contradict higher ones:

```
Engineering Principles → Product Vision (Operating Model) → ARCHITECTURE (ADRs + THIS DOC)
   → Specifications → Implementation → Code
```

**Within the Architecture layer, the ADRs are the decisions and this document is their integration.** ### **Where this document and an ADR disagree, THE ADR WINS and this document is defective.**

**Evidence documents** (Current-State Reconciliation, Freight Discovery, the reviews) sit **beside** the hierarchy, not inside it. *(Evidence does not command; it constrains.)*

---

## §3. Canonical Vocabulary — **normative by reference**

> **M-1.** Every term in this document MUST carry the meaning defined in `docs/architecture/semantic-model.md`. **No synonym may be introduced.**
> **Mech:** the Semantic Model's Part 4 lexicon is the single source. · **Owner:** architecture governance · **Fails:** a document using a deprecated term is defective and rejected at review · **Test:** `test_spec_uses_canonical_vocabulary` — greps this file for the deprecated list and **fails the build**.

**The twelve terms an implementer must not get wrong:**

| Term | The one-line meaning that matters |
|---|---|
| **Work Item** | The unit of **business responsibility and closure**. ### **Intent originates here.** Always has an accountable human owner. |
| **Pipeline Instance** | **One durable attempt to produce one effect.** ### **The Pipeline Instance IS the command. There is no `Command` entity.** |
| **Observation** | An **immutable** record that a source **said** something, at a time. **Projected.** |
| **Evidence** | The **retained artifact + span** a human would look at to check a claim. ### **Not a claim.** |
| **Claim** | A proposition Neyma **holds**, with `provenance_class` + evidence. ### **NATIVE state. NOT a fact.** |
| **Checkpoint Witness** | Proof the seven-part atomic checkpoint passed. ### **No public constructor.** |
| **Effect Grant** | Permission for **ONE attempt** to touch the world. **Single-use, by database CAS.** ### **Necessary but NOT sufficient.** |
| **Commit Key** | The identity of the **EFFECT** — ### **never the content of the decision. The amount is NOT in it.** |
| **Material Facts Fingerprint** | A hash over **exactly what was rendered to the approver**. **Drift ⇒ the approval is void.** |
| **`provenance_class`** | ### **HOW a field came to be believed.** Six values (§9). |
| **Gate Decision** | One of **four**, ### **NOT NULL** (§20). |
| **Human Brake** | **Admission control** — refuses to *mint* and refuses to *claim*. ### **Never kills a worker.** |

---

## §4. Architectural Assumptions & Open Decisions

| # | Assumption | Source |
|---|---|---|
| **A1** | ### **One transactional relational store** holds machine state, the outbox, the inbox, and the Effect Grant Ledger. **They must share a transaction; therefore they share a store.** | ADR-008 §2.1 |
| **A2** | **Modular monolith.** The actuation runtime is **co-located** in v1. | ADR-004 §2.5 |
| **A3** | ### **Later process separation must not change the Effect Grant contract** — which is why authority lives in the **ledger**, not in a process-local type. **A process boundary confers no privilege.** | ADR-004 §4.4 |
| **A4** | **External systems remain authoritative.** Neyma maintains a **derived, reconciled, fully-auditable projection.** | ADR-001 |
| **A5** | ### **There is no BREAK_GLASS.** An emergency is **a human acting directly in the external system**, which Neyma then **observes and reconciles**. *(An emergency path is a bypass with a nicer name.)* | ADR-004 §2.5 |

**Open decisions:** all are `NEEDS VALIDATION`, all carry a **fail-closed default** (§32). ### **No open question blocks architecture or implementation.**

---

## §5. Requirements Traceability

**Full matrix: §33.**

> ### **No requirement is marked RESOLVED merely because this document states it. RESOLVED requires a named MECHANISM and a named validating TEST.**

---

# PART II — THE MODEL OF REALITY

## §6. Truth & Authority Model

### 6.1 The eight kinds of thing — **and they are eight, not one**

| # | Kind | Class | Authoritative? | Mutable? |
|---|---|---|---|---|
| 1 | **Raw Observation** | Projected | the **source** is | ### **NEVER.** Superseded, never edited |
| 2 | **Evidence** (artifact + span) | Projected | — | immutable, **content-addressed** |
| 3 | **Claim** | ### **NATIVE** | ### **Neyma is** | correctable, supersedable — **with history** |
| 4 | **Projected State** | Projected | ### **the external system is** | rebuildable; **never optimistically updated** |
| 5 | **Materialized Canonical Projection** | Projected | ### **NOT authority — it is for KNOWING** | rebuilt from 1 + 3 |
| 6 | **Neyma-Native State** | Native | ### **Neyma is** | versioned, correctable, event-reconstructable |
| 7 | **Intent** | Native | Neyma + humans | lives in a **Work Item**. ### **NEVER in the projection.** |
| 8 | **Verified External Effect** | both | the external system | immutable record of what we did |

> **M-2.** Projected state MUST be externally sourced, attributable, rebuildable, ### **never optimistically updated**, and updated **only** from a verified observation or a verified readback.
> **Mech:** the projection writer accepts **only** `ObservationBound` or `EffectVerified` events — ### **it has no API that takes a value directly.** · **Owner:** Projection Service · **State:** `projections` · **Fails:** writing a projection from an intent **raises** · **Event:** `ProjectionUpdated{from_observation_id|from_effect_id}` · **Test:** `test_projection_cannot_be_written_from_intent`; `test_full_corpus_rebuild_reproduces_projection`.

> **M-3.** Native state MUST be authored **only** by Neyma or an **authenticated human**, and MUST be event-reconstructable, versioned, correctable, auditable.
> **Mech:** every native write is a Durable Machine transition (§12) through the transactional outbox. · **Fails:** illegal transition ⇒ **raises, persists nothing** · **Test:** `test_native_state_replays_from_events`.

> ### **M-4. An inference is NATIVE state and MUST NEVER masquerade as projected truth.**
> **Mech:** `provenance_class` on every lineage record (§9); the materializer **refuses** a `MODEL_INFERRED` claim as a projected field value. · **Owner:** Lineage Service · **Fails:** raises · **Event:** `IllegalProvenanceWrite` **(security)** · **Test:** `test_inference_cannot_become_projected_truth`. *(ADR-002 §1.3.)*

### 6.2 Authority on conflict

> ### **M-5. On conflict, Neyma NEVER silently chooses.**
> **Mech:** a Conflict machine is raised (§12.7); the field's evidence condition becomes **`conflicting`**, which **blocks every consequential action on that entity**. · **Owner:** Reconciliation Service · **State:** `conflicts` · **Event:** `ConflictRaised` · **Test:** `test_open_conflict_blocks_all_consequential_actions`. *(ADR-001; ADR-002 C6.)*

### 6.3 The five evidence conditions — **and they are five**

> ### **M-6. `absent` · `unknown` · `consistent` · `conflicting` · `stale` MUST remain five distinct conditions. Collapsing any two is a defect.**
> **Mech:** a closed enum on every projected field. ### **There is no boolean `is_known` anywhere in the system.** · **Fails:** a consequential action on a field that is not `consistent` **fails closed** · **Event:** `ConsequentialActionBlocked{condition}` · **Test:** `test_five_conditions_never_collapse`; `test_unknown_is_not_absent`. *(ADR-002 C5/C6; **I8**.)*

### 6.4 The projection is for knowing; the authoritative system is for acting

> ### **M-7. A consequential action MUST revalidate against the authoritative source at execution time. The projection MAY NEVER satisfy the pre-effect freshness check.**
> **Mech:** three **read classes** with **structurally different constructors** (§16.4). ### **A `CONSEQUENTIAL_FRESHNESS_READ` reader's constructor CANNOT ACCEPT a cache path, a cached observation, a stale fallback, or a generic read provider** *(a generic provider is a cache in disguise)*. · **Owner:** Read Layer · **Fails:** no live read ⇒ **no witness ⇒ no effect** · **Event:** `CheckpointFailed{step:3}` · **Test:** ### `test_consequential_read_boundary` — **already in the baseline, proven by NEGATIVE CONTROL** *(injecting a `cache_path` onto the money resolver makes it fail loudly)*. *(ADR-001 **C4**.)*

---

## §7. Tenancy, Users, Roles & Authority

> ### **M-8. `tenant_id` MUST be structurally present — and FIRST — in every record, event, Effect Grant, Checkpoint Witness, credential, adapter call, audit record, cache key, partition key, and consumer lease.**
> **Mech:** `tenant_id NOT NULL`, **the first column of every primary key and every unique index**; the first field of the event envelope; the first parameter of every adapter. · **Fails:** ### **cross-tenant processing is rejected BEFORE any business handler runs** — the inbox dedup key is `(consumer_id, tenant_id, event_id)` and dispatch is **per tenant** · **Event:** `CrossTenantAccessAttempted` — ### **Sev-0, AUTO-ENGAGES A GLOBAL BRAKE** *(a tenant-boundary failure is never one tenant's problem)* · **Test:** `test_cross_tenant_rejected_before_handler`; `test_same_load_number_two_tenants_no_interference`. *(F-12.)*

| Role | May |
|---|---|
| **Policy Owner** *(exactly one named human per tenant — **I1**)* | author/approve/activate policy; graduate autonomy; **release a brake** |
| **Authorized human** | approve actions within their authority; ### **ASSERT an authorization (ADR-003)**; ### **engage a brake, instantly** |
| **Automated detector** | ### **engage or widen a brake; narrow autonomy. NEVER release. NEVER broaden.** |
| ### **Agent / model** | ### **emit a `ProposedIntent`. NOTHING ELSE.** |

> ### **M-9. `OWNER_ASSERTED` requires an authenticated human INSIDE Neyma's trust boundary. A counterparty is never an authority on our decisions.**
> **Mech:** `provenance_class` is runtime-assigned (R-P1) from the authenticated session; ### **inbound content cannot set it.** · **Fails:** an inbound assertion is `MODEL_EXTRACTED` at best, ### **blocks the payable**, and raises a **fraud signal** · **Event:** `FraudSignalRaised{counterparty_authorization_claim}` · **Test:** `test_counterparty_cannot_self_authorize`. *(**ADR-003 — PERMANENT. Cannot graduate away.**)*

---

## §8. Canonical Domain Entities

**Native:** Work Item · Pipeline Instance · Approval · Effect Grant · Checkpoint Witness · Claim / Identity Binding · Conflict · Exception · Expectation · Compensation · Policy · Rule · Brake · Audit Event.
**Projected:** Quote · Customer Order · Brokerage Load · Carrier Movement · Leg · Stop · Document · Customer Invoice · Carrier Payable · Freight Claim · Counterparty.

> **M-10.** Every store, entity, and service MUST declare **(a)** its state class, **(b)** for projected: **how it is rebuilt**, **(c)** for native: **how it is replayed and corrected**.
> **Mech:** a registry; ### **a component that cannot answer these three questions fails a CI check.** · **Test:** `test_every_entity_declares_state_class`. *(ADR-002 §4.)*

> ### **M-11. `counterparty` MUST always resolve to `customer` (owes us) or `carrier` (we owe them). The ambiguous term `party` is FORBIDDEN.**
> **Mech:** the type system — `Customer` and `Carrier` are **distinct types**; ### **there is no `Party` type.** ### **`money_direction ∈ {IN, OUT}` is a required field on every money action class.** · **Fails:** compile error · **Test:** `test_no_party_type_exists`.
>
> ### ***The consignee RECEIVES the goods and usually does NOT pay. Calling them the customer bills the wrong party.***

---

## §9. Evidence, Observation & Provenance

### 9.1 Five distinctly-modelled concerns *(ADR-002 §2.1)*

| # | Concern | Store |
|---|---|---|
| 1 | **Source observations** — the raw sourced values **exactly as observed** | `observations` |
| 2 | **Claims & bindings** — inference evidence + correction history | `claims` |
| 3 | **Provenance / lineage records** — connect an observation or claim to a **canonical field** | `provenance_records` |
| 4 | **Materialized canonical projections** — typed values + summarized status | `projections` |
| 5 | **Evidence traversal** — from any canonical field back to the **complete** chain | index |

> **M-12.** A consequential action MUST be able to walk from any canonical field back to its **complete evidence chain**, **in one query**.
> **Mech:** `provenance_records` indexed by `(tenant, entity, field)`. · **Fails:** an untraceable field **blocks** consequential action · **Event:** `EvidenceChainBroken` · **Test:** `test_evidence_traversal_from_any_field`. *(**I3** — explainable to an angry person; **I5**.)*

### 9.2 `provenance_class` — the six values *(ADR-002 §2.3, Amendment A2)*

| Class | Artifact backs it? | Machine may recompute? | ### May it gate a consequential action? |
|---|---|---|---|
| `SYSTEM_IMPORTED` | ✅ the external record | only by re-import from that authority | ✅ **but still revalidated live at the checkpoint (C4)** |
| `OWNER_ASSERTED` | ✅ the decision record | ### ❌ **NEVER** | ✅ |
| `LINKER_INFERRED` | ✅ rule id + inputs | ✅ freely — **this is a projection rebuild** | ✅ |
| `MODEL_EXTRACTED` | ✅ **the document + the span** | ✅ | ⚠️ **it may EVIDENCE a money field; it may never CHOOSE one** |
| ### `MODEL_INFERRED` | ### ❌ **nothing** | ✅ | ### ❌ **NEVER. At any confidence. Including 1.0.** |
| `RECONCILED` | ✅ rule id + every input | ✅ | ✅ |

> ### **M-13. `provenance_class` is RUNTIME-ASSIGNED (R-P1). Never chosen by a model. Never carried in inbound content. Never settable through an API untrusted data can reach.**
> **Mech:** assigned at creation from **how the value was actually obtained**; ### **the ingest API's type has no provenance field.** · **Fails:** raises · **Event:** `IllegalProvenanceWrite` **(security)** · **Test:** `test_inbound_content_cannot_set_provenance`.
> ### ***A field describing trust that untrusted input can set is worse than no field at all.***

> ### **M-14. NO PROVENANCE LAUNDERING (R-P2). Provenance may be WEAKENED, never STRENGTHENED — except by an authenticated human act, which creates a NEW `OWNER_ASSERTED` claim that supersedes and RETAINS the old one.**
> **Mech:** a total order on trust; the only strengthening transition requires an authenticated actor. · **Event:** `ProvenanceLaunderingAttempted` **(security)** · **Test:** ### `test_no_provenance_laundering` — **push a `MODEL_INFERRED` value through copy, cache round-trip, re-observation, reconciliation, projection materialization, serialization, and a process boundary; assert it emerges `MODEL_INFERRED` every time.**
> ### ***Provenance laundering — a guess acquiring the authority of a fact by moving through enough layers — is the single most likely way this architecture gets quietly defeated. So it gets the most adversarial test in the suite.***

> ### **M-15. Machine recomputation MUST NEVER overwrite `OWNER_ASSERTED` state (R-P3).**
> **Mech:** ### **an ILLEGAL TRANSITION in the Identity Binding Claim machine (§12.6).** · **Fails:** raises, **persists nothing** · **Event:** `IllegalTransitionAttempted` **(security)** · **Test:** ### `test_owner_binding_survives_relinker` *(the B3 regression)*. · **On genuine disagreement:** ### **a Conflict is raised. Neyma does not pick a winner.**

> ### **M-16. `MODEL_INFERRED` MAY NEVER gate a consequential action — at any confidence score.**
> **Mech:** the checkpoint's input type carries `provenance_class` per field and ### **RAISES ON READ** of an inferred field. ### **`confidence` is structurally ABSENT from the checkpoint's inputs — a guard CANNOT read it.** · **Fails:** no witness ⇒ no effect · **Event:** `CheckpointFailed{reason:model_inferred_material_fact}` · **Test:** `test_guess_cannot_gate_money_at_confidence_1_0`.

> ### **Confidence may PRIORITIZE. It may never AUTHORIZE.**
> *There is no threshold — not 0.95, not 0.99, not 1.0 — at which a `MODEL_INFERRED` claim becomes bindable. **A threshold is an engineer choosing, in advance, an acceptable rate of being wrong about someone else's money, and encoding it as a constant nobody revisits.***

---

## §10. Identity & Correlation

### 10.1 Deterministic-first. Always.

> ### **M-17. A binding is CONFIRMED only through deterministic evidence sufficient for its binding class. Candidate count and model confidence NEVER authorize confirmation. A SINGLE WEAK CANDIDATE IS STILL AMBIGUOUS.**
> **Mech:** the confirmation guard reads **only** `(match_method, provenance_class)` — ### **it has no access to a candidate count or a score.** · **State:** `identity_binding_claims` · **Fails:** ⇒ `AMBIGUOUS` ⇒ **Exception, human-owned** · **Event:** `ClaimAmbiguous` · **Test:** `test_single_weak_candidate_is_still_ambiguous`.
> ### ***"It's the only thing it could be" is not evidence. It is a shrug with a number attached.***

| # | Method | `provenance_class` | Auto-confirms? |
|---|---|---|---|
| 1 | **Exact trusted-identifier match** → **exactly one** open entity | `LINKER_INFERRED` | ✅ |
| 2 | **Registered deterministic rule** *(with an id)* | `LINKER_INFERRED` | ✅ |
| 3 | **Reconciliation across ≥2 sources** | `RECONCILED` | ✅ |
| 4 | **Model extraction** — the model **read** an identifier off a **retained artifact** | `MODEL_EXTRACTED` | ### ❌ **It is EVIDENCE. The extracted identifier re-enters at step 1 and is matched deterministically.** |
| 5 | **Model inference** — a guess | `MODEL_INFERRED` | ### ❌ **NEVER ⇒ `AMBIGUOUS` ⇒ human** |
| 6 | **Human assertion** | `OWNER_ASSERTED` | ✅ — ### **and never machine-recomputed** |

> ### **The model's job is to READ, never to DECIDE. The model finds the string; the linker decides.**

**Trusted identifier classes and their collision characteristics** *(this is why "exact match" alone is not enough)*:

| Identifier | Collision risk | Sufficient alone? |
|---|---|---|
| **TMS load number** | low within tenant; ### **HIGH across tenants** | ✅ **within `(tenant, TMS)`** |
| **PRO / BOL number** | medium — carriers reuse and reformat | ⚠️ only with a second corroborator |
| ### **Invoice number** | ### **the TMS may RENUMBER on edit** | ### ❌ **NEVER key idempotency on it** |
| **MC / DOT number** | low — but ### **a broker may pose as a carrier (co-brokering)** | ✅ for identity; ### **NOT for trust** |
| **Email `Message-ID`** | very low | ✅ for **observation** identity |
| ### **Document content digest** | ### **none** | ### ✅ **the strongest identifier we have** |

> **M-18.** A **read-only informational binding** MAY be `MODEL_EXTRACTED`. ### **A CONSEQUENTIAL binding MUST be `LINKER_INFERRED`, `RECONCILED`, `SYSTEM_IMPORTED`, or `OWNER_ASSERTED`.**
> **Mech:** the binding class is declared on the action class; the checkpoint enforces it. · **Test:** `test_consequential_binding_requires_deterministic_provenance`.

### 10.2 Correction vs supersession — **the difference that costs money**

> ### **M-19. SUPERSESSION and CORRECTION are different, and MUST NOT be one verb.**
> **Supersession** — a newer claim replaces an older one. ### **The old one was TRUE when made. Nothing downstream is invalidated.**
> **Correction** — a `CONFIRMED` claim is declared ### **WRONG**. ### **It MUST propagate, and it MAY raise a Compensation.**
> **Mech:** two distinct events, two distinct handlers. · **Event:** `ClaimSuperseded` vs `ClaimCorrected` · **Test:** `test_supersession_raises_no_compensation`; `test_correction_raises_compensation`.

> ### **M-20. A CORRECTION MUST PROPAGATE. A correction that does not propagate is a lie with a timestamp.**
> **Mech:** on `ClaimCorrected`, the Lineage Service **walks the lineage forward**, re-derives every dependent canonical field, identifies **every completed external effect** that rested on them, and ### **raises an individually-gated Compensation for each.** Any **in-flight** effect on the entity is **VOIDED at the checkpoint** (material facts drifted). · **State:** `compensations` · **Event:** `CompensationRequired{exposure}` · **Test:** `test_correction_propagation_end_to_end`. *(F-17.)*

**Correction-of-correction:** fully supported, **append-only** — each supersedes the prior correction, **retains it**, and **re-runs propagation**. ### **History is never rewritten** (**S8**).

**The worked example — the whole system in one paragraph:**

> The owner corrects a POD binding: it was load **44718**, not **4471**. But we already invoiced 4471 on the strength of that POD.
> ⇒ Claim `CORRECTED`. ⇒ 4471's `documented` field re-derives to **`absent`**. ⇒ **Invoice #560010 rests on a binding now known to be wrong** ⇒ a **Compensation** is raised: *"Invoice #560010 (£2,850, Acme) was issued on a POD that belongs to load 44718. It needs to be credited. Approve?"* ⇒ It goes through **the full pipeline** — checkpoint, approval, grant, readback. ⇒ Load **44718** is now `documented`, and becomes billable.
> ### **Nothing was silently fixed. Nothing was silently left broken. A human was told, in money.**

---

## §11. Domain Events

### 11.1 ### **There is NO `Command` entity**

> ### **M-21. Intent originates in a Work Item. Pipeline Instances represent the durable execution of that intent. Events record what occurred. COMMANDS ARE NOT CANONICAL ARCHITECTURAL ENTITIES.**
> **Mech:** the type system has **no `Command` type**. · **Fails:** compile error · **Test:** `test_no_command_type_exists`.
>
> *(ADR-008 §2.12; ADR-002 **C3 as amended (A1)**. ### **Revision 1 of this document MANDATED a `Command` type. That mandate is DELETED — and the code still follows it (`CommandIntent`, 51 uses). See §30.3.** The rule **"events are not commands"** — Engineering Principles — **stands unchanged**: an event says what **happened**; ### **if you want something to happen, create a Work Item.**)*

### 11.2 The canonical event envelope

| Field | Notes |
|---|---|
| ### **`tenant_id`** | ### **MANDATORY. FIRST. The partition key AND the ownership field.** |
| `event_id` | the dedup key, **with tenant** |
| `event_type` · **`event_version`** | ### **versioned from the FIRST event ever written** |
| `schema_version` | the envelope itself |
| `producer` | the component |
| `entity_type` · `entity_id` · `entity_version` | the aggregate |
| **`pipeline_instance_id`** | which attempt |
| **`work_item_id`** | which business obligation |
| **`causation_id`** | the event that **directly caused** this one |
| **`correlation_id`** | the whole business transaction |
| **`evidence_refs[]`** | ### **content-addressed** |
| **`policy_version`** | what was in force |
| `actor` | human id · detector id · `system` |
| `occurred_at` · `recorded_at` | ### **both, UTC** |

### 11.3 Business vs Audit events

**Business Event** — *what happened in the freight world* (`InvoiceIssued`, `LoadDelivered`). Drives projections.
**Audit Event** — *what happened in Neyma, and why* (`ApprovalGranted`, `GrantClaimed`, `CheckpointFailed`, `IllegalTransitionAttempted`).

> **M-22.** Both are **FACTS**. ### **Neither is a command.**
> ### ***Conflating them makes the system's authority impossible to audit — you get a log that says what changed but never who decided.***

### 11.4 Outbox · inbox · upcasters · parking · replay

> ### **M-23. The state transition and the events it emits MUST be written in ONE atomic commit.**
> **Mech:** transactional outbox — `UPDATE machine_state (version++)` **+** `INSERT INTO outbox`, **one transaction**. A relay publishes at-least-once. · **State:** `outbox` · **Fails:** **neither happens** · **Test:** `test_dual_write_kill_between_effect_and_event`.
> ### ***I10 stops being a slogan and becomes a database guarantee.***

> **M-24.** Every consumer MUST have a durable inbox keyed ### **`(consumer_id, tenant_id, event_id)`**, and MUST process the event and insert the inbox row **in one transaction**.
> **Fails:** a duplicate delivery is a **no-op** · **Test:** `test_duplicate_delivery_is_noop`.
> ### ***This is HOW "consumers must be idempotent" is achieved. Previously it was an instruction — and instructions are not mechanisms.***

> **M-25.** Historical events MUST be interpreted through **explicit upcasters** and ### **NEVER rewritten**.
> **Test:** ### **the rebuild test runs against the FULL historical corpus**, not a recent window — *otherwise it passes for eighteen months, then goes permanently red, then gets disabled, which is worse than never having had it.*

> **M-26.** An event referencing a machine that does not exist yet MUST be **parked** — neither dropped nor failed.
> **Mech:** `pending_references`, keyed by the referenced id, arrival sequence + TTL; drained **in arrival order**. · **Fails:** TTL expiry ⇒ ### **an Exception with an accountable owner** *(a permanently dangling reference is a real problem, and it gets a human — not a log line)* · **Test:** `test_dangling_reference_parked_then_drained`.

> ### **M-27. Replay MUST be side-effect free — STRUCTURALLY.**
> **Mech:** ### **replay performs no live revalidation ⇒ it cannot construct a `CheckpointPassed` ⇒ it cannot mint an Effect Grant ⇒ it cannot act.** · **Test:** `test_replay_full_corpus_produces_zero_grants_and_zero_effect_attempts`.
> ### ***The guarantee is a consequence of the capability model, not a discipline to be maintained.*** *(**S7**.)*

---

## §12. Lifecycles & State Machines

### 12.0 The canonical Durable Machine — **no lifecycle invents its own machinery**

| Element | Requirement |
|---|---|
| Identity | `machine_id`, ### **`tenant_id` (first)**, `type` |
| State | an **enumerated set**. `unknown` is legal where the domain admits it (**I7**) |
| Version | monotonic — optimistic concurrency |
| **Transition table** | ### **declarative DATA, not `if` branches**: `(state, event) → (next, guard, emitted)` |
| Guards | deterministic over evidence and state. ### **NEVER model-evaluated** (**P2**) |
| Terminal states | explicitly enumerated |
| **Closure** | ### **an emitted event, NEVER an inference** (**I11**) |
| Timeout | ### **a durable timer emitting `TimerFired`. A timeout is an event, not a background sweep.** |
| **Ownership** | machines representing *work* carry ### **an accountable human owner at all times** (**I1**) |
| **Provenance** | every field carries `provenance_class` (§9) |

> ### **M-28. An event not in the transition table for the current state is an ILLEGAL TRANSITION. It MUST raise, MUST persist NO state change, and MUST emit `IllegalTransitionAttempted` — an audit AND security event.**
> **Test:** `test_every_illegal_state_event_pair_raises`.
> ### ***A silently-ignored illegal transition is how a state machine rots back into a pile of `if` statements.***

**Applies to EVERY transition below — stated once, not repeated:**
**Transaction boundary:** the state change + emitted events + any grant/approval CAS occur in ### **ONE transaction** (§11.4).
**Idempotency:** every transition is keyed by the triggering `event_id` in the consumer inbox — ### **a redelivered trigger is a no-op.**
**Illegal-transition behaviour:** as **M-28**.

---

### 12.1 WORK ITEM — *the unit of business responsibility and closure*

**States:** `OPEN` · `IN_PROGRESS` · `BLOCKED` · `AWAITING_HUMAN` · `ESCALATED` · **`CLOSED` (T)** · **`CANCELLED` (T)**

| From | Trigger | Guard | → | Emits | Actor |
|---|---|---|---|---|---|
| — | `WorkItemCreated` | ### **an accountable human owner is assigned (I1)** | `OPEN` | `WorkItemCreated` | system/human |
| `OPEN` | `PipelineStarted` | ≥1 Pipeline Instance | `IN_PROGRESS` | `WorkStarted` | system |
| `IN_PROGRESS` | `PipelineClosed` | no open pipeline **and the obligation is satisfied** | `CLOSED` | `WorkItemClosed{decision_ref}` | system |
| `IN_PROGRESS` | `PipelineFailed` | **TRANSIENT**, retries remain | `IN_PROGRESS` | `AttemptFailed` | system |
| `IN_PROGRESS` | `PipelineFailed` | ### **PERMANENT**, or retries exhausted | `BLOCKED` | `WorkBlocked{reason}` | system |
| `OPEN`\|`IN_PROGRESS` | `EvidenceMissing` \| `ConflictRaised` | — | `BLOCKED` | `WorkBlocked` | system |
| `OPEN`\|`IN_PROGRESS` | `HumanDecisionRequired` | — | `AWAITING_HUMAN` | `HumanRequested` | system |
| `BLOCKED` | `BlockerCleared` | resolved | `IN_PROGRESS` | `WorkUnblocked` | system |
| `AWAITING_HUMAN` | `HumanDecided` | ### **`decision_ref`** | `IN_PROGRESS` | `HumanDecided` | human |
| any non-terminal | `AgeThresholdCrossed` | — | `ESCALATED` | `WorkEscalated` | system |
| `ESCALATED` | `OwnerReassigned` | new owner present | *(prior)* | `OwnershipTransferred` | human |
| any non-terminal | `CancellationRequested` | ### **`decision_ref`** | `CANCELLED` | `WorkItemCancelled` | human |
| **`CLOSED`** | `ReopenRequested` | ### **`decision_ref`** (§12.14) | `IN_PROGRESS` *(new phase)* | `Reopened{prior_closure_ref}` | human |

**Expiry:** ### **NEVER. Work does not disappear because it got old.** It ages and escalates.
**Retry:** never in place — it **spawns another Pipeline Instance** (1:N).
**Failure:** `BLOCKED` — ### **not terminal. A blocked work item still has an owner.**
**Closure:** ### **requires an explicit closure event with a `decision_ref`. Inactivity is NOT closure** (**I11**).
**Compensation:** a correction invalidating a completed effect ⇒ **Compensation (§12.10)**.

---

### 12.2 PIPELINE INSTANCE — *one durable attempt to produce one effect*

**States:** `PROPOSED` · `POLICY_CHECKED` · `VALIDATED` · `AWAITING_APPROVAL` · `CHECKPOINT` · `GRANTED` · `CLAIMED` · `EXECUTED` · `VERIFIED` · `RECORDED` · `PROJECTED` · **`CLOSED` (T)** · **`REJECTED` (T)** · **`VOIDED` (T)** · **`FAILED` (T)** · ### **`NEEDS_VERIFICATION`** *(non-terminal, human-owned)*

| From | Trigger | Guard | → | Emits |
|---|---|---|---|---|
| — | `IntentProposed` | ### **`ProposedIntent` is INERT DATA — no effect capability.** Commit-key **reservation acquired** (§12.2.1) | `PROPOSED` | `PipelineStarted` |
| `PROPOSED` | `PolicyEvaluated` | ### **gate decision NOT NULL** | `POLICY_CHECKED` | `PolicyEvaluated{policy_version}` |
| `PROPOSED` | `PolicyEvaluated` | policy **DENIES** | `REJECTED` | `PipelineRejected{reason}` |
| `POLICY_CHECKED` | `Validated` | money fence · document fence · evidence `consistent` | `VALIDATED` | `IntentValidated` |
| `POLICY_CHECKED` | `ValidationFailed` | — | `REJECTED` | `PipelineRejected` |
| `VALIDATED` | — | gate = **`HUMAN_APPROVAL_REQUIRED`** | `AWAITING_APPROVAL` | `ApprovalRequested` |
| `VALIDATED` | — | gate = ### **`PERMANENT_HUMAN_ASSERTION_REQUIRED`** *(ADR-003 — an authenticated human **assertion**)* | `AWAITING_APPROVAL` | `ApprovalRequested{permanent_assertion}` |
| `VALIDATED` | — | gate = `AUTONOMOUS_WITHIN_CAPS` **and every cap holds** | `CHECKPOINT` | — |
| `VALIDATED` | — | gate = ### **`FORBIDDEN`** | `REJECTED` | `PipelineRejected{forbidden}` |
| `AWAITING_APPROVAL` | `ApprovalGranted` | approval binds **this** commit key **and this fingerprint** | `CHECKPOINT` | `ApprovalBound` |
| `AWAITING_APPROVAL` | `ApprovalDenied`\|`ApprovalExpired`\|`BrakeEngaged` | — | `VOIDED` | `PipelineVoided{reason}` |
| `CHECKPOINT` | `CheckpointPassed` | ### **ALL SEVEN checks, ATOMICALLY** (§19.2) | `GRANTED` | `EffectGranted{grant_id}` |
| `CHECKPOINT` | `CheckpointFailed` | **any one** fails | `VOIDED` | `PipelineVoided{failed_step}` |
| `GRANTED` | `GrantClaimed` | ### **the atomic CAS succeeded** | `CLAIMED` | `EffectAttempted` |
| `GRANTED` | `GrantExpired`\|`GrantRevoked`\|`BrakeEngaged` | — | `VOIDED` | `PipelineVoided` — ### **nothing happened** |
| `CLAIMED` | `EffectSucceeded` | adapter returned success | `EXECUTED` | `EffectExecuted` |
| `CLAIMED` | `EffectFailedCleanly` | ### **PROVABLY no effect** *(pre-flight rejection)* | `FAILED` | `EffectFailed{proof}` |
| ### **`CLAIMED`** | `OutcomeUnknown` \| crash \| timeout | ### ⚠️ **we cannot prove nothing happened** | ### **`NEEDS_VERIFICATION`** | `OutcomeUnknown{exposure, unknown_reason}` |
| `EXECUTED` | `ReadbackConfirmed` | ### **readback matches the APPROVED material facts** | `VERIFIED` | `EffectVerified` |
| `EXECUTED` | `ReadbackContradicts` | readback ≠ approved | ### **`NEEDS_VERIFICATION`** | `VerificationConflict{unknown_reason:OBSERVATION_CONFLICTING}` |
| `EXECUTED` | `ReadbackUnavailable` | ### **the channel was blind** | ### **`NEEDS_VERIFICATION`** | `VerificationUnavailable{unknown_reason:OBSERVATION_UNAVAILABLE}` |
| `EXECUTED` | `VerificationDeferred` | **declared** async posting, within bound | `EXECUTED` *(durable timer)* | `VerificationDeferred{recheck_at}` |
| `VERIFIED` | `Recorded` | ### **the SAME atomic commit as verify** | `RECORDED` | `EffectRecorded` |
| `RECORDED` | `Projected` | ### **the projection is updated ONLY from verified evidence** | `PROJECTED` | `ProjectionUpdated` |
| `PROJECTED` | `Closed` | — | `CLOSED` | `PipelineClosed` |
| ### **`NEEDS_VERIFICATION`** | `HumanEstablishedReality` | ### **`decision_ref`** | `VERIFIED`\|`FAILED` | `RealityEstablished` |
| ### **`NEEDS_VERIFICATION`** | `LaterObservationProves` | a deterministic observation carrying **our commit key** | `VERIFIED`\|`FAILED` | `RealityEstablished` |
| ### **`NEEDS_VERIFICATION`** | ### **ANY `TimerFired`** | — | ### ⛔ **ILLEGAL TRANSITION** | `IllegalTransitionAttempted` |

> ### **The single most important row in this document is `CLAIMED → NEEDS_VERIFICATION`.**
> ### **Every system that gets money wrong got it wrong by making that arrow point at `FAILED`.**

**Cancellation:** only **before `CLAIMED`** ⇒ `VOIDED`. ### **After `CLAIMED`, cancellation is meaningless — the world may already have changed. Post-claim undo is COMPENSATION, not cancellation.**
**Retry:** ### **NEVER in place. A retry is a NEW Pipeline Instance, SAME commit key, NEW grant, FULL checkpoint (including drift).**
**Reopening:** ### **never** — an attempt is immutable history. **Reopening happens at the Work Item.**
**Failure:** ### **`FAILED` only when PROVABLY no effect occurred. Otherwise `NEEDS_VERIFICATION`. When in doubt, it is NOT failure.**
**Expiry:** grant TTL ⇒ `VOIDED` *(pre-claim, safe)*. ### **`NEEDS_VERIFICATION` NEVER expires.**

#### 12.2.1 The commit-key reservation — ### **the Pipeline Instance IS the reservation**

> ### **M-29. A second proposal for a commit key held by a non-terminal Pipeline Instance MUST NOT create a second pipeline. It is ABSORBED.**
> **Mech:** ### **`UNIQUE (tenant_id, commit_key) WHERE state NOT IN (terminal)`** on `pipeline_instances`. · **Fails:** the second proposal **attaches to the existing instance as evidence** · **Event:** `DuplicateProposalAbsorbed` · **Test:** `test_two_concurrent_proposals_produce_one_card_one_approval`.
> ### ***The owner sees ONE card. An owner shown two cards for the same load will tap both, and be right to.***

---

### 12.3 EXTERNAL EFFECT — *the record of touching the world*

**States:** `GRANTED` · `CLAIMED` · `ATTEMPTED` · **`VERIFIED` (T)** · **`FAILED` (T)** · **`EXPIRED_UNCLAIMED` (T)** · ### **`UNKNOWN_OUTCOME`** *(non-terminal, human-owned)*

| From | Trigger | Guard | → | Emits |
|---|---|---|---|---|
| — | `GrantMinted` | ### **a `CheckpointPassed` witness exists** | `GRANTED` | `EffectGranted` |
| `GRANTED` | `ClaimAttempted` | ### **CAS `GRANTED→CLAIMED` succeeds** *(+ `brake_version` and `policy_version` still current)* | `CLAIMED` | `GrantClaimed` |
| `GRANTED` | `ClaimAttempted` | ### **CAS fails** *(already claimed · expired · revoked · **brake moved** · **policy moved**)* | *(no change)* | `ClaimRefused` — ### **the adapter does NOTHING** |
| `GRANTED` | `TimerFired` | TTL, unclaimed | `EXPIRED_UNCLAIMED` | `GrantExpired` — **nothing happened** |
| `CLAIMED` | `AdapterReturnedSuccess` | — | `ATTEMPTED` | `EffectAttempted` |
| `CLAIMED` | `AdapterRejectedPreFlight` | ### **provably no effect** | `FAILED` | `EffectFailed{proof}` |
| ### **`CLAIMED`** | timeout \| crash \| lost response | ⚠️ | ### **`UNKNOWN_OUTCOME`** | `OutcomeUnknown{exposure, unknown_reason}` |
| `ATTEMPTED` | readback **matches the approved facts** | ### **a HEALTHY channel** (§26.2) | `VERIFIED` | `EffectVerified` |
| `ATTEMPTED` | readback contradicts \| unavailable | — | ### **`UNKNOWN_OUTCOME`** | `VerificationConflict` \| `VerificationUnavailable` |
| ### **`UNKNOWN_OUTCOME`** | `HumanEstablishedReality` \| `LaterObservationProves` | `decision_ref` **or** deterministic proof | `VERIFIED`\|`FAILED` | `RealityEstablished` |

> ### **`UNKNOWN_OUTCOME` MUST carry `unknown_reason ∈ {UNKNOWN_OUTCOME, OBSERVATION_UNAVAILABLE, OBSERVATION_CONFLICTING}`. A transition into it WITHOUT one is an ILLEGAL TRANSITION.**
> *The consequences are identical — freeze, escalate, never retry, never auto-resolve. ### **The question we ask the human is not.***

**Retry:** ### **NEVER.** A new attempt is a **new grant** under the **same commit key** — ### **and the unique index means that if the first one committed, the second CANNOT.** *The retry does not need to be trusted. The database is.*
**Compensation:** ### **FORBIDDEN on `UNKNOWN_OUTCOME`** (§12.10, M-33).

---

### 12.4 APPROVAL

**States:** `REQUESTED` · `GRANTED` · **`CONSUMED` (T)** · **`DENIED` (T)** · **`EXPIRED` (T)** · **`REVOKED` (T)** · **`VOID_ON_DRIFT` (T)** · **`VOID_ON_BRAKE` (T)**

| From | Trigger | Guard | → | Emits |
|---|---|---|---|---|
| — | `ApprovalRequested` | gate ∈ {`HUMAN_APPROVAL_REQUIRED`, `PERMANENT_HUMAN_ASSERTION_REQUIRED`}; ### **material facts fingerprinted** | `REQUESTED` | `ApprovalRequested{fingerprint}` |
| `REQUESTED` | `HumanApproved` | ### **an AUTHENTICATED, authorized human** *(never a model, never a counterparty)* | `GRANTED` | `ApprovalGranted` |
| `REQUESTED` | `HumanDenied` | — | `DENIED` | `ApprovalDenied` |
| `REQUESTED`\|`GRANTED` | `TimerFired` | TTL | `EXPIRED` | `ApprovalExpired` |
| ### **`GRANTED`** | `MaterialFactsChanged` | ### **fingerprint ≠ the fingerprint at approval** | ### **`VOID_ON_DRIFT`** | `ApprovalVoided{drift_diff}` |
| `GRANTED` | `PolicyVersionChanged` | `policy_version` is a **material fact** | `VOID_ON_DRIFT` | `ApprovalVoided{policy}` |
| `GRANTED` | `BrakeEngaged` | — | `VOID_ON_BRAKE` | `ApprovalVoided{brake}` |
| `GRANTED` | `HumanRevoked` | — | `REVOKED` | `ApprovalRevoked` |
| `GRANTED` | `EffectCommitted` | commit key matches; ### **CAS, in the grant-claim transaction** | `CONSUMED` | `ApprovalConsumed` |
| `GRANTED` | `AttemptFailedProvably` | ### **provably no effect** | `GRANTED` | — ### **survives a provably-failed attempt** |
| ### **`GRANTED`** | `AttemptOutcomeUnknown` | — | `GRANTED` *(frozen)* | — ### **MUST NOT be reused until reality is established** |

> ### **M-30. An approval authorizes ONE COMMITTED EFFECT — not one network attempt.**

> ### **M-31. An approval is CONSUMED EXACTLY ONCE.**
> **Mech:** atomic CAS `GRANTED → CONSUMED`, ### **in the same transaction as the grant claim.** · **Fails:** a double-tap finds `CONSUMED` and replies ### ***"already done — invoice 560010, sent at 09:52"* — it does NOT raise, and it does NOT act** · **Test:** `test_double_tap_is_idempotent_not_an_error`.
> ### ***An owner tapping twice because Slack was slow must never be punished with an error, and never rewarded with a second invoice.***

**Multi-step (dual control):** `ApprovalSignature{approval_id, actor_id, signed_fingerprint}`; `REQUESTED → GRANTED` only on **quorum by distinct authenticated actors**. ### **Every signature binds the SAME fingerprint. If a material fact drifts between signature 1 and signature 2, ALL signatures are void and every human signs again.**
### ***A second approver who is shown different facts from the first is not a control. It is two people approving two different things and believing they agreed.***

---

### 12.5 OBSERVATION

**States:** `RECEIVED` · `PARSED` · **`BOUND` (T)** · `UNBOUND` · `CONFIRMED` · **`SUPERSEDED` (T)** · **`UNPARSEABLE` (T)**

| From | Trigger | Guard | → | Emits |
|---|---|---|---|---|
| — | `ObservationIngested` | ### **idempotent upsert on `(tenant, source, external_id, content_digest)`** | `RECEIVED` | `ObservationReceived` |
| — | `ObservationIngested` | ### **the natural key exists and the content is identical** | `CONFIRMED` | ### **`ObservationConfirmed`** — *updates `as_of` only; **NOT a new fact**; ### **does NOT re-trigger work*** |
| `RECEIVED` | `Parsed` | — | `PARSED` | `ObservationParsed` |
| `RECEIVED` | `ParseFailed` | — | `UNPARSEABLE` | → **Exception** |
| `PARSED` | `BindingConfirmed` | ### **deterministic** (§10.1) | `BOUND` | `ObservationBound{provenance_class}` |
| `PARSED` | `BindingAmbiguous`\|`BindingAbsent` | — | `UNBOUND` | → **Exception, human-owned** |
| `UNBOUND` | `BindingConfirmed` | incl. **`OWNER_ASSERTED`** | `BOUND` | `ObservationBound` |
| `BOUND`\|`PARSED` | `NewerObservationSupersedes` | ### **a deterministic rule or a human — NEVER a re-run of the inferrer** | `SUPERSEDED` | `ObservationSuperseded` |

**Mutability:** ### **NEVER.**
**Cancellation:** ### **none — an observation is a fact that arrived. You cannot cancel that the world spoke.**
**Expiry:** never. ### **Freshness (`as_of`) ≠ expiry.** *A stale observation is still a fact; it just stops satisfying a freshness check.*

---

### 12.6 IDENTITY BINDING CLAIM

**States:** `PROPOSED` · `CONFIRMED` · `AMBIGUOUS` · **`REJECTED` (T)** · **`SUPERSEDED` (T)** · `CORRECTED` · `CONFLICTING`

| From | Trigger | Guard | → | Emits |
|---|---|---|---|---|
| — | `ClaimProposed` | carries ### **`provenance_class`** *(runtime-assigned)* | `PROPOSED` | `ClaimProposed` |
| `PROPOSED` | `DeterministicMatch` | ### **exact ID → exactly one entity** | `CONFIRMED` | `ClaimConfirmed{LINKER_INFERRED}` |
| `PROPOSED` | `HumanAsserted` | ### **authenticated**; bound to an **immutable id** | `CONFIRMED` | `ClaimConfirmed{OWNER_ASSERTED}` |
| `PROPOSED` | `ModelReadItOffAnArtifact` | the artifact is **retained**, the span recorded | `PROPOSED` | `ClaimEvidenced{MODEL_EXTRACTED}` — ### **evidence, not confirmation** |
| ### **`PROPOSED`** | ### **`ModelGuessed`** | `MODEL_INFERRED` | ### **`AMBIGUOUS`** | → **Exception.** ### **A guess NEVER auto-confirms — at any confidence.** |
| `PROPOSED` | `MultipleCandidates` \| ### **`SingleWeakCandidate`** | — | `AMBIGUOUS` | → Exception |
| `AMBIGUOUS` | `HumanResolved` | `decision_ref` | `CONFIRMED` | `ClaimConfirmed{OWNER_ASSERTED}` |
| `CONFIRMED` | `RecomputedByInferrer` | provenance = `LINKER_INFERRED` | `SUPERSEDED` | `ClaimSuperseded` — *a legitimate projection rebuild* |
| ### **`CONFIRMED`** | ### **`RecomputedByInferrer`** | ### **provenance = `OWNER_ASSERTED`** | ### ⛔ **ILLEGAL TRANSITION** | ### **`IllegalTransitionAttempted` (security)** |
| `CONFIRMED` | `InferrerDisagrees` | provenance = `OWNER_ASSERTED` | ### **`CONFLICTING`** | ### **`ConflictRaised`** |
| `CONFIRMED` | `HumanCorrected` | `decision_ref`; ### **propagates** (M-20) | `CORRECTED` | `ClaimCorrected` |

> ### **This table is where the pre-baseline B3 defect becomes STRUCTURALLY UNREPRESENTABLE.**
> *A re-linker recomputed load bindings every intake cycle and silently overwrote the owner's own manual correction — while the audit log continued to report that the correction stood.* ### **It could not compile against this table.**

---

### 12.7 CONFLICT

**States:** `RAISED` · `OPEN` · `ESCALATED` · **`RESOLVED_BY_RULE` (T)** · **`RESOLVED_BY_HUMAN` (T)**

| From | Trigger | Guard | → | Emits |
|---|---|---|---|---|
| — | `ConflictDetected` | system-vs-system · claim-vs-claim · claim-vs-observation · ### **inferrer-vs-owner** · readback-vs-approved · ### **rule-vs-rule** | `RAISED` | `ConflictRaised` |
| `RAISED` | `Acknowledged` | owner assigned | `OPEN` | `ConflictOpened` |
| `OPEN` | `DeterministicRuleApplies` | ### **a REGISTERED rule id** *(never a model, never recency)* | `RESOLVED_BY_RULE` | `ConflictResolved{rule_id}` |
| `OPEN` | `HumanResolved` | `decision_ref` | `RESOLVED_BY_HUMAN` | `ConflictResolved{decision_ref}` |
| `OPEN` | `AgeThresholdCrossed` | — | `ESCALATED` | `ConflictEscalated` |
| any | ### **`AutoResolve`** \| `TimerFired` | — | ### ⛔ **ILLEGAL** | `IllegalTransitionAttempted` |

> ### **THE INVARIANT: while a Conflict is OPEN, the affected field is `conflicting` and BLOCKS every consequential action on that entity.** *(ADR-002 C6.)*
**Expiry:** ### **NEVER. It escalates.** *A conflict that times out is a conflict resolved by a clock, and the clock knows nothing about freight.*

---

### 12.8 EXPECTATION — *the non-event problem*

**States:** `RAISED` · **`DISCHARGED` (T)** · `OVERDUE` · ### **`INDETERMINATE`** · **`CANCELLED` (T)** · **`EXPIRED` (T)**

| From | Trigger | Guard | → | Emits |
|---|---|---|---|---|
| — | `ExpectationRaised` | deadline · ### **an observability channel DECLARED** · **a duplicate-prevention key** | `RAISED` | `ExpectationRaised` |
| `RAISED` | `ObservationBound` | the discharging observation matches | `DISCHARGED` | `ExpectationDischarged` |
| `RAISED` | `TimerFired` | deadline passed ### **AND the channel was demonstrably HEALTHY throughout the window** | `OVERDUE` | `ExpectationOverdue` → **Exception** |
| ### **`RAISED`** | `TimerFired` | deadline passed ### **AND the channel was DOWN, or coverage is unknown** | ### **`INDETERMINATE`** | `ExpectationIndeterminate` |
| `OVERDUE`\|`INDETERMINATE` | `ObservationBound` | late arrival | `DISCHARGED` | `ExpectationDischarged{late}` |
| `RAISED` | `DeadlineChanged` | — | `RAISED` *(v++)* | `ExpectationReVersioned` |
| `RAISED`\|`OVERDUE` | `ReasonDisappeared` | e.g. the load cancelled | `CANCELLED` | `ExpectationCancelled` |
| `OVERDUE`\|`INDETERMINATE` | `TimerFired` | terminal age | `EXPIRED` | `ExpectationExpired` → **Exception** |

> ### **M-32. An Expectation MAY transition to `OVERDUE` ONLY where the observation channel was sufficiently observable during the required window. If observability was interrupted, it MUST go to `INDETERMINATE`.**
> **Mech:** an **observation-coverage record** per `(channel, window)`, written by the channel's own health probe. · **State:** `observation_coverage` · **Fails:** ### **no coverage record ⇒ `INDETERMINATE`** *(it fails toward blindness — the safe direction)* · **Event:** `ExpectationIndeterminate` · **Test:** ### `test_deadline_passes_while_channel_down_yields_INDETERMINATE_not_OVERDUE`. *(F-14; **I8**.)*
>
> ### ***"The POD never came" and "we were not watching" are DIFFERENT FACTS. A system that cannot tell them apart will accuse a counterparty of a failure that was ours.***

**Discharge evidence:** the bound Observation, retained.
**Duplicate prevention:** `UNIQUE (tenant, expectation_key)` while non-terminal.
**Timezone:** ### **store instants in UTC; RETAIN the originating business timezone.** ### **Evaluate facility and appointment windows in the FACILITY's local timezone.** *(A 17:00 delivery appointment in Denver is not 17:00 UTC — and a DST boundary is a real freight event.)* · **Test:** `test_appointment_window_evaluated_in_facility_local_time_across_dst`. *(F-25.)*

---

### 12.9 EXCEPTION

**States:** `OPEN` · `ACKNOWLEDGED` · `AGEING` · `ESCALATED` · **`RESOLVED` (T)**

| From | Trigger | Guard | → | Emits |
|---|---|---|---|---|
| — | `ExceptionRaised` | ### **an accountable human owner at creation (I1)** | `OPEN` | `ExceptionRaised{severity, exposure}` |
| `OPEN` | `Acknowledged` | a human saw it | `ACKNOWLEDGED` | `ExceptionAcknowledged` |
| `OPEN`\|`ACKNOWLEDGED` | `Resolved` | ### **REQUIRES `decision_ref`** | `RESOLVED` | `ExceptionResolved{decision_ref}` |
| `OPEN`\|`ACKNOWLEDGED` | `Resolved` | ### **NO `decision_ref`** | ### ⛔ **ILLEGAL** | `IllegalTransitionAttempted` |
| any | `TimerFired` | age | `AGEING` → `ESCALATED` | `ExceptionAgeing` / `ExceptionEscalated` |
| any | ### **`AutoClose`** \| `Inactivity` | — | ### ⛔ **ILLEGAL** | `IllegalTransitionAttempted` |

> ### **An exception closed without a decision is not closed — it is FORGOTTEN.** *(F-30.)*
**Expiry:** ### **NEVER. An exception cannot be outlived.**
**PERMANENT-failure exceptions** *(auth/config — §26.4)*: raised **immediately**, ### **never retried.**

---

### 12.10 COMPENSATION

**States:** `REQUIRED` · `APPROVED` · `EXECUTING` · **`COMPLETED` (T)** · ### **`COMPENSATION_FAILED`** *(non-terminal, human-owned)* · ### **`NOT_POSSIBLE`** *(non-terminal, human-owned)*

| From | Trigger | Guard | → | Emits |
|---|---|---|---|---|
| — | `CorrectionInvalidatedAnEffect` | ### **a `VERIFIED` effect is now known to be wrong** | `REQUIRED` | `CompensationRequired{exposure}` |
| — | `CorrectionInvalidatedAnEffect` | ### **the effect is `UNKNOWN_OUTCOME`** | ### ⛔ **REFUSED — M-33** | `CompensationRefused{unknown}` |
| `REQUIRED` | `HumanApproved` | ### **money-affecting compensation is ALWAYS `HUMAN_APPROVAL_REQUIRED`** | `APPROVED` | `CompensationApproved` |
| `REQUIRED` | `NoCompensatingActionExists` | *the world offers no undo* | ### **`NOT_POSSIBLE`** | `CompensationImpossible{exposure}` |
| `APPROVED` | `PipelineStarted` | ### **its OWN Pipeline Instance — FULLY GATED** | `EXECUTING` | `CompensationStarted` |
| `EXECUTING` | `PipelineClosed` | the compensating effect is **verified by readback** | `COMPLETED` | `CompensationCompleted` |
| `EXECUTING` | `PipelineFailed` \| `NEEDS_VERIFICATION` | — | ### **`COMPENSATION_FAILED`** | `CompensationFailed{exposure}` |
| ### **`COMPENSATION_FAILED`**\|**`NOT_POSSIBLE`** | `HumanEstablishedReality` | `decision_ref` | `COMPLETED` | `RealityEstablished` |
| ### **`COMPENSATION_FAILED`** | any `TimerFired` | — | ### ⛔ **ILLEGAL** | — |

> ### **M-33. COMPENSATION IS FORBIDDEN ON AN `UNKNOWN_OUTCOME`.**
> **Mech:** the guard refuses; the Compensation cannot leave `REQUIRED`. · **Fails:** ### **it WAITS for the human** · **Event:** `CompensationRefused{unknown}` · **Test:** `test_cannot_compensate_an_unknown_outcome`.
>
> ### ***You cannot undo what you cannot prove you did — and a compensating write can CREATE the very state it was trying to remove.*** *"Cancel the invoice" against a TMS where no invoice exists can, in some systems, create a credit note out of nothing.* ### **Resolve to `VERIFIED` or `FAILED` FIRST. Only then may compensation be considered.**

> ### **A COMPENSATION IS AN EFFECT. It passes through the full pipeline — checkpoint, grant, approval, readback. THERE IS NO FAST PATH FOR UNDO.**
> ### ***An "undo" that bypasses the gates is an ungated write with a good excuse.***

**Correction storm:** each invalidated effect raises **its own individually-gated** Compensation. ### **THERE IS NO BULK UNDO** — *a bulk undo is 200 ungated writes with one tap.* **The owner is shown the aggregate exposure first.**
### **`NOT_POSSIBLE` is honest:** *some things cannot be undone — a sent email, a wire.* ### **The system says so and escalates. It does not pretend it compensated.**

---

### 12.11 POLICY · 12.12 RULE

**Policy states:** `DRAFT` · `PROPOSED` · `APPROVED` · **`ACTIVE`** · **`SUPERSEDED` (T)** · **`REVOKED` (T)** · **`EXPIRED` (T)**
**Rule states:** `PROPOSED` · `COMPILED` · `CONFIRMED` · **`ACTIVE`** · **`REJECTED` (T)** · **`SUPERSEDED` (T)** · **`REVOKED` (T)** · **`EXPIRED` (T)**

| From | Trigger | Guard | → | Emits |
|---|---|---|---|---|
| — | `RuleProposed` | ### **a model MAY propose the TEXT** | `PROPOSED` | `RuleProposed` |
| `PROPOSED` | `Compiled` | ### **every referenced field is MODELLED and NON-INFERRED (M-49); the predicate is decidable at checkpoint time; the scope resolves** | `COMPILED` | `RuleCompiled{rule_id}` |
| ### **`PROPOSED`** | ### **`CompilationFailed`** | a referenced field is unmodelled **or `MODEL_INFERRED`** | ### **`REJECTED`** | ### **`RuleNotEnforceable{missing, why}`** — *and the owner is TOLD* |
| `COMPILED` | `ConflictDetected` | vs an active rule | *(blocked)* | ### **`ConflictRaised`** — **fail closed; never auto-merge** |
| `COMPILED` | `HumanConfirmed` | ### **the owner is shown the COMPILED rule AND generated test vectors** | `CONFIRMED` | `RuleConfirmed` |
| `CONFIRMED` | `Activated` | ### **an AUTHENTICATED HUMAN. NEVER a model. NEVER automation.** | `ACTIVE` | `RuleActivated{version}` |
| `ACTIVE` | `Superseded` | a new version | `SUPERSEDED` | `RuleSuperseded` — ### **the old version is RETAINED** *(effects were judged under it)* |
| `ACTIVE` | `Revoked` | ### **immediate if it NARROWS**; the Policy Owner if it **broadens** | `REVOKED` | `RuleRevoked` |

**A policy change is itself an action class with `HUMAN_APPROVAL_REQUIRED`**, through the **ordinary pipeline**, with the **diff** as its material facts. ### **There is no admin path.**
**Effective dates** are supported. ### **A policy is never retroactive — an effect is judged by the version in force AT ITS CHECKPOINT.**
**Expiry:** ### **a NARROWING policy may expire — but its expiry is a BROADENING event and therefore REQUIRES A HUMAN AT EXPIRY.**
### ***Otherwise "temporarily tighten" becomes "automatically loosen later, when nobody is watching."***
**Testability:** ### **every compiled rule ships with generated test vectors** — *"here are three loads this rule WOULD have blocked last month."* ### **A rule whose consequences the owner cannot see is a rule they have not really approved.**

---

### 12.13 BRAKE

**States:** ### **`ACTIVE` · `RELEASED`** — **and no others.**

| From | Trigger | Guard | → | Emits |
|---|---|---|---|---|
| — | `BrakeEngaged` | ### **ANY authenticated human, instantly — OR an automated Sev-0 detector** | **`ACTIVE`** | `BrakeEngaged{scope, actor, reason, brake_version++}` |
| `ACTIVE` | `BrakeWidened` | ### **narrows AUTHORITY ⇒ human OR automation** | `ACTIVE` | `BrakeWidened{brake_version++}` |
| `ACTIVE` | `BrakeNarrowed` | ### **broadens AUTHORITY ⇒ AUTHENTICATED HUMAN ONLY** | `ACTIVE` | `BrakeNarrowed{brake_version++}` |
| `ACTIVE` | `BrakeReleased` | ### **AUTHENTICATED HUMAN ONLY** + the release conditions (§21.6) | **`RELEASED`** | `BrakeReleased{decision_ref, brake_version++}` |
| `ACTIVE` | ### **`TimerFired`** | — | ### ⛔ **ILLEGAL TRANSITION** | `IllegalTransitionAttempted` |

> ### **A brake NEVER expires. A brake that expires releases itself while nobody is looking — and a clock cannot know whether the fire is out.**

**Two states suffice.** *"Engaged by a human"* vs *"engaged by automation"* is an ### **`actor` field, not a state** *(it changes who may release, not what the brake does)*. *"Partially released"* is a ### **scope change, not a state.**
**Record:** `brake_id` · **`tenant_id`** · `scope` · `state` · ### **`brake_version` (monotonic, GLOBAL per tenant)** · `actor` · `engaged_reason` · `engaged_at` · `released_by` · `release_decision_ref` · `released_at`.

---

### 12.14 Generic reopening machinery

> **M-34.** A closure event is **immutable**. Reopening MUST NOT mutate, delete, or rewrite it.
> **Mech:** append-only. `Reopened{prior_closure_ref, reason, decision_ref, actor}` creates **either** a **new work phase** on the same Work Item (`phase_seq++`, prior phase preserved) **or** a **new linked Work Item** (`reopens: <id>`). ### **Same obligation to the same party ⇒ new phase. A materially different obligation ⇒ a linked Work Item.** · **Fails:** reopening without a `decision_ref` ⇒ **illegal transition** · **Test:** `test_reopening_never_mutates_closure`.

> ### **The DOMAIN POLICY of WHEN to reopen is `NEEDS VALIDATION` (§32 V1). THE MACHINERY IS NOT OPTIONAL and exists regardless.**

---

### 12.15 Architectural lifecycle contracts — domain entities

**CONTRACTS, not full tables.** The full tables are written in the **entity specifications** (the next phase). ### **They MUST conform to §12.0 and MUST NOT invent machinery.**

| Entity | State set | Effect points *(each = a full Pipeline Instance)* | Notes |
|---|---|---|---|
| **Quote** | `REQUESTED → PRICED → SENT → ACCEPTED` \| `DECLINED` \| `EXPIRED` | `SEND_QUOTE` | ### **The sell rate is a HUMAN decision** |
| **Customer Order** | `RECEIVED → CONFIRMED → CONVERTED` \| `CANCELLED` | — | The customer's **request**, before it is a Load |
| **Brokerage Load** | `TENDERED → COVERED → DISPATCHED → IN_TRANSIT → DELIVERED → DOCUMENTED → BILLED → PAID` · `CANCELLED` · `TONU` | `BILL_LOAD` | ### **The loop closes at `PAID`, not at `BILLED`** (L8, P24) |
| **Carrier Movement** | `OFFERED → BOOKED → CONFIRMED → PICKED_UP → DELIVERED → INVOICED → SETTLED` · `FELL_OFF` | `BOOK_CARRIER`, `SETTLE_CARRIER` | ### **Carrier trust is a HUMAN decision** |
| **Leg** | `PLANNED → ACTIVE → COMPLETED` · `CANCELLED` | — | a segment of a Movement between two Stops |
| **Stop** | `SCHEDULED → ARRIVED → DEPARTED` · `MISSED` · `RESCHEDULED` | — | ### **the appointment window is evaluated in the FACILITY's local timezone** |
| **Document** | `EXPECTED → RECEIVED → EXTRACTED → BOUND → FILED` · `ILLEGIBLE` · `REJECTED` · `SUPERSEDED` | `FILE_DOCUMENT` | `EXPECTED` **creates an Expectation.** ### **An UNSIGNED BOL is NOT a POD.** |
| **Customer Invoice** | `ELIGIBLE → PREPARED → APPROVED → ISSUED → SENT → PAID` · `SHORT_PAID` · `DISPUTED` · `VOIDED` · `CREDITED` | `RAISE_INVOICE`, `SEND_INVOICE`, `CREDIT_INVOICE` | ### **`ELIGIBLE` is POD-GATED.** Void/credit ⇒ **Compensation** |
| **Carrier Payable** | `INVOICE_RECEIVED → RECONCILED → APPROVED → RECORDED → PAID` · `DISPUTED` · `HELD` · `SHORT_PAID` · `DUPLICATE_SUPPRESSED` | `RECORD_PAYABLE`, `PAY_CARRIER` | ### **An accessorial supported only by a counterparty's authorization claim is `unconfirmed` and BLOCKS** (ADR-003) |
| **Freight Claim** | `RAISED → ACKNOWLEDGED → INVESTIGATING → RESOLVED` · `DENIED` · `ESCALATED` | — | ### **TERM COLLISION: a freight `Claim` (cargo damage) is NOT an evidentiary `Claim` (§3). ALWAYS QUALIFY.** |

---

## §13. The Work Model

**Work Item : Pipeline Instance = 1:N.** ### **Every attempt and every compensation may have its own Pipeline Instance. The Work Item is what the business owes someone.**

> **M-35.** Every Work Item and every Exception MUST have **an accountable human owner, at all times, from creation**.
> **Mech:** `owner_id NOT NULL` at insert. · **Fails:** the insert fails · **Test:** `test_no_ownerless_work_item_can_exist`. *(**I1**. ### **Never null. Never "the system."**)*

---

## §14. Triggers, Time, Expectations & Non-Events

**Triggers:** an inbound Observation · a **durable timer** · a projection change · a human instruction · a completed Pipeline Instance.

> **M-36.** A timeout MUST be a **durable timer emitting `TimerFired`** — ### **never a background sweep**, never a scan for "things that look old".
> **Mech:** `durable_timers` + a relay. · **Test:** `test_no_component_scans_for_staleness`.
> ### ***A sweep is a decision made by a cron job that nobody reviewed.***

**The non-event problem is solved by the Expectation machine (§12.8), and its whole point is `OVERDUE` vs `INDETERMINATE`.**

---

# PART III — THE SYSTEM

## §15. Service Architecture & Boundaries

**Modular monolith. One process (v1). One transactional store. Module boundaries enforced by import-graph rules, not convention.**

```
                    ┌──────────────────── OBSERVE ────────────────────┐
  email · TMS · portals · documents  →  Ingestion  →  OBSERVATIONS
                                                          │
                                     Identity / Claims  →  CONFLICTS
                                                          │
                                     Reconciliation   →  PROJECTION
                                                          │
  ┌───────────────────────────── DECIDE ───────────────────┴──────────┐
     Agents (ProposedIntent ONLY)  →  WORK ITEMS  →  PIPELINE
                                                          │
  ┌───────────────────── THE SAFETY KERNEL ────────────────┴──────────┐
  │   §19   ATOMIC PRE-EFFECT CHECKPOINT   (7 checks, ONE txn)        │
  │              ↓  CheckpointPassed  (no public constructor)         │
  │         EFFECT GRANT LEDGER   ──CAS──▶   CLAIMED                  │
  └───────────────────────────────┬──────────────────────────────────┘
                                  │  grant + witness  (BOTH required)
                           ┌──────▼──────┐
                           │   ADAPTERS  │ ◀── module-private; CI import gate
                           └──────┬──────┘
                                  ▼
                         THE EXTERNAL WORLD
                                  │
                readback (§26) → VERIFIED → RECORDED → PROJECTED
```

> ### **M-37. NOTHING may reach an adapter except the Pipeline.**
> **Mech:** ### **a static import-graph check FAILS THE BUILD if any module outside `pipeline/` imports `adapters/`. NOT SKIPPABLE. NO EXEMPTION LIST.** · **Owner:** CI · **Test:** `test_import_graph_no_module_outside_pipeline_imports_adapters`.

---

## §16. Data Architecture

**One transactional relational store (A1).** Machine state · outbox · inbox · Effect Grant Ledger · checkpoint records — ### **all in one transaction, therefore one store.**

**Tables:** `work_items` · `pipeline_instances` · `effect_grants` · `checkpoint_records` · `approvals` · `approval_signatures` · `observations` · `claims` · `provenance_records` · `projections` · `conflicts` · `exceptions` · `expectations` · `observation_coverage` · `compensations` · `policies` · `rules` · `brakes` · `outbox` · `inbox` · `pending_references` · `durable_timers` · `audit_events`.

### 16.1 ### **The two indexes that carry the architecture**

```sql
-- LAYER 1 — the RESERVATION (protects the owner's attention)
CREATE UNIQUE INDEX pipeline_reservation
    ON pipeline_instances (tenant_id, commit_key)
 WHERE state NOT IN ('CLOSED','REJECTED','VOIDED','FAILED');

-- LAYER 2 — COMMIT-ONCE (protects the money)     ◀── THE GUARANTEE
CREATE UNIQUE INDEX effect_commit_once
    ON effect_grants (tenant_id, commit_key)
 WHERE state = 'CLAIMED';
```

> ### **Layer 2 alone is sufficient for SAFETY. Layer 1 exists so the owner is never shown two cards for the same thing.**
> ### **If Layer 1 is ever bypassed, the database still refuses.**
>
> ### **A Layer-2 refusal in production is a Sev-1: it means something proposed an effect OUTSIDE the pipeline. That is the R-02 signature.**

### 16.2 Retention
Observations · evidence · provenance · events · grants · checkpoints · approvals **(with full canonical payloads)** · audit events — ### **retained PERMANENTLY.** *A grant is the record of **why** an effect was permitted.*

### 16.3 Content addressing
Evidence artifacts are **content-addressed** (`sha256`). ### **The document digest is the strongest identifier we have** (§10.1).

### 16.4 ### **The three read classes — structurally distinguished**

| Class | May take a cache? | MUST return |
|---|---|---|
| `INFORMATIONAL_READ` | ✅ | value **+ a visible `as_of`** |
| `DECISION_SUPPORT_READ` | ✅ | value **+ `as_of` + `stale`** — ### **disclosure is MANDATORY** |
| ### **`CONSEQUENTIAL_FRESHNESS_READ`** | ### ❌ **the CONSTRUCTOR cannot accept a cache path, a cached observation, a stale fallback, or a generic read provider** | a **live** observation with `observed_at`; ### **`None` on failure — NEVER a fallback** |

> **Test:** ### `test_consequential_read_boundary` — **already in the baseline**, and **proven by negative control**: injecting a `cache_path` onto the money-sensitive amount resolver makes it fail loudly.
> ### ***The cache is not unsafe today. It is one plausible line away from being unsafe, and nothing in the code says so — so the TEST says it.***

---

## §17. The Event Backbone

**Transactional outbox → relay → at-least-once publication → durable inbox.** Dedup on `(consumer_id, tenant_id, event_id)`. Upcasters on read. Parking for dangling references. ### **Replay is structurally inert.** *(§11.4.)*

---

## §18. Integration & Actuation Layer

> ### **M-38. An adapter's ONLY public entry point MUST require BOTH an Effect Grant AND a fresh Checkpoint Witness.**
> ```
> execute(grant: EffectGrantHandle, witness: CheckpointWitness, params: EffectParams)
> ```
> **Mech:** signature inspection over the whole `adapters/` package **in CI**. · **Fails:** ### **BUILD FAILURE — an adapter that forgets is a build failure, not a review comment.** · **Test:** `test_every_adapter_entry_point_requires_grant_and_witness`.

**The adapter's validation algorithm — in order, before touching the world:**

1. **Verify the handle signature** *(a cheap filter)*. Fail ⇒ reject.
2. **Load the grant row.** ### **Absent ⇒ Sev-0** *(a well-formed handle naming no row means someone is minting handles).*
3. ### **Validate the witness:** `witness.checkpoint_id == grant.checkpoint_id`, the checkpoint record exists, **and it is within the freshness window.** ### **Stale or mismatched ⇒ REFUSE.** *(The two-key rule, enforced.)*
4. ### **Confusion check** — re-validate the grant against **the adapter's OWN call parameters**: tenant · action class · target system · target resource · operation. ### **ANY mismatch is a Sev-0 SECURITY event, not an error.**
5. ### **CAS `GRANTED → CLAIMED`** *(with `brake_version` and `policy_version` still current)*. ### **Zero rows ⇒ DO NOTHING. Raise.**
6. **Emit `EffectAttempted`** — ### **BEFORE the call**, so an orphan is detectable even if the call never returns.
7. ### **Only now: touch the outside world.**

**Credentials.** ### **Resolvable ONLY inside an adapter, ONLY on presentation of a claimed grant. NEVER reachable by agents, tooling, or even the Pipeline itself.**
**Browser actuation.** `human_established_session_only` + a **browser lock**.

**Verification modes — declared per adapter, per operation, UP FRONT:** `READBACK_VERIFIABLE` · `RECEIPT_VERIFIABLE` · ### **`UNVERIFIABLE`**.

> ### **M-39. An operation whose verification mode is `UNVERIFIABLE` MAY NOT be `AUTONOMOUS_WITHIN_CAPS`.**
> **Mech:** a startup check over the action-class registry. · **Fails:** ### **THE SYSTEM FAILS TO START.** · **Test:** `test_unverifiable_operation_cannot_be_autonomous`.
> ### ***If we cannot check it, a human must be the check.***

---

## §19. The Action Pipeline & The Effect Boundary

### 19.1 The rule

> ### **An external effect can only be produced by an adapter.**
> ### **An adapter can only act when presented with (a) a claimable Effect Grant AND (b) a fresh Checkpoint Witness.**
> ### **An Effect Grant can only be minted by the Pipeline, and only from a passed atomic pre-effect checkpoint.**
>
> ### **There is no admin path. No migration path. No emergency path. No agent path. No replay path. No retry path. No compensation path.**

### 19.2 ### **THE ATOMIC PRE-EFFECT CHECKPOINT**

> ### **M-40. These seven checks MUST occur as ONE atomic decision, in ONE transaction, immediately before the Effect Grant claim.**
> ### **NO asynchronous work may occur between the evaluation and the claim.**
> ### **NO individual result may be cached or reused independently.**

| # | Check | Mechanism | On failure |
|---|---|---|---|
| **1** | **Approval validity** — present, unexpired, unrevoked, correct authority | the `approvals` row + an authority check | no witness |
| **2** | ### **Material-Facts Fingerprint equality** | ### **re-read every material fact LIVE from its authoritative source; recompute under the approval's STORED `fingerprint_version`; compare** | ### **`VOID_ON_DRIFT` + a field-level diff (§21.2)** |
| **3** | **Projected-state freshness** | ### **a `CONSEQUENTIAL_FRESHNESS_READ` — structurally cannot use a cache** (§16.4) | ### **an UNREADABLE source is NOT "no drift" — FAIL CLOSED** |
| **4** | **Native-state validity** | claims unretracted, unsuperseded, **not `conflicting`**; ### **no `MODEL_INFERRED` material fact** | fail closed |
| **5** | **Entity-version concurrency** | re-read `entity_versions`; **any change ⇒ fail** | fail closed |
| **6** | ### **Policy & autonomy authorization** | a deterministic `PolicyDecision` (§20); ### **gate decision NEVER NULL**; caps evaluated against **current** counters | fail closed |
| **7** | ### **Human-brake admission** | the brake state for the scope, ### **in the same transaction** | fail closed |

> ### **ALL SEVEN PASS ⇒ ONE immutable Checkpoint Witness is persisted AND the Effect Grant is claimed, ATOMICALLY.**
> ### **ANY ONE FAILS ⇒ NO authorization capability is persisted.**
> ### **THERE IS NO PARTIAL AUTHORIZATION.**

**Mech:** ### **`CheckpointPassed` has NO PUBLIC CONSTRUCTOR** — it is produced **only** by the checkpoint function, on success. ### **`mint_grant(witness: CheckpointPassed, …)` — code that has not passed the checkpoint CANNOT EXPRESS the call. The type system refuses to compile the bypass.**
**Owner:** Safety Kernel · **State:** `checkpoint_records`, `effect_grants` · **Event:** `CheckpointPassed` / `CheckpointFailed{step, reason}` · **Test:** `test_checkpoint_is_atomic_no_partial_authorization`; `test_no_async_work_between_checkpoint_and_claim`.

### 19.3 The Checkpoint Witness — **binds all of this**

`tenant` · `actor` · **`accountable_owner`** · `action_class` · `target_system` · `target_resource` · `operation` · **`commit_key`** · **`material_facts_fingerprint`** · `entity_versions` · `approval_id` *(when required)* · **`approval_fingerprint`** · **`policy_version`** · **`gate_decision`** · **`autonomy_state`** · ### **`brake_version`** · **`projected_observations_used[]`** · **`native_claims_used[]`** · `created_at` · ### **`expires_at`**

> ### **M-41. A stale Witness is INVALID. An Effect Grant is NECESSARY but NOT SUFFICIENT.**
> **Mech:** the adapter requires **both**; the claim CAS re-checks `brake_version` and `policy_version`. · **Test:** `test_valid_grant_with_stale_witness_is_refused`.
> ### ***A grant answers "may this attempt exist?" — a question about the PAST. It says nothing about whether the world still looks the way it did.***

### 19.4 The stage sequence

```
intent recorded in a WORK ITEM
  → PIPELINE INSTANCE created            (commit-key reservation acquired)
  → early deterministic validation       (money fence, document fence, evidence conditions)
  → APPROVAL REQUESTED when required     ◀── THE HUMAN GATE
  → approval received
  → ### ATOMIC PRE-EFFECT CHECKPOINT (7) ◀── AFTER the human gate. THIS IS F-01.
  → EFFECT GRANT CLAIMED via CAS
  → execution started
  → VERIFICATION per the declared mode
  → outcome durably recorded             (verify + record = ONE commit)
  → external observation ingested
  → PROJECTION updated ONLY from verified evidence
  → WORK ITEM closure evaluated
```

> ### **M-42. The human gate occurs BEFORE the final atomic freshness and concurrency checkpoint. ANY material-fact drift AFTER approval VOIDS the approval and requires RE-ESCALATION.**
> **Mech:** checkpoint step 2. · **Fails:** `VOID_ON_DRIFT` · **Event:** `ApprovalVoided{drift_diff}` · **Test:** ### `test_F01_approve_2850_then_tms_moves_to_3100_no_effect_occurs`.
>
> ### ***Revision 1 of this document revalidated BEFORE the human gate. That would have PAID THE WRONG AMOUNT. It is the defect this architecture exists to prevent.***

> ### **M-43. An approval authorizes ONE COMMITTED EFFECT — not one network attempt.**

### 19.5 Outcome handling — **the complete table**

| Outcome | Effect state | Pipeline | Entity frozen? | Retry the effect? | Human? |
|---|---|---|---|---|---|
| **Provably not executed** | `FAILED` | `FAILED` | no | ### ✅ **a NEW pipeline, same commit key, new grant, full checkpoint** | no |
| **Retryable transient failure** *(pre-claim)* | — | re-checkpoint | no | ✅ bounded, backoff | no |
| ### **Unknown outcome** | `UNKNOWN_OUTCOME` | `NEEDS_VERIFICATION` | ### **YES** | ### ❌ **NEVER** | ### **YES** |
| **Verification deferred** | `ATTEMPTED` + timer | in flight | yes | ❌ | not yet |
| ### **Verification impossible** | `ATTEMPTED` | `CLOSED` **with an honest label** | no | ❌ | ### **at proposal time — the human IS the verification** |
| ### **Observation unavailable** *(blind)* | `UNKNOWN_OUTCOME` | `NEEDS_VERIFICATION` | ### **YES** | ### ❌ | ### **YES** |
| ### **Observation conflicting** | `UNKNOWN_OUTCOME` **+ a Conflict** | `NEEDS_VERIFICATION` | ### **YES** | ### ❌ | ### **YES — urgently. Something else may have acted.** |
| **Failed compensation** | — | `COMPENSATION_FAILED` | ### **YES** | ❌ **never auto-retried** | ### **YES** |
| **Brake engaged** *(pre-claim)* | `EXPIRED_UNCLAIMED` | `VOIDED` | no | after release, ### **via a NEW checkpoint** | no |
| **Policy changed** | — | `VOIDED` | no | via a new checkpoint | re-approval |
| **Entity version changed** | — | `VOIDED` | no | via a new checkpoint | re-approval if material |

### 19.6 The Effect Grant Ledger — **the single capability and commit namespace**

**Binds:** `grant_id` · **`tenant_id`** · `action_class` · ### **`gate_decision` (NOT NULL)** · `target_system` · `target_resource_id` · `target_operation` · **`commit_key`** · **`material_facts_fingerprint`** · `entity_versions` · **`policy_version`** · ### **`brake_version`** · `approval_id` *(### **DB CHECK constraint**: NOT NULL when gate ∈ {`HUMAN_APPROVAL_REQUIRED`, `PERMANENT_HUMAN_ASSERTION_REQUIRED`})* · **`checkpoint_id`** · `pipeline_instance_id` · `state` · `issued_at` · `expires_at` · `claimed_at` · `handle_digest`.

**The token** is **opaque and signed** — ### **and NEITHER property is the security control.**
### **Authority lives in the LEDGER. A forged handle names no row, so the claim fails. A replayed handle attempts to claim an already-`CLAIMED` row, so the CAS fails.**
*(A signature proves **origin**, never **single-use**. A replayed signed bearer token executes twice.)*

### 19.7 ### **THE COMMIT KEY**

```
commit_key = SHA256( "ck_v1" | tenant_id | action_class
                   | target_system | target_resource_id | target_operation
                   | occurrence_key )
```

> ### **M-44. The commit key describes the LOGICAL EFFECT — never the CONTENT of the decision.**
> ### **The amount, rate, or any other mutable value belongs in the MATERIAL FACTS FINGERPRINT, NOT the commit key.**
> **Mech:** the composition above. ### **`approved_amount` is structurally ABSENT.** · **Test:** ### `test_two_proposals_at_different_amounts_share_one_commit_key_and_produce_one_invoice`.
>
> ### **"Bill load 4471" is ONE effect whether it is £2,850 or £3,100.**
> ### **If the amount changes, the approval is VOID (drift) — the effect does not become a DIFFERENT effect.**

**`occurrence_key`** — derived from ### **the WORLD, never a counter** *(a counter would let the system authorize its own repetition)*: the **remittance reference** for a payment · the **carrier invoice number** for a payable · the **content digest** for a document · `""` for an invoice *(an invoice is raised once; a re-issue is a **different action class** after a credit)*.

> ### **M-45. THE FAIL-CLOSED RULE: if you cannot name what makes this occurrence different from the last one, you MAY NOT repeat the effect.**
> **Mech:** a missing required `occurrence_key` ⇒ `REJECTED` at `PROPOSED`. · **Test:** `test_second_payment_without_remittance_reference_is_rejected`.
> ### ***"I don't know why this is a second payment" is a refusal, not a default.***

> ### **M-46. EVERY effect has a commit key. `None` is not a legal value.**
> **Mech:** `commit_key NOT NULL`; the pipeline cannot be created without one. · **Test:** `test_filing_the_same_pod_twice_produces_one_attachment`.

### 19.8 ### ⛔ **THE LIVE IMPLEMENTATION DEFECT — MIGRATION SAFETY TASK #1**

> ### **`_commit_identity` (`src/freight_recon/operation_router.py:335`) is a LIVE DOUBLE-BILLING HOLE in the frozen baseline `f0e801b`.**

```python
def _commit_identity(tenant, lane, intent, amount) -> dict | None:
    if not amount:
        return None                                                  # ⛔ (B)
    return {..., "approved_amount": normalize_money_amount(amount)}  # ⛔ (A)
```

### **(A) The approved amount is IN the commit key.**
Two proposals to bill load 4471 — one that read **£2,850**, one that read **£3,100** — produce ### **two DIFFERENT commit keys.** ### **Commit-once does not fire. BOTH COMMIT. The customer is invoiced twice, for two different amounts.**

> ### **Commit-once fails in precisely the case it exists for** — the amount is ### **the field MOST LIKELY to differ between two racing reads**, so it is the **worst possible** component of an effect's identity.

### **(B) No amount ⇒ no commit key ⇒ NO commit-once protection AT ALL.**
### **Filing a POD, flipping a status, updating a load — none of them have duplicate protection today.**

**The root confusion:** the key was built from ### **the CONTENT of the decision** instead of ### **the IDENTITY of the effect.** *(§19.7 corrects it. The amount is a **material fact**, bound in the fingerprint. It is not an identity.)*

> ### **THIS IS MIGRATION SAFETY TASK #1 (§30.1). It is not fixed in this document; no implementation code is written here.**

### 19.9 Structural enforcement of the single-effect boundary — **six layers**

| # | Layer | Mechanism |
|---|---|---|
| 1 | **Type** | ### **`CheckpointPassed` has no public constructor.** Code that has not passed the checkpoint **cannot express** a call to mint. |
| 2 | **Module** | ### **Adapter constructors are module-private.** The registry is reachable only from `pipeline/`. |
| 3 | **CI** | ### **Import-graph gate: no module outside `pipeline/` imports `adapters/`. NOT SKIPPABLE. NO EXEMPTION LIST.** |
| 4 | **Database** | ### **The CAS, and `UNIQUE (tenant, commit_key) WHERE state='CLAIMED'`. The database is the final arbiter of "may this act."** |
| 5 | **Runtime** | ### **Orphan detection** — every `EffectAttempted` must have a matching CLAIMED grant + a live pipeline. ### **An orphan is a Sev-0 and AUTO-ENGAGES THE BRAKE** for that tenant + action class. |
| 6 | **Credential** | resolvable only inside an adapter, only on a claimed grant. |

> ### **M-47. NO privileged bypass exists for: agents · admin tools · migrations · retries · compensation · background workers · replay.**
> **Mech:** all six layers. **Migrations use a `MIGRATION` action class with its own positively-asserted gate.** **Replay cannot construct a witness.** · **Test:** `test_no_bypass_for_any_of_the_seven`.
>
> ### ***Adapters cannot be "quickly called" from a script. This will be experienced as friction. THAT FRICTION IS THE FEATURE — it is the same friction that would have prevented R-01.***

---

## §20. Guardrails & The Safety Kernel

### 20.1 ### **The gate decisions — four, NOT NULL**

| Gate | Meaning | Graduatable? |
|---|---|---|
| **`HUMAN_APPROVAL_REQUIRED`** | needs an Approval bound to the material facts | ### ✅ **yes — this is POLICY, and policy evolves** |
| **`AUTONOMOUS_WITHIN_CAPS`** | may proceed with no human ### **iff every cap holds** | — |
| ### **`PERMANENT_HUMAN_ASSERTION_REQUIRED`** | requires an **authenticated human ASSERTION** of a fact the system cannot observe | ### ❌ **NEVER. This is a PERMANENT TRUTH.** |
| ### **`FORBIDDEN`** | ### **may never be performed. By anyone. No approval unlocks it.** | ❌ |

> ### **M-48. Every action class carries EXACTLY ONE gate decision. Null, missing, default, inherited-by-accident, and implicit gate decisions are FORBIDDEN.**
> **Mech:** a startup registry check. · **Fails:** ### **THE SYSTEM FAILS TO START.** · **Test:** `test_action_class_without_gate_fails_startup`.
>
> ### ***F-20 dies at BOOT, not at runtime. The most dangerous action in the system must not be the one nobody remembered to think about.***

**The permanent set (today, exactly one member):** ### **any action whose correctness depends on an undocumented authorization** ⇒ `PERMANENT_HUMAN_ASSERTION_REQUIRED` **(ADR-003)**.
*A counterparty saying "per our call, you approved this detention" is an unverified counterparty claim and a **fraud signal** — **not** authorization. **Only an authenticated human may assert it.***
**The `FORBIDDEN` set (today):** ### **EMPTY — and an empty set is a POSITIVE ASSERTION, not an oversight.**

> ### **Money-out requiring a human is CURRENT PRODUCT POLICY (Operating Model §7.6). It is NOT a permanent truth, and this document does NOT silently promote it into one.**

### 20.2 The seven concepts — **not collapsed**

**Principle** *(a human commitment; amended in writing, never bypassed)* · ### **Permanent Product Truth** *(enforced in **CODE**; **nobody** may change it — not the owner, not Neyma, not a policy)* · **Product Policy** *(Neyma's **ceiling**; enforced in **CONFIG**; evolvable in writing)* · **Tenant Policy** *(### **may only NARROW the product ceiling — never broaden it**)* · **Rule** *(registered, versioned, deterministic, **with an id**)* · **Constraint** *(### **not evaluated — ENFORCED**: a DB constraint, an illegal transition, a type)* · ### **Organizational Knowledge** *(**non-authoritative memory. It has no authority to override, because it has no authority at all.**)*

### 20.3 ### **A policy may never branch on a guess**

> ### **M-49. A policy predicate MAY ONLY read deterministic inputs. It MAY NEVER branch on a `MODEL_INFERRED` value — at any confidence, including 1.0.**
> **Mech:** the evaluator's input type carries `provenance_class` per field and ### **RAISES ON READ** of an inferred field. ### **A rule referencing one FAILS TO COMPILE.** ### **`confidence` is not an input at all — a guard CANNOT read it.** · **Fails:** compile failure / no witness · **Event:** `RuleNotEnforceable` / `CheckpointFailed` · **Test:** `test_policy_cannot_branch_on_model_inferred`; `test_evaluator_input_type_has_no_confidence_field`.
>
> ### ***This is what stops the entire architecture being defeated by one `if confidence > 0.98` written by a well-meaning engineer at 6pm.***

### 20.4 Policy evaluation — inputs and output

**Inputs:** tenant · actor · accountable owner · action class · target system · target resource · counterparty · value · ### **`money_direction` (IN/OUT — never ambiguous)** · workflow · entity versions · material facts · ### **the `provenance_class` of every material fact** · ### **the `evidence_condition` of every material fact** · policy version · autonomy state · ### **open conflicts** · open exceptions · approval state · `now` **(the DB clock)** · applicable caps.

**Output — `PolicyDecision`** *(a **value**, not an entity)*: ### **`gate_decision` (NEVER NULL)** · `decision` · `policy_version` · `rules_evaluated[]` · `rules_matched[]` · `rules_rejected[]` · `caps_applied[]` · ### **`reason` (MANDATORY, ALWAYS — including on PERMIT)** · `security_signals[]` · `escalation_required`.

> **M-50.** Given the same inputs and the same `policy_version`, evaluation MUST produce a ### **byte-identical** `PolicyDecision`.
> **Test:** `test_policy_evaluation_is_deterministic_and_reproducible`.
> ### ***A decision we cannot re-derive is a decision we cannot defend.*** *(**I3**.)*

> ### **M-51. The model has NO role in the final evaluation. It may PROPOSE rule text. It may never evaluate, activate, broaden, reinterpret, or resolve policy.**
> **Test:** `test_model_cannot_activate_or_resolve_policy`. *(**P2**.)*

### 20.5 Rule compilation — ### **two honest outcomes, and no third**

> ### **M-52. A natural-language instruction MUST either:**
> ### **(A) compile into a structured, validated, scoped, versioned, testable rule — or**
> ### **(B) be stored honestly as non-authoritative organizational memory, AND THE OWNER MUST BE TOLD IT IS NOT AN ENFORCED RULE.**
> ### **The system MUST NOT claim a procedure was installed when no deterministic rule exists.**
> **Mech:** the compilation pipeline (§12.11) — parse *(a model may propose)* → ### **validate deterministically** → conflict-detect → ### **human confirmation, shown the compiled rule AND its generated test vectors** → activate. · **Fails:** compilation failure ⇒ ### **Outcome B, WITH an explanation of exactly what is missing** · **Event:** `RuleNotEnforceable{missing}` · **Test:** ### `test_uncompilable_instruction_reply_does_not_claim_a_rule_was_installed` — **asserts on the LITERAL reply text.**
>
> ### ***"📋 Noted the procedure" is FORBIDDEN unless a rule actually compiled and activated.***
> ### ***The honest failure sentence is: "I can't enforce that. Here's why, and here's what I'd need." That is a better answer than a false yes — and the owner can act on it.***

**Worked:**

| Owner says | Outcome |
|---|---|
| *"Never bill without a POD."* | ### **A — a real rule.** A precondition on `RAISE_INVOICE`: `pod.evidence_condition == consistent` **and** `pod.provenance_class ∈ {SYSTEM_IMPORTED, OWNER_ASSERTED, MODEL_EXTRACTED-with-artifact}`. ### **A `MODEL_INFERRED` POD ⇒ DENY. An "inferred" POD is not a POD.** |
| *"Do not use Carrier X for produce."* | ### **B — it CANNOT compile.** `commodity` is not a modelled field. **The owner is told:** *"I can't enforce that — I don't track commodity type on a load. I've saved it as a note. To make it a real rule I'd need commodity as a field."* ### **An honest refusal that surfaces a FEATURE REQUEST — instead of a silent "noted" and then booking Carrier X for a load of lettuce.** |
| *"Customer Y requires hourly updates."* | ### **A — via the EXISTING Expectation machine** (§12.8). **No new primitive.** ### **It gates nothing; it OWES something.** |
| *"Require manager approval under 12% margin."* | ### **CONDITIONAL.** Compiles **only if margin is deterministic**. If the carrier cost is a model estimate ⇒ ### **REFUSES TO COMPILE (M-49).** *"I can enforce this where I have a real carrier rate. Where I'd have to estimate the cost, I'll escalate to you rather than guess at the margin."* |

### 20.6 Autonomy — ### **the one-way ratchet**

> ## **M-53. Automation may only ever move authority in the SAFE direction.**
> ## **It may NARROW autonomy automatically. It may NEVER BROADEN autonomy automatically.**
> **Mech:** graduation is ### **itself an action class with `HUMAN_APPROVAL_REQUIRED`**, whose material facts are the evidence below. **Narrowing triggers require no human.** · **Test:** `test_automation_can_only_narrow` *(a property test over EVERY automated path)*.

**Graduation evidence:** supervised execution history ### **in this exact scope** · ### **ZERO wrong actions — not a low rate, ZERO** *(a single wrong money action is a customer relationship, and there is no acceptable non-zero rate for it)* · minimum sample size *(`NEEDS VALIDATION`, proposed **≥100**)* · escalation precision · verification success rate · ### **an unknown-outcome rate of ~0** *(an action class that regularly cannot be verified must NEVER be autonomous — there would be nobody watching when it goes unknown)* · counterparty scope · **value cap** · **frequency cap** · **time window** · **a named accountable owner**.

**Autonomy expiry NARROWS:** at expiry, the action class reverts to `HUMAN_APPROVAL_REQUIRED` and must be **re-graduated by a human**.
### **The clock may TAKE authority away. The clock may never GIVE it.**

**Automatic narrowing triggers:** any wrong action · a rising unknown-outcome rate · a verification-failure breach · repeated drift-voids *(a flapping source)* · an open Conflict in scope · ### **a fraud signal** · a cap breach · integration degradation · ### **an orphan adapter invocation (Sev-0)**.
**Narrowing is graduated:** `AUTONOMOUS_WITHIN_CAPS` → *reduced caps* → `HUMAN_APPROVAL_REQUIRED` → ### **the Brake.**

### 20.7 ### **Policy precedence — deterministic, no ties**

```
1. CONSTRAINT                 — cannot be violated. Enforced, not evaluated.
2. PERMANENT PRODUCT TRUTH    — ### nothing below may override it. Not a policy. Not a human. Not an emergency.
3. HUMAN BRAKE                — admission control. Denies regardless of everything below.
4. PRODUCT POLICY             — the ceiling.
5. TENANT POLICY              — ### may only NARROW #4.
6. STANDING RULES
7. WORKFLOW DEFAULT           — ### and it is NEVER autonomous.
```

**Within a layer:** ### **the NARROWER scope wins** *(specificity is intent)*. **A customer rule beats a workflow default.** **An expired instruction has no force** — *it is not "weaker"; it is not a rule.*

> ### **Two genuinely conflicting standing rules ⇒ FAIL CLOSED ⇒ a CONFLICT (§12.7) ⇒ the field is `conflicting` ⇒ the action BLOCKS ⇒ a human resolves it. NEYMA NEVER PICKS A WINNER.**

> ### **M-54. A direct human instruction may override a standing rule FOR ONE BOUNDED INSTANCE ONLY — with authority, bound to exactly ONE commit key, single-use, and explicitly recorded. IT NEVER REWRITES THE STANDING RULE. It can NEVER cross layers 1–3.**
> **Event:** `PolicyOverridden{rule_id, actor, reason, decision_ref, commit_key}` — ### **audit AND security.** · **Test:** `test_override_is_single_use_and_leaves_the_rule_unchanged`.
>
> ### ***An override that silently edits the rule is how a one-time exception becomes the new default, and nobody remembers deciding.***

**A repeatedly-overridden rule ⇒ an Exception to the Policy Owner:** *"you have overridden this rule 6 times this month — should it change?"* ### **The system does NOT change it. IT ASKS.** *(Auto-disabling is a machine decision about machine authority.)*

---

## §21. Human Approval, Escalation & The Oversight Surface

### 21.1 The Material Fact Set

> ### **M-55. The material fact set is EXACTLY what was rendered to the approver, plus the identity of the effect.**
> ### **If it was on the card, it is material. If it was material, it must have been on the card.**
> ### **Anything the human could not see cannot be a fact they approved.**

**Includes:** tenant · action class · target *(system + resource + operation)* · commit key · ### **amount as INTEGER MINOR UNITS + ISO-4217** · counterparty identity · entity reference · bound document ids **+ content digests** · ### **the `evidence_condition` of every material field** · ### **the `provenance_class` of every material field** · policy version · entity versions · fingerprint version.
**Excludes:** cosmetics · thread ids · ### **confidence scores** *(a confidence score is not a fact)*.

> ### **M-56. `provenance_class` is INSIDE the fingerprint. The same number, believed for a different reason, is a DIFFERENT FACT.**
> **Test:** `test_same_amount_changed_provenance_voids_the_approval`.
> ### ***This closes the "swap the evidence, keep the number, keep the approval" laundering route.***

**Canonical serialization `fp_v1`:** UTF-8 **NFC** · a flat, **bytewise-sorted** key list · ### **money as INTEGER MINOR UNITS — FLOATS ARE FORBIDDEN** *(`2850.00` and `2850.0` are the same money and different bytes — that is a defect waiting to be a double-payment)* · RFC-3339 **UTC**, **exactly millisecond** precision · ### **`null` and `absent` are DISTINCT and both EXPLICIT** · enums **by name, never ordinal** · **raw strings — no trimming, no case-folding, no locale collation** · ### **the version is INSIDE the hashed bytes** (`fp_v1\n` prefix).

> ### **M-57. We store the FULL canonical payload, not just the hash.**
> **Mech:** `approvals.canonical_payload`, retained permanently. · **Test:** `test_drift_explanation_names_the_changed_field_old_and_new`.
> ### ***A hash proves THAT something drifted. It can NEVER say WHAT. You cannot diff a hash — and the owner needs the diff.***

### 21.2 The drift explanation — a **required output**, not a log line

> ### *"I did not invoice load 4471.*
> ### *When you approved it 41 minutes ago, the amount was **£2,850** (read from the TMS invoice screen at 09:14).*
> ### *It is now **£3,100** (same source, read just now).*
> ### *Nothing has been sent. Do you want me to invoice £3,100?"*

> ### **M-58. A system that blocks an action it cannot explain has merely relocated the owner's problem.** *(**I3** applies to REFUSALS, not only to actions.)*

### 21.3 Scope · partial approvals · expiry · replay

**Scope:** ### **one approval = one commit key = one committed effect.**
A batch `[Approve all 7]` mints ### **SEVEN approvals**, each with its own fingerprint, in one transaction. ### **It is NOT one approval covering seven effects.** *(If load 3 has drifted, loads 1, 2, 4–7 still execute and load 3 comes back as a new question — and **one tap never silently authorizes a fact the owner never saw**.)*

> ### **PARTIAL APPROVALS DO NOT EXIST.** *"Approve it, but for £2,700"* is ### **a NEW proposal with a NEW fingerprint.**
> ### ***A partial approval is agreement to a fact set the system assembled AFTER the human looked — which is F-01 wearing a friendlier interface.***

**Expiry:** money-out **1h** · money-in **8h** · documents/status **24h** *(all `NEEDS VALIDATION` — §32 V2)*. Fired by a **durable timer**.
### **An expired approval is not a weaker approval. It is not an approval.**

**Replay protection — two layers, because the transport and the authority are different things:**
1. **Transport:** a **single-use HMAC token** bound to `(approval_id, channel, thread, user)`.
2. **Authority:** the ### **`GRANTED → CONSUMED` CAS**, in the grant-claim transaction.

### 21.4 The Human Brake — **admission control**

> ### **M-59. The brake is ADMISSION CONTROL, not process termination. It is enforced by REFUSING TO MINT and REFUSING TO CLAIM — NEVER by killing a worker.**
> **Mech:** checkpoint step 7 **and** the claim CAS's `brake_version` predicate. · **Owner:** Safety Kernel · **State:** `brakes` · **Test:** ### `test_engaging_the_brake_during_an_adapter_call_does_not_create_an_unknown_outcome`.
>
> ### ***A brake that kills workers MANUFACTURES the exact thing the architecture fears most: an `UNKNOWN_OUTCOME`. You would engage it to become safer and, in the very act, create a payable of unknown status.***

**When engaged, within scope:**

| | |
|---|---|
| ### **No new Effect Grant may be MINTED** | step 7 fails ⇒ no witness ⇒ nothing to mint from |
| ### **No existing Effect Grant may be CLAIMED** | the CAS's `brake_version` predicate fails ⇒ **zero rows** |
| **No Pipeline Instance may enter execution** | it halts at `CHECKPOINT`, **durably** |
| **Pending approvals remain RECORDED** | ### **not deleted, not denied — they simply cannot authorize execution** |
| **Queued work remains DURABLE** | ### **Nothing is lost. The brake is a pause on ACTING, not on KNOWING.** |
| **Observation & reconciliation CONTINUE** | ### **by default — blinding yourself during an incident is the opposite of what you want** *(they may be disabled by a separate, narrower control)* |
| ### **Effects already executing CONTINUE through verification and durable recording** | §21.5 |
| **All in-flight effects are SURFACED** | §21.6 |

### 21.5 ### **The in-flight boundary — five positions**

| Position | Ledger | World changed? | ### Brake behaviour |
|---|---|---|---|
| **1. Not yet executing** | none | ### **NO** | ### **STOP.** Halt durably. **Nothing happened.** |
| **2. Grant MINTED, UNCLAIMED** | `GRANTED` | ### **NO — the adapter never acted** | ### **STOP.** Revoked ⇒ `EXPIRED_UNCLAIMED`; pipeline `VOIDED`. **Safe.** |
| **3. CLAIMED, adapter not yet called** | `CLAIMED` | ⚠️ **we cannot prove it didn't** | ### **DO NOT KILL.** Let it complete and verify. |
| ### **4. Adapter called, response pending** | `CLAIMED` | ### ⚠️ **POSSIBLY — this is the money** | ### **DO NOT KILL. LET IT FINISH AND VERIFY.** *Killing here converts a knowable outcome into an unknown one.* |
| **5. Verification in progress** | `ATTEMPTED` | yes — and we are finding out what | ### **LET IT FINISH.** *Verification is a READ. The brake has no reason to stop a read.* |

> ### **The brake stops the NEXT effect. It cannot stop the LAST one — and it must not pretend to.**
> *(The CAS is placed immediately before the call precisely to make this window as small as physically possible. **It cannot be made zero, and the architecture must not pretend otherwise.**)*

**If verification becomes impossible** ⇒ ### **ownership transfers to the `UNKNOWN_OUTCOME` process of §26** — non-terminal, human-owned, **entity frozen**, **commit key held**, escalated **with the dollar exposure**.
**Compensation in progress:** a compensation **is an effect** ⇒ the same table. ### **`COMPENSATION_FAILED` remains non-terminal and human-owned — the brake does not, and cannot, clear it.**

### 21.6 Activation · release · visibility

**Engage:** ### **ANY authenticated operator may engage a TENANT-scoped brake — instantly, with no approval and no ceremony** *(unless a permanent rule forbids it)*. **Automated Sev-0 detectors may engage or widen.** ### **A model may NEVER engage or release.**

> ## **M-60. Automation may ENGAGE and WIDEN a brake. Automation may NEVER RELEASE or NARROW one.**
> ### **("Narrow"/"broaden" throughout this document refer to AUTHORITY. Widening a brake NARROWS authority — automation may. Narrowing a brake BROADENS authority — humans only.)**
> **Test:** `test_automation_can_engage_but_never_release` *(a property test over every detector)*.
>
> ### ***This is the same sentence that governs autonomy (§20.6). That is not a coincidence — it IS the invariant.***

**Automated Sev-0 triggers:** ### **unauthorized adapter invocation** *(tenant + action class — the effect boundary has been breached)* · runtime orphan detection · ### **tenant isolation breach ⇒ GLOBAL** · projection rebuild divergence · ### **repeated unknown outcomes** *(tenant + integration — we cannot see what we are doing, so we must stop doing it)* · credential compromise · ### **a fraud-signal threshold** *(+ counterparty)* · integration corruption.

> ### **M-61. The brake MUST be engageable when the system is UNHEALTHY. It MUST NOT require the system to be healthy.**
> **Mech:** it is ### **a single row write** in the transactional store. ### **If that store is down, no effect can happen anyway — the grant cannot be claimed. THE BRAKE FAILS SAFE BY CONSTRUCTION.** · **Test:** ### `test_brake_engages_with_the_policy_engine_and_the_tms_down`.
>
> ### ***A safety control that requires the system to be healthy is not a safety control.***

**Release** — ### **an authenticated human ONLY. Never automation. Never a timer. Never a model.**
### **An automated detector that engaged a brake may NEVER release it** *(a detector that could clear its own alarm is not a detector)*.
**Required evidence, all mandatory and all recorded:**
1. ### **Every in-flight effect at engagement is ACCOUNTED FOR** — each is `VERIFIED`, `FAILED`, or **explicitly acknowledged as `UNKNOWN_OUTCOME` with a named owner.**
2. ### **No unresolved Sev-0 security event** in scope.
3. ### **Integration health POSITIVELY demonstrated** *(a positive control — §26.2 — **not** "the page loaded")*.
4. A **`decision_ref`**.

> ### **Unresolved `UNKNOWN_OUTCOME`s do NOT block release — but they MUST be explicitly acknowledged and owned.**
> *(Blocking release on them would create a perverse incentive to resolve them carelessly in order to get the system running again.)*
> ### **Their entities stay frozen and their commit keys stay held REGARDLESS of the brake. The brake's release does not release them. NOTHING does but a human or a proof.**

> ### **M-62. Release MUST NOT reactivate stale Checkpoint Witnesses or Effect Grants. EVERY queued consequential action MUST pass a NEW, FULL checkpoint.**
> **Mech:** ### **`brake_version` is GLOBAL PER TENANT and monotonic — ANY brake change invalidates ALL outstanding witnesses and grants for that tenant, even ones outside the engaged scope.** · **Test:** `test_release_re_checkpoints_all_queued_work`; `test_stale_grant_after_release_is_refused`.
>
> **Why the bluntness is correct:** scope-precise invalidation would require reasoning about scope overlap at claim time, ### **and a bug in that reasoning would let an effect through during a brake.** ### **A conservative over-invalidation costs a re-checkpoint (cheap, correct). A precise under-invalidation costs a PAYMENT (irreversible). We take the cheap failure.**
>
> ### ***A brake that released a queue of pre-authorized effects into a world that has changed since would be worse than no brake at all — it would be a stored-up volley.***

**Visibility.**

> ### **M-63. A hidden brake is a silent degradation and violates R17.**
> **Mech:** every operator surface — Slack, CLI, health — reports it ### **UNPROMPTED, on every interaction**: scope · ### **what is STILL ALLOWED** *(so the owner knows Neyma is still watching)* · reason · actor *(the named human, **or the named automated detector**)* · time engaged · affected workflows · **prevented effects** · ### **in-flight effects and their current status** · ### **unresolved unknown outcomes, with dollar exposure** · ### **the exact requirements for release — NOT "contact an administrator."** · **Test:** `test_active_brake_is_reported_unprompted_on_every_surface`.
>
> ### ***A system that has quietly stopped working is indistinguishable, to an owner, from a system with nothing to do.***

**Example:**

> ### ⛔ **NEYMA IS STOPPED — carrier payables, TruckingOffice**
> **Engaged automatically 14 minutes ago** by the **orphan-effect detector**: *an adapter was invoked without a valid Effect Grant.*
> **I am not writing anything to the TMS.** I am **still reading**, and still watching your inbox.
> **Prevented:** 3 payables (£11,400 total) — all held, none lost.
> ### **In flight when I stopped: 1.** Payable to Redline Carriers, **£4,200** — ### **I do not know if it went through. Frozen. Owner: you.**
> **To release, I need:** (1) that payable resolved, (2) the orphan investigated, (3) a healthy TMS read.

**Brake scope — five dimensions, all reusing existing concepts:** global · tenant · integration (`target_system`) · action class · counterparty.

**Deliberately NOT scope dimensions:**

| Rejected | Why |
|---|---|
| ### **Entity** *("brake load 4471")* | ### **An entity is ALREADY frozen** by an open Conflict, a `NEEDS_VERIFICATION`, or a `COMPENSATION_FAILED`. ### **A second mechanism for freezing an entity is two things that mean the same — which is precisely how they drift apart.** |
| ### **Accountable owner** | ### **A brake on a PERSON is an HR control, not a safety control.** *Stopping "everything Dave approved" describes a suspicion, not a hazard.* If someone's authority is the problem, ### **that is a POLICY change** (§20) — **narrowing authority, which any human may do instantly.** |

---

## §22. Knowledge, Context, Rules & Learning

| | **Policy / Rule** | ### **Organizational Knowledge** |
|---|---|---|
| Representation | structured, typed, **versioned** | free text |
| Scope | explicit | implicit |
| Consumed by | ### **a deterministic guard** | ### **a model's prompt** |
| Can it refuse an effect? | ### **YES** | ### **NO. It has no authority at all.** |
| Failure mode | ### **fails closed** | ### **silently ignored** |
| Honest reply | *"That rule is now enforced. I cannot bill without a POD."* | *"I'll keep that in mind."* |

> ### **M-64. A prompt-string memory is NOT a policy. The system MUST NOT reply "Noted the procedure" unless a real rule compiled and activated.**
> **Test:** `test_reply_text_never_claims_enforcement_without_an_active_rule_id`.
>
> ### ***If the owner believes they installed a control and what they installed was a suggestion, the system has LIED — and the owner will stop checking the thing they think is now guarded. That is strictly worse than refusing the request.***

**Learning narrows, never broadens.** A learned correction **improves proposals**. ### **It never increases authority.**
### **Memory MUST NEVER store a money value.** *(A remembered amount is an amount nobody re-read.)*

---

## §23. Agent Orchestration

> ### **M-65. An agent's ONLY output is a `ProposedIntent` — INERT DATA.**
> ### **It cannot construct a Checkpoint Witness · cannot mint or claim an Effect Grant · cannot name or invoke an adapter · cannot hold a credential · cannot activate policy · cannot engage or release a brake · cannot strengthen provenance.**
> **Mech:** the capability model (§19.9). · **Test:** ### `test_adversarial_document_instructing_pay_this_invoice_produces_a_proposed_intent_and_nothing_else`.
>
> ### ***Injection can make Neyma propose something stupid. It CANNOT make Neyma DO something.***
> ### ***A braked system with a hallucinating agent is still a safe system.***

**Agents ARE used for:** reading documents (`MODEL_EXTRACTED`) · drafting language · proposing intents · proposing rule text · planning. ### ***The brain proposes; the gates dispose.***
**Agents are NEVER used for:** ### **choosing an amount** · evaluating a guard (**P2**) · confirming an identity binding · resolving a conflict · deciding a verification outcome · activating a policy · releasing a brake.

---

# PART IV — OPERATING IT SAFELY

## §24. Security & Threat Model

| Threat | Control | Test |
|---|---|---|
| ### **Prompt injection** *(the primary technical threat)* | ### **The CAPABILITY boundary, not the prompt.** A compromised model produces a bad `ProposedIntent`, which the checkpoint **independently validates against reality**. *Content sanitisation is defence-in-depth, not the wall.* | `test_injection_containment` |
| ### **Counterparty fraud** *(the most common REAL attack — and it arrives as a polite email)* | ### **ADR-003, PERMANENT.** *"Per our call, you approved this detention"* is `MODEL_EXTRACTED` at best, ### **cannot be promoted (R-P2)**, ### **BLOCKS the payable**, and raises a **fraud signal** — ### **which narrows autonomy automatically.** | `test_counterparty_cannot_self_authorize` |
| **Provenance laundering** | **R-P2** — weakened, never strengthened. | ### `test_no_provenance_laundering` |
| **Confused deputy** | the adapter **re-validates the grant against its OWN call parameters**. ### **A mismatch is a Sev-0.** | `test_confused_deputy` |
| **Replay** *(approval or grant)* | ### **single-use CAS ×2.** | `test_replayed_grant_fails` |
| **Forged handle** | ### **irrelevant — it names no ledger row.** A well-formed handle naming **no row** ⇒ **Sev-0.** | `test_forged_handle` |
| **Cross-tenant** | `tenant_id` first everywhere; rejected **before** any handler. ### **A breach engages a GLOBAL brake.** | `test_cross_tenant_rejected` |
| **Insider / tooling** | ### **there is no admin bypass, by construction.** | `test_no_bypass_for_any_of_the_seven` |
| **Orphan adapter invocation** | runtime detection ⇒ ### **Sev-0 ⇒ AUTO-ENGAGE THE BRAKE.** | `test_orphan_detection_engages_brake` |
| ### **A hostile TMS** | ### **OUT OF SCOPE — and stated rather than hidden.** *A **broken** TMS is in scope. A **malicious** one that can forge its own readback is not defensible from inside the browser, and we do not pretend otherwise.* | — |

> ### **M-66. Inbound content is DATA, never instruction, never authority.**
> ### **A document may EVIDENCE a claim; it may never MAKE one.**

---

## §25. Observability, Audit & Replay

> ### **M-67. A decision MUST pin the exact versions of everything it depended on: evidence · observations · claims · knowledge items · rules · policy · prompts · model · schemas.**
> **Mech:** the Checkpoint Witness (§19.3) + the event envelope (§11.2), with ### **content-addressed evidence references.** · **State:** `checkpoint_records` *(permanent)* · **Test:** `test_decision_pins_every_input_version`.

> ### **M-68. Historical explanation MUST reconstruct what the system knew AT THE TIME — not what it knows now.**
> **Mech:** upcasters on read · observations immutable · superseded claims **retained** · ### **history is never rewritten** (**S8**). · **Test:** ### `test_explanation_of_a_90_day_old_decision_uses_the_beliefs_of_that_day`.
>
> ### ***Explaining a past decision using today's knowledge is not an explanation. It is a reconstruction that flatters us.***

**Trace structure:** `correlation_id` *(the business transaction)* → `causation_id` *(the direct cause)* → `work_item_id` → `pipeline_instance_id` → `checkpoint_id` → `grant_id` → `effect_id`.
**Explainability query** — *"why did you do that?"* ⇒ a walk from the effect back through the grant → the witness → the approval **(with its full canonical payload)** → the policy version → the rules matched → the claims used → the observations behind them → ### **to the retained artifact a human can actually look at.** **Latency: < 2 s p95.**
**Audit immutability:** append-only. ### **No UPDATE. No DELETE.** Enforced by grant.
**Replay isolation:** replay runs against a projection sandbox and ### **cannot construct a witness.**
**Projection rebuild comparison:** a scheduled rebuild from the **full corpus** is compared to the live projection. ### **DIVERGENCE IS A SEV-0 AND AUTO-ENGAGES A BRAKE.**
### ***It means our beliefs are not derivable from our evidence — which means we cannot defend any of them.***
**Retention / tiering:** hot (90d) → warm (2y) → cold (7y, immutable). ### **Evidence artifacts are NEVER deleted while any effect rests on them.**

---

## §26. Reliability, Verification, Failure & Recovery

### 26.1 The verification taxonomy — **eight outcomes, each with a proof standard**

| Outcome | Means | Proof required |
|---|---|---|
| **`VERIFIED_SUCCESS`** | the effect exists **AND matches the approved material facts** | a **live, healthy** read returning a record whose material facts **equal the approved fingerprint** |
| ### **`VERIFIED_FAILURE`** | the effect **provably does not exist** | ### **a live, HEALTHY read of a source that WOULD have shown it, returning nothing — PLUS a positive health signal** |
| `UNKNOWN_OUTCOME` | we cannot establish either | *(the honest default — it is what remains)* |
| `VERIFICATION_DEFERRED` | real, but the system will not reflect it yet | the adapter **declared** async posting, **with a bound** |
| ### `VERIFICATION_IMPOSSIBLE` | ### **no readback exists, ever** | ### **declared per adapter, per operation, UP FRONT — never discovered at runtime** |
| `AWAITING_OBSERVATION` | depends on an inbound observation | an **Expectation** is raised |
| ### `OBSERVATION_UNAVAILABLE` | ### **we were BLIND** | a **negative** health signal |
| ### `OBSERVATION_CONFLICTING` | two reads disagree, **or the readback contradicts the approved facts** | two observations that cannot both be true |

> ### **M-69. THE LOAD-BEARING DISTINCTION: `VERIFIED_FAILURE` vs `OBSERVATION_UNAVAILABLE`.**
> ### **Both look IDENTICAL at the call site — "I didn't find it."**
> ### **ONE MEANS RETRY. THE OTHER MEANS STOP.**
> ### **Collapsing them is the double-billing machine.**

### 26.2 ### **Proof of absence requires a HEALTHY channel**

> ### **M-70. A verifier MAY NOT return `VERIFIED_FAILURE` unless it holds a POSITIVE health signal for the channel it read.**
> **Mech:** a **positive control** — evidence the read was **capable of seeing the thing**: a **known-present sentinel row**; an authenticated-session marker **plus** the expected page structure; a 2xx on a known-good probe **in the same session**.
> ### **"The page loaded" is NOT a health signal — a logged-out page also loads.**
> · **Fails:** ### **no health signal ⇒ `OBSERVATION_UNAVAILABLE`, NEVER `VERIFIED_FAILURE`** *(it fails toward blindness — the safe direction)* · **Event:** `VerificationUnavailable{channel, health_signal}` · **Test:** ### `test_logged_out_session_yields_OBSERVATION_UNAVAILABLE_not_VERIFIED_FAILURE`.

> ### **M-71. Readback MUST identify the SPECIFIC target or the EXPECTED DELTA — and MUST match the APPROVED material facts.**
> ### **A stale or ambiguous readback CANNOT verify success.**
> **Test:** `test_readback_must_match_approved_fingerprint`.
>
> ### ***Finding AN invoice on load 4471 is not verification. Finding one for £3,100 when £2,850 was approved is `OBSERVATION_CONFLICTING` — and it means something acted that we did not authorize, or we acted wrongly.***
> ### ***"A record is there" answers a question nobody asked. The question is: is it THE ONE THE HUMAN APPROVED?***

> ### **M-72. Local persistence MUST NEVER be represented as verification of an external effect.**
> **Mech:** the verification interface takes an **authoritative-source reader**; ### **it has no access to local state.** · **Test:** `test_local_write_cannot_satisfy_verification`.
>
> ### ***This is R-01, generalized: a mock ledger reporting `DONE`. A JSON file is not the world.***

**`VERIFICATION_IMPOSSIBLE` — declared, never discovered.** We record ### **only what we can prove**: *the transmission was accepted by the relay at 14:02, and here is the byte-for-byte copy of what was sent.* ### **We NEVER record "delivered", "received", or "read".** The projection stores the field as ### **`unknown`**, never as success.
### ***The honest sentence is "I sent it; I cannot prove it arrived." Any system that says "Sent ✅" and means "handed to a relay" is lying by omission — and the owner will find out on the day it matters.***

### 26.3 Unknown outcomes

> ### **M-73. `FAILED` requires AFFIRMATIVE EVIDENCE that the effect did not occur.**
> ### **NO TIMEOUT ALONE may transition an effect to `FAILED` — or to `VERIFIED`.**
> **Mech:** ### **every timer transition out of `NEEDS_VERIFICATION` / `UNKNOWN_OUTCOME` is an ILLEGAL TRANSITION.** · **Test:** `test_no_timer_can_move_an_unknown_outcome`.
>
> ### ***Any timeout here is a decision to guess about money. This is the single change that would undo the entire architecture.***

**`UNKNOWN_OUTCOME` MUST carry `unknown_reason`** (§12.3).
**Terminal operational handling:** non-terminal · **human-owned** · **entity frozen** · ### **commit key held indefinitely** · escalated with ### **the dollar exposure · what we attempted and when · what we tried in order to verify and why each attempt was inconclusive · what we have frozen · and the SPECIFIC question we need answered** — *"Please look at load 4471 in TruckingOffice. Is there an invoice for £2,850? Tell me yes or no."*

### 26.4 Retry — **classified**

> ### **M-74. VERIFICATION may be retried. The EFFECT may NEVER be retried on an unknown outcome.**
> **Mech:** every failure is classified **TRANSIENT** *(socket · timeout · throttle · browser busy ⇒ bounded retry with backoff)* or ### **PERMANENT** *(authentication · authorization · configuration · protocol ⇒ **fail loudly, ONCE, NEVER retried, raise an Exception with a human owner**)*. ### **A catch-all base class is NOT a classification.** · **Test:** ### `test_auth_failure_raises_immediately_with_zero_retries`.
>
> ### ***A permanent credential failure retried forever is not resilience. It is a system HIDING A FIXABLE PROBLEM from the only person who can fix it*** — while looking, from the outside, like an intermittent transient. *(And against a provider, a tight retry loop on a bad password invites a security block: a five-minute fix becomes an account lockout.)*

### 26.5 Crash recovery

**Pre-effect stages** ⇒ ### **re-run the checkpoint from the beginning. Nothing happened.**
**`CLAIMED` / `EXECUTING`** ⇒ ### ⚠️ **UNKNOWN OUTCOME. NEVER RE-EXECUTE.** Resolve by **verification**; unresolvable ⇒ **`NEEDS_VERIFICATION`.**
### **Recovery never guesses. It re-derives, or it escalates.**

---

## §27. Performance, Latency & Cost Envelope

| Surface | Target |
|---|---|
| Slack slash-command **fast ack** | ### **< 3 s (HARD)** — a fast ack, then the real work |
| Owner read (*"who owes us money?"*) | < 5 s p95 |
| ### **The checkpoint** (7 live checks) | < 2 s p95 |
| Browser actuation *(observed)* | 20–35 s |
| **Explainability query** | < 2 s p95 |
| Projection rebuild (full corpus) | nightly; < 1 h |

> ### **The checkpoint's live re-reads make every effect SLOWER. This is ACCEPTED. It is the difference between an approval and a guess.**

---

## §28. Testing & Verification Architecture

> ### **Green tests are NOT evidence that a capability works. Only a live drive is.**
> *(A permanent SCAR: a capability was once reported as working on the strength of **685 passing tests**, having **never been run against the real system**.)*

| Suite | The test that matters most |
|---|---|
| **Effect boundary** | ### `test_import_graph_no_module_outside_pipeline_imports_adapters` *(CI, unskippable)* |
| **Approval / drift** | ### `test_F01_approve_2850_then_tms_moves_to_3100_no_effect_occurs` |
| **Commit-once** | ### `test_two_proposals_at_different_amounts_share_one_commit_key_and_produce_one_invoice` |
| **Verification** | ### `test_logged_out_session_yields_OBSERVATION_UNAVAILABLE_not_VERIFIED_FAILURE` |
| **Unknown outcome** | ### `test_no_timer_can_move_an_unknown_outcome` |
| **Identity** | ### `test_owner_binding_survives_relinker` *(the B3 regression)* |
| **Provenance** | ### `test_no_provenance_laundering` *(the most adversarial test in the suite)* |
| **Policy** | ### `test_policy_cannot_branch_on_model_inferred` *(at confidence 1.0)* |
| **Honesty (L-C)** | ### `test_uncompilable_instruction_reply_does_not_claim_a_rule_was_installed` |
| **Brake** | ### `test_engaging_the_brake_during_an_adapter_call_does_not_create_an_unknown_outcome` |
| **Injection** | ### `test_adversarial_document_produces_a_proposed_intent_and_nothing_else` |
| **Replay** | ### `test_replay_full_corpus_produces_zero_grants` |
| **Rebuild** | ### `test_full_corpus_rebuild_reproduces_projection` |
| **Crash matrix** | crash at **every** stage ⇒ correct resumed state; ### **no effect is EVER double-executed** |
| **Race** | ### **brake-vs-claim, 10,000× interleaved ⇒ NEVER BOTH, NEVER NEITHER** |
| **Read boundary** | ### `test_consequential_read_boundary` — **already in the baseline; proven by negative control** |
| ### **LIVE DRIVE** | ### **the capability is driven END-TO-END against the REAL TMS through the REAL approval path, and mirrored.** |

---

## §29. Deployment, Environments & Runtime Topology

**v1: a modular monolith.** The **actuation runtime is co-located** (A2).
### **Later process separation MUST NOT change the Effect Grant contract** — authority is **a shared ledger row**, not a process-local type. ### **A process boundary confers no privilege: the actuating process must still CLAIM from the same ledger.**

**Environments:** `dev` · `staging` *(a real TMS sandbox)* · `production`.
### **Mock adapters exist ONLY in test-scoped code. NO production entry point may select a mock financial adapter** — guarded by `test_no_mock_effect_in_production.py`, ### **already in the baseline.** *(This is R-01, severed at `974031d`: the supervised production runner shipped with the mock financial path **enabled by default**, driving human-approved payables into a **JSON file** and reporting them as entered.)*
**Browser actuation:** Chrome + CDP · `human_established_session_only` · a **browser lock**.
**Credentials:** `.env`, **gitignored, never committed**; resolvable **only inside an adapter, on a claimed grant**.

---

# PART V — GETTING THERE

## §30. Migration from the Current System

**Migration baseline:** ### **`f0e801b4dfd611345ca6c2842e946d58a7512ae5`**
*(BASELINE_READY. Stream B is preserved off-baseline on `preserve/pre-reset-readiness-hardening` and is **NOT approved for production inclusion**.)*

### 30.1 ### **SAFETY TASK #1 — the commit key** *(before anything else)*

> ### **Rewrite `_commit_identity` (`operation_router.py:335`) to the §19.7 composition.**
> ### **It is a live double-billing hole (§19.8), and it is the FIRST implementation task of the migration.**

### 30.2 Entry-point disposition *(from the live-effect inventory)*

| # | Entry point | R/W | ### Disposition |
|---|---|---|---|
| 1 | `run_action_callback_server.py` | **W** | ### **CONVERT_TO_PIPELINE_CLIENT** *(it already routes through the gated spine — it becomes the canonical client)* |
| 2 | `run_teammate.py` | **W** *(supervisor)* | **CONVERT_TO_PIPELINE_CLIENT** |
| 3 | `propose_ar_from_tms.py` | **W** | **CONVERT_TO_PIPELINE_CLIENT** *(it proposes; the pipeline effects)* |
| 4 | `drive_real_tms.py` | R | ### **MAKE_READ_ONLY** *(assert it structurally — today it is read-only by convention)* |
| 5 | `discover_tms_screen.py` | R | **MAKE_READ_ONLY** |
| 6 | `enter_truckingoffice_invoice.py` | **W** ⚠️ | ### **CONVERT_TO_PIPELINE_CLIENT or REMOVE** |
| 7 | `enter_invoice_discovered.py` | **W** ⚠️ | ### **CONVERT_TO_PIPELINE_CLIENT or REMOVE** |
| 8 | `orient_tms.py` | R | **MAKE_READ_ONLY** |
| 9 | `run_operate_request.py` | **W** ⚠️ | ### **CONVERT_TO_PIPELINE_CLIENT** *(a terminal is not an approval authority)* |
| 10 | ### `run_operator_agent.py` | **W** ⚠️ | ### **TEST_ONLY or REMOVE** — *the least-gated live-write path in the repo* |
| 11 | `verify_owner_onboarding.py` | R | **KEEP** |
| — | `enter_tms_payable.py` · `run_dogfood_pilot.py` | mock | **TEST_ONLY** |

> ### **M-75. There MUST be NO coexistence in which an old and a new runtime can perform the same effect independently.**
> ### **PREFERRED: HARD CUTOVER by capability, with PHYSICAL DELETION of the old write path.**
> **Fallback, only if unavoidable:** a temporary window in which ### **the legacy runtime claims from the SAME Effect Grant Ledger and the SAME commit namespace — or it does not act.**
> **Mech:** under §19.9, entry points **6, 7, 9, 10 simply STOP WORKING** until refactored — ### **which is the correct and desirable outcome.** · **Test:** `test_no_second_write_path`.

**Interim discipline, until cutover:** ### **do NOT run 6, 7, 9, or 10 against a live TMS while the teammate is running.**
### **This is DISCIPLINE, not a fix. It does NOT resolve R-02.**

### 30.3 ### **Required semantic code migrations** — *NOT performed now*

| Legacy symbol | Uses | ### Canonical | Note |
|---|---|---|---|
| ### **`lane`** *(as action class)* | **291** | ### **action class** | ### **`lane` ALSO means an origin–destination pair in freight — a REAL and DIFFERENT concept. It means BOTH today, in a codebase that gates money on one of them.** ### **MUST NOT be done by find-and-replace.** |
| ### **`run` · `workflow_runs`** | **423** | **Pipeline Instance** | the **ancestor** — **generalize, do not discard** |
| ### **`CommandIntent`** | **51** | ### **`ProposedIntent`** | ### **Named after an entity ADR-008 DELETED — and REVISION 1 OF THIS DOCUMENT MANDATED IT (§11.1, line 400). The code follows the OLD SPEC.** *(A lower layer contradicting a higher one — in production.)* |
| ### **`commit_identity`** | **16** | ### **commit key** | ### **A RENAME *and* A RECOMPOSITION — see §30.1** |
| `operation_action_claims` | 1 table | **`effect_grants`** | the ancestor of the ledger. ### **Discipline right, key wrong.** |
| ### ambiguous **`done`** | many | ### **`VERIFIED_SUCCESS`** | ### **`done` must mean `VERIFIED_SUCCESS` and NOTHING ELSE** |
| overloaded **`claim`** | many | *(both correct)* | ### **Always QUALIFY: "binding claim" vs "grant claim." Do NOT rename either.** |

### 30.4 What to KEEP — **the ancestors**

`enter_approved_payable` — the **gated write driver**. ### **It is the SPINE, not the mock** (audit **R-03**).
`WorkflowStore`'s explicit states + allowed-transition table + audit log — ### **the discipline is right; the shape is document-shaped. Generalize it.**
The **single-use HMAC Slack token** — ### **it is already §21.3 layer 1.**
The email→load linker's ### **deterministic-ID-match-first, model-fuzzy-second, fail-closed** design — ### **this is EXACTLY §10.1, and it was built before the ADR existed.**
`invoices_table_present` — ### **an early POSITIVE HEALTH CONTROL (§26.2). Generalize it.**
The **document fence** — ### **it becomes the first compiled rule.**

---

## §31. Implementation Sequencing

| Wave | What | Gate to proceed |
|---|---|---|
| ### **0** | ### **THE COMMIT KEY (§30.1).** | the double-billing test passes |
| **1** | **The transactional store + the canonical Durable Machine + outbox/inbox** | crash matrix + duplicate-delivery green |
| ### **2** | ### **The Effect Grant Ledger + the Checkpoint + Policy + Brake + adapters behind the boundary** *(ADR-004/005/009/010/011 **together**)* | ### **import-graph gate green; F-01 green; brake-race green** |
| **3** | Observations · Claims · provenance · Conflicts *(ADR-002/007)* | ### **no-laundering + B3 regression green** |
| **4** | The verification taxonomy + `NEEDS_VERIFICATION` *(ADR-006)* | ### **the blindness test green** |
| **5** | Policy compilation + autonomy *(ADR-010)* | ### **the L-C reply test green** |
| **6** | Expectations · Exceptions · Compensation | the indeterminate test green |
| ### **7** | ### **Entry-point cutover (§30.2) — PHYSICAL DELETION of the old write path** | ### **`test_no_second_write_path` green ⇒ R-02 CLOSED** |
| **8** | Domain lifecycles (§12.15) on the proven machinery | **live drives, mirrored** |

> ### **Wave 2 CANNOT be decomposed. The grant, the checkpoint, the policy, and the brake are ONE MECHANISM WITH FOUR NAMES. Building them separately produces four half-mechanisms and zero guarantees.**

---

## §32. Open Questions — **all fail closed**

| # | Question | Fail-closed default | Blocks arch? | Blocks impl? | Who answers | Evidence needed | If the answer differs |
|---|---|---|---|---|---|---|---|
| **V1** | May a written-off load be re-billed when a POD surfaces in month 4? | generic reopening machinery exists; ### **the *when* goes to a human** | ❌ | ❌ | Customer | a real late-POD case | only the **policy** changes; §12.14 is unaffected |
| **V2** | Approval TTLs (1h / 8h / 24h) | conservative defaults | ❌ | ❌ | Customer | *"how long is a rate good for?"* | a config value |
| **V3** | Which classes need dual control, at what threshold | single approval | ❌ | ❌ | Customer | loss data | a policy value; §12.4 unaffected |
| **V4** | Registered deterministic identity rules *(MC+date+amount? BOL? PRO?)* | ### **exact ID match only; everything else ⇒ `AMBIGUOUS` ⇒ human** | ❌ | ❌ | Customer/domain | a real mail corpus | ### **more auto-binding, LESS HUMAN WORK — never less safety** |
| **V5** | Registered conflict-resolution rules *(does the TMS beat the portal?)* | ### **no rule ⇒ EVERY conflict goes to a human** | ❌ | ❌ | Customer | disagreement cases | fewer human interrupts |
| **V6** | Deferred-verification bounds per TMS | `AWAITING_OBSERVATION` + an Expectation | ❌ | ❌ | Per integration | timing measurements | a bound value |
| **V7** | Can the commit key be written INTO the external record? | ### **if not: a human resolves `NEEDS_VERIFICATION`. We do not infer.** | ❌ | ❌ | Per integration | a TMS field survey | ### **deterministic auto-discharge becomes possible** |
| **V8** | Re-issue after credit — a distinct action class? | ⚠️ **recommend a distinct class** | ❌ | ❌ | Customer | a real credit-and-rebill | ### **modelling it as "the same effect again" is how a credit-and-rebill loop becomes a double-bill** |
| **V9** | Partial payments — one effect per remittance reference? | ⚠️ recommend yes | ❌ | ❌ | Customer | a real remittance file | the `occurrence_key` composition |
| **V10** | Per-lane exception ageing thresholds | ages · escalates · ### **never expires** | ❌ | ❌ | Product | ops data | config |
| **V11** | ### **Autonomy graduation thresholds** *(≥100?)* | ### **NOTHING graduates. Everything stays `HUMAN_APPROVAL_REQUIRED`.** | ❌ | ❌ | Customer + data | supervised history | ### **a number chosen without data is a guess with a threshold** |
| **V12** | Which authorities exist per tenant | one Policy Owner, one level | ❌ | ❌ | Customer | an org chart | *"manager approval"* rules become compilable |
| **V13** | Who may ENGAGE the brake? | ### ⚠️ **recommend EVERYONE authenticated** | ❌ | ❌ | Customer | — | ### **the cost of a spurious engagement is a PAUSE. The cost of a delayed one is a PAYMENT. Those are not close — and any policy that makes an operator hesitate to hit the brake is a bad policy.** |
| **V14** | Who may RELEASE? | the Policy Owner | ❌ | ❌ | Customer | — | ### **the asymmetry IS the control** |
| **V15** | Should repeated unknown outcomes auto-engage a brake? | ⚠️ recommend **2 per integration per window** | ❌ | ❌ | Threshold | incident data | ### **two unknowns on one integration is not bad luck — it means we cannot see what we are doing** |
| **V16** | Does `FORBIDDEN` have a v1 member? | ### **EMPTY — a positive assertion** | ❌ | ❌ | Product | — | ### **inventing a member to make the enum feel used would be design by symmetry** |

> ### **NO OPEN QUESTION BLOCKS ARCHITECTURE OR IMPLEMENTATION.**
> ### **Every one has a fail-closed default, and every default sends the unknown case to a human.**

---

## §33. Requirements Traceability

> ### **No requirement is RESOLVED merely because this document states it. RESOLVED requires a named MECHANISM and a named validating TEST.**

| Requirement | § | Mechanism | Test | Status |
|---|---|---|---|---|
| **P2** guards never model-evaluated | §20.3 | evaluator raises on `MODEL_INFERRED`; **no confidence field** | `test_policy_cannot_branch_on_model_inferred` | ✅ |
| **P11** a model's output is a claim | §9, §10 | `provenance_class` | `test_no_provenance_laundering` | ✅ |
| **P24** the loop closes at cash | §12.15 | Invoice `PAID` is terminal | domain suite | ✅ |
| **P36** fewest concepts | §4 | modular monolith; ### **ZERO new primitives in Waves 2–4** | — | ✅ |
| **R10** never report done without proof | §26 | `VERIFIED_SUCCESS` only | `test_local_write_cannot_satisfy_verification` | ✅ |
| **R17** no silent degradation | §21.6 | the brake is reported unprompted | `test_active_brake_is_reported_unprompted` | ✅ |
| **I1** an accountable human, always | §13 | `owner_id NOT NULL` | `test_no_ownerless_work_item` | ✅ |
| **I3** explainable to an angry person | §21.2, §25 | the canonical payload + evidence traversal | `test_explanation_uses_beliefs_of_that_day` | ✅ |
| **I5** provenance survives | §9 | permanent retention | `test_evidence_traversal` | ✅ |
| **I7** `unknown` is legal | §6.3 | the 5-condition enum | `test_five_conditions_never_collapse` | ✅ |
| ### **I8** missing ≠ contradictory | §6.3, §12.8, §26.1 | ### **`unknown`≠`conflicting`; `OVERDUE`≠`INDETERMINATE`; `VERIFIED_FAILURE`≠`OBSERVATION_UNAVAILABLE`** | `test_deadline_while_blind_is_INDETERMINATE` | ✅ |
| **I10** never taken and unrecorded | §11.4 | ### **the transactional outbox** | `test_dual_write_kill` | ✅ |
| **I11** closure is an event | §12.1, §12.9 | `decision_ref` required | `test_exception_closure_requires_decision_ref` | ✅ |
| ### **Authorization Assertion (PERMANENT)** | §7, §20.1 | ### **`PERMANENT_HUMAN_ASSERTION_REQUIRED`; R-P2 forbids promotion** | `test_counterparty_cannot_self_authorize` | ✅ |
| ### **Money-out = product POLICY, not a truth** | §20.1 | ### **explicitly NOT promoted** | — | ✅ |
| **S1–S28** *(Semantic Model)* | throughout | each has a mechanism | each has a test | ✅ |
| **ADR-001 C4** | §6.4, §16.4 | the **read classes** | ### `test_consequential_read_boundary` *(in the baseline)* | ✅ |
| **ADR-002 A2** `provenance_class` | §9.2 | six classes; R-P1/2/3 | `test_no_provenance_laundering` | ✅ |
| **ADR-003** | §7, §20.1, §24 | a permanent gate + a fraud signal | `test_counterparty_cannot_self_authorize` | ✅ |
| **ADR-004** the effect boundary | §19 | **six enforcement layers** | `test_import_graph…` | ✅ |
| **ADR-005** drift | §21 | the fingerprint, at checkpoint step 2 | ### `test_F01…` | ✅ |
| **ADR-006** verification | §26 | 8 outcomes + a health control | `test_logged_out_yields_UNAVAILABLE` | ✅ |
| **ADR-007** identity | §10 | deterministic-first | `test_owner_binding_survives_relinker` | ✅ |
| **ADR-008** durable workflows | §12 | 13 machines + the outbox | the crash matrix | ✅ |
| **ADR-009** concurrency | §16.1, §19.7 | ### **two unique indexes** | `test_one_commit_key_one_invoice` | ✅ |
| **ADR-010** policy | §20 | gate NOT NULL; compile-or-refuse | `test_action_class_without_gate_fails_startup` | ✅ |
| **ADR-011** brake | §21.4 | admission control | `test_brake_does_not_create_unknowns` | ✅ |
| **F-01** *(CRITICAL)* | §19.4 | ### **the checkpoint AFTER the human gate** | `test_F01…` | ✅ |
| **F-02** *(CRITICAL)* | §19.9 | the capability boundary | `test_import_graph…` | ✅ |
| **F-06** *(CRITICAL)* | §11.4 | the outbox | `test_dual_write_kill` | ✅ |
| **F-10** *(CRITICAL)* | §16.1 | the unique indexes | `test_one_commit_key_one_invoice` | ✅ |
| **F-14** | §12.8 | observation coverage | `test_deadline_while_blind…` | ✅ |
| **F-17** | §10.2 | correction propagation | `test_correction_propagation_end_to_end` | ✅ |
| **F-20** | §20.1 | ### **an unregistered gate ⇒ FAILS TO START** | `test_action_class_without_gate…` | ✅ |
| **F-25** | §12.8 | facility-local timezone | `test_appointment_window_across_dst` | ✅ |
| **F-33** | §26.3 | `NEEDS_VERIFICATION` never auto-resolves | `test_no_timer_can_move_it` | ✅ |
| **F-35** | §23, §24 | capability containment | `test_injection_containment` | ✅ |
| ### **F-07 / R-02** | §30.2 | ### **the shared ledger + commit namespace** | `test_no_second_write_path` | ### ⚠️ **OPEN — closes on IMPLEMENTATION, not on this document** |
| **R-01** | §29 | mock path severed at `974031d` | `test_no_mock_effect_in_production` | ✅ *(baseline)* |
| **R-03** | §30.4 | `enter_approved_payable` retained | `test_the_gated_write_driver_survives` | ✅ *(baseline)* |
| ### **The live commit-key defect** | ### **§19.8, §30.1** | the §19.7 composition | `test_one_commit_key_one_invoice` | ### ⛔ **OPEN — SAFETY TASK #1** |
| **L-A** | §12.6 | an illegal transition | `test_owner_binding_survives_relinker` | ✅ |
| **L-B** | §10.1 | binding by immutable id | `test_ordinal_binding_fails_closed` | ✅ |
| **L-C** | §20.5, §22 | compile-or-refuse | `test_uncompilable_instruction_reply…` | ✅ |
| **L-D** | §26.4 | retry classification | `test_auth_failure_zero_retries` | ✅ |

---

## §34. Governance & Evolution

**This document is the INTEGRATION of the ADRs.** ### **Where it disagrees with an ADR, THE ADR WINS and this document is defective.**
**Amending it requires** the seven-question change process (Engineering Principles §11), a written reason, and — if a **frozen** higher document is affected — ### **an explicit Amendment Record, NEVER a silent edit.**

> ### **Two defects in previously-frozen output were found by writing the NEXT LAYER DOWN** *(the `UNKNOWN_OUTCOME` three-way overload; the `UNGATABLE_PERMANENT → REJECTED` collapse, which would have made Neyma structurally unable to pay a legitimate, human-authorized detention charge)*.
> ### **That is what the reviews are for, and it is why they are not a formality.**

---

## CLOSING

> ### **Neyma observes an authoritative system it does not own, forms claims it must be able to defend, projects a view it may never act on, and — only after one atomic checkpoint against the live world — spends a single-use grant to touch reality once, and then reads it back to find out what actually happened.**
>
> ### **Everything in this document exists to make that sentence true, mechanically, on the worst day.**
