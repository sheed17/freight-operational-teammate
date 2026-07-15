# Entity Specification — Checkpoint Witness

*Conventions & `[C-n]`: see `00-conventions.md`. Definition: canonical spec §19.2–§19.3.*

1. **Canonical name.** Checkpoint Witness.
2. **Definition.** Immutable proof that all seven pre-effect checkpoint checks passed **atomically**, immediately before an Effect Grant claim.
3. **Purpose.** To make "the world was re-validated moments ago, and still held" a **thing the type system can require** — `mint_grant` takes a `CheckpointPassed` witness, so code that has not passed the checkpoint cannot express a mint.
4. **What it is not.** ### **Not seven independent results that can be cached and reused** (that is F-01). Not reusable. Not refreshable. Not sufficient alone — the adapter also needs a claimable grant.
5. **Owning component.** Safety Kernel (the checkpoint function).
6. **Authority class.** ### **Immutable record.** Written once by the checkpoint function; never transitions, never edited.
7. **Tenant ownership.** `[C-1]`.
8. **Canonical identifier.** `checkpoint_id` (uuid).
9. **Natural / external identifiers.** None. Bound 1:1 to the grant it authorizes.
10. **Required attributes** *(spec §19.3)*. `checkpoint_id` · `tenant_id` · `actor` · `accountable_owner` · `action_class` · `target_system` · `target_resource` · `operation` · `commit_key` · `material_facts_fingerprint` · `entity_versions` · `approval_fingerprint` (when required) · `policy_version` · `gate_decision` · `autonomy_state` · **`brake_version`** · `projected_observations_used[]` · `native_claims_used[]` · `created_at` · **`expires_at`** (the freshness window).
11. **Optional attributes.** `approval_id` (present iff the gate required a human).
12. **Enums.** `gate_decision` per the 4-member registry. No state enum — **the witness has no lifecycle.**
13. **Provenance requirements.** ### **`projected_observations_used[]` and `native_claims_used[]` pin the EXACT versions read.** No entry may be a `MODEL_INFERRED` material fact (M-16). The `material_facts_fingerprint` was computed from these pinned reads.
14. **Relationships & cardinalities.** Checkpoint Witness 1 : 1 Effect Grant. Checkpoint Witness N : 1 Pipeline Instance (a retry family has one witness per attempt). Witness → Observations/Claims used (evidence pins).
15. **Aggregate / transaction boundary.** ### **Inserted in ONE transaction with the grant mint and the pipeline `CHECKPOINT → GRANTED` transition** (spec §19.2). **No asynchronous work may occur between the seven checks and this insert** (M-40).
16. **Database constraints.** All point-10 columns `NOT NULL` (except the approval pair). ### **`gate_decision NOT NULL`** (F-20). `expires_at > created_at`. **Append-only — no `UPDATE`, no `DELETE`** `[C-8]`.
17. **Uniqueness constraints.** PK `(tenant_id, checkpoint_id)`. `UNIQUE (tenant_id, grant_id)` (1:1 to the grant).
18. **Referential integrity.** `grant_id`, `pipeline_instance_id`, `approval_id` (when present) FK. Each `projected_observations_used[]` / `native_claims_used[]` entry references a real observation/claim version.
19. **Versioning / OCC.** N/A — immutable, no version.
20. **Lifecycle reference.** ### **None — the Checkpoint Witness has no state machine. It is created once and is thereafter only VALID or STALE (a derived predicate, not a state):** valid iff `now() < expires_at` AND `brake_version = current` AND `policy_version = current`. Not blocked (an immutable record needs no lifecycle table).
21. **Creation rules.** Created **only** by the checkpoint function, **only** when all seven checks pass. ### **`CheckpointPassed` (the in-process type) has no public constructor.**
22. **Mutation rules.** ### **NONE. Immutable.**
23. **Correction rules.** N/A. A wrong checkpoint is not corrected; the pipeline `VOIDED` and re-checkpoints.
24. **Supersession rules.** N/A.
25. **Cancellation rules.** N/A (the grant it authorizes may be revoked; the witness record persists as evidence).
26. **Expiry rules.** ### **A stale witness is INVALID** (`now() ≥ expires_at`). The freshness window is short (bounds the claim-to-call gap). A stale witness at the adapter ⇒ refuse (M-41).
27. **Reopening rules.** N/A.
28. **Deletion policy.** None `[C-9]`.
29. **Retention policy.** Permanent — it is the evidentiary heart of "why did you act": the pinned versions of everything the decision depended on (spec §25, M-67).
30. **Audit requirements.** Emitted as `CheckpointPassed`. A failed checkpoint emits `CheckpointFailed{step, reason}` and **no witness is created**.
31. **Events emitted.** `CheckpointPassed` (with `checkpoint_id`).
32. **Events consumed.** None — it is a synchronous product of the checkpoint function, not an event handler.
33. **Idempotency.** A re-run of the checkpoint produces a **new** witness (new `checkpoint_id`, fresh reads). Witnesses are never reused.
34. **Replay behavior.** `[C-5]`. ### **Replay cannot construct a `CheckpointPassed`** (it performs no live revalidation) — this is the structural root of side-effect-free replay.
35. **Security / authorization.** ### **A model, an agent, an admin tool, a migration, a retry handler, and replay can NONE of them construct a witness** (M-47, M-65). This is capability-by-construction.
36. **Fail-closed behavior.** Any one of the seven checks failing ⇒ ### **no witness exists ⇒ no grant can be minted ⇒ no effect is possible.** There is no partial witness.
37. **Structurally impossible states.** A witness with a null `gate_decision`. A witness built from fewer than seven passing checks. A witness constructed outside the checkpoint function. A reused witness.
38. **Interaction with the checkpoint.** ### **It IS the output of the checkpoint** — the seven checks (spec §19.2): approval validity · material-facts fingerprint · projected freshness (live) · native-state validity · entity-version concurrency · policy · brake.
39. **Interaction with Effect Grants.** ### **`mint_grant(witness: CheckpointPassed, …)` — the witness is the required, non-forgeable argument.** The adapter re-validates `witness.checkpoint_id == grant.checkpoint_id` and freshness (the two-key rule).
40. **Interaction with human approval.** When the gate required a human, the witness binds `approval_id` and `approval_fingerprint`; step 2 re-checked that the approved fingerprint still holds.
41. **Interaction with policy & brake.** ### **Binds `policy_version` and `brake_version`; the adapter's claim CAS re-validates both — a change since the witness ⇒ the CAS fails, the witness is effectively invalid.**
42. **Observability.** Witness creation rate ≈ effect rate. `CheckpointFailed{step}` distribution shows which check blocks most (a drift-heavy step 2 = a fast-moving world or a flapping source).
43. **Acceptance criteria.** (a) no witness without all seven checks; (b) a stale witness is refused at the adapter; (c) a witness cannot be constructed outside the checkpoint; (d) replay constructs none; (e) `gate_decision` is never null.
44. **Adversarial tests.** `test_witness_has_no_public_constructor` · `test_stale_witness_after_brake_version_change_is_refused` (the named case from the brief) · `test_checkpoint_failure_creates_no_witness` · `test_replay_constructs_no_checkpoint_passed` `[C-5]` · `test_no_async_work_between_checkpoint_and_claim` (M-40) · `test_witness_pins_every_input_version` (M-67).
45. **Open validation questions.** The **freshness-window length** (`expires_at − created_at`). **Fail-closed default:** short, ≥ the claim-to-call latency, ≤ the grant TTL. Implementation tuning, **not a block.**
