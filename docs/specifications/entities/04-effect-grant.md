# Entity Specification — Effect Grant

*Conventions & `[C-n]`: see `00-conventions.md`. Ledger: canonical spec §19.6; lifecycle: ADR-004 §3.2 + spec §12.3 (shared row — see `03-external-effect.md` resolution box).*

1. **Canonical name.** Effect Grant.
2. **Definition.** Permission for **ONE attempt** to touch the world, right now — a durable row in the Effect Grant Ledger plus a signed opaque handle that points at it.
3. **Purpose.** To make external effects impossible **except** through a single-use, checkpoint-derived capability, so that bypass is structurally impossible rather than merely forbidden.
4. **What it is not.** ### **Not the authority itself — the authority is the LEDGER ROW; the handle is a pointer.** Not reusable. Not refreshable. ### **Not sufficient on its own — a fresh Checkpoint Witness is also required at the adapter (the two-key rule).**
5. **Owning component.** Effect Grant Ledger (Safety Kernel). ### **Minted by exactly one function, `mint_grant(witness: CheckpointPassed, …)`.**
6. **Authority class.** **Neyma-native** (a capability record). Same durable row as the External Effect.
7. **Tenant ownership.** `[C-1]`.
8. **Canonical identifier.** `grant_id` (uuid, PK).
9. **Natural / external identifiers.** `commit_key`. `handle_digest` (a digest of the issued handle; the handle itself is never stored).
10. **Required attributes** *(spec §19.6)*. `grant_id` · `tenant_id` · `action_class` · **`gate_decision` (NOT NULL)** · `target_system` · `target_resource_id` · `target_operation` · `commit_key` · `material_facts_fingerprint` · `entity_versions` (jsonb) · `policy_version` · **`brake_version`** · `checkpoint_id` (FK → Checkpoint Witness) · `pipeline_instance_id` · `state` · `issued_at` · `expires_at` · `handle_digest`.
11. **Optional attributes.** `approval_id` (see the CHECK) · `claimed_at`.
12. **Enums.** `state ∈ {GRANTED, CLAIMED, EXPIRED_UNCLAIMED, REVOKED}` *(the capability aspect; the outcome states `ATTEMPTED/VERIFIED/FAILED/UNKNOWN_OUTCOME` belong to the External Effect aspect of the same row — see resolution box)*. `gate_decision` per the canonical 4-member registry.
13. **Provenance requirements.** The bound `material_facts_fingerprint` was computed from runtime reads, never model output (M-13). No `MODEL_INFERRED` material fact could have reached the checkpoint that minted this grant (M-16).
14. **Relationships & cardinalities.** Pipeline Instance 1 : 0..1 Effect Grant. Effect Grant 1 : 1 Checkpoint Witness (`checkpoint_id`). Effect Grant 1 : 0..1 Approval. Effect Grant N : 1 `commit_key`.
15. **Aggregate / transaction boundary.** ### **Minted in ONE transaction with the Checkpoint Witness insert and the `CHECKPOINT → GRANTED` pipeline transition** (spec §19.2). ### **Claimed via an atomic CAS in ONE transaction with `EffectAttempted` and the `GRANTED → CLAIMED` transition** (spec §18 step 5). The ledger shares the store with pipeline state + outbox (A1).
16. **Database constraints.** All point-10 columns `NOT NULL` (except `approval_id`, `claimed_at`). ### **CHECK: `approval_id NOT NULL` when `gate_decision ∈ {HUMAN_APPROVAL_REQUIRED, PERMANENT_HUMAN_ASSERTION_REQUIRED}`.** `expires_at > issued_at`. FK `checkpoint_id`, `pipeline_instance_id`.
17. **Uniqueness constraints.** PK `(tenant_id, grant_id)`. ### **LAYER 2 COMMIT-ONCE: `UNIQUE (tenant_id, commit_key) WHERE state = 'CLAIMED'`** (spec §16.1). ### **This is the atomic claim-instant exclusion; the durable through-life hold (including `NEEDS_VERIFICATION`) is the Pipeline Instance Layer-1 reservation.**
18. **Referential integrity.** `checkpoint_id`, `pipeline_instance_id`, `approval_id` (when present) FK.
19. **Versioning / OCC.** The state transition `GRANTED → CLAIMED` is itself the concurrency control — the CAS. No separate version column is needed on the grant; the CAS is the guard.
20. **Lifecycle reference.** **ADR-004 §3.2** (`GRANTED → CLAIMED | EXPIRED_UNCLAIMED | REVOKED`) + the shared §12.3 outcome states. Not blocked.
21. **Creation rules.** ### **Minted ONLY by `mint_grant`, which requires a `CheckpointPassed` witness argument.** `CheckpointPassed` has no public constructor (spec §19.2). ### **Therefore code that has not passed the checkpoint cannot express a mint.**
22. **Mutation rules.** `GRANTED → CLAIMED` only via the CAS (`WHERE state='GRANTED' AND expires_at>now() AND brake_version=current AND policy_version=current`). `GRANTED → EXPIRED_UNCLAIMED` on TTL. `GRANTED → REVOKED` on brake/approval-revocation/policy-change/entity-freeze.
23. **Correction rules.** N/A — a grant is not corrected; a new attempt mints a new grant.
24. **Supersession rules.** N/A.
25. **Cancellation rules.** Revocation of an **unclaimed** grant is always safe (nothing happened). ### **Revoking a claimed grant does nothing** — the effect may already exist; that is `UNKNOWN_OUTCOME` territory, not revocation.
26. **Expiry rules.** ### **Short, absolute TTL — seconds, not minutes** (it must exceed the claim-to-call window, not the whole execution). An expired grant is unclaimable ⇒ re-checkpoint + re-mint.
27. **Reopening rules.** N/A.
28. **Deletion policy.** None `[C-9]` — a grant is the permanent record of *why* an effect was permitted.
29. **Retention policy.** Permanent.
30. **Audit requirements.** Every mint, claim, refusal, expiry, and revocation is an event. ### **An adapter invocation with no matching claimed grant is a Sev-0** (orphan detection).
31. **Events emitted.** `EffectGranted{grant_id}` · `GrantClaimed` · `ClaimRefused` · `GrantExpired` · `GrantRevoked`.
32. **Events consumed.** `CheckpointPassed` (mints) · `ClaimAttempted` (the adapter) · `TimerFired` (TTL) · `BrakeEngaged`/`PolicyVersionChanged`/`ApprovalRevoked`/`EntityFrozen` (revoke).
33. **Idempotency.** ### **Single-use is a database guarantee: the CAS `GRANTED → CLAIMED` succeeds for exactly one caller. A second claim matches zero rows and the adapter does nothing** (spec §18 step 5, §19.6). Not a token property.
34. **Replay behavior.** `[C-5]`. ### **Replay cannot construct a `CheckpointPassed`, therefore cannot mint a grant. Replaying the full corpus produces ZERO grants** (M-27).
35. **Security / authorization.** ### **The token is opaque AND signed — and NEITHER is the security control.** A forged handle names no ledger row ⇒ the claim fails. A replayed handle hits an already-`CLAIMED` row ⇒ the CAS fails. ### **The adapter re-validates tenant/action/target against its OWN call parameters — a mismatch is a Sev-0 confused-deputy event** (spec §18 step 4). Agents can never hold a grant (M-65).
36. **Fail-closed behavior.** No witness ⇒ no mint. Stale `brake_version`/`policy_version` at claim ⇒ CAS matches zero rows ⇒ adapter does nothing. A claim after expiry ⇒ nothing.
37. **Structurally impossible states.** A grant that exists without a `checkpoint_id`. A second `CLAIMED` grant for one `commit_key` (Layer 2). A grant minted by anything but `mint_grant`. A grant reachable by an agent.
38. **Interaction with the checkpoint.** ### **The grant is the OUTPUT of a passed checkpoint** — it binds `checkpoint_id`, `material_facts_fingerprint`, `entity_versions`, `policy_version`, `brake_version`, and (when required) `approval_id`.
39. **Interaction with Effect Grants.** (self) — one per attempt, single-use.
40. **Interaction with human approval.** When the gate requires it, `approval_id` is bound and enforced by a DB CHECK; the approval is `CONSUMED` in the claim transaction.
41. **Interaction with policy & brake.** ### **`policy_version` and `brake_version` are bound at mint and RE-VALIDATED in the claim CAS** — if either moved between mint and claim, the claim fails. This is how a brake engaged mid-flight makes the claim match zero rows (spec §21.4).
42. **Observability.** Grant mint/claim/refusal rates; ### **a Layer-2 refusal in production is a Sev-1 — it means something proposed an effect outside the pipeline (the R-02 signature).**
43. **Acceptance criteria.** (a) mint requires a witness (type-level); (b) two claims ⇒ exactly one succeeds; (c) a forged/replayed handle fails; (d) a wrong-target grant is refused with a Sev-0; (e) a brake between mint and claim makes the claim fail; (f) replay mints zero.
44. **Adversarial tests.** `test_bypass_calling_adapter_without_grant_fails` · `test_two_key_stale_witness_is_refused` (M-41) · `test_forged_handle_fails_to_claim` · `test_replayed_grant_second_claim_fails` · `test_confused_deputy_wrong_target_is_sev0` · `test_expired_grant_claim_fails` · `test_brake_between_mint_and_claim_fails_the_claim` · `test_commit_once_two_concurrent_pipelines_one_claims` · `test_replay_full_corpus_produces_zero_grants` `[C-5]` · `test_import_graph_no_module_outside_pipeline_imports_adapters` (spec §19.9).
45. **Open validation questions.** **Grant TTL length** (seconds — how many, vs the observed 20–35 s browser-actuation window). **Fail-closed default:** a conservative TTL exceeding the claim-to-call window; **an expired grant simply re-checkpoints.** Implementation tuning, **not a design block.**
