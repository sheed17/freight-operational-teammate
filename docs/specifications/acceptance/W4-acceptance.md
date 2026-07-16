# W4 Dispatch Acceptance *(AC-WF4-*)*
*Source: `workflows/W4-dispatch.md`, Operating Model L4.*

| ID | Proves | Oracle / negative |
|---|---|---|
| **AC-WF4-001** | ### **readiness requires its COMPLETE evidence set** | {appointment `CONFIRMED`, driver+equipment confirmed, refs, required docs} — a missing element ⇒ not ready |
| **AC-WF4-002** | ### **a message sent is NOT readiness proof** | a sent dispatch + unconfirmed appointment ⇒ **not ready** (AC-FC-004) |
| **AC-WF4-003** | driver/equipment/appointment/refs/facility validated | each with its provenance; a reefer temp `unknown` ⇒ fail-closed |
| **AC-WF4-004** | ### **post-dispatch changes invalidate stale preparation** | an appointment moved after dispatch ⇒ `RESCHEDULED` + re-notify + re-versioned Expectation |
| **AC-WF4-005** | falloff / pickup delay follow deterministic paths | `FELL_OFF` ⇒ W2 re-cover; delay ⇒ Expectation/Exception |
| **AC-WF4-006** | ### **cancellation after carrier commitment creates the required exception/compensation obligation** | Assignment `CANCELLED` + TONU Accessorial obligation (→W9), owned |
