# Entity Specification — Brake

*Conventions & `[C-n]`: see `00-conventions.md`. Lifecycle: canonical spec §12.13; ADR-011.*

1. **Canonical name.** Brake (Human Brake).
2. **Definition.** ### **Admission control — a global withdrawal of the capability to act, enforced at the effect boundary by REFUSING TO MINT and REFUSING TO CLAIM. It is not a UI button and not a policy rule.**
3. **Purpose.** To let a human (or a Sev-0 detector) stop Neyma from acting **instantly, when the system is broken**, without killing in-flight work and without manufacturing an unknown outcome.
4. **What it is not.** ### **Not process termination** (a brake that kills workers manufactures an `UNKNOWN_OUTCOME`). Not a policy (one reason you pull it is that the policy engine is wrong). Not an entity freeze (an entity is already frozen by a Conflict/`NEEDS_VERIFICATION`/`COMPENSATION_FAILED`). Not an HR control on a person.
5. **Owning component.** Safety Kernel.
6. **Authority class.** **Neyma-native.**
7. **Tenant ownership.** `[C-1]` (a `GLOBAL`-scoped brake spans tenants but is still recorded per-tenant for enforcement; the tenant-isolation-breach trigger engages a global brake).
8. **Canonical identifier.** `brake_id` (uuid).
9. **Natural / external identifiers.** `scope` (the dimension it applies to). ### **`brake_version`** — monotonic, GLOBAL per tenant — is the value bound into every Witness/Grant.
10. **Required attributes.** `brake_id` · `tenant_id` · `scope` · `state` · **`brake_version`** · `actor` (a human id **or** a named detector id) · `engaged_reason` · `engaged_at`.
11. **Optional attributes.** `released_by` · `release_decision_ref` · `released_at`.
12. **Enums.** ### **`state ∈ {ACTIVE, RELEASED}` — and no others** (spec §12.13). Terminal: `RELEASED`. `scope` dimension ∈ `{GLOBAL, TENANT, INTEGRATION(target_system), ACTION_CLASS, COUNTERPARTY}`.
13. **Provenance requirements.** `actor` records **who or which detector** engaged it — a human id (may release) or a detector id (may never release).
14. **Relationships & cardinalities.** Tenant 1 : N Brake (over time / different scopes). ### **A brake is consulted by every checkpoint (step 7) and every claim CAS in scope.** It owns no per-effect record; its `brake_version` is bound into every Witness/Grant.
15. **Aggregate / transaction boundary.** ### **Engagement is a SINGLE ROW WRITE** in the transactional store (so it works when the system is broken). Checkpoint step 7 and the claim CAS read brake state **in the same transaction** as the other checks.
16. **Database constraints.** `tenant_id, scope, state, brake_version, actor, engaged_reason, engaged_at NOT NULL`. ### **CHECK: `state = RELEASED` requires a non-null `released_by` (an authenticated human) AND `release_decision_ref`.** **CHECK: `released_by` is never a detector id.**
17. **Uniqueness constraints.** PK `(tenant_id, brake_id)`. `brake_version` monotonic per tenant. `UNIQUE (tenant_id, scope) WHERE state = 'ACTIVE'` (one active brake per scope; overlapping scopes are separate rows, all consulted).
18. **Referential integrity.** `released_by` FK → an authenticated human with release authority (the Policy Owner by default). `release_decision_ref` FK.
19. **Versioning / OCC.** ### **`brake_version` is the concurrency mechanism** — any brake change increments it, invalidating all outstanding witnesses/grants for the tenant.
20. **Lifecycle reference.** **Canonical spec §12.13** (complete — two states). Not blocked.
21. **Creation rules.** ### **Engaged by any authenticated human instantly (no approval, no ceremony), OR by an automated Sev-0 detector** (orphan adapter, tenant-isolation breach ⇒ GLOBAL, rebuild divergence, repeated unknown outcomes, credential compromise, fraud-signal threshold, integration corruption). ### **Never requires the system to be healthy.**
22. **Mutation rules.** Only via §12.13. `BrakeWidened` (narrows authority) may be human or automation; `BrakeNarrowed`/`BrakeReleased` (broadens authority) is an authenticated human only. ### **A `TimerFired` transition is ILLEGAL — a brake never expires.**
23. **Correction rules.** N/A.
24. **Supersession rules.** N/A (scope changes are `BrakeWidened`/`BrakeNarrowed`, not supersession).
25. **Cancellation rules.** Release (`→ RELEASED`) is the only exit, human-only, with release conditions (point 36).
26. **Expiry rules.** ### **NEVER. No TTL. A brake that expires releases itself while nobody is looking — and a clock cannot know whether the fire is out.**
27. **Reopening rules.** N/A (a new incident is a new brake).
28. **Deletion policy.** None `[C-9]`.
29. **Retention policy.** Permanent (the incident record).
30. **Audit requirements.** Engage/widen/narrow/release events with actor, reason, `brake_version`, and (release) `decision_ref`. The brake report (point 42) is the incident timeline.
31. **Events emitted.** `BrakeEngaged{scope, actor, reason, brake_version}` · `BrakeWidened{brake_version}` · `BrakeNarrowed{brake_version}` · `BrakeReleased{decision_ref, brake_version}`.
32. **Events consumed.** Sev-0 detector signals · human engage/release commands.
33. **Idempotency.** `[C-3]`. ### **Engagement is idempotent on scope — repeated engagement is one `ACTIVE` brake and a rising signal count; a flapping detector cannot open a window because it cannot self-release.**
34. **Replay behavior.** `[C-5]`. Brake history replays; it never re-engages a real brake as a side effect.
35. **Security / authorization.** ### **A model/agent may NEVER engage or release** (M-60). ### **Automation may engage/widen; it may NEVER release/narrow.** A detector that engaged a brake may never release it (a detector that could clear its own alarm is not a detector).
36. **Fail-closed behavior.** ### **The brake store unreachable at checkpoint ⇒ no effect is possible** ("cannot read the brake" must never mean "the brake is off"). ### **Release requires: every in-flight effect accounted for; no unresolved Sev-0; integration health POSITIVELY demonstrated; a `decision_ref`.** Unresolved unknown outcomes do not block release but must be explicitly acknowledged and owned (and their entities stay frozen regardless).
37. **Structurally impossible states.** A brake with a third state. An expired/auto-released brake. A detector-released brake. A release without a `decision_ref`. A release that reactivates stale witnesses/grants.
38. **Interaction with the checkpoint.** ### **This entity IS checkpoint step 7.** An `ACTIVE` brake in scope ⇒ no witness ⇒ no mint. `brake_version` is bound into the Witness.
39. **Interaction with Effect Grants.** ### **The claim CAS re-validates `brake_version`; a brake engaged between mint and claim makes the CAS match zero rows — the adapter does nothing** (the brake-vs-claim race: never both, never neither). Unclaimed grants become unclaimable; ### **claimed grants run to verification (the brake cannot un-ring a bell).**
40. **Interaction with human approval.** Pending approvals remain recorded but cannot authorize execution; `BrakeEngaged` ⇒ `VOID_ON_BRAKE` on an approval. ### **On release, every queued consequential action passes a NEW full checkpoint** (M-62) — most old approvals will be `VOID_ON_DRIFT` (the world moved while stopped).
41. **Interaction with policy & brake.** Precedence layer 3 (above all policy); it denies regardless of what policy permits. Compensation and migration tools are **blocked** under a brake; observation/reconciliation **continue**; agents were never a threat (inert proposals).
42. **Observability.** ### **A hidden brake is a silent degradation and violates R17** — every operator surface reports it unprompted: scope, what is still allowed, reason, actor (human or named detector), time engaged, prevented effects, in-flight effects and their status, unresolved unknown outcomes with exposure, and the exact release requirements.
43. **Acceptance criteria.** (a) engaging during an adapter call does not create an unknown outcome; (b) a brake between mint and claim makes the claim match zero rows (10,000× interleaved: never both, never neither); (c) it engages with the policy engine and TMS down; (d) automation can engage but never release; (e) release re-checkpoints all queued work; (f) it never auto-expires.
44. **Adversarial tests.** `test_engaging_the_brake_during_an_adapter_call_does_not_create_an_unknown_outcome` · `test_brake_between_mint_and_claim_race_never_both_never_neither` · `test_brake_engages_with_policy_engine_and_tms_down` (M-61) · `test_automation_can_engage_but_never_release` (M-60) · `test_release_re_checkpoints_all_queued_work` (M-62) · `test_stale_grant_after_release_is_refused` · `test_no_timer_can_move_a_brake` · `test_detector_cannot_release_its_own_brake` · `test_active_brake_is_reported_unprompted_on_every_surface` (R17) · `test_fail_closed_on_unreadable_brake`.
45. **Open validation questions.** **V13** (who may engage — **recommend everyone authenticated**), **V14** (who may release — **recommend a narrower set; the asymmetry is the control**), **V15** (should repeated unknown outcomes auto-engage — **recommend 2 per integration per window**). **Fail-closed defaults** in place. **None is a block.**
