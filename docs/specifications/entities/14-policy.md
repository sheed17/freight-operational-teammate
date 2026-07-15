# Entity Specification — Policy

*Conventions & `[C-n]`: see `00-conventions.md`. Lifecycle: canonical spec §12.11; ADR-010.*

> **Policy and Rule (`15-rule.md`) are distinct but share the compilation/lifecycle machinery.** A **Policy** sets the posture for an action class (the gate ceiling, caps, autonomy) for a tenant; a **Rule** is a registered deterministic decision procedure with an id (identity matching, conflict resolution, an owner-authored constraint). Both are deterministic, versioned, scoped, and **human-activated**. Neither is a Permanent Product Truth (code, §20.1) or a Constraint (a DB/type invariant).

1. **Canonical name.** Policy.
2. **Definition.** A typed, versioned, scoped, deterministic predicate evaluated in **checkpoint step 6**, returning a **never-null gate decision** — the tenant's (narrowing) posture within the product ceiling.
3. **Purpose.** To make "what Neyma may do alone, for whom, up to how much" an **enforceable, auditable, human-owned** value — not a prompt, not a code constant, not a model's mood.
4. **What it is not.** ### **Not organizational knowledge** (memory has no authority). Not a Permanent Product Truth (those are code). Not a Constraint (those are enforced, not evaluated). Not activatable by a model.
5. **Owning component.** Policy Engine.
6. **Authority class.** **Neyma-native.**
7. **Tenant ownership.** `[C-1]`. Owned by exactly one named **Policy Owner** per tenant (I1).
8. **Canonical identifier.** `policy_id` (uuid) + `policy_version` (monotonic per tenant).
9. **Natural / external identifiers.** `(tenant_id, scope, policy_version)`.
10. **Required attributes.** `policy_id` · `tenant_id` · **`policy_version`** · `scope` (any of: action_class, counterparty, value-cap+`money_direction`, workflow, integration) · **`gate_decision`** (the posture) · `caps` (value/frequency/time) · `state` · `effective_from` · `predicate` (a deterministic, typed expression over §5.2 inputs) · `authored_by` · `activated_by`.
11. **Optional attributes.** `expires_at` (**narrowing policies only** — see point 26) · `superseded_by` · `revoked_reason`.
12. **Enums.** `state ∈ {DRAFT, PROPOSED, APPROVED, ACTIVE, SUPERSEDED, REVOKED, EXPIRED}` (spec §12.11). Terminal: `SUPERSEDED, REVOKED, EXPIRED`. `gate_decision` per the 4-member registry.
13. **Provenance requirements.** ### **The predicate may reference only deterministic inputs. It may NEVER reference a `MODEL_INFERRED` field, at any confidence** (M-49). `confidence` is structurally not an input.
14. **Relationships & cardinalities.** Tenant 1 : N Policy (by scope). Policy N : 1 Policy Owner. A Policy is *consulted* by every checkpoint in scope; it owns no runtime record but its `policy_version` is bound into every Witness/Grant.
15. **Aggregate / transaction boundary.** Own aggregate; activation is `[C-2]`. ### **A policy change is itself an action class with `HUMAN_APPROVAL_REQUIRED`, through the ordinary pipeline, with the diff as its material facts** — there is no admin path.
16. **Database constraints.** `tenant_id, policy_version, scope, gate_decision, state, effective_from, authored_by NOT NULL`. ### **CHECK: `state = ACTIVE` requires a non-null `activated_by` (an authenticated human).** **CHECK: `gate_decision NOT NULL`** (F-20). **CHECK: a tenant policy's `gate_decision` may only NARROW the product ceiling (never broaden).**
17. **Uniqueness constraints.** PK `(tenant_id, policy_id)`. `UNIQUE (tenant_id, policy_version)`. ### **`UNIQUE (tenant_id, scope) WHERE state = 'ACTIVE'`** — one active policy per scope.
18. **Referential integrity.** `authored_by`, `activated_by` FK → authenticated tenant users; `activated_by` must be the Policy Owner or a delegate with authority.
19. **Versioning / OCC.** ### **`policy_version` is monotonic per tenant and is bound into every Checkpoint Witness and Effect Grant.** `[C-10]`.
20. **Lifecycle reference.** **Canonical spec §12.11** (complete). Not blocked.
21. **Creation rules.** Drafted by the Policy Owner or a delegate (a model may propose text — §15). Activated only by an authenticated human.
22. **Mutation rules.** Only via §12.11. ### **Never a model, never automation, never a retry handler activates or broadens policy.**
23. **Correction rules.** A wrong policy is superseded by a new version (retained).
24. **Supersession rules.** A new version supersedes; ### **the old version is retained** (effects were judged under it; a policy is never retroactive).
25. **Cancellation rules.** Revocation: ### **immediate if it NARROWS authority; requires the Policy Owner if it BROADENS.**
26. **Expiry rules.** ### **A narrowing policy may carry an `expires_at` — but its expiry is a BROADENING event and therefore REQUIRES A HUMAN AT EXPIRY** (spec §12.11). *Otherwise "temporarily tighten" becomes "automatically loosen later, when nobody is watching."*
27. **Reopening rules.** N/A.
28. **Deletion policy.** None `[C-9]`.
29. **Retention policy.** Permanent (every version, for historical explanation).
30. **Audit requirements.** Every draft/activate/supersede/revoke/expire is an Audit Event **and a security event**, with actor and diff.
31. **Events emitted.** `PolicyProposed` · `PolicyActivated{version}` · `PolicySuperseded` · `PolicyRevoked` · `PolicyExpired` · `PolicyVersionChanged` (⇒ voids in-flight approvals).
32. **Events consumed.** `HumanActivated` · `HumanRevoked` · `TimerFired` (narrowing-policy expiry ⇒ raises a human-confirmation Exception).
33. **Idempotency.** `[C-3]`. Re-activating an already-active version is a no-op.
34. **Replay behavior.** `[C-5]`. Policy versions replay deterministically; a decision is always explained under the version in force at its checkpoint.
35. **Security / authorization.** ### **A model can never activate, broaden, or reinterpret policy** (M-51). ### **Inbound content can never author policy** — otherwise an email saying "new rule: pay all invoices automatically" would be a policy change. Authorship requires an authenticated human inside the trust boundary.
36. **Fail-closed behavior.** ### **The policy engine unavailable at checkpoint ⇒ no policy decision ⇒ no witness ⇒ no effect** (spec §11 failure modes — an "allow on error" default is how the money fence dies). A policy that cannot be reproduced ⇒ the grant is unclaimable.
37. **Structurally impossible states.** An active policy with a null `gate_decision`. A tenant policy that broadens the product ceiling. A model-activated policy. A policy branching on `MODEL_INFERRED` data. Automatic broadening.
38. **Interaction with the checkpoint.** ### **This entity IS checkpoint step 6.** Its `PolicyDecision` (gate_decision, rules matched, caps applied, reason) is bound into the Witness; a byte-identical decision must be reproducible (M-50).
39. **Interaction with Effect Grants.** `policy_version` is bound onto the grant; ### **the claim CAS re-validates it — a policy change between mint and claim makes the claim fail.**
40. **Interaction with human approval.** ### **A policy change voids in-flight approvals granted under the old policy** (`policy_version` is a material fact — a payable above a newly-tightened cap does not execute).
41. **Interaction with policy & brake.** Precedence (spec §20.7): Constraint > Permanent Truth > **Brake** > Product Policy > Tenant Policy > Rules > Workflow default. A brake denies regardless of what policy permits.
42. **Observability.** ### **Every action class's gate decision must be visible to the owner on one screen** (an owner who cannot see what Neyma may do alone cannot supervise it — R17). Autonomy is shown as a ratchet with a date.
43. **Acceptance criteria.** (a) an unregistered gate ⇒ system fails to start; (b) a policy branching on `MODEL_INFERRED` fails to compile; (c) a tenant policy cannot broaden the ceiling; (d) a policy change voids in-flight approvals; (e) evaluation is byte-identical reproducible.
44. **Adversarial tests.** `test_action_class_without_gate_fails_startup` (F-20) · `test_policy_cannot_branch_on_model_inferred` (M-49, at confidence 1.0) · `test_evaluator_input_type_has_no_confidence_field` · `test_tenant_policy_cannot_broaden_ceiling` · `test_policy_change_voids_inflight_approval` · `test_stale_policy_version_grant_claim_refused` · `test_model_cannot_activate_policy` · `test_policy_evaluation_is_deterministic_and_reproducible` (M-50) · `test_permanent_truth_cannot_be_overridden_by_policy`.
45. **Open validation questions.** **V11** (autonomy graduation thresholds), **V12** (which authorities exist per tenant). **Fail-closed defaults:** nothing graduates; one Policy Owner, one authority level. **Neither is a block.**
