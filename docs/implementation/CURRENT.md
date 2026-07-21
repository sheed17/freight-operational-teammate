# CURRENT — The Repository Status Authority

> ### **This is the ONLY short-form current-status authority in this repository.**
> Every phase review, blocker review and planning document is **historical evidence**. Do not
> reconstruct status by reading them — that is the failure this file exists to prevent.
>
> **Last updated:** U-REBASELINE-1A founder rebaseline adjudication (both gates closed; P3 is READY).

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
content_commit: d96e7455c47f6eefaf7e666207ba26ef74fc29b2
content_tree: c8e9008acba2319206c59e979271922921d830bb
suite_passed: 1274
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

**U-REBASELINE-1A — FOUNDER REBASELINE ADJUDICATION** — complete. Review:
[`u-rebaseline-1a-founder-adjudication-review.md`](u-rebaseline-1a-founder-adjudication-review.md).

### **BOTH GATES ARE CLOSED. The next approved unit is `P3`.**
The **INDEPENDENT** U-REBASELINE-REVIEW-1 (fresh testing-account clone at `fb5fcd93`, preserved at
[`u-rebaseline-review-1-independent-report.md`](u-rebaseline-review-1-independent-report.md))
returned **five PASS verdicts and zero CRITICAL findings**. Its four HIGH findings (stale L6→W8
residue, the CK/MF step-contract shortfall and its false-green self-review row, coverage-guard
porosity, the broken V-reference namespace) and the accepted MEDIUM set were **all resolved by
U-REBASELINE-1A before RB-24 was awarded**. **U-REBASELINE-1 is COMPLETE (RB-01..RB-24 all PASS);
`P3` is the one and only READY unit**, with a weighted 14-criterion acceptance contract instantiated
and entirely PENDING.

### **P3 is READY — and still NOT IMPLEMENTED.** No checkpoint, witness or claim-CAS symbol exists
in `src/`; **R-07 stays OPEN — NOT CONTAINED** (it closes at P4, nowhere earlier); every phase from
P4 onward stays BLOCKED; every customer-specific validation blocker stands.

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

### **P3 — CHECKPOINT WITNESS, SEVEN-STEP ATOMIC CHECKPOINT, AND CLAIM CAS**

Unit `P3` in [`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml) — **the one and only
READY unit.** Both gates that stood in front of it are CLOSED on independent evidence:
`U-HANDOFF-1` (adjudicated by U-HANDOFF-1D from U-HANDOFF-2B) and **`U-REBASELINE-1` COMPLETE —
RB-01..RB-24 ALL PASS**, adjudicated by U-REBASELINE-1A from the **INDEPENDENT**
U-REBASELINE-REVIEW-1 (preserved:
[`u-rebaseline-review-1-independent-report.md`](u-rebaseline-review-1-independent-report.md);
adjudication: [`u-rebaseline-1a-founder-adjudication-review.md`](u-rebaseline-1a-founder-adjudication-review.md)).

**P3's acceptance contract is the weighted 14-criterion `acceptance_criteria` block on the P3 unit
in the registry** — weights sum to exactly 100, **every criterion PENDING**. Phase completion is
computed from it ([`PROGRESS-PROTOCOL.md`](PROGRESS-PROTOCOL.md) §3: only `PASS` contributes; code
written is not completion).

P3 makes the two-key rule real: the seven checks in ONE atomic transaction, an unconstructable
`CheckpointPassed` witness, grant mint + claim CAS, and brake admission read inside the checkpoint
transaction. **A grant becomes necessary but not sufficient.**

> ### **P3 is READY — and NOT IMPLEMENTED.** READY is permission to begin, not evidence of
> beginning. No checkpoint, witness or claim-CAS symbol exists in `src/`, pinned as
> `absent_symbols` in [`IMPLEMENTATION-SURFACE.yaml`](IMPLEMENTATION-SURFACE.yaml) and enforced by
> a live test-of-absence. **P3 ships dark** — capability flag OFF; deploy and enable are separate
> decisions.

**P3's prohibited scope stands unchanged:** adapter containment is P4, events are P5, freight
workflows are P6–P9. **Reaching P3 does not close R-07.**

## ⛔ What must NOT begin yet

| Not yet | Why |
|---|---|
| ### **Implementation Phase 4** (adapter containment) | Requires `P3` COMPLETE. This is the phase that closes R-07 — and a gate with nothing behind it is theatre |
| Events / outbox / replay isolation | P5 content; also blocked on the G2 transition/event adjudication |
| Closing R-07 | ### **Only completing P4 closes it.** Not P3, not a plan, not operator discipline |
| Freight workflow implementation | Requires P6–P9 foundations |
| Deleting legacy production code | Requires the deletion conditions in [`LEGACY-DISPOSITION.md`](LEGACY-DISPOSITION.md) |
| Promoting Delivered Load Closure to validated | It is a **`HYPOTHESIS`** — requires recorded design-partner evidence ([`DESIGN-PARTNER-EVIDENCE-PROGRAM.md`](../product/DESIGN-PARTNER-EVIDENCE-PROGRAM.md)) |

## Blocked future units

**Every implementation phase from `P4` onward is BLOCKED behind `P3`.** See the registry for the
full dependency graph; the transitive safety wall (P3 an ancestor of every P≥4, P4 of every P≥5) is
guarded.

<details>
<summary><b>⛔ HISTORICAL — PRE-ADJUDICATION PROGRAM (superseded 2026-07-20; NOT current instruction)</b></summary>

**Everything in this block is superseded and must not be followed.** Before the U-REBASELINE-1A
adjudication, this file named **U-REBASELINE-1** as the next approved work program, described its
contract as **RB-01..RB-23 PASS with RB-24 PENDING**, said the unit was **awaiting an independent
product/production rebaseline review**, and listed **P3 as BLOCKED** behind it. The independent
review has since been run, delivered, preserved and adjudicated: **U-REBASELINE-1 is COMPLETE, all
24 criteria PASS, and P3 is the sole READY unit.** Retained only so the transition is auditable.

</details>

## Documents required before proceeding

A session picking up `P3` must have read, in order:
[`CLAUDE.md`](../../CLAUDE.md) → [`PRODUCT.md`](../../PRODUCT.md) →
[`ARCHITECTURE.md`](../../ARCHITECTURE.md) → [`CANONICAL-DOCUMENTS.md`](../CANONICAL-DOCUMENTS.md) →
this file → [`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml) →
[`TOOL-ACCESS-POLICY.md`](TOOL-ACCESS-POLICY.md) → the **P3 `acceptance_criteria`** block in
[`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml) →
[`PROGRESS-PROTOCOL.md`](PROGRESS-PROTOCOL.md).
