# Workflow W3 — L3 Compliance *(continuous carrier qualification)*

*Registry defaults apply. ### A CONTINUOUS loop, not a per-load one — it feeds W2's gate.*

**2.** W3. **3.** Keep carriers **qualified at the relevant time for the relevant movement** — authority, insurance, safety, fraud. **4.** ### **we never tender to a carrier who lapsed — before the load, not after.** **5.** own each carrier's qualification currency. **6.** ### **NOT one-time onboarding — qualification is time-and-movement-specific (CD-2); onboarding is not permanent (hostile — #18).** **10.** the carrier-compliance owner. **13.** Carrier, Compliance Record, Carrier Qualification Decision. **14.** `QUALIFY_CARRIER`.

## Key steps
| Step | machine · adapter · class | notes |
|---|---|---|
| W3-1 pull authority/insurance/safety | M5 · A10/A11 · ### `CONSEQUENTIAL_FRESHNESS_READ` at qualification | each Observation carries a source timestamp; `expires_at` |
| W3-2 continuous revalidation | M8 · A10 · T | ### **durable timers on `expires_at`; an authority/insurance change after a decision (hostile #14) ⇒ a new Observation ⇒ re-evaluate** |
| W3-3 surface fraud/impersonation | agent · A10 · — | ### **`MODEL_INFERRED` signal ⇒ `FraudSignalRaised`/narrow autonomy — the model SURFACES, the human DECIDES trust** |
| W3-4 make Qualification Decision | M-native · — · — | ### **native, HUMAN-RESERVED where the Operating Model reserves it; a model may NOT make the final trust call** |

**22. Expectations.** each `expires_at` ⇒ a re-qualification Expectation. **23. Conflicts.** impersonation (matching MC, different entity) ⇒ Conflict + fraud. **24. Exceptions.** a lapse before a tendered load ⇒ Exception ⇒ block. **26. Rule.** a `do_not_use` / preferred-carrier rule (compiled). **48. Compensation.** if an unqualified carrier was somehow used ⇒ escalation (rare — the gate prevents it). **53. Closure.** ### **a current Qualification Decision on file (the loop is continuous — it "closes" per carrier per validity window, reopening on expiry/signal).** **54. Not.** a past onboarding; an expired authority read. **52. Degraded.** no FMCSA feed ⇒ ### **fail-closed: block autonomous tender; a human verifies manually and asserts.** **57. Metrics.** % carriers current, lapse-caught-before-tender rate, fraud-signal precision. **60. Adversarial.** #5 (suspension pre-acceptance), #14. **61. Open.** insurance/COI source; which trust decisions are human-reserved per tenant (V-open).
