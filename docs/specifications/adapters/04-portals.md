# Adapter Family 04 — Customer & Appointment Portals *(A7 Customer Portal · A8 Appointment Portal)*

*Registry + defaults apply. Often browser-actuated (A15).*

---
## A7 — Customer Portal Adapter
**Purpose.** Read customer tenders/orders, submit status/docs. **Not.** authoritative for our commercial commitment (that is native). **Direction.** bidirectional. **Ops.** `read_tenders` (`OBSERVATION_ONLY`/`DECISION_SUPPORT_READ`); `submit_status`/`upload_pod` (`CONSEQUENTIAL_EFFECT`, READBACK_VERIFIABLE). **Hostile #15:** ### **a customer changes an appointment/pickup address after dispatch ⇒ an inbound Observation ⇒ Stop/Appointment `RESCHEDULED` + a Conflict if the buy rate is invalidated + a re-notify Work Item.** **Security.** portal content untrusted. **Acceptance.** `test_a7_customer_change_after_dispatch_reschedules`. **Open.** per-customer portal semantics.

---
## A8 — Appointment Portal Adapter
**Purpose.** Request/confirm dock appointments at a Facility's scheduling portal. **Not.** ### **authoritative that an appointment is KEPT (that is tracking + POD).** **Direction.** bidirectional. **Ops.** `request_appointment` (`CONSEQUENTIAL_EFFECT`/`REQUEST_APPOINTMENT`, READBACK_VERIFIABLE — read the confirmed window back); `read_appointment` (`CONSEQUENTIAL_FRESHNESS_READ` when gating dispatch). **Authority.** ### **the CONFIRMED window is projected from the portal/facility (field-level); the REQUESTED window is native. `REQUESTED` does NOT imply `CONFIRMED` (CD-13).** **Time.** ### **the window is stored UTC + the FACILITY's local timezone; all window evaluation is facility-local across DST (F-25).** **Acceptance.** `test_a8_requested_does_not_confirm`; `test_a8_window_facility_local_tz`. **Open.** portal vendor coverage per facility — NEEDS VALIDATION.
