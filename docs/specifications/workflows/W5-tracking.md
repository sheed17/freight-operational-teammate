# Workflow W5 — L5 Tracking *(in-transit execution)*

*Registry defaults apply.*

**2.** W5. **3.** From pickup → the customer knows the true status, delays caught early, delivery reached. **4.** ### **the customer hears the truth early, especially when it's bad — not silence.** **5.** own status currency and delay detection through delivery. **6.** ### **NOT "a tracking status field" — a status is a CLAIM, not proof (CD-15).** **10.** the tracking/ops owner. **13.** Carrier Movement, Stop, Appointment, Tracking Event. **14.** `TRACK_LOAD`.

## Key steps
| Step | machine · adapter · class | notes |
|---|---|---|
| W5-1 ingest positions/status | M5 · A9 · `OBSERVATION_ONLY` | ### **source-specific provenance: position `SYSTEM_IMPORTED`, driver/carrier assertion `MODEL_EXTRACTED`, derived ETA `MODEL_INFERRED` (never gates)** |
| W5-2 detect delay early | agent · A9 · — | a `MODEL_INFERRED` ETA vs the appointment window ⇒ a delay **claim** ⇒ draft a customer notice (→W10) |
| W5-3 check-call the carrier | M2 · A1/A18 · `CONSEQUENTIAL_EFFECT`(`SEND_OUTBOUND`) | RECEIPT |
| W5-4 detention clock | M8 · A9 · T | ### **facility-local; a detention basis is a CLAIM requiring Authorization to bill (CD-5)** |

**22. Expectations.** each milestone (arrival/departure/delivery) ⇒ an Expectation; ### **tracking unavailable for 6h (hostile #9) ⇒ the Expectation ⇒ `INDETERMINATE` (channel blind), NEVER `OVERDUE`/late/on-time (CD-14).** **23. Conflicts.** ### **tracking-provider vs TMS vs driver assertion disagree ⇒ `ConflictRaised`; a "delivered" claim vs a later damaged POD (hostile #13) ⇒ Conflict ⇒ W11.** **53. Closure.** ### **delivery reached (a claim) AND handed to W6 for document completion — W5 does NOT close on a "delivered" status (CD-8).** **54. Not.** a tracking "delivered"; a blind window read as on-time. **52. Degraded.** no tracking provider ⇒ Expectations `INDETERMINATE`, human check-calls; Neyma drafts customer notices from what it knows. **57. Metrics.** delay-caught-early rate, status-currency, customer-notified-before-they-ask rate. **60. Adversarial.** #9, #10 (→W11), #13. **61. Open.** provider trust tiers.
