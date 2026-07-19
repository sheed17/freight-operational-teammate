# CURRENT — The Repository Status Authority

> ### **This is the ONLY short-form current-status authority in this repository.**
> Every phase review, blocker review and planning document is **historical evidence**. Do not
> reconstruct status by reading them — that is the failure this file exists to prevent.
>
> **Last updated:** U-HANDOFF-1A bounded control-system correction.

---

## Position

**The block below is machine-maintained and machine-verified.** It is written by
`scripts/update_current_status.py` from `git rev-parse` and a real suite run — never by hand — and
[`eval/tests/test_status_reality.py`](../../eval/tests/test_status_reality.py) fails the build when
it disagrees with the checked-out commit. The zero-context rehearsal proved a hand-maintained
version of this block goes stale within one commit and nothing notices.

```yaml
# status-block: maintained by scripts/update_current_status.py - do not edit by hand
branch: recovery/u2-6bc-atomic-cutover
content_commit: fde6c9531fa22761799f81e55d6022640697f85c
content_tree: 1f046f3925fde9e57d8c7de470a4f9f30a4fc4a2
suite_passed: 1179
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

**U-HANDOFF-1B — CLEAN-CLONE REPRODUCIBILITY AND AUTHORITY CORRECTION** — complete.
Review: [`u-handoff-1b-clean-clone-correction-review.md`](u-handoff-1b-clean-clone-correction-review.md).

### The rehearsal record so far — two rehearsals, both NOT READY, both fully adjudicated
1. A **non-independent** rehearsal (the control-document author) returned **NOT READY** — the
   status authority was stale by one commit, unguarded. Corrected by **U-HANDOFF-1A**.
2. The **first INDEPENDENT rehearsal** (fresh session, repository-only) returned **NOT READY** —
   **11 of 13 criteria PASS; HANDOFF-03 and HANDOFF-12 FAIL.** Its decisive finding: the recorded
   green was **not clean-clone reproducible** (46 tests read a gitignored developer-local
   database; an undeclared dependency; an unenforced Python floor; a status guard that verified
   test COUNTS, not test RESULTS) — plus a contradictory `registry.md`, an unclassified root
   roadmap, eight graph inconsistencies, and figures ("24 of 134", `:1639`, "six") that no
   executable source computed. All corrected and guarded by **U-HANDOFF-1B**; the suite is now
   hermetic, the status record is artifact-backed, and the clean-clone gate
   (`scripts/clean_clone_gate.py`) is the reproducibility oracle.
### **U-HANDOFF-1 itself remains OPEN: a SECOND independent rehearsal against the corrected
repository has not been run**, and only it can close the gate.

## ✅ The exact next approved work program

### **ZERO-CONTEXT CLI HANDOFF REHEARSAL AND HOSTILE READINESS REVIEW — run INDEPENDENTLY**

Unit `U-HANDOFF-1` in [`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml).
The executable acceptance checklist is
[`U-HANDOFF-1-ACCEPTANCE.yaml`](U-HANDOFF-1-ACCEPTANCE.yaml) — **13 criteria, all currently
PENDING**; the independent rehearsal produces a structured result against it.

It tests whether a clean-session agent, given only this repository, can:

1. identify the product correctly (and **reject** the invoice-processor interpretation)
2. identify the current implementation state correctly — **including this file's commit/tree/suite block**
3. identify legacy code correctly
4. identify the next work unit correctly
5. explain that unit's expected outputs correctly
6. **refuse to invent missing product rules**
7. follow acceptance and commit discipline
8. describe the broad-tool-access posture and **distinguish tool access from action authority**
   ([`TOOL-ACCESS-POLICY.md`](TOOL-ACCESS-POLICY.md))

**This is a rehearsal and review unit. It writes no runtime code.**

## ⛔ What must NOT begin yet

| Not yet | Why |
|---|---|
| ### **Implementation Phase 3** | Requires `U-HANDOFF-1` to pass **and** an independent repository inspection |
| Checkpoint Witness / seven-step checkpoint / claim CAS | P3 content |
| Adapter containment | P4 content |
| Closing R-07 | Only reaching P4 closes it |
| Freight workflow implementation | Requires P6–P9 foundations |
| Deleting legacy production code | Requires the deletion conditions in [`LEGACY-DISPOSITION.md`](LEGACY-DISPOSITION.md) |
| Promoting the W6→W8 slice to validated | It is **provisional** and marked **NEEDS DESIGN-PARTNER VALIDATION**; requires recorded evidence |
| The final formal CLI bootstrap prompt | Requires `U-HANDOFF-1` |

## Blocked future units

Every unit from `U3.1` onward is **BLOCKED** on `U-HANDOFF-1`. See the registry for the full
dependency graph.

## Documents required before proceeding

A session picking up `U-HANDOFF-1` must have read, in order:
[`CLAUDE.md`](../../CLAUDE.md) → [`PRODUCT.md`](../../PRODUCT.md) →
[`ARCHITECTURE.md`](../../ARCHITECTURE.md) → [`CANONICAL-DOCUMENTS.md`](../CANONICAL-DOCUMENTS.md) →
this file → [`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml) →
[`TOOL-ACCESS-POLICY.md`](TOOL-ACCESS-POLICY.md) →
[`U-HANDOFF-1-ACCEPTANCE.yaml`](U-HANDOFF-1-ACCEPTANCE.yaml).
