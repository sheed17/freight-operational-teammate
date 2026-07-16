# Workflow W10 — L10 Customer comms

*Registry defaults apply.*

**2.** W10. **3.** The customer gets the right message at the right time; commitments made to them are tracked. **4.** ### **the customer feels informed, especially when it's bad — and we keep our promises.** **5.** own each customer-facing communication obligation until delivered + any commitment tracked. **6.** ### **NOT "a message was sent" — sent ≠ received ≠ complied (M-72); a draft is not a send.** **10.** the account/comms owner. **13.** Communication Thread, Communication Message, Customer, Brokerage Load. **14.** `CUSTOMER_COMMS`.

## Key steps
| Step | machine · adapter · class | notes |
|---|---|---|
| W10-1 detect a comms need | agent · reads · — | from W5 (delay), W6 (missing doc), W8 (dispute) — **drafts everything** |
| W10-2 **send** | M2 · A1/A18 · ### `CONSEQUENTIAL_EFFECT`(`SEND_OUTBOUND`) | ### **`❌ never sends unapproved` initially (Operating Model L10) — `HUMAN_APPROVAL_REQUIRED`; RECEIPT (transmission, not receipt); a bounce ⇒ retry/Expectation (hostile — #28 domain)** |
| W10-3 track commitments | M8 · — · — | ### **a commitment made TO the customer ("we'll deliver by 5") ⇒ an Expectation; quoted/forwarded text is NOT a new commitment without evidence** |

**22. Expectations.** a reply owed; a commitment made ⇒ tracked to fulfillment. **24. Exceptions.** an outbound bounce; an unfulfilled commitment. **28. Brake.** outbound is admission-controlled. **51. Observability.** ### **outbound content is generated from canonical facts — never echoes unsanitized inbound content (no injection relayed to a counterparty).** **53. Closure.** ### **the message delivered (receipt) + any commitment tracked to fulfillment — NOT a send.** **54. Not.** a sent/drafted message. **52. Degraded.** always available (email/SMS) — Neyma drafts, the human approves+sends initially, autonomy graduates. **57. Metrics.** customer-response time, proactive-notice rate, commitment-kept rate. **60. Adversarial.** delivery-unknown; injection-relay (prevented). **61. Open.** which notices carry commitments; autonomy graduation for sends (V11).
