# Workflow W9 — L9 Settlement *(carrier invoice audit + AP + payment + reconciliation)*

*Registry defaults apply. ### The highest-risk loop: money OUT. Closes at settled payment.*

**2.** W9. **3.** From a carrier invoice → **the carrier PAID correctly**, line-by-line reconciled, settled. **4.** ### **the right carrier paid the right amount to the right destination — and we can prove every line.** **5.** own the payable from receipt to settlement or disposition. **6.** ### **NOT "a payable was entered" — entered ≠ approved ≠ paid ≠ settled (CD-11); an extracted invoice is not approvable.** **10.** the settlement/AP owner. **13.** Carrier Payable, Carrier Payable Line, Rate Confirmation, Accessorial Charge, Accessorial Authorization, Payment Application, Factoring Company, Financial Reconciliation Result. **14.** `AUDIT_AND_PAY`.

## Key steps
| Step | machine · adapter · class | notes |
|---|---|---|
| W9-1 receive carrier invoice | M5 · A1 · `OBSERVATION_ONLY` | ### **duplicate detection (carrier invoice number = occurrence_key) ⇒ `DUPLICATE_SUPPRESSED`; arrives before POD (hostile #39) ⇒ held, awaiting the packet** |
| W9-2 reconcile line-by-line | agent · A4/A11 · `DECISION_SUPPORT` | ### **match linehaul/fuel/accessorials vs the Rate Con; flag the delta with evidence; a late Rate Con contradicting terms (hostile #29 domain) ⇒ `ConflictRaised`** |
| W9-3 accessorial authorization gate | M-native · — · — | ### **an unsupported detention (hostile #15) ⇒ blocked; a counterparty "you approved it" (hostile #16 setup) is `MODEL_EXTRACTED` fraud ⇒ blocks; a HUMAN validates the undocumented authorization (hostile #16) ⇒ `OWNER_ASSERTED` `PERMANENT_HUMAN_ASSERTION_REQUIRED` ⇒ now billable (CD-5)** |
| W9-4 verify remittance target | M2 · A1 · ### `CONSEQUENTIAL_FRESHNESS_READ` at pay | ### **`remittance_party` (factoring) verified; a change before execution (hostile #19) ⇒ drift ⇒ re-verify/void — never pay the wrong factor** |
| W9-5 **record payable** | M2 · A4/A12 · ### `CONSEQUENTIAL_EFFECT`(`RECORD_PAYABLE`) | ### **gate = `HUMAN_APPROVAL_REQUIRED` (money-out); blocked on any `conflicting` field (CD-4); READBACK; CK amount-free; MF = {carrier, remittance_party, amount, ratecon, authorized accessorials}** |
| W9-6 **pay + settle** | M2 · A12 · `CONSEQUENTIAL_EFFECT`(`PAY_CARRIER`) | ### **payment initiation ≠ settlement; a timeout after submit (hostile #20) ⇒ `UNKNOWN_OUTCOME` (never `FAILED`); settled-but-local-pending (hostile #21) ⇒ the bank Observation is authoritative, reconcile** |
| W9-7 reconcile | M-native · A13 · — | Financial Reconciliation Result; discrepancies ⇒ Conflict (→W7) |

**25. Approvals.** recording the payable; approving each disputed line; **confirming a verbal authorization** (Operating Model L9 human line). **53. Closure.** ### **the payable SETTLED (a verified payment/settlement Observation) — OR disputed/held with a decision.** **54. Not.** entered/approved/initiated; a local `PAID` without a bank Observation. **52. Degraded.** no accounting write ⇒ Neyma audits + prepares the payable + flags deltas; the human enters/pays; Neyma reconciles from the payment Observation. **57. Metrics.** ### **carrier-payment cycle time, audit-catch rate (deltas found), duplicate-suppressed count, `UNKNOWN_OUTCOME` rate — NOT "payables entered".** **60. Adversarial.** #15, #16, #19, #20, #21, #24 (claim after settled), #29, #39. **61. Open.** factoring-verification + bank-feed sources; matching rules.
