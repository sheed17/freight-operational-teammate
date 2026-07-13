# Neyma — Target System Architecture Specification

**Layer:** Architecture (per `engineering-principles.md` §12.1).
**Governed by:** Engineering Principles (constitution) · Operating Model (canonical).
**Constrained by:** Current-State Reconciliation · Freight Discovery (evidence base).
**Decided by:** ADR-001 (Authority Model) · ADR-002 (State Classes & Lineage).
**Status:** Draft for review. **Contains no implementation code and no pseudocode.**
**Date:** 2026-07-09

---

# PART I — FRAME

## §1. Purpose, Scope & Non-Goals

### 1.1 Purpose
This document is the **engineering source of truth** for Neyma. Multiple engineers and AI coding agents will implement directly from it over multiple years. Every major engineering decision must have an obvious home here.

It specifies **the shape of the system**. It does not specify the business (Operating Model), how we build (Engineering Principles), or what the code says (Implementation).

### 1.2 What this document governs
The structure, boundaries, state model, control flow, safety architecture, and construction sequence of the production system.

### 1.3 Explicit non-goals
Neyma is **not**, and this architecture will never make it:

| Not a… | Because |
|---|---|
| **TMS** | Permanent product boundary (Operating Model §7.5). It is the reason customers can adopt without fear. |
| **System of record for the customer's business** | ADR-001. Neyma projects; it does not replace. |
| **Load board, visibility platform, or WMS** | Different businesses (Operating Model §2.4). |
| **General-purpose agent platform** | Agents are bounded workers, not a product surface (P34, P35). |

### 1.4 Audience
Engineers and AI coding agents implementing the system; reviewers evaluating proposed changes against it.

---

## §2. How to Read This Document

### 2.1 Normative language
- **MUST / MUST NOT** — a requirement. A violation is a defect, not a trade-off.
- **SHOULD / SHOULD NOT** — a strong default. Departure requires a recorded justification (ADR).
- **MAY** — genuinely optional.

### 2.2 Citations
- `P#` — Engineering Principle. `R#` — Refusal (a hard rejection). `I#` — Operational Invariant.
- `ADR-###` — a recorded architectural decision.
- **"This violates P6" is a complete and sufficient objection** (Principles §7).

### 2.3 Open decisions
Anything not yet resolvable from evidence is marked **`NEEDS VALIDATION`** and registered in **§4**. A section that depends on an open assumption is marked **`PROVISIONAL`** and MUST state what breaks if the assumption is false (Principles §12.3 — *a design built on `NEEDS VALIDATION` is a design built on sand*).

### 2.4 Architecture Decision Records
Every decision that closes a fork, departs from a SHOULD, or changes this document is recorded as an **ADR** (§32, Appendix A). **An architectural change made without an ADR did not happen** — it is drift.

---

## §3. Canonical Vocabulary

**One name per concept. Forever.** This section exists as the direct defence against **P30** (*never collapse distinct concepts because they usually coincide*).

### 3.1 The load family — six distinct concepts `PROVISIONAL — FORK A`
> **These MUST NOT be collapsed.** They frequently coincide. Coincidence is not identity.

| Term | Definition |
|---|---|
| **Customer Order** | What the *customer* believes they bought. Carries their reference. May span multiple movements. |
| **Brokerage Load** | The unit *we* sell, price, and book margin on. |
| **Carrier Movement** | The unit a *carrier* agrees to haul and invoices against. |
| **Leg** | A segment of a movement (drayage → linehaul → delivery), potentially its own carrier and rate. |
| **Stop** | A single pickup or delivery event, with its own window, appointment, and paperwork. |
| **TMS Load Record** | A **row in a vendor's database**. A system artifact — **not a business concept** (P28). |

### 3.2 Commercial terms
- **Sell rate** — what the customer pays us. **Buy rate** — what we pay the carrier. **Never interchangeable.**
- **Margin / spread** — sell minus buy, per load. The business's actual product.
- **Linehaul · Fuel surcharge · Accessorial** — distinct rate components. Never summed into "the rate" internally.
- **Accessorial charge** vs **accessorial authorization** — **two different entities.** A charge is a claim for money. An authorization is permission for it to exist. *One can exist without the other, in both directions.* (Freight Discovery §4.3)

### 3.3 Evidence terms (five distinct conditions — ADR-002 C5)
| Term | Meaning |
|---|---|
| **absent** | We looked; the fact is not there. |
| **unknown** | We could not look, or could not read. **Not the same as absent.** (I7) |
| **consistent** | Observed, and all sources agree. |
| **conflicting** | Observed, and sources **disagree**. (I8) |
| **stale** | Observed, previously consistent, **not confirmed recently enough** for the intended use. |

**Collapsing any two of these is a defect.** (ADR-002 C5)

### 3.4 System terms
**Observe** (see it) · **Bind** (tie it to the right thing) · **Claim** (assert an inference, with evidence) · **Reconcile** (compare across sources) · **Act** (effect the outside world) · **Verify** (read back and confirm) · **Escalate** (hand a human the decision, with evidence) · **Close** (a loop reaches its completion condition — an *event*, never an inference, I11).

---

## §4. Architectural Assumptions & Open Decisions

### 4.1 Closed decisions
| Fork | Resolution |
|---|---|
| **Authority model** | **CLOSED** — ADR-001. Canonical operational projection; external systems remain authoritative for their domains. |
| **State classes** | **CLOSED** — ADR-002. Projected state vs. Neyma-native state; lineage without attributed cells. |
| **Multi-tenancy** | **CLOSED by P16** — tenancy is a property of every record from the first commit. Not a fork. |

---

### 4.2 FORK A — Load-family relationships `NEEDS VALIDATION`

**The question:** at our design partner, are Customer Order / Brokerage Load / Carrier Movement / Leg / Stop / TMS Record distinct — and how do they relate (1:1, 1:N, N:M)?

**Provisional assumption:**
> **Model all six as DISTINCT entities with EXPLICIT relationships.** Where the partner's reality is unknown, default the cardinality to **1:1**, but **never collapse the identities**.

**Why this is the reversible choice — and this is the key architectural insight of the fork:**
> **Collapsing two distinct entities later is trivial. Splitting one collapsed entity later is impossible.**
> Once code, queries, joins, and every integration have assumed *load = order = movement*, the assumption is encoded everywhere and cannot be unwound. Therefore: **keep them distinct even while they coincide.** The cost of being wrong in this direction is a few redundant joins. The cost of being wrong in the other direction is a rewrite.

**Sections affected:** §3 (vocabulary), §8 (entities), §10 (identity — *which* entity does an artifact bind to?), §12 (lifecycles — each has its own), §13 (work items reference a specific member), §16 (data), §19 (which entity does an action target?), §30 (migration — the current `load_id` is a *TMS row id* masquerading as a business identity).

**What breaks if the assumption is false:**
- If the true relationships are **N:M** (e.g. one order fulfilled by several movements; one movement serving several orders): **cardinality assumptions in relationships break**, and queries assuming 1:1 return wrong results. **But the identities remain intact** — the fix is a relationship migration, **not a re-split**. This is the whole point of the provisional choice.
- If the partner genuinely has **only one concept**: we carry modest redundant structure. **Acceptable.**

**Irreversible decisions to avoid:** MUST NOT introduce a single generic `load_id` foreign key used across the family. MUST NOT denormalize fields across family members. MUST NOT let a TMS row id become a business identity (P28).

---

### 4.3 FORK B — Credential and session posture `NEEDS VALIDATION`

**The question:** does Neyma ever hold a credential and establish its own session, or is `human_established_session_only` permanent?

**Provisional assumption:**
> **The architecture defines a `SessionProvider` abstraction with TWO implementations**, and commits to **neither** as permanent:
> - **(a) Human-established session** — a human logs in; Neyma attaches. *(Current posture. Default. Safe.)*
> - **(b) Per-tenant credential vault** — capability-scoped, short-lived, fully audited session materialization.
>
> **(a) is the default.** **(b) MAY be enabled per-tenant, per-system, only by explicit product decision and ADR.**

**Sections affected:** §14 (continuous observation and non-event detection), §18 (integration/actuation), §24 (security), §26 (degradation when no session exists), §27 (concurrency — a shared human session **serializes all work**), §29 (runtime), §31 (unattended operation depends on this).

**What breaks if (a) is permanent — stated starkly, because it matters:**
> **Continuous observation is impossible when no human is logged in.** Therefore **§14 (non-event detection) cannot run** outside a human's working session — and §14 is where the brokerage's **largest and most silent losses** live (Operating Model §4.5). A permanently human-gated session does not merely inconvenience the architecture; **it removes the single largest source of value.**
>
> The Operating Model requires Neyma to observe email, portals, boards, and a TMS **continuously**. That requirement and `human_established_session_only` are **in direct tension**, and this document does not resolve it — it makes the tension explicit and keeps both doors open.

**Irreversible decisions to avoid:** MUST NOT write actuation code that assumes a session always exists. MUST NOT bake credentials into any code path. The **session lifecycle MUST live entirely behind the abstraction**, and every observation path MUST have a defined behaviour when **no session is available** (it degrades to `unknown` — **never to `absent`**, I7).

---

### 4.4 Other named assumptions
| Assumption | Basis | If false |
|---|---|---|
| ICP is a small/medium US truckload brokerage | Operating Model §2.1, `HYPOTHESIS` | Loop priorities and integration set change; the spine does not. |
| First loop is Documentation → Billing | Operating Model §9.5, `HYPOTHESIS` | Sequencing changes (§31). Architecture unaffected. |
| Partner's TMS is browser-only (no usable API) | `NEEDS VALIDATION` | If an API exists, §18 gets a cheaper adapter. **The capability contract is unchanged.** |

---

## §5. Requirements Traceability from the Frozen Foundation

**This section makes the hierarchy mechanical rather than ceremonial.** A binding with no discharging section is a hole in the architecture.

### 5.1 Operating Model §11 bindings

| # | Binding | Discharged by |
|---|---|---|
| 1 | Work originating from a **non-event** | **§14** (Expectations) |
| 2 | A **commitment with no document** | **§9** (Evidence — a Claim sourced from a communication observation) |
| 3 | **Distributed truth** | **§6** (Projection & Reconciliation), ADR-001 |
| 4 | A loop **open but not closed** | **§13** (Work Model), §25 (honest reporting) |
| 5 | **Escalation with evidence** | **§21** (Decision Packet) |
| 6 | A **gate on any action, enforceable permanently** | **§19** (Action Pipeline), §20 (Safety Kernel) |
| 7 | **Identity binding** as first-class | **§10** |
| 8 | **Three-state evidence** (extended to five) | **§9**, §6 (reconciliation status) |
| 9 | **Accountable human owner** for every unit of work | **§13**, §7 |
| 10 | Every invariant in §10 of the Operating Model | *below* |

### 5.2 Invariants I1–I12

| Invariant | Discharged by |
|---|---|
| I1 accountable owner | §7 (roles), §13 (work model) |
| I2 attributable action | §19 (pipeline records the actor), §25 |
| I3 explainable financial action | §6 (lineage), §25 (traversal) |
| I4 reconstructable transition | §11 (events), §12 (state machines) |
| I5 document provenance | §9, §16 |
| I6 reproducible from evidence **at the time** | §25 (replay reconstructs the then-known state) |
| I7 `unknown` is first-class | §3.3, §9, §12 |
| I8 missing ≠ contradictory | §3.3, §6 (reconciliation status), §9 |
| I9 deterministic completion condition | §12, §13 |
| I10 no action taken and unrecorded | §19 (recording is a pipeline stage, not a caller's duty) |
| I11 closure is an event | §11, §13 |
| I12 escalation carries evidence | §21 |

### 5.3 Load-bearing refusals
| Refusal | Enforced by |
|---|---|
| R6 no agent write without deterministic validation | §19, §20 |
| R7 no model-chosen consequential value | §19 (runtime-supplied values), §20 |
| R8 no prompt as a security boundary | §20, §24 |
| R9 no unverified completion | §19 (verify stage) |
| R10 no failed read as a clean result | §6, §9 (`unknown` ≠ `absent`) |
| R14 no second implementation | §19 (**the single effect boundary**) |
| R15 no tenancy retrofit | §7, §16 |

---

# PART II — THE MODEL OF REALITY

## §6. The Canonical Operational Projection & Reconciliation Model

*Specifies ADR-001 and ADR-002.*

### 6.1 The five-layer lineage model

The system MUST separate these five concerns. **They are distinct layers, not a single table.**

| Layer | Content | Class | Mutability |
|---|---|---|---|
| **L1 — Observations** | Raw sourced values, exactly as seen, from one external system at one moment. | **Projected** | **Immutable** |
| **L2 — Claims** | Neyma's inferences: bindings, extractions, interpretations — each with evidence and correction history. | **Native** | **Append-only + correctable** |
| **L3 — Lineage records** | Links an **observation or a claim** to a **canonical field**. | Native | Append-only |
| **L4 — Materialized projection** | **Strongly typed domain records** plus **summarized field status**. What business logic reads. | Derived | Rebuildable |
| **L5 — Evidence traversal** | The ability to walk from any canonical field back to the complete chain. | Capability | — |

> **The unit of *provenance* is the field. The unit of *operational state* is a typed domain record.** (ADR-002 §2)
> Business logic reads a `Load`. It does not read a bag of attributed cells. **Ergonomics and lineage are not in tension** — they are in different layers.

### 6.2 Field status (the summarized status carried on L4)

Every canonical field MUST expose a compact status sufficient for a caller to decide whether it may be used:

| Attribute | Purpose |
|---|---|
| **condition** | One of: `absent` · `unknown` · `consistent` · `conflicting` · `stale` (§3.3) |
| **as_of** | When the underlying observation was made (**not** when we wrote it) |
| **confidence** | May **route** work. MUST NOT **authorize** an action. (P4) |
| **lineage_ref** | Handle for L5 traversal |

The physical representation of this status is **NOT decided here** (§16 decides, and must justify).

### 6.3 Reconciliation
- Reconciliation is **continuous**, not a one-time import.
- The reconciler compares **observations of the same canonical field across sources and across time**, and emits a `condition` (§6.2).
- **When authoritative systems disagree, the system MUST NOT choose.** It MUST record a **Conflict** (a native entity, §8.7) and route it to **deterministic reconciliation** (a rule with a right answer) or **human approval**. **A model MUST NOT resolve a conflict.** (P2, ADR-001 §2.4)

### 6.4 The rules that make "derived" true

| # | Rule |
|---|---|
| **6.4.1** | **The projection MUST be rebuildable** from retained observations and events. **This is a tested, enforced property (§28), not an aspiration.** *If we cannot rebuild it, it has silently become authoritative — and we would never notice.* |
| **6.4.2** | **The projection MUST NOT be optimistically updated.** A write to an external system does not update the projection; the **verified readback** does. **Intent lives in the command or work item. Fact lives in the projection.** (ADR-002 C3) |
| **6.4.3** | **The projection is for *knowing*. The authoritative system is for *acting*.** A consequential action MUST revalidate against the authoritative source **at execution time** (§19.4). The projection never authorizes an effect. (ADR-002 C4) |
| **6.4.4** | **A `conflicting` field MUST block a consequential action** that depends on it. So MUST `unknown`. So MUST `stale` beyond the freshness policy for that use. (ADR-002 C6, P6) |

### 6.5 Freshness policy
Staleness is **relative to use**, not absolute. Each consumption site MUST declare its freshness requirement.

| Use class | Requirement |
|---|---|
| **Informational** (a digest, a summary) | The projection, with `as_of` **displayed honestly**. |
| **Decision-supporting** (an escalation packet) | The projection, with staleness **surfaced to the human**. |
| **Consequential** (a money or outbound action) | **Live revalidation against the authoritative source.** The projection is insufficient, always. |

---

## §7. Tenancy, Users, Roles & Authority

### 7.1 Tenancy (P16, R15)
- **Tenant is a property of every record, every credential, every action, every event, and every log line — from the first commit.**
- Cross-tenant reads MUST be structurally impossible, not merely unauthorized. Isolation is enforced at the **data access boundary** (§16), not by convention in query construction.
- **No global mutable context** (R5). No ambient "current tenant."

### 7.2 Users and roles
The current system's "one owner, one channel" is a `REPO_CONFIRMED` defect. A brokerage is a **team**.

The architecture MUST support distinct roles with distinct authority. The **specific role set is `NEEDS VALIDATION`** (partner's actual roles). The architecture MUST NOT hardcode a role list; roles are **configuration within a tenant**.

### 7.3 The authority matrix
Authority is a **function of (role, action class, value, counterparty)** — not a boolean "is admin."

| Concept | Requirement |
|---|---|
| **Action class** | Every action belongs to a class (§19.2). |
| **Approval authority** | Per (role × action class × value ceiling). |
| **Accountable owner** | Every work item has exactly one, at every moment (I1). Ownership transfer is an **event** (§11). |
| **Delegation** | MUST be explicit, time-bounded, and recorded. **Never implicit.** (R4) |

**MUST:** the authority matrix is evaluated in the **Safety Kernel** (§20), in code, at the effect boundary. It MUST NOT be evaluated by an agent, and it MUST NOT be advisory.

---

## §8. Canonical Domain Entities

*Entities are the nouns the business would recognize with every computer switched off (P26). If it exists only because code needed somewhere to put a value, it is a table, not an entity (P29).*

### 8.1 The load family `PROVISIONAL — FORK A`
Six distinct entities (§3.1), with **explicit** relationships. **MUST NOT be collapsed** (P30, §4.2).

### 8.2 Party entities
Customer · Shipper facility · Consignee · Carrier · Driver · Broker staff (User, §7) · Factoring company · Insurer.

> Note: **the paying customer is not always the physical shipper.** These are distinct.

### 8.3 Commercial entities
Quote · Bid/Offer · Rate (with **sell** and **buy** as distinct) · Rate components (linehaul, fuel, accessorial) · Lane · Margin.

**Accessorial Charge** and **Accessorial Authorization** are **separate entities** (§3.2). This is the entity-level expression of *the commitment precedes the document* (Operating Model §3.3, P31).

> **An Authorization MAY exist with no document.** It is a **Claim** (§6 L2) sourced from a communication observation — e.g. a phone call or a text. **The architecture MUST be able to represent an authorization that has no artifact.** Without this, the system will confidently accuse honest people (P31).

### 8.4 Execution entities
Stop · Appointment · Equipment/trailer type · Status/milestone.

### 8.5 Financial entities
Customer Invoice (AR) · Carrier Invoice (AP) · Payable/Settlement · Payment/Remittance · Short-pay · Adjustment · Claim (OS&D).

### 8.6 Compliance entities
Operating authority · Certificate of Insurance (with expiry) · Carrier agreement · W-9 · Safety rating.

### 8.7 Native entities (Neyma-authoritative — ADR-002 §1.2)
**Work Item** (§13) · **Binding Claim** (§10) · **Exception** · **Conflict** (§6.3) · **Approval** (§21) · **Expectation** (§14) · **Knowledge record** (§22) · **Autonomy grant** (§20) · **Audit event** (§25).

### 8.8 Communication as a first-class entity
The Reconciliation found: *a strong log of what Neyma did, and no log of what Neyma said or was told.* In a business run on email and text, **that is the majority of the record.**

A **Communication** (message, thread, call, SMS) MUST be a first-class entity — because it is where **commitments** live (Operating Model §3.3), and it is the **evidence** for authorizations that have no document.

### 8.9 What is deliberately NOT an entity
A TMS row (it is a *source record*, §6 L1). A page. A screen. A queue. **These are artifacts of systems, not concepts of the business** (P28, P29).

---

## §9. Evidence, Observation & Provenance

### 9.1 The Observation (L1 — projected, immutable)
An Observation records: **what was seen · from which system · from which source record · at what time · by which actor/mechanism · with what raw content retained.**

**MUST:** the **raw sourced value is retained** — not merely the parsed interpretation (§2.3 of the Principles: *evidence is kept, not summarized away*). The parse can be re-run; the observation cannot be re-taken.

### 9.2 The Claim (L2 — native, correctable)
A Claim records an **inference**: an identity binding, a document extraction, an interpretation of a message.

A Claim MUST carry: **the assertion · the evidence it rests on (observation refs) · the actor (which agent/model/human) · the reason · the confidence · the correction history.**

> **An inference is native state, not projected state.** It **MUST NOT silently masquerade as an observed fact.** (ADR-002 §1.3, P11)

### 9.3 The five conditions (§3.3)
`absent` · `unknown` · `consistent` · `conflicting` · `stale`. **MUST remain distinct** (ADR-002 C5).

> **The most dangerous defect this system can have is rendering `unknown` as `absent`.** It has happened (`SCAR`, P6/R10). The type system SHOULD make it impossible to read a field's value without confronting its condition.

### 9.4 Confidence
Confidence MAY **route** work (e.g. to a higher-scrutiny path). Confidence MUST NOT **authorize** an action (P4). **There is no confidence threshold above which a consequential action proceeds without its gate.**

### 9.5 Provenance survival
When a value passes observation → extraction → claim → decision → action, **the chain back to the original observation MUST survive** (P15, I5). A value in the projection with no lineage is a defect, not a value.

---

## §10. Identity & Correlation

> **The highest-consequence inference the system makes.** Binding an artifact to the wrong record is the failure that quietly moves real money to the wrong party. **It is a subsystem, not a helper function** (P32).

### 10.1 The Binding Claim
A binding is a **Claim** (§9.2), i.e. **native state** — not an observed fact. It is:
- **evidenced** (which identifiers matched, from which observations),
- **confidence-scored**,
- **correctable** (with history),
- **escalatable**.

### 10.2 The identifier problem
The domain presents **heterogeneous, colliding references**: load # · order # · trip # · PRO · BOL # · customer reference · carrier invoice # · MC #. `CONFIRMED INDUSTRY PATTERN`.
**Live evidence:** 5 of 11 open exceptions in the current system were **emails that could not be bound to a load** (`REPO_CONFIRMED`).

### 10.3 The binding pipeline (MUST)
1. **Candidate generation** — the model MAY propose candidates from ambiguous text. *(This is legitimate AI use: irreducible ambiguity, §3.1 of the Principles.)*
2. **Deterministic confirmation** — a **rule with a right answer** MUST confirm the candidate. **The model's proposal is never sufficient** (§3.2, R6).
3. **Ambiguity ⇒ escalation.** Two plausible candidates, or none, MUST escalate with the evidence (I12). **It MUST NOT guess, and it MUST NOT pick the most likely.**
4. **Binding is recorded as a Claim** with its evidence.

### 10.4 Re-binding and correction
A wrong bind MUST be **correctable**, and the correction MUST:
- be recorded as a **correction event** with actor and reason,
- **propagate** to everything derived from the wrong binding,
- feed the learning loop (§22) — **a repeat correction is a defect, not a metric** (Operating Model §8).

### 10.5 Binding to *which* entity `PROVISIONAL — FORK A`
An artifact binds to a **specific member of the load family** — not to "the load." *(A carrier invoice binds to a Carrier Movement. A customer's PO binds to a Customer Order. A POD binds to a Stop.)*
**If Fork A resolves to a single concept**, this collapses harmlessly. **If it resolves to N:M**, this design already holds.

---

## §11. Domain Events

### 11.1 Events are facts, not commands
An event describes **an observation or a decision that has occurred**. It never expresses intent. *"We intend to pay" is state. "We paid, and here is what we saw when we did" is an event.* (§2.2 of the Principles)

**MUST:** the type system MUST distinguish an **Event** (something happened) from a **Command** (something should happen). Conflating them makes the system's authority impossible to audit.

### 11.2 Properties
Events MUST be **append-only, immutable, provenanced, and attributable** (I2, I10). **History is never mutated to make the present look tidy.**

### 11.3 Taxonomy
Observation · Claim · Decision · Action-attempted · Action-verified · Approval · Correction · Escalation · **Closure**.

### 11.4 Closure
**Loop closure MUST be an explicit event, never an inference** (I11). *A loop is closed because something closed it — not because nothing has happened lately.* **Silence is not success.**

### 11.5 Ordering
Global ordering MUST NOT be assumed. Ordering guarantees are **per-partition** (§17) and MUST be stated wherever relied upon.

---

## §12. Lifecycles & State Machines

### 12.1 Requirements (P10)
Every long-lived entity and every loop MUST have:
- **explicit named states**,
- an **enumerated transition table**,
- **guards** derived from evidence (§9),
- **`unknown` as a first-class state** (I7),
- **illegal transitions as hard errors, not warnings.**

State MUST NOT be inferred from the presence of a row, the absence of a field, or a string comparison.

### 12.2 Entities requiring lifecycles
Each member of the load family (`PROVISIONAL — FORK A`) · Quote · Carrier (compliance) · Document · Expectation · Exception · Conflict · Customer Invoice · Carrier Invoice/Payable · Claim (OS&D) · Work Item.

### 12.3 Completion conditions (I9)
Every lifecycle MUST have a **deterministic completion condition** — knowable, checkable, and not a matter of opinion. *A loop with a fuzzy ending never ends; it stays "in progress" forever, which is indistinguishable from failure.*

### 12.4 Open-but-not-closed
The state machine MUST make the distinction between **acted upon** and **closed** representable and queryable — because the gap between them **is where the money is** (P24, Operating Model §3.4).

---

## §13. The Work Model

### 13.1 The Work Item (native)
A Work Item is Neyma's representation of **a unit of work inside an operational loop**. It carries:

| Attribute | Requirement |
|---|---|
| **Loop** | Which operating-model loop it belongs to. |
| **Subject** | The entity it concerns (a specific load-family member, a carrier, an invoice). |
| **Accountable owner** | **Exactly one human, at every moment** (I1). Assignment and transfer are **events**. |
| **State** | Explicit (§12). |
| **Completion condition** | Deterministic (I9). |
| **Evidence** | What justifies its existence. |
| **Age / SLA** | For §14 and §25. |

> **Work with no owner rots silently.** *"The system was handling it"* is how loops die unnoticed (I1).

### 13.2 Intent lives here, not in the projection
**A Work Item may express intent** ("we intend to bill this load"). **The projection may not** (§6.4.2, ADR-002 C3). This is the boundary that prevents the projection from becoming a shadow source of truth.

### 13.3 The honest ledger
The system MUST be able to report, truthfully and at any time: **loops opened vs. loops closed**, and **the age of the oldest open one** (Operating Model §8). Reporting actions taken instead of loops closed is **vanity** (P20, P24).

---

## §14. Triggers: Time, Expectation & the Non-Event Problem

> **You cannot subscribe to an event that never happened.** The brokerage's largest and most silent losses originate from **absence**: the POD that never arrived, the customer that never paid, the COI that lapsed (Operating Model §4.5). **A system that only reacts to events is structurally blind to them.**

### 14.1 The Expectation (native entity)
The architecture's answer to the non-event problem is to make **absence observable by making expectation explicit.**

An **Expectation** records: **what we expect · from which party · by when · why (what created it) · what would discharge it.**

### 14.2 Lifecycle
`raised → (discharged | overdue → escalated | cancelled | expired)`

- **Discharged** by a matching **observation** (§9) — bound via §10.
- **Overdue** by **time** — which is itself a trigger source (Operating Model §4.4).
- **Cancelled** when the reason for expecting it disappears (e.g. the load was cancelled).

### 14.3 The three absences (MUST remain distinct)
| Condition | Meaning |
|---|---|
| **not yet** | Expected, not yet due. **No work.** |
| **overdue** | Expected, past due, still absent. **This is work.** |
| **unknown** | **We could not look.** *(No session, unreadable page, failed integration.)* **This is a different kind of work — and it MUST NOT be reported as "nothing is missing."** (I7, R10) |

> **The `unknown` case is where the system lies to the owner if we get this wrong.** *(`SCAR`: an unreadable page rendered as "every invoice is paid in full.")*

### 14.4 Dependency on Fork B `PROVISIONAL`
**Continuous absence detection requires continuous observation, which requires a live session.** Under Fork B assumption (a) — human-established sessions only — **§14 can only run while a human is logged in.** This is the tension named in §4.3. The architecture MUST therefore:
- treat "no session" as producing **`unknown`**, never `absent`;
- **surface the blindness explicitly** ("I have not been able to check X since T") — honest health (§25);
- keep the Expectation model **independent of how observation is achieved**, so that resolving Fork B changes coverage, not design.

---

# PART III — THE SYSTEM

## §15. Service Architecture & Boundaries

### 15.1 Decomposition posture — start as a modular monolith
**MUST:** the system begins as a **single deployable with rigorously enforced internal boundaries**, not as distributed microservices.

**Rationale (P36 — minimize architectural surface area):** every service, queue, and network hop is a permanent failure mode and a permanent maintenance liability. Distribution is a *response to a scaling or isolation constraint we do not yet have*. **The best component is the one we did not add.**

**Boundaries are enforced in code** (module ownership, no cross-module state writes) so that extraction into separate deployables later is **mechanical, not archaeological**.

### 15.2 The service map

| Service | Owns | State class |
|---|---|---|
| **Ingestion & Observation** | Turning external signals into **Observations** (§9.1). One adapter per channel. | Projected (L1) |
| **Identity & Correlation** | Binding claims (§10). | Native |
| **Projection & Reconciliation** | The canonical projection, reconciliation, conflicts (§6). | Projected (L4) + Native (conflicts) |
| **Work & Loop Orchestration** | Work items, expectations, exceptions, lifecycles (§12–§14). | Native |
| **Action Pipeline** | **The single effect boundary** (§19). | Native (attempts, verifications) |
| **Safety Kernel** | Policy, fences, caps, autonomy, security events (§20). | Native |
| **Approval & Oversight** | Approvals, decision packets, escalations, the brake (§21). | Native |
| **Knowledge** | Company rules, corrections, retrieval (§22). | Native |
| **Agent Runtime** | Bounded agents; a **client** of the Action Pipeline (§23). | Native (agent steps as evidence) |
| **Integration & Actuation** | Capability contracts to the outside world (§18). | — |
| **Audit & Replay** | The event/audit record, traversal, replay (§25). | Native |

### 15.3 Boundary rules
- **One capability, one owner, one body of state.** If two modules must write the same fact, **the boundary is wrong** (§2.6 of the Principles).
- **No shared writable state across a boundary.** Reads across boundaries go through a contract.
- **A module that does routing, validation, execution, rendering, and persistence is a liability, not a service.** *(`SCAR`: a ~2,000-line module in the current system does exactly this.)*

---

## §16. Data Architecture

### 16.1 Stores (logical — physical mapping justified, not assumed)

| Store | Contents | Class | Properties |
|---|---|---|---|
| **Observation store** | Raw sourced values (§9.1) | Projected | **Immutable, append-only.** |
| **Event store** | Domain events (§11) | Native | **Immutable, append-only, ordered per partition.** |
| **Claim store** | Inferences + correction history (§9.2) | Native | Append-only + corrections. |
| **Lineage store** | Observation/Claim → canonical field links (§6 L3) | Native | Append-only. |
| **Projection store** | Materialized typed records + field status (§6 L4) | Derived | **Rebuildable. Disposable.** |
| **Document/blob store** | Source documents | Projected | Immutable; provenance-linked (I5). |
| **Knowledge store** | Company rules, corrections (§22) | Native | Versioned, revocable. |

### 16.2 The physical schema is an open decision
**MUST NOT** be assumed from ADR-001's "field-level provenance." The **unit of provenance is the field; the unit of operational state is a typed domain record** (ADR-002 §2).
Any physical design MUST justify how it satisfies §6 L1–L5 **without** forcing business queries onto attributed-cell objects. **`NEEDS VALIDATION` against real query patterns before it is fixed.**

### 16.3 Rebuildability (the load-bearing test)
**MUST:** the projection store is **rebuildable from the observation store + the event store**, and this is **verified continuously in CI** (§28).

> **If we cannot rebuild it, it has silently become authoritative** (ADR-001 C2). This test is the only thing standing between "a derived projection" and "an undeclared source of truth."

### 16.4 Retention, legal hold, PII
- **49 CFR §371.3** requires brokers to keep a transaction record per shipment (`CONFIRMED INDUSTRY PATTERN`). Retention policy MUST accommodate it.
- Evidence is **kept, not summarized away** (§2.3 of the Principles).
- PII classification and handling MUST be explicit (§24). Communications contain PII by default.

### 16.5 Tenancy
Tenant partitioning is **structural** (§7.1). Cross-tenant access MUST be **impossible**, not merely denied (R15).

---

## §17. The Event Backbone

### 17.1 Delivery semantics
**MUST assume at-least-once delivery.** **A system that assumes exactly-once will double-act** (§4.2 of the Principles).
Therefore: **every consumer MUST be idempotent** (P8).

### 17.2 Ordering
Ordering is guaranteed **per partition only**. The partition key SHOULD be the entity or work item the events concern. **Global ordering MUST NOT be assumed anywhere.**

### 17.3 Events vs commands
Enforced at the boundary (§11.1). **A command MUST NOT be published as an event**, and a consumer MUST NOT treat an event as an instruction.

### 17.4 Failure handling
Explicit, bounded, recorded retries; a dead-letter path that is **visible, not silent** (R3, R17). **A dead letter is an exception (§13), not a log line.**

### 17.5 Replay
The stream MUST be replayable **without side-effects** (§4.7, §25.4).

---

## §18. Integration & Actuation Layer

### 18.1 The bimodal reality (`CONFIRMED INDUSTRY PATTERN`)
Load boards and visibility platforms have **real APIs**. Facility portals, customer portals, and many small TMSs are **human-operated web UIs with no API** (Freight Discovery §6.2).

**Both MUST be first-class.** Browser operation is **not a hack to be replaced later** — it is a permanent, structural requirement of this domain.

### 18.2 The uniform Capability Contract
**MUST:** every external system is expressed through **one capability contract**, regardless of how it is reached.

| Capability | Notes |
|---|---|
| **Observe** | Read a source into Observations (§9.1). |
| **Act** | Perform an effect. **Only reachable through §19.** |
| **Verify** | Read back the result of an effect (P5). |

Adapters differ (API / browser / email / SMS). **Callers MUST NOT know which.** This is what makes "operate any system" true rather than aspirational — and it is what allows an API to replace a browser adapter with **no change above the boundary**.

### 18.3 Adapter failure taxonomy
Every adapter MUST classify its failures into: **transient · deterministic · unknown-outcome · unavailable (no session)**. An unclassified failure defaults to **`unknown`** and **fails closed** (P6, §26).

### 18.4 Session & credential architecture `PROVISIONAL — FORK B`
**MUST:** a **`SessionProvider`** abstraction with two implementations (§4.3):
- **(a)** human-established session *(default)*
- **(b)** per-tenant credential vault — capability-scoped, short-lived, fully audited

**MUST NOT:** write any actuation path that assumes a session always exists. Every observation path MUST define its behaviour when **no session is available**: it produces **`unknown`**, never `absent` (§14.3).

### 18.5 Concurrency
The current system's **single global browser lock serializes all work** (`REPO_CONFIRMED` defect). The target architecture MUST support **concurrent observation and actuation across multiple systems**, bounded per tenant and per external system (§27).

### 18.6 Inbound content is untrusted at the boundary
Everything an adapter returns is **untrusted data** (P13). It is marked as such **at the point of ingestion**, and that marking MUST survive into every downstream use (§24).

---

## §19. The Action Pipeline — The Effect Boundary

> **This is the most important section in this document.**
> **Every effect on the outside world passes through exactly one pipeline. If there are two ways to reach the world, the safety model is a fiction** (P18, R14).

### 19.1 The mandatory stage order
**MUST**, in this order, without exception (§3.4 of the Principles):

```
  Intent
    → Policy check                 (Safety Kernel, §20)
    → Deterministic validation     (§20; R6)
    → Freshness revalidation       (§6.4.3 — against the authoritative source)
    → Human gate                   (§21, if the action class requires it)
    → Commit-key reservation       (§19.5)
    → Execute                      (§18)
    → Verify by readback           (§19.6; P5)
    → Record                       (§19.7; I10)
    → Update projection            (§6.4.2 — from the verified readback, never from intent)
```

**The model has no seat in this chain after it proposes** (§3.4). An agent may originate an *intent*; it may not skip, reorder, or reach past any stage.

### 19.2 Action classes
Every action belongs to a class carrying its gate requirements, caps, reversibility, and verification method. **Class membership is data, not code branching** — so a policy change (§7.6 of the Operating Model) is a **configuration decision with an audit trail**, not a code change.

### 19.3 Runtime-supplied consequential values (P3, R7)
**MUST:** all consequential values — **amounts, file paths, recipients, identifiers, target records** — are **supplied by the runtime**, never originated by the model.
The model may say *"put the amount here."* It may never say *what* the amount is.
> *A model that can name a file path can name **any** file path.* (`SCAR` — the document fence)

### 19.4 Freshness revalidation
A consequential action MUST **revalidate the fields it depends on against the authoritative source at execution time** (ADR-001 C4). **The projection is never sufficient to authorize an effect.**
If revalidation returns `conflicting`, `unknown`, or `stale`-beyond-policy → **the action MUST NOT proceed** (§6.4.4). It escalates.

### 19.5 Idempotency and commit-once (P8)
- Every effect has a **durable commit key** derived from the logical work, not from a retry counter.
- The key is **reserved before execution** and **resolved after verification**.
- **After any crash, the system MUST be able to determine whether the effect landed.** This is a **design requirement, not an operational hope**.
> **`SCAR`:** a crash *after* reserving a commit and *before* confirming it caused a later retry to report a false `DONE` **with no write having occurred.** A supervisor that restarts crashed workers will find every one of these holes.

### 19.6 Verify by readback (P5, R9)
**Verification is a pipeline stage, not the caller's responsibility.** An effect that has not been read back and confirmed is **unverified**, not complete.
> **`SCAR`:** an agent reported `DONE` after clicking a button that merely *opened a form*. **Real signal, not a proxy.**

### 19.7 Recording (I10)
**Recording is part of the effect, not a step after it.** An action that succeeded but was not recorded is a defect of the highest severity — **an unrecorded effect is an effect nobody can reverse.**

### 19.8 The unknown-outcome protocol (§26)
If execution returns an **unknown outcome** (timeout, disconnect, crash), the pipeline MUST **verify** — it MUST NOT blindly retry, and it MUST NOT assume failure. **This is the single most dangerous state in the system.**

---

## §20. Guardrails & the Safety Kernel

> **The wall around the model, enforced in code the model cannot reach.**
> **Deliberately specified before agents (§23), because order encodes intent:** the fence exists first, and agents are introduced as clients that cannot bypass it. *A prompt is not a security boundary* (P13, R8).

### 20.1 The consequential-value fence (generalizes the money and document fences)
**MUST:** any value that (a) moves money, (b) selects a resource, (c) identifies a counterparty, or (d) addresses an outbound message, is **runtime-supplied** and **structurally unreachable by the model** (P3, R7).

### 20.2 The policy engine
Evaluates, in code, at the effect boundary (§19.1):
- **Caps** — value, counterparty, frequency, daily volume.
- **Authority** — the §7.3 matrix.
- **Autonomy state** — what this workflow has *earned* (§20.5).
- **Allowlists** — navigable domains, permitted recipients, permitted action classes.

**Policy MUST be evaluated at the boundary of the effect**, not merely at the point of intent. *Checking only at intake means every future caller must remember to check* (§3.4).

### 20.3 Fail-closed as a kernel behaviour (P6, R10)
Fail-closed is **a property of the kernel, not a choice each caller makes.** Ambiguity, an unreadable source, an unbindable reference, a timeout, a `conflicting` or `unknown` field — **all resolve to "stop and ask."** Never to "proceed," and never to "nothing to do."

### 20.4 Policy violations are security events
**MUST:** a model output that violates policy is **discarded, and the violation is recorded as a security event** (§24) — **not silently corrected and forgotten.**
> **A model attempting a forbidden action is *signal*.** Throwing that signal away means never finding out we were being probed.

### 20.5 Autonomy and the brake (P14)
- Autonomy is **per (tenant, workflow, action class)**, **earned**, and **capped**.
- Granting, changing, or revoking autonomy is an **explicit, audited event** — **never a code deploy, never a config drift** (Operating Model §7.6: *never by erosion*).
- **A human brake MUST exist and MUST actually stop the system.** Its correctness is tested like any other safety property (§28).

### 20.6 The permanent capability (Operating Model §7.5)
**The capability to gate, audit, and reverse any action MUST exist permanently in the architecture — regardless of which gates a given tenant or era has switched on.**
> **Losing the capability is irreversible. Relaxing a policy is not. Never trade the first to get the second.**

---

## §21. Human Approval, Escalation & the Oversight Surface

*The human is part of the system, not an escape hatch (§2.8 of the Principles).*

### 21.1 The Approval object (P12, R4)
**MUST** be: **per-action · single-use · bound to the specific effect · time-limited · attributable to an authorized human** (§7.3).
**MUST NOT** be: a mode, a session-wide blanket, a role setting, or **implicit in silence**. *Silence is not consent.*

### 21.2 The Decision Packet (I12)
An escalation MUST carry everything needed to decide:

| Contents | Why |
|---|---|
| What happened, and what the system **saw** | Evidence, not assertion (P4) |
| What it **proposes**, and why | The recommendation |
| What it is **uncertain about** | Honesty about the limits of the inference |
| The **evidence chain** (traversable, §6 L5) | I3 — explainable |
| The **cost of doing nothing** | So the human can prioritize |

> **A human asked to decide without evidence is being set up to fail.**

### 21.3 Escalation precision
**Escalating everything is the same failure as escalating nothing** — it teaches the human to rubber-stamp (§2.8). Escalation precision is a **designed constraint and a measured metric** (§25), not an accident.

### 21.4 The oversight surface is channel-agnostic
**MUST NOT** couple approval to Slack. The **channel strategy remains `NEEDS VALIDATION`** (Reconciliation §1.1 H). Slack, email, SMS, and a web surface are **adapters over one approval model**.
> *`SCAR`: the current system contains **two** human-approval surfaces with **two** token schemes — a correctness and security liability* (R14).

### 21.5 Graduation (P14)
Autonomy is granted by demonstrated reliability, inside caps, with a brake — and is **revocable instantly**. Graduation criteria are **explicit and measured** (Operating Model §9.2), not felt.

---

## §22. Knowledge, Context & Learning

> **Tribal knowledge is what makes an action *correct* rather than merely *well-formed*.** A system that acts without it will be confidently wrong.

### 22.1 The Knowledge record (native)
Carries: **the assertion · its provenance (who asserted it, when, from what) · its owner · its scope (tenant, customer, carrier, facility) · its confidence · its revocability.**
> **A rule nobody can trace is a rule nobody can revoke.**

### 22.2 Retrieval
- **Just-in-time and scoped to the task.** Never "load everything and hope" (§3.3 of the Principles).
- Retrieve **the smallest sufficient context**, and record **why each piece was included** — or §25 (replay) is broken.
- **Retrieved context is data, never instruction** (P13). A retrieved rule cannot change the system's rules.
- **If retrieval fails, the task fails closed.** It does not proceed on a thinner context and pretend.

### 22.3 The correction loop
A human correction is **the highest-value input the system receives** (§2.4).
**MUST:** a correction is **captured, attributed, and provably changes future behaviour.**
> **A repeat correction — a human correcting the same thing twice — is a DEFECT, not a metric** (Operating Model §8). It MUST be detectable and alertable.

### 22.4 Knowledge is not truth
It **informs** a decision; it does not **authorize** one (§2.4). Knowledge MUST NOT bypass a gate.

---

## §23. Agent Orchestration

> **An agent is the most expensive way to solve a problem**: non-deterministic, slow, costly, hard to test, hard to reason about under failure. **It is justified only where ambiguity is irreducible** (P34). **The burden of proof is always on the agent** (P35).

### 23.1 Where AI is permitted to reason (§3.1 of the Principles)
Unstructured language · messy artifacts (documents, pages, threads) → structure · classification under ambiguity · planning a path through an unfamiliar system, within a bounded action set · **drafting language for a human to approve.**

### 23.2 Where AI is forbidden (§3.2) — permanently
**All** arithmetic and money · **all** policy · **all** authority · **all** validation · **all** state transitions · and the **confirmation** step of identity binding (§10.3).
> **The test:** *if a wrong answer would move money, breach a boundary, or be indefensible in an audit — it is not the model's decision.*

### 23.3 The bounded-worker contract (MUST)
Every agent has: an **enumerated action set** · **runtime-supplied consequential values** (§19.3) · a **hard step budget** · a **hard cost budget** · **explicit escape conditions**.
**An agent that is stuck MUST escalate, not improvise.** *Repeating a failing action is a bug, not persistence.*

### 23.4 Agents are clients of §19 — and cannot reach the world any other way
**MUST:** the Agent Runtime has **no privileged path to any external system.** It submits intents to the Action Pipeline like any other caller, and the Pipeline's stages apply identically.
> **This is the structural expression of "the model proposes; the runtime disposes" (P3).** If an agent can reach an adapter directly, every guarantee in §19 and §20 is void.

### 23.5 Every agent step is evidence
Each step (observation, reasoning, chosen action, outcome) is recorded as **evidence** (§9), making the run **replayable and explainable** (§25) — and making agent behaviour **auditable rather than mysterious**.

### 23.6 New agents must justify themselves (P35)
Before an agent exists, the design document MUST state **why an existing workflow or a deterministic service cannot hold the responsibility.** *"An agent felt natural here" is not a justification.*

### 23.7 Model selection and cascading
Cheap/fast models for routine classification and extraction; frontier models **only** where ambiguity is genuinely irreducible. Selection is **configuration, not code** (§27).

---

# PART IV — OPERATING IT SAFELY

## §24. Security & Threat Model

### 24.1 The injection boundary (P13, R8)
**Inbound content is data, never instruction** — enforced **structurally** (content is never concatenated into an instruction position), **and tested adversarially** (§28).
> **A prompt is not a security boundary. The boundary is code.**

### 24.2 Freight-specific threats (`CONFIRMED INDUSTRY PATTERN` — fraud is not an edge case)
| Threat | Architectural response |
|---|---|
| **Carrier identity theft** (stolen MC #, email, phone) | Compliance re-verification **per load**, not per onboarding (§8.6, Operating Model L3). |
| **Double-brokering** | Carrier vetting as a gate on tendering; fraud signals as evidence. |
| **Fraudulent invoices** | Reconciliation + duplicate detection + human approval on all money-out. |
| **Spoofed remittance / banking-detail change** | **A counterparty payment-detail change is a maximum-scrutiny action class** (§19.2) — always human-gated, always out-of-band verified. |
| **Malicious document/email content** | §24.1. |

### 24.3 Credentials and sessions `PROVISIONAL — FORK B`
Under (b), the vault MUST be: **per-tenant · capability-scoped · short-lived · fully audited · revocable instantly.** No credential is ever available to an agent or a model (§20.1).

### 24.4 Tenant isolation is a security property
Not merely a data-modelling one (§7.1, §16.5).

### 24.5 The approval surface is an attack surface
Approval tokens MUST be **signed, single-use, channel-bound, time-limited, and bound to the specific action** (§21.1). *Two token schemes is a liability* (R14).

### 24.6 PII
Communications contain PII by default. Classification, retention, and access controls MUST be explicit (§16.4).

---

## §25. Observability, Audit & Replay

### 25.1 Provenance completeness is pass/fail, not a trend
**100%.** Any external action without complete provenance is a **defect** (P7, I2). This is measured continuously.

### 25.2 Tracing
Every unit of work is traceable end to end: **trigger → decision → action → verification → outcome**, with lineage intact and traversable (§6 L5).

### 25.3 Explainability (I3)
The system MUST be able to answer **"why did you do that?"** — *in plain language, to a person who is angry* — **by reconstruction, not recollection.**

### 25.4 Replay (P9, I6)
- Replay MUST be **side-effect free**. Reconstructing history MUST NOT re-execute it.
- Replay MUST reconstruct **what the system knew at the time** — not what we know now (I6).
> *Judging a past decision by present knowledge is hindsight, not audit. A system that cannot show what it knew then can be neither fairly evaluated nor fairly improved.*
- **Replay is also a correctness test**: rebuilding the projection from observations + events is the enforcement of ADR-001 C2 (§16.3, §28).

### 25.5 Honest health (R17)
- A health surface MUST report **blind as blind**, never as green.
> *`SCAR`: a health surface reported green while the system could not read the page it was reporting on.*
- **Silence is alarming.** A component that stops emitting is **presumed broken**, never presumed idle.
- **Blindness is announced**: *"I have not been able to check X since T"* (§14.4).

### 25.6 Metrics — outcomes, not activity
Measured (Operating Model §8): delivered→invoiced latency · invoiced→paid latency · dollars of incorrect carrier charges caught **before** payment · **dollars paid in error (target: zero)** · work removed · **loop closure rate** · exception age · escalation precision · **repeat corrections (a defect)** · approval latency.

**Explicitly rejected as vanity** (P20): messages sent · AI calls · tasks processed · automation % · engagement.

### 25.7 Silent failures are P0
Any action that failed and was **not surfaced** is a Sev-0 defect (R17).

---

## §26. Reliability, Failure & Recovery

### 26.1 Failure taxonomy
| Class | Response |
|---|---|
| **Transient** | Bounded, recorded retry (idempotent operations only). |
| **Deterministic** | **Do not retry.** Retrying a deterministic failure is a busy-loop, not resilience. Escalate. |
| **Unknown-outcome** | **The dangerous one. VERIFY.** Never blindly retry; never assume failure (§19.8). |
| **Unavailable** (no session, system down) | Produce **`unknown`**, fail closed, **announce the blindness** (§25.5). |

### 26.2 Retries (R3)
**Explicit, bounded, recorded. Never silent, never infinite.** Only **idempotent** operations may be retried automatically. **A retry MUST know why it is retrying.**

### 26.3 Compensation (§4.5 of the Principles)
- **Reversibility is preferred to cleverness.**
- Where an action **cannot** be reversed, it earns **a stronger gate before it** — **not a compensation story after it.** *"We'll fix it afterwards" is not a safety model for money.*
- A compensating action is **itself** an action: gated, verified, idempotent, recorded.

### 26.4 Crash-safety is a precondition of automatic restart
**MUST:** after any crash, the system can determine **whether the effect landed** (§19.5). **A supervisor that restarts crashed workers will find every hole in this — and turn each one into a double-effect or a false completion.**

### 26.5 Degradation announces itself (R17)
A degraded system **never quietly does less while appearing to do everything.**

---

## §27. Performance, Latency & Cost Envelope

*Physics is an architectural constraint, not a tuning parameter.*

### 27.1 Latency classes
| Class | Budget | Pattern |
|---|---|---|
| **Human-interactive** (a question in a chat surface) | **Sub-second acknowledge**, bounded answer | **Fast-acknowledge + deferred result is an architectural pattern, not a patch.** |
| **Human-gated action** | Ack immediately; execute in background; **post a verified receipt** | Never block a human surface on an agent run. |
| **Background reconciliation** | Minutes | Freshness policy (§6.5) governs. |

> **`SCAR`:** a synchronous read exceeded a 3-second interaction timeout in the current system. **The fix is architectural, not a faster query.**

### 27.2 Model cost and cascading
Cost per **closed loop** is the unit economic (P24) — **not cost per call.** Cheap models for routine work; frontier models only for irreducible ambiguity (§23.7). Every agent has a **hard cost budget** (§23.3).

### 27.3 Concurrency
The current single global browser lock **serializes everything** (`REPO_CONFIRMED`). The target MUST support **concurrent observation and actuation**, bounded per tenant and per external system (rate limits, session limits) — **and the bound MUST be explicit, not emergent** (§18.5).

### 27.4 Read economics
The projection (§6) exists partly to retire **scrape-on-every-read** (ADR-001 C8). Freshness checks are **deliberate and targeted**, not implicit and constant.

---

## §28. Testing & Verification Architecture

*Correctness is **established**, not asserted.*

### 28.1 Determinism is tested exhaustively
Money, policy, authority, validation, state transitions, reconciliation rules, identity confirmation — **anything with a right answer gets tests that pin the right answer** (§4.8).

### 28.2 Non-determinism is BOUNDED, not asserted
**MUST NOT** test that a model produces a specific sentence.
**MUST** test that **the fence holds no matter what the model says.**
> **The correct test of the money fence is: the model *tries* to inject a value, and the value never reaches the world.** The correct test of the document fence is: the model *tries* to name a path, and the path is ignored. **Adversarial-by-construction.**

### 28.3 Failure injection is a first-class harness
Hostile states MUST be **deliberately produced**, because they **cannot be reliably provoked against a live system** — and they are exactly where the money is lost:
stale pages · partial renders · expired sessions · **mid-write crashes** · duplicate deliveries · unreadable documents · **conflicting sources** · **absent vs. unknown** · adapter timeouts with unknown outcome.

> **This is where the mock estate flagged in the Reconciliation earns its second life.** It is **removed from every production path** (`tms_write.py` is currently live-reachable — a `REPO_CONFIRMED` risk), and **retained, if and only if justified, as deterministic test fixtures, contract-test infrastructure, and failure-injection tooling.** That evaluation is a task of §30, not an assumption of this section.

### 28.4 Contract tests
Every adapter MUST be verified against the **Capability Contract** (§18.2), so an API adapter can replace a browser adapter with **no change above the boundary**.

### 28.5 Rebuildability test (ADR-001 C2)
**Continuous:** rebuild the projection from observations + events; assert equivalence. **A failure here means the projection has become authoritative without anyone deciding.**

### 28.6 The live-drive gate (P17)
> **Every test suite is a hypothesis until the workflow has run live.**
> **`SCAR`: green tests were reported as evidence of a capability that had never once been run against the real system.**

**MUST:** no workflow is released until it has been **driven end-to-end against the real system and observed working.** **A green suite does not satisfy this.**

### 28.7 Production-readiness is mechanically enforced
The Definition of Production-Ready (Principles §6) is a **release gate applied per workflow**, checked in CI where mechanizable and in review where not.

---

## §29. Deployment, Environments & Runtime Topology

### 29.1 The current posture is not a production posture
A laptop, a dev tunnel, and a human-logged-in browser (`REPO_CONFIRMED`). This is stated so it cannot be mistaken for a starting point.

### 29.2 Runtime
Single deployable (§15.1) + a **separate, isolated actuation runtime** for browser sessions (which have distinct lifecycle, memory, and failure characteristics), + background workers for reconciliation and expectation evaluation.

### 29.3 Environments
A hard production/non-production boundary. **No production credential, tenant, or external system is reachable from a non-production environment** — structurally.

### 29.4 Configuration, secrets, policy flags
- Secrets are **never in code, never in an agent's reach** (§20.1).
- **Policy gates (Operating Model §7.6) are switched deliberately and auditably** — a change to a gate is an **event with an actor and a reason** (§20.5), never a quiet config edit.
> **This is the mechanism that prevents erosion** — the failure mode the Operating Model explicitly named.

### 29.5 Supervision
Restart is safe **only because** §19.5 makes crash-safety a design property (§26.4). Supervision without crash-safety **manufactures double-effects**.

### 29.6 Runbooks
Every degradation mode in §26 has a documented human response.

---

# PART V — GETTING THERE

## §30. Migration from the Current System

### 30.1 ⛔ BLOCKING PREREQUISITE
> **There is no clean baseline to migrate from.** The working tree carries uncommitted changes of **mixed and partly unattributed authorship**, plus dead code in a live module (Reconciliation §0.3).
>
> **MUST:** establish a **committed, attributed, test-green baseline** before any migration work begins. **A rewrite forked from an unreconciled tree silently inherits changes nobody has reviewed.**

### 30.2 Carried forward (the assets)
The **safety spine** (money fence, document fence, approve-to-act, verify-by-readback, commit-once, fail-closed, injection boundary) · the **CDP actuation core** · the **deterministic reconciliation engine** · the **template-free extraction stack** · the **state-machine/audit/idempotency discipline** · the **lane-graduation model**.

### 30.3 Severed immediately
- **The mock write path (`tms_write.py`) is reachable from the live stack** — an active risk. **Sever from every production path**, regardless of what §28.3 decides about its retention as test infrastructure.
- **ngrok** as any part of a production posture.

### 30.4 Deprecated
The **duplicate legacy review surface and its parallel approval-token scheme** (R14) · the **redundant orchestrators** (two of three must die) · the **pilot instrumentation**.
> **P37: remove before you add.** *Two lineages, two approval surfaces, three orchestrators — every one added in good faith, not one ever removed.*

### 30.5 Strangler sequence
1. Establish the baseline (§30.1).
2. Build the **spine**: §19 (Action Pipeline) + §20 (Safety Kernel) + §21 (Approval) — **behind the existing behaviour**.
3. Route **one** existing capability through the new spine; verify identical outcomes live.
4. Migrate observation → projection (§6) for that capability's data.
5. Delete the old path. **Deletion is part of the step, not a follow-up ticket** (P37).
6. Repeat.

**No big-bang rewrite.** **No parallel second system** (R14) — the strangler is a *migration*, not a permanent duality.

### 30.6 Data migration
There is **no existing domain model** to migrate (`REPO_CONFIRMED` — only a run log). The projection is therefore **built from observation forward**, not back-filled from a model that never existed. Historical run/audit data is **retained as evidence**, not converted into domain state.

---

## §31. Implementation Sequencing

### 31.1 The spine before any loop
**MUST:** nothing runs until §19, §20, §21 exist. **A loop without the effect boundary is a loop with no safety model.**

### 31.2 Then: one loop, closed completely
> **Start with one loop. Close it completely. Make it boring. Only then take the next one** (Operating Model §9.1).

### 31.3 The four gates for choosing a loop (Operating Model §9.5)
**Pain** (does it cost real money/hours today?) · **Truth** (is there something to check against?) · **Surface** (can we observe and act?) · **Blast radius** (how bad if wrong; can it be undone?).

### 31.4 First loop `HYPOTHESIS — NEEDS VALIDATION`
The evidence points at **Documentation → Billing (L6 → L8)**: acute pain, checkable truth, reachable surface, bounded and reversible blast radius. **This is not yet a decision** — it must be validated against the design partner's actual pain (Freight Discovery §13).

### 31.5 Per-loop release gate
Each loop passes the **Definition of Production-Ready** (Principles §6) — including §6.6: **driven end-to-end against the real system, with failure modes deliberately provoked.**

### 31.6 Expansion (Operating Model §9.3–9.4)
Expansion means **only**: deeper autonomy in a loop we already run, or a new loop **riding the same spine**.
It **never** means a disconnected feature, a second spine, a second way to do something, or **widening scope to hide that the current loop isn't closing.**

### 31.7 Honest progress reporting
Progress is reported as **loops closed** — never as actions taken (P24, §25.6).

---

## §32. Governance & Evolution of This Document

### 32.1 ADRs
Every fork closed, every SHOULD departed from, and every change to this document is recorded as an **ADR** (Appendix A). **An architectural change made without an ADR is drift, not a decision.**

### 32.2 The seven-question change process (Principles §11)
Every architectural change answers, in writing, before it is built: *why does this exist · which principle supports it · **what scar or operational observation motivated it** · what problem does it solve · what complexity does it introduce · what existing capability could it replace · **what future maintenance cost does it create**.*
**Questions 3 and 7 are hard gates.** *We do not build for imagined pain. An unpriced maintenance cost is a debt taken out in someone else's name.*

### 32.3 Closing an open fork
When a `NEEDS VALIDATION` assumption (§4) is validated or refuted: an **ADR** records it; **every section marked `PROVISIONAL` on that assumption is revisited**; and what breaks (§4.2, §4.3) is checked against reality.

### 32.4 Conflict with the frozen layer
If this architecture conflicts with the Operating Model or the Principles: **the higher document is amended deliberately, in writing, with its reason — or this architecture is wrong.**
**There is no third option, and there are no silent exceptions** (Principles §12.2).

---

# APPENDICES

### Appendix A — ADR Index
| ADR | Title | Status |
|---|---|---|
| **ADR-001** | The Authority Model: Canonical Operational Projection | ACCEPTED |
| **ADR-002** | State Classes and the Lineage Model | ACCEPTED |
| *ADR-003* | *Load-family relationships* | **OPEN — `NEEDS VALIDATION` (Fork A)** |
| *ADR-004* | *Credential and session posture* | **OPEN — `NEEDS VALIDATION` (Fork B)** |
| *ADR-005* | *Physical schema for the lineage model* | **OPEN — must be justified (§16.2)** |
| *ADR-006* | *Oversight channel strategy* | **OPEN — `NEEDS VALIDATION` (§21.4)** |
| *ADR-007* | *Retention of the mock estate as test infrastructure* | **OPEN (§28.3, §30.3)** |

### Appendix B — Open Questions Register
| # | Question | Blocks | Owner |
|---|---|---|---|
| B1 | Load-family relationships at the partner | §8, §10, §12, §16 schema | Rasheed (field) |
| B2 | Credential/session posture | §14 coverage, §18, §27, §31 unattended operation | Rasheed (product) |
| B3 | Partner's actual roles and approval authority | §7.2, §7.3 | Rasheed (field) |
| B4 | Partner's real TMS, and whether it has a usable API | §18 adapter cost | Rasheed (field) |
| B5 | **What is in their spreadsheets, and why isn't it in the TMS** | §8 (missing entities), §6 (a source we don't model) | Rasheed (field) |
| B6 | How accessorials are authorized in the moment, and where recorded | §8.3 — whether reconciliation can ever be *correct* | Rasheed (field) |
| B7 | Which loop is first | §31.4 | Rasheed (product) |
| B8 | Physical schema | §16.2 | Architecture (needs query patterns) |
| B9 | Oversight channel strategy | §21.4 | Rasheed (product) |
| B10 | Repository hygiene resolution | **§30 — blocks ALL implementation** | Rasheed (now) |

### Appendix C — Traceability Matrix
See **§5**. Every Operating-Model binding, every invariant I1–I12, and every load-bearing refusal maps to a discharging section. **A binding with no discharging section is a hole in the architecture.**

### Appendix D — Glossary
See **§3**. The canonical vocabulary is normative: **one name per concept, forever.**

---

## Closing statement

This architecture is designed around a single conviction, inherited from the constitution and earned from real defects:

> **Be deterministic where it matters. Be honest about what you don't know. Never let the model touch the money. Prove it happened before you say it did. And earn autonomy instead of assuming it.**

Everything above is machinery in service of that. **If any part of this document is found to contradict the frozen layer above it, this document is wrong** — and it will be changed deliberately, in writing, with its reason.
