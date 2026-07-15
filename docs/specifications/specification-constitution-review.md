# Specification Constitution Review — A Hostile Review of the Specification Layer

**Subject:** the 17 foundational entity specifications (`docs/specifications/entities/`) + `00-conventions.md`.
**Posture:** ### **Hostile. The question is not "is the architecture sound?" (it is, and is frozen). The question is: "could two experienced engineers implement this entity independently and produce materially different behavior?" Every yes is a specification defect.**
**Method:** line-level interrogation + mechanical grep, against Engineering Principles · Operating Model · Semantic Model · Target Spec (`7ae1564`) · ADR-001…011.
**Date:** 2026-07-13 · **No specification was modified. No higher document was amended.**

---

## 1. EXECUTIVE SUMMARY

The entity specifications are **structurally excellent** — 45/45 points each, canonical enums only, zero deprecated terms, cardinalities and transaction boundaries that reconcile (confirmed by the prior consistency review). **The architecture-derived guarantees are sound.**

**But this review found five specification defects where two engineers WOULD diverge, and two of them are safety-adjacent.** They are not architecture gaps — the architecture already implies the right answer in each case — they are places where the **entity layer under-specifies the referent, the domain, or the selection rule**, leaving a decision to the implementer that must not be left to the implementer.

> ### **Because at least one under-specification (which entity versions the checkpoint pins) can silently permit a stale-fact write, and another (what `decision_ref` references) can weaken "never closed without a decision" into "never closed without a string," the honest verdict is NOT READY — pending a bounded, spec-layer-only clarification pass.**

**Crucially: every finding is resolvable ENTIRELY within specification engineering. NONE requires amending a higher-level document.** The fix is a short, mechanical clarification pass over ~6 files. This is a punch-list, not a redesign.

---

## 2. AMBIGUITIES DISCOVERED

### SD-1 — `decision_ref` has no defined referent · **MATERIAL + SAFETY-ADJACENT**
`decision_ref` is used as a **required field / foreign key in nine files** (Work Item, Pipeline Instance, External Effect, Approval, Conflict, Identity Binding Claim, Compensation, Exception, Brake). It is the linchpin of *"an exception closed without a decision is not closed"* (I11), *"a conflict resolved only by a human `decision_ref`"*, *"reopening requires a `decision_ref`."*

> ### **No entity specifies WHAT a `decision_ref` points to.** ADR-008 says only *"a human decision id or a deterministic rule id."*

**Two engineers diverge:** (a) a free-text string; (b) an FK to the `audit_events` row recording the human's decision; (c) an FK to a new `HumanDecision` entity. **Under (a), an Exception can be "closed" with the string `"done"` — satisfying the CHECK constraint while referencing nothing.** That **weakens the closure guarantee from "a real decision exists" to "a non-null string exists."** The whole I11 mechanism rests on a field whose meaning is undefined.

### SD-5 — `entity_ref` vs `subject_ref` vs `target_resource_id` · **MATERIAL**
Three names for "the thing this record is about," with undefined boundaries:
- `entity_ref` — Work Item, Observation, Identity Binding Claim (the projected business entity)
- `subject_ref` — Identity Binding Claim, Expectation (the artifact/observation being bound or awaited)
- `target_resource_id` — Effect Grant, Pipeline Instance (the external resource acted upon)

**Two engineers diverge:** is a Work Item's `entity_ref` the same value as its Pipeline Instance's `target_resource_id`? Is an Identity Binding Claim's `subject_ref` (the artifact) distinct from its `entity_ref` (the entity it's bound to)? The 09 file uses **both** `subject_ref` and `entity_ref` without stating they are the two ends of the binding. **One engineer treats them as synonyms; another as the two ends of a relation. Their join logic differs.**

### Minor ambiguities
- **SD-6 — `match_method` vs `provenance_class` (Identity Binding Claim).** Both are stored (points 10–13 of `09`); `provenance_class` is described as *derived from* `match_method`, but **not stated as a computed/immutable derivation**. Two engineers: one stores both and lets them drift; one derives on read. **Recommend:** state that `provenance_class` is a **deterministic function of `match_method`**, written once, never independently edited.
- **SD-9 — `exposure` (a money value) on Work Item / Exception / Compensation vs "Memory MUST NEVER store a money value" (spec §22).** These do not contradict (the rule governs the *knowledge/memory* store, not operational records), but a reader can mis-scope it. **Recommend:** one sentence scoping the money-in-memory prohibition to the knowledge base, explicitly permitting `exposure` on operational records **sourced from a verified/live read**.

---

## 3. HIDDEN ASSUMPTIONS

- **HA-1 — Every "ONE transaction" guarantee assumes the single transactional store (A1).** The checkpoint atomicity, verify+record atomicity, the outbox, and the claim CAS all silently assume machine state + ledger + outbox share one store. This **is** decided (A1, ADR-008 §2.1) and the modular-monolith posture (A2) — but **no entity file restates that its transaction-boundary guarantee DEPENDS on A1.** A future distributed refactor that missed this would silently break commit-once and I10. *(ADR-004 §4.4 anticipates this: authority lives in the shared ledger precisely so a process split preserves it — but the entity specs don't carry that forward.)* **Recommend:** a `[C-11]` convention noting that all one-transaction guarantees require the shared store, and a distributed evolution must preserve them via the shared ledger.
- **HA-2 — Clock source.** TTLs use "the DB clock" (pinned — good). But event `occurred_at` is implicitly the producer's clock; harmless in a monolith, an ordering hazard if distributed. **Note only.**
- **HA-3 — `entity_ref` may reference a not-yet-existing projected entity**, relying on dangling-reference parking (M-26). Assumed by Work Item / Observation but not restated. **Note only.**

---

## 4. MULTIPLE VALID INTERPRETATIONS

Beyond SD-1 and SD-5 (§2), the sharpest:

### SD-2 — The `effect_grants` unified `state` column domain is unspecified · **MATERIAL + SAFETY-ADJACENT**
The prior review resolved *"Effect Grant and External Effect are the same row, two aspects."* **But the two files then declare two different `state` enums:**
- `03-external-effect.md`: `{GRANTED, CLAIMED, ATTEMPTED, VERIFIED, FAILED, EXPIRED_UNCLAIMED, UNKNOWN_OUTCOME}` (7)
- `04-effect-grant.md`: `{GRANTED, CLAIMED, EXPIRED_UNCLAIMED, REVOKED}` (4)

**If it is one row, what is the actual `state` column's domain?** The union is **eight** states — and `REVOKED` (in `04`) **appears in neither the External Effect enum nor spec §12.3.** Two engineers building "one row" will **build two different state columns**, and their commit-once index (`WHERE state='CLAIMED'`) and their revocation handling will differ. **Worse:** if one engineer models `REVOKED` or an outcome transition as *leaving* a commit-key-holding state at the wrong moment, a **commit-once hole** can open. The resolution named the *concept* but never pinned the *column*.

### SD-4 — `RECEIPT_VERIFIABLE` verification mode is named but unspecified
The architecture (spec §18, §26.1) declares three verification modes: `READBACK_VERIFIABLE`, `RECEIPT_VERIFIABLE`, `UNVERIFIABLE`. **The entity layer specifies readback and impossible in detail — but `RECEIPT_VERIFIABLE` appears in ZERO entity files** (grep-confirmed). Which of the eight verification outcomes does a receipt produce? Is an SMTP 250 or an API confirmation-id a `VERIFIED_SUCCESS`, or a distinct receipt-outcome that still needs later reconciliation? **Two engineers implementing a receipt-verifiable adapter will make different choices about whether a receipt closes the effect.** Given M-72 (*local persistence is never verification*) and the "never say delivered" rule, the boundary of what a *receipt* may assert is exactly the kind of thing that must be pinned.

---

## 5. MISSING DETERMINISTIC BEHAVIOR

### SD-3 — The `entity_versions` selection rule is unspecified · **MATERIAL + SAFETY** *(the most serious finding)*
The Checkpoint Witness and Effect Grant both bind **`entity_versions`** — described as *"the versions of every entity whose state made this action correct"* (spec §19.3, ADR-009 §5). **No file specifies the RULE for which entities are in that set.**

> ### **This is not a clarity nicety — it is a correctness hole the specification currently permits.**
> Checkpoint step 5 (entity-version concurrency) only fails if a **pinned** entity's version changed. **If an engineer pins too few entities — say, the load but not the customer record whose credit-hold status is material — then a concurrent change to the unpinned entity does NOT fail the checkpoint, and the effect proceeds on a stale fact.** The specification, as written, does not forbid this: it leaves the selection to interpretation.

**Two engineers pin different sets. One system catches a concurrent credit-hold change; the other bills anyway.** **Recommend (within spec):** a deterministic rule — *"`entity_versions` MUST include the version of every entity referenced by any material fact in the fingerprint, plus the target resource."* — testable and mechanical.

### SD-7 — `CheckpointFailed{step}` when multiple steps fail
The seven checks are "one atomic decision." **If two fail, which `step` is reported?** Undefined. Two engineers: one reports the first failure by a fixed order; one reports all. This changes the drift explanation and the observability metric (spec §21.2 requires a *specific* diff). **Recommend:** a fixed evaluation order (approval → fingerprint → freshness → native → version → policy → brake) and *"the first failing step is reported; the checkpoint short-circuits."* — OR *"all failures are collected"* — but **pick one.**

### SD-10 — Work Item deduplication across trigger sources
Two triggers about the same obligation (an inbound email **and** an AR sweep both flag load 4471 for billing) create **two Work Items** — `01` point 17 states *"no business-natural uniqueness."* The Pipeline-Instance Layer-1 reservation dedups the **effect**, but **nothing relates or merges the two Work Items.** Is that intended (two independent "we should" signals) or a defect (two owners, two closures for one obligation)? **The spec is silent, so two engineers build different things.** **Recommend:** state the intent explicitly — either "Work Items are not deduplicated; the effect layer prevents double-action" (and how a redundant Work Item is closed) or a correlation rule.

---

## 6. MISSING TESTABILITY

The specifications are **strongly testable** — every entity's point 44 names concrete adversarial tests, and the acceptance criteria (point 43) are mechanical. **Two testability gaps trace directly to the ambiguities above:**

- **SD-1 ⇒** `test_exception_closure_requires_decision_ref` is currently satisfiable by a non-null **string**. Until the referent is defined, the test **cannot assert that a real decision exists** — only that a field is non-null. The test is weaker than the requirement it claims to enforce.
- **SD-3 ⇒** there is **no test that could exist** for "the checkpoint pins all material entities," because the required set is undefined. `test_stale_version_transition_fails` tests a *pinned* entity; nothing tests that the *right* entities were pinned. **An untestable requirement is an incomplete specification** (review area F).

Everything else (brake races, drift-void, blindness, no-laundering, replay-zero-grants) is mechanically testable as written.

---

## 7. SAFETY GAPS

**Could an implementation satisfy the specification and still bypass a control?**

| Control | Bypassable within spec? | Evidence |
|---|---|---|
| Effect Grant | ❌ No | `mint_grant(witness: CheckpointPassed)` + no public constructor + CI import gate + CAS (specified in `04`/`05`). |
| Checkpoint Witness | ❌ No | Type-level; replay cannot construct one. |
| Policy / Brake | ❌ No | Checkpoint steps 6/7 + claim-CAS re-validation of `policy_version`/`brake_version`. |
| Approval | ❌ No | Fingerprint at step 2; single-use CAS. |
| Tenant isolation | ❌ No | `tenant_id` first in every key; `[C-1]`. |
| Provenance | ❌ No | R-P1/2/3 + no-laundering test. |
| Verification | ⚠️ **Partially — SD-4** | `RECEIPT_VERIFIABLE` is unspecified; a lax reading could let a receipt assert success a readback would not. |
| **Concurrency / stale fact** | ⚠️ **YES — SD-3** | **The `entity_versions` selection rule is undefined, so an implementation can pin too few entities and act on a stale material fact while passing the checkpoint.** |
| **Decision integrity** | ⚠️ **YES — SD-1** | **`decision_ref` as free text lets a closure/resolution reference nothing, weakening I11/conflict-closure to a non-null-string check.** |
| Compensation | ❌ No | Full pipeline; forbidden on unknown; no bulk undo. |
| Replay | ❌ No — **but see SD-8** | Cannot mint a grant. **SD-8:** files say "replay reconstructs state" without uniformly stating *"into a sandbox, emitting ZERO events to real consumers, writing only sandbox projections."* One engineer could build a replay that **re-emits to the live outbox**, re-triggering work. `17` says replay creates no Audit Events; the other files should say the same about **all** side effects. **Recommend a `[C-5]` addendum: replay is read-only reconstruction into an isolated sandbox; it emits nothing to real consumers and mints nothing.** |

> ### **Two genuine safety-adjacent gaps (SD-1, SD-3) and one latent one (SD-8) exist not because the architecture permits them — it does not — but because the entity layer left a referent/rule/scope under-specified. This is exactly the class of defect this review exists to catch.**

---

## 8. CROSS-SPECIFICATION INCONSISTENCIES

- **SD-2** (the `effect_grants` state domain — two files, two enums, one row) — the sharpest cross-file inconsistency.
- **SD-5** (`entity_ref`/`subject_ref` used in overlapping ways across `01`/`07`/`09`/`11`).
- **SD-8** (replay side-effect language inconsistent between `17` and the others).
- **Otherwise consistent:** state names, event names, provenance classes, gate decisions, verification outcomes, evidence conditions, and identifier spellings are **identical across all 17 files** (grep-confirmed in the prior review and re-confirmed here). No ownership disagreements. No conflicting transaction boundaries. No duplicate responsibilities beyond the already-resolved Grant/Effect aspect split.

---

## 9. EVOLUTION RISKS

- **SD-11 — `occurrence_key` derivation is illustrated per-action-class by EXAMPLE (spec §19.7), not declared as an extensible property.** Adding a new payment type or action class requires knowing its `occurrence_key` rule. If implemented as a central switch, **every new action class edits shared code** — an extensibility smell. **Recommend:** `occurrence_key` derivation is a **declared property of the action class** (registered with its gate decision and verification mode), so a new class is additive.
- **New action class / integration / adapter:** ✅ **additive and safe** — the gate registry, verification-mode declaration, and adapter registration are all additive; adding one does not change existing semantics (verified against `02`/`14`/`18`). This is a strength.
- **SD-12 — GLOBAL brake across N tenants.** `16` point 7 says a `GLOBAL` brake "spans tenants but is recorded per-tenant." **One row or N? Engaged atomically how?** Under-specified for multi-tenant. Harmless at v1 (few tenants), a real question at scale. **Recommend:** specify the GLOBAL-brake representation and its atomic-engagement semantics.
- **New counterparty role (e.g. a factoring company).** `money_direction` is binary IN/OUT and Counterparty is `customer | carrier`. A **factor** inserts a third party into the money flow. This is **freight-domain (deferred)**, but flag it: the foundational Counterparty/`money_direction` model may need extension, and that extension should not require re-specifying the money fence. **Watch-item, not a current defect.**

---

## 10. RECOMMENDED CLARIFICATIONS *(all within spec engineering)*

| # | Finding | Fix | Sev |
|---|---|---|---|
| **SD-1** | `decision_ref` referent undefined | Define `decision_ref` as an FK to the `audit_events` row recording the authenticated human decision, **or** a `rule_id` — with a CHECK that it resolves. Add to `00-conventions.md`. | **Material/Safety** |
| **SD-2** | `effect_grants` state domain | Pin ONE `state` column domain = **8 states** `{GRANTED, CLAIMED, ATTEMPTED, VERIFIED, FAILED, EXPIRED_UNCLAIMED, REVOKED, UNKNOWN_OUTCOME}`; state which are the "grant aspect" vs "outcome aspect" projections of the single column; confirm commit-once `WHERE state='CLAIMED'`. | **Material/Safety** |
| **SD-3** | `entity_versions` selection rule | *"MUST include the version of every entity referenced by any material fact, plus the target resource."* Add a test. | **Material/Safety** |
| **SD-4** | `RECEIPT_VERIFIABLE` semantics | Specify its outcome mapping in `03`: a receipt yields `VERIFIED_SUCCESS` **only** when the receipt is an authoritative confirmation of the *specific* effect; otherwise `AWAITING_OBSERVATION`/`VERIFICATION_DEFERRED`. Never "delivered." | **Material** |
| **SD-5** | `entity_ref`/`subject_ref`/`target_resource_id` | Define each precisely in `00-conventions.md` and state their relationships (a binding's `subject_ref` = artifact, `entity_ref` = bound entity; a pipeline's `target_resource_id` = the external resource; the Work Item's `entity_ref` = the projected entity). | **Material** |
| **SD-6** | `match_method`→`provenance_class` | State the derivation is deterministic and immutable. | Minor |
| **SD-7** | multi-step `CheckpointFailed` | Fix the evaluation order + short-circuit-first (or collect-all). | Minor |
| **SD-8** | replay side-effects | `[C-5]` addendum: sandbox, zero real emissions, zero mints. | Minor/Safety |
| **SD-9** | `exposure` vs memory-money rule | Scope the money-in-memory prohibition to the knowledge base. | Minor |
| **SD-10** | Work Item dedup across triggers | State the intent (no dedup; effect layer prevents double-action; redundant items closed how). | Minor |
| **SD-11** | `occurrence_key` extensibility | Declare it a property of the action class. | Minor/Evolution |
| **SD-12** | GLOBAL brake representation | Specify one-row-or-N + atomic engagement. | Minor/Evolution |

---

## 11. CLARIFICATIONS REQUIRING HIGHER-LEVEL AMENDMENTS

> ### **NONE.**

Every finding is resolvable within the specification layer. In each case the **architecture already implies the correct answer** — `decision_ref` is "a human decision id or rule id" (ADR-008); `entity_versions` is "every entity whose state made this action correct" (ADR-009 §5); the Grant/Effect unification is the prior review's resolution; `RECEIPT_VERIFIABLE` is a named mode in the frozen spec. **The entity layer simply failed to make these precise.** No ADR, no Semantic-Model entry, no Operating-Model invariant, and no Target-Spec section needs to change.

*(The one previously-noted **recommended-not-required** clarifying note to canonical §12.3/§16.1 — that the External Effect and Effect Grant are one `effect_grants` row — would also cleanly resolve SD-2 at the source. It remains optional; SD-2 can be fixed entirely in the entity layer.)*

---

## 12. CLARIFICATIONS RESOLVABLE ENTIRELY WITHIN SPECIFICATION ENGINEERING

> ### **ALL TWELVE (SD-1 … SD-12).**

The fix is a bounded clarification pass touching ~6 files:
- **`00-conventions.md`:** define `decision_ref` (SD-1), the three "about" references (SD-5), the replay-sandbox addendum (SD-8), the money-in-memory scope (SD-9), a new `[C-11]` for the single-store dependency (HA-1).
- **`03-external-effect.md` + `04-effect-grant.md`:** the unified 8-state column (SD-2), `RECEIPT_VERIFIABLE` (SD-4).
- **`05-checkpoint-witness.md`:** the `entity_versions` selection rule + a test (SD-3); the multi-step-failure order (SD-7).
- **`09-identity-binding-claim.md`:** `match_method`→`provenance_class` derivation (SD-6).
- **`01-work-item.md`:** trigger-source dedup intent (SD-10).
- **`14-policy.md` / action-class registry:** `occurrence_key` as a declared property (SD-11).
- **`16-brake.md`:** GLOBAL-brake representation (SD-12).

**No new entity. No new state. No new event. No architecture change.**

---

## 13. FINAL READINESS ASSESSMENT

The specification layer is **close** — the structure, the canonical vocabulary, the transaction boundaries, and the adversarial-test surface are all strong, and **no finding requires touching the frozen architecture.** But this was a hostile review, and it found what it was sent to find:

- **Two safety-adjacent under-specifications** (SD-1 `decision_ref` referent; **SD-3 `entity_versions` selection rule**) where an implementation can satisfy the spec and still weaken a control — SD-3 by acting on a stale material fact, SD-1 by closing a decision that references nothing.
- **Two material interpretation gaps** (SD-2 the one-row state domain; SD-4 receipt verification) where two engineers build **different behavior**.
- **One material naming ambiguity** (SD-5) and seven minor clarity/determinism/evolution items.

By the review's own rule — *"could two experienced engineers independently implement this and produce materially different behavior? If yes, that is a specification defect"* — **the answer is yes for SD-1 through SD-5.** Rubber-stamping past a demonstrated stale-fact hole would betray the purpose of this gate.

> # **NOT READY**
>
> ### **for executable specification engineering — pending a bounded, specification-layer-only clarification pass resolving SD-1 through SD-12 (§12).**
>
> **Evidence:** SD-3 permits a checkpoint that pins too few entity versions and therefore acts on a stale material fact (§5, §7); SD-1 permits a `decision_ref` that references nothing, weakening I11 closure to a non-null-string check (§2, §7); SD-2 gives one durable row two conflicting `state` enums (§4); SD-4 leaves a named verification mode unspecified (§4); SD-5 uses three overlapping "about" references without defined boundaries (§2).
>
> ### **This is a punch-list, not a redesign. NONE of the twelve requires a higher-level amendment; all are fixable in ~6 files with no new primitive. Once resolved, the layer will be READY — and this review should be re-run mechanically against the diff to confirm the five material findings are closed and no new divergence was introduced.**

**Recommended next step:** a single clarification pass (SD-1…SD-12), then a short re-review confirming closure — **not** a return to the architecture, which remains sound and frozen.
