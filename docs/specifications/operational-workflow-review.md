# Operational Workflow Review — Hostile

**Subject:** `docs/specifications/workflows/` — 11 workflows (W1–W11, the canonical L1–L11 loops) + `registry.md`.
**Method:** 40 hostile workflow traces + a mechanical sweep.
**Date:** 2026-07-16 · **No frozen document modified.**

---

## PART 1 — THE 40 HOSTILE TRACES *(entities/states · Work Items · ownership · effects · verification · handoffs · closure/non-closure · human · test)*

| # | Scenario | Deterministic trace & result |
|---|---|---|
| **1** | One order → two loads after intake | W1-8 `CONVERTED` creates 2 Loads; **2 `COVER_LOAD` Work Items** (atomic handoff to W2). Neither closes on the other. ⇒ `test_wf_one_order_two_loads`. |
| **2** | Customer changes pickup after quote acceptance | W1/W2; an Observation ⇒ Stop `RESCHEDULED` + a `ConflictRaised` if the buy rate is invalidated + a re-quote Work Item. ⇒ `test_wf_pickup_change_after_accept`. |
| **3** | Quote accepted after evidence expired | W1-7; the sell basis is `stale` ⇒ **re-price or human-confirm** before commit. ⇒ `test_wf_accept_after_evidence_expiry`. |
| **4** | Carrier responds from an alias not bound to its MC | W2-3; confirmed only on MC/DOT ⇒ **`AMBIGUOUS`/Conflict**, the alias is a candidate. ⇒ `test_wf_carrier_alias_ambiguous`. |
| **5** | Qualified at selection, suspended before tender acceptance | W2-4/W3; the fresh qualification read at acceptance ⇒ **`NOT_QUALIFIED` ⇒ block** (CD-2). ⇒ `test_wf_suspension_before_acceptance_blocks`. |
| **6** | Verbal accept, refuses the written Rate Con | W2-7; ⇒ a Rate Con `ConflictRaised` (verbal-vs-written) ⇒ W7; no silent overwrite (CD-16). ⇒ `test_wf_verbal_vs_written_ratecon`. |
| **7** | Carrier falls off after dispatch | W4/W2; ⇒ Movement `FELL_OFF` ⇒ **re-cover via a new Movement**; the `COVER_LOAD` Work Item reopens a phase. ⇒ `test_wf_falloff_recovers`. |
| **8** | Pickup appointment changes after driver dispatch | W4-2/W4; ⇒ Appointment `RESCHEDULED` + re-notify + re-versioned Expectation. ⇒ `test_wf_appt_change_after_dispatch`. |
| **9** | Tracking unavailable for 6 hours | W5; the milestone Expectation ⇒ **`INDETERMINATE`** (blind), never `OVERDUE`/late (CD-14). ⇒ `test_wf_tracking_gap_indeterminate`. |
| **10** | Driver claims delivered, customer says not received | W5/W11; the "delivered" is a claim ⇒ a `ConflictRaised` ⇒ **open an OS&D Case (W11)**; billing blocks (no confirmed delivery/POD). ⇒ `test_wf_delivered_vs_not_received`. |
| **11** | POD bound to the wrong load | W6-4; a cross-customer/load match is `AMBIGUOUS` ⇒ human; a later correction ⇒ `ClaimCorrected` propagates (retains history, CD-6/7). ⇒ `test_wf_pod_wrong_load_ambiguous`. |
| **12** | POD valid for two related loads | W6-4; **binds both** deterministically, neither silently. ⇒ `test_wf_pod_two_loads`. |
| **13** | POD reveals damage after tracking said completed | W6-7/W5; ⇒ a `ConflictRaised` ⇒ **OS&D Case (W11)**; the packet may still complete but the claim obligation is created. ⇒ `test_wf_pod_damage_opens_claim`. |
| **14** | Customer-required doc missing at billing | W6/W8-1; Packet `INCOMPLETE` ⇒ **invoice NOT eligible** (CD-3); an Expectation chases the doc. ⇒ `test_wf_missing_required_doc_blocks_billing`. |
| **15** | Carrier invoice includes unsupported detention | W9-3; the Accessorial has **no Authorization** ⇒ `unconfirmed` ⇒ **payable blocked** (CD-5). ⇒ `test_wf_unsupported_detention_blocks`. |
| **16** | Human validates undocumented detention authorization | W9-3; an authenticated human asserts ⇒ Accessorial Authorization `CONFIRMED` `OWNER_ASSERTED` (`PERMANENT_HUMAN_ASSERTION_REQUIRED`) ⇒ now billable. ⇒ `test_wf_human_confirms_detention`. |
| **17** | Customer disputes an invoice after it was sent | W8-8/W7; ⇒ a dispute Exception (W7); the sent invoice history is immutable; a resolution may credit/rebill. ⇒ `test_wf_dispute_after_send`. |
| **18** | Credit-and-rebill required | W8-8; the credit is a **Compensation**; the rebill is **`REISSUE_INVOICE`** (distinct action class, new CK) ⇒ **no double-bill**. ⇒ `test_wf_credit_and_rebill_distinct`. |
| **19** | Payable approved, factoring info changes | W9-4; `remittance_party` re-verified at the pay checkpoint ⇒ **drift ⇒ void**, never pay the wrong factor. ⇒ `test_wf_remittance_change_voids`. |
| **20** | Payment request times out after submission | W9-6; ⇒ **`UNKNOWN_OUTCOME`** (never `FAILED`); entity frozen, human asked. ⇒ `test_wf_payment_timeout_unknown`. |
| **21** | Payment settles but local shows pending | W9-6; the **bank Observation is authoritative** ⇒ reconcile the local state; `PAY` verified. ⇒ `test_wf_settled_but_local_pending`. |
| **22** | Customer short-pays | W8-7; ⇒ `SHORT_PAID` + residual AR + a dispute (W7); **never silently closed** (CD-10). ⇒ `test_wf_short_pay_residual`. |
| **23** | Unmatched cash arrives | W8-7/A13; ⇒ an `UNMATCHED` Payment Application ⇒ a Conflict/Work Item (W7). ⇒ `test_wf_unmatched_cash`. |
| **24** | Claim opens after invoice AND payable settled | W11-4; the settled records stay immutable ⇒ the resolution creates a **new adjustment**, never a rewrite (CD-7). ⇒ `test_wf_claim_after_settled_adjusts`. |
| **25** | Identity correction: two external records = one load | External Entity Mapping 1:N ⇒ identity not collapsed (CD-19); a correction propagates. ⇒ `test_wf_two_tms_records_one_load`. |
| **26** | Identity correction: one external record = two entities | mapping per-`(system, id, scope)` ⇒ no collapse. ⇒ `test_wf_one_record_two_entities`. |
| **27** | Brake engages while several workflows have queued effects | W7; **pre-claim ⇒ `PipelineVoided`; post-claim ⇒ runs to verification; queued approvals ⇒ `VOID_ON_BRAKE`; release re-checkpoints ALL** (GR-16, M-62). ⇒ `test_wf_brake_with_queued_effects`. |
| **28** | Policy narrows autonomy during active workflows | in-flight approvals/witnesses/unclaimed grants under the old policy ⇒ **`VOID_ON_DRIFT`** (policy_version is a material fact); re-approval under the new version. ⇒ `test_wf_policy_narrow_voids_inflight`. |
| **29** | Integration unavailable at a required freshness checkpoint | the `CONSEQUENTIAL_FRESHNESS_READ` returns `None` ⇒ **checkpoint fails closed ⇒ no effect** (never "assume"). ⇒ `test_wf_freshness_unavailable_fails_closed`. |
| **30** | Human leaves while owning open Work Items | every owned open Work Item ⇒ an **Exception**; **no consequential action proceeds until reassigned** (registry ownership). ⇒ `test_wf_owner_departure_reassigns`. |
| **31** | Event replay recreates every workflow projection | **sandbox rebuild, zero effects** (GR-11); a divergence ⇒ `ProjectionRebuildDiverged` ⇒ auto-brake. ⇒ `test_wf_replay_zero_effects`. |
| **32** | Duplicate inbound messages create competing Work Items | source-natural dedup ⇒ **`ObservationConfirmed`, ONE Work Item** (M-24). ⇒ `test_wf_duplicate_message_one_work_item`. |
| **33** | A loop tries to close while a required downstream Work Item was never created | ### **the handoff is ATOMIC (registry): the source cannot close/advance unless the downstream Work Item exists in the same commit** — a responsibility gap is structurally prevented. ⇒ `test_wf_no_close_without_downstream_work`. |
| **34** | A Compensation reaches UNKNOWN_OUTCOME | W7-4; ⇒ `COMPENSATION_FAILED` — **non-terminal, human-owned, exposure stated, loud**; never auto-resolves. ⇒ `test_wf_compensation_unknown`. |
| **35** | Cross-tenant external data enters a workflow | rejected before ingestion ⇒ `CrossTenantAccessAttempted` ⇒ **GLOBAL brake** (C-1). ⇒ `test_wf_cross_tenant_data`. |
| **36** | Operator acts outside Neyma, later supplies evidence | the out-of-band action is observed as an **Observation** (the human acted directly — the honest emergency path, ADR-004 §2.5); Neyma reconciles the projection, never claims it acted. ⇒ `test_wf_out_of_band_action_reconciled`. |
| **37** | A workflow runs with no write integration, human executes | **degraded mode**: Neyma observes+prepares+verifies+detects; the human executes; Neyma captures the resulting evidence and closes the loop with them. ⇒ `test_wf_no_write_integration_human_executes`. |
| **38** | Customer cancels after carrier commitment | W2/W1; ⇒ Assignment `CANCELLED` + possible TONU Accessorial (→W9); Load `CANCELLED`. ⇒ `test_wf_cancel_after_carrier_commit`. |
| **39** | Carrier invoice arrives before POD | W9-1; ⇒ **held, awaiting the packet** (W6); reconciliation cannot complete without the backup. ⇒ `test_wf_carrier_invoice_before_pod`. |
| **40** | Customer payment arrives before invoice reconciliation | W8-7; ⇒ an `UNMATCHED`/held Payment Application ⇒ reconcile when the invoice is ready; never auto-applied. ⇒ `test_wf_payment_before_reconciliation`. |

> ### **Every trace resolves to one deterministic outcome using only foundational + domain machinery — a handoff is atomic, an unknown outcome freezes and asks, a false-closure signal is rejected, an ownerless obligation is impossible. No workflow invented safety machinery.**

---

## PART 2 — MECHANICAL CONSISTENCY REVIEW

| Check | Result |
|---|---|
| Exactly eleven canonical loops | ✅ W1–W11 = the Operating Model's L1–L11, **exact names**, not renamed/combined/split. |
| Every workflow has one business outcome | ✅ registry index + point 4 each. |
| Every open obligation has one accountable owner | ✅ registry ownership + I1; owner-departure ⇒ Exception (H30). |
| Every consequential effect → adapter op + Action Class | ✅ `RAISE_INVOICE`/`RECORD_PAYABLE`/`FILE_DOCUMENT`/`SEND_OUTBOUND`/`BOOK_CARRIER`/`SEND_TENDER`/`REQUEST_APPOINTMENT`/… |
| Every effect uses checkpoint + witness + grant | ✅ registry write-path; no direct adapter call. |
| Every consequential step defines Commit Key + Material Facts | ⚠️ **CORRECTED (U-REBASELINE-1A, finding F-02):** this row overclaimed. Only W1-6/W8-4/W9-5 state MF and only W8-4 states a full CK tuple **in-spec**; every other consequential step **inherits the registry default write-path** (CK amount-free per ADR-009; MF = the approved facts for the action class), bound at implementation time in P6–P9. See the CK/MF default-inheritance rule in `workflows/registry.md`. |
| Every transition → a formal event | ✅ no workflow event invented (registry). |
| Deterministic entry + closure | ✅ registry closure contract per loop. |
| False-closure signals rejected | ✅ registry + point 54 each (created≠accepted, sent≠paid, delivered≠POD, entered≠paid, …). |
| Every cross-loop handoff durable | ✅ registry handoff table — **atomic; source can't close without the downstream Work Item** (H33). |
| No source loop closes before downstream work exists | ✅ H33. |
| No adapter called directly | ✅ inherited (§19.9). |
| No workflow owns business truth outside canonical entities | ✅ workflows compose domain entities; own no state. |
| No workflow strengthens provenance | ✅ inherited (ER-14). |
| No `MODEL_INFERRED` gates a consequential action | ✅ ETA/rate-suggestion/fraud-signal are surfaced, never gating. |
| All `UNKNOWN_OUTCOME` paths have owners | ✅ → W7, human-owned, frozen. |
| All compensation via the normal pipeline | ✅ W7-4/W8-8/W11-4 — full pipeline. |
| Degraded mode operationally coherent | ✅ registry matrix + point 52 each. |
| No workflow depends on one TMS/vendor | ✅ vendor-neutral adapter ops. |
| Every hostile scenario one deterministic result | ✅ Part 1 (all 40). |
| No new foundational primitive | ✅ workflows compose only frozen machinery. |

---

## PART 3 — FINDINGS

**1. Workflows created:** **11** (W1–W11) + registry.
**2. Workflow-step count:** ~55 named steps across the 11 (the consequential ones fully step-contracted).
**3. Consequential-step count:** ~20 (`SEND_QUOTE`, `POST_LOAD`, `SEND_TENDER`, `ISSUE_RATECON`, `REQUEST_APPOINTMENT`, `FILE_DOCUMENT`, `RAISE_INVOICE`, `RECORD_PAYABLE`, `PAY_CARRIER`, `SEND_OUTBOUND`, `REISSUE_INVOICE`, …).
**4. Cross-loop handoff count:** **10** (registry table) — all atomic, all durable.
**5. Work Item types:** 11 primary (`QUOTE_TO_COMMITMENT`, `COVER_LOAD`, `QUALIFY_CARRIER`, `DISPATCH_READY`, `TRACK_LOAD`, `COMPLETE_DOCS`, `RESOLVE_EXCEPTION`, `BILL_AND_COLLECT`, `AUDIT_AND_PAY`, `CUSTOMER_COMMS`, `HANDLE_CLAIM`).
**6. Action Classes used:** ~14 (money-in/out, document, outbound, booking, posting).
**7. Adapter operations used:** all 18 adapters participate; the write-capable ones only via the pipeline.
**8. Closure rules:** per registry — every loop closes at a **verified business outcome**, not an activity.
**9. False-closure rules:** the 12 explicit signals, all rejected.
**10. Ownership gaps:** ### **NONE** — no open obligation is ownerless; owner-departure raises an Exception.
**11. Unknown-outcome paths:** all route to W7, human-owned, entity frozen, exposure stated; **never auto-downgraded to FAILED**.
**12. Degraded-mode coverage:** all 11 loops specify degraded operation; ### **observe + prepare + verify + exception-detect remain without write access — the product is not useless.**
**13. Product metrics defined:** activity / workflow-completion / **business-outcome** / **safety** classes (registry) — ### **"documents processed" is explicitly NOT a loop-success metric.**
**14. Remaining `NEEDS VALIDATION`:** ### **the first-loop hypothesis (L6→L8) against the design partner's actual pain**; the canonical L8 closure disposition set; per-customer billing/document rules; autonomy graduation (V11); after-hours ownership; factoring/bank/tracking sources. **All fail-closed; none blocks.**
**15. Higher-level amendments required:** ### **NONE.** Every loop composes the frozen machinery; no new primitive; the canonical L1–L11 names and boundaries are the Operating Model's, unchanged.
**16. Deviation:** none beyond the file-per-loop structure the brief requested (one file per loop — followed exactly, 11 files).

---

## VERDICT

> # **READY FOR OPERATIONAL ACCEPTANCE SPECIFICATION ENGINEERING**
>
> **Evidence:** the eleven canonical Operating-Model loops (L1–L11, exact names, not renamed/combined/split) specified as deterministic coordination contracts that compose — and never re-invent — the frozen machinery; every loop with one business outcome, one accountable human owner (no ownerless obligation, owner-departure raises an Exception), a precise closure contract that closes at a **verified business outcome** (billing at cash, settlement at settled payment, documentation at a complete-and-correctly-bound packet) and explicitly **rejects the twelve false-closure signals** (created≠accepted, sent≠paid, delivered≠POD, entered≠paid, initiated≠settled, uploaded≠valid); ten cross-loop handoffs each **atomic and durable** so a source loop can never close before its downstream obligation exists (H33); every consequential effect through Work Item → Pipeline → Approval → Checkpoint → Witness → Grant → adapter → verification, with amount-free Commit Keys and `MODEL_INFERRED` never gating; a product model made explicit (the operational execution layer, not "documents connected to a TMS") with business-outcome and safety metrics distinguished from activity; degraded-mode operation that keeps observe/prepare/verify/exception-detect alive without write access; and **40 hostile traces** (order-splits, alias carriers, suspension-before-tender, verbal-vs-written, falloff, tracking-gap, wrong-POD, missing-doc-at-billing, unsupported-detention, human-confirmed-authorization, dispute, credit-rebill, remittance-change, payment-timeout, short-pay, unmatched-cash, claim-after-settled, brake-with-queued-effects, policy-narrow, freshness-unavailable, owner-departure, replay, duplicate-messages, close-without-downstream-work, compensation-unknown, cross-tenant, out-of-band-human-action, degraded-mode, cancel-after-commit, invoice-before-POD, payment-before-reconciliation) each resolving to one deterministic result in which no workflow invented safety machinery.
>
> **No new foundational primitive; no addition to any frozen contract; no higher-level amendment required.**
>
> **Operational Acceptance Specification Engineering may begin,** taking each loop's step contracts, closure/false-closure rules, degraded modes, and the 40 traces as the acceptance surface — expressing per-loop, executable acceptance criteria that a build must satisfy to be called done.

*Not started (per instruction): API specs, implementation/migration plans, production code, PRODUCT/ARCHITECTURE/CLAUDE. No implementation.*
