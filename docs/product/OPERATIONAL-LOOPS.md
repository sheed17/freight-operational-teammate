# Neyma — Operational Loops and Capability Coverage

> **CANONICAL — loop consolidation and gap analysis.** Maps the full operational scope onto the
> **eleven canonical loops W1–W11**, and records the exact coverage gaps. **It holds NO authority
> independent of its sources and creates NO new product decision. It does NOT create, rename,
> split, combine, or silently expand any loop.** The loop names and boundaries are the Operating
> Model's; the sole canonical loop index is [`workflows/registry.md`](../specifications/workflows/registry.md),
> and the per-loop binding detail is in [`workflows/W1..W11`](../specifications/workflows/). A twelfth
> loop is a product decision requiring an explicit change to [`PRODUCT.md §6`](../../PRODUCT.md) and
> the workflow registry — **this document proposes none.** On any conflict the cited source wins.

---

## 1. The eleven loops are the operational-execution map

There are **exactly eleven** loops ([`PRODUCT.md §6`](../../PRODUCT.md)). They are the map of the
operational *execution* domain. Two capability areas the product vision calls out — **customer
service** and **internal operations & management** — are **cross-cutting platform surfaces**, not
operational-execution loops, and are correctly represented outside the eleven (see §4). This
document therefore concludes with **no loop revision proposed** (§5), which also preserves the
`test_docs_control_system::test_7` invariant of exactly eleven loops and eleven spec files.

## 2. Per-loop definitions

Fields per loop: **purpose · trigger · entry conditions · key states · tools/integrations · evidence
inputs · messages/comms · approvals · effects · verification · exceptions · closure · related phases ·
initial autonomy → later autonomy.** These summarize the binding specs; the specs win on any detail.

### W1 — Quote *(incl. demand & order intake)*
- **Purpose:** a priced commitment the customer accepted, with downstream coverage work created.
- **Trigger / entry:** inbound customer demand (email/portal/spreadsheet/human); dedup on source-natural key.
- **Key states:** ingest demand → bind customer/facility → gather pricing evidence → recommend sell rate → create Quote Version → send quote → ingest acceptance → convert to Order → Load(s).
- **Tools:** A1 email, A5 load board (market rate), A7 customer portal, A16 spreadsheet, A4/A10 (bind).
- **Evidence inputs:** source demand w/ provenance; market rate as `DECISION_SUPPORT`.
- **Messages:** `SEND_QUOTE` (on approval).
- **Approvals / effects:** **sell rate `HUMAN_APPROVAL_REQUIRED`**; effect `SEND_QUOTE`.
- **Verification:** quote-send receipt; acceptance ingested; order created.
- **Exceptions:** ambiguous binding; incomplete/contradictory demand; below-floor price.
- **Closure:** an accepted Customer Order with `COVER_LOAD` durably created — **not** a sent quote.
- **Related phases:** P9 (domain/comms) → P13. · **Autonomy:** later-staged (`NEEDS VALIDATION`); send only on approval → graduate low-risk pieces only.

### W2 — Procurement *(sourcing + tender + assignment + rate con)*
- **Purpose:** a confirmed Carrier Assignment at a committed buy rate + signed Rate Con.
- **Trigger / entry:** an uncovered Load (W1→W2).
- **Key states:** search/post → ingest offers → confirm carrier identity → **qualification gate (W3)** → send tender → create Assignment → issue/receive Rate Con → capture remittance.
- **Tools:** A5 load board, A6 carrier portal, A1 email, A4/A10.
- **Evidence inputs:** `QUALIFIED` decision at tender time (freshness); buy rate `MODEL_EXTRACTED` until accepted.
- **Messages:** offers; tender.
- **Approvals / effects:** **carrier & rate `HUMAN_APPROVAL_REQUIRED`**; effects `POST_LOAD`, `SEND_TENDER`, `ISSUE_RATECON`.
- **Verification:** posting readback; assignment confirmed; signed rate con.
- **Exceptions:** uncovered freight; lapsed carrier; below-margin.
- **Closure:** a confirmed Assignment + signed Rate Con + verified remittance — **not** a search result or verbal yes.
- **Related phases:** P13. · **Autonomy:** rate-con issuance approval-gated; carrier commitment never autonomous.

### W3 — Compliance *(continuous carrier qualification)*
- **Purpose:** carriers qualified at the relevant time for the relevant movement.
- **Trigger / entry:** onboarding + every load + on expiry.
- **Key states:** pull authority/insurance/safety → continuous revalidation (durable timers on `expires_at`) → surface fraud/impersonation → make Qualification Decision (**human-reserved**).
- **Tools:** A10 FMCSA, A11 COI/docs.
- **Evidence inputs:** authority/insurance/safety at qualification (freshness); a counterparty authorization claim is a fraud signal.
- **Messages:** missing-document requests.
- **Approvals / effects:** trust decision **human-reserved**; `do_not_use`/preferred rules compiled.
- **Verification:** current decision on file; expiry expectations armed.
- **Exceptions:** lapsed authority/insurance; fraud/impersonation; marginal safety.
- **Closure:** a current Qualification Decision on file (continuous — reopens on expiry/signal).
- **Related phases:** P13. · **Autonomy:** collect/verify/monitor automatic; **qualification & trust never autonomous.**
- **Thin spot:** W-9 / signed-agreement onboarding artifacts named in the operating model but not decomposed into W3 steps — recorded elaboration debt (§4).

### W4 — Dispatch *(readiness + appointment booking)*
- **Purpose:** the load is operationally ready to move (driver, equipment, appointment, refs, docs).
- **Trigger / entry:** an active Assignment (W2→W4).
- **Key states:** confirm driver/equipment → request appointment (`REQUESTED`≠`CONFIRMED`) → read confirmed window → dispatch communication → readiness check.
- **Tools:** A8 appointment portal, A1 email, A18 notification, A6 carrier portal, A15 browser.
- **Evidence inputs:** driver/equipment confirmation; confirmed window (freshness; facility-local tz).
- **Messages:** appointment requests; dispatch comms (`SEND_OUTBOUND`); reminders.
- **Approvals / effects:** binding appointment **human-confirmed**; effects `REQUEST_APPOINTMENT`, `SEND_OUTBOUND`.
- **Verification:** readiness evidence complete; appointment confirmed.
- **Exceptions:** no window; portal down; driver no-show; unknown temperature (fail-closed).
- **Closure:** verified readiness evidence — **not** a sent dispatch message.
- **Related phases:** P13; comms via P9→P12. · **Autonomy:** appointment booking graduating within caps; dispatch issuance approval-gated.
- **Thin spots:** driver-directed **SMS/voice** ops (A2/A3 planned, unused); **port/rail/warehouse** appointment portals (generic A8 only) — recorded elaboration debt (§4).

### W5 — Tracking *(in-transit)*
- **Purpose:** the customer knows the true status; delays caught early.
- **Trigger / entry:** pickup / Stop `DEPARTED` (W4→W5).
- **Key states:** ingest positions/status → detect delay early → check-call the carrier → detention clock.
- **Tools:** A9 tracking/ELD, A1 email, A18 notification.
- **Evidence inputs:** positions `SYSTEM_IMPORTED`; driver assertion `MODEL_EXTRACTED`; **ETA `MODEL_INFERRED` never gates.**
- **Messages:** check-calls (`SEND_OUTBOUND`); delay notices (via W10).
- **Approvals / effects:** bad-news comms **human-owned**; effect `SEND_OUTBOUND`.
- **Verification:** status current; delivery reached (a claim, handed to W6).
- **Exceptions:** no provider (`INDETERMINATE`); conflicting signals; blind window (6h → `INDETERMINATE`, never `OVERDUE`).
- **Closure:** delivery reached AND handed to W6 — **not** a tracking "delivered" status.
- **Related phases:** P10 (shadow) → P12. · **Autonomy:** monitor/detect automatic; routine updates graduate; bad-news never autonomous.

### W6 — Documentation
- **Purpose:** the right documents on the right load, complete for billing; known per-load what is missing and for how long.
- **Trigger / entry:** delivery reached (W5→W6); owns non-events (documents not yet arrived).
- **Key states:** raise doc Expectations → ingest (content-addressed) → classify → bind to load → file → assess packet → OS&D branch (→W11).
- **Tools:** A1 email, A11 document storage, A15 browser, A4 TMS.
- **Evidence inputs:** content digest; deterministic binding within `(tenant, customer)`; a `MODEL_INFERRED` POD does not count.
- **Messages:** document requests (chase).
- **Approvals / effects:** filing gated; effect `FILE_DOCUMENT`.
- **Verification:** packet `COMPLETE` on the correct load.
- **Exceptions:** illegible/unsigned; ambiguous binding; contradictions.
- **Closure:** Document Packet `COMPLETE` + delivery outcome + any OS&D obligation created (→W8 atomic).
- **Related phases:** P10 → P12. · **Autonomy:** ingest/classify/validate automatic; chase-sends inherit outbound approval gate.

### W7 — Exceptions *(cross-cutting)*
- **Purpose:** every exception reaches an accountable, decision-referenced resolution.
- **Trigger / entry:** from any loop — unparseable obs, ambiguous binding, unknown outcome, conflict, permanent failure, fraud/Sev-0. Owner assigned at creation.
- **Key states:** raise → assemble evidence & recommend → resolve (human decision or ACTIVE rule) → compensation branch (full pipeline).
- **Tools:** reads for assembly; compensation uses the full effect pipeline.
- **Evidence inputs:** assembled evidence; a decision reference for closure.
- **Messages:** via W10 as needed.
- **Approvals / effects:** Sev-0 auto-engages the brake; open conflict on a material field blocks the entity's consequential actions; compensation gated.
- **Verification:** `RESOLVED{decision_ref}`; downstream disposition created; `UNKNOWN_OUTCOME` owned.
- **Exceptions:** the full taxonomy (see [`FREIGHT-CAPABILITY-MAP.md`](FREIGHT-CAPABILITY-MAP.md) §7).
- **Closure:** `RESOLVED{decision_ref}` — **`AutoClose`/inactivity is illegal.**
- **Related phases:** P8 → P10. · **Autonomy:** detect/assemble/recommend automatic; resolution human.

### W8 — Billing *(customer AR + cash application)*
- **Purpose:** the customer paid, reconciled — money in the door.
- **Trigger / entry:** Packet `COMPLETE` (W6→W8, atomic); POD-gated eligibility.
- **Key states:** eligibility → read sell + accessorials → prepare invoice → release invoice → verify → collection expectations → cash application → dispute/credit-rebill.
- **Tools:** A4 TMS, A12 accounting/ERP, A13 bank/payment observation, A1/A7.
- **Evidence inputs:** POD-gated eligibility; amount by deterministic validation (**model never chooses**); bank observation for `PAID`.
- **Messages:** invoice submission; approved reminders (via W10).
- **Approvals / effects:** **invoice release `HUMAN_APPROVAL_REQUIRED`**; credit/write-off human; effects `RAISE_INVOICE`, `REISSUE_INVOICE`.
- **Verification:** release readback; verified Payment Application.
- **Exceptions:** short-pay/dispute; aging; missing backup.
- **Closure:** `PAID` (or authorized write-off / approved short-pay / credit-rebill) — **not** a sent invoice.
- **Related phases:** P10 (readiness shadow) → P12 → P13. · **Autonomy:** prepare/aging automatic; release & write-off approval-gated.

### W9 — Settlement *(carrier invoice audit + AP + payment + reconciliation)*
- **Purpose:** the carrier paid correctly, line-by-line reconciled, settled — the highest-risk loop (money out).
- **Trigger / entry:** a carrier invoice received (dedup on invoice number).
- **Key states:** receive invoice (before-POD → held) → reconcile line-by-line → accessorial authorization gate → verify remittance target → record payable → pay + settle → reconcile.
- **Tools:** A1 email, A4 TMS, A11 docs, A12 accounting, A13 bank observation.
- **Evidence inputs:** rate con + authorized accessorials (Material Facts); undocumented accessorial blocks payable; a local `PAID` is never proof.
- **Messages:** dispute communications.
- **Approvals / effects:** **money-out `HUMAN_APPROVAL_REQUIRED`**; effects `RECORD_PAYABLE`, `PAY_CARRIER`; timeout → `UNKNOWN_OUTCOME`, never `FAILED`.
- **Verification:** verified payment/settlement observation.
- **Exceptions:** duplicate invoice; unauthorized accessorial (highest fraud risk); wrong remittance party.
- **Closure:** the payable **settled** — **not** entered/approved/initiated.
- **Related phases:** P13. · **Autonomy:** reconcile/prepare automatic; **record & pay approval-gated, never autonomous by default.**

### W10 — Customer Communications *(cross-cutting)*
- **Purpose:** the customer gets the right message at the right time; commitments tracked.
- **Trigger / entry:** any customer-facing need — from W5 (delay), W6 (missing doc), W8 (dispute).
- **Key states:** detect a comms need (draft everything) → send → track commitments.
- **Tools:** A1 email, A18 notification (A2 SMS planned).
- **Evidence inputs:** message-delivery receipt; never relays unsanitized inbound.
- **Messages:** the sends themselves (`SEND_OUTBOUND`).
- **Approvals / effects:** **never sends unapproved initially (`HUMAN_APPROVAL_REQUIRED`)**; outbound admission-controlled.
- **Verification:** delivery receipt + commitment tracked.
- **Exceptions:** undeliverable; injection attempt.
- **Closure:** message delivered + commitment tracked — **not** a send.
- **Related phases:** P9 → P12. · **Autonomy:** never send unapproved initially → autonomy graduates for specific low-risk templates only.

### W11 — Claims *(OS&D)*
- **Purpose:** an OS&D case reaches a referenced resolution with a financial adjustment — the human makes the legal call.
- **Trigger / entry:** POD OS&D notation (W6), damaged-vs-normal conflict (W5), or customer report.
- **Key states:** open case → assemble packet + timeline → resolve → financial adjustment (full pipeline).
- **Tools:** reads for assembly; compensation path for adjustment.
- **Evidence inputs:** assembled packet + timeline; deadlines as Expectations.
- **Messages:** to carriers/customers/warehouses/insurers/internal.
- **Approvals / effects:** settlement/credit **`HUMAN_APPROVAL_REQUIRED`**; adjustment is gated compensation, never a rewrite of a settled invoice/payable.
- **Verification:** `RESOLVED{decision_ref}` + durable financial adjustment.
- **Exceptions:** missing evidence; disputed liability; deadline risk.
- **Closure:** `RESOLVED{decision_ref}` + financial adjustment created.
- **Related phases:** P13. · **Autonomy:** assemble/recommend automatic; **filing & settlement never autonomous — permanent human authority.**

## 3. Capability → loop coverage (all requested areas represented)

| Requested capability | Owning loop(s) | Notes |
|---|---|---|
| Sales / quote / customer intake | **W1** | incl. order/load creation |
| Load creation / order entry | **W1** | W1→W2 handoff creates `COVER_LOAD` |
| Carrier sourcing & tendering | **W2** | gated by W3 |
| Dispatch & driver communication | **W4** (+W5 check-calls, W10 sends) | **thin:** driver SMS/voice ops (A2/A3) — §4 |
| Track & trace | **W5** | GPS/ELD via A9 (vendor-agnostic) |
| Appointment scheduling | **W4** | **thin:** port/rail/warehouse portals — §4 |
| Exception management | **W7** | cross-cutting |
| Document operations | **W6** | — |
| Delivered Load Closure | **W5/W6/W7/W8/W10** | the wedge outcome; no single loop |
| Carrier invoice audit / AP | **W9** | — |
| Customer billing / AR | **W8** | — |
| Claims / OS&D | **W11** | opened from W6/W5 |
| Carrier compliance & onboarding | **W3** | **thin:** W-9/agreement packet — §4 |
| Customer service | **W10** + conversational layer | **platform surface** — §4 |
| Internal ops & management | *(platform, not a loop)* | **platform surface** — §4 |

## 4. Gap analysis — exact gaps, and the smallest coherent handling

Three loop-internal **elaboration gaps** and two **platform-surface** capabilities were found. **None
requires a new loop, a rename, or a scope change to an existing loop.** Each is recorded as debt for
its owning phase — not silently expanded here.

| Gap | Kind | Where it belongs | Smallest coherent handling | Owning phase |
|---|---|---|---|---|
| **Driver-directed SMS/voice** | loop-internal (thin) | **W4/W5/W10** + adapters **A2/A3** | activate the already-specified SMS (A2) and voice (A3) adapters as channels for the existing `SEND_OUTBOUND` steps; add driver-addressed message routing. **No new loop.** | P9 (comms ingestion) / P12 (supervised sends) |
| **Appointment port/rail/warehouse specificity** | loop-internal (thin) | **W4** + adapter **A8** + mode-specific **UC-30** | specialize A8 per facility class as mode-specific evidence arrives; keep the generic W4 appointment step. **No new loop.** | P13 (+ UC-30 validation) |
| **Carrier onboarding packet (W-9 / signed agreement)** | loop-internal (thin) | **W3** + **UC-05** | decompose onboarding-packet collection into W3 steps as design-partner rules are recorded. **No new loop.** | P13 |
| **Customer service** | platform surface | **W10** + conversational layer **UC-33** ([`ADR-019`](../architecture/decisions/ADR-019-conversational-operations-layer.md)) | represent as a conversational/oversight surface over W10 and shared state — **not a separate loop and not a disconnected chatbot truth source.** | P11 |
| **Internal ops & management** | platform surface | **UC-23** + control plane [`ADR-017`](../architecture/decisions/ADR-017-tenant-and-integration-lifecycle.md) + conversational [`ADR-019`](../architecture/decisions/ADR-019-conversational-operations-layer.md) | represent as a cross-cutting oversight/reporting surface backed by the same events/evidence — correctly **not** one of the eleven operational-execution loops. | P11 |

## 5. Conclusion — no loop revision proposed

The eleven loops **fully cover quote-to-cash operational execution.** Dispatch/driver-comms,
track-and-trace, appointments, carrier sourcing, claims, billing, AP, AR and their communications
are each owned by an existing loop (W1–W11). Customer service and internal ops/management are
**platform surfaces** correctly outside the eleven. The three thin specifications are **elaboration
debt inside existing loops/adapters**, scheduled to their owning phases — **not** new scope.

Therefore this document **proposes no addition, rename, split, or merge of any loop.** Should the
founder ever decide a twelfth loop is warranted, it is a deliberate product decision requiring an
explicit change to [`PRODUCT.md §6`](../../PRODUCT.md) and [`workflows/registry.md`](../specifications/workflows/registry.md)
— and this document is not that change.

## 6. Does the W1–W11 loop model fully represent the AI-workforce vision?

**Verdict: the eleven loops fully represent the *operational-execution* layer of the vision — but
the AI-operations-team vision is broader than the loops, and the loops alone were never meant to
carry all of it. The vision is a three-layer model plus two cross-cutting surfaces:**

| Layer | What it is | Where it lives | Adequate? |
|---|---|---|---|
| **A — Shared operating system (the spine)** | one work-item/load state · knowledge · evidence/provenance · policy/approvals · communications history · safety & effect boundary · audit trail | [`PRODUCT.md §7–§9`](../../PRODUCT.md), the ADRs, the entity/event specs | **Yes — canonical and adequate.** |
| **B — The eleven operational loops (W1–W11)** | the trigger→accountable-closure execution decomposition | [`operating-model.md`](operating-model.md), [`workflows/`](../specifications/workflows/) | **Yes — adequate; no revision needed.** Every operational function in the founder's teammate list maps to a loop (or to a surface in D). |
| **C — Role-based AI teammates** | the *presentation* personas (AI dispatcher, AI AP clerk, AI operations manager, …) that operate loops + surfaces on the spine | implicit today (role owners in the operating model; `user_role` in the coverage matrix; "not a collection of disconnected agents" in [`PRODUCT.md §12`](../../PRODUCT.md)); **now made explicit in [`FREIGHT-OPERATING-VISION.md §3`](FREIGHT-OPERATING-VISION.md)** | **Under-formalized as an explicit concept** — see the recommendation below. |
| **D — Cross-cutting platform surfaces** | customer service (reactive Q&A/requests) and operational management & reporting (oversight/aggregation) | W10 + conversational layer ([`ADR-019`](../architecture/decisions/ADR-019-conversational-operations-layer.md)); control plane ([`ADR-017`](../architecture/decisions/ADR-017-tenant-and-integration-lifecycle.md)); UC-23/UC-33 | **Yes — adequate as surfaces.** Forcing them into loops would mis-model them (they are not obligation-closure workflows). |

**So: W1–W11 does not, by itself, represent the whole vision — but that is by design.** The missing
piece is **not a loop; it is the explicit teammate/role layer (C).** Modeling customer service or
operational management as new W-loops would violate the loop definition (a loop brings *one freight
obligation* from trigger to accountable closure) and would be exactly the "silently forcing the
vision into inadequate loops" failure this analysis is meant to avoid.

### The smallest coherent revision — FOUNDER-APPROVED (no loop change)

**No loop is added, renamed, split, or merged.** The single coherent change the vision called for
was to **formalize the role-based-teammate layer (C) as a first-class, named product concept** — a
thin mapping of *role → loop(s)/surface → capability → autonomy ceiling* over the existing spine,
**not** a new workflow family. The founder reviewed this and **approved it**:

1. **Elevate the teammate/role layer into the root product authority** — **DONE / APPROVED.** The
   coordinated-AI-workforce model and the teammate roles are now stated first-class in
   [`PRODUCT.md §4`](../../PRODUCT.md) (additive; changes no loop and no status) and fully in
   [`FREIGHT-OPERATING-VISION.md §3`](FREIGHT-OPERATING-VISION.md).
2. **Disposition of the two cross-cutting surfaces** — **APPROVED.** **Customer service** and
   **operational management & reporting** remain **platform surfaces (D), not loops.**
3. **(Optional, later)** a lightweight canonical *role registry* artifact if the teammate layer ever
   needs machine-checkable role→loop coverage — deferred; not required to represent the vision.

**Founder-approved outcome: the three-layer model (A spine · B loops W1–W11 · C teammates) is
adopted with no change to W1–W11.** The eleven loops are the right execution decomposition; the
vision is completed by making the teammate layer explicit (documentation), not by revising the
loops.
