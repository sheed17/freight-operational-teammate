# Entity Specification — Pipeline Instance

*Conventions & `[C-n]`: see `00-conventions.md`. Lifecycle: canonical spec §12.2.*

1. **Canonical name.** Pipeline Instance.
2. **Definition.** One durable attempt to produce one effect. ### **The Pipeline Instance IS the command.**
3. **Purpose.** To carry a single intended effect through validation → the human gate → the atomic checkpoint → a single-use grant claim → verification → recording, durably and idempotently, so a crash at any point leaves a resumable, inspectable instance rather than a void.
4. **What it is not.** Not the intent (that is the Work Item). Not the outcome record (that is the External Effect). Not a `Command`. Not retryable in place. Not reopenable.
5. **Owning component.** Pipeline Service (the Safety Kernel hosts the checkpoint it calls).
6. **Authority class.** **Neyma-native.**
7. **Tenant ownership.** `[C-1]`.
8. **Canonical identifier.** `pipeline_instance_id` (uuid).
9. **Natural / external identifiers.** **`commit_key`** — the identity of the *effect* this instance attempts (spec §19.7). Multiple instances (retries) share one `commit_key`.
10. **Required attributes.** `pipeline_instance_id` · `tenant_id` · `work_item_id` (FK) · **`commit_key`** · `action_class` · `state` · `version` · `target_system` · `target_resource_id` · `target_operation` · `created_at` · `accountable_owner` (= the Work Item's owner).
11. **Optional attributes.** `approval_id` (when the gate requires one) · `checkpoint_id` · `grant_id` · `external_effect_id` · `unknown_reason` (only in `NEEDS_VERIFICATION`) · `void_reason` · `absorbed_evidence[]` (proposals absorbed per M-29).
12. **Enums.** `state ∈ {PROPOSED, POLICY_CHECKED, VALIDATED, AWAITING_APPROVAL, CHECKPOINT, GRANTED, CLAIMED, EXECUTED, VERIFIED, RECORDED, PROJECTED, CLOSED, REJECTED, VOIDED, FAILED, NEEDS_VERIFICATION}`. Terminal: `CLOSED, REJECTED, VOIDED, FAILED`. ### **Non-terminal, human-owned: `NEEDS_VERIFICATION`.** `action_class` and `gate_decision` per the canonical registry.
13. **Provenance requirements.** No material fact of a `MODEL_INFERRED` provenance may reach the checkpoint `[C-7]`, M-16. The proposing agent's output is inert `ProposedIntent`.
14. **Relationships & cardinalities.** **Work Item 1 : N Pipeline Instance.** Pipeline Instance 1 : 0..1 Approval. Pipeline Instance 1 : 0..1 Checkpoint Witness. Pipeline Instance 1 : 0..1 Effect Grant. Pipeline Instance 1 : 0..1 External Effect. Pipeline Instance N : 1 `commit_key` (the retry family).
15. **Aggregate / transaction boundary.** Aggregate root for one attempt. ### **The `CHECKPOINT → GRANTED` transition, the Checkpoint Witness insert, and the Effect Grant mint occur in ONE transaction** (spec §19.2). The `GRANTED → CLAIMED` transition occurs in the **claim CAS transaction** (spec §18 step 5). All other transitions are ordinary `[C-2]`.
16. **Database constraints.** `tenant_id, work_item_id, commit_key, action_class, state, version, accountable_owner NOT NULL`. **CHECK: `approval_id NOT NULL` when `gate_decision ∈ {HUMAN_APPROVAL_REQUIRED, PERMANENT_HUMAN_ASSERTION_REQUIRED}` at `CHECKPOINT` and beyond.** **CHECK: `unknown_reason NOT NULL` iff `state = NEEDS_VERIFICATION`.**
17. **Uniqueness constraints.** PK `(tenant_id, pipeline_instance_id)`. ### **LAYER 1 RESERVATION: `UNIQUE (tenant_id, commit_key) WHERE state NOT IN ('CLOSED','REJECTED','VOIDED','FAILED')`** (spec §16.1). This is the commit-key reservation — one non-terminal pipeline per effect. **`NEEDS_VERIFICATION` is non-terminal, so it HOLDS the reservation** (ADR-009 §3.3).
18. **Referential integrity.** `work_item_id` FK. `approval_id`/`checkpoint_id`/`grant_id`/`external_effect_id` FK when present.
19. **Versioning / OCC.** `[C-10]`.
20. **Lifecycle reference.** **Canonical spec §12.2** (complete, 16 states). Not blocked.
21. **Creation rules.** Created from a `ProposedIntent` (agent, sweep, human instruction, or a completed pipeline chaining work). ### **Creation ACQUIRES the Layer-1 reservation in the same transaction.** A second proposal for a held `commit_key` is **absorbed** (M-29), not created.
22. **Mutation rules.** Only via §12.2 transitions. ### **A retry is NEVER an in-place mutation — it is a NEW Pipeline Instance with the same `commit_key` and a new grant** (M-42 area, ADR-009).
23. **Correction rules.** N/A in place. A wrong proposal is `REJECTED`/`VOIDED`; a corrected attempt is a new instance.
24. **Supersession rules.** N/A — attempts are immutable history.
25. **Cancellation rules.** ### **Only before `CLAIMED`** (⇒ `VOIDED`). **After `CLAIMED`, cancellation is meaningless — post-claim undo is Compensation** (spec §12.2, §12.10).
26. **Expiry rules.** Grant TTL before claim ⇒ `VOIDED` (safe — nothing happened). Approval TTL ⇒ `VOIDED`. ### **`NEEDS_VERIFICATION` NEVER expires** (M-73).
27. **Reopening rules.** ### **Never.** Reopening happens at the Work Item.
28. **Deletion policy.** None `[C-9]`.
29. **Retention policy.** Permanent.
30. **Audit requirements.** Every transition is an Audit Event. `CheckpointFailed{step}`, `GrantClaimed`, `PipelineVoided{reason}` are load-bearing for explainability (spec §25).
31. **Events emitted.** `PipelineStarted` · `DuplicateProposalAbsorbed` · `PolicyEvaluated{policy_version}` · `IntentValidated` · `PipelineRejected{reason}` · `ApprovalRequested` · `ApprovalBound` · `CheckpointPassed`/`CheckpointFailed{step}` · `EffectGranted{grant_id}` · `EffectAttempted` · `PipelineVoided{reason}` · `EffectExecuted` · `EffectVerified` · `EffectFailed{proof}` · `OutcomeUnknown{exposure,unknown_reason}` · `VerificationConflict` · `VerificationUnavailable` · `EffectRecorded` · `ProjectionUpdated` · `PipelineClosed` · `RealityEstablished`.
32. **Events consumed.** `IntentProposed` · `ApprovalGranted`/`ApprovalDenied`/`ApprovalExpired` · `BrakeEngaged` · `GrantExpired`/`GrantRevoked` · `AdapterReturnedSuccess`/`AdapterRejectedPreFlight`/`OutcomeUnknown` · `ReadbackConfirmed`/`ReadbackContradicts`/`ReadbackUnavailable`/`VerificationDeferred` · `HumanEstablishedReality{decision_ref}` · `LaterObservationProves`.
33. **Idempotency.** `[C-3]`. ### **The claim is single-use via the Effect Grant CAS — a redelivered claim finds the grant not-`GRANTED` and does nothing** (spec §18 step 5). Commit-once across retries via Layer 1 + the grant ledger.
34. **Replay behavior.** `[C-5]`. ### **Replay of a Pipeline Instance produces NO grant and NO `EffectAttempted`** — it cannot construct a `CheckpointPassed`.
35. **Security / authorization.** `[C-6]`. The proposing actor may be an agent (inert). The approving actor (when required) is an authenticated human. Adapters are unreachable except through the grant+witness.
36. **Fail-closed behavior.** Any checkpoint step failing ⇒ no witness ⇒ no grant ⇒ no effect. An unreadable authoritative source at step 3 is **not** "no drift" — fail closed. Ambiguous outcome ⇒ `NEEDS_VERIFICATION`, never `FAILED`.
37. **Structurally impossible states.** Reaching `GRANTED` without a `CheckpointPassed` witness. `CLAIMED` without a successful CAS. `NEEDS_VERIFICATION` without an `unknown_reason`. Two non-terminal instances sharing a `commit_key` (Layer 1). A timer moving `NEEDS_VERIFICATION`.
38. **Interaction with the checkpoint.** ### **This entity IS the caller of the atomic pre-effect checkpoint** (spec §19.2). It transitions `CHECKPOINT → GRANTED` only on `CheckpointPassed`.
39. **Interaction with Effect Grants.** Holds `grant_id`; mints exactly one grant per attempt; the grant is single-use.
40. **Interaction with human approval.** `AWAITING_APPROVAL` binds an Approval to *this* `commit_key` and *this* fingerprint. Drift after approval ⇒ `VOID_ON_DRIFT` on the Approval ⇒ pipeline `VOIDED`.
41. **Interaction with policy & brake.** Step 6 (policy) and step 7 (brake) are checkpoint checks. `BrakeEngaged` while `AWAITING_APPROVAL`/`GRANTED` ⇒ `VOIDED` (pre-claim, safe). A claimed effect proceeds to verification (the brake never kills it).
42. **Observability.** `NEEDS_VERIFICATION` instances are a Sev-1 operational queue with owner, age, and exposure. Checkpoint-failure reasons are queryable.
43. **Acceptance criteria.** (a) `GRANTED` unreachable without a witness; (b) drift after approval voids; (c) a retry is a new instance with the same `commit_key`; (d) `NEEDS_VERIFICATION` never auto-resolves; (e) Layer-1 reservation absorbs a concurrent duplicate into one card.
44. **Adversarial tests.** `test_reaching_granted_without_witness_is_impossible` · `test_F01_drift_after_approval_voids` · `test_two_concurrent_proposals_produce_one_card_one_approval` (M-29) · `test_no_timer_can_move_needs_verification` (M-73) · `test_claim_is_single_use` · `test_replay_produces_zero_grants` `[C-5]` · `test_brake_pre_claim_voids_post_claim_verifies` · `test_cross_tenant_commit_key_no_collision` `[C-1]`.
45. **Open validation questions.** **V6:** deferred-verification bounds per TMS (how long `VERIFICATION_DEFERRED` may wait). **Fail-closed default:** treat as `AWAITING_OBSERVATION` with an Expectation. **Not a block.**
