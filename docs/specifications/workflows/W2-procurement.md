# Workflow W2 — L2 Procurement *(sourcing + tender + assignment + rate confirmation)*

*Registry defaults apply.*

**2.** W2. **3.** From an uncovered Load → a **confirmed Carrier Assignment** at a committed buy rate with a signed Rate Con. **4.** ### **the load is covered by a carrier we trust at a rate we chose — not a board posting.** **5.** own coverage until a valid Assignment OR unserviceable/escalated. **6.** ### **NOT "a carrier responded" — a search result/response is a CANDIDATE/Offer, never an Assignment.** **10.** the coverage broker. **12.** Carrier, Carrier Contact, Factoring Company (remittance), Driver. **13.** Carrier, Carrier Offer, Tender, Carrier Assignment, Rate Confirmation, Carrier Movement, Qualification Decision. **14.** `COVER_LOAD`.

## Key steps
| Step | machine · adapter · class | notes |
|---|---|---|
| W2-1 search / post | M2 · A5 · ### `DECISION_SUPPORT_READ` / `CONSEQUENTIAL_EFFECT`(`POST_LOAD`) | posting is READBACK-verified; search results are candidates |
| W2-2 ingest offers | M5 · A5/A1 · X | Carrier Offer candidates; ### **buy rate `MODEL_EXTRACTED` until human-accepted** |
| W2-3 confirm carrier identity | M6 · A10 · — | ### **on MC/DOT, not the board alias/email name (hostile #4/#27); a mismatch ⇒ `AMBIGUOUS`/Conflict** |
| W2-4 qualification gate | M2 · A10 · ### `CONSEQUENTIAL_FRESHNESS_READ` | ### **W3 Qualification `QUALIFIED` at THIS time (CD-2); suspended-before-acceptance (hostile #5) ⇒ re-check blocks** |
| W2-5 **send tender** | M2 · A5/A6 · `CONSEQUENTIAL_EFFECT`(`SEND_TENDER`) | READBACK; gate per policy |
| W2-6 accept + create Assignment | M-native · — · — | ### **an Assignment may NOT become `ACTIVE` from a weak identity match or stale qualification** |
| W2-7 create/receive Rate Con | M2/M5 · A1/A4 · `CONSEQUENTIAL_EFFECT`(`ISSUE_RATECON`) | ### **a written Rate Con NEVER silently overwrites a prior commitment (CD-16, hostile #6: verbal-vs-written ⇒ a new version + `ConflictRaised`)** |
| W2-8 capture factoring/remittance | M6 · A1 · — | ### **`remittance_party` `OWNER_ASSERTED`/documented — verified before pay (W9)** |

**22. Expectations.** tender ⇒ acceptance Expectation (`EXPIRED` ⇒ re-source). **23. Conflicts.** verbal-vs-written rate; MC mismatch. **24. Exceptions.** ### **carrier falloff (hostile #7/#38) ⇒ `FELL_OFF` ⇒ re-cover via a NEW Movement (Load→Movement 1:N).** **25. Approvals.** issuing the rate con; below-margin. **53. Closure.** ### **a confirmed Carrier Assignment + signed Rate Con + verified remittance, OR the load explicitly unserviceable/cancelled/escalated with a decision.** **54. Not.** a search result; a verbal yes; a posted load. **52. Degraded.** no board API ⇒ email outreach + human selection; still confirms identity, computes margin, drafts the rate con. **57. Metrics.** coverage time, tender acceptance rate, re-cover rate, margin realized. **60. Adversarial.** #4, #5, #6, #7, #27, #38. **61. Open.** board tiers; preferred/prohibited carrier rules (V5).
