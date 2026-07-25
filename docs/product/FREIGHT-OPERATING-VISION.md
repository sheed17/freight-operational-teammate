# Neyma — The Freight Operating Vision

> **CANONICAL — product vision consolidation.** This document gathers Neyma's complete product
> vision and operational scope into one readable place. **It holds NO authority independent of its
> sources and creates NO new product decision.** On any conflict, the cited source wins:
> product identity → [`PRODUCT.md`](../../PRODUCT.md); the eleven loops → [`operating-model.md`](operating-model.md)
> and [`docs/specifications/workflows/`](../specifications/workflows/); use-case classification,
> phase and readiness tier → [`OPERATIONAL-USE-CASE-COVERAGE.yaml`](OPERATIONAL-USE-CASE-COVERAGE.yaml);
> autonomy/authority → [`ADR-010`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md)
> and [`ADR-003`](../architecture/decisions/ADR-003-authorization-assertion.md); **current
> implementation status → [`CURRENT.md`](../implementation/CURRENT.md)** (this file copies no
> volatile commit/suite figures and states no phase as complete).
>
> **Companion documents:** [`FREIGHT-CAPABILITY-MAP.md`](FREIGHT-CAPABILITY-MAP.md) ·
> [`QUOTE-TO-CASH-LIFECYCLE.md`](QUOTE-TO-CASH-LIFECYCLE.md) ·
> [`OPERATIONAL-LOOPS.md`](OPERATIONAL-LOOPS.md) · [`AUTONOMY-MATRIX.md`](AUTONOMY-MATRIX.md) ·
> [`NEYMA-OPERATOR.md`](NEYMA-OPERATOR.md) *(the top-level coordinating Operator role + customer-discovery lifecycle)*.

---

## 1. The thesis

**Neyma is not primarily a document-processing tool, an invoice-audit product, or a replacement
TMS.** Neyma is the **AI operating layer for freight companies**: it connects to the systems a
freight or logistics company already uses and operates across them as a **coordinated AI
workforce.**

The long-term end state is that a freight company can **add Neyma as its AI operations team.**
Specialized, role-based AI teammates coordinate the complete operation — from a customer request to
cash collected — working through the customer's existing systems, closing operational loops, and
escalating genuine judgment to the accountable humans.

This is the plain-language framing of the canonical identity in [`PRODUCT.md §1`](../../PRODUCT.md)
and [`ADR-012`](../architecture/decisions/ADR-012-product-identity-and-strategy.md): *"Neyma is the
AI-native operating platform and system of action for small and medium freight and logistics
companies."* The unit of value is a **correctly closed operational loop**, not a processed document.

**Delivered Load Closure is the first commercial wedge, not the final product.** The expansion
thesis, in one line:

> **Neyma starts by closing delivered loads, proves value inside the customer's existing systems,
> and expands into the coordinated AI operations team running the freight company from quote to
> cash.**

## 2. Who it serves

The initial ICP is a **small-to-medium US truckload freight brokerage** (or brokerage-leaning 3PL)
that runs the business out of a shared inbox, has little or no EDI, and has no in-house engineering
([`PRODUCT.md §2`](../../PRODUCT.md)). **Formal-TMS ownership is not a requirement** — the
operational system of record may be a TMS, Google Sheets, a shared inbox, portals, accounting
software, SMS and phone, or a customer-specific combination. Neyma models the real workflow
independently of whatever software performs it today
([`ADR-018`](../architecture/decisions/ADR-018-customer-operational-graph.md)): **the TMS is one
node in the customer's operational graph, not the center of the product.**

## 3. Neyma as a coordinated AI operations team

The end-state product is experienced as a **team of specialized AI teammates**, each a role over the
one shared operating system. **These are not disconnected bots.** They are role-based teammates on a
single shared spine, and **one teammate's completed work becomes the next teammate's context
automatically** — the mechanism is the atomic cross-loop handoff (the downstream Work Item is
created in the *same commit* as the source transition, so no responsibility gap and no lost context
can appear between roles — see [`workflows/registry.md`](../specifications/workflows/registry.md)
and [`QUOTE-TO-CASH-LIFECYCLE.md`](QUOTE-TO-CASH-LIFECYCLE.md)).

### 3.1 The role-based teammates *(long-term vision — not current capability)*

| AI teammate (role) | Primary loop / surface | Capability |
|---|---|---|
| AI sales coordinator | W1 | sales & quote intake |
| AI load planner | W1 (+W4 planning) | load planning & order entry |
| AI carrier representative | W2 | carrier sourcing & tendering |
| AI dispatcher | W4 | dispatch & driver communication |
| AI track-and-trace coordinator | W5 | in-transit tracking |
| AI appointment coordinator | W4 | appointment scheduling |
| AI document specialist | W6 | document operations |
| AI claims coordinator | W11 | claims / OS&D |
| AI AP clerk | W9 | carrier invoice audit & AP |
| AI AR clerk | W8 | customer billing & AR |
| AI customer-service representative | W10 + conversational layer | customer service |
| AI compliance teammate | W3 | carrier compliance |
| AI operations manager | oversight surface (not a loop) | operational management & reporting |
| AI exceptions coordinator | W7 (cross-cutting) | exception management |

> **The teammate/role layer is a *presentation* over the loops and the shared spine — not a set of
> new loops and not isolated agents.** A teammate is a persona that operates one or more of the
> eleven canonical loops (or a cross-cutting surface) on shared state. See
> [`OPERATIONAL-LOOPS.md §6`](OPERATIONAL-LOOPS.md) for why this does **not** require a loop-model
> revision.

### 3.2 The one shared system every teammate operates on

| One shared… | What it means | Canonical source |
|---|---|---|
| **load & work-item state** | every unit of accountable work is a Work Item with exactly one human owner | [`PRODUCT.md §8`](../../PRODUCT.md), entities |
| **customer / carrier / driver / lane / facility knowledge** | one durable, tenant-safe, inspectable operational knowledge base | [`FREIGHT-CAPABILITY-MAP.md §17`](FREIGHT-CAPABILITY-MAP.md) |
| **evidence & provenance** | one content-addressed Evidence store; every fact carries provenance | ADR-002, [`semantic-model.md`](../architecture/semantic-model.md) |
| **policies & approvals** | one typed policy + approval + brake system, per action class | [`ADR-010`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md), ADR-011 |
| **communications history** | one correlated inbound/outbound record across channels | [`ADR-015`](../architecture/decisions/ADR-015-communications-subsystem.md) |
| **safety & effect boundary** | one checkpoint → witness → grant → adapter → verification path for every external effect | ADR-004/009, [`ARCHITECTURE.md`](../../ARCHITECTURE.md) |
| **audit trail** | one event stream that reconstructs every loop | ADR-006/007 |

A disconnected-bot design would fork state, fork authority, and lose the one thing that makes the
product valuable: **a single system accountable for whether the loop is actually closed.** This is
also why [`PRODUCT.md §12`](../../PRODUCT.md) lists *"a collection of disconnected agents"* among the
things Neyma is **not**.

### 3.3 Where humans stay responsible

Neyma handles the **repetitive coordination and execution** around the people who own the business.
Humans remain responsible for **major relationships, unusual judgment, sensitive financial
authority, legal decisions, safety incidents, and policy setting.** The accountable human stays in
the operating seat; every open obligation has exactly one accountable human owner
([`PRODUCT.md §9`](../../PRODUCT.md)).

## 4. The product model — how every teammate acts

For every action, a teammate moves through this model:

```
observe → understand → coordinate → recommend → draft → request approval (where necessary)
        → execute (through the controlled effect boundary) → verify the real outcome
        → escalate uncertainty or judgment
```

This is a *presentation* of the canonical enforcement, not a rival to it. It decomposes onto the
five capability verbs ([`operating-model.md §6.2`](operating-model.md): **Observe · Assist · Execute ·
Verify · Escalate**) and the four gate decisions
([`ADR-010`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md):
`HUMAN_APPROVAL_REQUIRED` · `AUTONOMOUS_WITHIN_CAPS` · `PERMANENT_HUMAN_ASSERTION_REQUIRED` ·
`FORBIDDEN`). **Every action class carries exactly one gate decision, never null.** Execution always
runs the full effect pipeline (`Work Item → Pipeline Instance → policy & validation → optional
approval → atomic checkpoint → Checkpoint Witness → Effect Grant → atomic claim → adapter execution
→ verification → outcome → evidence & projection → closure`). **The model never chooses an amount**
([`PRODUCT.md §10`](../../PRODUCT.md)). Per-capability ceilings are in
[`AUTONOMY-MATRIX.md`](AUTONOMY-MATRIX.md).

## 5. The systems Neyma works through

Neyma works through the customer's existing systems — never requiring a rip-and-replace: **TMS ·
email · SMS and eventually voice · customer and carrier portals · scheduling portals · GPS/ELD/tracking
providers · accounting systems · document stores · Slack/internal tools · APIs · browser-based legacy
systems.** All external effects use the canonical effect boundary and authorization model
([`ADR-004`](../architecture/decisions/ADR-004-effect-boundary.md)); a successful write into one node
is never proof the workflow is complete. Adapter maturity (live / partial / planned) is tracked in
[`adapters/registry.md`](../specifications/adapters/registry.md).

## 6. The quote-to-cash lifecycle

The canonical end-to-end flow — with the loops, work items, evidence, approvals and external effects
at each stage — is in [`QUOTE-TO-CASH-LIFECYCLE.md`](QUOTE-TO-CASH-LIFECYCLE.md):

```
customer request → quote → booking → load creation → carrier sourcing & tendering → dispatch →
pickup → in-transit tracking → appointments & exceptions → delivery → document collection →
carrier payable → customer billing → collections → load closure → claims / post-load follow-up →
reporting & operational learning
```

A loop closes only at its **business outcome** (cash in, carrier paid correctly, packet complete on
the right load) — never at "sent / entered / uploaded" (the false-closure rules,
[`workflows/registry.md`](../specifications/workflows/registry.md)).

## 7. The expansion path

The wedge is the entry point, not the ceiling. The intended sequence — each step gated by evidence,
safety foundations and (past supervised execution) customer-authorized migration
([`ADR-013`](../architecture/decisions/ADR-013-workflow-authority-migration.md)):

**Delivered Load Closure → document operations → carrier invoice audit → customer billing →
accounts payable → accounts receivable → dispatch & driver communication → track-and-trace →
appointment scheduling → exception management → carrier sourcing & tendering → claims → customer
service → compliance → full freight operations management.**

This ordering is a **strategy sequence, not an implementation-status claim.** What is actually built,
and at what maturity, is governed by the roadmap phases and
[`FREIGHT-CAPABILITY-MAP.md`](FREIGHT-CAPABILITY-MAP.md).

## 8. The strict current-vs-future distinction

> **This is the section that prevents roadmap language from being mistaken for shipped capability.**
> Every capability sits in exactly one of five bands. For the authoritative, machine-verified
> status, see [`CURRENT.md`](../implementation/CURRENT.md); this table deliberately names no commit,
> suite figure or completion percentage, and **presents no future capability as currently
> available.**

| Band | Definition | What is in it today |
|---|---|---|
| **1 — Currently implemented** | Code exists and is exercised; a **safety/foundation** capability, not a product surface. | P0–P2 foundation (baseline + anti-false-green infra; amount-free effect identity; tenant-safe persistence) and the **P3 checkpoint kernel** (recorded COMPLETE; **ships dark — no production path routes through it**). |
| **2 — Currently specified** | The behaviour and acceptance contract exist (readiness tier **SPECIFIED**); **not implemented.** | The full canonical corpus — the eleven loops, 40 domain entities, event/adapter contracts, acceptance oracles, the use-case coverage matrix. **P4 adapter containment is READY and *in progress* — not complete; R-07 is OPEN — NOT CONTAINED.** No freight loop is implemented end-to-end. |
| **3 — Initial commercial wedge** | The one operational outcome Neyma is being built to deliver first. | **Delivered Load Closure** — a `HYPOTHESIS` needing design-partner validation; first delivered as a **read-only shadow slice** (phase P10). |
| **4 — Planned capability** | Scheduled on the roadmap; specification and/or shadow exists or is planned; **not yet built or not yet live.** | All quote-to-cash operational capabilities on the expansion path (§7), mapped to phases P5–P13 — shadow → supervised → customer-authorized migration. |
| **5 — Long-term product vision** | The destination; **directional, not scheduled as current work.** | The coordinated **AI operations team** running the freight company quote-to-cash; the role-based teammate experience (§3); **bounded, per-class, capped, revocable autonomy (P14) — never before it is earned.** |

**NOT yet implemented, explicitly** (bands 4–5, named so they are never mistaken for band 1): full
dispatch · live driver communications · continuous track-and-trace · autonomous carrier sourcing ·
appointment scheduling · full AP/AR execution · claims execution · full customer-service automation ·
company-wide autonomous operations.

## 9. What Neyma is NOT

Per [`PRODUCT.md §12`](../../PRODUCT.md): **not** a carrier-invoice processor, a document extraction
service, a TMS chatbot, a collection of disconnected agents, a Slack interface over old workflows, a
browser-automation wrapper, an AP reconciliation tool, or a chatbot-only product. **The current
runtime does carrier-invoice work, document extraction, browser driving and Slack — those are the
first implemented surfaces of the product, not the product.** No competitor and no first wedge
defines Neyma's canonical identity.

## 10. Reusable product narrative

**One sentence:**
> Neyma starts by closing delivered loads and expands into the AI operations team that runs the
> freight company from quote to cash.

**Short paragraph:**
> Neyma works across the systems freight teams already use — TMS, email, SMS, portals, documents,
> accounting tools, and internal communication. It handles routine operational work, prepares
> complex decisions for review, executes approved actions through a controlled safety boundary,
> verifies outcomes, and escalates genuine judgment.

**Long-term vision:**
> One AI operating system coordinating the freight company, not a collection of disconnected bots.

**Core positioning** *(from [`PRODUCT.md §1`](../../PRODUCT.md), refined for reuse):*
> Neyma is the AI operating layer for freight companies. It coordinates the full lifecycle from
> quote to cash across sales, load planning, carrier sourcing, dispatch, track-and-trace,
> appointments, exceptions, documents, billing, payables, claims, customer service, and management.
> Neyma observes, understands, recommends, drafts, requests approval, executes, verifies, and
> escalates work across the systems freight teams already use. Consequential actions remain
> policy-bound, evidence-backed, and human-supervised where required.
