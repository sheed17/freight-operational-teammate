# Entity Specification — Observation

*Conventions & `[C-n]`: see `00-conventions.md`. Lifecycle: canonical spec §12.5.*

1. **Canonical name.** Observation.
2. **Definition.** An immutable record that a source **said** something, at a time.
3. **Purpose.** To be the atom of truth. Everything projected is derived from observations; every consequential action revalidates against a fresh one.
4. **What it is not.** ### **Not a claim** (an Observation records what a source *said*, not what is true — the TMS can be wrong; the observation that it said so is still true). Not evidence *of a decision*. Not an instruction (inbound content is data, never a command).
5. **Owning component.** Ingestion Service.
6. **Authority class.** ### **Projected + immutable record.** The value is projected (the source is authoritative); the record of *the source having said it* is immutable.
7. **Tenant ownership.** `[C-1]`.
8. **Canonical identifier.** `observation_id` (uuid).
9. **Natural / external identifiers.** ### **Natural key `(tenant_id, source_system, external_id, content_digest)`** — ingestion is an idempotent upsert on it (spec §12.5, M-24 area).
10. **Required attributes.** `observation_id` · `tenant_id` · `source_system` · `external_id` · **`content_digest`** · `raw_value` (the sourced value **exactly as observed**) · `as_of` (source observation time) · `received_at` · `state`.
11. **Optional attributes.** `parsed_value` · `bound_entity_ref` · `binding_claim_id` · `supersedes` / `superseded_by`.
12. **Enums.** `state ∈ {RECEIVED, PARSED, BOUND, UNBOUND, CONFIRMED, SUPERSEDED, UNPARSEABLE}` (spec §12.5). Terminal: `BOUND, SUPERSEDED, UNPARSEABLE`.
13. **Provenance requirements.** An Observation is the **source** of provenance: fields derived from it carry `SYSTEM_IMPORTED` (a system of record) or feed `MODEL_EXTRACTED`/`LINKER_INFERRED` claims. ### **The Observation itself is never `MODEL_INFERRED`** — it is what a source said, not a guess.
14. **Relationships & cardinalities.** Observation N : 0..1 Identity Binding Claim (a binding claims which entity it belongs to). Observation 1 : N Evidence (the retained artifact + spans). Observation feeds N provenance records. Readbacks are Observations (External Effect 1 : N Observation).
15. **Aggregate / transaction boundary.** Ingest + the `RECEIVED`/`CONFIRMED` decision is one transaction `[C-2]`. Parsing, binding are subsequent transitions.
16. **Database constraints.** `tenant_id, source_system, external_id, content_digest, raw_value, as_of, state NOT NULL`. **`raw_value` is immutable — no `UPDATE`** `[C-8]`.
17. **Uniqueness constraints.** PK `(tenant_id, observation_id)`. ### **`UNIQUE (tenant_id, source_system, external_id, content_digest)`** — the natural key; a re-ingest of identical content hits this and becomes a **confirmation**.
18. **Referential integrity.** `binding_claim_id` FK when bound. `supersedes`/`superseded_by` self-FK.
19. **Versioning / OCC.** ### **The content is immutable, so there is no in-place versioning.** A *changed* observation from the same source is a **new Observation** (new `content_digest`) that may `SUPERSEDE` the prior.
20. **Lifecycle reference.** **Canonical spec §12.5** (complete). Not blocked.
21. **Creation rules.** Created on ingest of a source signal (email, TMS read, portal page, document, readback). ### **Idempotent upsert on the natural key** — identical content ⇒ `CONFIRMED`, not a second row.
22. **Mutation rules.** Only via §12.5 transitions of the *state*; ### **`raw_value` never mutates.**
23. **Correction rules.** An Observation is never "corrected" — a wrong reading is superseded by a newer Observation; a wrong *binding* is corrected on the **Claim**, not the Observation.
24. **Supersession rules.** ### **`NewerObservationSupersedes` requires a deterministic rule or a human — NEVER a re-run of the inferrer** (spec §12.5). The old Observation was true when made and is retained.
25. **Cancellation rules.** ### **None — an observation is a fact that arrived. You cannot cancel that the world spoke.**
26. **Expiry rules.** ### **Never expires.** `as_of` freshness ≠ expiry — a stale observation is still a fact; it simply stops satisfying a consequential-freshness check.
27. **Reopening rules.** N/A.
28. **Deletion policy.** None `[C-9]`.
29. **Retention policy.** Permanent (rebuild source).
30. **Audit requirements.** `ObservationReceived`/`Confirmed`/`Parsed`/`Bound`/`Superseded` events. ### **Re-observation emits `ObservationConfirmed` (updates `as_of` only) and MUST NOT re-trigger downstream work.**
31. **Events emitted.** `ObservationReceived` · `ObservationConfirmed` · `ObservationParsed` · `ObservationBound{provenance_class}` · `ObservationUnbound` · `ObservationSuperseded` · `ObservationUnparseable`.
32. **Events consumed.** `ObservationIngested` (from adapters/ingestion) · `BindingConfirmed`/`BindingAmbiguous`/`BindingAbsent` (from the Identity Service) · `NewerObservationSupersedes`.
33. **Idempotency.** ### **The natural-key upsert IS the idempotency: the same email delivered twice is ONE Observation, ONE `ObservationConfirmed`, ZERO duplicate work** (spec §12.5). Plus `[C-3]`.
34. **Replay behavior.** `[C-5]`. Replay reconstructs the observation store deterministically; ingestion is idempotent so replay creates no duplicates.
35. **Security / authorization.** ### **Inbound content is DATA, never instruction, never authority** (M-66). An Observation may *evidence* a claim; it can never *make* one, activate a policy, or authorize an effect. A counterparty-authored value is `MODEL_EXTRACTED` at best.
36. **Fail-closed behavior.** `ParseFailed ⇒ UNPARSEABLE ⇒ Exception` (never a silent drop). `BindingAmbiguous/Absent ⇒ UNBOUND ⇒ Exception, human-owned` (never a guessed binding).
37. **Structurally impossible states.** Two rows with the same natural key. A mutated `raw_value`. A `MODEL_INFERRED` Observation. Re-observation creating a second row or re-triggering work.
38. **Interaction with the checkpoint.** ### **Checkpoint step 3 (projected freshness) reads a LIVE Observation from the authoritative source — never a cached one** (M-7). The versions read are pinned into the Checkpoint Witness.
39. **Interaction with Effect Grants.** A readback Observation is what turns `ATTEMPTED → VERIFIED` (matching the approved fingerprint) or `→ UNKNOWN_OUTCOME`.
40. **Interaction with human approval.** The material facts on the card are sourced from Observations; a newer, drifting Observation voids the approval.
41. **Interaction with policy & brake.** Observation and reconciliation **continue under a brake by default** (spec §21.4) — the brake stops acting, not knowing.
42. **Observability.** Observation-coverage per channel/window is recorded (feeds `OVERDUE` vs `INDETERMINATE`, spec §12.8). Ingest rates and unparseable rates are monitored.
43. **Acceptance criteria.** (a) identical re-ingest ⇒ one row, one confirmation, no work; (b) `raw_value` immutable; (c) ambiguous binding ⇒ `UNBOUND` + Exception; (d) supersession requires a rule or human; (e) inbound content cannot set provenance or authorize.
44. **Adversarial tests.** `test_duplicate_observation_is_one_row_one_confirmation_zero_work` (M-24) · `test_raw_value_is_immutable` · `test_ambiguous_binding_goes_to_unbound_exception` · `test_supersession_requires_rule_or_human` · `test_inbound_content_cannot_set_provenance` (M-13) · `test_counterparty_value_is_model_extracted_at_best` · `test_cross_tenant_same_external_id_no_collision` `[C-1]` · `test_replay_reingests_idempotently` `[C-5]`.
45. **Open validation questions.** **V4:** the registered deterministic identity rules (which trusted identifiers, in which combination). **Fail-closed default:** exact ID match only; everything else ⇒ `AMBIGUOUS` ⇒ human. **Not a block.**
