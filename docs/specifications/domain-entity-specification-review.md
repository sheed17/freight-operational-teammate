# Freight-Domain Entity Specification Review — Hostile

**Subject:** `docs/specifications/domain-entities/` — 40 entities (11 family files) + `registry.md`.
**Method:** 30 hostile domain scenarios (entities · bindings · authority-per-field · evidence · lifecycle · foundational Work Items/Expectations/Conflicts/Approvals/Events · effects blocked/allowed · compensation · final state · human action · test) + a mechanical sweep.
**Date:** 2026-07-14 · **No frozen document modified.**

---

## PART 1 — THE 30 HOSTILE SCENARIOS *(condensed traces; each names its test)*

| # | Scenario | Trace & deterministic result |
|---|---|---|
| **1** | Order → two loads | Customer Order `CONVERTED` creates **2 Brokerage Loads** (Order→Load is 1:N via the FK on Load; provisional 1:1 migration path pre-specified). Neither identity collapsed. ⇒ `test_one_order_can_convert_to_two_loads`. |
| **2** | Load re-powered across two movements | Movement A `FELL_OFF` ⇒ Load re-covers via **Movement B** (Load→Movement 1:N). The Load's `commit_key` for billing is unchanged; the buy side is per-Movement. ⇒ `test_fell_off_recovers_via_new_movement`. |
| **3** | One movement, several legs | Movement 1:N Leg (confirmed). ⇒ `test_movement_can_have_several_legs`. |
| **4** | Qualified at tender, suspended before pickup | Tender valid at `evaluated_at`; a **fresh Qualification Decision at booking** finds `SUSPENDED` ⇒ **BOOK_CARRIER blocks** (CD-2, qualification not sticky). Human may override with approval+policy. ⇒ `test_suspension_blocks_later_booking`. |
| **5** | Quote accepted after market evidence expired | The `market_rate_evidence.expires_at` passed ⇒ the sell basis is `stale` ⇒ **re-price or human-confirm** before commit (a `stale` field is not `consistent`). ⇒ `test_accept_after_evidence_expiry_requires_reprice_or_human`. |
| **6** | Rate Con conflicts with phone-agreed buy | A new Quote/Offer **version** + `ConflictRaised` (CD-16) ⇒ human resolves; **no silent overwrite**. ⇒ `test_ratecon_conflict_versions_not_overwrites`. |
| **7** | Customer changes pickup address after assignment | Stop `RESCHEDULED`; if mileage/buy changes ⇒ `ConflictRaised` on the buy rate + a Work Item. ⇒ `test_stop_reschedule_after_assignment`. |
| **8** | Doc says load# X but belongs to another customer | The load# is `MODEL_EXTRACTED` evidence, matched deterministically **within `(tenant, customer)`**; a cross-customer match is `AMBIGUOUS` ⇒ human, **never auto-bound** (CD-6). ⇒ `test_document_cross_customer_match_is_ambiguous`. |
| **9** | One POD covers two loads | Document 1:N Load binding — **both bound** deterministically, neither silently. ⇒ `test_one_pod_two_loads_binds_both`. |
| **10** | POD illegible | Document `ILLEGIBLE` ⇒ Exception ⇒ blocks the Packet `COMPLETE` ⇒ blocks billing (CD-3). ⇒ `test_illegible_blocks_billing`. |
| **11** | Invoice prepared without a customer-required lumper receipt | Document Requirement (customer-specific) unmet ⇒ Packet `INCOMPLETE` ⇒ **Invoice not `ELIGIBLE`** (CD-3). ⇒ `test_customer_specific_requirement_gates_invoice`. |
| **12** | Carrier invoice detention, only a counterparty assertion of approval | Accessorial `SUPPORTED` but **no Accessorial Authorization** ⇒ `unconfirmed` ⇒ **Payable blocked** (CD-5); the assertion ⇒ `CounterpartySelfAuthorizationDetected` (fraud). ⇒ `test_detention_with_only_counterparty_assertion_blocks`. |
| **13** | Human confirms the undocumented detention authorization | An authenticated human asserts ⇒ Accessorial Authorization `CONFIRMED` `OWNER_ASSERTED` with a `decision_ref` (`PERMANENT_HUMAN_ASSERTION_REQUIRED`). Now billable. ⇒ `test_human_can_confirm_undocumented_detention`. |
| **14** | Payable paid to the wrong factoring company | `remittance_party` is a verified `OWNER_ASSERTED`/documented binding, revalidated at the pay checkpoint ⇒ a wrong/unverified factor **blocks**. ⇒ `test_remittance_party_verified_before_pay`. |
| **15** | Appointment moved after dispatch | Appointment `RESCHEDULED` + re-notify Work Item + Expectation re-versioned. ⇒ `test_appointment_move_after_dispatch_reschedules`. |
| **16** | Tracking says delivered but POD missing | Tracking `DELIVERED` is a **claim** (CD-8); the POD Expectation stays open ⇒ **cannot bill** (CD-3). ⇒ `test_delivered_vs_missing_pod_blocks_billing`. |
| **17** | POD says damaged, tracking says normal | `ConflictRaised` (readback-vs-claim) ⇒ opens an **OS&D Case** + human. ⇒ `test_pod_damage_vs_tracking_raises_conflict`. |
| **18** | Onboarded once, insurance expires before a later load | The Compliance Record `EXPIRED` (durable timer) ⇒ the later Qualification Decision re-evaluates ⇒ **NOT_QUALIFIED** (CD-2, onboarding not permanent). ⇒ `test_expired_insurance_forces_requalification`. |
| **19** | Customer short-pays | Payment Application `SHORT` ⇒ Invoice `SHORT_PAID` + residual AR + Conflict/dispute; **never silently closed** (CD-10). ⇒ `test_short_pay_leaves_residual_ar`. |
| **20** | Credit and rebill for the same load | The credit is a **Compensation** (gated); the rebill is a **distinct action class** (`REISSUE_INVOICE`, new commit_key) ⇒ **no double-bill** (ADR-009 V8). ⇒ `test_credit_and_rebill_are_distinct_effects`. |
| **21** | Load cancelled after carrier acceptance | Assignment `CANCELLED` + possible TONU Accessorial; Load `CANCELLED`/`TONU`. ⇒ `test_cancel_after_acceptance`. |
| **22** | Carrier falls off after pickup appointment confirmed | Movement `FELL_OFF` ⇒ re-cover via a new Movement (=#2). ⇒ `test_fell_off_after_appointment`. |
| **23** | Claim opened after invoice already paid | Invoice stays `PAID` (immutable, GR-12); the OS&D resolution creates a **new adjustment** (credit/debit), never a rewrite (CD-10 history). ⇒ `test_claim_after_paid_invoice_creates_adjustment_not_rewrite`. |
| **24** | Binding correction invalidates a completed invoice | `ClaimCorrected` propagates ⇒ the invoice's evidence evaporates ⇒ **Compensation raised** (gated), the paid invoice retained (CD-7, F-17). ⇒ `test_binding_correction_raises_compensation`. |
| **25** | Two TMS records → one Brokerage Load | External Entity Mapping 1:N (Load ← two external records); identity not collapsed (CD-19). ⇒ `test_two_tms_records_one_load`. |
| **26** | One TMS record → two business entities | Mapping is per-`(external_system, external_id, field-scope)` ⇒ two entities map into one row without collapse. ⇒ `test_two_entities_one_tms_row_no_collapse`. |
| **27** | Same carrier under MC, DOT, email, factoring alias | Deterministic confirmation on **MC or DOT**; alias/email are candidate signals only; a name match never confirms (GR-8). ⇒ `test_carrier_confirmed_on_mc_or_dot_not_alias`. |
| **28** | Same org is Customer and Carrier | **One Organization**, roles per-transaction (party-role model); no duplicate record. ⇒ `test_same_org_two_roles_one_record`. |
| **29** | Late Rate Con contradicts a completed payable | `ConflictRaised` (a payable was `VERIFIED` on old terms) ⇒ human + possible Compensation; a Financial Reconciliation `DISCREPANT`. ⇒ `test_late_ratecon_vs_completed_payable_raises_conflict`. |
| **30** | Event arrives for an entity with no external mapping | **Parked** in `pending_references`, drained on mapping creation; TTL ⇒ Exception (M-26). ⇒ `test_event_before_mapping_is_parked`. |

> ### **Every scenario resolves to one deterministic domain result, using ONLY foundational machinery — a Conflict blocks, an Expectation goes indeterminate, a Compensation is raised, a human is asked. No scenario required a new primitive.**

---

## PART 2 — MECHANICAL CONSISTENCY REVIEW

| Check | Result |
|---|---|
| Canonical names match the Semantic Model | ✅ Load family (Order/Load/Movement/Leg/Stop), Customer/Carrier, Invoice=AR / Payable=AP, Rate Con=buy, POD gate — all per the Semantic Model. |
| **No generic `Load` collapse** | ✅ Order/Load/Movement/Leg/Stop distinct; **no `Load` entity**; TMS row only via External Entity Mapping. |
| No duplicated party records by role | ✅ one Organization, per-transaction roles (party-role model). |
| No duplicate financial concepts | ✅ Invoice (IN) / Payable (OUT) / Payment Application / Reconciliation distinct. |
| No Accessorial Charge/Authorization collapse | ✅ E28 vs E29 distinct; the Authorization gates the Charge. |
| No whole-record authority where field-level required | ✅ Customer, Carrier, Compliance, Appointment, Tracking, Document, Payment are explicitly **field-level**. |
| No `MODEL_INFERRED` consequential dependency | ✅ ETA, fraud signal, model-suggested rate are `MODEL_INFERRED` and **surfaced, never gating** (GR-8). |
| Lifecycle states globally consistent | ✅ 23 `L-*` contracts reuse the global transition contract + GR-1…GR-17; no new state-machine semantics. |
| Relationships/cardinalities compatible | ✅ load-family table (confirmed vs provisional, migration path each); no contradictions. |
| Every FK direction clear | ✅ stated (Load.`order_id`, Movement.`load_id`, Leg.`movement_id`, Stop.`leg_id`, Appointment.`stop_id`, …). |
| Every monetary value has currency + direction | ✅ Money Model (`amount_minor`+`currency`+`money_direction`+`money_kind`); CD-17. |
| Every timestamp has timezone semantics | ✅ UTC + originating tz; facility-local windows (F-25). |
| Every identity has collision rules | ✅ per entity (customer name HIGH, MC/DOT trusted, trailer# recycled, load_ref tenant-scoped, …). |
| Every consequential record has provenance | ✅ field-level `provenance_class`; evidence chains (CD-18). |
| Every lifecycle transition maps to an event | ✅ mapped to the frozen Event Registry (registry §Domain→Event); **no domain event invented**. |
| No event used as a command | ✅ inherited (ER-1). |
| No foundational entity re-created under a domain name | ✅ Document reuses Evidence+Binding; Message reuses Observation; OS&D `Claim` ≠ Identity Binding `Claim` (qualified). |
| No safety invariant relies on prose | ✅ each CD-1…CD-20 maps to a foundational mechanism (registry table). |
| Every hostile scenario has one deterministic result | ✅ Part 1. |

---

## PART 3 — FINDINGS

**1. Domain entities created:** **40** (E1–E40).
**2. Relationship count:** the load-family table (6) + party/asset/commercial/document/financial/compliance FKs — **~40 canonical relationships**, each with an explicit FK direction and cardinality (confirmed or provisional-with-migration).
**3. Lifecycle count:** **23** `L-*` contracts (≥ the 22 required).
**4. State & transition count:** ~120 domain states across the 23 lifecycles; transitions reuse the global contract (not re-enumerated at foundational depth — these are domain lifecycle *contracts* per the brief, riding GR-1…GR-17).
**5. Provisional cardinalities:** **2** — Order→Load and Load→Movement (both 1:1 provisional, 1:N migration pre-specified, **NEEDS VALIDATION**). Identity never collapsed.
**6. Identity risks:** customer-name fuzz, carrier multi-alias, trailer# recycling, load_ref cross-TMS/tenant, shared inboxes, factoring alias — all with deterministic-confirmation rules; **confidence ranks, never confirms**.
**7. Authority conflicts:** **NONE** — authority is field-level; a record with fields from FMCSA + TMS + owner + model is explicitly modeled.
**8. Financial-model conflicts:** **NONE** — IN/OUT/QUOTED explicit; buy/sell distinct; margin computed; AR/AP/Payment/Reconciliation distinct.
**9. Missing/ambiguous domain concepts:** **NONE** for the required 40; the party-role model, factoring redirection, and the charge/authorization split close the historically-fuzzy areas.
**10. Required additions to the formal Event Registry:** ### **NONE.** Every domain lifecycle transition maps to an existing event contract (registry §Domain→Event). Domain state names are entity attributes; their transitions emit platform events. **The frozen Event Registry is unchanged.** *(If a later adapter phase surfaces a genuine gap, it is collected here provisionally and amended under change control — not now.)*
**11. Remaining `NEEDS VALIDATION`:** the 2 provisional cardinalities; per-customer document requirements & accessorial matrices; equipment-type/doc-type/charge-type enums (all additive); market-rate & extraction confidence windows; factoring/bank/tracking feed sources; human-reserved trust decisions; reopen policy (V1); reissue action class (V8). ### **All fail-closed; none blocks.**
**12. Higher-level amendments required:** ### **NONE.** No freight-domain requirement needed a new primitive; every one was expressible with the 15 foundational entities + the frozen events. **No genuine contradiction was exposed.**
**13. Deviation flagged:** the 40 entities are specified in **11 family files** (a navigability decision), each entity complete and distinct, indexed in `registry.md`. This groups files, never entities. *(Stated openly per the standing discipline.)*

---

## VERDICT

> # **READY FOR ADAPTER CONTRACT SPECIFICATION ENGINEERING**
>
> **Evidence:** 40 distinct freight-domain entities recognizable to a broker, each independent of any TMS/portal/API; the load family preserved (no generic `Load`, identity never collapsed, provisional cardinalities with pre-specified 1:N migration paths); field-level authority throughout (a record carries FMCSA + TMS + owner + model fields, each with its own `provenance_class`, `MODEL_INFERRED` never gating, `OWNER_ASSERTED` never machine-recomputed); a money model with explicit IN/OUT/QUOTED direction and kind on every financial record and the buy/sell split; the accessorial charge-vs-authorization distinction with the undocumented case reserved to `PERMANENT_HUMAN_ASSERTION_REQUIRED`; 23 lifecycle contracts that reuse the global transition machinery and invent no new state semantics; 20 cross-domain invariants each bound to a foundational mechanism, none resting on prose; and 30 hostile scenarios each resolving to one deterministic result using only foundational machinery. **No new platform primitive was introduced; no addition to the frozen Event Registry is required; no higher-level amendment is needed.**
>
> **Adapter Contract Specification Engineering may begin,** taking these domain entities as the business vocabulary an adapter reads/writes, the field-level authority table as what each integration is authoritative for, the External Entity Mapping as the sole bridge to external ids, and the verification modes (readback/receipt/unverifiable) as the per-operation contract each adapter must declare.

*Not started (per instruction): adapter contracts, workflow specs, API specs, operational-loop acceptance specs, migration plans, PRODUCT/ARCHITECTURE/CLAUDE. No implementation code.*
