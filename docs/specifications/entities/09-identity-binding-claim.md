# Entity Specification — Identity Binding Claim

*Conventions & `[C-n]`: see `00-conventions.md`. Lifecycle: canonical spec §12.6; ADR-007.*

1. **Canonical name.** Identity Binding Claim.
2. **Definition.** A Neyma-native **claim** of the form *"artifact X belongs to entity Y"* — the most common and most dangerous claim in freight.
3. **Purpose.** To make identity a **first-class, evidenced, correctable, escalatable decision** — never a silent guess baked into a projection.
4. **What it is not.** ### **Not a fact. Not an observation.** Not authority. Not something a model may confirm. Not a freight `Claim` (cargo damage — a different, domain entity; always qualify).
5. **Owning component.** Identity Service.
6. **Authority class.** ### **Neyma-native** (an inference is native state — ADR-002 §1.3).
7. **Tenant ownership.** `[C-1]`.
8. **Canonical identifier.** `binding_claim_id` (uuid).
9. **Natural / external identifiers.** `(observation_id | evidence_id) → entity_ref`. A claim ties a source artifact to a business entity.
10. **Required attributes.** `binding_claim_id` · `tenant_id` · `subject_ref` (the artifact/observation) · `entity_ref` (the claimed entity) · **`provenance_class`** · `state` · `version` · `match_method` · `created_at`.
11. **Optional attributes.** `evidence_id` + `span` (**required when `provenance_class = MODEL_EXTRACTED`**) · `rule_id` (when `LINKER_INFERRED`/`RECONCILED`) · `confidence` (**for queue-ordering ONLY**) · `decision_ref` (human) · `corrected_from` · `superseded_by` · `conflict_id`.
12. **Enums.** `state ∈ {PROPOSED, CONFIRMED, AMBIGUOUS, REJECTED, SUPERSEDED, CORRECTED, CONFLICTING}` (spec §12.6). Terminal: `REJECTED, SUPERSEDED`. `provenance_class` per the 6-member registry. `match_method ∈ {EXACT_ID, RULE, RECONCILIATION, MODEL_EXTRACT, MODEL_INFER, HUMAN}`.
13. **Provenance requirements.** ### **Central to this entity.** `EXACT_ID`/`RULE` ⇒ `LINKER_INFERRED`; `RECONCILIATION` ⇒ `RECONCILED`; `MODEL_EXTRACT` ⇒ `MODEL_EXTRACTED` (**requires an Evidence span**); `MODEL_INFER` ⇒ `MODEL_INFERRED`; `HUMAN` ⇒ `OWNER_ASSERTED`. ### **SD-6 — `provenance_class` is a DETERMINISTIC, IMMUTABLE FUNCTION of `match_method` (the mapping above), computed ONCE at creation and never independently edited.** The two fields cannot drift: `provenance_class` is stored (for indexing/queries) but is **derived**, and any write MUST satisfy the mapping (a CHECK: `provenance_class = f(match_method)`). *(Runtime-assignment per R-P1; no laundering per R-P2 — a change of belief is a NEW claim with a new `match_method`, never an edit of `provenance_class`. **No new concept:** the mapping is exactly ADR-002 §2.3's provenance semantics; this states it is a function, not two free fields.)*
14. **Relationships & cardinalities.** Observation N : 0..1 confirmed binding. Claim 1 : 0..1 Conflict. Claim 1 : 0..1 `corrected_from` (self). A subject may have many `PROPOSED`/`AMBIGUOUS` claims but ### **at most one `CONFIRMED`** (the canonical binding).
15. **Aggregate / transaction boundary.** The claim is its own aggregate; transitions are `[C-2]`. A **correction** transaction emits `ClaimCorrected` and triggers propagation (a separate, event-driven fan-out — spec §10.2), not a single mega-transaction.
16. **Database constraints.** `tenant_id, subject_ref, entity_ref, provenance_class, state, version, match_method NOT NULL`. **CHECK: `provenance_class = MODEL_EXTRACTED` requires a non-null `evidence_id` + `span`.** **CHECK: `provenance_class ∈ {LINKER_INFERRED, RECONCILED}` requires a non-null `rule_id`.** **CHECK: a transition to `CONFIRMED` via `HumanAsserted` requires `provenance_class = OWNER_ASSERTED`.**
17. **Uniqueness constraints.** PK `(tenant_id, binding_claim_id)`. ### **`UNIQUE (tenant_id, subject_ref) WHERE state = 'CONFIRMED'`** — one canonical binding per subject.
18. **Referential integrity.** `subject_ref`, `entity_ref`, `evidence_id`, `rule_id`, `conflict_id`, `corrected_from` FK.
19. **Versioning / OCC.** `[C-10]`.
20. **Lifecycle reference.** **Canonical spec §12.6** (complete). Not blocked.
21. **Creation rules.** Proposed by the linker (deterministic-first, spec §10.1) or a human. ### **A `MODEL_INFERRED` proposal routes straight to `AMBIGUOUS`** — a guess never auto-confirms, at any confidence.
22. **Mutation rules.** Only via §12.6. ### **A `MODEL_EXTRACTED` claim is EVIDENCE — it re-enters deterministic matching (the extracted identifier is matched at step 1); it does not itself confirm.**
23. **Correction rules.** ### **`CONFIRMED → CORRECTED` via `HumanCorrected{decision_ref}` PROPAGATES** (spec §10.2, M-20): the lineage is walked forward, dependent fields re-derived, and a Compensation raised for every completed effect that rested on the wrong binding. Correction-of-correction is supported (append-only).
24. **Supersession rules.** ### **`RecomputedByInferrer` supersedes a `LINKER_INFERRED` claim FREELY (a legitimate projection rebuild).** Against an `OWNER_ASSERTED` claim it is an **ILLEGAL TRANSITION** (R-P3, M-15).
25. **Cancellation rules.** `PROPOSED/AMBIGUOUS → REJECTED`. A `CONFIRMED` binding on a **cancelled** entity ⇒ `SUPERSEDED`, subject returns to `UNBOUND`, human-owned.
26. **Expiry rules.** Never.
27. **Reopening rules.** N/A (a corrected/superseded claim is history; a new claim is proposed).
28. **Deletion policy.** None `[C-9]`.
29. **Retention policy.** Permanent (evidence chain).
30. **Audit requirements.** Every proposal/confirmation/correction/supersession/conflict is an Audit Event with `provenance_class`, `match_method`, and (human) `decision_ref`.
31. **Events emitted.** `ClaimProposed` · `ClaimConfirmed{provenance_class}` · `ClaimEvidenced{MODEL_EXTRACTED}` · `ClaimAmbiguous` · `ClaimCorrected` · `ClaimSuperseded` · `ConflictRaised` (on inferrer-vs-owner disagreement).
32. **Events consumed.** `DeterministicMatch` · `HumanAsserted` · `ModelReadItOffAnArtifact` · `ModelGuessed` · `MultipleCandidates`/`SingleWeakCandidate` · `HumanResolved{decision_ref}` · `RecomputedByInferrer` · `InferrerDisagrees` · `HumanCorrected{decision_ref}`.
33. **Idempotency.** `[C-3]`. Re-proposing an identical `LINKER_INFERRED` binding for an already-`CONFIRMED` subject is a no-op.
34. **Replay behavior.** `[C-5]`. ### **Replay preserves every `OWNER_ASSERTED` binding byte-identical** — a projection rebuild rebuilds projections, not the owner's mind (spec §10, S8).
35. **Security / authorization.** ### **`OWNER_ASSERTED` requires an authenticated human, bound to an IMMUTABLE identifier (never an ordinal — L-B)**: a rendered "assign unlinked 2" resolves at render time to an `observation_id`, and the action binds to that id or fails closed. `[C-6]` — a model proposes; it never confirms.
36. **Fail-closed behavior.** ### **`MODEL_INFERRED` ⇒ `AMBIGUOUS` ⇒ Exception.** A single weak candidate ⇒ `AMBIGUOUS`. Inferrer-vs-owner disagreement ⇒ `CONFLICTING` ⇒ blocks (never silently pick a winner).
37. **Structurally impossible states.** A `MODEL_INFERRED` claim in `CONFIRMED`. An `OWNER_ASSERTED` claim recomputed by the inferrer (illegal transition). Two `CONFIRMED` bindings for one subject. A `MODEL_EXTRACTED` claim with no Evidence span. Confirmation gated on a confidence score.
38. **Interaction with the checkpoint.** ### **Checkpoint step 4 (native-state validity): a claim that is `CONFLICTING`, `SUPERSEDED`, or retracted BLOCKS the action.** A consequential binding must be `LINKER_INFERRED`/`RECONCILED`/`SYSTEM_IMPORTED`/`OWNER_ASSERTED` (M-18).
39. **Interaction with Effect Grants.** A wrong binding discovered after an effect ⇒ Compensation (a gated effect).
40. **Interaction with human approval.** An `AMBIGUOUS`/`CONFLICTING` binding on a material entity ⇒ the approval cannot be requested (evidence not `consistent`) or is voided.
41. **Interaction with policy & brake.** ### **A policy/rule may never branch on a `MODEL_INFERRED` binding** (M-49). A confidence score is structurally invisible to any guard (M-16).
42. **Observability.** ### **The `AMBIGUOUS` rate is the key onboarding metric** — it should fall as the deterministic linker learns *this* customer's data. Conflict count should be near zero. Correction rate is the trust metric.
43. **Acceptance criteria.** (a) `MODEL_INFERRED` never confirms, even at confidence 1.0; (b) an `OWNER_ASSERTED` binding survives a linker re-run (illegal transition on overwrite); (c) a single weak candidate is `AMBIGUOUS`; (d) correction propagates a Compensation; (e) ordinal binding resolves to an immutable id or fails closed.
44. **Adversarial tests.** `test_owner_binding_survives_relinker` (B3 regression, M-15) · `test_guess_never_confirms_at_confidence_1_0` · `test_single_weak_candidate_is_still_ambiguous` (M-17) · `test_correction_propagates_a_compensation` (M-20) · `test_ordinal_binding_resolves_to_immutable_id_or_fails_closed` (L-B) · `test_model_extracted_requires_evidence_span` · `test_two_confirmed_bindings_impossible` · `test_no_provenance_laundering` (M-14) · `test_inferrer_vs_owner_raises_conflict_not_a_winner`.
45. **Open validation questions.** **V4** (registered deterministic identity rules — MC+date+amount? BOL? PRO?). **Fail-closed default:** exact ID match only; else `AMBIGUOUS` ⇒ human. **Migration hazard (noted, not a block):** existing owner corrections must be re-captured as `OWNER_ASSERTED` or they will be silently re-derived as `LINKER_INFERRED`.
