# Operational Workflow Registry — The Eleven Loops

**Layer:** Operational Workflow Specification. **Derived from (frozen):** the Operating Model (the canonical L1–L11 loops, §7) · the Foundational / State-Machine / Event / Domain-Entity / Adapter specs · ADR-001…011.
**Binding:** ### **This registry is the sole canonical index of the eleven workflows. The loop names and boundaries are the Operating Model's — NOT renamed, combined, or split to match code.**

> ### **A workflow is the deterministic coordination contract through which Neyma helps bring a real freight obligation from trigger to ACCOUNTABLE CLOSURE.** It is **not** a UI flow, a queue consumer, an agent prompt, a parser, an adapter sequence, a single Pipeline Instance, a vendor automation, or a happy-path checklist. ### **It composes — and NEVER re-invents — the frozen machinery** (domain entities · Work Items · Pipeline Instances · Observations · Evidence · Claims · Identity Bindings · Expectations · Conflicts · Exceptions · Approvals · Policies/Rules · Checkpoint Witnesses · Effect Grants · adapter ops · verification · compensation · human ownership · canonical events).

## The product model these workflows make explicit
> **Neyma is NOT "document processing connected to a TMS."** ### **Neyma is the operational execution layer that observes fragmented freight work, maintains a coherent business model, coordinates bounded actions, detects MISSING events, manages exceptions, and helps accountable humans CLOSE operational loops.** ### **Success is NEVER "document extracted / record written / message sent / invoice entered / status changed / task done" — success is a business obligation SATISFIED or explicitly dispositioned, with the loop verifiably closed.**

## The eleven canonical loops *(exact Operating Model names)*
| WF | Loop | Business outcome | Primary Work Item | Closes at |
|---|---|---|---|---|
| **W1** | **L1 Quote** *(incl. demand/order intake)* | a priced commitment the customer accepted, with downstream coverage work created | `QUOTE_TO_COMMITMENT` | an **accepted Customer Order** with accountable coverage work created — **NOT** a sent quote |
| **W2** | **L2 Procurement** *(sourcing + tender + rate con)* | a **confirmed Carrier Assignment** at a committed buy rate | `COVER_LOAD` | a confirmed **Carrier Assignment** + signed Rate Con — **NOT** a search result or a verbal yes |
| **W3** | **L3 Compliance** *(continuous)* | carriers are **qualified at the relevant time** for the relevant movement | `QUALIFY_CARRIER` | a current **Qualification Decision** on file — **NOT** a one-time onboarding |
| **W4** | **L4 Dispatch** *(readiness + appointment)* | the load is **operationally ready to move** (driver, equipment, appointment, refs, docs) | `DISPATCH_READY` | verified **readiness evidence** — **NOT** a sent dispatch message |
| **W5** | **L5 Tracking** *(in-transit)* | the customer knows the true status; delays caught early | `TRACK_LOAD` | delivery reached + status current — **NOT** a tracking "delivered" claim |
| **W6** | **L6 Documentation** | the **right documents on the right load**, complete for billing | `COMPLETE_DOCS` | the **Document Packet `COMPLETE`** on the correct load — **NOT** a delivered status |
| **W7** | **L7 Exceptions** *(cross-cutting)* | every exception reaches an accountable, decision-referenced resolution | `RESOLVE_EXCEPTION` | `RESOLVED{decision_ref}` — **NOT** the originating loop moving on |
| **W8** | **L8 Billing** *(customer AR + cash)* | the customer **PAID** | `BILL_AND_COLLECT` | ### **`PAID` (or an authorized write-off / approved short-pay / credit-rebill settlement)** — **NOT** a sent invoice (P24, CD-10) |
| **W9** | **L9 Settlement** *(carrier AP + payment)* | the carrier **PAID correctly**, reconciled | `AUDIT_AND_PAY` | ### **the payable **settled** (verified payment)** — **NOT** a recorded payable (CD-11) |
| **W10** | **L10 Customer comms** | the customer got the right message; commitments tracked | `CUSTOMER_COMMS` | the message delivered + any commitment tracked — **NOT** a sent message |
| **W11** | **L11 Claims** *(OS&D)* | an OS&D case reaches a referenced resolution | `HANDLE_CLAIM` | `RESOLVED{decision_ref}` + financial adjustment created — **NOT** a paid invoice being immutable |

## The 61-point defaults *(a workflow states only what differs)*
Ownership = **exactly one accountable human owner, always** (I1). Automation may **prepare · prioritize · gather evidence · perform allowed (gated) actions · narrow autonomy · escalate · engage a brake · recommend** — ### **it may NEVER erase human accountability.** All consequential effects go through Work Item → Pipeline → (Approval) → Checkpoint → Witness → Grant → adapter → verification → record → project. Reads are classified (informational/decision-support/consequential-freshness). `MODEL_INFERRED` never gates. Every transition maps to a **frozen event** (no workflow event invented). Crash-recovery, retry (classified), unknown-outcome (→ human-owned `NEEDS_VERIFICATION`), timeout (durable timer, never = failure) are inherited from the machines. Audit = the event stream reconstructs the loop.

## STEP-CONTRACT FORMAT *(per consequential step)*
`Step ID · name · owning machine · trigger · business state · required observations/evidence/bindings/field-authority/freshness/provenance/entity-versions · policy · gate · approval · brake · adapter op · pipeline transition · domain transition · event in/out · durable writes · txn boundary · idempotency identity · Commit Key (if consequential) · Material-Facts (if consequential) · verification mode · expected result · failure · unknown-outcome · human action · next legal steps · test.` ### **No step relies on an implicit transition. No step says "update the TMS" without naming the canonical adapter op, target resource, external mapping, Action Class, checkpoint inputs, Commit Key, Material Facts, and verification mode.**

## LOOP-CLOSURE CONTRACT *(every loop)*
Closure REQUIRES **all** of: the obligation was **satisfied or explicitly dispositioned** · all required effects reached a valid operational outcome · open Conflicts are **blocking or referenced by an authorized decision** · required Expectations discharged/cancelled/dispositioned · required documents/evidence present · required reconciliation complete · **any `UNKNOWN_OUTCOME` has an accountable owner + permitted terminal handling** · **no mandatory downstream obligation silently abandoned** · the closure event is **immutable** · reopening creates a **new phase or linked Work Item**.

### FALSE-CLOSURE SIGNALS *(explicitly rejected — none of these closes a loop)*
quote created ≠ accepted · accepted ≠ covered · assigned ≠ picked up · tracking "delivered" ≠ POD received · POD received ≠ invoice released · invoice released ≠ delivered · delivered ≠ collected · payable entered ≠ approved · approved ≠ paid · payment initiated ≠ settled · document uploaded ≠ valid · message sent ≠ received/complied.

## WORK-ITEM OWNERSHIP *(no open obligation is ever ownerless)*
default owner = the loop's role owner · reassignment = `OwnershipTransferred` (human) · **unavailable owner ⇒ an Exception, reassign before any consequential action** · escalation owner = the role's escalation path · after-hours = a role-based fallback · **ownership during `UNKNOWN_OUTCOME`/`Conflict`/`COMPENSATION_FAILED` = a named human, entity frozen** · at terminal closure = the closing actor of record. ### **A human leaving (hostile #30) ⇒ every owned open Work Item raises an Exception; no consequential action proceeds until reassigned.**

## CROSS-LOOP HANDOFFS *(a handoff must NOT create a responsibility gap)*
| Handoff | Trigger | Obligation created | Atomic? |
|---|---|---|---|
| W1→W2 | Order `CONVERTED` | `COVER_LOAD` | ### **the downstream Work Item creation is ATOMIC with the source transition (one commit); the source may NOT close until it durably exists** |
| W2→W4 | Assignment `ACTIVE` | `DISPATCH_READY` | atomic |
| W3→W2 (gate) | Qualification `QUALIFIED` | unblocks tender | — |
| W4→W5 | Stop `DEPARTED` (pickup) | `TRACK_LOAD` | atomic |
| W5→W6 | delivery reached | `COMPLETE_DOCS` | atomic |
| W6→W8 | Packet `COMPLETE` | `BILL_AND_COLLECT` | atomic |
| carrier-invoice→W9 | invoice received | `AUDIT_AND_PAY` | atomic |
| any→W7 | an Exception/Conflict | `RESOLVE_EXCEPTION` | atomic |
| W6/W5→W11 | OS&D notation | `HANDLE_CLAIM` | atomic |
| any→W10 | a customer-facing need | `CUSTOMER_COMMS` | atomic |
> ### **A source loop may NEVER close merely because it EMITTED a downstream event if the downstream obligation was not durably created (hostile #33). Handoff = the downstream Work Item exists in the same commit as the source transition, or the source does not advance.** Duplicate handoffs deduplicate on the source event id; replay recreates the projection, never re-actuates (GR-11).

## DEGRADED-MODE MATRIX *(the product is NOT useless without write access)*
| Integration missing | Neyma still | Requires human | Value retained |
|---|---|---|---|
| No TMS API / browser-only | observes (browser reads), prepares every effect, **actuates via A15 browser on a human session** | login | ### **full loop reachable via browser actuation (the live proof)** |
| Read-only TMS | observes + prepares + **presents the exact action for a human to execute**, captures the resulting evidence | execute the write | preparation + verification + exception detection |
| No portal access | observes via email/docs; prepares | portal actions | most of the loop |
| Email-only counterparty | full inbound observation + gated outbound | — | high |
| Spreadsheets as source | ingests (A16), never promotes silently | confirm semantics | evidence + reconciliation |
| Missing tracking | Expectations go `INDETERMINATE` (honest) | manual check calls | delay detection degrades to human |
| Missing accounting | observes payments where possible; prepares | manual entry | AR/AP prep + audit |
> ### **When write access is unavailable, autonomous EFFECT capability narrows to zero, but OBSERVE + PREPARE + VERIFY + EXCEPTION-DETECT remain — the human executes, Neyma captures the evidence and closes the loop with them.**

## METRICS TAXONOMY *(distinct classes — "documents processed" is NOT a loop-success metric)*
- **Activity:** documents read, messages drafted, reads performed *(inputs, not success)*.
- **Workflow-completion:** first-pass completion rate, cycle time per loop, human touches, unresolved Work Item age.
- ### **Business-outcome:** DSO (L8), carrier-payment cycle time (L9), invoice-release time (L6→L8), coverage time (L2), on-time-delivery (L5), missed-obligation rate — **the ones the owner cares about.**
- ### **Safety:** `UNKNOWN_OUTCOME` rate, compensation rate, drift-void rate, duplicate-effect-prevention count, autonomous-vs-human-approval ratio, correction rate — **near-zero targets; a rise is a signal.**

## NEEDS VALIDATION *(all fail-closed; none blocks)*
The **first-loop hypothesis (L6→L8, Documentation→Billing)** is `NEEDS VALIDATION` against the design partner's actual pain (Operating Model §, Discovery §13); autonomy graduation thresholds (V11); per-customer billing/document rules (V4/V5); the L8 canonical closure disposition set; after-hours ownership model; degraded-mode adoption sequence.
