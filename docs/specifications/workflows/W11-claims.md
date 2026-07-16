# Workflow W11 — L11 Claims *(OS&D)*

*Registry defaults apply. ### Operating Model L11 human line: "Everything. This is legal judgment." Neyma assembles; the human files.*

**2.** W11. **3.** An OS&D case (overage/shortage/damage/loss) reaches a referenced resolution with a financial adjustment created. **4.** ### **the loss is documented, the timeline assembled, the money recovered — the human makes the legal call.** **5.** own each OS&D case until `RESOLVED{decision_ref}`. **6.** ### **NOT an evidentiary Claim (the platform primitive) — a freight `Claim`; and it does NOT rewrite a settled invoice/payable (immutable history, CD-7).** **10.** the claims owner. **13.** OS&D Case, Document (POD notations, photos), Brokerage Load, Carrier Movement, Customer Invoice, Carrier Payable. **14.** `HANDLE_CLAIM`.

## Key steps
| Step | machine · adapter · class | notes |
|---|---|---|
| W11-1 open case | M-native · — · — | from a POD OS&D notation (W6), a damaged-vs-normal conflict (W5), or a customer report |
| W11-2 assemble packet + timeline | agent · reads · `INFORMATIONAL`/`DECISION_SUPPORT` | ### **assemble evidence + the timeline; Neyma does NOT file claims (Operating Model L11)** |
| W11-3 resolve | M9/M-native · — · — | ### **`RESOLVED{decision_ref}`; a settlement/credit is money-affecting ⇒ `HUMAN_APPROVAL_REQUIRED`** |
| W11-4 financial adjustment | M10 · full pipeline · `CONSEQUENTIAL_EFFECT` | ### **a claim opened AFTER invoice+payable settled (hostile #24) ⇒ the settled records stay immutable; the resolution creates a NEW adjustment (credit/debit/Compensation), never a rewrite** |

**23. Conflicts.** POD damage vs tracking normal (from W5). **24. Exceptions.** an aging unresolved claim. **48. Compensation.** the adjustment path. **53. Closure.** ### **`RESOLVED{decision_ref}` + the financial adjustment durably created.** **54. Not.** a paid invoice being immutable; an assembled packet. **52. Degraded.** fully available read-only — assembly + timeline are the value; the human files externally. **57. Metrics.** claim cycle time, recovery rate, evidence-completeness. **60. Adversarial.** #10 (delivered-but-not-received → loss claim), #13 (damage), #24. **61. Open.** per-customer/carrier claim workflows.
