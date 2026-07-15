# Entity Specification — Audit Event

*Conventions & `[C-n]`: see `00-conventions.md`. Definition: canonical spec §11.2–§11.3, §25.*

1. **Canonical name.** Audit Event.
2. **Definition.** A fact about what **Neyma** did, and why — as distinct from a Business Event (a fact about the freight world). Both are facts; neither is a command.
3. **Purpose.** To make the system's authority auditable: to reconstruct, at any later date, ### **what the system knew AT THE TIME and why it acted** — sufficient to explain a decision to an angry person (I3).
4. **What it is not.** ### **Not a command** (an event says what happened; if you want something to happen, create a Work Item). Not a log line (it is structured, versioned, immutable, and part of the event backbone). Not mutable.
5. **Owning component.** Every machine emits Audit Events; the Event Backbone stores and delivers them.
6. **Authority class.** ### **Immutable record** (append-only).
7. **Tenant ownership.** `[C-1]` — `tenant_id` is the first field and the partition key.
8. **Canonical identifier.** `event_id` (uuid).
9. **Natural / external identifiers.** `(tenant_id, event_id)` — the dedup key.
10. **Required attributes** *(the canonical envelope, spec §11.2)*. `event_id` · **`tenant_id`** · `event_type` · **`event_version`** · `schema_version` · `producer` · `entity_type` · `entity_id` · `entity_version` · `pipeline_instance_id` (when applicable) · `work_item_id` (when applicable) · **`causation_id`** · **`correlation_id`** · `actor` (human id · detector id · `system`) · **`occurred_at`** (UTC) · **`recorded_at`** (UTC).
11. **Optional attributes.** `evidence_refs[]` (content-addressed) · `policy_version` · `decision_ref` · `payload` (type-specific, versioned).
12. **Enums.** `actor` kind ∈ `{human, detector, system}`. `event_type` is an open, versioned registry (each entity's emitted-events list). ### **No new event *semantics* may be invented** — an event records what happened; it never carries an instruction.
13. **Provenance requirements.** An Audit Event carries the `actor` and, where it records a decision, the `decision_ref` and the pinned input versions (via the referenced Checkpoint Witness).
14. **Relationships & cardinalities.** Every machine 1 : N Audit Event. Audit Event N : 1 `correlation_id` (a business transaction) and N : 1 `causation_id` (its direct cause). Audit Events form the append-only stream every entity replays from.
15. **Aggregate / transaction boundary.** ### **Written into the transactional OUTBOX in the SAME transaction as the state change that emitted it** (M-23) — an event cannot exist without its transition, nor a transition without its event (I10).
16. **Database constraints.** All point-10 attributes `NOT NULL` (except the situational ids). ### **Append-only: no `UPDATE`, no `DELETE`, enforced by grant** `[C-8]`. `occurred_at`, `recorded_at` in UTC.
17. **Uniqueness constraints.** PK `(tenant_id, event_id)`. ### **The consumer inbox enforces `UNIQUE (consumer_id, tenant_id, event_id)`** for at-least-once delivery de-duplication (M-24).
18. **Referential integrity.** `causation_id`/`correlation_id` reference prior events; ### **an event referencing a not-yet-existing machine is PARKED (`pending_references`), not dropped, not failed** (M-26).
19. **Versioning / OCC.** ### **`event_version` from the FIRST event ever written; within a version, additive-only; a breaking change is a new version + a registered upcaster applied ON READ. Historical events are NEVER rewritten** (M-25).
20. **Lifecycle reference.** ### **None — an Audit Event is immutable; it has no state machine.** Not blocked.
21. **Creation rules.** Emitted by a machine transition, atomically via the outbox. ### **Replay does NOT create Audit Events** (it consumes them to rebuild state).
22. **Mutation rules.** ### **NONE. Append-only.**
23. **Correction rules.** ### **A mistake is corrected by a NEW compensating event, never by editing history** (S8) — *history is not mutated to make the present tidy.*
24. **Supersession rules.** N/A (a later event may describe a supersession; the earlier event stands).
25. **Cancellation rules.** N/A.
26. **Expiry rules.** None (tiered retention only).
27. **Reopening rules.** N/A.
28. **Deletion policy.** ### **None. Append-only, retained per the tiering schedule (hot 90d → warm 2y → cold 7y, immutable).**
29. **Retention policy.** Permanent (tiered).
30. **Audit requirements.** (self) — the Audit Event *is* the audit. It must be sufficient, with the referenced Witness and evidence, to reconstruct the decision.
31. **Events emitted.** N/A (it is the event).
32. **Events consumed.** N/A directly; every entity **consumes** Audit/Business events via its durable inbox.
33. **Idempotency.** ### **The inbox dedup key makes redelivery a no-op** (M-24); ingestion of the same `event_id` twice changes nothing.
34. **Replay behavior.** ### **Replay applies Audit/Business events through transition tables to rebuild state and produces ZERO grants and ZERO effects** (M-27) — the full-corpus rebuild is compared to the live projection nightly; **divergence is a Sev-0 that auto-engages a brake** (spec §25).
35. **Security / authorization.** ### **Append-only and tamper-evident.** Every mint/claim/refusal and every `IllegalTransitionAttempted` is a security-relevant Audit Event. Cross-tenant delivery is impossible (tenant-first inbox key). Inbound content becomes an Observation, never an Audit Event that could assert authority.
36. **Fail-closed behavior.** ### **A missing or unpersisted event is impossible** (the outbox guarantee, I10). A dangling reference is parked and, on TTL, raises an Exception (never a silent drop).
37. **Structurally impossible states.** A mutated Audit Event. A transition without its event, or an event without its transition. A duplicate-delivered event processed twice. An event carrying an instruction (a command).
38. **Interaction with the checkpoint.** The Checkpoint Witness pins the versions of the observations/claims used; Audit Events (`CheckpointPassed`/`CheckpointFailed{step}`) record the decision and its basis.
39. **Interaction with Effect Grants.** `EffectGranted`/`GrantClaimed`/`ClaimRefused`/`EffectAttempted` are the Audit Events that make orphan detection possible (an `EffectAttempted` with no matching claimed grant ⇒ Sev-0).
40. **Interaction with human approval.** `ApprovalRequested`/`Granted`/`Voided{drift_diff}`/`Consumed` capture exactly what the human saw and decided — the evidentiary heart of an approval.
41. **Interaction with policy & brake.** `PolicyActivated`, `PolicyOverridden` (audit + security), `BrakeEngaged`/`Released` are Audit Events; the brake report is assembled from them.
42. **Observability.** ### **The explainability query walks `correlation_id` → `causation_id` → work item → pipeline → checkpoint → grant → effect back to the retained artifact, in < 2s p95**, using the beliefs of that day (upcasters on read).
43. **Acceptance criteria.** (a) an event and its transition are one commit (kill between them ⇒ the outbox still delivers the event); (b) duplicate delivery is a no-op; (c) a full-corpus rebuild across a schema-version change succeeds via upcasters; (d) history is never rewritten; (e) a 90-day-old decision explains using that day's beliefs.
44. **Adversarial tests.** `test_dual_write_kill_between_effect_and_event` (I10) · `test_duplicate_delivery_is_noop` (M-24) · `test_upcaster_rebuild_across_schema_version` (M-25) · `test_full_corpus_rebuild_reproduces_projection` (M-27) · `test_history_is_never_rewritten` (S8) · `test_explanation_of_a_90_day_old_decision_uses_the_beliefs_of_that_day` (M-68) · `test_rebuild_divergence_is_sev0_and_brakes` · `test_dangling_reference_parked_then_drained` (M-26) · `test_cross_tenant_event_delivery_impossible` `[C-1]`.
45. **Open validation questions.** ### **Audit-query latency target** (< 2s p95 stated; validate under the full-corpus warm tier). ### **Retention-tiering thresholds** (hot/warm/cold) — operational. **Neither is a block.**
