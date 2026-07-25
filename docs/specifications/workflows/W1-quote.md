# Workflow W1 — L1 Quote *(incl. demand & order intake)*

*Registry: `workflows/registry.md`. 61-point defaults, closure/false-closure, ownership, step-contract format, degraded matrix, metrics: registry.*

**2. Id.** W1. **3. Business def.** From inbound customer demand → a priced commitment the customer accepted → downstream coverage work created. **4. Customer-visible outcome.** ### **a price they can act on, and freight that gets covered — not a quote in a queue.** **5. Obligation.** own the demand until it is an accepted Order (with coverage work created) OR explicitly dispositioned. **6. Not.** ### **NOT "extraction done" — a parsed email is not intake; a sent quote is not a commitment; acceptance is not coverage (CD-12).** **10. Owner.** the broker/pricing owner. **12. Parties.** Customer, Shipper, Consignee, Bill-To (roles, one Org possibly several). **13. Entities.** Customer Order, Quote, Quote Version, Customer, Facility, Brokerage Load. **14. Work Item.** `QUOTE_TO_COMMITMENT`.

## Key steps
| Step | machine · adapter · class | notes |
|---|---|---|
| W1-1 ingest demand | M5 · A1/A7/A16 · `OBSERVATION_ONLY` | email/portal/spreadsheet/human; ### **dedup on source-natural key (duplicate demand ⇒ `ObservationConfirmed`, not a 2nd Order — hostile #32); incomplete demand ⇒ an Exception "missing info" with a disposition** |
| W1-2 bind customer/facility | M6 · A4/A10 · — | ### **deterministic within `(tenant)`; a fuzzy customer name is `AMBIGUOUS` ⇒ human, never auto-confirmed (GR-8)** |
| W1-3 gather pricing evidence | M5 · A5 (load board market rate) · ### `DECISION_SUPPORT_READ` | market-rate evidence carries `as_of`+`expires_at` |
| W1-4 recommend sell rate | agent · — · proposal | ### **`MODEL_INFERRED` recommendation — never auto-sent; the sell rate is `OWNER_ASSERTED`** |
| W1-5 create Quote Version | M-native · — · — | immutable version |
| W1-6 **send quote** | M2 · A1 · ### **`CONSEQUENTIAL_EFFECT` `SEND_QUOTE`** | gate = `HUMAN_APPROVAL_REQUIRED` (the sell rate — Operating Model §6); RECEIPT_VERIFIABLE; MF = {customer, sell, version} |
| W1-7 ingest acceptance | M5 · A1/A7 · X | ### **accepted after evidence `expires_at` (hostile #3) ⇒ the sell basis is `stale` ⇒ re-price or human-confirm** |
| W1-8 convert to Order → Load(s) | M-native · — · — | ### **`CONVERTED` creates ≥1 Brokerage Load; ATOMIC handoff to W2 `COVER_LOAD` (registry) — hostile #1: one order → two loads** |

**22. Expectations.** a sent quote ⇒ a response Expectation (discharged by acceptance/decline; `EXPIRED` ⇒ follow-up). **23. Conflicts.** conflicting customer instructions ⇒ `ConflictRaised`. **25. Approvals.** the sell rate; a below-floor price. **37. Happy path.** demand → bound → priced → approved → sent → accepted → Order+Load → W2. **53. Closure.** ### **an accepted Customer Order with `COVER_LOAD` durably created, OR an explicit reject/cancel/duplicate/return-for-info with a disposition.** **54. Does NOT close.** a sent quote; a parsed email. **52. Degraded.** no portal ⇒ email-only intake + human execution; still prices, drafts, tracks. **57. Metrics.** quote-turnaround, acceptance rate, quote→Order conversion; **not** "emails parsed". **60. Adversarial.** #1, #2 (→W2 re-quote on address change), #3, #32. **61. Open.** per-customer pricing rules (V4/V5); the first-loop hypothesis is L6→L8, so W1 autonomy is later-staged (`NEEDS VALIDATION`).
