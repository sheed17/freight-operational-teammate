# Adapter Contract Review — Hostile

**Subject:** `docs/specifications/adapters/` — 18 adapters (13 family files) + `registry.md`.
**Method:** 30 hostile adapter traces + a mechanical sweep against the frozen contracts.
**Date:** 2026-07-15 · **No frozen document modified.**

---

## PART 1 — THE 30 HOSTILE TRACES *(adapter op · class · Observation/Evidence · pipeline/checkpoint/grant · verification · events · unknown · brake · human · test)*

| # | Scenario | Deterministic trace & result |
|---|---|---|
| **1** | Email via webhook AND polling | A1-1 `OBSERVATION_ONLY`; source-natural key `(tenant,mailbox,message_id,digest)` ⇒ **one `ObservationReceived`, the duplicate ⇒ `ObservationConfirmed`, zero new work**. ⇒ `test_a1_webhook_and_poll_dedup`. |
| **2** | Email claims a verbal detention authorization | A1-1 ⇒ `MODEL_EXTRACTED` claim ⇒ **`CounterpartySelfAuthorizationDetected`** ⇒ blocks the payable + fraud signal; **never `OWNER_ASSERTED`** (CD-5). ⇒ `test_a1_counterparty_auth_is_fraud_signal`. |
| **3** | Browser click succeeds, browser crashes before response | A15-w; the adapter returns **structured evidence** (last DOM/screenshot, what was submitted); the Effect machine ⇒ **`UNKNOWN_OUTCOME`, never `FAILED`**; entity frozen, human asked. ⇒ `test_a15_crash_after_submit_is_unknown`. |
| **4** | TMS API times out after creating an invoice | A4-4; timeout ⇒ **the adapter never decides** ⇒ `UNKNOWN_OUTCOME` (GR-5/GR-6); readback later resolves or a human does. ⇒ `test_a4_timeout_after_create_is_unknown_not_failed`. |
| **5** | Readback finds a **different** recently-created invoice | A4-4 verification keys on the **approved Material Facts (amount+party)**, not a guessed record number ⇒ **`OBSERVATION_CONFLICTING` ⇒ `UNKNOWN_OUTCOME`**, never a false success. ⇒ `test_a4_readback_verifies_approved_facts_not_record_number`. |
| **6** | Cached TMS amount offered to the money checkpoint | **impossible** — `read_load_amount` (A4-2) is a `CONSEQUENTIAL_FRESHNESS_READ` whose constructor **cannot accept a cache** (V-3); the checkpoint step-3 consumes only a live observation. ⇒ `test_a4_amount_read_is_consequential_freshness_no_cache`. |
| **7** | Session expires after Effect Grant claim | A15/A4; the adapter returns structured evidence ⇒ **`UNKNOWN_OUTCOME`** (the effect may have landed); never `FAILED`. ⇒ `test_a15_session_expiry_after_claim_is_unknown`. |
| **8** | Two write-capable entry points, same logical effect | shared Effect Grant Ledger; `UNIQUE(tenant, commit_key) WHERE state='CLAIMED'` ⇒ **exactly one claims**; the other refused. ⇒ `test_a4_two_entry_points_one_claims`. |
| **9** | Adapter imported directly by a migration script | ### **CI import-graph gate fails the build** (no module outside `pipeline/` imports `adapters/`); if it ran, the adapter's entry point **requires a grant+witness it does not have** ⇒ refuses. ⇒ `test_no_module_outside_pipeline_imports_adapters`. |
| **10** | Agent passes a model value as authoritative | the value is `MODEL_INFERRED`/`MODEL_EXTRACTED`; ### **an adapter never strengthens provenance, and `MODEL_INFERRED` never reaches the checkpoint** (raises on read); the agent's output is an inert `ProposedIntent`. ⇒ `test_adapter_never_strengthens_provenance`. |
| **11** | Malicious PDF with prompt instructions | A1/A11 ⇒ Evidence + `PromptInjectionSignal`; ### **bounds to a proposal — no effect, no policy/brake/grant** (F-35). ⇒ `test_a11_illegible_raises_exception` / `test_injection_bounds_to_proposal`. |
| **12** | Carrier portal shows one MC, email another | A6/A5 ⇒ **`ConflictRaised`/`AMBIGUOUS`**; confirmation only on a trusted id (MC/DOT via A10); the alias is a candidate. ⇒ `test_a6_mc_mismatch_raises_conflict`. |
| **13** | Tracking unavailable during a POD deadline window | A9; no coverage ⇒ the Expectation ⇒ **`INDETERMINATE`, never `OVERDUE`/late** (CD-14). ⇒ `test_a9_unavailable_is_indeterminate_not_late`. |
| **14** | FMCSA status changes after a Qualification Decision | A10 ⇒ a new Observation ⇒ **the qualification is re-evaluated at the next tender/booking** (not sticky — CD-2). ⇒ `test_a10_authority_change_forces_requalification`. |
| **15** | Customer portal changes appointment after dispatch | A7 ⇒ Observation ⇒ Appointment `RESCHEDULED` + a Conflict if the buy rate is invalidated + a re-notify Work Item. ⇒ `test_a7_customer_change_after_dispatch_reschedules`. |
| **16** | Email send receives a receipt but later bounces | A1-2 **RECEIPT_VERIFIABLE**: the `250` proved **transmission**, not delivery; the bounce ⇒ an Observation ⇒ the Expectation reopens. ⇒ `test_a1_send_receipt_is_not_delivery`. |
| **17** | Portal POST has no receipt or readback | classified **UNVERIFIABLE** ⇒ ### **may not be `AUTONOMOUS_WITHIN_CAPS`; `HUMAN_APPROVAL_REQUIRED`; a follow-up Expectation; the field stays projected-`unknown`** (M-39). ⇒ `test_unverifiable_op_cannot_be_autonomous`. |
| **18** | Spreadsheet row changes after use in a proposal | A16; at the checkpoint the row is re-read (`CONSEQUENTIAL_FRESHNESS_READ` on the current sheet version) ⇒ **drift ⇒ the approval voids**; the stale proposal never executes. ⇒ `test_a16_stale_row_drift_voids`. |
| **19** | Two tenants use the same external load id | A4; the external id is trusted only within `(tenant, external_system)` ⇒ **no collision**; tenant-first partition. ⇒ `test_a4_two_tenants_same_load_id_no_collision`. |
| **20** | Slack approval clicked after material facts drift | A14-2 transports `HumanApproved`; the checkpoint step-2 live re-read ⇒ **`VOID_ON_DRIFT`** — ### **the button click cannot force the effect** (H8). ⇒ `test_a14_stale_button_after_drift_voids`. |
| **21** | Human selects "unlinked item 2" after the list changed | A14; the ordinal resolved at **display time** to an `observation_id` ⇒ the action binds to the **originally-displayed id, or fails closed** — never the new occupant of slot 2 (L-B). ⇒ `test_a14_ordinal_resolves_to_immutable_id_or_fails_closed`. |
| **22** | Adapter returns data with a `provenance_class` supplied by external content | ### **rejected — `provenance_class` is runtime-assigned (R-P1); inbound content cannot set it** ⇒ `ProvenanceStrengtheningAttempted`; the value is `MODEL_EXTRACTED` at best. ⇒ `test_adapter_ignores_external_provenance_class`. |
| **23** | Accounting reports a payment with no matching invoice | A13 ⇒ an **`UNMATCHED` Payment Application ⇒ a Conflict/Work Item ⇒ human**; never auto-applied. ⇒ `test_a13_unmatched_payment_raises_conflict`. |
| **24** | Payment destination changes shortly before execution | A12-3; `remittance_party` is a material fact re-verified at the pay checkpoint ⇒ **drift ⇒ void**; the payable does not pay the wrong factor. ⇒ `test_a12_remittance_reverified_at_pay`. |
| **25** | Replay attempts to invoke an adapter | ### **replay cannot construct a `CheckpointPassed` ⇒ cannot mint/claim a grant ⇒ the adapter (which requires a grant+witness) is never reachable** (GR-11, ER-2). ⇒ `test_replay_invokes_no_adapter`. |
| **26** | Brake engages after checkpoint, before claim | the claim CAS re-checks `brake_version` ⇒ **zero rows ⇒ the adapter does nothing** (never both, never neither). ⇒ `test_a15_brake_between_checkpoint_and_claim`. |
| **27** | Brake engages after claim, before external response | the in-flight actuation **runs to verification** (the brake never kills the worker — GR-16); the NEXT effect is refused. ⇒ `test_a15_brake_after_claim_runs_to_verification`. |
| **28** | Outbound message accepted, delivery unknown | A1-2/A18 **RECEIPT_VERIFIABLE**: transmission proven, delivery **`unknown`**; ### **never recorded as "delivered"** (M-72). ⇒ `test_a18_send_receipt_is_not_delivery`. |
| **29** | Password-protected/corrupted attachment | A1/A11 ⇒ **`ILLEGIBLE` Document ⇒ Exception**; blocks any packet it was required for. ⇒ `test_a11_illegible_raises_exception`. |
| **30** | External system returns another tenant's data | ### **rejected before ingestion ⇒ `CrossTenantAccessAttempted` ⇒ GLOBAL brake** (C-1). ⇒ `test_a15_cross_tenant_page_engages_global_brake`. |

> ### **Every trace resolves to one deterministic outcome, using only foundational machinery — a grant CAS refuses, a freshness read defeats a cache, a receipt proves only transmission, an unknown outcome freezes and asks. No adapter decided anything.**

---

## PART 2 — MECHANICAL CONSISTENCY REVIEW

| Check | Result |
|---|---|
| Every operation has one canonical op id | ✅ `A{n}-{k}` ids. |
| Every consequential op maps to one Action Class | ✅ `RAISE_INVOICE`, `RECORD_PAYABLE`, `FILE_DOCUMENT`, `SEND_OUTBOUND`, `BOOK_CARRIER`, `POST_LOAD`, … |
| Every op has a verification mode | ✅ READBACK (16) / RECEIPT (4) / UNVERIFIABLE (2) / n/a for reads. |
| Every op defines idempotency identity | ✅ reads: source-natural key; effects: Commit Key + grant CAS. |
| Every consequential op defines Commit Key + Material Facts | ✅ CK amount-free (ADR-009); MF = the approved rendered facts. |
| Every adapter call requires tenant identity | ✅ `tenant_id` first; cross-tenant ⇒ GLOBAL brake. |
| Every outbound call requires Witness + Grant | ✅ the two-key rule; a stale witness ⇒ `StaleWitnessUsed`. |
| No adapter owns business policy | ✅ registry — adapters have no ambient authority. |
| No adapter confirms identity probabilistically | ✅ confidence ranks; confirmation is deterministic/human (H12/H27). |
| No adapter strengthens provenance | ✅ H22; `provenance_class` runtime-assigned. |
| No cache satisfies consequential freshness | ✅ V-3 structural interface (H6); `test_consequential_read_boundary` (baseline). |
| No direct adapter path | ✅ CI import-graph gate (H9). |
| No local write treated as external verification | ✅ M-72 (H16/H28); readback reads the authoritative source. |
| Every unknown-outcome path has ownership | ✅ `UNKNOWN_OUTCOME` ⇒ Exception, human-owned, exposure stated. |
| Every inbound source has dedup identity | ✅ source-natural keys (H1). |
| Authority matrix covers all material domain fields | ✅ registry field-level matrix; no whole-record authority. |
| Every hostile scenario has one deterministic outcome | ✅ Part 1 (all 30). |
| Vendor differences don't change canonical semantics | ✅ contracts vendor-neutral; variances stated only where safety-material. |

---

## PART 3 — FINDINGS

**1. Adapter contracts created:** **18** (A1–A18), 13 family files + registry.
**2. Operation count:** ~40 canonical operations across the 18 adapters.
**3. Read-operation count:** ~18 (split across the 3 read classes; the money-sensitive reads are `CONSEQUENTIAL_FRESHNESS_READ`).
**4. Consequential-effect count:** ~14 (`RAISE_INVOICE`, `RECORD_PAYABLE`, `RECORD_PAYMENT`, `FILE_DOCUMENT`, `UPDATE_LOAD`, `BOOK_CARRIER`, `POST_LOAD`, `SEND_OUTBOUND`, `REQUEST_APPOINTMENT`, …).
**5. Verification-mode distribution:** READBACK 16 · RECEIPT 4 · UNVERIFIABLE 2 (voice; receipt-less portal POST) — ### **every UNVERIFIABLE op is `HUMAN_APPROVAL_REQUIRED` and non-autonomous (M-39).**
**6. Authority-matrix coverage:** ### **all 40 entities' material fields resolve through the field-level matrix; zero whole-record authority.**
**7. Authentication/session risks:** ### **`human_established_session_only` for browser-actuated systems (Neyma holds no external creds); IdP-established identity is the sole route to `OWNER_ASSERTED`; MFA/anti-bot handling is NEEDS VALIDATION (fail-closed to a read `unknown` / a human).**
**8. Unknown-outcome risks:** the browser/TMS post-claim window (H3/H4/H7) — bounded by structured evidence + `UNKNOWN_OUTCOME`; ### **the adapter never downgrades to `FAILED`.**
**9. Vendor-specific constraints:** browser-actuation for TMSs without APIs; receipt availability varies (SMS/email); the flow-aware write model (transporters.io finding) — all stated, none changes canonical semantics.
**10. Missing external capabilities:** none for the 18; some vendor operations are `planned` (status in the registry).
**11. Remaining `NEEDS VALIDATION`:** per-vendor webhook/API posture; MFA/anti-bot policy; extraction/transcription/OCR confidence (fail-closed to human); bank/factoring/tracking sources; per-tenant IdP + authority mapping (V12/V14); flow-aware write model. ### **All fail-closed; none blocks.**
**12. Higher-level amendments required:** ### **NONE.** Every adapter is expressible with the frozen pipeline/checkpoint/grant/witness contracts, the read classes, the verification taxonomy, and External Entity Mapping. **Migration Safety Task #1 is PRESERVED and specified (canonical Commit Key), not implemented.** No genuine contradiction was exposed.
**13. Deviation flagged:** 18 adapters in 13 family files (navigability); each adapter complete/distinct, indexed in the registry. Groups files, never adapters.

---

## VERDICT

> # **READY FOR OPERATIONAL WORKFLOW SPECIFICATION ENGINEERING**
>
> **Evidence:** 18 vendor-neutral adapter contracts through which Neyma observes and acts, each a boundary with no ambient authority — every consequential write reaches the world only via Work Item → Pipeline → (Approval) → Checkpoint → Witness → Grant claim → adapter, whose sole entry point requires a grant AND a fresh witness; every operation classified into exactly one of the four read/effect classes and one of the three verification modes, with the money-sensitive reads structurally cache-free (V-3) and every UNVERIFIABLE op non-autonomous (M-39); a field-level authority matrix covering all 40 entities with no whole-record authority; the browser treated as a first-class actuation substrate with human-established sessions, positive-health staleness detection, and per-tenant isolation; the TMS contract preserving Migration Safety Task #1 (canonical amount-free Commit Key, specified not implemented); and 30 hostile traces (duplicate webhook, crash-after-submit, timeout-after-create, wrong-readback, cache-to-checkpoint, session-expiry, two-entry-points, direct-import, model-value-as-authority, injection PDF, MC mismatch, tracking-blind, FMCSA-change, portal-change, receipt-then-bounce, receiptless POST, stale spreadsheet, two-tenant load id, drift-after-click, ordinal-after-list-change, external-provenance-injection, unmatched-payment, remittance-change, replay-invoke, brake-before/after-claim, unknown-delivery, corrupt-attachment, cross-tenant-data) each resolving to one deterministic outcome in which no adapter decided anything.
>
> **No new platform primitive; no addition to the frozen contracts; no higher-level amendment required.**
>
> **Operational Workflow Specification Engineering may begin,** composing these adapter operations and the 13 machines into the 11 operating-model loops — each loop a sequence of Observations, Work Items, gated Pipeline effects, verifications, and Expectations, reusing (never re-inventing) the boundary contracts specified here.

*Not started (per instruction): operational workflow specs, API specs, operational-loop acceptance specs, migration plans, PRODUCT/ARCHITECTURE/CLAUDE. No implementation code.*
