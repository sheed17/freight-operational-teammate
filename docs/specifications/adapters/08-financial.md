# Adapter Family 08 — Accounting/ERP & Payment/Banking *(A12 Accounting · A13 Payment Observation)*

*Registry + defaults + Money Model apply. ### Money direction explicit on every op (CD-17).*

---
## A12 — Accounting / ERP Adapter
**Purpose.** Read/write invoices, payables, credits, reversals in the accounting system; observe settlement status. **Not.** ### **NOT authoritative for whether the underlying charge was commercially VALID (only for the transaction occurrence within its scope); a payable entered does NOT imply payment (CD-11); an invoice sent does NOT imply collection (CD-10).** **Vendors.** QuickBooks, NetSuite — same contract. **Direction.** bidirectional.
| Op | class | verification | notes |
|---|---|---|---|
| A12-1 `read_invoice`/`read_payable`/`read_settlement_status` | `DECISION_SUPPORT_READ` / `CONSEQUENTIAL_FRESHNESS_READ` (at issue/pay) | n/a | already-invoiced/already-paid guard is live |
| A12-2 `enter_invoice` (`RAISE_INVOICE`) | ### **`CONSEQUENTIAL_EFFECT`** | READBACK_VERIFIABLE | CK amount-free (ADR-009); MF={customer,amount,packet} |
| A12-3 `enter_payable` (`RECORD_PAYABLE`) | `CONSEQUENTIAL_EFFECT` | READBACK_VERIFIABLE | HUMAN_APPROVAL_REQUIRED; ### **`remittance_party` verified (H24: destination changes before execution ⇒ re-verify at the pay checkpoint; a stale destination ⇒ drift ⇒ void)** |
| A12-4 `apply_payment` | `CONSEQUENTIAL_EFFECT` | READBACK_VERIFIABLE | CK occ = remittance ref |

**Acceptance.** `test_a12_invoice_sent_not_collected`; `test_a12_payable_entered_not_paid`; `test_a12_remittance_reverified_at_pay` (H24). **Adversarial.** H23, H24.

---
## A13 — Payment / Banking Observation Adapter
**Purpose.** ### **OBSERVE payments/remittances/cash receipts/credits/reversals — the ONLY source whose VERIFIED observation closes the AR/AP loop (CD-10/CD-11).** **Not.** ### **authoritative for whether the charge was valid; NOT a write path (observation-only).** **Direction.** inbound. **Vendors.** bank feed, factoring remittance, lockbox — same contract.
| Op | class | notes |
|---|---|---|
| A13-1 `observe_payment` / `observe_remittance` | `OBSERVATION_ONLY` | ### **source-natural key = the remittance reference (check/ACH trace) = the payment `occurrence_key` (a partial payment is a distinct occurrence)** |

**Hostile #23:** ### **the accounting/bank reports a payment with NO matching invoice ⇒ an `UNMATCHED` Payment Application ⇒ a Conflict/Work Item ⇒ human; NEVER auto-applied.** **Reversal (bounced):** ⇒ reopen the AR/AP (a `REVERSED` Payment Application). **Money.** ### **direction explicit (a customer receipt=IN, a carrier disbursement observation=OUT).** **Acceptance.** `test_a13_only_verified_payment_closes_loop`; `test_a13_unmatched_payment_raises_conflict` (H23); `test_a13_partial_payment_distinct_occurrence`. **Adversarial.** H23. **Open.** bank-feed + factoring-remittance sources; matching rules — NEEDS VALIDATION.
