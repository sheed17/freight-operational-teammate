# Neyma — Freight Operations Capability Map

> **CANONICAL — product capability consolidation.** A freight-capability-oriented view of Neyma's
> full operational scope. **It holds NO authority independent of its sources and creates NO new
> product decision.** The **authoritative classification, phase and readiness tier** for every use
> case live in [`OPERATIONAL-USE-CASE-COVERAGE.yaml`](OPERATIONAL-USE-CASE-COVERAGE.yaml) (entries
> `UC-01…UC-33`); loops → [`operating-model.md`](operating-model.md) + [`workflows/`](../specifications/workflows/);
> phases → [`PHASE-OUTPUTS.md`](../implementation/PHASE-OUTPUTS.md); autonomy → [`AUTONOMY-MATRIX.md`](AUTONOMY-MATRIX.md)
> and [`ADR-010`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md);
> **current status → [`CURRENT.md`](../implementation/CURRENT.md).** On any conflict the cited
> source wins.

---

## How to read this map

Each capability below lists: **objective · triggers · inputs · work performed · outputs · external
systems · evidence required · common exceptions · approval boundary · current state · target phase ·
related loop · dependencies · autonomy ceiling.**

**Current state is uniform and honest:** per the coverage matrix, every freight use case is at
readiness tier **SPECIFIED** — the behaviour and acceptance contract exist, but the freight
capability is not implemented. The post-P2 work completed to date is the **safety foundation** —
the P3 checkpoint kernel (**COMPLETE, and shipping dark**) and the P4 adapter containment
(**COMPLETE — ADJUDICATED**; **R-07 recorded CONTAINED**, and *contained* means external-effect
paths are structurally forced through the governed boundary or fail closed — **not** that any
production write is enabled). **`P5` is COMPLETE — ADJUDICATED at 14/14 (100/100)**: the 118 canonical event
contracts, the transactional outbox, the dedup inbox, the GC-1 corpus, deterministic replay, audit
reconstruction, durable timers and the runtime on production PostgreSQL — independently reviewed
with zero material blocking defects and separately adjudicated. **`P6` is now the sole READY unit
and has NOT STARTED.** P5 ships dark: zero production callers, and completing it enables no external
effect.
**P6–P14 are BLOCKED.** So no freight capability here is a live product capability. Read
[`CURRENT.md`](../implementation/CURRENT.md) for the machine-verified status. "Target phase" is the earliest phase where the capability is
scheduled to appear (shadow, then supervised, then possibly bounded-autonomous) — **not a claim that
it exists.** Autonomy ceiling uses the canonical gate decisions of
[`ADR-010`](../architecture/decisions/ADR-010-policy-rules-constraints-autonomy.md).

**Autonomy-maturity legend** (the intended maximum, per capability — see [`AUTONOMY-MATRIX.md`](AUTONOMY-MATRIX.md)):
`OBSERVE` · `RECOMMEND` · `DRAFT` · `APPROVAL-REQUIRED EXECUTION` · `BOUNDED AUTONOMOUS` ·
`NEVER AUTONOMOUS / PERMANENT HUMAN AUTHORITY`.

---

## 1. Sales & customer intake  — loop **W1** · use cases **UC-02, UC-03** · coverage tier `REQUIRES_DESIGN_PARTNER_VALIDATION`

- **Objective:** turn inbound customer demand into a priced commitment the customer accepted, with downstream coverage work created.
- **Triggers:** a quote request arriving by email, portal, form, API, spreadsheet, or conversation.
- **Inputs:** the demand message/document; historical lane performance and pricing; customer-specific pricing and approval rules; customer/facility records.
- **Work performed:** extract origin, destination, dates, equipment, commodity, weight, references, accessorial requirements, special handling; detect missing/contradictory information; ask the customer for clarification; compare historical lanes; **prepare** quotes; **draft** responses; follow up on open quotes; convert accepted quotes into booked loads; preserve customer preferences and contractual requirements.
- **Outputs:** a Quote Version; a sent quote (on approval); an accepted Customer Order; preserved customer preferences.
- **External systems:** email (A1), customer portal (A7), spreadsheet/file (A16), load board for market rate (A5, decision-support read).
- **Evidence required:** the source demand (provenance preserved); market-rate observation as `DECISION_SUPPORT` only; human-approved sell rate before any commitment.
- **Common exceptions:** ambiguous customer/facility binding; incomplete or contradictory demand; below-floor price request.
- **Approval boundary:** **the sell rate is a human decision — Neyma never prices.** A model-recommended rate is `MODEL_INFERRED` and never auto-sent.
- **Current state:** SPECIFIED. · **Target phase:** P13 (supervised); quoting autonomy is later-staged and `NEEDS VALIDATION`. · **Related loop:** W1. · **Dependencies:** P6 (work items), P7 (evidence), P8 (policy), P9 (domain + comms).
- **Autonomy ceiling:** pricing/contractual commitment → **APPROVAL-REQUIRED EXECUTION** at most; extraction/clarification-drafting → `DRAFT`.

## 2. Load creation & order entry  — loop **W1** · use case **UC-03**

- **Objective:** create loads and stops in the system of record with correct, provenanced values, and no duplicate or unauthorized writes.
- **Triggers:** an accepted Customer Order (W1 conversion).
- **Inputs:** the accepted order; addresses/time zones/references/contacts/appointment windows; equipment/weight/commodity/date constraints.
- **Work performed:** create loads; create pickup and delivery stops; normalize addresses, time zones, references, contacts, windows; attach source documents; validate equipment/weight/dates/commodity/stop sequencing; identify duplicate orders; assign the correct customer/branch/team/operational owner; preserve source provenance per value.
- **Outputs:** one or more Brokerage Loads with stops; attached source documents; an assigned accountable owner.
- **External systems:** TMS or the customer's system-of-record node (A4 / operational graph), document storage (A11).
- **Evidence required:** source provenance for every entered field; duplicate-detection basis.
- **Common exceptions:** duplicate order; ambiguous customer/branch assignment; conflicting stop data.
- **Approval boundary:** writes to the system of record are gated external effects (checkpoint → witness → grant); duplicate/unauthorized writes are structurally prevented.
- **Current state:** SPECIFIED. · **Target phase:** P9 (domain) → P12 (supervised write). · **Related loop:** W1. · **Dependencies:** P4 (effect boundary), P6, P9.
- **Autonomy ceiling:** **APPROVAL-REQUIRED EXECUTION**, graduating to `BOUNDED AUTONOMOUS` for low-risk normalized fields only under earned policy.

## 3. Carrier sourcing & tendering  — loop **W2** · use cases **UC-04, UC-06** · tier `REQUIRES_DESIGN_PARTNER_VALIDATION`

- **Objective:** a confirmed Carrier Assignment at a committed buy rate with a signed Rate Confirmation.
- **Triggers:** an uncovered Load (W1→W2 handoff).
- **Inputs:** lane/equipment/geography/capacity/compliance/customer constraints; carrier performance/rate/service/risk/responsiveness/relationship history; carrier bids and responses.
- **Work performed:** identify matching carriers; rank by history/rate/service/risk/responsiveness/relationship; send load offers; collect bids and responses; answer routine carrier questions; negotiate **within explicitly approved ranges**; verify authority/insurance/safety and internal compliance (via W3); prepare rate confirmations; tender loads; escalate uncovered freight; **record why a carrier was selected.**
- **Outputs:** load postings; a confirmed Carrier Assignment; a signed Rate Con; a recorded selection rationale.
- **External systems:** load board (A5), carrier portal (A6), email (A1), FMCSA/authority (A10), TMS (A4).
- **Evidence required:** a current `QUALIFIED` carrier qualification decision at tender time (freshness read); carrier-asserted rate is `MODEL_EXTRACTED` until a human accepts it.
- **Common exceptions:** no capacity / uncovered freight; carrier lapsed on qualification; below-margin buy rate; carrier identity ambiguity.
- **Approval boundary:** **the human commits the carrier and the rate.** *Autonomous carrier booking does not exist and is not implied.*
- **Current state:** SPECIFIED. · **Target phase:** P13. · **Related loop:** W2 (gated by W3). · **Dependencies:** P4, P6–P9, W3.
- **Autonomy ceiling:** carrier selection & rate commitment → **NEVER AUTONOMOUS** at commitment; sourcing/ranking/outreach drafting → `RECOMMEND`/`DRAFT`.

## 4. Dispatch & driver communication  — loop **W4** (+ **W5** check-calls, **W10** sends) · use cases **UC-07, UC-11** · tier `IN_INITIAL_COMMERCIAL_WORKFLOW` (comms)

- **Objective:** the load is operationally ready to move and the driver/carrier is informed and confirmed, continuously, until delivery and document collection.
- **Triggers:** an active Carrier Assignment; then per-cycle: the next required check-in.
- **Inputs:** driver identity, phone, truck, trailer, dispatch contact; pickup/delivery instructions; appointment windows; status and ETA responses.
- **Work performed:** confirm driver/equipment/dispatch contact; deliver pickup/delivery instructions; confirm load acceptance; remind before appointments; request arrival/departure/loaded/empty/delivered statuses and ETA updates; collect check calls; request detention timestamps; request POD photos and missing paperwork; communicate appointment changes; detect driver silence or inconsistent replies; summarize exceptions for dispatchers; update timelines and TMS statuses where authorized; preserve full communication history; escalate safety/service/customer-impacting issues.
- **Intended loop:** `active load → determine next required check-in → contact driver/carrier → interpret response → update load state → detect delay/detention/inconsistency → notify the appropriate human/customer → schedule next check → continue until delivery + document collection.`
- **Outputs:** confirmed readiness evidence; updated load state/timeline; escalations; a preserved communication history.
- **External systems & channels:** email (A1), **SMS (A2 — planned)**, **phone/voice transcript (A3 — planned)**, carrier portal (A6), notification delivery (A18), TMS notes (A4), mobile/web surfaces.
- **Evidence required:** message-delivery receipt (a send with no delivery evidence → `UNKNOWN_OUTCOME`); driver "delivered" assertion is `MODEL_EXTRACTED`, never delivery proof.
- **Common exceptions:** driver no-show / silence; inconsistent status; late pickup; equipment/temperature unknown (fail-closed).
- **Approval boundary:** bad-news and money communications keep permanent human gates ([`ADR-015`](../architecture/decisions/ADR-015-communications-subsystem.md), [`ADR-003`](../architecture/decisions/ADR-003-authorization-assertion.md)); routine status sends are policy-controlled.
- **Current state:** SPECIFIED. **Thin spot (recorded elaboration debt):** no workflow step yet invokes a **driver-directed SMS/voice op** — outbound is carrier-addressed via A1/A18; A2/A3 are planned adapters. See [`OPERATIONAL-LOOPS.md`](OPERATIONAL-LOOPS.md) §gaps. · **Target phase:** P9 (comms ingestion) → P12 (supervised sends) → P13 (dispatch execution). · **Related loop:** W4/W5/W10. · **Dependencies:** P4, P9, ADR-015.
- **Autonomy ceiling:** routine status sends → `APPROVAL-REQUIRED EXECUTION`, graduating to `BOUNDED AUTONOMOUS` per earned low-risk template; dispatch issuance → **APPROVAL-REQUIRED**; bad-news/money → **NEVER AUTONOMOUS**.

## 5. Track & trace  — loop **W5** · use case **UC-09** · tier `IN_INITIAL_COMMERCIAL_WORKFLOW`

- **Objective:** the customer knows the true status and delays are caught early.
- **Triggers:** pickup (Stop `DEPARTED`); then continuous monitoring.
- **Inputs:** GPS/ELD/tracking-link positions, carrier-portal/email/SMS status, TMS events.
- **Work performed:** monitor positions and events; calculate/update ETA; detect missed check-ins; detect route/timing/status deviations; maintain a shipment event timeline; distinguish normal variance from actionable exceptions; notify customers per customer-specific rules; escalate late pickup/delivery, driver silence, tracking failure, appointment risk; reconcile conflicting location/status signals; preserve evidence for every status claim.
- **Outputs:** current ETA; a shipment event timeline; delay/exception detections; customer notifications (via W10).
- **External systems:** tracking provider / ELD (A9), email (A1), SMS (A2 — planned), notification (A18).
- **Evidence required:** position is `SYSTEM_IMPORTED`; driver status assertion `MODEL_EXTRACTED`; **derived ETA is `MODEL_INFERRED` and never gates**; a "delivered" tracking status is not delivery proof.
- **Common exceptions:** no tracking provider (Expectations go `INDETERMINATE`, not `OVERDUE`); conflicting signals; blind windows.
- **Approval boundary:** read + detect are automatic; **what to tell the customer when the news is bad is human-owned.**
- **Current state:** SPECIFIED. · **Target phase:** P10 (shadow read-only) → P12 (supervised notifications). · **Related loop:** W5. · **Dependencies:** P9, ADR-015.
- **Autonomy ceiling:** monitoring/detection → `OBSERVE`; ETA/timeline → `RECOMMEND`; routine "on-time" updates → `APPROVAL-REQUIRED`→`BOUNDED AUTONOMOUS`; bad-news → **NEVER AUTONOMOUS**.

## 6. Appointment scheduling  — loop **W4** · use case **UC-08** · tier `REQUIRES_DESIGN_PARTNER_VALIDATION`

- **Objective:** pickup and delivery appointments that fit the load's constraints, confirmed and recorded.
- **Triggers:** a load needing a pickup/delivery appointment (W4 readiness).
- **Inputs:** facility/retailer/port/rail/warehouse scheduling rules; transit time; driver availability and HOS where data exists; downstream stops.
- **Work performed:** request appointments; operate facility/retailer/port/rail/warehouse portals; compare options against load constraints; consider transit/HOS/downstream stops; schedule or reschedule; send confirmations; update the TMS; detect conflicts; escalate unavailable or risky windows; preserve appointment evidence and communication history.
- **Outputs:** a `CONFIRMED` appointment window (`REQUESTED` ≠ `CONFIRMED`); TMS update; confirmations; escalations.
- **External systems:** appointment portal (A8), email (A1), TMS (A4).
- **Evidence required:** the confirmed-window readback (freshness read; facility-local time zone); appointment evidence preserved.
- **Common exceptions:** no available window; portal unavailable; conflict with downstream stop.
- **Approval boundary:** **the human confirms binding appointments.**
- **Current state:** SPECIFIED. **Thin spot:** only a generic A8 "Appointment Portal"; **port/rail/warehouse-specific portals are not yet specified** (ties to mode-specific UC-30). · **Target phase:** P13. · **Related loop:** W4. · **Dependencies:** P4, P9, A8, UC-30.
- **Autonomy ceiling:** requesting/comparing → `RECOMMEND`/`DRAFT`; booking → `APPROVAL-REQUIRED EXECUTION`, graduating within caps.

## 7. Exception management  — loop **W7** (cross-cutting) · use case **UC-12** · tier `IN_INITIAL_COMMERCIAL_WORKFLOW`

- **Objective:** every exception reaches an accountable, decision-referenced resolution — nothing falls through the cracks.
- **Triggers:** any loop raising an unparseable observation, ambiguous binding, unknown outcome, conflict, permanent failure, or fraud/Sev-0 signal.
- **Inputs:** the originating signal; the load/parties/policies/deadlines/financial exposure; assembled evidence.
- **Work performed:** detect and coordinate the full exception taxonomy — late pickup/delivery, missed appointment, driver no-show, carrier rejection, breakdown, weather/route disruption, damaged/rejected freight, shortage/overage, wrong address, cancellation, detention, layover, lumper, accessorial disputes, missing documents, inconsistent status, invoice mismatch, short payment, operational uncertainty, and **external action with `UNKNOWN_OUTCOME`.** For each: gather evidence; identify load/parties/policies/deadlines/exposure; classify severity; recommend next actions; prepare communications; request approval when required; execute only within authority; verify the outcome; escalate unresolved/ambiguous cases; preserve a full audit trail.
- **Outputs:** `RESOLVED{decision_ref}` with the downstream disposition created; a compensated effect where required; an audit trail.
- **External systems:** reads for assembly; the compensation path uses the full effect pipeline.
- **Evidence required:** a decision reference for closure (**`AutoClose`/inactivity is illegal**); an owner + permitted terminal handling for any `UNKNOWN_OUTCOME`.
- **Common exceptions:** the taxonomy above is itself the exception set; Sev-0 auto-engages the brake.
- **Approval boundary:** the resolution decision is nearly always human; only licensed resolution actions execute.
- **Current state:** SPECIFIED. · **Target phase:** P8 (typed exceptions/compensation) → P10 (in the wedge). · **Related loop:** W7. · **Dependencies:** P6–P8.
- **Autonomy ceiling:** detection/assembly/recommendation → `OBSERVE`/`RECOMMEND`; resolution → **APPROVAL-REQUIRED / human decision**.

## 8. Document operations  — loop **W6** · use case **UC-10** · tier `IN_INITIAL_COMMERCIAL_WORKFLOW`

- **Objective:** the right documents on the right load, complete and correct for billing — and known, per load, what is missing and for how long.
- **Triggers:** delivery reached (W5→W6); required documents not yet arrived (a tracked non-event).
- **Inputs:** customer orders, rate cons (customer & carrier), BOLs, PODs, carrier/customer invoices, lumper receipts, detention forms, fuel receipts, manifests, weight tickets, customs docs, insurance certificates, claims evidence, facility receipts, accessorial backup, other load documents.
- **Work performed:** ingest (content-addressed); classify; extract; validate; match to load; detect duplicates; check signatures/required fields; detect contradictions; identify missing documents; request documents; file; version-track; preserve provenance; support retention and audit.
- **Outputs:** a `COMPLETE` Document Packet on the correct load; filed/versioned documents; missing-document expectations.
- **External systems:** email (A1), document storage (A11), TMS (A4).
- **Evidence required:** content digest per document; deterministic load binding within `(tenant, customer)`; a `MODEL_INFERRED` classification never counts as a validated POD.
- **Common exceptions:** illegible/unsigned document; ambiguous binding; contradictory documents; missing non-events.
- **Approval boundary:** filing is a gated effect; illegible/ambiguous/unconfirmable bindings route to a human.
- **Current state:** SPECIFIED. · **Target phase:** P10 (shadow) → P12 (supervised requests). · **Related loop:** W6. · **Dependencies:** P7 (evidence), P9.
- **Autonomy ceiling:** ingest/classify/validate → `OBSERVE`; request-missing-doc → `DRAFT`→`BOUNDED AUTONOMOUS` (low-risk); binding on ambiguity → **APPROVAL-REQUIRED**.

## 9. Delivered Load Closure  — the wedge outcome, spanning **W5/W6/W7/W8/W10**

- **Objective:** own a delivered/near-delivered load until its obligations are closed and the operational file can close on evidence and policy.
- **Intended chain:** `delivered load detected → verify load identity & delivery state → gather POD/BOL + required documents → validate signatures/fields → identify missing/conflicting evidence → validate accessorial support → reconcile carrier invoice → prepare carrier payable → prepare customer invoice → route exceptions for approval → close the file only when evidence & policy permit.`
- **Maturity split:** *shadow/read-only* — delivery detection, document collection, reconciliation, billing-readiness assessment (P10, no writes/sends); *recommendation/drafting* — drafted follow-ups and prepared billing/payable data; *supervised effects* — the writes and sends (P12); *later bounded autonomy* — only low-risk earned classes.
- **External systems / evidence / exceptions:** inherited from the contributing loops (W5/W6/W7/W8/W10).
- **Approval boundary:** money and bad-news stay human; the model never chooses an amount.
- **Current state:** SPECIFIED; **`HYPOTHESIS` pending design-partner validation.** · **Target phase:** P10 shadow → P11 deployed shadow → P12 supervised. · **Dependencies:** P4–P9, the design-partner evidence program.
- **Autonomy ceiling:** aggregate of its contributing loops; closure decision is human-accountable.

## 10. Carrier invoice audit & accounts payable  — loop **W9** · use cases **UC-16, UC-17, UC-18** · tier `REQUIRES_DESIGN_PARTNER_VALIDATION`

- **Objective:** the carrier paid correctly, line-by-line reconciled, and settled — with every line provable.
- **Triggers:** a carrier invoice received.
- **Inputs:** the carrier invoice; the Rate Con; supporting documents; fuel/detention/layover/lumper/accessorial backup; customer/company approval rules; remittance-party binding.
- **Work performed:** ingest carrier invoices; match to load and carrier; compare against the rate con; validate line items and totals; validate accessorials; detect duplicate invoices/charges; verify supporting documents; apply approval rules; prepare payables; route discrepancies; communicate disputes; monitor unresolved balances; record approval and payment-readiness evidence; verify remittance target (factoring change → drift → re-verify/void).
- **Outputs:** a reconciled, recorded payable; disputes; a settled payment reconciled against a bank observation.
- **External systems:** email (A1), TMS (A4), document storage (A11), accounting/ERP (A12), payment/bank observation (A13).
- **Evidence required:** the rate con + authorized accessorials as Material Facts; an accessorial supported only by a counterparty assertion **blocks** the payable; a local `PAID` is never proof — settlement needs a bank observation.
- **Common exceptions:** duplicate invoice; unauthorized/undocumented accessorial (highest fraud risk — detention/lumper/layover/TONU); wrong remittance party; before-POD invoice.
- **Approval boundary:** **money leaving the business requires human approval, permanently.** `UNKNOWN_OUTCOME` on pay never auto-resolves and never becomes `FAILED` on timeout.
- **Current state:** SPECIFIED. *Unrestricted money movement is not implied.* · **Target phase:** P13. · **Related loop:** W9. · **Dependencies:** P4–P9, ADR-003.
- **Autonomy ceiling:** ingest/reconcile/prepare → `RECOMMEND`/`DRAFT`; **record payable & pay → APPROVAL-REQUIRED (money-out), never autonomous by default.**

## 11. Customer billing & accounts receivable  — loop **W8** · use cases **UC-14, UC-15** · tier `IN_INITIAL_COMMERCIAL_WORKFLOW`

- **Objective:** the customer paid, reconciled — money in the door, not an invoice in an outbox.
- **Triggers:** a `COMPLETE` Document Packet (W6→W8, POD-gated eligibility).
- **Inputs:** the sell rate and authorized accessorials; customer-specific billing rules; POD and required backup; remittances/aging.
- **Work performed:** generate customer invoices; apply customer-specific billing rules; attach POD and required backup; submit via email/portal/API/accounting integration; track acceptance and payment status; monitor aging; send approved reminders; investigate short-payments; reconcile remittances; manage billing disputes; escalate collections and contractual issues; preserve submission and payment evidence.
- **Outputs:** a released invoice; tracked collections; a verified Payment Application (`PAID`) or an authorized write-off / approved short-pay / credit-rebill settlement.
- **External systems:** TMS (A4), accounting/ERP (A12), payment/bank observation (A13), email/portal (A1/A7).
- **Evidence required:** amount from deterministic validation (**the model never chooses an amount**); POD-gated eligibility; a bank observation to confirm payment.
- **Common exceptions:** short-pay/dispute; aging past terms; missing backup; credit-rebill.
- **Approval boundary:** **releasing the invoice, and any credit/write-off, require human approval.**
- **Current state:** SPECIFIED. · **Target phase:** P10 (billing-readiness in shadow) → P12 (supervised invoice release) → P13 (AR/collections). · **Related loop:** W8. · **Dependencies:** P4–P9.
- **Autonomy ceiling:** prepare/aging/reminders-draft → `RECOMMEND`/`DRAFT`; invoice release & write-off → **APPROVAL-REQUIRED**; disputes → human.

## 12. Claims & cargo exceptions (OS&D)  — loop **W11** · use case **UC-19** · tier `REQUIRES_DESIGN_PARTNER_VALIDATION`

- **Objective:** an OS&D case reaches a referenced resolution with a financial adjustment created — the human makes the legal call.
- **Triggers:** a POD OS&D notation (W6), a damaged-vs-normal conflict (W5), or a customer report.
- **Inputs:** BOL, POD, photos, invoices, correspondence, inspection records; filing/response deadlines; responsible parties.
- **Work performed:** open and track claims; collect evidence; identify responsible parties; track filing/response deadlines; calculate claimed values from available evidence; identify missing evidence; assemble claims packets; communicate with carriers/customers/warehouses/insurers/internal teams; monitor claim status; prepare settlement recommendations.
- **Outputs:** `RESOLVED{decision_ref}` + a durable financial adjustment (new credit/debit/compensation — never a rewrite of a settled invoice/payable).
- **External systems:** reads for assembly; the compensation path uses the full effect pipeline.
- **Evidence required:** the assembled packet + timeline; deadlines tracked as Expectations.
- **Common exceptions:** missing evidence; disputed liability; deadline risk.
- **Approval boundary:** **legal, liability and settlement decisions require human authority — Neyma does not file claims.**
- **Current state:** SPECIFIED. · **Target phase:** P13. · **Related loop:** W11. · **Dependencies:** P6–P9.
- **Autonomy ceiling:** assembly/timeline/recommendation → `RECOMMEND`/`DRAFT`; **filing & settlement → NEVER AUTONOMOUS / PERMANENT HUMAN AUTHORITY.**

## 13. Carrier compliance & onboarding  — loop **W3** · use case **UC-05** · tier `REQUIRES_DESIGN_PARTNER_VALIDATION`

- **Objective:** carriers are qualified at the relevant time for the relevant movement.
- **Triggers:** onboarding; every load (freshness gate); document expiry.
- **Inputs:** W-9s, insurance certificates, operating authority, contracts/onboarding packets, approved payment information, internal carrier requirements.
- **Work performed:** collect W-9s; collect insurance certificates; verify operating authority; manage contracts and onboarding packets; collect approved payment information through secure workflows; monitor document expirations; detect authority/insurance changes; apply internal requirements; flag risk; request missing compliance documents; preserve verification evidence.
- **Outputs:** a current Qualification Decision on file; a completed onboarding packet; expiry expectations; fraud/risk signals.
- **External systems:** FMCSA/authority (A10), document storage / COI (A11).
- **Evidence required:** authority/insurance/safety pulled at qualification time (freshness read); the final trust decision is human-reserved; a counterparty's authorization claim is a fraud signal, never authorization.
- **Common exceptions:** lapsed authority/insurance; impersonation/fraud signal; marginal safety score.
- **Approval boundary:** **identity, banking, credentials and compliance changes are sensitive, approval-controlled workflows; the final trust decision is human.**
- **Current state:** SPECIFIED. **Thin spot:** W-9 / signed-agreement artifacts are named in the operating model but not decomposed into W3 steps (recorded elaboration debt). · **Target phase:** P13. · **Related loop:** W3. · **Dependencies:** P7–P9, ADR-014.
- **Autonomy ceiling:** collect/verify/monitor/flag → `OBSERVE`/`RECOMMEND`; **qualification & trust decision → NEVER AUTONOMOUS / human**.

## 14. Customer service  — loop **W10** + conversational layer · use cases **UC-11, UC-33** · tier `PLANNED_PLATFORM_CAPABILITY` (conversational)

- **Objective:** answer and act on customer questions using the same operational state as the rest of Neyma.
- **Triggers:** a customer question (where is my load / ETA / has it delivered / is the POD available / why delayed / why is this invoice different / when will it be submitted / what documents are missing / which loads need attention / what action was already taken).
- **Inputs:** the shared Work Items, evidence, policies and operational state.
- **Work performed:** interpret the question; retrieve state and evidence; answer *what/why/what's-open*; take natural-language requests; and — where a request would cause a consequential effect — route it through the same authorization/policy/evidence/approval/idempotency/effect-grant/verification controls as any other action.
- **Outputs:** an evidence-backed answer; a routed request; a tracked commitment.
- **External systems:** web/Slack/Teams/email/mobile/voice (all resolving to one identity), the communications adapters.
- **Evidence required:** answers are grounded in canonical operational state; **conversation is never a second source of truth and never independent authority.**
- **Common exceptions:** a request beyond authority; an ambiguous instruction; a prompt-injection attempt (never relayed).
- **Approval boundary:** informational answers are automatic; any consequential request follows the normal gates.
- **Current state:** SPECIFIED. **Structural note:** customer service is a **platform/conversational surface** (UC-33) over W10 + shared state, **not a separate loop and not a disconnected chatbot truth source.** · **Target phase:** P11 (conversational workspace) building on P9. · **Related loop:** W10. · **Dependencies:** P9, ADR-019.
- **Autonomy ceiling:** answering → `OBSERVE`/`RECOMMEND`; acting → the underlying capability's ceiling.

## 15. Internal operations & management  — use cases **UC-22, UC-23, UC-24** · tier `PLANNED_PLATFORM_CAPABILITY`

- **Objective:** give the owner and operators an honest operating picture and surface where work is at risk.
- **Triggers:** a scheduled brief; a queue/aging threshold; an owner request.
- **Inputs:** the operational state across loops; metrics taxonomy (activity / workflow-completion / business-outcome / safety).
- **Work performed:** produce daily operating briefs; identify loads at risk; surface unassigned or stalled work; track missing documents and invoice/payment exceptions; measure carrier and customer-service performance; identify margin leakage and recurring accessorial disputes; monitor queue aging and service levels; forecast operational workload; identify bottlenecks; identify problematic customers/carriers/facilities/lanes; recommend process improvements; preserve the evidence behind every metric.
- **Outputs:** operating briefs; at-risk views; performance and safety metrics; process recommendations.
- **External systems:** oversight surfaces (Slack/A14), the web control plane (ADR-017), the conversational layer (ADR-019).
- **Evidence required:** every management metric is backed by the same evidence and events as the operational state (no vanity metrics).
- **Common exceptions:** stale/incomplete data; conflicting signals.
- **Approval boundary:** read/report only — **the owner remains accountable.**
- **Current state:** SPECIFIED. **Structural note:** management is a **cross-cutting oversight surface (UC-23), correctly not one of the eleven operational-execution loops.** · **Target phase:** P11 (control plane + oversight). · **Related loop:** none (platform). · **Dependencies:** P5–P9, ADR-017, ADR-019.
- **Autonomy ceiling:** **OBSERVE / RECOMMEND** only — never autonomous consequential action.

## 16. Safety, policy, approvals & control  — cross-cutting · use case **UC-33** infra · ADR-003/004/009/010/011

- **Objective:** ensure every consequential action is chosen deliberately from the capability ladder and passes the effect boundary.
- **The action choice (per action):** `observe · understand · recommend · draft · request approval · execute · verify · escalate · stop` — decomposing onto the canonical five verbs (Observe/Assist/Execute/Verify/Escalate) and the four gate decisions.
- **The canonical effect pipeline** (every consequential effect): `Work Item → Pipeline Instance → policy & validation → optional approval → atomic checkpoint → Checkpoint Witness → Effect Grant → atomic claim → adapter execution → verification → outcome → evidence & projection → closure.`
- **Examples of the ladder:** read a load → automatic observation · classify a document → automatic · request a missing POD → potentially bounded-automatic later · update a nonfinancial operational status → policy-controlled · send a routine status message → policy-controlled · book a carrier outside approved rate bounds → approval required · accept a claim settlement → human authority · change banking information → strong human verification · move money → tightly controlled · ambiguous external action → `UNKNOWN_OUTCOME`, stop, investigate, escalate.
- **Current state:** the safety kernel (checkpoint/witness/grant/brake) is recorded COMPLETE at P3 and **ships dark**; routing effects through it is P4, recorded **COMPLETE — ADJUDICATED**, and **R-07 is recorded CONTAINED** — external-effect paths are structurally forced through the governed boundary or fail closed. **No production write is enabled**: the deployed route answers a recorded `ROUTE_NOT_CONFIGURED` refusal and the production `GateRegistry` population stays EMPTY until U8.1 / P8. See [`CURRENT.md`](../implementation/CURRENT.md). · **Dependencies:** P3, P4, P8.
- **Autonomy ceiling:** this is the mechanism that *enforces* every other capability's ceiling; the authorization assertion is `PERMANENT_HUMAN_ASSERTION_REQUIRED` (ADR-003).

## 17. Shared memory & learning  — cross-cutting knowledge base · P7/P9

- **Objective:** accumulate durable, inspectable, tenant-safe operational knowledge — not uncontrolled model memory.
- **Knowledge domains:** customers, carriers, drivers, lanes, facilities, appointments, document quirks, billing requirements, accessorial rules, communication preferences, recurring exceptions, approval patterns, service history, operational corrections.
- **Work performed:** capture observations and corrections **with provenance and governance**; make knowledge inspectable and tenant-scoped; feed decision-support (never gating) reads.
- **Evidence required:** every correction preserved with provenance; **`MODEL_INFERRED` never gates a consequential action; `OWNER_ASSERTED` is never silently overwritten.**
- **Approval boundary:** learning informs; it never creates authority.
- **Current state:** LEGACY_IMPLEMENTATION_ONLY — **the canonical capability is not built**; a pre-reset analogue exists under disposition and may never be read as this capability being done. **Open finding:** that runtime knowledge base still hardcodes `tenant="default"` — a recorded finding that closes when the KB is made tenant-safe (see [`CURRENT.md`](../implementation/CURRENT.md)). · **Target phase:** P7 (provenance/evidence) → P9 (domain). · **Dependencies:** P2, P7.
- **Autonomy ceiling:** **OBSERVE / RECOMMEND** — memory is decision-support, never authority.

## 18. Channels & systems  — the adapter boundary · P9/P11/P12

- **Objective:** work across the systems freight teams already use — every external effect through the canonical effect boundary and authorization model.
- **Channels & systems Neyma may eventually work across:** TMS systems (A4), accounting systems (A12), email (A1), SMS (A2), phone/voice transcripts (A3), Slack/internal collaboration (A14), customer portals (A7), carrier portals (A6), retailer/facility scheduling portals (A8), GPS/ELD/tracking providers (A9), browser-based legacy systems (A15 actuation), document stores (A11), payment/bank observation (A13), notification delivery (A18), file/spreadsheet (A16), FMCSA/authority (A10), APIs and databases.
- **Rule:** **all external effects use the canonical effect boundary and authorization model** ([`ADR-004`](../architecture/decisions/ADR-004-effect-boundary.md)/ADR-009); reads are classified (informational / decision-support / consequential-freshness); a successful write into one node is never proof the workflow is complete.
- **Current state:** LEGACY_IMPLEMENTATION_ONLY — **none of the eighteen canonical adapter contracts is built**; the live/partial adapters in the tree are pre-reset modules under disposition. Per [`adapters/registry.md`](../specifications/adapters/registry.md) (A1/A4/A14/A15 live or partial; A2/A3/A5–A13/A16/A18 planned). · **Target phase:** P9 (comms ingestion) → P11 (integration onboarding) → P12 (supervised effects). · **Dependencies:** P4 (containment), P9, P11, ADR-014.
- **Autonomy ceiling:** per the effecting capability; the boundary itself never grants authority.

---

## Cross-reference — capability → loop → use case → earliest phases

| Capability | Loop | Use case(s) | Coverage tier | Earliest shadow | Earliest supervised |
|---|---|---|---|---|---|
| Sales & intake | W1 | UC-02, UC-03 | REQUIRES_DESIGN_PARTNER_VALIDATION | — | P13 |
| Load creation | W1 | UC-03 | (as above) | — | P12 |
| Carrier sourcing & tender | W2 | UC-04, UC-06 | REQUIRES_DESIGN_PARTNER_VALIDATION | — | P13 |
| Dispatch & driver comms | W4/W5/W10 | UC-07, UC-11 | IN_INITIAL_COMMERCIAL_WORKFLOW (comms) | P10 | P12 |
| Track & trace | W5 | UC-09 | IN_INITIAL_COMMERCIAL_WORKFLOW | P10 | P12 |
| Appointment scheduling | W4 | UC-08 | REQUIRES_DESIGN_PARTNER_VALIDATION | — | P13 |
| Exception management | W7 | UC-12 | IN_INITIAL_COMMERCIAL_WORKFLOW | P10 | P12 |
| Document operations | W6 | UC-10 | IN_INITIAL_COMMERCIAL_WORKFLOW | P10 | P12 |
| Delivered Load Closure | W5/6/7/8/10 | (aggregate) | IN_INITIAL_COMMERCIAL_WORKFLOW | P10 | P12 |
| Carrier invoice audit / AP | W9 | UC-16, UC-17, UC-18 | REQUIRES_DESIGN_PARTNER_VALIDATION | — | P13 |
| Customer billing / AR | W8 | UC-14, UC-15 | IN_INITIAL_COMMERCIAL_WORKFLOW | P10 | P12 |
| Claims / OS&D | W11 | UC-19 | REQUIRES_DESIGN_PARTNER_VALIDATION | — | P13 |
| Carrier compliance & onboarding | W3 | UC-05 | REQUIRES_DESIGN_PARTNER_VALIDATION | — | P13 |
| Customer service | W10 + conversational | UC-11, UC-33 | PLANNED_PLATFORM_CAPABILITY | P11 | P11 |
| Internal ops & management | platform | UC-22, UC-23, UC-24 | PLANNED_PLATFORM_CAPABILITY | P11 | — (read-only) |
| Safety/policy/approvals | cross-cutting | infra | — | P3/P4 | P8/P12 |
| Shared memory & learning | cross-cutting | infra | — | P7 | P9 |
| Channels & systems | adapters | infra | — | P9 | P12 |

> **No entry above is a claim that the capability exists today.** Every capability is at readiness
> tier SPECIFIED; the phases are the *earliest scheduled* appearance. "Earliest bounded-autonomy"
> for any capability is **never before P14** and only for classes that earn it — see
> [`AUTONOMY-MATRIX.md`](AUTONOMY-MATRIX.md). Authoritative status: [`CURRENT.md`](../implementation/CURRENT.md).
