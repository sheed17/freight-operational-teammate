# Neyma — The Quote-to-Cash Load Lifecycle

> **CANONICAL — lifecycle consolidation.** The canonical end-to-end freight lifecycle, stitching
> the eleven loops into one flow. **It holds NO authority independent of its sources and creates NO
> new product decision.** Loop boundaries, closure conditions and cross-loop handoffs are the
> Operating Model's and the workflow registry's — not restated to differ: loops →
> [`operating-model.md`](operating-model.md) + [`workflows/registry.md`](../specifications/workflows/registry.md);
> effect pipeline → [`ARCHITECTURE.md`](../../ARCHITECTURE.md); autonomy → [`AUTONOMY-MATRIX.md`](AUTONOMY-MATRIX.md);
> **status → [`CURRENT.md`](../implementation/CURRENT.md).** On any conflict the cited source wins.

---

## 1. The lifecycle, end to end

```
customer demand
  → quote                         (W1)
  → book                          (W1)
  → create load                   (W1)
  → source carrier                (W2)   ── gated by carrier qualification (W3, continuous)
  → tender                        (W2)
  → dispatch                      (W4)   ── incl. appointment booking (W4)
  → pickup                        (W4→W5)
  → in-transit tracking           (W5)
  → appointments (delivery)       (W4)
  → exceptions                    (W7, cross-cutting — may fire at ANY stage)
  → delivery                      (W5→W6)
  → documents                     (W6)
  → carrier payable               (W9)   ── carrier invoice audit + AP
  → customer billing              (W8)
  → collections                   (W8)
  → closure                       (per-loop, at the business outcome)
  → claims / post-load follow-up  (W11)
  → reporting & learning          (platform + shared knowledge base)
```

Two loops are **cross-cutting** and are not a single stage: **W7 Exceptions** and **W10 Customer
Communications** attach to every stage. **W3 Compliance** is **continuous** and gates W2. The
**Delivered Load Closure** wedge is the segment `delivery → documents → reconciliation → billing
readiness` (parts of W5/W6/W7/W8/W10).

## 2. What interacts at each stage

At every stage the same shared spine is in play. The table shows the primary Work Item, the
evidence that must exist, the policy/approval gate, the external effects, and the cross-loop
handoff created (handoffs are **atomic** — the downstream Work Item exists in the same commit as
the source transition, or the source does not advance).

| Stage | Loop | Primary Work Item | Key evidence | Policy / approval | External effects | Atomic handoff created |
|---|---|---|---|---|---|---|
| Demand & quote | W1 | `QUOTE_TO_COMMITMENT` | source demand (provenance); market rate (`DECISION_SUPPORT`) | **sell rate `HUMAN_APPROVAL_REQUIRED`** | `SEND_QUOTE` | — |
| Book & create load | W1 | `QUOTE_TO_COMMITMENT` | accepted order; entered-field provenance | gated write | load/stop creation | **W1→W2** `COVER_LOAD` |
| Carrier qualification | W3 | `QUALIFY_CARRIER` | authority/insurance/safety (freshness read) | trust decision **human-reserved** | — (reads) | **W3→W2 gate** unblocks tender |
| Source carrier | W2 | `COVER_LOAD` | carrier identity; buy-rate `MODEL_EXTRACTED` until accepted | **carrier & rate `HUMAN_APPROVAL_REQUIRED`** | `POST_LOAD` | — |
| Tender & rate con | W2 | `COVER_LOAD` | `QUALIFIED` decision at tender time | rate-con issuance gated | `SEND_TENDER`, `ISSUE_RATECON` | **W2→W4** `DISPATCH_READY` |
| Dispatch & appointment | W4 | `DISPATCH_READY` | driver/equipment confirmation; confirmed window (`REQUESTED`≠`CONFIRMED`) | binding appointment **human-confirmed** | `REQUEST_APPOINTMENT`, `SEND_OUTBOUND` | **W4→W5** `TRACK_LOAD` (at pickup) |
| In-transit tracking | W5 | `TRACK_LOAD` | positions `SYSTEM_IMPORTED`; ETA `MODEL_INFERRED` (never gates) | bad-news comms human-owned | `SEND_OUTBOUND` (check-calls) | **W5→W6** `COMPLETE_DOCS` (at delivery) |
| Delivery & documents | W6 | `COMPLETE_DOCS` | content-addressed docs; deterministic load binding | filing gated; ambiguity→human | `FILE_DOCUMENT` | **W6→W8** `BILL_AND_COLLECT`; **W6→W11** `HANDLE_CLAIM` (OS&D) |
| Carrier payable | W9 | `AUDIT_AND_PAY` | rate con + authorized accessorials (Material Facts); bank observation for settlement | **money-out `HUMAN_APPROVAL_REQUIRED`** | `RECORD_PAYABLE`, `PAY_CARRIER` | (from carrier-invoice→W9) |
| Customer billing | W8 | `BILL_AND_COLLECT` | POD-gated eligibility; amount by deterministic validation | **invoice release `HUMAN_APPROVAL_REQUIRED`** | `RAISE_INVOICE`, `REISSUE_INVOICE` | — |
| Collections | W8 | `BILL_AND_COLLECT` | aging; Payment Application (bank observation) | write-off/short-pay **human** | (reads + reminders via W10) | dispute→W7 |
| Closure | any | the loop's Work Item | closure conditions met (evidence + policy) | closure event is **immutable** | — | reopening = a new/linked Work Item |
| Claims / follow-up | W11 | `HANDLE_CLAIM` | assembled packet + timeline; deadlines as Expectations | **settlement human authority** | financial adjustment (compensation) | — |
| Reporting & learning | platform | (oversight) | evidence behind every metric; corrections with provenance | read/report only | — | feeds the shared knowledge base |
| Exceptions (any stage) | W7 | `RESOLVE_EXCEPTION` | assembled evidence; decision ref | resolution **human**; Sev-0 engages brake | compensation (gated) | **any→W7** |
| Customer comms (any stage) | W10 | `CUSTOMER_COMMS` | message-delivery receipt | bad-news/money **human-gated** | `SEND_OUTBOUND` | **any→W10** |

## 3. Closure is the business outcome, never the artifact

A stage advances only on its real outcome. The workflow registry's **false-closure rules** are
binding — none of these closes a loop:

> quote created ≠ accepted · accepted ≠ covered · assigned ≠ picked up · tracking "delivered" ≠ POD
> received · POD received ≠ invoice released · invoice released ≠ delivered · delivered ≠ collected ·
> payable entered ≠ approved · approved ≠ paid · payment initiated ≠ settled · document uploaded ≠
> valid · message sent ≠ received/complied.

Closure requires all of: the obligation satisfied or explicitly dispositioned; every required
effect reached a valid operational outcome; open conflicts blocking or referenced by an authorized
decision; required Expectations discharged/cancelled; required documents/evidence present; required
reconciliation complete; any `UNKNOWN_OUTCOME` owned with permitted terminal handling; no mandatory
downstream obligation silently abandoned; the closure event immutable; reopening creates a new or
linked Work Item ([`workflows/registry.md`](../specifications/workflows/registry.md), LOOP-CLOSURE CONTRACT).

## 4. Degraded operation — the product is not useless without write access

The lifecycle still runs when integrations are missing (from the workflow registry's degraded-mode
matrix). With no TMS API, Neyma observes via browser reads, prepares every effect, and actuates via
browser on a human session; read-only TMS → it presents the exact action for a human to execute and
captures the resulting evidence; email-only counterparty → full inbound observation + gated
outbound; spreadsheets → ingested, never silently promoted; missing tracking → Expectations go
`INDETERMINATE` (honest), humans make check calls. **When write access is unavailable, autonomous
effect capability narrows to zero, but observe + prepare + verify + exception-detect remain.**

## 5. Where the lifecycle is in the build

**Nothing in this lifecycle is implemented end-to-end to the canonical architecture yet.** The
first slice to run is **Delivered Load Closure in shadow (read-only) at phase P10**, then supervised
effects at P12, then multi-loop expansion + customer-authorized authority migration at P13. The
safety foundations that make any live write possible (P3 kernel COMPLETE but dark; **P4 adapter
containment READY, not complete; R-07 OPEN**) are the current focus — see
[`CURRENT.md`](../implementation/CURRENT.md). Per-capability phase mapping is in
[`FREIGHT-CAPABILITY-MAP.md`](FREIGHT-CAPABILITY-MAP.md).
