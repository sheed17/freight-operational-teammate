# Neyma — Product Definition

> **This file is the root product authority.** If any other document, roadmap, code comment, agent
> instruction or test disagrees with the product definition below, **this file wins** and the other
> document is stale. Report the contradiction; do not resolve it by inventing a third answer.

**Read this before writing any code in this repository.** It exists to stop a specific failure:
an agent opens the repo, sees a carrier-invoice pipeline and a Slack bot, concludes that Neyma is an
invoice-processing tool, and then builds the next feature for the wrong product.

---

## 1. Product definition

**Neyma is an operational execution layer for small and medium freight brokerages.**

It observes fragmented freight work across the systems a brokerage actually runs on — email, PDFs
and freight documents, TMS platforms, carrier and customer portals, SMS and calls, spreadsheets,
accounting systems, load boards, and human approval channels — and it:

- maintains **canonical operational state** across those fragments,
- **coordinates bounded actions** against external systems,
- **identifies missing events** (the thing that should have happened and did not),
- **manages exceptions**, and
- **helps accountable humans close operational loops.**

The unit of value is a **closed loop**, not a processed document.

## 2. Target customer

A **small-to-medium US truckload freight brokerage** (or brokerage-leaning 3PL) that has a TMS and
uses it, runs the business out of a shared inbox, keeps spreadsheets for everything the TMS cannot
hold, has little or no EDI, and has **no in-house engineering, no data team and no integration
budget**. Margin is thin and per-load, so one unaudited carrier invoice or one two-week-late
customer invoice is a visible hit rather than a rounding error.

`HYPOTHESIS` / `NEEDS VALIDATION` — the specific headcount, load volume and system mix of our design
partner. See [`docs/product/operating-model.md`](docs/product/operating-model.md) §2 and
[`docs/product/OPEN-VALIDATION-ITEMS.md`](docs/product/OPEN-VALIDATION-ITEMS.md).

## 3. The operational problem

A brokerage's work does not live in one system. The real cost of running the business is the
**human labour of carrying information between systems**, all day, without dropping anything.
Nothing owns the question *"what is actually true about this load right now, and what should have
happened by now that hasn't?"* — so loads sit unbilled, carrier invoices get paid unaudited, PODs
get chased by phone, AR ages past terms, and exceptions are discovered rather than resolved.

**The problem is not that documents are hard to read. It is that no system is accountable for the
loop being closed.** An extraction service makes the first problem smaller and leaves the second
one exactly where it was.

## 4. Final product vision

The destination is a system that runs the **entire operational back office** of a brokerage across
all eleven canonical loops: it knows what is true, knows what is missing, acts within explicitly
granted authority, escalates what needs judgement with the evidence already assembled, and leaves
an auditable trail for every consequential thing it did or refused to do.

**Autonomy is earned per action class, capped, time-boxed and revocable** — never global, never
assumed, and never a default. The end state is not "the AI runs the brokerage"; it is
**"every loop has an accountable owner, and Neyma does the carrying."**

## 5. User experience

The accountable human stays in the operating seat. Neyma works in the background across the
brokerage's existing systems and surfaces in the channels people already use, bringing a person a
**decision with the evidence attached**, not a notification asking them to go and look. When Neyma
is unsure, it says so and routes to a named human. When it acts, it records what it did, under whose
authority, and how it verified the result.

**The brokerage never rips out its TMS**, and Neyma never holds the human's TMS credentials —
the human establishes the session and Neyma attaches to it.

## 6. The eleven canonical operational loops

| ID | Loop | Spec |
|---|---|---|
| **W1** | Quote | [`W1-quote.md`](docs/specifications/workflows/W1-quote.md) |
| **W2** | Procurement | [`W2-procurement.md`](docs/specifications/workflows/W2-procurement.md) |
| **W3** | Compliance | [`W3-compliance.md`](docs/specifications/workflows/W3-compliance.md) |
| **W4** | Dispatch | [`W4-dispatch.md`](docs/specifications/workflows/W4-dispatch.md) |
| **W5** | Tracking | [`W5-tracking.md`](docs/specifications/workflows/W5-tracking.md) |
| **W6** | Documentation | [`W6-documentation.md`](docs/specifications/workflows/W6-documentation.md) |
| **W7** | Exceptions | [`W7-exceptions.md`](docs/specifications/workflows/W7-exceptions.md) |
| **W8** | Billing | [`W8-billing.md`](docs/specifications/workflows/W8-billing.md) |
| **W9** | Settlement | [`W9-settlement.md`](docs/specifications/workflows/W9-settlement.md) |
| **W10** | Customer Communications | [`W10-customer-comms.md`](docs/specifications/workflows/W10-customer-comms.md) |
| **W11** | Claims | [`W11-claims.md`](docs/specifications/workflows/W11-claims.md) |

**Exactly eleven.** A twelfth loop is a product decision, not an implementation detail: it requires
an explicit product change here and in [`docs/specifications/workflows/registry.md`](docs/specifications/workflows/registry.md).

## 7. Distributed source-of-truth model

**No single system holds the truth, and Neyma does not attempt to become the system of record.**
The TMS is authoritative for some fields, the accounting system for others, the carrier for others,
and the customer contract for others. Neyma maintains a **canonical operational state** that
records *what is believed, from what evidence, with what provenance, and how confidently* — and it
is explicit about which external system is authoritative for each field.

Where Neyma's belief and an external system disagree, that is an **observation to reconcile**, not
a value to overwrite. Field-level authority is specified per entity; see
[`docs/architecture/semantic-model.md`](docs/architecture/semantic-model.md).

## 8. Canonical operational-state ownership

Operational state is owned per **Tenant** (one brokerage). Within a tenant, every unit of work is a
**Work Item** with exactly one **accountable human owner**. Ownership is never inferred from data,
never defaulted, and never assigned by a machine on its own authority — **a human assigns it, and
the assertion is recorded before it takes effect.**

## 9. Human-accountability model

- Every unresolved operational obligation has **one accountable human owner**.
- A machine-inferred fact (`MODEL_INFERRED`) **cannot independently authorise a consequential
  action**.
- A human-asserted fact (`OWNER_ASSERTED`) **cannot be silently overwritten** by inference.
- Escalation carries the evidence. A request for judgement that makes the human go and gather
  context has moved the work, not done it.

## 10. Bounded autonomy model

Autonomy is admitted **per action class**, with caps, time boxes and revocation, and is gated by
policy plus a **human brake**. The brake controls **admission** — whether new work may start — not
termination of work already running. Consequential actions require deterministic validation;
financial and carrier-assignment actions always do. **The model never chooses an amount.**

## 11. Product principles

1. **A closed loop is the unit of value.** Not a parsed document, not a message sent.
2. **Fail closed.** When Neyma cannot establish truth, it stops and routes to a human.
3. **Evidence before assertion.** Every fact carries provenance.
4. **The human is accountable, and the system makes that possible** — not a rubber stamp.
5. **Never guess a consequential value.** Especially money.
6. **Act once.** An external effect has an identity; a retry is not a second effect.
7. **Meet the brokerage where it is.** No migration, no rip-and-replace, no EDI prerequisite.
8. **Say what is unknown.** An unvalidated freight rule is marked, not assumed.
9. **Earn autonomy.** Per class, capped, revocable, never global.
10. **The repository is the memory.** If it is not written down here, it is not decided.

## 12. What Neyma is NOT

Neyma is **not**:

- a carrier-invoice processor
- a document extraction service
- a TMS chatbot
- a collection of disconnected agents
- a Slack interface over old workflows
- a browser automation wrapper
- an AP reconciliation tool
- an invoice product with additional features

> **Each of these describes something the repository currently contains.** The current runtime does
> carrier-invoice work, does document extraction, does drive a browser, and does speak Slack.
> **Those are the first implemented surfaces of the product, not the product.** An agent that infers
> the product from the code will build the wrong thing — which is precisely why this section exists.

## 13. Current implemented state

**Implementation Phases 0, 1 and 2 are COMPLETE.** What that actually bought:

| | |
|---|---|
| **P0** | A baseline manifest of adjudicated current-state facts, plus anti-false-green guard infrastructure |
| **P1** | **Correct effect identity** — the Commit Key identifies the *effect*, and the amount is provably not in it |
| **P2** | **Tenant-safe persistence** — tenant required at construction, first in every key, enforced by the database, with auditable human-asserted ownership of historical rows |

The suite is green; ### **exact suite counts and the current commit/tree live ONLY in the
machine-maintained status block of [`docs/implementation/CURRENT.md`](docs/implementation/CURRENT.md)** —
this file deliberately does not copy them, because a copied figure is a stale figure within one commit.

## 14. Current unimplemented state

**Everything that makes consequential external effects safe is unbuilt.** Specifically:

- **P3** — the seven-step atomic checkpoint, the Checkpoint Witness, and the effect claim CAS
- **P4** — adapter containment (**R-07 is OPEN — NOT CONTAINED**; six production-reachable
  live-write paths remain physically capable of ungated external effects)
- **P5** — canonical events, outbox/inbox, replay isolation
- **P6–P9** — entities and state machines, provenance and evidence, policy/brake/exceptions,
  freight-domain projections
- **P10+** — the first validated vertical slice, shadow mode, supervised effects, expansion

**No freight loop is implemented end-to-end to the canonical architecture.**

## 15. Provisional first vertical slice

**W6 Documentation → atomic operational handoff → W8 Billing.**

### `NEEDS DESIGN-PARTNER VALIDATION`

This is the *provisional* first slice, chosen on architectural reasoning about which loop is most
self-contained and most obviously valuable. **It is not validated product truth.** It may not be
promoted to a validated commitment without design-partner evidence recorded in
[`docs/product/design-partner-observations.md`](docs/product/design-partner-observations.md).

## 16. Design-partner validation boundary

**The repository does not currently contain firsthand design-partner observation by any agent.**
Domain claims are labelled `CONFIRMED INDUSTRY PATTERN`, `COMMON INDUSTRY PRACTICE`,
`VENDOR-SPECIFIC APPROACH`, `SPECULATION` or `NEEDS VALIDATION`, and claims about *our partner*
specifically are sourced from the founder's report rather than direct observation.

**An agent may not invent, upgrade or relabel a domain claim.** Where a freight-specific rule is
required and unvalidated, the agent **stops and requests evidence** rather than choosing a
plausible default. This blocks the affected freight-specific units only — it does not block
foundational architecture work.

## 17. Authoritative product and workflow documents

| Document | Role |
|---|---|
| [`docs/product/operating-model.md`](docs/product/operating-model.md) | **CANONICAL** — how a brokerage operates and where Neyma sits inside it |
| [`docs/product/freight-discovery.md`](docs/product/freight-discovery.md) | **CANONICAL (evidence)** — the domain research, every claim labelled |
| [`docs/specifications/workflows/`](docs/specifications/workflows/) | **CANONICAL** — the eleven loop specifications + registry |
| [`docs/product/OPEN-VALIDATION-ITEMS.md`](docs/product/OPEN-VALIDATION-ITEMS.md) | **CANONICAL** — unresolved product/workflow rules and their safe interim behaviour |
| [`docs/product/design-partner-observations.md`](docs/product/design-partner-observations.md) | **EVIDENCE** — what is actually known, by source class |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | **CANONICAL** — the architecture entry point |
| [`docs/CANONICAL-DOCUMENTS.md`](docs/CANONICAL-DOCUMENTS.md) | **CANONICAL** — which documents may authorise decisions |

## 18. Current open product questions

Tracked with IDs, blocking status and safe interim behaviour in
[`docs/product/OPEN-VALIDATION-ITEMS.md`](docs/product/OPEN-VALIDATION-ITEMS.md). The largest are:
the design partner's actual volumes and roles; which approvals are required versus advisory; the
real exception taxonomy; customer-specific billing and settlement rules; and whether W6→W8 is in
fact the right first slice.

## 19. Existing code has no presumption of survival

> **No module in this repository is protected by being large, old, working, or well tested.**

The current runtime was built before the canonical architecture existed. Where it conflicts with
the architecture, **the architecture wins and the code is rewritten, contained or deleted.**
Every major subsystem carries an explicit disposition — KEEP, ADAPT, REWRITE, MAKE_READ_ONLY,
QUARANTINE or DELETE — in
[`docs/implementation/LEGACY-DISPOSITION.md`](docs/implementation/LEGACY-DISPOSITION.md).
There is deliberately **no permanent "legacy but active forever" category.**

Likewise, **a test that protects unsafe or obsolete behaviour is replaced, not preserved.** A green
test asserting a behaviour the architecture forbids is a defect with a passing status.

---

## How to read the claims in this file

| Class | Meaning |
|---|---|
| **Product destination** | §1–§12 — where this is going. Stable; changes are product decisions. |
| **Current implementation** | §13–§14 — what exists today. Changes every phase; `CURRENT.md` is authoritative. |
| **Validated fact** | Sourced and labelled in the product corpus. |
| **Architecture decision** | An ADR. Binding until superseded by another ADR. |
| **Hypothesis** | Explicitly marked. May not be built on without validation. |
| **Unresolved customer rule** | `NEEDS VALIDATION` — an agent must stop, not guess. |
