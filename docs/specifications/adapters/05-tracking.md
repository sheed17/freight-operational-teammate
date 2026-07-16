# Adapter Family 05 — Tracking Provider Adapter *(A9)*

*Registry + defaults apply.*

**Purpose.** Ingest movement telemetry as **source-specific Observations** — never as fact. **Not.** ### **NOT proof of real-world completion (CD-15); NOT the ETA authority.** **Direction.** inbound. **Vendors.** ELD/telematics providers, macro-point-style — same contract.

## Source-specific distinctions *(each its own `provenance_class`)*
### **`provider_position` (`SYSTEM_IMPORTED`) · `provider_status` (`SYSTEM_IMPORTED`) · `driver_assertion` (`MODEL_EXTRACTED` — a claim) · `carrier_assertion` (`MODEL_EXTRACTED`) · `derived_eta` (`MODEL_INFERRED` — a Claim, NEVER projected fact, NEVER a gate) · `tms_status` (via A4) · confirmed appointment (via A8).**

| Op | class | notes |
|---|---|---|
| A9-1 `poll_positions` / `receive_webhook` | `OBSERVATION_ONLY` | ### **polling and webhook COEXIST — dedup on the source-natural key `(tenant, provider, external_id, content_digest)`; a duplicate ⇒ `ObservationConfirmed`** |
| A9-2 `ingest_status` | `OBSERVATION_ONLY` | a status is a claim; a delivery assertion does NOT imply POD (CD-8) |

## Observability, gaps, detention
- ### **the adapter records observation-COVERAGE per movement/window — so a Stop/Appointment Expectation deadline distinguishes `OVERDUE` (channel healthy, nothing came) from `INDETERMINATE` (channel blind).**
- ### **Tracking UNAVAILABLE ⇒ `unknown`/`INDETERMINATE` — NEVER "late" and NEVER "on-time" (CD-14, H13).** Stale location ⇒ the position's `observed_at`, not "now". Geospatial accuracy is `metadata`.
- **Detention timing:** an `AT_DELIVERY` past the facility-local appointment window starts a detention clock — a **claim basis** for a detention Accessorial, requiring Authorization to bill (CD-5).
- **Conflict:** ### **tracking says delivered but POD says damaged (H17) ⇒ `ConflictRaised` ⇒ OS&D Case + human.**

**Acceptance.** `test_a9_derived_eta_is_model_inferred_never_gates`; `test_a9_unavailable_is_indeterminate_not_late` (H13); `test_a9_webhook_poll_coexist_dedup`; `test_a9_delivery_assertion_not_pod`. **Adversarial.** H13, H17. **Open.** provider trust tiers; position accuracy thresholds — NEEDS VALIDATION.
