# Entity Specification — Expectation

*Conventions & `[C-n]`: see `00-conventions.md`. Lifecycle: canonical spec §12.8; F-14/F-25.*

1. **Canonical name.** Expectation.
2. **Definition.** A commitment that something should be observed by a deadline — the mechanism for time-driven and *non-event* work.
3. **Purpose.** To distinguish, honestly, ### **"the thing never happened" (`OVERDUE`) from "we were not watching" (`INDETERMINATE`)** — different facts (I8), and the difference between accusing a counterparty and admitting our own blindness.
4. **What it is not.** ### **Not a bare timer or SLA** (it carries observability coverage). Not an accusation until observability is proven. Not a gate — it **owes** something, it does not authorize.
5. **Owning component.** Expectation Service.
6. **Authority class.** **Neyma-native.**
7. **Tenant ownership.** `[C-1]`.
8. **Canonical identifier.** `expectation_id` (uuid).
9. **Natural / external identifiers.** ### **`expectation_key`** — `(tenant_id, subject_ref, expected_type)` — for duplicate prevention.
10. **Required attributes.** `expectation_id` · `tenant_id` · `expectation_key` · `subject_ref` (the load/document/movement) · `expected_type` (POD, remittance, appointment confirmation…) · **`expected_source`** (the channel) · **`deadline_utc`** · **`originating_timezone`** · `state` · `version` · `created_at`.
11. **Optional attributes.** `discharge_observation_id` · `overdue_at` · `coverage_ref` (the observation-coverage record consulted) · `owner_id` (assigned on `OVERDUE`/`INDETERMINATE`) · `deadline_history[]`.
12. **Enums.** `state ∈ {RAISED, DISCHARGED, OVERDUE, INDETERMINATE, CANCELLED, EXPIRED}` (spec §12.8). Terminal: `DISCHARGED, CANCELLED, EXPIRED`.
13. **Provenance requirements.** Discharge requires a **bound Observation** matching the expectation (its provenance flows through §12.5). `INDETERMINATE` is asserted from a **negative/absent** observation-coverage record.
14. **Relationships & cardinalities.** Subject 1 : N Expectation. Expectation 1 : 0..1 discharging Observation. Expectation 1 : 1 `coverage` window (consulted at deadline). An `OVERDUE`/`INDETERMINATE`/`EXPIRED` Expectation 1 : 1 Exception.
15. **Aggregate / transaction boundary.** Own aggregate; the deadline `TimerFired` transition + the coverage read + the resulting state are one transaction `[C-2]`.
16. **Database constraints.** `tenant_id, expectation_key, subject_ref, expected_type, expected_source, deadline_utc, originating_timezone, state, version NOT NULL`. **`deadline_utc` stored in UTC; `originating_timezone` retained.** **CHECK: `OVERDUE` requires a `coverage_ref` proving the channel was HEALTHY over the window.**
17. **Uniqueness constraints.** PK `(tenant_id, expectation_id)`. ### **`UNIQUE (tenant_id, expectation_key) WHERE state = 'RAISED'`** — duplicate-expectation prevention.
18. **Referential integrity.** `subject_ref`, `discharge_observation_id`, `coverage_ref`, `owner_id` FK.
19. **Versioning / OCC.** `[C-10]`. A **deadline change** re-versions (`ExpectationReVersioned`), retaining `deadline_history[]`.
20. **Lifecycle reference.** **Canonical spec §12.8** (complete). Not blocked.
21. **Creation rules.** Raised when a future observation is owed (a delivery ⇒ expect a POD; an invoice ⇒ expect a remittance; a rule like *"Customer Y requires hourly updates"* compiles to a recurring Expectation, spec §20.5). ### **The observability channel MUST be declared at creation.**
22. **Mutation rules.** Only via §12.8. Deadlines may be amended (re-versioned); the subject/type may not.
23. **Correction rules.** N/A — a wrong expectation is `CANCELLED` (reason disappeared), not corrected.
24. **Supersession rules.** N/A (a re-versioned deadline is not a supersession of the Expectation).
25. **Cancellation rules.** `ReasonDisappeared` (e.g. the load cancelled) ⇒ `CANCELLED`.
26. **Expiry rules.** ### **A terminal age past `OVERDUE`/`INDETERMINATE` ⇒ `EXPIRED` ⇒ Exception** (never silence). A **late arrival is always accepted** from `OVERDUE`/`INDETERMINATE` ⇒ `DISCHARGED{late}` (*the POD that arrives in month 4 is still a POD*).
27. **Reopening rules.** N/A.
28. **Deletion policy.** None `[C-9]`.
29. **Retention policy.** Permanent.
30. **Audit requirements.** Raise/discharge/overdue/indeterminate/cancel/expire events with the coverage basis for `OVERDUE` vs `INDETERMINATE`.
31. **Events emitted.** `ExpectationRaised` · `ExpectationDischarged{late?}` · `ExpectationOverdue` · **`ExpectationIndeterminate`** · `ExpectationReVersioned` · `ExpectationCancelled` · `ExpectationExpired`.
32. **Events consumed.** `ObservationBound` (discharge) · `TimerFired` (deadline/terminal age) · `DeadlineChanged` · `ReasonDisappeared`.
33. **Idempotency.** `[C-3]`. The `expectation_key` unique index prevents duplicate live expectations for the same owed observation.
34. **Replay behavior.** `[C-5]`. Replay reconstructs coverage-based `OVERDUE`/`INDETERMINATE` decisions deterministically from the coverage records.
35. **Security / authorization.** `[C-6]`. A model may propose that an Expectation is owed; the deadline and coverage are runtime-set.
36. **Fail-closed behavior.** ### **No coverage record proving health over the window ⇒ `INDETERMINATE`, NOT `OVERDUE`** (M-32) — it fails toward blindness, the safe direction. *We do not accuse a counterparty of a failure that was ours.*
37. **Structurally impossible states.** `OVERDUE` without a healthy-coverage `coverage_ref`. A deadline evaluated in the wrong timezone. Two `RAISED` expectations for one `expectation_key`. Silent expiry (no Exception).
38. **Interaction with the checkpoint.** Indirect — an owed-but-undischarged Expectation may make a field `unknown`, which the checkpoint treats as not-`consistent` (blocks consequential action).
39. **Interaction with Effect Grants.** `AWAITING_OBSERVATION` verification (spec §26.1) is driven by an Expectation, not a retry loop.
40. **Interaction with human approval.** An `OVERDUE`/`INDETERMINATE` Expectation raises an Exception a human owns; it does not itself gate.
41. **Interaction with policy & brake.** A compiled rule (*hourly updates*) is an Expectation, not a gate (spec §20.5). Under a brake, observation continues, so discharge and `INDETERMINATE` detection continue.
42. **Observability.** ### **Timezone-correct evaluation of facility/appointment windows in the FACILITY's local timezone** (spec §12.8, F-25). The `OVERDUE`-vs-`INDETERMINATE` split is itself a monitored honesty metric.
43. **Acceptance criteria.** (a) deadline passes while the channel is down ⇒ `INDETERMINATE`, not `OVERDUE`; (b) a late arrival discharges; (c) duplicate expectations are prevented; (d) an appointment window evaluates in facility-local time across a DST boundary; (e) expiry raises an Exception.
44. **Adversarial tests.** `test_deadline_passes_while_channel_down_yields_INDETERMINATE_not_OVERDUE` (M-32) · `test_late_arrival_discharges` · `test_duplicate_expectation_prevented` · `test_appointment_window_evaluated_in_facility_local_time_across_dst` (F-25) · `test_expiry_raises_an_exception_never_silence` · `test_overdue_requires_healthy_coverage`.
45. **Open validation questions.** **V10** (per-lane exception ageing thresholds) and **V6** (deferred-verification bounds). **Fail-closed defaults:** ages/escalates, never expires silently; unknown coverage ⇒ `INDETERMINATE`. **Not a block.**
