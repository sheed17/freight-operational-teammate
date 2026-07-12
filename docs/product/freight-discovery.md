# Freight Discovery — How Brokerages Actually Operate

**Status:** Research and knowledge-gathering. **This is NOT architecture, NOT a specification, NOT an implementation plan.** No agents, services, systems, or Neyma designs are proposed anywhere in this document.
**Date:** 2026-07-09
**Purpose:** establish the strongest possible factual foundation *before* architecture begins.

---

## 0. HOW TO READ THIS DOCUMENT

### 0.1 Classification labels (every operational pattern carries exactly one)

| Label | Meaning | Maps to |
|---|---|---|
| **`CONFIRMED INDUSTRY PATTERN`** | Structural to how brokerage works. Regulatory, contractual, or universal. Would be true at essentially any US truckload brokerage. | KNOWN |
| **`COMMON INDUSTRY PRACTICE`** | Widespread and well-documented, but a choice — a brokerage could operate differently. | COMMON PRACTICE |
| **`VENDOR-SPECIFIC APPROACH`** | How a particular product/company does it. Evidence of what is possible, **not** evidence of what our customer does. | — |
| **`SPECULATION`** | My inference. Plausible, unverified. Must not be treated as fact. | HYPOTHESIS |
| **`NEEDS VALIDATION`** | Unknown. Requires field data from our design partner. | NEEDS VALIDATION |

### 0.2 The controlling caveat (carried forward from the reconciliation)

> **I have not observed our design partner. Rasheed has.** Nothing in this document describes *our customer* unless explicitly sourced from Rasheed's report. Industry patterns ≠ our partner's reality. **Section 13 exists precisely because the gap between them is where architecture goes wrong.**

---

## 1. CURRENT UNDERSTANDING OF FREIGHT BROKERAGE OPERATIONS

### 1.1 What a broker actually is `CONFIRMED INDUSTRY PATTERN`

A freight broker is a **licensed intermediary** that arranges transportation between a shipper and a motor carrier **without owning trucks or taking possession of the freight**. The broker's product is **capacity + coordination + risk absorption**. Its revenue is the **spread** between what the customer pays (sell rate) and what the carrier is paid (buy rate).

Regulatory consequences that shape every operational decision:
- Brokers must hold **FMCSA broker authority** and a **surety bond (BMC-84, $75,000)**. `CONFIRMED INDUSTRY PATTERN`
- Brokers are required to keep a **transaction record for each shipment** — **49 CFR §371.3** — and this record is what invoice reconciliation is legally anchored to. ([source](https://invoicedataextraction.com/blog/freight-broker-invoice-reconciliation)) `CONFIRMED INDUSTRY PATTERN`
- **Broker liability** for negligent carrier selection is a live and worsening exposure, which is *why* carrier vetting is not optional paperwork. ([source](https://amblogistic.us/why-freight-brokerage-risk-is-changing-fast/)) `CONFIRMED INDUSTRY PATTERN`

### 1.2 The economic shape of the business `CONFIRMED INDUSTRY PATTERN`

- **Margin is thin and per-load.** Every unbilled load, unaudited carrier invoice, unauthorized accessorial, or aged receivable is a **direct hit to net margin**, not a rounding error.
- **The broker is the bank.** The broker typically pays the carrier on shorter terms than the customer pays the broker (customer Net 30–60; carrier standard or QuickPay). The float is financed by working capital or **factoring**. ([source](https://truckstop.com/blog/freight-billing-process-for-brokers/)) `CONFIRMED INDUSTRY PATTERN`
- **Consequence:** *cash conversion speed* — how fast a delivered load becomes collected cash — is a first-order business metric, not a back-office nicety.

### 1.3 The operational reality `COMMON INDUSTRY PRACTICE`

Brokerage operations are **communication-bound, not compute-bound**. The dominant activity is moving information between systems and people that do not talk to each other: shared inboxes, phone, SMS, PDFs, portals, load boards, spreadsheets, and a TMS. This matches Rasheed's design-partner observation exactly. `DESIGN_PARTNER_OBSERVED` (relayed)

---

## 2. COMMON OPERATIONAL WORKFLOWS ACROSS BROKERAGES

Presented as the canonical load lifecycle. **This ordering is well-documented and stable across sources.** ([source](https://truckstop.com/blog/freight-billing-process-for-brokers/), [source](https://invoicedataextraction.com/blog/freight-broker-invoice-reconciliation))

| # | Workflow | Description | Label |
|---|---|---|---|
| 1 | **Quote / RFP response** | Customer requests a rate (spot or contract). Broker prices it and responds. | `CONFIRMED INDUSTRY PATTERN` |
| 2 | **Load tender / order entry** | Customer awards the load; broker enters it into the TMS. | `CONFIRMED INDUSTRY PATTERN` |
| 3 | **Carrier sourcing & vetting** | Find a truck; verify the carrier is legitimate, authorized, insured. | `CONFIRMED INDUSTRY PATTERN` |
| 4 | **Negotiation & booking** | Agree a buy rate; issue the **rate confirmation**. | `CONFIRMED INDUSTRY PATTERN` |
| 5 | **Appointment scheduling** | Secure pickup and delivery dock slots. | `CONFIRMED INDUSTRY PATTERN` (where facilities require it) |
| 6 | **Dispatch & track/trace** | Confirm pickup; monitor transit; check calls / ETA; detect delay. | `CONFIRMED INDUSTRY PATTERN` |
| 7 | **Exception handling in transit** | Breakdown, HOS exhaustion, detention, missed appointment, reconsignment. | `CONFIRMED INDUSTRY PATTERN` |
| 8 | **Delivery & document capture** | POD/signed BOL obtained; OS&D noted if present. | `CONFIRMED INDUSTRY PATTERN` |
| 9 | **Carrier invoice receipt & audit** | Carrier bills; broker reconciles pre-pay. | `CONFIRMED INDUSTRY PATTERN` |
| 10 | **Carrier settlement (AP)** | Pay the carrier per terms / QuickPay / factoring. | `CONFIRMED INDUSTRY PATTERN` |
| 11 | **Customer invoicing (AR)** | Bill the customer, typically with POD attached. | `CONFIRMED INDUSTRY PATTERN` |
| 12 | **Collections / aging** | Chase unpaid invoices; handle short-pays and disputes. | `CONFIRMED INDUSTRY PATTERN` |
| 13 | **Claims (OS&D)** | Damage/loss/shortage → claim against carrier/insurer. | `CONFIRMED INDUSTRY PATTERN` |
| 14 | **Carrier onboarding & compliance upkeep** | Packet, agreement, COI, re-verification, expiries. | `CONFIRMED INDUSTRY PATTERN` |

> **The single most important structural fact:** steps 9–12 form a **document-gated money chain**. The carrier is not paid and the customer is not billed until specific documents exist and reconcile. `CONFIRMED INDUSTRY PATTERN`

---

## 3. CORE BUSINESS ENTITIES COMMONLY FOUND

> ⚠️ **Modeling warning carried from the reconciliation:** the "load" is **not one concept**. Sources use *shipment*, *order*, *load*, *movement*, and *leg* loosely and inconsistently. **Do not collapse them.** How they relate at *our* partner is `NEEDS VALIDATION`.

### 3.1 Party entities `CONFIRMED INDUSTRY PATTERN`
- **Customer / Shipper** (the paying party — not always the physical shipper)
- **Shipper facility (origin)** and **Consignee / Receiver (destination)** — often *different legal entities from the customer*
- **Carrier** (motor carrier with MC/DOT authority)
- **Driver** (a human, usually reachable only by phone/SMS)
- **Broker staff** (dispatcher / ops / carrier sales / customer sales / controller / owner)
- **Factoring company** (carrier-side and/or broker-side)
- **Insurer** (cargo, auto liability); **Third-party claims adjuster**

### 3.2 Commercial entities `CONFIRMED INDUSTRY PATTERN`
- **Quote / bid** (with a validity window)
- **Rate** — *distinguish*: **sell rate** (customer) vs **buy rate** (carrier); **linehaul** vs **fuel surcharge** vs **accessorials**
- **Lane** (origin↔destination pair; the unit rate history is kept on)
- **Margin / spread** (per load — the business's actual product)
- **Accessorial charge** — detention, layover, lumper, TONU, reweigh, tarp, driver assist. `CONFIRMED INDUSTRY PATTERN` ([source](https://invoicedataextraction.com/blog/freight-broker-invoice-reconciliation))
- **Authorization** for an accessorial — **critically, this is a distinct concept from the *charge* itself.** `CONFIRMED INDUSTRY PATTERN`

### 3.3 Execution entities `CONFIRMED INDUSTRY PATTERN`
- **Stop** (pickup or delivery, each with its own window/appointment/paperwork)
- **Appointment** (a scheduled dock slot, often owned by the facility's portal)
- **Equipment / trailer type** (dry van 53', reefer + temp, flatbed, etc.)
- **Status / milestone** (dispatched, at shipper, loaded, in transit, at consignee, delivered)
- **Exception** (delay, detention, damage, refusal, missing document)

### 3.4 Financial entities `CONFIRMED INDUSTRY PATTERN`
- **Carrier invoice (AP)** · **Customer invoice (AR)** · **Payable / settlement** · **Payment / remittance** · **Short-pay** · **Credit memo / adjustment** · **Aging bucket** · **Claim**

### 3.5 Compliance entities `CONFIRMED INDUSTRY PATTERN`
- **MC / DOT number**, **operating authority status**, **Certificate of Insurance (COI)** with expiry, **W-9**, **signed carrier agreement**, **safety rating / CSA scores**

### 3.6 The entity nobody models but everybody depends on
- **Communication** — the email thread, the phone call, the text message. `CONFIRMED INDUSTRY PATTERN` that this is where authorization, agreement, and dispute evidence actually live. `SPECULATION`: most small brokerages have **no structured record of it** beyond the mailbox itself.

---

## 4. TYPICAL DOCUMENT LIFECYCLE

### 4.1 The four documents that must reconcile `CONFIRMED INDUSTRY PATTERN`
Sources are unusually consistent here: **every load generates four core documents that must reconcile before invoicing and payment** — the **rate confirmation**, the **BOL**, the **POD**, and the **carrier invoice**. Accessorial backup (lumper receipts, scale tickets, detention logs) attaches to that stack. ([source](https://www.laneproof.com/blog/billing-disputes-freight-documents-that-win))

| Document | Created by | Function | Gates |
|---|---|---|---|
| **Rate confirmation** | Broker → carrier | The **binding commercial agreement** on the buy rate. | Everything downstream is audited *against* it. |
| **Bill of Lading (BOL)** | Shipper (signed at origin) | Contract of carriage; describes the freight. | Establishes what was tendered. |
| **Proof of Delivery (POD)** | Consignee (signed at destination) | Proves delivery occurred, and in what condition. | **Gates customer invoicing.** Carries **OS&D** notations. |
| **Carrier invoice** | Carrier → broker | The carrier's claim for payment. | Gates carrier settlement. |
| **Accessorial backup** | Varies (lumper receipt, scale ticket) | Substantiates an extra charge. | Gates paying that charge. |

### 4.2 The lifecycle `CONFIRMED INDUSTRY PATTERN`
`rate con issued → BOL signed at pickup → POD signed at delivery → carrier submits invoice + POD + backup → broker reconciles (pre-pay) → carrier paid → customer invoiced (POD usually attached) → customer pays`

### 4.3 The reconciliation itself `CONFIRMED INDUSTRY PATTERN`
Brokers match **field by field**: load number / PRO, lane, **linehaul**, **fuel surcharge**, **detention**, **lumper**, accessorial totals — against the rate con, and validate each accessorial against **BOL/POD evidence**. ([source](https://invoicedataextraction.com/blog/freight-broker-invoice-reconciliation))

> **The deepest insight in this section:** reconciliation is not "does the invoice match the rate con." It is **"is each line item authorized, and is there evidence for it."** Authorization frequently occurred **in a channel that is not a document** — a phone call approving detention, a text approving a lumper. `CONFIRMED INDUSTRY PATTERN` that this happens; `NEEDS VALIDATION` how our partner records it.

### 4.4 Document capture reality `COMMON INDUSTRY PRACTICE`
Documents arrive as **email attachments, phone photos, faxes, portal downloads, and scans** — frequently skewed, handwritten, multi-page, or partially illegible. Pallet explicitly advertises handling *"any format including BOL, POD, ASN, and packing lists with support for handwriting and multi-page tables"* — `VENDOR-SPECIFIC APPROACH`, but it is strong evidence that **handwriting and layout chaos are the norm, not the exception**. ([source](https://www.pallet.com/operations/brokerages))

### 4.5 Document chasing `CONFIRMED INDUSTRY PATTERN`
**PODs must be chased.** Carriers are slow to send them; the broker cannot invoice without them; cash is stuck until they arrive. Pallet lists *"Retrieve PODs from carriers"* as a distinct product workflow — `VENDOR-SPECIFIC APPROACH` confirming that POD retrieval is a recognized, discrete operational job. ([source](https://www.pallet.com/operations/brokerages))

---

## 5. TYPICAL COMMUNICATION LIFECYCLE

### 5.1 Channels and what actually flows through each `CONFIRMED INDUSTRY PATTERN`

| Channel | Direction | Typical payload |
|---|---|---|
| **Shared email inbox** | in + out | Quote requests, tenders, rate cons, carrier offers, PODs, invoices, appointment confirmations, disputes |
| **Phone** | in + out | Carrier negotiation, check calls, facility coordination, escalation, **verbal accessorial authorization** |
| **SMS / text** | in + out | Driver status, photos of BOL/POD, ETA, breakdown |
| **Load board (DAT/Truckstop)** | out (post) / in (inquiries) | Load posting, capacity search, inbound carrier calls/emails |
| **Carrier portal / visibility platform** | in | Tracking pings, status |
| **Appointment portal** | out | Dock slot booking/confirmation |
| **Customer portal (EDI/web)** | in + out | Tenders, status updates, invoice submission |

### 5.2 The defining property `CONFIRMED INDUSTRY PATTERN`
**Communication is where commitments are made.** The rate is *agreed* on the phone or by email **before** the rate con exists. Detention is *approved* verbally. A delay is *excused* in a text. **The document is the artifact of the commitment, not the commitment itself** — and often lags it by hours.

### 5.3 Inbound volume shape `COMMON INDUSTRY PRACTICE` / `SPECULATION`
A shared brokerage inbox carries a **mixture**, of which documents-attached-to-a-known-load are only a portion. `SPECULATION`: the majority of inbound messages are *conversation* (quote requests, carrier offers, status pings, appointment confirmations, disputes) rather than document deliveries. **Volume ratios are `NEEDS VALIDATION` and should not be guessed.**

### 5.4 Vendor evidence that comms are the automation target
- Parade's **CoDriver** automates **inbound carrier calls and emails** — qualifying the carrier, extracting availability and pricing, logging quotes; they report **40% reduction in phone call volume** and **90% improvement in carrier response times**. `VENDOR-SPECIFIC APPROACH` ([source](https://www.parade.ai/resources/the-industry-s-first-voice-ai-for-capacity-management-revolutionizing-how-freight-brokers-communicate))
- Visibility platforms are explicitly positioned to **"replace the 'where's my truck' phone call."** `VENDOR-SPECIFIC APPROACH` ([source](https://ustechautomations.com/resources/blog/project44-vs-fourkites-2026))

> **Interpretation (`SPECULATION`):** the industry's automation frontier is converging on **the communication layer**, not the TMS. Multiple vendors independently target inbound email/phone as the bottleneck.

---

## 6. COMMON INTEGRATIONS

### 6.1 The systems a brokerage typically touches

| Category | Examples | Integration reality | Label |
|---|---|---|---|
| **TMS** | McLeod PowerBroker, Descartes Aljex, Turvo, Rose Rocket, Tai, TruckingOffice | The operational system of record for loads/invoices. Varies enormously in API maturity. | `CONFIRMED INDUSTRY PATTERN` |
| **Load boards** | **DAT**, **Truckstop** | **Real APIs exist.** DAT exposes Load Board, BookNow, Tracking, and Freight Posting APIs via `developer.dat.com`; production access carries setup fees (~$500–$1,000 reported). | `CONFIRMED INDUSTRY PATTERN` ([source](https://www.dat.com/api-integration)) |
| **Visibility / tracking** | project44, FourKites, Macropoint, Motive/Samsara/Omnitracs (ELD) | GPS/ELD pings, often 5–15 min. Requires carrier consent/enrollment. | `CONFIRMED INDUSTRY PATTERN` ([source](https://www.trychain.com/blog/best-real-time-freight-visibility-platforms-in-2025)) |
| **Appointment portals** | **Opendock**, retailer-specific portals | Carrier/broker **self-service** booking of dock slots against facility-defined capacity rules. | `CONFIRMED INDUSTRY PATTERN` ([source](https://opendock.com/en/)) |
| **Carrier vetting** | FMCSA **SAFER**, Carrier411, CarrierCheck, RMIS/MyCarrierPackets | Authority status, insurance, safety scores. | `CONFIRMED INDUSTRY PATTERN` ([source](https://carrierchk.com/blog/freight-broker-carrier-vetting-guide)) |
| **Accounting** | QuickBooks, NetSuite, Sage | Where money actually settles. | `COMMON INDUSTRY PRACTICE` |
| **Factoring** | Carrier-side factors; broker-side lines | Affects *who* gets paid and where remittance goes. | `COMMON INDUSTRY PRACTICE` |
| **Email / calendar** | Outlook / Microsoft 365, Google Workspace | **The de facto operational hub.** | `CONFIRMED INDUSTRY PATTERN` |
| **Spreadsheets** | Excel / Google Sheets | The shadow system for everything the TMS can't hold. | `COMMON INDUSTRY PRACTICE` |
| **EDI** | 204 (tender), 214 (status), 210 (invoice), 990 (accept/decline) | Standard with larger shippers; often absent at small brokerages. | `CONFIRMED INDUSTRY PATTERN` (that the standard exists) / `NEEDS VALIDATION` (whether our partner uses it) |

### 6.2 Critical integration truth `CONFIRMED INDUSTRY PATTERN`
**Integration availability is bimodal.** Load boards and visibility platforms have real APIs. **Facility portals, many carrier portals, small-TMS instances, and customer portals frequently do not** — they are human-operated web UIs, and that is precisely why browser-driven operation and email remain necessary.

### 6.3 The vendor consensus on posture `VENDOR-SPECIFIC APPROACH`
Pallet: *"Plug Pallet into the tools you already use… **No rip-and-replace**"*, integrating with McLeod and DAT and working through **"email and portals."** Parade integrates into **McLeod PowerBroker, Descartes Aljex, Tai, Turvo**. ([source](https://www.pallet.com/operations/brokerages), [source](https://www.parade.ai/resources/the-industry-s-first-voice-ai-for-capacity-management-revolutionizing-how-freight-brokers-communicate))

> **Interpretation (`SPECULATION`):** every serious vendor in this space has independently concluded that **you do not replace the brokerage's systems — you operate across them.** That is a strong convergent signal, not proof.

---

## 7. COMMON OPERATIONAL BOTTLENECKS

| Bottleneck | Why it bites | Label |
|---|---|---|
| **POD retrieval** | Cash is frozen until the POD arrives; the broker depends on a party (carrier/driver) with no urgency. | `CONFIRMED INDUSTRY PATTERN` |
| **Carrier invoice auditing** | Line-by-line matching is slow; skipping it silently leaks margin. | `CONFIRMED INDUSTRY PATTERN` ([source](https://www.laneproof.com/blog/invoice-reconciliation-software-freight-overbilling)) |
| **Manual data entry** | Details are re-typed from email/PDF into the TMS repeatedly. | `CONFIRMED INDUSTRY PATTERN` |
| **Quote response latency** | Spot quotes are frequently won by whoever responds first. | `COMMON INDUSTRY PRACTICE` |
| **Check calls** | High-volume, low-value, interrupt-driven phone work. | `CONFIRMED INDUSTRY PATTERN` |
| **Appointment scheduling** | Requires portal/phone work against facility rules; a missed slot can unravel the load. | `CONFIRMED INDUSTRY PATTERN` |
| **Carrier vetting** | Must be done *per load*, not just at onboarding, because authority/insurance lapse. | `CONFIRMED INDUSTRY PATTERN` |
| **AR collections** | Nobody owns the aging column while everyone covers loads. | `CONFIRMED INDUSTRY PATTERN` |
| **Context switching** | Staff move between inbox, TMS, portals, boards, spreadsheets continuously. | `DESIGN_PARTNER_OBSERVED` (relayed) + `COMMON INDUSTRY PRACTICE` |

---

## 8. COMMON HUMAN DECISION POINTS

These are the moments where judgment (not data entry) is exercised. **This list matters more than any other for scoping automation.**

| Decision | Nature | Label |
|---|---|---|
| **What to quote** (the sell rate) | Commercial judgment; margin vs win probability. | `CONFIRMED INDUSTRY PATTERN` |
| **Whether to accept a counter-offer** (the buy rate) | Live margin math under time pressure. | `CONFIRMED INDUSTRY PATTERN` |
| **Whether to trust a carrier** | Risk / fraud judgment. Highest-consequence decision a broker makes. | `CONFIRMED INDUSTRY PATTERN` |
| **Whether to authorize an accessorial** (detention/lumper/TONU) | Often made *in the moment*, verbally, under pressure. | `CONFIRMED INDUSTRY PATTERN` |
| **Whether to pay a disputed invoice line** | Margin vs carrier relationship. | `CONFIRMED INDUSTRY PATTERN` |
| **What to tell the customer when a load is late** | Relationship management; wording matters. | `CONFIRMED INDUSTRY PATTERN` |
| **Whether to file a claim, and against whom** | Legal/insurance judgment. | `CONFIRMED INDUSTRY PATTERN` |
| **Whether to extend credit / keep hauling for a slow payer** | Financial risk. | `COMMON INDUSTRY PRACTICE` |
| **Whether to re-cover a load after a carrier falls off** | Time-critical triage. | `CONFIRMED INDUSTRY PATTERN` |

> **Vendor corroboration:** Pallet explicitly keeps humans in this loop — *"Human logistics experts stay in the loop to catch edge cases, monitor quality, and step in when needed,"* escalating cases like damaged goods to a human supervisor. `VENDOR-SPECIFIC APPROACH` ([source](https://www.pallet.com/operations/brokerages))

---

## 9. COMMON EXCEPTION WORKFLOWS

| Exception | Typical shape | Label |
|---|---|---|
| **Missing / illegible POD** | Chase the carrier; escalate; block invoicing. | `CONFIRMED INDUSTRY PATTERN` |
| **Carrier invoice ≠ rate con** | Flag the delta; approve, short-pay, or dispute. | `CONFIRMED INDUSTRY PATTERN` |
| **Unauthorized accessorial** | Reject, or retroactively authorize if it was verbally agreed. | `CONFIRMED INDUSTRY PATTERN` |
| **Duplicate carrier invoice** | Detect and suppress before payment. | `CONFIRMED INDUSTRY PATTERN` |
| **Detention** | Log the exact minutes; substantiate; bill or absorb. | `CONFIRMED INDUSTRY PATTERN` |
| **Lumper demand at the dock** | Time-critical: driver is held until paid (often via ComCheck/EFS). | `CONFIRMED INDUSTRY PATTERN` |
| **OS&D (over/short/damaged)** | Noted on the POD → triggers a claim path. | `CONFIRMED INDUSTRY PATTERN` |
| **Carrier falls off / no-show (TONU)** | Re-cover the load immediately; possible TONU liability. | `CONFIRMED INDUSTRY PATTERN` |
| **Transit delay (breakdown / HOS / weather)** | Detect, notify customer, re-appoint if needed. | `CONFIRMED INDUSTRY PATTERN` |
| **Missed dock appointment** | Re-book; may cause a day's delay and detention. | `CONFIRMED INDUSTRY PATTERN` |
| **Customer short-pay / dispute** | Reconcile against POD and accessorial evidence; the four documents are the ammunition. | `CONFIRMED INDUSTRY PATTERN` ([source](https://www.laneproof.com/blog/billing-disputes-freight-documents-that-win)) |
| **Suspected double-brokering / fraud** | Halt payment; verify; possible law-enforcement path. | `CONFIRMED INDUSTRY PATTERN` |
| **Insurance/authority lapse mid-relationship** | Suspend the carrier; re-verify. | `CONFIRMED INDUSTRY PATTERN` |

---

## 10. COMMON APPROVAL WORKFLOWS

`CONFIRMED INDUSTRY PATTERN` that these approvals exist. **Who holds each authority, and at what dollar threshold, is `NEEDS VALIDATION` for our partner.**

| Approval | Typically gates |
|---|---|
| **Rate approval below/above a margin floor** | Whether the load can be booked at that buy rate. |
| **Carrier approval** (new carrier onto a load) | Whether we may legally/safely tender to them. |
| **Accessorial authorization** (in the moment) | Whether the charge will be honored later. |
| **Carrier invoice approval for payment** | Release of AP. |
| **Short-pay / dispute decision** | Whether to pay less than billed. |
| **Customer invoice release** | Whether the AR goes out (typically POD-gated). |
| **Credit / payment-terms exception** | Whether to keep hauling for a slow payer. |
| **Claim filing** | Legal/insurance exposure. |
| **Outbound customer communication in a bad situation** | Relationship risk. |

> `SPECULATION`: at a small brokerage, **most of these authorities collapse into one or two people** (often the owner), and the approval is *verbal or implicit* rather than recorded. This is a hypothesis, not a finding.

---

## 11. COMMON TRIBAL KNOWLEDGE

The rules that live in people's heads and in no system. `CONFIRMED INDUSTRY PATTERN` **that this category exists and is load-bearing**; the specific contents are always company-specific.

Typical shapes:
- **Facility quirks** — "Receiver X takes 6 hours; never promise a same-day second stop." "Facility Y won't unload without an appointment confirmation number." `COMMON INDUSTRY PRACTICE`
- **Customer requirements** — "Shipper X requires a clean 53' reefer only." "Customer Y will not pay detention without a signed in/out time." `COMMON INDUSTRY PRACTICE`
- **Carrier reputation** — "This carrier is reliable but always bills detention." "Never use that MC again." `COMMON INDUSTRY PRACTICE`
- **Lane pricing intuition** — "That lane runs $2.10/mi in July." `COMMON INDUSTRY PRACTICE`
- **Billing idiosyncrasies** — "Customer Z requires the POD *and* the lumper receipt or they short-pay." `COMMON INDUSTRY PRACTICE`
- **Fraud instincts** — "A carrier that only communicates by text and won't take a call is a flag." `COMMON INDUSTRY PRACTICE`

> **Why this matters and cannot be hand-waved:** tribal knowledge is precisely the input that determines whether an automated action is *correct* rather than merely *well-formed*. **Any system that acts without it will be confidently wrong.** `SPECULATION` (but strongly held).

---

## 12. COMMON FAILURE MODES

### 12.1 Business failure modes `CONFIRMED INDUSTRY PATTERN`
- **Margin leakage** — unaudited carrier invoices; unauthorized accessorials paid; duplicate invoices paid. ([source](https://www.laneproof.com/blog/brokerage-operations-where-small-freight-brokers-lose-money))
- **Cash trapped** — delivered loads unbilled (missing POD or nobody got to it); AR aging past terms.
- **Double-brokering / freight fraud** — a carrier re-tenders the load without consent; or **identity theft**, where thieves pick up loads using **stolen MC numbers, emails, and phone numbers of legitimate operators**. ([source](https://www.fmcsa.dot.gov/mission/help/broker-and-carrier-fraud-and-identity-theft), [source](https://truckdispatchexperts.com/resources/fmcsa-rules-2026/))
- **Negligent-selection liability** — tendering to an unvetted/uninsured carrier after an accident.
- **Claims exposure** — OS&D missed on the POD, discovered too late to file.
- **Customer churn** — poor communication during an exception, more than the exception itself.

### 12.2 Automation-specific failure modes (why systems fail *here* specifically)
| Failure mode | Why it happens | Label |
|---|---|---|
| **Wrong-load binding** | An artifact (email/PDF/text) is attached to the wrong load because references are ambiguous (load# vs order# vs PRO vs BOL# vs customer ref). | `CONFIRMED INDUSTRY PATTERN` that identifiers are heterogeneous; `SPECULATION` on mis-binding frequency |
| **Silent false-negative** | A page/inbox read fails and is interpreted as "nothing to do" instead of "I couldn't see." | `SPECULATION` (but we have **repo-confirmed** history of exactly this) |
| **Acting on stale state** | The TMS changed between read and write. | `SPECULATION` |
| **Extracted-but-wrong** | A confident extraction of a mis-read number moves real money. | `CONFIRMED INDUSTRY PATTERN` that documents are hostile (handwriting, skew, multi-page) |
| **Authorization invisible to the system** | A charge *was* verbally authorized; the system flags it as fraud, or vice versa. | `CONFIRMED INDUSTRY PATTERN` |
| **Prompt injection via inbound content** | A carrier email/document containing instruction-shaped text. | `SPECULATION` (real risk class; no public freight-specific incident data found) |
| **Over-automation of a relationship moment** | An auto-sent message at the wrong time damages a customer relationship irrecoverably. | `SPECULATION` |

---

## 13. UNKNOWNS THAT REMAIN SPECIFIC TO OUR CUSTOMER

> **Everything in Sections 1–12 is *industry*. None of it is *our partner*.** These must be answered with field data before architecture. All `NEEDS VALIDATION`.

### 13.1 Shape of the business
1. Loads/day, quotes/day, carrier invoices/week, emails/day.
2. Brokerage-only, asset-based, or hybrid? Do they own trucks?
3. Freight mix — dry van / reefer / flatbed; truckload vs LTL; spot vs contract.
4. Headcount and roles; **who may approve what, at what dollar threshold**.

### 13.2 Systems truth
5. **What is their actual TMS?** (TruckingOffice was *our* test rig — is it theirs?)
6. Does their TMS have an API, and do they have access to it?
7. Which load boards, visibility platforms, appointment portals, and carrier portals do they actually log into?
8. What accounting system, and how does data reach it today?
9. **What is in their spreadsheets, and why isn't it in the TMS?** *(Still the highest-value single unknown.)*
10. Is the inbox Outlook/M365 or Google? Shared mailbox or individual? How many?

### 13.3 Process truth
11. How do loads **enter** — email tender, EDI 204, portal, phone?
12. How is a sell rate actually decided — gut, history, load board, a rule?
13. How are carriers sourced — regular list, load board, network?
14. **Where is the agreed buy rate recorded *before* the rate con exists?**
15. **How are detention/lumper/TONU authorized in the moment, and where is that recorded?** *(Determines whether reconciliation can ever be correct.)*
16. How do PODs actually arrive — carrier email, driver text photo, portal?
17. What % of carrier invoices carry a discrepancy today, and what happens?
18. Do they factor? Do their carriers factor? (Changes who gets paid.)
19. How do they vet carriers today, and per-load or per-onboarding?
20. What's their claims frequency, and who handles them?

### 13.4 The modeling question
21. **Are customer order, brokerage load, carrier movement, leg, stop, and TMS record distinct at this partner — and how do they relate (1:1, 1:N, N:M)?** *(Carried from the reconciliation. Blocks any schema.)*

### 13.5 Human truth
22. Top three pains, **in their words**.
23. What would they **never** let software do unattended?
24. What did they try before that failed, and why?

---

## 14. ARCHITECTURE ASSUMPTIONS THAT SHOULD **NOT** BE MADE WITHOUT VALIDATION

> Constraints, not design. Each of these is a plausible-sounding assumption that this research shows is **unsafe to bake in**.

| # | Do NOT assume | Why it's unsafe |
|---|---|---|
| 1 | **The TMS is the center / the system of record.** | Quotes, communications, authorizations, and appointments do not live there. `CONFIRMED INDUSTRY PATTERN` |
| 2 | **A "load" is one thing.** | Order ≠ load ≠ movement ≠ leg ≠ stop ≠ TMS row. Collapsing them corrupts the schema permanently. `CONFIRMED INDUSTRY PATTERN` |
| 3 | **The document is the source of the commitment.** | The commitment (rate, authorization) is made in conversation; the document lags it. `CONFIRMED INDUSTRY PATTERN` |
| 4 | **An email's value is its attachment.** | Most brokerage email is conversation, not document delivery. `COMMON INDUSTRY PRACTICE` |
| 5 | **Every system has an API.** | Load boards/visibility often do; facility portals, customer portals, and small TMSs often do not. `CONFIRMED INDUSTRY PATTERN` |
| 6 | **Identifiers are stable and unique.** | load# / order# / trip# / PRO / BOL# / customer ref coexist and collide. Mis-binding is the top automation risk. `CONFIRMED INDUSTRY PATTERN` |
| 7 | **Reconciliation = invoice vs rate con.** | It is *authorization + evidence* per line item; authorization may be verbal. `CONFIRMED INDUSTRY PATTERN` |
| 8 | **Carrier vetting is a one-time onboarding step.** | Authority and insurance lapse; vetting is **per-load**. `CONFIRMED INDUSTRY PATTERN` |
| 9 | **One approver / one authority level.** | Approval thresholds and roles vary; at a small shop they may collapse — but that must be *verified*, not assumed. `NEEDS VALIDATION` |
| 10 | **Documents are machine-clean.** | Handwriting, skew, multi-page, phone photos are the norm. `COMMON INDUSTRY PRACTICE` |
| 11 | **Status data is available.** | Tracking requires carrier consent/enrollment; many small carriers aren't on a visibility platform. `CONFIRMED INDUSTRY PATTERN` |
| 12 | **Silence means nothing is wrong.** | A failed read must never be interpreted as an all-clear. (Repo-confirmed: we have shipped exactly this bug.) |
| 13 | **The job ends when the TMS row is written.** | The job ends when cash is collected or the exception is closed. `CONFIRMED INDUSTRY PATTERN` |
| 14 | **Outbound comms are low-risk.** | A wrongly-worded or wrongly-timed message to a customer/carrier is a *relationship* loss, which can exceed the dollar loss. `SPECULATION` (strongly held) |
| 15 | **Fraud is an edge case.** | Identity theft and double-brokering are active, escalating, and now the subject of 2026 federal legislation. `CONFIRMED INDUSTRY PATTERN` ([source](https://www.fmcsa.dot.gov/mission/help/broker-and-carrier-fraud-and-identity-theft)) |
| 16 | **The partner resembles the industry average.** | Nothing in this document is evidence about *them*. Section 13 is the gate. |

---

## 15. THE THREE FINDINGS THAT MOST SHOULD SHAPE WHAT COMES NEXT

1. **The money chain is document-gated, and the documents are the *artifacts* of commitments made elsewhere.** `CONFIRMED INDUSTRY PATTERN`. Any model of this business must be able to represent *an authorization that has no document*.

2. **The industry's automation frontier is the communication layer, not the TMS.** Pallet, Parade, and the visibility vendors have all independently converged on email/phone/portals as the target, and all explicitly refuse to replace the incumbent systems. `SPECULATION` as interpretation; `VENDOR-SPECIFIC APPROACH` as evidence.

3. **Identity resolution is the highest-risk primitive in the entire domain.** Heterogeneous, colliding references (load# / order# / PRO / BOL# / customer ref / MC#) are the norm, and binding an artifact to the wrong load is the failure mode that quietly moves real money to the wrong place. `CONFIRMED INDUSTRY PATTERN` (that identifiers are heterogeneous).

---

## Sources

- [Pallet — AI for Freight Brokerages](https://www.pallet.com/operations/brokerages)
- [Pallet — AI Quoting for Brokers and 3PLs](https://www.pallet.com/use-cases/quoting)
- [Truckstop — Freight billing process for brokers](https://truckstop.com/blog/freight-billing-process-for-brokers/)
- [Freight Broker Invoice Reconciliation: Pre-Pay Carrier Matching (49 CFR 371.3)](https://invoicedataextraction.com/blog/freight-broker-invoice-reconciliation)
- [Laneproof — Billing Disputes in Freight: 4 Documents That Win Every Time](https://www.laneproof.com/blog/billing-disputes-freight-documents-that-win)
- [Laneproof — Invoice Reconciliation Software / Overbilling](https://www.laneproof.com/blog/invoice-reconciliation-software-freight-overbilling)
- [Laneproof — Where Small Freight Brokers Lose Money](https://www.laneproof.com/blog/brokerage-operations-where-small-freight-brokers-lose-money)
- [CarrierCheck — Freight Broker's Complete Carrier Vetting Guide 2026](https://carrierchk.com/blog/freight-broker-carrier-vetting-guide)
- [FMCSA — Broker and Carrier Fraud and Identity Theft](https://www.fmcsa.dot.gov/mission/help/broker-and-carrier-fraud-and-identity-theft)
- [Truckstop — Freight Fraud: How Brokers Can Avoid This Common Threat](https://truckstop.com/blog/freight-fraud/)
- [FMCSA Rule Changes 2026 / SAFER Transport Act](https://truckdispatchexperts.com/resources/fmcsa-rules-2026/)
- [Broker Liability, FMCSA Enforcement — why brokerage risk is changing fast](https://amblogistic.us/why-freight-brokerage-risk-is-changing-fast/)
- [DAT — API Integration](https://www.dat.com/api-integration)
- [DAT — Load Boards](https://www.dat.com/load-boards)
- [Truckstop — API Integrations Marketplace](https://marketplace.truckstop.com/t/api-integrations)
- [Parade — Voice AI for Capacity Management (CoDriver)](https://www.parade.ai/resources/the-industry-s-first-voice-ai-for-capacity-management-revolutionizing-how-freight-brokers-communicate)
- [DAT + Parade integration — automating broker-carrier communications](https://www.dat.com/company/news-events/news-releases/dat-parade-integration-automates-broker-carrier-communications)
- [project44 vs FourKites 2026](https://ustechautomations.com/resources/blog/project44-vs-fourkites-2026)
- [Best Real-Time Freight Visibility Platforms](https://www.trychain.com/blog/best-real-time-freight-visibility-platforms-in-2025)
- [Opendock — Dock Scheduling Software](https://opendock.com/en/)
- [Opendock — How Carriers Self-Schedule Deliveries](https://blog.opendock.com/self-schedule)

---

**Nothing in this document proposes architecture, agents, services, or implementation. Its only purpose is to establish what is known, what is common, what is hypothesis, and what must be validated — before any of that begins.**
