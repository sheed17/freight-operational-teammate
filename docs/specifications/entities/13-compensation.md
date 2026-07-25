# Entity Specification — Compensation

*Conventions & `[C-n]`: see `00-conventions.md`. Lifecycle: canonical spec §12.10; F-17.*

1. **Canonical name.** Compensation.
2. **Definition.** The undoing of an external effect that should not have happened — ### **itself a separately gated external effect.**
3. **Purpose.** To reverse a *verified* effect that a later correction invalidated, through the **full pipeline** — never through a privileged undo.
4. **What it is not.** ### **Not a fast path. Not a rollback that bypasses the gates** (that is an ungated write with a good excuse). Not a cancellation (cancellation is pre-claim; compensation is post-effect). Not applicable to an unknown outcome.
5. **Owning component.** Compensation Service (spawns a Pipeline Instance to execute).
6. **Authority class.** **Neyma-native** (the compensation record); its execution is an External Effect.
7. **Tenant ownership.** `[C-1]`.
8. **Canonical identifier.** `compensation_id` (uuid).
9. **Natural / external identifiers.** `original_effect_id` (the `VERIFIED` External Effect being undone) + `commit_key` (its own, for the compensating effect).
10. **Required attributes.** `compensation_id` · `tenant_id` · `original_effect_id` · `commit_key` · `state` · `version` · **`exposure`** (the dollar amount at stake) · `owner_id` (a human, from `REQUIRED`) · `reason` (the correction that invalidated the original) · `created_at`.
11. **Optional attributes.** `pipeline_instance_id` (the executing attempt) · `approval_id` · `reality_decision_ref` (on human-established resolution).
12. **Enums.** `state ∈ {REQUIRED, APPROVED, EXECUTING, COMPLETED, COMPENSATION_FAILED, NOT_POSSIBLE}` (spec §12.10). Terminal: `COMPLETED`. ### **Non-terminal, human-owned: `COMPENSATION_FAILED`, `NOT_POSSIBLE`.**
13. **Provenance requirements.** The invalidating correction carries a `decision_ref` (human) or a deterministic rule id; ### **a compensation is never raised from a `MODEL_INFERRED` conclusion.**
14. **Relationships & cardinalities.** External Effect 1 : 0..1 Compensation. Compensation 1 : 0..1 executing Pipeline Instance. A correction (§10.2) 1 : N Compensation (a storm raises many, **each individually gated**).
15. **Aggregate / transaction boundary.** Own aggregate; transitions `[C-2]`. ### **Execution is a SEPARATE Pipeline Instance** with its own checkpoint, grant, approval, and readback — not a sub-transaction of the original.
16. **Database constraints.** `tenant_id, original_effect_id, commit_key, state, version, exposure, owner_id, reason NOT NULL`. **CHECK: `owner_id NOT NULL` from `REQUIRED`.** ### **CHECK: a transition to `EXECUTING` requires a bound `pipeline_instance_id` (the gated attempt).**
17. **Uniqueness constraints.** PK `(tenant_id, compensation_id)`. `UNIQUE (tenant_id, original_effect_id) WHERE state != 'NOT_POSSIBLE'` (one active compensation per invalidated effect). The executing pipeline uses its own commit-key uniqueness.
18. **Referential integrity.** `original_effect_id`, `pipeline_instance_id`, `approval_id`, `owner_id` FK.
19. **Versioning / OCC.** `[C-10]`.
20. **Lifecycle reference.** **Canonical spec §12.10** (complete). Not blocked.
21. **Creation rules.** Raised by `CorrectionInvalidatedAnEffect` **only when the original effect is `VERIFIED`.** ### **If the original is `UNKNOWN_OUTCOME`, creation is REFUSED (M-33)** — the compensation waits; a human resolves the unknown first.
22. **Mutation rules.** Only via §12.10. ### **`REQUIRED → APPROVED` requires a human — money-affecting compensation is ALWAYS `HUMAN_APPROVAL_REQUIRED`.**
23. **Correction rules.** N/A.
24. **Supersession rules.** N/A.
25. **Cancellation rules.** N/A once `REQUIRED` (the exposure exists); resolution is via completion or human-established reality.
26. **Expiry rules.** ### **NEVER.** `COMPENSATION_FAILED` and `NOT_POSSIBLE` are non-terminal and human-owned.
27. **Reopening rules.** N/A.
28. **Deletion policy.** None `[C-9]`.
29. **Retention policy.** Permanent.
30. **Audit requirements.** `CompensationRequired{exposure}`, approval, execution, completion/failure/impossible — with the invalidating `reason` and `decision_ref`.
31. **Events emitted.** `CompensationRequired{exposure}` · `CompensationRefused{unknown}` · `CompensationApproved` · `CompensationStarted` · `CompensationCompleted` · `CompensationFailed{exposure}` · `CompensationImpossible{exposure}` · `RealityEstablished`.
32. **Events consumed.** `CorrectionInvalidatedAnEffect` · `HumanApproved` · `NoCompensatingActionExists` · `PipelineClosed`/`PipelineFailed`/`NEEDS_VERIFICATION` (from its executing pipeline) · `HumanEstablishedReality{decision_ref}`.
33. **Idempotency.** `[C-3]`. The unique index prevents a second active compensation for one invalidated effect. Its executing pipeline has commit-once.
34. **Replay behavior.** `[C-5]`. Replay reconstructs the compensation record; the compensating effect (like any effect) is never produced by replay.
35. **Security / authorization.** ### **A compensation IS an effect — it passes the full checkpoint** `[C-6]`. It cannot bypass the pipeline. Under a brake it is **blocked** like any effect (an urgent compensation requires a human to narrow the brake — spec §21.5).
36. **Fail-closed behavior.** ### **FORBIDDEN on an `UNKNOWN_OUTCOME`** — *you cannot undo what you cannot prove you did, and a compensating write can CREATE the very state it meant to remove* (M-33). `EXECUTING → COMPENSATION_FAILED` (non-terminal) when its pipeline fails or goes unknown. `NOT_POSSIBLE` when the world offers no undo (a sent email, a wire) — the system says so honestly and escalates.
37. **Structurally impossible states.** A compensation of an `UNKNOWN_OUTCOME`. A compensating effect that bypassed the checkpoint. A `COMPENSATION_FAILED` moved by a timer. A bulk-undo (each is individually gated).
38. **Interaction with the checkpoint.** ### **Its execution IS a checkpoint pass** — the compensating effect is validated exactly as any effect.
39. **Interaction with Effect Grants.** The compensating effect claims its own single-use grant under its own commit key.
40. **Interaction with human approval.** Always `HUMAN_APPROVAL_REQUIRED` for money-affecting compensation; the human sees the exposure.
41. **Interaction with policy & brake.** ### **Blocked under an active brake** (a brake engaged because the system is misbehaving must not permit that same system to write "corrections" into the TMS). An urgent compensation requires an explicit human brake-narrow.
42. **Observability.** ### **`COMPENSATION_FAILED` and `NOT_POSSIBLE` are the most dangerous states the system can be in (reality and projection are known to diverge)** — they must be loud, owned, and carry the exposure.
43. **Acceptance criteria.** (a) compensation of an unknown outcome is refused; (b) execution passes the full pipeline; (c) money-affecting compensation is `HUMAN_APPROVAL_REQUIRED`; (d) no bulk undo — a storm raises N individually-gated compensations, aggregate exposure shown first; (e) `COMPENSATION_FAILED` never auto-resolves.
44. **Adversarial tests.** `test_cannot_compensate_an_unknown_outcome` (M-33) · `test_compensation_passes_the_full_pipeline` · `test_money_compensation_is_human_approval_required` · `test_compensation_storm_is_n_individually_gated_not_bulk` · `test_compensation_blocked_under_active_brake` · `test_compensation_failed_never_auto_resolves` · `test_not_possible_escalates_honestly`.
45. **Open validation questions.** **V1** interaction (reopening a written-off load may raise a compensation for a prior write-off). **Fail-closed default:** the generic machinery exists; each compensation is human-approved. **Not a block.**
