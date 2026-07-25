# Domain Family 04 — Commercial *(Quote · Quote Version · Carrier Offer · Tender · Carrier Assignment · Rate Confirmation)*

*Registry + Money Model apply. ### Money direction is EXPLICIT on every record (CD-17): sell = IN, buy = OUT, quote = QUOTED.*

---
## E16 — Quote · lifecycle **L-Quote**
**Def.** A **priced offer to the Customer** (a **sell** price, money **IN**, uncommitted). **Not.** ### **Not a Carrier Offer** (that is a buy); not a commitment; not a Load. **Authority.** native. ### **The sell rate is a HUMAN decision (Operating Model §6) — `OWNER_ASSERTED`; a model-suggested rate is `MODEL_INFERRED` and may NOT be sent autonomously.** **Identifier.** `quote_id`. **Money.** `sell` `QUOTED`; `market_rate_evidence` (`MODEL_EXTRACTED` from a rate tool) with a **freshness/`expires_at`**. **L-Quote states.** `REQUESTED → PRICED → SENT → ACCEPTED` · `DECLINED` · `EXPIRED`. **Key transitions:** `SENT` is a gated outbound effect; `ACCEPTED` (X, customer) — ### **hostile #5: accepted AFTER the market-rate evidence expired** ⇒ a Conflict/re-quote (the evidence's `expires_at` passed ⇒ the sell basis is `stale` ⇒ re-price or human-confirm). **CD-12:** ### **`ACCEPTED` does NOT imply carrier capacity exists** (that is Offer/Tender). **Versioning.** re-prices create **Quote Versions** (#17). **Acceptance.** `test_sell_rate_is_owner_asserted`; `test_accept_after_evidence_expiry_requires_reprice_or_human`. **Open.** market-rate evidence freshness window — NEEDS VALIDATION.

---
## E17 — Quote Version
**Def.** ### **An IMMUTABLE snapshot of a Quote's commercial terms at a point in time.** **Not.** A mutable field on the Quote. **Authority.** native, immutable. **Identifier.** `quote_version_id`; monotonic `version` per Quote. **Attrs.** `sell`, `rate_basis`, `linehaul`, `fuel`, `accessorials[]`, `effective_at`, `expires_at`. **Correction/supersession.** ### **a re-price ADDS a version; the prior is RETAINED (CD-16, GR-12); never edited in place.** **CD-16:** ### **a Rate Confirmation cannot overwrite a prior commercial commitment without a new version + conflict handling.** **Acceptance.** `test_quote_version_immutable`; `test_reprice_adds_version_retains_prior`. **Open.** none.

---
## E18 — Carrier Offer · lifecycle **L-Offer**
**Def.** A carrier's **buy** price to move a Movement (money **OUT**, uncommitted). **Not.** ### **Not the Quote** (sell); not a Tender (our push); not a commitment. **Authority.** native; the offered rate is `MODEL_EXTRACTED` from the carrier's message (evidence) until human-accepted. **Identifier.** `offer_id`. **Money.** `buy` `QUOTED`/`owed_to_carrier`. **L-Offer states.** `RECEIVED → UNDER_REVIEW → ACCEPTED` · `DECLINED` · `EXPIRED` · `COUNTERED`. **Acceptance.** `test_offer_is_buy_side_distinct_from_quote`. **Open.** none.

---
## E19 — Tender · lifecycle **L-Tender**
**Def.** ### **Our OFFER of a Movement to a specific Carrier at a buy rate.** **Not.** A Carrier Offer (their price); not an Assignment (accepted). **Authority.** native. **Identifier.** `tender_id`. **L-Tender states.** `SENT → ACCEPTED` · `REJECTED` · `EXPIRED` · `WITHDRAWN`. **Key transitions:** `SENT` — ### **guard: the Carrier is `QUALIFIED` at tender time OR human-approved (CD-2)** — `hostile #4: qualified at tender, suspended before pickup` ⇒ the *tender* was valid; a **new qualification check at booking/pickup** may block (qualification is time-and-movement-specific, CD-2). **Acceptance.** `test_tender_gated_by_qualification_at_tender_time`; `test_suspension_before_pickup_rechecks_at_booking`. **Open.** none.

---
## E20 — Carrier Assignment · lifecycle **L-Assign**
**Def.** ### **The confirmed binding of a Carrier (+ Driver + Equipment) to a Carrier Movement.** **Not.** A Tender (pre-acceptance); not the Movement. **Authority.** native. **Identifier.** `assignment_id`. **L-Assign states.** `ACTIVE → COMPLETED` · `CANCELLED` · `FELL_OFF`. **CD-1:** ### **cannot be `ACTIVE` without a valid (non-terminal) Carrier Movement** (FK + guard). **Cancellation:** ### **hostile #21 (load cancelled after acceptance)** ⇒ Assignment `CANCELLED` + possible TONU; **#22 (carrier falls off after pickup)** ⇒ `FELL_OFF` + re-cover. **Acceptance.** `test_assignment_requires_active_movement`. **Open.** none.

---
## E21 — Rate Confirmation · lifecycle **L-RateCon**
**Def.** ### **The agreement between US and the CARRIER on what we will PAY — evidence of a PAYABLE, not an invoice.** **Not.** ### **Not our customer rate/Quote** (commonly confused — it is the **buy**, money **OUT**); not the Carrier Invoice. **Authority.** native (the terms) + Evidence (the signed doc). **Identifier.** `ratecon_id`. **Money.** `buy`/`owed_to_carrier`. **L-RateCon states.** `DRAFTED → SENT → SIGNED` · `SUPERSEDED` · `VOIDED`. **CD-16:** ### **a Rate Con contradicting a prior commercial commitment (the phone-agreed buy) ⇒ a new Quote/Offer version + `ConflictRaised`, never a silent overwrite** — hostile #6. **Late arrival:** ### **hostile #29 — a late Rate Con contradicting a COMPLETED payable ⇒ `ConflictRaised` (a payable was verified on the old terms) ⇒ human + possible Compensation.** **Acceptance.** `test_ratecon_is_buy_not_sell`; `test_ratecon_conflict_versions_not_overwrites`; `test_late_ratecon_vs_completed_payable_raises_conflict`. **Open.** none.

---
## Family-wide
**Money.** ### **buy (OUT) and sell (IN) are ALWAYS distinct fields; margin = sell − buy, computed, never a mutable stored value (CD-17).** **Events.** `SENT`/outbound are gated effects (Pipeline → `EffectVerified`); acceptances are `ObservationBound`. **Approvals.** the sell rate, a below-margin booking, and carrier use are human/policy-gated (a `Require manager approval under 12% margin` rule compiles ONLY if margin is deterministic — else escalate, per M-49). **Adversarial:** hostile #4, #5, #6, #21, #22, #29 — traced in the review.
