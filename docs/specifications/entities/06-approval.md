# Entity Specification — Approval

*Conventions & `[C-n]`: see `00-conventions.md`. Lifecycle: canonical spec §12.4; binding: ADR-005.*

1. **Canonical name.** Approval.
2. **Definition.** An authenticated, authorized human agreeing to an action **together with the exact material facts that made it correct**.
3. **Purpose.** To make a human decision **bound to reality**: if any material fact drifts after the human taps, there is no approval — there is a new question.
4. **What it is not.** ### **Not an instruction. Not a mandate. Not reusable. Not extendable. Not refreshable.** Not creatable by a model, a counterparty, a document, a confidence score, a policy default, a retry handler, an agent, or an admin tool.
5. **Owning component.** Approval Service (renders the card, receives the tap, holds the fingerprint).
6. **Authority class.** **Neyma-native.**
7. **Tenant ownership.** `[C-1]`.
8. **Canonical identifier.** `approval_id` (uuid).
9. **Natural / external identifiers.** Bound to exactly one `commit_key` (the effect it authorizes).
10. **Required attributes.** `approval_id` · `tenant_id` · `commit_key` · `action_class` · `state` · `version` · **`material_facts_fingerprint`** · **`canonical_payload`** (the full `fp_v1` bytes — retained, so drift can be *explained*, not merely detected) · `fingerprint_version` · `policy_version` · `gate_decision` · `requested_at` · `expires_at` · `rendered_facts` (what was shown to the human).
11. **Optional attributes.** `granted_by` (authenticated actor) · `granted_at` · `consumed_at` · `void_reason` · `drift_diff` (on `VOID_ON_DRIFT`) · `required_authority` (e.g. MANAGER) · `signatures[]` (dual control).
12. **Enums.** `state ∈ {REQUESTED, GRANTED, CONSUMED, DENIED, EXPIRED, REVOKED, VOID_ON_DRIFT, VOID_ON_BRAKE}` (spec §12.4). Terminal: all but `REQUESTED`/`GRANTED`. `gate_decision ∈ {HUMAN_APPROVAL_REQUIRED, PERMANENT_HUMAN_ASSERTION_REQUIRED}` (an Approval only exists for these two).
13. **Provenance requirements.** ### **`provenance_class` of every material field is INSIDE the fingerprint** (M-56) — the same number believed for a different reason is a different fact, and re-approval is required. `granted_by` is always `OWNER_ASSERTED`-grade (an authenticated human inside the trust boundary).
14. **Relationships & cardinalities.** Pipeline Instance 1 : 0..1 Approval. Approval 1 : N ApprovalSignature (dual control). Approval 1 : 1 `commit_key`. Approval consumed by 1 Effect Grant claim.
15. **Aggregate / transaction boundary.** ### **`GRANTED → CONSUMED` is an atomic CAS in the SAME transaction as the Effect Grant claim** (spec §21.3). Request/grant/void are ordinary `[C-2]`.
16. **Database constraints.** `tenant_id, commit_key, action_class, state, version, material_facts_fingerprint, canonical_payload, fingerprint_version, policy_version, gate_decision, expires_at NOT NULL`. **CHECK: `state = GRANTED` requires a non-null `granted_by`.** **CHECK: a money-affecting `action_class` cannot have `gate_decision = AUTONOMOUS_WITHIN_CAPS`** (an Approval would not exist).
17. **Uniqueness constraints.** PK `(tenant_id, approval_id)`. ### **`UNIQUE (tenant_id, commit_key) WHERE state IN ('REQUESTED','GRANTED')`** — at most one live approval per effect (a re-approval supersedes only after the prior is terminal via drift/expiry).
18. **Referential integrity.** `commit_key` consistent with the Pipeline Instance. `granted_by` FK → an authenticated tenant user with authority for `action_class`.
19. **Versioning / OCC.** `[C-10]`.
20. **Lifecycle reference.** **Canonical spec §12.4** (complete). Not blocked.
21. **Creation rules.** Created by the Pipeline Instance at `VALIDATED` when the gate requires a human. ### **The `material_facts_fingerprint` and `canonical_payload` are computed from RUNTIME reads — never model output** (M-13, M-55: exactly what was rendered to the approver).
22. **Mutation rules.** Only via §12.4. ### **A re-approval is always a NEW Approval with a NEW fingerprint** — an approval is never "refreshed", "extended", or "re-validated in place".
23. **Correction rules.** N/A in place. A changed decision is a new proposal + new approval.
24. **Supersession rules.** ### **No `SUPERSEDED` state.** Supersession = drift-void ∪ duplicate-refusal (spec §12.4 / ADR-005 §3.10). *There is no third case, so there is no third state.*
25. **Cancellation rules.** `REQUESTED → DENIED` (human denies) or `→ EXPIRED`. `GRANTED → REVOKED` (human revokes) before consumption.
26. **Expiry rules.** ### **Absolute TTL per action class** (money-out 1h · money-in 8h · docs/status 24h — all `NEEDS VALIDATION`), fired by a durable timer. ### **An expired approval is not a weaker approval. It is not an approval.**
27. **Reopening rules.** N/A.
28. **Deletion policy.** None `[C-9]` — retained with the full canonical payload.
29. **Retention policy.** Permanent. ### **You must be able to reconstruct, years later, exactly what the human saw when they said yes.**
30. **Audit requirements.** Every request/grant/void/expiry/consume is an Audit Event with actor, and (voids) the `drift_diff` and reason.
31. **Events emitted.** `ApprovalRequested{fingerprint}` · `ApprovalGranted` · `ApprovalDenied` · `ApprovalExpired` · `ApprovalRevoked` · `ApprovalVoided{drift_diff|policy|brake}` · `ApprovalConsumed`.
32. **Events consumed.** `HumanApproved` · `HumanDenied` · `MaterialFactsChanged` · `PolicyVersionChanged` · `BrakeEngaged` · `HumanRevoked` · `EffectCommitted` (⇒ `CONSUMED`) · `AttemptFailedProvably` (survives) · `AttemptOutcomeUnknown` (frozen, not reusable) · `TimerFired`.
33. **Idempotency.** `[C-3]`. ### **A double-tap of the Slack button is idempotent** — the second finds `CONSUMED` and replies "already done — invoice 560010, sent at 09:52", raising nothing and acting nothing. **Two-layer replay protection: a single-use HMAC transport token AND the `GRANTED → CONSUMED` CAS** (spec §21.3).
34. **Replay behavior.** `[C-5]`. Replay reconstructs approval history; it never re-grants and never consumes into an effect.
35. **Security / authorization.** ### **Created ONLY by an authenticated, authorized human.** A counterparty's "you approved this" is `MODEL_EXTRACTED` at best, ### **a fraud signal, never an Approval** (ADR-003, M-9). The transport token is single-use and actor-bound.
36. **Fail-closed behavior.** Any material fact drift, provenance drift, evidence-condition degradation (`consistent → stale/unknown/conflicting`), policy-version change, or open Conflict on a material field ⇒ ### **`VOID_ON_DRIFT`** with a human-readable diff. An unreadable source at re-check ⇒ fail closed (not "no drift").
37. **Structurally impossible states.** A `GRANTED` approval with no `granted_by`. A partial approval (does not exist — "approve but for £2,700" is a new proposal). An approval consumed twice. An approval reused after a provably-**unknown** attempt.
38. **Interaction with the checkpoint.** ### **Checkpoint steps 1 (validity) and 2 (fingerprint equality) evaluate THIS approval, LIVE, inside the atomic checkpoint** (spec §19.2).
39. **Interaction with Effect Grants.** Bound as `approval_id` on the grant (DB CHECK); consumed in the claim CAS transaction.
40. **Interaction with human approval.** (self.)
41. **Interaction with policy & brake.** `policy_version` is a material fact ⇒ a policy change voids it. `BrakeEngaged` ⇒ `VOID_ON_BRAKE`. Dual control: **all** signatures bind the **same** fingerprint; drift between signatures voids all of them (spec §12.4).
42. **Observability.** ### **Drift-void rate and time-to-approve are first-class metrics** (a rising drift-void rate means the world is moving faster than the owner taps, or a source is flapping). Every drift-void must be explainable in one message.
43. **Acceptance criteria.** (a) approve £2,850 → TMS moves to £3,100 → `VOID_ON_DRIFT` with an amount diff, no effect; (b) double-tap idempotent; (c) same amount + changed provenance ⇒ void; (d) policy tightened while awaiting ⇒ void; (e) dual-control drift voids all signatures.
44. **Adversarial tests.** `test_F01_approve_2850_then_tms_moves_to_3100_no_effect_occurs` · `test_same_amount_changed_provenance_voids` (M-56) · `test_double_tap_is_idempotent_not_an_error` · `test_counterparty_cannot_self_authorize` (ADR-003) · `test_partial_approval_is_a_new_proposal` · `test_approval_after_unknown_attempt_is_not_reusable` · `test_dual_control_drift_voids_all_signatures` · `test_expired_approval_cannot_execute` · `test_policy_change_voids_inflight_approval`.
45. **Open validation questions.** **V2** (approval TTLs) and **V3** (which classes need dual control, at what threshold). **Fail-closed defaults:** conservative TTLs; single approval unless configured. **Neither is a block** — the mechanism is complete.
