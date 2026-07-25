# ADR-018 — The Customer Operational Graph and TMS-Agnostic Domain Model

**Status:** ✅ **FINAL — U-REBASELINE-1 (founder-authorized, 2026-07-20).**
**Extends:** ADR-013 (workflow-authority migration), ADR-014 (integration/credential models),
ADR-017 (tenant and integration lifecycle).
**Crystallizes existing truths:** engineering-principles P28 ("a vendor's table shape became our
ontology") and P31 ("model what is true, not merely what is observable"); operating-model §3.2
("there is no single source of truth in a brokerage"); ADR-001 (authority is per truth domain);
ADR-002/007 (provenance and identity); ADR-006 (verification / unknown outcomes); semantic-model
("Authoritative System").

---

## 1. Decision — the TMS is one node, not the center

**Do not assume a customer has a conventional TMS.** For one customer the operational system of
record may be an actual TMS; for another, the functional equivalent of a TMS is **distributed**
across Google Sheets, Excel, Gmail, Outlook, Google Drive, SharePoint, SMS, phone calls, load
boards, carrier portals, appointment portals, accounting systems, internal databases, paper
documents, and employee memory / tribal knowledge.

> **The architecture treats the TMS as one possible node in the customer's operational graph, not
> as the universal center of the product.** ⛔ "The TMS is the center of the product" and "the
> canonical domain model is shaped by a TMS schema" are **rejected as architecture** — they are
> the P28 scar written as a rule.

**Neyma models the company's complete real workflow independently from the software products
currently used to perform it.** The canonical domain model and workflow engine **must not depend
on any specific TMS schema.**

## 2. The per-tenant Operational System Map

For every tenant, Neyma maintains a **customer-specific operational system map** — a first-class,
owner-asserted, auditable artifact. For each operational capability it records the fifteen fields:

| Field | Meaning |
|---|---|
| operational capability | the business function (e.g. "record delivery", "hold the rate con") |
| current system or channel | where it lives today (a TMS, a Sheet, an inbox, a phone) |
| entities stored there | which domain entities that node holds |
| fields controlled there | which fields that node is authoritative for |
| source-of-truth precedence | who wins when nodes disagree (ADR-001) |
| read mechanism | how Neyma observes it (API, webhook, ingestion, browser, human) |
| write mechanism | how Neyma effects it, if at all (ADR-004 boundary) |
| synchronization frequency | how often state is reconciled |
| expected latency | how stale the projection may be |
| authentication method | the ADR-014 access model in use |
| reconciliation behavior | how divergence is detected and resolved |
| outage behavior | what happens when the node is unreachable |
| manual fallback | the human path when automation cannot proceed |
| migration status | where this capability sits on the §4 maturity ladder |
| target authority status | where the customer intends authority to end up (ADR-013) |

The map is produced during onboarding (§5) and kept current as the integration lifecycle
(ADR-017) evolves.

## 3. Source-agnostic workflows and per-fact authority

**The same operational workflow must function** whether load state originates from a Google
Sheet, an actual TMS, an email thread, a customer portal, Neyma itself, or a customer-specific
combination. The domain model is the invariant; the systems are interchangeable nodes.

All customer systems connect through **normalized integration boundaries** (ADR-014 §1): APIs,
webhooks, OAuth, service accounts, EDI, database connections, CSV import/export, spreadsheet
connectors, email ingestion, SMS, browser automation, document ingestion, human-provided
evidence, and manual supervised actions.

For every important operational fact, Neyma knows: **where it came from · which system currently
controls it · whether that source is authoritative · how recent it is · what evidence supports it
· how conflicts are resolved · whether Neyma may update it · how an update is verified.** This is
the provenance model (ADR-002/007) applied to the operational graph.

## 4. Completion is the real outcome, not a write

> **A successful write into one connected system is never proof that the business workflow is
> complete.** Workflow completion is defined by the **real operational outcome** (P24 loop
> closure; ADR-006 read-back verification). Updating a Sheet, or a TMS field, or sending a message
> is a step — the loop closes only when the owed business outcome is established and verified.

## 5. Progressive customer maturity

The product supports a customer moving through eight levels — Neyma delivers value at level 1 and
never *requires* a customer to advance:

1. **Observe** fragmented existing workflows.
2. **Normalize** state across those workflows.
3. **Coordinate** work across existing systems.
4. **Execute** supervised actions.
5. **Own** complete operational workflows.
6. Become the **primary interface** for selected workflows.
7. Become **authoritative** for selected workflow state.
8. **Replace** fragmented systems where the customer deliberately chooses to migrate.

Levels 6–8 are the ADR-013 authority-migration model in ladder form; every advance past level 4 is
a recorded, customer-authorized, reversible decision. **Customer onboarding includes operational
workflow discovery and source-of-truth mapping** — the map of §2 is an onboarding deliverable
(ADR-017).

## 6. Invariants preserved under fragmentation

**Fragmented customer tooling never reduces auditability, ownership, tenant safety, authorization,
or workflow-closure requirements.** A load whose state lives in a Sheet and three inboxes still
has: one accountable human owner; tenant-isolated state; provenance on every fact; the effect
boundary on every write; and a closure condition defined by outcome. Meeting the customer where
they are is an integration decision, never a safety compromise.

**Do not require a customer to replace Google Sheets, email or their existing TMS before Neyma can
deliver value.**

## 7. Consequences

- **P9** (domain projections + external entity mapping): the domain model is authored
  TMS-schema-independent; External Entity Mapping binds *any* node's identifiers, not a TMS's.
- **P11** (onboarding + control plane): onboarding produces the per-tenant Operational System Map;
  the control plane surfaces it and per-node connection health (ADR-017).
- **P13** (authority migration): the §5 ladder contextualizes the ADR-013 migration model.
- Spec: [`../specifications/operational-system-map.md`](../specifications/operational-system-map.md).
- Nothing here is implemented by U-REBASELINE-1 — the decision is durable; the capability lands in
  the phases above.
