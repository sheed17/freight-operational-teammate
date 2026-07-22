# CURRENT — The Repository Status Authority

> ### **This is the ONLY short-form current-status authority in this repository.**
> Every phase review, blocker review and planning document is **historical evidence**. Do not
> reconstruct status by reading them — that is the failure this file exists to prevent.
>
> **Last updated:** P3 — Checkpoint Witness, seven-step atomic checkpoint and claim CAS
> **IMPLEMENTED AND IN PROGRESS, NOT COMPLETE.** P3 remains the sole READY unit; P4 stays BLOCKED.

---

## Position

**The block below is machine-maintained and machine-verified.** It is written by
`scripts/update_current_status.py` from `git rev-parse` and a real suite run — never by hand — and
[`eval/tests/test_status_reality.py`](../../eval/tests/test_status_reality.py) fails the build when
it disagrees with the checked-out commit. The zero-context rehearsal proved a hand-maintained
version of this block goes stale within one commit and nothing notices.

```yaml
# status-block: maintained by scripts/finalize_status.py - do not edit by hand
recorded_authoring_branch: p3/checkpoint-witness   # advisory; not verified across bundles/clones
content_commit: 0bf72b7fd1af15e56fe8cf0fee245c6413d1e34b
content_tree: cc53ff4ff642bf5535f94dfb5dbd0a281b118c53
suite_passed: 1528
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
| **P3** — checkpoint, witness, claim CAS | ### **IN PROGRESS — NOT COMPLETE** | [`phase-3-implementation-review.md`](phase-3-implementation-review.md) — the implementer's record · [`p3-independent-review-findings.md`](p3-independent-review-findings.md) — the INDEPENDENT review, which P3 **did not pass** (9 findings, 60/100, NOT READY) · [`p3-findings-remediation-review.md`](p3-findings-remediation-review.md) — the remediation. ### **A fresh independent review of the remediated tree is outstanding** |
| **P4–P14** | **NOT STARTED** | [`PHASE-OUTPUTS.md`](PHASE-OUTPUTS.md) |

## Completed acceptance gates

| Case | Status |
|---|---|
| **AC-SAFE-012** | ### **GREEN** |
| **AC-SAFE-013** | ### **GREEN** |
| **AC-SEC-001** | ### **GREEN at the Phase-2 AND Phase-3 surfaces** (records, grants, api + witnesses, leases). Five surfaces deferred by phase: events (P5), mappings (P9), credentials (P4), cache keys (P4), adapter calls (P4). |
| **AC-CKPT matrix** | ### **GREEN — all 105 merge-gating cases** (7 steps × 15 conditions on the universal oracle), [`test_phase3_checkpoint_matrix.py`](../../eval/tests/test_phase3_checkpoint_matrix.py) |
| **G0** | passed |
| **G1–G10** | not reached |

## Exact counts *(recomputed mechanically, not transcribed)*

| Quantity | Count |
|---|---|
| **Canonical table partition** *(exact, disjoint, guarded — 7 + 1 + 3 + 2 + 1 = 14)* | |
| — Phase-2 **migrated** tenant-owned tables | **7** — `workflow_runs`, `audit_events`, `security_events`, `operation_action_claims`, `delivery_action_claims`, `effect_grants`, `operation_token_amounts` |
| — **Already tenant-first before P2** (the eighth tenant-first table, migrated by nobody) | **1** — `autonomous_run_counters` |
| — Tenant-**exempt** bookkeeping tables | **3** — `schema_migrations`, `migration_quarantine`, `owner_assertions` |
| — **Phase-3** tenant-owned tables | **2** — `checkpoint_witnesses` (append-only by trigger), `brakes` |
| — **Phase-3** tenant-exempt table | **1** — `platform_brake` (the ONE global admission brake, SD-12 — by definition nobody's tenant data) |
| — Canonical tables **total** | **14** — exactly the union of the five sets above |
| `WorkflowStore` methods, tenant-scoped + readiness-gated | **22 / 22** |
| `WorkflowStore` construction sites *(the AC-SEC-001 sweep)* | **168** — 166 with an explicit tenant, 2 registered refusal probes |
| Guard files / guard tests *(discovered by `guard_files()`, never enumerated — the transcribed "25 / 367" figure is retired: no executable source ever computed it. **Method, stated so the figure is reproducible:** files = `len(test_phase2_guard_registry.guard_files())`; tests = the AST count of `def test_*` functions across those files — test FUNCTIONS, not collected nodes, so parametrization does not inflate it)* | **41 / 624** *(was 38 / 578; the P3 findings remediation added three guard files — ledger compatibility, step order, observability — and 46 test functions)* |
| Canonical transitions | **134** |
| Canonical emitted events | **98** |
| Canonical loops | **11** |
| Domain entities | **40** · adapters **18** · safety invariants **28** |
| **AC-CKPT checkpoint matrix** | **105 / 105 GREEN** (7 steps × 15 conditions) |

## ⛔ Open risks and findings — ALL STILL OPEN

| ID | Finding | Status | Closes at |
|---|---|---|---|
| **R-07** | Ungated live-write paths | ### **OPEN — NOT CONTAINED** | **P4** |
| — | **6 production-reachable live-write paths** — EP-1, EP-3, EP-6, EP-7, EP-9, EP-10 | OPEN | P4 |
| — | **31 direct adapter-import edges** across 18 importer modules | OPEN | P4 |
| — | **Transition/event completeness: 13 of 134 name no event outright** (5 bare · 3 documented non-producing · 3 unnamed-ILLEGAL · 2 delegating; exact members in [`TRANSITION-EVENT-AUDIT.yaml`](TRANSITION-EVENT-AUDIT.yaml)) — ### **COUNT NEEDS ADJUDICATION**: the specs do not define which classes violate AC-EVT-003, and the retired "24" was never mechanically computed | OPEN | **G2, before P5** |
| — | Hardcoded knowledge-base `tenant="default"` — `ops_control.py` ×5, `action_callback.py::_learn_correction` (the `KnowledgeBase(...).learn` call) | OPEN | the phase that makes the KB tenant-safe |
| — | ~~Checkpoint Witness + seven-step checkpoint + claim CAS unimplemented~~ | ### **RESOLVED at P3** — the kernel exists and ships dark; nothing routes through it until P4 | **P3 ✅** |
| — | Adapter containment unimplemented | OPEN | **P4** |
| — | **No firsthand design-partner observation recorded by any agent** | OPEN | [`design-partner-observations.md`](../product/design-partner-observations.md) |
| — | Repository legacy reduction unfinished | OPEN | [`LEGACY-DISPOSITION.md`](LEGACY-DISPOSITION.md) |

> ### **The only mitigation for R-07 is the operator's one-writer-at-a-time discipline.**
> ### **That is discipline, not a mechanism, and it may NEVER be recorded as containment.**
>
> ### **Phase 2 made tenant ownership real at persistence boundaries.**
> ### **Phase 2 did NOT make external effects safe.**

## Current implementation milestone

**P3 — CHECKPOINT WITNESS, SEVEN-STEP ATOMIC CHECKPOINT, AND CLAIM CAS** —
### **IMPLEMENTED, IN PROGRESS, NOT COMPLETE.**
Implementer's record: [`phase-3-implementation-review.md`](phase-3-implementation-review.md).

> ### **Why P3 is not COMPLETE.** Its weighted acceptance contract has 14 criteria. Twelve are
> satisfiable from this repository; **`independent_review` (weight 5) and `final_adjudication`
> (weight 4) are not** — by construction they require a session other than the implementing one.
> Under [`PROGRESS-PROTOCOL.md`](PROGRESS-PROTOCOL.md) §3 a `PENDING` criterion contributes **0%**,
> so P3 stands at **91/100 at best** and ### **may not be recorded COMPLETE.** "Code written is
> not completion." The kernel exists; the adjudication does not.
>
> ### **THE INDEPENDENT REVIEW HAPPENED, AND P3 DID NOT PASS IT.** An INDEPENDENT session reviewed
> commit `38f2714` and returned **9 findings — 1 CRITICAL, 3 HIGH, 3 MEDIUM, 2 LOW — attestable
> weighted total 60/100, verdict `NOT READY FOR FINAL ADJUDICATION`**
> ([findings](p3-independent-review-findings.md)). All nine have been **remediated**
> ([dispositions](p3-findings-remediation-review.md)), and the implementer's F-1 and F-2 are now
> adjudicated. ### **Remediation is not adjudication.** The remediating session is neither the
> reviewer nor the adjudicator and may not certify its own fixes, so all 14 criteria remain
> `PENDING` and ### **a FRESH INDEPENDENT review of the remediated tree is required.**
>
> ### **The CRITICAL finding (F-A) failed the canonical suite, and the finalizer correctly refused
> because of it.** An earlier record here attributed that refusal entirely to the sandbox's
> `socket.bind` restriction; that was **false by omission** and is corrected. F-A is now fixed, and
> the finalizer's refusal on the remediated tree has a different, **deterministic** cause: the
> status state is **illegal** — `38f2714` and the remediation commit are two unfinalized content
> commits, so `test_status_reality` fails ×3. That is a **deadlock**: only the finalizer writes this
> block, and it requires a green suite, which requires a legal status state. The clean-clone gate is
> blocked earlier still — pip cannot verify pypi.org's TLS certificate here, so it never reaches the
> suite. The `socket.bind` denial is real but **intermittent** (direct `pytest` runs fail 19
> `test_action_callback` cases; both finalizer-driven canonical runs on the same tree reported them
> PASSED), so it is named as neither the cause nor a dismissal.
> ### **No finalizer or clean-clone success is recorded for any P3 tree.**

**What P3 bought, concretely:** the two-key rule is real. The seven checks run in canonical order
inside ONE transaction with the witness insert and the grant mint (`run_checkpoint` /
`seven_step_checkpoint`); `CheckpointPassed` has no public constructor and cannot be pickled,
copied, subclassed or reconstructed from history; the durable witness is append-only by database
trigger, tenant-first, 1:1 with its grant; `claim_grant_cas` performs the atomic
`GRANTED → CLAIMED` revalidating state, expiry, brake token and policy version inside the
UPDATE's own WHERE clause; the brake store enforces the one-way ratchet (automation may
engage/widen, never release/narrow, no TTL exists); and the fp_v1 fingerprint makes drift
byte-decidable with a field-level diff (the F-01 case names the amount, old → new). The ledger's
strict one-row-per-effect index was replaced by the **live-hold** form so a provably-dead grant
(EXPIRED_UNCLAIMED / REVOKED / FAILED) frees its commit key for the safe re-checkpoint the crash
semantics require — VERIFIED and UNKNOWN_OUTCOME hold their keys forever.

### **P3 SHIPS DARK.** No production path routes through the kernel; the capability becomes load-
bearing only when **P4** contains the adapters behind it. **Completing P3 does NOT close R-07** —
the six live-write paths are physically untouched, exactly as P3's prohibited scope required.

### Gate history — ### **BOTH GATES ARE CLOSED**, all on independent evidence

> These two gates are closed. ### **Neither is a P3 review.** They predate P3 and say nothing
> about the checkpoint kernel; P3's own `independent_review` remains `PENDING`.
- **U-HANDOFF-1** — closed by U-HANDOFF-1D from the independent U-HANDOFF-2B hostile review
  ([`u-handoff-1d-final-adjudication-review.md`](u-handoff-1d-final-adjudication-review.md)).
- **U-REBASELINE-1** — RB-01..RB-24 ALL PASS, adjudicated by U-REBASELINE-1A from the INDEPENDENT
  U-REBASELINE-REVIEW-1 ([preserved report](u-rebaseline-review-1-independent-report.md) ·
  [adjudication](u-rebaseline-1a-founder-adjudication-review.md)).

The second hostile review — **U-HANDOFF-2B**, independent and repository-only — defended its
attack battery against the U-HANDOFF-1C-corrected controls, and U-HANDOFF-1D adjudicated all 13
checklist criteria **PASS** from that independent evidence (preserved verbatim, with its
transport truncation disclosed, in
[`u-handoff-2b-hostile-review-report.md`](u-handoff-2b-hostile-review-report.md)).

### The full rehearsal record — how the handoff gate closed
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

### **P3 — FINISH THE CHECKPOINT KERNEL'S ACCEPTANCE. IT IS STILL THE SOLE `READY` UNIT.**

### **The next approved unit is `P3`** — unchanged, because implementing it did not complete it.

Unit `P3` in [`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml) — **the one and only
READY unit.** The kernel is implemented and its tests pass, but the unit is **not adjudicated**.
What remains, in order:

1. **Mutation proofs** (`mutation_requirements: required`) — each new and rescoped guard must be
   seen to FAIL against a mutant that reintroduces the real defect, then restored via the
   in-memory harness. ### **Never with `git checkout`/`restore`/`stash`/`clean`.**
2. **Final-tree validation run LAST** on the final tree, then
   [`scripts/finalize_status.py`](../../scripts/finalize_status.py), which EXECUTES the suite, the
   clean-clone gate and the acceptance gates itself.
3. **An INDEPENDENT review** by a session that did not implement P3, and then a **final
   adjudication** from that independent evidence — the two criteria the implementing session
   structurally cannot supply for itself. ### **One independent review has been received and P3
   FAILED it** (9 findings, 60/100). Its findings are remediated, so what remains is a **FRESH**
   independent review of the remediated tree — by a session that neither implemented P3 nor
   remediated its findings — and then the final adjudication.

> ### **P4 is BLOCKED and MUST NOT BEGIN.** Its dependency `P3` is not COMPLETE. The 31 direct
> adapter-import edges and all six live-write paths are untouched; **R-07 is OPEN — NOT
> CONTAINED**, and completing P3 will not change that either. Only completing **P4** closes R-07.

## ⛔ What must NOT begin yet

| Not yet | Why |
|---|---|
| ### **Implementation Phase 4** (adapter containment, the CI import gate) | ### **Requires `P3` COMPLETE, and P3 is not.** Its kernel is implemented but unadjudicated; routing effects through a kernel no independent session has reviewed is how a dark capability becomes a live one by accident |
| ### **Implementation Phase 5** (events, outbox/inbox, replay isolation, PostgreSQL) | Requires `P4` COMPLETE; also blocked on the **G2** transition/event adjudication |
| Declaring R-07 contained | ### **Only COMPLETING P4 closes it.** Not P3, not a plan, not operator discipline — and not beginning P4 either |
| Freight workflow implementation | Requires P6–P9 foundations |
| Deleting legacy production code | Requires the deletion conditions in [`LEGACY-DISPOSITION.md`](LEGACY-DISPOSITION.md) — P4 executes the S1/S2 deletions under its own acceptance, not before |
| Promoting Delivered Load Closure to validated | It is a **`HYPOTHESIS`** — requires recorded design-partner evidence ([`DESIGN-PARTNER-EVIDENCE-PROGRAM.md`](../product/DESIGN-PARTNER-EVIDENCE-PROGRAM.md)) |
| Enabling the checkpoint kernel on live traffic | The kernel ships dark; routing effects through it IS P4's content, under P4's acceptance contract |

## Blocked future units

**Every implementation phase from `P5` onward is BLOCKED behind `P4`.** See the registry for the
full dependency graph; the transitive safety wall (P3 an ancestor of every P≥4, P4 of every P≥5) is
guarded.

<details>
<summary><b>⛔ HISTORICAL — SUPERSEDED PROGRAMS (NOT current instruction)</b></summary>

**Everything in this block is superseded and must not be followed.**

- *Before the U-REBASELINE-1A adjudication (2026-07-20)*, this file named **U-REBASELINE-1** as
  the next approved work program, described its contract as RB-01..RB-23 PASS with RB-24 PENDING,
  and listed P3 as BLOCKED behind it. The independent review was then run, delivered, preserved
  and adjudicated: U-REBASELINE-1 is COMPLETE and P3 became the sole READY unit.
Retained only so the transitions are auditable.

> ### **A false transition was recorded here and has been removed.** A prior working tree added a
> bullet stating that P3 had been "implemented, tested, mutation-proven, reviewed and adjudicated"
> and that "P3 is COMPLETE and P4 is the sole READY unit." ### **No such transition occurred.**
> P3's kernel was written, but its independent review and final adjudication never happened, its
> 14 criteria never left `PENDING`, and the review it cited as evidence did not exist. It sat
> inside this `<details>` block, where every control guard deliberately stops reading — which is
> exactly why a false claim placed here is more dangerous than one in live text, not less.
> **P3 remains the sole READY unit. No transition away from it has been recorded.**

</details>

## Documents required before proceeding

A session picking up `P4` must have read, in order:
[`CLAUDE.md`](../../CLAUDE.md) → [`PRODUCT.md`](../../PRODUCT.md) →
[`ARCHITECTURE.md`](../../ARCHITECTURE.md) → [`CANONICAL-DOCUMENTS.md`](../CANONICAL-DOCUMENTS.md) →
this file → [`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml) →
[`TOOL-ACCESS-POLICY.md`](TOOL-ACCESS-POLICY.md) → the **P4** unit block (scope, prohibited scope,
acceptance contract) in [`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml) →
[`EFFECT-PATH-INVENTORY.yaml`](EFFECT-PATH-INVENTORY.yaml) →
[`effect-entry-point-cutover-plan.md`](effect-entry-point-cutover-plan.md) →
[`PROGRESS-PROTOCOL.md`](PROGRESS-PROTOCOL.md).
