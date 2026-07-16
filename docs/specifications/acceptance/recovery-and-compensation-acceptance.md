# Recovery, Compensation & Concurrency Acceptance *(AC-REC-*, AC-RACE-*)*
*Registry defaults apply. Levels: `RECOVERY`/`CROSS_MACHINE`. Gate: **G4**.*

## Deterministic schedules — the seventeen
> ### **Every schedule is an EXACT interleaving driven by a controllable scheduler (barriers/injected pauses), not luck. "No reproducible race occurred" is NOT an acceptable result — a non-deterministic run FAILS.**

| ID | Schedule | One canonical outcome |
|---|---|---|
| **AC-RACE-001** | two pipelines, one logical effect | ### **exactly ONE claim; N-1 `ClaimRefused`; ONE external call** |
| **AC-RACE-002** | brake vs grant claim | ### **never both, never neither** — the CAS decides; run 10,000 interleavings |
| **AC-RACE-003** | policy change vs claim | claim CAS zero rows OR the claim wins cleanly — never a half state |
| **AC-RACE-004** | entity update vs checkpoint | step-5 fails ⇒ (b) no capability |
| **AC-RACE-005** | approval vs material drift | `VOID_ON_DRIFT`; zero calls |
| **AC-RACE-006** | outbox crash **before** publish | the relay re-sends the identical `event_id` ⇒ inbox no-op |
| **AC-RACE-007** | outbox crash **after** publish | duplicate delivery ⇒ no-op |
| **AC-RACE-008** | consumer crash **before** inbox commit | reprocessed ⇒ same state digest |
| **AC-RACE-009** | consumer crash **after** inbox commit | not reprocessed |
| **AC-RACE-010** | ### **adapter timeout after submit** | ### **`UNKNOWN_OUTCOME` + structured evidence; NEVER `FAILED`; no retry** |
| **AC-RACE-011** | ### **browser crash after click** | ### **`UNKNOWN_OUTCOME`; entity frozen; commit key held** |
| **AC-RACE-012** | verification outage | `OBSERVATION_UNAVAILABLE` ⇒ `UNKNOWN_OUTCOME`; ### **never `VERIFIED_FAILURE`** |
| **AC-RACE-013** | compensation timeout | `COMPENSATION_FAILED` — non-terminal, owned, loud |
| **AC-RACE-014** | duplicate external webhook | ⇒ `ObservationConfirmed`; zero new work |
| **AC-RACE-015** | cross-tenant identifier collision | two independent entities; zero interference |
| **AC-RACE-016** | ### **owner deactivation during a transition** | ### **the transition completes or fails atomically; an Exception raises; NO consequential action proceeds without a reassigned owner** |
| **AC-RACE-017** | ### **downstream Work Item creation crash** | ### **the source transition does NOT advance (atomic handoff) — no responsibility gap** |

## Compensation acceptance
| ID | Proves | Oracle |
|---|---|---|
| **AC-REC-001** | ### **compensation FORBIDDEN on `UNKNOWN_OUTCOME`** | `CompensationRefused{unknown}`; ### **assert zero compensating calls — you cannot undo what you cannot prove you did** |
| **AC-REC-002** | compensation uses the **ordinary pipeline** | its own witness+grant+approval+readback |
| **AC-REC-003** | ### **no bulk undo** | a correction invalidating N effects ⇒ **N individually-gated Compensations**; the aggregate exposure shown first |
| **AC-REC-004** | ### **`COMPENSATION_FAILED` never auto-resolves** | no timer moves it (ILLEGAL); owned; exposure stated |
| **AC-REC-005** | crash recovery reaches the **canonical** state | pre-effect ⇒ re-checkpoint; post-claim ⇒ `UNKNOWN_OUTCOME`, **never re-execute** |
