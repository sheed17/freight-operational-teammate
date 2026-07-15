# Entity Specification — External Effect

*Conventions & `[C-n]`: see `00-conventions.md`. Lifecycle: canonical spec §12.3.*

> ### **RESOLVED MODELING DECISION (surfaced in the review, §2/§4/§6).**
> **The External Effect and the Effect Grant are the SAME durable ledger row — the `effect_grants` row — viewed through two aspects.** `04-effect-grant.md` describes the **capability aspect** (may this attempt act?); this file describes the **outcome aspect** (what happened when it did?). ### **This is not a new primitive — both are already canonical entities, and spec §12.3 models them as one machine.** The alternative (two 1:1 rows) was rejected: it would duplicate the commit-key namespace across two tables, and P36 forbids two things that mean the same. The commit-key HOLD through `NEEDS_VERIFICATION` is provided by the **Pipeline Instance Layer-1 reservation** (which is non-terminal in `NEEDS_VERIFICATION`), not by this row's state — so the `effect_grants` commit-once index (`WHERE state='CLAIMED'`, spec §16.1) is correct and needs no widening.

1. **Canonical name.** External Effect.
2. **Definition.** The durable record of an *attempt to touch the world* — the only irreversible thing in the system.
3. **Purpose.** To answer, durably and honestly, *what happened when we acted*: verified success, provable failure, or an unknown outcome that a human must resolve.
4. **What it is not.** Not the capability to act (that is the grant aspect). Not a local write (a JSON write is not an External Effect — M-72). Not "the adapter returned 200" (that is a proxy, not the money).
5. **Owning component.** Effect Grant Ledger (Safety Kernel).
6. **Authority class.** ### **Immutable record of the interaction, carrying a state that advances** — the *fact of the attempt* is immutable; the *verification outcome* is established once and never re-guessed.
7. **Tenant ownership.** `[C-1]`.
8. **Canonical identifier.** `grant_id` (the same row as the Effect Grant — see the resolution box). Referenced as `external_effect_id` = `grant_id`.
9. **Natural / external identifiers.** `commit_key` (the logical effect). The external record's own id (e.g. TMS invoice number), when known, is stored as **evidence of verification**, ### **never used to key idempotency** (spec §10.1 — the TMS may renumber).
10. **Required attributes.** `grant_id` · `tenant_id` · `commit_key` · `pipeline_instance_id` · `action_class` · `target_system` · `target_resource_id` · `target_operation` · `state` · `attempted_at` (set at claim) · `material_facts_fingerprint` (what we intended).
11. **Optional attributes.** `verified_at` · `verification_outcome` · `unknown_reason` · `exposure` · `external_record_ref` (evidence, not a key) · `health_signal` (the positive control that justified a `VERIFIED_FAILURE`) · `reality_decision_ref`.
12. **Enums.** *(SD-2 clarification.)* ### **The SAME single `effect_grants.state` column** (see `04-effect-grant.md` point 12) — the outcome aspect *continues from `CLAIMED`* through `{ATTEMPTED, VERIFIED, FAILED, UNKNOWN_OUTCOME}`; the full eight-value domain is `{GRANTED, CLAIMED, ATTEMPTED, VERIFIED, FAILED, EXPIRED_UNCLAIMED, REVOKED, UNKNOWN_OUTCOME}`. Terminal: `VERIFIED, FAILED, EXPIRED_UNCLAIMED, REVOKED`. ### **Non-terminal, human-owned: `UNKNOWN_OUTCOME`.** `verification_outcome` ∈ the 8-member canonical registry (a **separate** field recording *how* the outcome was established, distinct from the row `state`). `unknown_reason` ∈ its 3 members. *(SD-4: see point 22 for how each `verification_mode` maps to these states.)*
13. **Provenance requirements.** `VERIFIED_SUCCESS` requires a readback matching the **approved** material fingerprint from a **healthy** channel (M-70/M-71). The `external_record_ref` is `MODEL_EXTRACTED` at best and is evidence only.
14. **Relationships & cardinalities.** Pipeline Instance 1 : 0..1 External Effect. External Effect 1 : 0..1 Compensation (if later invalidated). External Effect 1 : N Observation (readbacks are observations).
15. **Aggregate / transaction boundary.** Same row as the Effect Grant. ### **The `CLAIMED` transition is the claim CAS transaction. `VERIFIED → recorded` is ONE transaction with the projection-eligible event** (spec §12.2 "verify + record = one commit") — closing the "verified but not recorded" window.
16. **Database constraints.** `tenant_id, grant_id, commit_key, pipeline_instance_id, state NOT NULL`. **CHECK: `unknown_reason NOT NULL` iff `state = UNKNOWN_OUTCOME`.** **CHECK: `state = FAILED` requires a non-null `failure_proof` (affirmative evidence — M-73).** **CHECK: `state = VERIFIED` requires a non-null `health_signal` on the verifying read.**
17. **Uniqueness constraints.** PK `(tenant_id, grant_id)`. Commit-once is on the grant aspect (point 17 of `04-effect-grant.md`).
18. **Referential integrity.** `pipeline_instance_id`, `commit_key` consistent with the pipeline.
19. **Versioning / OCC.** State advances under `[C-10]`; the *attempt fact* never mutates.
20. **Lifecycle reference.** **Canonical spec §12.3** (complete). Not blocked.
21. **Creation rules.** Created (as the grant) at mint; enters the outcome lifecycle at the successful claim (`CLAIMED`).
22. **Mutation rules.** Only via §12.3 transitions. ### **`FAILED` requires affirmative proof of non-occurrence.** ### **`VERIFIED` requires a healthy-channel readback matching the approved fingerprint.** Everything else that "didn't find it" is `UNKNOWN_OUTCOME` with a reason.

    **The three verification modes map deterministically to `state`+`verification_outcome` *(SD-4 clarification; the modes are the frozen set from spec §18/§26.1 — no new mode)*:**

    | `verification_mode` *(declared per action class — see `00-conventions.md` K-5)* | What "verified" means | Resulting `state` / `verification_outcome` |
    |---|---|---|
    | **`READBACK_VERIFIABLE`** | a live, **healthy-channel** read of the authoritative record matches the approved fingerprint | match ⇒ `VERIFIED`/`VERIFIED_SUCCESS`; contradiction ⇒ `UNKNOWN_OUTCOME`/`OBSERVATION_CONFLICTING`; blind ⇒ `UNKNOWN_OUTCOME`/`OBSERVATION_UNAVAILABLE`; healthy-and-absent ⇒ `FAILED`/`VERIFIED_FAILURE` |
    | ### **`RECEIPT_VERIFIABLE`** | the authoritative system returned a **synchronous receipt that uniquely identifies THIS effect** (e.g. a portal confirmation id, an API 2xx carrying the created record's id) | ### **the receipt is itself an Observation.** A receipt that **uniquely identifies this effect** ⇒ `VERIFIED`/`VERIFIED_SUCCESS`. A receipt that only confirms **transmission** (e.g. SMTP `250`, "queued") ⇒ ### **NOT verified** ⇒ `ATTEMPTED` + an **Expectation** (`AWAITING_OBSERVATION`) or `VERIFICATION_DEFERRED` with a bound; ### **it MUST NOT record "delivered/received/read" (M-72), and it may NEVER yield `VERIFIED_FAILURE`** (a receipt can confirm, never disprove). |
    | ### **`UNVERIFIABLE`** | the external system offers **no readback and no identifying receipt, ever** | ### the operation is `PERMANENT_HUMAN_ASSERTION_REQUIRED`-adjacent: it **may not be `AUTONOMOUS_WITHIN_CAPS`** (M-39); we record only the proven transmission fact; the field stays projected-`unknown`; ### **the human IS the verification.** |

    ### **A receipt is an authoritative confirmation, never a proxy: an SMTP `250` or a bare HTTP `200` is transmission, not verification** (M-72 — the money is in the record, not the response). The dividing line is *"does the receipt uniquely identify the specific effect?"* — declared per adapter, never inferred at runtime.
23. **Correction rules.** The outcome, once established (`VERIFIED`/`FAILED`), is not re-established. A later correction of an underlying *binding* does not rewrite the effect — it raises a **Compensation**.
24. **Supersession rules.** N/A.
25. **Cancellation rules.** ### **None after `CLAIMED`.** *You cannot cancel that the world may have changed.*
26. **Expiry rules.** `GRANTED` unclaimed past TTL ⇒ `EXPIRED_UNCLAIMED`. ### **`UNKNOWN_OUTCOME` NEVER expires** (M-73).
27. **Reopening rules.** N/A.
28. **Deletion policy.** None `[C-9]`.
29. **Retention policy.** Permanent.
30. **Audit requirements.** `EffectAttempted` (emitted **before** the adapter call — M-38 step 6), `EffectVerified`, `EffectFailed{proof}`, `OutcomeUnknown{exposure,unknown_reason}`, `RealityEstablished`. The `EffectAttempted`-without-a-matching-CLAIMED-grant reconciliation drives orphan detection (spec §19.9 layer 5).
31. **Events emitted.** As point 30, plus `VerificationDeferred{recheck_at}`, `VerificationConflict`, `VerificationUnavailable`.
32. **Events consumed.** `GrantClaimed` · `AdapterReturnedSuccess`/`AdapterRejectedPreFlight`/`AdapterTimedOut`/`ProcessCrashed` · readback observations · `HumanEstablishedReality{decision_ref}` · `LaterObservationProves`.
33. **Idempotency.** `[C-3]`. The `EffectAttempted` event is emitted once, before the call, so a lost response is detectable. **A retry is a new grant/effect under the same `commit_key`; if the first attempt secretly committed, the second attempt's grant claim proceeds but verification finds the conflict** — and Layer-1 prevents a *concurrent* second pipeline in the first place.
34. **Replay behavior.** `[C-5]`. Replay reconstructs the outcome record; it performs no adapter call.
35. **Security / authorization.** Reachable only via a claimed grant + fresh witness (M-38). An `EffectAttempted` with no matching claimed grant ⇒ ### **Sev-0, auto-engages the brake** (spec §19.9).
36. **Fail-closed behavior.** ### **The load-bearing rule: `CLAIMED` + (crash | timeout | lost response) ⇒ `UNKNOWN_OUTCOME`, NEVER `FAILED`.** No health signal on a "not found" read ⇒ `OBSERVATION_UNAVAILABLE` ⇒ `UNKNOWN_OUTCOME`, never `VERIFIED_FAILURE`.
37. **Structurally impossible states.** `VERIFIED` without a healthy-channel readback matching the fingerprint. `FAILED` without affirmative proof. A timer transitioning `UNKNOWN_OUTCOME`. An `ATTEMPTED` with no `EffectAttempted` event (orphan).
38. **Interaction with the checkpoint.** Created only *after* the checkpoint (as the grant) and claimed only via the CAS; the checkpoint is upstream.
39. **Interaction with Effect Grants.** ### **Same row.** The grant is the pre/at-claim aspect; this is the post-claim aspect.
40. **Interaction with human approval.** `VERIFIED_SUCCESS` matches the *approved* fingerprint; a mismatch is `OBSERVATION_CONFLICTING` ⇒ `UNKNOWN_OUTCOME` (something acted that we did not authorize, or we acted wrongly).
41. **Interaction with policy & brake.** A brake never converts an in-flight effect to failure (spec §21.5). Verification (a read) continues under a brake.
42. **Observability.** `UNKNOWN_OUTCOME` count is a Sev-1 metric; each carries exposure, the specific human question, and what is frozen (spec §26.3).
43. **Acceptance criteria.** (a) blindness yields `OBSERVATION_UNAVAILABLE`, not failure; (b) no timer moves `UNKNOWN_OUTCOME`; (c) `FAILED` requires proof; (d) verify+record is one commit; (e) `EffectAttempted` precedes the call.
44. **Adversarial tests.** `test_logged_out_session_yields_OBSERVATION_UNAVAILABLE_not_VERIFIED_FAILURE` · `test_no_timer_can_move_an_unknown_outcome` · `test_local_write_cannot_satisfy_verification` (M-72) · `test_readback_must_match_approved_fingerprint` · `test_effect_attempted_without_claimed_grant_is_sev0_and_brakes` · `test_verify_and_record_are_one_commit` · `test_replay_produces_zero_effect_attempts` `[C-5]` · ### `test_receipt_confirming_only_transmission_does_not_verify` (SD-4) · `test_receipt_can_never_yield_verified_failure` (SD-4) · `test_unverifiable_operation_field_stays_projected_unknown`.
45. **Open validation questions.** **V7:** can the `commit_key` be written into the external record, enabling deterministic `LaterObservationProves` discharge of `UNKNOWN_OUTCOME`? **Fail-closed default:** if not, a human resolves it; we never infer. **Not a block.**
