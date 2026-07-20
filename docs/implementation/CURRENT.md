# CURRENT — The Repository Status Authority

> ### **This is the ONLY short-form current-status authority in this repository.**
> Every phase review, blocker review and planning document is **historical evidence**. Do not
> reconstruct status by reading them — that is the failure this file exists to prevent.
>
> **Last updated:** U-REBASELINE-1 product, integration and production rebaseline (executed;
> awaiting independent review).

---

## Position

**The block below is machine-maintained and machine-verified.** It is written by
`scripts/update_current_status.py` from `git rev-parse` and a real suite run — never by hand — and
[`eval/tests/test_status_reality.py`](../../eval/tests/test_status_reality.py) fails the build when
it disagrees with the checked-out commit. The zero-context rehearsal proved a hand-maintained
version of this block goes stale within one commit and nothing notices.

```yaml
# status-block: maintained by scripts/finalize_status.py - do not edit by hand
recorded_authoring_branch: recovery/u2-6bc-atomic-cutover   # advisory; not verified across bundles/clones
content_commit: cd7729b0af3834daae5f81740ad7c139306fde94
content_tree: 704dd63842928a6780bc4aa6f369121043e0a736
suite_passed: 1265
suite_failed: 0
suite_skipped: 1
```

> ### **The two-commit convention (why this block can be truthful):** a commit cannot contain its
> own hash, so a self-referential "current commit" field is impossible and claiming one would be a
> lie. Instead: every substantive change lands in a **content commit**; the finalization script
> then records that commit here and the record lands in **exactly one status-metadata commit
> directly on top**, touching only the status files. `HEAD` is therefore either the content
> baseline itself or that one metadata commit — and the guard verifies exactly this relationship,
> including that the metadata commit changed nothing else.

| | |
|---|---|
| **The one skip** | Conditional and self-describing: *"no red-by-design cases remain: AC-SAFE-012/013 went green at Phase 1"* |
| **Working tree** | clean |
| **Suite counts elsewhere** | ### **Volatile commit/tree/suite figures live ONLY in the block above.** Other files link here instead of copying numbers — the rehearsal found the old figure duplicated into five files, all stale. |

## Completed phases

| Phase | Status | Evidence |
|---|---|---|
| **P0** — baseline & anti-false-green infrastructure | ### **COMPLETE** | [`phase-0-implementation-review.md`](phase-0-implementation-review.md) · `d33f251` |
| **P1** — correct effect identity (Commit Key) | ### **COMPLETE** | [`phase-1-implementation-review.md`](phase-1-implementation-review.md) · `149c02a`, `da07936` |
| **P2** — tenant-safe persistence | ### **COMPLETE** | [`u2-6bc-blocker-6-final-phase-2-review.md`](u2-6bc-blocker-6-final-phase-2-review.md) · `7d72498` |
| **P3** — checkpoint, witness, claim CAS | ### **NOT STARTED** | — |
| **P4–P14** | **NOT STARTED** | [`PHASE-OUTPUTS.md`](PHASE-OUTPUTS.md) |

## Completed acceptance gates

| Case | Status |
|---|---|
| **AC-SAFE-012** | ### **GREEN** |
| **AC-SAFE-013** | ### **GREEN** |
| **AC-SEC-001** | ### **GREEN at the Phase-2 surfaces** (records, grants, api). Seven surfaces deferred by phase: events (P5), witnesses (P3), leases (P3), mappings (P9), credentials (P4), cache keys (P4), adapter calls (P4). |
| **G0** | passed |
| **G1–G10** | not reached |

## Exact counts *(recomputed mechanically, not transcribed)*

| Quantity | Count |
|---|---|
| **Canonical table partition** *(exact, disjoint, guarded — 7 + 1 + 3 = 11)* | |
| — Phase-2 **migrated** tenant-owned tables | **7** — `workflow_runs`, `audit_events`, `security_events`, `operation_action_claims`, `delivery_action_claims`, `effect_grants`, `operation_token_amounts` |
| — **Already tenant-first before P2** (the eighth tenant-first table, migrated by nobody) | **1** — `autonomous_run_counters` |
| — Tenant-**exempt** bookkeeping tables | **3** — `schema_migrations`, `migration_quarantine`, `owner_assertions` |
| — Canonical tables **total** | **11** — exactly the union of the three sets above; "7 + 3" alone was the rehearsal's M-4 finding, hiding the eighth |
| `WorkflowStore` methods, tenant-scoped + readiness-gated | **22 / 22** |
| `WorkflowStore` construction sites, all with an explicit tenant | **154** *(plus 8 refusal probes, exempted structurally)* |
| Guard files / guard tests | **25 / 367** |
| Canonical transitions | **134** |
| Canonical emitted events | **98** |
| Canonical loops | **11** |
| Domain entities | **40** · adapters **18** · safety invariants **28** |

## ⛔ Open risks and findings — ALL STILL OPEN

| ID | Finding | Status | Closes at |
|---|---|---|---|
| **R-07** | Ungated live-write paths | ### **OPEN — NOT CONTAINED** | **P4** |
| — | **6 production-reachable live-write paths** — EP-1, EP-3, EP-6, EP-7, EP-9, EP-10 | OPEN | P4 |
| — | **31 direct adapter-import edges** across 18 importer modules | OPEN | P4 |
| — | **Transition/event completeness: 13 of 134 name no event outright** (5 bare · 3 documented non-producing · 3 unnamed-ILLEGAL · 2 delegating; exact members in [`TRANSITION-EVENT-AUDIT.yaml`](TRANSITION-EVENT-AUDIT.yaml)) — ### **COUNT NEEDS ADJUDICATION**: the specs do not define which classes violate AC-EVT-003, and the retired "24" was never mechanically computed | OPEN | **G2, before P5** |
| — | Hardcoded knowledge-base `tenant="default"` — `ops_control.py` ×5, `action_callback.py::_learn_correction` (the `KnowledgeBase(...).learn` call) | OPEN | the phase that makes the KB tenant-safe |
| — | Checkpoint Witness + seven-step checkpoint + claim CAS unimplemented | OPEN | **P3** |
| — | Adapter containment unimplemented | OPEN | **P4** |
| — | **No firsthand design-partner observation recorded by any agent** | OPEN | [`design-partner-observations.md`](../product/design-partner-observations.md) |
| — | Repository legacy reduction unfinished | OPEN | [`LEGACY-DISPOSITION.md`](LEGACY-DISPOSITION.md) |

> ### **The only mitigation for R-07 is the operator's one-writer-at-a-time discipline.**
> ### **That is discipline, not a mechanism, and it may NEVER be recorded as containment.**
>
> ### **Phase 2 made tenant ownership real at persistence boundaries.**
> ### **Phase 2 did NOT make external effects safe.**

## Current documentation milestone

**U-REBASELINE-1 — PRODUCT, INTEGRATION AND PRODUCTION REBASELINE** — executed (founder-authorized),
awaiting the independent product/production rebaseline review.
Review: [`u-rebaseline-1-product-production-review.md`](u-rebaseline-1-product-production-review.md).

### **The founder rebaseline is written.** The stable identity is now *"the AI-native operating
platform and system of action for small and medium freight and logistics companies"* (ADR-012);
Neyma may become authoritative for individual workflows through the customer-authorized migration
model (ADR-013); it may securely possess customer-authorized credentials while minimizing raw
password handling (ADR-014); communications are a core subsystem (ADR-015); production runs on
PostgreSQL/workers/object-storage with a thin web control plane (ADR-016/017); **the TMS is one
node in the customer's operational graph, not the center — the canonical domain model is
TMS-schema-independent, each tenant has an Operational System Map, and a write into one node is
never workflow completion (ADR-018)**; the wedge is **Delivered Load Closure** (a `HYPOTHESIS`).
**RB-01..RB-23 PASS; RB-24 (fresh-reviewer legibility) stays PENDING for the independent review;
U-REBASELINE-1 is NOT COMPLETE.** No production runtime code changed; R-07 stays OPEN — NOT
CONTAINED; P3 stays BLOCKED and unimplemented.

### Handoff-gate history (U-HANDOFF-1, closed by U-HANDOFF-1D)
Adjudication: [`u-handoff-1d-final-adjudication-review.md`](u-handoff-1d-final-adjudication-review.md).

### **The handoff gate is CLOSED.** The second hostile review — **U-HANDOFF-2B**, independent and
repository-only — defended its attack battery against the U-HANDOFF-1C-corrected controls, and
U-HANDOFF-1D adjudicated all 13 checklist criteria **PASS** from that independent evidence
(preserved verbatim, with its transport truncation disclosed, in
[`u-handoff-2b-hostile-review-report.md`](u-handoff-2b-hostile-review-report.md)). **U-HANDOFF-1
is COMPLETE.**

### The full rehearsal record — how the gate closed
1. A **non-independent** rehearsal (the control-document author) returned **NOT READY** — the
   status authority was stale by one commit, unguarded. Corrected by **U-HANDOFF-1A**.
2. The **first INDEPENDENT rehearsal** (fresh session, repository-only) returned **NOT READY** —
   **11 of 13 criteria PASS; HANDOFF-03 and HANDOFF-12 FAIL.** Its decisive finding: the recorded
   green was **not clean-clone reproducible** (46 tests read a gitignored developer-local
   database; an undeclared dependency; an unenforced Python floor; a status guard that verified
   test COUNTS, not test RESULTS) — plus a contradictory `registry.md`, an unclassified root
   roadmap, eight graph inconsistencies, and figures (the since-retired "24 of 134", the since-drifted `:1639`, the unadjudicated "six") that no
   executable source computed. All corrected and guarded by **U-HANDOFF-1B**; the suite is now
   hermetic, the status record is artifact-backed, and the clean-clone gate
   (`scripts/clean_clone_gate.py`) is the reproducibility oracle.
3. The **second independent rehearsal** PASSED **13/13** — comprehension is proven. The
   subsequent **hostile formal handoff-readiness review** then attacked the CONTROLS and returned
   **NOT READY**: fabricated artifacts were accepted, pytest configuration could silently remove
   tests, skip detection covered a quarter of the suite, a live "24" contradiction survived in
   the registry, P6+ could bypass the safety wall, and guard populations were hand-enumerated.
   All corrected and mutation-proven (44/44) by **U-HANDOFF-1C**: status is now finalized only by
   [`scripts/finalize_status.py`](../../scripts/finalize_status.py), which EXECUTES the suite,
   the clean-clone gate and the acceptance gates itself.
4. **U-HANDOFF-2B — the SECOND HOSTILE review** (independent, repository-only, branch
   `hostile-review-fe7843d`) attacked the corrected controls: bootstrap, finalizer execution,
   clean-clone reproduction, node-manifest identity, skip enforcement, dynamic discovery,
   authority resolution, the safety graph, product identity and the tool-authority boundary,
   plus a false-confidence mutation battery — **all received attack rows DEFENDED, zero
   critical or high findings in the received sections**. Its verdict — READY FOR FINAL ZIP
   INSPECTION — is founder-attested; the received evidence body plus the adjudicating session's
   own re-execution of the finalizer, suite and clean-clone gate closed the gate. Adjudication:
   [`u-handoff-1d-final-adjudication-review.md`](u-handoff-1d-final-adjudication-review.md).

## ✅ The exact next approved work program

### **U-REBASELINE-1 — PRODUCT, INTEGRATION AND PRODUCTION REBASELINE** *(founder-authorized — executed, awaiting independent review)*

Unit `U-REBASELINE-1` in [`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml) — the
**single READY unit**. The executable acceptance contract is
[`U-REBASELINE-1-ACCEPTANCE.yaml`](U-REBASELINE-1-ACCEPTANCE.yaml) — **RB-01..RB-23 PASS with
produced-artifact evidence; RB-24 PENDING** (only the independent review can certify fresh-reviewer
legibility). The rebaseline **content is written**; the unit stays READY (not COMPLETE) until the
independent product/production rebaseline review passes and the founder advances the program.

The rebaseline re-evaluated and corrected: stable product identity (ADR-012); the TMS
relationship and workflow-authority migration (ADR-013); credential and machine-identity models
(ADR-014); communications as a core subsystem (ADR-015); production hosting and deployment
(ADR-016); tenant and integration lifecycle plus the web control plane (ADR-017); the initial
commercial workflow hypothesis (Delivered Load Closure — PRODUCT.md §15); the revised P3–P14
program; and the design-partner evidence requirements
([`DESIGN-PARTNER-EVIDENCE-PROGRAM.md`](../product/DESIGN-PARTNER-EVIDENCE-PROGRAM.md)).

**It was a documentation, architecture, specification and control unit ONLY. It implemented no
runtime product behavior, changed no freight workflows, added no integrations, and left R-07
OPEN — NOT CONTAINED and P3 BLOCKED throughout.**

**Next: an INDEPENDENT product/production rebaseline review** (fresh session, fresh checkout).
Only after it passes does the founder advance the program toward P3.

## ⛔ What must NOT begin yet

| Not yet | Why |
|---|---|
| ### **Implementation Phase 3** | Requires `U-REBASELINE-1` COMPLETE, an independent product/production rebaseline review, **and** an independent repository inspection |
| ### **Executing U-REBASELINE-1's product decisions ahead of the unit** | Registration is not execution; the RB-01..RB-24 contract is entirely PENDING |
| Checkpoint Witness / seven-step checkpoint / claim CAS | P3 content |
| Adapter containment | P4 content |
| Closing R-07 | Only reaching P4 closes it |
| Freight workflow implementation | Requires P6–P9 foundations |
| Deleting legacy production code | Requires the deletion conditions in [`LEGACY-DISPOSITION.md`](LEGACY-DISPOSITION.md) |
| Promoting the W6→W8 slice to validated | It is **provisional** and marked **NEEDS DESIGN-PARTNER VALIDATION**; requires recorded evidence |

## Blocked future units

Every implementation phase from `P3` onward is **BLOCKED** behind `U-REBASELINE-1`. See the
registry for the full dependency graph.

## Documents required before proceeding

A session picking up `U-REBASELINE-1` must have read, in order:
[`CLAUDE.md`](../../CLAUDE.md) → [`PRODUCT.md`](../../PRODUCT.md) →
[`ARCHITECTURE.md`](../../ARCHITECTURE.md) → [`CANONICAL-DOCUMENTS.md`](../CANONICAL-DOCUMENTS.md) →
this file → [`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml) →
[`TOOL-ACCESS-POLICY.md`](TOOL-ACCESS-POLICY.md) →
[`U-REBASELINE-1-ACCEPTANCE.yaml`](U-REBASELINE-1-ACCEPTANCE.yaml).
