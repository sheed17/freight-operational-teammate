# Entity Specification — Rule

*Conventions & `[C-n]`: see `00-conventions.md`. Lifecycle: canonical spec §12.12; ADR-010 §6.*

1. **Canonical name.** Rule.
2. **Definition.** A registered, versioned, deterministic decision procedure **with an id** — identity matching, conflict resolution, or an owner-authored constraint (*"never bill without a POD"*), compiled from a human instruction and human-confirmed.
3. **Purpose.** To resolve **Stream B lesson L-C**: an owner sentence either **compiles into an enforceable rule** or is **honestly stored as memory and the owner is told it is not a rule.** There is no third outcome.
4. **What it is not.** ### **Not a prompt string. Not organizational knowledge.** Not authored or activated by a model. Not a Policy (a Rule is consulted *within* policy precedence, layer 6).
5. **Owning component.** Policy Engine (compilation) + the machine that evaluates it (Identity Service for binding rules, Reconciliation for conflict rules, the checkpoint for gate/constraint rules).
6. **Authority class.** **Neyma-native.**
7. **Tenant ownership.** `[C-1]`.
8. **Canonical identifier.** `rule_id` (uuid) + `rule_version` (monotonic).
9. **Natural / external identifiers.** `(tenant_id, scope, rule_version)`.
10. **Required attributes.** `rule_id` · `tenant_id` · **`rule_version`** · `scope` · `kind` (`IDENTITY`, `CONFLICT_RESOLUTION`, `GATE_PRECONDITION`, `CONSTRAINT`) · **`compiled_predicate`** (deterministic, typed) · `state` · `source_instruction` (the original human sentence) · `authored_by` · `activated_by` · `test_vectors[]` (generated — the loads it *would* have blocked).
11. **Optional attributes.** `expires_at` · `superseded_by` · `revoked_reason` · `conflict_id` (if it conflicts with another active rule).
12. **Enums.** `state ∈ {PROPOSED, COMPILED, CONFIRMED, ACTIVE, REJECTED, SUPERSEDED, REVOKED, EXPIRED}` (spec §12.12). Terminal: `REJECTED, SUPERSEDED, REVOKED, EXPIRED`.
13. **Provenance requirements.** ### **A referenced field must be MODELLED and NON-INFERRED. A rule referencing a `MODEL_INFERRED` field FAILS TO COMPILE** (M-49).
14. **Relationships & cardinalities.** Tenant 1 : N Rule. Rule 1 : 0..1 Conflict (rule-vs-rule). A Rule is referenced by resolutions (`ConflictResolved{rule_id}`) and by the checkpoint (gate/constraint rules).
15. **Aggregate / transaction boundary.** Own aggregate; activation `[C-2]`. Compilation is deterministic (no model in the loop after the initial text proposal).
16. **Database constraints.** `tenant_id, rule_version, scope, kind, compiled_predicate, state, source_instruction, authored_by NOT NULL`. ### **CHECK: `state = ACTIVE` requires a non-null `activated_by` (an authenticated human).** **CHECK: `compiled_predicate` references only modelled, non-inferred fields** (enforced at compile).
17. **Uniqueness constraints.** PK `(tenant_id, rule_id)`. `UNIQUE (tenant_id, rule_version)`. `UNIQUE (tenant_id, scope, kind) WHERE state = 'ACTIVE'` where a scope admits one rule; otherwise multiple active rules may coexist (and conflicts are detected).
18. **Referential integrity.** `authored_by`, `activated_by` FK. `conflict_id` FK.
19. **Versioning / OCC.** `[C-10]`. A new version supersedes; the old is retained (effects were judged under it).
20. **Lifecycle reference.** **Canonical spec §12.12** (complete). Not blocked.
21. **Creation rules.** ### **The compilation pipeline (spec §20.5):** parse *(a model MAY propose the structured candidate)* → **validate deterministically** (every field modelled and non-inferred; predicate decidable at checkpoint time; scope resolvable) → conflict-detect → **human confirmation (shown the compiled rule AND its test vectors)** → activate.
22. **Mutation rules.** Only via §12.12. ### **`CompilationFailed` (an unmodelled or inferred field) ⇒ `REJECTED` ⇒ the instruction becomes Organizational Knowledge and the owner is TOLD it is not a rule.**
23. **Correction rules.** A wrong rule is superseded (retained).
24. **Supersession rules.** New version supersedes; old retained.
25. **Cancellation rules.** Revocation: immediate if it narrows; the Policy Owner if it broadens.
26. **Expiry rules.** As Policy — a narrowing rule's expiry requires a human at expiry.
27. **Reopening rules.** N/A.
28. **Deletion policy.** None `[C-9]`.
29. **Retention policy.** Permanent.
30. **Audit requirements.** Propose/compile/reject/confirm/activate/supersede/revoke — with `source_instruction` and the compiled predicate.
31. **Events emitted.** `RuleProposed` · `RuleCompiled{rule_id}` · **`RuleNotEnforceable{missing, why}`** · `RuleConfirmed` · `RuleActivated{version}` · `RuleSuperseded` · `RuleRevoked` · `ConflictRaised` (rule-vs-rule).
32. **Events consumed.** `HumanConfirmed` · `HumanActivated` · `ConflictDetected` · `HumanRevoked` · `TimerFired`.
33. **Idempotency.** `[C-3]`. Re-activating an active rule version is a no-op.
34. **Replay behavior.** `[C-5]`. Rule versions replay deterministically; a decision is explained under the rule versions in force at its checkpoint.
35. **Security / authorization.** ### **A model proposes text; it never compiles, activates, evaluates, or resolves.** ### **The system MUST NOT reply "Noted the procedure" unless a rule actually compiled and activated** (M-52, M-64) — asserted on the literal reply text.
36. **Fail-closed behavior.** ### **A rule that cannot compile deterministically is NOT installed — the owner is told what is missing** (Outcome B). Two conflicting active rules ⇒ FAIL CLOSED ⇒ a `RULE_VS_RULE` Conflict ⇒ a human resolves it (never auto-merge). A repeatedly-overridden rule raises an Exception to the Policy Owner (the system asks; it does not auto-disable).
37. **Structurally impossible states.** An active rule with no `activated_by`. A rule branching on `MODEL_INFERRED`. A model-activated rule. A reply claiming enforcement with no active `rule_id`. Auto-merged conflicting rules.
38. **Interaction with the checkpoint.** ### **A `GATE_PRECONDITION`/`CONSTRAINT` rule is evaluated in checkpoint step 6** (e.g. *"never bill without a POD"* ⇒ `pod.evidence_condition == consistent` AND `pod.provenance_class ∈ {SYSTEM_IMPORTED, OWNER_ASSERTED, MODEL_EXTRACTED-with-artifact}`; a `MODEL_INFERRED` POD ⇒ DENY).
39. **Interaction with Effect Grants.** A denying rule ⇒ no witness ⇒ no grant.
40. **Interaction with human approval.** A `GATE_PRECONDITION` rule may set the gate to `HUMAN_APPROVAL_REQUIRED` under a condition (*manager approval under 12% margin — only if margin is deterministic*).
41. **Interaction with policy & brake.** Rules sit at precedence layer 6 (spec §20.7); the narrower scope wins; genuine conflicts fail closed.
42. **Observability.** ### **Override rate is the key rule-health metric** — a rule overridden constantly is a wrong rule and gets a human's attention (not a silent auto-disable). Test vectors show the owner what a rule *would* block before activation.
43. **Acceptance criteria.** (a) *"do not use Carrier X for produce"* cannot compile (commodity unmodelled) and the owner is told; (b) *"never bill without a POD"* compiles to a real precondition; (c) a reply never claims enforcement without an active rule id; (d) two conflicting rules fail closed; (e) a model cannot activate a rule.
44. **Adversarial tests.** `test_uncompilable_instruction_reply_does_not_claim_a_rule_was_installed` (M-52/M-64) · `test_never_bill_without_pod_compiles_to_a_precondition` · `test_do_not_use_carrier_x_for_produce_cannot_compile` · `test_margin_rule_refuses_to_compile_on_model_inferred_cost` · `test_two_conflicting_rules_fail_closed` · `test_model_cannot_activate_a_rule` · `test_repeatedly_overridden_rule_asks_does_not_auto_disable`.
45. **Open validation questions.** **V4/V5** (which identity and conflict rules to register). **Fail-closed default:** none registered ⇒ deterministic ID match only / every conflict to a human. **Q3 (deferred):** should a repeatedly-wrong rule auto-disable? **Recommendation:** never — auto-disabling is a machine decision about machine authority. **Not a block.**
