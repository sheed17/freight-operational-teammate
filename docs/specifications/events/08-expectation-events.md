# Event Family F8 — Expectation Events

*Registry: `events/registry.md`. Producer: machine M8. Defaults: registry §1–§2.*

**Family defaults:** `aggregate_type=expectation`; ordering = **order-tolerant except discharge/expiry** (per-aggregate version); security=`internal`; projection = **none** (expectations are native operational state); timestamps carry `originating_timezone` alongside UTC.

| Event · v1 · producer | Proves / ¬Proves | Payload | Consumers → guard | Notes / tests |
|---|---|---|---|---|
| **`ExpectationRaised`** EX-1 | proves a future observation is owed by a deadline over a declared channel · ¬proves it will arrive | `deadline_utc`(R), `originating_timezone`(R), `expected_source`(R), `expectation_key`(R) | M8 | duplicate prevention via `expectation_key`; `test_ev_expectationraised_declares_channel` |
| **`ExpectationDischarged`** EX-2/4 | proves the owed observation arrived (possibly late) | `discharge_observation_id`(R), `late?` | Oversight; M1 | ### **a late arrival ALWAYS discharges (EX-4)**; `test_ev_expectationdischarged_late_ok` |
| **`ExpectationOverdue`** EX-3 | ### **proves the thing did NOT arrive AND the channel was demonstrably healthy** · ¬proves it if coverage was absent | `coverage_ref`(R, proves health) | M9 (Exception) | ### **requires a healthy `coverage_ref` (F-14); else this event is ILLEGAL — must be `ExpectationIndeterminate`**; `test_ev_overdue_requires_healthy_coverage` |
| **`ExpectationIndeterminate`** EX-3i | ### **proves the deadline passed while we were BLIND (channel down / coverage unknown)** · ¬proves the counterparty failed | `coverage_gap` | M9 (Exception, human) | ### **the honest "we weren't watching" (I8, T8)**; `test_ev_indeterminate_on_blind_window` |
| **`ExpectationReVersioned`** EX-5 | proves the deadline was amended | `deadline_history[]` | M8 | `test_ev_expectation_reversioned` |
| **`ExpectationCancelled`** EX-6 | proves the reason disappeared (e.g. load cancelled) | `reason` | Oversight | `test_ev_expectation_cancelled` |
| **`ExpectationExpired`** EX-7 | proves terminal age reached | — | M9 (Exception) | ### **never silent — raises an Exception**; `test_ev_expectation_expired_raises` |

## Cross-cutting
**Dedup:** `expectation_key` unique index (`WHERE state='RAISED'`). **Ordering:** discharge/expiry STRICT; a discharge before the raise is parked. **Replay:** ### **coverage-based `OVERDUE` vs `INDETERMINATE` replays deterministically from the coverage records** — the honesty distinction survives replay. **Projection:** none. **Security:** none specific. **Audit:** the `OVERDUE`-vs-`INDETERMINATE` split is a monitored honesty metric; ### **facility/appointment windows evaluated in the facility's local timezone across DST (F-25).** **Open validation:** V10 (ageing thresholds), V6 (deferred bounds) — fail-closed to `INDETERMINATE`.
