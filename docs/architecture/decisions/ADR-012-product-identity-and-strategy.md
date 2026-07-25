# ADR-012 — Stable Product Identity and Mutable Strategy

**Status:** ✅ **FINAL — U-REBASELINE-1 (founder-authorized, 2026-07-20).**
**Authority:** an explicit founder product decision. Customer-specific operational rules remain
`NEEDS VALIDATION` regardless of anything here.
**Supersedes:** every prior absolute that made the first implementation wedge, the current TMS
posture, or any competitor's shape the permanent identity of the product.

---

## 1. Decision — the canonical identity

> **Neyma is the AI-native operating platform and system of action for small and medium freight
> and logistics companies.**
>
> It connects to the systems the company already uses, maintains coherent operational state
> across them, owns open operational obligations, coordinates authorized execution and remains
> responsible until the relevant business outcome is closed.

Neyma coordinates: operational state · responsibilities · missing information and missing events
· documents and evidence · communications · exceptions and conflicts · approvals · authorized
external effects · effect verification · accountable human ownership · final business-loop
closure.

**The unit of value remains a correctly closed operational loop.** The eleven W1–W11 freight
loops remain the canonical operating-domain map — a map, **not** an instruction to build every
loop simultaneously.

## 2. What is stable vs what is strategy

| Class | Contents | Change discipline |
|---|---|---|
| **Stable identity** | §1 above; the safety architecture (ADR-001..011); tenant isolation; access ≠ authority; the loop-closure unit of value | Changes require a founder decision recorded as an ADR supersession |
| **Mutable strategy** | The initial ICP; the first commercial wedge (currently **Delivered Load Closure** — a hypothesis); integration mix per customer; loop sequencing; pricing/packaging | The founder may revise on customer evidence **without** changing the identity |

The first implementation wedge is **evidence about the product, never the definition of it.**

## 3. Initial ICP vs broader direction

- **Initial ICP:** small and medium **US freight brokerages**, initially truckload-oriented, with
  fragmented systems, shared operations inboxes, limited internal engineering, and meaningful
  manual operational labor.
- **Broader direction:** small and medium **freight and logistics operators** — additional
  brokerage modes and adjacent logistics businesses **where evidence supports expansion**.

The broader direction never justifies broadening the initial implementation scope by itself.

## 4. What Neyma must not become

A narrow invoice processor · a document-extraction utility · a temporary browser bot · a
Slack-only interface · a collection of disconnected agents · a thin automation wrapper around a
TMS · a product whose first wedge permanently limits its identity.

**And symmetrically:** the repository must not impose artificial ceilings. The following are
**rejected as permanent product rules** (they may still describe an individual customer's
*initial* posture):

- ~~"The brokerage never rips out its TMS."~~
- ~~"Neyma never becomes a system of record."~~
- ~~"Anyone wanting TMS replacement is the wrong customer."~~
- ~~"The human must establish every session."~~
- ~~"Neyma must remain permanently outside native freight workflows."~~

The replacement position is ADR-013. The credential position is ADR-014.

**No competitor defines Neyma's canonical identity.** Competitor products are market references,
nothing more.

## 5. Consequences

- `PRODUCT.md` carries §1 verbatim as the canonical identity statement.
- `docs/product/operating-model.md`'s permanent "never the system of record" boundary (§2.4,
  §7.2) is **superseded in place** by ADR-013 with disarming annotations — the document remains
  canonical for how a brokerage operates.
- Guards (`eval/tests/test_rebaseline_invariants.py`) fail the build if any rejected absolute
  returns to a current-authority document as a live claim.
