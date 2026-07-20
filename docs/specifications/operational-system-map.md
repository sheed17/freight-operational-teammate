# Operational System Map — Specification

**Layer:** Specification. **Authority:** **CANONICAL.** **Decision of record:**
[`../architecture/decisions/ADR-018-customer-operational-graph.md`](../architecture/decisions/ADR-018-customer-operational-graph.md).
**Binding on:** P9 (domain projections + external entity mapping), P11 (onboarding + control
plane), P13 (authority migration).

> ### **The TMS is one node in the customer's operational graph, not the center of the product.**
> Every tenant's functional "system of record" may be a real TMS, or it may be distributed across
> spreadsheets, inboxes, portals, phones and paper. This spec defines the artifact that makes that
> graph explicit, per tenant, so the canonical domain model can stay independent of any one node's
> schema.

## 1. What it is

The **Operational System Map** is a per-tenant, owner-asserted, auditable record of *how this
customer actually operates* — the capabilities the business performs, the systems or channels each
one currently lives in, and the authority/read/write/reconciliation posture for each. It is
**produced during onboarding** and kept current as integrations change.

It is **not** a list of installed software. It is a model of the *real workflow*, independent of
the products used to perform it (ADR-018 §1). Two tenants running "the same" TMS may have very
different maps; a tenant with no TMS still has a complete map.

## 2. Per-capability record — the fifteen fields

For each operational capability the map records exactly:

1. **operational capability** — the business function
2. **current system or channel** — where it lives today
3. **entities stored there** — the domain entities that node holds
4. **fields controlled there** — the fields that node is authoritative for
5. **source-of-truth precedence** — who wins on disagreement (ADR-001)
6. **read mechanism** — how Neyma observes it
7. **write mechanism** — how Neyma effects it, if at all (through the ADR-004 boundary)
8. **synchronization frequency** — how often it is reconciled
9. **expected latency** — how stale the projection may be
10. **authentication method** — the ADR-014 access model in use
11. **reconciliation behavior** — how divergence is detected and resolved
12. **outage behavior** — what happens when the node is unreachable
13. **manual fallback** — the human path when automation cannot proceed
14. **migration status** — the capability's position on the ADR-018 §5 maturity ladder
15. **target authority status** — where the customer intends authority to end up (ADR-013)

A record missing any field is incomplete and fails closed — the affected capability is treated as
`NEEDS VALIDATION`, not silently assumed.

## 3. Invariants

- **Domain-model independence.** The canonical domain model and workflow engine do not depend on
  any node's schema. External identifiers bind through **External Entity Mapping** (P9), trusted
  only within `(tenant, external_system)` — never promoted to canonical identity (P28 scar).
- **Source-agnostic workflows.** The same workflow runs whether a fact originates from a Sheet, a
  TMS, an email thread, a portal, Neyma, or a combination (ADR-018 §3).
- **Per-fact authority.** Every operational fact carries: origin, controlling system, whether that
  source is authoritative, recency, supporting evidence, conflict resolution, whether Neyma may
  update it, and how an update is verified (ADR-002/007).
- **Write ≠ completion.** A successful write into one node is never proof the workflow is complete;
  completion is the real operational outcome (ADR-018 §4, ADR-006, P24).
- **Fragmentation never lowers the bar.** Auditability, single accountable ownership, tenant
  safety, authorization and workflow-closure requirements hold regardless of how fragmented the
  tooling is (ADR-018 §6).

## 4. Onboarding obligation

Customer onboarding **must** include operational-workflow discovery and source-of-truth mapping;
the map is an onboarding deliverable (ADR-017). Neyma does not require the customer to replace
Google Sheets, email or their TMS before delivering value (ADR-018 §6) — it begins at maturity
level 1 (observe) and advances only by the customer's deliberate, recorded, reversible decision.

## 5. Status

**`SPECIFICATION_ONLY`.** No Operational System Map runtime exists yet; it is an output of P9/P11.
Recorded in [`../implementation/IMPLEMENTATION-SURFACE.yaml`](../implementation/IMPLEMENTATION-SURFACE.yaml).
