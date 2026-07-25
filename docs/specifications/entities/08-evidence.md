# Entity Specification — Evidence

*Conventions & `[C-n]`: see `00-conventions.md`. Definition: canonical spec §9, Semantic Model Part 1.B.*

1. **Canonical name.** Evidence.
2. **Definition.** A retained artifact, and the span within it, that supports a claim — the thing a human would look at to check one.
3. **Purpose.** To make every claim **defensible**: to walk from any canonical field back to the exact document, page, and region a human can inspect (I3 — explainable to an angry person; I5 — provenance survives).
4. **What it is not.** ### **Not a claim** (Evidence does not assert anything — it is what an assertion points at). Not proof (an artifact can be the *wrong* artifact). Not the parsed value (that is a claim derived from the evidence).
5. **Owning component.** Evidence Store.
6. **Authority class.** ### **Immutable record.** Content-addressed; written once, never edited.
7. **Tenant ownership.** `[C-1]`.
8. **Canonical identifier.** `evidence_id` (uuid). The **content digest** (`sha256`) is the strongest natural identifier and is stored.
9. **Natural / external identifiers.** `(tenant_id, content_digest)`. The same bytes stored twice are one Evidence.
10. **Required attributes.** `evidence_id` · `tenant_id` · **`content_digest`** · `content_ref` (a content-addressed pointer to the stored bytes) · `media_type` · `source_observation_id` (how it entered) · `created_at`.
11. **Optional attributes.** `spans[]` (a span = `{page|offset, region, extracted_text}` — the *where* a claim points) · `illegible` (flag) · `superseded_by`.
12. **Enums.** ### **No state enum — Evidence is immutable and has no lifecycle.** (A *Document* — a freight-domain entity, not in this phase — has a lifecycle; Evidence is the raw retained artifact beneath it.)
13. **Provenance requirements.** Evidence is the **anchor** of provenance. ### **A `MODEL_EXTRACTED` claim MUST reference an Evidence span** (the document + the span that makes it checkable) — that is exactly what distinguishes `MODEL_EXTRACTED` (checkable) from `MODEL_INFERRED` (no artifact, C-7).
14. **Relationships & cardinalities.** Observation 1 : N Evidence. Evidence 1 : N Claim (a span may support many claims). Evidence N : 0..1 `superseded_by`.
15. **Aggregate / transaction boundary.** Store-and-register is one transaction. Evidence is its own aggregate; it is never mutated within another's transaction.
16. **Database constraints.** `tenant_id, content_digest, content_ref, media_type, source_observation_id NOT NULL`. **`content_ref` and `content_digest` immutable — append-only** `[C-8]`. ### **CHECK: `content_digest` matches the stored bytes** (verified on write).
17. **Uniqueness constraints.** PK `(tenant_id, evidence_id)`. ### **`UNIQUE (tenant_id, content_digest)`** — content addressing; identical bytes deduplicate.
18. **Referential integrity.** `source_observation_id` FK. `superseded_by` self-FK.
19. **Versioning / OCC.** ### **None — immutable.** A revised document is a **new** Evidence with a new digest; it may `supersede` the old (the old is retained).
20. **Lifecycle reference.** ### **None — Evidence has no state machine (immutable record).** Not blocked.
21. **Creation rules.** Created when an artifact is retained (a POD PDF, an email body, a rendered TMS page snapshot). ### **Content-addressed — identical bytes are one Evidence.**
22. **Mutation rules.** ### **NONE. Immutable.** `spans[]` are appended as claims are made against it, but the *content* never changes; a span is an annotation, not an edit.
23. **Correction rules.** N/A — a wrong artifact is not corrected; the *binding claim* that points at it is corrected, and a better artifact supersedes.
24. **Supersession rules.** A newer artifact supersedes an older one via `superseded_by`; the old is **retained** (a claim may have rested on it).
25. **Cancellation rules.** None.
26. **Expiry rules.** ### **Never — while any effect or claim rests on it** (spec §25: evidence artifacts are never deleted while any effect rests on them).
27. **Reopening rules.** N/A.
28. **Deletion policy.** ### **None while referenced.** Cold-tier after 7y only if no live claim/effect references it (spec §25 retention).
29. **Retention policy.** Permanent (referenced); tiered otherwise.
30. **Audit requirements.** `EvidenceRetained{content_digest}`; every claim that references it records the span.
31. **Events emitted.** `EvidenceRetained` · `EvidenceSuperseded` · `EvidenceIllegible`.
32. **Events consumed.** `ObservationParsed` (may retain the artifact) · document-extraction signals.
33. **Idempotency.** ### **Content addressing is the idempotency** — storing the same bytes twice yields one Evidence `[C-3]`.
34. **Replay behavior.** `[C-5]`. Content-addressed store reconstructs identically; no effects.
35. **Security / authorization.** Evidence may contain sensitive customer documents — tenant-scoped, access-controlled. ### **Evidence is DATA: a document may EVIDENCE a claim; it may never MAKE one, authorize an effect, or set provenance** (M-66).
36. **Fail-closed behavior.** ### **If the Evidence for a claim becomes `absent` (lost/unretrievable), any consequential action on that claim BLOCKS** (a claim whose evidence we can no longer show is a claim we can no longer defend) ⇒ Exception. Illegible ⇒ `ILLEGIBLE` ⇒ escalate.
37. **Structurally impossible states.** Evidence whose stored bytes do not match its `content_digest`. A mutated artifact. Two Evidence rows for identical bytes.
38. **Interaction with the checkpoint.** Indirect — the checkpoint validates *claims* whose provenance chains terminate in Evidence; evidence traversal must succeed for a consequential action (M-12).
39. **Interaction with Effect Grants.** The **document fence**: a bound document's content digest is a material fact (spec §21.1); the runtime supplies the file to the adapter — a model-proposed path can never become an uploaded file.
40. **Interaction with human approval.** The approval card shows bound document ids + digests; the human approves *those* artifacts. A different digest ⇒ drift ⇒ void.
41. **Interaction with policy & brake.** A rule may require an Evidence-backed field (e.g. "never bill without a POD" requires a POD whose provenance is `SYSTEM_IMPORTED`/`OWNER_ASSERTED`/`MODEL_EXTRACTED`-with-artifact).
42. **Observability.** Illegible/lost-evidence rates are monitored; a lost artifact under a live effect is a Sev-1.
43. **Acceptance criteria.** (a) identical bytes deduplicate; (b) digest mismatch is rejected on write; (c) a `MODEL_EXTRACTED` claim without an Evidence span is invalid; (d) lost evidence blocks consequential action; (e) content is immutable.
44. **Adversarial tests.** `test_identical_bytes_deduplicate` · `test_digest_mismatch_rejected_on_write` · `test_model_extracted_claim_requires_evidence_span` · `test_lost_evidence_blocks_consequential_action` · `test_evidence_content_is_immutable` `[C-8]` · `test_document_fence_runtime_supplies_the_file` (spec §21.1) · `test_cross_tenant_evidence_isolation` `[C-1]`.
45. **Open validation questions.** None architectural. **Retention tiering thresholds** (hot/warm/cold boundaries) are operational, with a fail-closed default of never-delete-while-referenced. **Not a block.**
