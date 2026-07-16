# Workflow W8 — L8 Billing *(customer AR + cash application)*

*Registry defaults apply. ### The FIRST-LOOP destination (L6→L8). The loop closes at CASH.*

**2.** W8. **3.** From a complete Document Packet → **the customer PAID**, reconciled. **4.** ### **money in the door — not an invoice in an outbox.** **5.** own the receivable from eligibility to collection or authorized disposition. **6.** ### **NOT "an invoice was entered/sent" — generation/transmission does NOT close AR (P24, CD-10); the loop closes at PAID.** **10.** the billing/AR owner. **13.** Customer Invoice, Customer Invoice Line, Customer, Document Packet, Accessorial Charge, Payment Application, Financial Reconciliation Result. **14.** `BILL_AND_COLLECT`.

## Key steps
| Step | machine · adapter · class | notes |
|---|---|---|
| W8-1 eligibility | M-native · — · — | ### **POD-gated: the Packet is `COMPLETE` or an authorized exception (CD-3); a customer-required doc missing (hostile #14) ⇒ NOT eligible** |
| W8-2 read sell + accessorials | M2 · A4/A12 · ### `CONSEQUENTIAL_FRESHNESS_READ` (amount, at issue) | ### **the amount is a live consequential-freshness read (no cache, V-3); accessorial lines require an `AUTHORIZED` Accessorial (CD-5)** |
| W8-3 prepare invoice | M-native · — · — | lines from the record; margin visible |
| W8-4 **release/issue invoice** | M2 · A4/A12 · ### `CONSEQUENTIAL_EFFECT`(`RAISE_INVOICE`) | ### **gate = `HUMAN_APPROVAL_REQUIRED` (releasing the invoice — Operating Model); READBACK; CK = `(tenant, RAISE_INVOICE, tms, load:<id>, create_invoice, occ="")` — amount NOT in CK (ADR-009); MF = {load, customer, amount, packet digests, provenance}** |
| W8-5 verify | M3 · A4 · READBACK | ### **read the invoice+balance back, matching the approved facts, healthy channel — not a local record (M-72); the already-invoiced guard is live** |
| W8-6 collection expectations | M8 · — · — | due-date Expectation; aging; rank collections |
| W8-7 cash application | M5 · A13/A12 · `OBSERVATION_ONLY` | ### **a VERIFIED Payment Application closes the invoice `→PAID`; short-pay (hostile #22) ⇒ `SHORT_PAID` + residual AR + dispute (→W7); unmatched cash (hostile #23) ⇒ Conflict (→W7)** |
| W8-8 dispute / credit-rebill | M10/M-native · full pipeline · `CONSEQUENTIAL_EFFECT` | ### **a dispute after send (hostile #17) ⇒ W7; a credit is a Compensation, a rebill is `REISSUE_INVOICE` (distinct action class, new CK) — no double-bill (hostile #18)** |

**25. Approvals.** releasing the invoice; a credit/write-off. **32. Material Facts.** {load, customer, amount (minor units), packet digests, provenance, policy version}. **53. Closure.** ### **`PAID` (a verified Payment Application) — OR an authorized write-off / approved short-pay resolution / credit-rebill settlement** *(the exact disposition set is `NEEDS VALIDATION` against the Operating Model's canonical L8 closure rule; the DEFAULT closure is `PAID`, P24).* **54. Not.** invoice created/released/sent/delivered; a local `PAID` without a verified payment. **52. Degraded.** read-only TMS ⇒ Neyma prepares the invoice + packet, the human enters it, Neyma reads it back and tracks collection — ### **the AR loop stays valuable without write access.** **57. Metrics.** ### **DSO, invoice-release time, first-pass billing rate, collection rate, short-pay rate — NOT "invoices entered".** **60. Adversarial.** #14, #17, #18, #22, #23, #40 (payment before reconciliation ⇒ held/unmatched). **61. Open.** ### **the canonical L8 closure disposition set (V-open); per-customer billing rules (V5); reopen-on-late-POD policy (V1).**
