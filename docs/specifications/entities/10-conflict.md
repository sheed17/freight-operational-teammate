# Entity Specification — Conflict

*Conventions & `[C-n]`: see `00-conventions.md`. Lifecycle: canonical spec §12.7; ADR-007 §5.*

1. **Canonical name.** Conflict.
2. **Definition.** Two or more mutually exclusive claims or observations on the same field.
3. **Purpose.** To make disagreement **visible and blocking**, instead of silently resolved — and to be the mechanism by which Neyma *never silently chooses*.
4. **What it is not.** ### **Not `unknown`** (we do not lack information — we have too much, and it disagrees — I8). Not an error. Not resolvable by recency, confidence, or a model.
5. **Owning component.** Reconciliation Service.
6. **Authority class.** **Neyma-native.**
7. **Tenant ownership.** `[C-1]`.
8. **Canonical identifier.** `conflict_id` (uuid).
9. **Natural / external identifiers.** `(tenant_id, entity_ref, field)` — the disputed field.
10. **Required attributes.** `conflict_id` · `tenant_id` · `entity_ref` · `field` · `kind` · `state` · `version` · `owner_id` (a human, from `RAISED`) · `created_at` · `parties[]` (the conflicting claims/observations).
11. **Optional attributes.** `rule_id` (on `RESOLVED_BY_RULE`) · `decision_ref` (on `RESOLVED_BY_HUMAN`) · `escalation_at` · `exposure`.
12. **Enums.** `state ∈ {RAISED, OPEN, ESCALATED, RESOLVED_BY_RULE, RESOLVED_BY_HUMAN}` (spec §12.7). Terminal: the two `RESOLVED_*`. `kind ∈ {SYSTEM_VS_SYSTEM, CLAIM_VS_CLAIM, CLAIM_VS_OBSERVATION, INFERRER_VS_OWNER, READBACK_VS_APPROVED, RULE_VS_RULE}`.
13. **Provenance requirements.** Each `parties[]` entry carries its own `provenance_class`; ### **an `INFERRER_VS_OWNER` conflict specifically records that one party is `OWNER_ASSERTED`** (which is why the inferrer may not overwrite it — it raised a Conflict instead).
14. **Relationships & cardinalities.** Conflict N : 1 entity. Conflict 1 : N parties (claims/observations). Conflict 1 : 0..1 resolving rule/decision.
15. **Aggregate / transaction boundary.** Own aggregate; transitions `[C-2]`. Raising a Conflict and setting the field's evidence condition to `conflicting` occur in one transaction.
16. **Database constraints.** `tenant_id, entity_ref, field, kind, state, version, owner_id NOT NULL`. **CHECK: `state = RESOLVED_BY_RULE` requires a non-null `rule_id`.** **CHECK: `state = RESOLVED_BY_HUMAN` requires a non-null `decision_ref`.** **CHECK: `owner_id NOT NULL` from creation.**
17. **Uniqueness constraints.** PK `(tenant_id, conflict_id)`. ### **`UNIQUE (tenant_id, entity_ref, field) WHERE state IN ('RAISED','OPEN','ESCALATED')`** — one open conflict per field (new disagreeing parties attach to it).
18. **Referential integrity.** `entity_ref`, `parties[]`, `rule_id`, `decision_ref`, `owner_id` FK.
19. **Versioning / OCC.** `[C-10]`.
20. **Lifecycle reference.** **Canonical spec §12.7** (complete). Not blocked.
21. **Creation rules.** Raised on detection of any `kind` above — including a readback that contradicts the approved facts (`OBSERVATION_CONFLICTING`) and two conflicting standing rules (`RULE_VS_RULE`, spec §20.7).
22. **Mutation rules.** Only via §12.7. ### **`AutoResolve` and any `TimerFired` transition to a resolved state are ILLEGAL** (spec §12.7).
23. **Correction rules.** N/A — a Conflict is resolved, not corrected. Resolution may *cause* a claim correction downstream.
24. **Supersession rules.** N/A.
25. **Cancellation rules.** Only if the **underlying disagreement disappears** (a party retracts) — still an event, never silence.
26. **Expiry rules.** ### **NEVER. It ages (`AgeThresholdCrossed → ESCALATED`) and escalates.** *A conflict that times out is a conflict resolved by a clock, and the clock knows nothing about freight.*
27. **Reopening rules.** N/A.
28. **Deletion policy.** None `[C-9]`.
29. **Retention policy.** Permanent.
30. **Audit requirements.** Raise/open/escalate/resolve events with parties and resolution basis (`rule_id` or `decision_ref`).
31. **Events emitted.** `ConflictRaised` · `ConflictOpened` · `ConflictEscalated` · `ConflictResolved{rule_id|decision_ref}`.
32. **Events consumed.** `ConflictDetected` · `Acknowledged` · `DeterministicRuleApplies` · `HumanResolved{decision_ref}` · `AgeThresholdCrossed`.
33. **Idempotency.** `[C-3]`. A second detection of the same `(entity, field)` disagreement attaches a party to the existing open Conflict, not a new one (the partial unique index).
34. **Replay behavior.** `[C-5]`.
35. **Security / authorization.** ### **A Conflict is a SECURITY control as much as a data-quality one: an attacker who injects a competing claim gains a FROZEN entity and a human's attention, not control** (spec §24). Resolution requires a registered `rule_id` or an authenticated human `decision_ref`; `[C-6]` — a model never resolves a Conflict.
36. **Fail-closed behavior.** ### **THE INVARIANT: while a Conflict is OPEN, the field is `conflicting` and BLOCKS every consequential action on that entity** (spec §12.7, ADR-002 C6).
37. **Structurally impossible states.** A Conflict auto-resolved by a timer or a model. A resolution with neither a `rule_id` nor a `decision_ref`. A consequential action proceeding on a field with an open Conflict. An ownerless Conflict.
38. **Interaction with the checkpoint.** ### **Checkpoint step 4 (native-state validity) FAILS if any material field has an open Conflict** — the action is blocked and fails closed.
39. **Interaction with Effect Grants.** No grant can be minted for an entity with an open Conflict on a material field. A `READBACK_VS_APPROVED` conflict is *how* an `UNKNOWN_OUTCOME` records that something else may have acted (the R-02 signature detected).
40. **Interaction with human approval.** An open Conflict on a material field voids/blocks the approval (`consistent` fails).
41. **Interaction with policy & brake.** ### **Two conflicting standing rules ⇒ FAIL CLOSED ⇒ a `RULE_VS_RULE` Conflict ⇒ a human resolves it. Neyma never picks a winner** (spec §20.7). A persistent conflict is an operational signal, not a bug.
42. **Observability.** ### **Conflict count should be near zero.** A persistent conflict means two systems genuinely disagree — an operational problem in the business; **surfacing it is the product.**
43. **Acceptance criteria.** (a) an open Conflict blocks all consequential actions on the entity; (b) no timer/model resolves it; (c) resolution requires a rule id or a decision ref; (d) inferrer-vs-owner disagreement raises a Conflict rather than overwriting; (e) two conflicting rules block, not auto-merge.
44. **Adversarial tests.** `test_open_conflict_blocks_all_consequential_actions` · `test_no_timer_or_model_resolves_a_conflict` · `test_resolution_requires_rule_id_or_decision_ref` · `test_inferrer_vs_owner_raises_conflict` · `test_two_conflicting_rules_fail_closed` (spec §20.7) · `test_readback_vs_approved_raises_conflict` · `test_injected_competing_claim_freezes_entity_not_control` (spec §24) · `test_ownerless_conflict_impossible`.
45. **Open validation questions.** **V5:** registered conflict-resolution rules (does the TMS always beat the portal on delivery status?). **Fail-closed default:** no rule ⇒ EVERY conflict goes to a human. **Not a block** — it just means more human work until rules are registered.
