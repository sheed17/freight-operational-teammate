# Neyma — The Operator and the Customer-Discovery Model

> **CANONICAL (navigation) — product consolidation.** This document formalizes the **Neyma
> Operator** as the single top-level coordinating and implementation-learning role, and the
> **customer-discovery / deployment lifecycle** it runs. **It holds NO authority independent of its
> sources and creates NO new product decision, no new operational loop, no new source of truth, and
> no new effect authority.** On any conflict the cited source wins:
> product identity → [`PRODUCT.md`](../../PRODUCT.md); the conversational identity →
> [`ADR-019`](../architecture/decisions/ADR-019-conversational-operations-layer.md); onboarding,
> tenant lifecycle and the control plane → [`ADR-017`](../architecture/decisions/ADR-017-tenant-and-integration-lifecycle.md);
> the operational graph and the Operational System Map →
> [`ADR-018`](../architecture/decisions/ADR-018-customer-operational-graph.md) and
> [`operational-system-map.md`](../specifications/operational-system-map.md); authority migration →
> [`ADR-013`](../architecture/decisions/ADR-013-workflow-authority-migration.md); policy, rules,
> autonomy and the change process → [`ADR-010`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md);
> the effect boundary → [`ADR-004`](../architecture/decisions/ADR-004-effect-boundary.md); the five
> capability verbs and the eleven loops → [`operating-model.md`](operating-model.md);
> **current implementation status → [`CURRENT.md`](../implementation/CURRENT.md)** (this file copies
> no volatile commit/suite figure and states no phase as complete or any capability as implemented).
>
> **Companion documents:** [`FREIGHT-OPERATING-VISION.md`](FREIGHT-OPERATING-VISION.md) ·
> [`OPERATIONAL-LOOPS.md`](OPERATIONAL-LOOPS.md) · [`AUTONOMY-MATRIX.md`](AUTONOMY-MATRIX.md) ·
> [`QUOTE-TO-CASH-LIFECYCLE.md`](QUOTE-TO-CASH-LIFECYCLE.md) ·
> [`FREIGHT-CAPABILITY-MAP.md`](FREIGHT-CAPABILITY-MAP.md).

---

## 0. Naming — three different "operators", kept apart

The word *operator* is already overloaded in this repository, and conflating the three is a defect.

| Term | Meaning | Notes |
|---|---|---|
| **human operator** (the operator, the owner-operator) | the accountable **person** at the brokerage | the dominant meaning across [`operating-model.md`](operating-model.md), the ADRs and the owner-operator docs. The human stays in the operating seat ([`PRODUCT.md §5`](../../PRODUCT.md)). |
| **the Neyma Operator** *(this document)* | the single top-level **AI coordinating + conversational + implementation-learning role** the human operator talks to | a **presentation/coordination surface over the canonical spine** — a persona, not a runtime orchestrator. It **proposes; it never disposes.** |
| the legacy `operator_*` / `brain_*` code | the pre-reset `operator_brain.py` / `brain_operator.py` / `operator_agent.py` / `operation_router.py` cluster | ### **This is NOT the Neyma Operator.** It is the non-canonical "second orchestration system" scheduled for **REWRITE → P6** ([`LEGACY-DISPOSITION.md`](../implementation/LEGACY-DISPOSITION.md), Rule #16/#10). The Neyma Operator is the *canonical* role that presentation layer becomes — over the Pipeline Instance, never beside it. |

Throughout this document, **"the Operator"** means the Neyma Operator; **"the human operator"** (or
"the owner", "the accountable human") means the person.

## 1. What the Neyma Operator is

**The Neyma Operator is the one primary interface the freight company's team talks to** — an
AI operations lead that understands requests, coordinates the specialized AI teammates, tracks
cross-workflow dependencies, surfaces exceptions, requests the decisions that belong to humans, and
gives the human operator **one coherent view of the company's operations**. It is the top of the
[`ADR-019`](../architecture/decisions/ADR-019-conversational-operations-layer.md) "one coherent
Neyma identity" and the coordinating persona of **Layer C** in the three-layer model
([`OPERATIONAL-LOOPS.md §6`](OPERATIONAL-LOOPS.md): A spine · B loops W1–W11 · C teammates).

It has a **second job**: it helps **deploy Neyma into a new customer** — interviewing operators,
reading SOPs, observing systems read-only, reconstructing how the company actually operates, and
turning what it learns into **explicit, inspectable, tenant-safe artifacts** that a human approves
before anything becomes real.

> **The Operator is a role/persona, not a new component of record.** The **workflow engine remains
> the source of truth**; the Operator reads it and proposes against it. It owns **no operational
> state of its own** ([`ADR-019 §1`](../architecture/decisions/ADR-019-conversational-operations-layer.md)).

### 1.1 The operating model — one sentence and one chain

> The human operator talks to the Neyma Operator, which coordinates work over the **shared work-item
> and workflow system**, dispatches bounded domain work to **specialist AI teammates**, and reaches
> the outside world **only** through the **controlled effect boundary** — with the **evidence layer**
> supporting every claim, the **policy system** deciding authority, and a **named human** accountable
> throughout.

```
human operator
  → Neyma Operator            (coordinates, converses, learns — proposes, never disposes)
    → shared work-item & workflow system   (the source of truth: Work Items, Pipeline Instances)
      → specialist AI teammates            (bounded domain work; each emits inert ProposedIntent)
        → controlled external systems      (only via the effect boundary: checkpoint → witness → grant → adapter → verify)
```

Every consequential action still runs the full canonical pipeline regardless of who initiated it:
`Work Item → Pipeline Instance → policy & validation → optional approval → atomic checkpoint →
Checkpoint Witness → Effect Grant → atomic claim → adapter execution → verification → outcome →
evidence & projection → closure` ([`ARCHITECTURE.md`](../../ARCHITECTURE.md),
[`ADR-004`](../architecture/decisions/ADR-004-effect-boundary.md)).

## 2. Responsibilities of the Neyma Operator

The Operator decomposes onto the five canonical capability verbs
([`operating-model.md §6`](operating-model.md): **Observe · Assist · Execute · Verify · Escalate**)
and the four gate decisions
([`ADR-010`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md)). It:

- **understands requests** — interprets natural-language operator input as *proposed* intent, draft
  Work Items or structured constraints (never authority — [`ADR-019 §5`](../architecture/decisions/ADR-019-conversational-operations-layer.md));
- **coordinates the AI teammates** across sales, planning, carrier sourcing, dispatch, driver
  communication, tracking, appointments, exceptions, documents, delivered-load closure, AP, AR,
  claims, compliance, customer service, and operations management — as roles over the eleven loops
  and the two cross-cutting surfaces, **not** as disconnected bots;
- **tracks cross-workflow dependencies** — reads the atomic cross-loop handoffs
  ([`QUOTE-TO-CASH-LIFECYCLE.md`](QUOTE-TO-CASH-LIFECYCLE.md)) and shows what is waiting on what;
- **surfaces exceptions** and **requests decisions**, always **with the evidence already assembled**
  (I12; [`operating-model.md §6.2`](operating-model.md));
- **gives one coherent operational view** — *what is true, what is missing, what is open, what was
  done and under whose authority* — across every channel (web, Slack, Teams, email, mobile, voice),
  all resolving to one conversation and history ([`ADR-019 §7`](../architecture/decisions/ADR-019-conversational-operations-layer.md));
- **communicates proactively** — when a decision is required, an obligation is late, evidence
  conflicts, an outcome is unknown, a policy boundary is reached, or work completes
  ([`ADR-019 §3`](../architecture/decisions/ADR-019-conversational-operations-layer.md));
- **helps deploy Neyma** into a new customer (§6–§7).

### 2.1 What the Operator must NOT do — the boundary of the role

The Operator is powerful precisely because it is **contained**. It **cannot**:

- **be a second workflow source of truth** — the shared work-item/workflow system is authoritative;
  the Operator owns no state of its own ([`ADR-019 §1,§5`](../architecture/decisions/ADR-019-conversational-operations-layer.md)).
- **invent workflow state** — state changes come from the machines' own deterministic guards, driven
  by facts, never from a coordinating command ([`events/15-coordination-events.md`](../specifications/events/15-coordination-events.md): a coordination event does not instruct a transition).
- **be a second orchestration or a second effect-authority system** — Rules #16/#17
  ([`CLAUDE.md §5`](../../CLAUDE.md)); the **Pipeline Instance is the canonical orchestrator**, and an
  agent's only output is an inert `ProposedIntent` ([`target-system-specification.md §23`](../architecture/target-system-specification.md)).
- **directly click or write into external systems, send messages, or move money** — every external
  effect goes through the effect boundary and the two-key rule ([`ADR-004`](../architecture/decisions/ADR-004-effect-boundary.md)); it never bypasses a workflow or an adapter.
- **override evidence or provenance** — `MODEL_INFERRED` never gates; `OWNER_ASSERTED` is never
  silently overwritten ([`ADR-002`](../architecture/decisions/ADR-002-state-classes-and-lineage.md)).
- **hide uncertainty or claim completion without verification** — `UNKNOWN_OUTCOME` is stated as
  unknown, never as done ([`ADR-006`](../architecture/decisions/ADR-006-verification-and-unknown-outcomes.md), [`ADR-019 §6`](../architecture/decisions/ADR-019-conversational-operations-layer.md)).
- **silently change a customer's operations or policies inside model memory** — everything it learns
  becomes an explicit, inspectable, tenant-safe artifact a human approves (§8, §9).
- **grant itself more autonomy** — autonomy narrows automatically and broadens **only** by a human's
  recorded activation ([`ADR-010 §7`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md)).
- **exercise commercial judgment** — the sell rate, whom to trust, the words when the news is bad,
  and whether to file a claim belong to the people who own the business ([`operating-model.md §6.2`](operating-model.md)).

## 3. Relationship to the spine, loops, teammates, policy, evidence and adapters

| Layer | What it is | The Operator's relationship to it |
|---|---|---|
| **Shared spine (A)** | one work-item/load state, knowledge, evidence/provenance, policy/approvals, communications history, effect boundary, audit trail | the Operator **reads and proposes against** it; it is the source of truth, and the Operator adds no rival state |
| **The eleven loops (B, W1–W11)** | the trigger→accountable-closure execution decomposition | the Operator **coordinates** loop work and **tracks handoffs**; it does not re-implement or bypass any loop |
| **Specialist AI teammates (C)** | role personas (AI dispatcher, AP clerk, operations manager, …) operating loops/surfaces on the spine | the Operator is the **top-level coordinator** of Layer C; a teammate's completed work becomes the next teammate's context via the atomic handoff, and the Operator makes that legible to the human |
| **Policy system** | typed, versioned, deterministic authority ([`ADR-010`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md)) | the policy system **decides authority**; the Operator may **propose** policy text but never authors or activates a policy |
| **Evidence layer** | content-addressed Evidence + provenance ([`ADR-002`](../architecture/decisions/ADR-002-state-classes-and-lineage.md)/[`ADR-007`](../architecture/decisions/ADR-007-identity-claims-and-conflict.md)) | **supports every claim and decision** the Operator surfaces; the Operator never asserts without it |
| **Effect boundary** | the structurally enforced single effect boundary ([`ADR-004`](../architecture/decisions/ADR-004-effect-boundary.md)) | **controls every consequential external action**; the Operator's requests reach the world only through it |
| **Adapters** | boundaries to external systems ([`adapters/registry.md`](../specifications/adapters/registry.md)) | a boundary, **not a brain**; the Operator never calls one directly and never treats a successful write as workflow completion |

## 4. Operator modes

The Operator runs in exactly one mode per tenant per capability at a time. The modes are a
*presentation* of the canonical enforcement — they introduce **no new authority concept** and map
onto the [`AUTONOMY-MATRIX.md`](AUTONOMY-MATRIX.md) rungs and the
[`ADR-010`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md) gate decisions.

| Mode | What it does | External effects | Gate / rung | Earliest phase |
|---|---|---|---|---|
| **DISCOVERY** | read-only: interviews, observation, process mapping, historical analysis; builds the proposed tenant operating model | **NONE — read-only by construction** | `OBSERVE` | onboarding at **P11** (reads land with **P9**) |
| **SHADOW OPERATOR** | creates **internal** Work Items and *proposed* decisions; compares against what the humans actually did; produces a shadow-vs-human diff | **NONE** — no writes, no sends (gate **G6**) | `OBSERVE` / `RECOMMEND` / `DRAFT` | **P10** (wedge slice) → **P11** (deployed shadow) |
| **SUPERVISED OPERATOR** | coordinates live work; every consequential action requires **policy + human approval** and runs the full kernel | **only** via the effect boundary, per action | `HUMAN_APPROVAL_REQUIRED` | **P12** |
| **BOUNDED AUTONOMY** | only the specific low-risk action classes that have **earned** it — explicit scope, value/frequency caps, verification required, uncertainty escalates, revocable | **only** via the effect boundary, within caps | `AUTONOMOUS_WITHIN_CAPS` | **P14** |

Rules that hold in every mode ([`ADR-010`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md), [`ADR-011`](../architecture/decisions/ADR-011-human-brake.md)):
**autonomy may narrow automatically but never broaden automatically**; a human always activates any
advance; the model never chooses an amount; `MODEL_INFERRED` never gates; and the **human brake**
(admission control) is always available and only a human releases it.

## 5. Human decision boundaries — what stays with a person, always

The Operator handles the **repetitive coordination and execution** around the people who own the
business. Humans remain responsible for major relationships, unusual judgment, sensitive financial
authority, legal decisions, safety incidents, and policy setting
([`FREIGHT-OPERATING-VISION.md §3.3`](FREIGHT-OPERATING-VISION.md)). The permanent human-owned
decisions, from [`AUTONOMY-MATRIX.md §3`](AUTONOMY-MATRIX.md) and
[`operating-model.md §7`](operating-model.md):

- **the sell rate / pricing** — the model never chooses an amount;
- **carrier selection and the buy rate**, and **whether to trust a carrier**;
- **money leaving the business** — permanently `HUMAN_APPROVAL_REQUIRED`;
- **banking / remittance changes** — strong human verification; a counterparty claim is a fraud signal;
- **claims, settlement and legal commitments** — permanent human authority; Neyma does not file claims;
- **the authorization assertion** ([`ADR-003`](../architecture/decisions/ADR-003-authorization-assertion.md), PERMANENT PRODUCT TRUTH) — only an authenticated human may assert an undocumented authorization; this never graduates away;
- **bad-news / customer-impacting communications** — what to say when the news is bad;
- **any `UNKNOWN_OUTCOME`** — stop, investigate, escalate; never auto-resolves, and a timeout never becomes `FAILED`;
- **setting or changing policy, approval thresholds, and autonomy scope** (§8).

## 6. The customer-discovery / deployment lifecycle

A canonical, staged deployment process. Each stage is an **explicit, recorded decision with its
evidence**; it produces inspectable artifacts (§9); it never advances by drift. The stages compose
the tenant lifecycle of [`ADR-017 §1`](../architecture/decisions/ADR-017-tenant-and-integration-lifecycle.md)
(prospect → pilot → supervised production → general production → offboarded), the integration
lifecycle (proposed → authorized → connected → healthy/degraded → suspended → revoked), the
[`ADR-018 §5`](../architecture/decisions/ADR-018-customer-operational-graph.md) maturity ladder, and
the release gates [`G5–G10`](../specifications/acceptance/release-gates.md).

> **Discovery is read-only until a human authorizes otherwise, and every learned thing is an artifact
> before it is a behavior.** The Operator may *propose* an operating model; a human *approves* it.

### 6.1 The fifteen stages

| # | Stage | Mode | Owning phase |
|---|---|---|---|
| 1 | **Connect approved systems read-only** — integration `proposed → authorized (recorded customer authorization) → connected`; scoped machine identities preferred ([`ADR-014`](../architecture/decisions/ADR-014-credential-and-machine-identity.md)) | DISCOVERY | P11 (creds P4/P11) |
| 2 | **Ingest SOPs, customer instructions, historical examples, and configuration** — as content-addressed evidence with provenance | DISCOVERY | P9 (ingestion) / P11 |
| 3 | **Interview relevant employees** — captured as `OWNER_ASSERTED` statements, never promoted to fact | DISCOVERY | P11 |
| 4 | **Observe actual workflow execution** read-only — how work really flows across systems | DISCOVERY | P11 (reads P9) |
| 5 | **Construct a proposed tenant operating model** — the per-tenant Operational System Map ([`operational-system-map.md`](../specifications/operational-system-map.md), 15 fields) | DISCOVERY | P9/P11 |
| 6 | **Identify contradictions, gaps, exceptions, and undocumented behavior** — including SOP-vs-reality differences | DISCOVERY | P11 |
| 7 | **Produce questions requiring customer decisions** — unresolved freight rules are `NEEDS VALIDATION`, never guessed ([`OPEN-VALIDATION-ITEMS.md`](OPEN-VALIDATION-ITEMS.md)) | DISCOVERY | P11 |
| 8 | **Replay historical cases** — run the proposed workflows/rules against historical loads, emails and documents (see §7 on what replay is and is not) | SHADOW | P10 (composes P7/P9) |
| 9 | **Measure agreement, disagreement, missed exceptions, and false positives** — the shadow-vs-human diff ([`release-gates.md` G6](../specifications/acceptance/release-gates.md)) | SHADOW | P10/P11 |
| 10 | **Obtain approval for initial workflows and policies** — a human activates each (rule activation [`ADR-010 §6`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md)) | human decision | P8 (policy) |
| 11 | **Enter live shadow mode** — live reads, **zero effects** | SHADOW | P11 |
| 12 | **Compare recommendations with real employee actions** — continuous shadow-vs-human diff | SHADOW | P11 |
| 13 | **Propose versioned adjustments** — every change is a versioned, evidence-backed proposal (§8) | SHADOW → human decision | P8/P12 |
| 14 | **Promote approved configurations to supervised execution** — first live gated effects | SUPERVISED | P12 |
| 15 | **Monitor and continuously improve** — instrument outcomes; a rising `UNKNOWN_OUTCOME`/wrong-action rate is automatic demotion, never silent | SUPERVISED (→ BOUNDED AUTONOMY, earned) | P12 (→ P14) |

### 6.2 Per-stage contract

For **every** stage the following are defined and recorded:

- **inputs** — the connected systems, ingested SOPs/examples, interviews, observations, prior artifacts.
- **outputs** — the artifacts of §9 (e.g. an Operational System Map, a proposed rule, a shadow diff).
- **evidence** — content-addressed, provenance-carrying support for every claim ([`ADR-002`](../architecture/decisions/ADR-002-state-classes-and-lineage.md)); nothing asserted without it.
- **user roles** — the human operator, the tenant **Policy Owner** (a single named human per tenant, [`ADR-010 §4`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md)), and the accountable Work-Item owner.
- **approval boundary** — read/observe stages need no external authority; any activation, write or send is `HUMAN_APPROVAL_REQUIRED` (or a permanent human gate, §5).
- **failure conditions** — a missing map field, an unresolvable binding, a degraded integration, an uncompilable rule, or an unverifiable outcome — each **fails closed** and raises work with a named owner.
- **stop conditions** — an unresolved `NEEDS VALIDATION` freight rule, ambiguous ownership, two systems claiming one authority, or a required design-partner observation that is absent — the Operator **stops and asks**, it does not invent ([`CLAUDE.md §7`](../../CLAUDE.md)).
- **artifacts created** — recorded per §9, tenant-scoped and inspectable.
- **audit requirements** — every stage transition, authorization, activation and effect is attributable and reconstructable (invariants I2/I4/I10; [`ADR-017`](../architecture/decisions/ADR-017-tenant-and-integration-lifecycle.md) records each lifecycle transition with its evidence).

## 7. The workflow-learning and change process

The Operator adapts a tenant's operations **only** through an explicit, evidence-backed, versioned,
reversible chain — never by silently rewriting behavior in model memory:

```
observed mismatch → evidence collection → proposed workflow/policy change → impact explanation
  → historical replay → shadow evaluation → human approval → versioned activation → monitoring
  → rollback if required
```

This chain **reuses existing canonical machinery** and invents no new change primitive. It maps onto:
rule **compilation** (`PROPOSED → COMPILED → CONFIRMED → ACTIVE`, [`ADR-010 §6`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md)); a policy change being **itself a `HUMAN_APPROVAL_REQUIRED` action bound to its diff**; autonomy **graduation** ([`ADR-010 §7`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md)); and, where authority itself moves, the [`ADR-013`](../architecture/decisions/ADR-013-workflow-authority-migration.md) migration model.

### 7.1 Every proposed change records, before activation

Drawn from [`ADR-010`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md),
[`ADR-005`](../architecture/decisions/ADR-005-approval-binding-and-drift.md) and the
[`ADR-013`](../architecture/decisions/ADR-013-workflow-authority-migration.md) 13-field record:

- **the problem observed** — the concrete mismatch;
- **affected customers, carriers, loads, or workflows** — the scope;
- **supporting examples** — with provenance;
- **the proposed rule or workflow change** — the compiled, structured diff (not a prompt string);
- **expected impact** — what changes, for whom;
- **historical replay result** — what it would have done on past cases (§7.2);
- **risk** — blast radius and reversibility;
- **required approver** — the named human authority for that action class and value;
- **effective date** — never retroactive; an effect is judged by the policy version in force at its checkpoint;
- **version** — `policy_version` (monotonic per tenant), bound into every witness and grant;
- **rollback plan** — how the change is reversed (§7.4).

### 7.2 What replay is, and is not — stated honestly

The "historical replay" the Operator performs at stages 8–9 means **running the proposed
workflows/rules against past loads, emails and documents and comparing the result to what the
humans actually did.** Today this is a **specified/vision capability composed on foundations that do
not yet exist** — it is not a built engine. Its closest *specified* analogs are:

- the **rule test-vectors** every compiled rule ships with — *"here are three loads this rule would
  have blocked last month"* ([`ADR-010 §6.2`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md)); a rule the owner cannot see the consequences of is a rule they have not really approved; and
- the **shadow-vs-human diff** of gate **G6** ([`release-gates.md`](../specifications/acceptance/release-gates.md)).

It is **distinct** from event-sourcing *replay* ([`ADR-008`](../architecture/decisions/ADR-008-durable-workflows.md)), which is structurally inert and **cannot mint authority, witnesses or grants, or call adapters** ([`CLAUDE.md §5`](../../CLAUDE.md) rules 10/11). Historical replay is a **decision-support** exercise — it informs a human's approval; it never authorizes anything and it never writes or sends.

### 7.3 Automatic vs approval-required learning

The line is drawn by [`ADR-010`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md):
a **Product/Tenant Policy** and a **Rule** gate actions and are human-authored/activated;
**Organizational Knowledge** is non-authoritative memory that helps the Operator be useful and
**never gates anything**. Learning **informs; it never creates authority.**

| Potentially automatic **later** (still logged, still tenant-safe, still `OBSERVE`/`RECOMMEND`, never gating) | Always **approval-controlled** (a human authors/activates; the model may only propose) |
|---|---|
| document naming patterns · inbox routing · contact-routing preferences · extraction mappings · common carrier document quirks · reminder timing **within already-approved bounds** | pricing · margin thresholds · carrier-selection policy · customer billing requirements · financial authority · banking information · claims and settlement rules · legal commitments · safety rules · approval thresholds · autonomous-action scope |

Even the left column is not silent: it is captured **with provenance**, remains inspectable and
tenant-scoped, and any piece that would *gate* an action must first **compile into a rule a human
activates** (Outcome A) — otherwise it stays Organizational Knowledge that explicitly does not stop
anything (Outcome B, [`ADR-010 §6`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md)).

### 7.4 Monitoring and rollback

After activation the Operator **monitors impact** and can **roll back a defective version**. There is
deliberately no "edit the live rule in place": a new version **supersedes** and the prior version is
**retained** (effects were judged under it, [`ADR-010 §6.2`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md)). Rollback uses existing machinery:

- **a narrowing change is immediate**; a broadening change requires the Policy Owner and, at a
  narrowing policy's expiry, a human to confirm (never "tighten now, loosen automatically later");
- **automatic demotion** on a wrong action, a rising `UNKNOWN_OUTCOME` rate, a verification-failure
  breach, a fraud signal, a cap breach or integration degradation
  ([`ADR-010 §7.3`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md); [`release-gates.md`](../specifications/acceptance/release-gates.md): engage the brake, revert to the prior gate's ceiling, retain the evidence, raise an Exception with a named owner);
- **reversing an external effect** is itself a **gated effect** — a Compensation
  ([`ADR-004`](../architecture/decisions/ADR-004-effect-boundary.md)), subject to every rule an effect is subject to, never a silent undo;
- **a policy change voids in-flight authority** — Approval `VOID_ON_DRIFT`, Witness invalid, Grant unclaimable ([`ADR-010 §7.4`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md)).

## 8. The artifacts — everything learned becomes explicit, inspectable and tenant-safe

**The Operator must not silently learn or rewrite a customer's operations inside model memory.**
Everything it learns becomes an explicit artifact, tenant-scoped, provenance-carrying, and
inspectable. The table records each artifact's **canonical home** and honest **status** — no
artifact below is presented as implemented (see [`CURRENT.md`](../implementation/CURRENT.md) and
[`IMPLEMENTATION-SURFACE.yaml`](../implementation/IMPLEMENTATION-SURFACE.yaml)).

| Artifact | Canonical home | Owning phase | Status today |
|---|---|---|---|
| **workflow definitions** | the eleven loop specs [`workflows/W1..W11`](../specifications/workflows/) + registry | P10/P13 | specs exist; per-tenant runtime **SPECIFICATION_ONLY** |
| **work-item templates** | Work Item primitive [`entities/01-work-item.md`](../specifications/entities/01-work-item.md) | P6 | primitive specified; **no template artifact yet — vision** |
| **customer profiles / tenant operating model** | the **Operational System Map** ([`operational-system-map.md`](../specifications/operational-system-map.md), [`ADR-018 §2`](../architecture/decisions/ADR-018-customer-operational-graph.md)) | P9/P11 | **SPECIFICATION_ONLY** |
| **carrier / driver / facility profiles** | `Party` + `Qualification Decision` ([`domain-entities/registry.md`](../specifications/domain-entities/registry.md)) | P9 | modelled as domain entities; **no dedicated profile artifact — vision**; legacy per-carrier facts live single-tenant in the knowledge base (an open finding) |
| **field mappings** | External Entity Mapping (P9) + map fields 3–5 | P9 | **SPECIFICATION_ONLY** |
| **document requirements** | W6 documentation (per-load required-doc set) | P9/P10 | specified within W6; no standalone artifact |
| **policy rules** | Policy/Rule ([`ADR-010`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md), [`entities/14-policy.md`](../specifications/entities/14-policy.md), [`entities/15-rule.md`](../specifications/entities/15-rule.md)) | P8 | **LEGACY_IMPLEMENTATION** (a prompt string is not a policy); canonical is P8 |
| **approval matrices** | Approval ([`ADR-005`](../architecture/decisions/ADR-005-approval-binding-and-drift.md), [`entities/06-approval.md`](../specifications/entities/06-approval.md)) | P6/P8 | approval entity specified; **per-role approver matrix is `NEEDS VALIDATION`** ([`OPEN-VALIDATION-ITEMS.md`](OPEN-VALIDATION-ITEMS.md)) |
| **exception playbooks** | Exception ([`entities/12-exception.md`](../specifications/entities/12-exception.md), W7) | P8 | exception primitive specified; **no "playbook" artifact yet — vision** |
| **communication templates** | ADR-015 open design point (templates vs model-generated) | P9/P12 | **not specified — open** ([`ADR-015`](../architecture/decisions/ADR-015-communications-subsystem.md)) |
| **autonomy limits** | caps + graduation ([`ADR-010 §7`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md), [`AUTONOMY-MATRIX.md`](AUTONOMY-MATRIX.md)) | P8/P14 | ceilings specified; runtime P8/P14 |
| **evaluation cases** | acceptance oracles ([`acceptance/registry.md`](../specifications/acceptance/registry.md)); shadow diff (G6) | P10 | acceptance corpus exists; per-tenant eval cases **vision** |
| **historical replay results** | rule test-vectors ([`ADR-010 §6.2`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md)) + shadow-vs-human diff (G6) | P10 | **vision** (§7.2); composes on P7/P9 |

**Invariants over every artifact** ([`ADR-002`](../architecture/decisions/ADR-002-state-classes-and-lineage.md), [`ADR-010`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md), [`operational-system-map.md §3`](../specifications/operational-system-map.md)): tenant-scoped (never `default`, never inferred); provenance on every fact; a `MODEL_INFERRED` value never gates; `OWNER_ASSERTED` is never silently overwritten; an incomplete artifact **fails closed** (`NEEDS VALIDATION`), never silently assumed.

## 9. Evaluation and promotion gates

The Operator advances a capability from mode to mode only by passing the canonical release gates
([`release-gates.md`](../specifications/acceptance/release-gates.md)); **automation may demote,
never promote** — a human signs off every advance.

| Gate | What it proves | Operator relevance |
|---|---|---|
| **G5** | single loop in a controlled environment, no live effects | the coordinated loop runs against a sandbox |
| **G6** | single-loop **shadow mode** — live reads, **zero effects**, shadow-vs-human diff | the evidence for stages 9/12; SHADOW mode's bar |
| **G7** | single-loop **human-executed** — Neyma prepares, the human executes; never claim Neyma executed | the honest "prepare-only" step |
| **G8** | single-loop **supervised effect** — live gated writes, the safety kernel re-run **LIVE**, `HUMAN_APPROVAL_REQUIRED` per effect | SUPERVISED mode's bar |
| **G9** | **multi-loop supervised** — all touched loops + atomic handoffs, no responsibility gap | the Operator coordinating across loops |
| **G10** | **bounded autonomy** — full suite + the graduation dossier ([`ADR-010 §7`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md)); **ZERO wrong actions**, ~0 unknown-outcome, capped/time-boxed/revocable | BOUNDED AUTONOMY mode's bar |

## 10. Phase mapping — the Operator across P5–P14 (NOT forced into P4)

The Neyma Operator is **not a single work unit that "lands" in one phase.** It is a coherent role
**assembled across phases** as its foundations arrive, and it is deliberately **not part of P4**.
P4 is adapter containment — routing effects through the kernel and closing R-07; it builds the wall
the Operator later coordinates work through, and it is [`CURRENT.md`](../implementation/CURRENT.md)'s
sole READY unit and **not complete**. The Operator's own capabilities begin only at **P9** and after.
This reconciles the founder's suggested placement with repository authority:

| Phase | What it buys the Operator | Canonical source |
|---|---|---|
| **P5** | durable observations & delivery; canonical events / replay isolation; production persistence — the substrate the Operator reads | [`ADR-008`](../architecture/decisions/ADR-008-durable-workflows.md), [`ADR-016`](../architecture/decisions/ADR-016-production-topology.md) |
| **P6** | Work Items & Pipeline Instances — the shared work-item/workflow **source of truth** the Operator coordinates over (and where the legacy `operator_*` cluster is retired) | [`entities/01-work-item.md`](../specifications/entities/01-work-item.md), [`entities/02-pipeline-instance.md`](../specifications/entities/02-pipeline-instance.md) |
| **P7** | evidence, provenance, identity binding — the evidence layer behind every Operator claim; the tenant-safe knowledge base ([`tenant="default"`](../implementation/CURRENT.md) finding closes) | [`ADR-002`](../architecture/decisions/ADR-002-state-classes-and-lineage.md)/[`ADR-007`](../architecture/decisions/ADR-007-identity-claims-and-conflict.md) |
| **P8** | policy, approvals, the **workflow/policy-change process**, exceptions — the authority the Operator proposes into | [`ADR-010`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md), [`ADR-005`](../architecture/decisions/ADR-005-approval-binding-and-drift.md), [`ADR-011`](../architecture/decisions/ADR-011-human-brake.md) |
| **P9** | freight-domain understanding + **conversational intent ingested as *proposed* with provenance** (never authority); comms ingestion; TMS-agnostic domain model | [`ADR-019 §10`](../architecture/decisions/ADR-019-conversational-operations-layer.md), [`ADR-015`](../architecture/decisions/ADR-015-communications-subsystem.md), [`ADR-018`](../architecture/decisions/ADR-018-customer-operational-graph.md) |
| **P10** | **shadow discovery on Delivered Load Closure** — the first read-only slice; historical replay + shadow-vs-human diff compose here | [`PHASE-OUTPUTS.md`](../implementation/PHASE-OUTPUTS.md) P10 (a `HYPOTHESIS`, [`PRODUCT.md §15`](../../PRODUCT.md)) |
| **P11** | the **production Operator interface**: onboarding + the Operational System Map, the web control plane's conversational workspace, cross-channel one-conversation continuity, scheduler, integration IAM/health, observability | [`ADR-017`](../architecture/decisions/ADR-017-tenant-and-integration-lifecycle.md), [`ADR-019 §7`](../architecture/decisions/ADR-019-conversational-operations-layer.md), [`ADR-018`](../architecture/decisions/ADR-018-customer-operational-graph.md) |
| **P12** | **supervised coordination and effects** — a conversational/Operator instruction that causes an effect routed through the full kernel; supervised sends | [`ADR-019 §10`](../architecture/decisions/ADR-019-conversational-operations-layer.md), [`ADR-004`](../architecture/decisions/ADR-004-effect-boundary.md), [`ADR-015`](../architecture/decisions/ADR-015-communications-subsystem.md) |
| **P13** | **coordination across multiple freight loops** + the ADR-013 workflow-authority migration model | [`ADR-013`](../architecture/decisions/ADR-013-workflow-authority-migration.md) |
| **P14** | **bounded autonomous operational adaptation** — per class, capped, time-boxed, revocable; never removing the ADR-003 assertion | [`ADR-010 §7`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md), [`ADR-003`](../architecture/decisions/ADR-003-authorization-assertion.md) |

## 11. Current-vs-future status — read this so roadmap language is never mistaken for capability

For the authoritative, machine-verified status see [`CURRENT.md`](../implementation/CURRENT.md); this
section names no commit, suite figure or completion percentage, and presents **no Operator capability
as currently available.** Every Operator capability sits in exactly one band:

| Band | Definition | Operator capabilities in it today |
|---|---|---|
| **Vision only** | directional; not scheduled as a work unit | the coherent **Neyma Operator persona** as an end-state experience; bounded autonomous adaptation (P14) |
| **Specified** | behaviour + acceptance contract exist; **not implemented** | the conversational layer ([`ADR-019`](../architecture/decisions/ADR-019-conversational-operations-layer.md)), onboarding + control plane ([`ADR-017`](../architecture/decisions/ADR-017-tenant-and-integration-lifecycle.md)), the Operational System Map, the policy-change process ([`ADR-010`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md)), authority migration ([`ADR-013`](../architecture/decisions/ADR-013-workflow-authority-migration.md)) |
| **Enabled by earlier foundations** | needs P5–P8 substrate before it can be built | Operator coordination over Work Items/policy/evidence |
| **Shadow-capable** | reachable in read-only shadow once P9/P10/P11 land | DISCOVERY and SHADOW OPERATOR modes; historical replay; shadow-vs-human diff |
| **Supervised-capable** | reachable under human approval once P12 lands | SUPERVISED OPERATOR mode |
| **Autonomy-capable** | reachable only per earned class once P14 lands | BOUNDED AUTONOMY mode |
| **Not yet implemented** | the honest state of **all** of the above today | **Nothing in this document is implemented.** No Operator mode, artifact runtime, discovery lifecycle, or learning/change process exists in production; the current program's active unit is **P4 adapter containment (READY, not complete; R-07 OPEN — NOT CONTAINED)**, and P5–P14 have not begun. |

> **The Operator is a documented role and a reconciled phase map — not a shipped capability.**
> It is built only when [`CURRENT.md`](../implementation/CURRENT.md) says a phase that carries it is
> complete, and every consequential thing it ever does passes the same effect boundary, policy,
> evidence, approval, verification and brake controls as any other action.
