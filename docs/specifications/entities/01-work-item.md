# Entity Specification — Work Item

*Conventions & cross-cutting `[C-n]`: see `00-conventions.md`. Lifecycle: canonical spec §12.1.*

1. **Canonical name.** Work Item.
2. **Definition.** The unit of business responsibility and closure. Intent originates here.
3. **Purpose.** To hold *what the business owes someone*, with an accountable human owner at all times, until it is explicitly closed with a recorded decision.
4. **What it is not.** Not an attempt (that is a Pipeline Instance). Not a task-queue row. Not closable by silence. Not the effect. Not a `Command` (no such entity).
5. **Owning component.** Work Service.
6. **Authority class.** **Neyma-native.**
7. **Tenant ownership.** `[C-1]`.
8. **Canonical identifier.** `work_item_id` (uuid).
9. **Natural / external identifiers.** None. A Work Item may *reference* a projected entity (`entity_ref`) but is not identified by it.
10. **Required attributes.** `work_item_id` · `tenant_id` · `type` · `state` · `version` · **`owner_id` (an authenticated human — never null, never "system", **I1**)** · `created_at` · `phase_seq` (int, default 1) · `entity_ref` (nullable — the projected entity this concerns).
11. **Optional attributes.** `reopens` (a prior `work_item_id`) · `escalation_at` · `blocker_ref` · `exposure` (money exposure, if any — **never a stored money value derived from memory; sourced from a live/verified observation only**).
12. **Enums.** `state ∈ {OPEN, IN_PROGRESS, BLOCKED, AWAITING_HUMAN, ESCALATED, CLOSED, CANCELLED}` (spec §12.1). Terminal: `CLOSED`, `CANCELLED`.
13. **Provenance requirements.** The `owner_id` and every closure/cancellation carries an `actor` and (for terminal transitions) a `decision_ref`. `[C-7]` applies to any claim-derived field.
14. **Relationships & cardinalities.** **Work Item 1 : N Pipeline Instance** (spec §13). Work Item 1 : N Exception (may raise many). Work Item 1 : 0..1 `reopens` (self, linked-item reopening). Work Item N : 0..1 `entity_ref`.
15. **Aggregate / transaction boundary.** The Work Item is its own aggregate root. A transition + emitted events = one transaction `[C-2]`. **It does not share a transaction with its Pipeline Instances** — those are separate aggregates coordinated by events.
16. **Database constraints.** `tenant_id NOT NULL` · `owner_id NOT NULL` · `state NOT NULL` · `version NOT NULL` · `type NOT NULL` · **CHECK: a transition to `CLOSED` or `CANCELLED` requires a non-null `decision_ref` on the emitting event** (enforced at the transition layer; see point 22).
17. **Uniqueness constraints.** PK `(tenant_id, work_item_id)`. No business-natural uniqueness (two distinct obligations about the same load are two Work Items).
18. **Referential integrity.** `owner_id` FK → an authenticated user of the tenant. `reopens` FK → `work_items(tenant_id, work_item_id)`. `entity_ref` is a soft reference (projected entities may not yet exist — parked per M-26).
19. **Versioning / OCC.** `[C-10]`. `version` increments on every transition.
20. **Lifecycle reference.** **Canonical spec §12.1** (complete). Not blocked.
21. **Creation rules.** Created by the Work Service on: an inbound Observation that implies an obligation, a human instruction, or a system-derived need. **`owner_id` MUST be assigned at creation** — creation with a null owner **fails** (M-35).
22. **Mutation rules.** Only via a transition in §12.1. State is never set directly. **Closure (`→ CLOSED`) and cancellation (`→ CANCELLED`) require a `decision_ref`**; without it the transition is illegal `[C-4]`.
23. **Correction rules.** Attributes other than `state` (e.g. `owner_id` via `OwnershipTransferred`, `exposure` via re-derivation) are corrected through explicit events, never in place.
24. **Supersession rules.** A Work Item is not superseded. A *reopened* obligation creates a **new phase** (same item, `phase_seq++`) or a **linked** new Work Item (`reopens`) — spec §12.14.
25. **Cancellation rules.** From any non-terminal state, `CancellationRequested` with a `decision_ref` ⇒ `CANCELLED`.
26. **Expiry rules.** ### **NEVER expires.** It ages (`AgeThresholdCrossed → ESCALATED`) and escalates. *Work does not disappear because it got old.*
27. **Reopening rules.** `CLOSED → IN_PROGRESS` (new phase) via `ReopenRequested{decision_ref}` (spec §12.14, M-34). ### **The closure event is immutable; reopening never rewrites it.** The *domain policy* of when reopening is permitted is `NEEDS VALIDATION` (§45).
28. **Deletion policy.** `[C-9]` — none.
29. **Retention policy.** Permanent.
30. **Audit requirements.** Every transition is an Audit Event with actor, from/to state, and (terminal) `decision_ref`. Sufficient to reconstruct ownership and closure history `[C-8]`.
31. **Events emitted.** `WorkItemCreated` · `WorkStarted` · `WorkBlocked` · `WorkUnblocked` · `HumanRequested` · `HumanDecided` · `WorkEscalated` · `OwnershipTransferred` · `WorkItemClosed{decision_ref}` · `WorkItemCancelled{decision_ref}` · `Reopened{prior_closure_ref}`.
32. **Events consumed.** `PipelineStarted` · `PipelineClosed` · `PipelineFailed{transient|permanent}` · `EvidenceMissing` · `ConflictRaised` · `HumanDecisionRequired` · `BlockerCleared` · `AgeThresholdCrossed` · `CorrectionInvalidatedAnEffect` (may raise a Compensation-bearing obligation).
33. **Idempotency.** `[C-3]`. Additionally: `PipelineClosed` for an already-closed obligation is a no-op.
34. **Replay behavior.** `[C-5]`. State reconstructs deterministically from its event stream; ownership and closure are replayable exactly.
35. **Security / authorization.** Creation and ownership transfer require an authenticated actor. Closure/cancellation require an actor with authority for the obligation. `[C-6]` — a model may propose that work is needed; it cannot own, close, or cancel.
36. **Fail-closed behavior.** A Work Item that loses its owner (e.g. offboarding) does not silently continue: an Exception is raised and no consequential Pipeline may be started for it until an owner is reassigned.
37. **Structurally impossible states.** An ownerless Work Item (point 16). A `CLOSED`/`CANCELLED` without a `decision_ref`. A closure by inactivity (I11).
38. **Interaction with the checkpoint.** Indirect: a Work Item spawns Pipeline Instances that pass the checkpoint. The Work Item itself performs no effect.
39. **Interaction with Effect Grants.** None directly. Grants belong to Pipeline Instances.
40. **Interaction with human approval.** `AWAITING_HUMAN` reflects an outstanding human decision; resolved by `HumanDecided{decision_ref}`.
41. **Interaction with policy & brake.** A brake does not close or cancel Work Items — it prevents their Pipelines from executing. Queued Work Items remain durable under a brake (spec §21.4).
42. **Observability.** Every open Work Item has a visible owner and age. `ESCALATED` items surface unprompted. Exposure (when present) is displayed.
43. **Acceptance criteria.** (a) creation assigns an owner or fails; (b) closure without `decision_ref` is rejected; (c) an aged item escalates via a durable timer, not a sweep; (d) reopening preserves the prior closure event and creates a new phase/linked item; (e) 1:N to Pipeline Instances holds.
44. **Adversarial tests.** `test_no_ownerless_work_item_can_exist` · `test_closure_without_decision_ref_is_illegal` · `test_inactivity_never_closes_a_work_item` · `test_reopening_never_mutates_closure` · `test_cross_tenant_work_item_rejected` `[C-1]` · `test_stale_version_transition_fails` `[C-10]` · `test_redelivered_pipeline_closed_is_noop` `[C-3]` · `test_replay_reconstructs_ownership_and_closure` `[C-5]`.
45. **Open validation questions.** **V1 (spec §32):** the *domain policy* for when a `CLOSED` obligation may be reopened (late POD, short-pay, post-close dispute). **Fail-closed default:** the generic machinery exists; a specific reopen requires a human `decision_ref`. **Not a block.**
