# Neyma — Operating Model

**Layer:** Product Vision (per `engineering-principles.md` §12.1). Governed by the Engineering Principles; constrained by the Reconciliation and the Freight Discovery.
**Status:** Draft for freeze. **This is NOT architecture, NOT implementation, NOT a PRD.**
**Contains no:** databases, services, agents, APIs, state machines, or system designs.
**Date:** 2026-07-09

> **What this document is:** a description of **how a freight brokerage actually operates**, and **where Neyma stands inside that operation**. Every future architecture must faithfully implement this model. If the architecture cannot express something here, the architecture is wrong (§12.2).

> **Honesty rule carried down:** claims about *our design partner* are marked `NEEDS VALIDATION`. Industry claims inherit their labels from `freight-discovery.md`. Nothing here invents domain knowledge.

---

## 1. MISSION

**Neyma closes the operational loops that keep a freight brokerage's money moving and stop its exceptions from falling through the cracks.**

A brokerage's work does not live in one system. It moves across a shared inbox, phone calls, text messages, PDFs, carrier portals, load boards, appointment portals, spreadsheets, an accounting package, and a TMS — and the real cost of running the business is the **human labor of carrying information between them**, all day, without dropping anything. Neyma carries it. It watches the work arrive, ties each piece to the load it belongs to, checks it against what the business already knows to be true, does the parts that are safe and repetitive, and brings a person the parts that need judgment — **with the evidence already in hand**. Its value is not measured in what it says or how clever it is. It is measured in **work that never reaches a human, cash that arrives sooner, margin that stops leaking, and exceptions that get resolved instead of discovered.** (P19, P20, P21, P24)

---

## 2. TARGET CUSTOMER

### 2.1 Ideal customer profile `HYPOTHESIS` — `NEEDS VALIDATION` against the design partner

A **small-to-medium US truckload freight brokerage** (or a brokerage-leaning 3PL) that:

| Dimension | Profile |
|---|---|
| **Size** | Small enough that the back office is done by people who also do other jobs; large enough that the back office is a **material cost**. `NEEDS VALIDATION`: the actual headcount and load volume of our partner. |
| **Operational maturity** | Has a TMS and uses it. **Runs the business out of a shared inbox.** Keeps spreadsheets for everything the TMS can't hold. Little or no EDI. **No in-house engineering, no data team, no integration budget.** |
| **Systems posture** | Cannot and will not rip out their TMS. Has already been burned by a migration, or has watched someone else be. |
| **Economics** | Margin is thin and per-load. A single unaudited carrier invoice or a two-week-late customer invoice is a **visible** hit, not a rounding error. |

### 2.2 Pain points they actually feel `CONFIRMED INDUSTRY PATTERN` (per discovery §7)

- Delivered loads sitting **unbilled** because the POD isn't in hand or nobody got to it — **cash they've earned and haven't collected**.
- **Carrier invoices paid without audit** — unauthorized accessorials, overbills, duplicates — because line-by-line checking takes time nobody has.
- **Chasing PODs** by phone and email from a party with no urgency.
- **AR aging** past terms while everyone is busy covering loads.
- **Check calls** — high-volume, low-value, interrupt-driven phone work.
- **Retyping the same data** out of email and PDFs into the TMS, forever.
- **Context switching** across a dozen systems all day. `DESIGN_PARTNER_OBSERVED` (relayed)

### 2.3 Why they adopt

1. **It doesn't ask them to change anything.** No migration, no new system of record, no retraining. It works inside the tools they already run. *(This is the industry's convergent posture — Pallet, Parade: "no rip-and-replace.")*
2. **The value is cash and margin**, which they can see in a week: money in sooner, money out correctly.
3. **It's cheaper than a hire, and it doesn't quit.** They are comparing this to a salary, not to software.
4. **It doesn't require trust up front.** It starts supervised. They watch it. Trust is earned. (P14, P25)

### 2.4 Who Neyma is explicitly **NOT** for

| Not for | Why |
|---|---|
| **Enterprise brokerages** with in-house engineering, EDI teams, and API budgets | They can integrate; they don't need an operator. Their constraint is scale, not systems chaos. |
| **Shippers** | Different business, different loops, different pain. |
| **Asset-heavy carriers** whose primary problem is fleet, drivers, maintenance, and compliance | That is a fleet-operations problem, not a brokerage back-office problem. |
| **Anyone who wants a TMS replacement** | We will never be the system of record for their loads. That is a permanent product boundary (§7). |
| **Anyone who wants full autonomy immediately** | Neyma will disappoint them by design. Money and outbound communication are gated. (P12, P14) |
| **Warehousing / WMS / yard / customs / international** | A different business entirely. |

> **The customer we are wrong for is a customer who thinks the problem is software.** The problem is **work**.

---

## 3. OPERATIONAL PHILOSOPHY

### 3.1 A brokerage is a network of loops, not a piece of software

The instinct — ours, and the industry's — is to describe a brokerage by naming its TMS. That is a **category error**. The TMS is a **ledger of some of the work**. It is not where the work happens, and it is not where most of the truth lives.

**The business is a set of operational loops.** Each loop:
- **starts** somewhere (usually a message from a human),
- **moves** across several systems that do not talk to each other,
- **is carried between them by a person**, and
- **finishes** when a specific condition is met in the real world.

**The connective tissue between systems is a human being.** That human — walking a piece of information from the inbox to the TMS to the portal to the spreadsheet and back — **is the operational cost of the business.** That labor is the target. (P19)

### 3.2 No system is authoritative for the whole

Each system is authoritative for a **slice**, and for nothing more:

| System | Authoritative for |
|---|---|
| Email / SMS / phone | **The commitments people made to each other.** |
| The TMS | Loads, invoices, and payables *of record*. |
| The rate confirmation | The agreed buy rate. |
| The POD | That delivery happened, and in what condition. |
| The facility's portal | The dock appointment. |
| Accounting / the bank | Money that actually moved. |
| FMCSA / the insurer | Whether a carrier is legally allowed to haul. |

> **There is no single source of truth in a brokerage. There is a *distributed* truth, and the operator's job is to reconcile it.** Any model that appoints one system as "the truth" will be wrong about the business. (Reconciliation §4.1 — the authority relationship remains `NEEDS VALIDATION`; this document does not resolve it.)

### 3.3 The commitment precedes the document

This is the deepest structural fact in the domain, and it must survive into every downstream design:

> **The rate is agreed on the phone before the rate confirmation exists. Detention is authorized verbally at the dock. A delay is excused in a text message. The document is the *artifact* of the commitment — not the commitment itself — and it lags it by hours or days.** `CONFIRMED INDUSTRY PATTERN` (discovery §5.2)

Therefore: **a model that can only represent what is written down will systematically misread the business** — it will flag legitimately-authorized charges as fraud, and it will believe a load is unhandled because the paperwork hasn't caught up. (P31)

### 3.4 The loop closes at value, not at action

Entering an invoice is not the goal. **Being paid** is the goal. Filing a document is not the goal. **Being able to bill** is the goal. Flagging an exception is not the goal. **The exception being resolved** is the goal.

A brokerage that "does everything" and still has aged AR and unaudited payables is a brokerage where **loops are opened and not closed**. That gap — between *action taken* and *loop closed* — **is where the money is.** (P24)

---

## 4. SOURCES OF OPERATIONAL WORK

Work enters the business from these places. **Any model of the front door must accept all of them.**

### 4.1 Inbound messages (the dominant source) `CONFIRMED INDUSTRY PATTERN`
- **Customer email** — quote requests, load tenders, status questions, billing disputes, appointment constraints.
- **Carrier email** — capacity offers, counter-offers, invoices, PODs, questions about payment.
- **Facility / consignee email** — appointment confirmations, rejections, lumper demands.
- **Phone calls** — negotiation, check calls, escalation, **verbal authorization** (§3.3).
- **Driver SMS** — status, photos of BOL/POD, breakdowns, detention.
- **Internal requests** — a human asking Neyma directly ("bill this," "where is that," "what do we owe").

### 4.2 Documents
Arriving as attachments, photos, scans, portal downloads. **Often handwritten, skewed, multi-page, or partially illegible.** `COMMON INDUSTRY PRACTICE`

### 4.3 System state changes
- A load becomes *delivered* in the TMS.
- A tracking feed emits a position or an ETA change.
- A portal shows an appointment moved.
- An invoice appears in accounting.

### 4.4 Time
**Time itself originates work.** An invoice crosses its terms. A COI approaches expiry. A load has been delivered for three days and still isn't billed. Nothing "happened" — and yet there is work.

### 4.5 **Non-events — the source everyone forgets** `CONFIRMED INDUSTRY PATTERN` (as pain), `INFERRED` (as a design constraint)

> **The most expensive work in a brokerage originates from things that did *not* happen.**
> The POD that never arrived. The carrier that never confirmed pickup. The customer that never paid. The appointment that was never booked. The insurance certificate that was never renewed.

A system that only reacts to events will be **structurally blind to the brokerage's largest losses**, because the losses are silent. **Absence must be a first-class trigger** — and this is exactly the principle that `unknown ≠ none` protects (P6, §2.3).

---

## 5. THE OPERATIONAL LOOPS

Eleven loops run a brokerage. **Nine are sequential-ish; two are cross-cutting and never stop.**

> No software is designed here. These are descriptions of *the business*.

---

### L1 — QUOTE
- **Objective:** turn a customer's request into a priced offer that wins the freight without giving away the margin.
- **Trigger:** a quote request arrives (email, portal, phone).
- **Completion condition:** the customer has accepted, declined, or the quote has expired — **and we know which**.
- **Human responsibility:** **deciding the sell rate.** This is commercial judgment: margin versus probability of winning. It is not arithmetic.
- **Information required:** lane, dates, equipment, commodity/weight, the customer's history and payment behavior, current market rates for the lane, whether capacity is actually available.
- **Note:** speed matters — spot quotes are frequently won by whoever answers first. `COMMON INDUSTRY PRACTICE`

### L2 — CARRIER PROCUREMENT (covering the load)
- **Objective:** find a **legitimate, insured, capable** carrier at a buy rate that preserves the margin.
- **Trigger:** a load is awarded and has no truck.
- **Completion condition:** a carrier is booked **and vetted**, the buy rate is agreed, and a rate confirmation has been issued and accepted.
- **Human responsibility:** **whether to trust this carrier** — the highest-consequence decision a broker makes (fraud, double-brokering, negligent-selection liability) — and **whether to accept a counter-offer** (live margin math under time pressure).
- **Information required:** load details, margin floor, carrier candidates and their history, authority/insurance/safety status, fraud signals, market rate.

### L3 — CARRIER COMPLIANCE *(continuous; gates L2)*
- **Objective:** ensure every carrier we tender to is **currently** authorized and insured — not merely that they once were.
- **Trigger:** onboarding a carrier; **and again on every load**; and on expiry of any document. `CONFIRMED INDUSTRY PATTERN` (discovery §14, #8)
- **Completion condition:** authority active, insurance valid and adequate, agreement signed, packet complete — **as of today**.
- **Human responsibility:** the decision to approve or suspend a carrier.
- **Information required:** MC/DOT, authority status, COI + expiry, safety scores, signed agreement, W-9, fraud/identity signals.

### L4 — DISPATCH & APPOINTMENTS
- **Objective:** set the load up so it cannot fail at the dock.
- **Trigger:** carrier booked.
- **Completion condition:** pickup and delivery appointments secured (where required), the carrier and driver have every instruction they need, and the load is dispatched.
- **Human responsibility:** negotiating with a difficult facility; deciding what to do when no slot exists in the window.
- **Information required:** stop windows, facility rules and quirks (**tribal knowledge**), portal access, special instructions, driver/equipment details.

### L5 — TRACKING
- **Objective:** know where the freight is and whether it will be on time — **before the customer asks**.
- **Trigger:** load dispatched. Runs continuously until delivered.
- **Completion condition:** delivery confirmed.
- **Human responsibility:** deciding **what to tell the customer when it's going wrong** (relationship risk).
- **Information required:** carrier/driver contact, any visibility/ELD feed, appointment windows, current position/ETA, HOS constraints.
- **Note:** many small carriers are **not** on a visibility platform. Tracking often means **asking a human**. `CONFIRMED INDUSTRY PATTERN`

### L6 — DOCUMENTATION
- **Objective:** assemble the **complete, legible, correctly-bound** document packet for the load.
- **Trigger:** a document arrives — **or a document is expected and has not arrived** (§4.5).
- **Completion condition:** every document this load requires exists, is readable, is bound to the **right** load, and is filed where the business keeps it.
- **Human responsibility:** judging an illegible or ambiguous document; deciding a document is "good enough"; resolving a binding the system could not.
- **Information required:** **what this load requires** (varies by customer — tribal knowledge), what exists, what is missing, and how long it has been missing.
- **Note:** this loop **gates the money.** Nothing downstream moves without it.

### L7 — EXCEPTION RESOLUTION *(cross-cutting; never stops)*
- **Objective:** catch what is about to go wrong and resolve it **before** it costs money or a customer.
- **Trigger:** any deviation — an invoice that doesn't match, a document that never came, a delay, a detention, a short-pay, an OS&D, a lapsed insurance certificate, a suspected fraud signal.
- **Completion condition:** **the exception is resolved, or a human has decided and the decision is recorded.** An exception that is "closed" without a decision is not closed — it is forgotten.
- **Human responsibility:** **nearly all of the judgment in the business lives in this loop.**
- **Information required:** the deviation, the evidence, the history, and **who has authority to decide**.

### L8 — BILLING (Accounts Receivable) — *through cash collected*
- **Objective:** turn a delivered load into **collected cash**, as fast as possible.
- **Trigger:** the load is delivered **and** the required documents exist.
- **Completion condition:** **payment received and applied.** *Not* "invoice sent."
- **Human responsibility:** releasing the invoice; deciding how to respond to a short-pay or a dispute; deciding whether to keep hauling for a slow payer.
- **Information required:** the agreed sell rate, accessorials **and their authorization**, the POD, and **the customer's specific billing requirements** (tribal knowledge — e.g. "will short-pay without the lumper receipt attached").
- **Note:** the industry habitually treats *invoicing* as the end of this loop. **That is precisely why AR ages.** (P24)

### L9 — SETTLEMENT (Accounts Payable)
- **Objective:** pay the carrier **what is owed — no more, no less** — with every line authorized and evidenced.
- **Trigger:** a carrier invoice arrives.
- **Completion condition:** the payable is approved and paid, **or** a dispute is opened and tracked to a decision.
- **Human responsibility:** approving payment; deciding a disputed line; **retroactively confirming an authorization that was given verbally** (§3.3).
- **Information required:** the rate confirmation, the POD/BOL, **accessorial authorizations including the ones that exist in no document**, backup receipts, a duplicate check, payment terms, and whether the carrier factors (which changes *who* gets paid).
- **Note:** this is the **margin guard**. It is also legally anchored — brokers must keep a transaction record per shipment (49 CFR §371.3). `CONFIRMED INDUSTRY PATTERN`

### L10 — CUSTOMER COMMUNICATION *(cross-cutting; never stops)*
- **Objective:** keep the customer informed and confident — **especially when something is wrong**.
- **Trigger:** a status change, a delay, an exception, a question, or a promised cadence.
- **Completion condition:** the customer has what they need and **no one is waiting on us**.
- **Human responsibility:** **what to say when the news is bad.** Wording carries relationship risk that can exceed the dollar value of the load.
- **Information required:** the current truth about the load, what we have already told them, and what this customer expects.

### L11 — CLAIMS (OS&D)
- **Objective:** recover the value of freight that was lost, short, or damaged.
- **Trigger:** an OS&D notation on the POD, or a customer report.
- **Completion condition:** the claim is filed, pursued, and settled or denied — **with a decision recorded**.
- **Human responsibility:** whether to file, against whom, and how hard to push. Legal and insurance judgment.
- **Information required:** the BOL, the POD **with its notations**, photos, the carrier's insurance, the value of the freight, the timeline.

---

## 6. NEYMA'S RESPONSIBILITY IN EACH LOOP

Five verbs, applied consistently. **They are ordered by increasing consequence, and Neyma's licence decreases as consequence rises.**

| Verb | Meaning |
|---|---|
| **Observe** | See the work arrive, bind it to the right load, and know its state. **Neyma does this everywhere, always, without asking.** |
| **Assist** | Prepare, gather, draft, compare, and surface — so a human's decision costs seconds instead of minutes. |
| **Execute** | Perform the action in the real system. |
| **Verify** | Read the result back and confirm it actually happened. **Neyma does this for everything it executes, without exception.** (P5) |
| **Escalate** | Hand a human the decision, **with the evidence already assembled**. (§2.8) |

### 6.1 The responsibility matrix

| Loop | Observe | Assist | Execute | Verify | **Remains human** |
|---|---|---|---|---|---|
| **L1 Quote** | ✅ all requests | ✅ pull lane history, market rate, capacity; draft the reply | ⚠️ send the quote **only on approval** | ✅ confirm it sent, track the outcome | **The sell rate. Always.** |
| **L2 Procurement** | ✅ carrier offers, counter-offers | ✅ surface vetted candidates, compute margin at each offer | ⚠️ issue the rate con **only on approval** | ✅ confirm the carrier accepted | **Whether to trust the carrier. Whether to accept the rate.** |
| **L3 Compliance** | ✅ authority, insurance, expiries — continuously | ✅ flag lapses and fraud signals **before** the load is tendered | ✅ collect and file the packet | ✅ confirm documents on file and current | **Approving or suspending a carrier.** |
| **L4 Dispatch** | ✅ appointment needs and windows | ✅ find available slots, prepare the booking | ⚠️ book the appointment (graduating) | ✅ confirm the slot is really booked | **Fighting a facility. Choosing among bad options.** |
| **L5 Tracking** | ✅ feeds, replies, ETAs | ✅ detect the delay early; draft the customer notice | ✅ ask the carrier for status; update the record | ✅ confirm status is current | **What to tell the customer when it's bad.** |
| **L6 Documentation** | ✅ every document, **and every one that hasn't arrived** | ✅ read it, bind it, tell us what's missing and for how long | ✅ file it; **chase it** (draft → approve → send) | ✅ confirm it is on file, on the **right** load | **Illegible/ambiguous documents. Any binding it can't confirm.** |
| **L7 Exceptions** | ✅ **this is Neyma's core job** — catch everything | ✅ assemble the evidence and propose the resolution | ⚠️ only the resolution actions it is licensed for | ✅ confirm the exception is actually closed | **The decision. Nearly always.** |
| **L8 Billing** | ✅ delivered-and-billable; aging; short-pays | ✅ prepare the invoice from the record; rank the collections | ⚠️ raise the invoice **on approval**; record payments | ✅ read back the invoice and the balance | **Releasing the invoice. Dispute strategy. Credit decisions.** |
| **L9 Settlement** | ✅ every carrier invoice | ✅ **reconcile line-by-line; flag the delta with evidence** | ⚠️ record the payable **only on approval** | ✅ read back the payable | **Approving payment. Every disputed line. Confirming a verbal authorization.** |
| **L10 Customer comms** | ✅ what's been said, what's owed a reply | ✅ **draft everything** | ❌ **never sends unapproved** (initially) | ✅ confirm delivery | **The words, when it matters.** |
| **L11 Claims** | ✅ OS&D notations on PODs | ✅ assemble the packet and the timeline | ❌ does not file claims | — | **Everything. This is legal judgment.** |

**Legend:** ✅ Neyma · ⚠️ Neyma, **gated by human approval** · ❌ Neyma does not do this

### 6.2 The rule underneath the matrix

> **Neyma observes everything. Neyma assists everywhere. Neyma executes only what is bounded, evidenced, and licensed. Neyma verifies everything it executes. Neyma escalates every judgment — and never escalates without the evidence.**

**Neyma never exercises commercial judgment.** The sell rate, the decision to trust a carrier, the words used when the news is bad, whether to file a claim — **these are the business, and they belong to the people who own it.** (P12, §2.8)

---

## 7. PRODUCT BOUNDARIES

### 7.1 What Neyma owns
- **Its own operational model of the work** — the correlation between artifacts, loads, parties, and actions across systems. *(Nothing else holds this today. Whether it is ever* authoritative *is deliberately unresolved — Reconciliation §4.1, `NEEDS VALIDATION`.)*
- **The audit trail of everything it did**, with provenance. (P7)
- **The exception state** — what is open, what is aging, what needs a human.
- **Its learned knowledge** — the company's rules, and every correction a human has given it. (§2.4)
- **Its own autonomy policy** — what it has earned the right to do. (P14)

### 7.2 What Neyma **never** owns
| It never owns | It belongs to |
|---|---|
| **The commercial relationship** with a customer or carrier | The business's people |
| **The sell rate** and the decision to trust a carrier | The humans who bear the consequence |
| **Money that actually moves** | Accounting and the bank |
| **The loads/invoices of record** | The TMS |
| **The conversation record** | The mail and phone providers |
| **Carrier authority and insurance** | FMCSA and the insurer |
| **The dock appointment** | The facility |
| **Legal and insurance judgment** | The humans and their counsel |
| **Accountability** | **A named human. Always.** |

> **Neyma is never the system of record for the customer's business.** That is permanent, and it is the reason they can adopt it without fear. (§2.4)

### 7.3 What Neyma may **recommend** (always, freely)
A rate benchmark · a vetted carrier candidate · a proposed resolution to an exception · the wording of any message · what to do next, and what it would cost to keep ignoring something.

**Recommendation costs nothing and risks nothing.** Neyma should be maximally useful here.

### 7.4 What Neyma may **execute**
Only actions that are **bounded** (a known operation), **evidenced** (justified by an observation), **verifiable** (we can read back the result), and **licensed** (it has earned this, within caps) — for example: reading, binding, filing a document, recording a status, entering data derived from the record, and — **once graduated and capped** — the routine, low-blast-radius, reversible operations. (P14, P5)

### 7.5 Permanent product truths — these do not change

These are **structural**. They are not policies to be tuned; they are **what Neyma is**. A change here is not a roadmap decision — **it is a different product.**

1. **Neyma is never the customer's system of record.** (§7.2)
2. **Accountability always rests with a named human.** Neyma is never the accountable party for a business decision. (§7.2)
3. **Neyma never exercises commercial judgment** — the sell rate, whom to trust, the words when it matters. (§6.2)
4. **Every action is attributable, explainable, and verifiable — and the *capability* to gate, audit, and reverse exists permanently in the architecture**, regardless of which gates are currently switched on. (P5, P7)
5. **A human brake always exists and always works.** (P14)

> **#4 is the load-bearing one, and it is the distinction that matters most in this section.**
> The architecture must **always be able** to enforce a human gate on any action — **even if, for a given customer or a given era, that gate is not switched on.**
> **Losing the capability is irreversible. Relaxing a policy is not.** Never trade the first to get the second.

### 7.6 Current product policy — the gates in force today

`PRODUCT POLICY` — **in force for the foreseeable product roadmap.** These are **evolvable, but only through a deliberate product decision with a corresponding architectural review** (Engineering Principles §11, the seven-question change process). **Never by drift. Never by convenience. Never because a customer asks nicely in the moment.**

1. **Money leaving the business requires explicit human approval.**
2. **Any figure not derived from the business's own record requires approval.** (P3)
3. **Outbound communication to a customer or carrier requires approval** — unless a specific, low-risk template has explicitly earned graduation. **Bad news is never sent unapproved.**
4. **Trusting a carrier for the first time requires approval.**
5. **Irreversible actions require approval.** (P12, §4.5)
6. **Anything above the owner's caps, or where the evidence is incomplete, requires approval.** (P6, P14)

> **Why these are policy and not truth.** It is entirely conceivable that a mature Neyma — operating at volume, with a long reliability record and strict controls — is asked by a customer to release routine carrier payments autonomously within tight caps. **A foundational document must not make that impossible. It must make it *deliberate*.**
>
> What is **permanent** is that the gate *can* be enforced, that every action is attributable and explainable, and that a human is accountable (§7.5).
> What is **policy** is *which* gate is currently closed.
>
> **The failure mode this guards against is not evolution. It is erosion** — a policy quietly relaxed under commercial pressure, one exception at a time, with nobody ever having decided. (P25, §11 of the Principles)

---

## 8. SUCCESS METRICS

### 8.1 The metrics that matter

**Cash (the reason they hire us)**
- **Delivered → invoiced latency.** Days from delivery to invoice out.
- **Invoiced → paid latency.** Days from invoice to cash applied.
- **Dollars of AR aged past terms.** Should trend down.

**Margin (the reason they keep us)**
- **Dollars of incorrect carrier charges caught before payment** — unauthorized accessorials, overbills, duplicates.
- **Dollars paid in error.** Should be **zero**.

**Work (the reason it's cheaper than a hire)**
- **Work removed:** units of work that **never reached a human at all**.
- **Human touches per load.** Should fall.
- **Document turnaround:** delivered → POD on file.

**Loop closure (the honest one)** (P24)
- **Loop closure rate:** loops opened vs. loops actually **closed**.
- **Exception resolution time**, and **exception age** (how long the oldest open one has sat).
- **Loops closed with no human involvement**, as a share of total.

**Trust (the one that decides whether we survive)** (P25)
- **Wrong actions taken.** Must trend to **zero** and be treated as a P0 every time.
- **Escalation precision:** what share of escalations were genuinely necessary. *Escalating everything is the same failure as escalating nothing.* (§2.8)
- **Repeat corrections:** how often a human corrects the **same** thing twice. **A repeat correction means we did not learn — and that is a defect, not a metric.** (§2.4)
- **Approval latency:** how long a human sits on an approval. *(If it's long, we're asking wrong.)*

**Integrity (non-negotiable, and therefore a pass/fail, not a trend)**
- **Provenance completeness: 100%.** Any action without full provenance is a defect. (P7)
- **Silent failures: 0.** Any action that failed and was not surfaced is a P0. (P6, R17)

### 8.2 Metrics we explicitly reject as vanity
Messages sent · AI calls made · tasks "processed" · documents "touched" · automation percentage · engagement · time in app · dashboards viewed.

> **Every one of these can go up while the business gets worse.** Engagement is an **anti-metric**: a teammate you have to keep visiting has not done its job. (P20)

---

## 9. FUTURE EXPANSION

### 9.1 The law of expansion
> **Start with one loop. Close it completely. Make it boring. Only then take the next one.**

**Expansion is earned, not scheduled.** (P14, P25)

### 9.2 What "earned" means, concretely
A loop is **not** ready to be joined by a new one until:
1. It **closes** end-to-end, live, on real operations — not in a test. (P17)
2. It is **boring** — it runs for a sustained period without surprising anyone.
3. Its **escalations are precise** — the human is not rubber-stamping, and not being spammed.
4. Its **wrong-action count is zero**, and stays there.

### 9.3 What expansion is allowed to mean
Exactly two things:
- **Deeper autonomy inside a loop we already run** — the same work, with a longer leash and the same caps and brake. (P14)
- **A new loop that rides the same spine** — the same observe → bind → check → do-or-ask → verify → record discipline, pointed at new work. (P38)

### 9.4 What expansion may never mean `REFUSED`
- **A disconnected feature** that doesn't close a loop, because it demos well. (P21, P36)
- **A new spine.** If a new loop requires changing the core, the core is wrong — fix the core. (P38)
- **A second way to do something we already do.** (P18, R14)
- **Widening scope to hide that the current loop isn't closing.** *(This is the most seductive failure mode available to us, and it should be named as such.)*

### 9.5 How the next loop is chosen
Four gates, in order. A loop may only be taken up when it passes all four:

| Gate | Question |
|---|---|
| **1. Pain** | Does this cost the owner real money or real hours, today? |
| **2. Truth** | Is there something we can **check against**? A loop with no source of truth is a loop where we would be guessing. (P4) |
| **3. Surface** | Can we actually observe the inputs and perform the actions — or is the system a black box to us? |
| **4. Blast radius** | If we get it wrong, how bad is it — and can it be undone? (§4.5) |

> `HYPOTHESIS` — **The evidence points at the Documentation → Billing chain (L6 → L8) as the first loop**: the pain is acute and immediate (cash), the truth is checkable (the document either exists or it does not), the surface is reachable, and the blast radius is bounded and reversible. **This is not yet a decision.** It must be validated against the design partner's actual pain (`NEEDS VALIDATION`, discovery §13).

### 9.6 The end state
Every loop in §5, closed by Neyma, supervised from wherever the owner already works — with the business's people spending their day on the **four or five decisions that genuinely require a human**, and none of the hundreds of movements of information between systems that currently fill it.

> **We will know we have succeeded when the owner checks because they *want* visibility — not because they *need* to verify our work.**

Verification will never disappear entirely, and it **should not**. An owner will always want to look at their money and their customer relationships, and they are right to. **The goal is not to remove their oversight. It is to change its nature** — from an anxious duty performed because the work might be wrong, to a chosen glance at work they already trust is right.

---

## 10. OPERATIONAL INVARIANTS

**These are always true of Neyma's operation** — in every loop, for every customer, in every era.

They sit **between** the Engineering Principles (which govern *how we build*) and product policy (which governs *what is switched on today*). Unlike policy (§7.6), **invariants do not evolve.** Unlike principles, they are specific to the operation of this system.

> **An invariant is not an aspiration. If a design can violate one, the design is wrong.** These are the properties a reviewer checks any future architecture against.

| # | Invariant | What breaks without it |
|---|---|---|
| **I1** | **Every unit of work has an accountable human owner.** At any moment someone is responsible for it, and the system knows who. | Work with no owner rots silently. *"The system was handling it"* is how loops die unnoticed. |
| **I2** | **Every operational action is attributable.** Who or what did it — human or agent — is recorded, always. | An unattributable action cannot be defended, corrected, or learned from. (P7) |
| **I3** | **Every financial action is explainable.** We can say *why* this amount, to this party, on this evidence — **in plain language, to a person who is angry.** | Money you cannot explain is money you cannot defend. (P7, P15) |
| **I4** | **Every state transition is reconstructable.** We can show how a thing got from where it was to where it is. | Without it there is no debugging, no audit, and no trust. (P9, P10) |
| **I5** | **Every document preserves its provenance.** Where it came from, when, from whom, what it was bound to, and why. | A document with no lineage cannot settle a dispute — **which is the only reason it exists.** (P15) |
| **I6** | **Every decision is reproducible from the evidence available *at the time*** — not from what we know now. | Judging a past decision by present knowledge is hindsight, not audit. A system that cannot show **what it knew then** can be neither fairly evaluated nor fairly improved. |
| **I7** | **`Unknown` is a valid, first-class state.** Not an error, not a default, not a zero. | The most dangerous failure we have shipped. **"I could not see" must never render as "there is nothing there."** (P6, R10) |
| **I8** | **Missing evidence and contradictory evidence are different states, handled differently.** *Absent* ≠ *present-and-consistent* ≠ *present-and-conflicting*. | Treating a **conflict as an absence** hides a real problem. Treating an **absence as a conflict** manufactures a false one. **Both are wrong, in opposite directions, and both move money.** |
| **I9** | **Every loop has a deterministic completion condition** — knowable, checkable, and not a matter of opinion. | A loop with a fuzzy ending never ends. It stays "in progress" forever, which is indistinguishable from failure. (P24) |
| **I10** | **No action is both taken and unrecorded.** If it happened in the world, it exists as an event. | An unrecorded effect is an effect nobody can reverse. (P7, §2.2) |
| **I11** | **Loop closure is an event, never an inference.** A loop is closed because something closed it — **not because nothing has happened lately.** | Silence is not success. (P6, I7) |
| **I12** | **Every escalation carries its evidence.** A human is never asked to decide blind. | An evidence-free escalation trains the human to rubber-stamp — **which is worse than not escalating at all.** (§2.8) |

> **I8 deserves particular attention: it names a third state the system has never had.** Until now we have reasoned in two states — *we saw it* and *we didn't*. But a document that **contradicts** the record is a fundamentally different situation from a document that is **missing**, and they demand opposite responses. Collapsing them is a class of bug we have not yet written, precisely because we lacked the vocabulary to see it.

---

## 11. WHAT THIS DOCUMENT BINDS

Per §12.2 of the Engineering Principles, **the architecture that follows must faithfully implement this model.** Specifically, it must be able to express, without contortion:

1. **Work that originates from a non-event** (§4.5) — an absence must be able to start a loop.
2. **A commitment that has no document** (§3.3, P31) — an authorization that exists only in a conversation.
3. **A distributed truth** (§3.2) — no single system appointed as *the* source.
4. **A loop that is open but not closed** (§3.4, P24) — and the ability to report honestly on the gap.
5. **Escalation with evidence attached** (§6.2, I12) — a human never asked to decide blind.
6. **A gate on any action, enforceable permanently** (§7.5) — **whether or not a given policy currently closes it** (§7.6).
7. **Identity binding as a first-class, evidenced, escalatable decision** (P32).
8. **Three-state evidence** — absent, consistent, contradictory — as distinct, differently-handled states (I8).
9. **An accountable human owner for every unit of work, at every moment** (I1).
10. **Every invariant in §10, without exception.**

**If the architecture cannot express these, the architecture is wrong — not this document.**
