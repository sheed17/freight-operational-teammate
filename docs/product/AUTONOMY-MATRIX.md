# Neyma — Autonomy Matrix

> **CANONICAL — autonomy consolidation.** The intended autonomy maturity for each capability.
> **It holds NO authority independent of its sources and creates NO new product decision.** The
> binding autonomy mechanism is [`ADR-010`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md)
> (gate decisions, graduation, caps) and [`ADR-003`](../architecture/decisions/ADR-003-authorization-assertion.md)
> (the permanent authorization assertion); the capability verbs are [`operating-model.md §6.2`](operating-model.md);
> the customer maturity ladder is [`ADR-018 §5`](../architecture/decisions/ADR-018-customer-operational-graph.md);
> provenance is [`semantic-model.md`](../architecture/semantic-model.md). **Current status →
> [`CURRENT.md`](../implementation/CURRENT.md).** On any conflict the cited source wins. Nothing
> here is a claim that any autonomy exists today — the earliest bounded autonomy is **never before
> P14**, and only for classes that earn it.

---

## 1. The presentation ladder maps onto the canonical enforcement

The product describes autonomy as a six-rung **maturity ladder**. Each rung is a *presentation* of
the canonical enforcement primitives — it introduces **no new authority concept**:

| Presentation rung | Canonical capability verb ([`operating-model.md`](operating-model.md)) | Canonical gate decision ([`ADR-010`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md)) |
|---|---|---|
| **OBSERVE ONLY** | Observe | — (no effect; classified read) |
| **RECOMMEND** | Assist (surface/compare) | — (`MODEL_INFERRED` never gates) |
| **DRAFT** | Assist (prepare/draft) | — (prepared effect, not executed) |
| **APPROVAL-REQUIRED EXECUTION** | Execute (+ Verify) | `HUMAN_APPROVAL_REQUIRED` |
| **BOUNDED AUTONOMOUS EXECUTION** | Execute (+ Verify) | `AUTONOMOUS_WITHIN_CAPS` |
| **NEVER AUTONOMOUS / PERMANENT HUMAN AUTHORITY** | Escalate / human decision | `PERMANENT_HUMAN_ASSERTION_REQUIRED` or `FORBIDDEN` |

**Rules that hold at every rung** ([`ADR-010`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md), [`semantic-model.md`](../architecture/semantic-model.md)):
every action class carries **exactly one gate decision, never null**; **autonomy may narrow
automatically but never broaden automatically**; graduation to `AUTONOMOUS_WITHIN_CAPS` requires
supervised history, **zero wrong actions**, a value cap, a frequency cap, a per-counterparty scope,
and an expiring window that reverts to `HUMAN_APPROVAL_REQUIRED`; a human always activates
graduation; **the model never chooses an amount**; and `MODEL_INFERRED` may never gate a
consequential action at any confidence.

The independent **customer maturity ladder** — `observe → normalize → coordinate → execute → own →
primary interface → authoritative → replace` ([`ADR-018 §5`](../architecture/decisions/ADR-018-customer-operational-graph.md))
— is a *per-workflow, per-customer* migration axis; **every advance past "execute" is a recorded,
customer-authorized, reversible decision** ([`ADR-013`](../architecture/decisions/ADR-013-workflow-authority-migration.md)).
Autonomy maturity (this document) and authority migration (ADR-013/018) are **orthogonal**: bounded
autonomy on a class does not move authority to Neyma, and migrated authority does not remove the
per-class gate.

## 2. Per-capability autonomy ceiling

"Ceiling" = the **maximum** intended maturity for the capability's consequential action, once fully
earned. Everything below the ceiling (observe/recommend/draft) is always available earlier. See
[`FREIGHT-CAPABILITY-MAP.md`](FREIGHT-CAPABILITY-MAP.md) for scope and phases.

| Capability | Consequential action | Intended ceiling | Enforcing gate decision |
|---|---|---|---|
| Sales & intake | quoting / pricing commitment | **APPROVAL-REQUIRED** | `HUMAN_APPROVAL_REQUIRED` (sell rate) |
| Load creation | writing loads/stops to system of record | **BOUNDED AUTONOMOUS** (low-risk normalized fields only) | `AUTONOMOUS_WITHIN_CAPS` after graduation |
| Carrier sourcing & tender | committing carrier & buy rate | **NEVER AUTONOMOUS** at commitment | `HUMAN_APPROVAL_REQUIRED` |
| Dispatch & driver comms | routine status sends | **BOUNDED AUTONOMOUS** (earned low-risk templates) | `AUTONOMOUS_WITHIN_CAPS`; bad-news/money `HUMAN_APPROVAL_REQUIRED` |
| Track & trace | routine "on-time" customer updates | **BOUNDED AUTONOMOUS** (routine only) | `AUTONOMOUS_WITHIN_CAPS`; bad-news `HUMAN_APPROVAL_REQUIRED` |
| Appointment scheduling | booking a binding appointment | **APPROVAL-REQUIRED** → within caps | `HUMAN_APPROVAL_REQUIRED` |
| Exception management | resolving an exception | **APPROVAL-REQUIRED / human decision** | `HUMAN_APPROVAL_REQUIRED` |
| Document operations | requesting a missing document | **BOUNDED AUTONOMOUS** (low-risk chase) | `AUTONOMOUS_WITHIN_CAPS`; filing gated |
| Delivered Load Closure | the aggregate | **per contributing loop; closure human-accountable** | mixed |
| Carrier invoice audit / AP | recording payable & paying carrier | **NEVER AUTONOMOUS by default (money out)** | `HUMAN_APPROVAL_REQUIRED` |
| Customer billing / AR | releasing an invoice; write-off | **APPROVAL-REQUIRED** | `HUMAN_APPROVAL_REQUIRED` |
| Claims / OS&D | filing / settling a claim | **NEVER AUTONOMOUS / PERMANENT HUMAN AUTHORITY** | `PERMANENT_HUMAN_ASSERTION_REQUIRED` |
| Carrier compliance | the qualification / trust decision | **NEVER AUTONOMOUS / human** | `PERMANENT_HUMAN_ASSERTION_REQUIRED` (trust) |
| Customer service | answering | **RECOMMEND**; acting inherits the underlying capability's ceiling | — |
| Internal ops & management | reporting | **OBSERVE / RECOMMEND** only | — (no consequential effect) |
| Shared memory & learning | capturing knowledge/corrections | **OBSERVE / RECOMMEND** (decision-support, never gating) | — |

## 3. High-risk classes — the permanent gates

These are called out because they are where an over-eager autonomy design does the most damage.
Each is bound to a canonical gate decision and cannot be graduated past it by confidence, history,
or configuration.

| High-risk class | Intended ceiling | Gate / rule | Canonical source |
|---|---|---|---|
| **Pricing (sell rate)** | APPROVAL-REQUIRED | the model never chooses an amount; a human sets/approves the rate | [`PRODUCT.md §10`](../../PRODUCT.md), engineering-principles (money fence) |
| **Carrier selection & buy rate** | NEVER AUTONOMOUS at commitment | `BOOK_CARRIER` is `HUMAN_APPROVAL_REQUIRED`; needs a `QUALIFIED` decision or human approval | domain-entities (load family), target spec |
| **Claims settlement / legal commitments** | PERMANENT HUMAN AUTHORITY | legal/liability/settlement judgment is human; Neyma does not file claims | [`operating-model.md`](operating-model.md) (L11), W11 |
| **Banking / remittance changes** | STRONG HUMAN VERIFICATION | `remittance_party` is a verified `OWNER_ASSERTED`/documented binding; a change is a re-bind requiring re-verification; a counterparty claim is a fraud signal | domain-entities (financial), W9, [`ADR-003`](../architecture/decisions/ADR-003-authorization-assertion.md) |
| **Payments / money out** | NEVER AUTONOMOUS by default | money leaving the business requires human approval, permanently | [`operating-model.md`](operating-model.md) (§7), W9 |
| **Safety incidents** | ESCALATE / human (Sev-0) | a Sev-0 condition auto-engages the brake; admission stops | ADR-011, W7 |
| **`UNKNOWN_OUTCOME`** | STOP · investigate · escalate; **never auto-resolves; timeout is never `FAILED`** | an unknown outcome has an accountable human owner + permitted terminal handling | [`workflows/registry.md`](../specifications/workflows/registry.md), semantic-model |
| **Customer-impacting exceptions (bad news)** | APPROVAL-REQUIRED / human-owned | what to tell the customer when the news is bad is human-owned | [`operating-model.md`](operating-model.md) (L5/L10), W5/W10 |
| **The authorization assertion** | PERMANENT HUMAN ASSERTION — never graduates | only an authenticated human may assert an authorization; a counterparty claim is a fraud signal, never authorization | [`ADR-003`](../architecture/decisions/ADR-003-authorization-assertion.md) (PERMANENT PRODUCT TRUTH) |

## 4. What this means in practice

- **Nothing consequential is autonomous today.** The safety foundation is built and dark: **P3
  kernel COMPLETE but dark; P4 adapter containment COMPLETE and adjudicated, with R-07 recorded
  CONTAINED** — [`CURRENT.md`](../implementation/CURRENT.md). **Containment granted no autonomy of
  any kind:** production writes stay dark behind a `ROUTE_NOT_CONFIGURED` refusal and the
  production `GateRegistry` stays EMPTY until U8.1 / P8. Bounded autonomy remains a P14
  destination.
  *(SUPERSEDED wording, kept so it is recognisable if it returns: "P4 adapter containment READY,
  not complete; R-07 OPEN".)*
- **Every consequential action passes the full effect pipeline** — `Work Item → Pipeline Instance →
  policy & validation → optional approval → atomic checkpoint → Checkpoint Witness → Effect Grant →
  atomic claim → adapter execution → verification → outcome → evidence & projection → closure`
  ([`ARCHITECTURE.md`](../../ARCHITECTURE.md)) — regardless of autonomy rung. Bounded autonomy
  removes the *per-action human approval*, never the pipeline, the caps, the verification, or the
  brake.
- **The brake is admission control, always available.** It governs whether new work may start, not
  the termination of work already running, and automation may engage/widen it but never
  release/narrow it (ADR-011).
