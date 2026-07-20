# Open Validation Items

> **Every unresolved product or workflow rule lives here, with a safe interim behaviour.**
> An agent that hits one of these **stops and requests evidence**. It does not choose a plausible
> default, because in this system a plausible default becomes a permanent, invisible decision
> enforced on real money.

**The safe default for any unresolved consequential behaviour is: fail closed and route to
accountable human review.** Where an item below names a different interim behaviour, that is a
deliberate, narrower exception.

**Source:** items V-01…V-21 are the customer-specific unknowns already enumerated in
[`freight-discovery.md`](freight-discovery.md) §13. Items V-A* are architectural. Nothing here was
invented for this registry.

---

## Blocking classes

| Class | Meaning | Effect |
|---|---|---|
| **ARCHITECTURE_BLOCKER** | Blocks a schema or architecture decision | Blocks the named phase for everyone |
| **IMPLEMENTATION_BLOCKER** | Blocks a specific unit's implementation | Blocks that unit only |
| **WORKFLOW_BLOCKER** | Blocks one operational loop | Blocks that loop only |
| **CUSTOMER_CONFIG** | Varies per brokerage; must be configurable, not hardcoded | Blocks nothing; forbids a constant |
| **NON_BLOCKING** | Future discovery | Blocks nothing |

> ### **A `CUSTOMER_CONFIG` item is never an excuse to hardcode a value "for now".**
> An unvalidated rule compiled into code is indistinguishable from a validated one six months later.

---

## ⛔ ARCHITECTURE BLOCKERS

### V-21 — Are order, load, movement, leg, stop and TMS record distinct entities, and how do they relate?

| | |
|---|---|
| **Question** | At this partner, are customer order, brokerage load, carrier movement, leg, stop and TMS record distinct — and 1:1, 1:N or N:M? |
| **Affected workflow** | All eleven |
| **Affected entity/state** | The entire freight-domain entity model |
| **Implementation impact** | ### **Blocks any freight-domain schema.** The 40 domain entities' cardinalities are marked *provisional* precisely because of this. |
| **Blocking status** | **ARCHITECTURE_BLOCKER** — blocks **P9** |
| **Safe interim behaviour** | Cardinalities remain provisional with a pre-specified migration path per entity. Do not collapse them to 1:1 for convenience. |
| **Evidence needed** | The partner's actual load records with their relationships |
| **Accountable source** | Design partner, via the founder |
| **Status** | **OPEN** |

### V-A1 — Which transition/event classes violate `AC-EVT-003`? (COUNT NEEDS ADJUDICATION)

| | |
|---|---|
| **Question** | 13 of 134 transitions name no event outright, in 4 structurally different classes ([`TRANSITION-EVENT-AUDIT.yaml`](../implementation/TRANSITION-EVENT-AUDIT.yaml)). Which classes are legitimate non-producers and which are mapping gaps? The retired "24" was never mechanically computed. |
| **Affected workflow** | All |
| **Affected entity/state** | State machines ↔ event contracts |
| **Implementation impact** | ### **Blocks P5.** If they are a gap, the event corpus is incomplete and replay reconstructs a state history with holes. |
| **Blocking status** | **ARCHITECTURE_BLOCKER** — blocks **P5**, gate **G2** |
| **Safe interim behaviour** | The bijection guard asserts the exact set; no transition may silently acquire or lose an event |
| **Evidence needed** | Adjudication against each machine — **a repository decision, not a customer one** |
| **Accountable source** | Architecture (settle before P5) |
| **Status** | **OPEN** |

### V-15 — How are detention, lumper and TONU authorised in the moment, and where is that recorded?

| | |
|---|---|
| **Question** | When an accessorial is agreed by phone mid-load, what makes it authorised, and where does it live? |
| **Affected workflow** | W5 Tracking, W7 Exceptions, W8 Billing, W9 Settlement |
| **Affected entity/state** | Approval, Accessorial, Expectation |
| **Implementation impact** | ### **Determines whether reconciliation can ever be correct.** If authorisation lives only in a phone call, an invoice line can be legitimate with no record — and an agent that flags it as an overbill is wrong. |
| **Blocking status** | **ARCHITECTURE_BLOCKER** — blocks **P8** |
| **Safe interim behaviour** | ### **Fail closed.** An unmatched accessorial is an Exception routed to a human — **never auto-approved and never auto-disputed.** |
| **Evidence needed** | Real examples of in-the-moment authorisation |
| **Accountable source** | Design partner |
| **Status** | **OPEN** |

### V-14 — Where is the agreed buy rate recorded before the rate confirmation exists?

| | |
|---|---|
| **Question** | Between agreeing a rate with a carrier and issuing the rate con, where does the number live? |
| **Affected workflow** | W2 Procurement, W8 Billing |
| **Affected entity/state** | Commercial entities; provenance |
| **Implementation impact** | Determines whether a pre-rate-con buy rate has any authoritative source at all |
| **Blocking status** | **ARCHITECTURE_BLOCKER** — blocks **P9** |
| **Safe interim behaviour** | Treat the rate con as the only authoritative buy rate. Earlier values are `MODEL_INFERRED` observations and may not authorise payment. |
| **Evidence needed** | Partner process description |
| **Accountable source** | Design partner |
| **Status** | **OPEN** |

## ⛔ IMPLEMENTATION BLOCKERS

### V-04 — Who may approve what, at what dollar threshold?

| | |
|---|---|
| **Question** | The partner's actual approval authority matrix — roles, limits, escalation |
| **Affected workflow** | All consequential loops |
| **Affected entity/state** | Approval, Policy, Rule |
| **Implementation impact** | ### **Blocks the policy engine.** Caps and authority are policy inputs; without them the engine has no thresholds to compile. |
| **Blocking status** | **IMPLEMENTATION_BLOCKER** — blocks **P8** |
| **Safe interim behaviour** | ### **Every consequential action requires explicit human approval, with no threshold-based auto-approval whatsoever.** ADR-003 makes this permanently safe as a floor. |
| **Evidence needed** | The partner's approval matrix and approver names/roles |
| **Accountable source** | Design partner |
| **Status** | **OPEN** |

### V-05 / V-06 — What is the partner's actual TMS, and does it have an API they can access?

| | |
|---|---|
| **Question** | TruckingOffice was **our** test rig. Is it theirs? Is there an API? |
| **Affected workflow** | W4, W6, W8, W9 |
| **Affected entity/state** | TMS adapter contract |
| **Implementation impact** | Determines whether the TMS adapter is an API client or a browser agent, and how much of the write model transfers |
| **Blocking status** | **IMPLEMENTATION_BLOCKER** — blocks **P4** adapter work for the real partner |
| **Safe interim behaviour** | The adapter contract is written to be TMS-agnostic; discovery is generalised and fails closed on an unrecognised screen |
| **Evidence needed** | TMS name, version, API availability, credentials posture |
| **Accountable source** | Design partner |
| **Status** | **OPEN** |

### V-10 — Is the inbox Outlook/M365 or Google, shared or individual, and how many?

| | |
|---|---|
| **Question** | The actual mailbox topology |
| **Affected workflow** | W6, W7, W10 |
| **Affected entity/state** | Inbound-comms adapter |
| **Implementation impact** | Determines the ingestion adapter and the tenancy of a shared mailbox |
| **Blocking status** | **IMPLEMENTATION_BLOCKER** — blocks the P4 inbound adapter |
| **Safe interim behaviour** | IMAP with an explicit per-mailbox tenant binding; **no ambient mailbox→tenant inference** |
| **Evidence needed** | Provider, topology, access |
| **Accountable source** | Design partner |
| **Status** | **OPEN** |

## ⛔ WORKFLOW BLOCKERS

### V-W1 — Is Delivered Load Closure actually the right wedge?

*(Rebaselined by U-REBASELINE-1: the founder-selected wedge is now **Delivered Load Closure** —
PRODUCT.md §15 — superseding the narrower "W6 Documentation → W8 Billing" framing this item
originally carried. The validation question is unchanged in kind and remains OPEN.)*

| | |
|---|---|
| **Question** | Is owning delivered loads to billing-ready closure the partner's real acute pain, or ours? |
| **Affected workflow** | W5, W6, W7, W8, W10 (the parts Delivered Load Closure spans) |
| **Affected entity/state** | The wedge Work Item and its closure conditions |
| **Implementation impact** | ### **Determines what P10 builds.** PRODUCT.md §15 marks this a `HYPOTHESIS`, explicitly not a decision. The founder may revise the wedge on customer evidence without changing the platform identity (ADR-012 §2). |
| **Blocking status** | **WORKFLOW_BLOCKER** — blocks **P10** |
| **Safe interim behaviour** | ### **The wedge stays marked `NEEDS DESIGN-PARTNER VALIDATION` and may not be promoted to validated product truth.** Foundational phases P3–P8 proceed regardless — they are loop-independent. |
| **Evidence needed** | The evidence set in [`DESIGN-PARTNER-EVIDENCE-PROGRAM.md`](DESIGN-PARTNER-EVIDENCE-PROGRAM.md), E-08/E-16/E-17/E-19 first |
| **Accountable source** | Design partner |
| **Status** | **OPEN** |

### V-16 — How do PODs actually arrive?

| | |
|---|---|
| **Question** | Carrier email, driver text photo, portal, or all three? |
| **Affected workflow** | W6 Documentation |
| **Implementation impact** | Determines which inbound adapters W6 needs on day one |
| **Blocking status** | **WORKFLOW_BLOCKER** — blocks **P10** |
| **Safe interim behaviour** | Email ingestion only; other channels raise an Expectation that a human satisfies |
| **Evidence needed** | Channel mix with rough proportions |
| **Accountable source** | Design partner |
| **Status** | **OPEN** |

### V-17 — What percentage of carrier invoices carry a discrepancy, and what happens then?

| | |
|---|---|
| **Question** | The real discrepancy rate and the real resolution path |
| **Affected workflow** | W7 Exceptions, W8 Billing |
| **Implementation impact** | Determines the exception taxonomy and whether the volume justifies automation |
| **Blocking status** | **WORKFLOW_BLOCKER** — blocks **P8** taxonomy |
| **Safe interim behaviour** | Every discrepancy is an Exception with a human owner; no auto-resolution of any class |
| **Evidence needed** | Historical rate + resolution examples |
| **Accountable source** | Design partner |
| **Status** | **OPEN** |

### V-18 — Do they factor? Do their carriers factor?

| | |
|---|---|
| **Question** | Factoring changes **who gets paid** |
| **Affected workflow** | W9 Settlement |
| **Implementation impact** | A payment to the wrong party is unrecoverable in practice |
| **Blocking status** | **WORKFLOW_BLOCKER** — blocks **P13** W9 |
| **Safe interim behaviour** | ### **Fail closed.** Remittance party is always human-confirmed; never inferred from the invoice. |
| **Evidence needed** | Factoring relationships and NOA handling |
| **Accountable source** | Design partner |
| **Status** | **OPEN** |

## CUSTOMER CONFIGURATION QUESTIONS

These block nothing. **They forbid a hardcoded constant.**

| ID | Question | Loop | Interim behaviour |
|---|---|---|---|
| **V-01** | Loads/day, quotes/day, invoices/week, emails/day | all | No volume assumptions in design; no fixed batch sizes |
| **V-02** | Brokerage-only, asset-based or hybrid | all | Support brokerage-only; asset paths raise `NEEDS VALIDATION` |
| **V-03** | Freight mix — van/reefer/flatbed, TL vs LTL, spot vs contract | W1, W2 | Mode is a configured attribute, never assumed |
| **V-07** | Which load boards, visibility platforms, portals | W2, W5 | Adapters are registered per tenant; none assumed present |
| **V-08** | Accounting system and how data reaches it | W8, W9 | Accounting is an adapter, not an assumption |
| **V-11** | How loads enter — tender, EDI 204, portal, phone | W1 | Email tender only; others raise an Expectation |
| **V-12** | How a sell rate is decided | W1 | ### **Never computed by Neyma.** Human-entered or TMS-sourced. |
| **V-13** | How carriers are sourced | W2 | No automated sourcing |
| **V-19** | How carriers are vetted, per-load or per-onboarding | W3 | FMCSA read-only; no automated vetting decision |
| **V-20** | Claims frequency and handler | W11 | W11 is not implemented; claims route to a human |

## NON-BLOCKING FUTURE DISCOVERY

| ID | Question | Notes |
|---|---|---|
| **V-09** | ### **What is in their spreadsheets, and why isn't it in the TMS?** | The corpus calls this *"the highest-value single unknown"*. Non-blocking today because no phase before P9 depends on it — but it is the most likely source of a surprise that invalidates a model. |

---

## Summary

| Class | Count | Blocks |
|---|---|---|
| **ARCHITECTURE_BLOCKER** | 4 | P5, P8, P9 |
| **IMPLEMENTATION_BLOCKER** | 4 | P4, P8 |
| **WORKFLOW_BLOCKER** | 4 | P8, P10, P13 |
| **CUSTOMER_CONFIG** | 10 | nothing — forbids constants |
| **NON_BLOCKING** | 1 | nothing |

> ### **None of these blocks P3.** The checkpoint, witness and claim CAS are loop-independent
> platform safety, which is exactly why they are next in the phase order and why the freight
> unknowns do not stall the safety wall.

**Every item's safe interim behaviour is fail-closed with a human owner.** If you find yourself
needing an answer that is not here, that is a new validation item — **add it and stop**, do not
answer it yourself.
