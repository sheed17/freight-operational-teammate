# Adapter Family 06 — FMCSA / Carrier Authority Adapter *(A10)*

*Registry + defaults apply.*

**Purpose.** Look up carrier authority/safety/insurance as **projected Observations + Evidence** feeding the Qualification Decision. **Not.** ### **The adapter supplies Observations/Evidence; it does NOT make the Carrier Qualification Decision (that is native, human-reserved — CD-2, #37).** **Direction.** inbound. **Vendors.** FMCSA SAFER/QCMobile, insurance/COI verification services — same contract.

| Op | class | verification | notes |
|---|---|---|---|
| A10-1 `lookup_mc` / `lookup_dot` | ### **`CONSEQUENTIAL_FRESHNESS_READ`** when feeding a qualification at tender/booking time | n/a | ### **live at qualification time (CD-2); a cached authority is `DECISION_SUPPORT` only** |
| A10-2 `read_authority_status` / `safety_rating` / `insurance` | as above | n/a | each carries a **source timestamp**; freshness decisive |

**Identity.** ### **MC and DOT are trusted low-collision identifiers — but MC ≠ trust (identity, not qualification); a carrier impersonation (matching MC, different operating entity) ⇒ a fraud signal + `AMBIGUOUS`/human.** **Fraud.** ### **the adapter surfaces fraud/impersonation indicators as `MODEL_INFERRED` signals ⇒ `FraudSignalRaised`/narrow autonomy; the human makes the trust call.** **Revalidation.** ### **periodic (durable timer on `expires_at`); an authority/insurance change AFTER a Qualification Decision (H14) ⇒ a new Observation ⇒ the qualification is re-evaluated at the next tender/booking (not sticky — CD-2, #18).** **Unavailable.** ### **FMCSA unavailable at qualification time ⇒ fail-closed (block the tender), never assume qualified.** **Acceptance.** `test_a10_supplies_observations_not_qualification_decision`; `test_a10_authority_change_forces_requalification` (H14); `test_a10_unavailable_blocks_tender`. **Adversarial.** H14. **Open.** insurance/COI verification source — NEEDS VALIDATION.
