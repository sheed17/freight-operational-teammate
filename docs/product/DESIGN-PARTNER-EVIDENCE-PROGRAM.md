# DESIGN-PARTNER EVIDENCE PROGRAM

> **CANONICAL — the customer-evidence track.** Created by U-REBASELINE-1 (founder-authorized).
> This program runs **alongside** platform engineering. It is not a work unit in the
> implementation registry and it never becomes a second READY coding unit — evidence gathering
> and platform engineering proceed in parallel, and only the founder (or a human the founder
> names) supplies observations.

## 1. Purpose

The **Delivered Load Closure** wedge (PRODUCT.md §15) is a hypothesis. This document specifies
exactly what evidence validates or refutes it, who may supply each item, and what the repository
does while an item is missing. **No agent may invent, infer, upgrade or relabel any item below.
Fabricated validation is the program's terminal failure mode.**

## 2. Required evidence

Each item is recorded with: the fact observed · the **accountable source** (named human or named
system, with date) · the collection method · and its epistemic label (`DESIGN_PARTNER_OBSERVED`,
`FOUNDER_RELAYED`, `CONFIRMED INDUSTRY PATTERN`, `NEEDS VALIDATION`).

| # | Evidence required | Why it matters |
|---|---|---|
| E-01 | **Real TMS and version** | Integration surface and write model |
| E-02 | **Integration method actually available** (API? EDI? browser only?) | Chooses the ADR-014 access model |
| E-03 | **Mailbox topology** (shared inboxes, personal inboxes, who reads what) | Communications ingestion design |
| E-04 | **SMS use** (who texts whom, about what) | Whether SMS is a required day-one channel |
| E-05 | **Phone use** (what only ever happens by phone) | Voice-evidence requirements |
| E-06 | **Accounting platform** and its boundary with the TMS | Billing readiness + payable preparation |
| E-07 | **Load and document samples** (real PODs, BOLs, invoices, lumper/detention receipts) | Extraction and binding reality |
| E-08 | **Delivered-load volumes** (per day/week, seasonality) | Sizing, and the wedge's addressable pain |
| E-09 | **Document arrival channels** (email %, portal %, driver photo %, mail %) | Where ingestion must actually live |
| E-10 | **Approval roles and limits** (who approves what, at what amounts) | Policy and approval-packet design |
| E-11 | **Accessorial authorization** — how charges are authorized in the moment, and where recorded | The verbal-authorization problem; gates what may ever be inferred |
| E-12 | **Exception taxonomy** as the partner actually experiences it | W7 reality vs. our model |
| E-13 | **Order/load/movement/leg/stop relationships** in their operation | Domain-entity fidelity |
| E-14 | **Billing requirements per customer** (required documents, formats, portals) | Billing-readiness rules |
| E-15 | **Factoring and remittance** arrangements | Where the money actually flows |
| E-16 | **Baseline operational metrics** (delivered-to-invoiced time, DSO, aging) | The before-picture for wedge outcomes |
| E-17 | **Human touches** per delivered load today (who, what, how long) | The labor the wedge must remove |
| E-18 | **Retention and security requirements** | Tenant lifecycle + deletion policy inputs |
| E-19 | **Ranked owner pain** — in the owner's own ordering | Whether the wedge matches the pain |
| E-20 | **Willingness to pay** (number, structure, comparison anchor) | Commercial viability |
| E-21 | **Pilot success criteria** — what the owner would call success | The pilot's definition of done |
| E-22 | **Expansion intent** — what they'd want next if the wedge works | The second loop's evidence |

## 3. Fail-closed behavior

- A missing item is recorded as `NEEDS VALIDATION` with its blocking effect named. The affected
  freight-specific design proceeds **only** if it names the assumption, states what breaks if it
  is false, and marks itself provisional.
- **Foundational platform work (P3–P8) is never blocked** by missing items in this table; the
  wedge-specific phases (P10+) carry the validation blockers.
- The Delivered Load Closure hypothesis is **not validated** until the founder records the
  supporting evidence here and in
  [`design-partner-observations.md`](design-partner-observations.md). Nothing in this document
  is evidence; it is the *specification* of the evidence required.

## 4. Recording discipline

Observations land in [`design-partner-observations.md`](design-partner-observations.md) with
accountable sources. This file changes only when the *required set* changes (a founder decision).
The guard suite enforces that this program exists, that it requires accountable sources and
fail-closed behavior, and that no tracked file claims design-partner validation without recorded
evidence.
