# Wave 4.5 — Specification Clarification Pass & Review

**Scope:** resolve SD-1 … SD-12 from `specification-constitution-review.md`. **Clarification only** — no redesign, no new primitive, no higher-level amendment.
**Method:** targeted edits to the frozen entity specs, each stating the deterministic rule and citing the frozen source that already implied it; followed by a mechanical hostile re-review.
**Date:** 2026-07-13

---

## PART 1 — THE TWELVE CLARIFICATIONS

For each: **affected spec · exact ambiguity · deterministic rule · why already implied · no-new-concept check.**

### SD-1 — `decision_ref` referent *(safety-adjacent)*
- **Affected:** `00-conventions.md` **K-1** (governs all 9 files that use `decision_ref`).
- **Ambiguity:** a required FK with no defined referent — satisfiable by a free-text string.
- **Rule:** `decision_ref` MUST resolve to **either** an `audit_events` row of a human-decision type (authenticated human actor) **or** a `rule_id` of an `ACTIVE` Rule; discriminated by `decision_ref_kind ∈ {AUDIT_EVENT, RULE}`; a value that resolves to neither makes the transition illegal.
- **Implied by:** ADR-008 (*"a human decision id or a deterministic rule id"*); Audit Events already record human decisions (`17`); Rules already carry `rule_id` (`15`).
- **No new concept:** names the two **existing** referents; the discriminator column is representation, not a new entity.

### SD-2 — the `effect_grants` unified `state` column *(safety-adjacent)*
- **Affected:** `03-external-effect.md` p12 · `04-effect-grant.md` p12, p17.
- **Ambiguity:** one row, two files, two different `state` enums (7 vs 4); `REVOKED` in neither the other enum nor spec §12.3.
- **Rule:** ONE `state` column, EIGHT values `{GRANTED, CLAIMED, ATTEMPTED, VERIFIED, FAILED, EXPIRED_UNCLAIMED, REVOKED, UNKNOWN_OUTCOME}`. Capability aspect writes `{GRANTED, CLAIMED, EXPIRED_UNCLAIMED, REVOKED}`; outcome aspect continues from `CLAIMED` into `{ATTEMPTED, VERIFIED, FAILED, UNKNOWN_OUTCOME}`; **`CLAIMED` is the join.** Commit-once `WHERE state='CLAIMED'` unchanged.
- **Implied by:** ADR-004 §3.2 (`GRANTED→CLAIMED | EXPIRED | REVOKED`, `REVOKED` distinct) ∪ spec §12.3 (the outcome states). **The hierarchy makes ADR-004 authoritative over spec §12.3's narrative fold of revoked→EXPIRED_UNCLAIMED** — so `REVOKED` is a distinct terminal, aligning *to* the ADR.
- **No new concept:** all eight values are canonical; none invented.

### SD-3 — `entity_versions` selection rule *(SAFETY — the most serious)*
- **Affected:** `05-checkpoint-witness.md` p13 (+ test in p44).
- **Ambiguity:** "every entity whose state made this action correct" left the *set* to implementer judgment; under-pinning permits a stale-fact write that passes the checkpoint.
- **Rule:** `entity_versions` MUST contain the version of every entity that (1) is referenced by any material-fact field, (2) is the target resource's projection, or (3) backs a `GATE_PRECONDITION` evaluated in step 6. Exact set, no exceptions.
- **Implied by:** ADR-009 §5 (*"the versions of every entity whose state made this action correct"*); the fingerprint + target already enumerate those entities.
- **No new concept:** a mechanical membership test over already-required inputs.

### SD-4 — `RECEIPT_VERIFIABLE` semantics
- **Affected:** `03-external-effect.md` p12, p22, p44.
- **Ambiguity:** a frozen verification mode absent from the entity layer; no outcome mapping.
- **Rule:** a receipt is an Observation; a receipt that **uniquely identifies this effect** ⇒ `VERIFIED_SUCCESS`; a receipt confirming only **transmission** (SMTP 250, "queued") ⇒ `ATTEMPTED` + Expectation/`VERIFICATION_DEFERRED`, never "delivered", **never `VERIFIED_FAILURE`**. `UNVERIFIABLE` ⇒ may not be autonomous; field stays projected-`unknown`.
- **Implied by:** spec §18/§26.1 declare the three modes and the 8 outcomes; M-72 (local persistence ≠ verification); "never say delivered."
- **No new concept:** maps a frozen mode onto frozen states/outcomes.

### SD-5 — `entity_ref` / `subject_ref` / `target_resource_id`
- **Affected:** `00-conventions.md` **K-2** (+ a naming note reconciling Observation's `bound_entity_ref`).
- **Ambiguity:** three overlapping "about" references, boundaries undefined.
- **Rule:** three distinct references — `target_resource_id` = external-system handle; `entity_ref` (`bound_entity_ref` on Observation) = canonical projection row; `subject_ref` = artifact/observation. A binding carries **both** `subject_ref` (one end) and `entity_ref` (the other). Joins go through provenance, never string equality.
- **Implied by:** spec §6.1's eight kinds of thing — these are the identifiers of three of them.
- **No new concept.**

### SD-6 — `match_method` → `provenance_class`
- **Affected:** `09-identity-binding-claim.md` p13.
- **Rule:** `provenance_class = f(match_method)`, computed once at creation, immutable, CHECK-enforced; a change of belief is a NEW claim, never an edit.
- **Implied by:** ADR-002 §2.3 provenance semantics; R-P1/R-P2.
- **No new concept.**

### SD-7 — multi-step `CheckpointFailed`
- **Affected:** `05-checkpoint-witness.md` p30 (+ test p44).
- **Rule:** fixed canonical order (1 approval → 7 brake, per spec §19.2); **short-circuit on the first failure**; report that step only. Atomicity unaffected (still no witness).
- **Implied by:** spec §19.2 already fixes the seven-step order; this fixes only "which is reported."
- **No new concept.**

### SD-8 — replay side-effects
- **Affected:** `00-conventions.md` **K-3** (extends `[C-5]`).
- **Rule:** replay is read-only into an isolated sandbox — zero real-consumer events, zero real projections (only sandbox projections for the divergence comparison), zero grants, zero effects.
- **Implied by:** spec §25 (*"replay runs against a projection sandbox and cannot construct a witness"*).
- **No new concept.**

### SD-9 — `exposure` vs "memory never stores money"
- **Affected:** `00-conventions.md` **K-4**.
- **Rule:** the money-in-memory prohibition is scoped to the **knowledge base**; `exposure` on operational records is permitted **iff** sourced from a live/verified read (carries its `observation_id`), never a memory recall.
- **Implied by:** spec §22 places the rule under Knowledge; §21 requires runtime-read amounts.
- **No new concept.**

### SD-10 — Work Item dedup across trigger sources
- **Affected:** `01-work-item.md` p17.
- **Rule:** Work Items are **not** deduplicated across triggers (two "we should" signals = two items); **double-action is prevented at the effect layer** (shared `commit_key` + Layer-1 absorption ⇒ one card/approval/effect); a redundant item closes on the same `PipelineClosed`/`decision_ref`.
- **Implied by:** spec §13 (Work Item = intent, Pipeline = effect) + §16.1/M-29 (commit-key exclusion).
- **No new concept, no dedup mechanism invented.**

### SD-11 — `occurrence_key` extensibility
- **Affected:** `00-conventions.md` **K-5**.
- **Rule:** each action class is a registered descriptor declaring `gate_decision`, `verification_mode`, `money_direction`, and `occurrence_key_rule`; derivation is a property of the class, never a central switch; adding a class is purely additive.
- **Implied by:** spec §19.7 (per-class `occurrence_key`), §20.1 (per-class gate), §18/§26.1 (per-operation mode).
- **No new concept:** names where four already-required per-class properties live.

### SD-12 — GLOBAL brake representation
- **Affected:** `16-brake.md` p7.
- **Rule:** the `GLOBAL` brake is ONE platform-level row; checkpoint step 7 / the claim CAS consult the platform row AND the tenant's rows (either `ACTIVE` denies); engagement is a single atomic write; witnesses/grants bind both `global_brake_version` and `tenant_brake_version`, both re-validated at claim.
- **Implied by:** spec §21.6 lists `GLOBAL` as a scope and requires a tenant-isolation breach to engage it.
- **No new concept:** states row cardinality + version composition for a frozen scope value.

### HA-1 (bonus) — single-store dependency
- **Affected:** `00-conventions.md` **C-11**. States that every one-transaction guarantee depends on the single store (A1) and a future process-split must preserve it via the shared ledger (ADR-004 §4.4). A documented assumption, not a new decision.

---

## PART 2 — MECHANICAL HOSTILE RE-REVIEW

*"Do not search for new architecture. Verify only closure, no new ambiguity, no drift, no ADR contradiction, no remaining implementation choice where determinism is required."*

| Check | Method | Result |
|---|---|---|
| **SD-1 … SD-12 closed** | grep each rule + its test | ✅ **all 12 present** — K-1 (decision_ref), 8-state union in **both** `03`+`04`, `entity_versions` rule + 2 test refs, `RECEIPT_VERIFIABLE` in `03`+`00`, K-2/K-3/K-4/K-5/C-11, SD-6/7/10/12 in their files |
| **No new UPPER_SNAKE token** *(terminology drift)* | grep all `*.md`, subtract the canonical registry | ✅ **empty** — zero new state/enum tokens introduced |
| **No new architectural concept** | manual: every clarification cites a frozen source; the only new identifiers (`decision_ref_kind`, `occurrence_key_rule`, `global_brake_version`) are **representations of already-required data**, not new entities/states/effects | ✅ **none** |
| **No ADR contradiction** | the one risk was SD-2's `REVOKED`: resolved by **aligning to ADR-004 §3.2** (which the hierarchy makes authoritative over spec §12.3's narrative fold) | ✅ **aligns to, does not contradict** |
| **Structure intact** | 45/45 points every entity; `00` has 7 addendum markers | ✅ |
| **Naming reconciled** | Observation's `bound_entity_ref` explicitly tied to `entity_ref` in K-2 | ✅ **no residual drift** |
| **No remaining implementer choice where determinism is required** | the five material gaps (SD-1/2/3/4/5) each now state an exact rule, constraint, and (where behavioral) a test | ✅ |

### New tests added by this pass *(acceptance surface for the clarified behavior)*
`test_decision_ref_must_resolve_to_a_human_decision_event_or_active_rule` (SD-1) · `test_entity_versions_pins_every_material_fact_entity_plus_target` (SD-3) · `test_checkpoint_reports_the_first_failing_step_in_canonical_order` (SD-7) · `test_receipt_confirming_only_transmission_does_not_verify` + `test_receipt_can_never_yield_verified_failure` + `test_unverifiable_operation_field_stays_projected_unknown` (SD-4).

### Did the pass introduce a new divergence point?
**Checked and no.** The only judgment the clarifications *could* have re-opened is SD-2's `REVOKED` placement; it is pinned to a single 8-value domain aligned to ADR-004, with commit-once explicitly unchanged. No clarification defers a behavioral decision to the implementer.

---

## VERDICT

> # **READY FOR EXECUTABLE SPECIFICATION ENGINEERING**

**Evidence:**
1. **All twelve specification defects (SD-1 … SD-12) are closed** with deterministic rules, each traced to a frozen source that already implied it (Part 1; grep-confirmed in Part 2).
2. **The two safety-adjacent gaps are eliminated:** `entity_versions` now has an exact membership rule with a test (a checkpoint can no longer pass on a stale unpinned material fact — SD-3); `decision_ref` must resolve to a real human-decision event or active rule (closure can no longer be satisfied by a bare string — SD-1).
3. **Zero terminology drift, zero new primitives, zero new states/events/enums** — the only new identifiers are representations of already-required data.
4. **No specification contradicts a frozen ADR** — the sole tension (SD-2 `REVOKED`) was resolved by aligning to ADR-004 §3.2 per the document hierarchy.
5. **No higher-level document was amended; no specification was redesigned.** Every change was a clarification within the frozen entity layer.
6. **No implementer choice remains where deterministic behavior is required** — the five material findings each carry an exact rule, a constraint, and (where behavioral) a merge-gating test.

**Executable specification engineering — the declarative transition tables, guards, and event contracts for the 13 canonical machines — may now begin,** carrying forward the SD-2 one-row/eight-state resolution and the SD-3 `entity_versions` membership rule as hard acceptance criteria.
