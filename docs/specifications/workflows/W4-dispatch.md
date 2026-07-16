# Workflow W4 — L4 Dispatch *(pickup & dispatch readiness + appointment booking)*

*Registry defaults apply.*

**2.** W4. **3.** From an active Assignment → the load **operationally ready to move** (driver, equipment, appointment, refs, docs, carrier-confirmed). **4.** ### **the truck shows up prepared — not a dispatch email fired into the void.** **5.** own readiness until verified ready OR a readiness failure is escalated. **6.** ### **NOT "a dispatch message was sent" — sending ≠ readiness; the loop names the EVIDENCE of readiness.** **10.** the dispatch owner. **13.** Carrier Assignment, Driver, Equipment, Stop, Appointment, Facility, Document Requirement. **14.** `DISPATCH_READY`.

## Key steps
| Step | machine · adapter · class | notes |
|---|---|---|
| W4-1 confirm driver/equipment | M5 · A1/A6 · X | `MODEL_EXTRACTED` claims until confirmed; reefer temp required (fail-closed if `unknown`) |
| W4-2 **request appointment** | M2 · A8 · ### `CONSEQUENTIAL_EFFECT`(`REQUEST_APPOINTMENT`) | READBACK (read the confirmed window back); ### **`REQUESTED` ≠ `CONFIRMED` (CD-13)** |
| W4-3 read confirmed window | M5 · A8 · ### `CONSEQUENTIAL_FRESHNESS_READ` when gating dispatch | ### **facility-local timezone (F-25)** |
| W4-4 **dispatch communication** | M2 · A1/A18 · `CONSEQUENTIAL_EFFECT`(`SEND_OUTBOUND`) | RECEIPT (transmission, not readiness) |
| W4-5 readiness check | M-native · — · — | ### **readiness = {appointment `CONFIRMED`, driver/equipment confirmed, refs present, required docs identified} — a checklist of EVIDENCE, not a sent message** |

**22. Expectations.** a dispatch ⇒ a carrier-confirmation Expectation; ### **an appointment change after dispatch (hostile #8/#15) ⇒ `RESCHEDULED` + re-notify + re-versioned Expectation.** **24. Exceptions.** missed confirmation ⇒ Exception; ### **carrier falloff after dispatch (hostile #7) ⇒ W2 re-cover; TONU risk tracked.** **53. Closure.** ### **verified readiness evidence complete, OR a readiness failure escalated (falloff/no-confirm) with a decision.** **54. Not.** a sent dispatch; an unconfirmed appointment. **52. Degraded.** no appointment portal ⇒ human books, Neyma captures the confirmation as an Observation. **57. Metrics.** on-time pickup rate, dispatch-to-ready time, TONU rate. **60. Adversarial.** #7, #8. **61. Open.** per-facility appointment sources.
