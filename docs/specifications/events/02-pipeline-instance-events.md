# Event Family F2 — Pipeline Instance Events

*Registry: `events/registry.md`. Producer: machine M2. Envelope + defaults: registry §1–§2.*

**Family defaults:** `aggregate_type=pipeline_instance`; ordering = ### **STRICT per-aggregate** (version-monotonic — a pipeline's stages must not reorder); security=`internal` (checkpoint events=`high`); projection-permitted = **none except `ProjectionUpdated`** (§7); `work_item_id`+`pipeline_instance_id` required on all.

| Event · v1 · producer | Proves / ¬Proves | Payload | Consumers → guard | Notes / tests |
|---|---|---|---|---|
| **`PipelineStarted`** PL-1 | proves an attempt began and holds the Layer-1 reservation · ¬proves any effect will occur (intent, ER-1) | `commit_key`(R) | Oversight | `test_ev_pipelinestarted_reserves` |
| **`DuplicateProposalAbsorbed`** PL-1b | proves a duplicate proposal for a reserved `commit_key` was absorbed | `commit_key`, `absorbed_ref` | Oversight | ### **one card, not two** (T4); `test_ev_duplicate_absorbed` |
| **`PolicyEvaluated`** PL-2 | proves policy ran and produced a **non-null** gate decision | `policy_version`(R), `gate_decision`(R), `decision`, `rules_matched[]`, `reason`(R) | Oversight; audit | ### **`gate_decision` NEVER null (F-20)**; deterministic-reproducible (M-50); `test_ev_policyevaluated_never_null_gate` |
| **`IntentValidated`** PL-4 | proves money+document fences passed and every material field is `consistent` · ¬proves approval or freshness (those are later) | — | Oversight | `test_ev_intentvalidated` |
| **`PipelineRejected`** PL-3/5 | proves the attempt was rejected pre-effect (policy deny, `FORBIDDEN`, validation fail) | `reason`(R) | Oversight; M1 | `test_ev_pipelinerejected` |
| **`ApprovalBound`** PL-7b | proves an approval was bound to THIS commit_key + fingerprint | `approval_id`(R), `material_facts_fingerprint`(R) | Oversight | `test_ev_approvalbound_this_commit_key` |
| **`CheckpointPassed`** PL-8 | ### **proves ALL SEVEN checks passed ATOMICALLY, live, and pins the full decision context** · ¬proves the effect happened (that follows at claim/verify) | ### `checkpoint_id`(R), `material_facts_fingerprint`(R), `entity_versions`(R, SD-3 set), `policy_version`(R), `brake_version`(R), `approval_id?`, `projected_observations_used[]`, `native_claims_used[]` | M3 (mint — co-commit) | **consequential** (§5); audit=`high`; the reproducibility anchor (§11); `test_ev_checkpointpassed_pins_everything` |
| **`CheckpointFailed`** PL-8f | proves the checkpoint refused, at the **first failing step** (SD-7 order) · ¬proves anything about later steps | `step`(R, 1–7), `reason`(R) | Oversight; M2 void | `test_ev_checkpointfailed_first_step` |
| **`PipelineVoided`** PL-7v/9v | proves the attempt was voided pre-claim (drift/policy/brake/expiry) — ### **nothing happened** | `reason`(R) | Oversight; M1 | `test_ev_pipelinevoided_nothing_happened` |
| **`EffectRecorded`** PL-12 | proves the verified effect was durably recorded **in the same commit as verify** | — | M2 (→project) | consequential; co-commit with `EffectVerified`; `test_ev_effectrecorded_same_commit_as_verify` |
| **`ProjectionUpdated`** PL-13 | ### **proves projected state was updated from VERIFIED evidence** · ¬proves anything optimistic | `entity_ref`, `from_effect_id`(R) | Projection reads | ### **the ONLY F2 event permitted to update projected truth, and ONLY from a verified effect (M-2, §7)**; `test_ev_projectionupdated_only_from_verified` |
| **`PipelineClosed`** PL-14 | proves the attempt completed · ¬proves the Work Item closed (WI-3 decides) | — | M1 (closure criterion) | `test_ev_pipelineclosed_does_not_close_work_item` |

## Cross-cutting
**Dedup:** transition-natural; ### **an outbox retry after a crash re-sends the identical `event_id`** (registry §4) ⇒ inbox no-op. **Ordering:** STRICT per-pipeline (a `GrantClaimed`-era event before `CheckpointPassed` is impossible; if delivered out of order, parked). **Replay:** ### **replaying `CheckpointPassed` constructs NO witness and mints NO grant** (ER-2) — it only rebuilds the pipeline's state row. **Projection:** only `ProjectionUpdated`, only from a verified effect. **Security:** the checkpoint's atomicity is enforced at the *transition* (no async work PL-8→PL-9); a stale-witness use at the adapter emits `StaleWitnessUsed` (F14). **Open validation:** V6 (deferred-verification bounds) — fail-closed.
